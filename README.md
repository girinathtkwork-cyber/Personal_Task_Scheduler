# TaskEDF - Backend Module Documentation

TaskEDF is a personal task scheduler built around real-time operating system scheduling ideas. Instead of keeping tasks in a simple to-do list order, the backend schedules pending work using EDF, or Earliest Deadline First, then checks whether the planned work can actually finish before each deadline.

This README documents the completed backend work for Modules 1, 2, and 3, explains how the files were built, and records what is still left for later modules.

## Current Module Status

Last checked: 2026-09-12

| Module | Backend Status | Notes |
| --- | --- | --- |
| Module 1 - Core Scheduling Pipeline | Complete | `generate_schedule()` supports EDF, pending-only scheduling, priority tie-breaks, timetable output, and a standalone console demo. |
| Module 2 - Task Input + Persistence | Complete | SQLite persistence, task CRUD, backend validation, schedulability checking, and backend unit tests are implemented. |
| Module 3 - Gantt Timeline + Dynamic Reschedule | Complete for backend | Backend reschedule helpers exist for add, edit, delete, status update, and mark-done flows. The frontend can call one helper after each user action and redraw from the returned state. |
| Module 4 - EDF vs FCFS Comparison | Complete for backend | FCFS scheduling, deadline-miss metrics, SQLite history logging, and additive comparison results from the rescheduler are implemented and tested. |
| Module 5 - Polish and Edge Cases | Complete for backend | Backend validation rejects invalid values, past deadlines, and timezone-aware datetimes; edge cases and the SQLite workflow are covered by tests. GUI polish remains frontend work. |

## Project Structure

```text
task-scheduler/
|-- MODULE_PLAN_Frontend_Backend.md
|-- PROJECT_CONTEXT_AND_BUILD_SPEC.md
|-- README.md
|-- data/
|   |-- tasks.db
|-- src/
|   |-- task_scheduler/
|       |-- __init__.py
|       |-- core/
|       |   |-- __init__.py
|       |   |-- rescheduler.py
|       |   |-- scheduler.py
|       |   |-- schedulability.py
|       |-- gui/
|       |   |-- __init__.py
|       |   |-- app.py
|       |   |-- task_form.py
|       |-- persistence/
|           |-- __init__.py
|           |-- db.py
|-- tests/
    |-- unit/
        |-- test_db.py
        |-- test_rescheduler.py
        |-- test_schedulability.py
        |-- test_scheduler.py
```

## Module 1 - Core Scheduling Pipeline

Module 1 builds the pure backend scheduling function. This is the main OS-theory part of the project because it applies EDF scheduling to personal tasks.

### File: `src/task_scheduler/core/scheduler.py`

This file contains:

- `generate_schedule(tasks, algorithm="EDF", start_time=None)`
- EDF sorting logic
- FCFS sorting support for future Module 4 comparison
- pending-task filtering
- timetable generation
- a direct console demo under `if __name__ == "__main__"`

### Task Input Shape

Each task is represented as a Python dictionary:

```python
{
    "id": "task-1",
    "name": "Finish OS report",
    "deadline": datetime(2026, 8, 24, 18, 0),
    "duration_min": 120,
    "priority": "High",
    "status": "pending",
    "created_at": datetime(2026, 8, 24, 9, 0),
}
```

### Schedule Output Shape

`generate_schedule()` returns timetable entries:

```python
{
    "task_id": "task-1",
    "task_name": "Finish OS report",
    "start": datetime(...),
    "end": datetime(...),
}
```

### EDF Algorithm Built

EDF means Earliest Deadline First. The scheduler:

1. Keeps only tasks whose status is `pending`.
2. Sorts them by earliest deadline.
3. If two tasks have the same deadline, sorts by priority.
4. If deadline and priority are the same, sorts by creation time.
5. Places tasks back-to-back from `start_time`.

Priority order:

```text
High -> Medium -> Low
```

This means an urgent high-priority task with the same deadline as another task appears first.

### FCFS Support

Although FCFS belongs mainly to Module 4, the scheduler now supports:

```python
generate_schedule(tasks, algorithm="FCFS")
```

FCFS means First Come First Served. It sorts by `created_at` and ignores deadline/priority for ordering.

## Module 2 - Persistence and Schedulability

Module 2 adds real task storage and feasibility checking. This turns the scheduler from a hardcoded demo into a backend that can support the GUI form.

### File: `src/task_scheduler/persistence/db.py`

This file owns SQLite persistence.

It contains:

