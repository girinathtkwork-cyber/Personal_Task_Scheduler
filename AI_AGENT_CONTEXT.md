# Chronos OS — AI Agent Implementation Context

This is the current implementation handoff for coding agents. It supersedes
older plans where they disagree with the source. The app is an educational
single-user desktop scheduler and user-space simulator; it is not a modified
operating-system kernel and does not provide real-time guarantees.

## Product summary

The app has two distinct areas:

1. **Task planner:** SQLite-backed task entry and CRUD, the existing EDF/FCFS
   back-to-back schedule, task deadline feasibility warning, timeline, and
   deadline-miss metrics.
2. **Simulation lab:** a deterministic event-driven single-CPU simulation with
   execution states, simulated arrivals/deadlines, task events, preemption,
   context-switch overhead, per-policy counterfactual experiments, metrics,
   explanations, and persisted results.

The planner scheduling rules and simulation policies are separate. Keep
scheduling logic out of Tkinter and keep database writes in the persistence
layer. The GUI has been redesigned to be resizable and card-based; its visual
changes must not silently alter scheduler semantics.

## Repository layout

```text
.
|-- AI_AGENT_CONTEXT.md
|-- BACKEND_README.md
|-- MODULE_PLAN_Frontend_Backend.md
|-- PROJECT_CONTEXT_AND_BUILD_SPEC.md
|-- README.md
|-- data/
|   |-- tasks.db
|-- src/task_scheduler/
|   |-- core/
|   |   |-- scheduler.py
|   |   |-- schedulability.py
|   |   |-- rescheduler.py
|   |-- gui/
|   |   |-- app.py
|   |   |-- task_form.py
|   |   |-- gantt_view.py
|   |   |-- simulation_panel.py
|   |-- persistence/
|   |   |-- db.py
|   |-- simulation/
|       |-- engine.py
|       |-- experiments.py
|-- tests/
    |-- unit/
    |   |-- test_scheduler.py
    |   |-- test_schedulability.py
    |   |-- test_rescheduler.py
    |   |-- test_db.py
    |   |-- test_simulation_engine.py
    |   |-- test_simulation_experiments.py
    |-- integration/
        |-- test_backend_workflow.py
```

No third-party packages or package manifest are required. Tkinter, SQLite,
datetime, and the other dependencies are Python standard-library modules.

## Task planner architecture

### Task record

```python
{
    "id": "task-1",
    "name": "Finish OS report",
    "deadline": datetime(...),       # naive datetime
    "duration_min": 60,              # positive int, bool rejected
    "priority": "High",              # High | Medium | Low
    "status": "pending",             # pending | in_progress | done
    "created_at": datetime(...),     # naive datetime
}
```

The planner's schedule result is a sequence of
`{task_id, task_name, start, end}` entries.

### Scheduling behavior

- `core.scheduler.generate_schedule(tasks, algorithm="EDF", start_time=None)`
  schedules only pending tasks and places them back-to-back.
- Planner EDF sorts by deadline, priority (`High`, `Medium`, `Low`), then
  `created_at`.
- Planner FCFS sorts by `created_at` only.
- `count_deadline_misses()` treats completion exactly at a deadline as success.
- `core.schedulability.check_schedulability(tasks, now=None)` applies EDF
  ordering to pending tasks and reports projected at-risk task IDs and a
  message. This is a simple single-CPU, no-breaks feasibility estimate.
- `core.rescheduler` provides add/edit/delete/status/done mutation wrappers,
  rebuilds state, computes both planner algorithm metrics, and returns
  `tasks`, `pending_tasks`, `schedule`, `schedulability`, and `comparison`.

The existing task status operations live in the backend and are exposed in the
planner UI through the form and selected-task buttons. There is no explicit
in-progress button in the current GUI.

## Simulation engine

### Public surface and inputs

`task_scheduler.simulation.SimulationEngine` is the isolated engine.
`simulation.engine` exports policy/event constants. Task input:

```python
{
    "id": "job-a",
    "name": "Report",
    "arrival_time": datetime(...),
    "deadline": datetime(...),                  # absolute, naive datetime
    "estimated_execution_min": 25,              # positive finite number
    "priority": "High",                         # optional; defaults Medium
}
```

`duration_min` and `created_at` are accepted as aliases for execution time and
arrival for planner integration. Pass `start_time` explicitly for reproducible
runs (the engine otherwise derives it from arrivals, or wall time for an empty
workload).

Methods:

- `start()`, `pause()`, `resume()`
- `step()` / `run_until_next_event()` (advance one meaningful boundary)
- `run_to_completion()` (synchronous helper; use in a worker for substantial
  workloads)
- `reset()` (replays original tasks and all queued external events)
- `schedule_event(at, kind, **payload)` and `queue_arrival(task)`
- `snapshot()`, `metrics()`, `remaining_workload_forecast()`
- `scenario_inputs()` returns independent replay inputs for experiments.

The event queue is ordered by simulated timestamp, event priority, then stable
insertion sequence. At one timestamp: complete CPU work first; apply cancel;
apply overrun/deadline-change; apply interrupt/resume; process arrivals; record
unfinished deadline misses; then dispatch. Completion at the exact deadline
therefore wins over a same-time cancellation or miss.

