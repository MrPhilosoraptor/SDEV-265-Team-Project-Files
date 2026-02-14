"""windowsTests/backendTest.py

Windows OS - Backend unittest
"""

from __future__ import annotations

import os
import sys
import time
import unittest
import tempfile
from datetime import date, timedelta


TEST_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.abspath(os.path.join(TEST_DIR, ".."))
if DOCS_DIR not in sys.path:
	sys.path.insert(0, DOCS_DIR)

from StudyQuest import (
	Storage,
	Player,
	GoalManager,
	Task,
	Habit,
	Difficulty,
	Frequency,
	parse_date,
)

class _GridTableTestResult(unittest.TextTestResult):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._rows: list[tuple[str, str, str]] = []

	def _short_name(self, test: unittest.TestCase) -> str:
		return getattr(test, "_testMethodName", test.id())

	def _record(self, test: unittest.TestCase, status: str, details: str = "OK"):
		details = (details or "").replace("\n", " ").strip()
		self._rows.append((self._short_name(test), status, details))

	def addSuccess(self, test):
		super().addSuccess(test)
		self._record(test, "PASS", "OK")

	def addSkip(self, test, reason):
		super().addSkip(test, reason)
		self._record(test, "SKIP", str(reason))

	def addFailure(self, test, err):
		super().addFailure(test, err)
		ex = err[1]
		self._record(test, "FAIL", ex.__class__.__name__)

	def addError(self, test, err):
		super().addError(test, err)
		ex = err[1]
		self._record(test, "ERROR", ex.__class__.__name__)

	def addExpectedFailure(self, test, err):
		super().addExpectedFailure(test, err)
		ex = err[1]
		self._record(test, "XFAIL", ex.__class__.__name__)

	def addUnexpectedSuccess(self, test):
		super().addUnexpectedSuccess(test)
		self._record(test, "XPASS", "unexpected success")

	def render_grid_table(self) -> str:
		headers = ("Test Name", "Status", "Details")
		# Control total width to avoid wrapping in Windows terminals.
		max_widths = (42, 8, 20)

		def clip(value: str, max_len: int) -> str:
			value = str(value)
			if len(value) <= max_len:
				return value
			if max_len <= 3:
				return value[:max_len]
			return value[: max_len - 3] + "..."

		clipped_rows = [
			(clip(r[0], max_widths[0]), clip(r[1], max_widths[1]), clip(r[2], max_widths[2]))
			for r in self._rows
		]
		rows = [headers] + clipped_rows

		widths = [min(max(len(str(r[i])) for r in rows), max_widths[i]) for i in range(3)]

		def sep(char: str = "-") -> str:
			return "+" + "+".join(char * (w + 2) for w in widths) + "+"

		def fmt(r) -> str:
			return "|" + "|".join(f" {str(r[i]).ljust(widths[i])} " for i in range(3)) + "|"

		out = [sep("-"), fmt(headers), sep("=")]
		for r in clipped_rows:
			out.append(fmt(r))
			out.append(sep("-"))
		return "\n".join(out)


class BackendTestBase(unittest.TestCase):
	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory(prefix="studyquest_backend_")
		self.addCleanup(self._tmp.cleanup)
		self._old_cwd = os.getcwd()
		os.chdir(self._tmp.name)
		self.addCleanup(lambda: os.chdir(self._old_cwd))

	def _new_profile(self) -> tuple[Player, GoalManager]:
		return Player(name="WinTester"), GoalManager()

