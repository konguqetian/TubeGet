# TubeGet

基于 [yt-dlp](https://github.com/yt-dlp/yt-dlp) 的跨平台视频下载器，带图形界面与双通道自动更新。

**下载（v1.0.1）**：https://github.com/konguqetian/TubeGet/releases/latest

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
- 启动时默认自动检查并升级引擎（可在「应用 → 更新与网络设置」关闭）。
- 应用外壳更新：菜单「更新 → 检查应用更新」，下载安装包到下载目录后手动安装。

### 配置应用自更新仓库

仓库已就位：`konguqetian/TubeGet`。

1. 在应用内打开「应用 → 更新与网络设置」，填入 `konguqetian/TubeGet`。
2. 确保该仓库的 Release 中包含本平台产物（CI 会自动生成）。
3. 应用会按平台匹配产物名：macOS Intel → `-macOS-Intel.dmg`，Apple Silicon → `-macOS-AppleSilicon.dmg`，
   Windows → `-Windows-x64-Setup.exe`。

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
| macOS Intel | Intel Mac，或 GitHub Actions `macos-15-intel` |
| macOS Apple Silicon | Apple Silicon Mac，或 GitHub Actions `macos-14` |
| Windows x64 | Windows 机器，或 GitHub Actions `windows-latest` |

> **关于 Intel runner**：`macos-13` 镜像已于 2025-12-04 被 GitHub 退役，使用该标签的作业会永久停留在
> 排队状态。Intel 现用 `macos-15-intel`，该标签计划支持到 2027-08；之后 GitHub Actions 将不再提供
> x86_64 macOS runner（Apple 已停止支持 Intel 架构）。届时建议只发 Apple Silicon 版。

### 推荐：用 GitHub Actions 一次出三个版本

推送到 `main` 即自动触发；或手动：

```bash
git tag v1.0.0 && git push origin v1.0.0
```

或到仓库页面 → Actions → **Release** → `Run workflow`，填入 tag 后手动触发。

工作流会并行跑三个 runner，产出三个安装包并自动创建 Release（发布步骤幂等，tag 已存在则跳过）。

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

## 5. 网络与证书

### 为什么需要专门处理证书

PyInstaller 打包会带入**构建机上**的 OpenSSL，其默认根证书路径形如
`/Library/Frameworks/Python.framework/.../cert.pem`，在用户机器上并不存在。
于是 `ssl` 默认上下文一张根证书都加载不到，所有 HTTPS 请求都会报
`CERTIFICATE_VERIFY_FAILED`——包括下载引擎本身。

因此应用做了三件事：

1. **随包分发 certifi 根证书**（`build/TubeGet.spec` 的 `datas`），
   并显式用它构造 SSL 上下文（`src/net.py`）；
2. **自动兼容模式**（默认）下额外合并系统信任库：macOS 读
   `/private/etc/ssl/cert.pem` 并从钥匙串导出用户安装的证书，
   Windows 读 `ROOT`/`CA` 存储——从而兼容 Clash、Surge 等本地代理的自签 CA；
3. 下载引擎时把同一份证书通过 `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE`
   传给 yt-dlp 子进程，视频下载链路同样受益。

证书校验模式在「应用 → 更新与网络设置 → 证书校验」中切换：
`严格` / `自动兼容（推荐）` / `关闭校验（不安全）`。

### 排障

引擎下载失败时，先用 **「帮助 → 网络诊断」** 看哪一步是红的：

| 现象 | 处理 |
|---|---|
| `CERTIFICATE_VERIFY_FAILED` | 证书校验切到「自动兼容」；确认系统时间正确 |
| 连接超时 / 重置 | 在「高级选项 → 代理」填代理地址，如 `http://127.0.0.1:7890` |
| 代理环境下浏览器能开 YouTube 但应用不行 | 同上填代理；代理软件若是 TUN/增强模式可改用系统代理模式 |
| GitHub API 报 403 / 限流 | 匿名调用限 60 次/小时，设置环境变量 `GITHUB_TOKEN` |

---

## 6. ffmpeg

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
│   ├── net.py             网络层：显式 CA 证书、系统信任库合并、代理
│   ├── config.py          配置持久化
│   ├── platform_paths.py  跨平台路径解析
│   └── version.py         版本与发布产物命名
├── build/
│   ├── TubeGet.spec       PyInstaller 配置
│   ├── make_icon.py       图标生成（PNG / icns / ico）
│   ├── build_mac.sh       macOS 打包 + DMG
│   ├── build_win.bat      Windows 打包
│   ├── installer.iss      Inno Setup 安装脚本
│   └── languages/         官方中文语言包（vendored，避免依赖 runner 安装内容）
├── resources/             图标资源
└── .github/workflows/release.yml   三平台 CI
```

---

## 7. 使用提示

- 批量下载：URL 输入框每行一个地址。
- 会员 / 年龄限制内容：在「高级选项 → Cookies 来源」选择你的浏览器，复用登录态。
- 仅提取音频用于剪辑参考：格式选「仅提取音频」，音频格式可选 `wav`。
- 代理：YouTube 被墙或走本地代理时，在「高级选项 → 代理」填写地址（如 `http://127.0.0.1:7890`），
  对引擎下载与视频下载同时生效。
- 请仅下载你拥有权利或已获授权的内容，并遵守平台服务条款与当地法律。
