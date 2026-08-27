# walk through tasks => total time required, alert if task is at risk of being missed

# task-scheduler/src/task_scheduler/core/schedulability.py

from datetime import datetime, timedelta


def check_schedulability(tasks, now=None):
    """
    Checks whether all tasks' deadlines are actually achievable,
    given how much total time they need.

    Input: same task shape as scheduler.py
        {"name": str, "deadline": datetime, "duration_min": int, "priority": str}

    Output:
        {
            "feasible": bool,          # True if every deadline is achievable
            "at_risk_tasks": [str],     # names of tasks that will be missed
            "message": str               # human-readable summary
        }
    """
    if now is None:
        now = datetime.now()

    # sort by deadline, same as scheduler.py — earliest first
    sorted_tasks = sorted(tasks, key=lambda t: t["deadline"])

    at_risk = []
    cumulative_time = timedelta()

    for task in sorted_tasks:
        cumulative_time += timedelta(minutes=task["duration_min"])
        finish_time = now + cumulative_time

        if finish_time > task["deadline"]:
            at_risk.append(task["name"])

    if not at_risk:
        return {
            "feasible": True,
            "at_risk_tasks": [],
            "message": "All deadlines are achievable."
        }

    return {
        "feasible": False,
        "at_risk_tasks": at_risk,
        "message": f"You will miss {len(at_risk)} deadline(s): {', '.join(at_risk)}"
    }


if __name__ == "__main__":
    today = datetime(2026, 8, 24)

    # Case 1: a normal, achievable day
    ok_tasks = [
        {"name": "Email professor", "deadline": today.replace(hour=11), "duration_min": 15, "priority": "High"},
        {"name": "Finish OS report", "deadline": today.replace(hour=18), "duration_min": 120, "priority": "High"},
    ]

    result = check_schedulability(ok_tasks, now=today.replace(hour=9))
    print("Case 1 (should be feasible):")
    print(result)
    print()

    # Case 2: an overloaded day — too much work, too little time
    overloaded_tasks = [
        {"name": "Huge report", "deadline": today.replace(hour=10), "duration_min": 180, "priority": "High"},
        {"name": "Quick email", "deadline": today.replace(hour=11), "duration_min": 15, "priority": "High"},
    ]

    result2 = check_schedulability(overloaded_tasks, now=today.replace(hour=9))
    print("Case 2 (should be infeasible):")
    print(result2)