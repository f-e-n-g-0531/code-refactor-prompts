#!/usr/bin/env python3
"""Validate the code-refactor-prompts DSH skill.

Used by .github/workflows/ci.yml and .github/workflows/release.yml.
Run locally with:  python3 .github/scripts/validate_skill.py
Exits non-zero and prints a readable problem list on failure.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_NAME = "code-refactor-prompts"

REQUIRED_FILES = [
    "SKILL.md",
    "README.md",
    "README.en.md",
    "CHANGELOG.md",
    "LICENSE",
    ".gitignore",
    "references/specialized-prompts.md",
    "references/language-specific.md",
    "references/sources.md",
    "references/workflows.md",
    "examples/java-order-calculator-strategy-c.md",
    "examples/python-legacy-characterisation.md",
    "examples/go-legacy-order-total.md",
    "scripts/check_prompt.py",
    "scripts/fixtures/good-prompt.txt",
    "scripts/fixtures/bad-prompt.txt",
]

# Process / placeholder copy that must never leak into a released skill.
BANNED_PATTERNS = [
    r"author:\s*user\b",
    r"\bTODO\b",
    r"\bFIXME\b",
    r"继续深挖",
    r"检索词",
    r"检索与核验时间",
    r"占位作者",
]

errors: list[str] = []
warnings: list[str] = []


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def check_required_files() -> None:
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).is_file():
            errors.append(f"缺少必需文件：{rel}")


def check_frontmatter() -> str | None:
    skill = read("SKILL.md")
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", skill, re.S)
    if not match:
        errors.append("SKILL.md：缺少 YAML frontmatter（首行应为 ---）")
        return None

    frontmatter = match.group(1)

    def value(key: str) -> str | None:
        found = re.search(rf"^{re.escape(key)}:\s*(.+)$", frontmatter, re.M)
        return found.group(1).strip().strip('"') if found else None

    name = value("name")
    description = value("description")
    license_id = value("license")

    if name != SKILL_NAME:
        errors.append(f"SKILL.md：frontmatter name 应为 {SKILL_NAME!r}，实际 {name!r}")
    if not description or len(description) < 40:
        errors.append("SKILL.md：description 缺失或过短（<40 字符），会影响技能触发")
    if license_id != "MIT":
        errors.append(f"SKILL.md：license 应为 MIT，实际 {license_id!r}")
    if not re.search(r"^\s+author:\s*\S+", frontmatter, re.M):
        errors.append("SKILL.md：metadata.author 缺失")

    version_match = re.search(r'^\s+version:\s*"?([0-9]+\.[0-9]+\.[0-9]+)"?\s*$', frontmatter, re.M)
    if not version_match:
        errors.append("SKILL.md：metadata.version 缺失或不是语义化版本（X.Y.Z）")
        return None
    return version_match.group(1)


def check_version(version: str | None) -> None:
    if not version or not (ROOT / "CHANGELOG.md").is_file():
        return
    changelog = read("CHANGELOG.md")
    if not re.search(rf"^##\s*\[{re.escape(version)}\]", changelog, re.M):
        errors.append(f"CHANGELOG.md：缺少版本 [{version}] 的记录")


def check_references_wired() -> None:
    skill = read("SKILL.md")
    for ref in (
        "references/specialized-prompts.md",
        "references/language-specific.md",
        "references/sources.md",
        "references/workflows.md",
    ):
        if ref not in skill:
            errors.append(f"SKILL.md：未引用 {ref}")


def check_counts() -> None:
    readme = read("README.md")
    variants = len(re.findall(r"^##\s+\d+\.", read("references/specialized-prompts.md"), re.M))
    claimed = re.search(r"(\d+)\s*个专项变体", readme)
    if claimed and int(claimed.group(1)) != variants:
        errors.append(f"README 声称 {claimed.group(1)} 个专项变体，实际 {variants} 个")

    sources = len(re.findall(r"^###\s+\d+\.", read("references/sources.md"), re.M))
    claimed = re.search(r"出处与依据（(\d+) 条）", readme)
    if claimed and int(claimed.group(1)) != sources:
        errors.append(f"README 声称 {claimed.group(1)} 条出处，实际 {sources} 条")


def iter_markdown():
    for path in sorted(ROOT.rglob("*.md")):
        if ".git" in path.parts or ".github" in path.parts:
            continue
        yield path


def check_copy() -> None:
    for path in iter_markdown():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        for pattern in BANNED_PATTERNS:
            for hit in re.finditer(pattern, text):
                line = text[: hit.start()].count("\n") + 1
                errors.append(f"{rel}:{line} 含禁止的过程性/占位文案：{hit.group(0)!r}")


def check_links() -> None:
    for path in iter_markdown():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        for hit in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", text):
            target = hit.group(1).strip()
            if re.match(r"^(https?:|mailto:|#)", target) or target.startswith("<"):
                continue
            local = target.split("#", 1)[0]
            if not (path.parent / local).resolve().exists():
                errors.append(f"{rel}: 相对链接指向不存在的文件：{target}")


def main() -> int:
    check_required_files()
    version = check_frontmatter()
    check_version(version)
    check_references_wired()
    check_counts()
    check_copy()
    check_links()

    for warning in warnings:
        print(f"WARN: {warning}")
    if errors:
        print(f"FAILED: {len(errors)} problem(s) found")
        for item in errors:
            print(f"  - {item}")
        return 1
    print("OK: skill structure, frontmatter, version, references, links and copy are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
