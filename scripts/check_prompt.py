#!/usr/bin/env python3
"""Structural self-check for a code-refactoring prompt produced with this skill.

This is a heuristic *structure* check, not a judgement of semantic quality.
Both Chinese and English prompts are supported.

Usage:
    python3 scripts/check_prompt.py <file|dir|...> [--json] [--format text|github]
                                    [--lang auto|go|rust|python|...] [--strict]
                                    [--skeleton] [--fix] [--include PATTERNS]

Multiple paths are supported. A directory is scanned recursively for
*.prompt / *.prompt.md / *.prompt.txt (override with --include); this is what
the bundled pre-commit hook runs on the files passed by pre-commit.

Checks:
  - the eight required segments are present (Chinese or English headings);
  - the code section contains a fenced code block (or a {paste code} placeholder);
  - acceptance criteria is verifiable (test command or "input -> expected" cases),
    written inside the acceptance section;
  - the test command matches the language of the prompt (auto-detected from the
    fenced code block, or forced with --lang);
  - "keep behaviour unchanged" is backed by verifiable checks;
  - hard constraints mention behaviour / API / signature compatibility;
  - known anti-patterns are flagged with a concrete fix (Chinese and English).

Options:
    --format     text (default) or github (workflow-command annotations; cannot be
                 combined with --json / --fix)
    --strict     treat warnings as failures (CI gating)
    --skeleton   print fill-in skeletons for the segments that are missing
    --fix        append fill-in skeletons for missing segments to the file, then re-check
    --include    comma-separated glob patterns for directory scans
                 (default: *.prompt,*.prompt.md,*.prompt.txt)

Exit codes: 0 = pass, 1 = problems found, 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SEGMENTS = [
    ("role", "角色", r"角色|你是|作为.{0,12}(工程师|专家|开发)|" r"you are|act as|senior .{0,30}(engineer|developer|architect)"),
    ("context", "上下文", r"上下文|背景|\bcontext\b|\bbackground\b"),
    ("code", "待重构代码", r"待重构代码|粘贴代码|代码如下|\x60\x60\x60|" r"code to refactor|paste (the |your )?code"),
    ("constraints", "硬约束", r"硬约束|约束|" r"hard constraints?|must not|do not change"),
    ("goals", "重构目标", r"重构目标|重构要求|目标|" r"refactoring goals?|\bgoal\b|\bgoals\b"),
    ("acceptance", "验收标准", r"验收标准|验收|" r"acceptance criteria|acceptance|test command"),
    ("output", "输出格式", r"输出格式|" r"output format"),
    ("guard", "守卫", r"前置判断|NO_CODE_PROVIDED|NO_REFACTORING_NEEDED|守卫|" r"guard clauses?|no (code|refactoring) provided"),
]

TEST_COMMAND = re.compile(
    r"(pytest|unittest|npm\s+(run\s+)?test|yarn\s+test|pnpm\s+test|mvn\s+(test|verify)|"
    r"gradle(w)?\s+test|go\s+test|cargo\s+test|dotnet\s+test|rspec|phpunit|ctest|"
    r"swift\s+test|jest|vitest|junit|tox|nox|node\s+--test)",
    re.I,
)
VAGUE = re.compile(
    r"(保持|维持).{0,6}行为.{0,6}不变|行为(完全)?不变|"
    r"keep(ing)? (the )?behaviou?r (unchanged|identical)",
    re.I,
)
BEHAVIOUR_CONSTRAINT = re.compile(
    r"(行为|API|签名|异常|返回值|接口).{0,20}(一致|不变|兼容|保持)|"
    r"(一致|不变|兼容|保持).{0,20}(行为|API|签名|异常|返回值|接口)|"
    r"behaviou?r.{0,30}(identical|unchanged|preserved)|"
    r"(do not|don't) change.{0,20}(behaviou?r|public api|return values?|exception)",
    re.I,
)
VERIFIABLE_HINT = re.compile(r"期望|\bexpected\b|\bexpectation", re.I)
CODE_HEADING = re.compile(
    r"【待重构代码[^】]*】|\[CODE TO REFACTOR[^\]]*\]|^#{1,4}\s*(?:code to refactor|待重构代码)",
    re.I | re.M,
)
ACCEPTANCE_HEADING = re.compile(
    r"【验收标准[^】]*】|\[ACCEPTANCE[^\]]*\]|^#{1,4}\s*(?:acceptance criteria|验收标准)",
    re.I | re.M,
)
SEGMENT_BOUNDARY = re.compile(r"\n(?=\s*(?:【[^】\n]+】|\[[A-Z][^\]\n]*\]|#{1,4}\s))")
FENCED_BLOCK = re.compile(r"```[^\n]*\n(.*?)```", re.S)
CODE_PLACEHOLDER = re.compile(r"\{[^}\n]{0,100}(?:代码|code|粘贴|paste)[^}\n]{0,100}\}", re.I)

# Fence language -> canonical language.
LANGUAGE_FENCES = {
    "go": "go",
    "golang": "go",
    "rust": "rust",
    "python": "python",
    "py": "python",
    "java": "java",
    "ts": "typescript",
    "typescript": "typescript",
    "js": "javascript",
    "javascript": "javascript",
    "cs": "csharp",
    "csharp": "csharp",
    "c#": "csharp",
    "kotlin": "kotlin",
    "kt": "kotlin",
    "swift": "swift",
    "ruby": "ruby",
    "rb": "ruby",
    "php": "php",
    "sql": "sql",
    "cpp": "cpp",
    "c++": "cpp",
}

LANGUAGE_LABELS = {
    "go": "Go",
    "rust": "Rust",
    "python": "Python",
    "java": "Java",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "csharp": "C#",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "ruby": "Ruby",
    "php": "PHP",
    "sql": "SQL",
    "cpp": "C++",
}

# What a runnable acceptance command looks like for each language.
LANGUAGE_TEST_COMMANDS = {
    "go": r"go\s+test",
    "rust": r"cargo\s+test",
    "python": r"pytest|unittest|python3?\s+-m\s+(pytest|unittest)|tox|nox",
    "java": r"mvn\s+(test|verify)|\.?/?gradlew?\s+test|gradle\s+test|junit",
    "typescript": r"(npm|yarn|pnpm)\s+(run\s+)?test|jest|vitest|node\s+--test|tsc",
    "javascript": r"(npm|yarn|pnpm)\s+(run\s+)?test|jest|vitest|node\s+--test",
    "csharp": r"dotnet\s+test|dotnet\s+run|nunit|xunit",
    "kotlin": r"\.?/?gradlew?\s+test|gradle\s+test|kotlin\s+test",
    "swift": r"swift\s+test",
    "ruby": r"rspec|rake\s+test",
    "php": r"phpunit|composer\s+test",
    "cpp": r"ctest|gtest|cmake\s+--build",
    "sql": r"(EXPLAIN|执行|运行).{0,10}(查询|SQL)|期望(结果|行)|结果集",
}

LANGUAGE_EXPECTED_COMMAND = {
    "go": "go test",
    "rust": "cargo test",
    "python": "pytest / python -m unittest",
    "java": "mvn test / gradle test",
    "typescript": "npm test / node --test",
    "javascript": "npm test / node --test",
    "csharp": "dotnet test / dotnet run",
    "kotlin": "gradle test",
    "swift": "swift test",
    "ruby": "rspec",
    "php": "phpunit",
    "cpp": "ctest",
    "sql": "EXPLAIN / 期望结果集",
}

# (code, regex, severity, message)
ANTI_PATTERNS = [
    (
        "test-tampering",
        re.compile(r"顺便.{0,8}(把)?测试.{0,8}(改|删)|(also|while you.re at it|feel free to).{0,25}(change|update|modify|adjust).{0,15}tests?", re.I),
        "error",
        "「顺便改测试」会掩盖行为变更：测试只允许新增基线用例，不允许改既有断言。"
        " Do not change existing tests to match the code; add baseline cases only.",
    ),
    (
        "boil-the-ocean",
        re.compile(r"(整个|全部|全量|所有).{0,6}(项目|代码库|仓库).{0,6}(重构|重写)|rewrite (the )?(whole|entire) (project|codebase|repo)", re.I),
        "error",
        "整体重写无法评审与定位失败：按 references/workflows.md 工作流 3 分批，每批独立验收。"
        " Split into batches with separate acceptance per batch.",
    ),
    (
        "appeal-to-best-practice",
        re.compile(r"(用你|按你|用).{0,8}(熟悉|喜欢)?.{0,4}最佳实践.{0,6}(重写|重构|改写)|(use|apply|follow) (your )?(favorite |favourite )?best practices?", re.I),
        "error",
        "「最佳实践」是无依据架构改动的入口：限定只改结构不改行为，并禁止新增依赖。"
        " Constrain the change to structure only and forbid new dependencies.",
    ),
    (
        "unmeasurable-goal",
        re.compile(r"(性能|质量|可读性|可维护性)(更好|提升|更高|更强|增强)|(more readable|cleaner|faster|more maintainable|higher quality|better performance)", re.I),
        "error",
        "空泛的改进目标不可验收：改为可测量指标（基准命令、阈值、圈复杂度上限）或删除。"
        " Replace with a measurable metric (benchmark command, threshold, complexity cap).",
    ),
    (
        "scope-creep",
        re.compile(r"(顺手|顺便).{0,10}(重构|优化|清理)|while you.re at it|also clean up", re.I),
        "warning",
        "顺手改动会扩大评审面：把范围外改动单列，不放进本次重构。"
        " List out-of-scope changes separately.",
    ),
    (
        "behaviour-change-allowed",
        re.compile(r"(允许|可以|同意).{0,8}(行为|接口|API).{0,8}(变化|改变|调整)|(behaviou?r|public api|api).{0,20}(may|can|is allowed to) (change|differ)", re.I),
        "warning",
        "允许行为变化就不是重构：走需求 / 设计变更流程，本技能「行为等价」前提不成立。"
        " Allowing behaviour change means it is not a refactor.",
    ),
    (
        "hedged-constraint",
        re.compile(r"(大概|尽量|尽可能|差不多|基本上).{0,10}(保持|不变|一致)|(try to|roughly|more or less|as much as possible).{0,15}(keep|preserve|maintain)", re.I),
        "warning",
        "模棱两可的约束不可验收：写成明确的测试命令或用例。"
        " Replace with an explicit test command or cases.",
    ),
]

KNOWN_LANGUAGES = sorted(LANGUAGE_TEST_COMMANDS)

SKELETONS_ZH = {
    "role": "【角色】\n你是资深 {语言/框架} 工程师，专注在不改变行为的前提下做重构。",
    "context": "【上下文】\n- 项目/模块：{名称}\n- 语言与框架：{语言 + 版本 + 框架}\n- 这段代码做什么、已知痛点：{业务背景}",
    "code": "【待重构代码】\n{粘贴代码，使用 fenced code block}",
    "constraints": "【硬约束（不可违反）】\n1. 外部行为 100% 一致：不改公开 API、返回值、抛出的异常类型；\n2. 不新增第三方依赖；不弱化错误处理、日志、安全校验；\n3. 遵循项目现有编码规范与命名风格。",
    "goals": "【重构目标】\n0. 先为现有行为生成/补齐「行为基线测试」；\n1. {消除重复 / 降低圈复杂度 / 拆分长函数 / 提取子方法}；\n2. 用具名常量替换魔法数字。",
    "acceptance": "【验收标准（必填，可验证）】\n- 测试命令：{go test ./... / pytest / cargo test / npm test}\n- 用例：{给定输入 → 期望输出}\n- 若无法运行测试：给出等价验证步骤（命令 + 预期输出）。",
    "output": "【输出格式】\n1. 问题清单：问题 → 严重度 → 位置；\n2. 统一 diff（声明基线文件）或完整文件；\n3. 改动清单表格；\n4. 风险提示。",
    "guard": "【前置判断】\n- 未提供代码：输出 NO_CODE_PROVIDED 并索取代码；\n- 代码无明显可改进处：输出 NO_REFACTORING_NEEDED 并说明理由，不要硬改。",
}

SKELETONS_EN = {
    "role": "You are a senior {language/framework} engineer specialising in behaviour-preserving refactoring.",
    "context": "[CONTEXT]\n- Project/module: {name}\n- Language and framework: {language + version + framework}\n- What this code does / known pain points: {business context}",
    "code": "[CODE TO REFACTOR]\n{paste the code in a fenced block}",
    "constraints": "[HARD CONSTRAINTS]\n1. External behaviour is 100% identical: do not change public API, return values, or exception types;\n2. No new third-party dependencies; do not weaken error handling, logging, or security checks;\n3. Follow the existing code style and naming conventions.",
    "goals": "[REFACTORING GOALS]\n0. First generate behaviour-baseline tests that capture current behaviour;\n1. {remove duplication / reduce complexity / split long functions};\n2. Replace magic numbers with named constants.",
    "acceptance": "[ACCEPTANCE CRITERIA]\n- Test command: {go test ./... / pytest / cargo test / npm test}\n- Cases: {given input -> expected output}\n- If tests cannot run: provide equivalent verification steps.",
    "output": "[OUTPUT FORMAT]\n1. Problem list: problem -> severity -> location;\n2. Unified diff (state the baseline) or full files;\n3. Change table; 4. Risk notes.",
    "guard": "[GUARD CLAUSES]\n- No code provided: output NO_CODE_PROVIDED and ask for it;\n- Nothing worth refactoring: output NO_REFACTORING_NEEDED with reasons.",
}


def error(code: str, message: str) -> dict:
    return {"code": code, "message": message}


def detect_languages(text: str) -> list[str]:
    languages: list[str] = []
    for fence in re.findall(r"\x60\x60\x60([A-Za-z0-9#+_.-]+)", text):
        language = LANGUAGE_FENCES.get(fence.lower())
        if language and language not in languages:
            languages.append(language)
    return languages


def looks_english(text: str) -> bool:
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    letters = len(re.findall(r"[A-Za-z]", text))
    return cjk == 0 and letters > 20


def segment_body(text: str, heading: re.Pattern) -> str | None:
    """Return the text after a segment heading, up to the next segment heading."""
    match = heading.search(text)
    if not match:
        return None
    rest = text[match.end() :]
    boundary = SEGMENT_BOUNDARY.search(rest)
    return rest[: boundary.start()] if boundary else rest


def check_section_content(text: str, errors: list[dict], warnings: list[dict]) -> None:
    """The code section must contain code (or a placeholder), not just a heading."""
    code_body = segment_body(text, CODE_HEADING)
    if code_body is not None:
        has_code = bool(FENCED_BLOCK.search(code_body))
        has_placeholder = bool(CODE_PLACEHOLDER.search(code_body))
        if not has_code and not has_placeholder:
            errors.append(
                error(
                    "empty-code-section",
                    "【待重构代码】段落里没有代码：请粘贴 fenced code block，或保留 {粘贴代码} 占位符。"
                    " The code section must contain a fenced code block or placeholder.",
                )
            )

    acceptance_body = segment_body(text, ACCEPTANCE_HEADING)
    if acceptance_body is not None:
        local = bool(
            TEST_COMMAND.search(acceptance_body)
            or VERIFIABLE_HINT.search(acceptance_body)
            or (acceptance_body.count("→") + acceptance_body.count("->")) >= 2
        )
        if not local:
            warnings.append(
                error(
                    "acceptance-section-unverifiable",
                    "【验收标准】段落内没有测试命令或用例：把命令 / 用例直接写进验收标准段，不要只写「见上文」。"
                    " Put the command / cases inside the acceptance section.",
                )
            )


def check_language(text: str, languages: list[str], errors: list[dict], warnings: list[dict]) -> None:
    if not languages:
        return
    labels = " / ".join(LANGUAGE_LABELS[lang] for lang in languages)
    matched = [lang for lang in languages if re.search(LANGUAGE_TEST_COMMANDS[lang], text, re.I)]
    if matched:
        return

    generic = TEST_COMMAND.search(text)
    if generic:
        expected = "、".join(LANGUAGE_EXPECTED_COMMAND.get(lang, "对应测试命令") for lang in languages)
        errors.append(
            error(
                "language-mismatch",
                f"验收命令与语言不匹配：语言为 {labels}，验收里只有「{generic.group(0)}」；"
                f"应改用 {expected} 之一。 Test command does not match the prompt language.",
            )
        )
    else:
        warnings.append(
            error(
                "no-test-command",
                f"未声明可运行测试命令（语言：{labels}）：建议写明对应测试命令，"
                f"而不是只靠「输入 → 期望」的手工核对。 No runnable test command declared.",
            )
        )


def check(text: str, explicit_language: str = "auto", strict: bool = False) -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []

    missing = [label for _key, label, pattern in SEGMENTS if not re.search(pattern, text, re.S | re.I)]
    for label in missing:
        errors.append(error("missing-segment", f"缺少段落：{label}"))

    arrows = text.count("→") + text.count("->")
    verifiable = bool(TEST_COMMAND.search(text) or VERIFIABLE_HINT.search(text) or arrows >= 2)
    if not verifiable:
        errors.append(
            error("unverifiable-acceptance", "验收标准不可验证：未发现测试命令，也没有「输入 → 期望输出」用例")
        )

    if VAGUE.search(text) and not verifiable:
        errors.append(
            error("vague-equivalence", "出现「保持行为不变」但没有可验证的测试命令或用例，无法验收")
        )

    if not BEHAVIOUR_CONSTRAINT.search(text):
        warnings.append(
            error("no-behaviour-constraint", "硬约束未显式约束行为 / API / 签名 / 异常兼容性")
        )

    if not re.search(r"diff|完整文件|patch", text, re.I):
        warnings.append(
            error("no-output-format", "输出格式未约定 unified diff / 完整文件 / patch")
        )

    check_section_content(text, errors, warnings)

    if explicit_language == "auto":
        languages = detect_languages(text)
        language_source = "auto"
    else:
        languages = [explicit_language]
        language_source = "explicit"
    check_language(text, languages, errors, warnings)

    for code, pattern, severity, message in ANTI_PATTERNS:
        if pattern.search(text):
            target = errors if severity == "error" else warnings
            target.append(error(code, message))

    skeleton = [
        {"segment": key, "label": label}
        for key, label, _pattern in SEGMENTS
        if label in missing
    ]

    if strict:
        errors = errors + [error("strict-" + item["code"], item["message"]) for item in warnings]
        warnings = []

    return {
        "pass": not errors,
        "errors": errors,
        "warnings": warnings,
        "missing_segments": missing,
        "verifiable": verifiable,
        "languages": languages,
        "language_source": language_source,
        "strict": strict,
        "skeleton": skeleton,
    }


def skeleton_blocks(keys: list[str], english: bool) -> list[str]:
    table = SKELETONS_EN if english else SKELETONS_ZH
    return [table[key] for key in keys if key in table]


DEFAULT_INCLUDE_PATTERNS = ("*.prompt", "*.prompt.md", "*.prompt.txt")
GITHUB_ESCAPE = str.maketrans({"%": "%25", "\r": "%0D", "\n": "%0A"})


def github_annotation(level: str, path: str | None, message: str) -> str:
    """Format a GitHub Actions workflow command (error / warning / notice)."""
    if path is None:
        return f"::{level}::{message.translate(GITHUB_ESCAPE)}"
    clean = path.replace("\\", "/").translate(GITHUB_ESCAPE)
    return f"::{level} file={clean}::{message.translate(GITHUB_ESCAPE)}"


def read_text_file(path: Path) -> str:
    """Read UTF-8 text (BOM tolerated) or raise ValueError with a usable message."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path} is not valid UTF-8; save the prompt as UTF-8") from exc


