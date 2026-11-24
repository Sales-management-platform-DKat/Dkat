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
    # explicit, so a developer's backend/.env (e.g. DB_SSL_MODE=disabled for a local MySQL) cannot change the result
    env["DB_SSL_MODE"] = database_fields.get("DB_SSL_MODE", "verify")
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

    def ssl_args(self, environment: str, mode: str | None):
        env = os.environ.copy()
        env.update(DKAT_ENV=environment, DB_HOST="127.0.0.1", DB_PORT="3306", DB_NAME="dkat_test",
                   DB_USER="dkat_app", DB_PASSWORD="test-only-password")
        env.pop("DKAT_DATABASE_URL", None)
        env.pop("DB_SSL_MODE", None)
        if mode is not None:
            env["DB_SSL_MODE"] = mode
        return subprocess.run(
            # backend/.env is ignored here: the test checks the code's own default, not a developer's settings
            [sys.executable, "-c", "import dotenv; dotenv.load_dotenv = lambda *a, **k: False; "
                                   "from app.core.config import DATABASE_CONNECT_ARGS as a; print(sorted(a))"],
            cwd=BACKEND_DIR, env=env, capture_output=True, text=True, check=False,
        )

    def test_ssl_is_verified_by_default(self):
        result = self.ssl_args("development", None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ssl_verify_identity", result.stdout)

    def test_local_mysql_can_disable_ssl_in_development(self):
        result = self.ssl_args("development", "disabled")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "['connect_timeout']")

    def test_production_refuses_disabled_ssl_and_unknown_modes(self):
        self.assertIn("Production requires DB_SSL_MODE=verify", self.ssl_args("production", "disabled").stderr)
        self.assertIn("DB_SSL_MODE must be", self.ssl_args("development", "off").stderr)


if __name__ == "__main__":
    unittest.main()