Task state starts `NEW`, becomes `READY` on arrival, then `RUNNING` when
dispatched. Preempted work returns to `READY`; interruption uses `INTERRUPTED`;
completion and cancellation are terminal. An interrupted task with no future
resume remains unfinished and the simulation reports a stopped (not completed)
run.

### Simulation policies

`POLICIES` in `simulation.engine`:

- `EDF`: non-preemptive earliest deadline; deadline ties use priority, arrival,
  then ID.
- `EDF-P`: preemptive EDF with the same tie-breaks.
- `FCFS`: non-preemptive arrival order, then ID.
- `SJF`: non-preemptive shortest current estimated execution, then arrival/ID.
- `SRTF`: preemptive shortest remaining execution, then arrival/ID.

Only `EDF` and `FCFS` are in the original planner. Do not conflate planner EDF
with the separate preemptive simulation policy `EDF-P`.

### Dynamic events and recovery

Supported event kinds: `arrival`, `overrun`, `cancel`, `deadline_change`,
`interrupt`, and `resume`. Event processing is owned by the engine; the GUI
queues inputs and renders the returned state. Scheduling-relevant changes
trigger a fresh policy decision, which records the timestamp, selected task,
eligible task IDs/deadlines/remaining times, policy, criterion, trigger, and
human-readable explanation.

`remaining_workload_forecast()` clones the current simulation, completes that
projection under the same policy/configuration/events, and returns the predicted
misses. It distinguishes tasks individually unable to meet the deadline from a
policy projection that predicts misses even though no task is individually
impossible. This is a policy projection, not a mathematical optimality proof.

### Metrics

`SimulationEngine.metrics()` returns:

- `tasks_total`, `tasks_completed`, `deadline_misses`,
  `deadline_miss_rate` (cancelled tasks excluded from denominator)
- `total_tardiness_min`: sum of positive completion lateness
- `maximum_lateness_min`: maximum signed lateness among completed tasks
- `average_waiting_min`: time in READY, over completed tasks
- `average_turnaround_min`: completion minus arrival
- `average_response_min`: first start minus arrival
- `cpu_utilization`, `cpu_execution_min`, `cpu_idle_min`,
  `context_switch_min`, `context_switch_count`, `preemption_count`

Execution and overhead use minutes; overhead is not useful CPU execution.
Waiting/response/turnaround are averages over completed tasks; cancelled and
unfinished tasks do not contribute.

## Experiments and persistence

`simulation.experiments.run_counterfactual()` creates a new engine for each
policy, deep-copies the same task/event inputs, runs independently, and returns
actual metrics, task results, timeline, event log, decisions, execution order,
and verified prevented-miss deltas relative to the requested baseline.

`create_overrun_demo()` builds a workload feasible without an overrun and a
20-minute overrun event at simulated minute 5.

The default SQLite database is `data/tasks.db`, resolved relative to source.
Existing tables are `tasks` and planner `history`. App initialization adds
simulation tables with `CREATE TABLE IF NOT EXISTS`:

- `simulation_experiments`: replay configuration and complete result JSON
- `simulation_events`: per-policy processed event records
- `simulation_decisions`: per-policy structured scheduling decisions

Foreign keys cascade from an experiment to its records. This schema addition
does not alter or drop existing task/history tables. Tests use temporary
databases; do not use destructive resets for this project.

## GUI integration

`gui.app.App` contains two notebook pages:

- **Task planner:** task form, EDF/FCFS selector, schedule Gantt, warning,
  editable task table, complete/delete actions, selected details, comparison
  counts.
- **Simulation lab:** policy/context switch settings, task/demo loading,
  start/pause/resume/step/run/reset, event injection/queue, current task state,
  CPU intervals including idle/switch time, deadline-miss marking, log and
  decision explanations, remaining-work analysis, policy experiment results.

The resizable Gantt uses an 08:00–22:00 clock scale with task urgency color and
hover details. Simulation progression is driven through short Tk `after`
callbacks. Counterfactuals and feasibility projections run in worker threads;
Tk widget updates and SQLite writes occur on the main thread. `WM_DELETE_WINDOW`
stops timers and closes the connection.

`load_overrun_demo()` intentionally loads only the feasible workload. The UI
pre-fills the overrun parameters, but the user must queue the event. This makes
the before/after feasibility transition observable.

## Run and test

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m task_scheduler.gui.app
```

Test directories are run separately:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests\unit -p "test_*.py" -v
python -m unittest discover -s tests\integration -p "test_*.py" -v
```

Tests now inject fixed reference times when checking persistence/deadlines,
instead of depending on the machine's wall clock. The latest verified run for
this implementation was **44 unit tests passed and 1 integration test passed**.
GUI construction and the overrun-demo flow were separately smoke-tested with a
temporary database.

## Source-of-truth and constraints

- `README.md` is the user-facing run/features guide.
- `BACKEND_README.md` documents the original task-planner backend.
- `MODULE_PLAN_Frontend_Backend.md` and
  `PROJECT_CONTEXT_AND_BUILD_SPEC.md` are historical plans, not proof of
  current UI functionality.
- No web server, authentication, cloud sync, periodic-task model, multiple CPU,
  deadlock/resource allocation, or kernel integration is implemented.
- Preserve planner APIs; add simulation-specific behavior to `simulation/`.
- Keep any future UI-only visual enhancement isolated from simulation and
  scheduling rules.
