#!/usr/bin/env python3

"""
----------------------------------------------------------------------------------------

StudyQuest Program
Current Version: v3.1
Team: 3
Class: SDEV 265
Term: Spring 2026

----------------------------------------------------------------------------------------

Update change log:
    Version 3.1:
        - The save file was moved to the following directory:
            C -> Users -> <your-username> -> .studyquest -> studyquest_save.txt (Windows)
            /Users/<your-username>/.studyquest/studyquest_save.txt (macOS)
        - Fixed the macOS bug where the save file is never written
            due to macOS's security restrictions (Errno 30 read-only file system)

            
    Version 3:
        - Delete Profile Button added.
        - New file the program works with:
            studyquest_save.txt.bak - a save file created in case profile deletion fails
            the program will restore the progress from that file in such case
        - "Tasks (pending, completed and total goals)" cosmetic change:
            It now look as follows: Pending: x | Completed: y | Total Goals: z
        - Search label was moved next to the search bar
        - Fixed the macOS bug where the main program always launched in behind

----------------------------------------------------------------------------------------

Implementation details:
    Frontend: Tkinter (GUI)
    Backend: classes for Player, Goal (Task/Habit), GoalManager, Storage

----------------------------------------------------------------------------------------
"""


import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import simpledialog
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from typing import List, Optional
import os
import shutil
import tempfile

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
    def __init__(self, path: Optional[str] = None):
        """
        Default save location is a per-user data folder to avoid read-onlyfilesystem issues.
        By default the file will be: ~/.studyquest/studyquest_save.txt
        """
        if path:
            self.path = path
        else:
            home = os.path.expanduser("~") or tempfile.gettempdir()
            data_dir = os.path.join(home, ".studyquest")
            try:
                os.makedirs(data_dir, exist_ok=True)
            except Exception:
                # fallback to system temp dir if home cannot be used
                data_dir = tempfile.gettempdir()
            self.path = os.path.join(data_dir, "studyquest_save.txt")

    def save(self, player: Player, gm: GoalManager):
        """
        Write to a temporary file and atomically replace the target.
        If the primary path is not writable,
        attempt a fallback into the per-user .studyquest folder.
        Raise an exception on failure so the caller (UI) can show an error.
        """
        tmp_path = self.path + ".tmp"
        dirpath = os.path.dirname(self.path)
        try:
            os.makedirs(dirpath, exist_ok=True)
        except Exception:
            # if even creating dir fails, we'll handle when trying to write
            pass

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(player.serialize() + "\n")
                for line in gm.serialize_all():
                    f.write(line + "\n")
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
            os.replace(tmp_path, self.path)
            return
        except (PermissionError, OSError) as primary_exc:
            # Primary write failed (likely read-only). Try fallback to ~/.studyquest explicitly.
            fallback_dir = os.path.join(os.path.expanduser("~"), ".studyquest")
            try:
                os.makedirs(fallback_dir, exist_ok=True)
                fallback_path = os.path.join(fallback_dir, "studyquest_save.txt")
                fallback_tmp = fallback_path + ".tmp"
                with open(fallback_tmp, "w", encoding="utf-8") as f:
                    f.write(player.serialize() + "\n")
                    for line in gm.serialize_all():
                        f.write(line + "\n")
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except Exception:
                        pass
                os.replace(fallback_tmp, fallback_path)
                # update self.path to the fallback so subsequent runs use it
                self.path = fallback_path
                return
            except Exception as fallback_exc:
                # Cleanup any leftover tmp from primary attempt
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass
                # Raise a single informative exception
                raise OSError(f"Save failed (primary: {primary_exc}, fallback: {fallback_exc})")

    def load(self) -> (Player, GoalManager):
        # Keep the simple loader (expects file at self.path)
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
        self.e_due.configure(state="normal" if self.var_has_due.get() else "disabled")

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
        self.due_val = parse_date(self.e_due.get().strip()) if self.var_has_due.get() else None

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
        self.title("StudyQuest v3.1 | Team 3 | SDEV265 Spring 2026")
        self.geometry("1200x900")
        self.resizable(False, False)

        # Sketch colors
        self.COL_BG = "#E7EEF8"
        self.COL_PANEL = "#F8F8FA"
        self.COL_BORDER = "#B9C6DA"
        self.COL_BLUE = "#3B8BDB"
        self.COL_GREEN = "#2EAD5B"
        self.COL_ORANGE = "#E3A11B"
        self.COL_RED = "#D65C5C"
        self.COL_GRAY = "#6A6A6A"
        self.COL_TEXT = "#1F2A3A"

        self.configure(bg=self.COL_BG)
        self._apply_styles()

        # Backend instances
        self.storage = Storage()

        try:
            if os.path.exists(self.storage.path):
                # load existing save (player AND goal manager returned)
                self.player, self.gm = self.storage.load()
            else:
                # no save file -> prompt for name and start fresh
                self.withdraw()
                name = simpledialog.askstring("Name", "Enter your name:", parent=self)
                if not name or not name.strip():
                    name = "Student"
                self.player = Player(name=name.strip())
                self.gm = GoalManager()
                self.deiconify()

            # bring main window to front
            self.after(0, self._bring_to_front)
        except Exception as e:
            messagebox.showwarning("Load error", f"Failed to load save file: {e}\nStarting fresh.")
            name = simpledialog.askstring("Name", "Enter your name:", parent=self)
            if not name or not name.strip():
                name = "Student"
            self.player = Player(name=name.strip())
            self.gm = GoalManager()

        # Filter state (UI only)
        self.var_show_tasks = tk.IntVar(value=1)
        self.var_show_habits = tk.IntVar(value=1)
        self.var_show_completed = tk.IntVar(value=1)
        self.var_search = tk.StringVar(value="")

        self._build_ui()
        self.refresh_ui()

    def _apply_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", font=("Segoe UI", 10))
        style.configure("Header.TLabel",
                background=self.COL_PANEL,
                foreground=self.COL_TEXT,
                font=("Segoe UI", 18, "bold"))

        style.configure("HeaderSub.TLabel",
                background=self.COL_PANEL,
                foreground="#4A5A70",
                font=("Segoe UI", 11))


        style.configure("App.TFrame", background=self.COL_BG)
        style.configure("Panel.TFrame", background=self.COL_PANEL, relief="solid", borderwidth=1)
        style.configure("PanelHeader.TLabel", background=self.COL_PANEL, foreground=self.COL_TEXT, font=("Segoe UI", 11, "bold"))
        style.configure("Small.TLabel", background=self.COL_PANEL, foreground=self.COL_TEXT, font=("Segoe UI", 9))
        style.configure("Stat.TLabel", background=self.COL_PANEL, foreground=self.COL_TEXT, font=("Segoe UI", 10, "bold"))

        # Buttons
        style.configure("TButton", padding=(10, 6), foreground=self.COL_TEXT)
        style.map("TButton",
                  foreground=[("disabled", "#8A8A8A"), ("active", self.COL_TEXT), ("!active", self.COL_TEXT)])

        style.configure("Primary.TButton", padding=(12, 7), foreground="white")
        style.map("Primary.TButton",
                  background=[("active", self.COL_BLUE), ("!active", self.COL_BLUE)],
                  foreground=[("active", "white"), ("!active", "white")])

        style.configure("Action.TButton", padding=(10, 6), foreground=self.COL_TEXT)
        style.map("Action.TButton",
                  background=[("active", "#D6E6FF"), ("!active", self.COL_BG)],
                  foreground=[("disabled", "#8A8A8A"), ("active", self.COL_TEXT), ("!active", self.COL_TEXT)])
        
        # StudyQuest v3 update: Red button for profile deletion
        style.configure("Danger.TButton", padding=(10, 6), foreground="white",
                        background=self.COL_RED)
        style.map("Danger.TButton",
                  background=[("active", self.COL_RED), ("!active", self.COL_RED)],
                  foreground=[("disabled", "#FFFFFF"), ("!disabled", "white")])


        # Entries
        style.configure("TEntry", padding=(6, 4))
        style.configure("TCombobox", padding=(6, 4))

        # Checkbuttons background match panel
        style.configure("Panel.TCheckbutton", background=self.COL_PANEL, foreground=self.COL_TEXT)
        style.map("Panel.TCheckbutton",
                  background=[("active", self.COL_PANEL), ("!active", self.COL_PANEL)],
                  foreground=[("disabled", "#8A8A8A"), ("!active", self.COL_TEXT)])

        # Treeview
        style.configure("Treeview",
                        background=self.COL_PANEL,
                        fieldbackground=self.COL_PANEL,
                        foreground=self.COL_TEXT,
                        bordercolor=self.COL_BORDER,
                        lightcolor=self.COL_BORDER,
                        darkcolor=self.COL_BORDER,
                        rowheight=26)
        style.configure("Treeview.Heading",
                        background=self.COL_BG,
                        foreground=self.COL_TEXT,
                        font=("Segoe UI", 10, "bold"))
        style.map("Treeview",
                  background=[("selected", "#D6E6FF")],
                  foreground=[("selected", self.COL_TEXT)])

        # XP bar
        style.configure("XP.Horizontal.TProgressbar",
                        troughcolor="#000000",
                        background=self.COL_BLUE,
                        bordercolor=self.COL_BORDER,
                        lightcolor=self.COL_BORDER,
                        darkcolor=self.COL_BORDER)
    
    def _bring_to_front(self):
        """Bring main window above other apps"""
        try:
            # Try to lift and force focus
            self.lift()
            # Temporarily force on-top, then clear the flag shortly after
            try:
                self.attributes("-topmost", True)
                self.after(200, lambda: self.attributes("-topmost", False))
            except Exception:
                pass
            # Try to give keyboard focus
            try:
                self.focus_force()
            except Exception:
                pass
        except Exception:
            pass

    def _panel_frame(self, parent, pad=10):
        return ttk.Frame(parent, style="Panel.TFrame", padding=pad)

    def _build_ui(self):
        root = ttk.Frame(self, style="App.TFrame", padding=12)
        root.pack(fill="both", expand=True)

        # Header
        header = self._panel_frame(root, pad=(16, 14))
        header.pack(fill="x")

        header_left = ttk.Frame(header, style="Panel.TFrame")
        header_left.pack(side="left", fill="x", expand=True)

        self.lbl_title = ttk.Label(
            header_left,
            text="StudyQuest",
            style="Header.TLabel"
        )
        self.lbl_title.pack(anchor="w")

        self.lbl_profile = ttk.Label(
            header_left,
            text="",
            style="HeaderSub.TLabel"
        )
        self.lbl_profile.pack(anchor="w", pady=(2, 0))

        header_right = ttk.Frame(header, style="Panel.TFrame")
        header_right.pack(side="right")

        self.btn_add_task = ttk.Button(header_right, text="Add Task", style="Primary.TButton", command=self.on_add_task)
        self.btn_add_task.grid(row=0, column=0, padx=(0, 8))
        self.btn_add_habit = ttk.Button(header_right, text="Add Habit", style="Primary.TButton", command=self.on_add_habit)
        self.btn_add_habit.grid(row=0, column=1, padx=(0, 8))
        self.btn_save = ttk.Button(header_right, text="Save", command=self.on_save)
        self.btn_save.grid(row=0, column=2)

        # Stats row
        stats_row = ttk.Frame(root, style="App.TFrame")
        stats_row.pack(fill="x", pady=(10, 10))

        self.box_level = self._panel_frame(stats_row, pad=10)
        self.box_level.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(self.box_level, text="Level", style="Small.TLabel").pack(anchor="w")
        self.lbl_level = ttk.Label(self.box_level, text="", style="Stat.TLabel", font=("Segoe UI", 13, "bold"))
        self.lbl_level.pack(anchor="w", pady=(2, 0))

        self.box_xp = self._panel_frame(stats_row, pad=10)
        self.box_xp.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Label(self.box_xp, text="XP", style="Small.TLabel").pack(anchor="w")
        self.lbl_xp = ttk.Label(self.box_xp, text="", style="Stat.TLabel", font=("Segoe UI", 13, "bold"))
        self.lbl_xp.pack(anchor="w", pady=(2, 0))

        self.box_tasks = self._panel_frame(stats_row, pad=10)
        self.box_tasks.pack(side="left", fill="x", expand=True)
        ttk.Label(self.box_tasks, text="Tasks", style="Small.TLabel").pack(anchor="w")
        self.lbl_tasks = ttk.Label(self.box_tasks, text="", style="Stat.TLabel", font=("Segoe UI", 11, "bold"))
        self.lbl_tasks.pack(anchor="w", pady=(2, 0))

        # Main area
        main = ttk.Frame(root, style="App.TFrame")
        main.pack(fill="both", expand=True)

        left_panel = self._panel_frame(main, pad=10)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Filter row, aligned
        filter_row = ttk.Frame(left_panel, style="Panel.TFrame")
        filter_row.pack(fill="x", pady=(0, 8))

        ttk.Label(filter_row, text="Filter:", style="Small.TLabel").grid(row=0, column=0, sticky="w", padx=(10, 8))
        ttk.Checkbutton(filter_row, text="Tasks", style="Panel.TCheckbutton",
                        variable=self.var_show_tasks, command=self.refresh_ui).grid(row=0, column=1, sticky="w", padx=(0, 10))
        ttk.Checkbutton(filter_row, text="Habits", style="Panel.TCheckbutton",
                        variable=self.var_show_habits, command=self.refresh_ui).grid(row=0, column=2, sticky="w", padx=(0, 10))
        ttk.Checkbutton(filter_row, text="Show completed", style="Panel.TCheckbutton",
                        variable=self.var_show_completed, command=self.refresh_ui).grid(row=0, column=3, sticky="w", padx=(0, 18))

        ttk.Label(filter_row, text="Search:", style="Small.TLabel").grid(row=0, column=4, sticky="e", padx=(300, 8))
        self.e_search = ttk.Entry(filter_row, textvariable=self.var_search, width=34)
        self.e_search.grid(row=0, column=5, sticky="e")
        self.e_search.bind("<KeyRelease>", lambda _e: self.refresh_ui())

        filter_row.columnconfigure(5, weight=1)

        # Treeview with a dedicated difficulty bar column
        self.tree = ttk.Treeview(
            left_panel,
            columns=("type", "title", "difficulty", "diffbar", "status"),
            show="headings",
            selectmode="browse",
            height=13
        )
        self.tree.heading("type", text="Type")
        self.tree.heading("title", text="Title")
        self.tree.heading("difficulty", text="Difficulty")
        self.tree.heading("diffbar", text="")
        self.tree.heading("status", text="Status / Streak")

        self.tree.column("type", width=80, anchor="center")
        self.tree.column("title", width=300, anchor="w")
        self.tree.column("difficulty", width=90, anchor="center")
        self.tree.column("diffbar", width=90, anchor="w")
        self.tree.column("status", width=310, anchor="w")

        self.tree.pack(fill="both", expand=True)

        # Vertical scrollbar only (removes the empty horizontal bar)
        yscroll = ttk.Scrollbar(left_panel, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        yscroll.place(in_=self.tree, relx=1.0, rely=0.0, relheight=1.0, anchor="ne")

        self.tree.tag_configure("easy", foreground=self.COL_TEXT)
        self.tree.tag_configure("medium", foreground=self.COL_TEXT)
        self.tree.tag_configure("hard", foreground=self.COL_TEXT)
        self.tree.tag_configure("completed", foreground=self.COL_GRAY)

        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._update_details())

        # Bottom action row
        list_btn_row = ttk.Frame(left_panel, style="Panel.TFrame")
        list_btn_row.pack(fill="x", pady=(8, 0))

        self.btn_complete = ttk.Button(list_btn_row, text="Complete selected", style="Action.TButton", command=self.on_complete_selected)
        self.btn_complete.pack(side="left")
        self.btn_delete = ttk.Button(list_btn_row, text="Delete selected", style="Action.TButton", command=self.on_delete_selected)
        self.btn_delete.pack(side="left", padx=(10, 0))

        # StudyQuest v3 update: Red button for profile deletion
        self.btn_delete_profile = ttk.Button(list_btn_row, text="Delete profile", style="Danger.TButton", command=self.on_delete_profile)
        self.btn_delete_profile.pack(side="right")

        # Details
        right_panel = self._panel_frame(main, pad=10)
        right_panel.pack(side="right", fill="y")

        ttk.Label(right_panel, text="Details", style="PanelHeader.TLabel").pack(anchor="w")

        self.details_box = tk.Text(
            right_panel,
            width=34,
            height=19,
            wrap="word",
            bd=1,
            relief="solid",
            background=self.COL_PANEL,
            foreground=self.COL_TEXT,
            padx=8,
            pady=8
        )
        self.details_box.pack(fill="both", expand=False, pady=(8, 10))
        self.details_box.configure(state="disabled")

        # XP strip
        xp_strip = self._panel_frame(root, pad=(12, 10))
        xp_strip.pack(fill="x", pady=(10, 0))

        self.lbl_xp_strip_left = ttk.Label(xp_strip, text="", style="Small.TLabel")
        self.lbl_xp_strip_left.pack(side="left")

        self.xp_bar = ttk.Progressbar(xp_strip, style="XP.Horizontal.TProgressbar",
                                      orient="horizontal", length=560, mode="determinate")
        self.xp_bar.pack(side="left", padx=12)

        self.lbl_xp_strip_right = ttk.Label(xp_strip, text="", style="Small.TLabel")
        self.lbl_xp_strip_right.pack(side="right")

    def _difficulty_bar(self, diff: str) -> str:
        
        if diff == Difficulty.EASY:
            return "████"
        if diff == Difficulty.MEDIUM:
            return "███████"
        return "██████████"

    def _status_compact(self, g: Goal) -> str:
        # Keeps the list clean.
        # Full info stays in Details.
        if isinstance(g, Task):
            return "Completed" if g.completed else "Pending"
        # Habit
        return f"Streak {g.current_streak} (best {g.best_streak})"

    def _filtered_goals(self) -> List[Goal]:
        show_tasks = bool(self.var_show_tasks.get())
        show_habits = bool(self.var_show_habits.get())
        show_completed = bool(self.var_show_completed.get())
        q = (self.var_search.get() or "").strip().lower()

        out: List[Goal] = []
        for g in self.gm.goals:
            is_task = isinstance(g, Task)
            is_habit = isinstance(g, Habit)

            if is_task and not show_tasks:
                continue
            if is_habit and not show_habits:
                continue
            if is_task and not show_completed and g.completed:
                continue

            if q:
                hay = f"{g.type_name()} {g.title} {g.description} {g.difficulty} {g.status_text()}".lower()
                if q not in hay:
                    continue

            out.append(g)
        return out

    def refresh_ui(self):
        self.lbl_profile.config(text=f"Player {self.player.name}  |  Level {self.player.level}")


        self.lbl_level.config(text=str(self.player.level))
        self.lbl_xp.config(text=f"{self.player.current_xp} / {self.player.xp_to_next}")

        pending = self.gm.count_tasks(False)
        completed = self.gm.count_tasks(True)
        self.lbl_tasks.config(text=f"Pending: {pending} | Completed: {completed} | Total Goals: {len(self.gm.goals)}")

        # XP strip
        self.lbl_xp_strip_left.config(text=f"{self.player.current_xp}/{self.player.xp_to_next} XP")
        self.lbl_xp_strip_right.config(text=f"Level {self.player.level}")
        pct = int((self.player.current_xp / self.player.xp_to_next) * 100) if self.player.xp_to_next > 0 else 0
        self.xp_bar["value"] = pct

        # Tree
        sel_before = self.tree.selection()
        for item in self.tree.get_children():
            self.tree.delete(item)

        for g in self._filtered_goals():
            diff_name = g.difficulty
            bar = self._difficulty_bar(g.difficulty)
            status = self._status_compact(g)

            values = (g.type_name(), g.title, diff_name, bar, status)

            tags = []
            if isinstance(g, Task) and g.completed:
                tags.append("completed")
            else:
                if g.difficulty == Difficulty.EASY:
                    tags.append("easy")
                elif g.difficulty == Difficulty.MEDIUM:
                    tags.append("medium")
                else:
                    tags.append("hard")

            self.tree.insert("", "end", iid=str(g.id), values=values, tags=tuple(tags))

        if sel_before and self.tree.exists(sel_before[0]):
            self.tree.selection_set(sel_before[0])
        else:
            self._update_details()

    def _update_details(self):
        sel = self.tree.selection()
        if not sel:
            text = "Select a goal to view details."
            self.details_box.configure(state="normal")
            self.details_box.delete("1.0", "end")
            self.details_box.insert("1.0", text)
            self.details_box.configure(state="disabled")
            return

        gid = int(sel[0])
        g = self.gm.find_by_id(gid)
        if g is None:
            return

        lines = []
        lines.append(f"Type: {g.type_name()}")
        lines.append(f"Title: {g.title}")
        lines.append(f"Difficulty: {g.difficulty}")
        lines.append("")
        if g.description:
            lines.append("Description:")
            lines.append(g.description)
            lines.append("")

        if isinstance(g, Task):
            due = g.due_date.isoformat() if g.due_date else "-"
            lines.append(f"Due date: {due}")
            lines.append(f"Status: {g.status_text()}")
        else:
            lines.append(f"Frequency: {g.frequency}")
            lines.append(f"Status: {g.status_text()}")

        self.details_box.configure(state="normal")
        self.details_box.delete("1.0", "end")
        self.details_box.insert("1.0", "\n".join(lines))
        self.details_box.configure(state="disabled")

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
            messagebox.showinfo("Complete", "Select a goal first")
            return
        gid = int(sel[0])
        try:
            xp = self.gm.complete_by_id(gid, date.today())
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if xp <= 0:
            messagebox.showinfo("Complete", "No XP gained")
            self.refresh_ui()
            return
        before_level = self.player.level
        self.player += xp
        msg = f"Completed. +{xp} XP."
        if self.player.level > before_level:
            msg += f"\nLevel up. Level {self.player.level}."
        messagebox.showinfo("Success", msg)
        self.refresh_ui()

    def on_delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Delete", "Select a goal first")
            return
        gid = int(sel[0])
        g = self.gm.find_by_id(gid)
        if g is None:
            return
        if not messagebox.askyesno("Delete", f"Delete {g.type_name()} '{g.title}'?"):
            return
        for i, goal in enumerate(self.gm.goals):
            if goal.id == gid:
                del self.gm.goals[i]
                break
        self.refresh_ui()

    def on_save(self):
        try:
            self.storage.save(self.player, self.gm)
            messagebox.showinfo("Save", "Saved.")
        except Exception as e:
            messagebox.showerror("Save error", str(e))

    # StudyQuest v3 update: Red button for profile deletion
    def on_delete_profile(self):
        confirm = messagebox.askokcancel(
            "Delete profile",
            "This will permanently delete your profile and all saved goals.\n\n"
            "A backup named 'studyquest_save.txt.bak' will be created so if deletion fails, your progress will restore.\n\n"
            "The application will close after deletion.\n\n"
            "Do you want to proceed?",
            icon="warning",
            parent=self
        )
        if not confirm:
            return

        path = self.storage.path
        try:
            if os.path.exists(path):
                bak = path + ".bak"
                # Attempt to create a backup copy first (overwriting existing bak if necessary)
                try:
                    if os.path.exists(bak):
                        try:
                            os.remove(bak)
                        except Exception:
                            # if bak cannot be removed, continue and let copy2 overwrite if possible
                            pass
                    shutil.copy2(path, bak)
                except Exception as e:
                    # If copying fails, stop to avoid data loss
                    messagebox.showerror("Delete error", f"Could not create backup file: {e}", parent=self)
                    return

                # Now delete the original file
                try:
                    os.remove(path)
                except Exception as e:
                    # Try to restore from bak if deletion failed
                    try:
                        if os.path.exists(bak) and not os.path.exists(path):
                            shutil.copy2(bak, path)
                    except Exception:
                        pass
                    messagebox.showerror("Delete error", f"Could not delete save file: {e}", parent=self)
                    return

                # .bak deletion if profile successfully deleted
                try:
                    if os.path.exists(bak):
                        os.remove(bak)
                except Exception:
                    # if we cannot remove bak, ignore (it can be removed manually)
                    pass

            # Clear in-memory state
            self.player = Player(name="Student")
            self.gm = GoalManager()
            self.refresh_ui()

            messagebox.showinfo("Profile deleted", "Profile deleted. The application will now close.", parent=self)

            # Close the application without automatically saving
            self.destroy()

        except Exception as e:
            messagebox.showerror("Delete error", f"Failed to delete profile: {e}", parent=self)

    def on_close(self):
        try:
            self.storage.save(self.player, self.gm)
        except Exception as e:
            # Inform the user so they can take corrective action (permissions, location)
            try:
                messagebox.showerror("Save error on exit",
                                     f"Failed to save your profile:\n{e}\n\n"
                                     f"The program will still close but your progress was not saved.",
                                     parent=self)
            except Exception:
                pass
        finally:
            self.destroy()
def main():
    app = MainApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()

if __name__ == "__main__":
    main()