#!/usr/bin/env python3
"""Execute the worked examples instead of trusting them.

Verifiable examples carry two kinds of HTML markers:

    <!-- verify:run
    go test ./...
    -->

    <!-- verify:file=orders.go -->
    ```go
    package orders
    ...
    ```

Each marked fenced block is materialised into a fresh temporary directory with
the minimal scaffolding its toolchain needs (go.mod / Cargo.toml /
package.json), then the declared shell commands are executed. A non-zero exit
code fails the script, so "the examples really run" is enforced by CI rather
than asserted in prose.

Examples without a verify:run block are illustration-only and are skipped.

Usage:
    python3 .github/scripts/verify_examples.py [--only NAME] [--require-all]

Options:
    --only NAME      verify a single example by file stem
    --require-all    fail when a required toolchain is missing (CI uses this;
                     omit it locally to skip examples whose toolchain is absent)
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"
TIMEOUT_SECONDS = 180

RUN_RE = re.compile(r"<!--\s*verify:run\s*\r?\n(.*?)\r?\n\s*-->", re.S)
FILE_RE = re.compile(
    r"<!--\s*verify:file=([^\s>]+?)\s*-->\s*\r?\n"
    r"```[^\r\n]*\r?\n(.*?)\r?\n```[ \t]*(?:\r?\n|$)",
    re.S,
)

TOOL_FOR_TOKEN = {
    "go": "go",
    "cargo": "cargo",
    "node": "node",
    "npm": "npm",
    "python": "python",
    "python3": "python",
    "pytest": "python",
}


class ExampleError(Exception):
    pass


def parse_example(path: Path) -> tuple[list[tuple[str, str]], list[str]]:
    text = path.read_text(encoding="utf-8")
    run_match = RUN_RE.search(text)
    if not run_match:
        return [], []

    commands = [
        line.strip()
        for line in run_match.group(1).splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    files: list[tuple[str, str]] = []
    for match in FILE_RE.finditer(text):
        name = match.group(1)
        target = Path(name)
        if target.is_absolute() or ".." in target.parts:
            raise ExampleError(f"unsafe verify:file target: {name!r}")
        files.append((name, match.group(2)))
    if not files:
        raise ExampleError("verify:run declared but no verify:file blocks found")
    if not commands:
        raise ExampleError("verify:run block is empty")
    return files, commands


def scaffold(directory: Path, names: set[str]) -> None:
    """Add the minimal build metadata a toolchain needs, if not provided."""
    if any(n.endswith(".go") for n in names) and "go.mod" not in names:
        (directory / "go.mod").write_text("module verify.local/example\n\ngo 1.21\n", encoding="utf-8")
    if any(n.endswith(".rs") for n in names) and "Cargo.toml" not in names:
        if "src/lib.rs" not in names:
            raise ExampleError("Rust example must provide src/lib.rs")
        (directory / "Cargo.toml").write_text(
            '[package]\nname = "verify_example"\nversion = "0.1.0"\nedition = "2021"\n\n'
            '[lib]\npath = "src/lib.rs"\n',
            encoding="utf-8",
        )
    if any(n.endswith((".ts", ".tsx", ".mts")) for n in names) and "package.json" not in names:
        (directory / "package.json").write_text('{"type": "module"}\n', encoding="utf-8")


def command_for_shell(command: str) -> str:
    """Run python commands with the current interpreter, whatever its name."""
    parts = command.split()
    if parts and parts[0] in {"python", "python3"}:
        return " ".join(['"' + sys.executable + '"'] + parts[1:])
    return command


def required_tool(command: str) -> str | None:
    first = command.split()[0]
    return TOOL_FOR_TOKEN.get(first)


def tool_available(tool: str) -> bool:
    if tool == "python":
        return True
    return shutil.which(tool) is not None


def verify_example(path: Path) -> tuple[str, list[str]]:
    files, commands = parse_example(path)
    if not commands:
        return "skipped", []

    missing = sorted({t for t in (required_tool(c) for c in commands) if t and not tool_available(t)})
    if missing:
        return "missing-toolchain", missing

    with tempfile.TemporaryDirectory(prefix="example-") as raw_tmp:
        tmp = Path(raw_tmp)
        for name, content in files:
            target = tmp / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content + "\n", encoding="utf-8")
        scaffold(tmp, {name for name, _ in files})

        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["CARGO_TERM_COLOR"] = "never"

        for command in commands:
            shell_command = command_for_shell(command)
            result = subprocess.run(
                shell_command,
                cwd=tmp,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=TIMEOUT_SECONDS,
                env=env,
            )
            if result.returncode != 0:
                output = (result.stdout + result.stderr).strip()
                raise ExampleError(
                    f"command failed ({result.returncode}): {command}\n{output[-4000:]}"
                )
    return "passed", commands


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute verifiable worked examples.")
    parser.add_argument("--only", help="single example file stem")
    parser.add_argument("--require-all", action="store_true", help="fail on missing toolchains")
    args = parser.parse_args()

    paths = sorted(EXAMPLES.glob("*.md"))
    if args.only:
        paths = [p for p in paths if p.stem == args.only]
        if not paths:
            print(f"no example named {args.only!r}", file=sys.stderr)
            return 2

    failed = 0
    verified = 0
    for path in paths:
        name = path.stem
        try:
            status, detail = verify_example(path)
        except ExampleError as exc:
            print(f"FAIL {name}\n  {exc}")
            failed += 1
            continue
        except subprocess.TimeoutExpired:
            print(f"FAIL {name}\n  command timed out after {TIMEOUT_SECONDS}s")
            failed += 1
            continue

        if status == "passed":
            verified += 1
            print(f"PASS {name}: " + "; ".join(detail))
        elif status == "skipped":
            print(f"SKIP {name}: illustration-only (no verify:run marker)")
        elif status == "missing-toolchain":
            message = f"{name}: missing toolchain(s) {', '.join(detail)}"
            if args.require_all:
                print(f"FAIL {message}")
                failed += 1
            else:
                print(f"SKIP {message}")

    print(f"\n{verified} example(s) executed green, {failed} failure(s).")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
