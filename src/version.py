"""应用版本信息。"""

APP_NAME = "TubeGet"
APP_ID = "com.tubeget.app"
APP_VERSION = "1.0.1"
APP_AUTHOR = "TubeGet"

# 应用外壳的自更新仓库（GitHub "owner/repo"）。
# 留空表示未配置，可在「设置」中填写；引擎更新不依赖此项。
DEFAULT_UPDATE_REPO = ""

ENGINE_REPO = "yt-dlp/yt-dlp"

# GitHub Release 产物命名（须与 .github/workflows/release.yml 保持一致）
# 说明：Windows 只发布 x64 安装包；Windows on ARM 通过内置的 x64 模拟层运行该包，
# 因此 arm64 同样匹配 x64 产物，避免更新检查找不到文件。
_WIN_SETUP = f"{APP_NAME}-Windows-x64-Setup.exe"

RELEASE_ASSET = {
    ("darwin", "x86_64"): f"{APP_NAME}-macOS-Intel.dmg",
    ("darwin", "arm64"): f"{APP_NAME}-macOS-AppleSilicon.dmg",
    ("win32", "x86_64"): _WIN_SETUP,
    ("win32", "arm64"): _WIN_SETUP,
    ("linux", "x86_64"): f"{APP_NAME}-Linux-x64.tar.gz",
    ("linux", "arm64"): f"{APP_NAME}-Linux-ARM64.tar.gz",
}
