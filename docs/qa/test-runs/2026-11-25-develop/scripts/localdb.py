"""QA-only wrapper: run a module/script of the develop backend against local MySQL without TLS.

develop's app/core/config.py always sets ssl_verify_cert/ssl_verify_identity (TiDB Cloud), which
local MySQL 8 (self-signed cert) rejects. We drop those keys in place BEFORE app.db.session is
imported (session does `from config import DATABASE_CONNECT_ARGS`, same dict object).
Usage: python localdb.py -m <module> [args...]   |   python localdb.py <script.py> [args...]
"""
import runpy
import sys

import app.core.config as cfg

for k in ("ssl_ca", "ssl_verify_cert", "ssl_verify_identity"):
    cfg.DATABASE_CONNECT_ARGS.pop(k, None)

args = sys.argv[1:]
if args[0] == "-m":
    sys.argv = [args[1]] + args[2:]
    runpy.run_module(args[1], run_name="__main__", alter_sys=True)
else:
    sys.argv = args
    runpy.run_path(args[0], run_name="__main__")
