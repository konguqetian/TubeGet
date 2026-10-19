"""应用外壳自更新：从自建仓库的 GitHub Release 拉取安装包。"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from platform_paths import downloads_dir, machine_arch, platform_key
from version import RELEASE_ASSET

API = "https://api.github.com/repos/{repo}/releases/latest"


def _ua() -> str:
    from version import APP_NAME, APP_VERSION

    return f"{APP_NAME}/{APP_VERSION}"


def _get_json(url: str) -> dict:
    req = urllib.request.Request(
        url, headers={"User-Agent": _ua(), "Accept": "application/vnd.github+json"}
    )
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


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
    def __init__(self, repo: str, current_version: str):
        self.repo = (repo or "").strip().strip("/")
        self.current_version = current_version

    @property
    def configured(self) -> bool:
        return "/" in self.repo

    def latest(self) -> dict | None:
        """返回最新发布信息；未配置仓库时返回 None。"""
        if not self.configured:
            return None
        data = _get_json(API.format(repo=self.repo))
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
        req = urllib.request.Request(info["url"], headers={"User-Agent": _ua()})
        tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if tok:
            req.add_header("Authorization", f"Bearer {tok}")
        with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        return dest
