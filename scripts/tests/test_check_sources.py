"""Regression tests for scripts/check_sources.py.

Run with:  python3 -m unittest discover -s scripts/tests -p "test_*.py" -v
"""
from __future__ import annotations

import importlib.util
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

    def test_parenthesised_urls_are_preserved(self):
        path = write_temp(
            "See https://en.wikipedia.org/wiki/Function_(mathematics) and "
            "[wiki](https://example.com/f(x)) plus (https://example.com/plain).\n"
        )
        try:
            result = run(str(path), "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["unique_urls"], 3)
            found = {entry["url"] for entry in payload["urls"]}
            self.assertEqual(found, {
                "https://en.wikipedia.org/wiki/Function_(mathematics)",
                "https://example.com/f(x)",
                "https://example.com/plain",
            })
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

    def test_ports_are_validated_offline(self):
        for port, valid in [("abc", False), ("99999", False), ("-1", False),
                            ("0", True), ("443", True), ("65535", True)]:
            with self.subTest(port=port):
                path = write_temp(f"https://example.com:{port}/a\n")
                try:
                    result = run(str(path), "--json")
                    self.assertEqual(result.returncode, 0 if valid else 1)
                    payload = json.loads(result.stdout)
                    self.assertEqual(payload["pass"], valid)
                    self.assertEqual(payload["urls"][0]["status"], "pass" if valid else "invalid")
                finally:
                    path.unlink()

    def test_malformed_authority_returns_validation_error(self):
        spec = importlib.util.spec_from_file_location("check_sources_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for url in ("https://[broken/a", "https://example.com:abc/a", "https://example.com:99999/a"):
            with self.subTest(url=url):
                self.assertIsNotNone(module.validate(url))

    def test_nonfinite_timeout_is_usage_error(self):
        for value in ("nan", "inf", "-inf"):
            with self.subTest(value=value):
                result = run("--timeout=" + value)
                self.assertEqual(result.returncode, 2)
                self.assertIn("--timeout", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

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

    def test_invalid_jobs_is_usage_error(self):
        result = run("--jobs", "0")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--jobs", result.stderr)

    def test_non_utf8_sources_file_is_usage_error(self):
        path = write_temp("placeholder")
        try:
            path.write_bytes("链接：https://example.com".encode("gbk"))
            result = run(str(path))
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("not valid UTF-8", result.stderr)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
