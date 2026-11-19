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
package.json / Example.csproj), then the declared shell commands are executed.
A non-zero exit code fails the script, so "the examples really run" is enforced
by CI rather than asserted in prose.

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
import time
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"
TIMEOUT_SECONDS = 240

RUN_RE = re.compile(r"<!--\s*verify:run\s*\r?\n(.*?)\r?\n\s*-->", re.S)
FILE_RE = re.compile(
    r"<!--\s*verify:file=([^\s>]+?)\s*-->\s*\r?\n"
    r"\x60\x60\x60[^\r\n]*\r?\n(.*?)\r?\n\x60\x60\x60[ \t]*(?:\r?\n|$)",
    re.S,
)

TOOL_FOR_TOKEN = {
    "go": "go",
    "cargo": "cargo",
    "node": "node",
    "npm": "npm",
    "dotnet": "dotnet",
    "python": "python",
    "python3": "python",
    "pytest": "python",
    "javac": "javac",
    "java": "java",
}


class ExampleError(Exception):
    pass


def remove_tree_with_retry(directory: Path, attempts: int = 21, delay: float = 0.5) -> None:
    """Remove a temp tree, tolerating transient external holds on Windows.

    A toolchain or external scanner can briefly hold a freshly built file
    (e.g. a Go test binary) right after execution, making the first rmtree
    raise PermissionError (WinError 32). Retry a bounded number of times and
    re-raise when the hold persists, so real leaks still fail loudly.
    """
    for attempt in range(attempts):
        try:
            shutil.rmtree(directory)
            return
        except FileNotFoundError:
            return  # already removed
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)


def marker_offsets(text: str):
    """Find standalone marker starts outside Markdown code fences."""
    offset = 0
    fence = ""
    declaration = re.compile(r"[ \t]*<!--\s*verify:")
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^[ \t]{0,3}(\x60{3,}|~{3,})([^\r\n]*)", line)
        if fence:
            if marker and marker[1].startswith(fence) and not marker[2].strip(" \t"):
                fence = ""
        elif marker and not (marker[1][0] == chr(96) and chr(96) in marker[2]):
            fence = marker[1]
        elif line.lstrip(" \t").startswith("<!--") and declaration.match(text, offset):
            yield offset + line.index("<!--")
        offset += len(line)


def parse_example(path: Path) -> tuple[list[tuple[str, str]], list[str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ExampleError("example document is not valid UTF-8") from exc
    except OSError as exc:
        raise ExampleError(f"cannot read example document: {exc}") from exc
    declared = set(marker_offsets(text))
    if not declared:
        return [], []
    runs = [match for match in RUN_RE.finditer(text) if match.start() in declared]
    file_blocks = [match for match in FILE_RE.finditer(text) if match.start() in declared]
    # A declared but malformed marker must never become an illustration-only skip.
    parsed_starts = {match.start() for match in runs + file_blocks}
    if len(runs) != 1 or declared != parsed_starts:
        raise ExampleError("expected one valid verify:run block and valid verify:file blocks")
    run_match = runs[0]

    commands = [
        line.strip()
        for line in run_match.group(1).splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    files: list[tuple[str, str]] = []
    targets: set[tuple[str, ...]] = set()
    for match in file_blocks:
        name = match.group(1)
        parts = name.split("/")
        windows = PureWindowsPath(name)
        # Markers use portable, canonical POSIX-relative names on every host.
        if (windows.drive or windows.root or "\\" in name
                or any(part in {"", ".", ".."} or part.endswith((".", " "))
                       or re.search(r'[<>:"|?*\x00-\x1f]', part)
                       or re.fullmatch(r"(?i:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³])",
                                       part.split(".", 1)[0].rstrip(" ")) for part in parts)):
            raise ExampleError(f"unsafe verify:file target: {name!r}")
        key = tuple(part.casefold() for part in parts)
        if any(key == other or key[:len(other)] == other or other[:len(key)] == key
               for other in targets):
            raise ExampleError(f"duplicate or conflicting verify:file target: {name!r}")
        targets.add(key)
        files.append((name, match.group(2)))
    if not files:
        raise ExampleError("verify:run declared but no verify:file blocks found")
    if not commands:
        raise ExampleError("verify:run block is empty")
    return files, commands


def dotnet_target_framework() -> str:
    try:
        result = subprocess.run(
            ["dotnet", "--version"], capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.TimeoutExpired) as exc:  # pragma: no cover - env dependent
        raise ExampleError(f"cannot determine .NET SDK version: {exc}") from exc
    version = result.stdout.strip()
    major = version.split(".", 1)[0]
    if result.returncode != 0 or not major.isdigit():
        raise ExampleError(f"cannot determine .NET SDK version from {version!r}")
    return f"net{major}.0"


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
    if any(n.endswith(".cs") for n in names) and not any(n.endswith(".csproj") for n in names):
        tfm = dotnet_target_framework()
        (directory / "Example.csproj").write_text(
            "<Project Sdk=\"Microsoft.NET.Sdk\">\n"
            "  <PropertyGroup>\n"
            "    <OutputType>Exe</OutputType>\n"
            f"    <TargetFramework>{tfm}</TargetFramework>\n"
            "    <Nullable>disable</Nullable>\n"
            "    <ImplicitUsings>disable</ImplicitUsings>\n"
            "    <AssemblyName>example</AssemblyName>\n"
            "  </PropertyGroup>\n"
            "</Project>\n",
            encoding="utf-8",
        )


def command_for_shell(command: str) -> str:
    """Run python commands with the current interpreter, whatever its name."""
    # Replace just the executable token; the shell must see the original
    # arguments, including whitespace inside quoted strings.
    match = re.match(r"^python3?(?=\s|$)", command)
    if match:
        return '"' + sys.executable + '"' + command[match.end():]
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

    try:
        tmp = Path(tempfile.mkdtemp(prefix="example-"))
    except OSError as exc:
        raise ExampleError(f"cannot create temporary directory: {exc}") from exc
    failure = None
    try:
        for name, content in files:
            target = tmp / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content + "\n", encoding="utf-8")
        scaffold(tmp, {name for name, _ in files})

        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["CARGO_TERM_COLOR"] = "never"
        env["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"
        env["DOTNET_NOLOGO"] = "1"
        env["DOTNET_SKIP_FIRST_TIME_EXPERIENCE"] = "1"

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
    except (ExampleError, subprocess.TimeoutExpired, OSError) as exc:
        failure = exc
        if isinstance(exc, subprocess.TimeoutExpired):
            message = f"command timed out after {exc.timeout}s: {command}"
        elif isinstance(exc, OSError):
            message = f"cannot prepare or execute example: {exc}"
        else:
            message = str(exc)
    finally:
        try:
            remove_tree_with_retry(tmp)
        except OSError as exc:
            cleanup = f"cannot clean up temporary directory {tmp}: {exc}"
            if failure is None:
                raise ExampleError(cleanup) from exc
            message = message.rstrip() + "\n  " + cleanup
    if failure is not None:
        raise ExampleError(message) from failure
    return "passed", commands


def main() -> int:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
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

    if args.require_all and verified == 0:
        print("FAIL no executable examples were successfully executed")
        failed += 1
    print(f"\n{verified} example(s) executed green, {failed} failure(s).")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
