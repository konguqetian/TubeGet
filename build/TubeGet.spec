# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置。

本 spec 只应由对应平台的 runner 执行（PyInstaller 不支持交叉编译）：
  macOS Intel        -> macos-15-intel
  macOS Apple Silicon-> macos-14
  Windows x64        -> windows-latest
"""

import os
import re
import shutil
import sys
from pathlib import Path

import certifi
import imageio_ffmpeg

ROOT = Path(SPECPATH).parent
FFMPEG_SRC = Path(imageio_ffmpeg.get_ffmpeg_exe())

# imageio-ffmpeg 的二进制名带平台与版本后缀（如 ffmpeg-macos-aarch64-v7.1），
# 运行时按规范名 ffmpeg / ffmpeg.exe 查找，因此先复制成固定名再打包。
FFMPEG_NAME = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
FFMPEG = ROOT / "build" / ".cache" / FFMPEG_NAME
FFMPEG.parent.mkdir(parents=True, exist_ok=True)
if not FFMPEG.exists() or FFMPEG.stat().st_size != FFMPEG_SRC.stat().st_size:
    shutil.copy2(FFMPEG_SRC, FFMPEG)

_src = (ROOT / "src" / "version.py").read_text(encoding="utf-8")
APP_NAME = re.search(r'APP_NAME\s*=\s*"([^"]+)"', _src).group(1)
APP_VERSION = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', _src).group(1)
APP_ID = re.search(r'APP_ID\s*=\s*"([^"]+)"', _src).group(1)

ICON = None
if sys.platform == "darwin":
    _p = ROOT / "resources" / "icon.icns"
    ICON = str(_p) if _p.exists() else None
elif os.name == "nt":
    _p = ROOT / "resources" / "icon.ico"
    ICON = str(_p) if _p.exists() else None

EXCLUDES = [
    "tkinter", "numpy", "pandas", "scipy", "matplotlib", "PIL",
    "IPython", "pytest", "sphinx", "notebook", "imageio_ffmpeg",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQml", "PySide6.QtQmlCore", "PySide6.QtQmlNetwork", "PySide6.QtQmlModels",
    "PySide6.QtQmlWorkerScript", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
    "PySide6.QtQuickControls2", "PySide6.QtQuick3D", "PySide6.Qt3DCore",
    "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DAnimation",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtTest", "PySide6.QtUiTools",
    "PySide6.QtSql", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
]

a = Analysis(
    [str(ROOT / "src" / "main.py")],
    pathex=[str(ROOT / "src")],
    binaries=[(FFMPEG, "bin")],
    # 必须随包分发根证书：打包后自带 OpenSSL 的默认证书路径是构建机上的路径，
    # 在用户机器上不存在，会导致所有 HTTPS 请求 CERTIFICATE_VERIFY_FAILED。
    datas=[(certifi.where(), "certifi")],
    hiddenimports=["PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "certifi"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

info_plist = {
    "CFBundleName": APP_NAME,
    "CFBundleDisplayName": APP_NAME,
    "CFBundleIdentifier": APP_ID,
    "CFBundleShortVersionString": APP_VERSION,
    "CFBundleVersion": APP_VERSION,
    "NSHighResolutionCapable": True,
    "NSRequiresAquaSystemAppearance": False,
    "LSApplicationCategoryType": "public.app-category.utilities",
}

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=ICON,
        bundle_identifier=APP_ID,
        version=APP_VERSION,
        info_plist=info_plist,
    )
