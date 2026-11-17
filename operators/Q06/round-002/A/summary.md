# 第六题 PadV3Grad／round-002／A

任务 `Q06-R002-A-OFFICIAL-COMPARABILITY-20261117`；执行者 A。准确起点 `cb4016d4406b245461f57998f693d7feacc0e297`，独立分支 `q06/r002/a-official-comparability`。P/PL/F/L 都是指定既有冻结实现，无算子修改；P 和 F 仅为任务局部对照，团队共同基线尚未批准。

**有界比较已完成；共同基线资格未结案。** 本轮完成 4 次原样官方运行，全部结果与排名观察保留。准确代码、38文件模板、原生 valid/revision、公开用例 ID、未舍入 TBest 和精确 submission_id 总分绑定已逐任务核对。公开协议允许比较这些记录时点的官方总分；不要求取得隐藏输入、隐藏耗时或后台实现才无限继续提交。

## 统一实验表

| 实验编号 | 假设与改动 | 准确代码版本 | 来源／官方任务 | 官方状态与总分 | 相对 P 局部对照 | 结论 | 证据 |
|---|---|---|---|---|---|---|---|
| Q06-R002-A-E001（P） | 在当前观察窗口取得准确任务绑定的 P 局部对照；保留上轮任务身份和归档结果；无代码修改 | `d0b680d59d1dfa088dd24fff5d3128feb2758251bcd8d3b34b39635bad68f949` | 官方提交；1381855 / `6afc3b166bd0f9be377f93c5` | Pass；valid=true；29.35 | +0.00 分 | verified：仅观察分比较 | [结果](artifacts/official/6afc3b166bd0f9be377f93c5.json)／[38文件](artifacts/manifests/6afc3b166bd0f9be377f93c5.json) |
| Q06-R002-A-E002（PL） | 独立恢复既有 PL，补齐 valid/revision、精确源码/公开标尺和排行绑定，比较本轮 P/PL 官方观察分；无代码修改 | `988e491ec2d8d758adac5caa0e304cc81cb500ade732aadc9427fa1254267d41` | 官方提交；1381889 / `6afc3bd16bd0f9be3780fbd0` | Pass；valid=true；29.36 | +0.01 分 | verified：仅观察分比较 | [结果](artifacts/official/6afc3bd16bd0f9be3780fbd0.json)／[38文件](artifacts/manifests/6afc3bd16bd0f9be3780fbd0.json) |
| Q06-R002-A-E003（F） | 为四臂比较取得朋友原版 F 的当前公开协议、原生有效性和准确任务总分；无代码修改 | `700af8da3ef6679f48ebf8bbfa9d2f145d9357e9b6fd2e4f288542c662a1969b` | 官方提交；1381929 / `6afc3ca46bd0f9be3782644c` | Pass；valid=true；28.98 | -0.37 分 | verified：仅观察分比较 | [结果](artifacts/official/6afc3ca46bd0f9be3782644c.json)／[38文件](artifacts/manifests/6afc3ca46bd0f9be3782644c.json) |
| Q06-R002-A-E004（L） | 为四臂比较取得既有 L 的当前公开协议、原生有效性和准确任务总分；无代码修改 | `d3174f99553a7ba700a726f77370e1e287e1084cd2bc9768d4bbbcbd66ce9d24` | 官方提交；1381993 / `6afc3d976bd0f9be378432b7` | Pass；valid=true；28.77 | -0.58 分 | verified：仅观察分比较 | [结果](artifacts/official/6afc3d976bd0f9be378432b7.json)／[38文件](artifacts/manifests/6afc3d976bd0f9be378432b7.json) |

全部原始 result（含 Hidden/null）、theory_score 与准确任务绑定总分见 [experiments.jsonl](experiments.jsonl)。theory_score=0 不替代排行总分，分数差不换算算子加速比。重复读取同一任务不计新运行。

## P/PL 与四臂结果

- PL − P：0.01 分；verified，仅本轮记录总分差。
- L − F：-0.21 分；verified，仅本轮记录总分差。
- P − F：0.37 分；verified，仅本轮记录总分差。
- PL − F：0.38 分；verified，仅本轮记录总分差。

本轮最高有效单次观察是 **PL，29.36 分，任务 1381889**。 本次 PL 比 P 单次观察高 0.01 分；没有稳定性或因果收益证据，不能仅因此替换工作 P，也不能批准共同基线。建议保留 P 工作起点，并同时留存 PL 供中央结合数值门裁决。 **稳定最佳未判定，团队共同基线未批准。** 四臂的官方观察可比较；这些单次差不能证明组合收益可叠加、稳定退化/提升或某条优化的因果贡献。见 [有界比较审计](artifacts/audit/bounded_comparison.json)。

## 已补齐的口径与发现

