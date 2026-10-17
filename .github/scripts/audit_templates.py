#!/usr/bin/env python3
"""Audit the prompt assets shipped with the skill.

Two audit levels:

1. Master templates (SKILL.md 默认模板, references/template-en.md) must pass the
   full shipped checker: eight segments, verifiable acceptance, language match,
   no anti-patterns.
2. The 13 specialised variants in references/specialized-prompts.md are
   fragments that intentionally inherit the master template. Each one must still
   carry a verification anchor (验收 / 验证 / 测试 / 等价 / 回归); the guard-clause
   variant instead must contain the NO_CODE_PROVIDED / NO_REFACTORING_NEEDED
   markers. No variant may contain the checker's error-level anti-patterns.

Run with:  python3 .github/scripts/audit_templates.py
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scripts" / "check_prompt.py"
VARIANTS = ROOT / "references" / "specialized-prompts.md"

MASTER_TEMPLATES = [
    ("SKILL.md", r"## 默认模板[^\n]*\n(?:.|\n)*?\x60\x60\x60text\n(.*?)\x60\x60\x60", "默认模板（中文）"),
    (
        "references/template-en.md",
        r"## Master template[^\n]*\n(?:.|\n)*?\x60\x60\x60text\n(.*?)\x60\x60\x60",
        "master template (English)",
    ),
]

VARIANT_HEADING = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$", re.M)
FENCE = re.compile(r"\x60\x60\x60[^\r\n]*\r?\n(.*?)\r?\n?\x60\x60\x60", re.S)
VERIFICATION_ANCHOR = re.compile(r"验收|验证|测试|等价|回归", re.I)
GUARD_MARKER = re.compile(r"NO_CODE_PROVIDED|NO_REFACTORING_NEEDED")


def load_checker():
    spec = importlib.util.spec_from_file_location("check_prompt", CHECKER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def audit_master_templates(checker) -> int:
    failures = 0
    for rel, pattern, label in MASTER_TEMPLATES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        match = re.search(pattern, text, re.S)
        if not match:
            print(f"FAIL {label}: template block not found in {rel}")
            failures += 1
            continue
        result = checker.check(match.group(1))
        if result["pass"]:
            print(f"PASS {label}: passes the full prompt checker ({rel})")
        else:
            failures += 1
            print(f"FAIL {label}: fails the prompt checker ({rel})")
            for item in result["errors"]:
                print(f"  - {item['message']}")
    return failures


def variant_sections(text: str):
    headings = list(VARIANT_HEADING.finditer(text))
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        yield heading.group(1), heading.group(2), text[heading.end() : end]


def audit_variants(checker) -> int:
    text = VARIANTS.read_text(encoding="utf-8")
    failures = 0
    checked = 0
    for number, title, body in variant_sections(text):
        blocks = FENCE.findall(body)
        if not blocks:
            print(f"SKIP variant {number} ({title}): reference table, no prompt block")
            continue
        prompt = "\n".join(blocks)
        checked += 1
        problems: list[str] = []
        if "守卫" in title:
            if not GUARD_MARKER.search(prompt):
                problems.append("guard variant lacks NO_CODE_PROVIDED / NO_REFACTORING_NEEDED markers")
        elif not VERIFICATION_ANCHOR.search(prompt):
            problems.append("no verification anchor (验收 / 验证 / 测试 / 等价 / 回归)")
        for code, pattern, severity, _message in checker.ANTI_PATTERNS:
            if severity == "error" and pattern.search(prompt):
                problems.append(f"anti-pattern: {code}")
        if problems:
            failures += 1
            print(f"FAIL variant {number} ({title}): " + "; ".join(problems))
        else:
            kind = "guard fragment" if "守卫" in title else "verification anchor"
            print(f"PASS variant {number} ({title}): {kind}")
    print(f"\n{checked} specialised variant(s) audited, {failures} failure(s).")
    return failures


def main() -> int:
    checker = load_checker()
    failures = audit_master_templates(checker)
    failures += audit_variants(checker)
    if failures:
        print(f"\nTOTAL: {failures} audit failure(s).")
        return 1
    print("\nTOTAL: master templates and specialised variants pass the audit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
