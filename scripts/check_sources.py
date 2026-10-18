#!/usr/bin/env python3
"""Check the external sources referenced by the skill.

Offline mode (default) validates that every URL is a well-formed http(s) URL
with a host and reports how many references were found. Online mode
(--online) additionally requests each URL and reports HTTP failures; it is
meant for the scheduled "Link check" workflow, not for every push.

Usage:
    python3 scripts/check_sources.py [paths...] [--online] [--timeout SECONDS] [--json]

Exit codes: 0 = all good, 1 = problems found, 2 = usage / input error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = ROOT / "references" / "sources.md"
URL_RE = re.compile(r"https?://[^\s<>()\[\]\"'\x60，。；、]+")
TRAILING = ".,;:!?)]}>，。；、"
USER_AGENT = (
    "Mozilla/5.0 (compatible; code-refactor-prompts-link-check/1.0; "
    "+https://github.com/f-e-n-g-0531/code-refactor-prompts)"
)
WARN_STATUSES = {403, 429}


def extract_urls(text: str) -> list[str]:
    """Return every URL occurrence in order, stripped of trailing punctuation."""
    return [match.group(0).rstrip(TRAILING) for match in URL_RE.finditer(text)]


def validate(url: str) -> str | None:
    """Return an error message for a malformed URL, else None."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return f"unsupported scheme {parsed.scheme!r}"
    if not parsed.netloc:
        return "missing host"
    host = parsed.hostname or ""
    if "." not in host and host != "localhost":
        return f"host {host!r} has no dot"
    return None


def classify(code: int) -> tuple[str, str]:
    if 200 <= code < 400:
        return "pass", f"HTTP {code}"
    if code in WARN_STATUSES:
        return "warn", f"HTTP {code} (blocked or rate-limited)"
    return "fail", f"HTTP {code}"


def curl_status(url: str, timeout: float) -> int | None:
    """Last-resort probe via curl for networks where Python's TLS is interfered with."""
    if shutil.which("curl") is None:
        return None
    try:
        result = subprocess.run(
            [
                "curl",
                "-sS",
                "-L",
                "-o",
                os.devnull,
                "-w",
                "%{http_code}",
                "--max-time",
                str(max(1, int(timeout))),
                "-A",
                USER_AGENT,
                url,
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    code = result.stdout.strip()
    return int(code) if result.returncode == 0 and code.isdigit() else None


def check_online(url: str, timeout: float, attempts: int = 2) -> tuple[str, str]:
    """Return (status, detail) where status is pass / warn / fail.

    Network errors are retried once; HTTP error codes are not (they are stable
    answers such as 404). If Python's TLS stack keeps failing (some networks
    interfere with it), fall back to curl when available.
    """
    last_error = ""
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response.read(2048)
                code = response.status
            return classify(code)
        except urllib.error.HTTPError as exc:
            return classify(exc.code)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
            if attempt < attempts:
                time.sleep(1.0)
    fallback = curl_status(url, timeout)
    if fallback is not None:
        status, detail = classify(fallback)
        return status, detail + " (curl fallback)"
    return "fail", f"request failed after {attempts} attempt(s): {last_error}"


def collect(paths: list[str]) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    problems: list[str] = []
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            problems.append(f"file not found: {raw}")
        else:
            files.append(path)
    return files, problems


def main() -> int:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Check external source links.")
    parser.add_argument("paths", nargs="*", help="files to scan (default: references/sources.md)")
    parser.add_argument("--online", action="store_true", help="request every URL (scheduled workflow)")
    parser.add_argument("--timeout", type=float, default=10.0, help="per-request timeout in seconds")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    if args.timeout <= 0:
        print("--timeout must be positive", file=sys.stderr)
        return 2

    paths = args.paths or [str(DEFAULT_SOURCES)]
    files, problems = collect(paths)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 2

    occurrences: list[str] = []
    for path in files:
        occurrences.extend(extract_urls(path.read_text(encoding="utf-8")))
    references = len(occurrences)
    urls = list(dict.fromkeys(occurrences))
    if not urls:
        print("no URLs found in: " + ", ".join(str(path) for path in files), file=sys.stderr)
        return 1

    entries: list[dict] = []
    for url in urls:
        problem = validate(url)
        if problem:
            entries.append({"url": url, "status": "invalid", "detail": problem})
        elif args.online:
            status, detail = check_online(url, args.timeout)
            entries.append({"url": url, "status": status, "detail": detail})
        else:
            entries.append({"url": url, "status": "pass", "detail": "syntax OK"})

    passed = sum(1 for entry in entries if entry["status"] == "pass")
    warned = sum(1 for entry in entries if entry["status"] == "warn")
    failed = sum(1 for entry in entries if entry["status"] in {"fail", "invalid"})
    ok = failed == 0
    duplicates = references - len(urls)

    if args.json:
        payload = {
            "pass": ok,
            "mode": "online" if args.online else "offline",
            "references": references,
            "unique_urls": len(urls),
            "counts": {"pass": passed, "warn": warned, "fail": failed},
            "urls": entries,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if ok else 1

    for entry in entries:
        label = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "invalid": "FAIL"}[entry["status"]]
        print(f"{label} {entry['url']} — {entry['detail']}")
    print(
        f"\n{references} reference(s), {len(urls)} unique URL(s); "
        f"{passed} pass, {warned} warn, {failed} fail"
        + (f"; {duplicates} duplicate reference(s)" if duplicates else "")
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
