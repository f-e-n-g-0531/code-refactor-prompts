"""Regression tests for scripts/check_prompt.py.

Run with:  python3 -m unittest discover -s scripts/tests -p "test_*.py" -v
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scripts" / "check_prompt.py"
FIXTURES = ROOT / "scripts" / "fixtures"


def load_checker():
    spec = importlib.util.spec_from_file_location("check_prompt_under_test", CHECKER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


checker = load_checker()

FENCE_LANGUAGES = {
    "java": "java",
    "python": "python",
    "go": "go",
    "rust": "rust",
    "typescript": "ts",
    "javascript": "js",
    "csharp": "csharp",
    "kotlin": "kotlin",
    "swift": "swift",
    "ruby": "ruby",
    "php": "php",
    "cpp": "cpp",
    "sql": "sql",
}

TEST_COMMANDS = {
    "java": "mvn test",
    "python": "pytest",
    "go": "go test ./...",
    "rust": "cargo test",
    "typescript": "npm test",
    "javascript": "npm test",
    "csharp": "dotnet test",
    "kotlin": "gradle test",
    "swift": "swift test",
    "ruby": "rspec",
    "php": "phpunit",
    "cpp": "ctest",
    "sql": "期望结果集对比",
}

CODE_SNIPPETS = {
    "java": "class Example {}",
    "python": "def example():\n    pass",
    "go": "package example",
    "rust": "fn example() {}",
    "typescript": "const example: number = 1;",
    "javascript": "const example = 1;",
    "csharp": "class Example {}",
    "kotlin": "fun example() {}",
    "swift": "func example() {}",
    "ruby": "def example; end",
    "php": "<?php echo 1;",
    "cpp": "int main() { return 0; }",
    "sql": "SELECT 1;",
}

PROMPT = """你是资深 {language} 工程师。

【前置判断】
- 未提供代码：输出 NO_CODE_PROVIDED 并索取代码。

【上下文】
- 项目/模块：示例
- 语言与框架：{language}

【待重构代码】
```{fence}
{code}
```

【硬约束】
1. 外部行为 100% 一致：不改公开 API、返回值与异常类型。

【重构目标】
1. 拆分长函数，提取子方法。

【验收标准】
- 测试命令：{command}
- 用例：给定输入 → 期望输出

