# TaskEDF Backend

TaskEDF is a personal task scheduler based on real-time operating-system scheduling concepts. The backend uses Earliest Deadline First (EDF) as its primary algorithm, checks whether pending work can meet its deadlines, persists tasks in SQLite, and supports dynamic rescheduling when tasks change.

This document describes the complete backend. It does not document or modify the Tkinter frontend.

## Backend Status

| Module | Status | Backend responsibility |
| --- | --- | --- |
| Module 1 - Core Scheduling Pipeline | Complete | EDF and FCFS schedule generation. |
| Module 2 - Persistence and Schedulability | Complete | SQLite task storage, validation, CRUD, and feasibility checking. |
| Module 3 - Dynamic Rescheduling | Complete | Rebuild the schedule after task mutations while excluding started/completed tasks. |
| Module 4 - EDF vs FCFS Comparison | Complete | Deadline-miss metrics and history logging for both algorithms. |
| Module 5 - Edge Cases and Reliability | Complete | Validation, boundary handling, error handling, and backend integration tests. |

## Backend Files

```text
src/task_scheduler/
|-- core/
|   |-- scheduler.py       # EDF, FCFS, timetable generation, deadline metrics
|   |-- schedulability.py   # Deadline feasibility analysis
|   |-- rescheduler.py     # Persistence + scheduling orchestration
|-- persistence/
    |-- db.py              # SQLite connection, tasks, history, validation

tests/
|-- unit/
|   |-- test_scheduler.py
|   |-- test_schedulability.py
|   |-- test_rescheduler.py
|   |-- test_db.py
|-- integration/
    |-- test_backend_workflow.py
```

## Design Principles

- Scheduling logic has no GUI dependency.
- SQLite access is isolated inside `persistence/db.py`.
- Task and schedule data use Python dictionaries.
- Only pending tasks are rearranged by the scheduler.
- `in_progress` and `done` tasks remain stored but are excluded from new schedules.
- The backend is deterministic in tests through injectable `start_time` and `now` values.
- The backend uses naive `datetime` values only.
- Backend validation is authoritative; frontend validation is only a convenience layer.

## Data Model

### Task

Tasks are represented as dictionaries:

```python
{
    "id": "task-1",
    "name": "Finish OS report",
    "deadline": datetime(2026, 9, 24, 18, 0),
    "duration_min": 120,
    "priority": "High",
    "status": "pending",
    "created_at": datetime(2026, 9, 24, 9, 0),
}
```

Fields:

| Field | Type | Description |
| --- | --- | --- |
| `id` | `str` | Unique task identifier. |
| `name` | `str` | Human-readable task name. |
| `deadline` | `datetime` | Latest acceptable completion time. |
| `duration_min` | `int` | Required work duration in minutes. Must be positive. |
| `priority` | `str` | `High`, `Medium`, or `Low`. |
| `status` | `str` | `pending`, `in_progress`, or `done`. |
| `created_at` | `datetime` | Creation time used by FCFS. |

### Timetable Entry

`generate_schedule()` returns entries with this shape:

```python
{
    "task_id": "task-1",
    "task_name": "Finish OS report",
    "start": datetime(2026, 9, 24, 9, 0),
    "end": datetime(2026, 9, 24, 11, 0),
}
```

The scheduler places pending tasks back-to-back. It does not create gaps between tasks.

## Scheduling Algorithms

### EDF

Earliest Deadline First is the primary algorithm.

Tasks are ordered by:

1. Earliest `deadline`.
2. Highest priority when deadlines are equal: `High`, then `Medium`, then `Low`.
3. Earliest `created_at` when deadline and priority are equal.

```python
from task_scheduler.core.scheduler import generate_schedule

schedule = generate_schedule(
    tasks,
    algorithm="EDF",
    start_time=datetime(2026, 9, 24, 9, 0),
)
```

### FCFS

First Come First Served is the comparison baseline. Tasks are ordered only by `created_at`; deadline and priority do not affect FCFS ordering.

```python
schedule = generate_schedule(
    tasks,
    algorithm="FCFS",
    start_time=datetime(2026, 9, 24, 9, 0),
)
```

Only `EDF` and `FCFS` are accepted. Other algorithm names raise `ValueError`.

### Deadline Metrics

