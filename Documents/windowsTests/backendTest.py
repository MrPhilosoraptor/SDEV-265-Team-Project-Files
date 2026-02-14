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