def build_skeleton_blocks(text: str) -> list[str]:
    result = check(text)
    keys = [item["segment"] for item in result["skeleton"]]
    return skeleton_blocks(keys, looks_english(text))


def apply_fix_to_file(path: Path, language: str, strict: bool) -> dict:
    """Append missing-segment skeletons to path, then return the re-checked result."""
    text = read_text_file(path)
    result = check(text, explicit_language=language, strict=strict)
    keys = [item["segment"] for item in result["skeleton"]]
    if keys:
        english = looks_english(text)
        note = (
            "<!-- check_prompt.py --fix: missing-segment skeletons; move them into place and fill them in -->"
            if english
            else "<!-- check_prompt.py --fix: 以下为缺失段落骨架，请移动到对应位置并补全 -->"
        )
        blocks = skeleton_blocks(keys, english)
        path.write_text(
            text.rstrip() + "\n\n" + note + "\n\n" + "\n\n".join(blocks) + "\n",
            encoding="utf-8",
        )
        print(f"--fix: appended {len(blocks)} missing segment skeleton(s) to {path}", file=sys.stderr)
        text = path.read_text(encoding="utf-8")
        result = check(text, explicit_language=language, strict=strict)
    return result


def print_result(result: dict, blocks: list[str] | None = None) -> None:
    if result["pass"]:
        note = ""
        if result["languages"]:
            note = " [" + " / ".join(LANGUAGE_LABELS[lang] for lang in result["languages"]) + "]"
        print(f"PASS: 8 segments present, acceptance criteria verifiable{note}")
    else:
        print(f"FAIL: {len(result['errors'])} problem(s) found")
        for item in result["errors"]:
            print(f"  - {item['message']}")
    for warning in result["warnings"]:
        print(f"  warn: {warning['message']}")
    if blocks:
        print("\n--- 缺失段落骨架 / missing-segment skeletons ---")
        for block in blocks:
            print()
            print(block)


