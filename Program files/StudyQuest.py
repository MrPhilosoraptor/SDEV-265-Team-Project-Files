#!/usr/bin/env python3
"""
Frontend: Tkinter (GUI)
Backend: classes for Player, Goal (Task/Habit), GoalManager, Storage
Save file: studyquest_save.txt (in current working directory)
"""

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import simpledialog
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from typing import List, Optional
import os

# -------------------------
# Backend: Domain & Storage
# -------------------------

def sanitize(s: str) -> str:
    return (s or "").replace("|", "/")

def parse_date(s: str) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

def today_str() -> str:
    return date.today().isoformat()

class Difficulty:
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"

class Frequency:
    DAILY = "Daily"
    WEEKLY = "Weekly"

def base_xp(diff: str) -> int:
    if diff == Difficulty.EASY:
        return 10
    if diff == Difficulty.MEDIUM:
        return 20
    return 35

@dataclass
class Player:
    name: str = "Student"
    level: int = 1
    current_xp: int = 0
    xp_to_next: int = 100

    def add_xp(self, amount: int):
        if amount <= 0:
            return
        self.current_xp += amount
        while self.current_xp >= self.xp_to_next:
            self.current_xp -= self.xp_to_next
            self.level += 1
            self.xp_to_next += 50

    # allow `player += xp`
    def __iadd__(self, xp: int):
        self.add_xp(xp)
        return self

    def serialize(self) -> str:
        return f"PLAYER|{sanitize(self.name)}|{self.level}|{self.current_xp}|{self.xp_to_next}"

    @staticmethod
    def from_parts(parts: List[str]) -> "Player":
        if len(parts) != 5:
            raise ValueError("Invalid PLAYER record")
        p = Player(parts[1])
        p.level = int(parts[2])
        p.current_xp = int(parts[3])
        p.xp_to_next = int(parts[4])
        if p.level < 1 or p.xp_to_next < 1:
            raise ValueError("Invalid player data")
        return p

class Goal(ABC):
    def __init__(self, id_: int, title: str, description: str, difficulty: str):
        self.id = id_
        self.title = title
        self.description = description
        self.difficulty = difficulty

    @abstractmethod
    def type_name(self) -> str:
        pass

    @abstractmethod
    def is_completed(self) -> bool:
        pass

    @abstractmethod
    def complete(self, when: date) -> int:
        """Return XP awarded (0 if none)"""
        pass

    @abstractmethod
    def status_text(self) -> str:
        pass

    @abstractmethod
    def serialize(self) -> str:
        pass

class Task(Goal):
    def __init__(self, id_, title, description, difficulty, due_date: Optional[date], completed: bool = False):
        super().__init__(id_, title, description, difficulty)
        self.due_date = due_date
        self.completed = completed

    def type_name(self) -> str:
        return "Task"

    def is_completed(self) -> bool:
        return self.completed

    def complete(self, when: date) -> int:
        if self.completed:
            return 0
        self.completed = True
        xp = base_xp(self.difficulty)
        if self.due_date and when <= self.due_date:
            xp += 5
        return xp

    def status_text(self) -> str:
        if self.completed:
            return "Completed"
        if self.due_date:
            return f"Pending (due {self.due_date.isoformat()})"
        return "Pending"

    def serialize(self) -> str:
        due = self.due_date.isoformat() if self.due_date else ""
        comp = "1" if self.completed else "0"
        return f"GOAL|TASK|{self.id}|{sanitize(self.title)}|{sanitize(self.description)}|{self.difficulty}|{due}|{comp}"

    @staticmethod
    def from_parts(parts: List[str]) -> "Task":
        # expecting 8 parts: GOAL|TASK|id|title|desc|difficulty|due|completed
        if len(parts) != 8:
            raise ValueError("Invalid TASK record")
        id_ = int(parts[2])
        title = parts[3]
        desc = parts[4]
        diff = parts[5]
        due = parse_date(parts[6]) if parts[6] else None
        completed = parts[7] == "1"
        return Task(id_, title, desc, diff, due, completed)

