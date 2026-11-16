# 功能证据与前处理门禁

状态：static_preparation_complete_dynamic_gate_pending。没有执行本地 CANN 构建、NPU 运行或 TTK；不填 strict_pass/conditional_pass，不把源哈希核对写成精度通过。

当前已核验的历史事实是官方任务 1367774 对准确 P 版本为 Pass，归档总分29.39；七源码 SHA256 d0b680d59d1dfa088dd24fff5d3128feb2758251bcd8d3b34b39635bad68f949，ZIP SHA256 18679dad71f9ea7723ca524599b0d9363861aeadf8f8032202f6391199a5a85a。该结果只能引用到 P，不能转移为 PL 结果，也不能声称完成本轮边界用例或完整 TTK 子集。官方实际完成时间未提供，completed_at/evaluated_at 为 null；2026/11/16 23:18:30 是提交时间。

归档公开5点均 Pass、显示输出错误占比0.00%；45点隐藏，未访问或推断。公开耗时分别6.77、7.18、7.26、9.16、6.98 μs，仅作为该官方任务原始观察，不证明稳定收益。

本机已知 Windows 无 CANN/NPU，Python 为占位入口；TTK 标准 Skill 未在当前工程技能目录发现。不安装工具、不执行必然失败的 CANN 构建，不编造缺失的 RUN 二进制或加载哈希。官方源码与结果身份映射可供主 Agent 用作必要的历史有效性证据；通用 Skill 的本地 TTK/加载门禁仍标 pending。

真实本地入口位于 P/README.md 和 build.sh：bash build.sh -j4；-e 运行 examples/run.sh，仅对应 samples 首个 FP32 reflect 测试点。samples/sample.py 固定随机种子42，np.isclose(rtol=atol=1e-4,equal_nan=True)，bad<=1e-4*N，精确检查输出文件与字节数；该比较器只证明其首样例口径，不替换官方全部合法输入标准。

README 声称默认 -u 跳过内层数值断言，但实际 tests/ut/CMakeLists.txt 无条件 add_subdirectory(op_kernel)，run.sh 无条件运行 kernel UT 和 sample verify；所检查脚本没有实现 ENABLE_INNER_KERNEL_UT 开关控制，两者存在不一致。当前 tests/ut/op_kernel/test_pad_v3_grad.cpp 保留初始模板 totalNum 字段和 TODO，不能冒充现有可直接运行的全精度测试。API UT 需要设备上下文，其 workspace 接口检查不替代 -e 数值校验。

下一步：冻结 PL 单文件差异，执行组合自身必要边界检查和官方构建/评测，回下载完整官方工程核验38文件，按实际终态和评分可比性给出结论。若 C 提供反例，保留现有快照后单建实验验证，不用历史 Pass 覆盖。

