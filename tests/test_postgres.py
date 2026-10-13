"""外部 DB に接続せず、既存の接続・設定仕様を検証する。"""

import os
import unittest
from unittest.mock import MagicMock, patch

from app.config import settings
from app.db import postgres_connector as connector
from scripts import check_postgres


class SettingsTests(unittest.TestCase):
    def test_url_priority(self):
        values = {
            settings.ENV_DELIVERIES_DATABASE_URL: "postgresql://override/delivery",
            settings.ENV_POSTGRES_ARAI_MASTERS_URL: "postgresql://standard/delivery",
            settings.ENV_MASTERS_DATABASE_URL: "postgresql://override/master",
            settings.ENV_POSTGRES_ORDER_MANAGEMENT_DB_URL: "postgresql://standard/master",
        }
        with patch.dict(os.environ, values, clear=True), patch.object(settings, "_DOTENV_LOADED", True):
            self.assertEqual(settings.resolve_deliveries_database_url(), values[settings.ENV_DELIVERIES_DATABASE_URL])
            self.assertEqual(settings.resolve_masters_database_url(), values[settings.ENV_MASTERS_DATABASE_URL])

    def test_missing_password_fails_without_fallback(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(settings, "_DOTENV_LOADED", True):
            with self.assertRaises(RuntimeError):
                settings.resolve_deliveries_database_url()


class ConnectionTests(unittest.TestCase):
    def test_same_url_reuses_and_closes_connection(self):
        conn = MagicMock()
        with patch.object(settings, "resolve_deliveries_database_url", return_value="postgresql://test/db"), patch.object(settings, "resolve_masters_database_url", return_value="postgresql://test/db"), patch.object(settings, "resolve_postgres_schema", return_value="public"), patch.object(connector.psycopg, "connect", return_value=conn) as connect:
            with connector.open_app_connections() as conns:
                self.assertIs(conns.deliveries, conns.masters)
            connect.assert_called_once_with("postgresql://test/db", connect_timeout=settings.POSTGRES_CONNECT_TIMEOUT_SECONDS)
        conn.close.assert_called_once()

    def test_connection_failure_raises_postgres_error(self):
        with patch.object(connector.psycopg, "connect", side_effect=RuntimeError("接続失敗")) as connect:
            with self.assertRaises(connector.PostgresConnectionError):
                with connector.open_connection("postgresql://test/db"):
                    self.fail("接続失敗時に処理が続行された")
            connect.assert_called_once()

    def test_deliveries_can_be_selected_from_other_postgres_connection(self):
        deliveries, masters = MagicMock(), MagicMock()
        with patch.object(settings, "resolve_deliveries_database_url", return_value="postgresql://test/delivery"), patch.object(settings, "resolve_masters_database_url", return_value="postgresql://test/master"), patch.object(settings, "resolve_postgres_schema", return_value="public"), patch.object(connector.psycopg, "connect", side_effect=[deliveries, masters]), patch.object(connector, "table_exists", side_effect=[False, True]):
            with connector.open_app_connections() as conns:
                self.assertIs(conns.deliveries, masters)
                self.assertIs(conns.masters, masters)
        deliveries.close.assert_called_once()
        masters.close.assert_called_once()


class ReadOnlySmokeTests(unittest.TestCase):
    def test_shared_connection_enters_read_only_once_before_queries(self):
        conn = MagicMock()
        context = MagicMock()
        context.__enter__.return_value = connector.PostgresConnections(conn, conn)
        with patch.object(check_postgres, "open_app_connections", return_value=context):
            self.assertEqual(check_postgres.main(), 0)
        statements = [call.args[0] for call in conn.execute.call_args_list]
        self.assertEqual(statements[0], "SET TRANSACTION READ ONLY")
        self.assertEqual(statements.count("SET TRANSACTION READ ONLY"), 1)
        self.assertEqual(sum(statement.startswith("SELECT") for statement in statements), 3)

    def test_separate_connections_are_both_read_only(self):
        deliveries, masters = MagicMock(), MagicMock()
        context = MagicMock()
        context.__enter__.return_value = connector.PostgresConnections(deliveries, masters)
        with patch.object(check_postgres, "open_app_connections", return_value=context):
            self.assertEqual(check_postgres.main(), 0)
        for conn in (deliveries, masters):
            self.assertEqual(conn.execute.call_args_list[0].args[0], "SET TRANSACTION READ ONLY")

    def test_failure_does_not_log_connection_secret(self):
        with patch.object(check_postgres, "open_app_connections", side_effect=RuntimeError("secret-password")):
            with self.assertLogs(check_postgres.LOGGER, level="ERROR") as captured:
                self.assertEqual(check_postgres.main(), 1)
        self.assertNotIn("secret-password", "".join(captured.output))