class Habit(Goal):
    def __init__(self, id_, title, description, difficulty, frequency: str, current_streak: int = 0, best_streak: int = 0, last_completed: Optional[date] = None):
        super().__init__(id_, title, description, difficulty)
        self.frequency = frequency
        self.current_streak = current_streak
        self.best_streak = best_streak
        self.last_completed = last_completed

    def type_name(self) -> str:
        return "Habit"

    def is_completed(self) -> bool:
        # habits are never permanently completed
        return False

    def complete(self, when: date) -> int:
        if self.last_completed and self.last_completed == when:
            return 0  # already done today
        if not self.last_completed:
            self.current_streak = 1
        else:
            diff_days = (when - self.last_completed).days
            if self.frequency == Frequency.DAILY:
                self.current_streak = self.current_streak + 1 if diff_days == 1 else 1
            else:  # weekly
                self.current_streak = self.current_streak + 1 if (0 < diff_days <= 7) else 1
        self.last_completed = when
        if self.current_streak > self.best_streak:
            self.best_streak = self.current_streak
        xp = base_xp(self.difficulty) + min(10, self.current_streak)
        return xp

    def status_text(self) -> str:
        last = self.last_completed.isoformat() if self.last_completed else "—"
        return f"Streak {self.current_streak} (best {self.best_streak}), last: {last}"

    def serialize(self) -> str:
        last = self.last_completed.isoformat() if self.last_completed else ""
        return f"GOAL|HABIT|{self.id}|{sanitize(self.title)}|{sanitize(self.description)}|{self.difficulty}|{self.frequency}|{self.current_streak}|{self.best_streak}|{last}"

    @staticmethod
    def from_parts(parts: List[str]) -> "Habit":
        # The format is this:
        # GOAL|HABIT|id|title|desc|difficulty|frequency|cur|best|last
        if len(parts) != 10:
            raise ValueError("Invalid HABIT record")
        id_ = int(parts[2])
        title = parts[3]
        desc = parts[4]
        diff = parts[5]
        freq = parts[6]
        cur = int(parts[7])
        best = int(parts[8])
        last = parse_date(parts[9]) if parts[9] else None
        return Habit(id_, title, desc, diff, freq, cur, best, last)

class GoalManager:
    def __init__(self):
        self.goals: List[Goal] = []
        self.next_id: int = 1

    def clear(self):
        self.goals.clear()
        self.next_id = 1

    def add_task(self, title, desc, diff, due_date: Optional[date]):
        t = Task(self.next_id, title, desc, diff, due_date, False)
        self.goals.append(t)
        self.next_id += 1

    def add_habit(self, title, desc, diff, freq):
        h = Habit(self.next_id, title, desc, diff, freq, 0, 0, None)
        self.goals.append(h)
        self.next_id += 1

    def find_by_id(self, id_) -> Optional[Goal]:
        for g in self.goals:
            if g.id == id_:
                return g
        return None

    def complete_by_id(self, id_, when: date) -> int:
        g = self.find_by_id(id_)
        if g is None:
            raise ValueError("No such goal")
        return g.complete(when)

    def count_tasks(self, completed: bool) -> int:
        c = 0
        for g in self.goals:
            if isinstance(g, Task) and g.completed == completed:
                c += 1
        return c

    def rebuild_next_id(self):
        mx = 0
        for g in self.goals:
            if g.id > mx:
                mx = g.id
        self.next_id = mx + 1

    def serialize_all(self) -> List[str]:
        lines = []
        for g in self.goals:
            lines.append(g.serialize())
        return lines

    def load_goal_line(self, line: str):
        parts = line.split("|")
        if not parts or parts[0] != "GOAL":
            raise ValueError("Bad GOAL line")
        if parts[1] == "TASK":
            self.goals.append(Task.from_parts(parts))
        elif parts[1] == "HABIT":
            self.goals.append(Habit.from_parts(parts))
        else:
            raise ValueError("Unknown goal type")

class Storage:
    def __init__(self, path="studyquest_save.txt"):
        self.path = path

    def save(self, player: Player, gm: GoalManager):
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(player.serialize() + "\n")
            for line in gm.serialize_all():
                f.write(line + "\n")
        os.replace(tmp_path, self.path)

    def load(self) -> (Player, GoalManager):
        if not os.path.exists(self.path):
            return Player(), GoalManager()
        with open(self.path, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f if ln.strip()]
        if not lines:
            return Player(), GoalManager()
        first = lines[0].split("|")
        if first[0] != "PLAYER":
            raise ValueError("Save file missing PLAYER")
        player = Player.from_parts(first)
        gm = GoalManager()
        for ln in lines[1:]:
            gm.load_goal_line(ln)
        gm.rebuild_next_id()
        return player, gm


# -------------------------
# Frontend: Tkinter GUI
# -------------------------


