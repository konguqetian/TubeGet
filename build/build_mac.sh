#!/usr/bin/env bash
# macOS 打包：产出 .app 与 .dmg
# 用法：PYTHON=<解释器> bash build/build_mac.sh
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
PY="${PYTHON:-python3}"

ARCH="$(uname -m)"
if [ "$ARCH" = "arm64" ]; then
  VARIANT="AppleSilicon"
else
  VARIANT="Intel"
fi

echo "==> 架构: $ARCH ($VARIANT)"

# 图标（CI 上 iconutil 可用，本地亦可用纯 Python 实现）
"$PY" build/make_icon.py resources || true

echo "==> PyInstaller 打包"
"$PY" -m PyInstaller build/TubeGet.spec --noconfirm --clean

APP="$ROOT/dist/TubeGet.app"

# ad-hoc 签名：保证本机可直接启动
if command -v codesign >/dev/null 2>&1; then
  echo "==> ad-hoc 签名"
  codesign --force --deep --timestamp=none -s - "$APP" || true
fi
xattr -cr "$APP" 2>/dev/null || true

echo "==> 生成 DMG"
DMG_ROOT="$ROOT/dist/dmgroot"
rm -rf "$DMG_ROOT"
mkdir -p "$DMG_ROOT"
cp -R "$APP" "$DMG_ROOT/"
ln -sf /Applications "$DMG_ROOT/Applications"

OUT="$ROOT/dist/TubeGet-macOS-$VARIANT.dmg"
rm -f "$OUT"
hdiutil create -volname "TubeGet" -srcfolder "$DMG_ROOT" -ov -format UDZO "$OUT"

echo "==> 完成: $OUT"
ls -lh "$OUT"
