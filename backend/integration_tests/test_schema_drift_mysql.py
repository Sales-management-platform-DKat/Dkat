"""A pre-order schema that lags behind the code (production TiDB without 08_preorder_cancellation.sql).

Reproduces "Unknown column 'p.cancel_reason'" on a disposable MySQL, checks that it is
reported as an outdated schema, then repairs it with scripts/db_migrate.py and checks the
pre-order API end to end. Run through scripts/test_schema_drift_mysql.ps1.
"""
import os
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.schema_check import find_schema_drift
from app.db.session import engine
from app.main import app
from scripts import db_migrate

DATABASE = "dkat_schema_drift_test"


@unittest.skipUnless(os.getenv("DKAT_SCHEMA_DRIFT_TEST_DB") == "1", "Requires isolated MySQL test database")
class PreorderSchemaDriftMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if engine.url.host not in {"127.0.0.1", "localhost"} or engine.url.database != DATABASE:
            raise RuntimeError(f"Use a local, disposable {DATABASE} schema only")
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()
        suffix = uuid4().hex[:8]
        r = cls.client.post("/api/v1/admin/accounts", headers={"X-Admin-Token": os.environ["DKAT_ADMIN_TOKEN"]}, json={
            "shop_name": "Drift " + suffix, "plan": "basic", "subscription_months": 1, "owner_username": "drift" + suffix,
            "owner_email": f"drift{suffix}@example.com", "owner_full_name": "Owner", "owner_password": "drift-test-password-1",
        })
        assert r.status_code == 201, r.text
        r = cls.client.post("/api/v1/auth/login", json={"username": "drift" + suffix, "password": "drift-test-password-1"})
        assert r.status_code == 200, r.text
        cls.headers = {"Authorization": "Bearer " + r.json()["access_token"]}
        with engine.begin() as db:
            store, user = db.execute(text("SELECT store_id, user_id FROM users WHERE username=:u"), {"u": "drift" + suffix}).one()
            cls.branches = [db.execute(text("""
                INSERT INTO branches (store_id, branch_code, name, address, status) VALUES (:s, :c, :c, 'QA', 'ACTIVE')
            """), {"s": store, "c": f"D{i}"}).lastrowid for i in range(2)]
            category = db.execute(text("INSERT INTO categories (store_id, name, status) VALUES (:s, 'Drift', 'ACTIVE')"), {"s": store}).lastrowid
            product = db.execute(text("""
                INSERT INTO products (store_id, category_id, product_code, name, status, created_by)
                VALUES (:s, :c, 'DRIFT', 'Drift product', 'ACTIVE', :u)
            """), {"s": store, "c": category, "u": user}).lastrowid
            cls.variant = db.execute(text("""
                INSERT INTO product_variants (product_id, sku, variant_name, price, status) VALUES (:p, :sku, 'M', 100000, 'ACTIVE')
            """), {"p": product, "sku": "DRIFT-" + suffix}).lastrowid
        cls.orders = []
        for index in range(3):
            r = cls.client.post("/api/v1/preorders", json={
                "branchId": cls.branches[0], "items": [{"variantId": cls.variant, "quantity": 1}],
                "customer": {"fullName": f"Khach {index}", "phone": f"09123400{index:02d}", "address": "HN"},
            })
            assert r.status_code == 201, r.text
            cls.orders.append(r.json()["preorderId"])

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)

    def test_outdated_schema_is_detected_reported_and_repaired(self):
        # 1. The production state: the database predates 08_preorder_cancellation.sql.
        with engine.begin() as db:
            db.execute(text("ALTER TABLE preorders DROP INDEX ix_preorders_expiry"))
            db.execute(text("ALTER TABLE preorders DROP COLUMN cancel_reason, DROP COLUMN cancelled_at"))
            before = db.execute(text("SELECT preorder_id, status, total_amount, customer_name FROM preorders ORDER BY preorder_id")).all()
        missing = find_schema_drift(engine)
        self.assertEqual({item.describe() for item in missing}, {
            "column preorders.cancel_reason", "column preorders.cancelled_at", "index preorders.ix_preorders_expiry"})

        # 2. The same request that failed in production: now a clear, specific 503.
        url = f"/api/v1/preorders?page=1&size=50&branchId={self.branches[0]}"
        r = self.client.get(url, headers=self.headers)
        self.assertEqual(r.status_code, 503, r.text)
        self.assertEqual(r.json()["detail"]["code"], "DATABASE_SCHEMA_OUTDATED")
        health = self.client.get("/health").json()
        self.assertEqual((health["status"], health["pendingMigrations"]), ("degraded", ["08_preorder_cancellation.sql"]))

        # 3. The migration tool is read-only unless told the right database.
        self.assertEqual(db_migrate.main([]), 1)
        self.assertEqual(db_migrate.main(["--apply", "--database", "dkat"]), 2)
        self.assertEqual(len(find_schema_drift(engine)), 3)

        # 4. Apply: only 08 runs, existing rows are untouched, a second run is a no-op.
        self.assertEqual(db_migrate.main(["--apply", "--database", DATABASE]), 0)
        self.assertEqual(find_schema_drift(engine), [])
        self.assertEqual(db_migrate.main(["--apply", "--database", DATABASE]), 0)
        with engine.connect() as db:
            after = db.execute(text("SELECT preorder_id, status, total_amount, customer_name FROM preorders ORDER BY preorder_id")).all()
            self.assertEqual(after, before)
            self.assertEqual(db.execute(text("SELECT COUNT(*) FROM preorders WHERE cancel_reason IS NOT NULL OR cancelled_at IS NOT NULL")).scalar(), 0)
        self.assertEqual(self.client.get("/health").json()["status"], "ok")

        # 5. List, branch filter and paging.
        r = self.client.get(url, headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual([row["preorderId"] for row in r.json()], self.orders)
        self.assertTrue(all(row["cancelReason"] is None and row["cancelledAt"] is None for row in r.json()))
        self.assertEqual(self.client.get(f"/api/v1/preorders?branchId={self.branches[1]}", headers=self.headers).json(), [])
        pages = [self.client.get(f"/api/v1/preorders?page={page}&size=2&branchId={self.branches[0]}", headers=self.headers).json()
                 for page in (1, 2, 3)]
        self.assertEqual([[row["preorderId"] for row in page] for page in pages], [self.orders[:2], self.orders[2:], []])

        # 6. Cancelling stores and returns the reason and time.
        r = self.client.post(f"/api/v1/preorders/{self.orders[0]}/cancel", headers=self.headers, json={"reason": "Khach doi y"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["status"], r.json()["cancelReason"]), ("CANCELLED", "Khach doi y"))
        self.assertIsNotNone(r.json()["cancelledAt"])
        detail = self.client.get(f"/api/v1/preorders/{self.orders[0]}", headers=self.headers).json()
        self.assertEqual((detail["cancelReason"], detail["cancelledAt"]), (r.json()["cancelReason"], r.json()["cancelledAt"]))
        cancelled = self.client.get(f"/api/v1/preorders?status=CANCELLED&branchId={self.branches[0]}", headers=self.headers).json()
        self.assertEqual([row["preorderId"] for row in cancelled], [self.orders[0]])
        self.assertEqual(self.client.post(f"/api/v1/preorders/{self.orders[0]}/cancel", headers=self.headers,
                                          json={"reason": "again"}).status_code, 409)

        # 7. The other pre-order endpoints still work on the repaired schema.
        r = self.client.post("/api/v1/inventory/import", headers=self.headers,
                             json={"branchId": self.branches[0], "items": [{"variantId": self.variant, "quantity": 1}]})
        self.assertEqual(r.status_code, 201, r.text)
        ready = self.client.get(f"/api/v1/preorders/{self.orders[1]}", headers=self.headers).json()
        self.assertIn(ready["status"], {"READY", "NOTIFIED"})
        self.assertIsNotNone(ready["expiresAt"])
        r = self.client.get(f"/api/v1/preorders/{self.orders[1]}/notifications", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        r = self.client.post(f"/api/v1/preorders/{self.orders[1]}/confirm-payment", headers=self.headers,
                             json={"paymentMethod": "CASH", "amount": 100000})
        self.assertEqual(r.status_code, 200, r.text)
        r = self.client.post(f"/api/v1/preorders/{self.orders[1]}/fulfill", headers=self.headers, json={})
        self.assertEqual((r.status_code, r.json().get("status")), (200, "FULFILLED"), r.text)
        customers = self.client.get("/api/v1/customers?q=Khach&limit=10", headers=self.headers).json()
        self.assertEqual(sum(row["orderCount"] for row in customers), 1)


if __name__ == "__main__":
    unittest.main()
