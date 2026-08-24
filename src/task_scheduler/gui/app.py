"""
app.py — Tkinter GUI shell for the Personal Task Scheduler.

Module 1 (Frontend scope) — INTEGRATION VERSION:
- Now calls the real generate_schedule() from Backend's scheduler.py
- No more fake hardcoded timetable
"""

import tkinter as tk
from datetime import datetime

# Import Backend's real scheduling function
from task_scheduler.core.scheduler import generate_schedule


# ---------------------------------------------------------------------------
# Sample tasks used to test the integrated pipeline.
# Shape matches what Backend's generate_schedule() expects:
#   {"name": str, "deadline": datetime, "duration_min": int, "priority": str}
# (This will later be replaced by tasks coming from the entry form + DB
# in Module 2 — for now it's still a fixed list, just no longer fake output.)
# ---------------------------------------------------------------------------
def get_sample_tasks():
    today = datetime.now().replace(second=0, microsecond=0)
    return [
        {"name": "Finish OS Report", "deadline": today.replace(hour=18, minute=0), "duration_min": 120, "priority": "High"},
        {"name": "Email Professor", "deadline": today.replace(hour=11, minute=0), "duration_min": 15, "priority": "High"},
        {"name": "Gym", "deadline": today.replace(hour=9, minute=0), "duration_min": 60, "priority": "Medium"},
        {"name": "Study DBMS", "deadline": today.replace(hour=14, minute=0), "duration_min": 45, "priority": "Medium"},
        {"name": "Lunch Break", "deadline": today.replace(hour=13, minute=0), "duration_min": 30, "priority": "Low"},
    ]


class TaskSchedulerApp:
    """Main application window."""

    def __init__(self, root):
        self.root = root

        # --- Window basics ---
        self.root.title("Personal Task Scheduler — EDF")
        self.root.geometry("600x400")
        self.root.resizable(False, False)

        # --- Heading label ---
        heading = tk.Label(
            self.root,
            text="Today's Schedule",
            font=("Helvetica", 16, "bold")
        )
        heading.pack(pady=10)

        # --- Placeholder text area to display the schedule ---
        self.schedule_display = tk.Text(
            self.root,
            width=60,
            height=15,
            font=("Courier", 11),
            state="disabled"
        )
        self.schedule_display.pack(padx=10, pady=10)

        # Build the real schedule using Backend's generate_schedule()
        tasks = get_sample_tasks()
        # Schedule starting from 8 AM today, so output is easy to eyeball-check
        start_time = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        timetable = generate_schedule(tasks, start_time=start_time)

        self.display_schedule(timetable)

    def display_schedule(self, timetable):
        """
        Renders a list of timetable entries as plain text lines.

        timetable: list of dicts with 'start' (datetime), 'end' (datetime),
        'task_name' (str) — this is the REAL shape returned by
        Backend's generate_schedule().
        """
        self.schedule_display.config(state="normal")
        self.schedule_display.delete("1.0", tk.END)

        if not timetable:
            self.schedule_display.insert(tk.END, "No tasks scheduled.\n")
        else:
            for entry in timetable:
                start_str = entry["start"].strftime("%H:%M")
                end_str = entry["end"].strftime("%H:%M")
                line = f"{start_str} - {end_str}   {entry['task_name']}\n"
                self.schedule_display.insert(tk.END, line)

        self.schedule_display.config(state="disabled")


def main():
    root = tk.Tk()
    app = TaskSchedulerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()