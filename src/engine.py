"""yt-dlp 引擎管理：安装、版本检查、自动升级。

更新源为官方仓库 yt-dlp/yt-dlp 的 GitHub Release，按当前平台选取对应产物。
所有网络请求都走 net 层（显式 CA 证书 + 代理支持）。
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import net
from platform_paths import machine_arch, user_data_dir
from version import ENGINE_REPO

API_LATEST = f"https://api.github.com/repos/{ENGINE_REPO}/releases/latest"
UA = "TubeGet"

SSL_MODES = ("strict", "compat", "off")


def _token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def asset_for_platform() -> str:
    """当前平台对应的 yt-dlp 发布产物名。"""
    if sys.platform == "darwin":
        return "yt-dlp_macos"
    if os.name == "nt":
        return "yt-dlp_arm64.exe" if machine_arch() == "arm64" else "yt-dlp.exe"
    return "yt-dlp_linux_aarch64" if machine_arch() == "arm64" else "yt-dlp_linux"


class Engine:
    def __init__(self, proxy: str | None = None, ssl_mode: str = "compat"):
        self.data_dir = user_data_dir()
        self.bin_dir = self.data_dir / "bin"
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        self.exe = self.bin_dir / ("yt-dlp.exe" if os.name == "nt" else "yt-dlp")
        self.proxy = (proxy or "").strip()
        self.ssl_mode = ssl_mode if ssl_mode in SSL_MODES else "compat"

    # ---------- 状态 ----------
    @property
    def installed(self) -> bool:
        return self.exe.exists()

    def version(self) -> str:
        if not self.installed:
            return ""
        try:
            out = subprocess.run(
                [str(self.exe), "--version"], capture_output=True, text=True, timeout=60
            )
            return out.stdout.strip().splitlines()[0].strip() if out.stdout else ""
        except Exception:
            return ""

    # ---------- 远程查询 ----------
    def latest_release(self) -> dict:
        """返回 {'tag':..., 'url':..., 'name':..., 'size':...}"""
        headers = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
        tok = _token()
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
        data = net.get_json(
            API_LATEST, timeout=30, headers=headers, proxy=self.proxy, ssl_mode=self.ssl_mode
        )
        want = asset_for_platform()
        for a in data.get("assets", []):
            if a["name"] == want:
                return {
                    "tag": data.get("tag_name", "").lstrip("v"),
                    "url": a.get("browser_download_url") or a.get("url"),
                    "name": a["name"],
                    "size": a.get("size", 0),
                }
        raise RuntimeError(f"未在最新发布中找到适用于本平台的产物：{want}")

    def has_update(self) -> tuple[bool, str, str]:
        """(是否有更新, 本地版本, 远端版本)"""
        local = self.version()
        try:
            rel = self.latest_release()
        except Exception:
            return (False, local, "")
        return (bool(local) and rel["tag"] != local, local, rel["tag"])

    # ---------- 下载安装 ----------
    def install_or_update(self, progress=None, log=print) -> str:
        """下载并替换引擎，返回安装后的版本号。"""
        rel = self.latest_release()
        log(f"正在下载 {rel['name']}（{rel['tag']}）…")
        tmp = self.exe.with_suffix(self.exe.suffix + ".new")
        self._download(rel["url"], tmp, progress)

        tmp.chmod(tmp.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        _strip_quarantine(tmp)

        # 冒烟校验
        try:
            out = subprocess.run([str(tmp), "--version"], capture_output=True, text=True, timeout=60)
            v = out.stdout.strip().splitlines()[0].strip() if out.stdout else ""
        except Exception as e:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"下载的引擎无法执行：{e}") from e

        if os.name == "nt":
            old = self.exe.with_suffix(self.exe.suffix + ".old")
            if self.exe.exists():
                self.exe.replace(old) if not old.exists() else old.unlink(missing_ok=True)
        self.exe.unlink(missing_ok=True)
        tmp.replace(self.exe)
        _strip_quarantine(self.exe)
        log(f"引擎已更新至 {v}")
        return v

    def ensure(self, progress=None, log=print) -> str:
        if not self.installed:
            return self.install_or_update(progress, log)
        return self.version()

    def _download(self, url: str, dest: Path, progress=None) -> None:
        headers = {"User-Agent": UA}
        tok = _token()
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
        net.download(
            url, dest, progress=progress, timeout=180,
            headers=headers, proxy=self.proxy, ssl_mode=self.ssl_mode,
        )


def _strip_quarantine(path: Path) -> None:
    """macOS：尽量移除隔离属性，避免 Gatekeeper 拦截下载得到的二进制。"""
    if sys.platform != "darwin":
        return
    import shutil

    if shutil.which("xattr"):
        try:
            subprocess.run(
                ["xattr", "-d", "com.apple.quarantine", str(path)],
                capture_output=True,
                timeout=10,
            )
        except Exception:
            pass
