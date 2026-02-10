"""windowsTests/frontendTest.py

Windows OS - Frontend unittest"""

from __future__ import annotations

import os
import sys
import time
import unittest
import tempfile
from unittest import mock


# Make StudyQuest importable when running tests from repo root.
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.abspath(os.path.join(TEST_DIR, ".."))
if DOCS_DIR not in sys.path:
	sys.path.insert(0, DOCS_DIR)


import tkinter as tk  

from StudyQuest import (  
	MainApp,
	Storage,
	GoalManager,
	Player,
	Difficulty,
	Frequency,
)
class _MarkdownTableTestResult(unittest.TextTestResult):
	"""Collect per-test timing and print a markdown table for easy reporting."""

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

	def render_markdown_table(self) -> str:
		# Kept for compatibility if you prefer markdown in a written report.
		lines = ["| Test | Status | Duration (s) | Notes |", "|---|---:|---:|---|"]
		for test_id, status, duration, notes in self._rows:
			safe_notes = (notes or "").replace("\n", " ").replace("|", "/")
			lines.append(f"| {test_id} | {status} | {duration:.3f} | {safe_notes} |")
		return "\n".join(lines)

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
	
class FrontendWindowsTests(unittest.TestCase):
	def setUp(self):
		# Isolated temp working directory so UI save/load uses only test files.
		self._tmp = tempfile.TemporaryDirectory(prefix="studyquest_frontend_")
		self.addCleanup(self._tmp.cleanup)
		self._old_cwd = os.getcwd()
		os.chdir(self._tmp.name)
		self.addCleanup(lambda: os.chdir(self._old_cwd))

	def _build_app_no_popups(self, save_exists: bool, save_contents: str | None = None) -> MainApp:
		"""Create MainApp with popups mocked out to avoid manual interaction."""
		storage_path = "studyquest_save.txt"
		if save_exists:
			with open(storage_path, "w", encoding="utf-8") as f:
				f.write(save_contents or "")

		# Mock name prompt and message boxes.
		patchers = [
			mock.patch("tkinter.simpledialog.askstring", return_value="WinUITester"),
			mock.patch("tkinter.messagebox.showinfo"),
			mock.patch("tkinter.messagebox.showwarning"),
			mock.patch("tkinter.messagebox.showerror"),
		]
		for p in patchers:
			p.start()
			self.addCleanup(p.stop)

		app = MainApp()
		# Keep UI from flashing.
		app.withdraw()
		self.addCleanup(lambda: (app.destroy() if app.winfo_exists() else None))
		return app

	def test_main_window_renders_and_widgets_exist(self):
		"""Smoke test: Main window builds UI and key widgets exist."""
		app = self._build_app_no_popups(save_exists=False)
		app.update_idletasks()

		self.assertTrue(app.winfo_exists())
		self.assertTrue(hasattr(app, "tree"), "Treeview should exist")
		self.assertTrue(hasattr(app, "lbl_level"), "Level label should exist")
		self.assertTrue(hasattr(app, "lbl_xp"), "XP label should exist")

		# Basic label content should be set.
		self.assertIn("Level", app.lbl_level.cget("text"))
		self.assertIn("XP", app.lbl_xp.cget("text"))

	def test_tk_scaling_smoke_100_125_150(self):
		"""Ensure UI still updates at common scaling levels."""
		app = self._build_app_no_popups(save_exists=False)

		for scaling in (1.0, 1.25, 1.5):
			app.tk.call("tk", "scaling", scaling)
			app.update_idletasks()
			# Ensure geometry call succeeds and widgets still exist.
			geom = app.geometry()
			self.assertIsInstance(geom, str)
			self.assertGreater(len(app.tree.get_children()), -1)