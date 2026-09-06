"""
app.py

Main entry point for the Tkinter GUI.

Module 3 frontend changes:
    - Replaced the text-based schedule display with the visual GanttView.
    - Wired task mutation and startup load through core.rescheduler instead
      of manual db + scheduler sequence.
    - Extracted warning banner update logic to a helper for shared use.
"""

import tkinter as tk
from tkinter import ttk
import uuid
from datetime import datetime

from task_scheduler.persistence import db
from task_scheduler.gui.task_form import TaskForm
from task_scheduler.core import rescheduler
from task_scheduler.gui.gantt_view import GanttView


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
        # Not packed yet — only shown when infeasible (see _update_warning_banner)

        # --- Task entry form ---
        self.task_form = TaskForm(self, on_submit=self.handle_new_task)
        self.task_form.pack(side="top", fill="x")

        ttk.Separator(self, orient="horizontal").pack(side="top", fill="x", pady=5)

        # --- Schedule display ---
        self.gantt_view = GanttView(self, on_task_hover=self._show_task_details)
        self.gantt_view.pack(side="top", padx=10, pady=(0, 10), fill="both", expand=True)

        # --- Details Panel ---
        self.details_frame = ttk.LabelFrame(self, text="Task Details")
        self.details_frame.pack(side="top", fill="x", padx=10, pady=(0, 10))
        
        self.details_label = tk.Label(self.details_frame, text="Hover over a task to see details", justify="left")
        self.details_label.pack(side="top", anchor="w", padx=5, pady=5)

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

        state = rescheduler.add_task_and_reschedule(self.conn, task)
        self.gantt_view.animate_to(state["schedule"], state["tasks"])
        self._update_warning_banner(state["schedulability"])

    def refresh_schedule(self):
        """
        Reload all tasks from the database, re-run generate_schedule() and
        check_schedulability() using the backend rescheduler, and redraw both the 
        schedule display and the warning banner using snap-render.
        Called only on startup.
        """
        state = rescheduler.build_schedule_state(self.conn)
        self.gantt_view.render(state["schedule"], state["tasks"])
        self._update_warning_banner(state["schedulability"])

    def _update_warning_banner(self, schedulability_result):
        """
        Shows or hides the warning banner based on the schedulability result.
        """
        if not schedulability_result["feasible"]:
            self.warning_label.config(text=f"⚠ {schedulability_result['message']}")
            self.warning_label.pack(side="top", fill="x", before=self.task_form)
        else:
            self.warning_label.pack_forget()

    def _show_task_details(self, task):
        if not task:
            self.details_label.config(text="Hover over a task to see details")
        else:
            dt_str = task["deadline"].strftime("%Y-%m-%d %H:%M")
            text = (
                f"Name: {task['name']}\n"
                f"Deadline: {dt_str}\n"
                f"Duration: {task['duration_min']} mins\n"
                f"Priority: {task['priority']}\n"
                f"Status: {task['status']}"
            )
            self.details_label.config(text=text)

    def destroy(self):
        """Close the database connection cleanly when the window is closed."""
        self.conn.close()
        super().destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()