$ErrorActionPreference = 'Stop'
$runRoot = 'D:\算子比赛\346题\work\Q06\round-001\B'
$outputRoot = Join-Path $runRoot 'artifacts\workflow\preparation'
$sourceZip = 'D:\算子比赛\346题\第六题\历史盘点\B\artifacts\official\1367774.zip'
$restorationPath = Join-Path $runRoot 'artifacts\workflow\baseline\restoration-identity.json'
$restoration = Get-Content -LiteralPath $restorationPath -Raw | ConvertFrom-Json
$pArm = $restoration.arms | Where-Object arm -eq 'P'
$mapping = @($pArm.files | ForEach-Object {
    $workingFile = Join-Path $pArm.root $_.file
    $fileItem = Get-Item -LiteralPath $workingFile
    $sha = (Get-FileHash -LiteralPath $workingFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($sha -ne $_.sha256) { throw "Working file changed: $workingFile" }
    if ($fileItem.LinkType) { throw "Working file is linked: $workingFile" }
    [ordered]@{ source = "$sourceZip!code/$($_.file)"; working = $workingFile; relative = $_.file; source_sha256 = $_.sha256; working_sha256 = $sha; identical = $true; copy_type = 'ordinary extracted file'; adaptation = $null }
})
$manifest = [ordered]@{
    schema_version = 1
    task_id = 'Q06-R001-B-COMBINE-20261117'
    status = 'static_preparation_complete_dynamic_gate_pending'
    invocation = 'registry'
    source_repository = 'https://github.com/shorydh/bisai'
    source_commit = '8e245dab91700555bd619e95c70fa780305b1b37'
    source_package = $sourceZip
    source_package_sha256 = $pArm.package_sha256
    source_seven_source_sha256 = $pArm.seven_source_sha256
    working_directory = $pArm.root
    working_file_count = $mapping.Count
    source_and_working_all_38_digest = $pArm.all_38_file_sha256
    mapping = $mapping
    adaptations = @()
    dependency_closure = [ordered]@{
        static_status = 'self-contained project sources; SDK, generated API and runtime external dependencies declared'
        private_repository_source_dependencies = @()
        source_directories = @('op_host','op_kernel','examples','samples','tests/ut')
        sdk = @('CANN find_package(ASC)','AscendC kernel_operator.h and kernel_tiling/kernel_tiling.h','ASCEND_HOME_PATH includes and runtime libraries','npu_op_code_gen generated aclnn_*.cpp and op_proto.cc')
        optional_ut = @('local googletest source','nlohmann/json include','tikicpulib')
        python_sample = @('python3','numpy','ml_dtypes and imports required by samples/reference.py')
        dynamic_independence_verified = $false
    }
    entrypoints = [ordered]@{
        original = 'aclnnPadV3GradGetWorkspaceSize -> aclnnPadV3Grad; registered OpType PadV3Grad'
        working = 'same generated registry/ACLNN path; examples/test_aclnn_pad_v3_grad.cpp'
        local_example_driver = 'examples/run.sh via DEVICE_ID=<confirmed device> bash build.sh -j4 -e'
        local_build = 'source <actual CANN set_env.sh>; bash build.sh -j4'
        local_ut = 'NLOHMANN_JSON_INCLUDE_DIR=<actual include> GTEST_SOURCE_DIR=<actual source> bash build.sh -j4 -u'
        official_result = 'https://cannjudge.cn/public/ictcompetition/padv3grad/submission/6afb1ec66bd0f9be37b4e0f3'
    }
    build_route = [ordered]@{
        package = 'pad_v3_grad_custom RUN'
        build_sh_compute_unit = 'ascend910b'
        cmake_declared_units = @('ascend910b','ascend910_93','ascend950')
        op_registration_aicore_configs = @('ascend910b')
        runtime_library_search = 'examples/CMakeLists.txt find_library(cust_opapi) with NO_DEFAULT_PATH at this build/packages/vendors/pad_v3_grad_custom/op_api/lib'
        runtime_environment = 'examples/run.sh prepends this project custom OPP and op_api/lib before SDK libraries'
        loaded_library_path = $null
        loaded_library_sha256 = $null
        compiled_binary_sha256 = $null
        local_build_executed = $false
    }
    target_socs = $null
    cann_runtime_version = $null
    cann_readme_supported_versions = @('9.0.0','9.1.0')
    historical_official_pass = [ordered]@{task_id=1367774;status='Pass';score=29.39;completed_at=$null;submission_time='2026/11/16 23:18:30';scope='only exact archived P official submission; not PL and not local TTK';source_identity_verified=$true}
    gates = [ordered]@{static_identity='pass';static_source_closure='pass_with_declared_external_sdk';local_build='not_run';actual_loaded_binary_identity='pending';ttk='not_run_unavailable';full_functional_subset='pending';generic_preparation_gate='pending'}
    user_scope_override = 'Independent static preparation authorized; official evaluation is authoritative. Do not invent local CANN/TTK or stop independent preparation for inaccessible official device facts.'
    evidence = @($restorationPath,(Join-Path $runRoot 'artifacts\fixed-commit-zip-checks.json'),'D:\算子比赛\346题\第六题\历史盘点\B\artifacts\official\1367774-identity.json','D:\算子比赛\346题\第六题\历史盘点\B\artifacts\official\1367774.json')
}
$manifest | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $outputRoot 'extraction-manifest.json') -Encoding utf8
@'
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
'@ | Set-Content -LiteralPath (Join-Path $outputRoot 'source-compatibility.md') -Encoding utf8
@'
# 功能证据与前处理门禁

