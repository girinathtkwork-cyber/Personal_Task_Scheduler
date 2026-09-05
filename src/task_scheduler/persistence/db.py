import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[3] / "data" / "tasks.db"
VALID_PRIORITIES = {"High", "Medium", "Low"}
VALID_STATUSES = {"pending", "in_progress", "done"}


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
    conn.commit()


def validate_task(task):
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

    if not isinstance(task["deadline"], datetime):
        raise ValueError("Task deadline must be a datetime object.")

    if not isinstance(task["duration_min"], int) or task["duration_min"] <= 0:
        raise ValueError("Task duration_min must be a positive integer.")

    if task["priority"] not in VALID_PRIORITIES:
        valid = ", ".join(sorted(VALID_PRIORITIES))
        raise ValueError(f"Task priority must be one of: {valid}.")

    status = task.get("status", "pending")
    if status not in VALID_STATUSES:
        valid = ", ".join(sorted(VALID_STATUSES))
        raise ValueError(f"Task status must be one of: {valid}.")

    if not isinstance(task["created_at"], datetime):
        raise ValueError("Task created_at must be a datetime object.")


def add_task(conn, task):
    """
    Save one validated task to the database.
    deadline and created_at are stored as ISO 8601 datetime strings.
    """
    validate_task(task)

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


def update_task(conn, task_id, changes):
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
    validate_task(updated_task)

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

    conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
    conn.commit()


def delete_task(conn, task_id):
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()


if __name__ == "__main__":
    import tempfile
    import uuid

    with tempfile.TemporaryDirectory() as tmp_dir:
        demo_db = Path(tmp_dir) / "tasks.db"
        conn = get_connection(demo_db)

        test_task = {
            "id": str(uuid.uuid4()),
            "name": "Test task from db.py",
            "deadline": datetime(2026, 8, 24, 18, 0),
            "duration_min": 30,
            "priority": "Medium",
            "status": "pending",
            "created_at": datetime(2026, 8, 24, 9, 0),
        }
        add_task(conn, test_task)
        print("Task added.")

        all_tasks = get_all_tasks(conn)
        print(f"\n{len(all_tasks)} task(s) in temporary demo database:")
        for task in all_tasks:
            print(f"  - {task['name']} (deadline: {task['deadline']}, status: {task['status']})")

        conn.close()
