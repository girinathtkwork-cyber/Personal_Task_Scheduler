import unittest
from datetime import datetime

from task_scheduler.core.scheduler import generate_schedule


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.today = datetime(2026, 8, 24)
        self.start_time = self.today.replace(hour=8)

    def task(self, task_id, name, deadline_hour, duration, priority, created_minute, status="pending"):
        return {
            "id": task_id,
            "name": name,
            "deadline": self.today.replace(hour=deadline_hour),
            "duration_min": duration,
            "priority": priority,
            "status": status,
            "created_at": self.today.replace(hour=7, minute=created_minute),
        }

    def test_edf_orders_by_deadline(self):
        tasks = [
            self.task("task-1", "Later", 18, 30, "High", 0),
            self.task("task-2", "Sooner", 10, 30, "Low", 1),
        ]

        schedule = generate_schedule(tasks, start_time=self.start_time)

        self.assertEqual([entry["task_id"] for entry in schedule], ["task-2", "task-1"])

    def test_edf_tie_breaks_by_priority_then_created_at(self):
        tasks = [
            self.task("task-1", "Low priority", 12, 30, "Low", 0),
            self.task("task-2", "High newer", 12, 30, "High", 10),
            self.task("task-3", "High older", 12, 30, "High", 5),
        ]

        schedule = generate_schedule(tasks, start_time=self.start_time)

        self.assertEqual(
            [entry["task_id"] for entry in schedule],
            ["task-3", "task-2", "task-1"],
        )

    def test_scheduler_ignores_non_pending_tasks(self):
        tasks = [
            self.task("task-1", "Pending", 12, 30, "Medium", 0),
            self.task("task-2", "Done", 9, 30, "High", 1, status="done"),
            self.task("task-3", "In progress", 10, 30, "High", 2, status="in_progress"),
        ]

        schedule = generate_schedule(tasks, start_time=self.start_time)

        self.assertEqual([entry["task_id"] for entry in schedule], ["task-1"])

    def test_fcfs_orders_by_created_at(self):
        tasks = [
            self.task("task-1", "Created second", 9, 30, "High", 20),
            self.task("task-2", "Created first", 18, 30, "Low", 5),
        ]

        schedule = generate_schedule(tasks, algorithm="FCFS", start_time=self.start_time)

        self.assertEqual([entry["task_id"] for entry in schedule], ["task-2", "task-1"])

    def test_rejects_unknown_algorithm(self):
        with self.assertRaises(ValueError):
            generate_schedule([], algorithm="SJF", start_time=self.start_time)


if __name__ == "__main__":
    unittest.main()
