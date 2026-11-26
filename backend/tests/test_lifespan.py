import asyncio
from threading import Event
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main


class LifespanTests(unittest.TestCase):
    def test_preorder_expiry_worker_starts_and_stops_with_application(self):
        started = Event()
        stopped = Event()

        async def worker(stop):
            started.set()
            await stop.wait()
            stopped.set()

        with patch.object(main.Base.metadata, "create_all"), patch.object(
            main, "run_preorder_expiry", side_effect=worker
        ):
            with TestClient(main.app):
                self.assertTrue(started.wait(timeout=2))
            self.assertTrue(stopped.wait(timeout=2))
