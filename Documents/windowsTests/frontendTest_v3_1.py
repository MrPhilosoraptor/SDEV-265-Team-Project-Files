"""windowsTests/frontendTest_v3_1.py

    - Run using `python Documents/windowsTests/frontendTest_v3_1.py` from repo root.

Windows OS - Frontend unittest for StudyQuest v3.1"""

from __future__ import annotations

import contextlib
import importlib.util
import os
import sys
import time
import unittest
import tempfile
from unittest import mock

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(TEST_DIR, "..", ".."))

MODULE_NAME = "StudyQuest_v3_1_runtime"
MODULE_PATH = os.path.join(REPO_ROOT, "Program files", "StudyQuest_v3.1.py")
spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError(f"Unable to load StudyQuest v3.1 module from {MODULE_PATH}")
studyquest_module = importlib.util.module_from_spec(spec)
sys.modules[MODULE_NAME] = studyquest_module
spec.loader.exec_module(studyquest_module)

import tkinter as tk


MainApp = studyquest_module.MainApp
GoalManager = studyquest_module.GoalManager
Player = studyquest_module.Player
Difficulty = studyquest_module.Difficulty
Frequency = studyquest_module.Frequency
AddTaskDialog = studyquest_module.AddTaskDialog
AddHabitDialog = studyquest_module.AddHabitDialog


