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