# 出处与依据

本技能的方法论沉淀自以下公开资料（检索与核验时间：2026-10）。按五类整理，每条附「可借鉴手法」。

## 一、核心实验与完整工作流

### 1. 三种提示词策略对代码重构质量的影响（对照实验报告）
- 链接：https://grapecity.csdn.net/6a8ea3e1662f9a54cba0a71a.html
- 说明：同一段 Java 订单类，用 A（模糊）/ B（结构化）/ C（上下文＋验收标准）三档各跑 3 次的对照实验。
- 可借鉴：结论「信息密度决定重构质量上限」；把「保持行为不变」落到可验证测试用例，是与「能跑」拉开差距的关键。

### 2. AI 辅助代码审查与重构的完整工作流（Python 案例）
- 链接：https://grapecity.csdn.net/6a91ac212b83d06f0ec71b6e.html
- 说明：Codex 实战，演示「先审查出分级问题清单 → 再重构」的两步流水线。
- 可借鉴：审查阶段要求「按严重程度分级＋给行号」；重构阶段锁死「保持对外函数签名不变」，再叠加 dataclass／缓存／类型注解／异常处理。

## 二、结构化提示词合集（GitHub 开源）

### 3. flickleafy/prompt-engineering-models · Refactoring Prompts Collection
- 链接：https://github.com/flickleafy/prompt-engineering-models/tree/main/refactoring
- 说明：14 类重构提示词，统一「角色／上下文／分析说明／严重度／风险／结构化输出」骨架。
- 可借鉴：为每个问题标注严重度（🔴🟡🔵）与影响分；强制给出 before/after 与风险；要求分阶段路线图。

### 4. jgamblin/PGP（Pretty Good Prompts）· Code Refactoring
- 链接：https://github.com/jgamblin/PGP （文件：generic/code-refactoring.md）
- 说明：面向 Codex/Claude/ChatGPT/Copilot/Agent 的可直接粘贴提示词集。
- 可借鉴：Guard Clauses（NO_CODE_PROVIDED / NO_REFACTORING_NEEDED）与 Quick Context Checklist；按目标拆成单一粒度提示（Extract Functions／Reduce Complexity 圈复杂度 <10／Improve Naming／Add Error Handling／Remove Duplication）。

### 5. keploy/engineering-prompts
- 链接：https://github.com/keploy/engineering-prompts
- 说明：按领域组织的 AI 提示链合集（重构、CI/CD、数据库、安全等 17 个域）。
- 可借鉴：「prompt chain」思路——多步任务拆成链式提示，先建上下文再执行。

### 6. Pwd9000-ML/GitHub-Copilot-Bootcamp · Week4 Prompts
- 链接：https://github.com/Pwd9000-ML/GitHub-Copilot-Bootcamp （文件：Workshops/Week4/5-Week4-Prompts.md）
- 说明：重构、质量、安全、伦理、评审、组合 6 类训练提示词。
- 可借鉴：「行为基线测试（characterisation test）」——重构前先让 AI 生成捕捉当前行为（含 bug）的测试做安全网；以及「先用测试锁行为，再增量重构」的顺序。

## 三、官方资料

### 7. Amazon Nova Prompt Examples · Code Refactoring
- 链接：https://aws-samples.github.io/sample-amazon-nova-prompt-examples/prompts/software_engineering/code_refactoring/example/
- 说明：官方「System Prompt（角色）＋ User Prompt（Context ＋ Task）」两段式模板。
- 可借鉴：结尾固定「Ask clarifying questions if needed」；任务里点名具体诉求，而非笼统说「优化一下」。

### 8. GitHub Blog · Copilot 代码评审 instructions files
- 链接：https://github.blog/ai-and-ml/github-copilot/unlocking-the-full-power-of-copilot-code-review-master-your-instructions-files/
- 说明：官方教你如何把评审规则写成可版本化、可复用的指令文件（例：TypeScript instructions.md）。
- 可借鉴：把评审／重构规则沉淀为指令文件（类 AGENTS.md / instructions.md），避免每次重复描述。

### 9. Microsoft Learn · GitHub Copilot 重构最佳实践
- 链接：https://learn.microsoft.com/zh-cn/training/modules/implement-code-improvements-using-github-copilot-tools/4-review-code-refactoring-scenarios
- 说明：官方重构场景与最佳实践（重复代码、大函数拆分等）。

## 四、代码评审 / Review 专用

### 10. baz-scm/awesome-reviewers（awesomereviewers.com）
- 链接：https://github.com/baz-scm/awesome-reviewers · https://awesomereviewers.com
- 说明：从生产开源项目真实评审意见提炼的「即用系统提示词」，一条指令＝规则＋为什么＋示例。
- 可借鉴：精简原子化的规则条格式；提供 index.json / llms.txt，可编程获取整库。

## 五、工具聚合与其他

### 11. adnanmokhtar/refract
- 链接：https://github.com/adnanmokhtar/refract
- 说明：「写一次 AI 配置，到处运行」的聚合层（148 commands / 88 agents / 115 skills / 23 packs），导出到 Claude Code、Cursor、Gemini CLI、Codex 等。
- 可借鉴：跨工具沉淀思路——同一套重构提示词多端复用。

### 12. ahicks92/llm-mod-refactoring-prompts
- 链接：https://github.com/ahicks92/llm-mod-refactoring-prompts
- 说明：面向「vibe coded 代码」做自动化重构的实验性提示词。
- 可借鉴：对随意拼凑、无测试的 AI 生成代码，如何做大范围安全改动的参考。

### 13. AI-Code-Tutorials · 提示词优化技巧·案例研究
- 链接：https://github.com/0xfnzero/AI-Code-Tutorials/blob/main/tutorials/09-%E6%8F%90%E7%A4%BA%E8%AF%8D%E4%BC%98%E5%8C%96%E6%8A%80%E5%B7%A7/05-%E6%A1%88%E4%BE%8B%E7%A0%94%E7%A9%B6.md
- 说明：组件拆分／性能优化／bug 排查的完整中文提示词范例。
- 可借鉴：「问题具体＋流程清晰＋结果验证＋经验总结」四要素。

## 继续深挖的检索词

在 GitHub／搜索引擎上可用下列关键词找到更多同类资源：
- "refactoring prompts" / "code review system prompt" / "prompt engineering models"
- "awesome-copilot / Awesome GitHub Copilot Customizations"（微软官方聚合仓）
- "Claude Code refactor CLAUDE.md"（约束多文件重构范围）
- "characterisation tests AI refactoring"（行为基线安全网）