class AddTaskDialog(simpledialog.Dialog):
    def __init__(self, parent, title="Add Task"):
        self.title_val = ""
        self.desc_val = ""
        self.diff_val = Difficulty.EASY
        self.due_val = None
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="Title:").grid(row=0, column=0, sticky="w")
        self.e_title = ttk.Entry(master, width=50)
        self.e_title.grid(row=0, column=1, padx=6, pady=4)

        ttk.Label(master, text="Description:").grid(row=1, column=0, sticky="nw")
        self.t_desc = tk.Text(master, width=38, height=6)
        self.t_desc.grid(row=1, column=1, padx=6, pady=4)

        ttk.Label(master, text="Difficulty:").grid(row=2, column=0, sticky="w")
        self.c_diff = ttk.Combobox(master, values=[Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD], state="readonly")
        self.c_diff.current(0)
        self.c_diff.grid(row=2, column=1, sticky="w", padx=6, pady=4)

        self.var_has_due = tk.IntVar(value=0)
        self.chk_due = ttk.Checkbutton(master, text="Has due date", variable=self.var_has_due, command=self._toggle_due)
        self.chk_due.grid(row=3, column=0, sticky="w", padx=6, pady=4)

        self.e_due = ttk.Entry(master, width=20)
        self.e_due.insert(0, date.today().isoformat())
        self.e_due.grid(row=3, column=1, sticky="w", padx=6, pady=4)
        self.e_due.configure(state="disabled")
        return self.e_title

    def _toggle_due(self):
        if self.var_has_due.get():
            self.e_due.configure(state="normal")
        else:
            self.e_due.configure(state="disabled")

    def validate(self):
        title = self.e_title.get().strip()
        if not title:
            messagebox.showwarning("Validation", "Title cannot be empty")
            return False
        if self.var_has_due.get():
            s = self.e_due.get().strip()
            if not parse_date(s):
                messagebox.showwarning("Validation", "Due date must be YYYY-MM-DD")
                return False
        return True

    def apply(self):
        self.title_val = self.e_title.get().strip()
        self.desc_val = self.t_desc.get("1.0", "end").strip()
        self.diff_val = self.c_diff.get()
        if self.var_has_due.get():
            self.due_val = parse_date(self.e_due.get().strip())
        else:
            self.due_val = None

