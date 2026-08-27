"""
app.py

Main entry point for the Tkinter GUI.

Module 2 (final) changes:
    - Removed the in-memory self.tasks list — now backed by real SQLite
      persistence via persistence/db.py (add_task, get_all_tasks).
    - On startup, loads existing tasks from the database instead of
      starting empty.
    - On submit, fills in the fields db.py requires that TaskForm doesn't
      collect (id, status, created_at), then calls db.add_task().
    - Added a schedulability warning banner wired to
      core/schedulability.py's check_schedulability().

Run from Personal_Task_Scheduler/src with:
    python -m task_scheduler.gui.app
"""

import tkinter as tk
from tkinter import ttk
import uuid
from datetime import datetime

from task_scheduler.core.scheduler import generate_schedule
from task_scheduler.core.schedulability import check_schedulability
from task_scheduler.persistence import db
from task_scheduler.gui.task_form import TaskForm


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Personal Task Scheduler")
        self.geometry("700x650")
        self.resizable(False, False)

        # --- Database connection (opened once, kept for the app's lifetime) ---
        self.conn = db.get_connection()

        # --- Schedulability warning banner (top of window, hidden by default) ---
        self.warning_label = tk.Label(
            self,
            text="",
            bg="#c0392b",       # red background — must be unmissable per spec
            fg="white",
            font=("TkDefaultFont", 10, "bold"),
            wraplength=680,
            justify="left",
            pady=6,
        )
        # Not packed yet — only shown when infeasible (see refresh_schedule)

        # --- Task entry form ---
        self.task_form = TaskForm(self, on_submit=self.handle_new_task)
        self.task_form.pack(side="top", fill="x")

        ttk.Separator(self, orient="horizontal").pack(side="top", fill="x", pady=5)

        # --- Schedule display ---
        ttk.Label(self, text="Current Schedule (EDF order):", font=("TkDefaultFont", 10, "bold")).pack(
            side="top", anchor="w", padx=10
        )

        self.schedule_text = tk.Text(self, height=20, width=80, state="disabled")
        self.schedule_text.pack(side="top", padx=10, pady=(0, 10), fill="both", expand=True)

        # --- Load existing tasks from the database and show them ---
        self.refresh_schedule()

    def handle_new_task(self, task):
        """
        Called by TaskForm with a task dict: {name, deadline, duration_min, priority}.
        db.py's add_task() needs more fields than the form collects, so we
        fill those in here before saving.
        """
        task["id"] = str(uuid.uuid4())
        task["status"] = "pending"
        task["created_at"] = datetime.now()

        db.add_task(self.conn, task)
        self.refresh_schedule()

    def refresh_schedule(self):
        """
        Reload all tasks from the database, re-run generate_schedule() and
        check_schedulability(), and redraw both the schedule display and
        the warning banner.
        """
        all_tasks = db.get_all_tasks(self.conn)

        # Only pending tasks get scheduled/checked — matches the spec's
        # rule that in-progress/done tasks aren't re-arranged.
        pending_tasks = [t for t in all_tasks if t["status"] == "pending"]

        schedule = generate_schedule(pending_tasks) if pending_tasks else []

        # --- Update schedule display ---
        self.schedule_text.config(state="normal")
        self.schedule_text.delete("1.0", tk.END)

        if not schedule:
            self.schedule_text.insert(tk.END, "No tasks yet. Add one above.")
        else:
            for entry in schedule:
                start_str = entry["start"].strftime("%Y-%m-%d %H:%M")
                end_str = entry["end"].strftime("%H:%M")
                self.schedule_text.insert(
                    tk.END, f"{start_str} - {end_str}   {entry['task_name']}\n"
                )

        self.schedule_text.config(state="disabled")

        # --- Update schedulability warning banner ---
        if pending_tasks:
            result = check_schedulability(pending_tasks)
            if not result["feasible"]:
                self.warning_label.config(text=f"⚠ {result['message']}")
                self.warning_label.pack(side="top", fill="x", before=self.task_form)
            else:
                self.warning_label.pack_forget()
        else:
            self.warning_label.pack_forget()

    def destroy(self):
        """Close the database connection cleanly when the window is closed."""
        self.conn.close()
        super().destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()