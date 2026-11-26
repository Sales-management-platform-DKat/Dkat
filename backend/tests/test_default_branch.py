"""Owner first login creates exactly one default branch; nobody else creates branches."""
import unittest
from unittest.mock import patch

from sqlalchemy.exc import OperationalError

from app.modules.branches import defaults
from tests import test_auth_flow as base

test_engine = base.test_engine

STORE_TABLES = """
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS product_variants;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS branches;
CREATE TABLE branches (
    branch_id INTEGER PRIMARY KEY AUTOINCREMENT, store_id INTEGER NOT NULL,
    branch_code VARCHAR(30) NOT NULL, name VARCHAR(150) NOT NULL, address VARCHAR(255) NOT NULL,
    phone VARCHAR(20), status VARCHAR(20) NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (store_id, branch_code)
);
CREATE TABLE products (product_id INTEGER PRIMARY KEY, store_id INTEGER NOT NULL);
CREATE TABLE product_variants (
    variant_id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL, status VARCHAR(20) NOT NULL
);
CREATE TABLE inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT, branch_id INTEGER NOT NULL,
    variant_id INTEGER NOT NULL, quantity INTEGER NOT NULL, UNIQUE (branch_id, variant_id)
);
"""


class DefaultBranchTests(unittest.TestCase):
    setUpClass = classmethod(base.AuthFlowTests.setUpClass.__func__)
    tearDownClass = classmethod(base.AuthFlowTests.tearDownClass.__func__)
    provision = base.AuthFlowTests.provision
    login = base.AuthFlowTests.login

    def setUp(self):
        base.AuthFlowTests.setUp(self)
        raw = test_engine.raw_connection()
        try:
            raw.executescript(STORE_TABLES)
            raw.commit()
        finally:
            raw.close()

    def sql(self, statement, params=None):
        from sqlalchemy import text
        with test_engine.begin() as connection:
            result = connection.execute(text(statement), params or {})
            return result.mappings().all() if result.returns_rows else None

    def branches(self, store_id):
        return self.sql("SELECT * FROM branches WHERE store_id = :s ORDER BY branch_id", {"s": store_id})

    def owner_login(self, **extra):
        response = self.client.post("/api/v1/auth/login", json={
            "username": "owner1", "password": "owner-password-123", **extra,
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_first_owner_login_creates_main_branch_with_inventory_rows(self):
        shop_id = self.provision().json()["shop_id"]
        self.sql("INSERT INTO products VALUES (1, :s), (2, 999)", {"s": shop_id})
        self.sql("INSERT INTO product_variants VALUES (10, 1, 'ACTIVE'), (11, 1, 'INACTIVE'), (12, 2, 'ACTIVE')")

        body = self.owner_login()

        rows = self.branches(shop_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(body["branch_setup"], "created")
        self.assertEqual(body["default_branch_id"], rows[0]["branch_id"])
        self.assertEqual((rows[0]["branch_code"], rows[0]["name"], rows[0]["status"], rows[0]["address"]),
                         ("CN01", "Chi nhánh chính", "ACTIVE", ""))
        inventory = self.sql("SELECT branch_id, variant_id, quantity FROM inventory")
        # Only the store's ACTIVE variant gets a zero row; other stores are untouched.
        self.assertEqual([dict(r) for r in inventory], [{"branch_id": rows[0]["branch_id"], "variant_id": 10, "quantity": 0}])

    def test_english_login_names_branch_main_branch(self):
        shop_id = self.provision().json()["shop_id"]
        self.owner_login(locale="en")
        self.assertEqual(self.branches(shop_id)[0]["name"], "Main Branch")

    def test_next_logins_and_refresh_reuse_existing_branch(self):
        shop_id = self.provision().json()["shop_id"]
        first = self.owner_login()
        second = self.owner_login()
        self.assertEqual(second["branch_setup"], "existing")
        self.assertEqual(second["default_branch_id"], first["default_branch_id"])
        refreshed = self.client.post("/api/v1/auth/refresh")
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        self.assertEqual(refreshed.json()["default_branch_id"], first["default_branch_id"])
        self.assertEqual(len(self.branches(shop_id)), 1)

    def test_owner_with_several_branches_gets_first_active_and_nothing_is_created(self):
        shop_id = self.provision().json()["shop_id"]
        self.sql("""INSERT INTO branches (store_id, branch_code, name, address, status) VALUES
            (:s, 'HN', 'Ha Noi', 'a', 'INACTIVE'), (:s, 'HCM', 'HCM', 'b', 'ACTIVE'), (:s, 'DN', 'DN', 'c', 'ACTIVE')""",
                 {"s": shop_id})
        body = self.owner_login()
        rows = self.branches(shop_id)
        self.assertEqual(len(rows), 3)
        self.assertEqual(body["branch_setup"], "existing")
        self.assertEqual(body["default_branch_id"], rows[1]["branch_id"])

    def test_store_with_only_inactive_branches_is_not_given_a_new_branch(self):
        shop_id = self.provision().json()["shop_id"]
        self.sql("INSERT INTO branches (store_id, branch_code, name, address, status) VALUES (:s, 'CN01', 'Old', 'x', 'INACTIVE')",
                 {"s": shop_id})
        body = self.owner_login()
        self.assertEqual((body["branch_setup"], body["default_branch_id"]), ("inactive", None))
        self.assertEqual(len(self.branches(shop_id)), 1)

    def test_manager_and_staff_logins_never_create_branches(self):
        shop_id = self.provision().json()["shop_id"]
        # Create staff accounts with the owner session, then remove the branch that login created
        # so the store is empty again before the staff log in.
        owner = self.owner_login()
        headers = {"Authorization": f"Bearer {owner['access_token']}"}
        for username, role in (("manager1", "manager"), ("staff1", "staff")):
            created = self.client.post("/api/v1/users", headers=headers, json={
                "username": username, "full_name": role, "password": "role-password-123", "role": role,
            })
            self.assertEqual(created.status_code, 201, created.text)
        self.sql("DELETE FROM inventory")
        self.sql("DELETE FROM branches")
        for login_name in ("manager1:manager", "staff1:staff"):
            response = self.login(login_name, "role-password-123")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["branch_setup"], "not_applicable")
            self.assertIsNone(response.json()["default_branch_id"])
        self.assertEqual(self.branches(shop_id), [])

    def test_failed_creation_rolls_back_and_login_still_succeeds(self):
        shop_id = self.provision().json()["shop_id"]
        with patch.object(defaults, "create_zero_inventory_rows",
                          side_effect=OperationalError("INSERT", {}, Exception("disk full"))):
            body = self.owner_login()
        self.assertEqual((body["branch_setup"], body["default_branch_id"]), ("failed", None))
        self.assertEqual(self.branches(shop_id), [], "the half-created branch must be rolled back")
        # The next login retries and succeeds.
        self.assertEqual(self.owner_login()["branch_setup"], "created")

    def test_concurrent_creation_loses_race_gracefully(self):
        """Simulate a second request inserting CN01 between our check and our insert."""
        shop_id = self.provision().json()["shop_id"]
        real_first_branch = defaults._first_branch
        calls = {"n": 0}

        def racing_first_branch(db, store_id):
            calls["n"] += 1
            if calls["n"] == 1:
                self.sql("INSERT INTO branches (store_id, branch_code, name, address, status) "
                         "VALUES (:s, 'CN01', 'Chi nhánh chính', '', 'ACTIVE')", {"s": store_id})
                return None, False  # our check ran before the other insert committed
            return real_first_branch(db, store_id)

        with patch.object(defaults, "_first_branch", side_effect=racing_first_branch), \
                patch.object(defaults, "_free_branch_code", return_value="CN01"):
            body = self.owner_login()
        rows = self.branches(shop_id)
        self.assertEqual(len(rows), 1, "unique (store_id, branch_code) must prevent a duplicate")
        self.assertEqual((body["branch_setup"], body["default_branch_id"]), ("existing", rows[0]["branch_id"]))

    def test_branch_code_skips_codes_already_used(self):
        shop_id = self.provision().json()["shop_id"]
        self.sql("INSERT INTO branches (store_id, branch_code, name, address, status) VALUES (:s, 'CN01', 'x', 'x', 'INACTIVE'), (:s, 'CN02', 'y', 'y', 'INACTIVE')",
                 {"s": shop_id})
        with base.TestSession() as db:
            self.assertEqual(defaults._free_branch_code(db, shop_id), "CN03")


if __name__ == "__main__":
    unittest.main()
