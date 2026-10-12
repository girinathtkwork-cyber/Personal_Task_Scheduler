# Chronos OS — Personal Task Scheduler and Simulation Lab

Chronos is a Python/Tkinter desktop app for planning personal tasks and
experimenting with real-time CPU scheduling ideas. Its task planner preserves
the original EDF scheduler and adds a separate, deterministic, event-driven
simulation lab for execution overruns, arrivals, preemption, and policy
comparison.

**This is a user-space educational simulation, not an operating-system kernel
or a real-time guarantee.** Simulated time advances in event-sized jumps without
waiting for the corresponding wall-clock time.

## Features

### Task planner

- Add, edit, delete, and complete locally persisted tasks.
- Sort pending work with EDF or FCFS.
- Inspect the schedule on a Gantt-like timeline, with urgency colors and
  hover/selection details.
- See deadline feasibility warnings and EDF/FCFS deadline-miss counts.
- Animate schedule changes after a task is added, completed, or deleted.

### Simulation lab

- Simulate one CPU with task arrivals, absolute deadlines, estimated execution
  time, remaining time, CPU occupancy, events, decisions, and deadline misses.
- Start, pause, resume, step to the next event, run to completion, and reset.
- Inject task arrivals, execution overruns, cancellations, deadline changes,
  interruptions, and resumptions.
- Configure context-switch overhead in simulated minutes.
- Inspect the event queue, task states, CPU timeline, explanations, and computed
  metrics.
- Run isolated counterfactuals across scheduling policies and persist experiment
  inputs/results without replacing or rewriting task records.
- Load a predefined overrun demonstration whose initial workload is feasible.

## Scheduling policies

Policies used by the simulator are separate from the task planner's original
schedule API:

| Policy | Preemptive? | Selection rule |
| --- | --- | --- |
| `EDF` | No | Earliest absolute deadline; ties use priority, arrival, then task ID. |
| `EDF-P` | Yes | Earliest absolute deadline; ties use priority, arrival, then task ID. |
| `FCFS` | No | Earliest arrival, then task ID. |
| `SJF` | No | Shortest estimated execution time, then arrival and task ID. |
| `SRTF` | Yes | Shortest remaining execution time, then arrival and task ID. |

The ordinary planner continues to support its existing `EDF` and `FCFS`
algorithms. `EDF` in the simulator is non-preemptive; `EDF-P` is the separate
preemptive variant.

## Simulation model

Each simulation task provides:

```python
{
    "id": "task-1",
    "name": "Write report",
    "arrival_time": datetime(...),              # naive datetime
    "deadline": datetime(...),                  # absolute, naive datetime
    "estimated_execution_min": 30,              # positive number
    "priority": "High",                         # High | Medium | Low
}
```

Execution time and context-switch overhead use simulated minutes. A simulation
task follows `NEW -> READY -> RUNNING -> READY -> COMPLETED`; it may instead be
`INTERRUPTED` or `CANCELLED`. A task that remains interrupted without a future
resume event causes the run to stop with that task unfinished.

At a shared timestamp, the engine processes events deterministically:

1. Complete work whose remaining execution reached zero.
2. Apply cancellation, overrun/deadline-change, and interrupt/resume events.
   Events with equal priority retain insertion order.
3. Process arrivals.
4. Mark deadlines missed for unfinished work.
5. Re-evaluate the ready queue and record a scheduling decision.

The engine is single-CPU and non-parallel. It models no task dependencies,
periodic releases, I/O blocking, multiple resources, or operating-system kernel
behavior. “Feasibility” from the simulation is a projection under the selected
policy and configuration, not a proof of global optimality. An individually
impossible task is one whose remaining execution cannot finish by its deadline
even if it ran alone from the current time (or its arrival time).

## Metrics

Metrics are calculated from simulated results and use minutes unless noted:

- **Tasks completed:** tasks reaching `COMPLETED`.
- **Deadline misses / rate:** number of tasks that passed their deadlines
  unfinished; rate denominator excludes cancelled tasks.
