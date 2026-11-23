# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

DKat is a multi-branch store management platform (inventory, POS, pre-orders) built by a student team. Specs live in DKat_SRS.docx / DKat_CSDL.docx (not in the repo); code comments cite requirement ids like FR-01.4, BR-10, NFR-02. The team writes docs, commit messages and API error messages in Vietnamese; code identifiers and code comments are in English.

## Repository and branches

- Remote: https://github.com/Sales-management-platform-DKat/Dkat. The local `Dkat` folder may **not** be a git checkout; if `git status` fails, clone the remote elsewhere, copy the changed files in, then commit and push from the clone.
- Branch naming: `<member>/<feature>` (e.g. `tuan/backend`, `tuan/rbac-middleware`, `tuan/branches-api`, `tuiladien/pbi-66`). Feature branches are stacked: `tuan/backend` → `tuan/rbac-middleware` → `tuan/branches-api`.
- `master` and the `tuiladien/*` branches contain an **older/different backend** (sync `Connection`-based services, `dkat.db`, `admin` module). The async architecture described below exists on the `tuan/*` branches. Expect conflicts in `products/` and `inventory/` when merging the two lines.

## Backend (`backend/`): FastAPI + SQLAlchemy 2 async + MySQL (aiomysql)

### Commands (run from `backend/`, venv at `backend/.venv`)

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env               # set DB_* and JWT_SECRET
uvicorn app.main:app --reload        # http://127.0.0.1:8000, Swagger at /docs (disabled in production)
python -m scripts.seed_auth          # idempotent seed: store, branches CN01-CN03, users, sample product/variants, pre-order
python -m scripts.seed_catalog       # idempotent catalog fixtures for /public (run after seed_auth)
python -m scripts.check_rbac         # in-process RBAC regression check (3 roles x 5 routes); exit code 1 on failure
python -m scripts.check_public_catalog   # in-process /public checks: filters, no internal fields, rate limit, EXPLAIN index use
npx newman@6.2.1 run postman/DKat_Branches.postman_collection.json   # needs the server running (also DKat_Users, DKat_Auth)
```

- No pytest/lint setup in this tree. Verification is `scripts/check_rbac.py` (uses `httpx.ASGITransport`, no server needed, real MySQL) and the Postman collections in `backend/postman/`. Collections run in order and depend on seed data (all seeded passwords: `Dkat@1234`; accounts `owner01`, `manager01` → CN01+CN02, `staff01` → CN01, `locked01`).
- The DB schema (18 tables) is created outside this repo (`Dkat-Database/` is empty locally). There are no migrations; SQLAlchemy models mirror existing tables. Extra tables come from the SQL files in `database/` (copied verbatim from the `tuiladien/*` line so merges don't conflict); e.g. `customers` needs `database/04_sales_order_customers.sql`, whose `USE dkat;` must match the local DB name (`DB_NAME`).
- Don't declare `ForeignKey(...)` to a table that has no ORM model (e.g. `stores`): the ORM flush fails with `NoReferencedTableError` (500). The FK lives in the DB anyway. `GET /api/v1/health/db` (OWNER only) reports missing tables.

### Architecture

- Each feature is `app/modules/<module>/{router,schemas,service,repository,models}.py`. Flow is strictly `router → service → repository → DB`: routers never write SQL, repositories hold no business rules. Many modules are still empty placeholder files. Register every new router in `app/api/v1/router.py` (mounted at `/api/v1`).
- **Responses:** routes return `ok(data)` → `{"success": true, "data": ...}` and declare `response_model=SuccessResponse[X], response_model_by_alias=True`. Errors: raise `AppError(status, CODE, message, details)` or its helpers (`AppError.not_found(...)`, `.forbidden`, `.conflict`, `.validation`). `core/exceptions.py` turns everything (validation, IntegrityError 1062/1451/1452, DB down) into `{"success": false, "error": {code, message, details}}`.
- **JSON is camelCase:** schemas extend `CamelModel` from `app/modules/auth/schemas.py` (alias generator), while Python attributes stay snake_case.
- **Transactions:** `get_db()` gives one `AsyncSession` per request. Wrap writes in `async with transaction(db):` (it uses a SAVEPOINT plus commit when the session already auto-began, which is always the case after `require_auth` ran). Outside requests use `standalone_transaction()`. Use `with_for_update()` when a check-then-write must not race (see `branches.service.change_status`).
- **Auth / RBAC (`app/core/permissions.py`):**
  - `require_auth` verifies the JWT, then **reloads the user and their branch ids from the DB on every request** (token claims are never trusted for role/branches). Locked users get 403 `ACCOUNT_LOCKED`.
  - `require_role(ROLE_OWNER, ...)` gives 403 `FORBIDDEN`.
  - `require_branch_access()` reads `branch_id`/`branchId` from the path, query **and** JSON body; values that disagree → 400. OWNER may access every branch of their store (any status). MANAGER/EMPLOYEE may access only ACTIVE branches assigned in `user_branches`; anything else is 403, never 404.
  - For list endpoints, filter with `get_accessible_branch_ids(user)` (an empty list means return nothing, not "no filter"). For branch ids taken from loaded records, call `ensure_branch_access(db, user, branch_id)`.
  - Put role checks in the route's `dependencies=[...]` so they run before branch checks and before body validation; that way a wrong role gets 403, not 422.
- Account management (`/users`): OWNER manages every account of the store. A MANAGER manages only EMPLOYEE accounts whose ACTIVE branches all lie within the manager's branches (`users.service._in_manager_scope`; the paged list repeats this rule in SQL in `users.repository.list_users_page`, so keep the two in sync). Accounts are never deleted, only LOCKED. `UserOut` deliberately has no password field.
- Public catalog (`app/modules/catalog`, `/api/v1/public/*`): no auth, rate limited per IP by `core/rate_limit.py` (in-memory, per worker). Response schemas are an allowlist (FR-07.5): never add cost price, stock quantities, product codes, store ids or statuses. Only the product detail (`GET /public/products/{id}`, FR-07.4) exposes variant id + SKU and per-branch `IN_STOCK`/`OUT_OF_STOCK`, because the pre-order form submits `variantId` + `branchId`. "Available stock" = `inventory.quantity` minus `allocated_quantity` of WAITING_STOCK/READY/NOTIFIED pre-orders at that branch (same formula as the inventory module on `tuiladien/*`).
- Customers (`/customers`): store-level, one per phone per store; phones are normalized to `0xxxxxxxxx` (`customers.schemas.normalize_phone`) before any lookup. Other modules create/reuse profiles with `customers.service.upsert_customer_by_phone` inside their own transaction. NFR-08: lists and `/customers/quick-search` return only `{id, fullName, maskedPhone}`; full contact data comes only from `GET /customers/{id}`, which writes an audit line via `core/audit.log_customer_view` (file `logs/customer_access.log`, ids only). `RequestLoggerMiddleware` masks `phone`/`email`/`keyword` query values; keep personal data out of logs.
- Roles: `OWNER`, `MANAGER`, `EMPLOYEE`. Branches are never deleted: they are set INACTIVE, which is refused while pre-orders are `WAITING_STOCK`/`READY`/`NOTIFIED`. Creating or reactivating a branch inserts `inventory` rows with quantity 0 for the store's ACTIVE variants. The effective permission table is in `docs/rbac-matrix.md`.

### Gotchas

- On Windows the console is cp1252: `print()` of Vietnamese text in scripts raises `UnicodeEncodeError` (and rolls back a seed transaction). Keep script output ASCII, or call `sys.stdout.reconfigure(encoding="utf-8")` / set `PYTHONIOENCODING=utf-8`.
- In Postman test scripts, don't declare a variable named `data` (it is a sandbox global).

## Frontend (`frontend/`): React 19 + Vite 7, plain JS demo (Node >= 22.12)

```powershell
npm ci
npm run dev        # vite on 127.0.0.1
npm run build      # base './'; do not open dist/index.html via file://
npm test           # node --test tests/*.test.js
node --test --test-name-pattern "<name>" tests/domain.test.js   # single test
```

- The running app is `index.html` → `src/main.jsx` (all screens/dialogs in one file, hash routes like `/#/admin/...`). It is a **browser-only demo**: business logic is mocked in `src/domain.js` with data from `src/seed.js` persisted in localStorage key `dkat-demo-v1`. It does not call the backend yet.
- The `.ts/.tsx` files (`src/main.tsx`, `src/app/`, `src/features/*/api.ts|types.ts`, `src/layouts/`, `src/lib/`) are empty placeholders for a planned TypeScript feature-folder structure.
- `src/api.js` is the future HTTP adapter (`VITE_API_BASE_URL`, default `http://127.0.0.1:8000/api/v1`, Bearer token). It currently reads `data.detail` for error messages, but the backend returns `error.message`; fix this when wiring it up.
- Root `Install-to-D.ps1` / `Start-DKat.ps1` install to `D:\Dkat` and launch the frontend dev server only.