# Task Tests
class TaskTests(BackendTestBase):
	def test_create_task(self):
		_, gm = self._new_profile()
		due = date.today() + timedelta(days=2)
		gm.add_task("T1", "Notes", Difficulty.EASY, due)

		self.assertEqual(len(gm.goals), 1)
		g = gm.goals[0]
		self.assertIsInstance(g, Task)
		self.assertEqual(g.title, "T1")
		self.assertEqual(g.description, "Notes")
		self.assertEqual(g.difficulty, Difficulty.EASY)
		self.assertEqual(g.due_date, due)
		self.assertFalse(g.completed)

	def test_edit_task_fields(self):
		_, gm = self._new_profile()
		gm.add_task("Old", "OldDesc", Difficulty.EASY, None)
		t = gm.find_by_id(1)
		self.assertIsInstance(t, Task)

		t.title = "New"
		t.description = "NewDesc"
		t.difficulty = Difficulty.HARD
		t.due_date = date.today()

		self.assertEqual(t.title, "New")
		self.assertIn("New", t.serialize())

	@unittest.expectedFailure
	def test_delete_task_by_id_required_but_missing(self):
		_, gm = self._new_profile()
		gm.add_task("A", "", Difficulty.EASY, None)

		self.assertTrue(
			hasattr(gm, "delete_by_id"),
			"Requirements specify task deletion; backend has no delete_by_id().",
		)

	def test_mark_task_complete_awards_xp(self):
		player, gm = self._new_profile()
		gm.add_task("T", "", Difficulty.MEDIUM, date.today())

		xp = gm.complete_by_id(1, date.today())
		self.assertGreater(xp, 0)
		before = player.current_xp
		player.add_xp(xp)
		self.assertGreater(player.current_xp, before)

		t = gm.find_by_id(1)
		self.assertTrue(isinstance(t, Task) and t.completed)

	def test_completed_removed_from_active_list_semantics(self):
		_, gm = self._new_profile()
		gm.add_task("T1", "", Difficulty.EASY, None)
		gm.add_task("T2", "", Difficulty.EASY, None)
		self.assertEqual(gm.count_tasks(False), 2)

		gm.complete_by_id(1, date.today())
		self.assertEqual(gm.count_tasks(False), 1)
		self.assertEqual(gm.count_tasks(True), 1)

	@unittest.expectedFailure
	def test_weekly_organization_logic_required_but_missing(self):
		_, gm = self._new_profile()
		self.assertTrue(
			hasattr(gm, "tasks_for_week"),
			"Requirements mention weekly planner organization; no tasks_for_week().",
		)
		
# Habit Tests
class HabitTests(BackendTestBase):
	def test_create_habit(self):
		_, gm = self._new_profile()
		gm.add_habit("H1", "", Difficulty.EASY, Frequency.DAILY)
		self.assertEqual(len(gm.goals), 1)
		h = gm.goals[0]
		self.assertIsInstance(h, Habit)
		self.assertEqual(h.frequency, Frequency.DAILY)
		self.assertEqual(h.current_streak, 0)
		self.assertIsNone(h.last_completed)

	def test_habit_xp_reward_on_completion(self):
		player, gm = self._new_profile()
		gm.add_habit("H", "", Difficulty.EASY, Frequency.DAILY)
		xp = gm.complete_by_id(1, date.today())
		self.assertGreater(xp, 0)
		before = player.current_xp
		player += xp
		self.assertGreater(player.current_xp, before)

	def test_habit_streak_updates_daily(self):
		_, gm = self._new_profile()
		gm.add_habit("H", "", Difficulty.EASY, Frequency.DAILY)
		h = gm.find_by_id(1)
		self.assertIsInstance(h, Habit)

		day1 = date(2026, 2, 10)
		day2 = day1 + timedelta(days=1)
		day3 = day2 + timedelta(days=1)

		gm.complete_by_id(1, day1)
		self.assertEqual(h.current_streak, 1)
		gm.complete_by_id(1, day2)
		self.assertEqual(h.current_streak, 2)
		gm.complete_by_id(1, day3)
		self.assertEqual(h.current_streak, 3)
		self.assertEqual(h.best_streak, 3)

	def test_prevent_multiple_completions_same_day(self):
		_, gm = self._new_profile()
		gm.add_habit("H", "", Difficulty.EASY, Frequency.DAILY)

		today = date(2026, 2, 10)
		xp1 = gm.complete_by_id(1, today)
		xp2 = gm.complete_by_id(1, today)
		self.assertGreater(xp1, 0)
		self.assertEqual(xp2, 0)
		

if __name__ == "__main__":
	suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
	runner = unittest.TextTestRunner(verbosity=2, resultclass=_GridTableTestResult)
	result = runner.run(suite)
	print("\n## Backend Test Results (Windows)\n")
	print(result.render_grid_table())
	raise SystemExit(0 if result.wasSuccessful() else 1)    