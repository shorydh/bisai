# 第六题 PadV3Grad／round-001／A

任务：`Q06-R001-A-BASELINE-20261117`。任务类型：共同基线资格核验、官方复测、独立恢复 B r6。执行者 A；起点为 A 固定提交 `562db68e0193c407dd714f5f071800911f378190`，仅单独读取 B 固定提交 `8e245dab91700555bd619e95c70fa780305b1b37`，未合并其分支。没有修改三份冻结算子，也没有更新中央基线。

**结论：共同基线和稳定最佳仍未判定。** 本轮完成 3 次原样官方复测，全部结果及重复观测逐项保留；分数为 exp5：14.73（1369690）；u64src：15.53（1369742）；r6：29.67（1369815）。E001 的 exp5 仅作为任务指定局部对照。源码、模板、公开 testcase/TBest 与可见配置能逐项核验，但完整计时定义、退化要求及隐藏 TBest 标尺仍有证据边界，不能凭单次最高分认定团队最佳或全输入泛化已通过。

## 统一实验表

| 实验 | 假设与改动 | 准确源码 | 测量来源 / 官方任务 | 官方状态及实际指标 | 与 E001 局部对照 | 结论 | 证据 |
|---|---|---|---|---|---|---|---|
| Q06-R001-A-E001 (exp5) | 原样 A exp5 能否以当前官方口径有效通过并提供本轮局部对照；无代码修改 | `11bb802ef346fd11a4c9d157e0bb1b56591fd125a6fed93c4992b8cd3d5e4330` | 官方提交环境；1369690 / `6afb3b9e6bd0f9be37e9567e` | Pass；valid=true；总分=14.73 | +0.00 分，仅描述性观测 | 官方身份/状态已核验；共同基线资格 pending | [结果](artifacts/official/6afb3b9e6bd0f9be37e9567e.json) / [38文件清单](artifacts/manifests/6afb3b9e6bd0f9be37e9567e.json) |
| Q06-R001-A-E002 (u64src) | 原样 A u64src 能否以与 E001 相同的可见官方口径复现，并核对归档 +0.77 是否只是单次观测；无代码修改 | `119a5a5b9e4c1589e595a391c8867e75eb5901e192183c4ac5ad7a2a90ea1b86` | 官方提交环境；1369742 / `6afb3c6f6bd0f9be37eabd76` | Pass；valid=true；总分=15.53 | +0.80 分，仅描述性观测 | 官方身份/状态已核验；共同基线资格 pending | [结果](artifacts/official/6afb3c6f6bd0f9be37eabd76.json) / [38文件清单](artifacts/manifests/6afb3c6f6bd0f9be37eabd76.json) |
| Q06-R001-A-E003 (r6) | 从 B 固定官方包独立恢复的 r6 能否在 A 授权官方入口有效运行，并补齐跨包源码、模板与可见评分标尺的比较证据；无代码修改 | `d0b680d59d1dfa088dd24fff5d3128feb2758251bcd8d3b34b39635bad68f949` | 官方提交环境；1369815 / `6afb3e276bd0f9be37ed9f96` | Pass；valid=true；总分=29.67 | +14.94 分，仅描述性观测 | 官方身份/状态已核验；共同基线资格 pending | [结果](artifacts/official/6afb3e276bd0f9be37ed9f96.json) / [38文件清单](artifacts/manifests/6afb3e276bd0f9be37ed9f96.json) |

`official_metrics` 保留官方实际返回的 theory_score、全部 result（含 Hidden/null）、总用例数及准确绑定排行总分；`theory_score=0` 不替代排行总分。相同任务的多份引用不算多次复测。原始数值和逐项可比条件见 [experiments.jsonl](experiments.jsonl)。

## 证据与规则边界

