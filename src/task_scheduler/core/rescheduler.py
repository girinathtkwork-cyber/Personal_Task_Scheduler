from datetime import datetime

from task_scheduler.core.scheduler import count_deadline_misses, generate_schedule
from task_scheduler.core.schedulability import check_schedulability
from task_scheduler.persistence import db


def build_schedule_state(conn, algorithm="EDF", start_time=None, now=None):
    """
    Reload tasks from storage and return the current scheduling state.

    Frontend code can call this after any task change to redraw the timeline.
    Only pending tasks are scheduled; in-progress and done tasks stay in the
    task list but are not rearranged.
    """
    normalized_algorithm = algorithm.upper()
    if normalized_algorithm not in {"EDF", "FCFS"}:
        raise ValueError("algorithm must be 'EDF' or 'FCFS'")

    all_tasks = db.get_all_tasks(conn)
    pending_tasks = [task for task in all_tasks if task.get("status", "pending") == "pending"]
    schedules = {
        current_algorithm: generate_schedule(
            pending_tasks,
            algorithm=current_algorithm,
            start_time=start_time,
        )
        for current_algorithm in ("EDF", "FCFS")
    }
    outcomes = {}
    for current_algorithm, current_schedule in schedules.items():
        outcome = {
            "algorithm": current_algorithm,
            "tasks_scheduled": len(current_schedule),
            "deadlines_missed": count_deadline_misses(pending_tasks, current_schedule),
        }
        outcomes[current_algorithm] = outcome
        db.log_history(
            conn,
            now or start_time or datetime.now(),
            current_algorithm,
            outcome["tasks_scheduled"],
            outcome["deadlines_missed"],
        )

    return {
        "tasks": all_tasks,
        "pending_tasks": pending_tasks,
        "schedule": schedules[normalized_algorithm],
        "schedulability": check_schedulability(pending_tasks, now=now),
        "comparison": outcomes,
    }


def add_task_and_reschedule(conn, task, algorithm="EDF", start_time=None, now=None):
    db.add_task(conn, task, reference_time=now)
    return build_schedule_state(conn, algorithm=algorithm, start_time=start_time, now=now)


def edit_task_and_reschedule(conn, task_id, changes, algorithm="EDF", start_time=None, now=None):
    db.update_task(conn, task_id, changes)
    return build_schedule_state(conn, algorithm=algorithm, start_time=start_time, now=now)


def update_status_and_reschedule(conn, task_id, status, algorithm="EDF", start_time=None, now=None):
    db.update_task_status(conn, task_id, status)
    return build_schedule_state(conn, algorithm=algorithm, start_time=start_time, now=now)


def mark_done_and_reschedule(conn, task_id, algorithm="EDF", start_time=None, now=None):
    return update_status_and_reschedule(
        conn,
        task_id,
        "done",
        algorithm=algorithm,
        start_time=start_time,
        now=now,
    )


def delete_task_and_reschedule(conn, task_id, algorithm="EDF", start_time=None, now=None):
    db.delete_task(conn, task_id)
    return build_schedule_state(conn, algorithm=algorithm, start_time=start_time, now=now)
