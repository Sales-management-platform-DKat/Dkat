"""PBI 121: authenticated preorder queries and atomic manual payments on isolated MySQL."""
import itertools
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import config
from app.db.session import engine
from app.main import app


@unittest.skipUnless(os.getenv("DKAT_PREORDER_ADMIN_TEST_DB") == "1", "Requires isolated MySQL test database")
class PreorderAdminMySQLTests(unittest.TestCase):
    seq = itertools.count(1)

    @classmethod
    def setUpClass(cls):
        if engine.url.host not in {"127.0.0.1", "localhost"} or engine.url.database != "dkat_pbi121_test":
            raise RuntimeError("Use a local, disposable dkat_pbi121_test schema only")
        cls.suffix = uuid4().hex[:10]
        cls.password = "pbi121-test-password-123"
        cls.store, cls.owner, cls.owner_id = cls.provision("owner")
        cls.other_store, cls.other_owner, _ = cls.provision("other")
        cls.members = {}
        for name, role in (("manager", "manager"), ("staff", "staff"), ("unassigned", "staff")):
            with TestClient(app) as client:
                r = client.post("/api/v1/users", headers=cls.owner, json={
                    "username": name + cls.suffix, "full_name": name, "role": role, "password": cls.password,
                })
                assert r.status_code == 201, r.text
                user_id = r.json()["id"]
                r = client.post("/api/v1/auth/login", json={"username": name + cls.suffix + ":" + role, "password": cls.password})
                assert r.status_code == 200, r.text
                cls.members[name] = ({"Authorization": "Bearer " + r.json()["access_token"]}, user_id)
        with engine.begin() as db:
            cls.branches = [db.execute(text("""
                INSERT INTO branches (store_id,branch_code,name,address,status) VALUES (:s,:n,:n,'QA','ACTIVE')
            """), {"s": store, "n": str(i)}).lastrowid for i, store in enumerate((cls.store, cls.store, cls.other_store))]
            for name in ("manager", "staff"):
                db.execute(text("INSERT INTO user_branches (user_id,branch_id) VALUES (:u,:b)"),
                           {"u": cls.members[name][1], "b": cls.branches[0]})
            category = db.execute(text("INSERT INTO categories (store_id,name,status) VALUES (:s,'QA121','ACTIVE')"), {"s": cls.store}).lastrowid
            cls.product = db.execute(text("""
                INSERT INTO products (store_id,category_id,product_code,name,status,created_by)
                VALUES (:s,:c,'QA121','Original121','ACTIVE',:u)
            """), {"s": cls.store, "c": category, "u": cls.owner_id}).lastrowid
            cls.variants = [db.execute(text("""
                INSERT INTO product_variants (product_id,sku,variant_name,price,status)
                VALUES (:p,:sku,'QA',:price,'ACTIVE')
            """), {"p": cls.product, "sku": cls.suffix + str(i), "price": price}).lastrowid
                for i, price in enumerate(("12.50", "7.25"))]
            for branch in cls.branches[:2]:
                for variant in cls.variants:
                    db.execute(text("INSERT INTO inventory (branch_id,variant_id,quantity) VALUES (:b,:v,0)"),
                               {"b": branch, "v": variant})
        cls.branch = cls.branches[0]

    @classmethod
    def provision(cls, prefix):
        name = prefix + cls.suffix
        with TestClient(app) as client:
            r = client.post("/api/v1/admin/accounts", headers={"X-Admin-Token": config.ADMIN_TOKEN}, json={
                "shop_name": name, "plan": "pro", "subscription_months": 12, "owner_username": name,
                "owner_full_name": name, "owner_password": cls.password,
            })
            assert r.status_code == 201, r.text
            store = r.json()["shop_id"]
            r = client.post("/api/v1/auth/login", json={"username": name, "password": cls.password})
            assert r.status_code == 200, r.text
            return store, {"Authorization": "Bearer " + r.json()["access_token"]}, r.json()["user"]["id"]

    def setUp(self):
        self.tag = "QA121-" + uuid4().hex[:12]
        with engine.begin() as db:
            db.execute(text("UPDATE inventory SET quantity=0 WHERE branch_id IN (:a,:b)"),
                       {"a": self.branch, "b": self.branches[1]})
            db.execute(text("UPDATE products SET name='Original121' WHERE product_id=:p"), {"p": self.product})
            for variant, price in zip(self.variants, ("12.50", "7.25")):
                db.execute(text("UPDATE product_variants SET price=:price WHERE variant_id=:v"), {"price": price, "v": variant})

    def request(self, method, path, expected=200, auth=None, body=None, params=None):
        with TestClient(app) as client:
            r = client.request(method, path, headers=self.owner if auth is None else auth, json=body, params=params)
        self.assertEqual(r.status_code, expected, r.text)
        return r.json()

    def order(self, branch=None, status="WAITING_STOCK", payment="UNPAID", zero=False):
        sequence = next(self.seq)
        body = {
            "branchId": branch or self.branch,
            "customer": {"fullName": self.tag, "phone": "09" + str(sequence).zfill(8), "address": "Địa chỉ snapshot"},
            "items": [{"variantId": variant, "quantity": q} for variant, q in zip(self.variants, (2, 3))],
            "note": "Ghi chú 121",
        }
        if zero:
            with engine.begin() as db:
                db.execute(text("UPDATE product_variants SET price=0 WHERE product_id=:p"), {"p": self.product})
        with TestClient(app, client=(f"2001:db8:121::{sequence:x}", 50000)) as client:
            r = client.post("/preorders", json=body)
        self.assertEqual(r.status_code, 201, r.text)
        order = r.json()
        with engine.begin() as db:
            db.execute(text("UPDATE preorders SET status=:status,payment_status=:payment WHERE preorder_id=:p"),
                       {"status": status, "payment": payment, "p": order["preorderId"]})
        return order

    def pay(self, order, expected=200, method="CASH", amount=None, auth=None):
        return self.request("POST", f"/preorders/{order['preorderId']}/confirm-payment", expected, auth, {
            "paymentMethod": method, "amount": order["totalAmount"] if amount is None else amount,
        })

    def stock_snapshot(self):
        with engine.connect() as db:
            stock = db.execute(text("SELECT inventory_id,quantity,updated_at FROM inventory ORDER BY inventory_id")).all()
            allocations = db.execute(text("SELECT preorder_item_id,allocated_quantity FROM preorder_items ORDER BY preorder_item_id")).all()
            movements = db.execute(text("SELECT COUNT(*) FROM inventory_movements")).scalar_one()
        return stock, allocations, movements

    def test_each_payable_status_and_method_keep_stock_allocations_and_order_status(self):
        for status in ("WAITING_STOCK", "READY", "NOTIFIED"):
            for method in ("CASH", "BANK_TRANSFER", "CARD", "OTHER"):
                with self.subTest(status=status, method=method):
                    order = self.order(status=status)
                    with engine.begin() as db:
                        db.execute(text("UPDATE preorder_items SET allocated_quantity=1 WHERE preorder_id=:p"), {"p": order["preorderId"]})
                    before = self.stock_snapshot()
                    paid = self.pay(order, method=method)
                    self.assertEqual((paid["status"], paid["paymentStatus"]), (status, "PAID"))
                    payment, = paid["payments"]
                    self.assertEqual((payment["paymentMethod"], payment["amount"], payment["status"], payment["confirmedBy"]),
                                     (method, order["totalAmount"], "SUCCESS", self.owner_id))
                    self.assertTrue(payment["confirmedAt"].endswith("Z"))
                    self.assertEqual(self.stock_snapshot(), before)
                    self.assertEqual(self.pay(order, 409)["detail"]["code"], "PREORDER_ALREADY_PAID")

    def test_closed_and_previously_paid_or_refunded_orders_are_rejected(self):
        for status in ("FULFILLED", "CANCELLED", "EXPIRED"):
            order = self.order(status=status)
            self.assertEqual(self.pay(order, 409)["detail"]["code"], "PREORDER_NOT_PAYABLE")
        for payment in ("PAID", "REFUNDED"):
            order = self.order(payment=payment)
            self.assertEqual(self.pay(order, 409)["detail"]["code"], "PREORDER_ALREADY_PAID")

    def test_exact_amount_and_validation_do_not_write_payments(self):
        order = self.order()
        self.assertEqual(self.pay(order, 422, amount="1.00")["detail"]["code"], "PAYMENT_AMOUNT_MISMATCH")
        for body in ({"paymentMethod": "WIRE", "amount": "46.75"}, {"paymentMethod": "CASH"},
                     {"paymentMethod": "CASH", "amount": "-1"}, {"paymentMethod": "CASH", "amount": "NaN"},
                     {"paymentMethod": "CASH", "amount": "1.001"},
                     {"paymentMethod": "CASH", "amount": "46.75", "confirmedBy": self.owner_id}):
            self.request("POST", f"/preorders/{order['preorderId']}/confirm-payment", 422, body=body)
        detail = self.request("GET", f"/preorders/{order['preorderId']}")
        self.assertEqual((detail["paymentStatus"], detail["payments"]), ("UNPAID", []))

    def test_zero_total_can_be_recorded(self):
        order = self.order(zero=True)
        self.assertEqual(self.pay(order)["payments"][0]["amount"], "0.00")

    def test_all_private_routes_require_auth_and_do_not_use_public_rate_limit(self):
        order = self.order()
        for auth in ({}, {"Authorization": "Bearer invalid"}):
            self.request("GET", "/preorders", 401, auth)
            self.request("GET", f"/preorders/{order['preorderId']}", 401, auth)
            self.pay(order, 401, auth=auth)
        for _ in range(8):
            self.request("GET", "/preorders", params={"keyword": self.tag})

    def test_branch_and_store_scope_for_list_detail_and_payment(self):
        own, outside = self.order(), self.order(branch=self.branches[1])
        for role in ("manager", "staff"):
            auth, uid = self.members[role]
            orders = self.request("GET", "/preorders", auth=auth, params={"keyword": self.tag})
            self.assertIn(own["preorderId"], [row["preorderId"] for row in orders])
            self.assertNotIn(outside["preorderId"], [row["preorderId"] for row in orders])
            self.assertTrue(all(row["branchId"] == self.branch for row in orders))
            self.request("GET", "/preorders", 403, auth, params={"branchId": self.branches[1]})
            self.request("GET", f"/preorders/{outside['preorderId']}", 403, auth)
            self.pay(outside, 403, auth=auth)
            order = self.order()
            self.assertEqual(self.pay(order, auth=auth)["payments"][0]["confirmedBy"], uid)
        for order in (own, outside):
            self.request("GET", f"/preorders/{order['preorderId']}", 404, self.other_owner)
            self.pay(order, 404, auth=self.other_owner)
        self.assertEqual(self.request("GET", "/preorders", auth=self.other_owner), [])
        self.assertEqual(self.request("GET", "/preorders", auth=self.members["unassigned"][0]), [])
        self.pay(own, 403, auth=self.members["unassigned"][0])

    def test_fifo_pagination_filters_search_and_stable_ties(self):
        first, second, older = self.order(), self.order(status="READY", payment="PAID"), self.order(status="NOTIFIED")
        with engine.begin() as db:
            db.execute(text("UPDATE preorders SET created_at='2026-01-02 00:00:00' WHERE preorder_id IN (:a,:b)"),
                       {"a": first["preorderId"], "b": second["preorderId"]})
            db.execute(text("UPDATE preorders SET created_at='2026-01-01 00:00:00' WHERE preorder_id=:p"), {"p": older["preorderId"]})
        rows = self.request("GET", "/preorders", params={"keyword": self.tag})
        self.assertEqual([row["preorderId"] for row in rows], [older["preorderId"], first["preorderId"], second["preorderId"]])
        self.assertEqual(len(rows[0]["items"]), 2)
        self.assertEqual(rows[0]["customer"]["fullName"], self.tag)
        page = self.request("GET", "/preorders", params={"keyword": self.tag, "page": 2, "size": 1})
        self.assertEqual(page[0]["preorderId"], first["preorderId"])
        for params, expected in (({"status": "READY"}, second), ({"paymentStatus": "PAID"}, second)):
            matches = self.request("GET", "/preorders", params={"keyword": self.tag, **params})
            self.assertEqual([row["preorderId"] for row in matches], [expected["preorderId"]])
        self.assertEqual(self.request("GET", "/preorders", params={"keyword": first["preorderCode"]})[0]["preorderId"], first["preorderId"])
        phone = "+84" + first["customer"]["phone"][1:]
        self.assertEqual(self.request("GET", "/preorders", params={"keyword": phone})[0]["preorderId"], first["preorderId"])

    def test_keyword_wildcards_are_literal_and_query_validation(self):
        order = self.order()
        code = "PD-" + self.tag + "-%_!"
        with engine.begin() as db:
            db.execute(text("UPDATE preorders SET preorder_code=:code WHERE preorder_id=:p"), {"code": code, "p": order["preorderId"]})
        found = self.request("GET", "/preorders", params={"keyword": code})
        self.assertEqual([row["preorderId"] for row in found], [order["preorderId"]])
        for params in ({"status": "UNKNOWN"}, {"paymentStatus": "SUCCESS"}, {"page": 0}, {"size": 101}, {"branchId": 0}):
            self.request("GET", "/preorders", 422, params=params)
        self.request("GET", "/preorders/0", 422)
        self.request("GET", "/preorders/9223372036854775807", 404)

    def test_detail_contains_snapshots_payments_fulfillment_and_notifications(self):
        order = self.order()
        with engine.begin() as db:
            db.execute(text("UPDATE customers SET full_name='Changed',address='Changed' WHERE customer_id=:c"), {"c": order["customerId"]})
            db.execute(text("UPDATE products SET name='Changed product' WHERE product_id=:p"), {"p": self.product})
            db.execute(text("UPDATE product_variants SET price=100 WHERE product_id=:p"), {"p": self.product})
            db.execute(text("UPDATE preorder_items SET allocated_quantity=1 WHERE preorder_id=:p"), {"p": order["preorderId"]})
            db.execute(text("""
                INSERT INTO preorder_fulfillments (preorder_id,fulfillment_method,delivery_address,status)
                VALUES (:p,'DELIVERY','Địa chỉ nhận','PENDING')
            """), {"p": order["preorderId"]})
            for state in ("FAILED", "SENT"):
                db.execute(text("""
                    INSERT INTO notifications (preorder_id,channel,recipient,message,status,error_message,sent_at,created_at)
                    VALUES (:p,'SMS','0900000000','QA',:status,:error,'2026-01-01 00:00:00','2026-01-01 00:00:00')
                """), {"p": order["preorderId"], "status": state, "error": "Provider error" if state == "FAILED" else None})
            for state in ("FAILED", "PENDING"):
                db.execute(text("""
                    INSERT INTO payments (preorder_id,payment_method,amount,status,confirmed_by)
                    VALUES (:p,'CARD',46.75,:status,:u)
                """), {"p": order["preorderId"], "status": state, "u": self.owner_id})
        detail = self.pay(order)
        self.assertEqual(detail["customer"]["fullName"], self.tag)
        self.assertEqual(detail["customer"]["address"], "Địa chỉ snapshot")
        self.assertEqual(detail["items"][0]["productName"], "Original121")
        self.assertEqual(detail["items"][0]["unitPrice"], "12.50")
        self.assertEqual(detail["items"][0]["allocatedQuantity"], 1)
        self.assertEqual(len(detail["payments"]), 3)
        self.assertEqual(detail["fulfillment"]["method"], "DELIVERY")
        self.assertEqual([item["status"] for item in detail["notifications"]], ["SENT", "FAILED"])
        self.assertTrue(detail["notifications"][0]["sentAt"].endswith("Z"))
        self.assertEqual(detail["notifications"][1]["errorMessage"], "Provider error")

    def test_legacy_nullable_customer_and_missing_optional_children(self):
        order = self.order()
        with engine.begin() as db:
            db.execute(text("UPDATE preorders SET customer_id=NULL,customer_address=NULL WHERE preorder_id=:p"), {"p": order["preorderId"]})
        detail = self.request("GET", f"/preorders/{order['preorderId']}")
        self.assertIsNone(detail["customerId"])
        self.assertIsNone(detail["customer"]["address"])
        self.assertEqual((detail["payments"], detail["fulfillment"], detail["notifications"]), ([], None, []))

    def test_inconsistent_existing_success_is_not_recorded_twice(self):
        order = self.order()
        with engine.begin() as db:
            db.execute(text("""
                INSERT INTO payments (preorder_id,payment_method,amount,status,confirmed_by)
                VALUES (:p,'CASH',46.75,'SUCCESS',:u)
            """), {"p": order["preorderId"], "u": self.owner_id})
        self.assertEqual(self.pay(order, 409)["detail"]["code"], "PREORDER_ALREADY_PAID")

    def test_simultaneous_payments_only_one_success_and_no_inventory_change(self):
        order = self.order()
        before = self.stock_snapshot()
        barrier = Barrier(2)
        def invoke():
            barrier.wait(timeout=10)
            with TestClient(app) as client:
                return client.post(f"/preorders/{order['preorderId']}/confirm-payment", headers=self.owner,
                                   json={"paymentMethod": "CASH", "amount": order["totalAmount"]}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(invoke) for _ in range(2)]
            results = [future.result(timeout=30) for future in futures]
        self.assertEqual(sorted(results), [200, 409])
        detail = self.request("GET", f"/preorders/{order['preorderId']}")
        self.assertEqual(len(detail["payments"]), 1)
        self.assertEqual(self.stock_snapshot(), before)

    def test_sql_failures_roll_back_payment_and_payment_status(self):
        for stage in ("payment", "status"):
            with self.subTest(stage=stage):
                order = self.order()
                before = self.stock_snapshot()
                with engine.begin() as db:
                    clause = ("BEFORE INSERT ON payments", f"NEW.preorder_id={order['preorderId']}") if stage == "payment" else (
                        "BEFORE UPDATE ON preorders", f"NEW.preorder_id={order['preorderId']} AND NEW.payment_status='PAID'")
                    db.exec_driver_sql(f"""
                        CREATE TRIGGER pbi121_fail_payment {clause[0]} FOR EACH ROW
                        BEGIN IF {clause[1]} THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PBI121 test failure'; END IF; END
                    """)
                try:
                    with self.assertLogs("app.modules.preorders.router", level="ERROR"):
                        self.pay(order, 503)
                    detail = self.request("GET", f"/preorders/{order['preorderId']}")
                    self.assertEqual((detail["paymentStatus"], detail["payments"]), ("UNPAID", []))
                    self.assertEqual(self.stock_snapshot(), before)
                finally:
                    with engine.begin() as db:
                        db.exec_driver_sql("DROP TRIGGER pbi121_fail_payment")
                self.pay(order)


if __name__ == "__main__":
    unittest.main(verbosity=2)