- **verified：四臂源码身份。** 四份七源码树与任务单一致，152个文件均有哈希，31个不可编辑模板相同；reference SHA为 `1542d63e602aa3aaa60242e91ea0d6a8ac038bab788c6898dc4777557f040ed3`。原ZIP SHA和固定Git出处见 [恢复审计](artifacts/audit/restoration_identity.json)。
- **verified：旧 B 证据的具体缺项已用自身任务补齐。** 旧档案只有显示精度 TBest，缺原生 valid、revision、testcase ID，排名文本本身不带 submission_id；本轮保留旧档案的原身份与局限，分别取得 A 可直接核对的新任务与精确排名行。见 [历史审计](artifacts/audit/historical_evidence_audit.json)。
- **verified：当前公开协议刷新。** 当前题目仍 CANN9.1.0、revision0、score_mode1、iterations5、latest；官方默认评分说明 SHA 与上轮相同，TBest 动态变化。公式与赛事权重属于不同层次，沿用有来源的上轮证据并记录本轮刷新。见 [规则报告](artifacts/rules/report.md)。
- **verified：历史任务 GET 的标尺会变化。** 旧 P 的源码、实际 time 和状态保持一致，但本轮 GET 的五个公开 best_time 中四项相对上轮归档发生变化（例如 3.75 → 3.7466666666666666、3.73 → 3.67）。这是历史响应的动态标尺刷新，不是重新评测，也不把旧29.67混入本轮。差异分析在 E001 提交后才发现；提交前补测 P 的已知理由仍是当前精确排行缺行。见 [历史P刷新差异](artifacts/audit/historical_P_refresh_changes.json)。
- **verified：同响应的观察总分与公开标尺。** 每个精确排行摘取同时保留该响应五个公开 testcase ID、未舍入 tbest、type 和源摘要；隐藏45项标尺未提取。HTTP原字节SHA与本机保存JSON字节SHA分开标注，避免误认同一摘要。所有重复排名观察均保存。
- **verified：比较范围有界。** 同公开协议下的原始官方分数及其算术差可以比较，所有观测时刻均保存；没有把隐藏标尺恒定或后台实现披露作为前置条件，也没有从五个公开点重建隐藏45点。
- **invalid：沿用 C 旧 E004 的真实原依赖 reference 已验证结论。** 固定 C 脚本用 float32 替代 bfloat16 依赖，使原 reference 的 FP32 输入误入 torch.bfloat16 转换分支；摘要又硬编码零结果。旧四次运行确实在替代依赖条件下记录零输出，不据此指称记录造假；它们不能认证真实依赖路径，更不能据此声称真实 NPU 已失败。详见规则报告中的固定提交与行号。
- **pending：C 数值门。** 需要真实 numpy/torch/ml_dtypes 依赖、原 SHA 的 reference、原输入字节及实际输出；随后取得同一合法输入在冻结实现上的 NPU 输出及调用/分支证据，按真实精度标准裁决。此具体未关闭门阻止无条件基线批准。A 不重做 C 的数值修复，任何后续修复必须新快照、新官方结果再交中央审议。

## 计划、历史与未完成项

先检查上轮 P（Q06-R001-A-E003／1369815，归档29.67），详情仍有效 Pass；当前排名扫描未返回它的精确任务行。提交前将最初“复用P+补PL/F/L”方案改为当前窗口四臂原样复测，初稿、冻结方案及缺行证据均保留在 artifacts/plan 与 artifacts/reuse/P。缺行不解释为0分，旧分数不覆盖。本轮没有复测 exp5/u64src，也没有新增组合优化。

- 历史记录保留原 experiment_id、round_id、task_id，见 [历史引用](artifacts/historical_references.json)；B 旧 PL 29.20、F/L/P旧观察不冒充本轮数据。
- 官方没有给实际完成时间，所以 evaluated_at=null；提交时间、请求时间、终态观察时间、排名观察时间分别保留。冻结与请求先后顺序依据客户端记录；服务器 create_time 与客户端时间存在数秒偏移，不用它推断完成时刻或改写操作顺序。
- 精确计时/预热/同步/聚合、硬件与负载、退化阈值、公式边界及隐藏TBest固定性仍未知。这些限制稳定性能归因，不阻止本轮已满足条件的有界总分比较；不自定门槛、不为这些未知无限重提。
- 模板 -e 仅首个 seed42 FP32 样例；旧 -u fixture 和 README 静态不一致。首次交接时没有云端编译、全精度、云性能或 Profiler 运行声明；之后用户恢复连接，本轮补充 CANNLab 原样构建，结果见末节。没有执行云端 NPU 样例、精度、性能或 Profiler 测试，平台没提供的独立官方日志不造。
- 下一步交中央保留选择并等待 C 的真实 reference/NPU 裁决；B 可继续其缓存可达性/成本路线。P/PL冻结双臂已由A完成，其他路线无需为本次结论重复同一提交。

