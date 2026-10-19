"""TubeGet 应用入口。"""

from __future__ import annotations

import multiprocessing
import sys


def main() -> int:
    # Windows / macOS 下 PyInstaller 生成的子进程需要 freeze_support
    multiprocessing.freeze_support()

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from ui import MainWindow
    from version import APP_ID, APP_NAME, APP_VERSION

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_ID)

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
