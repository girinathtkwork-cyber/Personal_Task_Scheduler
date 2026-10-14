"""
gantt_view.py

Module 3 frontend: A Tkinter Gantt chart view for the daily schedule.
Provides a snap-to render method and an animated transition method.
"""

import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime, timedelta

# Constants for the visible range of the Gantt chart (hours)
START_HOUR = 8
END_HOUR = 22
CANVAS_HEIGHT = 190
MIN_VISIBLE_HEIGHT = 118
LEFT_PADDING = 48
RIGHT_PADDING = 18
TASK_TOP = 32
TASK_BOTTOM = 72
TASK_TEXT_Y = (TASK_TOP + TASK_BOTTOM) / 2

class GanttView(tk.Frame):
    def __init__(self, master=None, on_task_hover=None, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(height=CANVAS_HEIGHT)
        self.canvas = tk.Canvas(self, bg="#ffffff", height=CANVAS_HEIGHT, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.task_font = tkfont.Font(family="Segoe UI", size=8, weight="bold")
        
        self.on_task_hover = on_task_hover
        
        # State tracking for animation
        self.current_schedule = []
        self.current_tasks = []
        self.visible_start = None
        self.visible_end = None
        self.animation_job = None
        self.resize_job = None
        self.canvas.bind("<Configure>", self._schedule_resize)

    def _handle_hover(self, task):
        if self.on_task_hover:
            self.on_task_hover(task)

    def _get_time_fraction(self, dt):
        """Map a full date and time onto the currently visible timeline."""
        if self.visible_start is None or self.visible_end is None:
            return 0.0
        span = (self.visible_end - self.visible_start).total_seconds()
        if span <= 0:
            return 0.0
        return min(1.0, max(0.0, (dt - self.visible_start).total_seconds() / span))

    def _set_visible_range(self, schedule):
        if not schedule:
            today = datetime.now().replace(hour=START_HOUR, minute=0, second=0, microsecond=0)
            self.visible_start = today
            self.visible_end = today + timedelta(hours=END_HOUR - START_HOUR)
            return
        first = min(entry["start"] for entry in schedule)
        last = max(entry["end"] for entry in schedule)
        self.visible_start = first.replace(minute=0, second=0, microsecond=0) - timedelta(minutes=30)
        self.visible_end = last.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1, minutes=30)
        if self.visible_end - self.visible_start < timedelta(hours=6):
            midpoint = self.visible_start + (self.visible_end - self.visible_start) / 2
            self.visible_start = midpoint - timedelta(hours=3)
            self.visible_end = midpoint + timedelta(hours=3)

    def time_to_pixel(self, dt):
        """Linear map from a datetime's clock time to an x-coordinate."""
        # Force an update of geometry to ensure width is accurate if called early
        self.update_idletasks()
        width = self.canvas.winfo_width()
        
        # Fallback if canvas is not yet drawn
        if width <= 1:
            width = 680
        
        fraction = self._get_time_fraction(dt)
        return LEFT_PADDING + fraction * max(1, width - LEFT_PADDING - RIGHT_PADDING)

    def _draw_axis(self):
        width = max(self.canvas.winfo_width(), 680)
        height = max(self.canvas.winfo_height(), MIN_VISIBLE_HEIGHT)
        plot_right = width - RIGHT_PADDING
        axis_y = height - 27
        self.canvas.create_line(LEFT_PADDING, axis_y, plot_right, axis_y, fill="#dce4ee")
        start = self.visible_start or datetime.now().replace(hour=START_HOUR, minute=0, second=0, microsecond=0)
        end = self.visible_end or start + timedelta(hours=END_HOUR - START_HOUR)
        span_hours = max(1, (end - start).total_seconds() / 3600)
        step_hours = 1 if span_hours <= 12 else (2 if span_hours <= 36 else 4)
        tick = start.replace(minute=0, second=0, microsecond=0)
        if tick < start:
            tick += timedelta(hours=1)
        while tick <= end:
            x = LEFT_PADDING + (tick - start).total_seconds() / (end - start).total_seconds() * (plot_right - LEFT_PADDING)
            self.canvas.create_line(x, 26, x, axis_y, fill="#edf1f6")
            label = tick.strftime("%m-%d %H:%M" if start.date() != end.date() else "%H:%M")
            self.canvas.create_text(x, axis_y + 13, text=label, fill="#68778d", font=("Segoe UI", 8))
            tick += timedelta(hours=step_hours)
        self.canvas.create_text(
            6,
            16,
            text="TIME",
            anchor="w",
            fill="#68778d",
            font=("Segoe UI Semibold", 8),
        )

    def _schedule_resize(self, _event=None):
        if self.animation_job or self.resize_job:
            return
        self.resize_job = self.after_idle(self._render_after_resize)

    def _render_after_resize(self):
        self.resize_job = None
        if self.current_schedule:
            self.render(self.current_schedule, self.current_tasks)
        else:
            self.canvas.delete("all")
            self._draw_axis()

    def _get_color(self, task, now):
        """Determine task color based on deadline urgency."""
        time_left = task["deadline"] - now
        if time_left < timedelta(hours=1):
            return "#e74c3c" # Red
        elif time_left < timedelta(hours=3):
            return "#f39c12" # Orange
        else:
            return "#2ecc71" # Green

    def _fit_task_name(self, text, width):
        available_width = max(0, int(width) - 10)
        if available_width < self.task_font.measure("..."):
            return ""
        if self.task_font.measure(text) <= available_width:
            return text
        trimmed = text
        while trimmed and self.task_font.measure(f"{trimmed}...") > available_width:
            trimmed = trimmed[:-1]
        return f"{trimmed.rstrip()}..." if trimmed else ""

    def _draw_task_box(self, x1, x2, color, text, task):
        label = self._fit_task_name(text, x2 - x1)
        rect_id = self.canvas.create_rectangle(
            x1,
            TASK_TOP,
            x2,
            TASK_BOTTOM,
            fill=color,
            outline="#174c3b",
            width=2,
        )
        text_id = None
        if label:
            text_id = self.canvas.create_text(
                (x1 + x2) / 2,
                TASK_TEXT_Y,
                text=label,
                fill="#ffffff",
                anchor="center",
                font=self.task_font,
            )
        for item_id in (rect_id, text_id):
            if item_id:
                self.canvas.tag_bind(item_id, "<Enter>", lambda e, t=task: self._handle_hover(t))
                self.canvas.tag_bind(item_id, "<Leave>", lambda e: self._handle_hover(None))

    def render(self, schedule, tasks, now=None):
        """Snaps the schedule onto the canvas, clearing anything previously drawn."""
        if now is None:
            now = datetime.now()
            
        self.current_schedule = schedule
        self.current_tasks = tasks
        self._set_visible_range(schedule)
        
        if self.animation_job:
            self.after_cancel(self.animation_job)
            self.animation_job = None

        self.canvas.delete("all")
        self._draw_axis()
        
        task_dict = {t["id"]: t for t in tasks}
        
        for index, entry in enumerate(schedule):
            task = task_dict.get(entry["task_id"])
            if not task:
                continue
                
            x1 = self.time_to_pixel(entry["start"])
            x2 = self.time_to_pixel(entry["end"])
            
            color = self._get_color(task, now)
            
            self._draw_task_box(x1, x2, color, entry["task_name"], task)
            if index:
                self.canvas.create_line(x1, TASK_TOP - 3, x1, TASK_BOTTOM + 3, fill="#17324d", width=3)

    def animate_to(self, new_schedule, new_tasks, now=None, steps=8, delay_ms=50):
        """Animates the transition from the current schedule to the new schedule."""
        if now is None:
            now = datetime.now()
            
        if self.animation_job:
            self.after_cancel(self.animation_job)

        self._set_visible_range(new_schedule)
            
        old_schedule_dict = {entry["task_id"]: entry for entry in self.current_schedule}
        new_schedule_dict = {entry["task_id"]: entry for entry in new_schedule}
        new_task_dict = {t["id"]: t for t in new_tasks}
        
        # Calculate target positions
        transitions = {}
        
        for task_id, new_entry in new_schedule_dict.items():
            if task_id not in new_task_dict:
                continue
                
            new_x1 = self.time_to_pixel(new_entry["start"])
            new_x2 = self.time_to_pixel(new_entry["end"])
            
            if task_id in old_schedule_dict:
                old_entry = old_schedule_dict[task_id]
                old_x1 = self.time_to_pixel(old_entry["start"])
                old_x2 = self.time_to_pixel(old_entry["end"])
                
                transitions[task_id] = {
                    "type": "move",
                    "start_x1": old_x1, "start_x2": old_x2,
                    "end_x1": new_x1, "end_x2": new_x2,
                    "color": self._get_color(new_task_dict[task_id], now),
                    "text": new_entry["task_name"],
                    "task": new_task_dict[task_id]
                }
            else:
                transitions[task_id] = {
                    "type": "new",
                    "end_x1": new_x1, "end_x2": new_x2,
                    "color": self._get_color(new_task_dict[task_id], now),
                    "text": new_entry["task_name"],
                    "task": new_task_dict[task_id]
                }
                
        for task_id, old_entry in old_schedule_dict.items():
            if task_id not in new_schedule_dict:
                old_x1 = self.time_to_pixel(old_entry["start"])
                old_x2 = self.time_to_pixel(old_entry["end"])
                old_task = next((t for t in self.current_tasks if t["id"] == task_id), None)
                color = self._get_color(old_task, now) if old_task else "grey"
                
                transitions[task_id] = {
                    "type": "remove",
                    "start_x1": old_x1, "start_x2": old_x2,
                    "color": color,
                    "text": old_entry["task_name"],
                    "task": old_task
                }
                
        self._animate_step(transitions, 1, steps, delay_ms, new_schedule, new_tasks)

    def _animate_step(self, transitions, step, total_steps, delay_ms, final_schedule, final_tasks):
        """Helper to run a single frame of the animation loop."""
        self.canvas.delete("all")
        self._draw_axis()
        
        progress = step / total_steps
        
        for task_id, data in transitions.items():
            if data["type"] == "move":
                x1 = data["start_x1"] + (data["end_x1"] - data["start_x1"]) * progress
                x2 = data["start_x2"] + (data["end_x2"] - data["start_x2"]) * progress
                self._draw_task_box(x1, x2, data["color"], data["text"], data["task"])
            elif data["type"] == "new" and step == total_steps:
                x1 = data["end_x1"]
                x2 = data["end_x2"]
                self._draw_task_box(x1, x2, data["color"], data["text"], data["task"])
            elif data["type"] == "remove" and step < total_steps:
                # Keep them at their old positions until the end
                x1 = data["start_x1"]
                x2 = data["start_x2"]
                self._draw_task_box(x1, x2, data["color"], data["text"], data["task"])
                
        if step < total_steps:
            self.animation_job = self.after(delay_ms, self._animate_step, transitions, step + 1, total_steps, delay_ms, final_schedule, final_tasks)
        else:
            self.current_schedule = final_schedule
            self.current_tasks = final_tasks
            self.animation_job = None

if __name__ == "__main__":
    # Test standalone block
    root = tk.Tk()
    root.title("GanttView Test")
    root.geometry("800x150")
    
    gantt = GanttView(root)
    gantt.pack(fill="both", expand=True, padx=20, pady=20)
    
    # Fake current time: 10:00 AM today
    now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    
    tasks = [
        {"id": "t1", "name": "Urgent Task", "deadline": now + timedelta(minutes=45)},   # < 1 hour -> Red
        {"id": "t2", "name": "Medium Task", "deadline": now + timedelta(hours=2)},      # < 3 hours -> Orange
        {"id": "t3", "name": "Chill Task", "deadline": now + timedelta(hours=5)}        # > 3 hours -> Green
    ]
    
    schedule = [
        {"task_id": "t1", "task_name": "Urgent Task", "start": now, "end": now + timedelta(hours=1)},
        {"task_id": "t2", "task_name": "Medium Task", "start": now + timedelta(hours=1), "end": now + timedelta(hours=2)},
        {"task_id": "t3", "task_name": "Chill Task", "start": now + timedelta(hours=2), "end": now + timedelta(hours=3)}
    ]
    
    # Initial render
    gantt.render(schedule, tasks, now=now)
    
    def trigger_animation():
        # New schedule: Urgent task removed, Medium moved, new task added
        new_tasks = [
            {"id": "t2", "name": "Medium Task", "deadline": now + timedelta(hours=2)},
            {"id": "t3", "name": "Chill Task", "deadline": now + timedelta(hours=5)},
            {"id": "t4", "name": "New Task", "deadline": now + timedelta(hours=8)}
        ]
        new_schedule = [
            {"task_id": "t2", "task_name": "Medium Task", "start": now, "end": now + timedelta(hours=1)},
            {"task_id": "t3", "task_name": "Chill Task", "start": now + timedelta(hours=1), "end": now + timedelta(hours=2)},
            {"task_id": "t4", "task_name": "New Task", "start": now + timedelta(hours=2), "end": now + timedelta(hours=4)}
        ]
        gantt.animate_to(new_schedule, new_tasks, now=now)
        
    btn = tk.Button(root, text="Animate Change", command=trigger_animation)
    btn.pack(pady=10)
    
    root.mainloop()
