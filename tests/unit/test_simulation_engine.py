import unittest
from datetime import datetime, timedelta

from task_scheduler.simulation.engine import SimulationEngine


class SimulationEngineTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2030, 1, 1, 9, 0)

    def task(self, task_id, deadline_min, execution_min, arrival_min=0):
        return {
            "id": task_id,
            "name": task_id.upper(),
            "arrival_time": self.start + timedelta(minutes=arrival_min),
            "deadline": self.start + timedelta(minutes=deadline_min),
            "estimated_execution_min": execution_min,
            "priority": "Medium",
        }

    def test_completion_and_metrics_are_deterministic(self):
        tasks = [self.task("a", 20, 5), self.task("b", 30, 10, 2)]
        results = []
        for _ in range(2):
            engine = SimulationEngine(tasks, policy="EDF", start_time=self.start)
            results.append(engine.run_to_completion())

        self.assertEqual(results[0]["cpu_timeline"], results[1]["cpu_timeline"])
        self.assertEqual(results[0]["decisions"], results[1]["decisions"])
        self.assertEqual(results[0]["metrics"]["tasks_completed"], 2)
        self.assertEqual(results[0]["metrics"]["deadline_misses"], 0)

    def test_step_pause_and_resume_advance_without_wall_clock_waiting(self):
        engine = SimulationEngine([self.task("a", 30, 5)], start_time=self.start)

        first = engine.step()
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["current_time"], self.start + timedelta(minutes=5))
        self.assertEqual(first["tasks"][0]["state"], "COMPLETED")

        engine.reset()
        engine.start()
        paused = engine.pause()
        self.assertEqual(paused["status"], "paused")
        resumed = engine.resume()
        self.assertEqual(resumed["status"], "running")
        self.assertEqual(engine.run_to_completion()["status"], "completed")

    def test_preemptive_edf_preempts_nonpreemptive_task(self):
        tasks = [self.task("long", 60, 40), self.task("urgent", 15, 5, 10)]
        engine = SimulationEngine(tasks, policy="EDF-P", start_time=self.start)

        state = engine.run_to_completion()

        self.assertEqual(state["metrics"]["preemption_count"], 1)
        self.assertEqual(state["tasks"][0]["state"], "COMPLETED")
        self.assertEqual(state["tasks"][1]["state"], "COMPLETED")
        self.assertEqual(state["cpu_timeline"][1]["task_id"], "urgent")
        self.assertEqual(state["cpu_timeline"][1]["start"], self.start + timedelta(minutes=10))
        self.assertIn("preempted", state["decisions"][1]["explanation"])
        self.assertIn("arrival", state["decisions"][1]["trigger"])

    def test_nonpreemptive_fcfs_does_not_preempt_for_later_arrival(self):
        tasks = [self.task("long", 60, 40), self.task("urgent", 15, 5, 10)]
        state = SimulationEngine(tasks, policy="FCFS", start_time=self.start).run_to_completion()

        self.assertEqual(state["metrics"]["preemption_count"], 0)
        self.assertEqual(state["cpu_timeline"][0]["task_id"], "long")
        self.assertGreater(state["metrics"]["deadline_misses"], 0)

    def test_overrun_changes_a_feasible_projection_to_a_miss(self):
        tasks = [self.task("first", 20, 10), self.task("second", 30, 10)]
        engine = SimulationEngine(tasks, policy="EDF", start_time=self.start)
        self.assertTrue(engine.remaining_workload_forecast()["feasible"])
        engine.schedule_event(
            self.start + timedelta(minutes=5),
            "overrun",
            task_id="first",
            additional_min=15,
        )

        state = engine.run_to_completion()

        self.assertEqual(state["metrics"]["deadline_misses"], 2)
        self.assertEqual(state["tasks"][0]["estimated_execution_min"], 25)

    def test_forecast_distinguishes_individual_from_combined_infeasibility(self):
        tasks = [self.task("a", 8, 5), self.task("b", 8, 5)]
        state = SimulationEngine(tasks, start_time=self.start).remaining_workload_forecast()

        self.assertFalse(state["feasible"])
        self.assertTrue(state["workload_infeasible"])
        self.assertEqual(state["individually_impossible"], [])
        self.assertEqual(state["deadline_misses"], 1)

    def test_same_time_event_order_is_stable_and_completion_precedes_cancel(self):
        tasks = [self.task("a", 10, 5)]
        engine = SimulationEngine(tasks, start_time=self.start)
        event_time = self.start + timedelta(minutes=5)
        engine.schedule_event(event_time, "cancel", task_id="a")
        state = engine.run_to_completion()

        self.assertEqual(state["tasks"][0]["state"], "COMPLETED")
        self.assertEqual(
            [event["kind"] for event in state["events"] if event["at"] == event_time],
            ["completion"],
        )

    def test_cancel_deadline_change_interrupt_and_resume_events(self):
        tasks = [self.task("a", 20, 10), self.task("b", 40, 8)]
        engine = SimulationEngine(tasks, start_time=self.start)
        engine.schedule_event(self.start + timedelta(minutes=2), "interrupt", task_id="a")
        engine.schedule_event(self.start + timedelta(minutes=4), "resume", task_id="a")
        engine.schedule_event(
            self.start + timedelta(minutes=5),
            "deadline_change",
            task_id="b",
            deadline=self.start + timedelta(minutes=50),
        )
        engine.schedule_event(self.start + timedelta(minutes=6), "cancel", task_id="b")

        state = engine.run_to_completion()

        self.assertEqual(state["tasks"][0]["state"], "COMPLETED")
        self.assertEqual(state["tasks"][1]["state"], "CANCELLED")
        self.assertEqual(state["tasks"][1]["deadline"], self.start + timedelta(minutes=50))

    def test_context_switch_overhead_is_not_useful_execution(self):
        tasks = [self.task("a", 30, 2), self.task("b", 30, 2)]
        state = SimulationEngine(
            tasks,
            policy="FCFS",
            start_time=self.start,
            context_switch_overhead_min=1,
        ).run_to_completion()

        self.assertEqual(state["metrics"]["context_switch_count"], 1)
        self.assertEqual(state["metrics"]["context_switch_min"], 1)
        self.assertEqual(state["metrics"]["cpu_execution_min"], 4)
        self.assertEqual(state["cpu_timeline"][1]["kind"], "context_switch")

    def test_reset_replays_configured_events_without_sharing_task_state(self):
        engine = SimulationEngine([self.task("a", 30, 5)], start_time=self.start)
        engine.schedule_event(
            self.start + timedelta(minutes=1),
            "overrun",
            task_id="a",
            additional_min=2,
        )
        first = engine.run_to_completion()
        engine.reset()
        second = engine.run_to_completion()

        self.assertEqual(first["cpu_timeline"], second["cpu_timeline"])
        self.assertEqual(second["tasks"][0]["estimated_execution_min"], 7)
        self.assertEqual(second["tasks"][0]["remaining_min"], 0)

    def test_policy_and_duration_validation(self):
        with self.assertRaises(ValueError):
            SimulationEngine([self.task("a", 30, 5)], policy="RMS", start_time=self.start)
        with self.assertRaises(ValueError):
            SimulationEngine([self.task("a", 30, 0)], start_time=self.start)

    def test_future_arrival_and_interruption_without_resume_stops_cleanly(self):
        engine = SimulationEngine(
            [self.task("first", 10, 2)],
            start_time=self.start,
        )
        engine.queue_arrival(self.task("later", 30, 3, arrival_min=5))
        engine.schedule_event(
            self.start + timedelta(minutes=1),
            "interrupt",
            task_id="first",
        )

        state = engine.run_to_completion()

        states = {task["id"]: task["state"] for task in state["tasks"]}
        self.assertEqual(states["first"], "INTERRUPTED")
        self.assertEqual(states["later"], "COMPLETED")
        self.assertEqual(state["status"], "stopped")


if __name__ == "__main__":
    unittest.main()
