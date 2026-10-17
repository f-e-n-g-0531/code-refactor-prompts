# Changelog

本项目遵循 [Semantic Versioning](https://semver.org/)。

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
