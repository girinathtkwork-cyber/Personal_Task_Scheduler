"""Tkinter controls and views for the discrete-event simulation engine."""

from datetime import datetime, timedelta
import queue
import sqlite3
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import uuid

from task_scheduler.persistence import db
from task_scheduler.simulation.engine import POLICIES, SimulationEngine
from task_scheduler.simulation.experiments import create_overrun_demo, run_counterfactual


class SimulationPanel(ttk.Frame):
    def __init__(self, master, conn):
        super().__init__(master, padding=16)
        self.conn = conn
        self.engine = None
        self.scenario_tasks = []
        self.scenario_events = []
        self.simulation_start = None
        self._timer = None
        self._auto_run = False
        self._worker_queue = queue.Queue()
        self._worker_running = False
        self._poll_job = None
        self._task_labels = {}
        self.policy = tk.StringVar(value="EDF")
        self.overhead = tk.StringVar(value="0")
        self.clock_text = tk.StringVar(value="Not started")
        self.cpu_text = tk.StringVar(value="CPU idle")
        self.forecast_text = tk.StringVar(value="Load tasks to inspect a workload.")
        self.event_kind = tk.StringVar(value="overrun")
        self.target_task = tk.StringVar()
        self.event_offset = tk.StringVar(value="5")
        self.event_value = tk.StringVar(value="10")
        self.event_deadline = tk.StringVar(value="30")
        self.new_task_name = tk.StringVar(value="Unexpected task")
        self._build_ui()
        self._load_saved_experiments()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        toolbar.columnconfigure(1, weight=1)
        ttk.Label(toolbar, text="Simulation lab", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        controls = ttk.Frame(toolbar)
        controls.grid(row=0, column=1, sticky="e")
        ttk.Label(controls, text="Policy").pack(side="left", padx=(0, 5))
        ttk.Combobox(
            controls,
            textvariable=self.policy,
            values=tuple(sorted(POLICIES)),
            state="readonly",
            width=9,
        ).pack(side="left", padx=(0, 10))
        ttk.Label(controls, text="Switch min").pack(side="left", padx=(0, 5))
        ttk.Entry(controls, textvariable=self.overhead, width=6).pack(side="left", padx=(0, 10))
        ttk.Button(controls, text="Load current tasks", command=self.load_current_tasks).pack(side="left")
        ttk.Button(controls, text="Overrun demo", command=self.load_overrun_demo).pack(side="left", padx=(7, 0))

        buttons = ttk.Frame(self)
        buttons.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        ttk.Button(buttons, text="Start / resume", style="Accent.TButton", command=self.start).pack(side="left")
        ttk.Button(buttons, text="Pause", command=self.pause).pack(side="left", padx=6)
        ttk.Button(buttons, text="Step to event", command=self.step).pack(side="left")
        ttk.Button(buttons, text="Run to finish", command=self.run_to_completion).pack(side="left", padx=6)
        ttk.Button(buttons, text="Reset", command=self.reset).pack(side="left")
        ttk.Label(buttons, textvariable=self.clock_text, style="Section.TLabel").pack(side="right", padx=(10, 0))

        panes = ttk.Panedwindow(self, orient="horizontal")
        panes.grid(row=2, column=0, sticky="nsew")
        left = ttk.Frame(panes, style="Card.TFrame", padding=14)
        right = ttk.Frame(panes, style="Card.TFrame", padding=14)
        panes.add(left, weight=2)
        panes.add(right, weight=3)
        # ttk.Panedwindow does not support a pane-level minsize option on all
        # Tk versions; requested frame widths keep the controls readable.
        left.configure(width=410)
        right.configure(width=430)
        left.columnconfigure(0, weight=1)
        # Keep the workload list compact so the pending event queue remains
        # visible in the same panel, even at the app's minimum window height.
        left.rowconfigure(3, weight=0)
        left.rowconfigure(6, weight=1)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        ttk.Label(left, text="Inject an event", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        event_form = ttk.Frame(left, style="Card.TFrame")
        event_form.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        event_form.columnconfigure(1, weight=1, minsize=145)
        ttk.Label(event_form, text="Event", style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=3)
        kind_box = ttk.Combobox(
            event_form,
            textvariable=self.event_kind,
            values=("arrival", "overrun", "cancel", "deadline_change", "interrupt", "resume"),
            state="readonly",
        )
        kind_box.grid(row=0, column=1, sticky="ew", pady=3)
        ttk.Label(event_form, text="At minute", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(event_form, textvariable=self.event_offset).grid(row=1, column=1, sticky="ew", pady=3)
        ttk.Label(event_form, text="Target task", style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=3)
        self.target_box = ttk.Combobox(event_form, textvariable=self.target_task, state="readonly")
        self.target_box.grid(row=2, column=1, sticky="ew", pady=3)
        extra_value_label = ttk.Label(event_form, text="Extra execution / new task duration", style="Card.TLabel")
        extra_value_label.grid(row=3, column=0, sticky="w", pady=3)
        extra_value_entry = ttk.Entry(event_form, textvariable=self.event_value)
        extra_value_entry.grid(row=3, column=1, sticky="ew", pady=3)
        self.extra_value_widgets = (extra_value_label, extra_value_entry)
        self.optional_event_fields = {
            4: (
                ttk.Label(event_form, text="New task name", style="Card.TLabel"),
                ttk.Entry(event_form, textvariable=self.new_task_name),
            ),
            5: (
                ttk.Label(event_form, text="New deadline offset", style="Card.TLabel"),
                ttk.Entry(event_form, textvariable=self.event_deadline),
            ),
        }
        for row, widgets in self.optional_event_fields.items():
            widgets[0].grid(row=row, column=0, sticky="w", pady=3)
            widgets[1].grid(row=row, column=1, sticky="ew", pady=3)
        kind_box.bind("<<ComboboxSelected>>", self._update_event_form_fields)
        ttk.Button(event_form, text="Queue event", command=self.queue_event).grid(
            row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )

        ttk.Label(left, text="Workload state", style="Section.TLabel").grid(row=2, column=0, sticky="nw", pady=(0, 8))
        self.task_table = ttk.Treeview(
            left,
            columns=("task", "state", "remaining", "deadline"),
            show="headings",
            height=2,
        )
        for column, title, width in (
            ("task", "TASK", 130),
            ("state", "STATE", 95),
            ("remaining", "LEFT", 65),
            ("deadline", "DEADLINE", 130),
        ):
            self.task_table.heading(column, text=title)
            self.task_table.column(column, width=width, minwidth=45)
        self.task_table.grid(row=3, column=0, sticky="nsew")
        task_scroll = ttk.Scrollbar(left, orient="vertical", command=self.task_table.yview)
        task_scroll.grid(row=3, column=1, sticky="ns")
        task_horizontal_scroll = ttk.Scrollbar(left, orient="horizontal", command=self.task_table.xview)
        task_horizontal_scroll.grid(row=4, column=0, sticky="ew")
        self.task_table.configure(
            yscrollcommand=task_scroll.set,
            xscrollcommand=task_horizontal_scroll.set,
        )
        ttk.Label(left, text="Pending event queue", style="Section.TLabel").grid(
            row=5, column=0, sticky="w", pady=(10, 6)
        )
        self.event_table = ttk.Treeview(
            left,
            columns=("at", "event", "task"),
            show="headings",
            height=3,
        )
        for column, title, width in (
            ("at", "AT", 125),
            ("event", "EVENT", 115),
            ("task", "TASK", 150),
        ):
            self.event_table.heading(column, text=title)
            self.event_table.column(column, width=width, minwidth=45)
        self.event_table.grid(row=6, column=0, sticky="nsew")
        event_scroll = ttk.Scrollbar(left, orient="vertical", command=self.event_table.yview)
        event_scroll.grid(row=6, column=1, sticky="ns")
        event_horizontal_scroll = ttk.Scrollbar(left, orient="horizontal", command=self.event_table.xview)
        event_horizontal_scroll.grid(row=7, column=0, sticky="ew")
        self.event_table.configure(
            yscrollcommand=event_scroll.set,
            xscrollcommand=event_horizontal_scroll.set,
        )

        ttk.Label(right, text="CPU timeline", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.timeline = ttk.Treeview(
            right,
            columns=("start", "end", "cpu", "task", "deadline", "duration"),
            show="headings",
            height=8,
        )
        for column, title, width in (
            ("start", "START", 130),
            ("end", "END", 130),
            ("cpu", "CPU", 110),
            ("task", "TASK", 150),
            ("deadline", "DEADLINE", 110),
            ("duration", "MIN", 65),
        ):
            self.timeline.heading(column, text=title)
            self.timeline.column(column, width=width, minwidth=50)
        self.timeline.grid(row=1, column=0, sticky="nsew")
        self.timeline.tag_configure("missed", foreground="#a83434")
        timeline_scroll = ttk.Scrollbar(right, orient="vertical", command=self.timeline.yview)
        timeline_scroll.grid(row=1, column=1, sticky="ns")
        timeline_horizontal_scroll = ttk.Scrollbar(right, orient="horizontal", command=self.timeline.xview)
        timeline_horizontal_scroll.grid(row=2, column=0, sticky="ew")
        self.timeline.configure(
            yscrollcommand=timeline_scroll.set,
            xscrollcommand=timeline_horizontal_scroll.set,
        )

        state_bar = ttk.Frame(right, style="Card.TFrame")
        state_bar.grid(row=3, column=0, sticky="ew", pady=(10, 5))
        ttk.Label(state_bar, textvariable=self.cpu_text, style="Section.TLabel").pack(side="left")
        ttk.Button(state_bar, text="Analyze remaining", command=self.analyze_remaining).pack(side="right")
        ttk.Button(state_bar, text="Compare policies", command=self.compare_policies).pack(side="right")
        ttk.Label(
            right,
            textvariable=self.forecast_text,
            style="Muted.Card.TLabel",
            wraplength=700,
            justify="left",
        ).grid(row=4, column=0, sticky="ew", pady=(0, 8))

        lower = ttk.Panedwindow(right, orient="horizontal")
        lower.grid(row=5, column=0, sticky="nsew", pady=(4, 0))
        right.rowconfigure(5, weight=1)
        explanations = ttk.Frame(lower, style="Card.TFrame")
        results = ttk.Frame(lower, style="Card.TFrame")
        lower.add(explanations, weight=2)
        lower.add(results, weight=3)
        ttk.Label(explanations, text="Events and decisions", style="Section.TLabel").pack(anchor="w", pady=(0, 5))
        self.log = tk.Text(
            explanations,
            height=9,
            wrap="word",
            bg="#f7f9fc",
            fg="#34445a",
            relief="flat",
            font=("Segoe UI", 9),
            padx=8,
            pady=8,
        )
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")
        ttk.Label(results, text="Experiment results", style="Section.TLabel").pack(anchor="w", pady=(0, 5))
        self.results_table = ttk.Treeview(
            results,
            columns=("policy", "completed", "misses", "utilization", "tardiness", "order"),
            show="headings",
            height=8,
        )
        for column, title, width in (
            ("policy", "POLICY", 80),
            ("completed", "DONE", 60),
            ("misses", "MISSES", 65),
            ("utilization", "CPU %", 70),
            ("tardiness", "TARDY MIN", 80),
            ("order", "EXECUTION ORDER", 210),
        ):
            self.results_table.heading(column, text=title)
            self.results_table.column(column, width=width, minwidth=45)
        self.results_table.pack(fill="both", expand=True)
        results_horizontal_scroll = ttk.Scrollbar(results, orient="horizontal", command=self.results_table.xview)
        results_horizontal_scroll.pack(fill="x")
        self.results_table.configure(xscrollcommand=results_horizontal_scroll.set)
        self.results_table.bind("<<TreeviewSelect>>", self._show_selected_metrics)
        self._update_event_form_fields()

    def _update_event_form_fields(self, _event=None):
        """Show only the extra event inputs needed by the selected event."""
        kind = self.event_kind.get()
        if kind in {"overrun", "arrival"}:
            for widget in self.extra_value_widgets:
                widget.grid()
        else:
            for widget in self.extra_value_widgets:
                widget.grid_remove()

        visible_rows = set()
        if kind == "arrival":
            visible_rows = {4, 5}
        elif kind == "deadline_change":
            visible_rows = {5}
        for row, widgets in self.optional_event_fields.items():
            for widget in widgets:
                if row in visible_rows:
                    widget.grid()
                else:
                    widget.grid_remove()

    def load_current_tasks(self):
        now = datetime.now().replace(second=0, microsecond=0)
        tasks = db.get_all_tasks(self.conn)
        self.scenario_tasks = [
            {
                "id": task["id"],
                "name": task["name"],
                "arrival_time": now,
                "deadline": task["deadline"],
                "estimated_execution_min": task["duration_min"],
                "priority": task["priority"],
            }
            for task in tasks
            if task["status"] == "pending"
        ]
        if not self.scenario_tasks:
            messagebox.showinfo("No pending tasks", "Add pending tasks in the planner before simulating.", parent=self)
            return
        self.scenario_events = []
        self.simulation_start = now
        self._create_engine()
        if not self.engine:
            return
        self._render_state(self.engine.snapshot())

    def load_overrun_demo(self):
        scenario = create_overrun_demo()
        self.scenario_tasks = scenario["tasks"]
        self.scenario_events = []
        self.simulation_start = scenario["start_time"]
        self.event_kind.set("overrun")
        self._update_event_form_fields()
        self.event_offset.set("5")
        self.event_value.set(str(scenario["events"][0]["additional_min"]))
        self._create_engine()
        if not self.engine:
            return
        self._render_state(self.engine.snapshot())
        self.forecast_text.set("Initially feasible. Queue the prepared overrun event to see the plan become infeasible.")

    def _create_engine(self):
        try:
            overhead = float(self.overhead.get())
            self.engine = SimulationEngine(
                self.scenario_tasks,
                policy=self.policy.get(),
                start_time=self.simulation_start,
                context_switch_overhead_min=overhead,
                events=self.scenario_events,
            )
        except (ValueError, TypeError) as error:
            messagebox.showerror("Invalid simulation setup", str(error), parent=self)
            self.engine = None
            return
        self._refresh_target_choices()

    def _refresh_target_choices(self):
        self._task_labels = {}
        values = []
        for task in self.scenario_tasks:
            label = f"{task['name']}  ·  {task['id'][:8]}"
            self._task_labels[label] = task["id"]
            values.append(label)
        self.target_box.configure(values=values)
        if values and self.target_task.get() not in self._task_labels:
            self.target_task.set(values[0])

    def start(self):
        if self.engine is None:
            if not self.scenario_tasks:
                self.load_current_tasks()
            if self.engine is None:
                return
        self.engine.start()
        self._auto_run = True
        self._render_state(self.engine.snapshot())
        self._schedule_tick()

    def pause(self):
        self._auto_run = False
        self._cancel_timer()
        if self.engine:
            self._render_state(self.engine.pause())

    def step(self):
        if self.engine is None:
            self.start()
            self._cancel_timer()
            self._auto_run = False
        if self.engine:
            self._render_state(self.engine.step())

    def run_to_completion(self):
        if self.engine is None:
            self.start()
            self._cancel_timer()
            self._auto_run = False
        if self.engine:
            self._auto_run = True
            self._schedule_tick()

    def reset(self):
        self._auto_run = False
        self._cancel_timer()
        if self.engine:
            self._render_state(self.engine.reset())

    def _schedule_tick(self):
        self._cancel_timer()
        if self._auto_run and self.engine and self.engine.status not in {"completed", "stopped"}:
            self._timer = self.after(80, self._tick)

    def _tick(self):
        self._timer = None
        if not self._auto_run or not self.engine:
            return
        snapshot = self.engine.step()
        self._render_state(snapshot)
        if snapshot["status"] in {"completed", "stopped"}:
            self._auto_run = False
        else:
            self._schedule_tick()

    def _cancel_timer(self):
        if self._timer is not None:
            self.after_cancel(self._timer)
            self._timer = None

    def queue_event(self):
        if not self.engine:
            messagebox.showinfo("Load a workload", "Load tasks or the overrun demo first.", parent=self)
            return
        try:
            at = self.simulation_start + timedelta(minutes=float(self.event_offset.get()))
            kind = self.event_kind.get()
            if kind == "arrival":
                duration = float(self.event_value.get())
                deadline_offset = float(self.event_deadline.get())
                task = {
                    "id": str(uuid.uuid4()),
                    "name": self.new_task_name.get().strip(),
                    "arrival_time": at,
                    "deadline": self.simulation_start + timedelta(minutes=deadline_offset),
                    "estimated_execution_min": duration,
                    "priority": "Medium",
                }
                self.engine.queue_arrival(task)
                self.scenario_events = self.engine.scenario_inputs()["events"]
                self.scenario_tasks.append(task)
                self._refresh_target_choices()
            else:
                label = self.target_task.get()
                if label not in self._task_labels:
                    raise ValueError("Choose a target task.")
                payload = {"task_id": self._task_labels[label]}
                if kind == "overrun":
                    payload["additional_min"] = float(self.event_value.get())
                elif kind == "deadline_change":
                    payload["deadline"] = self.simulation_start + timedelta(
                        minutes=float(self.event_deadline.get())
                    )
                self.engine.schedule_event(at, kind, **payload)
                self.scenario_events = self.engine.scenario_inputs()["events"]
        except (ValueError, TypeError) as error:
            messagebox.showerror("Unable to queue event", str(error), parent=self)
            return
        self._render_state(self.engine.snapshot())

    def _render_state(self, snapshot):
        self.clock_text.set(
            f"{snapshot['current_time'].strftime('%H:%M:%S')}  ·  {snapshot['status'].upper()}"
        )
        if snapshot["running_task_id"]:
            task = next(item for item in snapshot["tasks"] if item["id"] == snapshot["running_task_id"])
            self.cpu_text.set(f"CPU running  ·  {task['name']}")
        elif snapshot["cpu_state"] == "switching":
            self.cpu_text.set("CPU switching context")
        else:
            self.cpu_text.set("CPU idle")

        self.task_table.delete(*self.task_table.get_children())
        for task in snapshot["tasks"]:
            self.task_table.insert(
                "",
                "end",
                iid=task["id"],
                values=(
                    task["name"],
                    task["state"],
                    f"{task['remaining_min']:.1f}",
                    task["deadline"].strftime("%H:%M"),
                ),
            )
        self.timeline.delete(*self.timeline.get_children())
        task_by_id = {item["id"]: item for item in snapshot["tasks"]}
        for interval in snapshot["cpu_timeline"]:
            task = task_by_id.get(interval["task_id"])
            missed = task["missed"] if task else False
            self.timeline.insert(
                "",
                "end",
                values=(
                    interval["start"].strftime("%H:%M:%S"),
                    interval["end"].strftime("%H:%M:%S"),
                    interval["kind"].replace("_", " ").title(),
                    task["name"] if task else "—",
                    task["deadline"].strftime("%H:%M") if task else "—",
                    f"{interval['duration_min']:.1f}",
                ),
                tags=("missed",) if missed else (),
            )
        self.event_table.delete(*self.event_table.get_children())
        for event in snapshot["pending_events"]:
            task = task_by_id.get(event.get("task_id"))
            payload_task = event.get("task", {})
            self.event_table.insert(
                "",
                "end",
                values=(
                    event["at"].strftime("%H:%M:%S"),
                    event["kind"].replace("_", " ").title(),
                    task["name"] if task else payload_task.get("name", "—"),
                ),
            )
        decision_lines = [item["explanation"] for item in snapshot["decisions"][-5:]]
        event_lines = [item["message"] for item in snapshot["events"][-5:]]
        lines = event_lines + decision_lines
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("1.0", "\n".join(lines) if lines else "No events or scheduling decisions yet.")
        self.log.configure(state="disabled")
        if snapshot["status"] in {"completed", "stopped"}:
            metrics = snapshot["metrics"]
            self.forecast_text.set(
                f"Finished: {metrics['tasks_completed']} completed, "
                f"{metrics['deadline_misses']} missed deadline(s), "
                f"{metrics['cpu_utilization'] * 100:.1f}% useful CPU utilization."
            )
        elif snapshot["status"] == "ready":
            self.forecast_text.set("Ready. Start or step through the event-driven workload.")
        else:
            self.forecast_text.set(
                "Simulation is active. Analyze remaining runs a deterministic policy projection."
            )

    def analyze_remaining(self):
        if not self.engine:
            messagebox.showinfo("Load a workload", "Load tasks or the overrun demo first.", parent=self)
            return
        self._run_background("forecast", self.engine.remaining_workload_forecast)

    def compare_policies(self):
        if not self.engine:
            messagebox.showinfo("Load a workload", "Load tasks or the overrun demo first.", parent=self)
            return
        scenario = self.engine.scenario_inputs()
        self._run_background(
            "experiment",
            lambda: run_counterfactual(
                scenario["tasks"],
                start_time=scenario["start_time"],
                events=scenario["events"],
                context_switch_overhead_min=scenario["context_switch_overhead_min"],
            ),
        )

    def _run_background(self, operation, function):
        if self._worker_running:
            return
        self._worker_running = True
        self.forecast_text.set(
            "Comparing policies in a background run…"
            if operation == "experiment"
            else "Projecting the remaining workload in the background…"
        )

        def worker():
            try:
                self._worker_queue.put((operation, function(), None))
            except Exception as error:
                self._worker_queue.put((operation, None, error))

        threading.Thread(target=worker, daemon=True).start()
        self._poll_job = self.after(50, self._poll_background_result)

    def _poll_background_result(self):
        self._poll_job = None
        try:
            operation, result, error = self._worker_queue.get_nowait()
        except queue.Empty:
            self._poll_job = self.after(50, self._poll_background_result)
            return
        self._worker_running = False
        if error:
            messagebox.showerror("Analysis failed", str(error), parent=self)
            return
        if operation == "forecast":
            self.forecast_text.set(result["explanation"])
            return
        experiment = result
        try:
            db.save_simulation_experiment(self.conn, experiment)
        except (sqlite3.Error, ValueError, TypeError) as error:
            messagebox.showerror("Unable to save experiment", str(error), parent=self)
            return
        self._show_experiment(experiment)

    def _show_experiment(self, experiment):
        self.last_experiment = experiment
        self.results_table.delete(*self.results_table.get_children())
        for policy, result in experiment["runs"].items():
            metrics = result["metrics"]
            self.results_table.insert(
                "",
                "end",
                iid=f"current|{experiment['id']}|{policy}",
                values=(
                    policy,
                    metrics["tasks_completed"],
                    metrics["deadline_misses"],
                    f"{metrics['cpu_utilization'] * 100:.1f}",
                    f"{metrics['total_tardiness_min']:.1f}",
                    " → ".join(experiment["comparisons"][policy]["execution_order"]),
                ),
            )
        self.forecast_text.set(
            "Policy comparison completed from the same task/event inputs. "
            f"Results saved as {experiment['id'][:8]}."
        )

    def _load_saved_experiments(self):
        for row in self.results_table.get_children():
            self.results_table.delete(row)
        try:
            summaries = db.get_simulation_experiment_summaries(self.conn, limit=5)
        except sqlite3.Error as error:
            messagebox.showerror("Unable to load experiment history", str(error), parent=self)
            return
        for summary in summaries:
            for policy in summary["policies"]:
                self.results_table.insert(
                    "",
                    "end",
                    iid=f"saved|{summary['id']}|{policy}",
                    values=(
                        policy,
                        summary["tasks_completed"][policy],
                        summary["deadline_misses"][policy],
                        f"{summary['cpu_utilization'][policy] * 100:.1f}",
                        "—",
                        "Open saved experiment to inspect",
                    ),
                )

    def _show_selected_metrics(self, _event=None):
        selected = self.results_table.selection()
        if not selected:
            return
        parts = selected[0].split("|", 2)
        if len(parts) != 3:
            return
        source, experiment_id, policy = parts
        if source == "current":
            experiment = self.last_experiment
        else:
            stored = db.get_simulation_experiment(self.conn, experiment_id)
            if stored is None:
                return
            experiment = stored["result"]
        metrics = experiment["runs"][policy]["metrics"]
        self.forecast_text.set(
            f"{policy}: {metrics['tasks_completed']} completed; "
            f"{metrics['deadline_misses']} deadline misses "
            f"({metrics['deadline_miss_rate'] * 100:.1f}%); "
            f"tardiness {metrics['total_tardiness_min']:.1f} min; "
            f"maximum lateness {metrics['maximum_lateness_min']:.1f} min; "
            f"average waiting {metrics['average_waiting_min']:.1f} min; "
            f"turnaround {metrics['average_turnaround_min']:.1f} min; "
            f"response {metrics['average_response_min']:.1f} min; "
            f"CPU execution {metrics['cpu_execution_min']:.1f} min, "
            f"idle {metrics['cpu_idle_min']:.1f} min, "
            f"switching {metrics['context_switch_min']:.1f} min; "
            f"{metrics['preemption_count']} preemption(s)."
        )
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert(
            "1.0",
            "\n".join(item["explanation"] for item in experiment["runs"][policy]["decisions"])
            or "No scheduling decisions were recorded.",
        )
        self.log.configure(state="disabled")

    def destroy(self):
        self.shutdown()
        super().destroy()

    def shutdown(self):
        self._auto_run = False
        self._cancel_timer()
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None
