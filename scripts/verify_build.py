"""PostgreSQL 配布用 exe の同梱物を検査する。"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path, PurePosixPath

from PyInstaller.archive.readers import CArchiveReader

LOGGER = logging.getLogger(__name__)
ACCESS_MODULES = ("pyodbc", "pypyodbc", "win32com")
ACCESS_SUFFIXES = {".mdb", ".accdb", ".mde", ".accde", ".laccdb", ".ldb"}
ACCESS_DRIVERS = {"aceodbc.dll", "aceoledb.dll", "msjet40.dll", "msjetoledb40.dll", "odbcjt32.dll"}
REQUIRED_MODULES = {
    "app.webview_app", "psycopg", "psycopg_binary", "pandas", "numpy",
    "matplotlib", "openpyxl", "webview", "pythonnet", "clr_loader", "sqlite3",
}
REQUIRED_FILES = {
    "app/web/index.html", "app/web/app.js", "app/web/styles.css",
    "docs/icon.png", "docs/DESIGN/arai_logo.png",
    "pythonnet/runtime/Python.Runtime.dll",
    "webview/lib/Microsoft.Web.WebView2.Core.dll",
    "webview/lib/Microsoft.Web.WebView2.WinForms.dll",
    "webview/lib/runtimes/win-x64/native/WebView2Loader.dll",
}


def validate_members(modules: set[str], files: set[str]) -> None:
    """PYZ と外側アーカイブの一覧を検証する（内容や接続情報は表示しない）。"""
    normalized = {name.replace("\\", "/") for name in files}
    forbidden = {
        name for name in modules
        if name.split(".", 1)[0].lower() in ACCESS_MODULES
    }
    for name in normalized:
        path = PurePosixPath(name.lower())
        if (
            path.suffix in ACCESS_SUFFIXES
            or path.name in ACCESS_DRIVERS
            or any(part.split(".", 1)[0] in ACCESS_MODULES for part in path.parts)
        ):
            forbidden.add(name)
    missing = (REQUIRED_MODULES - modules) | (REQUIRED_FILES - normalized)
    if not any("libpq" in name.lower() and name.lower().endswith(".dll") for name in normalized):
        missing.add("libpq DLL")
    for extension in ("pq", "_psycopg"):
        if not any(name.startswith(f"psycopg_binary/{extension}.") and name.endswith(".pyd") for name in normalized):
            missing.add(f"psycopg_binary/{extension}.*.pyd")
    if forbidden or missing:
        raise ValueError(f"同梱物検査失敗: 禁止={sorted(forbidden)}, 不足={sorted(missing)}")


def verify_archive(executable: Path) -> None:
    archive = CArchiveReader(str(executable))
    python_archive = archive.open_embedded_archive("PYZ.pyz")
    validate_members(set(python_archive.toc), set(archive.toc))
    LOGGER.info("同梱物検査 PASS: %s (%s バイト)", executable.name, executable.stat().st_size)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", nargs="?", type=Path)
    parser.add_argument("--excluded-modules", action="store_true")
    args = parser.parse_args()
    if args.excluded_modules:
        print("\n".join(ACCESS_MODULES))
        return 0
    if args.executable is None:
        parser.error("検査対象の exe を指定してください。")
    try:
        verify_archive(args.executable)
    except Exception:
        LOGGER.exception("ビルド成果物の検査に失敗しました")
        return 1
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    raise SystemExit(main())
