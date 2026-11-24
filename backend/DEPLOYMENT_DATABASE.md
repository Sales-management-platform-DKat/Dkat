# Backend database deployment

## Current configuration

The backend uses SQLAlchemy. Local `backend/.env` selects `mysql+pymysql` through `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD`; the verified local database uses port `4000` and contains `users.user_id`.

`backend/app/core/config.py` previously selected `sqlite:///./dkat.db` whenever no `DB_*` values were present. That development fallback explains why the tunneled Linux backend opened an old SQLite file whose `users` table has no `user_id` column. `create_all()` creates missing tables but does not transform an existing table into the current schema. The project has SQL schema scripts and no Alembic migration environment.

## Configure a Cloudflare Tunnel backend

Cloudflare Tunnel forwards HTTP traffic to the backend; it does not provide a MySQL database. The process behind the tunnel must have network access to the same MySQL/TiDB instance and use its credentials from the host's secret/environment settings.

Set these variables in the Linux environment that launches Uvicorn:

```text
DKAT_ENV=production
DB_HOST=<database host>
DB_PORT=4000
DB_NAME=<database name>
DB_USER=<database user>
DB_PASSWORD=<database password>
```

Do not commit the values or paste them into chat. Ensure the database firewall permits outbound connections from the backend host, and use the required TLS settings for the database provider. Restart Uvicorn after changing the environment. If the host cannot reach the database, configure a reachable MySQL/TiDB service; the tunnel itself cannot bridge the database connection.

Production startup now fails with a configuration error if the server database is missing, partial, or set to SQLite. SQLite remains available for local development. The backend never migrates, drops, or recreates the existing `dkat.db` file as part of this change.

## Verify without exposing credentials

After restarting the backend:

1. `GET /health` should return `{"status":"ok","database":"up"}`. It verifies that `users.user_id` is queryable.
2. Check the process startup succeeds with `DKAT_ENV=production`; a missing/invalid database configuration stops startup instead of serving login against stale SQLite.
3. Try login over the Cloudflare hostname. Successful authentication returns the existing access-token response; an invalid password returns HTTP 401 JSON. A database connection/schema failure returns an unavailable health status and is recorded server-side without logging the password or database URL.

The old SQLite database may contain data. Keep it as-is unless a separate, backed-up, verified data migration is planned. This deployment fix points the backend to the existing MySQL/TiDB schema; it does not migrate SQLite data.
