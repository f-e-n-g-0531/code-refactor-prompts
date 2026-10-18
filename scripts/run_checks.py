#!/usr/bin/env python3
"""Run the repository's local quality gate with one command.

Usage:
    python3 scripts/run_checks.py [--full] [--list]

The fast gate validates the skill structure, audits templates, runs the tooling
regression tests and checks source links offline. --full additionally executes
all runnable examples (needs Go / Rust / Node / .NET / Python toolchains).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAST_STEPS = [
    ("structure validation", [sys.executable, str(ROOT / ".github" / "scripts" / "validate_skill.py")]),
    ("template audit", [sys.executable, str(ROOT / ".github" / "scripts" / "audit_templates.py")]),
    (
        "tooling tests",
        [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "scripts" / "tests"), "-p", "test_*.py"],
    ),
    ("source links (offline)", [sys.executable, str(ROOT / "scripts" / "check_sources.py")]),
]
FULL_STEPS = [
    (
        "executable examples",
        [sys.executable, str(ROOT / ".github" / "scripts" / "verify_examples.py"), "--require-all"],
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local quality gate.")
    parser.add_argument("--full", action="store_true", help="also execute the runnable examples")
    parser.add_argument("--list", action="store_true", help="list the steps and exit")
    args = parser.parse_args()

    steps = FAST_STEPS + (FULL_STEPS if args.full else [])
    if args.list:
        for name, _command in steps:
            print(name)
        return 0

    for name, command in steps:
        print(f"==> {name}", flush=True)
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode != 0:
            print(f"FAILED: {name}", file=sys.stderr)
            return 1
    print("OK: all local checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
