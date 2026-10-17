# code-refactor-prompts

一个用于生成高质量、行为等价、可验收的 **代码重构提示词** 的可复用技能（DSH Skill）。

本技能把「信息密度决定质量上限」的方法论沉淀为可直接加载、可直接粘贴使用的结构化提示词体系：三档策略（A 模糊 / B 结构化 / C 上下文＋验收标准）、八段式骨架、13 个专项变体、分语言定制参考，并以「行为基线测试 + 可验证验收标准」和 Guard Clauses 作为两道质量防线。

## 结构

```text
code-refactor-prompts/
├── SKILL.md                      主技能（核心原则、八段骨架、三档策略、默认模板）
├── README.md                     项目说明、安装与使用
├── CHANGELOG.md                  版本记录（遵循 SemVer）
├── LICENSE                       MIT 许可
├── .gitignore
├── references/
│   ├── specialized-prompts.md    13 个专项变体提示词
│   ├── language-specific.md      分语言定制要点（Java/Python/JS-TS/React/Go/Rust/C#/C++/SQL/Ruby/PHP）
│   └── sources.md                出处与依据（19 条）
└── examples/
    └── java-order-calculator-strategy-c.md   实战样例（策略 C 全景）
```

## 特性

- **三档策略**：按风险与场景在 A/B/C 三档间选择，关键重构必用「上下文 + 验收标准」。
- **八段式骨架**：角色、上下文、待重构代码、硬约束、重构目标、验收标准、输出格式、守卫，缺一不可。
- **行为等价可验收**：用「行为基线测试 + 可验证验收标准」取代空泛的「保持行为不变」。
- **Guard Clauses 防废话**：无代码输出 NO_CODE_PROVIDED，无问题输出 NO_REFACTORING_NEEDED。
- **分语言定制**：Java / Python / JS-TS / React / Go / Rust / C# / C++ / SQL / Ruby / PHP 的惯用手法、测试命令与红线。

## 安装（DSH）

1. 将本仓库放入 DSH 的 skills 目录：`~/.dsh/skills/`
2. 目录名必须为 `code-refactor-prompts`，且包含 `SKILL.md`
3. DSH 会自动发现并注册该技能

## 使用

对模型说「重构这段代码」或「给我一个重构提示词」，技能即被触发，产出结构化、强制带验收标准的提示词。

## 许可

[MIT](LICENSE)
