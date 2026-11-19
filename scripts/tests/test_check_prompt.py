"""Regression tests for scripts/check_prompt.py.

Run with:  python3 -m unittest discover -s scripts/tests -p "test_*.py" -v
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
    def test_segment_locations_preserve_first_match_and_line_offsets(self):
        texts = ["", "no headings",
                 "prefix\n【上下文】\nbody\n【验收标准】\npytest",
                 "prefix\r\n## CONTEXT\r\nbody\r\n[ACCEPTANCE CRITERIA]\r\npytest",
                 "preamble\nYou are a senior engineer\n## Context\n## Context\n",
                 "【输出格式】\npatch\n【上下文】\n【重构目标】\n",
                 "before inline 【上下文】 text\nNO_CODE_PROVIDED"]
        for text in texts:
            with self.subTest(text=text):
                matches = [re.search(pattern, text, re.S | re.M | re.I)
                           for _, _, pattern in checker.SEGMENTS]
                positions = {key: text.rfind("\n", 0, match.start()) + 1
                             for (key, _, _), match in zip(checker.SEGMENTS, matches) if match}
                self.assertEqual(checker.segment_positions(text), positions)
                self.assertEqual(checker.check(text)["missing_segments"],
                                 [label for (_, label, _), match in zip(checker.SEGMENTS, matches) if not match])
                lines = [text[:match.start()].count("\n") + 1 if match else None for match in matches]
                for index, (_, label, _) in enumerate(checker.SEGMENTS):
                    later = next((line for line in lines[index + 1:] if line), None)
                    earlier = next((line for line in reversed(lines[:index]) if line), 1)
                    expected = max(1, later - 1) if later else earlier
                    self.assertEqual(checker.missing_segment_line(text, label), expected)
                self.assertEqual(checker.missing_segment_line(text, "unknown"), 1)

    def test_verifiability_rules_match_global_and_section_checks(self):
        cases = [
            ("", False), ("see above", False), ("input -> output", False),
            ("input → output", False), ("a -> b → c", True),
            ("a -> b -> c", True), ("a → b → c", True),
            ("PYTEST", True), ("expected", True), ("expectations", True),
            ("unexpected", False), ("期望", True),
        ]
        for body, expected in cases:
            with self.subTest(body=body):
                text = "[ACCEPTANCE CRITERIA]\n" + body
                result = checker.check(text)
                self.assertEqual(result["verifiable"], expected)
                errors, warnings = [], []
                checker.check_section_content(text, errors, warnings)
                self.assertEqual(errors, [])
                self.assertEqual(
                    [item["code"] for item in warnings],
                    [] if expected else ["acceptance-section-unverifiable"],
                )

    def test_fenced_source_headings_do_not_split_sections(self):
        for fence in ("```", "````", "~~~~"):
            code = "# Context\n【验收标准】\n[OUTPUT FORMAT]\n```go\n# cleaner\n"
            prompt = PROMPT.format(language="python", fence="python", code="pass", command="pytest")
            prompt = prompt.replace("```python\npass\n```", fence + "python\n" + code + fence)
            with self.subTest(fence=fence):
                body = checker.segment_body(prompt, checker.CODE_HEADING)
                self.assertIn(code, body)
                self.assertTrue(checker.check(prompt, strict=True)["pass"], checker.check(prompt))
                self.assertEqual(checker.check(prompt)["languages"], ["python"])

    def test_source_cannot_supply_missing_segments(self):
        prompt = PROMPT.format(language="python", fence="python", code="【上下文】\nNO_CODE_PROVIDED", command="pytest")
        prompt = prompt.replace("【上下文】\n- 项目/模块：示例\n- 语言与框架：python", "")
        prompt = prompt.replace("【前置判断】\n- 未提供代码：输出 NO_CODE_PROVIDED 并索取代码。", "")
        result = checker.check(prompt)
        self.assertIn("上下文", result["missing_segments"])
        self.assertIn("守卫", result["missing_segments"])
        self.assertNotIn("context", checker.segment_positions(prompt))

    def test_source_and_context_cannot_validate_wrong_command(self):
        for language, matching, wrong in (("python", "pytest", "go test ./..."), ("go", "go test", "pytest")):
            prompt = PROMPT.format(language=language, fence=language, code=matching, command=wrong)
            prompt = prompt.replace("- 项目/模块：示例", "- 项目/模块：示例 " + matching)
            with self.subTest(language=language):
                result = checker.check(prompt)
                self.assertIn("language-mismatch", [item["code"] for item in result["errors"]])

    def test_fenced_output_is_not_interpreted_as_an_instruction(self):
        prompt = PROMPT.format(language="python", fence="python", code="pass", command="pytest")
        prompt += "\n```text\nrewrite the whole project\n```\n"
        self.assertTrue(checker.check(prompt, strict=True)["pass"], checker.check(prompt))

    def test_fenced_acceptance_commands_remain_valid(self):
        prompt = PROMPT.format(language="python", fence="python", code="pass", command="\n```sh\npytest\n```")
        self.assertTrue(checker.check(prompt, strict=True)["pass"], checker.check(prompt))

    def test_acceptance_fence_cannot_replace_source(self):
        prompt = PROMPT.format(language="python", fence="python", code="pass", command="\n```sh\npytest\n```")
        prompt = prompt.replace("【待重构代码】\n```python\npass\n```", "")
        self.assertIn("待重构代码", checker.check(prompt, strict=True)["missing_segments"])

    def test_whitespace_only_source_fence_is_empty(self):
        prompt = PROMPT.format(language="python", fence="python", code="  ", command="pytest")
        self.assertIn("empty-code-section", [item["code"] for item in checker.check(prompt)["errors"]])

    def test_nested_markdown_acceptance_heading_keeps_commands(self):
        prompt = (FIXTURES / "good-en-prompt.txt").read_text(encoding="utf-8")
        prompt = prompt.replace("[ACCEPTANCE CRITERIA]", "## Acceptance Criteria\n\n### Automated checks")
        self.assertIn("### Automated checks", prompt)
        self.assertTrue(checker.check(prompt, strict=True)["pass"], checker.check(prompt))

    def test_unclosed_source_masks_fake_headings_and_commands(self):
        prompt = "【待重构代码】\n````python\n```\n【验收标准】\npytest\n"
        result = checker.check(prompt)
        self.assertIn("验收标准", result["missing_segments"])
        self.assertIn("empty-code-section", [item["code"] for item in result["errors"]])
        self.assertFalse(result["verifiable"])

    def test_source_antipatterns_are_data_but_real_instructions_fail(self):
        for phrase, code in ZH_ANTI_PATTERNS + EN_ANTI_PATTERNS:
            prompt = PROMPT.format(language="python", fence="python", code=phrase, command="pytest")
            with self.subTest(phrase=phrase):
                self.assertTrue(checker.check(prompt, strict=True)["pass"], checker.check(prompt))
                self.assertIn(code, [item["code"] for item in checker.check(prompt + "\n" + phrase)["errors"]])

    def test_finding_lines_ignore_same_text_in_source(self):
        prompt = PROMPT.format(language="python", fence="python", code="pytest\n# cleaner", command="go test ./...") + "\nMake it cleaner.\n"
        self.assertEqual(checker.finding_line(prompt, "language-mismatch"), prompt[:prompt.index("go test")].count("\n") + 1)
        self.assertEqual(checker.finding_line(prompt, "unmeasurable-goal"), prompt[:prompt.index("Make it cleaner")].count("\n") + 1)

    def test_crlf_acceptance_fences_and_heading_offsets(self):
        prompt = PROMPT.format(language="python", fence="python", code="# Context\npass", command="\n~~~sh\n# Context\npytest\n~~~").replace("\n", "\r\n")
        result = checker.check(prompt, strict=True)
        self.assertTrue(result["pass"], result)
        self.assertEqual(checker.segment_positions(prompt)["acceptance"], prompt.index("【验收标准】"))
        self.assertIn("pytest", checker.segment_body(prompt, checker.ACCEPTANCE_HEADING))

    def test_bare_source_fence_retains_acceptance_commands(self):
        base = "```python\npass\n```\n【验收标准】\n```sh\npytest\n```\n"
        for prompt in (base, base + "【待重构代码】\n{粘贴代码}\n"):
            with self.subTest(prompt=prompt):
                result = checker.check(prompt)
                self.assertTrue(result["verifiable"], result)
                self.assertNotIn("unverifiable-acceptance", [item["code"] for item in result["errors"]])
                self.assertEqual(checker.segment_positions(prompt)["code"], 0)

    def test_full_check_scans_the_whole_prompt_once(self):
        text = (FIXTURES / "good-en-prompt.txt").read_text(encoding="utf-8")
        with patch.object(checker, "fenced_blocks", wraps=checker.fenced_blocks) as scans:
            self.assertTrue(checker.check(text, strict=True)["pass"])
        self.assertEqual(sum(call.args == (text,) for call in scans.call_args_list), 1)
        self.assertEqual(scans.call_count, 2)

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

    def test_test_tool_names_match_whole_tokens(self):
        for command, expected in (("notpytest", "no-test-command"), ("pytest-wrapper", "no-test-command"),
                                  ("rake test", "language-mismatch"), ("python -m pytest -q", None)):
            with self.subTest(command=command):
                prompt = PROMPT.format(language="python", fence="python", code="pass", command=command)
                result = checker.check(prompt)
                diagnostics = [item["code"] for item in result["errors"] + result["warnings"]]
                if expected:
                    self.assertIn(expected, diagnostics)
                else:
                    self.assertEqual(diagnostics, [])

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
    def test_github_annotation_escaping_and_optional_location(self):
        self.assertEqual(
            checker.github_annotation("warning", "dir\\a%file", "x%\r\ny", 3),
            "::warning file=dir/a%25file,line=3::x%25%0D%0Ay",
        )
        self.assertEqual(checker.github_annotation("error", "draft,a:b.prompt.md", "x,y:z", 3),
                         "::error file=draft%2Ca%3Ab.prompt.md,line=3::x,y:z")
        self.assertEqual(checker.github_annotation("error", None, "x", 3), "::error::x")
        self.assertEqual(checker.github_annotation("notice", "a", "x", 0), "::notice file=a::x")

    def test_multiple_annotations_scan_full_prompt_once(self):
        text = (FIXTURES / "bad-prompt.txt").read_text(encoding="utf-8")
        result = checker.check(text, strict=True)
        with patch.object(checker, "fenced_blocks", wraps=checker.fenced_blocks) as scans:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                checker._print_github_findings(result, text, "bad.prompt.txt")
        self.assertGreater(len(output.getvalue().splitlines()), 1)
        self.assertEqual(sum(call.args == (text,) for call in scans.call_args_list), 1)

    def test_github_empty_prompt_exact_output_in_all_modes(self):
        messages = ["缺少段落：" + label for label in
                    ["角色", "上下文", "待重构代码", "硬约束", "重构目标", "验收标准", "输出格式", "守卫"]]
        messages.append("验收标准不可验证：未发现测试命令，也没有「输入 → 期望输出」用例")
        warnings = ["硬约束未显式约束行为 / API / 签名 / 异常兼容性",
                    "输出格式未约定 unified diff / 完整文件 / patch"]
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "empty.prompt.txt"
            target.write_text("", encoding="utf-8")
            for mode in ("stdin", "file", "batch"):
                with self.subTest(mode=mode):
                    source = "-" if mode == "stdin" else str(Path(raw) if mode == "batch" else target)
                    result = run_checker(source, "--format", "github", input_text="")
                    path = str(target).replace("\\", "/").replace(":", "%3A").replace(",", "%2C")
                    location = "" if mode == "stdin" else " file=" + path
                    lines = []
                    for index, message in enumerate(messages):
                        line = ",line=1" if location and index < 8 else ""
                        lines.append(f"::error{location}{line}::{message}")
                    lines.extend(f"::warning{location}::{message}" for message in warnings)
                    if mode == "batch":
                        lines.append("\n0 passed, 1 failed (1 file(s) checked)")
                    else:
                        label = "(stdin)" if mode == "stdin" else str(target)
                        lines.append(f"9 error(s), 2 warning(s) in {label}")
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stderr, "")
                    self.assertEqual(result.stdout, "\n".join(lines) + "\n")

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

    def test_fix_refuses_unclosed_fence_without_writing(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "unclosed.prompt.txt"
            original = b"[CODE TO REFACTOR]\n````python\n# Context\n```\n"
            target.write_bytes(original)
            result = run_checker(str(target), "--fix")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("Close the code fence", result.stdout)
            self.assertEqual(target.read_bytes(), original)

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

    def test_changed_mode_preserves_unicode_and_whitespace_names(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = self._init_repo(raw)
            (repo / "seed").write_text("base", encoding="utf-8")
            self._git(repo, "add", "-A")
            self._git(repo, "commit", "-qm", "base")
            names = ["中文.prompt.md", " leading.prompt.txt"]
            if os.name != "nt":
                names.extend(["line\nbreak.prompt.md", "carriage\rreturn.prompt.md", "pair\r\nname.prompt.md"])
            for name in names:
                (repo / name).write_text("broken", encoding="utf-8")
            self._git(repo, "add", "-A")
            self._git(repo, "commit", "-qm", "bad prompts")
            result = run_checker("--changed", "HEAD~1", "--json", cwd=repo)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual({Path(item["file"]).name for item in payload["results"]}, set(names))
            self.assertEqual(payload["failed"], len(names))

    def test_changed_mode_subdirectory_checks_root_file_not_decoy(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = self._init_repo(raw)
            (repo / "seed").write_text("base", encoding="utf-8")
            self._git(repo, "add", "-A")
            self._git(repo, "commit", "-qm", "base")
            (repo / "bad.prompt.md").write_text("broken", encoding="utf-8")
            self._git(repo, "add", "-A")
            self._git(repo, "commit", "-qm", "bad prompt")
            child = repo / "child"
            child.mkdir()
            decoy = child / "bad.prompt.md"
            good = (FIXTURES / "good-prompt.txt").read_text(encoding="utf-8")
            decoy.write_text(good, encoding="utf-8")
            self._git(repo, "config", "diff.relative", "true")
            result = run_checker("--changed", "HEAD~1", "--json", cwd=child)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            item = json.loads(result.stdout)["results"][0]
            self.assertEqual(Path(item["file"]).resolve(), (repo / "bad.prompt.md").resolve())
            self.assertFalse(item["pass"])
            self.assertEqual(decoy.read_text(encoding="utf-8"), good)

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
            result = run_checker("--changed", "HEAD~1", "--json", cwd=repo)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout), {"pass": True, "passed": 0, "failed": 0, "results": []})

    def test_changed_rejects_invalid_include_before_reporting_no_changes(self):
        for include in (" , ", "/absolute/*.prompt.md"):
            with self.subTest(include=include):
                result = run_checker("--changed", "HEAD", "--include", include, "--json")
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("--include", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_changed_root_checks_only_committed_prompt_paths(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = self._init_repo(raw)
            prompt = repo / "root prompt.prompt.md"
            prompt.write_text("broken", encoding="utf-8")
            self._git(repo, "add", "-A")
            self._git(repo, "commit", "-qm", "root")
            (repo / "untracked.prompt.md").write_text("broken", encoding="utf-8")
            result = run_checker("--changed-root", "--json", cwd=repo)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual([Path(item["file"]).name for item in json.loads(result.stdout)["results"]], [prompt.name])

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

    def test_fix_preserves_hard_breaks_and_mixed_line_endings(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "mixed.prompt.txt"
            original_lines = [b"You are a senior Python engineer.  \r\n", b"[CODE TO REFACTOR]\n",
                              b"{paste code}  \r\n", b"[ACCEPTANCE CRITERIA]\n", b"pytest  \n"]
            target.write_bytes(b"".join(original_lines))
            result = run_checker(str(target), "--fix")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            first = target.read_bytes()
            cursor = 0
            for line in original_lines:
                cursor = first.index(line, cursor) + len(line)
            second = run_checker(str(target), "--fix")
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual(target.read_bytes(), first)

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
