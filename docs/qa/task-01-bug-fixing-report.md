# Task 01 – Bug Fixing Report

## Summary

- Source: `docs/qa/DKat_Bug_Log.xlsx`, BUG-006 (latest available copy on `origin/develop`).
- Bugs reviewed: 1.
- Bugs fixed in this task: 1 regression.
- The source log lists BUG-006 as closed after its original fix. The verified `333a38b` code had regressed: the API lifespan imported the expiry worker but never started it.

## BUG-006 – Scheduled expiry worker does not run

- **Module / severity:** preorder lifecycle / High.
- **Reproduction:** start the FastAPI app with a due `READY` or `NOTIFIED` preorder; wait past the scheduler interval; check whether it transitions to expired and stock is reallocated. The log's prior integration check patches the interval to 0.01 seconds and waits up to 5 seconds.
- **Actual before fix:** the app lifespan only called `Base.metadata.create_all()` and yielded. It never created the scheduled task, so due reservations remained active and could block FIFO allocation.
- **Expected:** start the worker when the application starts and signal it to stop cleanly during shutdown.
- **Root cause:** a merge regression removed `asyncio.create_task(run_preorder_expiry(stop))` and its shutdown lifecycle wiring, while leaving the worker import in place.
- **Fix:** start the worker in lifespan, set its stop event during shutdown, and await completion.
- **Files changed:** `backend/app/main.py`; `backend/tests/test_lifespan.py`.
- **After:** the isolated lifecycle test checks that the worker starts and receives shutdown before the application exits. The database-backed expiry scenario remains unverified in this environment.

## Verification

- Run: `python -m unittest tests.test_lifespan -v` from `backend/` — **Pass** (1 test).
- The MySQL integration check `integration_tests.test_preorder_fifo_mysql.PreorderFifoTests.test_api_lifespan_runs_scheduled_expiry` requires a dedicated test MySQL database and was not run against any configured database.

## Remaining issues

Other open entries in the source log were not changed in this task. No production database, schema, API contract, credentials, or `.env` file was modified.
