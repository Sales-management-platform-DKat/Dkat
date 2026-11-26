"""Reset the DEMO database to a known state for the final demo (docs/demo/kich-ban-demo.md).

    python -m scripts.demo_reset            # from backend/, server may be stopped or running

What it does (about 20 seconds):
1. DROP + CREATE the database DB_NAME from database/01_schema.sql. Refuses any name that does not
   start with "dkat_demo", so it can never wipe a real database.
2. Seeds everything through the real API, in-process (same validation as the UI):
   store "DKat Fashion", branches CN01-CN03, owner01 / manager01 / staff01, 3 categories,
   4 products, stock, 30 days of paid sales for the dashboard, and customer "Chị Lan" who
   pre-ordered the out-of-stock jacket yesterday (queue position 1 for the FIFO step).
3. Prints the demo accounts and ids.

No SMS / email is sent while seeding. Required in backend/.env:
  DB_* (DB_NAME=dkat_demo), DB_SSL_MODE=disabled for a local MySQL, DKAT_ADMIN_TOKEN (32+ chars),
  DKAT_AUTH_SECRET_KEY. Optional: DEMO_PASSWORD (default DKat@Demo2026),
  DEMO_QUEUE_EMAIL (email of the seeded queue customer, default SMTP_FROM_EMAIL = the team mailbox).
"""
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pymysql

from app.core import config
from app.core.config import settings

BACKEND = Path(__file__).resolve().parents[1]
SCHEMA = BACKEND.parent / "database" / "01_schema.sql"
PASSWORD = os.getenv("DEMO_PASSWORD", "DKat@Demo2026")
VN = timezone(timedelta(hours=7))

BRANCHES = [  # code, name, address, phone (fictional hotline shown in SMS / email)
    ("CN01", "DKat Quận 1", "12 Lê Lợi, Quận 1, TP.HCM", "028 3822 1001"),
    ("CN02", "DKat Cầu Giấy", "88 Xuân Thủy, Cầu Giấy, Hà Nội", "024 3756 2002"),
    ("CN03", "DKat Hải Châu", "45 Bạch Đằng, Hải Châu, Đà Nẵng", "0236 382 1003"),
]
USERS = [("manager01", "Trần Thị Quản Lý", "manager", ["CN01", "CN02"]), ("staff01", "Lê Văn Bán Hàng", "staff", ["CN01"])]
# category, product, [(sku, variant, price, cost, stock CN01, stock CN02)]
CATALOG = [
    ("Áo", "Áo thun cotton DKat", [("AT-COT-S", "Trắng / S", 199000, 90000, 40, 20), ("AT-COT-M", "Trắng / M", 199000, 90000, 50, 25),
                                     ("AT-COT-L", "Trắng / L", 199000, 90000, 35, 20)]),
    ("Quần", "Quần jean slim", [("QJ-SLIM-29", "Xanh / 29", 449000, 220000, 20, 10), ("QJ-SLIM-30", "Xanh / 30", 449000, 220000, 25, 12),
                                ("QJ-SLIM-31", "Xanh / 31", 449000, 220000, 18, 8)]),
    ("Phụ kiện", "Mũ lưỡi trai DKat", [("MU-LT-DEN", "Đen", 149000, 60000, 45, 30)]),
    ("Áo", "Áo khoác gió DKat", [("AK-GIO-DEN-M", "Đen / M", 599000, 300000, 0, 0), ("AK-GIO-DEN-L", "Đen / L", 599000, 300000, 6, 4)]),
]
HERO_SKU = "AK-GIO-DEN-M"  # out of stock everywhere: pre-ordered on the website during the demo
CUSTOMERS = [("Nguyễn Minh Anh", "0901000001"), ("Phạm Quốc Bảo", "0901000002"), ("Võ Thu Hà", "0901000003")]


def fail(message: str) -> None:
    print(f"DEMO RESET FAILED: {message}")
    sys.exit(1)


