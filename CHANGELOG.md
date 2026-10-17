# Changelog

本项目遵循 [Semantic Versioning](https://semver.org/)。

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
