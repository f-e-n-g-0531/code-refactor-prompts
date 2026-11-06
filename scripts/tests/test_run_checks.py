"""Regression tests for scripts/run_checks.py.

Run with:  python3 -m unittest discover -s scripts/tests -p "test_*.py" -v
"""
from __future__ import annotations

import importlib.util
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch, call

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
    def test_execution_order_cwd_and_failure_short_circuit(self):
        spec = importlib.util.spec_from_file_location("run_checks_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for full, failure in [(False, None), (True, None), (True, 0), (True, 2)]:
            with self.subTest(full=full, failure=failure):
                steps = module.FAST_STEPS + (module.FULL_STEPS if full else [])
                count = len(steps) if failure is None else failure + 1
                results = [subprocess.CompletedProcess(command, 1 if i == failure else 0)
                           for i, (_, command) in enumerate(steps[:count])]
                stdout, stderr = io.StringIO(), io.StringIO()
                with patch.object(sys, "argv", [str(SCRIPT)] + (["--full"] if full else [])), \
                     patch.object(module.subprocess, "run", side_effect=results) as execute, \
                     redirect_stdout(stdout), redirect_stderr(stderr):
                    status = module.main()
                self.assertEqual(status, 0 if failure is None else 1)
                self.assertEqual(execute.call_args_list,
                                 [call(command, cwd=module.ROOT) for _, command in steps[:count]])
                if failure is None:
                    self.assertIn("OK: all local checks passed", stdout.getvalue())
                    self.assertEqual(stderr.getvalue(), "")
                else:
                    self.assertEqual(stderr.getvalue(), f"FAILED: {steps[failure][0]}\n")
                    self.assertNotIn("all local checks passed", stdout.getvalue())

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