## 材料位置

本目录提供 summary.md、experiments.jsonl、四组七源码、每任务38文件清单、请求与回执、官方结果/精确排行摘取、前后配置、规则和审计及恢复/校验工具。完整未筛选响应留在机器A `work/Q06/round-002/A/raw_official/`；公开包剔除账号、无关排行及31官方模板/样例/测试正文，指标保持原值。恢复完整工程方法见 [README](README.md)。发布提交只标识交接包，实际测试版本以七源码和38文件身份为准。

发布前独立复核已通过：[原始响应与公开材料逐项对照](artifacts/audit/root_raw_to_published_audit.json)核验四次实际返回指标、排行任务、公开标尺及152个源码文件；[四版本端到端恢复](artifacts/audit/root_restoration_audit.json)分别将包内七源码与匹配官方模板恢复到新目录，四次均通过38文件校验。这些是交接一致性检查，不是新增官方评测或本地NPU测试。

## 用户追问后的 CANNLab 补查

此前未执行云端构建的原因是执行者将云环境步骤视为可选，本轮只做冻结版本官方复测；不是当时已经验证了云端不可用。用户追问后，2026-11-17 12:18:23 UTC 实测项目配置的本机 SSH 隧道 127.0.0.1:31640 返回 WinError 10061，另一次 SSH 探测20秒超时。网页工具未能完成环境页导航，历史 issue 不能用于推断当前实例状态。

该次补查时，四份冻结工程及顺序构建记录脚本已准备，但尚未上传、未执行编译，因此当时 CANNLab 构建为 **pending／未执行**，编译退出码及日志均为 null；这属于接入受阻，不是构建失败。见 [当时补查记录](artifacts/cannlab/status_before_connection_restored.json)及[连接探测](artifacts/cannlab/connection_probe.json)。随后用户恢复既有连接，实际构建结果见下一节。既有四条官方结果、总分比较及 C 数值门保持原结论，未新增官方实验。

## 连接恢复后的 CANNLab 实际构建

以下构建在四次官方评测之后补做，使用原样冻结源码和实际 CANN 环境；没有新增官方提交，也没有用云数据改写官方分数。先前未执行记录保留为历史状态。

| 版本 | 云构建退出码 | 构建结果 | 38文件前后身份 | 证据 |
|---|---:|---|---|---|
| P | 0 | 通过；非空安装包及内核目标文件已生成 | 全部一致 | [日志](artifacts/cannlab/completed/P.log)／[记录](artifacts/cannlab/completed/P.json) |
| PL | 0 | 通过；非空安装包及内核目标文件已生成 | 全部一致 | [日志](artifacts/cannlab/completed/PL.log)／[记录](artifacts/cannlab/completed/PL.json) |
| F | 0 | 通过；非空安装包及内核目标文件已生成 | 全部一致 | [日志](artifacts/cannlab/completed/F.log)／[记录](artifacts/cannlab/completed/F.json) |
| L | 0 | 通过；非空安装包及内核目标文件已生成 | 全部一致 | [日志](artifacts/cannlab/completed/L.log)／[记录](artifacts/cannlab/completed/L.json) |

真实命令为各独立工程内 `bash build.sh -j4`，默认目标 ascend910b；CMake 安装位置为各工程自身 build/。实际工具链、版本文件、环境路径和 NPU 只读快照见 [云环境记录](artifacts/cannlab/completed/environment.json)。日志中的构建时长不是算子耗时。`source_tree_sha256` 表示七源码树，完整38文件身份另以逐文件SHA映射记录。

初次 SCP 传输认证失败、随后一次 SSH 传输连接关闭；这些发生在编译之前，记录保留，不计作构建失败。已就绪隧道下的后续传输成功，远端验证源码包SHA后才启动构建。

本次未运行 `-e` 单样例、`-u`、全量精度、性能测试或 Profiler；C 的真实依赖 reference 与 NPU 数值门仍未关闭。官方四任务与分数比较保持原结论。

四臂每臂生成1个安装包与4个内核目标文件，共20个产物已下载到本机并重新计算大小和SHA256，全部与远端构建记录吻合：[产物核验](artifacts/cannlab/compiled_output_audit.json)／[编译产物归档](artifacts/cannlab/compiled_artifacts.tar.gz)。原样保留的四份日志均有同一条自动生成代码警告：`autogen/aclnn_pad_v3_grad.cpp:236` 的 `static char *modeOptionalDef = "reflect";` 触发 `-Wwrite-strings`；未导致失败，没有为消除警告修改冻结源码。

[独立云构建审计](artifacts/cannlab/independent_cloud_audit.json)再次复核152个源码、四个七源码树与官方任务绑定、四份日志及20个下载产物的大小与SHA256，全部通过。此检查仅证明构建证据一致，不证明NPU运行正确性。
