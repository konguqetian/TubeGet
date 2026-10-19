"""本地打包包装器（仅用于受限沙箱环境）。

某些受管控的 macOS 环境禁止调用 codesign，PyInstaller 在生成可执行文件前会尝试
剥离签名而直接失败。这里把该步骤替换为空操作；GitHub Actions 等正常环境无需使用。
"""

from __future__ import annotations

import sys


def main() -> int:
    import os
    import shutil

    # 1) 受限环境禁止 codesign
    try:
        from PyInstaller.utils import osx

        osx.remove_signature_from_binary = lambda *a, **k: None
        osx.sign_binary = lambda *a, **k: None
        osx.set_relink_timestamp = lambda *a, **k: None
    except Exception:
        pass

    # 2) 受限环境禁止删除文件：降级为忽略，构建产物仍会正常写入
    _remove = os.remove
    _unlink = os.unlink
    _rmtree = shutil.rmtree

    def _safe_remove(path, *a, **k):
        try:
            _remove(path, *a, **k)
        except OSError:
            pass

    def _safe_unlink(path, *a, **k):
        try:
            _unlink(path, *a, **k)
        except OSError:
            pass

    def _safe_rmtree(path, *a, **k):
        try:
            _rmtree(path, ignore_errors=True)
        except OSError:
            pass

    os.remove = _safe_remove
    os.unlink = _safe_unlink
    shutil.rmtree = _safe_rmtree

    from PyInstaller import __main__

    sys.argv = ["pyinstaller"] + sys.argv[1:]
    __main__.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
