"""Exercise the actual distribution, including the fast gate after extraction."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import time
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / ".github/scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


package = load("package_skill")
validator = load("validate_skill")


def cleanup_retrying(directory: tempfile.TemporaryDirectory, attempts: int = 6, delay: float = 0.5) -> None:
    """Remove a TemporaryDirectory, tolerating transient external holds on Windows.

    Freshly written archives are occasionally held briefly by external tools
    (indexer / scanner), making the first rmtree raise PermissionError
    (WinError 32) - the intermittent failure observed in full-gate runs.
    Retry a bounded number of times and re-raise when the hold persists, so a
    real handle leak still fails the test loudly.
    """
    for attempt in range(attempts):
        try:
            directory.cleanup()
            return
        except FileNotFoundError:
            return  # already removed
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)


class PackageSkillTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(cleanup_retrying, self.tmp)
        self.output = Path(self.tmp.name) / "dist"

    def test_manifest_contains_gate_dependencies_not_workflows(self):
        files = package.package_files(ROOT)
        for name in validator.REQUIRED_FILES:
            self.assertIn(name, files)
        self.assertIn(".skill-package", files)
        self.assertFalse(any(name.startswith(".github/") and not name.startswith(".github/scripts/") for name in files))
        self.assertFalse(any("__pycache__" in name or name.endswith(".pyc") for name in files))

    def test_archive_formats_have_identical_bytes_and_checksums(self):
        archives = package.build(ROOT, self.output, "test")
        # Content/checksum verification still runs; only the expensive gate is stubbed here.
        with patch.object(package.subprocess, "run") as run:
            package.verify(archives, ROOT)
        self.assertEqual(run.call_count, 2)
        self.assertTrue(all(call.kwargs["check"] for call in run.call_args_list))

    @unittest.skipIf(os.environ.get("PACKAGE_GATE_CHILD") == "1", "avoid recursively packaging the package gate")
    def test_real_extracted_archives_run_fast_gate(self):
        package.verify(package.build(ROOT, self.output, "integration"), ROOT)

    def test_missing_dependency_is_rejected(self):
        files = package.package_files(ROOT)
        root = Path(self.tmp.name) / "broken"
        for name, data in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (root / ".github/scripts/audit_templates.py").unlink()
        with patch.object(validator, "ROOT", root), patch.object(validator, "errors", []):
            validator.check_required_files()
            self.assertTrue(any("audit_templates.py" in error for error in validator.errors))

    def test_repository_still_requires_workflows(self):
        with patch.object(validator, "ROOT", Path(self.tmp.name)), patch.object(validator, "errors", []):
            validator.check_required_files()
            self.assertTrue(any("workflows/ci.yml" in error for error in validator.errors))

    def test_unsafe_package_labels_rejected(self):
        for label in ("../escape", "a/b", "a\\b", "x;echo bad", "", "a\n"):
            with self.subTest(label=label), self.assertRaises(ValueError):
                package.build(ROOT, self.output, label)

    def test_tampered_archive_rejected_before_execution(self):
        archives = package.build(ROOT, self.output, "test")
        with zipfile.ZipFile(archives[0], "a") as archive:
            archive.writestr("../escape", b"bad")
        with patch.object(package.subprocess, "run") as run, self.assertRaisesRegex(ValueError, "contents mismatch"):
            package.verify(archives, ROOT)
        run.assert_not_called()

    def test_tampered_checksum_rejected_before_execution(self):
        archives = package.build(ROOT, self.output, "test")
        (self.output / "SHA256SUMS.txt").write_text("invalid", encoding="utf-8")
        with patch.object(package.subprocess, "run") as run, self.assertRaisesRegex(ValueError, "checksum mismatch"):
            package.verify(archives, ROOT)
        run.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows-only file-share semantics")
    def test_cleanup_retries_and_still_fails_on_persistent_lock(self):
        """Transient external holds must not fail cleanup; persistent ones still must."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(cleanup_retrying, tmp)
        target = Path(tmp.name) / "held.zip"
        target.write_bytes(b"data")
        handle = os.open(target, os.O_RDWR)  # no FILE_SHARE_DELETE on Windows
        try:
            with self.assertRaises(PermissionError):
                cleanup_retrying(tmp, attempts=2, delay=0.01)
            self.assertTrue(Path(tmp.name).exists(), "persistent lock must not be masked")
        finally:
            os.close(handle)
        cleanup_retrying(tmp, attempts=1)
        self.assertFalse(Path(tmp.name).exists(), "cleanup succeeds once the hold is gone")


if __name__ == "__main__":
    unittest.main()
