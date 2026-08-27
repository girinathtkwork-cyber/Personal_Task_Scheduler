"""
task_form.py

A Tkinter Frame containing the task entry form:
    Name | Deadline (date + time) | Duration (minutes) | Priority | Submit

This file does NOT talk to a database. Backend's db.py isn't ready yet,
so on Submit we just build a task dict (matching scheduler.py's expected
input shape) and hand it off via an on_submit callback. Whatever file
embeds this form (app.py) decides what to do with that task — for now,
that will be: append to a local Python list, then re-run generate_schedule().

Expected task dict shape (matches core/scheduler.py's generate_schedule() input):
    {"name": str, "deadline": datetime, "duration_min": int, "priority": str}
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime


class TaskForm(ttk.Frame):
    """
    A self-contained form for entering one task.

    Usage:
        form = TaskForm(parent, on_submit=my_callback)
        form.pack()

    `on_submit` is called with a single task dict (see module docstring)
    whenever the user successfully submits a valid task. Validation errors
    are shown to the user via a messagebox and on_submit is NOT called.
    """

    def __init__(self, parent, on_submit):
        super().__init__(parent, padding=10)
        self.on_submit = on_submit

        # --- Name ---
        ttk.Label(self, text="Task Name:").grid(row=0, column=0, sticky="w", pady=4)
        self.name_entry = ttk.Entry(self, width=30)
        self.name_entry.grid(row=0, column=1, columnspan=3, sticky="w", pady=4)

        # --- Deadline: date + time as separate simple text fields ---
        # (Spec explicitly allows plain text fields here instead of a date picker)
        ttk.Label(self, text="Deadline Date (YYYY-MM-DD):").grid(row=1, column=0, sticky="w", pady=4)
        self.date_entry = ttk.Entry(self, width=15)
        self.date_entry.grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(self, text="Time (HH:MM, 24hr):").grid(row=1, column=2, sticky="w", pady=4)
        self.time_entry = ttk.Entry(self, width=10)
        self.time_entry.grid(row=1, column=3, sticky="w", pady=4)

        # --- Duration ---
        ttk.Label(self, text="Duration (minutes):").grid(row=2, column=0, sticky="w", pady=4)
        self.duration_entry = ttk.Entry(self, width=10)
        self.duration_entry.grid(row=2, column=1, sticky="w", pady=4)

        # --- Priority ---
        ttk.Label(self, text="Priority:").grid(row=3, column=0, sticky="w", pady=4)
        self.priority_var = tk.StringVar(value="Medium")
        priority_dropdown = ttk.Combobox(
            self,
            textvariable=self.priority_var,
            values=["High", "Medium", "Low"],
            state="readonly",  # user can only pick from the list, not type freely
            width=12,
        )
        priority_dropdown.grid(row=3, column=1, sticky="w", pady=4)

        # --- Submit ---
        submit_btn = ttk.Button(self, text="Add Task", command=self._handle_submit)
        submit_btn.grid(row=4, column=0, columnspan=2, pady=(10, 0), sticky="w")

    def _handle_submit(self):
        """Validate all fields, build a task dict, call on_submit, then clear the form."""
        name = self.name_entry.get().strip()
        date_str = self.date_entry.get().strip()
        time_str = self.time_entry.get().strip()
        duration_str = self.duration_entry.get().strip()
        priority = self.priority_var.get()

        # --- Validation ---
        if not name:
            messagebox.showerror("Missing Name", "Please enter a task name.")
            return

        try:
            deadline = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showerror(
                "Invalid Deadline",
                "Deadline must be a valid date (YYYY-MM-DD) and time (HH:MM, 24hr).\n"
                "Example: 2026-08-30 and 18:00",
            )
            return

        try:
            duration_min = int(duration_str)
            if duration_min <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Invalid Duration",
                "Duration must be a whole number of minutes greater than 0.",
            )
            return

        task = {
            "name": name,
            "deadline": deadline,
            "duration_min": duration_min,
            "priority": priority,
        }

        self.on_submit(task)
        self._clear_form()

    def _clear_form(self):
        """Reset all fields after a successful submit, ready for the next task."""
        self.name_entry.delete(0, tk.END)
        self.date_entry.delete(0, tk.END)
        self.time_entry.delete(0, tk.END)
        self.duration_entry.delete(0, tk.END)
        self.priority_var.set("Medium")