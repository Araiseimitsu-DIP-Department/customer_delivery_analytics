# -*- coding: utf-8 -*-
"""アプリ全体の定数・既定値（仕様書・依頼仕様に準拠）"""

from pathlib import Path

# --- 表示・識別名（名称統一） ---
APP_DISPLAY_NAME = "顧客別納入分析システム"
WINDOW_TITLE = "顧客別納入分析システム - Customer Delivery Analytics"
EXE_BASENAME = "顧客別納入分析システム"
APP_ICON_PNG = ("docs", "icon.png")
APP_ICON_ICO = ("docs", "icon.ico")

# --- PostgreSQL 接続 ---
ENV_DELIVERIES_DATABASE_URL = "CDA_DELIVERIES_DATABASE_URL"
ENV_MASTERS_DATABASE_URL = "CDA_MASTERS_DATABASE_URL"
ENV_POSTGRES_HOST = "CDA_POSTGRES_HOST"
ENV_POSTGRES_PORT = "CDA_POSTGRES_PORT"
ENV_POSTGRES_USER = "CDA_POSTGRES_USER"
ENV_POSTGRES_PASSWORD = "CDA_POSTGRES_PASSWORD"
ENV_DELIVERIES_DATABASE = "CDA_DELIVERIES_DATABASE"
ENV_MASTERS_DATABASE = "CDA_MASTERS_DATABASE"
ENV_POSTGRES_SCHEMA = "POSTGRES_SCHEMA"
ENV_POSTGRES_ARAI_MASTERS_URL = "POSTGRES_ARAI_MASTERS_URL"
ENV_POSTGRES_ORDER_MANAGEMENT_DB_URL = "POSTGRES_ORDER_MANAGEMENT_DB_URL"
DEFAULT_POSTGRES_HOST = "192.168.1.120"
DEFAULT_POSTGRES_PORT = "5432"
DEFAULT_POSTGRES_USER = "postgres"
DEFAULT_DELIVERIES_DATABASE = "arai_masters"
DEFAULT_MASTERS_DATABASE = "order_management"
DEFAULT_POSTGRES_SCHEMA = "public"
POSTGRES_CONNECT_TIMEOUT_SECONDS = 8
DOTENV_FILE_NAME = ".env"
_DOTENV_LOADED = False

# --- 実績対象期間（仕様） ---
DEFAULT_YEAR_START = 2018
DEFAULT_YEAR_END = 2025


def _load_dotenv() -> None:
    import os
    import sys

    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True

    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / DOTENV_FILE_NAME)
    candidates.append(Path(__file__).resolve().parent.parent.parent / DOTENV_FILE_NAME)
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / DOTENV_FILE_NAME)

    for dotenv_path in candidates:
        if not dotenv_path.exists():
            continue
        for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)


def _env(name: str, default: str = "") -> str:
    import os

    _load_dotenv()
    return os.environ.get(name, default).strip()


def _build_postgres_url(database: str) -> str:
    from urllib.parse import quote

    host = _env(ENV_POSTGRES_HOST, DEFAULT_POSTGRES_HOST)
    port = _env(ENV_POSTGRES_PORT, DEFAULT_POSTGRES_PORT)
    user = _env(ENV_POSTGRES_USER, DEFAULT_POSTGRES_USER)
    password = _env(ENV_POSTGRES_PASSWORD)
    if not password:
        raise RuntimeError(f"{ENV_POSTGRES_PASSWORD} が設定されていません。")
    return f"postgresql://{quote(user)}:{quote(password)}@{host}:{port}/{database}"


def resolve_deliveries_database_url() -> str:
    """納品実績 DB の接続 URL を解決する。"""
    override = _env(ENV_DELIVERIES_DATABASE_URL) or _env(ENV_POSTGRES_ARAI_MASTERS_URL)
    if override:
        return override
    database = _env(ENV_DELIVERIES_DATABASE, DEFAULT_DELIVERIES_DATABASE)
    return _build_postgres_url(database)


def resolve_masters_database_url() -> str:
    """製品・客先マスタ DB の接続 URL を解決する。"""
    override = _env(ENV_MASTERS_DATABASE_URL) or _env(ENV_POSTGRES_ORDER_MANAGEMENT_DB_URL)
    if override:
        return override
    database = _env(ENV_MASTERS_DATABASE, DEFAULT_MASTERS_DATABASE)
    return _build_postgres_url(database)


def resolve_postgres_schema() -> str:
    """PostgreSQL の search_path 用スキーマを解決する。"""
    return _env(ENV_POSTGRES_SCHEMA, DEFAULT_POSTGRES_SCHEMA) or DEFAULT_POSTGRES_SCHEMA


def database_summary() -> str:
    deliveries_db = _env(ENV_DELIVERIES_DATABASE, DEFAULT_DELIVERIES_DATABASE)
    masters_db = _env(ENV_MASTERS_DATABASE, DEFAULT_MASTERS_DATABASE)
    if _env(ENV_DELIVERIES_DATABASE_URL) or _env(ENV_POSTGRES_ARAI_MASTERS_URL):
        deliveries_db = "URL指定"
    if _env(ENV_MASTERS_DATABASE_URL) or _env(ENV_POSTGRES_ORDER_MANAGEMENT_DB_URL):
        masters_db = "URL指定"
    schema = resolve_postgres_schema()
    return f"納品DB: {deliveries_db} / マスタDB: {masters_db} / schema: {schema}"


def project_root() -> Path:
    """開発時はリポジトリルート、exe 化時は実行ファイルの親を返す目安。"""
    import sys

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def resource_root() -> Path:
    """同梱リソースの基準ディレクトリ。PyInstaller onefile では展開先を返す。"""
    import sys

    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent


def resource_path(*parts: str) -> Path:
    return resource_root().joinpath(*parts)


def app_icon_png_path() -> Path:
    return resource_path(*APP_ICON_PNG)


def app_icon_ico_path() -> Path:
    return resource_path(*APP_ICON_ICO)
