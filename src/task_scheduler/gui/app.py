"""Tkinter user interface for the personal task scheduler."""

import tkinter as tk
from tkinter import messagebox, ttk
import uuid
from datetime import datetime

from task_scheduler.core import rescheduler
from task_scheduler.core.schedulability import check_schedulability
from task_scheduler.gui.gantt_view import GanttView
from task_scheduler.gui.simulation_panel import SimulationPanel
from task_scheduler.gui.task_form import TaskForm
from task_scheduler.persistence import db


COLORS = {
    "background": "#f3f6fb",
    "surface": "#ffffff",
    "ink": "#17243a",
    "muted": "#68778d",
    "accent": "#277da1",
    "accent_dark": "#1c5d78",
    "border": "#dce4ee",
    "danger": "#a83434",
    "danger_bg": "#fff0ef",
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Chronos | Personal Task Scheduler")
        self.geometry("1120x930")
        self.minsize(900, 800)
        self.configure(bg=COLORS["background"])

        self.conn = db.get_connection()
        self.selected_algorithm = tk.StringVar(value="EDF")
        self.current_tasks = []
        self.current_schedulability = None
        self._closing = False
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._configure_style()
        self._build_layout()
        self.refresh_schedule()
        self.after(30_000, self._refresh_warning_clock)

    def _configure_style(self):
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background=COLORS["background"])
        style.configure("Card.TFrame", background=COLORS["surface"])
        style.configure("TLabel", background=COLORS["background"], foreground=COLORS["ink"], font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=("Segoe UI", 10))
        style.configure("Muted.Card.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("Title.TLabel", background="#172b4d", foreground="white", font=("Segoe UI Semibold", 21))
        style.configure("Subtitle.TLabel", background="#172b4d", foreground="#c6d4e5", font=("Segoe UI", 10))
        style.configure("Section.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=("Segoe UI Semibold", 12))
        style.configure("TButton", font=("Segoe UI Semibold", 9), padding=(11, 7))
        style.configure("Accent.TButton", background=COLORS["accent"], foreground="white")
        style.map("Accent.TButton", background=[("active", COLORS["accent_dark"])])
        style.configure("Treeview", rowheight=29, font=("Segoe UI", 9), background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 9), padding=(6, 7))
        style.configure("TCombobox", padding=5)

    def _build_layout(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg="#172b4d", padx=24, pady=18)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Chronos", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Plan your day with deadline-aware scheduling",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        tk.Label(
            header,
            text="PERSONAL TASK SCHEDULER",
            bg="#172b4d",
            fg="#9eb6d2",
            font=("Segoe UI Semibold", 9),
        ).grid(row=0, column=1, rowspan=2, padx=(12, 0))

        notebook = ttk.Notebook(self)
        notebook.grid(row=1, column=0, sticky="nsew")
        body = ttk.Frame(notebook, padding=(18, 16))
        notebook.add(body, text="Task planner")
        self.simulation_panel = SimulationPanel(notebook, self.conn)
        notebook.add(self.simulation_panel, text="Simulation lab")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=2)
        body.rowconfigure(3, weight=3)

        self.warning_label = tk.Label(
            body,
            text="",
            bg=COLORS["danger_bg"],
            fg=COLORS["danger"],
            font=("Segoe UI Semibold", 10),
            wraplength=1050,
            justify="left",
            padx=14,
            pady=6,
            anchor="w",
        )

        self.task_form = TaskForm(body, on_submit=self.handle_task_submit)
        self.task_form.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        schedule_card = ttk.Frame(body, style="Card.TFrame", padding=14)
        schedule_card.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        schedule_card.columnconfigure(0, weight=1)
        schedule_card.rowconfigure(1, weight=1, minsize=190)

        schedule_heading = ttk.Frame(schedule_card, style="Card.TFrame")
        schedule_heading.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        schedule_heading.columnconfigure(0, weight=1)
        ttk.Label(schedule_heading, text="Today's schedule", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(schedule_heading, text="Sort policy", style="Muted.Card.TLabel").grid(row=0, column=1, padx=(12, 6))
        self.algorithm_box = ttk.Combobox(
            schedule_heading,
            textvariable=self.selected_algorithm,
            values=("EDF", "FCFS"),
            state="readonly",
            width=8,
        )
        self.algorithm_box.grid(row=0, column=2, sticky="e")
        self.algorithm_box.bind("<<ComboboxSelected>>", self._on_algorithm_changed)

        self.gantt_view = GanttView(schedule_card, on_task_hover=self._show_task_details)
        self.gantt_view.configure(bg=COLORS["surface"])
        self.gantt_view.grid(row=1, column=0, sticky="nsew")

        lower = ttk.Frame(body)
        lower.grid(row=3, column=0, sticky="nsew")
        lower.columnconfigure(0, weight=3)
        lower.columnconfigure(1, weight=2)
        lower.rowconfigure(0, weight=1)

        task_card = ttk.Frame(lower, style="Card.TFrame", padding=14)
        task_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        task_card.columnconfigure(0, weight=1)
        task_card.rowconfigure(1, weight=1)
        ttk.Label(task_card, text="Tasks", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.task_table = ttk.Treeview(
            task_card,
            columns=("name", "deadline", "duration", "priority", "status"),
            show="headings",
            selectmode="browse",
        )
        for column, heading, width in (
            ("name", "TASK", 150),
            ("deadline", "DEADLINE", 120),
            ("duration", "MIN", 50),
            ("priority", "PRIORITY", 70),
            ("status", "STATUS", 95),
        ):
            self.task_table.heading(column, text=heading)
            self.task_table.column(column, width=width, minwidth=45, anchor="w")
        self.task_table.grid(row=1, column=0, sticky="nsew")
        self.task_table.bind("<<TreeviewSelect>>", self._show_selected_details)
        table_scroll = ttk.Scrollbar(task_card, orient="vertical", command=self.task_table.yview)
        table_scroll.grid(row=1, column=1, sticky="ns")
        task_horizontal_scroll = ttk.Scrollbar(task_card, orient="horizontal", command=self.task_table.xview)
        task_horizontal_scroll.grid(row=2, column=0, sticky="ew")
        self.task_table.configure(yscrollcommand=table_scroll.set, xscrollcommand=task_horizontal_scroll.set)

        actions = ttk.Frame(task_card, style="Card.TFrame")
        actions.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Edit selected", command=self.edit_selected_task).pack(side="left")
        ttk.Button(actions, text="Mark complete", command=self.complete_selected_task).pack(side="left", padx=7)
        ttk.Button(actions, text="Delete", command=self.delete_selected_task).pack(side="left")

        info_card = ttk.Frame(lower, style="Card.TFrame", padding=14)
        info_card.grid(row=0, column=1, sticky="nsew")
        info_card.columnconfigure(0, weight=1)
        ttk.Label(info_card, text="Task details", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.details_label = ttk.Label(
            info_card,
            text="Select a task or hover over a schedule block.",
            style="Muted.Card.TLabel",
            justify="left",
            wraplength=300,
        )
        self.details_label.grid(row=1, column=0, sticky="nw", pady=(8, 18))
        ttk.Separator(info_card).grid(row=2, column=0, sticky="ew", pady=(0, 14))
        ttk.Label(info_card, text="EDF vs FCFS", style="Section.TLabel").grid(row=3, column=0, sticky="w")
        self.comparison_label = ttk.Label(
            info_card,
            text="",
            style="Muted.Card.TLabel",
            justify="left",
        )
        self.comparison_label.grid(row=4, column=0, sticky="nw", pady=(8, 0))

        footer = tk.Label(
            body,
            text="Tasks are saved locally on this device",
            bg=COLORS["background"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            anchor="e",
        )
        footer.grid(row=4, column=0, sticky="ew", pady=(9, 0))

    def handle_task_submit(self, task):
        try:
            if self.task_form.editing_task_id:
                state = rescheduler.edit_task_and_reschedule(
                    self.conn,
                    self.task_form.editing_task_id,
                    task,
                    algorithm=self.selected_algorithm.get(),
                )
            else:
                task.update({
                    "id": str(uuid.uuid4()),
                    "status": "pending",
                    "created_at": datetime.now(),
                })
                state = rescheduler.add_task_and_reschedule(
                    self.conn,
                    task,
                    algorithm=self.selected_algorithm.get(),
                )
        except ValueError as error:
            messagebox.showerror("Unable to save task", str(error), parent=self)
            return False

        self.task_form.reset()
        self._display_state(state, animate=True)

    def refresh_schedule(self):
        state = rescheduler.build_schedule_state(
            self.conn,
            algorithm=self.selected_algorithm.get(),
        )
        self._display_state(state)

    def _display_state(self, state, animate=False):
        self.current_tasks = state["tasks"]
        if animate:
            self.gantt_view.animate_to(state["schedule"], state["tasks"])
        else:
            self.gantt_view.render(state["schedule"], state["tasks"])
        self._update_warning_banner(state["schedulability"])
        self._refresh_task_table(state["tasks"])
        self._update_comparison(state["comparison"])

    def _refresh_task_table(self, tasks):
        selected = self.task_table.selection()
        selected_id = selected[0] if selected else None
        self.task_table.delete(*self.task_table.get_children())
        for task in tasks:
            deadline = task["deadline"].strftime("%b %d, %H:%M")
            self.task_table.insert(
                "",
                "end",
                iid=task["id"],
                values=(
                    task["name"],
                    deadline,
                    task["duration_min"],
                    task["priority"],
                    task["status"].replace("_", " ").title(),
                ),
            )
        if selected_id and self.task_table.exists(selected_id):
            self.task_table.selection_set(selected_id)

    def _update_warning_banner(self, result):
        self.current_schedulability = result
        self._render_warning_banner()

    def _refresh_warning_clock(self):
        """Keep the forecast banner current as task deadlines pass."""
        self._render_warning_banner()
        self.after(30_000, self._refresh_warning_clock)

    def _render_warning_banner(self):
        if not self.current_schedulability:
            self.warning_label.grid_forget()
            return
        now = datetime.now()
        future_tasks = [
            task for task in self.current_tasks
            if task.get("status", "pending") == "pending" and task["deadline"] > now
        ]
        result = check_schedulability(future_tasks, now=now)
        if result["feasible"]:
            self.warning_label.grid_forget()
            return
        self.warning_label.config(text=f"Schedule at risk  •  {result['message']}")
        self.warning_label.grid(row=0, column=0, sticky="ew", pady=(0, 12))

    def _update_comparison(self, comparison):
        edf = comparison["EDF"]
        fcfs = comparison["FCFS"]
        self.comparison_label.config(
            text=(
                f"EDF   {edf['deadlines_missed']} missed / {edf['tasks_scheduled']} tasks\n"
                f"FCFS  {fcfs['deadlines_missed']} missed / {fcfs['tasks_scheduled']} tasks\n\n"
                "The selected policy controls the timeline above."
            )
        )

    def _on_algorithm_changed(self, _event=None):
        self.refresh_schedule()

    def _selected_task(self):
        selection = self.task_table.selection()
        if not selection:
            messagebox.showinfo("Select a task", "Choose a task from the list first.", parent=self)
            return None
        return next((task for task in self.current_tasks if task["id"] == selection[0]), None)

    def edit_selected_task(self):
        task = self._selected_task()
        if task:
            self.task_form.load_task(task)
            self.task_form.name_entry.focus_set()

    def complete_selected_task(self):
        task = self._selected_task()
        if not task:
            return
        try:
            state = rescheduler.mark_done_and_reschedule(
                self.conn,
                task["id"],
                algorithm=self.selected_algorithm.get(),
            )
        except ValueError as error:
            messagebox.showerror("Unable to complete task", str(error), parent=self)
            return
        self._display_state(state, animate=True)

    def delete_selected_task(self):
        task = self._selected_task()
        if not task:
            return
        if not messagebox.askyesno(
            "Delete task",
            f"Delete “{task['name']}” permanently?",
            parent=self,
        ):
            return
        try:
            state = rescheduler.delete_task_and_reschedule(
                self.conn,
                task["id"],
                algorithm=self.selected_algorithm.get(),
            )
        except ValueError as error:
            messagebox.showerror("Unable to delete task", str(error), parent=self)
            return
        self.task_form.reset()
        self._display_state(state, animate=True)

    def _show_selected_details(self, _event=None):
        task = self._selected_task_without_message()
        self._show_task_details(task)

    def _selected_task_without_message(self):
        selection = self.task_table.selection()
        if not selection:
            return None
        return next((task for task in self.current_tasks if task["id"] == selection[0]), None)

    def _show_task_details(self, task):
        if not task:
            self.details_label.config(text="Select a task or hover over a schedule block.")
            return
        self.details_label.config(
            text=(
                f"{task['name']}\n\n"
                f"Deadline   {task['deadline'].strftime('%A, %b %d at %H:%M')}\n"
                f"Duration   {task['duration_min']} minutes\n"
                f"Priority   {task['priority']}\n"
                f"Status   {task['status'].replace('_', ' ').title()}"
            )
        )

    def destroy(self):
        if not self._closing:
            self._closing = True
            self.simulation_panel.shutdown()
            self.conn.close()
        super().destroy()


if __name__ == "__main__":
    App().mainloop()
