"""下载任务线程：调用 yt-dlp 进程并解析进度输出。"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal

import net
from platform_paths import find_ffmpeg

PROGRESS_RE = re.compile(
    r"\[download\]\s+(?P<pct>[\d.]+)%\s+of\s+~?\s*"
    r"(?P<size>[\d.]+\s*[KMGT]?i?B)"
    r"(?:\s+at\s+(?P<speed>[\d.]+\s*[KMGT]?i?B/s))?"
    r"(?:\s+ETA\s+(?P<eta>[\d:]+))?"
)


class DownloadWorker(QThread):
    log = Signal(str)
    progress = Signal(float, str)
    item_started = Signal(str, int, int)  # 标题, 序号, 总数
    finished_all = Signal(int, int)  # 成功数, 失败数

    def __init__(self, engine_exe: str, urls: list[str], opts: dict, parent=None):
        super().__init__(parent)
        self.engine_exe = engine_exe
        self.urls = urls
        self.opts = opts
        self._proc: subprocess.Popen | None = None
        self._stopped = False

    # ---------- 参数构造 ----------
    def build_args(self, url: str) -> list[str]:
        o = self.opts
        args = [
            self.engine_exe,
            "--newline",
            "--ignore-config",
            "--no-playlist" if not o.get("playlist") else "--yes-playlist",
            "-P",
            str(o["output_dir"]),
            "-o",
            "%(title).180s [%(id)s].%(ext)s",
            "--no-part",
        ]

        ff = find_ffmpeg(o.get("ffmpeg_path") or "")
        if ff:
            args += ["--ffmpeg-location", ff]

        preset = o.get("format_preset")
        if preset == "audio_only":
            args += ["-x", "--audio-format", o.get("audio_format", "mp3"), "--audio-quality", "0"]
        elif preset == "custom":
            args += ["-f", o.get("custom_format") or "best"]
        else:
            fmt = o.get("format_string") or "bv*+ba/best"
            args += ["-f", fmt]
            if preset == "bestvideo_mp4":
                args += ["--merge-output-format", "mp4"]

        sub = o.get("subtitle_mode", "none")
        langs = (o.get("subtitle_langs") or "").strip()
        if sub != "none" and langs:
            args += ["--sub-langs", langs]
            if sub == "embed":
                args += ["--embed-subs"]
            else:
                args += ["--write-subs", "--write-auto-subs", "--convert-subs", "srt"]

        if o.get("embed_metadata"):
            args += ["--embed-metadata"]
        if o.get("embed_thumbnail"):
            args += ["--embed-thumbnail"]

        if o.get("concurrency", 1) > 1 and preset != "audio_only":
            args += ["-N", str(int(o["concurrency"]))]
        if o.get("rate_limit"):
            args += ["--limit-rate", str(o["rate_limit"]).strip()]
        if o.get("proxy"):
            args += ["--proxy", str(o["proxy"]).strip()]
        if o.get("cookies_browser"):
            args += ["--cookies-from-browser", str(o["cookies_browser"]).strip()]

        args.append(url)
        return args

    # ---------- 执行 ----------
    def run(self) -> None:
        ok = 0
        fail = 0
        total = len(self.urls)
        for idx, url in enumerate(self.urls, 1):
            if self._stopped:
                break
            self.item_started.emit(url.strip(), idx, total)
            self.progress.emit(0.0, f"({idx}/{total}) 准备中…")
            code = self._run_one(url.strip())
            if code == 0:
                ok += 1
            elif code == -99:
                break  # 被用户中止
            else:
                fail += 1
        self.finished_all.emit(ok, fail)

    def _run_one(self, url: str) -> int:
        args = self.build_args(url)
        self.log.emit("$ " + " ".join(f'"{a}"' if " " in a else a for a in args[1:]))

        creation = {}
        if sys.platform == "win32":
            creation = {"creationflags": subprocess.CREATE_NO_WINDOW}  # type: ignore[attr-defined]

        # 让引擎子进程复用同一份 CA 证书（含系统信任库），
        # 既能验证正规证书，也兼容本地代理软件的自签 CA。
        env = os.environ.copy()
        try:
            ca = net.effective_ca_bundle(self.opts.get("ssl_mode") or "compat")
            if ca and ca.is_file():
                env["SSL_CERT_FILE"] = str(ca)
                env["REQUESTS_CA_BUNDLE"] = str(ca)
                env["CURL_CA_BUNDLE"] = str(ca)
        except Exception:
            pass

        try:
            self._proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
                **creation,
            )
        except Exception as e:
            self.log.emit(f"[错误] 无法启动引擎：{e}")
            return -1

        assert self._proc.stdout is not None
        last_pct = 0.0
        for line in self._proc.stdout:
            if self._stopped:
                break
            line = line.rstrip("\n")
            if not line.strip():
                continue
            self.log.emit(line)

            m = PROGRESS_RE.search(line)
            if m:
                try:
                    last_pct = float(m.group("pct"))
                except ValueError:
                    continue
                detail = f"{m.group('size')}"
                if m.group("speed"):
                    detail += f" · {m.group('speed')}"
                if m.group("eta"):
                    detail += f" · ETA {m.group('eta')}"
                self.progress.emit(last_pct, detail)
            elif "[ExtractAudio]" in line or "[Merger]" in line or "[Fixup" in line or "[Embed" in line:
                self.progress.emit(100.0, "后处理中…")
            elif line.startswith("[download] Destination:"):
                self.log.emit("")

        if self._stopped:
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc.wait(timeout=10)
            return -99

        self._proc.wait()
        return int(self._proc.returncode or 0)

    def stop(self) -> None:
        self._stopped = True
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass
