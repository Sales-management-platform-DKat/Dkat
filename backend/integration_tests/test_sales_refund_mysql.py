"""PBI 122: full refunds, audit trail, stock integrity and concurrency on isolated MySQL."""
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


@unittest.skipUnless(os.getenv("DKAT_REFUND_TEST_DB") == "1", "Requires isolated MySQL test database")
class SalesRefundMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if engine.url.host not in {"127.0.0.1", "localhost"} or engine.url.database != "dkat_pbi122_test":
            raise RuntimeError("Use a local, disposable dkat_pbi122_test schema only")
        cls.suffix, cls.password = uuid4().hex[:10], "pbi122-test-password-123"
        cls.store, cls.owner, cls.owner_id = cls.provision("owner")
        cls.other_store, cls.other_owner, _ = cls.provision("other")
        cls.members = {}
        for label, role in (("manager", "manager"), ("staff", "staff"), ("unassigned", "manager")):
            user = cls.request("POST", "/api/v1/users", 201, cls.owner, {
                "username": label + cls.suffix, "full_name": label, "role": role, "password": cls.password,
            })
            login = cls.request("POST", "/api/v1/auth/login", 200, body={
                "username": label + cls.suffix + ":" + role, "password": cls.password,
            })
            cls.members[label] = ({"Authorization": "Bearer " + login["access_token"]}, user["id"])
        with engine.begin() as db:
            cls.branches = [db.execute(text("""
                INSERT INTO branches (store_id,branch_code,name,address,status) VALUES (:s,:n,:n,'QA','ACTIVE')
            """), {"s": cls.store, "n": str(i)}).lastrowid for i in range(2)]
            for label in ("manager", "staff"):
                db.execute(text("INSERT INTO user_branches (user_id,branch_id) VALUES (:u,:b)"),
                           {"u": cls.members[label][1], "b": cls.branches[0]})
            category = db.execute(text("INSERT INTO categories (store_id,name,status) VALUES (:s,'QA122','ACTIVE')"), {"s": cls.store}).lastrowid
            cls.product = db.execute(text("""
                INSERT INTO products (store_id,category_id,product_code,name,status,created_by)
                VALUES (:s,:c,'QA122','Original122','ACTIVE',:u)
            """), {"s": cls.store, "c": category, "u": cls.owner_id}).lastrowid
            cls.variants = [db.execute(text("""
                INSERT INTO product_variants (product_id,sku,variant_name,price,status)
                VALUES (:p,:sku,'QA',:price,'ACTIVE')
            """), {"p": cls.product, "sku": cls.suffix + str(i), "price": price}).lastrowid
                for i, price in enumerate(("12.50", "7.25"))]
            for branch in cls.branches:
                for variant in cls.variants:
                    db.execute(text("INSERT INTO inventory (branch_id,variant_id,quantity) VALUES (:b,:v,100)"),
                               {"b": branch, "v": variant})
        cls.branch = cls.branches[0]

    @classmethod
    def request(cls, method, path, status=200, auth=None, body=None, params=None):
        with TestClient(app) as client:
            response = client.request(method, path, headers=cls.owner if auth is None and hasattr(cls, "owner") else auth,
                                      json=body, params=params)
        if response.status_code != status:
            raise AssertionError((path, status, response.status_code, response.text))
        return response.json()

    @classmethod
    def provision(cls, prefix):
        name = prefix + cls.suffix
        shop = cls.request("POST", "/api/v1/admin/accounts", 201, {"X-Admin-Token": config.ADMIN_TOKEN}, {
            "shop_name": name, "plan": "pro", "subscription_months": 12, "owner_username": name,
            "owner_full_name": name, "owner_password": cls.password,
        })
        login = cls.request("POST", "/api/v1/auth/login", body={"username": name, "password": cls.password})
        return shop["shop_id"], {"Authorization": "Bearer " + login["access_token"]}, login["user"]["id"]

    def setUp(self):
        with engine.begin() as db:
            db.execute(text("UPDATE inventory SET quantity=100 WHERE branch_id IN (:a,:b)"), {"a": self.branch, "b": self.branches[1]})
            db.execute(text("UPDATE products SET status='ACTIVE',name='Original122' WHERE product_id=:p"), {"p": self.product})
            for i, (variant, price) in enumerate(zip(self.variants, ("12.50", "7.25"))):
                db.execute(text("UPDATE product_variants SET status='ACTIVE',price=:price,sku=:sku WHERE variant_id=:v"),
                           {"price": price, "sku": self.suffix + str(i), "v": variant})
            db.execute(text("UPDATE preorders SET status='CANCELLED' WHERE branch_id=:b"), {"b": self.branch})

    def order(self, quantities=(2, 3), branch=None, paid=True, method="CASH", discount="0.00", reverse=False):
        items = [{"variantId": v, "quantity": q} for v, q in zip(self.variants, quantities) if q]
        order = self.request("POST", "/sales-orders", 201, body={
            "branchId": branch or self.branch, "discountAmount": discount, "items": list(reversed(items)) if reverse else items,
        })
        if paid:
            return self.request("POST", f"/sales-orders/{order['salesOrderId']}/confirm-payment", body={
                "paymentMethod": method, "amount": order["totalAmount"],
            })
        return order

    def refund(self, order, status=200, auth=None, body=None):
        return self.request("POST", f"/sales-orders/{order['salesOrderId']}/refund", status, auth,
                            {"reason": "  Khách trả toàn bộ hàng  "} if body is None else body)

    def quantities(self):
        with engine.connect() as db:
            return list(db.execute(text("SELECT quantity FROM inventory WHERE branch_id=:b ORDER BY variant_id"), {"b": self.branch}).scalars())

    def state(self, order):
        with engine.connect() as db:
            header = db.execute(text("SELECT status,cancel_reason,cancelled_at,paid_at FROM sales_orders WHERE sales_order_id=:o"),
                                {"o": order["salesOrderId"]}).one()
            payments = db.execute(text("SELECT payment_id,status,amount,confirmed_by,confirmed_at FROM payments WHERE sales_order_id=:o ORDER BY payment_id"),
                                  {"o": order["salesOrderId"]}).all()
            inventory = db.execute(text("SELECT inventory_id,quantity,updated_at FROM inventory WHERE branch_id=:b ORDER BY inventory_id"), {"b": self.branch}).all()
            movements = db.execute(text("SELECT movement_id,movement_type,quantity_change,created_by FROM inventory_movements WHERE reference_type='SALES_ORDER' AND reference_id=:o ORDER BY movement_id"),
                                   {"o": order["salesOrderId"]}).all()
        return header, payments, inventory, movements

    def concurrent(self, functions):
        barrier = Barrier(len(functions))
        def invoke(fn):
            barrier.wait(timeout=10)
            return fn()
        with ThreadPoolExecutor(max_workers=len(functions)) as pool:
            futures = [pool.submit(invoke, fn) for fn in functions]
            return [future.result(timeout=30) for future in futures]

    def raw_refund(self, order):
        with TestClient(app) as client:
            return client.post(f"/sales-orders/{order['salesOrderId']}/refund", headers=self.owner,
                               json={"reason": "QA concurrent refund"}).status_code

    def test_owner_full_refund_preserves_history_and_excludes_revenue(self):
        order = self.order(discount="1.75")
        self.assertEqual(self.quantities(), [98, 97])
        before = self.state(order)
        result = self.refund(order)
        self.assertEqual((result["status"], result["cancelReason"]), ("CANCELLED", "Khách trả toàn bộ hàng"))
        self.assertTrue(result["cancelledAt"].endswith("Z"))
        self.assertEqual(result["paidAt"], order["paidAt"])
        self.assertEqual(result["items"], order["items"])
        self.assertEqual(result["totalAmount"], order["totalAmount"])
        self.assertEqual(result["payments"][0]["paymentId"], order["payments"][0]["paymentId"])
        self.assertEqual(result["payments"][0]["status"], "REFUNDED")
        self.assertEqual(self.quantities(), [100, 100])
        with engine.connect() as db:
            movements = db.execute(text("""
                SELECT movement_type,quantity_change,note,created_by FROM inventory_movements
                WHERE reference_type='SALES_ORDER' AND reference_id=:o ORDER BY movement_id
            """), {"o": order["salesOrderId"]}).all()
            revenue = db.execute(text("SELECT COALESCE(SUM(total_amount),0) FROM sales_orders WHERE sales_order_id=:o AND status='PAID'"),
                                 {"o": order["salesOrderId"]}).scalar_one()
            payments = db.execute(text("SELECT COALESCE(SUM(amount),0) FROM payments WHERE sales_order_id=:o AND status='SUCCESS'"),
                                  {"o": order["salesOrderId"]}).scalar_one()
        self.assertEqual([row[:2] for row in movements], [("SALE", -2), ("SALE", -3), ("ADJUSTMENT", 2), ("ADJUSTMENT", 3)])
        self.assertEqual([(row.note, row.created_by) for row in movements[2:]], [("Hoàn đơn " + order["orderCode"], self.owner_id)] * 2)
        self.assertEqual((revenue, payments), (0, 0))
        self.assertEqual(self.state(order)[3][:2], before[3])

    def test_manager_audit_keeps_original_payment_confirmation(self):
        order = self.order()
        with engine.begin() as db:
            db.execute(text("UPDATE payments SET confirmed_at='2024-01-01 00:00:00' WHERE sales_order_id=:o"), {"o": order["salesOrderId"]})
        result = self.refund(order, auth=self.members["manager"][0])
        self.assertEqual(result["payments"][0]["confirmedBy"], self.owner_id)
        self.assertEqual(result["payments"][0]["confirmedAt"], "2024-01-01T00:00:00Z")
        self.assertEqual({row.created_by for row in self.state(order)[3][2:]}, {self.members["manager"][1]})

    def test_all_payment_methods_and_zero_total(self):
        for method in ("CASH", "BANK_TRANSFER", "CARD", "OTHER"):
            order = self.order(method=method)
            self.assertEqual(self.refund(order)["payments"][0]["paymentMethod"], method)
        free = self.order(quantities=(1, 0), discount="12.50")
        self.assertEqual(self.refund(free)["payments"][0]["amount"], "0.00")

    def test_auth_roles_and_branch_store_scope(self):
        order = self.order()
        before = self.state(order)
        self.refund(order, 401, auth={})
        self.refund(order, 401, auth={"Authorization": "Bearer invalid"})
        previous = config.ALLOW_EMPLOYEE_STOCK
        config.ALLOW_EMPLOYEE_STOCK = True
        try:
            self.refund(order, 403, auth=self.members["staff"][0])
        finally:
            config.ALLOW_EMPLOYEE_STOCK = previous
        self.refund(order, 403, auth=self.members["unassigned"][0])
        self.refund(order, 404, auth=self.other_owner)
        outside = self.order(branch=self.branches[1])
        self.refund(outside, 403, auth=self.members["manager"][0])
        self.assertEqual(self.state(order), before)
        self.refund(outside)
        self.refund(order)

    def test_reason_required_and_partial_refunds_forbidden(self):
        order = self.order()
        before = self.state(order)
        for body in ({}, {"reason": " "}, {"reason": None}, {"reason": 12}, {"reason": "x" * 256},
                     {"reason": "QA", "amount": "1"}, {"reason": "QA", "items": [{"variantId": self.variants[0], "quantity": 1}]}):
            self.refund(order, 422, body=body)
        self.assertEqual(self.state(order), before)
        self.request("POST", "/sales-orders/0/refund", 422, body={"reason": "QA"})
        self.request("POST", "/sales-orders/9223372036854775807/refund", 404, body={"reason": "QA"})

    def test_pending_cancelled_and_repeat_refunds_are_rejected(self):
        pending = self.order(paid=False)
        before = self.state(pending)
        self.assertEqual(self.refund(pending, 409)["detail"]["code"], "ORDER_NOT_PAID")
        self.assertEqual(self.state(pending), before)
        cancelled = self.request("POST", f"/sales-orders/{pending['salesOrderId']}/cancel", body={"reason": "QA"})
        self.refund(cancelled, 409)
        paid = self.order()
        self.refund(paid)
        before = self.state(paid)
        self.refund(paid, 409)
        self.assertEqual(self.state(paid), before)

    def test_multiple_success_payments_refund_once_and_preserve_failed_attempts(self):
        order = self.order()
        with engine.begin() as db:
            db.execute(text("UPDATE payments SET amount=20 WHERE sales_order_id=:o"), {"o": order["salesOrderId"]})
            for amount, state in (("26.75", "SUCCESS"), ("46.75", "FAILED"), ("46.75", "PENDING")):
                db.execute(text("""
                    INSERT INTO payments (sales_order_id,payment_method,amount,status,confirmed_by)
                    VALUES (:o,'CARD',:a,:s,:u)
                """), {"o": order["salesOrderId"], "a": amount, "s": state, "u": self.owner_id})
        result = self.refund(order)
        self.assertEqual([payment["status"] for payment in result["payments"]], ["REFUNDED", "REFUNDED", "FAILED", "PENDING"])
        self.assertEqual(self.quantities(), [100, 100])

    def test_inconsistent_payment_history_and_missing_lines_are_rejected(self):
        for change in ("status='FAILED'", "amount=1", "status='REFUNDED'"):
            order = self.order()
            with engine.begin() as db:
                db.exec_driver_sql("UPDATE payments SET " + change + " WHERE sales_order_id=%s", (order["salesOrderId"],))
            before = self.state(order)
            self.assertEqual(self.refund(order, 409)["detail"]["code"], "ORDER_PAYMENT_INCONSISTENT")
            self.assertEqual(self.state(order), before)
        empty = self.order()
        with engine.begin() as db:
            db.execute(text("DELETE FROM sales_order_items WHERE sales_order_id=:o"), {"o": empty["salesOrderId"]})
        self.assertEqual(self.refund(empty, 409)["detail"]["code"], "ORDER_HAS_NO_ITEMS")

    def test_stock_overflow_rejects_all_lines_before_any_refund(self):
        order = self.order()
        with engine.begin() as db:
            db.execute(text("UPDATE inventory SET quantity=2147483647 WHERE branch_id=:b AND variant_id=:v"),
                       {"b": self.branch, "v": self.variants[1]})
        before = self.state(order)
        result = self.refund(order, 409)
        self.assertEqual(result["detail"]["code"], "STOCK_LIMIT_EXCEEDED")
        self.assertEqual(self.state(order), before)

    def test_missing_legacy_inventory_is_created_and_only_sold_quantity_is_returned(self):
        order = self.order()
        with engine.begin() as db:
            inventory = db.execute(text("SELECT inventory_id FROM inventory WHERE branch_id=:b AND variant_id=:v"),
                                   {"b": self.branch, "v": self.variants[0]}).scalar_one()
            # Simulate an old paid order whose ledger/inventory row has been removed externally.
            db.execute(text("DELETE FROM inventory_movements WHERE inventory_id=:i"), {"i": inventory})
            db.execute(text("DELETE FROM inventory WHERE inventory_id=:i"), {"i": inventory})
        self.refund(order)
        self.assertEqual(self.quantities(), [2, 100])

    def test_inactive_products_and_changed_prices_use_original_order_lines(self):
        order = self.order()
        with engine.begin() as db:
            db.execute(text("UPDATE products SET status='INACTIVE',name='Changed' WHERE product_id=:p"), {"p": self.product})
            db.execute(text("UPDATE product_variants SET status='INACTIVE',price=999 WHERE product_id=:p"), {"p": self.product})
        result = self.refund(order)
        self.assertEqual(result["items"], order["items"])
        self.assertEqual(self.quantities(), [100, 100])

    def test_preorder_allocations_remain_unchanged(self):
        order = self.order()
        with engine.begin() as db:
            preorder = db.execute(text("""
                INSERT INTO preorders (preorder_code,branch_id,customer_name,customer_phone,total_amount,payment_status,status)
                VALUES (:code,:b,'QA','0900000000',0,'UNPAID','READY')
            """), {"code": uuid4().hex, "b": self.branch}).lastrowid
            db.execute(text("""
                INSERT INTO preorder_items (preorder_id,variant_id,product_name_snapshot,sku_snapshot,unit_price,quantity,allocated_quantity,line_total)
                VALUES (:p,:v,'QA','QA',0,50,50,0)
            """), {"p": preorder, "v": self.variants[0]})
        self.refund(order)
        row = self.request("GET", f"/inventory/{self.branch}/{self.variants[0]}")
        self.assertEqual((row["quantity"], row["reserved"], row["available"]), (100, 50, 50))

    def test_concurrent_refunds_same_order_restore_stock_once(self):
        order = self.order()
        self.assertEqual(sorted(self.concurrent([lambda: self.raw_refund(order)] * 2)), [200, 409])
        self.assertEqual(self.quantities(), [100, 100])
        self.assertEqual(len([row for row in self.state(order)[3] if row.movement_type == "ADJUSTMENT"]), 2)

    def test_concurrent_refunds_reverse_line_order_use_consistent_locks(self):
        first, second = self.order(), self.order(reverse=True)
        self.assertEqual(self.concurrent([lambda: self.raw_refund(first), lambda: self.raw_refund(second)]), [200, 200])
        self.assertEqual(self.quantities(), [100, 100])

    def test_refund_racing_with_another_sale_keeps_stock_consistent(self):
        with engine.begin() as db:
            db.execute(text("UPDATE inventory SET quantity=1 WHERE branch_id=:b AND variant_id=:v"), {"b": self.branch, "v": self.variants[0]})
        paid, competing = self.order(quantities=(1, 0), paid=False), self.order(quantities=(1, 0), paid=False)
        self.request("POST", f"/sales-orders/{paid['salesOrderId']}/confirm-payment", body={"paymentMethod": "CASH", "amount": paid["totalAmount"]})
        def sale():
            with TestClient(app) as client:
                return client.post(f"/sales-orders/{competing['salesOrderId']}/confirm-payment", headers=self.owner,
                                   json={"paymentMethod": "CASH", "amount": competing["totalAmount"]}).status_code
        refund_status, sale_status = self.concurrent([lambda: self.raw_refund(paid), sale])
        self.assertEqual(refund_status, 200)
        self.assertIn(sale_status, (200, 409))
        self.assertEqual(self.quantities()[0], 0 if sale_status == 200 else 1)

    def test_sql_failures_roll_back_payment_stock_movements_and_order(self):
        for stage in ("payment", "second_movement", "order"):
            with self.subTest(stage=stage):
                order = self.order()
                before = self.state(order)
                with engine.begin() as db:
                    inventory = db.execute(text("SELECT inventory_id FROM inventory WHERE branch_id=:b AND variant_id=:v"),
                                           {"b": self.branch, "v": self.variants[1]}).scalar_one()
                    clause = {
                        "payment": ("BEFORE UPDATE ON payments", f"NEW.sales_order_id={order['salesOrderId']} AND NEW.status='REFUNDED'"),
                        "second_movement": ("BEFORE INSERT ON inventory_movements", f"NEW.inventory_id={inventory} AND NEW.movement_type='ADJUSTMENT'"),
                        "order": ("BEFORE UPDATE ON sales_orders", f"NEW.sales_order_id={order['salesOrderId']} AND NEW.status='CANCELLED'"),
                    }[stage]
                    db.exec_driver_sql(f"""
                        CREATE TRIGGER pbi122_fail_refund {clause[0]} FOR EACH ROW
                        BEGIN IF {clause[1]} THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PBI122 test failure'; END IF; END
                    """)
                try:
                    with self.assertLogs("app.modules.sales.router", level="ERROR"):
                        self.refund(order, 503)
                    self.assertEqual(self.state(order), before)
                finally:
                    with engine.begin() as db:
                        db.exec_driver_sql("DROP TRIGGER pbi122_fail_refund")
                self.refund(order)


if __name__ == "__main__":
    unittest.main(verbosity=2)