状态：static_preparation_complete_dynamic_gate_pending。没有执行本地 CANN 构建、NPU 运行或 TTK；不填 strict_pass/conditional_pass，不把源哈希核对写成精度通过。

当前已核验的历史事实是官方任务 1367774 对准确 P 版本为 Pass，归档总分29.39；七源码 SHA256 d0b680d59d1dfa088dd24fff5d3128feb2758251bcd8d3b34b39635bad68f949，ZIP SHA256 18679dad71f9ea7723ca524599b0d9363861aeadf8f8032202f6391199a5a85a。该结果只能引用到 P，不能转移为 PL 结果，也不能声称完成本轮边界用例或完整 TTK 子集。官方实际完成时间未提供，completed_at/evaluated_at 为 null；2026/11/16 23:18:30 是提交时间。

归档公开5点均 Pass、显示输出错误占比0.00%；45点隐藏，未访问或推断。公开耗时分别6.77、7.18、7.26、9.16、6.98 μs，仅作为该官方任务原始观察，不证明稳定收益。

本机已知 Windows 无 CANN/NPU，Python 为占位入口；TTK 标准 Skill 未在当前工程技能目录发现。不安装工具、不执行必然失败的 CANN 构建，不编造缺失的 RUN 二进制或加载哈希。官方源码与结果身份映射可供主 Agent 用作必要的历史有效性证据；通用 Skill 的本地 TTK/加载门禁仍标 pending。

真实本地入口位于 P/README.md 和 build.sh：bash build.sh -j4；-e 运行 examples/run.sh，仅对应 samples 首个 FP32 reflect 测试点。samples/sample.py 固定随机种子42，np.isclose(rtol=atol=1e-4,equal_nan=True)，bad<=1e-4*N，精确检查输出文件与字节数；该比较器只证明其首样例口径，不替换官方全部合法输入标准。

README 声称默认 -u 跳过内层数值断言，但实际 tests/ut/CMakeLists.txt 无条件 add_subdirectory(op_kernel)，run.sh 无条件运行 kernel UT 和 sample verify；所检查脚本没有实现 ENABLE_INNER_KERNEL_UT 开关控制，两者存在不一致。当前 tests/ut/op_kernel/test_pad_v3_grad.cpp 保留初始模板 totalNum 字段和 TODO，不能冒充现有可直接运行的全精度测试。API UT 需要设备上下文，其 workspace 接口检查不替代 -e 数值校验。

下一步：冻结 PL 单文件差异，执行组合自身必要边界检查和官方构建/评测，回下载完整官方工程核验38文件，按实际终态和评分可比性给出结论。若 C 提供反例，保留现有快照后单建实验验证，不用历史 Pass 覆盖。
'@ | Set-Content -LiteralPath (Join-Path $outputRoot 'functional-acceptance.md') -Encoding utf8
@'
# 前处理阶段总结

## 做了什么

完整读取任务单、ops-perf-preparation 与共享验证/精度/隔离参考；审阅已恢复 P 的构建、注册、Host/Tiling、kernel、examples 和 sample。逐文件重新核对38文件与 baseline 的官方 ZIP 身份，所有文件均为普通副本且 SHA256 相同。没有修改原始 P/F/L 或实现 PL。

## 获取了什么成果

静态独立工程与原注册/ACLNN调用方式已确认，38文件映射及声明的 SDK 依赖闭包已保存。源码声明的 CMake 三个 compute unit、build.sh 固定 ascend910b 与注册仅 ascend910b 已分别记录，没有合并为硬件支持结论。

- D:\算子比赛\346题\work\Q06\round-001\B\artifacts\workflow\preparation\extraction-manifest.json
- D:\算子比赛\346题\work\Q06\round-001\B\artifacts\workflow\preparation\source-compatibility.md
- D:\算子比赛\346题\work\Q06\round-001\B\artifacts\workflow\preparation\functional-acceptance.md

## 未决项与下一动作

本次本地 CANN 构建、加载血缘、TTK、完整功能库存及实际官方设备未知，通用前处理动态门禁为 pending。历史1367774的准确 P 官方 Pass可以被真实引用；不延伸为 PL 验证。用户要求以官方评测为准，主 Agent可继续已授权的PL单文件组合、必要组合检查与官方评测；不能把本阶段静态准备称作五阶段全部通过。
'@ | Set-Content -LiteralPath (Join-Path $outputRoot '阶段总结.md') -Encoding utf8
[pscustomobject]@{status=$manifest.status;files=$mapping.Count;all_files_identical=(@($mapping | Where-Object { -not $_.identical }).Count -eq 0);seven_source=$pArm.seven_source_sha256;generic_gate='pending';output=$outputRoot} | ConvertTo-Json

