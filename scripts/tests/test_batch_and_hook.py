"""Regression tests for batch mode and the pre-commit hook contract.

Run with:  python3 -m unittest discover -s scripts/tests -p "test_*.py" -v
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        result = run_checker(str(self.dir), "--json", "--skeleton")
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["pass"])
        self.assertEqual(payload["passed"], 1)
        self.assertEqual(payload["failed"], 1)
        self.assertEqual(len(payload["results"]), 2)
        for item in payload["results"]:
            self.assertIn("skeleton", item)
            self.assertIn("skeleton_segments", item)
            self.assertIn("strict", item)
        failing = [item for item in payload["results"] if not item["pass"]][0]
        self.assertTrue(failing["skeleton"])
        self.assertTrue(failing["skeleton_segments"])

    def test_include_override(self):
        self.write("custom.md", GOOD)
        default = run_checker(str(self.dir))
        self.assertEqual(default.returncode, 2)
        custom = run_checker(str(self.dir), "--include", "*.md")
        self.assertEqual(custom.returncode, 0, custom.stdout + custom.stderr)

    def test_absolute_include_is_reported_as_usage_error(self):
        self.write("good.prompt.txt", GOOD)
        result = run_checker(str(self.dir), "--include", str(self.dir / "*.txt"))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("--include", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_empty_directory_is_usage_error(self):
        empty = self.dir / "empty"
        empty.mkdir()
        (empty / "folder.prompt").mkdir()
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

    def test_github_annotations_in_batch(self):
        self.write("good.prompt.txt", GOOD)
        self.write("bad.prompt.txt", BAD)
        result = run_checker(str(self.dir), "--format", "github")
        self.assertEqual(result.returncode, 1)
        errors = [line for line in result.stdout.splitlines() if line.startswith("::error")]
        self.assertTrue(any("bad.prompt.txt" in line for line in errors))
        self.assertFalse(any("good.prompt.txt" in line for line in errors))
        self.assertIn("1 passed, 1 failed", result.stdout)

    def test_stdin_cannot_be_combined(self):
        target = self.write("good.prompt.txt", GOOD)
        result = run_checker("-", str(target))
        self.assertEqual(result.returncode, 2)


class PreCommitHookTest(unittest.TestCase):
    def test_shared_hook_gate_uses_expected_exits_and_cleans_up(self):
        spec = importlib.util.spec_from_file_location("verify_precommit_test", ROOT / ".github/scripts/verify_precommit.py")
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        for bad_exit in (1, 0, 3):
            with self.subTest(bad_exit=bad_exit), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                fixtures = root / "scripts" / "fixtures"
                fixtures.mkdir(parents=True)
                for name, text in (("good", GOOD), ("bad", BAD)):
                    (fixtures / f"{name}-prompt.txt").write_text(text, encoding="utf-8")
                calls = []

                def run(args, **kwargs):
                    self.assertEqual(kwargs["cwd"], root)
                    calls.append(args)
                    if args[0] == "git":
                        self.assertEqual(args, ["git", "rev-parse", "--verify", "HEAD"])
                        return subprocess.CompletedProcess(args, 0, stdout="a" * 40 + "\n")
                    if args[2] == "pip":
                        return subprocess.CompletedProcess(args, 0)
                    self.assertEqual(args[2:-1], ["pre_commit", "try-repo", ".", "--ref", "a" * 40, "--files"])
                    self.assertTrue(Path(kwargs["env"]["PRE_COMMIT_HOME"]).parent.is_dir())
                    expected_seeder = os.environ.get("VIRTUALENV_SEEDER", "pip" if os.name == "nt" else None)
                    self.assertEqual(kwargs["env"].get("VIRTUALENV_SEEDER"), expected_seeder)
                    file = root / args[-1]
                    self.assertTrue(file.is_file())
                    is_bad = file.name.startswith("bad")
                    self.assertEqual(file.read_text(encoding="utf-8"), BAD if is_bad else GOOD)
                    return subprocess.CompletedProcess(args, bad_exit if is_bad else 0)

                with patch.object(gate.venv.EnvBuilder, "create"), patch.object(gate.subprocess, "run", side_effect=run):
                    if bad_exit == 1:
                        gate.verify(root)
                    else:
                        with self.assertRaisesRegex(RuntimeError, f"got {bad_exit}"):
                            gate.verify(root)
                self.assertEqual(len(calls), 4)
                self.assertFalse(Path(calls[1][0]).parents[1].exists())
                self.assertEqual(list(root.glob(".pre-commit-e2e-*")), [])

    def test_hook_definition_calls_the_installed_console_script(self):
        text = HOOKS.read_text(encoding="utf-8")
        self.assertIn("entry: code-refactor-prompt-check --strict", text)
        self.assertIn("language: python", text)
        self.assertIn("pass_filenames: true", text)
        self.assertIn("files:", text)
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('code-refactor-prompt-check = "check_prompt:main"', pyproject)
        self.assertIn('py-modules = ["check_prompt"]', pyproject)

    def test_action_definition_supports_changed_only(self):
        action = (ROOT / "action.yml").read_text(encoding="utf-8")
        for marker in ("changed-only", "BASE_SHA", "--changed"):
            self.assertIn(marker, action)

    @unittest.skipUnless(os.name != "nt" and shutil.which("bash"), "requires a Bash runner")
    def test_action_run_handles_paths_and_a_root_commit(self):
        action = (ROOT / "action.yml").read_text(encoding="utf-8")
        run = action.split("      run: |\n", 1)[1]
        script = "\n".join(line[8:] for line in run.splitlines())
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            (repo / "Draft Prompts").mkdir()
            first = "Draft Prompts/bad.prompt.md"
            second = "good.prompt.txt"
            (repo / first).write_text(BAD, encoding="utf-8")
            (repo / second).write_text(GOOD, encoding="utf-8")
            for git_args in (("init", "-q"), ("add", "--", first, second),
                             ("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "root")):
                subprocess.run(["git", *git_args], cwd=repo, check=True, capture_output=True)
            for paths, changed, expected in ((first, False, 1), (f"{first}\n{second}", False, 1),
                                             (second, False, 0), (".", False, 1), (".", True, 1)):
                with self.subTest(paths=paths, changed=changed):
                    result = subprocess.run(
                        ["bash", "-c", script], cwd=repo, capture_output=True, text=True, encoding="utf-8",
                        env={**os.environ, "GITHUB_ACTION_PATH": str(ROOT), "INPUT_FILES": paths,
                             "INPUT_INCLUDE": "", "INPUT_STRICT": "true",
                             "INPUT_CHANGED_ONLY": str(changed).lower(), "BASE_SHA": "0" * 40},
                    )
                    self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                    if expected:
                        self.assertIn(first, result.stdout)
                    if not changed and "\n" in paths:
                        self.assertIn("1 passed, 1 failed", result.stdout)

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
