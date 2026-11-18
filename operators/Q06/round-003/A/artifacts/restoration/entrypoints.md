# Q06 R003 A 冻结工程恢复与运行入口检查

本次仅恢复、逐字节核验和静态检查，未编译、未运行 NPU、未访问官方。PL 与 PL-lazy 工程根为本目录上一级的 `PL/`、`PL-lazy/`，没有额外 `code/` 层。

## 恢复结果

- 原 PL 的 38 文件与 R002 A 官方任务 1381889 的归档文件清单全部一致，七源码摘要 `988e491ec2d8d758adac5caa0e304cc81cb500ade732aadc9427fa1254267d41`。
- 从本轮 `task.txt` 的唯一完整 diff 提取 UTF-8/LF `lazy.patch`，在独立副本执行指定 `git -c core.autocrlf=false -c core.eol=lf apply --check` 和 `apply`，两个退出码均为 0。
- PL-lazy 七源码摘要 `03e6bc1bb81dc40ba71d4691aeb08feebdf38fe0a2ac12f2a59aeff0445afb39`，主头 SHA `676d61fc35ade7689f96fa8e1cc77c2973aab0820b949607d3480f847edcdcac`，符合任务单。只有 `op_kernel/pad_v3_grad.h` 改变；其余 37 文件逐字节一致，包含全部 31 个不可编辑模板文件。
- 两版本 reference SHA 均为 `1542d63e602aa3aaa60242e91ea0d6a8ac038bab788c6898dc4777557f040ed3`。
- 完整记录见 `PL_manifest.json`、`PL-lazy_manifest.json`、`restoration_audit.json` 和 `patch_commands.json`。这些证明独立恢复的文件身份，实际官方任务绑定由后续官方取证核验；没有下载或生成冒充官方的 ZIP。

可恢复命令（输出目录须尚无 `PL` / `PL-lazy`，脚本拒绝覆盖）：

```powershell
python restore_frozen.py --source-pl <准确的38文件PL工程根> --destination <新的输出父目录> --audit-dir <新的审计目录>
```

脚本读取同目录 `base_official_manifest.json` 和 `lazy.patch`。`template_path_audit.json` 保存 R002 官方模板的路径/可编辑属性核对，七源码路径没有 `code/` 前缀。

## 构建与示例

| 阶段 | 原有入口 | 静态核对的条件和覆盖 |
|---|---|---|
| 原样构建 | 配置当前 CANN 环境后，在工程根 `bash build.sh -j4` | `build.sh` 默认 `ascend910b`，依次构建 all/binary/package/install，检查非空 `.o` 和 `.run`。本次没有执行。 |
| 单样例 NPU | `DEVICE_ID=<实际设备> bash build.sh -j4 -e` | 构建后调用 `examples/run.sh`，它调用 `samples/sample.py generate`、ACLNN sample 二进制、`verify`。仅首个 FP32 reflect 样例，不能称全量精度。 |
| UT | `NLOHMANN_JSON_INCLUDE_DIR=<实际include> GTEST_SOURCE_DIR=<实际googletest> bash build.sh -j4 -u` | 本地 nlohmann/json、GoogleTest、tikicpulib 依赖；存在下述未适配 fixture，不能直接宣称可通过。 |
| 性能/Profiler | 未发现工程提供通用全量性能命令 | `examples/test_aclnn_pad_v3_grad.cpp` 单次 ACLNN 调用并同步/保存输出，没有计时、warmup、重复采样与统计协议。自建调用脚本或 Profiler 必须另存配置和原始证据；构建耗时不是算子耗时。 |

首样例：`samples/case.json` 与 sample 固定输入 x `float32 [1,1,8,8]`，paddings `int32 [4,2]` 为 `[[0,0],[0,0],[2,2],[2,2]]`，mode=reflect、paddings_contiguous=true，输出 `[1,1,4,4]`。`samples/sample.py:16` 使用随机种子 42。reference 实际导入 numpy、torch 和 ml_dtypes.bfloat16；不得替换依赖或改变其 dtype 分支。

示例比较器在 `samples/sample.py:62` 对 float64 转换后的实际/预期数组做 `np.isclose(rtol=1e-4, atol=1e-4, equal_nan=True)`，再以 `bad <= 1e-4 * 元素数` 判定；16 元素的此样例要求 bad=0。这个已读代码只说明本机样例的判定，不推定官方隐藏用例的完整算法。

## UT 具体缺项（静态检查，尚非构建失败记录）

1. `tests/ut/op_kernel/test_pad_v3_grad.cpp:82` 给 `tilingData->totalNum` 赋值，但当前 `op_kernel/pad_v3_grad_tiling_data.h` 的结构没有该字段，使用 totalInput/totalOutput，并要求 rank/mode/shape/stride/padding 等字段。原 fixture 只设置 totalNum/blockFactor/ubFactor，不能代表当前内核完整 tiling。
2. 同一 kernel fixture 在行 87 固定 tiling key 1、行 90 调 `pad_v3_grad<1>`。真实 host 对低 rank 的 compact 路径选择模式 2/3，见 `op_host/pad_v3_grad_tiling.cpp:245`；应按实际路径构造完整 fixture，不能把当前固定值视作已验证映射。
3. `tests/ut/op_host/test_pad_v3_grad_tiling.cpp:39` 仍有初始模板期望：key=1、tiling 字符串 `"0 1 0 "`、workspace={0}。这是源码中明示的 TODO fixture，未证明符合当前 tiling。
4. README 声称 `ENABLE_INNER_KERNEL_UT=OFF` 默认跳过内层数值断言，但当前 `tests/ut/CMakeLists.txt` 无条件 add_subdirectory(op_kernel)，`tests/ut/op_kernel/CMakeLists.txt` 无条件 add_executable，test_cpp 也没有相应跳过条件。run.sh 虽传入该选项，不能据 README 推断实际会跳过。
5. kernel UT CMake 固定 `SOC_VERSION "Ascend910B1"`（行 16）及对应 tikicpulib 路径。实际云设备和 SDK 可用模拟库需检查；不把这条静态配置当作当前 910B3 的运行证明。
6. 当前 38 文件没有 `op_api/` 手写 UT 子目录；tests/ut 的相关条件入口仅在目录存在时才成立。README 中 API UT 的开关说明不能证明本工程已包含该测试。

本次保持 38 文件冻结，不修模板和 fixture。若后续建立诊断 harness，应放独立目录并保存差异、构建配置、调用与分支证据；不能将诊断修改混入这两份待核对官方的冻结源码。
