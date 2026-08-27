# TaskEDF — Module-Wise Project Plan
### Frontend / Backend Split, Tested Per Module (2 people, 4 weeks)

## How this split works

Not "one person builds everything backend, then hands off" — that means Person B waits weeks to see anything real, and bugs surface too late to fix comfortably. Instead: the project is broken into **modules** (self-contained features). For each module, **Backend builds the logic piece and Frontend builds the UI piece in parallel**, then you **integrate and test that module together before moving to the next one**.

This means:
- You're never more than one module away from a working, tested feature
- Integration bugs get caught early and often, not all at once in Week 4
- Each module has a clear "done" checkpoint — both of you know exactly when to move on

**Roles for this plan:**
- **Backend** — owns `scheduler.py`, `schedulability.py`, `db.py` (all logic, pure Python, no GUI)
- **Frontend** — owns everything in `gui/` (Tkinter — forms, Canvas timeline, comparison view)

---

## Module 1 — Core Scheduling Pipeline (Week 1)

**What it delivers:** a hardcoded list of tasks gets scheduled by EDF and displayed on screen — the thinnest possible end-to-end slice.

### Backend tasks
- Implement `generate_schedule(tasks, algorithm="EDF")` in `scheduler.py`
- Sort logic: by deadline ascending, tie-break by priority
- Test standalone: hardcode ~5 sample tasks, print the resulting timetable to console, confirm the order is correct
- Deliverable: a working `generate_schedule()` function with a known input/output shape (see Data Model in the main spec doc)

### Frontend tasks
- Build the Tkinter window shell (`app.py`): title, fixed size, basic layout
- Add a placeholder area (a `Label` or `Text` widget) to display a schedule
- Use a **hardcoded fake timetable** (a Python list you make up) to build and test the display — don't wait on Backend's real function
- Deliverable: a window that displays a fake schedule as plain text

### Integration + Test (do together, end of week)
- Wire Frontend's display to call Backend's real `generate_schedule()` instead of fake data
- **Test:** run the app, confirm the on-screen schedule matches what Backend's console version printed — same order, same times
- **Pass criteria:** app opens, shows a real EDF-ordered schedule, no crash

---

## Module 2 — Task Input + Persistence (Week 2)

**What it delivers:** users can add real tasks through a form, and they're saved permanently (persist after closing the app).

### Backend tasks
- Implement `db.py`: SQLite connection, `tasks` table, `add_task()`, `get_all_tasks()`, `update_task_status()`, `delete_task()`
- Implement `check_schedulability(tasks)` in `schedulability.py`
- Test standalone: add a few tasks via a console script, close and reopen the DB connection, confirm tasks persisted correctly. Test schedulability with a hand-built "overloaded day" case and confirm it correctly flags the risk

### Frontend tasks
- Build the task entry form: Name, Deadline (date + time fields), Duration (minutes), Priority (dropdown), Submit button
- Form should collect input into the correct task shape (matching the data model) but can still save to a local Python list for now if Backend's `db.py` isn't ready yet
- Deliverable: a working form that visually collects and lists entered tasks (even before DB is wired in)

### Integration + Test (together)
- Wire the form's Submit button to Backend's `db.py.add_task()`
- Wire app startup to load existing tasks via `get_all_tasks()`
- Wire a warning label to `check_schedulability()`'s output
- **Test:** add 3 tasks, close the app fully, reopen it — confirm all 3 tasks are still there. Add a deliberately overloaded set of tasks — confirm the warning message appears correctly
- **Pass criteria:** tasks survive an app restart; infeasible days are correctly flagged with a visible message

---

## Module 3 — Gantt Timeline + Dynamic Reschedule (Week 3)

**What it delivers:** the plain-text schedule becomes a real visual timeline, and it updates live when tasks change — this is the demo centerpiece.

### Backend tasks
- Add `status` field handling (`pending` / `in_progress` / `done`) so re-scheduling only touches tasks not yet started
- Build the re-schedule trigger logic: whenever a task is added/edited/deleted/marked done, re-run `generate_schedule()` on the current pending set
- Test standalone: simulate adding a new urgent task mid-list via console, confirm only pending tasks get reordered, in-progress/done tasks are untouched

