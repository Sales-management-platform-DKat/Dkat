# DKat system audit

## Scope and baseline

- Audited the `master` checkout at commit `7926c61`.
- Frontend: React 19 + Vite; the active HTML entry is `frontend/src/main.jsx`. `main.tsx`, `app/App.tsx`, `app/router.tsx`, and `app/providers.tsx` are empty placeholders.
- Backend: FastAPI + SQLAlchemy + PyMySQL, split into domain modules under `backend/app/modules`.
- Database: MySQL/TiDB-compatible schema in `database/01_schema.sql`, with ordered SQL upgrade scripts `02` through `08`. There is no Alembic environment. Startup calls `Base.metadata.create_all()`, which creates missing tables but does not alter columns in existing tables.
- Authentication: access/refresh session flow and role checks exist. Store and branch scoping is implemented in several backend modules. Existing contracts are a mix of raw lists/objects and the optional `success/data` helper; a system-wide wrapper change would be breaking and is not recommended.
- The audit did not read or modify `.env` values, and did not access or mutate any database.

## API map

All business routers are mounted under `/api/v1` in `backend/app/main.py` unless noted.

| Area | Existing endpoints/capabilities | Audit status |
| --- | --- | --- |
| Auth | login, refresh, me, logout | Implemented; frontend login uses `auth-client.js` |
| Store admin | create/list/update store accounts and subscriptions | Implemented |
| Branches | list/detail/create/update/status | Implemented with role/store checks |
| Products | list/detail/create/update/status, CSV import, attributes, variants | Implemented; frontend page still uses local demo state |
| Categories | list/create/update/status | Implemented; no image upload/URL field found in current category model/API |
| Inventory | list, movements, import/export/stocktake, CSV import | Implemented; frontend page still uses local demo state |
| Sales | create/list/detail/cancel/payment/refund | Implemented; frontend POS/order flows still use local demo state |
| Preorders | public creation, list/detail/payment/fulfillment/cancel and expiry/FIFO services | Implemented; frontend flow still uses local demo state |
| Customers | list/search/profile/create/update/purchase history | Implemented; frontend page still uses local demo state |
| Employees/users | create store user | Partial: no employee list/update/deactivation/branch-assignment API found in the active router |
| Reports | revenue, summary, top products, revenue CSV export | Partial: no explicit dashboard endpoint; report API is present but current UI reports use local state |
| Notifications | models/services/workers exist | Partial: notification router is not mounted; current screen renders local demo rows |
| Health | `/health` checks `users.user_id` | Implemented |

The separate `frontend/src/features/*/api.*` files are not imported by the active `main.jsx`; `frontend/src/api.js` is explicitly an adapter for a future backend. Auth is the main active API integration.

## Database and security map

The base schema includes stores, branches, users/user_branches, categories, products/product_variants/attributes, inventory/movements, customers, sales orders/items, preorders/items, payments, fulfillments, and notifications. Auth additions include subscriptions and auth sessions. IDs and foreign keys connect business records to stores/branches/users.

Manual upgrade scripts are the current migration mechanism. Apply only the applicable ordered script after inspecting the deployed schema and taking a backup. Do not use `create_all()` as a substitute for migrations. Existing role and store/branch authorization must remain enforced server-side when adding list/update/report endpoints.

## Frontend and presentation findings

- The active application is a large single-file app in `frontend/src/main.jsx`; it imports `seed.js` and the domain helpers and stores business state in localStorage. Authenticated users still see the local-state workflows, while the UI itself notes that business data is not yet connected to the server.
- Product, customer, employee, inventory, POS/order, preorder, branch, report, and notification screens currently use that local state. The dashboard intentionally displays an API-not-connected message outside demo mode.
- A Vietnamese/English translation provider exists and stores the selection. Translation coverage is incomplete because many labels are inline Vietnamese. The code has an ad-hoc mojibake repair function, and HTML entities occur in JSX plus JavaScript string values; entities in ordinary JS strings are displayed literally.
- Light/dark state and CSS styling exist, but page components define many local styles and the overall application is not yet consistently driven by shared tokens/components.
- The current public demo is intentionally local-only. It should remain available as a distinct demo and must not be used as business data for authenticated sessions.

