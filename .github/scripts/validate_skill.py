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
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "LICENSE",
    ".gitignore",
    ".pre-commit-hooks.yaml",
    "action.yml",
    "pyproject.toml",
    "references/specialized-prompts.md",
    "references/language-specific.md",
    "references/sources.md",
    "references/workflows.md",
    "references/template-en.md",
    "references/checklists.md",
    "examples/java-order-calculator-strategy-c.md",
    "examples/python-legacy-characterisation.md",
    "examples/go-legacy-order-total.md",
    "examples/rust-legacy-order-total.md",
    "examples/typescript-legacy-characterisation.md",
    "examples/csharp-legacy-order-total.md",
    "examples/sql-legacy-report-equivalence.md",
    "scripts/check_prompt.py",
    "scripts/check_sources.py",
    "scripts/compose_prompt.py",
    "scripts/run_checks.py",
    "scripts/fixtures/sample.go",
    "scripts/fixtures/sample.py",
    "scripts/tests/test_check_prompt.py",
    "scripts/tests/test_check_sources.py",
    "scripts/tests/test_compose_prompt.py",
    "scripts/tests/test_batch_and_hook.py",
    "scripts/tests/test_run_checks.py",
    "scripts/tests/test_validate_skill.py",
    "scripts/fixtures/good-prompt.txt",
    "scripts/fixtures/good-go-prompt.txt",
    "scripts/fixtures/good-en-prompt.txt",
    "scripts/fixtures/bad-prompt.txt",
    "scripts/fixtures/bad-language-prompt.txt",
    "scripts/fixtures/bad-antipattern-prompt.txt",
    "scripts/fixtures/bad-en-prompt.txt",
    "scripts/fixtures/weak-prompt.txt",
    ".github/scripts/verify_examples.py",
    ".github/scripts/audit_templates.py",
    ".github/workflows/link-check.yml",
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
        "references/template-en.md",
        "references/checklists.md",
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

    executable = sum(
        1
        for path in (ROOT / "examples").glob("*.md")
        if "<!-- verify:run" in path.read_text(encoding="utf-8")
    )
    claimed = re.search(r"(\d+)\s*个可执行样例", readme)
    if claimed and int(claimed.group(1)) != executable:
        errors.append(f"README 声称 {claimed.group(1)} 个可执行样例，实际 {executable} 个")
    readme_en = read("README.en.md")
    claimed = re.search(r"(\d+)\s*runnable examples", readme_en)
    if claimed and int(claimed.group(1)) != executable:
        errors.append(f"README.en 声称 {claimed.group(1)} 个可执行样例，实际 {executable} 个")
    claimed = re.search(r"(\d+)\s+specialised", readme_en)
    if claimed and int(claimed.group(1)) != variants:
        errors.append(f"README.en 声称 {claimed.group(1)} 个专项变体，实际 {variants} 个")
    claimed = re.search(r"(\d+)\s+sources", readme_en)
    if claimed and int(claimed.group(1)) != sources:
        errors.append(f"README.en 声称 {claimed.group(1)} 条出处，实际 {sources} 条")


def count_test_methods() -> int:
    total = 0
    for path in sorted((ROOT / "scripts" / "tests").glob("test_*.py")):
        total += len(
            re.findall(r"^\s+(?:async\s+)?def test_", path.read_text(encoding="utf-8"), re.M)
        )
    return total


def check_test_counts() -> None:
    """The test count advertised in the READMEs must match the actual test methods."""
    actual = count_test_methods()
    for rel, pattern in (
        ("README.md", r"以\s*(\d+)\s*个用例"),
        ("README.en.md", r"with\s+(\d+)\s+tests"),
    ):
        claimed = re.search(pattern, read(rel))
        if claimed and int(claimed.group(1)) != actual:
            errors.append(f"{rel} 声称 {claimed.group(1)} 个用例，实际 {actual} 个")


def strip_fenced_blocks(text: str) -> str:
    """Blank out fenced code blocks so headings inside code samples are ignored."""
    lines: list[str] = []
    fence_char = ""
    fence_length = 0
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if fence_char:
            lines.append("")
            if marker and marker.group(1)[0] == fence_char and len(marker.group(1)) >= fence_length:
                fence_char = ""
                fence_length = 0
        elif marker:
            fence_char = marker.group(1)[0]
            fence_length = len(marker.group(1))
            lines.append("")
        else:
            lines.append(line)
    return "\n".join(lines)


