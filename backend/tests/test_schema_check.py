"""Schema drift detection: the requirement list matches database/, errors name the cause."""
import re
import unittest
from pathlib import Path

import pymysql
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from app.core.db_errors import SCHEMA_OUTDATED, database_error, is_schema_error
from app.db.schema_check import REQUIREMENTS, find_schema_drift, missing_scripts
from scripts.db_migrate import statements, unsafe_statements

DATABASE_DIR = Path(__file__).resolve().parents[2] / "database"
INCREMENTAL = sorted(path for path in DATABASE_DIR.glob("0*.sql") if not path.name.startswith("01_"))


def added_objects(script: Path) -> set[tuple]:
    """(kind, table, name) for everything a script adds: columns, indexes and tables."""
    sql = script.read_text(encoding="utf-8")
    found = {("table", table, "") for table in re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", sql)}
    for table, kind, name in re.findall(r"ALTER TABLE (\w+) ADD (COLUMN|INDEX) (\w+)", sql):
        found.add(("column" if kind == "COLUMN" else "index", table, name))
    for name, table in re.findall(r"CREATE INDEX (\w+) ON (\w+)", sql):
        found.add(("index", table, name))
    if "''EXPORT''" in sql and "MODIFY COLUMN movement_type" in sql:
        found.add(("enum", "inventory_movements", "movement_type"))
    return found


class SchemaRequirementTests(unittest.TestCase):
    def test_every_object_added_by_an_incremental_script_is_checked(self):
        # A new database/0N_*.sql must also be listed in app/db/schema_check.py.
        checked = {(item.kind, item.table, item.name if item.kind != "table" else "") for item in REQUIREMENTS}
        self.assertEqual(len(set().union(*(added_objects(script) for script in INCREMENTAL))), len(checked))
        for script in INCREMENTAL:
            for obj in added_objects(script):
                self.assertIn(obj, checked, f"{script.name} adds {obj}; add it to REQUIREMENTS")

    def test_each_requirement_names_a_script_that_really_adds_it(self):
        by_name = {script.name: added_objects(script) for script in INCREMENTAL}
        for item in REQUIREMENTS:
            self.assertIn(item.script, by_name, item)
            self.assertIn((item.kind, item.table, item.name if item.kind != "table" else ""), by_name[item.script], item)

    def test_a_fresh_01_schema_already_has_everything(self):
        base = (DATABASE_DIR / "01_schema.sql").read_text(encoding="utf-8")
        tables = dict(re.findall(r"CREATE TABLE (\w+) \((.*?)\n\) ENGINE", base, re.S))
        for item in REQUIREMENTS:
            if item.table == "preorder_request_limits":
                continue  # only created by 06_public_preorders.sql
            self.assertIn(item.table, tables, item)
            if item.kind == "column":
                self.assertRegex(tables[item.table], rf"\n\s+{item.name} ", item)
            elif item.kind == "index":
                self.assertIn(item.name, base, item)
            elif item.kind == "enum":
                self.assertIn(f"'{item.value}'", tables[item.table], item)

    def test_preorder_cancellation_columns_come_from_script_08(self):
        missing = [item for item in REQUIREMENTS if item.table == "preorders" and item.name in {"cancel_reason", "cancelled_at"}]
        self.assertEqual(missing_scripts(missing), ["08_preorder_cancellation.sql"])

    def test_sqlite_is_not_checked(self):
        self.assertEqual(find_schema_drift(create_engine("sqlite://")), [])


class MigrationScriptTests(unittest.TestCase):
    def test_scripts_are_split_into_statements_without_use(self):
        parts = statements(DATABASE_DIR / "08_preorder_cancellation.sql")
        self.assertEqual(len(parts), 12)  # 3 x (SET, PREPARE, EXECUTE, DEALLOCATE)
        self.assertFalse(any(part.upper().startswith("USE ") for part in parts))
        self.assertTrue(parts[0].startswith("SET @ddl = IF("))

    def test_every_incremental_script_is_additive_only(self):
        for script in INCREMENTAL:
            self.assertEqual(unsafe_statements(script), [], script.name)

    def test_destructive_sql_is_refused(self):
        sample = DATABASE_DIR.parent / "backend" / "tests" / "_unsafe_sample.sql"
        try:
            for sql in ("DROP TABLE preorders;\n", "TRUNCATE preorders;\n", "SET @x = 'ALTER TABLE p DROP COLUMN note';\n",
                        "DELETE FROM preorders;\n", "UPDATE preorders SET note = NULL;\n"):
                sample.write_text(sql, encoding="utf-8")
                self.assertTrue(unsafe_statements(sample), sql)
        finally:
            sample.unlink(missing_ok=True)


class DatabaseErrorTests(unittest.TestCase):
    @staticmethod
    def error(code, message):
        return OperationalError("SELECT 1", {}, pymysql.err.OperationalError(code, message))

    def test_unknown_column_is_reported_as_an_outdated_schema(self):
        exc = self.error(1054, "Unknown column 'p.cancel_reason' in 'field list'")
        self.assertTrue(is_schema_error(exc))
        with self.assertLogs("app.errors", "ERROR") as logs:
            http = database_error(exc, "Preorder list failed")
        self.assertEqual((http.status_code, http.detail), (503, SCHEMA_OUTDATED))
        self.assertIn("cancel_reason", "".join(logs.output))

    def test_missing_table_is_reported_as_an_outdated_schema(self):
        self.assertTrue(is_schema_error(self.error(1146, "Table 'dkat.preorder_request_limits' doesn't exist")))

    def test_connection_failures_keep_the_connection_message(self):
        exc = self.error(2003, "Can't connect to MySQL server")
        self.assertFalse(is_schema_error(exc))
        with self.assertLogs("app.errors", "ERROR"):
            http = database_error(exc)
        self.assertEqual(http.status_code, 503)
        self.assertIsInstance(http.detail, str)


if __name__ == "__main__":
    unittest.main()
