"""Regression tests for .github/scripts/validate_skill.py.

The validator is the only thing standing between a broken document and a
release (v1.8.0 shipped READMEs with a full duplicate copy because nothing
checked for it). These tests copy the repository to a temp directory, inject
the defect each guard is meant to catch, and assert that the validator fails.
"""
from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_main_does_not_carry_diagnostics_between_runs(self) -> None:
        root = self._copy_case("repeated-main")
        spec = importlib.util.spec_from_file_location("validator_repeat_test", root / VALIDATOR)
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
        readme = root / "README.md"
        original = readme.read_bytes()
        readme.write_bytes(original + b"\n# Second title\n")
        with patch.object(sys, "stdout", io.StringIO()) as first:
            self.assertEqual(validator.main(), 1)
        self.assertIn("一级标题", first.getvalue())
        readme.write_bytes(original)
        with redirect_stdout(io.StringIO()) as second:
            self.assertEqual(validator.main(), 0, second.getvalue())
        self.assertNotIn("一级标题", second.getvalue())

    def test_duplicate_section_is_rejected(self) -> None:
        root = self._copy_case("duplicate-section")
        readme = root / "README.md"
        text = readme.read_text(encoding="utf-8")
        readme.write_text(text + "\n## 特性\n\n重复粘贴的段落。\n", encoding="utf-8")
        result = run_validator(root)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("二级标题重复", result.stdout)

    def test_fence_with_info_string_does_not_close_code_block(self) -> None:
        root = self._copy_case("fence-info-string")
        readme = root / "README.md"
        with readme.open("a", encoding="utf-8") as document:
            document.write("\n```text\n```python\n# Literal heading\n```\n")
        result = run_validator(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_links_inside_fences_are_not_checked(self) -> None:
        root = self._copy_case("fenced-links")
        readme = root / "README.md"
        with readme.open("a", encoding="utf-8") as document:
            document.write("\n~~~markdown\n[Example](missing-example.md)\n~~~\n")
        result = run_validator(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with readme.open("a", encoding="utf-8") as document:
            document.write("\n[Actual link](missing-real.md)\n")
        result = run_validator(root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("missing-real.md", result.stdout)
        self.assertNotIn("missing-example.md", result.stdout)

    def test_relative_links_with_titles_or_angle_brackets(self) -> None:
        root = self._copy_case("link-destinations")
        (root / "with spaces.md").write_text("# Link target\n", encoding="utf-8")
        readme = root / "README.md"
        with readme.open("a", encoding="utf-8") as document:
            document.write('\n[Existing](README.en.md "Title (with parentheses)")\n')
            document.write('[Spaces](<with spaces.md> "Title")\n')
            document.write("[Encoded](with%20spaces.md?view=1#link-target)\n")
        result = run_validator(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with readme.open("a", encoding="utf-8") as document:
            document.write('\n[Missing](<no such file.md> "Title")\n')
        result = run_validator(root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("no such file.md", result.stdout)
        with readme.open("a", encoding="utf-8") as document:
            document.write("[Missing with parentheses](missing(copy).md)\n")
        result = run_validator(root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("missing(copy).md", result.stdout)
        with readme.open("a", encoding="utf-8") as document:
            document.write("[Missing encoded](missing%20encoded.md?view=1)\n")
            document.write("[Invalid UTF-8](%ff.md)\n")
        result = run_validator(root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("missing%20encoded.md?view=1", result.stdout)
        self.assertIn("无法检查链接 '%ff.md'", result.stdout)

    def test_fenced_numbered_headings_do_not_inflate_document_counts(self) -> None:
        root = self._copy_case("fenced-count-headings")
        for file, heading in (("specialized-prompts.md", "## 99. Sample"), ("sources.md", "### 99. Sample")):
            with (root / "references" / file).open("a", encoding="utf-8") as stream:
                stream.write(f"\n~~~markdown\n{heading}\n~~~\n")
        result = run_validator(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_example_marker_counts_match_the_executor(self) -> None:
        root = self._copy_case("marker-forms")
        runnable = root / "examples" / "go-legacy-order-total.md"
        runnable.write_text(runnable.read_text(encoding="utf-8").replace("<!-- verify:run", "<!--\nverify:run", 1), encoding="utf-8")
        illustration = root / "examples" / "java-order-calculator-strategy-c.md"
        with illustration.open("a", encoding="utf-8") as stream:
            stream.write("\nAn illustrative marker: `<!-- verify:file=sample.java -->`.\n")
        result = run_validator(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_generated_markdown_is_not_scanned_as_project_documentation(self) -> None:
        root = self._copy_case("generated-markdown")
        for directory in ("dist", "build", "node_modules", ".venv", "example.egg-info"):
            generated = root / directory
            generated.mkdir(exist_ok=True)
            (generated / "GENERATED.md").write_text("[not a project link](missing.md)\n", encoding="utf-8")
        result = run_validator(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (root / "references" / "genuine.md").write_text("[broken](missing.md)\n", encoding="utf-8")
        result = run_validator(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("references/genuine.md", result.stdout)

    def test_test_count_ignores_strings_and_nested_helpers(self) -> None:
        root = self._copy_case("test-count-literals")
        fixture = root / "scripts" / "tests" / "test_count_fixture.py"
        fixture.write_text(
            'SAMPLE = """\n    def test_literal(self): pass\n"""\n\n'
            'def helper():\n    def test_nested(): pass\n', encoding="utf-8",
        )
        result = run_validator(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with fixture.open("a", encoding="utf-8") as stream:
            stream.write("\nclass Sample:\n    async def test_real(self): pass\n")
        result = run_validator(root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        claimed = re.search(r"以\s*(\d+)\s*个用例", (root / "README.md").read_text(encoding="utf-8"))
        self.assertIn(f"实际 {int(claimed[1]) + 1} 个", result.stdout)

    def test_stale_test_count_is_rejected(self) -> None:
        root = self._copy_case("stale-test-count")
        readme = root / "README.md"
        text = readme.read_text(encoding="utf-8")
        updated = re.sub(r"以\s*\d+\s*个用例", "以 999999 个用例", text, count=1)
        self.assertNotEqual(text, updated)
        readme.write_text(updated, encoding="utf-8")
        result = run_validator(root)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("999999", result.stdout)

    def test_metadata_version_must_be_unique_and_inside_metadata(self) -> None:
        root = self._copy_case("skill-version-scope")
        skill = root / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        current = re.search(r'^  version:.*$', text, re.M)[0]
        for replacement in ("other:\n" + current, current + "\n" + current):
            with self.subTest(replacement=replacement):
                skill.write_text(text.replace(current, replacement, 1), encoding="utf-8")
                result = run_validator(root)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("metadata.version", result.stdout)

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


    def test_pyproject_version_drift_is_rejected(self) -> None:
        root = self._copy_case("pyproject-version-drift")
        pyproject = root / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8")
        updated = re.sub(r'^version = "\d+\.\d+\.\d+"', 'version = "0.0.0"', text, count=1, flags=re.M)
        self.assertNotEqual(text, updated)
        pyproject.write_text(updated, encoding="utf-8")
        result = run_validator(root)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("pyproject.toml", result.stdout)

    def test_duplicate_project_versions_are_rejected(self) -> None:
        root = self._copy_case("pyproject-duplicate-version")
        project = root / "pyproject.toml"
        text = project.read_text(encoding="utf-8")
        original = re.search(r'^version = "[^"]+"$', text, re.M)[0]
        for duplicate in (original, '  version = "0.0.0" # conflicting version'):
            with self.subTest(duplicate=duplicate):
                project.write_text(text.replace(original, original + "\n" + duplicate, 1), encoding="utf-8")
                result = run_validator(root)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("version 重复", result.stdout)

    def test_pyproject_other_section_version_is_ignored(self) -> None:
        root = self._copy_case("pyproject-other-version")
        pyproject = root / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8")
        updated = '[tool.other]\nversion = "9.9.9"\n\n' + text
        self.assertNotEqual(text, updated)
        pyproject.write_text(updated, encoding="utf-8")
        result = run_validator(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_hook_entry_drift_is_rejected(self) -> None:
        root = self._copy_case("hook-entry-drift")
        hooks = root / ".pre-commit-hooks.yaml"
        text = hooks.read_text(encoding="utf-8")
        updated = text.replace(
            "entry: code-refactor-prompt-check --strict",
            "entry: python3 scripts/check_prompt.py --strict",
        )
        self.assertNotEqual(text, updated)
        hooks.write_text(updated, encoding="utf-8")
        result = run_validator(root)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(".pre-commit-hooks.yaml", result.stdout)

    def test_duplicate_h1_is_rejected(self) -> None:
        root = self._copy_case("duplicate-h1")
        readme = root / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8") + "\n# Second title\n", encoding="utf-8"
        )
        result = run_validator(root)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("一级标题", result.stdout)

if __name__ == "__main__":
    unittest.main()
