# P 工作工程兼容性与调用路径

任务 Q06-R001-B-COMBINE-20261117；只做静态前处理。P 已由 baseline 从固定交接提交对应的 1367774.zip/code/ 提取成独立普通文件目录，38 文件全部与官方 ZIP 一致。本阶段逐文件再次核验 SHA256，未修改 P，未增加工程适配；映射见 extraction-manifest.json。

## 工程与真实入口

这是注册算子工程：op_host/pad_v3_grad_def.cpp 的 OP_ADD(PadV3Grad)，经 npu_op_code_gen 生成 ACLNN 接口，cust_optiling/cust_op_proto/cust_opapi 和 AscendC kernel 被打入 pad_v3_grad_custom RUN 包。不存在手写 op_api 目录时，op_host/CMakeLists.txt 从当前 build/autogen/aclnn_*.cpp 获取生成接口，不依赖其他算子仓源码。示例通过 aclnnPadV3GradGetWorkspaceSize 和 aclnnPadV3Grad 调用，保持注册方式；没有改为直接 kernel launch。

examples/CMakeLists.txt 使用 NO_DEFAULT_PATH 在本工程 RUN 的 op_api/include 和 op_api/lib 解析接口及 cust_opapi，examples/run.sh 提前设置本工程 ASCEND_CUSTOM_OPP_PATH 与 LD_LIBRARY_PATH。此接线有利于选中当前构建，但没有实际动态加载路径或二进制哈希，不能宣称本次本机加载身份成立。

## SoC 与公开契约

| 来源 | 源码事实 | 本次验证状态 |
|---|---|---|
| 根 CMakeLists.txt | 声明 ascend910b、ascend910_93、ascend950；未指定时列出三者 | 仅构建配置声明，非全部硬件支持证明 |
| build.sh | 实际 COMPUTE_UNIT 固定为 ascend910b；传给 -DASCEND_COMPUTE_UNIT | 未在本机执行 |
| op_host/pad_v3_grad_def.cpp | AICore AddConfig 仅 ascend910b | 注册范围源码事实 |
| README.md | 环境说明 CANN 9.0.0 或 9.1.0 | 不能证明官方本次驱动/芯片/CANN 实际身份 |
| 官方任务 1367774 | 完整终态 Pass；准确 P 源码身份已核验 | 未公开/恢复实际加载二进制及目标设备信息 |

本次 TARGET_SOCS 仍未知，不能由 build.sh 的默认值认定官方物理设备。源码没有按 __NPU_ARCH__ 分开的本主头实现；pad_v3_grad.h 是所有 schMode 所用的共享模板头。用户明确只允许在 PL 中适配 r1 缓存，本阶段不为通用隔离机制扩大文件范围，后续必须陈述共享分支和动态覆盖限制。

公开面为两个 required ND Tensor 输入 x、paddings，以及 y；x/y FLOAT16 或 FLOAT，paddings INT32 或 INT64；mode 默认 reflect，paddings_contiguous 默认 true。infer shape 和 host tiling 保持原内容。源声明的 dtype/format 组合仅是现有代码事实，不宣称已覆盖所有官方合法输入。

## 模板与依赖盘点

kernel 入口 pad_v3_grad<schMode>：0/1 为完整 TilingData 的 half/float，2/3 为 SmallTilingData 的 half/float；主头 PadV3Grad<T,TilingDataT> 被四分支使用。host 选择完整/小元数据并设置四个 TilingKey。TryWideCertifiedFlat 与通用回退位于共享主头；不得把未运行分支认作死代码。

工程本地源码闭包包含七个编辑源码、Host/Kernel CMake、构建脚本、examples、samples、tests/ut。外部依赖是 CANN ASC/注册/图/tiling 头与代码生成器、运行库，sample 的 Python/numpy/ml_dtypes，UT 的 Googletest/nlohmann-json/tikicpulib。没有发现对原工作目录的绝对 include/link 路径或源码软链接。未执行 CANN 构建，因此动态闭包和二进制加载仍待验证。

## 不变与缺口

映射覆盖完整38文件，并以原始官方 ZIP 保留原始快照。未做工程重构、注册转直调、tiling/ABI/算法修改、安装或系统 OPP 覆盖。源文件身份已核对；实际构建、SDK 依赖可用性、动态加载血缘、完整本地 TTK 门禁均未完成。必要官方 PL 评测及其回下载核验由主 Agent 后续执行。
