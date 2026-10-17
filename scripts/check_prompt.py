#!/usr/bin/env python3
"""Structural self-check for a code-refactoring prompt produced with this skill.

This is a heuristic *structure* check, not a judgement of semantic quality.

Usage:
    python3 scripts/check_prompt.py <file|-> [--json] [--lang auto|go|rust|python|...]

Checks:
  - the eight required segments are present;
  - acceptance criteria is verifiable (test command or "input -> expected" cases);
  - the test command matches the language of the prompt (auto-detected from the
    fenced code block, or forced with --lang);
  - "keep behaviour unchanged" is backed by verifiable checks;
  - hard constraints mention behaviour / API / signature compatibility;
  - known anti-patterns are flagged with a concrete fix.

Exit codes: 0 = pass, 1 = problems found, 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SEGMENTS = [
    ("role", "角色", r"角色|你是|作为.{0,12}(工程师|专家|开发)"),
    ("context", "上下文", r"上下文|背景"),
    ("code", "待重构代码", r"待重构代码|粘贴代码|代码如下|\x60\x60\x60"),
    ("constraints", "硬约束", r"硬约束|约束"),
    ("goals", "重构目标", r"重构目标|重构要求|目标"),
    ("acceptance", "验收标准", r"验收标准|验收"),
    ("output", "输出格式", r"输出格式"),
    ("guard", "守卫", r"前置判断|NO_CODE_PROVIDED|NO_REFACTORING_NEEDED|守卫"),
]

TEST_COMMAND = re.compile(
    r"(pytest|unittest|npm\s+(run\s+)?test|yarn\s+test|pnpm\s+test|mvn\s+(test|verify)|"
    r"gradle(w)?\s+test|go\s+test|cargo\s+test|dotnet\s+test|rspec|phpunit|ctest|"
    r"swift\s+test|jest|vitest|junit|tox|nox|node\s+--test)",
    re.I,
)
VAGUE = re.compile(r"(保持|维持).{0,6}行为.{0,6}不变|行为(完全)?不变")
BEHAVIOUR_CONSTRAINT = re.compile(
    r"(行为|API|签名|异常|返回值|接口).{0,20}(一致|不变|兼容|保持)|"
    r"(一致|不变|兼容|保持).{0,20}(行为|API|签名|异常|返回值|接口)"
)

# Fence language -> canonical language.
LANGUAGE_FENCES = {
    "go": "go",
    "golang": "go",
    "rust": "rust",
    "python": "python",
    "py": "python",
    "java": "java",
    "ts": "typescript",
    "typescript": "typescript",
    "js": "javascript",
    "javascript": "javascript",
    "cs": "csharp",
    "csharp": "csharp",
    "c#": "csharp",
    "kotlin": "kotlin",
    "kt": "kotlin",
    "swift": "swift",
    "ruby": "ruby",
    "rb": "ruby",
    "php": "php",
    "sql": "sql",
    "cpp": "cpp",
    "c++": "cpp",
}

LANGUAGE_LABELS = {
    "go": "Go",
    "rust": "Rust",
    "python": "Python",
    "java": "Java",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "csharp": "C#",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "ruby": "Ruby",
    "php": "PHP",
    "sql": "SQL",
    "cpp": "C++",
}

# What a runnable acceptance command looks like for each language.
LANGUAGE_TEST_COMMANDS = {
    "go": r"go\s+test",
    "rust": r"cargo\s+test",
    "python": r"pytest|unittest|python3?\s+-m\s+(pytest|unittest)|tox|nox",
    "java": r"mvn\s+(test|verify)|\.?/?gradlew?\s+test|gradle\s+test|junit",
    "typescript": r"(npm|yarn|pnpm)\s+(run\s+)?test|jest|vitest|node\s+--test|tsc",
    "javascript": r"(npm|yarn|pnpm)\s+(run\s+)?test|jest|vitest|node\s+--test",
    "csharp": r"dotnet\s+test|nunit|xunit",
    "kotlin": r"\.?/?gradlew?\s+test|gradle\s+test|kotlin\s+test",
    "swift": r"swift\s+test",
    "ruby": r"rspec|rake\s+test",
    "php": r"phpunit|composer\s+test",
    "cpp": r"ctest|gtest|cmake\s+--build",
    "sql": r"(EXPLAIN|执行|运行).{0,10}(查询|SQL)|期望(结果|行)|结果集",
}

# (code, regex, severity, message)
ANTI_PATTERNS = [
    (
        "test-tampering",
        re.compile(r"顺便.{0,8}(把)?测试.{0,8}(改|删)"),
        "error",
        "「顺便改测试」会掩盖行为变更：测试只允许新增基线用例，不允许改既有断言。",
    ),
    (
        "boil-the-ocean",
        re.compile(r"(整个|全部|全量|所有).{0,6}(项目|代码库|仓库).{0,6}(重构|重写)"),
        "error",
        "整体重写无法评审与定位失败：按 references/workflows.md 工作流 3 分批，每批独立验收。",
    ),
    (
        "appeal-to-best-practice",
        re.compile(r"(用你|按你|用).{0,8}(熟悉|喜欢)?.{0,4}最佳实践.{0,6}(重写|重构|改写)"),
        "error",
        "「最佳实践」是无依据架构改动的入口：限定只改结构不改行为，并禁止新增依赖。",
    ),
    (
        "unmeasurable-goal",
        re.compile(r"(性能|质量|可读性|可维护性)(更好|提升|更高|增强)"),
        "error",
        "空泛的改进目标不可验收：改为可测量指标（基准命令、阈值、圈复杂度上限）或删除。",
    ),
    (
        "scope-creep",
        re.compile(r"(顺手|顺便).{0,10}(重构|优化|清理)"),
        "warning",
        "顺手改动会扩大评审面：把范围外改动单列，不放进本次重构。",
    ),
    (
        "behaviour-change-allowed",
        re.compile(r"(允许|可以|同意).{0,8}(行为|接口|API).{0,8}(变化|改变|调整)"),
        "warning",
        "允许行为变化就不是重构：走需求 / 设计变更流程，本技能「行为等价」前提不成立。",
    ),
    (
        "hedged-constraint",
        re.compile(r"(大概|尽量|尽可能|差不多|基本上).{0,10}(保持|不变|一致)"),
        "warning",
        "模棱两可的约束不可验收：写成明确的测试命令或用例。",
    ),
]

KNOWN_LANGUAGES = sorted(LANGUAGE_TEST_COMMANDS)


def error(code: str, message: str) -> dict:
    return {"code": code, "message": message}


def detect_languages(text: str) -> list[str]:
    languages: list[str] = []
    for fence in re.findall(r"\x60\x60\x60([A-Za-z0-9#+_.-]+)", text):
        language = LANGUAGE_FENCES.get(fence.lower())
        if language and language not in languages:
            languages.append(language)
    return languages


def check_language(text: str, languages: list[str], errors: list[dict], warnings: list[dict]) -> None:
    if not languages:
        return
    labels = " / ".join(LANGUAGE_LABELS[lang] for lang in languages)
    matched = [lang for lang in languages if re.search(LANGUAGE_TEST_COMMANDS[lang], text, re.I)]
    if matched:
        return

    generic = TEST_COMMAND.search(text)
    if generic:
        expected = "、".join(
            {
                "go": "go test",
                "rust": "cargo test",
                "python": "pytest / python -m unittest",
                "java": "mvn test / gradle test",
                "typescript": "npm test / node --test",
                "javascript": "npm test / node --test",
                "csharp": "dotnet test",
                "kotlin": "gradle test",
                "swift": "swift test",
                "ruby": "rspec",
                "php": "phpunit",
                "cpp": "ctest",
                "sql": "EXPLAIN / 期望结果集",
            }.get(lang, "对应测试命令")
            for lang in languages
        )
        errors.append(
            error(
                "language-mismatch",
                f"验收命令与语言不匹配：语言为 {labels}，验收里只有「{generic.group(0)}」；"
                f"应改用 {expected} 之一。",
            )
        )
    else:
        warnings.append(
            error(
                "no-test-command",
                f"未声明可运行测试命令（语言：{labels}）：建议写明对应测试命令，替代仅靠「输入 → 期望」的手工核对。",
            )
        )


def check(text: str, explicit_language: str = "auto") -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []

    missing = [label for _key, label, pattern in SEGMENTS if not re.search(pattern, text, re.S)]
    for label in missing:
        errors.append(error("missing-segment", f"缺少段落：{label}"))

    arrows = text.count("→") + text.count("->")
    verifiable = bool(TEST_COMMAND.search(text) or "期望" in text or arrows >= 2)
    if not verifiable:
        errors.append(
            error("unverifiable-acceptance", "验收标准不可验证：未发现测试命令，也没有「输入 → 期望输出」用例")
        )

    if VAGUE.search(text) and not verifiable:
        errors.append(
            error("vague-equivalence", "出现「保持行为不变」但没有可验证的测试命令或用例，无法验收")
        )

    if not BEHAVIOUR_CONSTRAINT.search(text):
        warnings.append(
            error("no-behaviour-constraint", "硬约束未显式约束行为 / API / 签名 / 异常兼容性")
        )

    if not re.search(r"diff|完整文件|patch", text, re.I):
        warnings.append(
            error("no-output-format", "输出格式未约定 unified diff / 完整文件 / patch")
        )

    if explicit_language == "auto":
        languages = detect_languages(text)
        language_source = "auto"
    else:
        languages = [explicit_language]
        language_source = "explicit"
    check_language(text, languages, errors, warnings)

    for code, pattern, severity, message in ANTI_PATTERNS:
        if pattern.search(text):
            target = errors if severity == "error" else warnings
            target.append(error(code, message))

    return {
        "pass": not errors,
        "errors": errors,
        "warnings": warnings,
        "missing_segments": missing,
        "verifiable": verifiable,
        "languages": languages,
        "language_source": language_source,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Structural self-check for refactoring prompts.")
    parser.add_argument("source", nargs="?", help="prompt file, or - for stdin")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--lang",
        default="auto",
        metavar="LANG",
        help="force the prompt language (default: auto-detect from fenced code); "
        "one of: auto, " + ", ".join(KNOWN_LANGUAGES),
    )
    args = parser.parse_args()

    if not args.source:
        parser.print_usage(sys.stderr)
        return 2
    language = args.lang.lower()
    if language != "auto" and language not in LANGUAGE_TEST_COMMANDS:
        print(
            f"unknown --lang {args.lang!r}; expected auto or one of: {', '.join(KNOWN_LANGUAGES)}",
            file=sys.stderr,
        )
        return 2

    if args.source == "-":
        text = sys.stdin.read()
    else:
        path = Path(args.source)
        if not path.is_file():
            print(f"file not found: {args.source}", file=sys.stderr)
            return 2
        text = path.read_text(encoding="utf-8")

    result = check(text, explicit_language=language)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["pass"]:
        language_note = ""
        if result["languages"]:
            language_note = " [" + " / ".join(LANGUAGE_LABELS[lang] for lang in result["languages"]) + "]"
        print(f"PASS: 8 segments present, acceptance criteria verifiable{language_note}")
        for warning in result["warnings"]:
            print(f"  warn: {warning['message']}")
    else:
        print(f"FAIL: {len(result['errors'])} problem(s) found")
        for item in result["errors"]:
            print(f"  - {item['message']}")
        for warning in result["warnings"]:
            print(f"  warn: {warning['message']}")

    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
