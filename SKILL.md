---
name: code-refactor-prompts
description: Compose high-quality, behavior-preserving code refactoring prompts. Use when the user asks how to write a refactoring/optimization prompt, wants a reusable prompt template, or needs AI to refactor, de-smell, or optimize code safely. Distill every prompt into role, context, code, hard constraints, refactoring goals, verifiable acceptance criteria, and output format; never let "keep behavior unchanged" go untested.
license: MIT
metadata:
  author: user
  version: "1.0.0"
---

# 代码重构优化提示词

当用户要求重构/优化代码、索要重构提示词模板，或需要 AI 安全地重构、去坏味道、优化代码时，按本技能产出**可直接粘贴使用的结构化提示词**。默认中文输出；若用户指定语言/框架，把模板中 `{占位符}` 与测试命令填成对应的可用值。

## 核心原则

1. **信息密度决定质量上限**：模糊指令 → 只能"能跑"；结构化指令 → "规范"；带上下文 + 验收标准 → "可靠"。
2. **行为等价必须用可验证用例表达**：把"保持行为不变"写成一条可运行的测试命令，或若干「给定输入 → 期望输出」用例。这是拉开重构质量差距最关键的一步。
3. **先问清再动手**：提示词结尾让模型在信息不足时先提澄清问题，避免瞎猜。

## 骨架（每段缺一不可）

1. 角色（Role）
2. 上下文（Context）：项目/模块、语言+版本+框架、这段代码做什么、已知痛点
3. 待重构代码
4. 硬约束（不可违反）
5. 重构目标
6. 验收标准（必填）
7. 输出格式

## 三档策略（何时用）

- **A 模糊**（仅"重构这段代码"）：只在用户明确要快速粗改时给，否则不要给。
- **B 结构化**（目标 + 约束 + 输出格式）：**日常默认给这档**。
- **C 上下文 + 验收标准**（B + 业务规则 + 可验证用例）：**关键或高风险重构必给这档**。

## 默认模板（主用）

```text
你是资深 {语言/框架} 专家，专注在不改变行为的前提下做重构。

【上下文】
- 项目/模块：{名称}
- 语言与框架：{语言 + 版本 + 框架}
- 这段代码做什么、已知痛点：{业务背景}

【待重构代码】
{粘贴代码，用 fenced code block}

【硬约束（不可违反）】
1. 外部行为 100% 一致：不改公开 API、返回值、抛出的异常类型；
2. 不新增第三方依赖；不弱化错误处理、日志、安全校验；
3. 遵循项目现有编码规范与命名风格。

【重构目标】
1. {消除重复 / 降低圈复杂度 / 拆分长函数 / 提取子方法 / 语义化命名}
2. 用具名常量或枚举替换魔法数字/字符串。

【验收标准（必填，用可验证的用例/命令表达）】
重构后必须通过：
- 测试命令：{例如 pytest / npm test / mvn test}
- 用例：{给定输入 → 期望输出}

【输出格式】
1. 问题清单：问题 → 严重度(高/中/低) → 位置；
2. 重构后的完整代码（用 diff 展示改动）；
3. 表格：每处改动 → 改了什么 → 为什么 → 影响面；
4. 风险提示：哪些改动有兼容性风险。

如有信息不足，先提问再动手。
```

## 专项变体

性能优化、代码坏味道、大文件/长函数拆分、安全加固、现代化升级、分语言定制，见 `references/specialized-prompts.md`。依据与出处见 `references/sources.md`。
