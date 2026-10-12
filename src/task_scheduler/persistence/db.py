import sqlite3
import json
from datetime import date, datetime, timedelta
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[3] / "data" / "tasks.db"
VALID_PRIORITIES = {"High", "Medium", "Low"}
VALID_STATUSES = {"pending", "in_progress", "done"}
VALID_ALGORITHMS = {"EDF", "FCFS"}


def get_connection(db_path=None):
    """
    Open a SQLite connection and ensure the tasks table exists.

    db_path is optional so tests can use a temporary database without touching
    the real application database in data/tasks.db.
    """
    path = Path(db_path) if db_path is not None else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _create_tables(conn)
    return conn


def _create_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            deadline TEXT NOT NULL,
            duration_min INTEGER NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            algorithm TEXT NOT NULL,
            tasks_scheduled INTEGER NOT NULL,
            deadlines_missed INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS simulation_experiments (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            start_time TEXT NOT NULL,
            baseline_policy TEXT NOT NULL,
            config_json TEXT NOT NULL,
            result_json TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS simulation_events (
            experiment_id TEXT NOT NULL,
            policy TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            simulated_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_json TEXT NOT NULL,
            PRIMARY KEY (experiment_id, policy, sequence),
            FOREIGN KEY (experiment_id) REFERENCES simulation_experiments(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS simulation_decisions (
            experiment_id TEXT NOT NULL,
            policy TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            simulated_at TEXT NOT NULL,
            decision_json TEXT NOT NULL,
            PRIMARY KEY (experiment_id, policy, sequence),
            FOREIGN KEY (experiment_id) REFERENCES simulation_experiments(id) ON DELETE CASCADE
        )
    """)
    conn.commit()


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Cannot serialize value of type {type(value).__name__}.")


def save_simulation_experiment(conn, experiment):
    """Persist experiment input/results separately from ordinary task records."""
    required = {"id", "created_at", "start_time", "baseline_policy", "runs"}
    missing = sorted(required - experiment.keys())
    if missing:
        raise ValueError(f"Missing simulation experiment field(s): {', '.join(missing)}")

    config = {
        "context_switch_overhead_min": experiment.get("context_switch_overhead_min", 0),
        "workload": experiment.get("workload", []),
        "events_input": experiment.get("events_input", []),
    }
    with conn:
        conn.execute(
            """INSERT INTO simulation_experiments
               (id, created_at, start_time, baseline_policy, config_json, result_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                experiment["id"],
                experiment["created_at"].isoformat(),
                experiment["start_time"].isoformat(),
                experiment["baseline_policy"],
                json.dumps(config, default=_json_default),
                json.dumps(experiment, default=_json_default),
            ),
        )
        for policy, result in experiment["runs"].items():
            for sequence, event in enumerate(result.get("events", [])):
                conn.execute(
                    """INSERT INTO simulation_events
                       (experiment_id, policy, sequence, simulated_at, event_type, event_json)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        experiment["id"],
                        policy,
                        sequence,
                        event["at"].isoformat(),
                        event["kind"],
                        json.dumps(event, default=_json_default),
                    ),
                )
            for sequence, decision in enumerate(result.get("decisions", [])):
                conn.execute(
                    """INSERT INTO simulation_decisions
                       (experiment_id, policy, sequence, simulated_at, decision_json)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        experiment["id"],
                        policy,
                        sequence,
                        decision["at"].isoformat(),
                        json.dumps(decision, default=_json_default),
                    ),
                )
    return experiment["id"]


def get_simulation_experiment(conn, experiment_id):
    row = conn.execute(
        "SELECT * FROM simulation_experiments WHERE id = ?",
        (experiment_id,),
    ).fetchone()
    if row is None:
        return None
    result = json.loads(row["result_json"])
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "start_time": row["start_time"],
        "baseline_policy": row["baseline_policy"],
        "config": json.loads(row["config_json"]),
        "result": result,
    }


