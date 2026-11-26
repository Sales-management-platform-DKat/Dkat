"""Authenticated preorder queries, payments and fulfillment on isolated MySQL."""
import itertools
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
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
            with TestClient(app, base_url="http://testserver/api/v1") as client:
                r = client.post("/users", headers=cls.owner, json={
                    "username": name + cls.suffix, "full_name": name, "role": role, "password": cls.password,
                })
                assert r.status_code == 201, r.text
                user_id = r.json()["id"]
                r = client.post("/auth/login", json={"username": name + cls.suffix + ":" + role, "password": cls.password})
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
        with TestClient(app, base_url="http://testserver/api/v1") as client:
            r = client.post("/admin/accounts", headers={"X-Admin-Token": config.ADMIN_TOKEN}, json={
                "shop_name": name, "plan": "basic", "subscription_months": 12, "owner_username": name, "owner_email": name + "@example.test",
                "owner_full_name": name, "owner_password": cls.password,
            })
            assert r.status_code == 201, r.text
            store = r.json()["shop_id"]
            r = client.post("/auth/login", json={"username": name, "password": cls.password})
            assert r.status_code == 200, r.text
            return store, {"Authorization": "Bearer " + r.json()["access_token"]}, r.json()["user"]["id"]

    def setUp(self):
        self.tag = "QA121-" + uuid4().hex[:12]
        with engine.begin() as db:
            db.execute(text("UPDATE inventory SET quantity=0 WHERE branch_id IN (:a,:b)"),
                       {"a": self.branch, "b": self.branches[1]})
            db.execute(text("UPDATE preorders SET status='CANCELLED' WHERE branch_id IN (:a,:b)"),
                       {"a": self.branch, "b": self.branches[1]})
            db.execute(text("UPDATE products SET name='Original121' WHERE product_id=:p"), {"p": self.product})
            for variant, price in zip(self.variants, ("12.50", "7.25")):
                db.execute(text("UPDATE product_variants SET price=:price WHERE variant_id=:v"), {"price": price, "v": variant})

    def request(self, method, path, expected=200, auth=None, body=None, params=None):
        with TestClient(app, base_url="http://testserver/api/v1") as client:
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
        with TestClient(app, base_url="http://testserver/api/v1", client=(f"2001:db8:121::{sequence:x}", 50000)) as client:
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
            with TestClient(app, base_url="http://testserver/api/v1") as client:
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

    def reserve_for_fulfillment(self, order, status="READY"):
        with engine.begin() as db:
            db.execute(text("""
                UPDATE preorders SET status=:status, ready_at=UTC_TIMESTAMP(),
                    expires_at=UTC_TIMESTAMP() + INTERVAL 7 DAY WHERE preorder_id=:id
            """), {"id": order["preorderId"], "status": status})
            db.execute(text("UPDATE preorder_items SET allocated_quantity=quantity WHERE preorder_id=:id"),
                       {"id": order["preorderId"]})
            for item in order["items"]:
                db.execute(text("""
                    UPDATE inventory SET quantity=quantity + :q WHERE branch_id=:b AND variant_id=:v
                """), {"q": item["quantity"], "b": order["branchId"], "v": item["variantId"]})

    def test_fulfillment_choice_can_be_edited_without_touching_stock(self):
        order = self.order()
        path = f"/preorders/{order['preorderId']}/fulfillment"
        before = self.stock_snapshot()
        chosen = self.request("PUT", path, body={"method": "DELIVERY"})
        selected = chosen["fulfillment"]
        self.assertEqual((chosen["status"], selected["status"], selected["deliveryAddress"]),
                         ("WAITING_STOCK", "PENDING", "Địa chỉ snapshot"))
        edited = self.request("PUT", path, body={"fulfillmentMethod": "DELIVERY", "deliveryAddress": "  Địa chỉ mới  "})
        self.assertEqual(edited["fulfillment"]["deliveryAddress"], "Địa chỉ mới")
        pickup = self.request("PUT", path, body={"method": "PICKUP"})["fulfillment"]
        self.assertEqual((pickup["fulfillmentId"], pickup["method"], pickup["deliveryAddress"]),
                         (selected["fulfillmentId"], "PICKUP", None))
        with engine.begin() as db:
            db.execute(text("UPDATE preorders SET customer_address=NULL WHERE preorder_id=:id"),
                       {"id": order["preorderId"]})
        error = self.request("PUT", path, 422, body={"method": "DELIVERY", "deliveryAddress": "  "})
        self.assertEqual(error["detail"]["code"], "DELIVERY_ADDRESS_REQUIRED")
        self.request("PUT", path, 422, body={"method": "COURIER"})
        self.assertEqual(self.stock_snapshot(), before)

    def test_fulfill_after_import_records_payment_delivery_and_exact_stock_deltas(self):
        order = self.order()
        preorder_id = order["preorderId"]
        path = f"/preorders/{preorder_id}"
        staff, staff_id = self.members["staff"]
        with patch.dict("sys.modules", {"app.modules.notifications.service": None}):
            self.request("POST", "/inventory/import", 201, body={
                "branchId": self.branch, "items": [
                    {"variantId": item["variantId"], "quantity": item["quantity"] + 1} for item in order["items"]
                ],
            })
        before = self.stock_snapshot()
        selected = self.request("PUT", path + "/fulfillment", auth=staff, body={"method": "DELIVERY"})
        self.assertEqual((selected["status"], selected["paymentStatus"]), ("READY", "UNPAID"))
        self.assertEqual(self.request("POST", path + "/fulfill", 422, staff, {})["detail"]["code"],
                         "PAYMENT_METHOD_REQUIRED")
        self.assertEqual(self.stock_snapshot(), before)

        done = self.request("POST", path + "/fulfill", auth=staff, body={"paymentMethod": "CASH"})
        self.assertEqual((done["status"], done["paymentStatus"]), ("FULFILLED", "PAID"))
        fulfillment = done["fulfillment"]
        self.assertEqual((fulfillment["fulfillmentId"], fulfillment["method"], fulfillment["deliveryAddress"]),
                         (selected["fulfillment"]["fulfillmentId"], "DELIVERY", "Địa chỉ snapshot"))
        self.assertEqual((fulfillment["status"], fulfillment["confirmedBy"], fulfillment["completedAt"]),
                         ("COMPLETED", staff_id, done["fulfilledAt"]))
        payment, = done["payments"]
        self.assertEqual((payment["paymentMethod"], payment["status"], payment["amount"], payment["confirmedBy"]),
                         ("CASH", "SUCCESS", order["totalAmount"], staff_id))
        self.assertEqual(payment["confirmedAt"], done["fulfilledAt"])
        self.assertTrue(done["fulfilledAt"].endswith("Z"))
        self.assertEqual([item["allocatedQuantity"] for item in done["items"]], [0, 0])
        for item in order["items"]:
            inventory = self.request("GET", f"/inventory/{self.branch}/{item['variantId']}")
            self.assertEqual((inventory["quantity"], inventory["reserved"], inventory["available"]), (1, 0, 1))
        movements = self.request("GET", "/inventory/movements", params={"branchId": self.branch, "type": "PREORDER_FULFILLMENT"})
        self.assertEqual({row["variantId"]: row["quantityChange"] for row in movements if row["referenceId"] == preorder_id},
                         {item["variantId"]: -item["quantity"] for item in order["items"]})
        after = self.stock_snapshot()
        self.assertEqual(after[2] - before[2], 2)
        self.request("POST", path + "/fulfill", 409, body={"paymentMethod": "CASH"})
        self.request("PUT", path + "/fulfillment", 409, body={"method": "PICKUP"})
        self.assertEqual(self.request("GET", path), done)
        self.assertEqual(self.stock_snapshot(), after)

    def test_fulfill_notified_paid_order_defaults_to_pickup_and_keeps_other_reservations(self):
        order, waiting = self.order(), self.order()
        self.reserve_for_fulfillment(order, "NOTIFIED")
        self.reserve_for_fulfillment(waiting)
        paid = self.pay(order, method="BANK_TRANSFER")
        done = self.request("POST", f"/preorders/{order['preorderId']}/fulfill", body=None)
        self.assertEqual(done["payments"], paid["payments"])
        self.assertEqual((done["status"], done["fulfillment"]["method"]), ("FULFILLED", "PICKUP"))
        for item in waiting["items"]:
            stock = self.request("GET", f"/inventory/{self.branch}/{item['variantId']}")
            self.assertEqual((stock["quantity"], stock["reserved"], stock["available"]),
                             (item["quantity"], item["quantity"], 0))

    def test_fulfill_rejects_closed_expired_and_unallocated_orders(self):
        for status, code in (
            ("WAITING_STOCK", "PREORDER_NOT_FULFILLABLE"), ("CANCELLED", "PREORDER_NOT_FULFILLABLE"),
            ("EXPIRED", "PREORDER_NOT_FULFILLABLE"), ("FULFILLED", "PREORDER_NOT_FULFILLABLE"),
            ("READY", "PREORDER_NOT_FULLY_ALLOCATED"), ("NOTIFIED", "PREORDER_EXPIRED"),
        ):
            with self.subTest(status=status):
                order = self.order(status=status)
                path = f"/preorders/{order['preorderId']}"
                if status == "NOTIFIED":
                    with engine.begin() as db:
                        db.execute(text("UPDATE preorders SET expires_at=UTC_TIMESTAMP() WHERE preorder_id=:id"),
                                   {"id": order["preorderId"]})
                    self.assertEqual(self.request("PUT", path + "/fulfillment", 409, body={"method": "PICKUP"})["detail"]["code"], code)
                before = self.stock_snapshot()
                self.assertEqual(self.request("POST", path + "/fulfill", 409, body={"paymentMethod": "CASH"})["detail"]["code"], code)
                self.assertEqual(self.request("GET", path)["payments"], [])
                self.assertEqual(self.stock_snapshot(), before)

    def test_fulfillment_routes_enforce_auth_branch_and_store(self):
        order = self.order()
        path = f"/preorders/{order['preorderId']}"
        for auth, code in (({}, 401), (self.members["unassigned"][0], 403), (self.other_owner, 404)):
            self.request("PUT", path + "/fulfillment", code, auth, {"method": "PICKUP"})
            self.request("POST", path + "/fulfill", code, auth, {"paymentMethod": "CASH"})

    def test_preorder_cancel_validates_reason_access_and_closed_state(self):
        order = self.order(status="FULFILLED")
        path = f"/preorders/{order['preorderId']}/cancel"
        for auth, code in (({}, 401), (self.members["unassigned"][0], 403), (self.other_owner, 404)):
            self.request("POST", path, code, auth, {"reason": "Khách không nhận"})
        for body in ({}, {"reason": "  "}, {"reason": "x" * 256}):
            self.request("POST", path, 422, body=body)
        error = self.request("POST", path, 409, body={"reason": "Khách không nhận"})
        self.assertEqual(error["detail"]["code"], "PREORDER_NOT_CANCELLABLE")

    def test_stock_csv_reuses_stock_write_permissions_and_scopes_skus_to_store(self):
        path = "/inventory/import-csv"
        sku = self.suffix + "0"
        files = {"file": ("stock.csv", f"sku,quantity,note\n{sku},1,\n", "text/csv")}
        manager, _ = self.members["manager"]
        staff, _ = self.members["staff"]
        with TestClient(app, base_url="http://testserver/api/v1") as client, patch.object(config, "ALLOW_EMPLOYEE_STOCK", False):
            for auth, branch, code in (
                ({}, self.branch, 401), (staff, self.branch, 403), (manager, self.branches[1], 403),
                (self.other_owner, self.branch, 403),
            ):
                response = client.post(path, headers=auth, params={"branchId": branch}, files=files)
                self.assertEqual(response.status_code, code, response.text)
            preview = client.post(path, headers=manager, params={"branchId": self.branch}, files=files)
            self.assertEqual(preview.status_code, 200, preview.text)
            self.assertEqual((preview.json()["dryRun"], preview.json()["valid"]), (True, True))
            other = client.post(path, headers=self.other_owner, params={"branchId": self.branches[2]}, files=files)
            self.assertEqual(other.status_code, 200, other.text)
            self.assertEqual(other.json()["errors"][0]["code"], "SKU_NOT_FOUND")

    def test_fulfill_cannot_consume_stock_allocated_to_other_orders(self):
        order, other = self.order(), self.order()
        self.reserve_for_fulfillment(order)
        self.reserve_for_fulfillment(other)
        with engine.begin() as db:
            db.execute(text("UPDATE inventory SET quantity=quantity-1 WHERE branch_id=:b AND variant_id=:v"),
                       {"b": self.branch, "v": self.variants[1]})
        before = self.stock_snapshot()
        path = f"/preorders/{order['preorderId']}"
        result = self.request("POST", path + "/fulfill", 409, body={"paymentMethod": "CASH"})
        self.assertEqual(result["detail"], {"code": "INSUFFICIENT_STOCK", "variantId": self.variants[1]})
        self.assertEqual(self.request("GET", path)["payments"], [])
        self.assertEqual(self.stock_snapshot(), before)

    def test_fulfillment_sql_failure_rolls_back_payment_stock_movements_and_selection(self):
        order = self.order()
        self.reserve_for_fulfillment(order)
        path = f"/preorders/{order['preorderId']}"
        selected = self.request("PUT", path + "/fulfillment", body={"method": "DELIVERY"})
        before = self.stock_snapshot()
        with engine.begin() as db:
            db.exec_driver_sql("""
                CREATE TRIGGER pbi139_fail_fulfill BEFORE UPDATE ON preorders FOR EACH ROW
                BEGIN IF NEW.status='FULFILLED' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Test failure'; END IF; END
            """)
        try:
            with self.assertLogs("app.modules.preorders.router", level="ERROR"):
                self.request("POST", path + "/fulfill", 503, body={"paymentMethod": "CARD"})
            self.assertEqual(self.request("GET", path), selected)
            self.assertEqual(self.stock_snapshot(), before)
        finally:
            with engine.begin() as db:
                db.exec_driver_sql("DROP TRIGGER pbi139_fail_fulfill")
        self.request("POST", path + "/fulfill", body={"paymentMethod": "CARD"})

    def test_simultaneous_fulfill_requests_charge_and_deduct_once(self):
        order = self.order()
        self.reserve_for_fulfillment(order)
        path = f"/preorders/{order['preorderId']}"
        before = self.stock_snapshot()
        barrier = Barrier(2)

        def invoke():
            barrier.wait(timeout=10)
            with TestClient(app, base_url="http://testserver/api/v1") as client:
                return client.post(path + "/fulfill", headers=self.owner, json={"paymentMethod": "CASH"}).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(invoke) for _ in range(2)]
            self.assertEqual(sorted(future.result(timeout=30) for future in futures), [200, 409])
        done = self.request("GET", path)
        self.assertEqual((done["status"], len(done["payments"])), ("FULFILLED", 1))
        self.assertEqual(self.stock_snapshot()[2] - before[2], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
