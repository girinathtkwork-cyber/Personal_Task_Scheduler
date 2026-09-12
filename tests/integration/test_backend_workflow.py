import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from task_scheduler.core import rescheduler
from task_scheduler.persistence import db


class BackendWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "tasks.db"
        self.today = datetime(2026, 9, 24)
        self.start_time = self.today.replace(hour=8)
        self.conn = db.get_connection(self.db_path)

    def tearDown(self):
        self.conn.close()
        self.tmp_dir.cleanup()

    def task(self, task_id, name, deadline, created_minute, status="pending"):
        return {
            "id": task_id,
            "name": name,
            "deadline": deadline,
            "duration_min": 30,
            "priority": "Medium",
            "status": status,
            "created_at": self.today.replace(hour=7, minute=created_minute),
        }

    def test_backend_workflow_persists_compares_and_reschedules(self):
        urgent = self.task(
            "urgent",
            "Urgent task",
            self.today.replace(hour=8, minute=30),
            created_minute=20,
        )
        later = self.task(
            "later",
            "Later task",
            self.today.replace(hour=18),
            created_minute=0,
        )
        db.add_task(self.conn, urgent)
        db.add_task(self.conn, later)
        self.conn.close()

        self.conn = db.get_connection(self.db_path)
        state = rescheduler.build_schedule_state(
            self.conn,
            start_time=self.start_time,
            now=self.start_time,
        )

        self.assertEqual([entry["task_id"] for entry in state["schedule"]], ["urgent", "later"])
        self.assertEqual(state["comparison"]["EDF"]["deadlines_missed"], 0)
        self.assertEqual(state["comparison"]["FCFS"]["deadlines_missed"], 1)
        self.assertEqual(len(db.get_history(self.conn)), 2)

        completed = rescheduler.mark_done_and_reschedule(
            self.conn,
            "urgent",
            start_time=self.start_time,
            now=self.start_time,
        )
        self.assertEqual([entry["task_id"] for entry in completed["schedule"]], ["later"])
        self.assertEqual(len(completed["tasks"]), 2)

        deleted = rescheduler.delete_task_and_reschedule(
            self.conn,
            "later",
            start_time=self.start_time,
            now=self.start_time,
        )
        self.assertEqual([task["id"] for task in deleted["tasks"]], ["urgent"])
        self.assertEqual(deleted["tasks"][0]["status"], "done")
        self.assertEqual(deleted["schedule"], [])
        self.assertEqual(len(db.get_history(self.conn)), 6)


if __name__ == "__main__":
    unittest.main()
