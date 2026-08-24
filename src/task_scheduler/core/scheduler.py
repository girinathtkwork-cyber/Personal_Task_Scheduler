# task-scheduler/src/task_scheduler/core/scheduler.py

from datetime import datetime, timedelta


def generate_schedule(tasks, start_time=None):
    """
    Takes a list of task dictionaries.
    Returns a timetable: each task gets a start time and end time,
    placed back-to-back, ordered by earliest deadline first (EDF).

    Input task shape:
        {"name": str, "deadline": datetime, "duration_min": int, "priority": str}

    Output shape (this is what your teammate will build the GUI against):
        [{"task_name": str, "start": datetime, "end": datetime}, ...]
    """
    if start_time is None:
        start_time = datetime.now()

    # Step 1: sort by deadline (earliest first) — this is the EDF part
    sorted_tasks = sorted(tasks, key=lambda t: t["deadline"])

    # Step 2: place each task back-to-back on the timeline
    timetable = []
    cursor = start_time
    for task in sorted_tasks:
        entry_start = cursor
        entry_end = cursor + timedelta(minutes=task["duration_min"])
        timetable.append({
            "task_name": task["name"],
            "start": entry_start,
            "end": entry_end,
        })
        cursor = entry_end  # next task starts right after this one ends

    return timetable


if __name__ == "__main__":
    today = datetime(2026, 8, 24)  # fixed date so output is predictable while testing

    sample_tasks = [
        {"name": "Finish OS report", "deadline": today.replace(hour=18), "duration_min": 120, "priority": "High"},
        {"name": "Email professor", "deadline": today.replace(hour=11), "duration_min": 15, "priority": "High"},
        {"name": "Gym", "deadline": today.replace(hour=9), "duration_min": 60, "priority": "Medium"},
    ]

    # schedule starting from 8 AM
    schedule = generate_schedule(sample_tasks, start_time=today.replace(hour=8))

    for entry in schedule:
        start_str = entry["start"].strftime("%H:%M")
        end_str = entry["end"].strftime("%H:%M")
        print(f"{start_str}-{end_str}  {entry['task_name']}")