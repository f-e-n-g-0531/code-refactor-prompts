#!/usr/bin/env python3
"""Build GitHub Release notes for a tag from CHANGELOG.md.

Usage: python3 .github/scripts/release_notes.py v1.0.0 > release-notes.md
Exits non-zero unless the tag matches current metadata and a CHANGELOG section.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def validate_tag(tag: str, root: Path = ROOT) -> str:
    """Reject unsafe tags and tags for a historical or inconsistent version."""
    if not re.fullmatch(r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", tag):
        raise ValueError("tag must look like vX.Y.Z")
    version = tag[1:]
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = re.match(r"^---\r?\n(.*?)\r?\n---(?:\r?\n|$)", skill, re.S)
    metadata = re.search(r"^metadata:[ \t]*\n((?:[ \t]+[^\n]*\n?)*)", frontmatter.group(1) + "\n", re.M) if frontmatter else None
    # Any indentation level is legal YAML; must stay in sync with
    # validate_skill.check_frontmatter().
    declared_skill = re.findall(r'^\s+version:[ \t]*"?([0-9]+\.[0-9]+\.[0-9]+)"?[ \t]*$', metadata.group(1), re.M) if metadata else []
    project = (root / "pyproject.toml").read_text(encoding="utf-8")
    section = re.search(r"^\[project\][ \t]*\n(.*?)(?=^\[|\Z)", project, re.M | re.S)
    declared_project = re.findall(r'^version[ \t]*=[ \t]*"([^"\n]+)"[ \t]*$', section.group(1), re.M) if section else []
    if declared_skill != [version] or declared_project != [version]:
        raise ValueError(f"tag {tag} must match current SKILL.md metadata.version and pyproject.toml project.version")
    return version


def main() -> int:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        print("usage: release_notes.py <tag>", file=sys.stderr)
        return 2

    tag = sys.argv[1]
    try:
        version = validate_tag(tag)
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
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