class AddHabitDialog(simpledialog.Dialog):
    def __init__(self, parent, title="Add Habit"):
        self.title_val = ""
        self.desc_val = ""
        self.diff_val = Difficulty.EASY
        self.freq_val = Frequency.DAILY
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="Title:").grid(row=0, column=0, sticky="w")
        self.e_title = ttk.Entry(master, width=50)
        self.e_title.grid(row=0, column=1, padx=6, pady=4)

        ttk.Label(master, text="Description:").grid(row=1, column=0, sticky="nw")
        self.t_desc = tk.Text(master, width=38, height=6)
        self.t_desc.grid(row=1, column=1, padx=6, pady=4)

        ttk.Label(master, text="Difficulty:").grid(row=2, column=0, sticky="w")
        self.c_diff = ttk.Combobox(master, values=[Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD], state="readonly")
        self.c_diff.current(0)
        self.c_diff.grid(row=2, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(master, text="Frequency:").grid(row=3, column=0, sticky="w")
        self.c_freq = ttk.Combobox(master, values=[Frequency.DAILY, Frequency.WEEKLY], state="readonly")
        self.c_freq.current(0)
        self.c_freq.grid(row=3, column=1, sticky="w", padx=6, pady=4)
        return self.e_title

    def validate(self):
        title = self.e_title.get().strip()
        if not title:
            messagebox.showwarning("Validation", "Title cannot be empty")
            return False
        return True

    def apply(self):
        self.title_val = self.e_title.get().strip()
        self.desc_val = self.t_desc.get("1.0", "end").strip()
        self.diff_val = self.c_diff.get()
        self.freq_val = self.c_freq.get()

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("StudyQuest v1.0 | Team 3 | SDEV265 Spring 2026")
        self.geometry("900x560")
        self.resizable(False, False)

        # Backend instances
        self.storage = Storage()

        # If the save file exists, try to load it and use name from file
        # If it doesn't exist, prompt the user for their name and create a new profile
        try:
            if os.path.exists(self.storage.path):
                # save file exists - trying to load
                self.player, self.gm = self.storage.load()
            else:
                # no save file - ask for a name
                # if no name is provided, it will be defaulted to "Student"
                self.withdraw()
                name = simpledialog.askstring("Name", "Enter your name:", parent=self)
                if not name or not name.strip():
                    name = "Student" #defaulting to Student
                self.player = Player(name=name.strip())
                self.deiconify()
                self.gm = GoalManager()
        except Exception as e:
            # If loading failed for any reason, inform the user and prompt for a name
            messagebox.showwarning("Load error", f"Failed to load save file: {e}\nStarting fresh.")
            name = simpledialog.askstring("Name", "Enter your name:", parent=self)
            if not name or not name.strip():
                name = "Student"
            self.player = Player(name=name.strip())
            self.gm = GoalManager()

        # UI elements
        self._build_ui()
        self.refresh_ui()

    def _build_ui(self):
        top_frame = ttk.Frame(self, padding=10)
        top_frame.pack(side="top", fill="x")

        self.lbl_name = ttk.Label(top_frame, text=f"Profile: {self.player.name}", font=("Segoe UI", 12, "bold"))
        self.lbl_name.pack(side="left", anchor="w")

        right_frame = ttk.Frame(top_frame)
        right_frame.pack(side="right")

        btn_add_task = ttk.Button(right_frame, text="Add Task", command=self.on_add_task)
        btn_add_task.grid(row=0, column=0, padx=4)
        btn_add_habit = ttk.Button(right_frame, text="Add Habit", command=self.on_add_habit)
        btn_add_habit.grid(row=0, column=1, padx=4)
        btn_complete = ttk.Button(right_frame, text="Complete Selected", command=self.on_complete_selected)
        btn_complete.grid(row=0, column=2, padx=4)
        btn_save = ttk.Button(right_frame, text="Save", command=self.on_save)
        btn_save.grid(row=0, column=3, padx=4)

        stats_frame = ttk.Frame(self, padding=(10, 0, 10, 0))
        stats_frame.pack(side="top", fill="x")
        self.lbl_level = ttk.Label(stats_frame, text=f"Level: {self.player.level}")
        self.lbl_level.pack(side="left", padx=6)
        self.lbl_xp = ttk.Label(stats_frame, text=f"XP: {self.player.current_xp} / {self.player.xp_to_next}")
        self.lbl_xp.pack(side="left", padx=6)
        self.lbl_tasks = ttk.Label(stats_frame, text="")
        self.lbl_tasks.pack(side="left", padx=6)

        # Treeview for goals
        self.tree = ttk.Treeview(self, columns=("type", "title", "difficulty", "status"), show="headings", selectmode="browse")
        self.tree.heading("type", text="Type")
        self.tree.heading("title", text="Title")
        self.tree.heading("difficulty", text="Difficulty")
        self.tree.heading("status", text="Status / Streak")
        self.tree.column("type", width=100, anchor="center")
        self.tree.column("title", width=380, anchor="w")
        self.tree.column("difficulty", width=120, anchor="center")
        self.tree.column("status", width=320, anchor="w")
        self.tree.pack(side="top", fill="both", expand=True, padx=10, pady=8)

    def refresh_ui(self):
        self.lbl_name.config(text=f"Profile: {self.player.name}")
        self.lbl_level.config(text=f"Level: {self.player.level}")
        self.lbl_xp.config(text=f"XP: {self.player.current_xp} / {self.player.xp_to_next}")
        pending = self.gm.count_tasks(False)
        completed = self.gm.count_tasks(True)
        self.lbl_tasks.config(text=f"Tasks: pending {pending}, completed {completed}; Total goals: {len(self.gm.goals)}")

        # refresh tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        for g in self.gm.goals:
            values = (g.type_name(), g.title, g.difficulty, g.status_text())
            # use the item's id as Treeview iid so we can retrieve it later
            self.tree.insert("", "end", iid=str(g.id), values=values)

    def on_add_task(self):
        d = AddTaskDialog(self, "Add Task")
        if getattr(d, "title_val", ""):
            self.gm.add_task(d.title_val, d.desc_val, d.diff_val, d.due_val)
            self.refresh_ui()

    def on_add_habit(self):
        d = AddHabitDialog(self, "Add Habit")
        if getattr(d, "title_val", ""):
            self.gm.add_habit(d.title_val, d.desc_val, d.diff_val, d.freq_val)
            self.refresh_ui()

    def on_complete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Complete", "Please select a goal first")
            return
        gid = int(sel[0])
        try:
            xp = self.gm.complete_by_id(gid, date.today())
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if xp <= 0:
            messagebox.showinfo("Complete", "No XP gained (already completed today)")
            self.refresh_ui()
            return
        before_level = self.player.level
        self.player += xp
        msg = f"Completed! +{xp} XP."
        if self.player.level > before_level:
            msg += f"\nLevel up! You are now Level {self.player.level}."
        messagebox.showinfo("Success", msg)
        self.refresh_ui()

    def on_save(self):
        try:
            self.storage.save(self.player, self.gm)
            messagebox.showinfo("Save", "Saved.")
        except Exception as e:
            messagebox.showerror("Save error", str(e))

    def on_close(self):
        try:
            self.storage.save(self.player, self.gm)
        except Exception:
            pass
        self.destroy()

def main():
    app = MainApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()

if __name__ == "__main__":
    main()
