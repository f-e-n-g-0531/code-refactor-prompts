"""Regression tests for scripts/check_sources.py.

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
SCRIPT = ROOT / "scripts" / "check_sources.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def write_temp(text: str) -> Path:
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    )
    handle.write(text)
    handle.close()
    return Path(handle.name)


class SourceCheckTest(unittest.TestCase):
    def test_repository_sources_pass_offline(self):
        result = run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("unique URL(s)", result.stdout)

    def test_markdown_links_and_trailing_punctuation(self):
        path = write_temp(
            "[A](https://example.com/a)，另见 https://example.com/b。\n"
        )
        try:
            result = run(str(path), "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["pass"])
            self.assertEqual(payload["unique_urls"], 2)
            self.assertEqual(payload["references"], 2)
        finally:
            path.unlink()

    def test_duplicate_urls_are_counted_once(self):
        path = write_temp(
            "https://example.com/a\nhttps://example.com/a\nhttps://example.com/b\n"
        )
        try:
            result = run(str(path), "--json")
            payload = json.loads(result.stdout)
            self.assertEqual(payload["references"], 3)
            self.assertEqual(payload["unique_urls"], 2)
        finally:
            path.unlink()

    def test_invalid_url_is_rejected(self):
        path = write_temp("链接：http:///missing-host\n")
        try:
            result = run(str(path))
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("missing host", result.stdout)
        finally:
            path.unlink()

    def test_no_urls_is_a_failure(self):
        path = write_temp("没有链接\n")
        try:
            result = run(str(path))
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("no URLs found", result.stderr)
        finally:
            path.unlink()

    def test_missing_file_is_usage_error(self):
        result = run(str(ROOT / "does-not-exist.md"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("file not found", result.stderr)

    def test_invalid_timeout_is_usage_error(self):
        result = run("--timeout", "0")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--timeout", result.stderr)


if __name__ == "__main__":
    unittest.main()
