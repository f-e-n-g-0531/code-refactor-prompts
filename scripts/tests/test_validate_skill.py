"""Regression tests for .github/scripts/validate_skill.py.

The validator is the only thing standing between a broken document and a
release (v1.8.0 shipped READMEs with a full duplicate copy because nothing
checked for it). These tests copy the repository to a temp directory, inject
the defect each guard is meant to catch, and assert that the validator fails.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VALIDATOR = Path(".github") / "scripts" / "validate_skill.py"


def copy_repo(dest: Path) -> None:
    shutil.copytree(
        REPO,
        dest,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "dist", "build", "*.egg-info", ".venv"),
    )


def run_validator(root: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [sys.executable, str(root / VALIDATOR)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


class ValidatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls._root = Path(cls._tmp.name)
        cls._pristine = cls._root / "pristine"
        copy_repo(cls._pristine)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def _copy_case(self, name: str) -> Path:
        dest = self._root / name
        shutil.copytree(self._pristine, dest)
        return dest

    def test_pristine_repo_passes(self) -> None:
        result = run_validator(self._pristine)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_duplicate_section_is_rejected(self) -> None:
        root = self._copy_case("duplicate-section")
        readme = root / "README.md"
        text = readme.read_text(encoding="utf-8")
        readme.write_text(text + "\n## 特性\n\n重复粘贴的段落。\n", encoding="utf-8")
        result = run_validator(root)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("二级标题重复", result.stdout)

    def test_stale_test_count_is_rejected(self) -> None:
        root = self._copy_case("stale-test-count")
        readme = root / "README.md"
        text = readme.read_text(encoding="utf-8")
        updated = re.sub(r"以\s*\d+\s*个用例", "以 99 个用例", text, count=1)
        self.assertNotEqual(text, updated)
        readme.write_text(updated, encoding="utf-8")
        result = run_validator(root)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("99", result.stdout)

    def test_version_drift_is_rejected(self) -> None:
        root = self._copy_case("version-drift")
        readme = root / "README.md"
        text = readme.read_text(encoding="utf-8")
        updated = re.sub(r"rev:\s*v\d+\.\d+\.\d+", "rev: v0.0.0", text, count=1)
        self.assertNotEqual(text, updated)
        readme.write_text(updated, encoding="utf-8")
        result = run_validator(root)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("不一致", result.stdout)


if __name__ == "__main__":
    unittest.main()
