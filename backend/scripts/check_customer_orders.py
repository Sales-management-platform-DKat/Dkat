"""Check GET /customers/{id}/orders (purchase history) end to end.

Orders are written with the same SQL the POS / pre-order services use (tuiladien/* line):
create a sales order PENDING with customer_id, then pay it (payments SUCCESS + sales_orders PAID).
Everything this script creates is deleted at the end.

Requires: seed_auth, database/04_sales_order_customers.sql and 06_public_preorders.sql.
Run from backend/:  python -m scripts.check_customer_orders      (exit code 1 on any failure)
"""
import asyncio
import sys
import time
from datetime import datetime

import httpx
from sqlalchemy import text

from app.core.config import settings
from app.db.session import close_engine, engine, standalone_transaction
from app.main import create_app

API = settings.API_V1_PREFIX
PASSWORD = "Dkat@1234"
SFX = str(time.time_ns())[-7:]
results: list[tuple[bool, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((ok, name, detail))


async def sql(db, statement: str, params: dict | None = None):
    return await db.execute(text(statement), params or {})


async def setup() -> dict:
    """Customer A with 5 orders over 3 branches, customer B with 1 order, 1 walk-in order."""
    ids: dict = {"sales": [], "preorders": [], "customers": []}
    async with standalone_transaction() as db:
        store = (await sql(db, "SELECT store_id FROM users WHERE username = 'owner01'")).scalar_one()
        users = dict((await sql(db, "SELECT username, user_id FROM users")).all())
        br = dict((await sql(db, "SELECT branch_code, branch_id FROM branches WHERE store_id = :s", {"s": store})).all())
        variant = (await sql(db, "SELECT variant_id FROM product_variants WHERE sku = 'SP-MAU-01-S'")).scalar_one()
        ids.update(branches=br, users=users)

        async def customer(name: str, phone: str) -> int:
            cid = (await sql(db, "INSERT INTO customers (store_id, full_name, phone) VALUES (:s, :n, :p)",
                             {"s": store, "n": name, "p": phone})).lastrowid
            ids["customers"].append(cid)
            return cid

        a = await customer(f"Lịch sử A {SFX}", "05" + SFX + "1")
        b = await customer(f"Lịch sử B {SFX}", "05" + SFX + "2")
        ids.update(a=a, b=b)

        async def sale(tag, branch, cust, total, status="PENDING", created=None, payments=(), discount=0):
            # POS create (status PENDING, customer linked) - same columns as the sales service
            oid = (await sql(db, """INSERT INTO sales_orders (order_code, branch_id, customer_id, created_by, subtotal,
                                    discount_amount, total_amount, status, created_at)
                                    VALUES (:c, :b, :cu, :u, :sub, :d, :t, 'PENDING', COALESCE(:at, NOW()))""",
                             {"c": f"CHK-{tag}-{SFX}", "b": br[branch], "cu": cust, "u": users["staff01"],
                              "sub": total + discount, "d": discount, "t": total, "at": created})).lastrowid
            await sql(db, """INSERT INTO sales_order_items (sales_order_id, variant_id, product_name_snapshot, sku_snapshot,
                             unit_price, quantity, line_total) VALUES (:o, :v, :n, 'SKU-LUC-BAN', :p, 2, :lt)""",
                      {"o": oid, "v": variant, "n": f"Tên lúc bán {tag}", "p": (total + discount) / 2, "lt": total + discount})
            for method, amount, pstatus in payments:  # POS pay: payment SUCCESS then order PAID
                await sql(db, """INSERT INTO payments (sales_order_id, payment_method, amount, status, confirmed_by, confirmed_at)
                                 VALUES (:o, :m, :a, :st, :u, NOW())""",
                          {"o": oid, "m": method, "a": amount, "st": pstatus, "u": users["staff01"]})
            if status != "PENDING":
                await sql(db, "UPDATE sales_orders SET status = :st, paid_at = IF(:st = 'PAID', NOW(), NULL) WHERE sales_order_id = :o",
                          {"st": status, "o": oid})
            ids["sales"].append(oid)
            return oid

        async def preorder(tag, branch, cust, total, status, pay_status="UNPAID", payments=()):
            oid = (await sql(db, """INSERT INTO preorders (preorder_code, branch_id, customer_id, customer_name, customer_phone,
                                    total_amount, payment_status, status) VALUES (:c, :b, :cu, 'Snapshot', '0500000000', :t, :ps, :st)""",
                             {"c": f"CHK-{tag}-{SFX}", "b": br[branch], "cu": cust, "t": total, "ps": pay_status, "st": status})).lastrowid
            await sql(db, """INSERT INTO preorder_items (preorder_id, variant_id, product_name_snapshot, sku_snapshot, unit_price,
                             quantity, allocated_quantity, line_total) VALUES (:o, :v, :n, 'SKU-DAT-TRUOC', :t, 1, 0, :t)""",
                      {"o": oid, "v": variant, "n": f"Đặt trước {tag}", "t": total})
            for method, amount in payments:
                await sql(db, """INSERT INTO payments (preorder_id, payment_method, amount, status, confirmed_by, confirmed_at)
                                 VALUES (:o, :m, :a, 'SUCCESS', :u, NOW())""",
                          {"o": oid, "m": method, "a": amount, "u": users["owner01"]})
            ids["preorders"].append(oid)
            return oid

        ids["s2"] = await sale("S2", "CN02", a, 300000, "PAID", payments=[("CARD", 200000, "SUCCESS"), ("CASH", 100000, "SUCCESS")], discount=20000)
        ids["s3"] = await sale("S3", "CN01", a, 50000, "CANCELLED", created="2025-01-15 10:00:00", payments=[("CASH", 50000, "REFUNDED")])
        ids["p1"] = await preorder("P1", "CN03", a, 400000, "FULFILLED", "PAID", payments=[("BANK_TRANSFER", 400000)])
        ids["p2"] = await preorder("P2", "CN01", a, 120000, "WAITING_STOCK", "PAID", payments=[("CASH", 120000)])
        ids["walkin"] = await sale("W1", "CN01", None, 999000, "PAID", payments=[("CASH", 999000, "SUCCESS")])
        ids["b1"] = await sale("B1", "CN01", b, 70000, "PAID", payments=[("CASH", 70000, "SUCCESS")])
        ids["store"], ids["variant"] = store, variant
    return ids


async def pos_create_and_pay(ids: dict) -> tuple[int, callable]:
    """The completion scenario: POS order linked to customer A, created PENDING, paid afterwards."""
    async with standalone_transaction() as db:
        oid = (await sql(db, """INSERT INTO sales_orders (order_code, branch_id, customer_id, created_by, subtotal,
                                discount_amount, total_amount, status) VALUES (:c, :b, :cu, :u, 150000, 0, 150000, 'PENDING')""",
                         {"c": f"CHK-S1-{SFX}", "b": ids["branches"]["CN01"], "cu": ids["a"], "u": ids["users"]["staff01"]})).lastrowid
        await sql(db, """INSERT INTO sales_order_items (sales_order_id, variant_id, product_name_snapshot, sku_snapshot,
                         unit_price, quantity, line_total) VALUES (:o, :v, 'Áo thun mẫu', 'SP-MAU-01-S', 150000, 1, 150000)""",
                  {"o": oid, "v": ids["variant"]})
    ids["sales"].append(oid)

    async def pay() -> None:
        async with standalone_transaction() as db:
            await sql(db, """INSERT INTO payments (sales_order_id, payment_method, amount, status, confirmed_by, confirmed_at)
                             VALUES (:o, 'CASH', 150000, 'SUCCESS', :u, NOW())""", {"o": oid, "u": ids["users"]["staff01"]})
            await sql(db, "UPDATE sales_orders SET status = 'PAID', paid_at = NOW() WHERE sales_order_id = :o AND status = 'PENDING'",
                      {"o": oid})

    return oid, pay


async def cleanup(ids: dict) -> None:
    async with standalone_transaction() as db:
        for table, column, key in [
            ("payments", "sales_order_id", "sales"), ("payments", "preorder_id", "preorders"),
            ("sales_order_items", "sales_order_id", "sales"), ("preorder_items", "preorder_id", "preorders"),
            ("sales_orders", "sales_order_id", "sales"), ("preorders", "preorder_id", "preorders"),
            ("customers", "customer_id", "customers"),
        ]:
            if ids.get(key):
                await db.execute(
                    text(f"DELETE FROM {table} WHERE {column} IN ({','.join(str(int(i)) for i in ids[key])})")
                )


async def main() -> int:
    ids = await setup()
    a = ids["a"]
    try:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            tokens = {}
            for role, user in {"OWNER": "owner01", "MANAGER": "manager01", "EMPLOYEE": "staff01"}.items():
                tokens[role] = {"Authorization": "Bearer " + (await c.post(f"{API}/auth/login", json={"username": user, "password": PASSWORD})).json()["data"]["token"]}

            async def history(role, **params):
                r = await c.get(f"{API}/customers/{a}/orders", headers=tokens[role], params={"size": 100, **params})
                return r, (r.json()["data"] if r.status_code == 200 else {})

            # ---- completion scenario: POS order linked to A, then paid
            s1, pay = await pos_create_and_pay(ids)
            _, d = await history("EMPLOYEE")
            before = next((o for o in d.get("items", []) if o["key"] == f"SALE-{s1}"), None)
            check("Đơn POS mới tạo (PENDING) đã gắn vào lịch sử khách", before is not None and before["status"] == "PENDING", str(before))
            check("Đơn PENDING chưa tính vào thống kê", d.get("stats", {}).get("purchaseCount") == 0, str(d.get("stats")))
            await pay()
            _, d = await history("EMPLOYEE")
            after = next((o for o in d.get("items", []) if o["key"] == f"SALE-{s1}"), None)
            check(
                "Sau khi thanh toán: đơn PAID, phương thức CASH, có trong lịch sử",
                after is not None and after["status"] == "PAID" and after["paymentMethods"] == ["CASH"],
                str(after),
            )
            check("Sau khi thanh toán: thống kê 1 lần mua, 150000", d["stats"] == {"purchaseCount": 1, "totalSpent": 150000.0}, str(d["stats"]))

            # ---- branch scope + statistics (PAID / FULFILLED only)
            s2, s3, p1, p2 = ids["s2"], ids["s3"], ids["p1"], ids["p2"]
            r, d = await history("OWNER")
            keys = {o["key"] for o in d["items"]}
            expected_owner = {f"SALE-{s1}", f"SALE-{s2}", f"SALE-{s3}", f"PREORDER-{p1}", f"PREORDER-{p2}"}
            check("OWNER: đủ 5 đơn (bán + đặt trước, mọi chi nhánh)", keys == expected_owner, str(sorted(keys)))
            check("Không có đơn khách vãng lai / khách khác", f"SALE-{ids['walkin']}" not in keys and f"SALE-{ids['b1']}" not in keys)
            check(
                "OWNER thống kê: 3 lần mua (S1, S2 PAID + P1 FULFILLED), 850000",
                d["stats"] == {"purchaseCount": 3, "totalSpent": 850000.0},
                str(d["stats"]),
            )
            s2_row = next(o for o in d["items"] if o["key"] == f"SALE-{s2}")
            check("Đơn trả nhiều phương thức: CARD + CASH", s2_row["paymentMethods"] == ["CARD", "CASH"], str(s2_row["paymentMethods"]))
            s3_row = next(o for o in d["items"] if o["key"] == f"SALE-{s3}")
            check("Đơn huỷ (thanh toán REFUNDED): không có phương thức thành công", s3_row["paymentMethods"] == [], str(s3_row))
            p2_row = next(o for o in d["items"] if o["key"] == f"PREORDER-{p2}")
            check("Đơn đặt trước: có paymentStatus", p2_row["paymentStatus"] == "PAID" and p2_row["status"] == "WAITING_STOCK", str(p2_row))
            check(
                "Có mã đơn, thời gian, chi nhánh, tổng tiền, trạng thái",
                set(s2_row) == {"key", "type", "id", "code", "createdAt", "branch", "totalAmount", "status", "paymentStatus", "paymentMethods"},
                str(sorted(s2_row)),
            )
            dates = [o["createdAt"] for o in d["items"]]
            check("Sắp xếp mới nhất trước", dates == sorted(dates, reverse=True), str(dates))

            _, d = await history("MANAGER")
            keys = {o["key"] for o in d["items"]}
            check("MANAGER (CN01, CN02): không thấy đơn CN03", keys == expected_owner - {f"PREORDER-{p1}"}, str(sorted(keys)))
            check("MANAGER thống kê trong phạm vi: 2 lần, 450000", d["stats"] == {"purchaseCount": 2, "totalSpent": 450000.0}, str(d["stats"]))
            _, d = await history("EMPLOYEE")
            keys = {o["key"] for o in d["items"]}
            check("EMPLOYEE (CN01): chỉ đơn CN01", keys == {f"SALE-{s1}", f"SALE-{s3}", f"PREORDER-{p2}"}, str(sorted(keys)))

            # ---- date range and paging
            _, d = await history("OWNER", **{"from": "2025-01-01", "to": "2025-01-15"})
            check("from/to (to tính hết ngày): chỉ đơn ngày 15/01/2025", [o["key"] for o in d["items"]] == [f"SALE-{s3}"], str(d.get("items")))
            check("Thống kê theo khoảng ngày (đơn huỷ không tính)", d["stats"] == {"purchaseCount": 0, "totalSpent": 0.0}, str(d["stats"]))
            r, _ = await history("OWNER", **{"from": "2025-02-01", "to": "2025-01-01"})
            check("from > to -> 422", r.status_code == 422, str(r.status_code))
            r = await c.get(f"{API}/customers/{a}/orders", headers=tokens["OWNER"], params={"size": 2, "page": 3})
            pg = r.json()["data"]
            check("Phân trang size=2: trang 3 có 1 đơn, totalPages 3", len(pg["items"]) == 1 and pg["totalPages"] == 3 and pg["total"] == 5, str(pg["total"]))

            # ---- detail
            r = await c.get(f"{API}/customers/{a}/orders/SALE-{s2}", headers=tokens["OWNER"])
            det = r.json()["data"] if r.status_code == 200 else {}
            check("Chi tiết đơn bán -> 200", r.status_code == 200, r.text[:200])
            check(
                "Dòng hàng lấy từ snapshot trên đơn",
                det.get("lines") == [{"productName": "Tên lúc bán S2", "sku": "SKU-LUC-BAN", "unitPrice": 160000.0, "quantity": 2, "lineTotal": 320000.0}],
                str(det.get("lines")),
            )
            check("Chi tiết có subtotal, giảm giá", det.get("subtotal") == 320000.0 and det.get("discountAmount") == 20000.0, str(det.get("subtotal")))
            check("Chi tiết có 2 lần thanh toán", [p["method"] for p in det.get("payments", [])] == ["CARD", "CASH"], str(det.get("payments")))
            r = await c.get(f"{API}/customers/{a}/orders/preorder-{p2}", headers=tokens["EMPLOYEE"])
            check("Chi tiết đơn đặt trước (key không phân biệt hoa thường) -> 200", r.status_code == 200 and r.json()["data"]["lines"][0]["sku"] == "SKU-DAT-TRUOC", r.text[:200])
            for role, key, label in [("EMPLOYEE", f"SALE-{s2}", "EMPLOYEE xem đơn CN02"), ("MANAGER", f"PREORDER-{p1}", "MANAGER xem đơn CN03")]:
                r = await c.get(f"{API}/customers/{a}/orders/{key}", headers=tokens[role])
                check(f"{label} -> 403", r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN", str(r.status_code))
            for key, label in [(f"SALE-{ids['b1']}", "đơn của khách khác"), (f"SALE-{ids['walkin']}", "đơn khách vãng lai"), ("SALE-999999999", "đơn không tồn tại")]:
                r = await c.get(f"{API}/customers/{a}/orders/{key}", headers=tokens["OWNER"])
                check(f"Chi tiết {label} qua khách A -> 404", r.status_code == 404, str(r.status_code))
            r = await c.get(f"{API}/customers/{a}/orders/ABC-1", headers=tokens["OWNER"])
            check("Mã tham chiếu sai dạng -> 422", r.status_code == 422, str(r.status_code))
            r = await c.get(f"{API}/customers/999999999/orders", headers=tokens["OWNER"])
            check("Khách không tồn tại -> 404", r.status_code == 404, str(r.status_code))
            r = await c.get(f"{API}/customers/{a}/orders")
            check("Không token -> 401", r.status_code == 401, str(r.status_code))

        # ---- index use
        async with engine.connect() as conn:
            for table in ("sales_orders", "preorders"):
                plan = (await conn.execute(text(f"EXPLAIN SELECT * FROM {table} WHERE customer_id = :c"), {"c": a})).mappings().one()
                check(f"EXPLAIN {table}.customer_id dùng index", plan["type"] == "ref", f"{plan['type']}/{plan['key']}")
    finally:
        await cleanup(ids)
        await close_engine()

    width = max(len(n) for _, n, _ in results)
    for ok, name, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {'' if ok else detail}")
    failed = sum(not ok for ok, _, _ in results)
    print(f"\n{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(main()))
