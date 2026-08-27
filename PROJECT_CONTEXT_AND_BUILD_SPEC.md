# Personal Task Scheduler — Real-Time EDF Scheduling
### Complete Project Context & Build Spec (for AI coding agent / developer handoff)

---

## 1. Project Summary

A **desktop application** (Python, Tkinter) that schedules a user's daily tasks using **real-time operating system scheduling algorithms** instead of a plain to-do list. The core is **EDF (Earliest Deadline First)** — the user enters tasks with deadlines, durations, and priorities, and the app automatically builds an optimal timetable, checks whether all deadlines are actually achievable (schedulability analysis), and re-schedules live when the task list changes mid-day.

This is an academic project (Operating Systems course, university level) built by a 2-person team over ~4 weeks, but should be built as a genuinely usable, polished, demo-ready application — not a toy simulator.

## 2. Why this project exists / academic context

Maps to an Operating Systems syllabus module on **"CPU Scheduling and Deadlocks"**, specifically:
- Scheduling Criteria and Scheduling Algorithms
- Real-Time CPU Scheduling
- (Deadlock content exists in the syllabus but is explicitly OUT OF SCOPE for this project — see Section 6.)

The differentiator from typical student projects (which usually just simulate FCFS/SJF/RR and print stats) is: this is a **real, usable tool** applying real-time scheduling theory to personal productivity, with a live, animated, visual demo — not a console dump of numbers.

## 3. Core Concept — How the app works

