import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from task_scheduler.core import rescheduler
from task_scheduler.persistence import db


class ReschedulerTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.conn = db.get_connection(Path(self.tmp_dir.name) / "tasks.db")
        self.today = datetime(2026, 8, 24)
        self.start_time = self.today.replace(hour=8)

    def tearDown(self):
        self.conn.close()
        self.tmp_dir.cleanup()

    def task(self, task_id, name, deadline_hour, duration, created_minute, status="pending"):
        return {
            "id": task_id,
            "name": name,
            "deadline": self.today.replace(hour=deadline_hour),
            "duration_min": duration,
            "priority": "Medium",
            "status": status,
            "created_at": self.today.replace(hour=7, minute=created_minute),
        }

    def test_add_task_and_reschedule_places_urgent_task_first(self):
        db.add_task(self.conn, self.task("task-1", "Later report", 18, 60, 0))

        state = rescheduler.add_task_and_reschedule(
            self.conn,
            self.task("task-2", "Urgent email", 10, 15, 5),
            start_time=self.start_time,
            now=self.start_time,
        )

        self.assertEqual([entry["task_id"] for entry in state["schedule"]], ["task-2", "task-1"])
        self.assertEqual(len(state["tasks"]), 2)

    def test_edit_task_and_reschedule_reorders_pending_tasks(self):
        db.add_task(self.conn, self.task("task-1", "Report", 18, 60, 0))
        db.add_task(self.conn, self.task("task-2", "Email", 12, 15, 5))

        state = rescheduler.edit_task_and_reschedule(
            self.conn,
            "task-1",
            {"deadline": self.today.replace(hour=9)},
            start_time=self.start_time,
            now=self.start_time,
        )

        self.assertEqual([entry["task_id"] for entry in state["schedule"]], ["task-1", "task-2"])

    def test_mark_done_and_reschedule_removes_task_from_schedule_only(self):
        db.add_task(self.conn, self.task("task-1", "Report", 18, 60, 0))
        db.add_task(self.conn, self.task("task-2", "Email", 10, 15, 5))

        state = rescheduler.mark_done_and_reschedule(
            self.conn,
            "task-2",
            start_time=self.start_time,
            now=self.start_time,
        )

        self.assertEqual([entry["task_id"] for entry in state["schedule"]], ["task-1"])
        self.assertEqual(len(state["tasks"]), 2)
        self.assertEqual(len(state["pending_tasks"]), 1)

    def test_delete_task_and_reschedule_removes_task_from_state(self):
        db.add_task(self.conn, self.task("task-1", "Report", 18, 60, 0))
        db.add_task(self.conn, self.task("task-2", "Email", 10, 15, 5))

        state = rescheduler.delete_task_and_reschedule(
            self.conn,
            "task-2",
            start_time=self.start_time,
            now=self.start_time,
        )

        self.assertEqual([entry["task_id"] for entry in state["schedule"]], ["task-1"])
        self.assertEqual([task["id"] for task in state["tasks"]], ["task-1"])

    def test_in_progress_task_stays_unscheduled(self):
        db.add_task(self.conn, self.task("task-1", "Current task", 9, 60, 0, status="in_progress"))
        db.add_task(self.conn, self.task("task-2", "Next task", 10, 30, 5))

        state = rescheduler.build_schedule_state(
            self.conn,
            start_time=self.start_time,
            now=self.start_time,
        )

        self.assertEqual([entry["task_id"] for entry in state["schedule"]], ["task-2"])
        self.assertEqual(len(state["tasks"]), 2)


if __name__ == "__main__":
    unittest.main()