def check_markdown_structure() -> None:
    """Every Markdown document needs one H1 and must not repeat H2 section titles.

    A repeated H2 is the fingerprint of an accidental full-document paste (the
    v1.8.0 README duplication), which link/count checks alone cannot detect.
    """
    for path in iter_markdown():
        rel = path.relative_to(ROOT).as_posix()
        text = strip_fenced_blocks(path.read_text(encoding="utf-8"))
        h1 = re.findall(r"^# \S.*$", text, re.M)
        if len(h1) != 1:
            errors.append(f"{rel}：应恰好有 1 个一级标题，实际 {len(h1)} 个")
        h2 = re.findall(r"^## \S.*$", text, re.M)
        for heading in sorted({h for h in h2 if h2.count(h) > 1}):
            errors.append(f"{rel}：二级标题重复「{heading[3:].strip()}」（疑似整段内容被重复粘贴）")


def check_version_refs(version: str | None) -> None:
    """Version references in the docs and hook comment must track metadata.version."""
    if not version:
        return
    for rel in ("README.md", "README.en.md", ".pre-commit-hooks.yaml"):
        found = re.findall(r"rev:\s*['\"]?v(\d+\.\d+\.\d+)['\"]?", read(rel))
        if not found:
            errors.append(f"{rel}：缺少 rev: v{version} 版本引用")
        for got in found:
            if got != version:
                errors.append(f"{rel}：rev: v{got} 与 SKILL.md 的 metadata.version {version} 不一致")
    for rel in ("README.md", "README.en.md"):
        action_versions = re.findall(r"code-refactor-prompts@v(\d+\.\d+\.\d+)", read(rel))
        if not action_versions:
            errors.append(f"{rel}：缺少 GitHub Action 的 @v{version} 示例引用")
        for got in action_versions:
            if got != version:
                errors.append(f"{rel}：Action 示例 @v{got} 与 metadata.version {version} 不一致")
    pyproject = read("pyproject.toml")
    declared = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M)
    if not declared:
        errors.append("pyproject.toml：缺少 version（应与 SKILL.md 的 metadata.version 一致）")
    elif declared.group(1) != version:
        errors.append(
            f"pyproject.toml：version {declared.group(1)} 与 SKILL.md 的 metadata.version {version} 不一致"
        )


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


def check_examples() -> None:
    """Samples must be listed in both READMEs; executable ones must declare markers."""
    readme = read("README.md")
    readme_en = read("README.en.md")
    examples = sorted((ROOT / "examples").glob("*.md"))
    if not examples:
        errors.append("examples/ 下没有任何样例")
    for path in examples:
        name = path.name
        text = path.read_text(encoding="utf-8")
        for document, label in ((readme, "README.md"), (readme_en, "README.en.md")):
            if name not in document:
                errors.append(f"{label}：未列出样例 {name}")
        has_run = "<!-- verify:run" in text
        marked = len(re.findall(r"<!--\s*verify:file=", text))
        if has_run and marked == 0:
            errors.append(f"examples/{name}：声明了 verify:run 但没有 verify:file 代码块")
        if not has_run and marked > 0:
            errors.append(f"examples/{name}：有 verify:file 代码块但没有 verify:run 命令")


def check_ci_wiring() -> None:
    """The prompt checker self-tests and example verification must run in CI."""
    ci = read(".github/workflows/ci.yml")
    if "verify_examples.py" not in ci:
        errors.append("ci.yml：未接入 verify_examples.py（可执行样例将不再被验证）")
    if "audit_templates.py" not in ci:
        errors.append("ci.yml：未接入 audit_templates.py（模板自审计缺失）")
    if "compose_prompt.py" not in ci:
        errors.append("ci.yml：未自测 compose_prompt.py（生成器未闭环验证）")
    if "--fix" not in ci:
        errors.append("ci.yml：未自测 check_prompt.py --fix（修复闭环未验证）")
    if "scripts/tests" not in ci:
        errors.append("ci.yml：未运行工具链回归测试（scripts/tests）")
    if "Test the packaged pre-commit console script" not in ci:
        errors.append("ci.yml：缺少「Test the packaged pre-commit console script」步骤")
    if "pre-commit try-repo" not in ci:
        errors.append("ci.yml：未做 pre-commit 端到端测试（try-repo）")
    if "check_sources.py" not in ci:
        errors.append("ci.yml：未运行离线出处链接检查（check_sources.py）")
    if "run_checks.py --list" not in ci:
        errors.append("ci.yml：未验证一键本地门禁接线（run_checks.py --list）")
    if "windows-latest" not in ci:
        errors.append("ci.yml：缺少跨平台校验（windows-latest 的 Windows runner）")
    for workflow in (".github/workflows/ci.yml", ".github/workflows/release.yml"):
        if "CONTRIBUTING.md" not in read(workflow):
            errors.append(f"{workflow}：发布打包未包含 CONTRIBUTING.md")
    if "--format github" not in ci:
        errors.append("ci.yml：未自测 GitHub 注解输出（--format github）")
    release = read(".github/workflows/release.yml")
    if "pre-commit try-repo" not in release:
        errors.append("release.yml：未做 pre-commit 端到端测试（try-repo）")
    if "release artifact OK" not in release:
        errors.append("release.yml：缺少发布产物校验（必须含 pyproject.toml、不得含 .github）")
    for fixture in (
        "good-prompt.txt",
        "good-go-prompt.txt",
        "bad-prompt.txt",
        "bad-language-prompt.txt",
        "bad-antipattern-prompt.txt",
        "good-en-prompt.txt",
        "bad-en-prompt.txt",
        "weak-prompt.txt",
    ):
        if fixture not in ci:
            errors.append(f"ci.yml：未自测 scripts/fixtures/{fixture}")


