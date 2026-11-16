# PadV3Grad 组合方案分析

诊断分析阶段（ops-perf-analysis），round1；task_id=`Q06-R001-B-COMBINE-20261117`。

本报告是按用户任务单完成的有界源码分析。结论为 **ready_for_implementation_after_parent_freeze**；完整通用工作流的基线、前处理、设备测量及 manifest/state 门禁尚未完成，不能把本报告当作性能或全输入精度验收。只评估本轮指定的 P+r1 方案，不扩大到其他优化方向。

## 输入身份与现有观测

固定交接提交为 `8e245dab91700555bd619e95c70fa780305b1b37`。实际基线为官方 `1367774.zip` 的完整 `code/`，ZIP SHA256=`18679dad71f9ea7723ca524599b0d9363861aeadf8f8032202f6391199a5a85a`，P 七源码摘要为 `d0b680d59d1dfa088dd24fff5d3128feb2758251bcd8d3b34b39635bad68f949`。已读取工作副本 P，主头 SHA256=`9739a0c61d4c545dd0d98c0203c7cf4c786acf745d3a4cdb8c1e099a841381bb`，与官方身份一致。完整文件清单见同目录 source-isolation-PL.json；父 Agent 验收 ZIP 与完整恢复身份后冻结。

已读任务单、历史实验 JSONL、官方 P 源码、两个指定原始 diff、Host tiling 与注册入口、samples/reference.py。历史原始记录保持 `round_id=历史盘点`；这里只引用，不改写其完成时间。

| 臂 | 七源码摘要 | 历史官方任务／总分 | 本轮角色 |
|---|---|---|---|
| F | 700af8da3ef6679f48ebf8bbfa9d2f145d9357e9b6fd2e4f288542c662a1969b | 1362811／28.61；1367558／28.66 | 局部对照 |
| P | d0b680d59d1dfa088dd24fff5d3128feb2758251bcd8d3b34b39635bad68f949 | 1367629／29.59；1367774／29.39 | 本轮实现父版本 |
| L | d3174f99553a7ba700a726f77370e1e287e1084cd2bc9768d4bbbcbd66ce9d24 | 1362890／29.23；1364006／28.84 | 局部对照 |
| PL | 实施后冻结 | 无 | 新实验，不能继承 P/L Pass |

现有分数只是官方历史观测，不能直接证明本轮严格可比或稳定收益。共同基线未批准；完整计时、评分及退化规则、官方实际芯片与共享负载未知。没有 profiling 数据，MBU/MFU/mte2_util/cost_bound/ceiling_us/headroom/verdict 均为 unknown；不使用默认芯片峰值补算。公开五点不泄露完整 shape，45 个隐藏点不读取、不反推。

## 机制与可证伪假设

P 已在 `TryWideCertifiedFlat()` 入口执行 `InitOuterPrefix()`，将 front=0 且输入输出轴长相同的前导外轴折叠。L 只缓存末轴 `MakeContributors(column,inputWidth_,outputWidth_,front_[rank_-1],mode)`，该函数只依赖当前调用的列、末轴长度、front 与 mode，和外轴 row/cursor/base 无关。因此两个机制的数据依赖相互独立，可保留 P 的外轴逻辑，原样移植 L 的两个改动位置。

预测：在命中缓存守卫且 wide path 被接受的 core 区间中，末轴计划构造次数由 count 降为 outputWidth；当 count>outputWidth 时构造次数严格减少，源偏移有序序列与 P 完全相同。若实测 PL 比 P 更慢、出现编译/资源/精度失败，则记录当前预测未命中并区分实现成本、代码正确性和测量口径，不能凭一次退化否定所有缓存策略。端到端收益数值为 unknown，不给最低分数承诺。

缓存前置还可能在 wide path 早期因贡献数过多而拒绝时增加无用规划；它是原样适配 L 的一部分，不通过本轮暗改守卫来规避。新增结构赋值、分支和栈访问也可能抵消规划减少。

## 精确适配范围

P 主头 baseline 行501之后插入 r1 原文：`lastPlanCapacity=32`，守卫 `outputWidth_<=lastPlanCapacity && count>outputWidth_`，函数局部 `Contributors lastPlans[32]`，仅守卫成立时逐列生成计划；baseline 行510–511替换为原样三元选择缓存或 `MakeContributors`。其余 37 文件与主头其他内容保持字节一致；完整源码隔离范围与父版本逐文件 SHA 见 scope。

保留所有已存 TilingKey（0/1 full metadata、2/3 compact metadata）、FP16/FP32、padding int32/int64 两布局的原路径。注册源码只配置 `ascend910b`，这只证明工程注册声明，不能推定官方实测具体设备。用户明确限制只改当前完整独立 PL 工程中的主头，故不引入新的 SoC 分派或复制 helper；非本工程全代际收益不作声明。

## 正确性与边界推理

