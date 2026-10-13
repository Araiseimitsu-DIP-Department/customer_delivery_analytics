"""配布に必要な同梱物と Access 混入防止の検証。"""

import unittest

from scripts.verify_build import REQUIRED_FILES, REQUIRED_MODULES, validate_members


class BuildContentsTests(unittest.TestCase):
    def setUp(self):
        self.modules = set(REQUIRED_MODULES)
        self.files = set(REQUIRED_FILES) | {
            "psycopg_binary.libs/libpq-test.dll",
            "psycopg_binary/pq.cp312-win_amd64.pyd",
            "psycopg_binary/_psycopg.cp312-win_amd64.pyd",
        }

    def test_postgres_gui_and_sqlite_are_allowed(self):
        validate_members(self.modules, {name.replace("/", "\\") for name in self.files})

    def test_access_modules_and_files_are_rejected(self):
        for name in ("pyodbc", "pypyodbc", "win32com.client"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_members(self.modules | {name}, self.files)
        for name in ("data/legacy.ACCDB", "data/source.mdb", "drivers/ACEODBC.DLL", "pyodbc.cp312.pyd", "win32com/client.py"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_members(self.modules, self.files | {name})

    def test_missing_runtime_dependencies_are_rejected(self):
        for name in ("psycopg_binary", "sqlite3", "pythonnet"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_members(self.modules - {name}, self.files)
        for name in ("app/web/index.html", "psycopg_binary.libs/libpq-test.dll", "psycopg_binary/pq.cp312-win_amd64.pyd"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_members(self.modules, self.files - {name})