def get_simulation_experiment_summaries(conn, limit=25):
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("limit must be a positive integer.")
    rows = conn.execute(
        """SELECT id, created_at, start_time, baseline_policy, result_json
           FROM simulation_experiments ORDER BY created_at DESC, id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    summaries = []
    for row in rows:
        result = json.loads(row["result_json"])
        summaries.append({
            "id": row["id"],
            "created_at": row["created_at"],
            "start_time": row["start_time"],
            "baseline_policy": row["baseline_policy"],
            "policies": list(result["runs"]),
            "deadline_misses": {
                policy: run["metrics"]["deadline_misses"]
                for policy, run in result["runs"].items()
            },
            "tasks_completed": {
                policy: run["metrics"]["tasks_completed"]
                for policy, run in result["runs"].items()
            },
            "cpu_utilization": {
                policy: run["metrics"]["cpu_utilization"]
                for policy, run in result["runs"].items()
            },
        })
    return summaries


def _validate_datetime(value, field_name):
    if not isinstance(value, datetime):
        raise ValueError(f"Task {field_name} must be a datetime object.")
    if value.tzinfo is not None:
        raise ValueError(f"Task {field_name} must be a naive datetime.")


def _validate_deadline(deadline, reference_time):
    if reference_time is not None:
        _validate_datetime(reference_time, "reference_time")
        if deadline < reference_time:
            raise ValueError("Task deadline cannot be in the past.")


def validate_task(task, reference_time=None):
    """
    Validate the task shape used by the scheduler, GUI, and persistence layer.
    Raises ValueError with a clear message if the task is not acceptable.
    """
    required_fields = ["id", "name", "deadline", "duration_min", "priority", "created_at"]
    missing_fields = [field for field in required_fields if field not in task]
    if missing_fields:
        raise ValueError(f"Missing required task field(s): {', '.join(missing_fields)}")

    if not isinstance(task["id"], str) or not task["id"].strip():
        raise ValueError("Task id must be a non-empty string.")

    if not isinstance(task["name"], str) or not task["name"].strip():
        raise ValueError("Task name must be a non-empty string.")

    _validate_datetime(task["deadline"], "deadline")
    _validate_deadline(task["deadline"], reference_time)
    if isinstance(task["duration_min"], bool) or not isinstance(task["duration_min"], int) or task["duration_min"] <= 0:
        raise ValueError("Task duration_min must be a positive integer.")

    if task["priority"] not in VALID_PRIORITIES:
        valid = ", ".join(sorted(VALID_PRIORITIES))
        raise ValueError(f"Task priority must be one of: {valid}.")

    status = task.get("status", "pending")
    if status not in VALID_STATUSES:
        valid = ", ".join(sorted(VALID_STATUSES))
        raise ValueError(f"Task status must be one of: {valid}.")

    _validate_datetime(task["created_at"], "created_at")


def add_task(conn, task, reference_time=None):
    """Save one validated task to the database."""
    validate_task(task, reference_time=reference_time or datetime.now())

    conn.execute(
        """INSERT INTO tasks (id, name, deadline, duration_min, priority, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            task["id"].strip(),
            task["name"].strip(),
            task["deadline"].isoformat(),
            task["duration_min"],
            task["priority"],
            task.get("status", "pending"),
            task["created_at"].isoformat(),
        ),
    )
    conn.commit()


