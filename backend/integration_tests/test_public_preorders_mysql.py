"""PBI 110 integration tests against a disposable local MySQL, including real SQL failures."""
import copy
import hashlib
import itertools
import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import engine
from app.main import app


@unittest.skipUnless(os.getenv("DKAT_PREORDER_TEST_DB") == "1", "Requires isolated MySQL test database")
class PublicPreorderMySQLTests(unittest.TestCase):
    ips = itertools.count(1)

    @classmethod
    def setUpClass(cls):
        if engine.url.host not in {"127.0.0.1", "localhost"} or engine.url.database != "dkat_pbi110_test":
            raise RuntimeError("Use a local, disposable dkat_pbi110_test schema only")
        cls.suffix = uuid4().hex[:10]
        cls.stores, cls.branches, cls.products, cls.variants = [], [], [], []
        with engine.begin() as db:
            for i in range(2):
                store = db.execute(text("INSERT INTO stores (name) VALUES ('QA110')")).lastrowid
                user = db.execute(text("""
                    INSERT INTO users (store_id, full_name, username, password_hash, role, status)
                    VALUES (:s, 'QA110', :name, '!', 'OWNER', 'LOCKED')
                """), {"s": store, "name": cls.suffix + str(i)}).lastrowid
                db.execute(text("UPDATE stores SET owner_user_id=:u WHERE store_id=:s"), {"u": user, "s": store})
                branch = db.execute(text("""
                    INSERT INTO branches (store_id, branch_code, name, address, status)
                    VALUES (:s, 'A', 'QA110', 'Test', 'ACTIVE')
                """), {"s": store}).lastrowid
                category = db.execute(text("INSERT INTO categories (store_id,name,status) VALUES (:s,'QA110','ACTIVE')"),
                                      {"s": store}).lastrowid
                product = db.execute(text("""
                    INSERT INTO products (store_id, category_id, product_code, name, status, created_by)
                    VALUES (:s,:c,'QA110','Snapshot110','ACTIVE',:u)
                """), {"s": store, "c": category, "u": user}).lastrowid
                variants = []
                for j, price in enumerate(("12.50", "7.25")):
                    variant = db.execute(text("""
                        INSERT INTO product_variants (product_id,sku,variant_name,price,status)
                        VALUES (:p,:sku,'Test',:price,'ACTIVE')
                    """), {"p": product, "sku": f"{cls.suffix}-{i}-{j}", "price": price}).lastrowid
                    db.execute(text("INSERT INTO inventory (branch_id,variant_id,quantity) VALUES (:b,:v,0)"),
                               {"b": branch, "v": variant})
                    variants.append(variant)
                cls.stores.append(store)
                cls.branches.append(branch)
                cls.products.append(product)
                cls.variants.append(variants)
        cls.branch, cls.variant = cls.branches[0], cls.variants[0][0]

    def setUp(self):
        self.ip = f"2001:db8::{next(self.ips):x}"
        self.phone = "09" + str(next(self.ips)).zfill(8)
        self.body = {
            "branchId": self.branch,
            "customer": {"fullName": "  Khách thử nghiệm  ", "phone": self.phone,
                         "email": "qa@example.com", "address": "  123 Đường thử nghiệm  "},
            "items": [{"variantId": self.variants[0][0], "quantity": 2},
                      {"variantId": self.variants[0][1], "quantity": 3}],
            "note": "  Gọi trước khi giao  ",
        }
        with engine.begin() as db:
            for branch in self.branches:
                db.execute(text("UPDATE branches SET status='ACTIVE' WHERE branch_id=:b"), {"b": branch})
                db.execute(text("UPDATE inventory SET quantity=0 WHERE branch_id=:b"), {"b": branch})
                db.execute(text("UPDATE preorders SET status='CANCELLED' WHERE branch_id=:b"), {"b": branch})
                db.execute(text("""
                    UPDATE preorder_items AS i JOIN preorders AS p ON p.preorder_id=i.preorder_id
                    SET i.allocated_quantity=0 WHERE p.branch_id=:b
                """), {"b": branch})
            for product in self.products:
                db.execute(text("UPDATE products SET status='ACTIVE' WHERE product_id=:p"), {"p": product})
            for variants in self.variants:
                for variant, price in zip(variants, ("12.50", "7.25")):
                    db.execute(text("UPDATE product_variants SET status='ACTIVE',price=:price WHERE variant_id=:v"),
                               {"price": price, "v": variant})

    def submit(self, expected=201, body=None, ip=None, headers=None):
        with TestClient(app, client=(ip or self.ip, 50000)) as client:
            response = client.post("/api/v1/preorders", json=self.body if body is None else body, headers=headers)
        self.assertEqual(response.status_code, expected, response.text)
        return response

    def snapshot(self):
        with engine.connect() as db:
            counts = tuple(db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
                           for table in ("preorders", "preorder_items", "customers", "payments", "inventory_movements"))
            inventory = db.execute(text("SELECT inventory_id,quantity FROM inventory ORDER BY inventory_id")).all()
            allocated = db.execute(text("SELECT preorder_item_id,allocated_quantity FROM preorder_items ORDER BY preorder_item_id")).all()
        return counts, inventory, allocated

    def test_public_creation_snapshots_and_no_stock_or_payment_changes(self):
        before = self.snapshot()
        result = self.submit().json()
        self.assertEqual((result["status"], result["paymentStatus"], result["totalAmount"]), ("WAITING_STOCK", "UNPAID", "46.75"))
        self.assertRegex(result["preorderCode"], r"^PD-\d{6}-[A-F0-9]{32}$")
        self.assertEqual(result["customer"]["fullName"], "Khách thử nghiệm")
        self.assertEqual(result["note"], "Gọi trước khi giao")
        self.assertTrue(result["createdAt"].endswith("Z"))
        after = self.snapshot()
        self.assertEqual(after[0], tuple(a + b for a, b in zip(before[0], (1, 2, 1, 0, 0))))
        self.assertEqual(after[1], before[1])
        self.assertTrue(all(value == 0 for _, value in after[2]))
        with engine.begin() as db:
            header = db.execute(text("SELECT customer_id,customer_address,note FROM preorders WHERE preorder_id=:p"),
                                {"p": result["preorderId"]}).one()
            self.assertEqual(header, (result["customerId"], "123 Đường thử nghiệm", "Gọi trước khi giao"))
            db.execute(text("UPDATE product_variants SET price=99 WHERE variant_id=:v"), {"v": self.variant})
            row = db.execute(text("SELECT unit_price,line_total,product_name_snapshot FROM preorder_items WHERE preorder_id=:p AND variant_id=:v"),
                             {"p": result["preorderId"], "v": self.variant}).one()
            self.assertEqual((str(row.unit_price), str(row.line_total), row.product_name_snapshot), ("12.50", "25.00", "Snapshot110"))

    def test_missing_customer_fields_and_invalid_phone_email(self):
        bad_inputs = []
        for field in ("fullName", "phone", "address"):
            body = copy.deepcopy(self.body)
            del body["customer"][field]
            bad_inputs.append((body, "customer." + field))
        for field, value in (("fullName", " "), ("address", " "), ("phone", "123"),
                             ("phone", "abcdefghij"), ("phone", "0000000000"), ("email", "not-an-email")):
            body = copy.deepcopy(self.body)
            body["customer"][field] = value
            bad_inputs.append((body, "customer." + field))
        before = self.snapshot()
        for body, field in bad_inputs:
            with self.subTest(field=field):
                result = self.submit(422, body, ip=f"2001:db8::{next(self.ips):x}").json()
                self.assertEqual(result["code"], "INVALID_PREORDER")
                self.assertIn(field, [issue["field"] for issue in result["details"]])
                self.assertNotIn("input", str(result))
        self.assertEqual(self.snapshot(), before)

    def test_invalid_items_untrusted_prices_and_malformed_json(self):
        before = self.snapshot()
        for items in ([], [{"variantId": self.variant, "quantity": 0}],
                      [{"variantId": self.variant, "quantity": True}],
                      [{"variantId": self.variant, "quantity": 1.5}],
                      [{"variantId": self.variant, "quantity": 2147483648}],
                      [self.body["items"][0]] * 2,
                      [{"variantId": self.variant, "quantity": 2, "unitPrice": "0.01"}]):
            body = {**self.body, "items": items}
            self.submit(422, body, ip=f"2001:db8::{next(self.ips):x}")
        with TestClient(app, client=(self.ip, 50000)) as client:
            response = client.post("/api/v1/preorders", content="{", headers={"Content-Type": "application/json"})
        self.assertEqual((response.status_code, response.json()["code"]), (422, "INVALID_PREORDER"))
        self.assertEqual(self.snapshot(), before)

    def test_fully_available_line_rejects_the_entire_batch(self):
        with engine.begin() as db:
            db.execute(text("UPDATE inventory SET quantity=3 WHERE branch_id=:b AND variant_id=:v"),
                       {"b": self.branch, "v": self.variants[0][1]})
        before = self.snapshot()
        self.assertEqual(self.submit(409).json()["code"], "VARIANT_IN_STOCK")
        self.assertEqual(self.snapshot(), before)

    def test_partial_stock_and_open_reservations(self):
        with engine.begin() as db:
            db.execute(text("UPDATE inventory SET quantity=2 WHERE branch_id=:b AND variant_id=:v"),
                       {"b": self.branch, "v": self.variant})
            for status in ("WAITING_STOCK", "READY", "NOTIFIED"):
                preorder = db.execute(text("""
                    INSERT INTO preorders (preorder_code,branch_id,customer_name,customer_phone,total_amount,payment_status,status)
                    VALUES (:code,:b,'QA','0900000000',0,'UNPAID',:status)
                """), {"code": uuid4().hex, "b": self.branch, "status": status}).lastrowid
                db.execute(text("""
                    INSERT INTO preorder_items (preorder_id,variant_id,product_name_snapshot,sku_snapshot,unit_price,
                                                quantity,allocated_quantity,line_total)
                    VALUES (:p,:v,'QA','QA',0,1,1,0)
                """), {"p": preorder, "v": self.variant})
        before = self.snapshot()
        self.submit()
        after = self.snapshot()
        self.assertEqual(after[1], before[1])
        self.assertEqual(after[2][:len(before[2])], before[2])

    def test_missing_inventory_does_not_create_inventory(self):
        with engine.begin() as db:
            # A fresh variant has no movements, so deleting only this fixture row is safe.
            variant = db.execute(text("""
                INSERT INTO product_variants (product_id,sku,variant_name,price,status)
                VALUES (:p,:sku,'Missing inventory',1,'ACTIVE')
            """), {"p": self.products[0], "sku": uuid4().hex}).lastrowid
        before = self.snapshot()[1]
        self.submit(body={**self.body, "items": [{"variantId": variant, "quantity": 1}]})
        self.assertEqual(self.snapshot()[1], before)

    def test_inactive_missing_and_cross_store_entities(self):
        before = self.snapshot()
        for body, expected, code in (
            ({**self.body, "branchId": 9223372036854775807}, 404, "BRANCH_NOT_FOUND"),
            ({**self.body, "items": [{"variantId": self.variants[1][0], "quantity": 1}]}, 404, "VARIANT_NOT_FOUND"),
            ({**self.body, "items": [{"variantId": 9223372036854775807, "quantity": 1}]}, 404, "VARIANT_NOT_FOUND"),
        ):
            self.assertEqual(self.submit(expected, body).json()["code"], code)
        with engine.begin() as db:
            db.execute(text("UPDATE product_variants SET status='INACTIVE' WHERE variant_id=:v"), {"v": self.variant})
        self.assertEqual(self.submit(409).json()["code"], "VARIANT_INACTIVE")
        with engine.begin() as db:
            db.execute(text("UPDATE branches SET status='INACTIVE' WHERE branch_id=:b"), {"b": self.branch})
        self.assertEqual(self.submit(404).json()["code"], "BRANCH_NOT_FOUND")
        self.assertEqual(self.snapshot(), before)

    def test_phone_normalization_reuses_profile_but_keeps_order_snapshots(self):
        first = self.submit().json()
        body = copy.deepcopy(self.body)
        body["customer"].update(phone="+84 " + self.phone[1:], fullName="Tên lúc đặt mới", address="Địa chỉ mới")
        second = self.submit(body=body).json()
        self.assertEqual(first["customerId"], second["customerId"])
        self.assertNotEqual(first["preorderCode"], second["preorderCode"])
        with engine.connect() as db:
            profile = db.execute(text("SELECT full_name,address FROM customers WHERE customer_id=:c"), {"c": first["customerId"]}).one()
            snapshot = db.execute(text("SELECT customer_name,customer_address FROM preorders WHERE preorder_id=:p"), {"p": second["preorderId"]}).one()
        self.assertEqual(profile, ("Khách thử nghiệm", "123 Đường thử nghiệm"))
        self.assertEqual(snapshot, ("Tên lúc đặt mới", "Địa chỉ mới"))

    def test_same_phone_in_different_stores_is_independent(self):
        first = self.submit().json()
        second = self.submit(body={**self.body, "branchId": self.branches[1],
                                  "items": [{"variantId": self.variants[1][0], "quantity": 1}]}).json()
        self.assertNotEqual(first["customerId"], second["customerId"])

    def test_optional_email_and_zero_price(self):
        body = copy.deepcopy(self.body)
        body["customer"].pop("email")
        with engine.begin() as db:
            db.execute(text("UPDATE product_variants SET price=0 WHERE product_id=:p"), {"p": self.products[0]})
        result = self.submit(body=body).json()
        self.assertEqual(result["totalAmount"], "0.00")
        self.assertIsNone(result["customer"]["email"])

    def test_total_overflow_is_rejected_before_any_writes(self):
        with engine.begin() as db:
            db.execute(text("UPDATE product_variants SET price=9999999999.99 WHERE variant_id=:v"), {"v": self.variant})
        before = self.snapshot()
        self.assertEqual(self.submit(422).json()["code"], "INVALID_PREORDER")
        self.assertEqual(self.snapshot(), before)

    def test_rolling_rate_limit_and_untrusted_forwarded_header(self):
        for _ in range(5):
            self.submit(404, {**self.body, "branchId": 9223372036854775807})
        result = self.submit(429, headers={"X-Forwarded-For": "1.2.3.4"})
        self.assertEqual(result.json()["code"], "RATE_LIMIT_EXCEEDED")
        self.assertGreater(int(result.headers["Retry-After"]), 0)
        self.submit(ip="2001:db8:1::1")
        key = hashlib.sha256(self.ip.encode()).hexdigest()
        with engine.begin() as db:
            now = float(db.execute(text("SELECT UNIX_TIMESTAMP(UTC_TIMESTAMP(6))")).scalar_one())
            # Expire just the oldest attempt: a rolling window admits exactly one more.
            db.execute(text("UPDATE preorder_request_limits SET request_times=:times WHERE ip_key=:key"),
                       {"times": json.dumps([now - 601, now - 30, now - 20, now - 10, now - 5]), "key": key})
        self.submit()
        self.submit(429)

    def test_concurrent_requests_same_ip_are_limited_across_connections(self):
        barrier = Barrier(8)
        def invoke():
            barrier.wait(timeout=10)
            with TestClient(app, client=(self.ip, 50000)) as client:
                return client.post("/api/v1/preorders", json=self.body).status_code
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(invoke) for _ in range(8)]
            results = [future.result(timeout=30) for future in futures]
        self.assertEqual(sorted(results), [201] * 5 + [429] * 3)

    def test_malformed_json_requests_are_also_rate_limited(self):
        with TestClient(app, client=(self.ip, 50000)) as client:
            for _ in range(5):
                response = client.post("/api/v1/preorders", content="{", headers={"Content-Type": "application/json"})
                self.assertEqual(response.status_code, 422)
            response = client.post("/api/v1/preorders", content="{", headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 429)

    def test_concurrent_creations_same_phone_reuse_one_profile(self):
        barrier = Barrier(2)
        def invoke(i):
            barrier.wait(timeout=10)
            body = {**self.body, "items": [{"variantId": self.concurrent_variants[i], "quantity": 1}]}
            with TestClient(app, client=(f"2001:db8:2::{i}", 50000)) as client:
                response = client.post("/api/v1/preorders", json=body)
            self.assertEqual(response.status_code, 201, response.text)
            return response.json()["customerId"]
        with engine.begin() as db:
            self.concurrent_variants = [db.execute(text("""
                INSERT INTO product_variants (product_id,sku,variant_name,price,status)
                VALUES (:p,:sku,'Concurrent',1,'ACTIVE')
            """), {"p": self.products[0], "sku": uuid4().hex}).lastrowid for _ in range(2)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(invoke, i) for i in range(2)]
            customer_ids = [future.result(timeout=30) for future in futures]
        self.assertEqual(customer_ids[0], customer_ids[1])

    def test_rollback_includes_customer_header_and_all_items(self):
        before = self.snapshot()
        with engine.begin() as db:
            db.exec_driver_sql(f"""
                CREATE TRIGGER pbi110_fail_second_item BEFORE INSERT ON preorder_items FOR EACH ROW
                BEGIN IF NEW.variant_id={self.variants[0][1]} THEN
                    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PBI110 injected failure'; END IF; END
            """)
        try:
            with self.assertLogs("app.modules.preorders.public_router", level="ERROR"):
                self.assertEqual(self.submit(503).json()["code"], "DATABASE_UNAVAILABLE")
            self.assertEqual(self.snapshot(), before)
        finally:
            with engine.begin() as db:
                db.exec_driver_sql("DROP TRIGGER pbi110_fail_second_item")
        self.submit()


if __name__ == "__main__":
    unittest.main(verbosity=2)
