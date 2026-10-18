# code-refactor-prompts

[![CI](https://github.com/f-e-n-g-0531/code-refactor-prompts/actions/workflows/ci.yml/badge.svg)](https://github.com/f-e-n-g-0531/code-refactor-prompts/actions/workflows/ci.yml)
[![Release](https://github.com/f-e-n-g-0531/code-refactor-prompts/actions/workflows/release.yml/badge.svg)](https://github.com/f-e-n-g-0531/code-refactor-prompts/releases)

中文 | [English](README.en.md)

一个用于生成高质量、行为等价、可验收的 **代码重构提示词** 的可复用技能（DSH Skill）。

本技能把「信息密度决定质量上限」的方法论沉淀为可直接加载、可直接粘贴使用的结构化提示词体系：三档策略（A 模糊 / B 结构化 / C 上下文＋验收标准）、八段式骨架、13 个专项变体、分语言定制参考、端到端工作流，并以「行为基线测试 + 可验证验收标准」和 Guard Clauses 作为两道质量防线。样例代码不是纸面内容：6 个可执行样例（Python / Go / Rust / TypeScript / C# / SQL）由 CI 真实执行验证；默认模板、英文模板与含提示词块的专项变体也由同一检查器做分级审计。

## 结构

```text
code-refactor-prompts/
├── SKILL.md                      主技能（核心原则、八段骨架、三档策略、默认模板）
├── README.md                     中文说明
├── README.en.md                  英文说明
├── CHANGELOG.md                  版本记录（遵循 SemVer）
├── CONTRIBUTING.md               贡献指南（本地门禁、约定、发布流程）
├── LICENSE                       MIT 许可
├── .gitignore
├── .pre-commit-hooks.yaml        pre-commit 钩子定义（安装 console script 后批量检查）
├── pyproject.toml                打包元数据（console script：code-refactor-prompt-check）
├── action.yml                    GitHub Action（PR 门禁 + 文件级注解）
├── references/
│   ├── specialized-prompts.md    13 个专项变体提示词
│   ├── language-specific.md      分语言定制要点（12 门语言 + React 专题；含 Kotlin / Swift / Ruby / PHP）
│   ├── workflows.md              端到端工作流（评审 / 基线 / 分批 / 迭代修复）
│   ├── template-en.md            英文主模板（八段式 + 验收标准 + 输出格式）
│   ├── checklists.md             落地检查清单（发出 / 应用 / 验收 / 合并）
│   └── sources.md                出处与依据（19 条）
├── examples/
│   ├── java-order-calculator-strategy-c.md        实战样例（策略 C 全景）
│   ├── python-legacy-characterisation.md          可执行样例（Python 行为基线 + 差分）
│   ├── go-legacy-order-total.md                   可执行样例（Go 行为基线 + 差分）
│   ├── rust-legacy-order-total.md                 可执行样例（Rust 行为基线 + 差分）
│   ├── typescript-legacy-characterisation.md      可执行样例（TS 运行时等价的类型化重构）
│   ├── csharp-legacy-order-total.md               可执行样例（C# 无测试框架下的退出码断言）
│   └── sql-legacy-report-equivalence.md           可执行样例（SQL 结果集 golden + 差分）
├── scripts/
│   ├── check_prompt.py           生成提示词自检（八段 / 可验证 / 语言匹配 / 反模式 / 双语）
│   ├── check_sources.py          出处链接巡检（离线语法 / 在线可达性）
│   ├── compose_prompt.py         从源码文件一键生成「已填好且自检通过」的提示词
│   ├── run_checks.py             一键本地门禁（校验 / 审计 / 测试 / 链接，--full 跑样例）
│   ├── fixtures/                 正例 / 反例 / 示例源码（CI 自测用）
│   └── tests/                    工具链回归测试（检查器 / 生成器 / 批量与钩子 / 出处链接 / 门禁 / 校验脚本）
└── .github/
    ├── workflows/
    │   ├── ci.yml                校验 + 模板审计 + 自测 + 样例实跑（push 到 main / PR）
    │   ├── link-check.yml        每周在线巡检 sources.md 外链
    │   └── release.yml           推送 v* 标签自动发布
    └── scripts/
        ├── validate_skill.py     结构 / 文案 / 文档结构 / 版本与用例数校验
        ├── audit_templates.py    分级审计：主模板跑完整检查器，专项变体查验收锚点
        ├── verify_examples.py    从样例 md 提取代码并真实执行
        └── release_notes.py      从 CHANGELOG 生成 Release Notes
```

## 特性

- **三档策略**：按风险与场景在 A/B/C 三档间选择，关键重构必用「上下文 + 验收标准」。
- **八段式骨架**：角色、上下文、待重构代码、硬约束、重构目标、验收标准、输出格式、守卫，缺一不可。
- **行为等价可验收**：用「行为基线测试 + 可验证验收标准」取代空泛的「保持行为不变」。
- **Guard Clauses 防废话**：无代码输出 NO_CODE_PROVIDED，无问题输出 NO_REFACTORING_NEEDED。
- **端到端工作流**：评审驱动重构、遗留代码先锁行为基线、多文件分批验收、AI 输出后的迭代修复。
- **分语言定制**：Java / Python / JS-TS / React / Go / Rust / C# / C++ / SQL / Kotlin / Swift / Ruby / PHP 的惯用手法、测试命令与红线。
- **批量与门禁**：`check_prompt.py` 支持多文件 / 目录批量检查（逐文件 PASS/FAIL + 汇总），附 `.pre-commit-hooks.yaml`，pre-commit / CI 可直接接入。
- **PR 门禁（GitHub Actions）**：根目录 `action.yml` 在 PR 中运行检查器，并以 `--format github` 将问题注解到对应文件；`changed-only: true` 时只检查本次 PR 变更的提示词文件。
- **工具链回归测试**：`scripts/tests/` 以 73 个用例覆盖检查器、生成器（含 C 档）、`--fix` 闭环、出处链接巡检、13 语言矩阵与校验脚本自身，CI 每次运行。
- **一键本地门禁**：`scripts/run_checks.py` 串行执行结构校验、模板审计、工具链测试与出处离线检查；`--full` 额外真实执行全部可执行样例，`--list` 只列步骤。
- **落地清单**：`references/checklists.md` 给出「发提示词前 → 应用前 → 应用后 → 合并前」四段检查清单。
- **一键生成**：`scripts/compose_prompt.py --code <文件>` 从源码文件生成填好的八段提示词（中 / 英，自动识别 13 种语言与测试命令）；同时提供 `--rule`（业务规则）与 `--case`（验收用例）时直接生成完整 C 档，`--require-c-tier` 可强制要求两者（关键重构门禁）；生成结果先过检查器，不合规就拒绝输出。
- **可自检（双语）**：`scripts/check_prompt.py` 检查八段、可验证验收与守卫，并校验代码段是否真的含代码（或 `{粘贴代码}` 占位符）、验收命令是否写在验收段；自动识别中英文段落与提示词语言，校验验收命令是否匹配（如 Go 必须写 `go test`），拦截「顺便改测试」「整体重写」「空泛指标」等中英文反模式；支持 `--strict`（警告即失败）、`--skeleton`（打印缺失段落骨架）与 `--fix`（把缺失段落骨架追加到文件并复查）。
- **样例可执行**：6 个跨语言 / 跨领域样例由 CI 用 `verify_examples.py` 真实执行（`go test` / `python -m unittest` / `cargo test` / `node --test` / `dotnet run` / SQLite 结果集对比），文档与代码不会脱节。
- **出处可巡检**：`scripts/check_sources.py` 离线校验 `references/sources.md` 的链接语法与去重，`--online` 逐个请求；CI 每次跑离线检查，另有每周 `Link check` workflow 在线巡检，防止出处腐烂。
- **分级审计**：`audit_templates.py` 用同一检查器审计 SKILL.md 默认模板与英文模板（完整八段检查）；12 个含提示词块的专项变体检查「验收锚点」与 error 级反模式（第 6 节为速查表），守卫变体改查 `NO_CODE_PROVIDED` / `NO_REFACTORING_NEEDED`——主模板和变体的质量都不靠自觉。
- **英文模板**：`references/template-en.md` 提供八段式英文主模板，便于英文代码库与评审流程直接使用。
- **防误用**：给出「何时降档 / 不适用」「常见错误提示词（反例 → 修正）」与输出格式约定。

## 安装（DSH）

1. 将本仓库放入 DSH 的 skills 目录：`~/.dsh/skills/`
2. 目录名必须为 `code-refactor-prompts`，且包含 `SKILL.md`
3. DSH 会自动发现并注册该技能
4. 使用工具链需 Python 3.9+（Windows 上通常用 `python` 而不是 `python3`）

## 使用

对模型说「重构这段代码」或「给我一个重构提示词」，技能即被触发，产出结构化、强制带验收标准的提示词。英文代码库可直接套用 [英文主模板](references/template-en.md)。

## 一键生成提示词

手头有代码但不想手填模板时（以下命令在技能仓库根目录执行，把 `src/order.go` 换成你的源文件）：

```bash
python3 scripts/compose_prompt.py --code src/order.go --project order-pricing \
    --pain "Total 函数 150 行、魔法数字散落" \
    --rule "图书 9 折、电子 95 折，满 100 再 98 折" \
    --case "空订单 → 0" --case "图书 100×1 → 102.2" --out prompt.txt
python3 scripts/check_prompt.py prompt.txt
```

不给 `--rule` / `--case` 时输出 B 档提示词（业务规则与用例留占位符）；同时提供两者时输出完整 C 档（上下文含业务规则、验收标准含具体用例）；只提供一侧时该侧被填实、另一侧仍是占位符。自动识别的语言与默认测试命令覆盖 Go / Python / Java / Rust / TypeScript / JavaScript / C# / Kotlin / Swift / Ruby / PHP / C++ / SQL；生成时已内置自检，若生成的提示词过不了检查器（例如 `--test-command` 与语言不匹配），脚本直接报错退出、不输出不合规提示词。

## 落地检查清单

提示词写得再好，应用与验收环节掉链子也会前功尽弃。四段清单（发出前 / 应用前 / 应用后 / 合并前）见 [references/checklists.md](references/checklists.md)，每条都尽量能用命令核对。

## 提示词自检

生成提示词后存成文件，用脚本做结构自检（八段是否齐全、验收是否可验证、验收命令与语言是否匹配、是否存在典型反模式；中英文提示词均可）：

```bash
python3 scripts/check_prompt.py my-prompt.txt
python3 scripts/check_prompt.py my-prompt.txt --lang go       # 显式指定语言
python3 scripts/check_prompt.py my-prompt.txt --strict        # 警告也视为失败（团队门禁）
python3 scripts/check_prompt.py my-prompt.txt --skeleton      # 打印缺失段落骨架
python3 scripts/check_prompt.py my-prompt.txt --fix           # 追加缺失段落骨架并复查
python3 scripts/check_prompt.py --changed origin/main --strict # 只检查自基线以来变更的提示词
cat my-prompt.txt | python3 scripts/check_prompt.py -
```

只检查结构与模式，不判断语义质量；CI 用 `scripts/fixtures/` 里的正例 / 反例自测该脚本（含语言不匹配、中英文反模式、严格模式与骨架输出）。

退出码：`0` = 通过，`1` = 发现问题，`2` = 用法 / 输入错误（文件不存在、非 UTF-8、`--fix` 与 `--json` 同用等）。`--json` 输出机器可读结果；批量模式含逐文件结果与 `skeleton`。

Windows / PowerShell：请使用单行命令；读取中文提示词用 `Get-Content -Raw -Encoding UTF8 my-prompt.txt | python scripts/check_prompt.py -`，或直接传文件路径；解释器可能是 `python`。

## 接入 CI 与 pre-commit

批量检查一个提示词目录（逐文件 PASS/FAIL + 汇总）：

```bash
python3 scripts/check_prompt.py prompts/ --strict
```

目录默认递归匹配 `*.prompt`、`*.prompt.md`、`*.prompt.txt`（`--include` 可自定义）；多文件与目录可组合使用，`--fix` 不能与 `--json` / `--skeleton` 同用。

pre-commit（用于消费仓库；`rev` 需指向已发布的 tag）。先安装并启用钩子：

```bash
pip install pre-commit
pre-commit install
```

然后在 `.pre-commit-config.yaml` 中：

```yaml
repos:
  - repo: https://github.com/f-e-n-g-0531/code-refactor-prompts
    rev: v1.16.1
    hooks:
      - id: code-refactor-prompt-check
```

钩子通过 `pyproject.toml` 暴露 `code-refactor-prompt-check` console script，pre-commit 以 `language: python` 安装后直接调用；匹配 `\.prompt(\.(md|txt))?$` 的暂存文件会被批量交给检查器（`--strict`），有失败即阻止提交。本地试用钩子（无需先发 tag）：`pre-commit try-repo . --ref HEAD --files my.prompt.txt`。

## GitHub Actions（PR 门禁）

根目录 `action.yml` 可直接在 PR 中运行检查器，并用 `--format github` 把问题注解到对应文件（可定位的问题会带行号）：

```yaml
name: Prompts
on: [pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0        # changed-only 需要完整历史
      - uses: f-e-n-g-0531/code-refactor-prompts@v1.16.1
        with:
          changed-only: true     # 只检查本 PR 变更的提示词；不设置时检查 files（默认整个仓库）
          strict: true           # 警告也算失败
```

需要 Linux / macOS runner（依赖 bash 与 python3）；本地等价命令：`python3 scripts/check_prompt.py --changed origin/main --format github --strict`。

## CI 与发布

- **CI**（[.github/workflows/ci.yml](.github/workflows/ci.yml)）：push 到 main / PR 时校验技能结构、frontmatter、版本一致性、引用完整性、Markdown 文档结构（重复标题）与用例数、相对链接及禁止的过程性文案；对模板与专项变体做分级审计；自测提示词检查器；运行工具链回归测试；离线检查出处链接（`check_sources.py`）；自测 GitHub 注解输出（`--format github`）；安装并测试打包后的 pre-commit console script；用 `pre-commit try-repo` 做钩子端到端验证（好提示词通过、坏提示词阻断）；配置 Node 24 并实际执行全部 6 个可执行样例（go test / python unittest / cargo test / node --test / dotnet run / SQLite 结果集对比）；并 dry-run 一次发布打包。另有 Windows runner 任务复跑结构校验、模板审计、工具链测试、出处离线检查与 console script 安装，覆盖跨平台差异。
- **Link check**（[.github/workflows/link-check.yml](.github/workflows/link-check.yml)）：每周一 03:17 UTC（可手动触发）在线请求 `references/sources.md` 的全部链接，失败即报红。
- **Release**（[.github/workflows/release.yml](.github/workflows/release.yml)）：推送 `v*` 标签后自动校验、审计模板、实跑样例、打包（`zip` / `tar.gz` / `SHA256SUMS`）并创建 GitHub Release。

发布流程：

1. 更新 `CHANGELOG.md`、`SKILL.md` 的 `metadata.version`、`pyproject.toml` 的 `version`，以及两个 README 中的 `rev: vX.Y.Z` / Action 示例 `@vX.Y.Z` 与钩子注释（校验脚本会强制一致）；
2. 提交并推送 `main`；
3. 打标签并推送：`git tag -a vX.Y.Z -m "..." && git push origin vX.Y.Z`；
4. GitHub Actions 自动产出 Release 与附件。

## 贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md)：本地一键门禁 `python3 scripts/run_checks.py --full`；版本号、`rev`、Action 示例版本与测试数均由 `validate_skill.py` 强制同步。

## 许可

[MIT](LICENSE)
