"""Exercise the actual distribution, including the fast gate after extraction."""
from __future__ import annotations

import importlib.util
import hashlib
import io
import shutil
import stat
import tarfile
import warnings
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
            # On Python 3.9, TemporaryDirectory.cleanup() can transform a
            # locked file into NotADirectoryError and detach its finalizer.
            shutil.rmtree(directory.name)
        except FileNotFoundError:
            if Path(directory.name).exists():
                raise
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)
            continue
        directory.cleanup()  # detach the finalizer after successful removal
        return


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

    def test_repeated_builds_are_byte_identical(self):
        with patch.object(time, "time", return_value=1_000_000_000):
            first = package.build(ROOT, self.output / "first", "repro")
        with patch.object(time, "time", return_value=1_700_000_000):
            second = package.build(ROOT, self.output / "second", "repro")
        for left, right in zip(first, second):
            self.assertEqual(left.read_bytes(), right.read_bytes(), left.name)
        self.assertEqual((first[0].parent / "SHA256SUMS.txt").read_bytes(),
                         (second[0].parent / "SHA256SUMS.txt").read_bytes())
        with zipfile.ZipFile(first[0]) as archive:
            self.assertTrue(all(member.date_time == (1980, 1, 1, 0, 0, 0)
                                for member in archive.infolist()))
        self.assertEqual(first[1].read_bytes()[4:8], bytes(4))  # gzip mtime

    @unittest.skipIf(
        any(os.environ.get(flag) == "1" for flag in ("PACKAGE_GATE_CHILD", "SKIP_NESTED_PACKAGE_VERIFY")),
        "both archives are verified by the parent or a dedicated workflow step",
    )
    def test_real_extracted_archives_run_fast_gate(self):
        package.verify(package.build(ROOT, self.output, "integration"), ROOT)

    def refresh_checksums(self, archives):
        (self.output / "SHA256SUMS.txt").write_text("".join(
            hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n"
            for path in archives), encoding="utf-8")

    def test_duplicate_zip_member_rejected_before_execution(self):
        archives = package.build(ROOT, self.output, "duplicate")
        name = package.PREFIX + "/README.md"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(archives[0], "a") as archive:
                archive.writestr(name, (ROOT / "README.md").read_bytes())
        self.refresh_checksums(archives)
        with patch.object(package.subprocess, "run") as run, self.assertRaisesRegex(ValueError, "duplicate archive entry"):
            package.verify(archives, ROOT)
        run.assert_not_called()

    def test_duplicate_tar_member_rejected_before_any_execution(self):
        archives = package.build(ROOT, self.output, "duplicate")
        files = package.package_files(ROOT)
        with tarfile.open(archives[1], "w:gz") as archive:
            for name, data in list(files.items()) + [("README.md", files["README.md"])]:
                member = tarfile.TarInfo(package.PREFIX + "/" + name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        self.refresh_checksums(archives)
        with patch.object(package.subprocess, "run") as run, self.assertRaisesRegex(ValueError, "duplicate archive entry"):
            package.verify(archives, ROOT)
        run.assert_not_called()

    def test_zip_symlink_metadata_rejected(self):
        archives = package.build(ROOT, self.output, "symlink")
        files = package.package_files(ROOT)
        with zipfile.ZipFile(archives[0], "w") as archive:
            for name, data in files.items():
                member = zipfile.ZipInfo(package.PREFIX + "/" + name)
                member.create_system = 3
                member.external_attr = ((stat.S_IFLNK if name == "README.md" else stat.S_IFREG) | 0o644) << 16
                archive.writestr(member, data)
        self.refresh_checksums(archives)
        with patch.object(package.subprocess, "run") as run, self.assertRaisesRegex(ValueError, "unexpected archive entry"):
            package.verify(archives, ROOT)
        run.assert_not_called()

    def test_checksum_manifest_rejects_duplicate_conflicting_and_extra_entries(self):
        archives = package.build(ROOT, self.output, "manifest")
        manifest = self.output / "SHA256SUMS.txt"
        original = manifest.read_text(encoding="utf-8")
        first_line = original.splitlines()[0]
        for line in (first_line, "0" * 64 + "  " + archives[0].name, "0" * 64 + "  extra.zip"):
            with self.subTest(line=line):
                manifest.write_text(original + line + "\n", encoding="utf-8")
                with patch.object(package.subprocess, "run") as run, self.assertRaisesRegex(ValueError, "checksum"):
                    package.verify(archives, ROOT)
                run.assert_not_called()

    def test_archive_hash_and_parser_use_the_same_snapshot(self):
        archives = package.build(ROOT, self.output, "snapshot")
        with patch.object(package.zipfile, "ZipFile", wraps=zipfile.ZipFile) as open_zip, patch.object(
            package.tarfile, "open", wraps=tarfile.open,
        ) as open_tar, patch.object(package.subprocess, "run"):
            package.verify(archives, ROOT)
        self.assertIsInstance(open_zip.call_args.args[0], io.BytesIO)
        self.assertIsInstance(open_tar.call_args.kwargs["fileobj"], io.BytesIO)

    def test_second_archive_checksum_failure_prevents_first_gate(self):
        archives = package.build(ROOT, self.output, "checksum")
        checksum = self.output / "SHA256SUMS.txt"
        checksum.write_text(checksum.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")
        with patch.object(package.subprocess, "run") as run, self.assertRaisesRegex(ValueError, "checksum mismatch"):
            package.verify(archives, ROOT)
        run.assert_not_called()

    def test_verification_requires_both_release_formats(self):
        archives = package.build(ROOT, self.output, "formats")
        self.refresh_checksums(archives[:1])
        with patch.object(package.subprocess, "run") as run, self.assertRaisesRegex(ValueError, "require.*ZIP.*tar.gz"):
            package.verify(archives[:1], ROOT)
        run.assert_not_called()

    def test_empty_archive_set_does_not_claim_success(self):
        with patch.object(package.subprocess, "run") as run, self.assertRaisesRegex(ValueError, "no release archives"):
            package.verify([], ROOT)
        run.assert_not_called()

    def test_missing_dependency_is_rejected(self):
        files = package.package_files(ROOT)
        root = Path(self.tmp.name) / "broken"
        for name, data in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for rel in (".github/scripts/audit_templates.py", "scripts/tests/test_audit_templates.py",
                    "scripts/tests/test_package_skill.py", "scripts/tests/test_release_notes.py"):
            (root / rel).unlink()
        with patch.object(validator, "ROOT", root), patch.object(validator, "errors", []):
            validator.check_required_files()
            self.assertEqual(len(validator.errors), 4)
            for name in ("audit_templates.py", "test_audit_templates.py", "test_package_skill.py", "test_release_notes.py"):
                self.assertTrue(any(error.endswith("/" + name) for error in validator.errors), name)

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
