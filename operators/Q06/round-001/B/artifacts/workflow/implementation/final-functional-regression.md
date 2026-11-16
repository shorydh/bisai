# PL 组合必要验证

PL 是从完整38文件 P 工程复制后，仅在 `op_kernel/pad_v3_grad.h` 原样适配 r1 的两个代码片段。候选七源码摘要为 `988e491ec2d8d758adac5caa0e304cc81cb500ade732aadc9427fa1254267d41`，主头为 `88f6164377498e6c2d89d1c52578c4f601d172c98faa82c291197392249fcc08`。完整候选快照 `PL-source.zip` SHA256 为 `ee037759f9934f0ecf0fa3ed78c07ea15ed7f247fc07c87c89690c1a50f4127c`。所有测试材料均位于候选源码之外；冻结后没有改动候选。

源码与范围检查 PASS。38个文件完整，37个非主头文件与 P 逐字节一致；去掉新增缓存块并恢复原计划生成语句后，主头逐字节恢复 P。Host、TilingData、blockFactor、UB、64槽、sentinel、同步、证书阈值、归约及回退代码未修改。检查器为 `verify_candidate.cjs`，原始输出的结论和局限见 `scheme-conformance-gate.json`，未冒充 Python 标准工作流 gate。

源码派生规划诊断 PASS。`build_planner_harness.cjs` 从冻结 F/P/PL 主头提取原文 `MakeContributors`、`InitOuter/NextOuter`、P/PL 的 `InitOuterPrefix` 以及 wide 函数到首次输入 DMA 之前的规划前缀。CPU适配仅把 offsets存入 vector、同步替换为无操作、在DMA前截断；不执行设备向量、精度证书或Store。提取来源、各片段SHA和改造范围见 `harness-extraction.json`。

GCC 4.9.2，以 `-std=c++11 -O2 -Wall -Wextra -fno-fast-math` 编译。曾尝试 `-std=c++17`，该旧编译器不支持此选项，随后改用C++11；这不是AscendC候选编译失败。原始成功构建告警在 `harness-build.log`，主要为旧GCC的零初始化与有符号比较告警。工具链及尝试记录见 `harness-build-evidence.json`。

固定随机种子20261117，共359组shape、76030个区间：26866个按当前Host公式和假定核数生成的区间，49164个人工边界区间。wide规划接受73690、拒绝2340；32196区间满足缓存守卫。5894936个源偏移在F/P/PL间保持完全相同顺序，并与独立前向padding映射生成的来源多重集一致。207576次回退行比较及相同数量的部分cursor推进后重置比较全部一致；75710次同形状不同padding调用比较一致。以同一规划进行的8092400次CPU FP32成对求和位模式比较一致。原始stdout、stderr、规范JSON分别为 `planner-result.raw.txt`、`planner-errors.log`、`planner-result.json`。

覆盖width31/32/33、count<=width和>width、非零起始列及run尾段，无/部分/全部恒等前缀、两种padding布局、0/31/32/33/63/64来源，以及65来源强制拒绝后恢复原回退状态。主测试包括五种已恢复工程支持的mode与非负padding；零输入但非零输出及改变front后可能产生负back的探针单独作为签名/规划诊断，不据此新增官方合法域声明。FP16分支只使用2字节元素大小检查偏移和sentinel，未运行half数值算术；int32/int64 padding读入的设备类型转换和高rank全域未在本CPU工具上证明。

Host可达性独立检查 PASS。`host_reachability.cjs` 保存Host实际调度片段并对43008组总量、dtype字节数、假设核数枚举。若实际 `coreNum>=ceil(totalOutput/32)`，且wide所需small条件满足，则blockFactor<=32，width32缓存分支不可触发；width33总不触发。实际官方核数未知，低核数仍可能触发width32。结果见 `host-reachability.json`。这不是对官方芯片或实测时间的推断。

后续准确PL已取得官方任务1369663：Pass、29.20分。官方详情公开五点全部Pass、错误占比均0.00%，用时为6.67/6.93/7.00/8.35/6.93μs；45个隐藏点未读取或反推。提交时间2026-11-17 01:19:03+08:00；平台未提供实际完成时间，evaluated_at为null。父Agent下载本任务工程并核对完整38文件与冻结PL完全一致；详情、排行及身份原件见 `../../official/1369663.json`、`1369663-ranking.txt`、`1369663-identity.json` 与ZIP。该官方Pass是准确PL在这一次正式平台评测下的有效结果，不继承P/L历史Pass。

实际设备栈/寄存器压力、独立设备序列压测、TTK完整功能门禁仍未单独取得。CPU诊断只证明上述有限源码规划行为；CPU FP32求和输入为有限数，未覆盖NaN/Inf或设备数值指令，不证明全输入数学正确性、稳定收益或标准本地工作流eligible。设备编译与精度的可核对事实限该次官方任务Pass。