- `get_connection(db_path=None)`
- `validate_task(task)`
- `add_task(conn, task)`
- `get_all_tasks(conn)`
- `get_task_by_id(conn, task_id)`
- `update_task(conn, task_id, changes)`
- `update_task_status(conn, task_id, new_status)`
- `delete_task(conn, task_id)`
- `log_history(conn, date_value, algorithm, tasks_scheduled, deadlines_missed)`
- `get_history(conn, algorithm=None)`

The default database path is:

```text
data/tasks.db
```

`get_connection()` creates the database and table automatically if they do not already exist.

### SQLite Table

The backend creates this table:

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    deadline TEXT NOT NULL,
    duration_min INTEGER NOT NULL,
    priority TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);
```

Datetime values are stored as ISO 8601 strings in SQLite and converted back to Python `datetime` objects when loaded.

### Backend Validation

Before saving a task, `validate_task()` checks:

- `id` exists and is a non-empty string
- `name` exists and is a non-empty string
- `deadline` is a `datetime`
- `duration_min` is a positive integer
- `priority` is one of `High`, `Medium`, `Low`
- `status` is one of `pending`, `in_progress`, `done`
- `created_at` is a `datetime`

This protects the backend even if the frontend accidentally sends bad data.

### Edit and Status Update Support

Module 3 needs task changes to cause a fresh schedule. For that reason, `db.py` now supports editing existing tasks:

```python
db.update_task(conn, "task-1", {
    "deadline": datetime(2026, 8, 24, 17, 0),
    "duration_min": 60,
})
```

Editable fields:

- `name`
- `deadline`
- `duration_min`
- `priority`
- `status`

The task's `id` and `created_at` stay stable. This matters because `id` is the identity used by the GUI, and `created_at` is needed for FCFS order later.

### File: `src/task_scheduler/core/schedulability.py`

This file checks whether the pending task list is physically possible to complete before all deadlines.

It contains:

- `check_schedulability(tasks, now=None)`
- EDF-based feasibility ordering
- pending-task filtering
- at-risk task detection
- a human-readable warning message for the GUI banner
- a direct console demo under `if __name__ == "__main__"`

### Schedulability Logic

The check works like this:

1. Keep only `pending` tasks.
2. Sort tasks using the same EDF order.
3. Walk through tasks in that order.
4. Keep a cumulative total of required work time.
5. For each task, calculate its projected finish time.
6. If the projected finish time is after the task deadline, mark that task as at risk.

Return shape:

```python
{
    "feasible": False,
    "at_risk_tasks": ["task-1", "task-2"],
    "message": "You will miss 2 deadline(s): Huge report, Quick email. Free up about 120 minute(s) to recover the plan.",
}
```

Important detail: `at_risk_tasks` returns task IDs for code, while `message` contains names for humans.

## Module 3 - Dynamic Reschedule Backend

Module 3 turns the scheduler into a reusable backend workflow for live updates. The frontend will eventually draw a Gantt chart and animate changes, but the backend's job is to return a fresh schedule after every task mutation.

### File: `src/task_scheduler/core/rescheduler.py`

This file contains:

- `build_schedule_state(conn, algorithm="EDF", start_time=None, now=None)`
- `add_task_and_reschedule(conn, task, algorithm="EDF", start_time=None, now=None)`
- `edit_task_and_reschedule(conn, task_id, changes, algorithm="EDF", start_time=None, now=None)`
- `update_status_and_reschedule(conn, task_id, status, algorithm="EDF", start_time=None, now=None)`
- `mark_done_and_reschedule(conn, task_id, algorithm="EDF", start_time=None, now=None)`
- `delete_task_and_reschedule(conn, task_id, algorithm="EDF", start_time=None, now=None)`

### Why This File Exists

Before Module 3, the GUI had to manually do several backend steps:

1. Save or change a task.
2. Load all tasks from SQLite.
3. Filter pending tasks.
4. Generate the schedule.
5. Check schedulability.
6. Redraw the screen.

`rescheduler.py` packages the backend part of that sequence into one clean API. The frontend can call one function after a user action and then redraw from the returned data.

### Schedule State Shape

Every rescheduler function returns:

```python
{
    "tasks": [...],
    "pending_tasks": [...],
    "schedule": [...],
    "schedulability": {
        "feasible": True,
        "at_risk_tasks": [],
        "message": "All deadlines are achievable.",
    },
}
```

Field meanings:

- `tasks`: all tasks in SQLite, including `pending`, `in_progress`, and `done`
- `pending_tasks`: only tasks that can be rearranged by the scheduler
- `schedule`: generated timetable for pending tasks only
- `schedulability`: feasibility result for pending tasks only

### Dynamic Reschedule Flow

When a task changes, the backend flow is:

```text
user action -> database mutation -> reload tasks -> generate EDF schedule -> check feasibility -> return state
```

Examples:

```python
state = rescheduler.add_task_and_reschedule(conn, task)
state = rescheduler.edit_task_and_reschedule(conn, task_id, {"duration_min": 45})
state = rescheduler.mark_done_and_reschedule(conn, task_id)
state = rescheduler.delete_task_and_reschedule(conn, task_id)
```

The frontend should use `state["schedule"]` to redraw the Gantt timeline and `state["schedulability"]` for the warning banner.

The state also includes `state["comparison"]`, containing `tasks_scheduled` and
`deadlines_missed` for both EDF and FCFS. Each state refresh logs one history row
per algorithm in SQLite.

Backend validation requires naive `datetime` values and rejects a deadline in the
past when adding a task or editing its deadline. Status-only updates remain
available for existing tasks, including tasks that have become overdue.

### In-Progress and Done Task Rule

Module 3 requires that already-started or completed work should not be rearranged. The backend enforces that rule in two places:

- `generate_schedule()` ignores tasks whose status is not `pending`
- `build_schedule_state()` exposes all tasks but schedules only pending tasks

So if a task has:

```python
"status": "in_progress"
```

or:

```python
"status": "done"
```

it remains stored in the database but does not appear in the active schedule.

## Existing Frontend Touchpoints

Your teammate's frontend files already connect to the backend:

- `src/task_scheduler/gui/app.py`
- `src/task_scheduler/gui/task_form.py`

The app currently:

- opens a Tkinter window
- displays schedule output as plain text
- loads existing tasks from SQLite
- submits new tasks through `db.add_task()`
- calls `generate_schedule()`
- calls `check_schedulability()`
- shows a red warning banner when the task set is infeasible

The Gantt timeline and animation are frontend responsibilities in Module 3. The backend now returns the fresh state needed for that redraw.

## How To Run Backend Checks

From the project root:

```powershell
python src\task_scheduler\core\scheduler.py
python src\task_scheduler\core\schedulability.py
python src\task_scheduler\persistence\db.py
```

`db.py` uses a temporary database in its standalone demo, so running it does not add sample rows to `data/tasks.db`.

## How To Run Unit Tests

From the project root:

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests\unit -p "test_*.py"
```

