# Changelog

本项目遵循 [Semantic Versioning](https://semver.org/)。

## [1.11.0] - 2026-10-18

### Added

- `check_prompt.py --format github`：输出 GitHub Actions 工作流注解（`::error file=...::…` / `::warning file=...::…`，含 `%` 与换行转义），单文件与批量模式均支持；`--format github` 不能与 `--json` / `--fix` 同用。
- 根目录 `action.yml`：composite GitHub Action，在 PR 中直接运行检查器并以文件级注解呈现问题；输入 `files` / `include` / `strict`（默认开启），依赖 Linux / macOS runner 的 bash + python3。
- CI 新增注解输出自测；`validate_skill.py` 校验 Action 定义与 CI 接线，发布打包纳入 `action.yml`。
- 测试新增 3 个用例（单文件注解、批量注解、与 `--json` / `--fix` 组合拒绝），总数 56 → 59。

### Changed

- README / README.en 增加「PR 门禁（GitHub Actions）」特性、接入示例与结构树；SKILL 工具链说明补充 `--format github`；版本 1.11.0。

## [1.10.0] - 2026-10-18

### Added

- `scripts/check_sources.py`：出处链接巡检。默认离线校验 `references/sources.md` 中 URL 的语法、主机与去重；`--online` 逐个请求（网络错误自动重试一次，必要时回退到 `curl`，403 / 429 视为警告），支持 `--timeout` 与 `--json`，退出码 0 / 1 / 2。
- `.github/workflows/link-check.yml`：每周一 03:17 UTC + 手动触发的在线链接巡检，逐条请求全部 21 个出处链接。
- CI 每次 push 运行离线出处检查；`validate_skill.py` 校验巡检脚本、测试与 workflow 接线。
- `scripts/tests/test_check_sources.py`：7 个回归用例（仓库出处离线通过、Markdown 链接与中文标点、重复 URL 计数、非法 URL、无链接、缺文件、非法超时），用例总数 49 → 56。

### Changed

- README / README.en 增加「出处可巡检」特性、结构树、CI 与 Link check 说明；SKILL 指向巡检脚本；版本 1.10.0。

## [1.9.0] - 2026-10-18

### Added

- `compose_prompt.py` 支持 `--rule`（业务规则，可重复）与 `--case`（验收用例，可重复）：生成器可直接产出 C 档提示词——上下文含业务规则、验收标准含具体用例，不再只生成带占位符的 B 档；未提供时行为不变（占位符保留），输出仍先过检查器才写出。
- 工具链回归测试新增 10 个用例：3 个覆盖 C 档生成（中文、英文、未提供规则/用例时保留占位符），3 个注入用例覆盖校验脚本（pyproject 版本漂移、钩子 entry 漂移、重复 H1），4 个覆盖输入健壮性（非 UTF-8 提示词 / 源码、`--out` 目录不存在、stdin 缺 `--code-lang`）；用例总数 39 → 49。
- CI 与 Release 增加 pre-commit 端到端测试：用 `pre-commit try-repo .` 验证好提示词通过、坏提示词阻断提交，覆盖「文档声称可用」与「实际可用」之间的缝隙。
- Release 增加产物校验：发布 zip 必须包含 `pyproject.toml` / `.pre-commit-hooks.yaml` / `scripts/check_prompt.py`，且不得包含 `.github`。
- `validate_skill.py` 守卫加固：`rev` 支持带引号的 YAML、代码围栏按开围栏长度正确闭合、测试计数支持 `async`、CI 检查精确到步骤名，并校验 Release 的端到端测试与产物断言。

### Fixed

- 工具链输入健壮性：非 UTF-8 的提示词 / 源码不再抛 traceback，统一返回退出码 2 与可读错误；stdin 未给 `--code-lang` 时给出明确提示；`--out` 目录不存在时返回 2 而不是 traceback；批量 `--json` 结果补充 `skeleton` 字段，与单文件 JSON 对齐。
- 文档补齐消费端前置条件与实测反馈：pre-commit 的 `pip install pre-commit` / `pre-commit install`、`rev` 需指向已发布 tag、命令需在技能仓库根目录执行、Windows / PowerShell 单行命令与 UTF-8 读取方式、退出码 0 / 1 / 2 与 `--json` 说明；英文 README 的 compose 示例补 `--output-lang en`。

### Changed

- README / README.en 的「一键生成」说明与示例补充 C 档用法（明确「同时提供」才生成完整 C 档）；发布流程补齐 `pyproject.toml` 版本与 `rev` 同步；CI 说明补充 pre-commit 端到端；SKILL 工具链段落同步；版本 1.9.0。

## [1.8.1] - 2026-10-18

### Fixed

- 修复 `README.md` / `README.en.md` 整段重复粘贴：v1.8.0 的两份说明文档在 pre-commit 段落之后各重复了除该段落外的全部内容，并截断了 pre-commit 说明句；现恢复为单份文档并补全该句。
- 修复 pre-commit 钩子不可用：v1.8.0 的钩子缺少打包元数据（`pip install .` 失败），且 entry 按消费仓库 cwd 解析 `scripts/check_prompt.py`。新增 `pyproject.toml`（`check_prompt` 模块 + `code-refactor-prompt-check` console script），entry 改为调用该 console script；CI 增加 `pip install .` 与 console script 安装/行为自测（pre-commit 消费端端到端见 1.9.0），发布打包纳入 `pyproject.toml`。
- 修复 Java 样例验收用例：图书 100 × 1 折后为 90，不触发 100 元满减，期望值应为 `102.2`；补充「分类为 null 仍抛 NPE」的等价用例，参考重构改用 `category.equals(...)` 保留原异常行为，删除误导性的「有意行为收紧」说明。
- 修正文档与实现 / 审计口径不一致：`--fix` 不能与 `--json` / `--skeleton` 同用；语言参考为「12 门语言 + React 专题」而 compose 支持 13 种语言；审计覆盖 12 个含提示词块的变体（第 6 节速查表跳过）；pre-commit 正则补 `$`；`--skeleton` 只打印、`--fix` 才追加；frontmatter description 补 guard clauses；CI 中 Node 24 只服务 TS 样例；SKILL 工具链段落移出默认模板区。
- 修正 `README.md` / `README.en.md` 中过期的工具链用例数（23 → 39）。

### Added

- `pyproject.toml`：以 `scripts/check_prompt.py` 为 `check_prompt` 模块，暴露 `code-refactor-prompt-check` console script，供 pre-commit（`language: python`）安装调用。
- `validate_skill.py` 新增文档守卫：Markdown 必须恰好一个一级标题、不得重复二级标题（拦截整段重复粘贴）；README 的工具链用例数必须与 `scripts/tests/` 的实际用例数一致；README / 钩子注释 / `pyproject.toml` 的版本必须与 `SKILL.md` 的 `metadata.version` 一致；`REQUIRED_FILES` 补入 `test_batch_and_hook.py` 与 `pyproject.toml`。
- `scripts/tests/test_validate_skill.py`：4 个回归用例，用「复制仓库 → 注入缺陷 → 期望校验失败」的方式覆盖校验脚本自身（干净副本通过、重复二级标题、过期用例数、版本漂移）；`test_batch_and_hook.py` 改查 console script 与 `pyproject.toml` 契约。
- CI 新增打包后 console script 安装与行为自测；发布 dry-run 与 Release 产物纳入 `pyproject.toml`。

### Changed

- README / README.en / SKILL 全量同步上述事实：pre-commit 安装方式、批量选项组合限制、语言与变体审计口径、CI 步骤与结构树。
- pre-commit 钩子 entry 从 `python3 scripts/check_prompt.py --strict` 改为 `code-refactor-prompt-check --strict`。

## [1.8.0] - 2026-10-18

### Added

- `check_prompt.py` 批量模式：支持多文件与目录递归检查（默认匹配 `*.prompt` / `*.prompt.md` / `*.prompt.txt`，`--include` 自定义），逐文件 PASS/FAIL + 汇总，支持 `--fix` / `--strict` / `--json`（`--fix` 不能与 `--json` / `--skeleton` 同用）；目录无匹配文件或 stdin 与其他来源混用返回退出码 2。
- `.pre-commit-hooks.yaml`：pre-commit 钩子定义（v1.8.1 补齐 `pyproject.toml` 并改为 console script entry 后才真正可用）。
- `scripts/tests/test_batch_and_hook.py`：12 个新用例覆盖目录扫描、多文件、`--include`、批量 `--fix` / `--json` / `--strict`、空目录与 stdin 混用、钩子定义与钩子契约。

### Changed

- CI / Release 发布包纳入 `.pre-commit-hooks.yaml`，dry-run 增加入包断言；校验脚本检查钩子定义与打包接线。
- README / README.en 新增「接入 CI 与 pre-commit」；SKILL 说明批量用法；版本 1.8.0。

## [1.7.0] - 2026-10-18

### Added

- `scripts/tests/`：工具链回归测试套件（23 个用例，标准库 unittest），覆盖 8 个夹具的通过/拒绝矩阵、13 种语言 × 显式/自动识别、语言不匹配、严格模式、缺失段落、 中英文反模式、`--skeleton` / `--json` / stdin / `--fix` 修复闭环，以及生成器的 13 语言、stdin、`--out`、错误测试命令拒绝与退出码。
- `references/checklists.md`：四段落地检查清单（发提示词前 → 应用 AI 输出前 → 应用后 → 合并前），每条尽量可用命令核对。
- CI / Release 新增「Test the prompt tooling」步骤，校验脚本强制该步骤存在。

### Fixed

- `compose_prompt.py` 的输入错误（未知扩展名 / 未知 `--code-lang`）现在按约定返回退出码 2，与用法错误语义一致。

### Changed

- SKILL.md、README、README.en.md 同步工具链回归测试、落地清单与发布流程。

## [1.6.0] - 2026-10-18

### Added

- `scripts/compose_prompt.py`：从源码文件一键生成填好的八段提示词（中 / 英），自动识别 13 种语言并给出默认测试命令；生成结果先过检查器，不合规直接报错拒绝输出。
- `check_prompt.py --fix`：把缺失段落骨架直接追加到提示词文件并自动复查（按中文 / 英文提示词选择对应骨架）。
- CI 自测新增：compose 生成结果必须通过检查器、错误 `--test-command` 必须被拒绝、`--fix` 修复前后状态必须符合预期。

### Changed

- 检查器与生成器统一 UTF-8 输入输出，跨平台管道更稳定。
- 校验脚本覆盖生成器、示例源码夹具与 `--fix` 的 CI 接线；README / README.en / SKILL 同步「一键生成 → 自检 → 修复」工具链说明。

## [1.5.0] - 2026-10-18

### Added

- `examples/sql-legacy-report-equivalence.md`：可执行 SQL 样例——用固定数据集把遗留查询结果锁成 golden，再用 CTE + 独立聚合改写并逐行差分；验证只用 Python 标准库 `sqlite3`，零依赖。
- 专项变体分级审计：`audit_templates.py` 新增第二级审计，主模板跑完整检查器；12 个含提示词块的变体参与审计（11 个检查「验收锚点」，守卫变体检查 `NO_CODE_PROVIDED` / `NO_REFACTORING_NEEDED`；第 6 节速查表跳过），并扫描反模式。
- 5 个变体补齐显式验收锚点：代码坏味道、安全加固、模块化/解耦、SOLID、设计模式应用。

### Changed

- 校验脚本新增 README「可执行样例数量」一致性检查（中英文）。
- CI / Release 的审计步骤覆盖专项变体；发布打包 dry-run 增加 SQL 样例断言。
- SKILL.md、README、README.en.md 同步：6 个可执行样例、分级审计、变体验收锚点说明。

## [1.4.0] - 2026-10-18

### Added

- 提示词检查器 v3：中英文段落与反模式双语识别；`--strict` 把警告升级为失败（团队 / CI 门禁）；`--skeleton` 输出缺失段落的中英文可填骨架。
- `examples/csharp-legacy-order-total.md`：可执行 C# 样例——无测试框架时用「退出码断言程序」锁行为基线 + 差分校验（`dotnet run` 实测通过）；`verify_examples.py` 支持 dotnet，按本机 SDK 版本生成 `netX.0` 工程。
- `.github/scripts/audit_templates.py`：用同一检查器审计 SKILL.md 默认模板与英文模板，模板与检查器不再可能各说各话；CI / Release 均执行。
- 新夹具：`good-en-prompt.txt`（英文正例）、`bad-en-prompt.txt`（英文反模式）、`weak-prompt.txt`（严格模式用例）；CI 自测覆盖双语、严格模式与骨架输出。

### Changed

- 校验脚本覆盖 C# 样例、审计脚本与全部新夹具，并强制 CI 接入模板审计；发布打包 dry-run 增加新样例断言。
- SKILL.md、README、README.en.md 同步：检查器双语 / 严格模式 / 骨架生成、模板自审计、C# 样例与 5 个可执行样例。
- 英文提示词现在可用同一工具自检（此前英文模板无法通过段落识别）。

## [1.3.0] - 2026-10-18

### Added

- 提示词检查器升级：自动识别提示词语言（或 `--lang` 显式指定），校验验收命令与语言是否匹配（Go → `go test`、Rust → `cargo test`、Python → `pytest`，等），并内置反模式词库（改测试迁就代码、整体重写、「最佳实践」无依据重写、空泛指标、顺手扩大范围、允许行为变化、模棱两可约束）。
- `examples/rust-legacy-order-total.md`：可执行 Rust 样例（行为基线 + 差分测试，`cargo test` 实测通过）。
- `examples/typescript-legacy-characterisation.md`：可执行 TypeScript 样例（保留 `any` 遗留行为的运行时等价重构，`node --test` 实测通过）。
- `references/template-en.md`：英文主模板（八段式骨架、验收标准、输出格式与自检说明）。
- `.github/scripts/verify_examples.py`：从样例 Markdown 提取带标记代码块，写入临时工程并真实执行；CI 与 Release 流程新增「Verify examples」步骤（Node 24）。

### Changed

- Go 与 Python 样例改为可执行：Go 重构版导出为 `TotalRefactored` 以便与遗留实现在同包内做差分测试；Python 基线测试改用标准库 `unittest`（零依赖）并补充固定种子的差分测试。
- 校验脚本覆盖新增文件、英文模板引用、样例可执行标记与 CI 接线；CI 自测新增语言不匹配与反模式夹具。
- SKILL.md、README、README.en.md 同步更新；发布包纳入新增样例与英文模板。

## [1.2.0] - 2026-10-18

### Added

- `scripts/check_prompt.py`：生成提示词的结构自检工具（八段齐全、验收可验证、Guard Clauses），支持 `--json` 与 stdin。
- `scripts/fixtures/`：正例 / 反例夹具，CI 自测该工具。
- `examples/go-legacy-order-total.md`：遗留 Go 代码「行为基线 → 重构 → 差分测试」样例（`go test` 实测通过）。
- `README.en.md`：英文说明，覆盖安装、使用、自检与发布流程。

### Changed

- CI 增加「提示词检查器自测」步骤；发布包纳入 `scripts/` 与英文 README。
- SKILL.md「输出格式选项」补充生成后自检；校验脚本覆盖新增文件。

## [1.1.0] - 2026-10-18

### Added

- `references/workflows.md`：4 个端到端工作流——评审驱动重构、遗留/无测试代码先锁行为基线、多文件分批重构、应用 AI 输出后的迭代修复。
- `examples/python-legacy-characterisation.md`：无测试遗留代码「生成行为基线测试 → 重构 → 等价验证」全流程样例。
- SKILL.md 新增「何时降档 / 不适用」「常见错误提示词（反例 → 修正）」「输出格式选项」「迭代修复（应用后验证）」四节。
- 分语言参考新增 Kotlin、Swift，并将 Ruby / PHP 提升为独立小节。

### Changed

- 默认模板：【验收标准】补充「无法运行测试时的等价验证」；【输出格式】补充「统一 diff 需声明基线」。
- README 结构树、特性与简介同步更新；校验脚本覆盖新增文件与工作流引用。

## [1.0.0] - 2026-10-18

### Added

- SKILL.md 主技能：核心原则、八段式骨架、三档策略（A/B/C）、可直接粘贴的默认模板。
- 13 个专项变体：性能优化、代码坏味道、大文件/长函数拆分、安全加固、现代化升级、分语言定制、行为基线测试、守卫、可测试性改造、模块化解耦、SOLID 原则、设计模式应用、技术债/遗留系统。
- 分语言参考：Java、Python、JavaScript/TypeScript、React、Go、Rust、C#/.NET、C++、SQL，以及 Ruby/PHP。
- 19 条出处与依据，分六大类。
- 1 个实战样例（Java 订单计算器 · 策略 C 全景）。
- GitHub Actions CI：`ci.yml` 校验结构 / frontmatter / 版本一致性 / 相对链接 / 文案，`release.yml` 在推送 `v*` 标签时自动发布 GitHub Release，并附 `zip`、`tar.gz` 与 `SHA256SUMS`。
