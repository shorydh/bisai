# PadV3Grad 历史盘点 A 交接包

发布复核（2026-11-16 23:58:22 +08:00；复核记录时间 `2026-11-16T15:58:22.845773+00:00`）：本次发布核验仅 GET 30 个已存官方任务，未新增代码或官方评测；30 个任务的状态、7 个提交源码、全部 38 个文件及 `result` 均与原归档一致。2026-11-16 原归档轮次曾原样重放 5 个已有版本，其任务与评测结果保留在下文。本次最新排名扫描未找到当前保留版本的任务 `6afb1ca86bd0f9be37b0b7cd`，`current_ranking_observation=null`。15.51、14.74 和差值 +0.77 仅代表原归档轮次已精确绑定任务的保存观测，不能称为发布时的当前榜单值。复核证据见 [recheck.json](artifacts/recheck/recheck.json)。

先读 [summary.md](summary.md)，再读取 [experiments.jsonl](experiments.jsonl)。本包包含 30 条官方任务、21 个 editable 代码版本，原始指标保持不变；公开材料是明确标注的摘取，不是完整原始响应的替代副本。

本目录的 `.gitattributes` 禁用 Git 换行归一化，以保留证据和源码的准确字节及 SHA256。

## 目录

- `artifacts/official/`：本题官方字段与 7 个提交文件内容的摘取。
- `artifacts/ranking/`：精确对应任务的排行行；保留总分等指标，删除无关个人/团队展示资料。
- `artifacts/code/<完整哈希>/`：21 份去重的 7 文件源码快照。
- `artifacts/manifests/`：每次任务全部 38 文件的原始 SHA256。
- `artifacts/submissions/`：2026-11-16 原归档轮次重放的 5 次提交的 payload、原始源文件字节、回执与核对记录。
- `artifacts/recheck/recheck.json`：本次发布前 GET 核验记录，保留任务逐项一致性与最新榜单观测缺口。
- `artifacts/diffs/`：相对实际历史父版本的源码差异。
- `artifacts/auxiliary/`：本题本地模型与历史日志，仅辅助说明。
- `artifacts/version_coverage.json`：全部已知完整本地版本与官方任务的对应审计。
- `publication-manifest.json`：本包文件清单与 SHA256；`validation.json` 是本地一致性检查结果，不是新评测。

## 验证

在本目录使用 Python 3.10 或更高版本执行标准库工具：

```sh
python -B tools/validate_handoff.py
```

工具检查固定字段、证据引用、任务与状态、指标、源码原文/哈希、排行任务绑定、单次总分差及版本覆盖。不进行新官方提交。

维护者审阅新的证据或说明修改后，使用 `python -B tools/validate_handoff.py --write-report --write-manifest` 更新校验报告和文件清单；普通接收者只需上面的只读校验命令。

## 恢复实际测试的完整项目

先按题目授权从 [官方入口](https://cannjudge.cn/public/ictcompetition/padv3grad) 获取原始工程模板；package 接口为 `https://cannjudge.cn/api/problems/6ad9ab403ff2fef7e80e2a1d/package`。本共享包不含 31 个不可编辑官方模板/样例/测试文件，仅保留其哈希。

```sh
python -B tools/restore_sources.py --submission 6afb1ca86bd0f9be37b0b7cd --template /path/to/official/project --output /path/to/new-restored-project
```

也可用 `--version <完整editable树哈希>`。输出目录必须不存在；工具先确认模板 31 文件哈希和提交 7 文件哈希，再恢复全部 38 文件并逐一校验。如果官方当前模板已改变，需要取得匹配的历史模板；不能用新模板冒充当时项目。

## 比较边界

正式比较只使用 CANNJudge 官方任务及准确绑定的排行榜总分。当前保留版本的归档总分 15.51、共同基线 14.74、差 0.77 为原归档轮次单次观测；本次最新排名扫描未找到该当前版本任务，不能据此称为发布时当前榜单值。该单次总分差不是统计显著性或加速比。旧总分与完成时刻缺失保持 null；隐藏 45 例不推算。构建/本地模型/云分析材料不升级为官方结果。

完整未筛选原响应和完整源码在机器 A 的原本地交接目录 `handoffs/06_PadV3Grad/历史盘点复核_20261116/A/` 留存。公开版没有登录会话、访问令牌、私人 Library 引用或其他算子的提交列表。
