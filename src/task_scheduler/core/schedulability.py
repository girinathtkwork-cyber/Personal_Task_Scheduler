from datetime import datetime, timedelta

PRIORITY_RANK = {
    "High": 0,
    "Medium": 1,
    "Low": 2,
}


def _is_pending(task):
    return task.get("status", "pending") == "pending"


def _priority_rank(task):
    return PRIORITY_RANK.get(task.get("priority"), len(PRIORITY_RANK))


def check_schedulability(tasks, now=None):
    """
    Check whether all pending tasks can finish before their deadlines.

    The check follows EDF order because EDF is the primary real-time
    scheduling algorithm for this project.

    Returns:
        {
            "feasible": bool,
            "at_risk_tasks": [task_id],
            "message": str,
        }
    """
    if now is None:
        now = datetime.now()

    pending_tasks = [task for task in tasks if _is_pending(task)]
    sorted_tasks = sorted(
        pending_tasks,
        key=lambda task: (
            task["deadline"],
            _priority_rank(task),
            task.get("created_at", datetime.min),
        ),
    )

    at_risk_ids = []
    at_risk_names = []
    minutes_to_free = 0
    cumulative_time = timedelta()

    for task in sorted_tasks:
        cumulative_time += timedelta(minutes=task["duration_min"])
        finish_time = now + cumulative_time

        if finish_time > task["deadline"]:
            at_risk_ids.append(task["id"])
            at_risk_names.append(task["name"])
            delay_minutes = int((finish_time - task["deadline"]).total_seconds() // 60)
            minutes_to_free = max(minutes_to_free, delay_minutes)

    if not at_risk_ids:
        return {
            "feasible": True,
            "at_risk_tasks": [],
            "message": "All deadlines are achievable.",
        }

    if len(at_risk_names) == 1:
        message = (
            f"You will miss '{at_risk_names[0]}' unless you free up "
            f"about {minutes_to_free} minute(s)."
        )
    else:
        missed_names = ", ".join(at_risk_names)
        message = (
            f"You will miss {len(at_risk_names)} deadline(s): {missed_names}. "
            f"Free up about {minutes_to_free} minute(s) to recover the plan."
        )

    return {
        "feasible": False,
        "at_risk_tasks": at_risk_ids,
        "message": message,
    }


if __name__ == "__main__":
    today = datetime(2026, 8, 24)

    ok_tasks = [
        {
            "id": "task-1",
            "name": "Email professor",
            "deadline": today.replace(hour=11),
            "duration_min": 15,
            "priority": "High",
            "status": "pending",
            "created_at": today.replace(hour=8),
        },
        {
            "id": "task-2",
            "name": "Finish OS report",
            "deadline": today.replace(hour=18),
            "duration_min": 120,
            "priority": "High",
            "status": "pending",
            "created_at": today.replace(hour=8, minute=5),
        },
    ]

    result = check_schedulability(ok_tasks, now=today.replace(hour=9))
    print("Case 1 (should be feasible):")
    print(result)
    print()

    overloaded_tasks = [
        {
            "id": "task-3",
            "name": "Huge report",
            "deadline": today.replace(hour=10),
            "duration_min": 180,
            "priority": "High",
            "status": "pending",
            "created_at": today.replace(hour=8),
        },
        {
            "id": "task-4",
            "name": "Quick email",
            "deadline": today.replace(hour=11),
            "duration_min": 15,
            "priority": "High",
            "status": "pending",
            "created_at": today.replace(hour=8, minute=5),
        },
    ]

    result2 = check_schedulability(overloaded_tasks, now=today.replace(hour=9))
    print("Case 2 (should be infeasible):")
    print(result2)
