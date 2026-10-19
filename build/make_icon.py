"""生成应用图标：PNG → .icns（macOS）/ .ico（Windows）。

用法：python build/make_icon.py <输出目录>
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QPointF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)


def draw_icon(size: int = 1024) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)

    # 圆角底
    m = size * 0.06
    r = size * 0.22
    path = QPainterPath()
    path.addRoundedRect(m, m, size - 2 * m, size - 2 * m, r, r)
    grad = QLinearGradient(QPointF(0, 0), QPointF(size, size))
    grad.setColorAt(0.0, QColor("#3b6ef0"))
    grad.setColorAt(1.0, QColor("#7b4bf0"))
    p.fillPath(path, grad)

    # 托盘横线
    cx, cy = size / 2, size / 2
    pen = QPen(QColor("#ffffff"))
    pen.setCapStyle(Qt.RoundCap)
    pen.setWidthF(size * 0.062)
    p.setPen(pen)
    tray_w = size * 0.40
    tray_y = cy + size * 0.20
    p.drawLine(QPointF(cx - tray_w / 2, tray_y), QPointF(cx + tray_w / 2, tray_y))

    # 向下箭头
    stroke = size * 0.058
    pen.setWidthF(stroke)
    p.setPen(pen)
    top_y = cy - size * 0.20
    bot_y = tray_y - stroke * 0.9
    p.drawLine(QPointF(cx, top_y), QPointF(cx, bot_y))
    head = size * 0.115
    p.drawLine(QPointF(cx, bot_y), QPointF(cx - head, bot_y - head))
    p.drawLine(QPointF(cx, bot_y), QPointF(cx + head, bot_y - head))

    p.end()
    return img


def write_icns(png: Path, out: Path) -> bool:
    """纯 Python 生成 .icns（不依赖 iconutil，便于跨平台 CI）。

    条目类型与像素尺寸（载荷为 PNG）：
      ic11=32  ic12=64  ic07=128  ic08=256  ic13=256  ic09=512  ic14=512  ic10=1024
    """
    entries = [
        (b"ic11", 32),
        (b"ic12", 64),
        (b"ic07", 128),
        (b"ic08", 256),
        (b"ic13", 256),
        (b"ic09", 512),
        (b"ic14", 512),
        (b"ic10", 1024),
    ]
    src = QImage(str(png))
    body = bytearray()
    for tag, s in entries:
        img = src.scaled(s, s, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        buf = QByteArray()
        stream = QBuffer(buf)
        stream.open(QBuffer.OpenModeFlag.WriteOnly)
        img.save(stream, "PNG")
        stream.close()
        data = bytes(buf)
        body += tag + struct.pack(">I", 8 + len(data)) + data

    out.write_bytes(b"icns" + struct.pack(">I", 8 + len(body)) + bytes(body))
    return out.exists() and out.stat().st_size > 1000


def write_ico(png: Path, out: Path) -> None:
    """写入 ICO 容器（内嵌 PNG，Windows Vista+ 支持）。"""
    raw = png.read_bytes()
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(raw), 6 + 16)
    out.write_bytes(header + entry + raw)


def main() -> int:
    outdir = Path(sys.argv[1] if len(sys.argv) > 1 else "resources")
    outdir.mkdir(parents=True, exist_ok=True)

    # 无显示环境（CI）下回退到 offscreen 平台
    if sys.platform not in ("darwin", "win32"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QGuiApplication(sys.argv)
    img = draw_icon(1024)
    png = outdir / "icon.png"
    img.save(str(png), "PNG")

    if sys.platform == "darwin":
        ok = write_icns(png, outdir / "icon.icns")
        print("icns:", "OK" if ok else "FAILED")
    write_ico(png, outdir / "icon.ico")
    print("ico: OK")
    print("png:", png)
    return 0


if __name__ == "__main__":
    sys.exit(main())