def collect_sources(sources: list[str], include: str) -> tuple[list[Path], list[str]]:
    patterns = [item.strip() for item in include.split(",") if item.strip()]
    files: list[Path] = []
    missing: list[str] = []
    seen: set[Path] = set()
    for source in sources:
        candidate = Path(source)
        if candidate.is_dir():
            found: list[Path] = []
            for pattern in patterns:
                found.extend(sorted(candidate.rglob(pattern)))
            if not found:
                missing.append(f"{source}（目录下没有匹配 {', '.join(patterns)} 的文件）")
            for item in found:
                key = item.resolve()
                if key not in seen:
                    seen.add(key)
                    files.append(item)
        elif candidate.is_file():
            key = candidate.resolve()
            if key not in seen:
                seen.add(key)
                files.append(candidate)
        elif source == "-":
            missing.append("-（stdin 只能单独使用 / stdin can only be used alone）")
        else:
            missing.append(source)
    return files, missing


def run_batch(
    sources: list[str],
    *,
    include: str,
    language: str,
    strict: bool,
    fix: bool,
    skeleton_output: bool,
    as_json: bool,
    github_output: bool = False,
) -> int:
    files, missing = collect_sources(sources, include)
    if missing:
        for item in missing:
            print(f"cannot check: {item}", file=sys.stderr)
        return 2

    results: list[dict] = []
    passed = 0
    failed = 0
    for file in files:
        try:
            if fix:
                result = apply_fix_to_file(file, language, strict)
                text = read_text_file(file)
            else:
                text = read_text_file(file)
                result = check(text, explicit_language=language, strict=strict)
        except ValueError as exc:
            print(f"cannot check: {exc}", file=sys.stderr)
            return 2
        blocks = build_skeleton_blocks(text) if (skeleton_output and result["skeleton"]) else []
        results.append(
            {
                "file": str(file),
                "pass": result["pass"],
                "errors": result["errors"],
                "warnings": result["warnings"],
                "missing_segments": result["missing_segments"],
                "languages": result["languages"],
                "language_source": result["language_source"],
                "verifiable": result["verifiable"],
                "skeleton": blocks,
            }
        )
        if result["pass"]:
            passed += 1
        else:
            failed += 1
        if not as_json:
            if github_output:
                for item in result["errors"]:
                    print(github_annotation("error", str(file), item["message"]))
                for warning in result["warnings"]:
                    print(github_annotation("warning", str(file), warning["message"]))
            else:
                print(f"{'PASS' if result['pass'] else 'FAIL'} {file}")
                if not result["pass"]:
                    for item in result["errors"]:
                        print(f"  - {item['message']}")
                for warning in result["warnings"]:
                    print(f"  warn: {warning['message']}")
            for block in blocks:
                print()
                print(block)

    if as_json:
        print(
            json.dumps(
                {"pass": failed == 0, "passed": passed, "failed": failed, "results": results},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"\n{passed} passed, {failed} failed ({len(files)} file(s) checked)")

    return 0 if failed == 0 else 1


def main() -> int:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Structural self-check for refactoring prompts.")
    parser.add_argument("sources", nargs="+", help="prompt files, '-' for stdin, or directories to scan")
    parser.add_argument(
        "--include",
        default=",".join(DEFAULT_INCLUDE_PATTERNS),
        help="comma-separated glob patterns for directory scans",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--format",
        choices=["text", "github"],
        default="text",
        help="output format: text (default) or github (workflow-command annotations)",
    )
    parser.add_argument(
        "--lang",
        default="auto",
        metavar="LANG",
        help="force the prompt language (default: auto-detect from fenced code); "
        "one of: auto, " + ", ".join(KNOWN_LANGUAGES),
    )
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    parser.add_argument("--skeleton", action="store_true", help="print fill-in skeletons for missing segments")
    parser.add_argument("--fix", action="store_true", help="append missing-segment skeletons to the file and re-check")
    args = parser.parse_args()

    if args.fix and (args.json or args.skeleton):
        print("--fix cannot be combined with --json or --skeleton", file=sys.stderr)
        return 2
    if args.format == "github" and args.json:
        print("--format github cannot be combined with --json", file=sys.stderr)
        return 2
    if args.format == "github" and args.fix:
        print("--format github cannot be combined with --fix", file=sys.stderr)
        return 2

    language = args.lang.lower()
    if language != "auto" and language not in LANGUAGE_TEST_COMMANDS:
        print(
            f"unknown --lang {args.lang!r}; expected auto or one of: {', '.join(KNOWN_LANGUAGES)}",
            file=sys.stderr,
        )
        return 2

    sources = args.sources
    if "-" in sources and len(sources) > 1:
        print("stdin ('-') cannot be combined with other sources", file=sys.stderr)
        return 2

    batch = len(sources) > 1 or any(Path(source).is_dir() for source in sources)
    if batch:
        return run_batch(
            sources,
            include=args.include,
            language=language,
            strict=args.strict,
            fix=args.fix,
            skeleton_output=args.skeleton,
            as_json=args.json,
            github_output=args.format == "github",
        )

    source = sources[0]
    try:
        if source == "-":
            text = sys.stdin.read()
        else:
            candidate = Path(source)
            if not candidate.is_file():
                print(f"file not found: {source}", file=sys.stderr)
                return 2
            text = read_text_file(candidate)
    except (ValueError, UnicodeDecodeError) as exc:
        print(f"cannot read prompt: {exc}", file=sys.stderr)
        return 2

    if args.fix:
        if source == "-":
            print("--fix needs a file path (not stdin)", file=sys.stderr)
            return 2
        result = apply_fix_to_file(Path(source), language, args.strict)
        if result["pass"]:
            print("PASS after fix: 8 segments present, acceptance criteria verifiable")
        else:
            print(f"FAIL after fix: {len(result['errors'])} problem(s) found")
            for item in result["errors"]:
                print(f"  - {item['message']}")
        for warning in result["warnings"]:
            print(f"  warn: {warning['message']}")
        return 0 if result["pass"] else 1

    result = check(text, explicit_language=language, strict=args.strict)
    blocks = build_skeleton_blocks(text) if args.skeleton else []

    if args.json:
        payload = dict(result)
        payload["skeleton"] = blocks
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.format == "github":
        label = None if source == "-" else source
        for item in result["errors"]:
            print(github_annotation("error", label, item["message"]))
        for item in result["warnings"]:
            print(github_annotation("warning", label, item["message"]))
        print(
            f"{len(result['errors'])} error(s), {len(result['warnings'])} warning(s) in "
            f"{'(stdin)' if source == '-' else source}"
        )
    else:
        print_result(result, blocks)
        if args.skeleton and not blocks:
            print("\nno missing segments to add.")

    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
