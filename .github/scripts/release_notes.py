#!/usr/bin/env python3
"""Build GitHub Release notes for a tag from CHANGELOG.md.

Usage: python3 .github/scripts/release_notes.py v1.0.0 > release-notes.md
Exits non-zero when the tag has no matching CHANGELOG section.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: release_notes.py <tag>", file=sys.stderr)
        return 2

    tag = sys.argv[1].strip()
    version = tag[1:] if tag[:1] in {"v", "V"} else tag
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    heading = re.compile(rf"^##\s*\[{re.escape(version)}\][^\n]*\n", re.M)
    match = heading.search(changelog)
    if not match:
        print(
            f"CHANGELOG.md 中找不到版本 [{version}] 的条目；请先补 CHANGELOG 再打标签。",
            file=sys.stderr,
        )
        return 1

    body = changelog[match.end() :]
    nxt = re.search(r"^##\s", body, re.M)
    if nxt:
        body = body[: nxt.start()]
    body = body.strip()

    repo = os.environ.get("GITHUB_REPOSITORY", "f-e-n-g-0531/code-refactor-prompts")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    url = f"{server}/{repo}"

    print(body)
    print()
    print("---")
    print()
    print(f"- 版本：`{version}`（标签 `{tag}`）")
    print(f"- 完整变更记录：{url}/blob/{tag}/CHANGELOG.md")
    print("- 安装：解压后将 `code-refactor-prompts/` 放入 `~/.dsh/skills/`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
