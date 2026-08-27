# task-scheduler/src/task_scheduler/persistence/db.py

import sqlite3
from datetime import datetime
from pathlib import Path

# tasks.db will be created inside your data/ folder
DB_PATH = Path(__file__).resolve().parents[3] / "data" / "tasks.db"


def get_connection():
    """
    Opens a connection to the database file.
    Creates the tasks table if it doesn't exist yet.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us access columns by name, like a dict

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
    return conn


def add_task(conn, task):
    """
    Saves one task to the database.
    task is a dict: {id, name, deadline, duration_min, priority, status, created_at}
    deadline and created_at must be datetime objects — we convert them to text to store them.
    """
    conn.execute(
        """INSERT INTO tasks (id, name, deadline, duration_min, priority, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            task["id"],
            task["name"],
            task["deadline"].isoformat(),
            task["duration_min"],
            task["priority"],
            task.get("status", "pending"),
            task["created_at"].isoformat(),
        )
    )
    conn.commit()


def get_all_tasks(conn):
    """
    Loads every task from the database.
    Converts stored text dates back into real datetime objects.
    """
    rows = conn.execute("SELECT * FROM tasks").fetchall()

    tasks = []
    for row in rows:
        task = dict(row)
        task["deadline"] = datetime.fromisoformat(task["deadline"])
        task["created_at"] = datetime.fromisoformat(task["created_at"])
        tasks.append(task)

    return tasks


def update_task_status(conn, task_id, new_status):
    conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
    conn.commit()


def delete_task(conn, task_id):
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()


if __name__ == "__main__":
    import uuid

    conn = get_connection()

    # Add a test task
    test_task = {
        "id": str(uuid.uuid4()),
        "name": "Test task from db.py",
        "deadline": datetime(2026, 8, 24, 18, 0),
        "duration_min": 30,
        "priority": "Medium",
        "status": "pending",
        "created_at": datetime.now(),
    }
    add_task(conn, test_task)
    print("Task added.")

    # Load everything back
    all_tasks = get_all_tasks(conn)
    print(f"\n{len(all_tasks)} task(s) in database:")
    for t in all_tasks:
        print(f"  - {t['name']} (deadline: {t['deadline']}, status: {t['status']})")

    conn.close()