"""
app.py

Main entry point for the Tkinter GUI.

Module 2 changes:
    - Replaced the old hardcoded sample task list with a local, in-memory
      Python list (`self.tasks`) that acts as a stand-in for the database
      until teammate's db.py (add_task/get_all_tasks) is ready.
    - Embedded TaskForm (task_form.py). Submitting the form appends to
      self.tasks, then re-runs generate_schedule() and refreshes the
      Text widget display.

Run from Personal_Task_Scheduler/src with:
    python -m task_scheduler.gui.app
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime

from task_scheduler.core.scheduler import generate_schedule
from task_scheduler.gui.task_form import TaskForm


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Personal Task Scheduler")
        self.geometry("700x600")
        self.resizable(False, False)

        # --- In-memory task store (stand-in for db.py until it's ready) ---
        # Shape matches scheduler.py's expected input:
        #   {"name": str, "deadline": datetime, "duration_min": int, "priority": str}
        self.tasks = []

        # --- Task entry form (top of window) ---
        self.task_form = TaskForm(self, on_submit=self.handle_new_task)
        self.task_form.pack(side="top", fill="x")

        ttk.Separator(self, orient="horizontal").pack(side="top", fill="x", pady=5)

        # --- Schedule display (below the form) ---
        ttk.Label(self, text="Current Schedule (EDF order):", font=("TkDefaultFont", 10, "bold")).pack(
            side="top", anchor="w", padx=10
        )

        self.schedule_text = tk.Text(self, height=20, width=80, state="disabled")
        self.schedule_text.pack(side="top", padx=10, pady=(0, 10), fill="both", expand=True)

        # Show initial (empty) state
        self.refresh_schedule()

    def handle_new_task(self, task):
        """Called by TaskForm whenever a valid task is submitted."""
        self.tasks.append(task)
        self.refresh_schedule()

    def refresh_schedule(self):
        """Re-run generate_schedule() on the current task list and redraw the Text widget."""
        schedule = generate_schedule(self.tasks) if self.tasks else []

        self.schedule_text.config(state="normal")   # unlock for editing
        self.schedule_text.delete("1.0", tk.END)     # clear previous content

        if not schedule:
            self.schedule_text.insert(tk.END, "No tasks yet. Add one above.")
        else:
            for entry in schedule:
                start_str = entry["start"].strftime("%Y-%m-%d %H:%M")
                end_str = entry["end"].strftime("%H:%M")
                self.schedule_text.insert(
                    tk.END, f"{start_str} - {end_str}   {entry['task_name']}\n"
                )

        self.schedule_text.config(state="disabled")  # lock again (read-only display)


if __name__ == "__main__":
    app = App()
    app.mainloop()