import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from task_scheduler.persistence import db


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "tasks.db"
        self.conn = db.get_connection(self.db_path)
        self.now = datetime(2026, 8, 24, 9, 0)

    def tearDown(self):
        self.conn.close()
        self.tmp_dir.cleanup()

    def task(self, **overrides):
        task = {
            "id": "task-1",
            "name": "Write OS notes",
            "deadline": datetime(2026, 8, 24, 18, 0),
            "duration_min": 45,
            "priority": "High",
            "status": "pending",
            "created_at": self.now,
        }
        task.update(overrides)
        return task

    def test_add_and_load_task(self):
        db.add_task(self.conn, self.task())

        tasks = db.get_all_tasks(self.conn)

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["id"], "task-1")
        self.assertEqual(tasks[0]["deadline"], datetime(2026, 8, 24, 18, 0))

    def test_update_task_status(self):
        db.add_task(self.conn, self.task())

        db.update_task_status(self.conn, "task-1", "done")

        tasks = db.get_all_tasks(self.conn)
        self.assertEqual(tasks[0]["status"], "done")

    def test_get_task_by_id(self):
        db.add_task(self.conn, self.task())

        task = db.get_task_by_id(self.conn, "task-1")

        self.assertEqual(task["name"], "Write OS notes")

    def test_update_task_keeps_id_and_created_at(self):
        db.add_task(self.conn, self.task())

        updated = db.update_task(
            self.conn,
            "task-1",
            {
                "name": "Updated notes",
                "duration_min": 60,
                "priority": "Medium",
            },
        )

        self.assertEqual(updated["id"], "task-1")
        self.assertEqual(updated["created_at"], self.now)
        self.assertEqual(updated["name"], "Updated notes")
        self.assertEqual(db.get_all_tasks(self.conn)[0]["duration_min"], 60)

    def test_update_task_rejects_unknown_field(self):
        db.add_task(self.conn, self.task())

        with self.assertRaises(ValueError):
            db.update_task(self.conn, "task-1", {"created_at": datetime.now()})

    def test_update_task_rejects_missing_task(self):
        with self.assertRaises(ValueError):
            db.update_task(self.conn, "missing", {"name": "Nope"})

    def test_delete_task(self):
        db.add_task(self.conn, self.task())

        db.delete_task(self.conn, "task-1")

        self.assertEqual(db.get_all_tasks(self.conn), [])

    def test_rejects_invalid_duration(self):
        with self.assertRaises(ValueError):
            db.add_task(self.conn, self.task(duration_min=0))

    def test_rejects_invalid_priority(self):
        with self.assertRaises(ValueError):
            db.add_task(self.conn, self.task(priority="Urgent"))

    def test_rejects_invalid_status_update(self):
        with self.assertRaises(ValueError):
            db.update_task_status(self.conn, "task-1", "blocked")


if __name__ == "__main__":
    unittest.main()
