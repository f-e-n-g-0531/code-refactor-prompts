"""Regression tests for scripts/compose_prompt.py.

Run with:  python3 -m unittest discover -s scripts/tests -p "test_*.py" -v
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSER = ROOT / "scripts" / "compose_prompt.py"
CHECKER = ROOT / "scripts" / "check_prompt.py"
SAMPLE_GO = ROOT / "scripts" / "fixtures" / "sample.go"
SAMPLE_PY = ROOT / "scripts" / "fixtures" / "sample.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


checker = load(CHECKER, "check_prompt_for_composer_tests")


def run_compose(*args, input_text=None):
    return subprocess.run(
        [sys.executable, str(COMPOSER), *args],
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


class ComposeTest(unittest.TestCase):
    def test_chinese_prompt_passes_checker(self):
        result = run_compose("--code", str(SAMPLE_GO), "--project", "order-pricing")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("【验收标准", result.stdout)
        self.assertIn("go test ./...", result.stdout)
        self.assertTrue(checker.check(result.stdout, explicit_language="go")["pass"])

    def test_english_prompt_passes_checker(self):
        result = run_compose("--code", str(SAMPLE_PY), "--output-lang", "en")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[ACCEPTANCE CRITERIA", result.stdout)
        self.assertTrue(checker.check(result.stdout, explicit_language="python")["pass"])

    def test_language_overrides(self):
        languages = [
            "python",
            "java",
            "rust",
            "typescript",
            "javascript",
            "csharp",
            "kotlin",
            "swift",
            "ruby",
            "php",
            "cpp",
            "sql",
        ]
        for language in languages:
            with self.subTest(language=language):
                result = run_compose(
                    "--code", str(SAMPLE_GO), "--code-lang", language
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(
                    checker.check(result.stdout, explicit_language=language)["pass"]
                )

    def test_out_file_matches_self_check(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "prompt.txt"
            result = run_compose(
                "--code", str(SAMPLE_GO), "--out", str(target), "--goal", "提取子方法"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            prompt = target.read_text(encoding="utf-8")
            self.assertIn("提取子方法", prompt)
            self.assertTrue(checker.check(prompt, explicit_language="go")["pass"])

    def test_stdin_code(self):
        result = run_compose(
            "--code", "-", "--code-lang", "python", input_text="def total(items):\n    return 0\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(checker.check(result.stdout, explicit_language="python")["pass"])

    def test_mismatched_test_command_is_refused(self):
        result = run_compose("--code", str(SAMPLE_GO), "--test-command", "pytest")
        self.assertEqual(result.returncode, 1)
        self.assertIn("self-check", result.stderr)

    def test_unknown_extension_requires_code_lang(self):
        with tempfile.TemporaryDirectory() as raw:
            source = Path(raw) / "snippet.xyz"
            source.write_text("example", encoding="utf-8")
            result = run_compose("--code", str(source))
            self.assertEqual(result.returncode, 2)
            self.assertIn("cannot detect language", result.stderr)

    def test_missing_code_file(self):
        result = run_compose("--code", str(ROOT / "does-not-exist.go"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("not found", result.stderr)


if __name__ == "__main__":
    unittest.main()