### Frontend tasks
- Build the Canvas-based Gantt timeline (`gantt_view.py`): horizontal bar, colored rectangles positioned by task start/end time
- Implement `time_to_pixel()` mapping and urgency-based coloring (red <1hr, orange <3hr, green otherwise)
- Test standalone: render Backend's Module 1 hardcoded sample timetable as colored bars, confirm positions and colors look correct

### Integration + Test (together — this module needs the most joint time)
- Wire "add task" to trigger Backend's re-schedule function, then trigger Frontend's Canvas redraw
- Add incremental redraw steps (5-10 steps via `canvas.after()`) so the reshuffle is visibly animated, not an instant snap
- **Test:** load a full day's schedule, add one urgent task live, confirm: (1) the timeline visibly animates to the new arrangement, (2) already-in-progress tasks don't move, (3) the new task appears in the correct time-sorted position
- **Pass criteria:** live task addition produces a visibly animated, correctly-ordered reschedule with no crash

---

## Module 4 — EDF vs FCFS Comparison (Week 4, first half)

**What it delivers:** a side-by-side view proving EDF outperforms naive FCFS scheduling — your evaluation/results section.

### Backend tasks
- Implement FCFS mode in `generate_schedule()` (sort by `created_at` instead of deadline)
- Implement `log_history()` in `db.py`, called every time a schedule is generated, logging outcomes for both algorithms
- Test standalone: run the same task list through both EDF and FCFS, confirm FCFS produces a visibly worse (more deadline misses) result on a deliberately unordered task list

### Frontend tasks
- Build `comparison_view.py`: a second view/tab that renders two Gantt timelines stacked (EDF on top, FCFS below), reusing the Canvas-drawing code from Module 3
- Optional if time allows: add a `tk.Scale` slider to scrub through the day, highlighting the active task under each algorithm

### Integration + Test (together)
- Wire the comparison view to call `generate_schedule()` with both algorithms on the same task list
- **Test:** construct one deliberately tight/overloaded day, confirm EDF meets more deadlines than FCFS on the same input, and the visual difference is clearly visible on screen
- **Pass criteria:** comparison view runs without error and visibly demonstrates EDF's advantage

---

## Module 5 — Polish, Edge Cases, Full-System Test (Week 4, second half)

**What it delivers:** a demo-ready, crash-proof app.

### Backend tasks
- Handle edge cases: empty task list, all tasks infeasible, duplicate deadlines, a task whose duration exceeds time remaining before its own deadline
- Add basic input validation (reject negative durations, deadlines in the past, etc.) — decide together whether this lives in Backend (reject before saving) or Frontend (reject in the form) — recommendation: validate in both, but the authoritative check lives in Backend since Frontend input can't be trusted alone

### Frontend tasks
- Polish animation timing, banner visibility, color contrast
- Handle empty-state UI (what the app looks like with zero tasks)
- Make sure form validation gives clear error messages to the user

### Integration + Full System Test (together — this is the real dress rehearsal)
Run through the entire demo narrative end to end, multiple times, together:
1. Load a realistic day
2. Add one deliberately urgent task
3. Confirm the infeasibility warning appears
4. Resolve it (adjust/remove a task)
5. Confirm the timeline reschedules live and animates correctly
6. Switch to the comparison view, confirm EDF vs FCFS displays correctly

**Pass criteria:** this full sequence runs 3 times in a row with zero crashes and zero visual glitches, by both of you, independently.

---

## Testing philosophy for this plan

Every module has 3 built-in checkpoints:
1. **Backend tests their piece standalone** (console print, no GUI) before touching Frontend
2. **Frontend tests their piece standalone** (fake/hardcoded data) before touching Backend's real code
3. **Both test together** once wired, with a specific pass/fail criteria — not "looks fine," an actual repeatable test case

This means bugs get caught at the smallest possible scope — if something breaks during integration, you know it's specifically an integration issue, not a logic issue or a UI issue, because both sides were already verified independently.

## Working together, module by module

- **Sync at the start of each module** (a few minutes): confirm the exact data shape you're both building against (e.g. "timetable entries have `start`, `end`, `task_id`, `task_name`")
- **Work in parallel through the week**, each on your own files
- **Integrate together at the end of each module** — don't skip this even if you're confident it'll "just work," since that's exactly when small mismatches (a date format, a missing field) hide
- **Don't start the next module until the current one passes its test criteria** — a module that "mostly works" becomes a much bigger problem once two more modules are built on top of it
