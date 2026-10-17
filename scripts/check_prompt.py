#!/usr/bin/env python3
"""Structural self-check for a code-refactoring prompt produced with this skill.

This is a heuristic *structure* check, not a judgement of semantic quality.

Usage:
    python3 scripts/check_prompt.py <file|-> [--json]

Checks:
  - the eight required segments are present
  - acceptance criteria is verifiable (test command or input -> expected cases)
  - "keep behaviour unchanged" is backed by verifiable checks
  - hard constraints mention behaviour / API / signature compatibility

Exit codes: 0 = pass, 1 = problems found, 2 = usage error.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SEGMENTS = [
    ("role", "角色", r"角色|你是|作为.{0,12}(工程师|专家|开发)"),
    ("context", "上下文", r"上下文|背景"),
    ("code", "待重构代码", r"待重构代码|粘贴代码|代码如下|```"),
    ("constraints", "硬约束", r"硬约束|约束"),
    ("goals", "重构目标", r"重构目标|重构要求|目标"),
    ("acceptance", "验收标准", r"验收标准|验收"),
    ("output", "输出格式", r"输出格式"),
    ("guard", "守卫", r"前置判断|NO_CODE_PROVIDED|NO_REFACTORING_NEEDED|守卫"),
]

TEST_COMMAND = re.compile(
    r"(pytest|unittest|npm\s+(run\s+)?test|yarn\s+test|pnpm\s+test|mvn\s+(test|verify)|"
    r"gradle(w)?\s+test|go\s+test|cargo\s+test|dotnet\s+test|rspec|phpunit|ctest|"
    r"swift\s+test|jest|vitest|junit|tox|nox)",
    re.I,
)
VAGUE = re.compile(r"(保持|维持).{0,6}行为.{0,6}不变|行为(完全)?不变")
BEHAVIOUR_CONSTRAINT = re.compile(
    r"(行为|API|签名|异常|返回值|接口).{0,20}(一致|不变|兼容|保持)|"
    r"(一致|不变|兼容|保持).{0,20}(行为|API|签名|异常|返回值|接口)"
)


def check(text: str) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    missing = [label for _key, label, pattern in SEGMENTS if not re.search(pattern, text, re.S)]
    for label in missing:
        errors.append(f"缺少段落：{label}")

    arrows = text.count("→") + text.count("->")
    verifiable = bool(TEST_COMMAND.search(text) or "期望" in text or arrows >= 2)
    if not verifiable:
        errors.append("验收标准不可验证：未发现测试命令，也没有「输入 → 期望输出」用例")

    if VAGUE.search(text) and not verifiable:
        errors.append("出现「保持行为不变」但没有可验证的测试命令或用例，无法验收")

    if not BEHAVIOUR_CONSTRAINT.search(text):
        warnings.append("硬约束未显式约束行为 / API / 签名 / 异常兼容性")

    if not re.search(r"diff|完整文件|patch", text, re.I):
        warnings.append("输出格式未约定 unified diff / 完整文件 / patch")

    return {
        "pass": not errors,
        "errors": errors,
        "warnings": warnings,
        "missing_segments": missing,
        "verifiable": verifiable,
    }


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv[1:]
    if len(args) != 1:
        print("usage: check_prompt.py <file|-> [--json]", file=sys.stderr)
        return 2

    source = args[0]
    if source == "-":
        text = sys.stdin.read()
    else:
        path = Path(source)
        if not path.is_file():
            print(f"file not found: {source}", file=sys.stderr)
            return 2
        text = path.read_text(encoding="utf-8")

    result = check(text)

    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["pass"]:
        print("PASS: 8 segments present, acceptance criteria verifiable")
        for warning in result["warnings"]:
            print(f"  warn: {warning}")
    else:
        print(f"FAIL: {len(result['errors'])} problem(s) found")
        for error in result["errors"]:
            print(f"  - {error}")
        for warning in result["warnings"]:
            print(f"  warn: {warning}")

    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
