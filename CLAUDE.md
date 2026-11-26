# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

DKat is a multi-branch store management platform (inventory, POS, sales orders, pre-orders with FIFO allocation) built by a student team. Specs live in DKat_SRS.docx / DKat_CSDL.docx (not in the repo); code and READMEs cite requirement ids (FR-01.4, BR-10) and backlog items (PBI 99, PBI 129...). Docs, commit messages and API error messages are in Vietnamese; code identifiers and comments are in English.

## Repository and branches

- Remote: https://github.com/Sales-management-platform-DKat/Dkat. `master` is the integration branch; work happens on `feature/task-*`, `<member>/<feature>` (e.g. `tuan/*`, `tuiladien/pbi-*`) and `ngtrongkhanq`. Commit messages use conventional prefixes (`feat:`, `fix:`, `test:`, `merge:`).
- There are **two backend lines**. `master` and its descendants (this tree) run the **sync** backend described below. The `tuan/*` branches have an **async** SQLAlchemy/aiomysql backend (`AsyncSession`, `ok()` envelope, `CamelModel`, `require_role`). It was partly ported into `master` ("port compatible features into current backend"), so some async files remain here as **dead code** that nothing imports: `app/api/v1/router.py`, `app/modules/health/`, the `AsyncSession` functions in `auth/repository.py`, `branches/repository.py`/`service.py`, `users/` repository/service, `scripts/check_rbac.py`, `scripts/seed_auth.py` and `backend/postman/`. Don't follow their patterns, and don't expect them to run on this line.

## Backend (`backend/`): FastAPI + SQLAlchemy 2 (sync) + PyMySQL / SQLite

