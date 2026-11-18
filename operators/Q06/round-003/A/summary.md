# 第六题 PadV3Grad／round-003／A

任务 `Q06-R003-A-LAZY-OFFICIAL`；起点 `facfb39ece01643fa7f9452d09971f9ca4d2b246`，分支 `q06/r003/a-lazy-official`。本轮独立恢复既有 PL 与 PL-lazy，没有新增优化。PL 是直接父版局部对照；P 是此前工作起点，团队共同基线尚未确立。

## 统一实验表

| 实验 | 假设与改动 | 准确七源码版本 | 来源／官方任务 | 状态及原始总分 | 相对本轮 PL 分差 | 结论 | 证据 |
|---|---|---|---|---|---|---|---|
| Q06-R003-A-E001 / PL | 为冻结 PL-lazy 取得直接父版 PL 的同批局部对照；恢复既有冻结版本 | `988e491ec2d8d758adac5caa0e304cc81cb500ade732aadc9427fa1254267d41` | 官方 1402250 / `6afda28385ad43bbe043bf1c` | Pass，valid=True，总分 29.65 | 0.0 | verified，仅该次观察 | [结果](artifacts/official/6afda28385ad43bbe043bf1c.json) / [源码清单](artifacts/manifests/6afda28385ad43bbe043bf1c.json) |
| Q06-R003-A-E002 / PL-lazy | 延迟构造相对准确父版 PL 在同公开协议下产生可辨观察分差；恢复既有冻结版本 | `03e6bc1bb81dc40ba71d4691aeb08feebdf38fe0a2ac12f2a59aeff0445afb39` | 官方 1402299 / `6afda34285ad43bbe045172e` | Pass，valid=True，总分 29.97 | 0.32 | verified，仅该次观察 | [结果](artifacts/official/6afda34285ad43bbe045172e.json) / [源码清单](artifacts/manifests/6afda34285ad43bbe045172e.json) |

官方返回的完整 result（包括 Hidden/null）见 [experiments.jsonl](experiments.jsonl)。`evaluated_at=null`：官方未给实际完成时间；提交、回执、终态观察、排行观察时间分别记录。`theory_score` 不替代排行总分，分差不换算算子加速比。

## 比较与发现

- **verified：PL-lazy 对 PL 的有界官方总分比较。** 分差为 0.32；适用条件与逐项核对见 [比较审计](artifacts/audit/bounded_comparison.json)。全部重复观察保留；一次分差不证明稳定收益或因果贡献。
- **verified：独立恢复身份。** 两份完整 38 文件均绑定实际官方源码回读。PL-lazy 只有主头变化，其余 37 文件与 PL 字节一致，reference 保持任务单 SHA。见 [恢复审计](artifacts/restoration/restoration_audit.json)。
- **verified：历史记录不重编号。** B 的 `Q06-R002-B-E004 / 1379766` 详情在本次授权账号下返回 403；当前扫描缺旧 PL/P 的精确任务排行行。用户交付的旧29.64不混入当前分差，缺行不当作0分。旧四臂保留原轮次、任务与观察时间；详情 GET 不计新运行。见 [复用检查](artifacts/reuse/inspection.json)与[B 访问记录](artifacts/reuse/B_1379766_access.json)。
- **pending：稳定收益与共同基线。** 本轮没有主张优于工作 P，也没有追加 F/L/P。已核对的 C 固定提交 `622d7f0064073dff249c23424330466ce510e3e2` 验证了真实依赖 reference 与合法 edge 四变体，golden 为 `[0,0,0]`；其设备执行为 false、actual_npu_output=null。CPU 源码模型首元素为1不是 NPU 实测。本次可见发布记录仍缺冻结 r6/P 对同一合法输入的 NPU 输出与调用/分支证据，未发布进度未知；见[前序审计](artifacts/prior_audit/reuse-audit.json)。团队基线仍由中央结合该实际 NPU 裁决。
- **verified：旧 UT fixture 与当前 tiling 不匹配。** 这是源码静态发现，未自动改写为“本轮构建失败”。具体字段和 README/CMake 差异见[入口检查](artifacts/restoration/entrypoints.md)。

本轮可比的最高有效单次观察为 PL-lazy，29.97 分，任务 1402299。 稳定最佳未确定；本轮单次观察不批准替换团队共同基线。是否继续研究延迟构造的设备缓存成本，结合 B 的对应设备证据；不因本轮分差擅自叠加新优化。

