"""Reusable task-entry and task-edit form."""

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
        super().__init__(parent, padding=(16, 8), style="Card.TFrame")
        self.on_submit = on_submit
        self.editing_task_id = None

        self.columnconfigure(1, weight=2)
        self.columnconfigure(3, weight=1)
        self.heading = ttk.Label(self, text="Add a task", style="Section.TLabel")
        self.heading.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 5))

        ttk.Label(self, text="Task name", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=2)
        self.name_entry = ttk.Entry(self)
        self.name_entry.grid(row=1, column=1, columnspan=3, sticky="ew", pady=2)

        ttk.Label(self, text="Deadline date (YYYY-MM-DD)", style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=2)
        self.date_entry = ttk.Entry(self, width=15)
        self.date_entry.grid(row=2, column=1, sticky="ew", pady=2, padx=(0, 12))
        ttk.Label(self, text="Time (HH:MM, 24-hour)", style="Card.TLabel").grid(row=2, column=2, sticky="w", pady=2)
        self.time_entry = ttk.Entry(self, width=10)
        self.time_entry.grid(row=2, column=3, sticky="ew", pady=2)

        ttk.Label(self, text="Duration (minutes)", style="Card.TLabel").grid(row=3, column=0, sticky="w", pady=2)
        self.duration_entry = ttk.Entry(self, width=10)
        self.duration_entry.grid(row=3, column=1, sticky="ew", pady=2, padx=(0, 12))

        ttk.Label(self, text="Priority", style="Card.TLabel").grid(row=3, column=2, sticky="w", pady=2)
        self.priority_var = tk.StringVar(value="Medium")
        self.priority_dropdown = ttk.Combobox(
            self,
            textvariable=self.priority_var,
            values=["High", "Medium", "Low"],
            state="readonly",
        )
        self.priority_dropdown.grid(row=3, column=3, sticky="ew", pady=2)

        self.submit_button = ttk.Button(self, text="Add task", style="Accent.TButton", command=self._handle_submit)
        self.submit_button.grid(row=4, column=0, columnspan=2, pady=(5, 0), sticky="w")
        ttk.Label(
            self,
            text="Example: 2026-10-14 at 18:30",
            style="Muted.Card.TLabel",
        ).grid(row=4, column=2, columnspan=2, sticky="e", pady=(5, 0))

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

        if self.on_submit(task) is not False:
            self.reset()

    def load_task(self, task):
        """Populate the form to edit an existing task."""
        self.editing_task_id = task["id"]
        self.heading.config(text="Edit task")
        self.submit_button.config(text="Save changes")
        self.name_entry.delete(0, tk.END)
        self.name_entry.insert(0, task["name"])
        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, task["deadline"].strftime("%Y-%m-%d"))
        self.time_entry.delete(0, tk.END)
        self.time_entry.insert(0, task["deadline"].strftime("%H:%M"))
        self.duration_entry.delete(0, tk.END)
        self.duration_entry.insert(0, str(task["duration_min"]))
        self.priority_var.set(task["priority"])

    def reset(self):
        """Return to add-task mode and clear all form values."""
        self.editing_task_id = None
        self.heading.config(text="Add a task")
        self.submit_button.config(text="Add task")
        self.name_entry.delete(0, tk.END)
        self.date_entry.delete(0, tk.END)
        self.time_entry.delete(0, tk.END)
        self.duration_entry.delete(0, tk.END)
        self.priority_var.set("Medium")
