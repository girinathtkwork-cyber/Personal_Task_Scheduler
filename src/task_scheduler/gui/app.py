"""
app.py — Tkinter GUI shell for the Personal Task Scheduler.

Module 1 (Frontend scope):
- Basic window shell with title and fixed size
- A placeholder area that displays a schedule as plain text
- Uses a HARDCODED fake timetable for now (Backend's real
  generate_schedule() will be wired in during Module 1 integration,
  and the display upgrades to a Canvas Gantt view in Module 3)
"""

import tkinter as tk

# ---------------------------------------------------------------------------
# FAKE / HARDCODED TIMETABLE (for Frontend standalone testing only)
# This matches the "Timetable entry" shape from the data model:
#   { "start": ..., "end": ..., "task_id": ..., "task_name": ... }
# We use plain strings for start/end here (instead of real datetime objects)
# just to keep this file dependency-free for now. Once Backend's real
# generate_schedule() is wired in, this list gets replaced entirely.
# ---------------------------------------------------------------------------
FAKE_TIMETABLE = [
    {"start": "09:00", "end": "09:45", "task_id": "1", "task_name": "Finish OS Report"},
    {"start": "09:45", "end": "10:30", "task_id": "2", "task_name": "Gym"},
    {"start": "10:30", "end": "11:15", "task_id": "3", "task_name": "Team Meeting"},
    {"start": "11:15", "end": "12:00", "task_id": "4", "task_name": "Study DBMS"},
    {"start": "12:00", "end": "12:30", "task_id": "5", "task_name": "Lunch Break"},
]


class TaskSchedulerApp:
    """Main application window."""

    def __init__(self, root):
        self.root = root

        # --- Window basics ---
        self.root.title("Personal Task Scheduler — EDF")
        self.root.geometry("600x400")   # fixed size window (width x height)
        self.root.resizable(False, False)  # keep it fixed for demo reliability

        # --- Heading label ---
        heading = tk.Label(
            self.root,
            text="Today's Schedule",
            font=("Helvetica", 16, "bold")
        )
        heading.pack(pady=10)

        # --- Placeholder text area to display the schedule ---
        # A Text widget is used (instead of a single Label) because it can
        # show multiple lines cleanly. This gets replaced by the Canvas
        # Gantt view in Module 3 — for now it's plain text, per Module 1 scope.
        self.schedule_display = tk.Text(
            self.root,
            width=60,
            height=15,
            font=("Courier", 11),
            state="disabled"  # read-only; we only update it through code
        )
        self.schedule_display.pack(padx=10, pady=10)

        # Render the fake timetable immediately on startup
        self.display_schedule(FAKE_TIMETABLE)

    def display_schedule(self, timetable):
        """
        Renders a list of timetable entries as plain text lines
        inside the Text widget.

        timetable: list of dicts, each with 'start', 'end', 'task_name'
        (matches the shape Backend's generate_schedule() will return)
        """
        self.schedule_display.config(state="normal")   # unlock for editing
        self.schedule_display.delete("1.0", tk.END)    # clear old content

        if not timetable:
            self.schedule_display.insert(tk.END, "No tasks scheduled.\n")
        else:
            for entry in timetable:
                line = f"{entry['start']} - {entry['end']}   {entry['task_name']}\n"
                self.schedule_display.insert(tk.END, line)

        self.schedule_display.config(state="disabled")  # lock again


def main():
    root = tk.Tk()
    app = TaskSchedulerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()