1. User adds tasks: `name`, `deadline` (date+time), `duration` (minutes), `priority` (High/Medium/Low)
2. The scheduler runs **EDF**: sorts pending tasks by nearest deadline, places them back-to-back on today's timeline starting from the current time
3. Before finalizing, it runs a **schedulability check**: walks through cumulative required time vs. time remaining before each deadline, and flags if the plan is infeasible (i.e., not all deadlines can physically be met given total workload)
4. If a new urgent task is added mid-day, the app **re-schedules automatically** — only tasks not yet started/completed are re-arranged (already in-progress work isn't retroactively disturbed)
5. A comparison mode runs the same day's tasks through **FCFS** (naive, in-order scheduling) alongside EDF, to visually demonstrate EDF's advantage in deadline-miss rate — this is the project's "evaluation" / results section

## 4. Explicit Scope Boundaries

### IN SCOPE
- Single-user only
- EDF scheduling algorithm
- FCFS scheduling algorithm (comparison baseline only, not primary mode)
- Schedulability analysis (feasibility check before committing to a schedule)
- Dynamic re-scheduling on task add/edit/delete
- Local persistence (SQLite)
- Tkinter desktop GUI with a visual Gantt-style timeline
- EDF vs FCFS comparison view

### OUT OF SCOPE (explicitly, do not add unless asked)
- Multi-user / multi-person scheduling (was considered and rejected — keep single-user)
- Resource-conflict / deadlock-avoidance features (e.g. Banker's algorithm for shared resources) — was considered and rejected, keep pure EDF scheduling
- Login / authentication
- Cloud sync / networking of any kind
- Mobile or responsive design (fixed-size desktop window is fine)
- Notifications/reminders daemon
- Drag-and-drop task editing
- Rate Monotonic Scheduling or other RTOS algorithms beyond EDF/FCFS (mentioned as a stretch idea originally, cut for scope control)

If a feature isn't listed under IN SCOPE, treat it as excluded unless the user explicitly asks to add it.

## 5. Target audience & demo priorities

This will be demoed live to evaluators (professor/review panel) in an academic review setting. Priorities, in order:
1. **It must actually run and work reliably** — no crashes during a live demo
2. **The Gantt timeline visual is the centerpiece** — a horizontal timeline with color-coded task blocks, not a plain text/table list
3. **The reschedule must be visibly animated** — when a task is added and the schedule changes, blocks should visibly shift (even simple incremental redraws), not silently snap to a new state
4. **The schedulability warning must be unmissable** — a clear visual banner/alert, not subtle text
5. **The EDF vs FCFS comparison must be visual**, not just numbers in a table — ideally both timelines rendered and compared side by side

Design the code with the live demo narrative in mind: *load a realistic day → add an urgent task on purpose → show the infeasibility warning → resolve it → watch the schedule reshuffle live → show the EDF-vs-FCFS comparison proving EDF performs better.*

## 6. Decisions already made (do not re-litigate these)

- **Single-user, not multi-user.** A "2-person team as 2 CPU cores" load-balancing idea was proposed and explicitly rejected as too complex / not resonating with the team.
- **No deadlock/resource-conflict feature.** A "shared limited resource" deadlock-avoidance feature (Banker's-algorithm-style) was proposed and explicitly rejected in favor of keeping scope simple.
- **Frontend is Tkinter desktop app**, not web (Flask was considered and rejected — team confirmed desktop specifically).
- **Team has zero prior desktop app development experience.** Code and instructions should not assume familiarity with GUI frameworks; prefer simple, well-commented approaches over clever/terse ones.
- **Algorithm scope is EDF + FCFS only.** Rate Monotonic Scheduling and other RTOS algorithms were mentioned as possible stretch ideas but are not committed scope.

## 7. Technical Architecture

```
┌─────────────────────┐      ┌──────────────────────┐      ┌────────────────┐
│   Tkinter GUI         │─────▶│  Scheduler Engine      │─────▶│  SQLite DB       │
│  (app.py)              │◀─────│  (scheduler.py,        │◀─────│  (db.py,          │
│  - task entry form      │      │   schedulability.py)   │      │   tasks.db)        │
│  - Gantt canvas          │      │  - EDF logic            │      └────────────────┘
│  - comparison view        │      │  - FCFS logic            │
└─────────────────────┘      │  - feasibility check     │
                              └──────────────────────┘
```

Key architectural principle: **the scheduling logic has zero GUI dependencies.** `scheduler.py` and `schedulability.py` should be pure Python, testable and runnable standalone via console/print statements, completely decoupled from Tkinter. This matters both for code quality and because in the academic report/viva, this is the file that represents "the OS theory content" and should be presentable in isolation.

## 8. File structure

```
task-scheduler/
├── scheduler.py          # EDF + FCFS scheduling logic (pure Python, no GUI)
├── schedulability.py      # Feasibility/schedulability checking (pure Python)
├── db.py                  # SQLite persistence layer
├── app.py                 # Tkinter GUI — main entry point
├── gantt_view.py           # Canvas-based Gantt timeline rendering (used by app.py)
├── comparison_view.py       # EDF vs FCFS comparison rendering
├── tasks.db                # SQLite database file (generated at runtime)
├── README.md                # This file / project documentation
└── requirements.txt          # Python dependencies (should be minimal — stdlib mostly)
```

## 9. Data model

### Task object (shape used throughout the app)
```python
{
    "id": str,                # unique id, e.g. uuid4 hex
    "name": str,               # task name, e.g. "Finish OS report"
    "deadline": datetime,        # when it must be done by
    "duration_min": int,          # estimated duration in minutes
    "priority": str,               # "High" | "Medium" | "Low"
    "status": str,                   # "pending" | "in_progress" | "done"
    "created_at": datetime            # for FCFS ordering
}
```

### Timetable entry (output of the scheduler)
```python
{
    "start": datetime,
    "end": datetime,
    "task_id": str,
    "task_name": str
}
```

### SQLite schema (`db.py`)
```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    deadline TEXT NOT NULL,        -- ISO 8601 datetime string
    duration_min INTEGER NOT NULL,
    priority TEXT NOT NULL,         -- 'High' / 'Medium' / 'Low'
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);

CREATE TABLE history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    algorithm TEXT NOT NULL,        -- 'EDF' or 'FCFS'
    tasks_scheduled INTEGER,
    deadlines_missed INTEGER
);
```

`history` should be populated every time a schedule is generated — log outcomes for BOTH algorithms each time (even though only EDF is shown live to the user), so the comparison view always has real data without extra user action.

## 10. Core algorithm specifications

### `generate_schedule(tasks, algorithm="EDF") -> list[timetable_entry]`
- Filter to only `status == "pending"` tasks (in-progress/done tasks are not re-arranged)
- **EDF**: sort by `deadline` ascending (nearest deadline first); tie-break by `priority` (High > Medium > Low), then by `created_at`
- **FCFS**: sort by `created_at` ascending (ignore deadline/priority entirely — this is the "naive" baseline)
- Place tasks back-to-back on the timeline starting from the current time (or start of day if scheduling for a future day), each occupying `duration_min` minutes in sequence
- Return the resulting list of timetable entries

### `check_schedulability(tasks) -> dict`
- Sort pending tasks by deadline ascending
- Walk through cumulative duration; at each task, check if `current_time + cumulative_duration_so_far > task.deadline`
- If so, that task (and any after it, potentially) is at risk
- Return: `{"feasible": bool, "at_risk_tasks": list[task_id], "message": str}`
- The `message` should be human-readable and specific, e.g. "You will miss 'Gym' unless you free up 45 minutes elsewhere" — this message is what gets displayed in the UI warning banner

### Dynamic re-scheduling
- Triggered on: task added, task edited, task deleted, task marked done
- Re-run `generate_schedule()` on the current pending task set
- Tasks with `status == "in_progress"` or `status == "done"` are excluded from re-arrangement — only pending tasks move

## 11. GUI specifications (Tkinter)

### Task entry form
- Fields: Name (text entry), Deadline (date + time — simple text entry fields are acceptable given time constraints, e.g. separate date and time fields, no need for a fancy date picker widget), Duration in minutes (number entry), Priority (dropdown: High/Medium/Low)
- Submit button: saves task via `db.py`, triggers a full re-schedule and redraw

### Gantt timeline (Canvas-based) — the visual centerpiece
- Horizontal `tk.Canvas`, representing a day (e.g. 8 AM–10 PM, adjust range as needed)
- Each scheduled task rendered as a colored rectangle positioned by `time_to_pixel(start)` to `time_to_pixel(end)`, a linear mapping from clock time to x-coordinate
- **Color coding by urgency** (recomputed on every redraw, not static): red if deadline is under 1 hour away, orange if under 3 hours, green otherwise
- Task name rendered as text inside or below each rectangle

### Reschedule animation
- When the schedule changes (task added/edited/deleted), do not redraw instantly in one frame
- Use incremental redraw steps (e.g. 5-10 steps via `canvas.after(50, redraw_step)`) so blocks visibly shift position rather than snapping — this is a deliberate, important demo requirement, not optional polish

### Infeasibility warning banner
- When `check_schedulability()` returns `feasible: False`, display a clearly visible banner (e.g. red-background `Label` at the top of the window) showing the returned `message`
- Must be visually unmissable — this is a key live-demo moment

### EDF vs FCFS comparison view
- Separate view/tab within the app
- Calls `generate_schedule()` with both `"EDF"` and `"FCFS"` on the same task list
- Renders both timelines (reuse the Gantt-drawing logic) stacked or side-by-side for direct visual comparison
- Optional (only if time permits): a `tk.Scale` slider to "scrub" through the day, highlighting which task is active under each algorithm at that scrubbed time, with deadline-miss moments visually flagged (e.g. flash red)

## 12. Non-functional requirements

- **Reliability over cleverness**: this must not crash during a live demo. Handle edge cases explicitly: empty task list, all tasks infeasible, duplicate deadlines, a task whose duration exceeds the time remaining before its own deadline
- **No unnecessary dependencies**: prefer Python standard library (`tkinter`, `sqlite3`, `datetime`, `uuid`) wherever possible; only add external packages (e.g. `matplotlib`) if there's a clear, specific need, and note the addition
- **Code should be understandable by developers with no prior desktop-app experience** — favor clarity and comments over terse/clever code, since the team maintaining this has never built a Tkinter app before
- **Performance is a non-issue at this scale** — task lists will be roughly 5-20 items; no need to optimize algorithms for large-scale input

## 13. Build order / phased plan

Build in this order, and confirm each phase runs correctly before moving to the next:

**Phase 1 — Core pipeline, console-only**
Implement `generate_schedule()` (EDF only) as pure Python. Test with a hardcoded list of ~5 sample tasks, print the resulting timetable to console. No GUI, no database yet.

**Phase 2 — Persistence + schedulability**
Implement `db.py` (SQLite CRUD for tasks) and `check_schedulability()`. Test that tasks persist across runs and that the feasibility check correctly flags an overloaded day using a hand-constructed test case.

**Phase 3 — Basic GUI**
Build the Tkinter shell: task entry form wired to `db.py`, a button to generate and display the schedule (plain text/list display is fine at this stage — visual polish comes next), and the infeasibility warning banner wired to `check_schedulability()`.

**Phase 4 — Gantt timeline + animation**
Build the Canvas-based Gantt view with urgency color-coding. Wire task add/edit/delete to trigger re-scheduling and an animated (incremental) redraw.

**Phase 5 — Comparison view**
Implement FCFS mode in `generate_schedule()`. Build the comparison view rendering both EDF and FCFS timelines. Populate and use the `history` table.

**Phase 6 — Polish & edge cases**
Handle all edge cases listed in Section 12. Verify the full demo narrative (load a day → add urgent task → see warning → resolve → see live reschedule → see comparison) runs smoothly end to end without errors.

## 14. Suggested Python dependencies

```
# requirements.txt
# Core: stdlib only (tkinter, sqlite3, datetime, uuid) — no install needed for these
# Optional, only if used:
# matplotlib  # only if a more advanced chart is added beyond Canvas-drawn rectangles
```

Keep this minimal. Do not add packages speculatively.

## 15. Definition of done

The project is complete when:
- A user can add, edit, and delete tasks through the GUI, and they persist across app restarts
- EDF scheduling produces a correct, deadline-ordered timetable rendered as a Gantt-style timeline
- The schedulability check correctly identifies and clearly communicates infeasible days
- Adding a task mid-session triggers a visibly animated re-schedule, without disturbing in-progress/done tasks
- A comparison view shows EDF vs FCFS side by side with a visibly different (better) outcome for EDF on a deliberately overloaded test day
- The full demo narrative (Section 5) can be run live without crashing or requiring restarts
