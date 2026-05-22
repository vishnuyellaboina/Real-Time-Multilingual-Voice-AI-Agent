from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from pathlib import Path

from app.scheduler import SchedulerService
from app.storage import Storage


class SchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = Storage(Path("data/test_agent.db"))
        self.storage.connection.execute("DELETE FROM appointments")
        self.storage.connection.commit()
        self.scheduler = SchedulerService(self.storage)

    def test_book_rejects_past_slot(self) -> None:
        result = self.scheduler.book("P1001", "D100", datetime.utcnow() - timedelta(hours=1), "follow-up")
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "past-time")

    def test_book_rejects_conflicting_slot(self) -> None:
        slot = datetime.utcnow().replace(second=0, microsecond=0) + timedelta(days=1, hours=2)
        first = self.scheduler.book("P1001", "D100", slot, "follow-up")
        second = self.scheduler.book("P1002", "D100", slot, "follow-up")
        self.assertTrue(first.ok)
        self.assertFalse(second.ok)
        self.assertEqual(second.reason, "slot-conflict")

    def test_reschedule_allows_same_appointment_to_move(self) -> None:
        original_slot = datetime.utcnow().replace(second=0, microsecond=0) + timedelta(days=1, hours=1)
        booked = self.scheduler.book("P1001", "D100", original_slot, "follow-up")
        assert booked.appointment is not None
        new_slot = original_slot + timedelta(hours=1)
        moved = self.scheduler.reschedule(booked.appointment.appointment_id, new_slot)
        self.assertTrue(moved.ok)
        self.assertEqual(moved.appointment.start_at, new_slot)


if __name__ == "__main__":
    unittest.main()
