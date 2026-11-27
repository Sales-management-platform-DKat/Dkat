"""Check (default) or apply the incremental schema scripts in database/ on MySQL/TiDB.

    python -m scripts.db_migrate                       # read-only: what is missing, which script adds it
    python -m scripts.db_migrate --apply --database X  # run only the scripts still needed, on database X

Run from backend/. It connects with the same settings as the app (backend/.env or DB_* /
DKAT_DATABASE_URL), so check which database that is before applying anything.

Safety:
- Without --apply nothing is written.
- --apply needs --database equal to the name of the connected database.
- Only scripts with missing items run, in file order. Each is checked first and refused if it
  contains anything other than additive DDL (no DROP / TRUNCATE / DELETE / UPDATE / INSERT ...).
  The scripts themselves are idempotent: each step checks information_schema before changing it.
- Existing rows are never modified. New columns are NULL-able, so current data stays valid.
Output is ASCII so it also works on a cp1252 Windows console.
"""
import argparse
import re
import sys
from pathlib import Path

from sqlalchemy import text

from app.db.schema_check import find_schema_drift, missing_scripts
from app.db.session import engine

DATABASE_DIR = Path(__file__).resolve().parents[2] / "database"
FORBIDDEN = re.compile(
    r"^\s*(DROP|TRUNCATE|DELETE|UPDATE|INSERT|REPLACE|RENAME|GRANT|REVOKE|CREATE\s+USER|LOAD\s+DATA)\b"
    r"|\bDROP\s+(TABLE|COLUMN|INDEX|DATABASE|SCHEMA|PRIMARY|FOREIGN|CONSTRAINT)\b",
    re.IGNORECASE,
)


def statements(script: Path) -> list[str]:
    """Statements of one script without comments and its `USE dkat;` line (the app's database is used)."""
    body = "\n".join(line for line in script.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("--"))
    parts = [part.strip() for part in re.split(r";\s*\n", body + "\n")]
    return [part.rstrip(";") for part in parts if part and not re.fullmatch(r"USE\s+\w+", part, re.IGNORECASE)]


def unsafe_statements(script: Path) -> list[str]:
    return [statement for statement in statements(script) if FORBIDDEN.search(statement)]


def report(missing) -> None:
    if not missing:
        print("Schema is up to date: every item added by database/02..09 is present.")
        return
    print(f"Schema is behind the code: {len(missing)} item(s) missing.")
    for script in missing_scripts(missing):
        print(f"  {script}")
        for item in missing:
            if item.script == script:
                print(f"    - {item.describe()}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="run the scripts that are still needed")
    parser.add_argument("--database", help="name of the connected database (required with --apply)")
    args = parser.parse_args(argv)

    if engine.dialect.name != "mysql":
        print(f"Database is {engine.dialect.name}: the scripts in database/ are for MySQL/TiDB only.")
        return 2
    with engine.connect() as db:
        current = db.execute(text("SELECT DATABASE()")).scalar()
        version = db.execute(text("SELECT VERSION()")).scalar()
        missing = find_schema_drift(db)
    print(f"Connected to {engine.url.host}:{engine.url.port} database={current} server={version}")
    report(missing)
    if not args.apply:
        return 1 if missing else 0
    if not missing:
        return 0
    if args.database != current:
        print(f"Refusing to apply: pass --database {current} to confirm the target database.")
        return 2

    scripts = [DATABASE_DIR / name for name in missing_scripts(missing)]
    for script in scripts:
        if not script.is_file():
            print(f"Refusing to apply: {script} not found.")
            return 2
        unsafe = unsafe_statements(script)
        if unsafe:
            print(f"Refusing to apply {script.name}: it contains non-additive SQL: {unsafe[0][:80]!r}")
            return 2

    # One DBAPI connection: the scripts keep the DDL text in a session variable (@ddl)
    # between SET, PREPARE and EXECUTE. DDL commits implicitly on MySQL/TiDB.
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        for script in scripts:
            print(f"Applying {script.name}")
            for statement in statements(script):
                cursor.execute(statement)
                if cursor.description:
                    for row in cursor.fetchall():
                        print("   ", *row)
        raw.commit()
    finally:
        raw.close()

    with engine.connect() as db:
        remaining = find_schema_drift(db)
    report(remaining)
    return 1 if remaining else 0


if __name__ == "__main__":
    sys.exit(main())