```python
from task_scheduler.core.scheduler import count_deadline_misses

misses = count_deadline_misses(tasks, schedule)
```

A task is counted as missed when its timetable `end` is later than its deadline. Finishing exactly at the deadline is considered successful.

## Schedulability Analysis

`check_schedulability()` evaluates only pending tasks in EDF order.

```python
from task_scheduler.core.schedulability import check_schedulability

result = check_schedulability(
    tasks,
    now=datetime(2026, 9, 24, 9, 0),
)
```

Return shape:

```python
{
    "feasible": False,
    "at_risk_tasks": ["task-1", "task-2"],
    "message": "You will miss 2 deadline(s): Huge report, Quick email. Free up about 120 minute(s) to recover the plan.",
}
```

Field meanings:

- `feasible`: `True` when every pending task can finish by its deadline.
- `at_risk_tasks`: IDs of tasks whose projected completion exceeds their deadline.
- `message`: Human-readable explanation suitable for a warning banner.

An empty pending-task list is feasible and returns an empty `at_risk_tasks` list.

## Dynamic Rescheduling

`rescheduler.py` combines database mutation, task loading, scheduling, schedulability analysis, comparison metrics, and history logging.

Available functions:

```python
from task_scheduler.core import rescheduler

state = rescheduler.build_schedule_state(
    conn,
    algorithm="EDF",
    start_time=start_time,
    now=now,
)

state = rescheduler.add_task_and_reschedule(
    conn,
    task,
    algorithm="EDF",
    start_time=start_time,
    now=now,
)

state = rescheduler.edit_task_and_reschedule(
    conn,
    task_id,
    {"duration_min": 45},
    algorithm="EDF",
    start_time=start_time,
    now=now,
)

state = rescheduler.update_status_and_reschedule(
    conn,
    task_id,
    "in_progress",
    algorithm="EDF",
    start_time=start_time,
    now=now,
)

state = rescheduler.mark_done_and_reschedule(
    conn,
    task_id,
    algorithm="EDF",
    start_time=start_time,
    now=now,
)

state = rescheduler.delete_task_and_reschedule(
    conn,
    task_id,
    algorithm="EDF",
    start_time=start_time,
    now=now,
)
```

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
    "comparison": {
        "EDF": {
            "algorithm": "EDF",
            "tasks_scheduled": 3,
            "deadlines_missed": 0,
        },
        "FCFS": {
            "algorithm": "FCFS",
            "tasks_scheduled": 3,
            "deadlines_missed": 1,
        },
    },
}
```

Field meanings:

- `tasks`: every task in SQLite, including pending, in-progress, and done tasks.
- `pending_tasks`: tasks eligible for rearrangement.
- `schedule`: timetable produced by the requested algorithm.
- `schedulability`: feasibility result for pending tasks.
- `comparison`: outcome metrics for both EDF and FCFS.

The existing fields are preserved for frontend compatibility. `comparison` is additive.

### Rescheduling Flow

```text
Task mutation
    |
    v
SQLite update
    |
    v
Reload all tasks
    |
    v
Filter pending tasks
    |
    +--> Generate EDF schedule --> Calculate EDF misses --> Log EDF history
    |
    +--> Generate FCFS schedule -> Calculate FCFS misses -> Log FCFS history
    |
    v
Run EDF schedulability analysis
    |
    v
Return complete schedule state
```

## SQLite Persistence

### Connection

```python
from task_scheduler.persistence import db