def recreate_database() -> str:
    url = config.DATABASE_URL
    name = getattr(url, "database", None)
    if not name or not re.fullmatch(r"dkat_demo\w*", name):
        fail(f"DB_NAME must start with 'dkat_demo' (got {name!r}); this script drops the whole database")
    sql = SCHEMA.read_text(encoding="utf-8")
    sql = re.sub(r"^\s*(CREATE DATABASE|USE)\b[^;]*;", "", sql, flags=re.M | re.I)
    sql = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    conn = pymysql.connect(host=url.host, port=url.port, user=url.username, password=url.password or "",
                           charset="utf8mb4", autocommit=True, **config.DATABASE_CONNECT_ARGS)
    with conn.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS `{name}`")
        cur.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        cur.execute(f"USE `{name}`")
        for statement in statements:
            cur.execute(statement)
    conn.close()
    return name


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(config.ADMIN_TOKEN) < 32:
        fail("DKAT_ADMIN_TOKEN (32+ characters) is required in backend/.env")
    started = time.perf_counter()
    db_name = recreate_database()

    # nothing may be sent while seeding, and the retry job is not needed in-process
    settings.NOTIFY_RETRY_ENABLED = False
    queue_email = os.getenv("DEMO_QUEUE_EMAIL") or settings.SMTP_FROM_EMAIL or "khach.lan@example.com"
    settings.SMTP_HOST = settings.ESMS_API_KEY = settings.ESMS_SECRET_KEY = ""

    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from app.db.session import engine
    from app.main import app

    with TestClient(app) as client:
        def call(method, path, token=None, body=None, expect=(200, 201), **kw):
            headers = kw.pop("headers", {})
            if token:
                headers["Authorization"] = f"Bearer {token}"
            r = client.request(method, f"/api/v1{path}", json=body, headers=headers, **kw)
            if r.status_code not in expect:
                fail(f"{method} {path} -> {r.status_code} {r.text[:300]}")
            return r.json() if r.content else None

        shop = call("POST", "/admin/accounts", headers={"X-Admin-Token": config.ADMIN_TOKEN}, body={
            "shop_name": "DKat Fashion", "plan": "basic", "subscription_months": 12, "owner_username": "owner01",
            "owner_full_name": "Nguyễn Văn Chủ", "owner_password": PASSWORD, "owner_email": "owner01@dkat-demo.example"})
        owner = call("POST", "/auth/login", body={"username": "owner01", "password": PASSWORD})["access_token"]

        branch = {code: call("POST", "/branches", owner, {"branchCode": code, "name": name, "address": address, "phone": phone})["id"]
                  for code, name, address, phone in BRANCHES}
        for username, full_name, role, codes in USERS:
            call("POST", "/users", owner, {"username": username, "full_name": full_name, "password": PASSWORD, "role": role,
                                           "branch_ids": [branch[c] for c in codes]})

        categories, variants, prices = {}, {}, {}
        for cat_name, product_name, lines in CATALOG:
            if cat_name not in categories:
                categories[cat_name] = call("POST", "/categories", owner, {"name": cat_name})["categoryId"]
            product = call("POST", "/products", owner, {"categoryId": categories[cat_name], "name": product_name,
                                                        "description": f"{product_name} - hàng mẫu cho buổi demo"})["productId"]
            for sku, name, price, cost, *_ in lines:
                variants[sku] = call("POST", f"/products/{product}/variants", owner, {
                    "sku": sku, "variantName": name, "price": str(price), "costPrice": str(cost)})["variant_id"]
                prices[sku] = price
        for idx, code in ((4, "CN01"), (5, "CN02")):
            items = [{"variantId": variants[line[0]], "quantity": line[idx]} for _, _, lines in CATALOG for line in lines if line[idx] > 0]
            call("POST", "/inventory/import", owner, {"branchId": branch[code], "note": "Tồn kho đầu kỳ demo", "items": items})

        customer_ids = [call("POST", "/customers", owner, {"fullName": n, "phone": p})["customerId"] for n, p in CUSTOMERS]

        # 30 days of paid sales (yesterday back to 30 days ago), then moved back in time
        rng = random.Random(2026)
        sellable = [sku for sku in prices if sku != HERO_SKU and not sku.startswith("AK-")]
        today_vn = datetime.now(VN).replace(hour=0, minute=0, second=0, microsecond=0)
        stock = {(code, line[0]): line[idx] for _, _, lines in CATALOG for line in lines for idx, code in ((4, "CN01"), (5, "CN02"))}
        keep = 10  # leave enough stock for the live POS sale
        history = []
        for days_ago in range(29, 0, -1):  # inside the dashboard's default 30-day window
            for _ in range(rng.randint(1, 4)):
                code = rng.choice(["CN01", "CN01", "CN02"])
                candidates = [s for s in sellable if stock[(code, s)] >= keep + 2]
                if not candidates:
                    continue
                lines = [(s, rng.randint(1, 2)) for s in rng.sample(candidates, min(len(candidates), rng.randint(1, 3)))]
                for s, q in lines:
                    stock[(code, s)] -= q
                order = call("POST", "/sales-orders", owner, {
                    "branchId": branch[code], "customerId": rng.choice(customer_ids + [None, None]),
                    "items": [{"variantId": variants[s], "quantity": q} for s, q in lines]})
                call("POST", f"/sales-orders/{order['salesOrderId']}/confirm-payment", owner,
                     {"paymentMethod": rng.choice(["CASH", "BANK_TRANSFER", "CARD"]), "amount": order["totalAmount"]})
                local = today_vn - timedelta(days=days_ago) + timedelta(hours=rng.randint(9, 20), minutes=rng.randint(0, 59))
                history.append((order["salesOrderId"], local))

        # queue position 1 for the hero jacket at CN01: "Chị Lan". The API requires a phone, so a placeholder
        # is used and removed from the pre-order below: her READY notice then goes by email only (team
        # mailbox), never as an SMS to a number that may belong to a stranger.
        queued = call("POST", "/preorders", body={"branchId": branch["CN01"], "customer": {
            "fullName": "Trần Thị Lan", "phone": "0900000000", "email": queue_email, "address": "20 Nguyễn Huệ, Quận 1"},
            "items": [{"variantId": variants[HERO_SKU], "quantity": 1}], "note": "Khách đặt hôm qua"})

    with engine.begin() as db:
        for order_id, local in history:
            utc = (local - timedelta(hours=7)).replace(tzinfo=None)
            db.execute(text("UPDATE sales_orders SET created_at=:local, paid_at=:utc WHERE sales_order_id=:id"),
                       {"local": local.replace(tzinfo=None), "utc": utc, "id": order_id})
            db.execute(text("UPDATE payments SET confirmed_at=:utc WHERE sales_order_id=:id"), {"utc": utc, "id": order_id})
        # 18:00 yesterday Vietnam time, stored in UTC like every pre-order created by the pre-order module
        yesterday = (today_vn - timedelta(hours=6) - timedelta(hours=7)).replace(tzinfo=None)
        db.execute(text("UPDATE preorders SET created_at=:t, customer_phone=NULL WHERE preorder_id=:id"),
                   {"t": yesterday, "id": queued["preorderId"]})
        db.execute(text("DELETE FROM preorder_request_limits"))  # the website starts with a fresh rate limit

    print(f"OK demo database '{db_name}' reset in {time.perf_counter() - started:.0f}s")
    print(f"  storeId={shop['shop_id']}  (frontend/.env: VITE_PUBLIC_STORE_ID={shop['shop_id']})")
    print(f"  branches: " + ", ".join(f"{c}={i}" for c, i in branch.items()))
    print(f"  accounts (password {PASSWORD}): owner01 | manager01:manager | staff01:staff")
    print(f"  hero product: Áo khoác gió DKat - Đen / M (SKU {HERO_SKU}, variantId={variants[HERO_SKU]}): out of stock everywhere")
    print(f"  queue #1: {queued['preorderCode']} Trần Thị Lan (email {queue_email}) WAITING_STOCK at CN01")
    print(f"  sales history: {len(history)} paid orders over the last 29 days")
    return 0


if __name__ == "__main__":
    sys.exit(main())
