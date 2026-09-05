import unittest
from datetime import datetime

from task_scheduler.core.schedulability import check_schedulability


class SchedulabilityTests(unittest.TestCase):
    def setUp(self):
        self.today = datetime(2026, 8, 24)
        self.now = self.today.replace(hour=9)

    def task(self, task_id, name, deadline_hour, duration, priority="Medium", status="pending"):
        return {
            "id": task_id,
            "name": name,
            "deadline": self.today.replace(hour=deadline_hour),
            "duration_min": duration,
            "priority": priority,
            "status": status,
            "created_at": self.today.replace(hour=8),
        }

    def test_feasible_task_set(self):
        tasks = [
            self.task("task-1", "Email", 11, 15),
            self.task("task-2", "Report", 18, 120),
        ]

        result = check_schedulability(tasks, now=self.now)

        self.assertTrue(result["feasible"])
        self.assertEqual(result["at_risk_tasks"], [])

    def test_overloaded_task_set_returns_task_ids(self):
        tasks = [
            self.task("task-1", "Huge report", 10, 180, "High"),
            self.task("task-2", "Quick email", 11, 15, "High"),
        ]

        result = check_schedulability(tasks, now=self.now)

        self.assertFalse(result["feasible"])
        self.assertEqual(result["at_risk_tasks"], ["task-1", "task-2"])
        self.assertIn("Huge report", result["message"])

    def test_ignores_non_pending_tasks(self):
        tasks = [
            self.task("task-1", "Completed impossible task", 10, 180, status="done"),
        ]

        result = check_schedulability(tasks, now=self.now)

        self.assertTrue(result["feasible"])


if __name__ == "__main__":
    unittest.main()
