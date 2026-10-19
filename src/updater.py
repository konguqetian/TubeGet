"""应用外壳自更新：从自建仓库的 GitHub Release 拉取安装包。"""

from __future__ import annotations

import os
from pathlib import Path

import net
from platform_paths import downloads_dir, machine_arch, platform_key
from version import RELEASE_ASSET

API = "https://api.github.com/repos/{repo}/releases/latest"
SSL_MODES = ("strict", "compat", "off")


def _ua() -> str:
    from version import APP_NAME, APP_VERSION

    return f"{APP_NAME}/{APP_VERSION}"


def _headers() -> dict:
    h = {"User-Agent": _ua(), "Accept": "application/vnd.github+json"}
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def _parse_version(tag: str) -> tuple:
    t = tag.lstrip("v").split("-")[0]
    parts = []
    for p in t.split(".")[:3]:
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def current_asset_name() -> str | None:
    return RELEASE_ASSET.get((platform_key(), machine_arch()))


class AppUpdater:
    def __init__(self, repo: str, current_version: str,
                 proxy: str | None = None, ssl_mode: str = "compat"):
        self.repo = (repo or "").strip().strip("/")
        self.current_version = current_version
        self.proxy = (proxy or "").strip()
        self.ssl_mode = ssl_mode if ssl_mode in SSL_MODES else "compat"

    @property
    def configured(self) -> bool:
        return "/" in self.repo

    def latest(self) -> dict | None:
        """返回最新发布信息；未配置仓库时返回 None。"""
        if not self.configured:
            return None
        data = net.get_json(
            API.format(repo=self.repo), timeout=30, headers=_headers(),
            proxy=self.proxy, ssl_mode=self.ssl_mode,
        )
        want = current_asset_name()
        asset = None
        for a in data.get("assets", []):
            if want and a["name"] == want:
                asset = a
                break
        return {
            "tag": data.get("tag_name", ""),
            "notes": (data.get("body") or "").strip(),
            "asset": (asset or {}).get("name"),
            "url": (asset or {}).get("browser_download_url"),
            "size": (asset or {}).get("size", 0),
            "html_url": data.get("html_url", ""),
        }

    def available_update(self) -> dict | None:
        try:
            info = self.latest()
        except Exception:
            return None
        if not info:
            return None
        if _parse_version(info["tag"]) > _parse_version(self.current_version) and info["url"]:
            return info
        return None

    def download(self, info: dict, progress=None) -> Path:
        dest = downloads_dir() / info["asset"]
        net.download(
            info["url"], dest, progress=progress, timeout=300,
            headers=_headers(), proxy=self.proxy, ssl_mode=self.ssl_mode,
        )
        return dest
