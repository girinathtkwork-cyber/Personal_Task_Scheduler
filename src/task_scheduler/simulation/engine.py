"""Discrete-event simulation engine, independent of Tkinter and SQLite."""

from copy import deepcopy
from datetime import datetime, timedelta
import math


POLICIES = {"EDF", "EDF-P", "FCFS", "SJF", "SRTF"}
PREEMPTIVE_POLICIES = {"EDF-P", "SRTF"}
EVENT_PRIORITIES = {
    "cancel": 0,
    "overrun": 1,
    "deadline_change": 1,
    "interrupt": 2,
    "resume": 2,
    "arrival": 3,
}


def _minutes(value, label, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number of minutes.")
    if value < 0 or (value == 0 and not allow_zero):
        qualifier = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{label} must be {qualifier}.")
    return float(value)


class SimulationEngine:
    """Advance a one-CPU workload between meaningful simulated-time events.

    Events at one instant are resolved in this order: task completion, queued
    cancellation/overrun/deadline/state events (stable insertion order within
    each priority), arrivals, deadline misses, then scheduling. The simulation
    advances instantly from the caller's perspective; no wall-clock sleep is
    used.
    """

    def __init__(
        self,
        tasks,
        policy="EDF",
        start_time=None,
        context_switch_overhead_min=0,
        events=None,
    ):
        self.policy = self._validate_policy(policy)
        self.context_switch_overhead_min = _minutes(
            context_switch_overhead_min,
            "Context-switch overhead",
            allow_zero=True,
        )
        self._initial_tasks = deepcopy(list(tasks))
        self.start_time = start_time or self._initial_time(self._initial_tasks)
        if not isinstance(self.start_time, datetime) or self.start_time.tzinfo is not None:
            raise ValueError("Simulation start_time must be a naive datetime.")
        self._configured_events = deepcopy(list(events or []))
        self._reset_state()

    @staticmethod
    def _validate_policy(policy):
        if not isinstance(policy, str):
            raise ValueError(f"policy must be one of: {', '.join(sorted(POLICIES))}.")
        normalized = policy.upper()
        if normalized not in POLICIES:
            raise ValueError(f"policy must be one of: {', '.join(sorted(POLICIES))}.")
        return normalized

    @staticmethod
    def _initial_time(tasks):
        arrivals = [task.get("arrival_time", task.get("created_at")) for task in tasks]
        arrivals = [value for value in arrivals if isinstance(value, datetime)]
        return min(arrivals) if arrivals else datetime.now().replace(second=0, microsecond=0)

    def _normalize_task(self, task):
        task_id = task.get("id")
        name = task.get("name")
        arrival = task.get("arrival_time", task.get("created_at", self.start_time))
        deadline = task.get("deadline")
        execution = task.get("estimated_execution_min", task.get("duration_min"))
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("Simulation task id must be a non-empty string.")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Simulation task name must be a non-empty string.")
        for value, field in ((arrival, "arrival_time"), (deadline, "deadline")):
            if not isinstance(value, datetime) or value.tzinfo is not None:
                raise ValueError(f"Simulation task {field} must be a naive datetime.")
        execution = _minutes(execution, "Estimated execution time")
        priority = task.get("priority", "Medium")
        if priority not in {"High", "Medium", "Low"}:
            raise ValueError("Simulation task priority must be High, Medium, or Low.")
        return {
            "id": task_id,
            "name": name.strip(),
            "arrival_time": arrival,
            "deadline": deadline,
            "estimated_execution_min": execution,
            "remaining_min": execution,
            "priority": priority,
            "state": "NEW",
            "first_start": None,
            "completed_at": None,
            "waiting_min": 0.0,
            "missed": False,
        }

    def _reset_state(self):
        self.current_time = self.start_time
        self.status = "ready"
        self.tasks = {}
        self.event_queue = []
        self.event_log = []
        self.decisions = []
        self.cpu_timeline = []
        self.deadline_misses = []
        self.running_task_id = None
        self.last_task_id = None
        self.switch_target_id = None
        self.switch_complete_at = None
        self.context_switch_count = 0
        self.preemption_count = 0
        self._event_sequence = 0

        for task in self._initial_tasks:
            normalized = self._normalize_task(task)
            if normalized["id"] in self.tasks:
                raise ValueError(f"Duplicate simulation task id: {normalized['id']}")
            self.tasks[normalized["id"]] = normalized
            self._enqueue_event(
                normalized["arrival_time"],
                "arrival",
                task_id=normalized["id"],
            )
        for event in self._configured_events:
            self._queue_event_data(event, remember=False)
        self._process_current_time()
        self._dispatch("initial workload")

    def start(self):
        if self.status == "ready":
            self.status = "running"
            self._process_current_time()
            self._dispatch("simulation started")
        elif self.status == "paused":
            self.resume()
        return self.snapshot()

    def pause(self):
        if self.status == "running":
            self.status = "paused"
        return self.snapshot()

    def resume(self):
        if self.status == "paused":
            self.status = "running"
            self._process_current_time()
            self._dispatch("simulation resumed")
        return self.snapshot()

    def step(self):
        """Advance through one next event, then leave the engine paused."""
        if self.status == "ready":
            self.start()
        if self.status in {"completed", "stopped"}:
            return self.snapshot()
        self.status = "running"
        self._advance_to_next_event()
        if self.status == "running":
            self.status = "paused"
        return self.snapshot()

    def run_until_next_event(self):
        return self.step()

    def run_to_completion(self, max_steps=100000):
        """Run synchronously to a terminal state; suitable for background analysis."""
        if self.status == "ready":
            self.start()
        self.status = "running"
        for _ in range(max_steps):
            if self.status in {"completed", "stopped"}:
                break
            previous_progress = (
                self.current_time,
                len(self.event_queue),
                len(self.event_log),
                len(self.decisions),
                self.running_task_id,
                self.switch_complete_at,
            )
            self._advance_to_next_event()
            current_progress = (
                self.current_time,
                len(self.event_queue),
                len(self.event_log),
                len(self.decisions),
                self.running_task_id,
                self.switch_complete_at,
            )
            if self.status == "running" and current_progress == previous_progress:
                raise RuntimeError("Simulation made no progress; inspect pending events and task states.")
        else:
            raise RuntimeError("Simulation exceeded the maximum event-step limit.")
        return self.snapshot()

    def reset(self):
        self._reset_state()
        return self.snapshot()

    def schedule_event(self, at, kind, **payload):
        """Queue a future external event; it will replay after reset."""
        if not isinstance(at, datetime) or at.tzinfo is not None:
            raise ValueError("Event time must be a naive datetime.")
        if at < self.current_time:
            raise ValueError("Events cannot be scheduled in the simulated past.")
        event = {"at": at, "kind": kind, **payload}
        self._queue_event_data(event, remember=True)
        if at == self.current_time and self.status == "running":
            self._process_current_time()
            self._dispatch(f"{kind} event")
        return self.snapshot()

    def queue_arrival(self, task):
        data = deepcopy(task)
        arrival = data.get("arrival_time", data.get("created_at"))
        if arrival is None:
            arrival = self.current_time
        data["arrival_time"] = arrival
        return self.schedule_event(arrival, "arrival", task_id=data["id"], task=data)

    def _queue_event_data(self, event, remember):
        kind = event.get("kind")
        at = event.get("at")
        if kind not in EVENT_PRIORITIES:
            raise ValueError(f"Unsupported simulation event: {kind!r}.")
        if not isinstance(at, datetime) or at.tzinfo is not None:
            raise ValueError("Event time must be a naive datetime.")
        if at < self.current_time:
            raise ValueError("Events cannot be scheduled in the simulated past.")
        task_id = event.get("task_id")
        if kind != "arrival" and task_id not in self.tasks:
            raise ValueError(f"Unknown simulation task id: {task_id!r}.")
        if kind == "arrival":
            task_data = event.get("task")
            if task_data is None and task_id not in self.tasks:
                raise ValueError("Arrival events require a task payload.")
            if task_data is not None:
                if task_id in self.tasks or any(
                    queued["kind"] == "arrival" and queued.get("task_id") == task_id
                    for queued in self.event_queue
                ):
                    raise ValueError(f"Duplicate simulation task id: {task_id}")
                normalized = self._normalize_task(task_data)
                if normalized["id"] != task_id:
                    raise ValueError("Arrival task id must match the event task_id.")
        if kind == "overrun":
            _minutes(event.get("additional_min"), "Overrun duration")
        if kind == "deadline_change":
            deadline = event.get("deadline")
            if not isinstance(deadline, datetime) or deadline.tzinfo is not None:
                raise ValueError("New deadline must be a naive datetime.")
        self._enqueue_event(at, kind, **{key: value for key, value in event.items() if key not in {"at", "kind"}})
        if remember:
            self._configured_events.append(deepcopy(event))

    def _enqueue_event(self, at, kind, **payload):
        self._event_sequence += 1
        self.event_queue.append({
            "at": at,
            "kind": kind,
            "sequence": self._event_sequence,
            **payload,
        })
        self.event_queue.sort(
            key=lambda event: (
                event["at"],
                EVENT_PRIORITIES[event["kind"]],
                event["sequence"],
            )
        )

    def _next_boundary(self):
        boundaries = [event["at"] for event in self.event_queue if event["at"] >= self.current_time]
        if self.running_task_id:
            task = self.tasks[self.running_task_id]
            boundaries.append(self.current_time + timedelta(minutes=task["remaining_min"]))
        if self.switch_complete_at:
            boundaries.append(self.switch_complete_at)
        for task in self.tasks.values():
            if task["state"] not in {"COMPLETED", "CANCELLED"} and not task["missed"]:
                if task["deadline"] >= self.current_time:
                    boundaries.append(task["deadline"])
        return min(boundaries) if boundaries else None

    def _advance_to_next_event(self):
        boundary = self._next_boundary()
        if boundary is None:
            self.status = "completed" if self._all_terminal() else "stopped"
            return
        if boundary < self.current_time:
            raise RuntimeError("Simulation event queue contains a past event.")
        elapsed = (boundary - self.current_time).total_seconds() / 60
        trigger_kinds = []
        for task in self.tasks.values():
            if task["state"] == "READY":
                task["waiting_min"] += elapsed
        if self.running_task_id and elapsed:
            task = self.tasks[self.running_task_id]
            task["remaining_min"] = max(0.0, task["remaining_min"] - elapsed)
            self._append_interval(self.current_time, boundary, "execution", self.running_task_id)
        elif self.switch_complete_at and elapsed:
            self._append_interval(self.current_time, boundary, "context_switch", None)
        else:
            self._append_interval(self.current_time, boundary, "idle", None)
        self.current_time = boundary
        if self.running_task_id and self.tasks[self.running_task_id]["remaining_min"] <= 1e-9:
            self._complete_task(self.running_task_id)
            trigger_kinds.append("completion")
        if self.switch_complete_at and self.current_time >= self.switch_complete_at:
            self.switch_complete_at = None
            self.running_task_id = self.switch_target_id
            self.switch_target_id = None
            if self.running_task_id:
                self._start_task(self.tasks[self.running_task_id])
                trigger_kinds.append("context switch completed")
        trigger_kinds.extend(self._process_current_time())
        self._dispatch(", ".join(trigger_kinds) if trigger_kinds else "time boundary")
        if self._all_terminal():
            self.status = "completed"

    def _append_interval(self, start, end, kind, task_id):
        if end <= start:
            return
        minutes = (end - start).total_seconds() / 60
        if (
            self.cpu_timeline
            and self.cpu_timeline[-1]["kind"] == kind
            and self.cpu_timeline[-1]["task_id"] == task_id
            and self.cpu_timeline[-1]["end"] == start
        ):
            self.cpu_timeline[-1]["end"] = end
            self.cpu_timeline[-1]["duration_min"] += minutes
        else:
            self.cpu_timeline.append({
                "start": start,
                "end": end,
                "kind": kind,
                "task_id": task_id,
                "duration_min": minutes,
            })

    def _process_current_time(self):
        due = []
        future = []
        for event in self.event_queue:
            (due if event["at"] <= self.current_time else future).append(event)
        self.event_queue = future
        processed = []
        for event in due:
            if event["kind"] == "arrival":
                continue
            self._apply_event(event)
            processed.append(event["kind"])
        for event in due:
            if event["kind"] == "arrival":
                self._apply_event(event)
                processed.append(event["kind"])
        for task in self.tasks.values():
            if (
                task["state"] not in {"COMPLETED", "CANCELLED"}
                and not task["missed"]
                and task["deadline"] <= self.current_time
            ):
                task["missed"] = True
                self.deadline_misses.append({
                    "task_id": task["id"],
                    "task_name": task["name"],
                    "deadline": task["deadline"],
                    "detected_at": self.current_time,
                })
                self.event_log.append({
                    "at": self.current_time,
                    "kind": "deadline_miss",
                    "task_id": task["id"],
                    "message": f"{task['name']} passed its deadline before completion.",
                })
                processed.append("deadline_miss")
        return processed

    def _apply_event(self, event):
        kind = event["kind"]
        task_id = event.get("task_id")
        if kind == "arrival":
            if task_id in self.tasks:
                task = self.tasks[task_id]
            else:
                task = self._normalize_task(event["task"])
                self.tasks[task_id] = task
            if task["state"] in {"COMPLETED", "CANCELLED"}:
                return
            if task["state"] == "NEW":
                task["state"] = "READY"
            message = f"{task['name']} arrived and became ready."
        else:
            task = self.tasks[task_id]
            if task["state"] in {"COMPLETED", "CANCELLED"}:
                return
            if kind == "overrun":
                additional = float(event["additional_min"])
                task["remaining_min"] += additional
                task["estimated_execution_min"] += additional
                message = f"{task['name']} overran by {additional:g} minute(s)."
            elif kind == "cancel":
                if self.running_task_id == task_id:
                    self.last_task_id = task_id
                    self.running_task_id = None
                if self.switch_target_id == task_id:
                    self.switch_target_id = None
                    self.switch_complete_at = None
                task["state"] = "CANCELLED"
                message = f"{task['name']} was cancelled."
            elif kind == "deadline_change":
                task["deadline"] = event["deadline"]
                message = f"{task['name']}'s deadline changed to {task['deadline']}."
            elif kind == "interrupt":
                if task["state"] == "RUNNING":
                    self.running_task_id = None
                    self.last_task_id = task_id
                task["state"] = "INTERRUPTED"
                message = f"{task['name']} was interrupted."
            elif kind == "resume":
                if task["state"] == "INTERRUPTED":
                    task["state"] = "READY"
                message = f"{task['name']} was resumed."
            else:
                raise ValueError(f"Unsupported simulation event: {kind!r}.")
        self.event_log.append({
            "at": self.current_time,
            "kind": kind,
            "task_id": task_id,
            "message": message,
        })

    def _eligible(self):
        return [task for task in self.tasks.values() if task["state"] == "READY"]

    def _sort_key(self, task):
        if self.policy in {"EDF", "EDF-P"}:
            return (task["deadline"], {"High": 0, "Medium": 1, "Low": 2}[task["priority"]], task["arrival_time"], task["id"])
        if self.policy == "FCFS":
            return (task["arrival_time"], task["id"])
        if self.policy == "SJF":
            return (task["estimated_execution_min"], task["arrival_time"], task["id"])
        return (task["remaining_min"], task["arrival_time"], task["id"])

    def _dispatch(self, trigger):
        if self.status in {"completed", "stopped"}:
            return
        if self.switch_complete_at:
            eligible = sorted(self._eligible(), key=self._sort_key)
            candidate = eligible[0] if eligible else None
            previous_target = self.switch_target_id
            self.switch_target_id = candidate["id"] if candidate else None
            if candidate and candidate["id"] != previous_target:
                decision = {
                    "at": self.current_time,
                    "policy": self.policy,
                    "selected_task_id": candidate["id"],
                    "eligible_tasks": [
                        {
                            "task_id": item["id"],
                            "deadline": item["deadline"],
                            "remaining_min": item["remaining_min"],
                        }
                        for item in eligible
                    ],
                    "criterion": {
                        "EDF": "earliest absolute deadline, then priority and arrival",
                        "EDF-P": "earliest absolute deadline, then priority and arrival",
                        "FCFS": "earliest arrival time",
                        "SJF": "shortest original execution estimate",
                        "SRTF": "shortest remaining execution time",
                    }[self.policy],
                    "trigger": trigger,
                    "preempted_task_id": None,
                }
                decision["explanation"] = self._explain_decision(decision, candidate)
                self.decisions.append(decision)
            return
        current = self.tasks.get(self.running_task_id) if self.running_task_id else None
        if current and self.policy not in PREEMPTIVE_POLICIES:
            return
        eligible = self._eligible()
        if current:
            eligible.append(current)
        eligible.sort(key=self._sort_key)
        candidate = eligible[0] if eligible else None
        if current and (candidate is None or current["id"] == candidate["id"]):
            return
        if current:
            current["state"] = "READY"
            self.last_task_id = current["id"]
            self.running_task_id = None
            self.preemption_count += 1
        if not candidate:
            return
        task = candidate
        eligible_data = [
            {
                "task_id": item["id"],
                "deadline": item["deadline"],
                "remaining_min": item["remaining_min"],
            }
            for item in eligible
        ]
        selected_previous = current["id"] if current else None
        criterion = {
            "EDF": "earliest absolute deadline, then priority and arrival",
            "EDF-P": "earliest absolute deadline, then priority and arrival",
            "FCFS": "earliest arrival time",
            "SJF": "shortest original execution estimate",
            "SRTF": "shortest remaining execution time",
        }[self.policy]
        decision = {
            "at": self.current_time,
            "policy": self.policy,
            "selected_task_id": task["id"],
            "eligible_tasks": eligible_data,
            "criterion": criterion,
            "trigger": trigger,
            "preempted_task_id": selected_previous if current and selected_previous != task["id"] else None,
        }
        decision["explanation"] = self._explain_decision(decision, task)
        self.decisions.append(decision)
        task["state"] = "READY"
        if (
            self.context_switch_overhead_min > 0
            and self.last_task_id is not None
            and self.last_task_id != task["id"]
        ):
            self.context_switch_count += 1
            self.switch_target_id = task["id"]
            self.switch_complete_at = self.current_time + timedelta(minutes=self.context_switch_overhead_min)
            return
        self.running_task_id = task["id"]
        self._start_task(task)

    def _start_task(self, task):
        if task["first_start"] is None:
            task["first_start"] = self.current_time
        task["state"] = "RUNNING"

    def _complete_task(self, task_id):
        task = self.tasks[task_id]
        task["remaining_min"] = 0.0
        task["state"] = "COMPLETED"
        task["completed_at"] = self.current_time
        self.last_task_id = task_id
        self.running_task_id = None
        self.event_log.append({
            "at": self.current_time,
            "kind": "completion",
            "task_id": task_id,
            "message": f"{task['name']} completed.",
        })

    def _explain_decision(self, decision, task):
        if decision["preempted_task_id"]:
            previous = self.tasks[decision["preempted_task_id"]]["name"]
            return (
                f"{task['name']} was selected by {decision['policy']} "
                f"({decision['criterion']}); {previous} was preempted."
            )
        if self.policy in {"EDF", "EDF-P"}:
            return f"{task['name']} was selected because it had the earliest deadline among ready tasks."
        if self.policy == "FCFS":
            return f"{task['name']} was selected because it arrived before the other ready tasks."
        if self.policy == "SJF":
            return f"{task['name']} was selected because it had the shortest estimated execution time."
        return f"{task['name']} was selected because it had the least remaining execution time."

    def _all_terminal(self):
        return all(task["state"] in {"COMPLETED", "CANCELLED"} for task in self.tasks.values()) and not self.event_queue

    def forecast(self):
        """Return a policy-consistent projection from the current state."""
        projected = deepcopy(self)
        projected.status = "running"
        projected.run_to_completion()
        remaining = [
            task for task in projected.tasks.values()
            if task["state"] not in {"COMPLETED", "CANCELLED"}
        ]
        missed = [task for task in projected.tasks.values() if task["missed"] and task["state"] != "CANCELLED"]
        individually_impossible = [
            task["id"]
            for task in remaining
            if max(projected.current_time, task["arrival_time"])
            + timedelta(minutes=task["remaining_min"])
            > task["deadline"]
        ]
        return {
            "feasible": not missed,
            "at_risk_tasks": [task["id"] for task in missed],
            "individually_impossible": individually_impossible,
            "deadline_misses": len(missed),
            "workload_infeasible": bool(missed) and not individually_impossible,
            "explanation": self._forecast_explanation(missed, individually_impossible),
        }

    def remaining_workload_forecast(self):
        """Public alias clarifying that feasibility is a policy projection."""
        return self.forecast()

    @staticmethod
    def _forecast_explanation(missed, individually_impossible):
        if not missed:
            return "The current-policy projection meets all remaining deadlines."
        if individually_impossible:
            names = ", ".join(task["name"] for task in missed if task["id"] in individually_impossible)
            return f"At least one task cannot finish individually before its deadline: {names}."
        return (
            f"The selected-policy projection predicts {len(missed)} deadline miss(es)."
        )

    def scenario_inputs(self):
        """Return independent input data suitable for deterministic replay."""
        return {
            "tasks": deepcopy(self._initial_tasks),
            "events": deepcopy(self._configured_events),
            "policy": self.policy,
            "start_time": self.start_time,
            "context_switch_overhead_min": self.context_switch_overhead_min,
        }

    def metrics(self):
        completed = [task for task in self.tasks.values() if task["state"] == "COMPLETED"]
        non_cancelled = [task for task in self.tasks.values() if task["state"] != "CANCELLED"]
        elapsed = max(0.0, (self.current_time - self.start_time).total_seconds() / 60)
        execution = sum(entry["duration_min"] for entry in self.cpu_timeline if entry["kind"] == "execution")
        switching = sum(entry["duration_min"] for entry in self.cpu_timeline if entry["kind"] == "context_switch")
        idle = sum(entry["duration_min"] for entry in self.cpu_timeline if entry["kind"] == "idle")
        lateness = [
            (task["completed_at"] - task["deadline"]).total_seconds() / 60
            for task in completed
        ]
        waiting = [task["waiting_min"] for task in completed]
        turnaround = [
            (task["completed_at"] - task["arrival_time"]).total_seconds() / 60
            for task in completed
        ]
        response = [
            (task["first_start"] - task["arrival_time"]).total_seconds() / 60
            for task in completed
            if task["first_start"] is not None
        ]
        return {
            "tasks_total": len(non_cancelled),
            "tasks_completed": len(completed),
            "deadline_misses": sum(
                task["missed"] and task["state"] != "CANCELLED"
                for task in self.tasks.values()
            ),
            "deadline_miss_rate": (
                sum(
                    task["missed"] and task["state"] != "CANCELLED"
                    for task in self.tasks.values()
                ) / len(non_cancelled)
                if non_cancelled
                else 0.0
            ),
            "total_tardiness_min": sum(max(0.0, value) for value in lateness),
            "maximum_lateness_min": max(lateness, default=0.0),
            "average_waiting_min": sum(waiting) / len(waiting) if waiting else 0.0,
            "average_turnaround_min": sum(turnaround) / len(turnaround) if turnaround else 0.0,
            "average_response_min": sum(response) / len(response) if response else 0.0,
            "cpu_utilization": execution / elapsed if elapsed else 0.0,
            "cpu_execution_min": execution,
            "cpu_idle_min": idle,
            "context_switch_min": switching,
            "context_switch_count": self.context_switch_count,
            "preemption_count": self.preemption_count,
        }

    def snapshot(self):
        return {
            "current_time": self.current_time,
            "status": self.status,
            "policy": self.policy,
            "running_task_id": self.running_task_id,
            "cpu_state": "switching" if self.switch_complete_at else ("running" if self.running_task_id else "idle"),
            "tasks": deepcopy(list(self.tasks.values())),
            "pending_events": deepcopy(self.event_queue),
            "events": deepcopy(self.event_log),
            "decisions": deepcopy(self.decisions),
            "cpu_timeline": deepcopy(self.cpu_timeline),
            "deadline_misses": deepcopy(self.deadline_misses),
            "metrics": self.metrics(),
        }
