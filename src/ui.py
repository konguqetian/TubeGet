"""TubeGet 图形界面。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from config import FORMAT_PRESETS, Config
from engine import Engine
from platform_paths import (
    find_ffmpeg,
    machine_arch,
    platform_key,
    user_data_dir,
)
from updater import AppUpdater, current_asset_name
from version import APP_NAME, APP_VERSION
from worker import DownloadWorker

QSS = """
QWidget { background:#1c1d21; color:#e6e7ea; font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif; font-size:13px; }
QMainWindow, QDialog { background:#1c1d21; }
QGroupBox { border:1px solid #2f3137; border-radius:8px; margin-top:14px; padding:12px 10px 10px 10px; font-weight:600; }
QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 6px; color:#9aa0aa; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox {
    background:#25262b; border:1px solid #35373d; border-radius:6px; padding:6px 8px; selection-background-color:#3b6ef0;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border:1px solid #3b6ef0; }
QPlainTextEdit#log { font-family:"SF Mono",Menlo,Consolas,monospace; font-size:12px; color:#c8ccd2; background:#16171a; }
QPushButton { background:#2f3137; border:1px solid #3a3d44; border-radius:6px; padding:7px 16px; }
QPushButton:hover { background:#383b42; }
QPushButton:disabled { color:#6b7078; background:#26272b; }
QPushButton#primary { background:#3b6ef0; border:1px solid #3b6ef0; color:#fff; font-weight:600; }
QPushButton#primary:hover { background:#4a7bf5; }
QPushButton#danger { background:#3a2b2b; border:1px solid #5a3a3a; }
QProgressBar { border:1px solid #35373d; border-radius:5px; background:#25262b; height:18px; text-align:center; }
QProgressBar::chunk { background:#3b6ef0; border-radius:4px; }
QStatusBar { background:#16171a; color:#9aa0aa; }
QCheckBox { spacing:8px; }
"""

FORMAT_ORDER = ["bestvideo_mp4", "bestvideo_any", "best_single", "audio_only", "custom"]
AUDIO_FORMATS = ["mp3", "m4a", "wav", "flac", "opus"]
SUBTITLE_MODES = [("none", "不下载"), ("file", "下载字幕文件（.srt）"), ("embed", "下载并内嵌字幕")]
COOKIE_BROWSERS = [("", "不使用"), ("safari", "Safari"), ("chrome", "Chrome"), ("edge", "Edge"), ("firefox", "Firefox"), ("brave", "Brave")]


def open_path(p: Path) -> None:
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(p)], check=False)
        elif os.name == "nt":
            os.startfile(str(p))  # noqa: S606
        else:
            subprocess.run(["xdg-open", str(p)], check=False)
    except Exception:
        pass


# ---------------------------------------------------------------- 后台任务线程
class EngineTask(QThread):
    message = Signal(str)
    progress = Signal(int, int)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.mode = mode  # ensure | update

    def run(self) -> None:
        try:
            eng = Engine()
            if self.mode == "ensure" and eng.installed:
                self.succeeded.emit(eng.version())
                return
            v = eng.install_or_update(progress=lambda d, t: self.progress.emit(d, t),
                                      log=lambda m: self.message.emit(m))
            self.succeeded.emit(v)
        except Exception as e:
            self.failed.emit(str(e))


class UpdateCheckTask(QThread):
    found = Signal(dict)
    nothing = Signal()
    failed = Signal(str)

    def __init__(self, repo: str, version: str, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.version = version

    def run(self) -> None:
        try:
            u = AppUpdater(self.repo, self.version)
            info = u.available_update()
            if info:
                self.found.emit(info)
            else:
                self.nothing.emit()
        except Exception as e:
            self.failed.emit(str(e))


class UpdateDownloadTask(QThread):
    progress = Signal(int, int)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, repo: str, version: str, info: dict, parent=None):
        super().__init__(parent)
        self.repo, self.version, self.info = repo, version, info

    def run(self) -> None:
        try:
            u = AppUpdater(self.repo, self.version)
            p = u.download(self.info, progress=lambda d, t: self.progress.emit(d, t))
            self.succeeded.emit(str(p))
        except Exception as e:
            self.failed.emit(str(e))


# ---------------------------------------------------------------- 主窗口
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = Config.global_instance()
        self.engine = Engine()
        self.worker: DownloadWorker | None = None

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(780, 700)
        self.setStyleSheet(QSS)
        self._build_menu()
        self._build_ui()
        self._load_config_to_ui()
        self._refresh_status()
        QTimer.singleShot(300, self._bootstrap)

    # ---------------- 菜单 ----------------
    def _build_menu(self) -> None:
        m = self.menuBar()
        m.setStyleSheet("QMenuBar{background:#16171a;} QMenuBar::item:selected{background:#2f3137;}")

        app_menu = m.addMenu("应用")
        a_repo = QAction("更新源设置…", self)
        a_repo.triggered.connect(self._edit_update_repo)
        a_data = QAction("打开数据目录", self)
        a_data.triggered.connect(lambda: open_path(user_data_dir()))
        a_quit = QAction("退出", self)
        a_quit.setShortcut("Ctrl+Q")
        a_quit.triggered.connect(self.close)
        app_menu.addAction(a_repo)
        app_menu.addAction(a_data)
        app_menu.addSeparator()
        app_menu.addAction(a_quit)

        upd = m.addMenu("更新")
        a_eng = QAction("检查下载引擎更新…", self)
        a_eng.triggered.connect(lambda: self._engine_update(manual=True))
        a_app = QAction("检查应用更新…", self)
        a_app.triggered.connect(self._check_app_update)
        upd.addAction(a_eng)
        upd.addAction(a_app)

        h = m.addMenu("帮助")
        a_about = QAction("关于", self)
        a_about.triggered.connect(self._about)
        h.addAction(a_about)

    # ---------------- 界面 ----------------
    def _build_ui(self) -> None:
        root = QWidget()
        v = QVBoxLayout(root)
        v.setContentsMargins(16, 14, 16, 12)
        v.setSpacing(10)

        # URL
        g_url = QGroupBox("视频地址（每行一个）")
        lv = QVBoxLayout(g_url)
        self.url_edit = QPlainTextEdit()
        self.url_edit.setPlaceholderText("https://www.youtube.com/watch?v=…\n支持整条播放列表地址")
        self.url_edit.setFixedHeight(86)
        lv.addWidget(self.url_edit)
        v.addWidget(g_url)

        # 输出目录
        row_out = QHBoxLayout()
        row_out.addWidget(QLabel("保存到"))
        self.out_edit = QLineEdit()
        btn_out = QPushButton("选择…")
        btn_out.clicked.connect(self._pick_output)
        row_out.addWidget(self.out_edit, 1)
        row_out.addWidget(btn_out)
        v.addLayout(row_out)

        # 格式
        row_fmt = QHBoxLayout()
        row_fmt.addWidget(QLabel("下载格式"))
        self.fmt_combo = QComboBox()
        for key in FORMAT_ORDER:
            self.fmt_combo.addItem(FORMAT_PRESETS[key][0], key)
        self.fmt_combo.currentIndexChanged.connect(self._sync_format_ui)
        row_fmt.addWidget(self.fmt_combo, 1)
        row_fmt.addWidget(QLabel("音频格式"))
        self.audio_combo = QComboBox()
        self.audio_combo.addItems(AUDIO_FORMATS)
        row_fmt.addWidget(self.audio_combo)
        v.addLayout(row_fmt)

        self.custom_edit = QLineEdit()
        self.custom_edit.setPlaceholderText("自定义格式串，例如 bv[height<=1080]+ba/best")
        v.addWidget(self.custom_edit)

        # 字幕
        row_sub = QHBoxLayout()
        row_sub.addWidget(QLabel("字幕"))
        self.sub_combo = QComboBox()
        for k, label in SUBTITLE_MODES:
            self.sub_combo.addItem(label, k)
        row_sub.addWidget(self.sub_combo)
        row_sub.addWidget(QLabel("语言"))
        self.lang_edit = QLineEdit()
        self.lang_edit.setPlaceholderText("zh-Hans,zh-Hant,en")
        row_sub.addWidget(self.lang_edit, 1)
        v.addLayout(row_sub)

        # 高级
        self.adv = QGroupBox("高级选项")
        self.adv.setCheckable(True)
        self.adv.setChecked(False)
        self.adv.toggled.connect(self._toggle_adv)
        f = QFormLayout(self.adv)
        f.setLabelAlignment(Qt.AlignRight)
        self.spin_n = QSpinBox()
        self.spin_n.setRange(1, 16)
        self.rate_edit = QLineEdit()
        self.rate_edit.setPlaceholderText("留空不限速，例如 5M")
        self.proxy_edit = QLineEdit()
        self.proxy_edit.setPlaceholderText("例如 http://127.0.0.1:7890")
        self.cookie_combo = QComboBox()
        for k, label in COOKIE_BROWSERS:
            self.cookie_combo.addItem(label, k)
        self.chk_playlist = QCheckBox("下载整个播放列表")
        self.chk_meta = QCheckBox("写入元数据（标题/作者/日期）")
        self.chk_thumb = QCheckBox("内嵌封面")
        self.ff_edit = QLineEdit()
        self.ff_edit.setPlaceholderText("留空则使用随包 ffmpeg")
        btn_ff = QPushButton("选择…")
        btn_ff.clicked.connect(self._pick_ffmpeg)
        ff_row = QHBoxLayout()
        ff_row.addWidget(self.ff_edit, 1)
        ff_row.addWidget(btn_ff)
        f.addRow("并发分片", self.spin_n)
        f.addRow("限速", self.rate_edit)
        f.addRow("代理", self.proxy_edit)
        f.addRow("Cookies 来源", self.cookie_combo)
        f.addRow("ffmpeg", ff_row)
        f.addRow("", self.chk_playlist)
        f.addRow("", self.chk_meta)
        f.addRow("", self.chk_thumb)
        v.addWidget(self.adv)

        # 进度
        self.bar = QProgressBar()
        self.bar.setFormat("%p%")
        self.bar.setValue(0)
        self.detail = QLabel("就绪")
        self.detail.setStyleSheet("color:#9aa0aa;")
        v.addWidget(self.bar)
        v.addWidget(self.detail)

        # 按钮
        row_btn = QHBoxLayout()
        self.btn_start = QPushButton("开始下载")
        self.btn_start.setObjectName("primary")
        self.btn_start.clicked.connect(self._start)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setObjectName("danger")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop)
        btn_open = QPushButton("打开下载目录")
        btn_open.clicked.connect(self._open_output)
        row_btn.addWidget(self.btn_start)
        row_btn.addWidget(self.btn_stop)
        row_btn.addStretch(1)
        row_btn.addWidget(btn_open)
        v.addLayout(row_btn)

        # 日志
        self.log = QPlainTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QPlainTextEdit.NoWrap)
        v.addWidget(self.log, 1)

        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self._sync_format_ui()

    def _toggle_adv(self, on: bool) -> None:
        for w in (self.spin_n, self.rate_edit, self.proxy_edit, self.cookie_combo,
                  self.ff_edit, self.chk_playlist, self.chk_meta, self.chk_thumb):
            w.setVisible(on)
        self.adjustSize()

    def _sync_format_ui(self) -> None:
        key = self.fmt_combo.currentData()
        self.audio_combo.setEnabled(key == "audio_only")
        self.custom_edit.setVisible(key == "custom")

    # ---------------- 配置读写 ----------------
    def _load_config_to_ui(self) -> None:
        c = self.cfg
        self.out_edit.setText(c.get("output_dir") or str(c.output_dir))
        idx = self.fmt_combo.findData(c.get("format_preset"))
        if idx >= 0:
            self.fmt_combo.setCurrentIndex(idx)
        self.custom_edit.setText(c.get("custom_format") or "")
        ai = self.audio_combo.findText(c.get("audio_format") or "mp3")
        if ai >= 0:
            self.audio_combo.setCurrentIndex(ai)
        si = self.sub_combo.findData(c.get("subtitle_mode"))
        if si >= 0:
            self.sub_combo.setCurrentIndex(si)
        self.lang_edit.setText(c.get("subtitle_langs") or "")
        self.spin_n.setValue(int(c.get("concurrency") or 4))
        self.rate_edit.setText(c.get("rate_limit") or "")
        self.proxy_edit.setText(c.get("proxy") or "")
        ci = self.cookie_combo.findData(c.get("cookies_browser") or "")
        if ci >= 0:
            self.cookie_combo.setCurrentIndex(ci)
        self.chk_playlist.setChecked(bool(c.get("playlist")))
        self.chk_meta.setChecked(bool(c.get("embed_metadata")))
        self.chk_thumb.setChecked(bool(c.get("embed_thumbnail")))
        self.ff_edit.setText(c.get("ffmpeg_path") or "")

    def _collect(self) -> dict:
        return {
            "output_dir": self.out_edit.text().strip() or str(self.cfg.output_dir),
            "format_preset": self.fmt_combo.currentData(),
            "format_string": FORMAT_PRESETS[self.fmt_combo.currentData()][1],
            "custom_format": self.custom_edit.text().strip(),
            "audio_format": self.audio_combo.currentText(),
            "subtitle_mode": self.sub_combo.currentData(),
            "subtitle_langs": self.lang_edit.text().strip(),
            "playlist": self.chk_playlist.isChecked(),
            "concurrency": self.spin_n.value(),
            "rate_limit": self.rate_edit.text().strip(),
            "proxy": self.proxy_edit.text().strip(),
            "cookies_browser": self.cookie_combo.currentData(),
            "embed_metadata": self.chk_meta.isChecked(),
            "embed_thumbnail": self.chk_thumb.isChecked(),
            "ffmpeg_path": self.ff_edit.text().strip(),
        }

    def _persist(self) -> None:
        d = self._collect()
        d["format_preset"] = self.fmt_combo.currentData()
        for k, v in d.items():
            self.cfg.set(k, v)

    # ---------------- 交互 ----------------
    def _pick_output(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择保存目录", self.out_edit.text() or str(Path.home()))
        if d:
            self.out_edit.setText(d)

    def _pick_ffmpeg(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "选择 ffmpeg 可执行文件")
        if f:
            self.ff_edit.setText(f)

    def _open_output(self) -> None:
        p = Path(self.out_edit.text().strip() or str(self.cfg.output_dir))
        p.mkdir(parents=True, exist_ok=True)
        open_path(p)

    def _log(self, text: str) -> None:
        self.log.appendPlainText(text)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def _refresh_status(self) -> None:
        v = self.engine.version() if self.engine.installed else "未安装"
        ff = find_ffmpeg(self.cfg.get("ffmpeg_path") or "")
        arch = {"x86_64": "Intel x64", "arm64": "Apple Silicon / ARM64"}.get(machine_arch(), machine_arch())
        self.statusBar().showMessage(
            f"  引擎 yt-dlp {v}    |    ffmpeg {'已就绪' if ff else '缺失'}    |    {platform_key()} · {arch}"
        )

    # ---------------- 引擎引导与更新 ----------------
    def _bootstrap(self) -> None:
        if not self.engine.installed:
            self._engine_update(manual=False, ensure=True)
            return
        if self.cfg.get("keep_engine_updated"):
            self._log(f"引擎已就绪：yt-dlp {self.engine.version()}，正在检查上游更新…")
            self._engine_update(manual=False, ensure=False, silent=True)

    def _engine_update(self, manual: bool = True, ensure: bool = False, silent: bool = False) -> None:
        mode = "ensure" if ensure else "update"
        dlg = QProgressDialog("正在准备…", "取消", 0, 100, self)
        dlg.setWindowTitle("下载引擎" if ensure else "更新引擎")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setValue(0)

        def on_msg(m):
            if not silent:
                self._log(m)
            dlg.setLabelText(m)

        def on_prog(done, total):
            if total:
                dlg.setMaximum(100)
                dlg.setValue(min(100, int(done * 100 / total)))
            else:
                dlg.setMaximum(0)

        def on_ok(v):
            dlg.close()
            self._refresh_status()
            if not silent:
                self._log(f"✔ 引擎版本：{v}")
            if manual:
                QMessageBox.information(self, "引擎更新", f"当前已是最新版：{v}")

        def on_fail(e):
            dlg.close()
            self._log(f"[错误] 引擎更新失败：{e}")
            if manual or ensure:
                QMessageBox.warning(self, "引擎更新失败", f"{e}\n\n可稍后重试，或在应用内更换网络/代理后再次检查。")

        self._eng_task = EngineTask(mode, self)
        self._eng_task.message.connect(on_msg)
        self._eng_task.progress.connect(on_prog)
        self._eng_task.succeeded.connect(on_ok)
        self._eng_task.failed.connect(on_fail)
        dlg.canceled.connect(self._eng_task.requestInterruption)
        self._eng_task.start()

    # ---------------- 应用自更新 ----------------
    def _updater(self) -> AppUpdater:
        return AppUpdater(self.cfg.get("update_repo") or "", APP_VERSION)

    def _edit_update_repo(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("更新源设置")
        dlg.setStyleSheet(QSS)
        form = QFormLayout(dlg)
        edit = QLineEdit(self.cfg.get("update_repo") or "")
        edit.setPlaceholderText("例如 yourname/TubeGet")
        chk = QCheckBox("启动时自动升级下载引擎")
        chk.setChecked(bool(self.cfg.get("keep_engine_updated")))
        form.addRow("应用更新仓库（GitHub）", edit)
        form.addRow("", chk)
        note = QLabel(
            "应用外壳从此仓库的 Release 拉取更新；\n"
            "下载引擎始终从官方 yt-dlp/yt-dlp 拉取，与此项无关。"
        )
        note.setStyleSheet("color:#9aa0aa;")
        form.addRow("", note)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec():
            self.cfg.set("update_repo", edit.text().strip())
            self.cfg.set("keep_engine_updated", chk.isChecked())

    def _check_app_update(self) -> None:
        u = self._updater()
        if not u.configured:
            QMessageBox.information(
                self, "应用更新",
                "尚未配置更新仓库。\n\n请在「应用 → 更新源设置」中填写你的 GitHub 仓库（owner/repo），"
                "并确保该仓库的 Release 中包含本平台的安装包。",
            )
            return
        self._log("正在检查应用更新…")

        def on_found(info):
            size = info.get("size", 0) / 1024 / 1024
            r = QMessageBox.question(
                self, "发现新版本",
                f"新版本：{info['tag']}\n安装包：{info.get('asset')}（{size:.1f} MB）\n\n是否下载到下载目录？",
            )
            if r == QMessageBox.Yes:
                self._download_app_update(info)

        def on_none():
            self._log("应用已是最新版本。")
            QMessageBox.information(self, "应用更新", "已是最新版本。")

        def on_fail(e):
            self._log(f"[错误] 检查应用更新失败：{e}")
            QMessageBox.warning(self, "应用更新", f"检查失败：{e}")

        t = UpdateCheckTask(u.repo, APP_VERSION, self)
        t.found.connect(on_found)
        t.nothing.connect(on_none)
        t.failed.connect(on_fail)
        self._chk_task = t
        t.start()

    def _download_app_update(self, info: dict) -> None:
        dlg = QProgressDialog("正在下载安装包…", "取消", 0, 100, self)
        dlg.setWindowTitle("应用更新")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setValue(0)

        def on_prog(done, total):
            dlg.setValue(min(100, int(done * 100 / total))) if total else dlg.setMaximum(0)

        def on_ok(path):
            dlg.close()
            self._log(f"安装包已下载：{path}")
            r = QMessageBox.question(self, "下载完成", f"已保存到：\n{path}\n\n是否立即打开？")
            if r == QMessageBox.Yes:
                open_path(Path(path))

        def on_fail(e):
            dlg.close()
            QMessageBox.warning(self, "应用更新", f"下载失败：{e}")

        t = UpdateDownloadTask(self._updater().repo, APP_VERSION, info, self)
        t.progress.connect(on_prog)
        t.succeeded.connect(on_ok)
        t.failed.connect(on_fail)
        self._dl_task = t
        t.start()

    def _about(self) -> None:
        QMessageBox.about(
            self, "关于 TubeGet",
            f"<b>{APP_NAME} {APP_VERSION}</b><br><br>"
            f"基于 yt-dlp 的跨平台视频下载器。<br>"
            f"平台：{platform_key()} · {machine_arch()}<br>"
            f"发布产物：{current_asset_name() or '（当前平台未定义）'}<br><br>"
            f"请仅下载你拥有权利或已获授权的内容。",
        )

    # ---------------- 下载 ----------------
    def _start(self) -> None:
        urls = [u.strip() for u in self.url_edit.toPlainText().splitlines() if u.strip()]
        if not urls:
            QMessageBox.warning(self, "提示", "请先填写视频地址。")
            return
        if not self.engine.installed:
            QMessageBox.warning(self, "提示", "下载引擎尚未就绪，请等待初始化完成。")
            return

        self._persist()
        outdir = Path(self._collect()["output_dir"])
        outdir.mkdir(parents=True, exist_ok=True)

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.bar.setValue(0)
        self.log.clear()

        self.worker = DownloadWorker(str(self.engine.exe), urls, self._collect(), self)
        self.worker.log.connect(self._log)
        self.worker.progress.connect(self._on_progress)
        self.worker.item_started.connect(
            lambda u, i, n: self.detail.setText(f"({i}/{n}) {u}")
        )
        self.worker.finished_all.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, pct: float, detail: str) -> None:
        self.bar.setValue(int(pct))
        self.detail.setText(detail)

    def _on_finished(self, ok: int, fail: int) -> None:
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.bar.setValue(100 if fail == 0 else self.bar.value())
        self.detail.setText(f"完成：成功 {ok} 项，失败 {fail} 项")
        self._log(f"=== 任务结束：成功 {ok}，失败 {fail} ===")
        if fail == 0 and ok > 0:
            QMessageBox.information(self, "完成", f"{ok} 项下载完成。\n保存位置：{self._collect()['output_dir']}")

    def _stop(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.btn_stop.setEnabled(False)
            self.detail.setText("正在中止…")

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.worker and self.worker.isRunning():
            r = QMessageBox.question(self, "确认", "下载任务仍在进行，确定退出？")
            if r != QMessageBox.Yes:
                event.ignore()
                return
            self.worker.stop()
            self.worker.wait(3000)
        self._persist()
        event.accept()
