"""Isolated, reproducible policy comparisons for simulation workloads."""

from copy import deepcopy
from datetime import datetime, timedelta
import uuid

from task_scheduler.simulation.engine import POLICIES, SimulationEngine


def run_counterfactual(
    tasks,
    policies=("EDF", "EDF-P", "FCFS", "SJF", "SRTF"),
    start_time=None,
    events=None,
    context_switch_overhead_min=0,
):
    """Run independent engines over an identical workload and event sequence."""
    normalized_policies = []
    for policy in policies:
        normalized = SimulationEngine._validate_policy(policy)
        if normalized not in normalized_policies:
            normalized_policies.append(normalized)
    if not normalized_policies:
        raise ValueError("At least one policy is required for an experiment.")

    task_inputs = deepcopy(list(tasks))
    event_inputs = deepcopy(list(events or []))
    if start_time is None:
        start_time = SimulationEngine._initial_time(task_inputs)
    runs = {}
    for policy in normalized_policies:
        engine = SimulationEngine(
            deepcopy(task_inputs),
            policy=policy,
            start_time=start_time,
            context_switch_overhead_min=context_switch_overhead_min,
            events=deepcopy(event_inputs),
        )
        snapshot = engine.run_to_completion()
        runs[policy] = {
            "policy": policy,
            "status": snapshot["status"],
            "metrics": snapshot["metrics"],
            "tasks": snapshot["tasks"],
            "decisions": snapshot["decisions"],
            "events": snapshot["events"],
            "cpu_timeline": snapshot["cpu_timeline"],
            "deadline_misses": snapshot["deadline_misses"],
        }
    baseline_policy = normalized_policies[0]
    baseline_misses = runs[baseline_policy]["metrics"]["deadline_misses"]
    def execution_order(timeline):
        order = []
        for interval in timeline:
            task_id = interval["task_id"]
            if interval["kind"] == "execution" and (not order or order[-1] != task_id):
                order.append(task_id)
        return order

    comparisons = {
        policy: {
            "deadline_misses_delta": result["metrics"]["deadline_misses"] - baseline_misses,
            "completed_delta": result["metrics"]["tasks_completed"]
            - runs[baseline_policy]["metrics"]["tasks_completed"],
            "execution_order": execution_order(result["cpu_timeline"]),
            "verified_prevented_misses": max(0, baseline_misses - result["metrics"]["deadline_misses"]),
        }
        for policy, result in runs.items()
    }
    return {
        "id": str(uuid.uuid4()),
        "created_at": datetime.now().replace(microsecond=0),
        "start_time": start_time,
        "context_switch_overhead_min": float(context_switch_overhead_min),
        "workload": task_inputs,
        "events_input": event_inputs,
        "baseline_policy": baseline_policy,
        "runs": runs,
        "comparisons": comparisons,
    }


def create_overrun_demo(start_time=None):
    """Create a deterministic workload that becomes infeasible after an overrun."""
    start = start_time or datetime.now().replace(second=0, microsecond=0)
    tasks = [
        {
            "id": "demo-report",
            "name": "Short report",
            "arrival_time": start,
            "deadline": start + timedelta(minutes=25),
            "estimated_execution_min": 10,
            "priority": "High",
        },
        {
            "id": "demo-email",
            "name": "Reply to email",
            "arrival_time": start,
            "deadline": start + timedelta(minutes=45),
            "estimated_execution_min": 15,
            "priority": "Medium",
        },
    ]
    events = [{
        "at": start + timedelta(minutes=5),
        "kind": "overrun",
        "task_id": "demo-report",
        "additional_min": 20,
    }]
    return {"start_time": start, "tasks": tasks, "events": events}


def supported_policies():
    return tuple(sorted(POLICIES))
