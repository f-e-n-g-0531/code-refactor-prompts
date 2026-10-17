# code-refactor-prompts

一个用于生成高质量、行为等价、可验收的 **代码重构提示词** 的可复用技能（DSH Skill）。

它把「模糊指令 → 结构化指令 → 上下文 + 验收标准」三档策略、六段式骨架，以及性能优化 / 代码坏味道 / 大文件拆分 / 安全加固 / 现代化升级等专项变体，沉淀成一份可直接加载的方法论，并附 13 条出处与依据。

## 目录

- SKILL.md — 主技能（核心原则、骨架、三档策略、默认模板）
- references/specialized-prompts.md — 专项变体（性能/坏味道/拆分/安全/现代化/可测试性/解耦/SOLID/设计模式/技术债/分语言速查等）
- references/language-specific.md — 分语言定制要点
- references/sources.md — 出处与依据（19 条）
- examples/ — 实战样例（策略 C 全景）

## 安装（DSH）

1. 将本仓库放入 DSH 的 skills 目录：~/.dsh/skills/
2. 目录名必须为 code-refactor-prompts，且包含 SKILL.md
3. DSH 会自动发现并注册该技能

## 使用

对模型说「重构这段代码」或「给我一个重构提示词」，技能即被触发，产出结构化、强制带验收标准的提示词。

## 许可

MIT
