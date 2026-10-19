"""配置持久化（JSON，存放在用户数据目录）。"""

from __future__ import annotations

import json
from pathlib import Path

from platform_paths import user_data_dir

DEFAULTS = {
    "output_dir": "",
    "format_preset": "bestvideo_mp4",
    "custom_format": "",
    "audio_format": "mp3",
    "subtitle_mode": "none",           # none | file | embed
    "subtitle_langs": "zh-Hans,zh-Hant,en",
    "playlist": False,
    "concurrency": 4,
    "rate_limit": "",                  # 例如 5M
    "proxy": "",
    "cookies_browser": "",             # 留空 | safari | chrome | edge | firefox
    "embed_metadata": True,
    "embed_thumbnail": False,
    "keep_engine_updated": True,       # 启动时自动升级 yt-dlp
    "update_repo": "",                 # 应用外壳自更新仓库 owner/repo
    "ffmpeg_path": "",
    "ssl_mode": "compat",              # strict | compat | off（见 net.SSL_MODES）
}

FORMAT_PRESETS = {
    "bestvideo_mp4": ("最佳画质视频（合并为 MP4）", "bv*+ba/best"),
    "bestvideo_any": ("最佳画质视频（保持原始容器）", "bv*+ba/best"),
    "best_single": ("单文件最佳（≤1080p，体积更小）", "best[height<=1080]"),
    "audio_only": ("仅提取音频", None),
    "custom": ("自定义格式串", None),
}

_LABEL_TO_KEY = {v[0]: k for k, v in FORMAT_PRESETS.items()}


class Config:
    """单例式配置对象。"""

    _instance: "Config | None" = None

    def __init__(self, path: Path | None = None):
        self.path = path or (user_data_dir() / "config.json")
        self.data = dict(DEFAULTS)
        self.load()
        Config._instance = self

    @classmethod
    def global_instance(cls) -> "Config":
        if cls._instance is None:
            cls()
        return cls._instance

    def load(self) -> None:
        try:
            if self.path.exists():
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                for k, v in loaded.items():
                    if k in DEFAULTS:
                        self.data[k] = v
        except Exception:
            pass

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def get(self, key: str, default=None):
        return self.data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value) -> None:
        self.data[key] = value
        self.save()

    # 便捷属性
    @property
    def output_dir(self) -> Path:
        d = self.get("output_dir") or ""
        return Path(d).expanduser() if d else _default_output_dir()


def _default_output_dir() -> Path:
    from platform_paths import downloads_dir

    return downloads_dir() / "TubeGet"