- **verified：准确恢复。** exp5、u64src、r6 各 38 文件，三份七源码 SHA256 均符合任务单；B `1367774.zip` SHA256 为 `18679dad71f9ea7723ca524599b0d9363861aeadf8f8032202f6391199a5a85a`。31 个 readonly 模板文件逐一与 A manifest 一致。本轮官方回读的全部 38 文件亦一致。见 [恢复审计](artifacts/audit/restoration_identity.json) 和每次 verification.json。
- **verified：当前可见官方口径一致。** 六份评测前后配置相同、31 个模板文件相同、五个公开 testcase ID/type/未舍入的 TBest 数值 相同，114 个官方文件均对应仍未修改的冻结工程。见 [独立比较审计](artifacts/audit/official_comparability.json)。这是可见条件的一致性，不等于隐藏标尺和完整计时实现已获证明。
- **verified：配置按实际代码。** A 的 `PADV3_INFER_FROM_PADDINGS`、`PADV3_TILING_USE_OUT_SHAPE` 实际默认均为 0；冻结文件内未发现 `-D` 覆盖，不按过时注释当作 1。r6 原样恢复，未移植 A 配置。见 [配置及入口审计](artifacts/audit/config_and_test_entrypoints.json)。
- **verified／pending：当前官方规范。** CANN 9.1.0、revision=0、score_mode=1、iterations=5、ranking_submission_mode=latest 与题面精度要求均按本轮获取证据记录。平台公开评分文案生成器给出默认计分公式及动态 TBest；赛事正文与平台默认文案的层次、适用性及未确认事项分别写在 [规则审计](artifacts/rules/report.md)，不能把前端默认文字冒充已核实的后台计时实现。
- **verified：官方终态与有效性。** 每个新任务均记录 status、valid、revision、公开用例及 Hidden 条目、任务号与七源码/38文件绑定。Pass 是该次官方返回的有效状态，未读取隐藏输入，也不扩张为所有规格边界已独立验证。
- **pending：稳定性能及正式基线资格。** 仅在 JSONL 中列出的可见条件全部一致、双方有效 Pass 且总分精确绑定时，记录描述性总分差。动态 TBest、未披露的隐藏标尺、硬件/负载、完整计时统计与退化门槛限制跨时段外推。没有把分数差换算为算子加速比，也没有自行提出精度放宽规则。
- **invalid：把模板单测或模型 PASS 当全量精度证明。** README 对 `-u` 默认跳过内层的描述与实际脚本/fixture 不一致；旧 fixture 的成员和 tilingKey 与实现存在静态不兼容。该项是代码审计发现，未实际编译则不声称 Compile Error。`-e` 仅首个 seed=42 的 FP32 样例，sample.py 的 np.isclose 与允许 bad 数仅说明该样例。没有运行或引用 A 模型 SUMMARY PASS 作为官方验收。

## 历史身份、当前选择与下一步

历史 A exp5（1367540 / 14.74）、A u64src（1367599 / 15.51）及 B r6（1367629 / 29.59、1367774 / 29.39）保留 `round_id=历史盘点` 的身份，在 [历史引用](artifacts/historical_references.json) 引用，不冒充本轮新增观测。A 历史 +0.77 只是对应两任务保存的总分差。A exp5 与 B 朋友原版（历史任务 1148765、同期对照 1367558；七源码 `700af8da3ef6679f48ebf8bbfa9d2f145d9357e9b6fd2e4f288542c662a1969b`）的历史基线身份不合并；团队共同基线未批准。

当前最高观察分数只能作为本轮描述性排序，**稳定最佳和共同基线均未判定**。r6 在本轮三个有效任务中取得最高单次总分 29.67，可建议中央优先审查为共同基线候选；这仍需结合 B 的后续组合结果及 C 的数值反例/边界审计。本轮不重复 B 的组合实验，不扩展 C 的数值修复。中央需要补齐或明确接受计时/退化/动态评分边界后再审批基线。

## 异常、未完成项与材料位置

- 当前账号读取 B 历史任务详情返回 403“无权查看他人的提交记录”，见 [原错误](artifacts/audit/b_historical_access_error.json)。因此本轮通过 B 已发布的准确官方包恢复，并以 A 的新官方任务独立复现，没有把 B 的旧任务重新计数。
- 官方返回 `create_time` 为提交时间，未提供实际完成时间，所有 `evaluated_at=null`。另存请求时间、官方提交时间与终态观察时间；B 旧包把提交时间放入 evaluated_at 的做法不沿用。
- 正式计时统计、硬件/驱动/共享负载、完整退化要求未证实的部分保持 null/pending，具体来源与未获证据见规则报告。没有虚构预热/中位数、没有推算隐藏耗时/精度或 TBest。
- 没有本机 NPU 编译、精度、性能或 Profiler 运行声明；本轮编译及真机验收来自准确对应的官方任务。平台未返回独立构建日志的，不造日志。
- 本目录 `artifacts/` 提供七源码快照、38文件清单、提交输入、无改动记录、官方摘取、精确排名行、配置和审计。完整未筛选响应留在机器 A 的 `work/Q06/round-001/A/raw_official/`；公开包剔除其他参赛者展示资料，不更改实际指标。
- 恢复全部 38 文件需要匹配的官方模板，见 [README](README.md)；31 个官方不可编辑模板/样例/测试文件仅保留哈希，没有重新发布。校验报告为交接一致性检查，不是新一轮官方评测。