## Gaps and implementation order

1. Introduce a typed/central API service layer around the existing auth HTTP client and existing backend contracts. Keep raw response contracts intact during integration.
2. Complete missing backend capabilities with authorization tests first: employee list/update/status/branch assignment; dashboard summary using current report queries; notification list/read/unread only if the existing deployed schema supports it.
3. Connect authenticated UI workflows to the real APIs and provide loading, empty, and error states. Keep demo state isolated to explicit demo mode.
4. Complete real-data reporting and product/customer/preorder/employee workflows using existing endpoints; do not show cost/profit outside authorized roles.
5. Fix literal HTML entities/encoding, complete translation keys, and align responsive components/tokens without rewriting the visual system wholesale.
6. Review image storage before adding category image upload. No compatible image storage service/configuration was found in this audit; use a safe default image until storage is decided rather than inventing fake URLs.
7. Run backend tests and frontend tests/build after each integration group; add focused coverage for new API and permission behavior. Run against a disposable test database unless explicitly authorized for production data.

## Contract and data risks

- A global JSON envelope would break existing frontend and API consumers; use additive endpoints or update consumers in the same change only when necessary.
- Employee branch assignment and recipient-scoped notifications require careful schema/authorization review before writing data.
- The notification model is not proof that the deployed database has all expected columns. No notification migration should be applied without inspecting production schema and backup status.
- Product image upload needs a real storage target and size/type controls; the current category model has no image field.
- No live Cloudflare/VPS login or production database test was performed during this audit.

## Implementation progress (2026-11-24)

Changes currently in the local worktree, not committed:

- Added owner-scoped employee list, create, profile update, active/inactive status, branch assignment, and password-reset endpoints. The existing `/users` create path and login response contract remain intact. Employee status changes and password resets revoke sessions.
- Redacted variant cost prices from non-owner product detail responses.
- Connected authenticated customer and employee pages to the existing backend APIs.
- Connected authenticated dashboard, product catalog/detail, inventory, POS, sales orders, preorders, and branch screens to existing APIs. Demo-mode pages continue to use the local demo store explicitly.
- Added customer selection to POS and payment confirmation against the returned pending order total.
- Added customer lookup during preorder creation. The existing backend requires customer name, phone, address, and at least one currently unavailable product variant; the UI follows those constraints and does not decrement inventory when the preorder is created.
- Added product image uploads for JPEG, PNG, and WebP, with file signature/decoder validation, 5 MiB and 40 megapixel limits, image normalization, owner-only upload/delete, and public cacheable delivery. Images use the existing `products.image_url` column; no schema migration is needed. The local upload directory is ignored by Git and can be moved to persistent storage with `DKAT_PRODUCT_IMAGE_DIR`.
- Added category name editing through the existing category update endpoint.
- Added backend tests for employee management authorization/data handling and cost-price visibility.

Final verification: `python -m pytest -q -rs` reports 31 passed and 120 skipped; skipped cases explicitly require an isolated MySQL test database that is not configured here. `npm test` passes all 31 frontend tests. `npm run build` succeeds and `git diff --check` is clean. No database migration or production request was run.

Remaining gaps/constraints:

- Category image upload remains unavailable safely: categories have no image field. Product image uploads use the existing product field and filesystem storage; production must set `DKAT_PRODUCT_IMAGE_DIR` to a persistent backed-up directory.
- Notifications are not a general recipient-scoped notification system in the current database. The existing table is an SMS/email delivery queue tied to preorders; the notification module files are empty. Implementing user notifications/realtime updates would require an agreed schema migration and delivery/event design. The authenticated UI does not pretend demo notifications are real.
- Reports currently expose revenue, summary, top products, and revenue CSV export only. Separate slow-selling, inventory, customer, and branch-performance reports do not exist yet.
- System-wide API envelope and snake_case changes remain intentionally unimplemented because existing endpoints expose established mixed response contracts and changing them would break current consumers.
- A real login, payment, Cloudflare, or VPS integration run requires the user's deployed service/database; it was not claimed or performed here.
