# code-refactor-prompts

[![CI](https://github.com/f-e-n-g-0531/code-refactor-prompts/actions/workflows/ci.yml/badge.svg)](https://github.com/f-e-n-g-0531/code-refactor-prompts/actions/workflows/ci.yml)
[![Release](https://github.com/f-e-n-g-0531/code-refactor-prompts/actions/workflows/release.yml/badge.svg)](https://github.com/f-e-n-g-0531/code-refactor-prompts/releases)

[中文](README.md) | English

A reusable **DSH skill** that produces high-quality, behaviour-preserving, verifiable **code-refactoring prompts**.

It distils the "information density caps quality" methodology into ready-to-paste structured prompts: three tiers (A vague / B structured / C context + acceptance criteria), an eight-segment skeleton, 13 specialised variants, per-language guidance for 12 languages, and end-to-end workflows. Two quality gates keep it honest: behaviour-baseline (characterisation) tests and Guard Clauses.

## Structure

```text
code-refactor-prompts/
├── SKILL.md                      main skill: principles, skeleton, tiers, default template
├── README.md                     Chinese README
├── README.en.md                  English README
├── CHANGELOG.md                  release history (SemVer)
├── LICENSE                       MIT
├── .gitignore
├── references/
│   ├── specialized-prompts.md    13 specialised prompt variants
│   ├── language-specific.md      per-language guidance (12 languages)
│   ├── workflows.md              end-to-end workflows (review / baseline / batches / repair)
│   └── sources.md                19 sources
├── examples/
│   ├── java-order-calculator-strategy-c.md     strategy C walkthrough
│   ├── python-legacy-characterisation.md       legacy Python baseline
│   └── go-legacy-order-total.md                legacy Go baseline + differential test
├── scripts/
│   ├── check_prompt.py           structural self-check for generated prompts
│   └── fixtures/                 good / bad prompt fixtures used by CI
└── .github/                      CI and tag-driven release automation
```

## Features

- **Three tiers**: pick A/B/C by risk; critical refactors always use "context + acceptance criteria".
- **Eight-segment skeleton**: role, context, code, hard constraints, goals, acceptance criteria, output format, guard clauses.
- **Verifiable equivalence**: replaces "keep behaviour unchanged" with a runnable test command or input → expected cases.
- **Guard clauses**: `NO_CODE_PROVIDED` when no code, `NO_REFACTORING_NEEDED` when nothing to fix.
- **Per-language guidance**: Java, Python, JS/TS, React, Go, Rust, C#, C++, SQL, Kotlin, Swift, Ruby, PHP.
- **End-to-end workflows**: review-first, legacy baseline, multi-file batching, iterative repair.
- **Prompt self-check**: `scripts/check_prompt.py` lints a generated prompt for the eight segments and verifiable acceptance.
- **Anti-misuse**: "when to downgrade", a common-bad-prompt table, and output-format options.

## Install (DSH)

1. Put this repository into DSH's skills directory: `~/.dsh/skills/`
2. The directory must be named `code-refactor-prompts` and contain `SKILL.md`
3. DSH discovers and registers the skill automatically

## Usage

Ask the model to "refactor this code" or "give me a refactoring prompt". The skill triggers and returns a structured prompt with mandatory acceptance criteria.

## Self-check a prompt

```bash
python3 scripts/check_prompt.py my-prompt.txt
cat my-prompt.txt | python3 scripts/check_prompt.py -
```

It checks structure only (segments, verifiable acceptance, guard clauses); semantic quality is still your call.

## CI and release

- **CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)): validates skill structure, frontmatter, version alignment, references, links and copy; self-tests the prompt checker; dry-runs packaging.
- **Release** ([`.github/workflows/release.yml`](.github/workflows/release.yml)): on a `v*` tag it validates, builds `zip` / `tar.gz` / `SHA256SUMS`, and publishes a GitHub Release.

Release steps: update `CHANGELOG.md` and `metadata.version` → push `main` → `git tag -a vX.Y.Z -m "..." && git push origin vX.Y.Z`.

## License

[MIT](LICENSE)
