# Changelog

本项目遵循 [Semantic Versioning](https://semver.org/)。

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