def check_precommit_hook() -> None:
    """The pre-commit hook must ship, call the installed console script, and be packaged."""
    hooks = read(".pre-commit-hooks.yaml")
    if "entry: code-refactor-prompt-check --strict" not in hooks:
        errors.append(".pre-commit-hooks.yaml：entry 应调用已安装的 console script code-refactor-prompt-check --strict")
    if "language: python" not in hooks:
        errors.append(".pre-commit-hooks.yaml：应为 language: python（由 pyproject.toml 安装 console script）")
    if "pass_filenames: true" not in hooks:
        errors.append(".pre-commit-hooks.yaml：应设置 pass_filenames: true")
    if "files:" not in hooks:
        errors.append(".pre-commit-hooks.yaml：缺少 files 匹配规则")
    pyproject = read("pyproject.toml")
    if 'code-refactor-prompt-check = "check_prompt:main"' not in pyproject:
        errors.append("pyproject.toml：缺少 [project.scripts] code-refactor-prompt-check = \"check_prompt:main\"")
    if "py-modules" not in pyproject or "check_prompt" not in pyproject:
        errors.append("pyproject.toml：未声明 check_prompt 模块（py-modules / package-dir）")
    for workflow in (".github/workflows/ci.yml", ".github/workflows/release.yml"):
        text = read(workflow)
        if ".pre-commit-hooks.yaml" not in text:
            errors.append(f"{workflow}：发布打包未包含 .pre-commit-hooks.yaml")
        if "pyproject.toml" not in text:
            errors.append(f"{workflow}：发布打包未包含 pyproject.toml（pre-commit 安装依赖它）")


def check_action() -> None:
    """The composite GitHub Action must ship and call the checker with annotations."""
    rel = "action.yml"
    if not (ROOT / rel).is_file():
        errors.append(f"缺少 {rel}（PR 门禁）")
        return
    text = read(rel)
    if "using: composite" not in text:
        errors.append(f"{rel}：runs.using 应为 composite")
    if "scripts/check_prompt.py" not in text:
        errors.append(f"{rel}：未调用 scripts/check_prompt.py")
    if "--format github" not in text:
        errors.append(f"{rel}：未使用 --format github 注解输出")
    if "GITHUB_ACTION_PATH" not in text:
        errors.append(f"{rel}：应通过 GITHUB_ACTION_PATH 定位脚本")
    for marker in ("changed-only", "BASE_SHA", "--changed"):
        if marker not in text:
            errors.append(f"{rel}：缺少 changed-only 模式接线（{marker}）")
    for workflow in (".github/workflows/ci.yml", ".github/workflows/release.yml"):
        if "action.yml" not in read(workflow):
            errors.append(f"{workflow}：发布打包未包含 action.yml")


def check_link_workflow() -> None:
    """The scheduled online link check must exist and request every URL."""
    rel = ".github/workflows/link-check.yml"
    if not (ROOT / rel).is_file():
        errors.append(f"缺少 {rel}（sources.md 的在线巡检）")
        return
    text = read(rel)
    if "schedule:" not in text:
        errors.append(f"{rel}：缺少 schedule 触发器")
    if "check_sources.py --online" not in text:
        errors.append(f"{rel}：未运行 check_sources.py --online")


def main() -> int:
    check_required_files()
    version = check_frontmatter()
    check_version(version)
    check_version_refs(version)
    check_references_wired()
    check_counts()
    check_examples()
    check_test_counts()
    check_markdown_structure()
    check_ci_wiring()
    check_action()
    check_link_workflow()
    check_precommit_hook()
    check_copy()
    check_links()

    for warning in warnings:
        print(f"WARN: {warning}")
    if errors:
        print(f"FAILED: {len(errors)} problem(s) found")
        for item in errors:
            print(f"  - {item}")
        return 1
    print("OK: skill structure, frontmatter, version, references, examples, links and copy are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
