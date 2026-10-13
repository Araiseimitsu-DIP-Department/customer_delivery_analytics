"""集計・予測・Excel・SQLite・画面 API のオフライン回帰検証。"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from openpyxl import load_workbook

from app.infrastructure.indicator_store import IndicatorStore
from app.service import delivery_service, export_service, forecast_service


class CoreTests(unittest.TestCase):
    def test_aggregation_preserves_totals(self):
        raw = pd.DataFrame({
            "納入日": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-02-01"]),
            "顧客": ["A", "A", "B"], "品番": ["P1", "P2", "P1"],
            "納品数": [2, 3, 4], "金額": [20, 30, 40],
        })
        for mode in delivery_service.AggregateMode:
            with self.subTest(mode=mode):
                result = delivery_service.aggregate_for_list(raw, mode)
                self.assertEqual(list(result.columns), delivery_service.LIST_COLUMNS)
                self.assertEqual(result["納品数"].sum(), 9)
                self.assertEqual(result["金額"].sum(), 90)
        self.assertEqual(delivery_service.yearly_totals_from_raw_deliveries(raw)["金額"].tolist(), [90])
        self.assertEqual(delivery_service.monthly_totals_from_raw_deliveries(raw)["金額"].tolist(), [50, 40])

    def test_empty_aggregation_and_invalid_period(self):
        self.assertEqual(list(delivery_service.aggregate_for_list(pd.DataFrame(), delivery_service.AggregateMode.BY_CUSTOMER).columns), delivery_service.LIST_COLUMNS)
        with self.assertRaises(ValueError):
            delivery_service.fetch_deliveries(None, date_from=pd.Timestamp("2025-01-01").date())

    def test_numpy_forecast(self):
        model = forecast_service.fit_standard_model([2023, 2024, 2025], [10, 20, 30])
        np.testing.assert_allclose(forecast_service.predict(model, [[2026], [2027]]), [40, 50], atol=1e-6)
        self.assertEqual(len(forecast_service.generate_weights(0)), 0)
        self.assertTrue(np.all(np.diff(forecast_service.generate_weights(8)) > 0))

    def test_excel_readback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "一覧.xlsx"
            export_service.export_dataframe(str(path), pd.DataFrame({"品番": ["P1"], "納品数": [3]}))
            workbook = load_workbook(path)
            try:
                self.assertEqual(list(workbook.active.values), [("品番", "納品数"), ("P1", 3)])
            finally:
                workbook.close()

    def test_sqlite_update_readback_and_rerun(self):
        with tempfile.TemporaryDirectory() as folder:
            store = IndicatorStore(Path(folder) / "indicators.db")
            store.initialize()
            frame = pd.DataFrame({"year_month": ["2025-01"], "value": [100.0], "published_date": ["2025-02-01"], "fetched_at": ["2025-02-02"]})
            store.replace_monthly_values("IIP", frame)
            store.replace_monthly_values("IIP", frame)
            result = store.get_monthly_values("IIP")
            self.assertEqual(len(result), 1)
            self.assertEqual(result.iloc[0]["value"], 100)
            frame["value"] = 110.0
            store.replace_monthly_values("IIP", frame)
            self.assertEqual(store.get_monthly_values("IIP").iloc[0]["value"], 110)

    def test_startup_import_without_access(self):
        code = '''
import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in ('pyodbc', 'pypyodbc', 'win32com'):
        raise ImportError('Access 専用依存の読み込みを検出: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
import app.main
import app.webview_app
'''
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_bootstrap_without_database_connection(self):
        from app.webview_app import WebviewApi
        with patch.dict(os.environ, {"CDA_DELIVERIES_DATABASE_URL": "postgresql://test/db", "CDA_MASTERS_DATABASE_URL": "postgresql://test/db"}), patch("app.db.postgres_connector.psycopg.connect", side_effect=AssertionError("初期表示で DB に接続")):
            payload = WebviewApi().bootstrap()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["customers"], [])
        self.assertIn("defaults", payload)
