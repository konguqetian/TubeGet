# TubeGet

基于 [yt-dlp](https://github.com/yt-dlp/yt-dlp) 的跨平台视频下载器，带图形界面与双通道自动更新。

- **macOS Intel（x86_64）** → `TubeGet-macOS-Intel.dmg`
- **macOS Apple Silicon（arm64）** → `TubeGet-macOS-AppleSilicon.dmg`
- **Windows x64** → `TubeGet-Windows-x64-Setup.exe`（Windows on ARM 通过 x64 模拟层运行）

---

## 1. 更新机制（两套独立通道）

| 通道 | 更新源 | 是否需要自建仓库 |
|---|---|---|
| **下载引擎** | 官方 `yt-dlp/yt-dlp` 的 Release | 不需要，开箱即用 |
| **应用外壳** | 你自己的 GitHub 仓库 Release | 需要，见下方配置 |

- 引擎存放于用户数据目录（`~/Library/Application Support/TubeGet/bin/` 或 `%LOCALAPPDATA%\TubeGet\bin\`），
  与安装包解耦，因此**升级引擎不需要重装应用**。
- 启动时默认自动检查并升级引擎（可在「应用 → 更新源设置」关闭）。
- 应用外壳更新：菜单「更新 → 检查应用更新」，下载安装包到下载目录后手动安装。

### 配置应用自更新仓库

1. 把本项目推到你的 GitHub 仓库，例如 `yourname/TubeGet`。
2. 在应用内打开「应用 → 更新源设置」，填入 `yourname/TubeGet`。
3. 确保该仓库的 Release 中包含本平台产物（CI 会自动生成）。

> GitHub API 匿名调用限 60 次/小时。若需要更高配额，设置环境变量 `GITHUB_TOKEN`。

---

## 2. 本地开发与运行

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

首次启动会自动下载 yt-dlp 引擎。

---

## 3. 打包

### 关键约束

**PyInstaller 不支持交叉编译。** 每个平台的安装包必须在对应架构的机器上构建：

| 目标平台 | 构建环境 |
|---|---|
| macOS Intel | Intel Mac，或 GitHub Actions `macos-13` |
| macOS Apple Silicon | Apple Silicon Mac，或 GitHub Actions `macos-14` |
| Windows x64 | Windows 机器，或 GitHub Actions `windows-latest` |

### 推荐：用 GitHub Actions 一次出三个版本

```bash
git tag v1.0.0 && git push origin v1.0.0
```

或到仓库页面 → Actions → **Release** → `Run workflow`，填入 tag 后手动触发。

工作流会并行跑三个 runner，产出三个安装包并自动创建 Release。

### 本机手动打包

macOS：

```bash
pip install -r requirements.txt
bash build/build_mac.sh      # 产出 dist/TubeGet-macOS-<Intel|AppleSilicon>.dmg
```

Windows（PowerShell，需已安装 Inno Setup）：

```bat
build\build_win.bat          # 产出 dist\TubeGet-Windows-x64-Setup.exe
```

### 版本号

升级版本时同步修改两处：

- `src/version.py` → `APP_VERSION`
- `build/installer.iss` → `#define MyAppVersion`（CI 会自动同步此文件）

---

## 4. macOS 首次打开提示

未做 Developer ID 签名与公证，首次打开会被 Gatekeeper 拦截。两种方式：

- 右键点击 `TubeGet.app` → **打开** → 确认；
- 或终端执行：

```bash
xattr -cr /Applications/TubeGet.app
codesign --force --deep -s - /Applications/TubeGet.app
```

如需彻底免提示，可用 Apple Developer ID 签名并公证：在 `build/build_mac.sh` 中把
`codesign` 一行换成 `codesign --deep --force --options runtime -s "Developer ID Application: ..."`，
再用 `notarytool` 提交公证。

---

## 5. ffmpeg

音视频合并依赖 ffmpeg。安装包已内置静态 ffmpeg（来自 `imageio-ffmpeg`），
无需额外安装。若需换成系统版本，在「高级选项 → ffmpeg」中指定路径。

---

## 6. 目录结构

```
TubeGet/
├── src/
│   ├── main.py            应用入口
│   ├── ui.py              PySide6 图形界面
│   ├── worker.py          下载任务线程与进度解析
│   ├── engine.py          yt-dlp 引擎安装 / 版本检查 / 升级
│   ├── updater.py         应用外壳自更新
│   ├── config.py          配置持久化
│   ├── platform_paths.py  跨平台路径解析
│   └── version.py         版本与发布产物命名
├── build/
│   ├── TubeGet.spec       PyInstaller 配置
│   ├── make_icon.py       图标生成（PNG / icns / ico）
│   ├── build_mac.sh       macOS 打包 + DMG
│   ├── build_win.bat      Windows 打包
│   └── installer.iss      Inno Setup 安装脚本
├── resources/             图标资源
└── .github/workflows/release.yml   三平台 CI
```

---

## 7. 使用提示

- 批量下载：URL 输入框每行一个地址。
- 会员 / 年龄限制内容：在「高级选项 → Cookies 来源」选择你的浏览器，复用登录态。
- 仅提取音频用于剪辑参考：格式选「仅提取音频」，音频格式可选 `wav`。
- 请仅下载你拥有权利或已获授权的内容，并遵守平台服务条款与当地法律。
