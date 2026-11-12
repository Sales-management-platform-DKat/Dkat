"""RBAC check: 3 roles x 5 routes + authentication and branch-id edge cases.

Runs the app in-process (no uvicorn needed) against the real MySQL database.
Requires the seed data:  python -m scripts.seed_auth
Run from backend/:       python -m scripts.check_rbac
Exit code 0 = every case matches docs/rbac-matrix.md, 1 = at least one mismatch.

Products created by this script use the code prefix RBAC-TEST- and are deleted at the end.
"""
import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from fastapi import Body, Depends, Request
from sqlalchemy import text

from app.core.config import settings
from app.core.permissions import CurrentUser, require_branch_access
from app.db.session import close_engine, standalone_transaction
from app.main import create_app
from app.utils.response import ok

PASSWORD = "Dkat@1234"
ROLES = {"OWNER": "owner01", "MANAGER": "manager01", "EMPLOYEE": "staff01"}
API = settings.API_V1_PREFIX
TEST_CODE_PREFIX = "RBAC-TEST-"

results: list[tuple[bool, str, str, str, str]] = []  # ok, group, case, expected, actual


def record(group: str, case: str, resp: httpx.Response, status: int, code: str | None = None, check=None) -> None:
    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    actual_code = (body.get("error") or {}).get("code") if isinstance(body, dict) else None
    passed = resp.status_code == status and (code is None or actual_code == code)
    extra = ""
    if passed and check is not None:
        passed, extra = check(body)
    expected = f"{status}{' ' + code if code else ''}"
    actual = f"{resp.status_code}{' ' + actual_code if actual_code else ''}{' ' + extra if extra else ''}"
    results.append((passed, group, case, expected, actual))


def build_app():
    app = create_app()

    # Probe route: only exists in this script, to test branch_id taken from query / JSON body
    async def probe(
        request: Request,
        body: dict | None = Body(default=None),
        user: CurrentUser = Depends(require_branch_access()),
    ):
        return ok({"branchId": getattr(request.state, "branch_id", None), "bodyStillReadable": body is not None})

    app.add_api_route(f"{API}/__rbac_probe", probe, methods=["POST"])
    return app


async def load_ids() -> tuple[dict[str, int], int, int, list[int]]:
    async with standalone_transaction() as db:
        rows = (await db.execute(text("SELECT branch_code, branch_id FROM branches WHERE branch_code IN ('CN01','CN02','CN03')"))).all()
        branches = {code: bid for code, bid in rows}
        category_id = (await db.execute(text("SELECT category_id FROM categories WHERE status = 'ACTIVE' ORDER BY category_id LIMIT 1"))).scalar()
        locked_id = (await db.execute(text("SELECT user_id FROM users WHERE username = 'locked01'"))).scalar()
        # OWNER sees every branch of the store, including branches created later via POST /branches
        store_branch_ids = list(
            (
                await db.execute(
                    text(
                        "SELECT branch_id FROM branches WHERE store_id = "
                        "(SELECT store_id FROM users WHERE username = 'owner01') ORDER BY branch_id"
                    )
                )
            ).scalars()
        )
    missing = {"CN01", "CN02", "CN03"} - set(branches)
    if missing or category_id is None or locked_id is None:
        sys.exit(f"Missing seed data ({sorted(missing) or 'category/locked01'}). Run: python -m scripts.seed_auth")
    return branches, category_id, locked_id, store_branch_ids


async def cleanup() -> None:
    async with standalone_transaction() as db:
        await db.execute(text("DELETE FROM products WHERE product_code LIKE :p"), {"p": TEST_CODE_PREFIX + "%"})


