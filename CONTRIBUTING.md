# 贡献指南

本仓库是一份可复用的重构提示词技能 + 配套工具链。改动前请先在本地跑通一键门禁。

## 环境

- Python 3.9+、Git
- 可选工具链：Go / Rust / Node.js 24 / .NET SDK（仅 `--full` 执行样例时需要）
- 可选：pre-commit（验证提交钩子时使用）

## 一键本地门禁

```bash
python3 scripts/run_checks.py          # 结构校验 + 模板审计 + 工具链测试 + 出处离线检查
python3 scripts/run_checks.py --full   # 额外真实执行 examples/ 里的全部可执行样例
```

只列出步骤而不执行：`python3 scripts/run_checks.py --list`。

## 目录约定

- `SKILL.md`：主技能（八段骨架、三档策略、默认模板），frontmatter 含版本。
- `references/`：专项变体、分语言要点、工作流、检查清单、出处；变体必须有可验证的验收锚点。
- `examples/`：实战样例；可执行样例用 `<!-- verify:run -->` 与 `<!-- verify:file=NAME -->` 标记，CI 会真实执行。
- `scripts/`：检查器、生成器、出处巡检、一键门禁与回归测试。
- `.github/`：CI、发布、每周链接巡检与校验脚本（不随发布包分发）。

## 修改提示词资产

- **新增夹具**：放进 `scripts/fixtures/`，命名为 `good-*` / `bad-*`，并在 `validate_skill.py` 的必需文件与 CI 自测中登记。
- **新增专项变体**：编辑 `references/specialized-prompts.md`，保持 `## N. 标题` 编号与验收锚点；`audit_templates.py` 会自动审计。
- **新增可执行样例**：在 `examples/*.md` 中加入 `verify:run` 与 `verify:file` 标记，确保本机 `--full` 通过；CI 会用 `verify_examples.py --require-all` 实跑。
- **修改检查器**：同步更新 `scripts/tests/` 下的回归测试与 README 中的用例数声明。

## 版本与发布（校验脚本会强制）

1. 同步版本号：`SKILL.md` 的 `metadata.version`、`pyproject.toml` 的 `version`、两个 README 的 `rev: vX.Y.Z` 与 Action 示例 `@vX.Y.Z`、`.pre-commit-hooks.yaml` 注释。
2. 在 `CHANGELOG.md` 增加对应版本段；README 声称的测试数必须等于 `scripts/tests/` 中实际的 `def test_` 数量。
3. 提交并推送 `main`，然后打标签并推送：`git tag -a vX.Y.Z -m "..." && git push origin vX.Y.Z`。
4. 标签推送会触发 Release workflow：校验、审计、测试、实跑样例、pre-commit 端到端、打包并创建 GitHub Release。

发布流程与门禁细节见 [README.md](README.md) 的「CI 与发布」。
