---
name: code-refactor-prompts
description: Compose high-quality, behavior-preserving code refactoring prompts. Use when the user asks how to write a refactoring/optimization prompt, wants a reusable prompt template, or needs AI to refactor, de-smell, or optimize code safely. Distill every prompt into role, context, code, hard constraints, refactoring goals, verifiable acceptance criteria, output format, and guard clauses; never let "keep behavior unchanged" go untested.
license: MIT
metadata:
  author: f-e-n-g-0531
  version: "1.16.1"
---

# 代码重构优化提示词

当用户要求重构/优化代码、索要重构提示词模板，或需要 AI 安全地重构、去坏味道、优化代码时，按本技能产出**可直接粘贴使用的结构化提示词**。默认中文输出；若用户指定语言/框架，把模板中 `{占位符}` 与测试命令填成对应的可用值。英文模板见 `references/template-en.md`；检查器支持中英文提示词（`--strict` 严格模式、`--skeleton` 打印缺失段落骨架、`--fix` 追加并复查）；主模板与英文模板本身也由 `audit_templates.py` 用同一检查器审计；不想手填模板时，`scripts/compose_prompt.py` 可从源码文件一键生成填好的提示词（中/英，自动识别 13 种语言与测试命令），生成结果先过检查器才输出；仓库内 Python / Go / Rust / TypeScript / C# / SQL 六个样例均由 CI 实际执行（`verify_examples.py`），可直接照搬其验收标准写法；默认模板、英文模板与含提示词块的专项变体由 `audit_templates.py` 分级审计。

## 核心原则

1. **信息密度决定质量上限**：模糊指令 → 只能"能跑"；结构化指令 → "规范"；带上下文 + 验收标准 → "可靠"。
2. **行为等价必须用可验证用例表达**：把"保持行为不变"写成一条可运行的测试命令，或若干「给定输入 → 期望输出」用例。这是拉开重构质量差距最关键的一步。
3. **先问清再动手**：提示词结尾让模型在信息不足时先提澄清问题，避免瞎猜。
4. **重构前先锁行为基线（characterisation test）**：让 AI 先为现有代码生成捕捉当前实际行为（哪怕是 bug）的测试当安全网，重构后这套测试必须原样通过，比「重构后再跑测试」更稳。
5. **预设 Guard Clauses 防废话**：在提示词里预设分支——没给代码时输出 NO_CODE_PROVIDED 并索取；代码没问题时输出 NO_REFACTORING_NEEDED 并说明理由，不要硬改。

## 骨架（每段缺一不可）

1. 角色（Role）
2. 上下文（Context）：项目/模块、语言+版本+框架、这段代码做什么、已知痛点
3. 待重构代码
4. 硬约束（不可违反）
5. 重构目标（先锁行为基线）
6. 验收标准（必填，含行为基线测试）
7. 输出格式
8. 守卫（Guard Clauses）

## 三档策略（何时用）

- **A 模糊**（仅"重构这段代码"）：只在用户明确要快速粗改时给，否则不要给。
- **B 结构化**（目标 + 约束 + 输出格式）：**日常默认给这档**。
- **C 上下文 + 验收标准**（B + 业务规则 + 可验证用例）：**关键或高风险重构必给这档**。

## 何时降档 / 不适用

- **简单改动**（重命名、抽常量、格式化、明显的一行修复）：A 档或直接做，不要套重模板。
- **纯格式化 / 风格**：交给 formatter（gofmt、black/ruff、prettier、clang-format），不要用模型重写。
- **接口重设计 / 行为变更**：不是重构——先走需求与设计评审，本技能「行为等价」的前提不成立。
- **非代码任务**（写文档、解释代码、补测试）：按对应任务给提示词，不要套重构模板。

## 常见错误提示词（反例 → 修正）

| 反例 | 为什么错 | 修正 |
|---|---|---|
| 「优化一下这段代码」 | 无目标、无约束，只能得到「能跑」的改写 | 补目标 + 硬约束 + 验收标准（B/C 档） |
| 「保持行为完全不变」（仅此一句） | 不可验证 | 换成可运行测试命令或「输入 → 期望输出」用例 |
| 「顺便把测试也改一下」 | 改测试迁就代码 = 掩盖行为变更 | 测试只允许新增基线用例，不允许改既有断言 |
| 「把整个项目重构一遍」 | 范围过大，无法评审与定位失败 | 按工作流 3 分批，每批独立验收 |
| 「用你熟悉的最佳实践重写」 | 引入无依据的架构改动与依赖 | 限定「只改结构不改行为」，禁止新增依赖 |
| 「给出重构后的完整代码」（代码 500+ 行） | 输出易被截断、大段幻觉 | 要求 unified diff + 改动清单 |

