#!/usr/bin/env python3
"""Audit the prompt templates shipped with the skill using the shipped checker.

The master templates in SKILL.md and references/template-en.md must themselves
pass scripts/check_prompt.py. This keeps the template and the linter honest
instead of letting them drift apart.

Run with:  python3 .github/scripts/audit_templates.py
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scripts" / "check_prompt.py"

TARGETS = [
    ("SKILL.md", r"## 默认模板[^\n]*\n(?:.|\n)*?\x60\x60\x60text\n(.*?)\x60\x60\x60", "默认模板（中文）"),
    (
        "references/template-en.md",
        r"## Master template[^\n]*\n(?:.|\n)*?\x60\x60\x60text\n(.*?)\x60\x60\x60",
        "master template (English)",
    ),
]


def load_checker():
    spec = importlib.util.spec_from_file_location("check_prompt", CHECKER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    checker = load_checker()
    failures = 0
    for rel, pattern, label in TARGETS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        match = re.search(pattern, text, re.S)
        if not match:
            print(f"FAIL {label}: template block not found in {rel}")
            failures += 1
            continue
        result = checker.check(match.group(1))
        if result["pass"]:
            print(f"PASS {label}: template passes the prompt checker ({rel})")
        else:
            failures += 1
            print(f"FAIL {label}: template fails the prompt checker ({rel})")
            for item in result["errors"]:
                print(f"  - {item['message']}")

    print(f"\n{len(TARGETS) - failures}/{len(TARGETS)} template(s) pass the checker.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
