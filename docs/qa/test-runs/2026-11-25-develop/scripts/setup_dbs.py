"""Create clean, disposable MySQL databases for the develop integration run.

Reads DB_HOST/DB_PORT/DB_USER/DB_PASSWORD from the environment (never printed).
Usage: python setup_dbs.py <schema.sql> <db_name> [<db_name> ...]
Only names starting with dkat_develop or dkat_pbi and ending in _test / _develop are allowed.
"""
import os
import re
import sys

import pymysql

schema_path, names = sys.argv[1], sys.argv[2:]
for n in names:
    if not re.fullmatch(r"dkat_(develop|pbi\d+_test)", n):
        sys.exit(f"refusing unexpected database name {n}")

sql = open(schema_path, encoding="utf-8").read()
sql = re.sub(r"^\s*(CREATE DATABASE|USE)\b[^;]*;", "", sql, flags=re.M | re.I)
sql = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
statements = [s.strip() for s in sql.split(";") if s.strip()]

conn = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ["DB_PORT"]), user=os.environ["DB_USER"],
                       password=os.environ["DB_PASSWORD"], autocommit=True, charset="utf8mb4")
with conn.cursor() as cur:
    for n in names:
        cur.execute(f"DROP DATABASE IF EXISTS `{n}`")
        cur.execute(f"CREATE DATABASE `{n}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        cur.execute(f"USE `{n}`")
        for s in statements:
            cur.execute(s)
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s", (n,))
        print(f"OK {n}: {cur.fetchone()[0]} tables, {len(statements)} statements")
conn.close()
