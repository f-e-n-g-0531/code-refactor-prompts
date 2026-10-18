"""Regression tests for scripts/run_checks.py.

Run with:  python3 -m unittest discover -s scripts/tests -p "test_*.py" -v
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_checks.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


class RunChecksTest(unittest.TestCase):
    def test_list_fast_gate(self):
        result = run("--list")
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ("structure validation", "template audit", "tooling tests", "source links (offline)"):
            self.assertIn(name, result.stdout)
        self.assertNotIn("executable examples", result.stdout)

    def test_list_full_gate_adds_examples(self):
        result = run("--list", "--full")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("executable examples", result.stdout)


if __name__ == "__main__":
    unittest.main()
