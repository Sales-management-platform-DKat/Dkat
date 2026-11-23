"""Run only on an isolated MySQL schema; see README PBI 99. Never uses team data."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import config
from app.db.session import engine
from app.main import app


@unittest.skipUnless(os.getenv("DKAT_PAYMENT_TEST_DB") == "1", "Requires isolated MySQL test database")
class SalesPaymentMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if engine.url.host not in {"127.0.0.1", "localhost"} or engine.url.database != "dkat_pbi99_test":
            raise RuntimeError("Use a local, disposable dkat_pbi99_test schema only")
        cls.suffix = uuid4().hex[:10]
        cls.password = "pbi99-test-password-123"
        cls.store, cls.owner, cls.owner_id = cls.provision("owner")
        cls.other_store, cls.other_owner, _ = cls.provision("other")
        cls.roles = {}
        for role in ("manager", "staff"):
            username = role + cls.suffix
            user = cls.request("POST", "/api/v1/users", 201, cls.owner, {
                "username": username, "full_name": role, "role": role, "password": cls.password,
            })
            token = cls.request("POST", "/api/v1/auth/login", 200, body={
                "username": username + ":" + role, "password": cls.password,
            })["access_token"]
            cls.roles[role] = ({"Authorization": "Bearer " + token}, user["id"])
        with engine.begin() as db:
            cls.branch, cls.unassigned = [db.execute(text("""
                INSERT INTO branches (store_id, branch_code, name, address, status)
                VALUES (:s, :code, :code, 'Test', 'ACTIVE')
            """), {"s": cls.store, "code": code}).lastrowid for code in ("A", "B")]
            for _, user_id in cls.roles.values():
                db.execute(text("INSERT INTO user_branches (user_id, branch_id) VALUES (:u, :b)"),
                           {"u": user_id, "b": cls.branch})
            category = db.execute(text("""
                INSERT INTO categories (store_id, name, status) VALUES (:s, 'QA99', 'ACTIVE')
            """), {"s": cls.store}).lastrowid
            cls.product = db.execute(text("""
                INSERT INTO products (store_id, category_id, product_code, name, status, created_by)
                VALUES (:s, :c, 'QA99', 'Snapshot99', 'ACTIVE', :u)
            """), {"s": cls.store, "c": category, "u": cls.owner_id}).lastrowid
            cls.variants = [db.execute(text("""
                INSERT INTO product_variants (product_id, sku, variant_name, price, status)
                VALUES (:p, :sku, 'Test', :price, 'ACTIVE')
            """), {"p": cls.product, "sku": cls.suffix + str(i), "price": price}).lastrowid
                for i, price in enumerate(("12.50", "7.25"))]
            for branch in (cls.branch, cls.unassigned):
                for variant in cls.variants:
                    db.execute(text("""
                        INSERT INTO inventory (branch_id, variant_id, quantity) VALUES (:b, :v, 100)
                    """), {"b": branch, "v": variant})

    @classmethod
    def request(cls, method, path, expected, auth=None, body=None):
        with TestClient(app) as client:
            response = client.request(method, path, headers=auth, json=body)
        if response.status_code != expected:
            raise AssertionError((path, expected, response.status_code, response.text))
        return response.json()

    @classmethod
    def provision(cls, label):
        username = label + cls.suffix
        shop = cls.request("POST", "/api/v1/admin/accounts", 201,
                           {"X-Admin-Token": config.ADMIN_TOKEN}, {
            "shop_name": username, "plan": "pro", "subscription_months": 12,
            "owner_username": username, "owner_full_name": username, "owner_password": cls.password,
        })
        login = cls.request("POST", "/api/v1/auth/login", 200, body={
            "username": username, "password": cls.password,
        })
        return shop["shop_id"], {"Authorization": "Bearer " + login["access_token"]}, login["user"]["id"]

    def setUp(self):
        self.stock(100, 100)
        with engine.begin() as db:
            db.execute(text("UPDATE preorders SET status='CANCELLED' WHERE branch_id=:b"), {"b": self.branch})
            for variant, price in zip(self.variants, ("12.50", "7.25")):
                db.execute(text("UPDATE product_variants SET price=:p WHERE variant_id=:v"), {"p": price, "v": variant})

    def stock(self, first, second):
        with engine.begin() as db:
            for variant, quantity in zip(self.variants, (first, second)):
                db.execute(text("UPDATE inventory SET quantity=:q WHERE branch_id=:b AND variant_id=:v"),
                           {"q": quantity, "b": self.branch, "v": variant})

    def quantities(self):
        with engine.connect() as db:
            return list(db.execute(text("SELECT quantity FROM inventory WHERE branch_id=:b ORDER BY variant_id"),
                                   {"b": self.branch}).scalars())

    def order(self, quantities=(2, 3), branch=None, discount="0.00"):
        return self.request("POST", "/sales-orders", 201, self.owner, {
            "branchId": self.branch if branch is None else branch, "discountAmount": discount,
            "items": [{"variantId": v, "quantity": q} for v, q in zip(self.variants, quantities) if q],
        })

    def pay(self, order, status=200, method="CASH", auth=None, amount=None):
        return self.request("POST", f"/sales-orders/{order['salesOrderId']}/confirm-payment", status,
                            auth or self.owner, {"paymentMethod": method, "amount": order["totalAmount"] if amount is None else amount})

    def unchanged(self, order, quantities):
        detail = self.request("GET", f"/sales-orders/{order['salesOrderId']}", 200, self.owner)
        self.assertEqual((detail["status"], detail["paidAt"], detail["payments"]), ("PENDING", None, []))
        self.assertEqual(self.quantities(), quantities)
        with engine.connect() as db:
            self.assertEqual(db.execute(text("""
                SELECT COUNT(*) FROM inventory_movements WHERE reference_type='SALES_ORDER' AND reference_id=:id
            """), {"id": order["salesOrderId"]}).scalar_one(), 0)

    def reserve(self, allocated, status="READY"):
        with engine.begin() as db:
            preorder = db.execute(text("""
                INSERT INTO preorders
                    (preorder_code, branch_id, customer_name, customer_phone, total_amount, payment_status, status)
                VALUES (:code, :b, 'QA', '0900000000', 0, 'UNPAID', :status)
            """), {"code": uuid4().hex, "b": self.branch, "status": status}).lastrowid
            db.execute(text("""
                INSERT INTO preorder_items
                    (preorder_id, variant_id, product_name_snapshot, sku_snapshot, unit_price, quantity,
                     allocated_quantity, line_total)
                VALUES (:p, :v, 'QA', 'QA', 0, :q, :q, 0)
            """), {"p": preorder, "v": self.variants[0], "q": allocated})

    def concurrent(self, functions):
        barrier = Barrier(len(functions))
        def invoke(fn):
            barrier.wait(timeout=10)
            return fn()
        with ThreadPoolExecutor(max_workers=len(functions)) as pool:
            futures = [pool.submit(invoke, fn) for fn in functions]
            return [future.result(timeout=30) for future in futures]

    def raw_pay(self, order):
        with TestClient(app) as client:
            return client.post(f"/sales-orders/{order['salesOrderId']}/confirm-payment", headers=self.owner,
                               json={"paymentMethod": "CASH", "amount": order["totalAmount"]}).status_code

    def test_all_methods_snapshots_ledger_and_exactly_once(self):
        for method in ("CASH", "BANK_TRANSFER", "CARD", "OTHER"):
            with self.subTest(method=method):
                self.stock(100, 100)
                order = self.order(discount="1.75")
                with engine.begin() as db:
                    db.execute(text("UPDATE product_variants SET price=99 WHERE product_id=:p"), {"p": self.product})
                paid = self.pay(order, method=method)
                self.assertEqual((paid["status"], paid["items"], paid["totalAmount"]), ("PAID", order["items"], order["totalAmount"]))
                payment, = paid["payments"]
                self.assertEqual((payment["status"], payment["confirmedBy"], payment["paymentMethod"]),
                                 ("SUCCESS", self.owner_id, method))
                self.assertEqual(payment["confirmedAt"], paid["paidAt"])
                self.assertTrue(paid["paidAt"].endswith("Z"))
                self.assertEqual(self.quantities(), [98, 97])
                with engine.connect() as db:
                    movements = db.execute(text("""
                        SELECT movement_type, quantity_change, created_by FROM inventory_movements
                        WHERE reference_type='SALES_ORDER' AND reference_id=:id ORDER BY movement_id
                    """), {"id": order["salesOrderId"]}).all()
                self.assertEqual(movements, [("SALE", -2, self.owner_id), ("SALE", -3, self.owner_id)])
                self.assertEqual(self.pay(order, 409)["detail"]["code"], "ORDER_NOT_PENDING")
                self.assertEqual(self.quantities(), [98, 97])

    def test_amount_and_payload_validation(self):
        order = self.order()
        self.assertEqual(self.pay(order, 422, amount="1.00")["detail"]["code"], "PAYMENT_AMOUNT_MISMATCH")
        for body in ({"amount": "46.75"}, {"paymentMethod": "WIRE", "amount": "46.75"},
                     {"paymentMethod": "CASH", "amount": "-1"},
                     {"paymentMethod": "CASH", "amount": "1.001"},
                     {"paymentMethod": "CASH", "amount": "NaN"},
                     {"paymentMethod": "CASH", "amount": "10000000000.00"},
                     {"paymentMethod": "CASH", "amount": "46.75", "confirmedBy": self.owner_id}):
            self.request("POST", f"/sales-orders/{order['salesOrderId']}/confirm-payment", 422, self.owner, body)
        self.unchanged(order, [100, 100])

    def test_zero_total_can_be_paid(self):
        order = self.order((1, 0), discount="12.50")
        paid = self.pay(order, amount="0.00")
        self.assertEqual(Decimal(paid["payments"][0]["amount"]), Decimal(0))
        self.assertEqual(self.quantities(), [99, 100])

    def test_shortage_rolls_back_all_lines_and_retry(self):
        order = self.order()
        self.stock(100, 2)
        result = self.pay(order, 409)
        self.assertEqual(result["detail"]["code"], "OUT_OF_STOCK")
        self.assertEqual(result["detail"]["items"][0]["variantId"], self.variants[1])
        self.unchanged(order, [100, 2])
        self.stock(100, 3)
        self.pay(order)
        self.assertEqual(self.quantities(), [98, 0])

    def test_stock_endpoints_still_work_without_order_references(self):
        data = {"branchId": self.branch, "items": [{"variantId": self.variants[0], "quantity": 1}]}
        imported = self.request("POST", "/inventory/import", 201, self.owner, data)
        exported = self.request("POST", "/inventory/export", 201, self.owner, {**data, "reason": "KHAC"})
        counted = self.request("POST", "/inventory/stocktake", 201, self.owner, {
            "branchId": self.branch, "note": "QA99", "items": [{"variantId": self.variants[0], "countedQuantity": 99}],
        })
        self.assertEqual(self.quantities(), [99, 100])
        with engine.connect() as db:
            for result, delta, kind in ((imported, 1, "IMPORT"), (exported, -1, "EXPORT"), (counted, -1, "ADJUSTMENT")):
                movement = db.execute(text("""
                    SELECT movement_type, quantity_change, reference_type, reference_id
                    FROM inventory_movements WHERE movement_id=:id
                """), {"id": result["items"][0]["movementId"]}).one()
                self.assertEqual(movement, (kind, delta, None, None))

    def test_open_reservations_are_protected_even_above_physical_stock(self):
        for status in ("WAITING_STOCK", "READY", "NOTIFIED"):
            with self.subTest(status=status):
                self.setUp()
                order = self.order()
                self.reserve(101, status)
                result = self.pay(order, 409)
                self.assertEqual(result["detail"]["items"][0]["available"], -1)
                self.unchanged(order, [100, 100])

    def test_closed_reservations_do_not_block_sale(self):
        order = self.order()
        for status in ("CANCELLED", "EXPIRED", "FULFILLED"):
            self.reserve(100, status)
        self.pay(order)
        self.assertEqual(self.quantities(), [98, 97])

    def test_only_available_stock_can_be_sold(self):
        rejected = self.order((2, 0))
        accepted = self.order((1, 0))
        self.reserve(99)
        self.assertEqual(self.pay(rejected, 409)["detail"]["items"][0]["available"], 1)
        self.unchanged(rejected, [100, 100])
        self.pay(accepted)
        self.assertEqual(self.quantities(), [99, 100])

    def test_missing_inventory_is_zero_stock(self):
        order = self.order((1, 0), branch=self.unassigned)
        with engine.begin() as db:
            db.execute(text("DELETE FROM inventory WHERE branch_id=:b AND variant_id=:v"),
                       {"b": self.unassigned, "v": self.variants[0]})
        try:
            self.assertEqual(self.pay(order, 409)["detail"]["items"][0]["available"], 0)
        finally:
            with engine.begin() as db:
                db.execute(text("INSERT INTO inventory (branch_id,variant_id,quantity) VALUES (:b,:v,100)"),
                           {"b": self.unassigned, "v": self.variants[0]})

    def test_auth_branch_and_store_scope(self):
        order = self.order()
        path = f"/sales-orders/{order['salesOrderId']}/confirm-payment"
        body = {"paymentMethod": "CASH", "amount": order["totalAmount"]}
        self.request("POST", path, 401, body=body)
        self.request("POST", path, 401, {"Authorization": "Bearer invalid"}, body)
        self.pay(order, 404, auth=self.other_owner)
        self.request("POST", "/sales-orders/9223372036854775807/confirm-payment", 404, self.owner, body)
        self.unchanged(order, [100, 100])
        outside = self.order(branch=self.unassigned)
        for auth, _ in self.roles.values():
            self.pay(outside, 403, auth=auth)
        for auth, uid in self.roles.values():
            own_order = self.order()
            self.assertEqual(self.pay(own_order, auth=auth)["payments"][0]["confirmedBy"], uid)

    def test_cancelled_order_cannot_be_paid(self):
        order = self.order()
        self.request("POST", f"/sales-orders/{order['salesOrderId']}/cancel", 200, self.owner, {"reason": "QA"})
        self.assertEqual(self.pay(order, 409)["detail"]["code"], "ORDER_NOT_PENDING")
        self.assertEqual(self.quantities(), [100, 100])

    def test_two_payments_same_order_only_one_succeeds(self):
        order = self.order()
        self.assertEqual(sorted(self.concurrent([lambda: self.raw_pay(order)] * 2)), [200, 409])
        self.assertEqual(self.quantities(), [98, 97])
        detail = self.request("GET", f"/sales-orders/{order['salesOrderId']}", 200, self.owner)
        self.assertEqual(len(detail["payments"]), 1)

    def test_two_orders_compete_for_last_item(self):
        first, second = self.order((1, 0)), self.order((1, 0))
        self.stock(1, 100)
        self.assertEqual(sorted(self.concurrent([lambda: self.raw_pay(first), lambda: self.raw_pay(second)])), [200, 409])
        self.assertEqual(self.quantities(), [0, 100])

    def test_reverse_line_order_uses_consistent_inventory_lock_order(self):
        first = self.order()
        second = self.request("POST", "/sales-orders", 201, self.owner, {
            "branchId": self.branch,
            "items": [{"variantId": self.variants[1], "quantity": 3},
                      {"variantId": self.variants[0], "quantity": 2}],
        })
        self.assertEqual(self.concurrent([lambda: self.raw_pay(first), lambda: self.raw_pay(second)]), [200, 200])
        self.assertEqual(self.quantities(), [96, 94])

    def test_payment_and_cancellation_are_serialized(self):
        order = self.order()
        def cancel():
            with TestClient(app) as client:
                return client.post(f"/sales-orders/{order['salesOrderId']}/cancel", headers=self.owner,
                                   json={"reason": "QA race"}).status_code
        self.assertEqual(sorted(self.concurrent([lambda: self.raw_pay(order), cancel])), [200, 409])
        detail = self.request("GET", f"/sales-orders/{order['salesOrderId']}", 200, self.owner)
        self.assertEqual(self.quantities(), [98, 97] if detail["status"] == "PAID" else [100, 100])
        self.assertEqual(len(detail["payments"]), 1 if detail["status"] == "PAID" else 0)

    def test_rollback_on_real_database_failure_at_every_stage(self):
        for stage in ("payment", "second_movement", "paid_status"):
            with self.subTest(stage=stage):
                order = self.order()
                with engine.begin() as db:
                    second_inventory = db.execute(text("SELECT inventory_id FROM inventory WHERE branch_id=:b AND variant_id=:v"),
                                                  {"b": self.branch, "v": self.variants[1]}).scalar_one()
                    clause = {
                        "payment": ("BEFORE INSERT ON payments", f"NEW.sales_order_id = {order['salesOrderId']}"),
                        "second_movement": ("BEFORE INSERT ON inventory_movements", f"NEW.inventory_id = {second_inventory}"),
                        "paid_status": ("BEFORE UPDATE ON sales_orders", f"NEW.sales_order_id = {order['salesOrderId']} AND NEW.status = 'PAID'"),
                    }[stage]
                    db.exec_driver_sql(f"""
                        CREATE TRIGGER pbi99_inject_failure {clause[0]} FOR EACH ROW
                        BEGIN IF {clause[1]} THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PBI99 test failure'; END IF; END
                    """)
                try:
                    with self.assertLogs("app.modules.sales.router", level="ERROR"):
                        self.pay(order, 503)
                    self.unchanged(order, [100, 100])
                finally:
                    with engine.begin() as db:
                        db.exec_driver_sql("DROP TRIGGER pbi99_inject_failure")
                self.pay(order)
                self.stock(100, 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
