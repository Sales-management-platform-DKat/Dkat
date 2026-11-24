import os
import subprocess
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
DB_ENV_KEYS = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")


def load_config(*, environment: str, database_url: str = "", **database_fields: str):
    env = os.environ.copy()
    env["DKAT_ENV"] = environment
    if database_url:
        env["DKAT_DATABASE_URL"] = database_url
    else:
        env.pop("DKAT_DATABASE_URL", None)
    for key in DB_ENV_KEYS:
        env[key] = database_fields.get(key, "")
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.core.config import DATABASE_URL; print(DATABASE_URL.drivername if hasattr(DATABASE_URL, 'drivername') else DATABASE_URL.split(':', 1)[0])",
        ],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


class DatabaseConfigTests(unittest.TestCase):
    def test_production_requires_configured_server_database(self):
        result = load_config(environment="production")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SQLite fallback is disabled", result.stderr)

    def test_production_rejects_sqlite_url(self):
        result = load_config(environment="production", database_url="sqlite:///./dkat.db")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SQLite fallback is disabled", result.stderr)

    def test_production_rejects_non_mysql_database_url(self):
        result = load_config(environment="production", database_url="postgresql://user:pass@db.example.test/dkat")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires the MySQL/MariaDB database engine", result.stderr)

    def test_production_accepts_mysql_database_url(self):
        result = load_config(
            environment="production",
            database_url="mysql+pymysql://dkat_app:test-only-password@db.example.test:4000/dkat_test",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "mysql+pymysql")

    def test_production_accepts_mysql_environment_configuration(self):
        result = load_config(
            environment="production",
            DB_HOST="db.example.test",
            DB_PORT="4000",
            DB_NAME="dkat_test",
            DB_USER="dkat_app",
            DB_PASSWORD="test-only-password",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "mysql+pymysql")

    def test_development_keeps_sqlite_fallback(self):
        result = load_config(environment="development")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "sqlite")


if __name__ == "__main__":
    unittest.main()
