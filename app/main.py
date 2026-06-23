# -*- coding: utf-8 -*-
"""Application entry point."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
_root_str = str(_project_root)
if _root_str not in sys.path:
    sys.path.insert(0, _root_str)

_APP_DISPLAY_NAME = "顧客別納入分析システム"


def _report_fatal_startup_error(exc: BaseException) -> None:
    tb = traceback.format_exc()
    try:
        sys.stderr.write(tb)
        sys.stderr.flush()
    except Exception:
        pass
    text = f"{type(exc).__name__}: {exc}\n\n{tb}"[:3500]
    try:
        if sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                text,
                f"{_APP_DISPLAY_NAME} - 起動エラー",
                0x00000010,
            )
    except Exception:
        pass


def main() -> int:
    try:
        from app.webview_app import main as webview_main

        return webview_main()
    except Exception as exc:  # noqa: BLE001
        _report_fatal_startup_error(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
