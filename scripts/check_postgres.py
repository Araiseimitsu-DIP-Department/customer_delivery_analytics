"""設定済み PostgreSQL の主要テーブルを読み取り専用で確認する。"""

import logging

from app.db.postgres_connector import open_app_connections

LOGGER = logging.getLogger(__name__)
READ_ONLY_STATEMENT_TIMEOUT = "10s"


def main() -> int:
    try:
        with open_app_connections() as connections:
            unique_connections = {
                id(connection): connection
                for connection in (connections.deliveries, connections.masters)
            }
            for connection in unique_connections.values():
                connection.execute("SET TRANSACTION READ ONLY")
                connection.execute(f"SET LOCAL statement_timeout = '{READ_ONLY_STATEMENT_TIMEOUT}'")
            connections.deliveries.execute(
                "SELECT delivery_date, product_no, delivery_qty, amount FROM deliveries LIMIT 1"
            ).fetchone()
            connections.masters.execute(
                "SELECT product_no, customer_name FROM product_master LIMIT 1"
            ).fetchone()
            connections.masters.execute(
                "SELECT code, customer FROM customer_master LIMIT 1"
            ).fetchone()
    except Exception as exc:
        # 接続例外の本文に接続情報が入る場合があるため実値を表示しない。
        cause = exc.__cause__ or exc
        LOGGER.error("PostgreSQL 読取検証 FAIL: %s / %s", type(exc).__name__, type(cause).__name__)
        return 1
    LOGGER.info("PostgreSQL 読取検証 PASS（接続・主要3テーブルの列参照、実データ表示なし）")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    raise SystemExit(main())