conn = db.get_connection()
```

The default database path is:

```text
data/tasks.db
```

Tests can provide a temporary database path:

```python
conn = db.get_connection("temporary/tasks.db")
```

The connection uses `sqlite3.Row`, so rows are converted to dictionaries before being returned. Datetimes are stored as ISO 8601 strings and converted back to Python `datetime` objects.

### Tasks Table

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

### History Table

```sql
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    algorithm TEXT NOT NULL,
    tasks_scheduled INTEGER NOT NULL,
    deadlines_missed INTEGER NOT NULL
);
```

### Persistence API

#### Add a task

```python
db.add_task(conn, task)
```

An optional `reference_time` can be supplied for deterministic validation:

```python
db.add_task(conn, task, reference_time=now)
```

#### Read tasks

```python
all_tasks = db.get_all_tasks(conn)
task = db.get_task_by_id(conn, "task-1")
```

`get_task_by_id()` returns `None` when the task does not exist.

#### Edit a task

```python
db.update_task(
    conn,
    "task-1",
    {
        "name": "Updated report",
        "deadline": datetime(2026, 9, 24, 17, 0),
        "duration_min": 60,
        "priority": "High",
        "status": "pending",
    },
)
```

Editable fields are `name`, `deadline`, `duration_min`, `priority`, and `status`. The task `id` and `created_at` values cannot be changed through this API.

#### Update status

```python
db.update_task_status(conn, "task-1", "done")
```

#### Delete a task

```python
db.delete_task(conn, "task-1")
```

Missing task IDs raise `ValueError` for update, status update, and deletion operations.

#### History

```python
db.log_history(
    conn,
    date_value=datetime(2026, 9, 24),
    algorithm="EDF",
    tasks_scheduled=5,
    deadlines_missed=1,
)

all_history = db.get_history(conn)
edf_history = db.get_history(conn, algorithm="EDF")
```

Each schedule-state refresh logs one EDF row and one FCFS row.

## Validation Rules

The persistence layer validates all task writes.

- `id` must be a non-empty string.
- `name` must be a non-empty string.
- `deadline` must be a naive `datetime`.
- `created_at` must be a naive `datetime`.
- `duration_min` must be a positive integer.
- Boolean values are rejected as durations even though Python treats `bool` as an `int` subclass.
- `priority` must be `High`, `Medium`, or `Low`.
- `status` must be `pending`, `in_progress`, or `done`.
- New task deadlines cannot be in the past relative to the validation reference time.
- Editing a deadline also rejects a past deadline.
- Status-only updates do not revalidate an existing task's deadline.
- Timezone-aware datetimes are rejected instead of being silently converted.
- Duplicate task IDs are rejected by the SQLite primary key.
- Invalid algorithms raise `ValueError`.
- Invalid history counts must be non-negative integers.

## Backend Test Suite

The test directories are intentionally run separately because they are not Python packages.

From the project root:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests\unit -p "test_*.py" -v
python -m unittest discover -s tests\integration -p "test_*.py" -v
```

Current coverage includes:

- EDF ordering and priority tie-breaking.
- FCFS ordering.
- Pending-only scheduling.
- Exact-deadline success.
- EDF versus FCFS deadline-miss comparison.
- Empty and overloaded schedulability cases.
- SQLite task persistence and reconnection.
- Task edits, status changes, completion, and deletion.
- History persistence and algorithm filtering.
- Past-deadline and timezone-aware datetime rejection.
- Missing-record error handling.
- Full backend workflow integration.

## Standalone Backend Demos

Each core backend file can be run without starting the GUI:

```powershell
$env:PYTHONPATH = "src"
python -m task_scheduler.core.scheduler
python -m task_scheduler.core.schedulability
python -m task_scheduler.persistence.db
```

These demos show schedule generation, feasibility analysis, and temporary-database persistence.

## Frontend Integration Contract

The frontend can use the backend through this sequence:

```python
state = rescheduler.add_task_and_reschedule(conn, task)

schedule = state["schedule"]
warning = state["schedulability"]
comparison = state["comparison"]
```

Recommended frontend behavior:

- Draw `state["schedule"]` on the timeline.
- Use `state["tasks"]` to look up full task details.
- Show `state["schedulability"]["message"]` when `feasible` is false.
- Use `state["comparison"]` for the EDF versus FCFS comparison view.
- Keep completed and in-progress tasks visible in the task list, but do not draw them as newly scheduled pending work.

The backend does not depend on Tkinter and can be tested independently from the GUI.

## Scope Boundaries

Included:

- Single-user task scheduling.
- EDF scheduling.
- FCFS comparison scheduling.
- Deadline feasibility analysis.
- Dynamic rescheduling.
- SQLite persistence.
- Task status handling.
- Schedule history and deadline-miss metrics.

Excluded from the backend:

- GUI rendering.
- Tkinter widgets and event handling.
- Gantt canvas drawing.
- Animation timing.
- Login and authentication.
- Networking or cloud synchronization.
- Notifications and background reminders.
- Multi-user or multi-resource scheduling.
- Deadlock avoidance and Banker's algorithm.
- Rate Monotonic Scheduling and other additional algorithms.