def _history_date(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError("History date must be a date, datetime, or non-empty string.")


def log_history(conn, date_value, algorithm, tasks_scheduled, deadlines_missed):
    """Persist one algorithm outcome for a schedule generation."""
    normalized_algorithm = algorithm.upper() if isinstance(algorithm, str) else algorithm
    if normalized_algorithm not in VALID_ALGORITHMS:
        raise ValueError("algorithm must be 'EDF' or 'FCFS'")
    if isinstance(tasks_scheduled, bool) or not isinstance(tasks_scheduled, int) or tasks_scheduled < 0:
        raise ValueError("tasks_scheduled must be a non-negative integer.")
    if isinstance(deadlines_missed, bool) or not isinstance(deadlines_missed, int) or deadlines_missed < 0:
        raise ValueError("deadlines_missed must be a non-negative integer.")

    conn.execute(
        """INSERT INTO history (date, algorithm, tasks_scheduled, deadlines_missed)
           VALUES (?, ?, ?, ?)""",
        (_history_date(date_value), normalized_algorithm, tasks_scheduled, deadlines_missed),
    )
    conn.commit()


def get_history(conn, algorithm=None):
    """Return persisted schedule outcomes, optionally filtered by algorithm."""
    if algorithm is not None:
        normalized_algorithm = algorithm.upper() if isinstance(algorithm, str) else algorithm
        if normalized_algorithm not in VALID_ALGORITHMS:
            raise ValueError("algorithm must be 'EDF' or 'FCFS'")
        rows = conn.execute(
            "SELECT * FROM history WHERE algorithm = ? ORDER BY id",
            (normalized_algorithm,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM history ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def get_all_tasks(conn):
    """
    Load every task from the database and convert datetime strings back to
    datetime objects.
    """
    rows = conn.execute("SELECT * FROM tasks ORDER BY created_at").fetchall()

    tasks = []
    for row in rows:
        task = dict(row)
        task["deadline"] = datetime.fromisoformat(task["deadline"])
        task["created_at"] = datetime.fromisoformat(task["created_at"])
        tasks.append(task)

    return tasks


def get_task_by_id(conn, task_id):
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        return None

    task = dict(row)
    task["deadline"] = datetime.fromisoformat(task["deadline"])
    task["created_at"] = datetime.fromisoformat(task["created_at"])
    return task


def update_task(conn, task_id, changes, reference_time=None):
    """
    Update editable fields for an existing task.

    This is used by Module 3 when editing a task should immediately trigger a
    fresh schedule. The task id and created_at timestamp stay stable.
    """
    existing_task = get_task_by_id(conn, task_id)
    if existing_task is None:
        raise ValueError(f"No task found with id: {task_id}")

    allowed_fields = {"name", "deadline", "duration_min", "priority", "status"}
    unknown_fields = [field for field in changes if field not in allowed_fields]
    if unknown_fields:
        raise ValueError(f"Cannot update task field(s): {', '.join(unknown_fields)}")

    updated_task = dict(existing_task)
    updated_task.update(changes)
    validate_task(
        updated_task,
        reference_time=(reference_time or datetime.now()) if "deadline" in changes else None,
    )

    conn.execute(
        """UPDATE tasks
           SET name = ?, deadline = ?, duration_min = ?, priority = ?, status = ?
           WHERE id = ?""",
        (
            updated_task["name"].strip(),
            updated_task["deadline"].isoformat(),
            updated_task["duration_min"],
            updated_task["priority"],
            updated_task["status"],
            task_id,
        ),
    )
    conn.commit()
    return updated_task


def update_task_status(conn, task_id, new_status):
    if new_status not in VALID_STATUSES:
        valid = ", ".join(sorted(VALID_STATUSES))
        raise ValueError(f"Task status must be one of: {valid}.")

    if get_task_by_id(conn, task_id) is None:
        raise ValueError(f"No task found with id: {task_id}")

    conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
    conn.commit()


def delete_task(conn, task_id):
    cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    if cursor.rowcount == 0:
        raise ValueError(f"No task found with id: {task_id}")
    conn.commit()


if __name__ == "__main__":
    import tempfile
    import uuid

    with tempfile.TemporaryDirectory() as tmp_dir:
        demo_db = Path(tmp_dir) / "tasks.db"
        conn = get_connection(demo_db)
        demo_now = datetime.now()

        test_task = {
            "id": str(uuid.uuid4()),
            "name": "Test task from db.py",
            "deadline": demo_now + timedelta(hours=9),
            "duration_min": 30,
            "priority": "Medium",
            "status": "pending",
            "created_at": demo_now,
        }
        add_task(conn, test_task)
        print("Task added.")

        all_tasks = get_all_tasks(conn)
        print(f"\n{len(all_tasks)} task(s) in temporary demo database:")
        for task in all_tasks:
            print(f"  - {task['name']} (deadline: {task['deadline']}, status: {task['status']})")

        conn.close()
