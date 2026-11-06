"""Release tags must identify the checked-out version, not a historical heading."""
from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout, redirect_stderr

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("release_notes", ROOT / ".github/scripts/release_notes.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseNotesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "SKILL.md").write_text('---\nmetadata:\n  version: "1.2.3"\n---\n', encoding="utf-8")
        (self.root / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")

    def test_matching_current_tag(self):
        self.assertEqual(release.validate_tag("v1.2.3", self.root), "1.2.3")

    def test_unsafe_or_noncanonical_tags_rejected(self):
        for tag in ("1.2.3", "V1.2.3", "v1.2", "v01.2.3", "v1.2.3-rc1", "v1.2.3\nx=y",
                    "v1.2.3$(touch pwned)", "v1.2.3;echo bad", " v1.2.3", "v1.2.3\n"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                release.validate_tag(tag, self.root)

    def test_historical_tag_rejected_even_with_changelog_heading(self):
        (self.root / "CHANGELOG.md").write_text("## [1.0.0]\nOld release\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "must match current"):
            release.validate_tag("v1.0.0", self.root)

    def test_either_metadata_version_drift_rejected(self):
        for filename in ("SKILL.md", "pyproject.toml"):
            with self.subTest(filename=filename):
                path = self.root / filename
                before = path.read_text(encoding="utf-8")
                path.write_text(before.replace("1.2.3", "1.2.4"), encoding="utf-8")
                with self.assertRaises(ValueError):
                    release.validate_tag("v1.2.3", self.root)
                path.write_text(before, encoding="utf-8")

    def test_missing_or_out_of_section_versions_rejected(self):
        (self.root / "pyproject.toml").write_text('[tool.other]\nversion = "1.2.3"\n', encoding="utf-8")
        with self.assertRaises(ValueError):
            release.validate_tag("v1.2.3", self.root)

    def test_skill_version_accepts_any_indentation(self):
        (self.root / "SKILL.md").write_text(
            '---\nmetadata:\n    version: "1.2.3"\n---\n', encoding="utf-8"
        )
        self.assertEqual(release.validate_tag("v1.2.3", self.root), "1.2.3")

    def test_cli_rejects_tag_before_emitting_notes(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(release.sys, "argv", ["release_notes.py", "v0.0.0"]), redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(release.main(), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("must match current", stderr.getvalue())

    def test_cli_missing_changelog_section_rejected(self):
        (self.root / "CHANGELOG.md").write_text("# Changes\n", encoding="utf-8")
        with patch.object(release, "ROOT", self.root), patch.object(release, "validate_tag", return_value="1.2.3"), patch.object(release.sys, "argv", ["release_notes.py", "v1.2.3"]), redirect_stderr(io.StringIO()):
            self.assertEqual(release.main(), 1)


if __name__ == "__main__":
    unittest.main()
