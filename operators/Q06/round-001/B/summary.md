# 第六题 PadV3Grad／round-001／Agent B

任务：`Q06-R001-B-COMBINE-20261117`。用户授权的实验为F/P/L/PL四臂局部比较；团队共同基线由A/中央核验，本报告不设定或覆盖。交付分支：`q06/r001/b-r6-lastplan`，起点固定提交`8e245dab91700555bd619e95c70fa780305b1b37`。当前文件来自隔离工作目录，发布映射为`operators/Q06/round-001/B/`；精确发布commit见交付消息；该commit不写入自身文件以避免自引用。

| 实验编号 | 假设与改动 | 准确代码版本 | 测量来源 | 官方任务 | 官方状态／实际指标 | 比较与结论 | 证据 |
|---|---|---|---|---|---|---|---|
| B-HIST-1362811 | F，无代码修改／历史引用 | `700af8da3ef6` | 官方存档 | [1362811](https://cannjudge.cn/public/ictcompetition/padv3grad/submission/6afae80f6bd0f9be37477997) | Pass，28.61分 | 性能比较pending | [证据](artifacts/reporting/history/1362811.json) |
| B-HIST-1362890 | L，无代码修改／历史引用 | `d3174f99553a` | 官方存档 | [1362890](https://cannjudge.cn/public/ictcompetition/padv3grad/submission/6afae96e6bd0f9be374a1e96) | Pass，29.23分 | 性能比较pending | [证据](artifacts/reporting/history/1362890.json) |
| B-HIST-1364006 | L，无代码修改／历史引用 | `d3174f99553a` | 官方存档 | [1364006](https://cannjudge.cn/public/ictcompetition/padv3grad/submission/6afaf9e36bd0f9be3769c389) | Pass，28.84分 | 性能比较pending | [证据](artifacts/reporting/history/1364006.json) |
| B-HIST-1367558 | F，无代码修改／历史引用 | `700af8da3ef6` | 官方存档 | [1367558](https://cannjudge.cn/public/ictcompetition/padv3grad/submission/6afb1c176bd0f9be37af982a) | Pass，28.66分 | 性能比较pending | [证据](artifacts/reporting/history/1367558.json) |
| B-HIST-1367629 | P，无代码修改／历史引用 | `d0b680d59d1d` | 官方存档 | [1367629](https://cannjudge.cn/public/ictcompetition/padv3grad/submission/6afb1d006bd0f9be37b15ed8) | Pass，29.59分 | 性能比较pending | [证据](artifacts/reporting/history/1367629.json) |
| B-HIST-1367774 | P，无代码修改／历史引用 | `d0b680d59d1d` | 官方存档 | [1367774](https://cannjudge.cn/public/ictcompetition/padv3grad/submission/6afb1ec66bd0f9be37b4e0f3) | Pass，29.39分 | 性能比较pending | [证据](artifacts/reporting/history/1367774.json) |
| Q06-R001-B-E001 | P上适配L末轴计划缓存，仅两处主头改动 | `988e491ec2d8` | 官方结果已存档 | [1369663](https://cannjudge.cn/public/ictcompetition/padv3grad/submission/6afb3b076bd0f9be37e856f6) | Pass；总分29.2 | pending，提交源码身份已核验 | [候选身份](artifacts/workflow/implementation/candidate-identity.json)／[官方结果](artifacts/official/1369663.json) |

## 已验证与待验证

- 已验证：F/P/L完整38文件从指定官方ZIP恢复，ZIP与七源码一致；31个非编辑模板文件和所有37个非主头文件相同。固定提交ZIP的Git blob核对见[远端身份](artifacts/fixed-commit-zip-checks.json)。
- 已验证：F两次28.61/28.66，P两次29.59/29.39，L两次29.23/28.84，全部历史观察保留；它们是历史引用，不能重复计为本轮新测。
- 已冻结PL：七源码`988e491ec2d8d758adac5caa0e304cc81cb500ade732aadc9427fa1254267d41`，仅主头两处移植，其余37文件保持P。
- 官方任务[1369663](https://cannjudge.cn/public/ictcompetition/padv3grad/submission/6afb3b076bd0f9be37e856f6)返回Pass，实际总分29.2。下载工程全部38文件与冻结PL一致，ZIP及源码身份已核验。
- 待验证：实际官方设备/计时/完整评分/退化规则及跨历史版本一致性，单次得分波动与PL四臂正式比较。相同模板只证明工程一致，不证明全部性能协议相同。
- 辅助源码规划诊断PASS：[359组形状、76030核区间](artifacts/workflow/implementation/planner-result.json)，其中按Host公式生成的区间26866、人工边界区间49164；缓存活动32196区间，快路拒绝2340。验证顺序/偏移/回退复位及调用间padding变化，seed=20261117。device_execution=false，未执行设备Vector数学或half算术，不能冒充全量NPU精度；实际栈/寄存器压力仍未知。

辅助Host可达性枚举[43008项](artifacts/workflow/implementation/host-reachability.json)，0违反条件结论。条件为If coreNum>=ceil(totalOutput/32), totalInput<=8192,totalOutput<=256 and dtype bytes2/4, Host blockFactor<=32, so width32 count>width cache never activates; width33 guard always false. 这是假设核数下的源码公式检查；官方实际核数未知，不能把人工count>width范围当作官方必经路径，也不能据此否定全部缓存价值。



本次官方公开耗时（按测试点1—5）：6.67μs、6.93μs、7.00μs、8.35μs、6.93μs；仅为公开点指标，不推算45个隐藏点或整体加速比。

## 描述性分数观察

以下仅为PL总分减历史总分的算术差，不是已验证的性能收益，也不是算子加速比。

| 局部对照任务 | 臂／得分 | PL得分 | 分数差（点） |
|---|---|---|---|
| 1362811 | F／28.61 | 29.20 | +0.59 |
| 1362890 | L／29.23 | 29.20 | -0.03 |
| 1364006 | L／28.84 | 29.20 | +0.36 |
| 1367558 | F／28.66 | 29.20 | +0.54 |
| 1367629 | P／29.59 | 29.20 | -0.39 |
| 1367774 | P／29.39 | 29.20 | -0.19 |

PL公开五点均比P最新存档1367774更快，但总分29.20低于29.39。公开点不足以解释总分方向；不反推隐藏点耗时，不宣称整体加速或稳定退化。

## 当前保留版本与下一步

当前建议保留源码P/r6，依据其有效存档1367774 Pass29.39；历史最高单次29.59对应1367629。平台最后实际提交是PL任务1369663 Pass 29.20分，未重新提交P，也不将建议源码与当前排行榜提交混为一谈。尚未判定PL可替换P，也未判定团队共同最佳。F/P/L单项观察不能相加或相乘；正式比较pending时不据此切换。

本次官方终态与下载工程身份已保存；下一步核验官方完整评分/计时/退化规则及四臂可比性，必要时按事前明确的比较计划补证。保留失败与全部重复观察；不因单次分数切换保留版本。A共同基线若不同再补列，C反例若出现另建明确实验，不能用历史Pass覆盖。

## 异常、未完成事项与工作流边界

本机Windows未发现可用CANN/NPU；python/python3仅WindowsApps占位。通用Python五阶段manifest/state、canonical采集、全case逐SoC目标及本地构建/加载门禁未完成，未伪造成功。用户指定官方协议优先，授权实验实际结果与通用工作流未完成分别报告。

官方模板只提供首样例FP32 seed42、reflect、[1,1,8,8]→[1,1,4,4]，rtol=atol=1e-4，bad<=1e-4*N；-e不证明全量精度。真实UT旧fixture与README跳过描述不一致，仍含不存在的totalNum，尚未执行，不写实际编译失败。

历史旧包evaluated_at实际为提交时间；本轮引用使用submitted_at，未提供完成时间均为null。固定历史包未修改。评分公式、隐藏测试耗时与精确测量口径未知，不推算或绕过隐藏数据。

材料：[21字段JSONL](experiments.jsonl)、[恢复身份](artifacts/workflow/baseline/restoration-identity.json)、[环境报告](artifacts/workflow/baseline/环境检查报告.md)、[入口审计](artifacts/workflow/baseline/entrypoints-audit.json)、[历史观察](artifacts/workflow/baseline/historical-evidence-audit.json)、[分析契约](artifacts/workflow/analysis/round1/implementation-contract-PL.json)、[报告生成器](artifacts/reporting/generate-reports.cjs)。

本轮只新增一个准确组合假设和一次官方实验E001；边界规划、回退、Host可达性诊断均归同一快照。六条历史引用不计作新实验；流程检查不为凑次数新增无关修改。

交付状态：`exploration_delivered_formal_comparison_pending`。本次官方终态已取得，无活动授权阻塞；正式性能可比性、稳定最佳与中央共同基线仍未判定。

最终隔离交付核验：[VERIFY_REPORT.md](artifacts/workflow/integration/VERIFY_REPORT.md)。