- **Total tardiness:** sum of positive completion lateness for completed tasks.
- **Maximum lateness:** greatest signed `completion - deadline` among completed
  tasks. Negative means every completed task finished early.
- **Waiting time:** total time spent `READY`, averaged over completed tasks.
- **Turnaround time:** `completion - arrival`, averaged over completed tasks.
- **Response time:** `first start - arrival`, averaged over completed tasks.
- **CPU utilization:** useful execution time divided by total elapsed simulated
  time. Context-switch time is not useful execution.
- **CPU idle time:** time with neither execution nor a context switch.
- **Context switches:** charged transitions between different tasks after the
  initial dispatch.
- **Preemptions:** times a running task is displaced by the selected
  preemptive policy.

Cancelled and unfinished tasks do not contribute to completion-time averages.

## Requirements

- Python 3.10+ recommended.
- Tkinter must be available in the Python installation.
- No third-party Python packages are required.

There is no `requirements.txt` or package installer configuration. The project
uses a `src/` layout, so commands below set `PYTHONPATH`.

## Run the application

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m task_scheduler.gui.app
```

The task planner's database is `data/tasks.db`. The GUI creates the task/history
tables and additive simulation tables if needed. Simulation runs are stored
separately in `simulation_experiments`, `simulation_events`, and
`simulation_decisions`; existing task records are not migrated or deleted.

## Try the overrun demonstration

1. Open the **Simulation lab** tab.
2. Select **Overrun demo**. The workload is initially feasible.
3. Click **Analyze remaining** to inspect the baseline projection.
4. The event form is prepared for a 20-minute overrun of the report at simulated
   minute 5. Click **Queue event**.
5. Click **Start / resume** or **Step to event**. The engine applies the event,
   recalculates its schedule, and records explanations and deadline misses.
6. Click **Analyze remaining** again, then **Compare policies** to run the same
   workload and event sequence independently under each policy.
7. Select a policy result to inspect its metrics and scheduling explanations.

## Run tests

The project uses the standard-library `unittest` runner. Run unit and
integration tests separately from the repository root:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests\unit -p "test_*.py" -v
python -m unittest discover -s tests\integration -p "test_*.py" -v
```

All tests use fixed simulated/reference times and temporary databases; they do
not depend on the host's current date or write to the default task database.

Backend demonstrations can also run without starting Tkinter:

```powershell
$env:PYTHONPATH = "src"
python -m task_scheduler.core.scheduler
python -m task_scheduler.core.schedulability
python -m task_scheduler.persistence.db
```

## Architecture

```text
src/task_scheduler/
|-- core/
|   |-- scheduler.py       # Existing EDF/FCFS schedule generation
|   |-- schedulability.py  # Existing task-plan feasibility warning
|   |-- rescheduler.py    # Existing CRUD-to-schedule orchestration
|-- persistence/
|   |-- db.py              # Task/history storage and simulation result storage
|-- simulation/
|   |-- engine.py          # Deterministic event-driven single-CPU engine
|   |-- experiments.py     # Independent counterfactual runs and demo scenario
|-- gui/
    |-- app.py             # Planner shell, task management, visual styling
    |-- task_form.py       # Task create/edit form
    |-- gantt_view.py      # Resizable planner timeline and transitions
    |-- simulation_panel.py# Simulation controls, events, timeline, analysis
```

Scheduling/simulation decisions live outside the GUI. SQLite writes stay in the
persistence module. Counterfactual policy runs execute in a worker thread; GUI
updates and database writes remain on Tkinter's main thread.

## Documentation

- [AI_AGENT_CONTEXT.md](./AI_AGENT_CONTEXT.md) is the implementation handoff
  with current APIs, source-of-truth notes, and known limitations.
- [BACKEND_README.md](./BACKEND_README.md) describes the original task-planner
  backend contracts.
- `MODULE_PLAN_Frontend_Backend.md` and
  `PROJECT_CONTEXT_AND_BUILD_SPEC.md` are original project plans; planned
  features in those documents are not necessarily implemented.
