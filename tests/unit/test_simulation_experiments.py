import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from task_scheduler.persistence import db
from task_scheduler.simulation.engine import SimulationEngine
from task_scheduler.simulation.experiments import create_overrun_demo, run_counterfactual


class SimulationExperimentTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2030, 1, 1, 9)
        self.tasks = [
            {
                "id": "later",
                "name": "Long task",
                "arrival_time": self.start,
                "deadline": self.start + timedelta(minutes=30),
                "estimated_execution_min": 10,
                "priority": "Medium",
            },
            {
                "id": "urgent",
                "name": "Urgent task",
                "arrival_time": self.start,
                "deadline": self.start + timedelta(minutes=5),
                "estimated_execution_min": 2,
                "priority": "High",
            },
        ]

    def test_counterfactual_runs_are_isolated_and_use_actual_outcomes(self):
        experiment = run_counterfactual(
            self.tasks,
            policies=("FCFS", "EDF-P"),
            start_time=self.start,
        )

        self.assertEqual(experiment["runs"]["FCFS"]["metrics"]["deadline_misses"], 1)
        self.assertEqual(experiment["runs"]["EDF-P"]["metrics"]["deadline_misses"], 0)
        self.assertEqual(experiment["comparisons"]["EDF-P"]["verified_prevented_misses"], 1)
        self.assertEqual(self.tasks[0]["estimated_execution_min"], 10)
        self.assertEqual(experiment["runs"]["FCFS"]["tasks"][0]["remaining_min"], 0)
        self.assertNotEqual(
            experiment["runs"]["FCFS"]["tasks"],
            experiment["runs"]["EDF-P"]["tasks"],
        )

    def test_experiment_and_structured_records_round_trip_in_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            conn = db.get_connection(Path(tmp_dir) / "simulation.db")
            try:
                experiment = run_counterfactual(
                    self.tasks,
                    policies=("EDF", "FCFS"),
                    start_time=self.start,
                )
                experiment_id = db.save_simulation_experiment(conn, experiment)
                stored = db.get_simulation_experiment(conn, experiment_id)
                summaries = db.get_simulation_experiment_summaries(conn)

                self.assertEqual(stored["result"]["baseline_policy"], "EDF")
                self.assertEqual(set(stored["result"]["runs"]), {"EDF", "FCFS"})
                self.assertEqual(len(summaries), 1)
                self.assertEqual(len(conn.execute("SELECT * FROM simulation_decisions").fetchall()), 4)
            finally:
                conn.close()

    def test_predefined_overrun_demo_starts_feasible_and_then_misses(self):
        scenario = create_overrun_demo(start_time=self.start)
        engine = SimulationEngine(
            scenario["tasks"],
            start_time=scenario["start_time"],
        )
        self.assertTrue(engine.remaining_workload_forecast()["feasible"])
        for event in scenario["events"]:
            payload = {key: value for key, value in event.items() if key not in {"at", "kind"}}
            engine.schedule_event(event["at"], event["kind"], **payload)

        result = engine.run_to_completion()

        self.assertEqual(result["metrics"]["deadline_misses"], 1)
        self.assertEqual(result["deadline_misses"][0]["task_id"], "demo-report")

    def test_additive_schema_keeps_existing_task_records(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "existing.db"
            raw = sqlite3.connect(path)
            raw.execute(
                """CREATE TABLE tasks (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, deadline TEXT NOT NULL,
                    duration_min INTEGER NOT NULL, priority TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL
                )"""
            )
            raw.execute(
                """INSERT INTO tasks VALUES
                   ('preserved', 'Existing task', '2030-01-01T10:00:00',
                    5, 'High', 'pending', '2030-01-01T09:00:00')"""
            )
            raw.commit()
            raw.close()

            conn = db.get_connection(path)
            try:
                task = db.get_task_by_id(conn, "preserved")
                tables = {
                    row["name"]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                self.assertEqual(task["name"], "Existing task")
                self.assertIn("simulation_experiments", tables)
                self.assertIn("simulation_events", tables)
                self.assertIn("simulation_decisions", tables)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
