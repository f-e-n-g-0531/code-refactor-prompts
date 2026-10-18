# code-refactor-prompts

[![CI](https://github.com/f-e-n-g-0531/code-refactor-prompts/actions/workflows/ci.yml/badge.svg)](https://github.com/f-e-n-g-0531/code-refactor-prompts/actions/workflows/ci.yml)
[![Release](https://github.com/f-e-n-g-0531/code-refactor-prompts/actions/workflows/release.yml/badge.svg)](https://github.com/f-e-n-g-0531/code-refactor-prompts/releases)

[中文](README.md) | English

A reusable **DSH skill** that produces high-quality, behaviour-preserving, verifiable **code-refactoring prompts**.

It distils the "information density caps quality" methodology into ready-to-paste structured prompts: three tiers (A vague / B structured / C context + acceptance criteria), an eight-segment skeleton, 13 specialised variants, per-language guidance for 12 languages, and end-to-end workflows. Two quality gates keep it honest: behaviour-baseline (characterisation) tests and Guard Clauses. The samples are not decorative: 6 runnable examples (Python / Go / Rust / TypeScript / C# / SQL) are executed for real in CI, and the master templates plus the 12 specialised variants that carry a prompt block are audited in CI.

## Structure

```text
code-refactor-prompts/
├── SKILL.md                      main skill: principles, skeleton, tiers, default template
├── README.md                     Chinese README
├── README.en.md                  English README
├── CHANGELOG.md                  release history (SemVer)
├── LICENSE                       MIT
├── .gitignore
├── .pre-commit-hooks.yaml        pre-commit hook definition (batch check via console script)
├── pyproject.toml                packaging metadata (console script: code-refactor-prompt-check)
├── action.yml                    GitHub Action (PR gate + file-level annotations)
├── references/
│   ├── specialized-prompts.md    13 specialised prompt variants
│   ├── language-specific.md      per-language guidance (12 languages + a React section)
│   ├── workflows.md              end-to-end workflows (review / baseline / batches / repair)
│   ├── template-en.md            English master template (segments, acceptance, output format)
│   ├── checklists.md             delivery checklist (prompt / apply / verify / merge)
│   └── sources.md                19 sources
├── examples/
│   ├── java-order-calculator-strategy-c.md        strategy C walkthrough
│   ├── python-legacy-characterisation.md          executable: Python baseline + differential test
│   ├── go-legacy-order-total.md                   executable: Go baseline + differential test
│   ├── rust-legacy-order-total.md                 executable: Rust baseline + differential test
│   ├── typescript-legacy-characterisation.md      executable: TS runtime-equivalent typed refactor
│   ├── csharp-legacy-order-total.md               executable: C# exit-code assertions without a test framework
│   └── sql-legacy-report-equivalence.md           executable: SQL golden result set + differential check
├── scripts/
│   ├── check_prompt.py           structural self-check (segments / verifiability / language / anti-patterns / bilingual)
│   ├── check_sources.py          source-link check (offline syntax / online reachability)
│   ├── compose_prompt.py         compose a filled, self-checked prompt from a source file
│   ├── fixtures/                 good / bad fixtures and sample sources used by CI
│   └── tests/                    regression tests for the tooling (checker / composer / batch & hook / source links / validator)
└── .github/
    ├── workflows/
    │   ├── ci.yml                validate + template audit + self-test + execute examples (push to main / PR)
    │   ├── link-check.yml        weekly online source-link check
    │   └── release.yml           tag-driven automated release
    └── scripts/
        ├── validate_skill.py     structure, copy, markdown, version and test-count validation
        ├── audit_templates.py    graded audit: full checker for templates, acceptance anchor for variants
        ├── verify_examples.py    extract marked code from examples and run it
        └── release_notes.py      release notes from CHANGELOG
```

## Features

- **Three tiers**: pick A/B/C by risk; critical refactors always use "context + acceptance criteria".
- **Eight-segment skeleton**: role, context, code, hard constraints, goals, acceptance criteria, output format, guard clauses.
- **Verifiable equivalence**: replaces "keep behaviour unchanged" with a runnable test command or input → expected cases.
- **Guard clauses**: `NO_CODE_PROVIDED` when no code, `NO_REFACTORING_NEEDED` when nothing to fix.
- **Per-language guidance**: Java, Python, JS/TS, React, Go, Rust, C#, C++, SQL, Kotlin, Swift, Ruby, PHP.
- **End-to-end workflows**: review-first, legacy baseline, multi-file batching, iterative repair.
- **Batch checks and commit gating**: `check_prompt.py` accepts multiple files and directories (per-file PASS/FAIL plus a summary); `.pre-commit-hooks.yaml` lets pre-commit and CI gate on it directly.
- **PR gate (GitHub Actions)**: the root `action.yml` checks prompts in a pull request and annotates findings on the matching files via `--format github`; with `changed-only: true` it checks only the prompt files changed in that PR.
- **Tooling regression tests**: `scripts/tests/` covers the checker, composer (including tier C), `--fix` loop, source-link check, the 13-language matrix and the validator itself with 65 tests, run on every CI build.
- **Delivery checklist**: `references/checklists.md` walks from prompt authoring to merge.
- **One-command composition**: `scripts/compose_prompt.py --code <file>` builds a filled eight-segment prompt (Chinese or English, auto-detects 13 languages and their test commands); supplying both `--rule` (business rules) and `--case` (acceptance cases) produces a full tier-C prompt, and the result is refused unless it passes the shipped checker.
- **Bilingual self-check**: `scripts/check_prompt.py` validates the eight segments and verifiability in Chinese and English, checks that the code section contains code (or a paste placeholder) and that the acceptance command / cases live in the acceptance section, detects the prompt language and checks that the acceptance command matches it (e.g. Go requires `go test`), and flags anti-patterns such as "tweak the tests as well" or "rewrite the whole project". Adds `--strict` (warnings fail), `--skeleton` (print fill-in skeletons for missing segments) and `--fix` (append missing-segment skeletons to the file and re-check).
- **Executable examples**: 6 runnable examples are run in CI by `verify_examples.py` (`go test` / `python -m unittest` / `cargo test` / `node --test` / `dotnet run` / SQLite result-set comparison), so docs cannot drift from code.
- **Source-link checks**: `scripts/check_sources.py` validates `references/sources.md` offline for URL syntax and duplicates, and requests every URL with `--online`; CI runs the offline check on every push and a weekly `Link check` workflow catches rot.
- **Graded audit**: `audit_templates.py` runs the full checker over the default and English master templates, checks the 12 variants that carry a prompt block for an acceptance anchor and error-level anti-patterns, and checks the guard variant for its `NO_CODE_PROVIDED` / `NO_REFACTORING_NEEDED` markers (the quick-reference section is skipped).
- **English template**: `references/template-en.md` provides the eight-segment master template in English.
- **Anti-misuse**: "when to downgrade", a common-bad-prompt table, and output-format options.

## Install (DSH)

1. Put this repository into DSH's skills directory: `~/.dsh/skills/`
2. The directory must be named `code-refactor-prompts` and contain `SKILL.md`
3. DSH discovers and registers the skill automatically
4. The tooling needs Python 3.9+ (on Windows the interpreter is usually `python`, not `python3`)

## Usage

Ask the model to "refactor this code" or "give me a refactoring prompt". The skill triggers and returns a structured prompt with mandatory acceptance criteria. For English codebases use the [English master template](references/template-en.md).

## Compose a prompt

Run these commands from the skill repo root and replace `src/order.go` with your source file.

```bash
python3 scripts/compose_prompt.py --code src/order.go --project order-pricing \
    --pain "150-line Total function, magic numbers everywhere" \
    --rule "books 10% off, electronics 5% off, 2% off above 100" \
    --case "empty order -> 0" --case "book 100x1 -> 102.2" \
    --output-lang en --out prompt.txt
python3 scripts/check_prompt.py prompt.txt
```

Without `--rule` / `--case` the output is a tier-B prompt (rules and cases stay as placeholders); supplying both produces a full tier-C prompt (business rules in the context, concrete cases in the acceptance criteria); supplying only one fills that half and leaves the other as a placeholder. Language and default test command are auto-detected for Go / Python / Java / Rust / TypeScript / JavaScript / C# / Kotlin / Swift / Ruby / PHP / C++ / SQL. Composition self-checks the result and exits non-zero instead of emitting a prompt that would fail the checker.

## Delivery checklist

A good prompt is not enough if applying and verifying it go wrong. The four-stage checklist (before sending / before applying / after applying / before merging) lives in [references/checklists.md](references/checklists.md).

## Self-check a prompt

```bash
python3 scripts/check_prompt.py my-prompt.txt
python3 scripts/check_prompt.py my-prompt.txt --lang go       # force the language
python3 scripts/check_prompt.py my-prompt.txt --strict        # warnings fail (team gate)
python3 scripts/check_prompt.py my-prompt.txt --skeleton      # print skeletons for missing segments
python3 scripts/check_prompt.py my-prompt.txt --fix           # append skeletons to the file and re-check
python3 scripts/check_prompt.py --changed origin/main --strict # only prompts changed since the base
cat my-prompt.txt | python3 scripts/check_prompt.py -
```

It checks structure and known anti-patterns only (Chinese and English); semantic quality is still your call. CI self-tests the script with the good / bad fixtures, including a language-mismatch case, English anti-patterns, strict mode and the skeleton output.

Exit codes: `0` = pass, `1` = problems found, `2` = usage / input error (missing file, non-UTF-8 input, `--fix` with `--json`, ...). `--json` emits machine-readable output; batch mode adds per-file results and `skeleton`.

Windows / PowerShell: use single-line commands; read a Chinese prompt with `Get-Content -Raw -Encoding UTF8 my-prompt.txt | python scripts/check_prompt.py -`, or pass the file path directly; the interpreter may be `python` rather than `python3`.

## CI and pre-commit

Check a whole prompts directory (per-file PASS/FAIL plus a summary):

```bash
python3 scripts/check_prompt.py prompts/ --strict
```

Directories are scanned recursively for `*.prompt`, `*.prompt.md` and `*.prompt.txt` (override with `--include`); multiple files and directories can be combined, while `--fix` cannot be combined with `--json` or `--skeleton`.

pre-commit (for a consuming repository; `rev` must point at a published tag). Install and enable the hook first:

```bash
pip install pre-commit
pre-commit install
```

Then in `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/f-e-n-g-0531/code-refactor-prompts
    rev: v1.13.0
    hooks:
      - id: code-refactor-prompt-check
```

The repo exposes a `code-refactor-prompt-check` console script via `pyproject.toml`, so pre-commit's `language: python` installs the hook and staged files matching `\.prompt(\.(md|txt))?$` are checked in `--strict` mode; any failure blocks the commit. To try the hook locally without publishing a tag: `pre-commit try-repo . --ref HEAD --files my.prompt.txt`.

## GitHub Actions (PR gate)

The root `action.yml` runs the checker in a pull request and annotates findings on the matching files with `--format github`:

```yaml
name: Prompts
on: [pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0        # changed-only needs the full history
      - uses: f-e-n-g-0531/code-refactor-prompts@v1.13.0
        with:
          changed-only: true     # only prompts changed in this PR; otherwise files is used (repo root by default)
          strict: true           # warnings fail too
```

Requires a Linux / macOS runner (bash + python3). Local equivalent: `python3 scripts/check_prompt.py --changed origin/main --format github --strict`.

## CI and release

- **CI** ([.github/workflows/ci.yml](.github/workflows/ci.yml)): validates skill structure, frontmatter, version alignment, references, Markdown structure (duplicate headings) and test counts, links and copy; audits master templates and specialised variants; self-tests the prompt checker; runs the tooling regression suite; checks source links offline (`check_sources.py`); self-tests GitHub annotation output (`--format github`); installs and tests the packaged pre-commit console script; runs the hook end to end with `pre-commit try-repo` (good prompt passes, bad prompt blocks); sets up Node 24 and executes all 6 runnable examples (go test / python unittest / cargo test / node --test / dotnet run / SQLite comparison); dry-runs packaging.
- **Link check** ([.github/workflows/link-check.yml](.github/workflows/link-check.yml)): every Monday 03:17 UTC (or manually) it requests every URL in `references/sources.md` and fails the run when a link is broken.
- **Release** ([.github/workflows/release.yml](.github/workflows/release.yml)): on a `v*` tag it validates, audits templates, executes the examples, builds `zip` / `tar.gz` / `SHA256SUMS`, and publishes a GitHub Release.

Release steps: update `CHANGELOG.md`, `metadata.version` and the `pyproject.toml` version (the validator keeps them in sync with `rev: vX.Y.Z` in both READMEs and the hook comment) → push `main` → `git tag -a vX.Y.Z -m "..." && git push origin vX.Y.Z`.

## License

[MIT](LICENSE)