Current test coverage:

- EDF deadline ordering
- EDF priority and creation-time tie-breaks
- pending-only scheduling
- FCFS ordering
- invalid algorithm rejection
- feasible schedulability case
- overloaded schedulability case
- schedulability returns task IDs
- schedulability ignores done/in-progress tasks
- database add/load
- database status update
- database delete
- database task fetch
- database task edit
- dynamic reschedule after add
- dynamic reschedule after edit
- dynamic reschedule after mark done
- dynamic reschedule after delete
- in-progress task exclusion during reschedule
- invalid duration rejection
- invalid priority rejection
- invalid status rejection

## Verified Status

These checks passed on 2026-09-05:

```text
python src\task_scheduler\core\scheduler.py
python src\task_scheduler\core\schedulability.py
python src\task_scheduler\persistence\db.py
PYTHONPATH=src python -m unittest discover -s tests\unit -p "test_*.py"
PYTHONPATH=src python -c "from task_scheduler.gui.app import App; from task_scheduler.gui.task_form import TaskForm; print('GUI imports OK')"
```

Unit test result:

```text
Ran 23 tests
OK
```

## What Is Left After Module 3

Backend work left for later modules:

1. Add history table and `log_history()` for Module 4.
2. Count deadline misses for EDF and FCFS comparison metrics.
3. Expand validation for Module 5 decisions, such as whether to reject deadlines in the past.
4. Add more integration tests after the GUI timeline and comparison view exist.

Frontend work left for later modules:

1. Add edit/delete/mark-done controls.
2. Replace the plain text schedule with a Canvas Gantt timeline.
3. Add urgency colors.
4. Add visible reschedule animation.
5. Add EDF vs FCFS comparison view.

## Backend Handoff Summary

Modules 1, 2, and 3 backend are now complete and testable. The frontend can safely call:

```python
from task_scheduler.core import rescheduler
from task_scheduler.core.scheduler import generate_schedule
from task_scheduler.core.schedulability import check_schedulability
from task_scheduler.persistence import db
```

The most important backend contract is:

- send task dictionaries with the documented fields
- save tasks through `db.add_task()`
- load tasks through `db.get_all_tasks()`
- schedule tasks through `generate_schedule()`
- check feasibility through `check_schedulability()`
- after a task changes, call `rescheduler.*_and_reschedule()` to get a fresh state

That is the finished backend foundation through Module 3.