【输出格式】
1. 问题清单；
2. 统一 diff（声明基线文件）。
"""

FIXTURE_EXPECTATIONS = [
    ("good-prompt.txt", True),
    ("good-go-prompt.txt", True),
    ("good-en-prompt.txt", True),
    ("weak-prompt.txt", True),
    ("bad-prompt.txt", False),
    ("bad-language-prompt.txt", False),
    ("bad-antipattern-prompt.txt", False),
    ("bad-en-prompt.txt", False),
]

ZH_ANTI_PATTERNS = [
    ("顺便把测试也改一下", "test-tampering"),
    ("把整个项目重构一遍", "boil-the-ocean"),
    ("用你熟悉的最佳实践重写", "appeal-to-best-practice"),
    ("性能更好、可读性更强", "unmeasurable-goal"),
]

EN_ANTI_PATTERNS = [
    ("Also update the tests to match.", "test-tampering"),
    ("Rewrite the entire project.", "boil-the-ocean"),
    ("Use your favourite best practices.", "appeal-to-best-practice"),
    ("Make it cleaner and faster.", "unmeasurable-goal"),
]


def run_checker(*args, input_text=None, cwd=None):
    return subprocess.run(
        [sys.executable, str(CHECKER), *args],
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


class FixtureTest(unittest.TestCase):
    def test_fixtures(self):
        for name, expected_pass in FIXTURE_EXPECTATIONS:
            with self.subTest(fixture=name):
                result = checker.check((FIXTURES / name).read_text(encoding="utf-8"))
                self.assertEqual(result["pass"], expected_pass)

    def test_language_matrix_explicit(self):
        for language in FENCE_LANGUAGES:
            with self.subTest(language=language):
                prompt = PROMPT.format(
                    language=language,
                    fence=FENCE_LANGUAGES[language],
                    code=CODE_SNIPPETS[language],
                    command=TEST_COMMANDS[language],
                )
                result = checker.check(prompt, explicit_language=language)
                self.assertTrue(result["pass"], result["errors"])
                self.assertEqual(result["languages"], [language])

    def test_language_matrix_auto_detect(self):
        for language in FENCE_LANGUAGES:
            with self.subTest(language=language):
                prompt = PROMPT.format(
                    language=language,
                    fence=FENCE_LANGUAGES[language],
                    code=CODE_SNIPPETS[language],
                    command=TEST_COMMANDS[language],
                )
                result = checker.check(prompt)
                self.assertTrue(result["pass"], result["errors"])
                self.assertIn(language, result["languages"])

    def test_language_mismatch_is_an_error(self):
        prompt = PROMPT.format(
            language="Go", fence="go", code="package example", command="mvn test"
        )
        result = checker.check(prompt)
        self.assertFalse(result["pass"])
        self.assertIn("language-mismatch", [item["code"] for item in result["errors"]])

    def test_explicit_language_override_mismatch(self):
        template = (FIXTURES / "good-prompt.txt").read_text(encoding="utf-8")
        result = checker.check(template, explicit_language="python")
        self.assertFalse(result["pass"])
        self.assertIn("language-mismatch", [item["code"] for item in result["errors"]])

    def test_strict_mode_promotes_warnings(self):
        weak = (FIXTURES / "weak-prompt.txt").read_text(encoding="utf-8")
        self.assertTrue(checker.check(weak)["pass"])
        strict = checker.check(weak, strict=True)
        self.assertFalse(strict["pass"])
        self.assertEqual(strict["warnings"], [])
        self.assertTrue(all(item["code"].startswith("strict-") for item in strict["errors"]))

    def test_unverifiable_acceptance(self):
        prompt = "你是资深 Java 工程师。\n【上下文】\n【硬约束】\n【输出格式】\n"
        result = checker.check(prompt)
        codes = [item["code"] for item in result["errors"]]
        self.assertIn("unverifiable-acceptance", codes)

    def test_chinese_anti_patterns(self):
        base = (FIXTURES / "good-go-prompt.txt").read_text(encoding="utf-8")
        for phrase, code in ZH_ANTI_PATTERNS:
            with self.subTest(phrase=phrase):
                result = checker.check(base + "\n\n补充：" + phrase)
                self.assertIn(code, [item["code"] for item in result["errors"]])

    def test_empty_code_section_is_an_error(self):
        prompt = (
            "你是资深 Go 工程师。\n\n"
            "【前置判断】\n- 未提供代码：输出 NO_CODE_PROVIDED。\n\n"
            "【上下文】\n- 项目：demo\n\n"
            "【待重构代码】\n（代码随后补充）\n\n"
            "【硬约束】\n1. 外部行为 100% 一致。\n\n"
            "【重构目标】\n1. 拆分函数。\n\n"
            "【验收标准】\n- 测试命令：go test ./...\n- 用例：空输入 → 0\n\n"
            "【输出格式】\n1. 统一 diff（声明基线文件）。\n"
        )
        result = checker.check(prompt)
        self.assertIn("empty-code-section", [item["code"] for item in result["errors"]])

    def test_acceptance_must_live_in_the_acceptance_section(self):
        prompt = (
            "你是资深 Go 工程师。\n\n"
            "【前置判断】\n- 未提供代码：输出 NO_CODE_PROVIDED。\n\n"
            "【上下文】\n- 项目：demo，测试命令 go test ./...\n\n"
            "【待重构代码】\n" + "```go\npackage demo\n" + "```\n\n"
            "【硬约束】\n1. 外部行为 100% 一致。\n\n"
            "【重构目标】\n1. 拆分函数。\n\n"
            "【验收标准】\n- 见上文测试命令。\n\n"
            "【输出格式】\n1. 统一 diff（声明基线文件）。\n"
        )
        result = checker.check(prompt)
        self.assertTrue(result["pass"], result["errors"])
        self.assertIn(
            "acceptance-section-unverifiable",
            [item["code"] for item in result["warnings"]],
        )

    def test_english_anti_patterns(self):
        base = (FIXTURES / "good-en-prompt.txt").read_text(encoding="utf-8")
        for phrase, code in EN_ANTI_PATTERNS:
            with self.subTest(phrase=phrase):
                result = checker.check(base + "\n\nNote: " + phrase)
                self.assertIn(code, [item["code"] for item in result["errors"]])


class CliTest(unittest.TestCase):
    def test_json_output_for_english_prompt(self):
        result = run_checker("--json", str(FIXTURES / "good-en-prompt.txt"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["pass"])
        self.assertEqual(payload["languages"], ["python"])
        self.assertEqual(payload["skeleton"], [])
        self.assertEqual(payload["skeleton_segments"], [])

    def test_skeleton_output(self):
        result = run_checker("--skeleton", str(FIXTURES / "bad-prompt.txt"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("缺失段落骨架", result.stdout)

    def test_lang_override_via_cli(self):
        result = run_checker(str(FIXTURES / "good-prompt.txt"), "--lang", "python")
        self.assertEqual(result.returncode, 1)
        self.assertIn("不匹配", result.stdout)

    def test_usage_errors(self):
        self.assertEqual(run_checker().returncode, 2)
        self.assertEqual(run_checker(str(FIXTURES / "good-prompt.txt"), "--lang", "nope").returncode, 2)
        self.assertEqual(
            run_checker(str(FIXTURES / "good-prompt.txt"), "--fix", "--json").returncode, 2
        )
        self.assertEqual(
            run_checker(
                "--changed", "HEAD", str(FIXTURES / "good-prompt.txt")
            ).returncode,
            2,
        )

    def test_fix_repairs_a_broken_prompt(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "broken.txt"
            target.write_text((FIXTURES / "bad-prompt.txt").read_text(encoding="utf-8"), encoding="utf-8")
            self.assertEqual(run_checker(str(target)).returncode, 1)
            fixed = run_checker(str(target), "--fix")
            self.assertEqual(fixed.returncode, 0, fixed.stdout + fixed.stderr)
            content = target.read_text(encoding="utf-8")
            self.assertIn("check_prompt.py --fix", content)
            self.assertEqual(run_checker(str(target)).returncode, 0)

    def _git(self, repo, *args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    def _init_repo(self, raw):
        repo = Path(raw)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        self._git(repo, "config", "user.email", "test@example.com")
        self._git(repo, "config", "user.name", "test")
        return repo

    def test_changed_mode_only_checks_changed_files(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = self._init_repo(raw)
            (repo / "good.prompt.txt").write_text(
                (FIXTURES / "good-prompt.txt").read_text(encoding="utf-8"), encoding="utf-8"
            )
            self._git(repo, "add", "-A")
            self._git(repo, "commit", "-qm", "base")
            (repo / "bad.prompt.txt").write_text(
                (FIXTURES / "bad-prompt.txt").read_text(encoding="utf-8"), encoding="utf-8"
            )
            self._git(repo, "add", "-A")
            self._git(repo, "commit", "-qm", "add bad")
            result = run_checker("--changed", "HEAD~1", cwd=repo)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("bad.prompt.txt", result.stdout)
            self.assertNotIn("good.prompt.txt", result.stdout)

    def test_changed_mode_with_no_matching_changes_is_green(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = self._init_repo(raw)
            (repo / "notes.txt").write_text("hello\n", encoding="utf-8")
            self._git(repo, "add", "-A")
            self._git(repo, "commit", "-qm", "base")
            (repo / "notes.txt").write_text("hello again\n", encoding="utf-8")
            self._git(repo, "add", "-A")
            self._git(repo, "commit", "-qm", "change")
            result = run_checker("--changed", "HEAD~1", cwd=repo)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("no changed prompt files", result.stdout)

    def test_changed_mode_rejects_unknown_base(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = self._init_repo(raw)
            (repo / "notes.txt").write_text("x\n", encoding="utf-8")
            self._git(repo, "add", "-A")
            self._git(repo, "commit", "-qm", "base")
            result = run_checker("--changed", "does-not-exist", cwd=repo)
            self.assertEqual(result.returncode, 2)
            self.assertIn("cannot determine changed files", result.stderr)

    def test_fix_inserts_missing_segments_in_place(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "partial.prompt.txt"
            target.write_text(
                "你是资深 Go 工程师。\n\n"
                "【待重构代码】\n"
                "```go\npackage demo\n```\n\n"
                "【验收标准】\n- 测试命令：go test ./...\n- 用例：空输入 → 0\n\n"
                "【输出格式】\n1. 统一 diff（声明基线文件）。\n",
                encoding="utf-8",
            )
            result = run_checker(str(target), "--fix")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            fixed = target.read_text(encoding="utf-8")
            self.assertLess(fixed.index("【上下文】"), fixed.index("【待重构代码】"))
            self.assertLess(fixed.index("【硬约束"), fixed.index("【重构目标】"))
            self.assertLess(fixed.index("【重构目标】"), fixed.index("【验收标准】"))
            self.assertIn("check_prompt.py --fix", fixed)

    def test_fix_preserves_bom_and_crlf(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "bom.prompt.txt"
            text = (
                "\ufeff你是资深 Go 工程师。\r\n\r\n"
                "【待重构代码】\r\n\x60\x60\x60go\r\npackage demo\r\n\x60\x60\x60\r\n\r\n"
                "【验收标准】\r\n- 测试命令：go test ./...\r\n- 用例：空输入 → 0\r\n\r\n"
                "【输出格式】\r\n1. 统一 diff（声明基线文件）。\r\n"
            )
            target.write_bytes(text.encode("utf-8"))
            result = run_checker(str(target), "--fix")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            raw_bytes = target.read_bytes()
            self.assertTrue(raw_bytes.startswith(b"\xef\xbb\xbf"))
            self.assertIn(b"\r\n", raw_bytes)
            self.assertEqual(run_checker(str(target)).returncode, 0)

    def test_fix_does_not_treat_prose_as_segments(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "prose.prompt.txt"
            target.write_text(
                "背景：目标是把代码改好。\n\n"
                "【待重构代码】\n\x60\x60\x60go\npackage demo\n\x60\x60\x60\n\n"
                "【验收标准】\n- 测试命令：go test ./...\n- 用例：空输入 → 0\n\n"
                "【输出格式】\n1. 统一 diff（声明基线文件）。\n",
                encoding="utf-8",
            )
            result = run_checker(str(target), "--fix")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            fixed = target.read_text(encoding="utf-8")
            self.assertIn("【上下文】", fixed)
            self.assertIn("【重构目标】", fixed)

    def test_fix_inserts_missing_segments_in_place_english(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "partial-en.prompt.txt"
            target.write_text(
                "You are a senior Go engineer.\n\n"
                "[CODE TO REFACTOR]\n"
                "```go\npackage demo\n```\n\n"
                "[ACCEPTANCE CRITERIA]\n- Test command: go test ./...\n- Cases: empty -> 0\n\n"
                "[OUTPUT FORMAT]\n1. Unified diff (state the baseline file).\n",
                encoding="utf-8",
            )
            result = run_checker(str(target), "--fix")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            fixed = target.read_text(encoding="utf-8")
            self.assertLess(fixed.index("[CONTEXT]"), fixed.index("[CODE TO REFACTOR]"))
            self.assertLess(fixed.index("[HARD CONSTRAINTS"), fixed.index("[REFACTORING GOALS]"))
            self.assertLess(fixed.index("[REFACTORING GOALS]"), fixed.index("[ACCEPTANCE CRITERIA]"))

    def test_stdin_input(self):
        text = (FIXTURES / "good-prompt.txt").read_text(encoding="utf-8")
        result = run_checker("-", input_text=text)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_github_format_annotations(self):
        result = run_checker("--format", "github", str(FIXTURES / "bad-prompt.txt"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("::error file=", result.stdout)
        self.assertIn("::warning file=", result.stdout)
        self.assertIn("缺少段落", result.stdout)

    def test_github_format_includes_line_numbers_when_known(self):
        result = run_checker("--format", "github", str(FIXTURES / "bad-antipattern-prompt.txt"))
        self.assertEqual(result.returncode, 1)
        self.assertIsNotNone(re.search(r"::error file=.+,line=\d+::", result.stdout))

    def test_github_format_missing_segments_have_lines(self):
        result = run_checker("--format", "github", str(FIXTURES / "bad-prompt.txt"))
        self.assertEqual(result.returncode, 1)
        self.assertIsNotNone(
            re.search(r"::error file=.+,line=\d+::缺少段落", result.stdout)
        )

    def test_github_format_batch_includes_line_numbers(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "bad.prompt.txt"
            target.write_text(
                (FIXTURES / "bad-antipattern-prompt.txt").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            result = run_checker(str(Path(raw)), "--format", "github")
            self.assertEqual(result.returncode, 1)
            self.assertIsNotNone(re.search(r"::error file=.+,line=\d+::", result.stdout))

    def test_github_format_rejects_json_fix_and_skeleton(self):
        fixture = str(FIXTURES / "good-prompt.txt")
        self.assertEqual(run_checker("--format", "github", "--json", fixture).returncode, 2)
        self.assertEqual(run_checker("--format", "github", "--fix", fixture).returncode, 2)
        self.assertEqual(run_checker("--format", "github", "--skeleton", fixture).returncode, 2)

    def test_non_utf8_prompt_is_usage_error(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "ansi.prompt.txt"
            target.write_bytes("中文提示词".encode("gbk"))
            result = run_checker(str(target))
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("UTF-8", result.stderr)


if __name__ == "__main__":
    unittest.main()
