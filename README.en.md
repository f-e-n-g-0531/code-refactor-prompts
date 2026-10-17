# code-refactor-prompts

[![CI](https://github.com/f-e-n-g-0531/code-refactor-prompts/actions/workflows/ci.yml/badge.svg)](https://github.com/f-e-n-g-0531/code-refactor-prompts/actions/workflows/ci.yml)
[![Release](https://github.com/f-e-n-g-0531/code-refactor-prompts/actions/workflows/release.yml/badge.svg)](https://github.com/f-e-n-g-0531/code-refactor-prompts/releases)

[中文](README.md) | English

A reusable **DSH skill** that produces high-quality, behaviour-preserving, verifiable **code-refactoring prompts**.

It distils the "information density caps quality" methodology into ready-to-paste structured prompts: three tiers (A vague / B structured / C context + acceptance criteria), an eight-segment skeleton, 13 specialised variants, per-language guidance for 12 languages, and end-to-end workflows. Two quality gates keep it honest: behaviour-baseline (characterisation) tests and Guard Clauses. The samples are not decorative: the Python / Go / Rust / TypeScript / C# examples are executed for real in CI, and the master templates are audited by the same prompt checker.

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
│   ├── template-en.md            English master template (segments, acceptance, output format)
│   └── sources.md                19 sources
├── examples/
│   ├── java-order-calculator-strategy-c.md        strategy C walkthrough
│   ├── python-legacy-characterisation.md          executable: Python baseline + differential test
│   ├── go-legacy-order-total.md                   executable: Go baseline + differential test
│   ├── rust-legacy-order-total.md                 executable: Rust baseline + differential test
│   ├── typescript-legacy-characterisation.md      executable: TS runtime-equivalent typed refactor
│   └── csharp-legacy-order-total.md               executable: C# exit-code assertions without a test framework
├── scripts/
│   ├── check_prompt.py           structural self-check (segments / verifiability / language / anti-patterns / bilingual)
│   └── fixtures/                 good / bad prompt fixtures used by CI
└── .github/
    ├── workflows/
    │   ├── ci.yml                validate + template audit + self-test + execute examples (push / PR)
    │   └── release.yml           tag-driven automated release
    └── scripts/
        ├── validate_skill.py     structure and copy validation
        ├── audit_templates.py    audit the shipped templates with the checker
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
- **Bilingual self-check**: `scripts/check_prompt.py` validates the eight segments and verifiability in Chinese and English, detects the prompt language and checks that the acceptance command matches it (e.g. Go requires `go test`), and flags anti-patterns such as "tweak the tests as well" or "rewrite the whole project". Adds `--strict` (warnings fail) and `--skeleton` (print fill-in skeletons for missing segments).
- **Executable examples**: five cross-language samples are run in CI by `verify_examples.py` (`go test` / `python -m unittest` / `cargo test` / `node --test` / `dotnet run`), so docs cannot drift from code.
- **Template self-audit**: `audit_templates.py` runs the shipped checker over the default and English master templates.
- **English template**: `references/template-en.md` provides the eight-segment master template in English.
- **Anti-misuse**: "when to downgrade", a common-bad-prompt table, and output-format options.

## Install (DSH)

1. Put this repository into DSH's skills directory: `~/.dsh/skills/`
2. The directory must be named `code-refactor-prompts` and contain `SKILL.md`
3. DSH discovers and registers the skill automatically

## Usage

Ask the model to "refactor this code" or "give me a refactoring prompt". The skill triggers and returns a structured prompt with mandatory acceptance criteria. For English codebases use the [English master template](references/template-en.md).

## Self-check a prompt

```bash
python3 scripts/check_prompt.py my-prompt.txt
python3 scripts/check_prompt.py my-prompt.txt --lang go       # force the language
python3 scripts/check_prompt.py my-prompt.txt --strict        # warnings fail (team gate)
python3 scripts/check_prompt.py my-prompt.txt --skeleton      # print skeletons for missing segments
cat my-prompt.txt | python3 scripts/check_prompt.py -
```

It checks structure and known anti-patterns only (Chinese and English); semantic quality is still your call. CI self-tests the script with the good / bad fixtures, including a language-mismatch case, English anti-patterns, strict mode and the skeleton output.

## CI and release

- **CI** ([.github/workflows/ci.yml](.github/workflows/ci.yml)): validates skill structure, frontmatter, version alignment, references, links and copy; audits the shipped templates; self-tests the prompt checker; executes every runnable example with Node 24; dry-runs packaging.
- **Release** ([.github/workflows/release.yml](.github/workflows/release.yml)): on a `v*` tag it validates, audits templates, executes the examples, builds `zip` / `tar.gz` / `SHA256SUMS`, and publishes a GitHub Release.

Release steps: update `CHANGELOG.md` and `metadata.version` → push `main` → `git tag -a vX.Y.Z -m "..." && git push origin vX.Y.Z`.

## License

[MIT](LICENSE)