## 默认模板（主用）

```text
你是资深 {语言/框架} 专家，专注在不改变行为的前提下做重构。

【前置判断】
- 未提供代码：直接输出 NO_CODE_PROVIDED 并索取代码；
- 代码无明显可改进处：输出 NO_REFACTORING_NEEDED，说明理由，不要硬改。

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
0. 先为现有行为生成/补齐「行为基线测试」，捕捉当前实际行为（哪怕是 bug）作为安全网；
1. {消除重复 / 降低圈复杂度 / 拆分长函数 / 提取子方法 / 语义化命名}
2. 用具名常量或枚举替换魔法数字/字符串。

【验收标准（必填，用可验证的用例/命令表达）】
重构后（含上面生成的行为基线测试）必须全部通过：
- 测试命令：{例如 pytest / npm test / mvn test / go test ./... / cargo test}
- 用例：{给定输入 → 期望输出}
- 若无法运行测试：给出等价验证步骤（命令 + 预期输出，或可手工核对的检查清单）

【输出格式】
1. 问题清单：问题 → 严重度(高/中/低) → 位置；
2. 统一 diff（声明基线文件）或完整文件，二选一；
3. 表格：每处改动 → 改了什么 → 为什么 → 影响面；
4. 风险提示：哪些改动有兼容性风险。

如有信息不足，先提问再动手。
```

## 输出格式选项

在【输出格式】里按场景显式选择，不要留给模型自由发挥：

- **unified diff**（默认推荐）：要求声明 diff 基线（文件路径 + commit/分支），每处改动可定位、便于评审与回滚。
- **完整文件**：文件较小（< 200 行）或需要直接替换时用；要求给出完整可运行文件并标注文件名。
- **分步 patch**：大文件 / 多文件重构时按批次给 patch，每批附各自的验收命令。
- **改动清单（必选）**：无论哪种格式，都要求「每处改动 → 改了什么 → 为什么 → 影响面」表格。
- **生成后自检**：把提示词存成文件，运行 `python3 scripts/check_prompt.py <file>`，检查八段是否齐全、验收是否可验证、验收命令与语言是否匹配（自动识别，或 `--lang go` 显式指定），并拦截「顺便改测试」「整体重写」等典型反模式。中英文提示词都支持；团队门禁可用 `--strict`（警告即失败），缺失段落用 `--skeleton` 直接打印可填骨架。

生成、自检、批量与 pre-commit 集成：`scripts/compose_prompt.py --code <文件>` 一键生成（同时提供 `--rule` / `--case` 时直接生成 C 档，`--require-c-tier` 强制该组合）；`scripts/check_prompt.py <file>` 自检（`--strict` / `--skeleton` / `--fix` / `--json` / `--format github` / `--changed BASE`）；`scripts/check_prompt.py prompts/ --strict` 批量检查目录；`.pre-commit-hooks.yaml` 通过 `pyproject.toml` 安装的 `code-refactor-prompt-check` console script 接入 pre-commit。详见 README。

## 迭代修复（应用后验证）

1. 应用前确保已提交或已备份；按 diff 逐块应用。
2. 跑【验收标准】里的命令，收集**完整**失败输出。
3. 回喂时只给：失败用例 + 相关代码片段 + 已做改动摘要；要求「只做修复失败的最小改动」。
4. 连续两轮仍失败 → 回滚该批，缩小重构步长；不要把失败结果反复重贴全部代码。
5. 完整流程见 `references/workflows.md` 工作流 4。

## 专项变体

性能优化、代码坏味道、大文件/长函数拆分、安全加固、现代化升级、分语言定制（速查）、行为基线测试、守卫（Guard Clauses）、可测试性改造、模块化/解耦、SOLID 原则、设计模式应用、技术债/遗留系统，见 `references/specialized-prompts.md`；分语言完整版见 `references/language-specific.md`；端到端流程（评审驱动、遗留代码基线、多文件分批、迭代修复）见 `references/workflows.md`；英文主模板见 `references/template-en.md`；实战样例见 `examples/`；除速查表外的每个变体都带可验证的验收锚点（CI 分级审计）；落地检查清单（发提示词前 / 应用前 / 应用后 / 合并前）见 `references/checklists.md`；依据与出处见 `references/sources.md`（`scripts/check_sources.py` 可离线 / 在线巡检链接）。