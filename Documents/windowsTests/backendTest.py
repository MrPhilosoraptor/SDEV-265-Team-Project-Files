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