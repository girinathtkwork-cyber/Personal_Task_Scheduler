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


def generate_schedule(tasks, algorithm="EDF", start_time=None):
    """
    Generate a back-to-back schedule for pending tasks.

    Input task shape:
        {
            "id": str,
            "name": str,
            "deadline": datetime,
            "duration_min": int,
            "priority": str,
            "status": str,
            "created_at": datetime,
        }

    Supported algorithms:
        EDF  - earliest deadline first, with priority and created_at tie-breaks
        FCFS - first come first served, using created_at order

    Output shape:
        [{"task_id": str, "task_name": str, "start": datetime, "end": datetime}, ...]
    """
    if start_time is None:
        start_time = datetime.now()

    pending_tasks = [task for task in tasks if _is_pending(task)]
    normalized_algorithm = algorithm.upper()

    if normalized_algorithm == "EDF":
        sorted_tasks = sorted(
            pending_tasks,
            key=lambda task: (
                task["deadline"],
                _priority_rank(task),
                task.get("created_at", datetime.min),
            ),
        )
    elif normalized_algorithm == "FCFS":
        sorted_tasks = sorted(
            pending_tasks,
            key=lambda task: task.get("created_at", datetime.min),
        )
    else:
        raise ValueError("algorithm must be 'EDF' or 'FCFS'")

    timetable = []
    cursor = start_time
    for task in sorted_tasks:
        entry_start = cursor
        entry_end = cursor + timedelta(minutes=task["duration_min"])
        timetable.append({
            "task_id": task["id"],
            "task_name": task["name"],
            "start": entry_start,
            "end": entry_end,
        })
        cursor = entry_end

    return timetable


if __name__ == "__main__":
    today = datetime(2026, 8, 24)

    sample_tasks = [
        {
            "id": "task-1",
            "name": "Finish OS report",
            "deadline": today.replace(hour=18),
            "duration_min": 120,
            "priority": "High",
            "status": "pending",
            "created_at": today.replace(hour=7, minute=30),
        },
        {
            "id": "task-2",
            "name": "Email professor",
            "deadline": today.replace(hour=11),
            "duration_min": 15,
            "priority": "High",
            "status": "pending",
            "created_at": today.replace(hour=7, minute=45),
        },
        {
            "id": "task-3",
            "name": "Gym",
            "deadline": today.replace(hour=9),
            "duration_min": 60,
            "priority": "Medium",
            "status": "pending",
            "created_at": today.replace(hour=8),
        },
        {
            "id": "task-4",
            "name": "Already completed reading",
            "deadline": today.replace(hour=10),
            "duration_min": 30,
            "priority": "Low",
            "status": "done",
            "created_at": today.replace(hour=7),
        },
    ]

    schedule = generate_schedule(sample_tasks, start_time=today.replace(hour=8))

    for entry in schedule:
        start_str = entry["start"].strftime("%H:%M")
        end_str = entry["end"].strftime("%H:%M")
        print(f"{start_str}-{end_str}  {entry['task_name']}")