### Commands (run from `backend/`)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload            # Swagger at http://127.0.0.1:8000/docs
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v      # unit tests, in-memory SQLite
.\.venv\Scripts\python.exe -m unittest tests.test_auth_flow.AuthFlowTests.test_name   # single test
.\.venv\Scripts\python.exe -m app.workers.preorder_expiry              # one pre-order expiry sweep
```

- Unit tests (`tests/`) use `fastapi.testclient.TestClient` against SQLite. `SELECT ... FOR UPDATE` is faked there, so locking and concurrency are only exercised by the MySQL tests below.
- `integration_tests/*_mysql.py` are skipped unless a gate env var is set (e.g. `DKAT_PAYMENT_TEST_DB=1`). They refuse to run unless the DB is a local, disposable schema (e.g. `dkat_pbi99_test`). Run them through `scripts/test_pbi<N>_mysql.ps1` or `scripts/test_system_audit_mysql.ps1`, which set that up. Never point them at team data.
- `backend/.env` points at the **production TiDB**. For manual testing run `scripts/dev_isolated_mysql.ps1 -EnvFile <file>` (disposable mysqld with all schema scripts) and start the app with `DKAT_DATABASE_URL=mysql+pymysql://…` while masking `DB_*` (set them to a space; an empty value on Windows deletes the variable and `.env` refills it).
- Postman collections for each PBI are in `backend/samples/`. Set `accessToken` from a login.

### Configuration and database

- `app/core/config.py` reads `backend/.env` (template: `.env.example`). If any `DB_HOST/DB_PORT/DB_NAME/DB_USER` is set → MySQL/TiDB through `mysql+pymysql` with TLS verification. Otherwise → `DKAT_DATABASE_URL` or `sqlite:///./dkat.db`. When `DKAT_ENV=production`, startup **fails** on SQLite or incomplete DB config (see `DEPLOYMENT_DATABASE.md`).
- Other env vars: `DKAT_AUTH_SECRET_KEY` (≥32 chars), `DKAT_ADMIN_TOKEN` (≥32 chars, `X-Admin-Token` for `/api/v1/admin/accounts` to create store + subscription + OWNER), `DKAT_COOKIE_SECURE`, `DKAT_CORS_ORIGINS`, `PREORDER_READY_DAYS`, `ALLOW_EMPLOYEE_STOCK`, `DKAT_PRODUCT_IMAGE_DIR` (default `backend/uploads/products`, git-ignored).
- There are no migrations. The schema is `database/01_schema.sql` plus the numbered incremental scripts `database/02_*.sql`…`08_*.sql` and `samples/02_auth_schema.sql` (auth_sessions, store_subscriptions). The app's `create_all()` at startup only creates **missing** tables and never alters existing ones; an old `dkat.db` with a stale schema stays stale. `GET /health` checks `users.user_id` to detect this. MySQL and SQLite are separate databases with separate data.

### Architecture

- `app/main.py` mounts every module router under `/api/v1` directly. Register new routers **there**, not in `app/api/v1/router.py`. A FastAPI lifespan runs `create_all`. `app/workers/` holds the hourly pre-order expiry job (READY/NOTIFIED past `expires_at` → EXPIRED) and notification work.
- Modules live in `app/modules/<module>/` (router/schemas/service/repository/models), but layering is loose: some routers (e.g. `branches/router.py`) run raw `text()` SQL directly. Larger domains are split up: `preorders/services/{creation,allocation,payment,fulfillment,cancellation,lifecycle,...}.py`, `preorders/public_router.py` (unauthenticated tracking/creation, with `rate_limit.py`), and `products/` (categories, variants, CSV import, image storage).
- DB access is a sync `Session` from `app/db/session.get_db()` (SQLite gets `PRAGMA foreign_keys=ON`), or `engine.begin()` for raw-SQL blocks. Stock and pre-order writes take `FOR UPDATE` locks. Work that must happen after commit (FIFO allocation after stock import, notifications) runs once the transaction has committed; `ready_preorder_ids` is passed out of it for that.
- **Errors:** the `AppError`/envelope handlers in `core/exceptions.py` are **not registered** in `main.py`. Endpoints raise `HTTPException` with either a Vietnamese string or a dict like `{"code": "ORDER_NOT_PENDING", ...}`, so clients receive FastAPI's `{"detail": ...}`. JSON fields are mostly snake_case; some newer endpoints accept camelCase (e.g. `dryRun`).
- **Auth (`core/security.py`, `core/permissions.py`, `modules/auth`):** 15-min HS256 access tokens carry a session id (`sid`). Each request loads the `auth_sessions` row and the user, and rejects revoked or expired sessions, non-ACTIVE users and stores whose subscription has lapsed. Refresh tokens rotate and are stored hashed, in an HttpOnly cookie (30 days with "remember me", otherwise 12 h). Passwords are PBKDF2.
- **Roles:** the DB stores `OWNER`/`MANAGER`/`EMPLOYEE`; `require_roles()` maps them to `owner`/`manager`/`staff`. Login picks the role by username suffix: `name` = owner, `name:manager`, `name:staff`. Dependencies: `require_auth` / `require_owner` / `require_owner_or_manager` → `Actor(store_id, role, user_id)`. Branch scoping: `get_accessible_branch_ids(db, actor)` (OWNER = all store branches, others = their `user_branches`), and `require_branch_access(db, actor, branch_id)` returns 403. `docs/rbac-matrix.md` documents the intended matrix.

## Frontend (`frontend/`): React 19 + Vite 7, plain JS (Node >= 22.12)

```powershell
npm ci
npm run dev        # 127.0.0.1:5173; proxies /api and /health to 127.0.0.1:8000
npm run build      # base './'; don't open dist/index.html via file://
npm test           # node --test tests/*.test.js
node --test --test-name-pattern "<name>" tests/live-api-flows.test.js   # single test
```

- Entry: `index.html` → `src/main.jsx`, with hash routes: `/` landing, `#/login`, `#/platform-admin`, `#/track/<token>` (public pre-order tracking), `#/catalog`, `#/demo`, `#/admin/<screen>`.
- Admin screens are `src/features/<feature>/*Page.jsx` with an `api.js` per feature, calling `apiRequest` from `src/auth-client.js` (bearer token, silent refresh; failures become `ApiError` with a friendly Vietnamese `message`, `status`, `code`, `fieldErrors` from `src/lib/api-errors.js`).
  - **Demo mode uses the same screens**: `main.jsx` calls `setDemoApiHandler(createDemoApi(role))`, so every `apiRequest` goes to `src/demo/demo-api.js`, an in-browser backend (localStorage `dkat-demo-api-v2`) that mirrors the real response shapes and RBAC. When adding an endpoint used by a page, add it there too. `#/catalog` reads the same demo store.
  - Customer Display: `#/pos/customer-display` (standalone, no auth) receives cart state from `POSPage` over BroadcastChannel/postMessage (`src/features/customer-display/`). Only display data is sent.
  - `src/domain.js` + `src/seed.js` (localStorage `dkat-demo-v1`) now only back the demo Settings/notifications/track screens.
  - `src/api.js` is an older unused adapter. The root-level `src/Live*.jsx`, `CsvStockImport.jsx`, `ProductsPage.jsx`, `CategoriesPage.jsx`, `ComponentDemo.jsx`, `BusinessAnalytics.jsx` and `src/branches/BranchContext.jsx` are earlier screens that nothing imports any more, so edit `features/` instead.
  - `src/mocks/api.js` (`mockApiRequest`) is a browser mock of the API used by `tests/live-api-flows.test.js`. The README mentions `VITE_USE_MOCK`, but nothing in `src/` reads that variable.
- The `.ts/.tsx` files (`src/main.tsx`, `src/app/`, `src/lib/`, `src/layouts/`, `features/*/api.ts|types.ts`) are empty placeholders for a planned TypeScript migration.
- Shared UI: `src/components/ui.jsx`, `src/components/states.jsx` (loading/empty/error/status badge) and `src/components/overlay/` (`Dialog`, `Drawer`, `FormDialog`, `ConfirmDialog`, `pushToast`, `confirmAction`). `pushToast` and `confirmAction` (a promise, signalled by a `dkat-confirm` window event) only work because `main.jsx` mounts `<Toaster/>` and `<ConfirmHost/>` once at the root. Use them (`notify.success/error/warning` from the overlay index) and `FormDialog` + `FormField` for forms (inline + server field errors, unsaved-changes guard); never `window.confirm`/`prompt`. The landing CSS styles bare `footer` globally; `app-shared.css` resets it for dialog footers.
- i18n: `src/i18n/` + `src/locales/{vi,en}.json`. `vite.config.js` uses the classic `React.createElement` JSX factory on purpose: the i18n layer hooks `createElement` to translate literal JSX text in the legacy screens. Don't switch to the automatic JSX runtime.

## QA and gotchas

- Test cases and the execution report are in `docs/qa/`; the system audit is in `docs/SYSTEM_AUDIT_2026-11-24.md`. Sample CSVs for product and stock import are in `data/`.
- On Windows the console is cp1252: `print()` of Vietnamese text in scripts raises `UnicodeEncodeError`. Keep script output ASCII, or set `PYTHONIOENCODING=utf-8`.
- Root `Install-to-D.ps1` / `Start-DKat.ps1` install to `D:\Dkat` and start only the frontend dev server.