## 云环境与未完成项

| 版本 | 原样构建 | 源码身份 | 首个 NPU 样例 | msprof 实际采集 |
|---|---|---|---|---|
| PL | 执行=True，exit=0 | 38文件前后一致=True | 执行=True，exit=0，mismatched=0/16 | 执行=True，exit=0，op_summary=1，复验 exit=0 |
| PL-lazy | 执行=True，exit=0 | 38文件前后一致=True | 执行=True，exit=0，mismatched=0/16 | 执行=True，exit=0，op_summary=1，复验 exit=0 |

- PL UT：执行=False；原因：冻结 fixture 引用了不存在的 totalNum，且初始 tiling key/layout 与当前实现不符；本任务保持冻结版本，未修改 fixture。
- PL Profiler 覆盖：首个公开 FP32 reflect 样例；warmup=0，应用调用=1。常规性能阶段：执行=False；原因：仅采集一次首样例的插桩调用，缺少预热、重复统计及全用例覆盖。
- PL 此次插桩单调用的原始 `Task Duration(us)`：9.480；只作诊断，不计算稳定收益或官方分差。
- PL-lazy UT：执行=False；原因：冻结 fixture 引用了不存在的 totalNum，且初始 tiling key/layout 与当前实现不符；本任务保持冻结版本，未修改 fixture。
- PL-lazy Profiler 覆盖：首个公开 FP32 reflect 样例；warmup=0，应用调用=1。常规性能阶段：执行=False；原因：仅采集一次首样例的插桩调用，缺少预热、重复统计及全用例覆盖。
- PL-lazy 此次插桩单调用的原始 `Task Duration(us)`：9.420；只作诊断，不计算稳定收益或官方分差。

首样例仅 FP32 reflect 输入 `[1,1,8,8]` 到 `[1,1,4,4]`，不是全量精度，也不包含 C 的合法 edge 数值门。静态 UT 缺项包括不存在的 totalNum 字段、初始 tiling key/layout 与当前实现不一致；本轮未改冻结模板以制造 UT 通过。详细记录与实际产物见 [云证据清单](artifacts/cannlab/publication_manifest.json)。

编译、首样例、UT、常规性能和 Profiler 分开记；构建耗时不是算子耗时。单次插桩采集有真实硬件时间，但没有重复预热统计，不能当作稳定性能比较；云结果不替代官方比较。完整误差算法、官方计时/预热/同步和退化阈值仍未知；不据此虚构指标或无限追加提交。

## 材料与下一步

完整代码在 `artifacts/code/<七源码SHA>/`，各目录 38 文件；冻结任务/方案、恢复补丁、官方状态与所有排行观察、同响应公开标尺和云证据位于 `artifacts/`。公开结果剔除其他账号与无关排行，保留原指标及原响应 SHA；完整原始响应留本机 `work/Q06/round-003/A/raw_official/`。

中央可从 [README](README.md) 校验并恢复准确工程，复核局部 PL 比较与 C 数值门；如需新优化或新的计时实现，应建立新快照并保留相应官方结果。本包不声称重建 ZIP 的外层哈希等于官方 ZIP。


## 交付复核与已恢复异常

实际云环境为 910B3、CANN 9.1.0、driver 25.5.0，逻辑设备 0 对应物理卡 3；运行时查询 20 AICore、20 Cube、40 Vector。各阶段负载快照未显示其他 NPU 进程，但不据此保证独占。Profiler 在首样例后执行，无显式预热不等于冷缓存。

初次隧道[连接被拒绝](artifacts/cannlab/recovery/local_tunnel_probe.json)，用户恢复后已完成执行。结果归档第一次[下载连接损坏](artifacts/cannlab/recovery/download_error.log)，随后仅[重读现有归档成功](artifacts/cannlab/recovery/download_retry.json)，没有因此重跑构建、NPU 或官方提交；下载产物已校验 SHA。

[独立原始证据复核](artifacts/audit/raw_to_public_audit.json)确认两条 21 字段记录、15 次官方观察、精确排行、同响应公开标尺、76 个源码文件一致。审计还实际执行包内恢复脚本，恢复两臂并逐字节比对通过；这是交接一致性验证，不是新增官方运行。审计记录的文档 SHA 对应追加本节前的快照；最终文件以 publication-manifest.json 校验。