class _GridTableTestResult(unittest.TextTestResult):
    """Collect per-test timing and print an ASCII grid table for results."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._started_at: dict[str, float] = {}
        self._rows: list[tuple[str, str, float, str]] = []

    def startTest(self, test):
        self._started_at[test.id()] = time.perf_counter()
        super().startTest(test)

    def _record(self, test, status: str, notes: str = ""):
        started = self._started_at.get(test.id(), None)
        duration = (time.perf_counter() - started) if started is not None else 0.0
        self._rows.append((test.id(), status, duration, notes))

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "PASS")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "SKIP", str(reason))

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "FAIL")

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "ERROR")

    def render_grid_table(self, max_notes: int = 80) -> str:
        def short_name(test_id: str) -> str:
            parts = test_id.split(".")
            return parts[-1] if parts else test_id

        rows = []
        for test_id, status, duration, notes in self._rows:
            safe_notes = (notes or "").replace("\n", " ")
            if max_notes and len(safe_notes) > max_notes:
                safe_notes = safe_notes[: max_notes - 1] + "…"
            rows.append([short_name(test_id), status, f"{duration:.3f}", safe_notes])

        headers = ["Test", "Status", "Sec", "Notes"]
        all_rows = [headers] + rows
        widths = [max(len(str(r[i])) for r in all_rows) for i in range(len(headers))]

        def sep(char: str = "-") -> str:
            return "+" + "+".join(char * (w + 2) for w in widths) + "+"

        def fmt(r) -> str:
            cells = [f" {str(r[i]).ljust(widths[i])} " for i in range(len(headers))]
            return "|" + "|".join(cells) + "|"

        out = [sep("-"), fmt(headers), sep("=")]
        for r in rows:
            out.append(fmt(r))
            out.append(sep("-"))
        return "\n".join(out)


class FrontendWindowsV31Tests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="studyquest_frontend_")
        self.addCleanup(self._tmp.cleanup)
        self._old_cwd = os.getcwd()
        os.chdir(self._tmp.name)
        self.addCleanup(lambda: os.chdir(self._old_cwd))
        self._home = os.path.join(self._tmp.name, "home")
        os.makedirs(os.path.join(self._home, ".studyquest"), exist_ok=True)
        self._env_patch = mock.patch.dict(os.environ, {"HOME": self._home, "USERPROFILE": self._home}, clear=False)
        self._env_patch.start()
        self.addCleanup(self._env_patch.stop)

    def _build_app_no_popups(self, save_exists: bool, save_contents: str | None = None) -> MainApp:
        storage_path = os.path.join(self._home, ".studyquest", "studyquest_save.txt")
        if save_exists:
            os.makedirs(os.path.dirname(storage_path), exist_ok=True)
            with open(storage_path, "w", encoding="utf-8") as f:
                f.write(save_contents or "")

        patchers = [
            mock.patch("tkinter.simpledialog.askstring", return_value="Harold"),
            mock.patch("tkinter.messagebox.showinfo"),
            mock.patch("tkinter.messagebox.showwarning"),
            mock.patch("tkinter.messagebox.showerror"),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

        try:
            app = MainApp()
        except tk.TclError as e:
            self.skipTest(f"Tk unavailable on this system: {e}")

        app.withdraw()

        def _cleanup() -> None:
            with contextlib.suppress(Exception):
                app.destroy()

        self.addCleanup(_cleanup)
        return app

    class _FakeEntry:
        def __init__(self, value: str):
            self._value = value

        def get(self) -> str:
            return self._value

    class _FakeVar:
        def __init__(self, value: int):
            self._value = value

        def get(self) -> int:
            return self._value

    def test_main_window_renders_and_widgets_exist(self):
        app = self._build_app_no_popups(save_exists=False)
        app.update_idletasks()

        self.assertTrue(app.winfo_exists())
        self.assertTrue(hasattr(app, "tree"), "Treeview should exist")
        self.assertTrue(hasattr(app, "lbl_level"), "Level label should exist")
        self.assertTrue(hasattr(app, "lbl_xp"), "XP label should exist")
        self.assertTrue(hasattr(app, "var_show_tasks"), "Filter state should exist")
        self.assertTrue(hasattr(app, "btn_delete"), "Delete button should exist")

        level_text = app.lbl_level.cget("text")
        xp_text = app.lbl_xp.cget("text")
        self.assertTrue(str(level_text).strip().isdigit())
        self.assertIn("/", str(xp_text))

    def test_tk_scaling_smoke_100_125_150(self):
        app = self._build_app_no_popups(save_exists=False)

        for scaling in (1.0, 1.25, 1.5):
            app.tk.call("tk", "scaling", scaling)
            app.update_idletasks()
            geom = app.geometry()
            self.assertIsInstance(geom, str)
            self.assertGreaterEqual(len(app.tree.get_children()), 0)

    def test_dialog_open_close_best_effort(self):
        app = self._build_app_no_popups(save_exists=False)

        class _FakeTaskDialog:
            title_val = "T"
            desc_val = "D"
            diff_val = Difficulty.EASY
            due_val = None

            def __init__(self, *args, **kwargs):
                pass

        class _FakeHabitDialog:
            title_val = "H"
            desc_val = "D"
            diff_val = Difficulty.EASY
            freq_val = Frequency.DAILY

            def __init__(self, *args, **kwargs):
                pass

        with mock.patch.object(studyquest_module, "AddTaskDialog", _FakeTaskDialog), mock.patch.object(
            studyquest_module, "AddHabitDialog", _FakeHabitDialog
        ):
            app.on_add_task()
            app.on_add_habit()
            app.update_idletasks()

        self.assertEqual(len(app.gm.goals), 2, "Expected one task + one habit added")

    def test_delete_selected_removes_goal_from_list(self):
        app = self._build_app_no_popups(save_exists=False)

        app.gm.add_task("Delete me", "Desc", Difficulty.EASY, None)
        app.refresh_ui()
        app.update_idletasks()

        self.assertEqual(len(app.gm.goals), 1)
        app.tree.selection_set("1")

        with mock.patch("tkinter.messagebox.askyesno", return_value=True):
            app.on_delete_selected()

        self.assertEqual(len(app.gm.goals), 0)
        self.assertEqual(len(app.tree.get_children()), 0)

    def test_add_task_dialog_rejects_empty_title(self):
        dialog = AddTaskDialog.__new__(AddTaskDialog)
        dialog.e_title = self._FakeEntry("   ")
        dialog.var_has_due = self._FakeVar(0)
        dialog.e_due = self._FakeEntry("")

        with mock.patch("tkinter.messagebox.showwarning") as warning:
            result = AddTaskDialog.validate(dialog)

        self.assertFalse(result)
        warning.assert_called_once_with("Validation", "Title cannot be empty")

    def test_add_habit_dialog_rejects_empty_title(self):
        dialog = AddHabitDialog.__new__(AddHabitDialog)
        dialog.e_title = self._FakeEntry("   ")

        with mock.patch("tkinter.messagebox.showwarning") as warning:
            result = AddHabitDialog.validate(dialog)

        self.assertFalse(result)
        warning.assert_called_once_with("Validation", "Title cannot be empty")

    def test_ui_responsiveness_refresh_under_load(self):
        app = self._build_app_no_popups(save_exists=False)

        app.gm = GoalManager()
        for i in range(2000):
            app.gm.add_task(f"Task {i}", "Desc", Difficulty.MEDIUM, None)
        for i in range(2000):
            app.gm.add_habit(f"Habit {i}", "Desc", Difficulty.EASY, Frequency.DAILY)

        t0 = time.perf_counter()
        app.refresh_ui()
        app.update_idletasks()
        t1 = time.perf_counter()

        refresh_s = t1 - t0
        self.assertLess(refresh_s, 5.0, f"UI refresh too slow under load on Windows: {refresh_s:.2f}s")
        print(f"[Windows UI Perf] goals={len(app.gm.goals)} refresh={refresh_s:.3f}s")

    def test_rapid_interactions_complete_selected_no_crash(self):
        app = self._build_app_no_popups(save_exists=False)

        app.gm.add_task("QuickTask", "Desc", Difficulty.EASY, None)
        app.gm.add_habit("QuickHabit", "Desc", Difficulty.EASY, Frequency.DAILY)
        app.refresh_ui()
        app.update_idletasks()

        task_id = None
        for g in app.gm.goals:
            if g.type_name() == "Task":
                task_id = str(g.id)
                break
        self.assertIsNotNone(task_id)
        app.tree.selection_set(task_id)
        app.on_complete_selected()
        app.update_idletasks()

        habit_id = None
        for g in app.gm.goals:
            if g.type_name() == "Habit":
                habit_id = str(g.id)
                break
        self.assertIsNotNone(habit_id)
        app.tree.selection_set(habit_id)
        app.on_complete_selected()
        app.on_complete_selected()
        app.update_idletasks()

    def test_corrupted_save_file_recovery_starts_fresh(self):
        corrupted = "NOT_A_PLAYER|oops\nGOAL|TASK|1|A|B|Easy||0\n"
        app = self._build_app_no_popups(save_exists=True, save_contents=corrupted)
        app.update_idletasks()

        self.assertIsInstance(app.player, Player)
        self.assertGreaterEqual(app.player.level, 1)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2, resultclass=_GridTableTestResult)
    result = runner.run(suite)
    print("\n## Frontend Test Results (Windows)\n")
    print(result.render_grid_table())
    raise SystemExit(0 if result.wasSuccessful() else 1)