- count 是本核 `[begin_,end_)` 的长度，不是总输出或全张量行数。即使全张量多行，单核 count<=width 时不缓存。
- `run=min(count-j,width-column)`，故 `0<=column+c<width<=32`，访问 lastPlans 不越界；跨行尾块和非零起始列仍按真实 column 查询。width31/32分别受 count>width 判定，width33始终关闭。
- 核内 count>width 不保证包含两条完整行；守卫正确含义是多于一行的输出数量。部分起始行、部分尾行仍合法，不能将注释解释成额外完整行条件。
- Host smallOutput 在 totalInput<=8192 且 totalOutput<=256 时使用 workPerCore=32。若实际 coreNum>=ceil(totalOutput/32)，requestedCores>=ceil(totalOutput/32)，DMA 对齐后 blockFactor<=32。因此该常见条件下 width32 的 count>width 不可达，width31/count32是重要边界；低核数时可出现更大 count。模型需分开标记 Host 可达与 synthetic 区间，不用全张量行数推断缓存收益。
- Contributors 由5个 int64字段组成，源级对象大小40字节，数组增加1280字节自动存储；现有 outerBases[64] 为512字节。UB分配不变不代表栈、寄存器和编译器 spilling 无成本。即使守卫为 false，函数静态 frame 仍可能增加，实际大小需真实编译证据。
- `lastPlans` 是函数自动变量，每次 wide 尝试按当前 padding/mode 重建；未放入类成员、静态变量或跨调用全局状态，因此缓存不跨不同 padding 调用。Host 已指出 padding 不属于 tiling cache key，device Init 每次读取当前 front；必须保持该流程。
- P 的 `InitOuterPrefix()` 在 wide 早退检查之前执行，因而后续 TryCertifiedFlat/SmallFlat/普通路径也按 outerStart_ 处理。PL 不能将该调用移入缓存守卫或挪到 wide eligibility 之后。
- 同 row 的 InitOuter 会把 base 恢复 cachedOuterBase_，并将 `[outerStart_,rank-2]` 的 position 置0；新 row 会先失效缓存、清 base、重新枚举。保留这段保证 wide 拒绝后其他路径从首贡献开始。
- outerCount 到64后仍发现下一外轴组合会拒绝；lastCount>64/outerCount拒绝；缓存不改变两条检查。空末轴计划仍跳过外轴规划；空外轴计划保留零贡献。未填写 slots 仍使用相同 sentinel。
- cache 仅改变取得同一个不可变 Contributors 值的方式；outer-major/last-axis-minor 的嵌套、offset SetValue 顺序、32/64归约选择、证书阈值、浮点求和顺序及所有同步保持原文。相同有序偏移与相同浮点操作支持相对 P 的位级等价推理，但不代替 NPU 编译与运行验证，也不证明 P 自身全输入正确。
- rank0 和空输出保留原 guard；有正输出时 width>0。禁止为本轮加入新的边界修补而混淆独立假设。

## 实施验证方案

本轮只实现一个主要假设；3–5次有意义实验是用户检查节点，不为凑数量变更代码。F/P/L/PL各自恢复/身份核验、组合源码差分、下列独立验证及官方评测可作为不同证据步骤，不将同一任务重复引用当复测。

1. 完整38文件与七源码哈希冻结；diff只含两个指定位置，反向移除 r1 缓存后主头须与 P 字节一致。同步、UB、Host、Tiling、证书、阈值等 token/段落逐字比较。
2. 基于实际源函数的便携辅助测试，分别比较 F/P/L/PL 生成的 Contributors、完整有序 source offsets、sentinel slots、wide接受/拒绝与回退首贡献。辅助测试明确 `device_execution=false`，不作为官方编译、数值精度或性能结果。
3. 因子：无/部分/全部恒等前缀；width1、31、32、33；count width-1/width/width+1；非零 begin、run尾块；贡献数0/31/32/33/63/64/65及 outerCount64/65；padding连续/非连续、int32/int64、host/device front路径；rank full/compact边界。合法性先按当前官方说明和参考核验，不能将源码允许范围自动当官方承诺范围。
4. 明确测试宽路因outerCount>64或lastCount乘积>64拒绝，返回TryCertifiedFlat/SmallFlat/Scalar后同row和新row的base/cursor；随后改变padding再新建调用，验证计划重新生成。浮点输入覆盖取消、正负、空来源与异常值；其数值判据沿原规范，不放宽。
5. 使用官方已有授权页面编译和评测PL；下载实际该条工程核对全部38文件/七源码/配置，保存原始任务ID、终态、公开指标、准确绑定的排行榜分数及观察时间。`evaluated_at`只填官方完成时间，缺失为null；提交时间另存。
6. 正式四臂结论前核查F/P/L历史完整配置和协议可比性；不足就补有意义的官方同期对照或保持pending。保留全部重复观测和失败结果，不把总分差写成加速比、不挑最高分。

## 资料采用与未决项

已采用两个指定历史diff和准确源码作为机制依据；未引入新 API，无需以不明SDK签名扩展方案。知识库未安装或根未配置，`kb_unavailable=true`、`kb_cards=[]`。最佳实践、优化方法、静态检视与API概览已浏览适用范围；本方案由任务指定的两个确切实现导出，不执行未知芯片下的族级重写或通用profiling推断，也不声明PRC性能finding。MC2/Cube/VF不适用。

待验：PL新代码编译、官方精度/性能、真实栈压力、评分/计时/退化规则、四臂正式可比性、A共同基线与C反例。现阶段可确认数据依赖和适配范围，不能确认收益或团队最佳。`convergence_eligible=no`；unknown不代表不可行，下一动作为父Agent冻结scope后实施唯一PL并取得真实官方结果。
