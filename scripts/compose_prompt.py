#!/usr/bin/env python3
"""Compose a filled-in, self-verified refactoring prompt from a source file.

The composed prompt follows the eight-segment skeleton of this skill (or the
English template with --output-lang en) and is immediately re-checked with
scripts/check_prompt.py. If the generated prompt would not pass the checker,
the script exits non-zero instead of emitting a non-compliant prompt.

Usage:
    python3 scripts/compose_prompt.py --code path/to/file.go [options]
    python3 scripts/compose_prompt.py --code - < snippet.py

Options:
    --code PATH            source file to embed ('-' reads stdin) - required
    --code-lang LANG       override the language detected from the file extension
    --project NAME         project/module name (default: file stem)
    --pain TEXT            known pain points (default: a generic placeholder)
    --goal TEXT            refactoring goal (repeatable; sensible defaults given)
    --constraint TEXT      extra hard constraint (repeatable)
    --test-command CMD     acceptance test command (default: per language)
    --output-lang zh|en    language of the generated prompt (default: zh)
    --out FILE             write to FILE instead of stdout
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKER = HERE / "check_prompt.py"


class ComposeError(Exception):
    """Input error that should exit with code 2."""

EXTENSION_LANGUAGES = {
    ".go": "go",
    ".py": "python",
    ".java": "java",
    ".rs": "rust",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".cs": "csharp",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".rb": "ruby",
    ".php": "php",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".sql": "sql",
}

LANGUAGE_LABELS = {
    "go": "Go",
    "python": "Python",
    "java": "Java",
    "rust": "Rust",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "csharp": "C#",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "ruby": "Ruby",
    "php": "PHP",
    "cpp": "C++",
    "sql": "SQL",
}

DEFAULT_TEST_COMMANDS = {
    "go": "go test ./...",
    "python": "pytest",
    "java": "mvn test",
    "rust": "cargo test",
    "typescript": "npm test",
    "javascript": "npm test",
    "csharp": "dotnet test",
    "kotlin": "gradle test",
    "swift": "swift test",
    "ruby": "rspec",
    "php": "phpunit",
    "cpp": "ctest",
    "sql": "期望结果集对比（golden 数据）",
}

DEFAULT_GOALS = {
    "sql": [
        "消除重复子查询，改用 CTE 命名中间结果",
        "显式保留 NULL 语义、分组键与排序兜底",
        "如需索引或执行计划优化，作为独立性能变更评估",
    ],
    "default": [
        "拆分长函数 / 提取子方法，降低圈复杂度",
        "消除重复代码，用具名常量或枚举替换魔法数字/字符串",
        "保持计算顺序、错误语义与日志行为不变",
    ],
}

DEFAULT_GOALS_EN = {
    "sql": [
        "remove duplicated subqueries by naming intermediate results with CTEs",
        "preserve NULL semantics, grouping keys, and deterministic ordering",
        "evaluate indexes / query plans separately as a performance change",
    ],
    "default": [
        "split long functions / extract helpers to reduce cyclomatic complexity",
        "remove duplication and replace magic numbers or strings with named constants or enums",
        "keep computation order, error semantics, and logging behaviour unchanged",
    ],
}

DEFAULT_TEST_COMMANDS_EN = {
    **DEFAULT_TEST_COMMANDS,
    "sql": "golden result-set comparison on a fixed dataset",
}


def load_checker():
    spec = importlib.util.spec_from_file_location("check_prompt", CHECKER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def detect_language(path: str | None, override: str | None) -> str:
    if override:
        if override not in LANGUAGE_LABELS:
            raise ComposeError(f"unknown --code-lang {override!r}; expected one of: {', '.join(sorted(LANGUAGE_LABELS))}")
        return override
    suffix = Path(path).suffix.lower() if path else ""
    language = EXTENSION_LANGUAGES.get(suffix)
    if not language:
        raise ComposeError(
            f"cannot detect language from {path!r}; pass --code-lang "
            f"({', '.join(sorted(LANGUAGE_LABELS))})"
        )
    return language


def fence_for(code: str) -> str:
    longest = max((len(match.group(0)) for match in re.finditer(r"\x60+", code)), default=0)
    return chr(96) * max(3, longest + 1)


def fence_language(language: str) -> str:
    return {
        "python": "python",
        "typescript": "ts",
        "javascript": "js",
        "csharp": "csharp",
        "cpp": "cpp",
        "sql": "sql",
    }.get(language, language)


def build_zh(context: dict) -> str:
    fence = context["fence"]
    goals = context["goals"]
    lines = [
        f"你是资深 {context['label']} 工程师，专注在不改变行为的前提下做重构。",
        "",
        "【前置判断】",
        "- 未提供代码：直接输出 NO_CODE_PROVIDED 并索取代码；",
        "- 代码无明显可改进处：输出 NO_REFACTORING_NEEDED，说明理由，不要硬改。",
        "",
        "【上下文】",
        f"- 项目/模块：{context['project']}",
        f"- 语言与框架：{context['label']}（{context['language']}）",
        f"- 这段代码做什么、已知痛点：{context['pain']}",
        "",
        "【待重构代码】",
        f"{fence}{context['fence_language']}",
        context["code"].rstrip(),
        fence,
        "",
        "【硬约束（不可违反）】",
        "1. 外部行为 100% 一致：不改公开 API、返回值、抛出的异常类型；",
        "2. 不新增第三方依赖；不弱化错误处理、日志、安全校验；",
        "3. 遵循项目现有编码规范与命名风格。",
    ]
    for index, constraint in enumerate(context["constraints"], 4):
        lines.append(f"{index}. {constraint}")
    lines.extend(["", "【重构目标】", "0. 先为现有行为生成/补齐「行为基线测试」（characterisation test）作为安全网；"])
    for index, goal in enumerate(goals, 1):
        lines.append(f"{index}. {goal}")
    lines.extend(
        [
            "",
            "【验收标准（必填，用可验证的用例/命令表达）】",
            "重构后（含上面生成的行为基线测试）必须全部通过：",
            f"- 测试命令：{context['test_command']}",
            "- 用例：{给定输入 → 期望输出}（先由行为基线测试补齐，再逐条核对）",
            "",
            "【输出格式】",
            "1. 问题清单：问题 → 严重度(高/中/低) → 位置；",
            "2. 统一 diff（声明基线文件）或完整文件，二选一；",
            "3. 表格：每处改动 → 改了什么 → 为什么 → 影响面；",
            "4. 风险提示：哪些改动有兼容性风险。",
            "",
            "如有信息不足，先提问再动手。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_en(context: dict) -> str:
    fence = context["fence"]
    lines = [
        f"You are a senior {context['label']} engineer specialising in behaviour-preserving refactoring.",
        "",
        "[GUARD CLAUSES]",
        "- No code provided: output NO_CODE_PROVIDED and ask for it;",
        "- Nothing worth refactoring: output NO_REFACTORING_NEEDED with reasons; do not invent changes.",
        "",
        "[CONTEXT]",
        f"- Project/module: {context['project']}",
        f"- Language and framework: {context['label']} ({context['language']})",
        f"- What this code does / known pain points: {context['pain']}",
        "",
        "[CODE TO REFACTOR]",
        f"{fence}{context['fence_language']}",
        context["code"].rstrip(),
        fence,
        "",
        "[HARD CONSTRAINTS (must not violate)]",
        "1. External behaviour is 100% identical: do not change public API, return values, or exception types;",
        "2. No new third-party dependencies; do not weaken error handling, logging, or security checks;",
        "3. Follow the existing code style and naming conventions.",
    ]
    for index, constraint in enumerate(context["constraints"], 4):
        lines.append(f"{index}. {constraint}")
    lines.extend(["", "[REFACTORING GOALS]", "0. First generate behaviour-baseline (characterisation) tests as a safety net;"])
    for index, goal in enumerate(context["goals_en"], 1):
        lines.append(f"{index}. {goal}")
    lines.extend(
        [
            "",
            "[ACCEPTANCE CRITERIA (mandatory, expressed as runnable commands/cases)]",
            "After the refactor, all of the following must pass, including the baseline tests from goal 0:",
            f"- Test command: {context['test_command_en']}",
            "- Cases: {given input -> expected output} (fill in with the baseline tests)",
            "",
            "[OUTPUT FORMAT]",
            "1. Problem list: problem -> severity (high/medium/low) -> location;",
            "2. Unified diff (state the baseline file) or full files, pick one;",
            "3. Table: change -> what -> why -> blast radius;",
            "4. Risk notes: which changes carry compatibility risk.",
            "",
            "Ask clarifying questions before starting if information is missing.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Compose a self-verified refactoring prompt from source code.")
    parser.add_argument("--code", required=True, help="source file to embed, or - for stdin")
    parser.add_argument("--code-lang", help="override language auto-detection")
    parser.add_argument("--project", help="project/module name (default: file stem)")
    parser.add_argument("--pain", default="{一句话说明这段代码在做什么、哪里痛}", help="known pain points")
    parser.add_argument("--goal", action="append", default=[], help="refactoring goal (repeatable)")
    parser.add_argument("--constraint", action="append", default=[], help="extra hard constraint (repeatable)")
    parser.add_argument("--test-command", help="acceptance test command (default: per language)")
    parser.add_argument("--output-lang", choices=["zh", "en"], default="zh", help="language of the generated prompt")
    parser.add_argument("--out", help="write the prompt to FILE instead of stdout")
    args = parser.parse_args()

    if args.code == "-":
        code = sys.stdin.read()
        if not code.strip():
            print("no code on stdin", file=sys.stderr)
            return 2
        try:
            language = detect_language(None, args.code_lang)
        except ComposeError as exc:
            print(exc, file=sys.stderr)
            return 2
        default_project = "从标准输入读取的代码"
    else:
        source = Path(args.code)
        if not source.is_file():
            print(f"code file not found: {args.code}", file=sys.stderr)
            return 2
        code = source.read_text(encoding="utf-8")
        if not code.strip():
            print(f"code file is empty: {args.code}", file=sys.stderr)
            return 2
        try:
            language = detect_language(args.code, args.code_lang)
        except ComposeError as exc:
            print(exc, file=sys.stderr)
            return 2
        default_project = source.stem

    goals = args.goal or DEFAULT_GOALS.get(language, DEFAULT_GOALS["default"])
    goals_en = args.goal or DEFAULT_GOALS_EN.get(language, DEFAULT_GOALS_EN["default"])
    test_command = args.test_command or DEFAULT_TEST_COMMANDS[language]
    test_command_en = args.test_command or DEFAULT_TEST_COMMANDS_EN[language]

    context = {
        "language": language,
        "label": LANGUAGE_LABELS[language],
        "project": args.project or default_project,
        "pain": args.pain,
        "code": code,
        "fence": fence_for(code),
        "fence_language": fence_language(language),
        "test_command": test_command,
        "test_command_en": test_command_en,
        "goals": goals,
        "goals_en": goals_en,
        "constraints": args.constraint,
    }
    prompt = build_en(context) if args.output_lang == "en" else build_zh(context)

    checker = load_checker()
    result = checker.check(prompt, explicit_language=language)
    if not result["pass"]:
        print("generated prompt failed the self-check; refusing to emit it:", file=sys.stderr)
        for item in result["errors"]:
            print(f"  - {item['message']}", file=sys.stderr)
        print("adjust --goal / --constraint / --test-command and retry.", file=sys.stderr)
        return 1

    if args.out:
        Path(args.out).write_text(prompt, encoding="utf-8")
        print(f"wrote self-checked prompt to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(prompt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
