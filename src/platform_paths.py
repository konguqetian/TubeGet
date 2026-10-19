"""跨平台目录与运行时路径解析。"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from shutil import which

APP_NAME = "TubeGet"


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def bundle_dir() -> Path:
    """打包后的一体化资源目录（PyInstaller 的 _MEIPASS）。"""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def app_dir() -> Path:
    """可执行文件所在目录。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_data_dir() -> Path:
    """可写的用户数据目录（存放引擎、配置、日志）。"""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    p = base / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def bundled_ffmpeg() -> Path | None:
    """定位随包发行的 ffmpeg 静态二进制，找不到返回 None。

    PyInstaller 在不同平台/版本下安放位置有差异：
      - Windows/Linux onedir：<dist>/bin/ffmpeg[.exe]
      - macOS BUNDLE：Contents/Frameworks/bin/ffmpeg[.exe]（即 _MEIPASS/bin）
    另外历史版本里二进制名带平台与版本后缀（ffmpeg-macos-aarch64-v7.1），
    因此除精确名外再做一次有界递归兜底。
    """
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"

    candidates: list[Path] = [bundle_dir() / "bin" / name]

    if is_frozen():
        # macOS .app 下 _MEIPASS 指向 Contents/Frameworks，可执行文件在 Contents/MacOS
        exe_dir = Path(sys.executable).resolve().parent
        contents = exe_dir.parent
        candidates += [
            contents / "MacOS" / "bin" / name,
            contents / "Frameworks" / "bin" / name,
            contents / "Resources" / "bin" / name,
        ]
    else:
        candidates.append(bundle_dir() / name)

    for c in candidates:
        if c.is_file():
            return c

    # 兜底：在 _MEIPASS 下有界递归找 ffmpeg*（1~3 层，避免扫整包）
    root = bundle_dir()
    if root.is_dir():
        for depth in (1, 2, 3):
            pattern = "/".join(["*"] * depth)
            for c in sorted(root.glob(f"{pattern}/ffmpeg*")):
                if c.is_file():
                    return c
    return None


def find_ffmpeg(custom_path: str | None = None) -> str | None:
    """优先级：用户自定义 > 随包 ffmpeg > 系统 PATH。"""
    if custom_path and Path(custom_path).exists():
        return str(Path(custom_path))
    b = bundled_ffmpeg()
    if b is not None:
        return str(b)
    return which("ffmpeg")


def machine_arch() -> str:
    m = platform.machine().lower()
    if m in ("x86_64", "amd64"):
        return "x86_64"
    if m in ("arm64", "aarch64"):
        return "arm64"
    return m


def platform_key() -> str:
    return "win32" if os.name == "nt" else sys.platform


def downloads_dir() -> Path:
    d = Path.home() / "Downloads"
    return d if d.exists() else Path.home()