async def main() -> int:
    branches, category_id, locked_id, store_branch_ids = await load_ids()
    cn1, cn2, cn3 = branches["CN01"], branches["CN02"], branches["CN03"]
    transport = httpx.ASGITransport(app=build_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # ---------------------------------------------------------------- login
        tokens: dict[str, str] = {}
        for role, username in ROLES.items():
            r = await client.post(f"{API}/auth/login", json={"username": username, "password": PASSWORD})
            if r.status_code != 200:
                sys.exit(f"Login {username} failed: {r.status_code} {r.text}")
            tokens[role] = r.json()["data"]["token"]

        # ---------------------------------------------------------------- 1) require_auth
        g = "require_auth"
        record(g, "Không có token -> GET /auth/me", await client.get(f"{API}/auth/me"), 401, "UNAUTHORIZED")
        record(g, "Token rác", await client.get(f"{API}/auth/me", headers={"Authorization": "Bearer abc.def.ghi"}), 401, "INVALID_TOKEN")
        record(g, "Sai scheme (Basic)", await client.get(f"{API}/auth/me", headers={"Authorization": "Basic Zm9vOmJhcg=="}), 401, "UNAUTHORIZED")
        past = datetime.now(timezone.utc) - timedelta(hours=9)
        expired = jwt.encode({"sub": "1", "iat": past, "exp": past + timedelta(hours=1)}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        record(g, "Token hết hạn", await client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {expired}"}), 401, "TOKEN_EXPIRED")
        forged = jwt.encode({"sub": "1", "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "wrong-secret-wrong-secret-wrong-secret", algorithm="HS256")
        record(g, "Token ký sai secret", await client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {forged}"}), 401, "INVALID_TOKEN")
        now = datetime.now(timezone.utc)
        locked = jwt.encode({"sub": str(locked_id), "iat": now, "exp": now + timedelta(hours=1)}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        record(g, "Token hợp lệ của tài khoản LOCKED", await client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {locked}"}), 403, "ACCOUNT_LOCKED")
        record(g, "Không token -> POST /products", await client.post(f"{API}/products", json={}), 401, "UNAUTHORIZED")
        record(g, "Không token -> GET /branches/CN01/inventory", await client.get(f"{API}/branches/{cn1}/inventory"), 401, "UNAUTHORIZED")

        # ---------------------------------------------------------------- 2) 3 roles x 5 routes
        def h(role: str) -> dict[str, str]:
            return {"Authorization": f"Bearer {tokens[role]}"}

        def branch_ids_are(expected: list[int]):
            def check(body):
                got = body["data"]["branchIds"]
                return got == expected, f"branchIds={got}"
            return check

        expected_ids = {"OWNER": store_branch_ids, "MANAGER": [cn1, cn2], "EMPLOYEE": [cn1]}
        # route -> {role: expected status}
        matrix = [
            ("R1 GET /auth/me", lambda r: client.get(f"{API}/auth/me", headers=h(r)), {"OWNER": 200, "MANAGER": 200, "EMPLOYEE": 200}),
            ("R2 GET /health/db", lambda r: client.get(f"{API}/health/db", headers=h(r)), {"OWNER": 200, "MANAGER": 403, "EMPLOYEE": 403}),
            (
                "R3 POST /products",
                lambda r: client.post(
                    f"{API}/products",
                    headers=h(r),
                    json={"categoryId": category_id, "productCode": f"{TEST_CODE_PREFIX}{r}-{time.time_ns()}", "name": f"RBAC test {r}"},
                ),
                {"OWNER": 201, "MANAGER": 403, "EMPLOYEE": 403},
            ),
            ("R4 GET /branches/CN01/inventory", lambda r: client.get(f"{API}/branches/{cn1}/inventory", headers=h(r)), {"OWNER": 200, "MANAGER": 200, "EMPLOYEE": 200}),
            ("R4 GET /branches/CN02/inventory", lambda r: client.get(f"{API}/branches/{cn2}/inventory", headers=h(r)), {"OWNER": 200, "MANAGER": 200, "EMPLOYEE": 403}),
            ("R4 GET /branches/CN03/inventory", lambda r: client.get(f"{API}/branches/{cn3}/inventory", headers=h(r)), {"OWNER": 200, "MANAGER": 403, "EMPLOYEE": 403}),
            ("R5 GET /inventory (không lọc)", lambda r: client.get(f"{API}/inventory", headers=h(r)), {"OWNER": 200, "MANAGER": 200, "EMPLOYEE": 200}),
            ("R5 GET /inventory?branch_id=CN03", lambda r: client.get(f"{API}/inventory", params={"branch_id": cn3}, headers=h(r)), {"OWNER": 200, "MANAGER": 403, "EMPLOYEE": 403}),
        ]
        for name, call, expected in matrix:
            for role in ROLES:
                status = expected[role]
                check = branch_ids_are(expected_ids[role]) if name.startswith("R5 GET /inventory (") else None
                record("matrix", f"{name} [{role}]", await call(role), status, "FORBIDDEN" if status == 403 else None, check)

        # ---------------------------------------------------------------- 3) edge cases
        g = "edge"
        record(g, "EMPLOYEE POST /products body sai -> vẫn 403 (không lộ validation)", await client.post(f"{API}/products", headers=h("EMPLOYEE"), json={"x": 1}), 403, "FORBIDDEN")
        record(g, "OWNER chi nhánh không tồn tại -> 404", await client.get(f"{API}/branches/999999/inventory", headers=h("OWNER")), 404, "NOT_FOUND")
        record(g, "MANAGER chi nhánh không tồn tại -> 403 (không dò được id)", await client.get(f"{API}/branches/999999/inventory", headers=h("MANAGER")), 403, "FORBIDDEN")
        record(g, "branch_id không phải số -> 400", await client.get(f"{API}/inventory", params={"branch_id": "abc"}, headers=h("OWNER")), 400, "BAD_REQUEST")
        record(g, "branchId trong body, MANAGER, CN03 -> 403", await client.post(f"{API}/__rbac_probe", headers=h("MANAGER"), json={"branchId": cn3}), 403, "FORBIDDEN")
        record(
            g,
            "branchId trong body, MANAGER, CN02 -> 200 (body vẫn đọc được)",
            await client.post(f"{API}/__rbac_probe", headers=h("MANAGER"), json={"branchId": cn2}),
            200,
            check=lambda b: (b["data"] == {"branchId": cn2, "bodyStillReadable": True}, f"data={b['data']}"),
        )
        record(g, "branch_id trong body (snake_case), EMPLOYEE, CN02 -> 403", await client.post(f"{API}/__rbac_probe", headers=h("EMPLOYEE"), json={"branch_id": cn2}), 403, "FORBIDDEN")
        record(g, "query CN01 nhưng body CN03 -> 400 (không khớp)", await client.post(f"{API}/__rbac_probe", params={"branch_id": cn1}, headers=h("MANAGER"), json={"branchId": cn3}), 400, "BAD_REQUEST")
        record(g, "OWNER body CN03 -> 200", await client.post(f"{API}/__rbac_probe", headers=h("OWNER"), json={"branchId": cn3}), 200)

    await cleanup()
    await close_engine()

    # ---------------------------------------------------------------- report
    width = max(len(c) for _, _, c, _, _ in results)
    group = None
    for passed, grp, case, expected, actual in results:
        if grp != group:
            print(f"\n== {grp}")
            group = grp
        print(f"  {'PASS' if passed else 'FAIL'}  {case.ljust(width)}  expected {expected:<18} got {actual}")
    failed = sum(not r[0] for r in results)
    print(f"\n{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))
