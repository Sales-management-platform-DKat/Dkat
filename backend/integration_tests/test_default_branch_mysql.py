"""Default branch on real MySQL: concurrent first logins, then stock import, stocktake and a POS sale.

Run only through scripts/test_default_branch_mysql.ps1 (disposable local mysqld). Never uses team data.
"""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import config
from app.core.security import hash_password
from app.db.session import engine
from app.main import app

PASSWORD = "branch-test-password-123"


@unittest.skipUnless(os.getenv("DKAT_DEFAULT_BRANCH_TEST_DB") == "1", "Requires isolated MySQL test database")
class DefaultBranchMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if engine.url.host not in {"127.0.0.1", "localhost"} or engine.url.database != "dkat_branch_test":
            raise RuntimeError("Use a local, disposable dkat_branch_test schema only")

    def provision(self):
        """Create a store + OWNER through the platform admin API; returns (store_id, owner_id, username)."""
        username = "owner" + uuid4().hex[:10]
        with TestClient(app) as client:
            response = client.post("/api/v1/admin/accounts", headers={"X-Admin-Token": config.ADMIN_TOKEN}, json={
                "shop_name": username, "plan": "basic", "subscription_months": 12, "owner_username": username,
                "owner_email": f"{username}@example.test", "owner_full_name": username, "owner_password": PASSWORD,
            })
        self.assertEqual(response.status_code, 201, response.text)
        store = response.json()["shop_id"]
        with engine.connect() as db:
            owner = db.execute(text("SELECT owner_user_id FROM stores WHERE store_id=:s"), {"s": store}).scalar_one()
        return store, owner, username

    def login(self, username, client=None):
        if client is None:
            with TestClient(app) as own:
                return own.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
        return client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})

    def branches(self, store):
        with engine.connect() as db:
            return db.execute(text("SELECT branch_id, branch_code, name, address, status FROM branches WHERE store_id=:s"),
                              {"s": store}).all()

    def test_concurrent_first_logins_create_exactly_one_branch(self):
        store, _, username = self.provision()
        workers = 8
        barrier = Barrier(workers)

        def attempt(_):
            with TestClient(app) as client:
                barrier.wait()
                return self.login(username, client)

        with ThreadPoolExecutor(workers) as pool:
            responses = list(pool.map(attempt, range(workers)))
        self.assertEqual([r.status_code for r in responses], [200] * workers, [r.text for r in responses])
        rows = self.branches(store)
        self.assertEqual(len(rows), 1, rows)
        setups = sorted(r.json()["branch_setup"] for r in responses)
        self.assertEqual(setups, ["created"] + ["existing"] * (workers - 1))
        self.assertEqual({r.json()["default_branch_id"] for r in responses}, {rows[0].branch_id})
        self.assertEqual(tuple(rows[0][1:]), ("CN01", "Chi nhánh chính", "", "ACTIVE"))

    def test_staff_login_never_creates_a_branch(self):
        store, _, _ = self.provision()
        staff = "staff" + uuid4().hex[:10]
        with engine.begin() as db:
            db.execute(text("""
                INSERT INTO users (store_id, full_name, username, password_hash, role, status, created_at)
                VALUES (:s, 'Staff', :u, :h, 'EMPLOYEE', 'ACTIVE', NOW())
            """), {"s": store, "u": staff, "h": hash_password(PASSWORD)})
        response = self.login(staff + ":staff")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["branch_setup"], "not_applicable")
        self.assertEqual(self.branches(store), [])

    def test_new_owner_can_import_count_and_sell_on_the_auto_created_branch(self):
        store, owner_id, username = self.provision()
        with engine.begin() as db:
            category = db.execute(text("INSERT INTO categories (store_id, name, status) VALUES (:s, 'QA', 'ACTIVE')"),
                                  {"s": store}).lastrowid
            product = db.execute(text("""
                INSERT INTO products (store_id, category_id, product_code, name, status, created_by)
                VALUES (:s, :c, :code, 'Ao QA', 'ACTIVE', :u)
            """), {"s": store, "c": category, "code": "P" + uuid4().hex[:8], "u": owner_id}).lastrowid
            variant = db.execute(text("""
                INSERT INTO product_variants (product_id, sku, variant_name, price, status)
                VALUES (:p, :sku, 'M', '100000.00', 'ACTIVE')
            """), {"p": product, "sku": "SKU" + uuid4().hex[:8]}).lastrowid

        login = self.login(username)
        self.assertEqual(login.status_code, 200, login.text)
        body = login.json()
        self.assertEqual(body["branch_setup"], "created")
        branch = body["default_branch_id"]
        auth = {"Authorization": "Bearer " + body["access_token"]}

        def quantity():
            with engine.connect() as db:
                return db.execute(text("SELECT quantity FROM inventory WHERE branch_id=:b AND variant_id=:v"),
                                  {"b": branch, "v": variant}).scalar_one()

        self.assertEqual(quantity(), 0, "branch creation seeds a zero inventory row")
        with TestClient(app) as client:
            listed = client.get("/api/v1/branches", headers=auth)
            self.assertEqual([b["id"] for b in listed.json()], [branch], listed.text)

            imported = client.post("/api/v1/inventory/import", headers=auth, json={
                "branchId": branch, "items": [{"variantId": variant, "quantity": 10}]})
            self.assertEqual(imported.status_code, 201, imported.text)
            self.assertEqual(quantity(), 10)

            counted = client.post("/api/v1/inventory/stocktake", headers=auth, json={
                "branchId": branch, "note": "QA", "items": [{"variantId": variant, "countedQuantity": 8}]})
            self.assertEqual(counted.status_code, 201, counted.text)
            self.assertEqual(quantity(), 8)

            order = client.post("/api/v1/sales-orders", headers=auth, json={
                "branchId": branch, "discountAmount": "0.00", "items": [{"variantId": variant, "quantity": 3}]})
            self.assertEqual(order.status_code, 201, order.text)
            order = order.json()
            paid = client.post(f"/api/v1/sales-orders/{order['salesOrderId']}/confirm-payment", headers=auth,
                               json={"paymentMethod": "CASH", "amount": order["totalAmount"]})
            self.assertEqual(paid.status_code, 200, paid.text)
            self.assertEqual(quantity(), 5)

            # Relogin: no second branch.
            self.assertEqual(self.login(username).json()["branch_setup"], "existing")
        self.assertEqual(len(self.branches(store)), 1)

        with engine.connect() as db:
            movements = db.execute(text("""
                SELECT m.movement_type, m.quantity_change FROM inventory_movements m
                JOIN inventory i ON i.inventory_id = m.inventory_id
                WHERE i.branch_id=:b AND i.variant_id=:v ORDER BY m.movement_id
            """), {"b": branch, "v": variant}).all()
            order_branch = db.execute(text("SELECT branch_id, status FROM sales_orders WHERE sales_order_id=:o"),
                                      {"o": order["salesOrderId"]}).one()
        self.assertEqual([tuple(m) for m in movements], [("IMPORT", 10), ("ADJUSTMENT", -2), ("SALE", -3)])
        self.assertEqual(tuple(order_branch), (branch, "PAID"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
