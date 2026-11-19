#!/usr/bin/env python3
"""Audit the prompt assets shipped with the skill.

Two audit levels:

1. Master templates (SKILL.md 默认模板, references/template-en.md) must pass the
   full shipped checker: eight segments, verifiable acceptance, language match,
   no anti-patterns.
2. The specialised prompt fragments in references/specialized-prompts.md
   intentionally inherit the master template; section 6 is a reference table.
   Every other section must contain a prompt block carrying a verification
   anchor (验收 / 验证 / 测试 / 等价 / 回归); the guard-clause variant instead
   must contain both NO_CODE_PROVIDED and NO_REFACTORING_NEEDED markers.
   No variant may contain the checker's error-level anti-patterns.

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
    ("SKILL.md", r"^## 默认模板", "默认模板（中文）"),
    ("references/template-en.md", r"^## Master template", "master template (English)"),
]
VARIANT_HEADING = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$", re.M)
VERIFICATION_ANCHOR = re.compile(r"验收|验证|测试|等价|回归", re.I)
# Section 6 is a language reference table, not a prompt fragment.
REFERENCE_SECTIONS = {("6", "分语言定制要点")}
GUARD_MARKERS = ("NO_CODE_PROVIDED", "NO_REFACTORING_NEEDED")


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
        blocks = list(checker.fenced_blocks(text))
        visible = checker._heading_text(text, blocks)
        heading = re.search(pattern, visible, re.M)
        end = len(text)
        if heading:
            following = re.compile(r"^#{1,2}[ \t]", re.M).search(visible, heading.end())
            if following:
                end = following.start()
        templates = [text[start:stop] for opener, _, start, stop, info, closed in blocks
                     if heading and heading.end() <= opener < end and closed and info == "text"]
        if len(templates) != 1:
            print(f"FAIL {label}: expected one closed text template block in {rel}, found {len(templates)}")
            failures += 1
            continue
        result = checker.check(templates[0])
        if result["pass"]:
            print(f"PASS {label}: passes the full prompt checker ({rel})")
        else:
            failures += 1
            print(f"FAIL {label}: fails the prompt checker ({rel})")
            for item in result["errors"]:
                print(f"  - {item['message']}")
    return failures


def variant_sections(text: str, checker):
    # Search only between fenced blocks, keeping offsets in the original text.
    headings = []
    offset = 0
    for start, end, *_ in checker.fenced_blocks(text):
        headings.extend(VARIANT_HEADING.finditer(text, offset, start))
        offset = end
    headings.extend(VARIANT_HEADING.finditer(text, offset))
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        yield heading.group(1), heading.group(2), text[heading.end() : end]


def restarts_prompt_fence(body: str, start: int, content_start: int, content_end: int) -> bool:
    # A missing closer can swallow the next section and use its closer.
    # Literal nested text fences must use a shorter or different delimiter.
    opener = re.match(r"[ \t]*(`+|~+)[ \t]*text[ \t]*\r?\n$", body[start:content_start])
    if opener is None:
        return False
    marker = re.escape(opener[1])
    return bool(re.search(rf"^[ \t]{{0,3}}{marker}[ \t]*text[ \t]*\r?$",
                          body[content_start:content_end], re.M))


def audit_variants(checker) -> int:
    text = VARIANTS.read_text(encoding="utf-8")
    failures = 0
    checked = 0
    seen_numbers: set[int] = set()
    for number, title, body in variant_sections(text, checker):
        index = int(number)
        if index in seen_numbers:
            print(f"FAIL variant {number} ({title}): duplicate variant number {index}")
            failures += 1
        seen_numbers.add(index)
        spans = list(checker.fenced_blocks(body))
        if any(not closed or restarts_prompt_fence(body, start, content_start, content_end)
               for start, _, content_start, content_end, _, closed in spans):
            checked += 1
            print(f"FAIL variant {number} ({title}): unclosed prompt fence or ambiguous nested prompt fence")
            failures += 1
            continue
        blocks = [body[start:end] for _, _, start, end, _, _ in spans if body[start:end].strip()]
        if not spans and (number, title) in REFERENCE_SECTIONS:
            print(f"SKIP variant {number} ({title}): reference table, no prompt block")
            continue
        checked += 1
        if not blocks:
            print(f"FAIL variant {number} ({title}): prompt block not found")
            failures += 1
            continue
        prompt = "\n".join(checker._heading_text(block) for block in blocks)
        problems: list[str] = []
        if "守卫" in title:
            if not all(marker in prompt for marker in GUARD_MARKERS):
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
    if not seen_numbers:
        print("FAIL specialised variants: no numbered variant headings")
        failures += 1
    elif not checked:
        print("FAIL specialised variants: no prompt variants found")
        failures += 1
    print(f"\n{checked} specialised variant(s) audited, {failures} failure(s).")
    return failures


def main() -> int:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
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
