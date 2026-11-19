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
    # Keep the declaration rules aligned with validate_skill.check_frontmatter().
    blocks = re.findall(r"^metadata:[ \t]*\n((?:[ \t]+[^\n]*\n?)*)", frontmatter[1] + "\n", re.M) if frontmatter else []
    metadata = blocks[0] if len(blocks) == 1 else ""
    versions = re.findall(r"^[ \t]+version:[ \t]*([^\n]*)", metadata, re.M)
    declared_skill = (re.fullmatch(r'(?P<quote>"?)([0-9]+\.[0-9]+\.[0-9]+)(?P=quote)[ \t]*', versions[0])
                      if len(versions) == 1 else None)
    project = (root / "pyproject.toml").read_text(encoding="utf-8")
    section = re.search(r"^\[project\][ \t]*\n(.*?)(?=^\[|\Z)", project, re.M | re.S)
    declarations = re.findall(r'^[ \t]*(?:version|"version"|\x27version\x27)[ \t]*=[ \t]*([^\n]*)',
                              section[1], re.M) if section else []
    declared_project = (re.fullmatch(r'''("|')([0-9]+\.[0-9]+\.[0-9]+)\1[ \t]*(?:\#.*)?''', declarations[0])
                        if len(declarations) == 1 else None)
    if (declared_skill is None or declared_skill[2] != version
            or declared_project is None or declared_project[2] != version):
        raise ValueError(f"tag {tag} must match current SKILL.md metadata.version and pyproject.toml project.version")
    return version


def section_headings(changelog: str):
    """Yield level-two headings with original offsets, excluding code samples."""
    offset = 0
    fence = ""
    for line in changelog.splitlines(keepends=True):
        marker = re.match(r"^[ ]{0,3}(`{3,}|~{3,})([^\r\n]*)", line)
        if fence:
            if (marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence)
                    and not marker[2].strip(" \t")):
                fence = ""
        elif marker and not (marker[1][0] == "`" and "`" in marker[2]):
            fence = marker[1]
        elif re.match(r"^##[ \t]", line):
            yield offset, offset + len(line), line
        offset += len(line)


def main() -> int:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        print("usage: release_notes.py <tag>", file=sys.stderr)
        return 2

    tag = sys.argv[1]
    try:
        version = validate_tag(tag, ROOT)
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    try:
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"cannot read CHANGELOG.md: {error}", file=sys.stderr)
        return 1

    heading = re.compile(rf"^##[ \t]+\[{re.escape(version)}\]")
    sections = list(section_headings(changelog))
    matches = [index for index, (_, _, line) in enumerate(sections) if heading.match(line)]
    if not matches:
        print(
            f"CHANGELOG.md 中找不到版本 [{version}] 的条目；请先补 CHANGELOG 再打标签。",
            file=sys.stderr,
        )
        return 1

    if len(matches) != 1:
        print(f"duplicate version [{version}] in CHANGELOG.md", file=sys.stderr)
        return 1

    index = matches[0]
    start = sections[index][1]
    end = sections[index + 1][0] if index + 1 < len(sections) else len(changelog)
    body = changelog[start:end].strip()
    if not body:
        print(f"empty release notes for [{version}] in CHANGELOG.md", file=sys.stderr)
        return 1

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
