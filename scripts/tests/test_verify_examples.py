"""Regression tests for the executable-example gate (no external SDK required)."""
from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("verify_examples_under_test", ROOT / ".github/scripts/verify_examples.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def document(names=("main.py",), command="python main.py"):
    return "<!-- verify:run\n" + command + "\n-->\n" + "".join(
        "<!-- verify:file=" + name + " -->\n```python\nprint(42)\n```\n" for name in names
    )


class VerifyExamplesTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "example.md"

    def save(self, text):
        self.path.write_bytes(text.encode("utf-8"))
        return self.path

    def test_valid_nested_files_and_crlf(self):
        files, commands = verifier.parse_example(self.save(document(("src/main.py",)).replace("\n", "\r\n")))
        self.assertEqual(files, [("src/main.py", "print(42)")])
        self.assertEqual(commands, ["python main.py"])

    def test_illustration_without_markers_is_skipped(self):
        for text in ("# Illustration\n", "Markers look like `<!-- verify:file=... -->` in prose.\n"):
            self.assertEqual(verifier.verify_example(self.save(text)), ("skipped", []))

    def test_fenced_documentation_markers_are_not_executed(self):
        fence = "~~~~"
        sample = fence + "markdown\n" + document() + fence + "\n"
        self.assertEqual(verifier.parse_example(self.save(sample)), ([], []))
        files, commands = verifier.parse_example(self.save(sample + document()))
        self.assertEqual(files, [("main.py", "print(42)")])
        self.assertEqual(commands, ["python main.py"])

    def test_inline_marker_does_not_join_real_markers(self):
        text = document() + "Prose: <!-- verify:run\npython ignored.py\n-->\n"
        _, commands = verifier.parse_example(self.save(text))
        self.assertEqual(commands, ["python main.py"])

    def test_multiline_comment_prefix_is_still_recognised(self):
        text = document().replace("<!-- verify:", "<!--\nverify:")
        files, commands = verifier.parse_example(self.save(text))
        self.assertEqual(files, [("main.py", "print(42)")])
        self.assertEqual(commands, ["python main.py"])

    def test_malformed_markers_rejected_before_side_effects(self):
        valid = document()
        texts = [
            valid.replace("verify:run\npython main.py\n", "verify:run python main.py"),
            valid.replace("verify:run", "verify:runbroken"),
            valid.replace("verify:file=main.py", "verify:file= main.py"),
            valid.replace("```python", "not a fence"),
            "<!-- verify:file=main.py -->\n```python\npass\n```\n",
            valid + "<!-- verify:file=lost.py -->\n",
        ]
        for text in texts:
            with self.subTest(text=text), patch.object(verifier.tempfile, "mkdtemp") as create, patch.object(verifier.subprocess, "run") as run:
                with self.assertRaises(verifier.ExampleError):
                    verifier.verify_example(self.save(text))
                create.assert_not_called()
                run.assert_not_called()

    def test_multiple_run_blocks_rejected(self):
        with self.assertRaises(verifier.ExampleError):
            verifier.parse_example(self.save(document() + "<!-- verify:run\npython other.py\n-->\n"))

    def test_empty_commands_or_missing_files_rejected(self):
        for text in (document(command="# comment only"), "<!-- verify:run\npython main.py\n-->\n"):
            with self.subTest(text=text), self.assertRaises(verifier.ExampleError):
                verifier.parse_example(self.save(text))

    def test_unsafe_portable_paths_rejected_before_temp_creation(self):
        names = ("/escape.py", "\\escape.py", "C:escape.py", "C:/escape.py", "C:\\escape.py",
                 "../escape.py", "src/../escape.py", "./main.py", "src//main.py",
                 "main.py:stream", "NUL.py", "src/CON", "main.py.")
        for name in names:
            with self.subTest(name=name), patch.object(verifier.tempfile, "mkdtemp") as create, patch.object(Path, "mkdir"), patch.object(Path, "write_text"), patch.object(verifier.subprocess, "run"):
                with self.assertRaises(verifier.ExampleError):
                    verifier.verify_example(self.save(document((name,))))
                create.assert_not_called()

    def test_duplicate_or_conflicting_targets_rejected(self):
        for names in (("main.py", "main.py"), ("Main.py", "main.py"), ("src", "src/main.py"), ("src/main.py", "SRC")):
            with self.subTest(names=names), self.assertRaises(verifier.ExampleError):
                verifier.parse_example(self.save(document(names)))

    def test_python_example_really_executes_and_cleans_up(self):
        path = self.save(document())
        original = verifier.tempfile.mkdtemp
        created = []
        def create(**kwargs):
            result = original(**kwargs)
            created.append(Path(result))
            return result
        with patch.object(verifier.tempfile, "mkdtemp", side_effect=create):
            self.assertEqual(verifier.verify_example(path), ("passed", ["python main.py"]))
        self.assertTrue(created)
        self.assertTrue(all(not p.exists() for p in created))

    def test_python_command_preserves_quoted_whitespace(self):
        command = 'python3 -c "import sys; assert sys.argv[1] == chr(97)+chr(32)*2+chr(98)" "a  b"'
        self.assertEqual(verifier.verify_example(self.save(document(command=command))),
                         ("passed", [command]))

    def test_command_failure_is_not_success_and_cleans_up(self):
        path = self.save(document(command="python -c \"raise SystemExit(7)\""))
        with self.assertRaisesRegex(verifier.ExampleError, r"command failed \(7\)"):
            verifier.verify_example(path)

    def test_cleanup_failure_does_not_hide_command_failure(self):
        for exit_code in (0, 7):
            with self.subTest(exit_code=exit_code):
                path = self.save(document(command=f'python -c "raise SystemExit({exit_code})"'))
                work = self.path.parent / "work"
                work.mkdir(exist_ok=True)
                with patch.object(verifier.tempfile, "mkdtemp", return_value=str(work)), patch.object(
                    verifier, "remove_tree_with_retry", side_effect=PermissionError("still locked"),
                ), self.assertRaises(verifier.ExampleError) as failure:
                    verifier.verify_example(path)
                message = str(failure.exception)
                self.assertIn("cannot clean up temporary directory", message)
                self.assertIn("still locked", message)
                self.assertIn(str(work), message)
                if exit_code:
                    self.assertIn("command failed (7)", message)

    def test_missing_toolchain_creates_no_temp_directory(self):
        path = self.save(document(command="go test ./..."))
        with patch.object(verifier, "tool_available", return_value=False), patch.object(verifier.tempfile, "mkdtemp") as create:
            self.assertEqual(verifier.verify_example(path), ("missing-toolchain", ["go"]))
            create.assert_not_called()

    def test_bad_utf8_reports_failure_and_continues(self):
        bad = self.path.parent / "a-invalid.md"
        bad.write_bytes(bytes([255]))
        self.save(document())
        with patch.object(verifier, "EXAMPLES", self.path.parent), patch.object(sys, "argv", ["verify_examples.py", "--require-all"]), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(verifier.main(), 1)
        self.assertIn("FAIL a-invalid", output.getvalue())
        self.assertIn("not valid UTF-8", output.getvalue())
        self.assertIn("PASS example", output.getvalue())
        self.assertIn("1 example(s) executed green, 1 failure(s)", output.getvalue())

    def test_unreadable_example_reports_path_context(self):
        with patch.object(Path, "read_text", side_effect=PermissionError("access denied")):
            with self.assertRaisesRegex(verifier.ExampleError, "cannot read example document: access denied"):
                verifier.parse_example(self.path)

    def test_require_all_rejects_zero_executed_examples(self):
        for content in (None, "# Illustration\n"):
            if content is not None:
                self.save(content)
            with self.subTest(content=content), patch.object(verifier, "EXAMPLES", self.path.parent), patch.object(sys, "argv", ["verify_examples.py", "--require-all"]), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(verifier.main(), 1)
                self.assertIn("no executable examples", output.getvalue())

    def test_repository_markers_still_parse(self):
        runnable = [p for p in sorted((ROOT / "examples").glob("*.md")) if verifier.parse_example(p)[1]]
        self.assertEqual(len(runnable), 7)


if __name__ == "__main__":
    unittest.main()
