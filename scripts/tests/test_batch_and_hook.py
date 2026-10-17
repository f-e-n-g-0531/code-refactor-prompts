"""Regression tests for batch mode and the pre-commit hook contract.

Run with:  python3 -m unittest discover -s scripts/tests -p "test_*.py" -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scripts" / "check_prompt.py"
FIXTURES = ROOT / "scripts" / "fixtures"
HOOKS = ROOT / ".pre-commit-hooks.yaml"

GOOD = (FIXTURES / "good-prompt.txt").read_text(encoding="utf-8")
GOOD_EN = (FIXTURES / "good-en-prompt.txt").read_text(encoding="utf-8")
BAD = (FIXTURES / "bad-prompt.txt").read_text(encoding="utf-8")
WEAK = (FIXTURES / "weak-prompt.txt").read_text(encoding="utf-8")


def run_checker(*args):
    return subprocess.run(
        [sys.executable, str(CHECKER), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


class BatchTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, relative, content):
        target = self.dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def test_directory_scan_with_one_bad_file(self):
        self.write("good.prompt.txt", GOOD)
        self.write("nested/bad.prompt.txt", BAD)
        result = run_checker(str(self.dir))
        self.assertEqual(result.returncode, 1)
        self.assertIn("1 passed, 1 failed", result.stdout)
        self.assertIn("PASS", result.stdout)
        self.assertIn("FAIL", result.stdout)

    def test_directory_all_green(self):
        self.write("good.prompt.txt", GOOD)
        self.write("good-en.prompt.md", GOOD_EN)
        result = run_checker(str(self.dir))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("2 passed, 0 failed", result.stdout)

    def test_multiple_file_arguments(self):
        first = self.write("a.prompt.txt", GOOD)
        second = self.write("b.prompt.txt", GOOD_EN)
        result = run_checker(str(first), str(second))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("2 passed, 0 failed", result.stdout)

    def test_fix_repairs_batch(self):
        bad = self.write("bad.prompt.txt", BAD)
        result = run_checker(str(self.dir), "--fix")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("check_prompt.py --fix", bad.read_text(encoding="utf-8"))
        self.assertEqual(run_checker(str(self.dir)).returncode, 0)

    def test_json_batch_shape(self):
        self.write("good.prompt.txt", GOOD)
        self.write("bad.prompt.txt", BAD)
        result = run_checker(str(self.dir), "--json")
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["pass"])
        self.assertEqual(payload["passed"], 1)
        self.assertEqual(payload["failed"], 1)
        self.assertEqual(len(payload["results"]), 2)

    def test_include_override(self):
        self.write("custom.md", GOOD)
        default = run_checker(str(self.dir))
        self.assertEqual(default.returncode, 2)
        custom = run_checker(str(self.dir), "--include", "*.md")
        self.assertEqual(custom.returncode, 0, custom.stdout + custom.stderr)

    def test_empty_directory_is_usage_error(self):
        empty = self.dir / "empty"
        empty.mkdir()
        result = run_checker(str(empty))
        self.assertEqual(result.returncode, 2)
        self.assertIn("没有匹配", result.stderr)

    def test_strict_batch_promotes_warnings(self):
        self.write("good.prompt.txt", GOOD)
        self.write("weak.prompt.txt", WEAK)
        self.assertEqual(run_checker(str(self.dir)).returncode, 0)
        strict = run_checker(str(self.dir), "--strict")
        self.assertEqual(strict.returncode, 1)
        self.assertIn("weak.prompt.txt", strict.stdout)

    def test_stdin_cannot_be_combined(self):
        target = self.write("good.prompt.txt", GOOD)
        result = run_checker("-", str(target))
        self.assertEqual(result.returncode, 2)


class PreCommitHookTest(unittest.TestCase):
    def test_hook_definition_calls_the_checker(self):
        text = HOOKS.read_text(encoding="utf-8")
        self.assertIn("scripts/check_prompt.py --strict", text)
        self.assertIn("pass_filenames: true", text)
        self.assertIn("files:", text)
        self.assertIn("code-refactor-prompt-check", text)

    def test_hook_contract_accepts_passing_files(self):
        files = [str(FIXTURES / "good-prompt.txt"), str(FIXTURES / "good-en-prompt.txt")]
        result = run_checker("--strict", *files)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_hook_contract_rejects_failing_files(self):
        files = [str(FIXTURES / "good-prompt.txt"), str(FIXTURES / "bad-prompt.txt")]
        result = run_checker("--strict", *files)
        self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
