"""
gantt_view.py

Module 3 frontend: A Tkinter Gantt chart view for the daily schedule.
Provides a snap-to render method and an animated transition method.
"""

import tkinter as tk
from datetime import datetime, timedelta

# Constants for the visible range of the Gantt chart (hours)
START_HOUR = 8
END_HOUR = 22
CANVAS_HEIGHT = 150

class GanttView(tk.Frame):
    def __init__(self, master=None, on_task_hover=None, **kwargs):
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, bg="white", height=CANVAS_HEIGHT)
        self.canvas.pack(fill="both", expand=True)
        
        self.on_task_hover = on_task_hover
        
        # State tracking for animation
        self.current_schedule = []
        self.current_tasks = []
        self.animation_job = None

    def _handle_hover(self, task):
        if self.on_task_hover:
            self.on_task_hover(task)

    def _get_time_fraction(self, dt):
        """Helper to get the fraction of the day elapsed between START_HOUR and END_HOUR."""
        hour_fraction = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
        if hour_fraction < START_HOUR:
            return 0.0
        if hour_fraction > END_HOUR:
            return 1.0
        return (hour_fraction - START_HOUR) / (END_HOUR - START_HOUR)

    def time_to_pixel(self, dt):
        """Linear map from a datetime's clock time to an x-coordinate."""
        # Force an update of geometry to ensure width is accurate if called early
        self.update_idletasks()
        width = self.canvas.winfo_width()
        
        # Fallback if canvas is not yet drawn
        if width <= 1:
            width = 680 # roughly the default window width
        
        fraction = self._get_time_fraction(dt)
        return fraction * width

    def _get_color(self, task, now):
        """Determine task color based on deadline urgency."""
        time_left = task["deadline"] - now
        if time_left < timedelta(hours=1):
            return "#e74c3c" # Red
        elif time_left < timedelta(hours=3):
            return "#f39c12" # Orange
        else:
            return "#2ecc71" # Green

    def render(self, schedule, tasks, now=None):
        """Snaps the schedule onto the canvas, clearing anything previously drawn."""
        if now is None:
            now = datetime.now()
            
        self.current_schedule = schedule
        self.current_tasks = tasks
        
        if self.animation_job:
            self.after_cancel(self.animation_job)
            self.animation_job = None

        self.canvas.delete("all")
        
        task_dict = {t["id"]: t for t in tasks}
        
        for entry in schedule:
            task = task_dict.get(entry["task_id"])
            if not task:
                continue
                
            x1 = self.time_to_pixel(entry["start"])
            x2 = self.time_to_pixel(entry["end"])
            
            color = self._get_color(task, now)
            
            rect_id = self.canvas.create_rectangle(x1, 10, x2, 50, fill=color, outline="black")
            
            self.canvas.create_text((x1 + x2) / 2, 55, text=entry["task_name"], fill="black", anchor="e", angle=90)
            
            self.canvas.tag_bind(rect_id, "<Enter>", lambda e, t=task: self._handle_hover(t))
            self.canvas.tag_bind(rect_id, "<Leave>", lambda e: self._handle_hover(None))

    def animate_to(self, new_schedule, new_tasks, now=None, steps=8, delay_ms=50):
        """Animates the transition from the current schedule to the new schedule."""
        if now is None:
            now = datetime.now()
            
        if self.animation_job:
            self.after_cancel(self.animation_job)
            
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
        
        progress = step / total_steps
        
        for task_id, data in transitions.items():
            if data["type"] == "move":
                x1 = data["start_x1"] + (data["end_x1"] - data["start_x1"]) * progress
                x2 = data["start_x2"] + (data["end_x2"] - data["start_x2"]) * progress
                rect_id = self.canvas.create_rectangle(x1, 10, x2, 50, fill=data["color"], outline="black")
                self.canvas.create_text((x1 + x2) / 2, 55, text=data["text"], fill="black", anchor="e", angle=90)
                if data["task"]:
                    self.canvas.tag_bind(rect_id, "<Enter>", lambda e, t=data["task"]: self._handle_hover(t))
                    self.canvas.tag_bind(rect_id, "<Leave>", lambda e: self._handle_hover(None))
            elif data["type"] == "new" and step == total_steps:
                x1 = data["end_x1"]
                x2 = data["end_x2"]
                rect_id = self.canvas.create_rectangle(x1, 10, x2, 50, fill=data["color"], outline="black")
                self.canvas.create_text((x1 + x2) / 2, 55, text=data["text"], fill="black", anchor="e", angle=90)
                if data["task"]:
                    self.canvas.tag_bind(rect_id, "<Enter>", lambda e, t=data["task"]: self._handle_hover(t))
                    self.canvas.tag_bind(rect_id, "<Leave>", lambda e: self._handle_hover(None))
            elif data["type"] == "remove" and step < total_steps:
                # Keep them at their old positions until the end
                x1 = data["start_x1"]
                x2 = data["start_x2"]
                rect_id = self.canvas.create_rectangle(x1, 10, x2, 50, fill=data["color"], outline="black")
                self.canvas.create_text((x1 + x2) / 2, 55, text=data["text"], fill="black", anchor="e", angle=90)
                if data["task"]:
                    self.canvas.tag_bind(rect_id, "<Enter>", lambda e, t=data["task"]: self._handle_hover(t))
                    self.canvas.tag_bind(rect_id, "<Leave>", lambda e: self._handle_hover(None))
                
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
