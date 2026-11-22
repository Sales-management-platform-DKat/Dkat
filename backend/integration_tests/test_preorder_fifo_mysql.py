"""FIFO and post-import preorder notifications on isolated MySQL."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core import config
from app.db.session import engine
from app.main import app
from app.modules.preorders.services.allocation import (
    AllocationInvariantError, allocate_imported_preorders, allocate_preorders,
)


@unittest.skipUnless(os.getenv("DKAT_FIFO_TEST_DB") == "1", "Requires isolated MySQL test database")
class PreorderFifoMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if engine.url.host not in {"127.0.0.1", "localhost"} or engine.url.database != "dkat_pbi129_test":
            raise RuntimeError("Use a local, disposable dkat_pbi129_test schema only")
        suffix = uuid4().hex[:10]
        with TestClient(app) as client:
            r = client.post("/api/v1/admin/accounts", headers={"X-Admin-Token": config.ADMIN_TOKEN}, json={
                "shop_name": "FIFO129", "plan": "pro", "subscription_months": 12,
                "owner_username": "fifo" + suffix, "owner_full_name": "FIFO129", "owner_password": "fifo129-password-123",
            })
            assert r.status_code == 201, r.text
            cls.store = r.json()["shop_id"]
            r = client.post("/api/v1/auth/login", json={"username": "fifo" + suffix, "password": "fifo129-password-123"})
            assert r.status_code == 200, r.text
            cls.owner = {"Authorization": "Bearer " + r.json()["access_token"]}
            user = r.json()["user"]["id"]
        with engine.begin() as db:
            cls.branches = [db.execute(text("""
                INSERT INTO branches (store_id,branch_code,name,address,status) VALUES (:s,:code,:code,'QA','ACTIVE')
            """), {"s": cls.store, "code": code}).lastrowid for code in ("A", "B")]
            category = db.execute(text("INSERT INTO categories (store_id,name,status) VALUES (:s,'FIFO129','ACTIVE')"), {"s": cls.store}).lastrowid
            product = db.execute(text("""
                INSERT INTO products (store_id,category_id,product_code,name,status,created_by)
                VALUES (:s,:c,'FIFO129','FIFO129','ACTIVE',:u)
            """), {"s": cls.store, "c": category, "u": user}).lastrowid
            cls.variants = [db.execute(text("""
                INSERT INTO product_variants (product_id,sku,variant_name,price,status)
                VALUES (:p,:sku,'QA',1,'ACTIVE')
            """), {"p": product, "sku": suffix + str(i)}).lastrowid for i in range(2)]
            for branch in cls.branches:
                for variant in cls.variants:
                    db.execute(text("INSERT INTO inventory (branch_id,variant_id,quantity) VALUES (:b,:v,0)"), {"b": branch, "v": variant})
        cls.branch, cls.variant = cls.branches[0], cls.variants[0]

    def setUp(self):
        self.days_patch = patch.object(config, "PREORDER_READY_DAYS", 7)
        self.days_patch.start()
        self.addCleanup(self.days_patch.stop)
        with engine.begin() as db:
            db.execute(text("UPDATE inventory SET quantity=0 WHERE branch_id IN (:a,:b)"), {"a": self.branch, "b": self.branches[1]})
            db.execute(text("UPDATE preorders SET status='CANCELLED' WHERE branch_id IN (:a,:b)"), {"a": self.branch, "b": self.branches[1]})

    def order(self, quantity=1, *, items=None, allocated=None, status="WAITING_STOCK", branch=None,
              created="2026-01-01 00:00:00", payment="UNPAID"):
        items = items or [(self.variant, quantity)]
        allocated = allocated or {}
        with engine.begin() as db:
            order = db.execute(text("""
                INSERT INTO preorders (preorder_code,branch_id,customer_name,customer_phone,total_amount,
                                       payment_status,status,created_at)
                VALUES (:code,:b,'FIFO129','0900000000',:total,:payment,:status,:created)
            """), {"code": "FIFO-" + uuid4().hex, "b": branch or self.branch, "total": sum(q for _,q in items),
                   "payment": payment, "status": status, "created": created}).lastrowid
            for variant, requested in items:
                db.execute(text("""
                    INSERT INTO preorder_items (preorder_id,variant_id,product_name_snapshot,sku_snapshot,
                                                unit_price,quantity,allocated_quantity,line_total)
                    VALUES (:p,:v,'FIFO129','FIFO129',1,:q,:a,:q)
                """), {"p": order, "v": variant, "q": requested, "a": allocated.get(variant, 0)})
        return order

    def stock(self, quantity, variant=None, branch=None):
        with engine.begin() as db:
            db.execute(text("UPDATE inventory SET quantity=:q WHERE branch_id=:b AND variant_id=:v"),
                       {"q": quantity, "b": branch or self.branch, "v": variant or self.variant})

    def allocate(self, variant=None, branch=None, **options):
        with engine.execution_options(isolation_level="READ COMMITTED").begin() as db:
            return allocate_preorders(db, branch or self.branch, variant or self.variant, **options)

    def state(self, order):
        with engine.connect() as db:
            header = db.execute(text("SELECT status,ready_at,expires_at,payment_status FROM preorders WHERE preorder_id=:p"), {"p": order}).one()
            items = db.execute(text("SELECT variant_id,quantity,allocated_quantity FROM preorder_items WHERE preorder_id=:p ORDER BY preorder_item_id"), {"p": order}).all()
        return header, items

    def stock_snapshot(self):
        with engine.connect() as db:
            inventory = db.execute(text("SELECT inventory_id,quantity,updated_at FROM inventory ORDER BY inventory_id")).all()
            payments = db.execute(text("SELECT COUNT(*) FROM payments")).scalar_one()
            movements = db.execute(text("SELECT COUNT(*) FROM inventory_movements")).scalar_one()
        return inventory, payments, movements

    def concurrent(self, functions):
        barrier = Barrier(len(functions))
        def invoke(fn):
            barrier.wait(timeout=10)
            return fn()
        with ThreadPoolExecutor(max_workers=len(functions)) as pool:
            futures = [pool.submit(invoke, fn) for fn in functions]
            return [future.result(timeout=30) for future in futures]

    def test_acceptance_6_for_A2_B3_C4_fifo_ties_and_repeat_is_idempotent(self):
        a, b, c = self.order(2), self.order(3), self.order(4)
        self.stock(6)
        before = self.stock_snapshot()
        result = self.allocate()
        self.assertEqual([self.state(order)[1][0].allocated_quantity for order in (a,b,c)], [2,3,1])
        self.assertEqual([self.state(order)[0].status for order in (a,b,c)], ["READY", "READY", "WAITING_STOCK"])
        self.assertEqual(result.ready_preorder_ids, (a,b))
        self.assertEqual((result.quantity, result.reserved_quantity, result.allocated_quantity, result.available_quantity), (6,0,6,0))
        for order in (a,b):
            header = self.state(order)[0]
            self.assertEqual(header.expires_at - header.ready_at, timedelta(days=7))
        self.assertIsNone(self.state(c)[0].ready_at)
        self.assertIsNone(self.state(c)[0].expires_at)
        states = [self.state(order) for order in (a,b,c)]
        repeated = self.allocate()
        self.assertEqual((repeated.allocated_quantity, repeated.changes, repeated.ready_preorder_ids), (0, (), ()))
        self.assertEqual([self.state(order) for order in (a,b,c)], states)
        self.assertEqual(self.stock_snapshot(), before)
        print('FIFO acceptance passed: stock=6; A=2 READY, B=3 READY, C=1 WAITING_STOCK; rerun allocates 0.')

    def test_earlier_created_time_takes_priority_over_lower_id(self):
        later = self.order(3, created="2026-01-02 00:00:00")
        earlier = self.order(2, created="2026-01-01 00:00:00")
        self.stock(2)
        self.assertEqual(self.allocate().ready_preorder_ids, (earlier,))
        self.assertEqual(self.state(later)[1][0].allocated_quantity, 0)

    def test_partial_allocations_only_top_up_missing_quantity(self):
        a = self.order(4, allocated={self.variant: 2})
        b = self.order(4)
        self.stock(6)
        result = self.allocate()
        self.assertEqual((result.reserved_quantity, result.allocated_quantity), (2,4))
        self.assertEqual([self.state(order)[1][0].allocated_quantity for order in (a,b)], [4,2])
        first_ready = self.state(a)[0]
        self.stock(8)
        self.assertEqual(self.allocate().ready_preorder_ids, (b,))
        self.assertEqual(self.state(a)[0], first_ready)
        self.assertEqual(self.state(b)[1][0].allocated_quantity, 4)

    def test_open_reservations_are_protected_and_closed_reservations_are_excluded(self):
        ready = self.order(3, allocated={self.variant: 3}, status="READY")
        notified = self.order(2, allocated={self.variant: 2}, status="NOTIFIED")
        partial = self.order(2, allocated={self.variant: 1}, payment="PAID")
        pending = self.order(5)
        closed = [self.order(99, allocated={self.variant: 99}, status=status) for status in ("CANCELLED", "EXPIRED", "FULFILLED")]
        before = [self.state(order) for order in (ready,notified,*closed)]
        self.stock(10)
        result = self.allocate()
        self.assertEqual((result.reserved_quantity, result.allocated_quantity), (6,4))
        self.assertEqual(result.ready_preorder_ids, (partial,))
        self.assertEqual(self.state(pending)[1][0].allocated_quantity, 3)
        self.assertEqual(self.state(partial)[0].payment_status, "PAID")
        self.assertEqual([self.state(order) for order in (ready,notified,*closed)], before)

    def test_empty_queue_and_zero_fund_do_not_change_stock(self):
        self.stock(6)
        before = self.stock_snapshot()
        self.assertEqual(self.allocate().available_quantity, 6)
        self.assertEqual(self.stock_snapshot(), before)
        order = self.order(2)
        self.stock(0)
        self.assertEqual(self.allocate().changes, ())
        self.assertEqual((self.state(order)[0].status, self.state(order)[1][0].allocated_quantity), ("WAITING_STOCK",0))

    def test_missing_inventory_is_zero_without_inserting_rows(self):
        with engine.begin() as db:
            db.execute(text("DELETE FROM inventory WHERE branch_id=:b AND variant_id=:v"), {"b": self.branch, "v": self.variants[1]})
        order = self.order(items=[(self.variants[1],2)])
        before = self.stock_snapshot()
        try:
            self.assertEqual(self.allocate(self.variants[1]).allocated_quantity, 0)
            self.assertEqual(self.stock_snapshot(), before)
            self.assertEqual(self.state(order)[1][0].allocated_quantity, 0)
        finally:
            with engine.begin() as db:
                db.execute(text("INSERT INTO inventory (branch_id,variant_id,quantity) VALUES (:b,:v,0)"), {"b": self.branch, "v": self.variants[1]})

    def test_reservations_above_stock_abort_without_new_allocations(self):
        existing = self.order(4, allocated={self.variant:4}, status="READY")
        waiting = self.order(1)
        self.stock(3)
        before = [self.state(order) for order in (existing,waiting)]
        with self.assertRaisesRegex(AllocationInvariantError, 'RESERVATION_EXCEEDS_STOCK'):
            self.allocate()
        self.assertEqual([self.state(order) for order in (existing,waiting)], before)

    def test_multiple_lines_require_all_variants_before_ready(self):
        order = self.order(items=[(self.variant,2),(self.variants[1],3)])
        self.stock(2)
        self.stock(3, self.variants[1])
        self.assertEqual(self.allocate().ready_preorder_ids, ())
        self.assertEqual(self.state(order)[0].status, "WAITING_STOCK")
        self.assertIsNone(self.state(order)[0].expires_at)
        self.assertEqual(self.allocate(self.variants[1]).ready_preorder_ids, (order,))
        self.assertEqual(self.state(order)[0].status, "READY")

    def test_branch_and_variant_queues_are_independent(self):
        here, elsewhere = self.order(2), self.order(2, branch=self.branches[1])
        other_variant = self.order(items=[(self.variants[1],2)])
        self.stock(2)
        self.stock(2, branch=self.branches[1])
        self.stock(2, self.variants[1])
        self.allocate()
        self.assertEqual(self.state(here)[0].status, "READY")
        self.assertEqual(self.state(elsewhere)[1][0].allocated_quantity, 0)
        self.assertEqual(self.state(other_variant)[1][0].allocated_quantity, 0)

    def test_configured_deadline_and_repeat_do_not_extend_ready_times(self):
        order = self.order(1)
        self.stock(10)
        with patch.object(config, "PREORDER_READY_DAYS", 3):
            self.allocate()
        header = self.state(order)[0]
        self.assertEqual(header.expires_at-header.ready_at, timedelta(days=3))
        with engine.begin() as db:
            db.execute(text("UPDATE preorders SET ready_at='2026-01-01',expires_at='2026-01-04' WHERE preorder_id=:p"), {"p":order})
        self.allocate(ready_days=7)
        header = self.state(order)[0]
        self.assertEqual((header.ready_at, header.expires_at), (datetime(2026,1,1), datetime(2026,1,4)))

    def test_input_and_transaction_contract_are_explicit(self):
        with engine.connect() as db:
            with self.assertRaisesRegex(ValueError, "READ COMMITTED"):
                allocate_preorders(db,self.branch,self.variant)
        with engine.execution_options(isolation_level="REPEATABLE READ").begin() as db:
            with self.assertRaisesRegex(ValueError, "READ COMMITTED"):
                allocate_preorders(db,self.branch,self.variant)
        with engine.execution_options(isolation_level="READ COMMITTED").begin() as db:
            for days in (0, -1, 366, True, '7'):
                with self.assertRaises(ValueError):
                    allocate_preorders(db,self.branch,self.variant,ready_days=days)
            for variant in (0, -1, True, '1'):
                with self.assertRaises(ValueError):
                    allocate_preorders(db,self.branch,variant)

    def test_two_workers_same_variant_do_not_allocate_twice(self):
        orders = [self.order(q) for q in (2,3,4)]
        self.stock(6)
        results = self.concurrent([self.allocate, self.allocate])
        self.assertEqual(sum(result.allocated_quantity for result in results), 6)
        self.assertEqual(sum(len(result.ready_preorder_ids) for result in results), 2)
        self.assertEqual([self.state(order)[1][0].allocated_quantity for order in orders], [2,3,1])

    def test_workers_for_different_variants_mark_multi_line_order_ready_once(self):
        order = self.order(items=[(self.variant,2),(self.variants[1],3)])
        self.stock(2)
        self.stock(3,self.variants[1])
        results = self.concurrent([self.allocate, lambda:self.allocate(self.variants[1])])
        self.assertEqual(sum(len(result.ready_preorder_ids) for result in results), 1)
        self.assertEqual(self.state(order)[0].status, "READY")
        self.assertEqual([item.allocated_quantity for item in self.state(order)[1]], [2,3])

    def test_opposite_line_order_across_orders_does_not_deadlock(self):
        a = self.order(items=[(self.variant,2),(self.variants[1],3)])
        b = self.order(items=[(self.variants[1],3),(self.variant,2)])
        self.stock(4)
        self.stock(6,self.variants[1])
        results = self.concurrent([self.allocate, lambda:self.allocate(self.variants[1])])
        self.assertEqual(sum(result.allocated_quantity for result in results), 10)
        self.assertEqual([self.state(order)[0].status for order in (a,b)], ["READY","READY"])

    def test_batch_hook_handles_unsorted_duplicate_variants_and_is_idempotent(self):
        order = self.order(items=[(self.variant,2),(self.variants[1],3)])
        self.stock(2)
        self.stock(3,self.variants[1])
        self.assertEqual(allocate_imported_preorders(self.branch,[self.variants[1],self.variant,self.variant]), [order])
        self.assertEqual(allocate_imported_preorders(self.branch,list(self.variants)), [])
        self.assertEqual(allocate_imported_preorders(self.branch,[]), [])

    def check_sql_rollback(self, stage):
        orders = [self.order(q) for q in (2,3,4)]
        self.stock(6)
        before = [self.state(order) for order in orders]
        clause = ("BEFORE UPDATE ON preorder_items", f"NEW.preorder_id={orders[1]} AND NEW.allocated_quantity>OLD.allocated_quantity") if stage == "item" else (
            "BEFORE UPDATE ON preorders", f"NEW.preorder_id={orders[1]} AND NEW.status='READY'")
        with engine.begin() as db:
            db.exec_driver_sql(f"""
                CREATE TRIGGER pbi129_fail_fifo {clause[0]} FOR EACH ROW
                BEGIN IF {clause[1]} THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PBI129 test failure'; END IF; END
            """)
        try:
            with self.assertRaises(SQLAlchemyError):
                self.allocate()
            self.assertEqual([self.state(order) for order in orders], before)
        finally:
            with engine.begin() as db:
                db.exec_driver_sql("DROP TRIGGER pbi129_fail_fifo")
        self.assertEqual(self.allocate().allocated_quantity, 6)

    def test_item_sql_failure_rolls_back_earlier_allocations_and_ready_states(self):
        self.check_sql_rollback("item")

    def test_ready_sql_failure_rolls_back_all_changes(self):
        self.check_sql_rollback("ready")

    def test_batch_second_variant_failure_rolls_back_first_variant(self):
        order = self.order(items=[(self.variant,2),(self.variants[1],3)])
        self.stock(2)
        self.stock(3,self.variants[1])
        before = self.state(order)
        with engine.begin() as db:
            db.exec_driver_sql(f"""
                CREATE TRIGGER pbi129_fail_batch BEFORE UPDATE ON preorder_items FOR EACH ROW
                BEGIN IF NEW.preorder_id={order} AND NEW.variant_id={self.variants[1]} THEN
                    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PBI129 batch failure'; END IF; END
            """)
        try:
            with self.assertRaises(SQLAlchemyError):
                allocate_imported_preorders(self.branch,list(self.variants))
            self.assertEqual(self.state(order),before)
        finally:
            with engine.begin() as db:
                db.exec_driver_sql("DROP TRIGGER pbi129_fail_batch")

    def test_stock_import_existing_hook_and_expiry_visible_in_detail(self):
        a,b,c = [self.order(q) for q in (2,3,4)]
        with TestClient(app) as client:
            with patch.dict("sys.modules", {"app.modules.notifications.service": None}):
                with self.assertLogs("app.modules.inventory.post_import", level="WARNING"):
                    response = client.post('/inventory/import',headers=self.owner,json={'branchId':self.branch,'items':[{'variantId':self.variant,'quantity':6}]})
            self.assertEqual(response.status_code,201,response.text)
            detail = client.get(f'/preorders/{a}',headers=self.owner)
        self.assertEqual(detail.status_code,200,detail.text)
        self.assertEqual(detail.json()['status'],'READY')
        self.assertTrue(detail.json()['expiresAt'].endswith('Z'))
        self.assertEqual([self.state(order)[1][0].allocated_quantity for order in (a,b,c)],[2,3,1])
        with engine.connect() as db:
            self.assertEqual(db.execute(text('SELECT quantity FROM inventory WHERE branch_id=:b AND variant_id=:v'),{'b':self.branch,'v':self.variant}).scalar_one(),6)

    def test_failed_post_commit_hook_keeps_import_committed_but_no_partial_allocation(self):
        order = self.order(2)
        with engine.begin() as db:
            db.exec_driver_sql(f"""
                CREATE TRIGGER pbi129_fail_import BEFORE UPDATE ON preorder_items FOR EACH ROW
                BEGIN IF NEW.preorder_id={order} THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PBI129 hook failure'; END IF; END
            """)
        try:
            with self.assertLogs('app.modules.inventory.post_import',level='ERROR'):
                with TestClient(app) as client:
                    response = client.post('/inventory/import',headers=self.owner,json={'branchId':self.branch,'items':[{'variantId':self.variant,'quantity':6}]})
            self.assertEqual(response.status_code,201,response.text)
            self.assertEqual(self.state(order)[1][0].allocated_quantity,0)
            self.assertEqual(self.state(order)[0].status,'WAITING_STOCK')
            with engine.connect() as db:
                self.assertEqual(db.execute(text('SELECT quantity FROM inventory WHERE branch_id=:b AND variant_id=:v'),{'b':self.branch,'v':self.variant}).scalar_one(),6)
        finally:
            with engine.begin() as db:
                db.exec_driver_sql('DROP TRIGGER pbi129_fail_import')

    def record_notification(self, preorder_id, channel, status):
        with engine.begin() as db:
            db.execute(text("""
                INSERT INTO notifications (preorder_id, channel, recipient, message, status)
                VALUES (:id, :channel, 'QA', 'PBI130 test notification', :status)
            """), {"id": preorder_id, "channel": channel, "status": status})

    def test_import_notifies_after_commits_and_uses_persisted_channel_statuses(self):
        failed, pending, partly_sent, sent, waiting = [self.order(q) for q in (1, 1, 1, 1, 3)]
        visible_during_send = []

        def notify(preorder_id, event):
            header, items = self.state(preorder_id)
            with engine.connect() as db:
                quantity = db.execute(text("""
                    SELECT quantity FROM inventory WHERE branch_id=:b AND variant_id=:v
                """), {"b": self.branch, "v": self.variant}).scalar_one()
            visible_during_send.append((preorder_id, event, header.status, items[0].allocated_quantity, quantity))
            if preorder_id in (failed, partly_sent):
                self.record_notification(preorder_id, "SMS", "FAILED")
                if preorder_id == partly_sent:
                    self.record_notification(preorder_id, "EMAIL", "SENT")
                raise RuntimeError("Test channel unavailable")
            self.record_notification(preorder_id, "EMAIL", "PENDING" if preorder_id == pending else "SENT")

        with TestClient(app) as client, patch(
            "app.modules.notifications.service.NotificationService", create=True,
        ) as service:
            service.notifyPreorder.side_effect = notify
            payload = {"branchId": self.branch, "items": [{"variantId": self.variant, "quantity": 5}]}
            with self.assertLogs("app.modules.inventory.post_import", level="WARNING") as logs:
                response = client.post("/inventory/import", headers=self.owner, json=payload)
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(len(logs.records), 2)
            expected = {
                failed: ("READY", {"SMS": "FAILED"}),
                pending: ("READY", {"EMAIL": "PENDING"}),
                partly_sent: ("NOTIFIED", {"SMS": "FAILED", "EMAIL": "SENT"}),
                sent: ("NOTIFIED", {"EMAIL": "SENT"}),
                waiting: ("WAITING_STOCK", {}),
            }
            for preorder_id, (status, notifications) in expected.items():
                detail = client.get(f"/preorders/{preorder_id}", headers=self.owner)
                self.assertEqual(detail.status_code, 200, detail.text)
                body = detail.json()
                self.assertEqual(body["status"], status)
                self.assertEqual({row["channel"]: row["status"] for row in body["notifications"]}, notifications)
                if preorder_id != waiting:
                    self.assertTrue(body["expiresAt"].endswith("Z"))

            payload["items"][0]["quantity"] = 1
            response = client.post("/inventory/import", headers=self.owner, json=payload)
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(service.notifyPreorder.call_count, 4)

        self.assertEqual(visible_during_send, [
            (preorder_id, "PREORDER_READY", "READY", 1, 5)
            for preorder_id in (failed, pending, partly_sent, sent)
        ])

    def test_notification_cannot_overwrite_closed_orders(self):
        orders = {self.order(): status for status in ("CANCELLED", "FULFILLED")}

        def notify(preorder_id, event):
            with engine.begin() as db:
                db.execute(text("UPDATE preorders SET status=:status WHERE preorder_id=:id"),
                           {"id": preorder_id, "status": orders[preorder_id]})
            self.record_notification(preorder_id, "EMAIL", "SENT")

        with TestClient(app) as client, patch(
            "app.modules.notifications.service.NotificationService", create=True,
        ) as service:
            service.notifyPreorder.side_effect = notify
            response = client.post("/inventory/import", headers=self.owner, json={
                "branchId": self.branch, "items": [{"variantId": self.variant, "quantity": 2}],
            })
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(service.notifyPreorder.call_count, 2)
            for preorder_id, status in orders.items():
                detail = client.get(f"/preorders/{preorder_id}", headers=self.owner)
                self.assertEqual(detail.status_code, 200, detail.text)
                self.assertEqual(detail.json()["status"], status)
                self.assertEqual(detail.json()["notifications"][0]["status"], "SENT")

    def test_upgrade_migration_preserves_legacy_ready_order(self):
        with engine.connect() as db:
            row = db.execute(text("SELECT customer_name,status,ready_at,expires_at FROM preorders WHERE preorder_code='LEGACY-PBI129'")).one()
        self.assertEqual((row.customer_name,row.status,row.ready_at,row.expires_at),('Legacy before FIFO','READY',datetime(2026,1,1),None))


if __name__ == '__main__':
    unittest.main(verbosity=2)
