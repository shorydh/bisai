# PadV3Grad 第 3 轮 UT 补测 · 执行者 A

2026-11-18，北京时间。`Q06-R003-A-LAZY-OFFICIAL` 的两份冻结实现分别在 CANNLab 运行了 `bash build.sh -j4 -u`。运行环境为 aarch64、CANN 9.1.0，kernel 使用 Ascend910B3 的 `tikicpulib` CPU 仿真。每个版本均运行 2 个 host 测试、2 个 kernel 测试，零失败、零跳过。

| 冻结实现 | 原官方任务 | host UT | kernel UT | 公开 reflect 样例 | 原始记录 |
|---|---|---|---|---|---|
| PL | 1402250 | 2/2 | 2/2 | 0/16 不匹配 | [运行日志](evidence/PL/build.log) · [host XML](evidence/PL/evidence/host.xml) · [kernel XML](evidence/PL/evidence/kernel.xml) |
| PL-lazy | 1402299 | 2/2 | 2/2 | 0/16 不匹配 | [运行日志](evidence/PL-lazy/build.log) · [host XML](evidence/PL-lazy/evidence/host.xml) · [kernel XML](evidence/PL-lazy/evidence/kernel.xml) |

## 修复与覆盖范围

在原样 PL-lazy 工程上复现了 `build.sh -j4 -u` 退出码 2。旧 kernel fixture 访问已删除的 `totalNum`，将紧凑 tiling 指针传给仅接受完整结构的函数，还固定选择了 key 1。原模板在该环境中也未能链接到所需名称的 GoogleTest Debug 库。[修前日志](evidence/original-PL-lazy/build.log)

修复后的 host UT 用 CANN 的测试上下文调用该版本注册的 tiling 函数，校验 key、block 数、输入输出形状、stride、padding、workspace 和结构长度，并写出实际的调度参数与 tiling 字节。kernel UT 读取同一次运行生成的文件，在仿真库中执行对应冻结源码的 key 3 分支。脚本在构建 GoogleTest 前设置 Debug，对每次运行使用独立目录，结束前核对两份 XML 中四个必需用例的运行状态。[测试代码](overlay/tests/ut) · [源码身份核对](audit.json)

- **reflect** 使用公开首样例，种子为 42，FP32 输入 `[1,1,8,8]`，输出 `[1,1,4,4]`。host 生成 328 字节 tiling，调度 2 个 block。kernel 写回的全部 16 个元素通过原版 `sample.py verify`，`rtol` 和 `atol` 均为 `1e-4`。
- **edge** 使用 FP32 输入 `[1,2,3,4,5,6]`、左右 padding `[2,1]`。host 生成 328 字节 tiling，调度 1 个 block。两个版本的仿真输出均精确等于 `[6,4,11]`，覆盖多个输入梯度累加至同一边缘位置。

对两份工程分别核对了全部 38 个文件的 SHA-256。相对各自的官方工程，仅 `tests/ut/` 下 7 个文件发生变化。七份算子源码、`sample.py` 和 `reference.py` 均逐字节匹配各自的冻结快照。完整差异路径和源码摘要见上方 `audit.json`。本次增加的是 CPU 仿真 UT 证据。C 的消去误差 edge 用例仍需在目标 NPU 上单独裁决，其他 dtype、shape、mode 也超出这两项用例的覆盖范围。第 3 轮的官方分数及其来源见[原正式交接](https://github.com/shorydh/bisai/blob/eab6f8d2175aa2f557b93f0cce4debeddf0840c9/operators/Q06/round-003/A/summary.md)。

## 在 CANNLab 复跑

从补测 ZIP 解压后的根目录运行以下命令。仓库检出可在 `operators/Q06/round-003/` 下运行同一组命令。恢复脚本会逐文件验证冻结快照并创建新的 `ut-PL` 和 `ut-PL-lazy`。云环境已安装 GoogleTest、NumPy、PyTorch 和 `ml_dtypes`。[环境记录](evidence/probe-20261118T134903Z.log)

```bash
source /home/developer/Ascend/cann-9.1.0/bin/setenv.bash
for version in PL PL-lazy; do
    python3 supplements/A-ut/prepare.py --handoff A --version "$version" --destination "ut-$version" || exit 1
    (cd "ut-$version" && bash build.sh -j4 -u) || exit 1
done
```

每次运行的 `tests/ut/build/evidence/run-*/` 含 host、kernel 的 GoogleTest XML，host 导出的 tiling 与调度参数，以及公开样例的输入、golden 和实际输出。
