# 第六题 PadV3Grad／round-004／Agent C

- **题目**：PadV3Grad
- **轮次**：round-004
- **执行者**：C
- **task_id**：`Q06-R004-C-RUNNER-VALIDATION`
- **任务**：独立验证并修正 R003 设备验收程序
- **起点**：远端固定提交 `791878cdf850df52f5ea807def4557707f8a8987`，tree `a2d55cb3a152846e7ae00716184d2ac1daa9af30`
- **基线**：团队共同基线待定；P/r6 仍是工作起点，本次没有修改任何算子 kernel

## 结论

已在独立 R004 工作树中完成验收工具修正和无可执行设备条件下的验证：

- 原 verifier 的两个缺陷均被实际复现：根 `manifest.json` 被枚举成第五个 case；4 字节输出被 NumPy 广播后错误通过。
- 新 verifier 只读取 manifest 指定的四个 case_id，强制输出为 12 字节、三个 FP32；缺失、截短、陈旧、超差、额外 manifest 和错误形状均会失败。
- synthetic 结果无论是否 PASS 都固定记录 `device_execution=false`，不能升级为 NPU 证据。
- 显式工程路径已贯通 shell、CMake cache、generated vendor config 和运行时预期库路径。
- 使用同一 CMake build cache 依次配置两个不同 vendor 路径，A/B 两次配置均退出 0，cache 与 vendor config 都切换到对应路径。
- C++ runner 会在调用并同步后从 `/proc/self/maps` 读取实际 `libcust_opapi.so`，要求其解析路径等于所选 vendor 的库。
- 当前主机仍无 CANN/NPU、bash 或 CANNLab 入口，真实四例没有执行，不能产生设备 PASS/FAIL。

本轮是工具验证，未创建官方算子性能任务；所有 `official_task_id=null`、`official_metrics=null`。

## 修正版入口与校验值

```text
run_four_variants.sh SHA256 = 912a8eea92e6a9e4ed48cbd1d653d82c183ebfad8ff06672b62caebcda71711c
verify_outputs.py SHA256    = 13977854d2791fa126098b99acb8c068b9a3ab0c817b7414bdaeab93a709eaad
edge_case_runner.cpp SHA256 = 0dc9b5f158859119134323eb1d3f14b57966b1afbc20cb1d2bc81606b6f6f315
runner patch SHA256         = 7672cd88867381b2083fde14d555d0e231b99adc44ea178279f9edec4f87963d
```

## 修正前证据

保留的 R003 verifier SHA256：

```text
761537e3ab3b6f628b56ae5e3d8ed35db5682ded0b218800cd79143c8d7b2ac2
```

合成正确四例加根 manifest：

- 原 verifier 退出码 1，并输出第五项 `case="manifest.json"`、`status="missing_output"`.
- 原报告还无条件写入 `device_execution=true`，不区分合成夹具。

移走 manifest 并将 `int64-contiguous/output/y.bin` 截成 4 字节：

- 原 verifier 退出码 0，`actual=[0.0]`、`golden=[0.0,0.0,0.0]`、`all_pass=true`.
- 新 verifier 对同目录退出 1，原因为 `output_size_mismatch:4!=12`.

证据：

- `artifacts/r004/synth/legacy-repro-v1/legacy-with-manifest.json`
- `artifacts/r004/synth/legacy-repro-v1/legacy-truncated.json`
- `artifacts/r004/synth/legacy-repro-v1/strict-truncated.json`
- `artifacts/r004/synth/legacy-repro-v1/summary.json`

## 统一实验表

| 实验编号 | 假设与改动 | 准确代码版本 | 测量来源 | 官方任务 | 官方状态及实际指标 | 与官方基线比较 | 结论及证据 |
|---|---|---|---|---|---|---|---|
| Q06-R004-C-E001 | 中央指出的两个旧 verifier 缺陷可被最小合成夹具复现 | R003 runner 原样副本；无 kernel 修改 | R003 verifier + R004 新 verifier | null | not_submitted；无官方指标 | 不可比较 | **verified**：manifest 被当作第五例；4 字节输出广播后错误 PASS；新 verifier 对同截短文件 FAIL |
| Q06-R004-C-E002 | manifest 驱动、严格 12 字节/3 FP32、输入哈希和 provenance 可阻断全部已知假通过 | R004 corrected runner；无 kernel 修改 | 8 项 Python 合同测试 | null | not_submitted；8/8 PASS；无设备执行 | 不可比较 | **verified（合成夹具）**：正确四例 PASS 且 device=false；缺失/截短/陈旧/超差/错误形状/额外 variant 均 FAIL |
| Q06-R004-C-E003 | 显式工程路径可贯通 shell、CMake cache、vendor 配置及运行时加载检查 | R004 corrected runner；无 kernel 修改 | 同一 build cache 连续配置 A/B 两个合成项目 | null | not_submitted；configure exit 均为 0 | 不可比较 | **verified（配置/静态）**：cache 和 vendor config 均从 A 切到 B；真实 CANN 编译和 `/proc/self/maps` 待设备 |
| Q06-R004-C-E004 | 冻结 P/F、四输入、golden、reference 和当前公开规则仍一致；旧 UT fixture 有字段漂移 | P `d0b680d…`、F `700af8d…`；无源码修改 | 本地 SHA256 + CANNJudge API + 静态 fixture 审计 | null | not_submitted；公开题配置已复查 | 不可比较 | **verified**：P/F 各 38 文件及四 case 哈希通过；reference `1542d63…` 通过；host UT 仍期待旧 key 1，kernel UT 仍引用已移除的 `totalNum` |
| Q06-R004-C-E005 | 当前主机可执行真实合法 edge 四变体 | R004 corrected runner；无 kernel 修改 | 环境与入口探测 | null | not_submitted；设备未执行、实际输出 0 | 不可比较 | **pending**：无 `npu-smi`/CANN/bash，`127.0.0.1:31640` 未监听；不能声称 PASS/FAIL |

## 已验证

- 权威远端提交可从 `q06/r003/c-numerical-boundary` 拉取；本地 R004 工作树初始 HEAD 就是 `791878c…`.
- P/F 均保持 38 文件；七源码总哈希分别为 `d0b680d…` 和 `700af8d…`.
- 四变体均保持 `x SHA256=3579185f…`、golden `[0,0,0]`、`rtol=atol=1e-4`.
- reference SHA256 为 `1542d63e602aa3aaa60242e91ea0d6a8ac038bab788c6898dc4777557f040ed3`.
- 当前公开题仍为 CANN 9.1.0、revision 0、score_mode 1、iterations 5、latest、50 cases；API 当前记录 `enable_cannlab=false`.
- corrected shell 通过 ShellCheck；Python 文件通过 `py_compile`.
- 可移植 runner patch 已用 `git apply --check` 验证。

## 待验证

- 在 CANN 9.1 / 910B3 主机实际构建 P，并执行四合法 edge case。
- 目标环境中的 `libcust_opapi.so` 实际加载路径检查；本机只有配置层测试，没有 CANN 动态库。
- 设备原始 `stdout/stderr`、四份 12 字节 `y.bin`、退出码和逐元素误差。
- 实际快路、证书拒绝和标量回退的运行时可观察性。当前未插桩，不能从外部 runner 推断真实 kernel 路径。
- 旧 host UT key/fixture 是否需要更新；当前无 CANN，不修改、不运行。

## 已证伪或无效

- “原 verifier 的 all_pass 足以验收”已证伪：4 字节输出可广播为三元素 PASS。
- “根 manifest.json 可作为 case”已证伪：会产生第五行 missing_output。
- 合成 PASS 不能代表 NPU 执行；本轮 corrected report 明确 `device_execution=false`.
- 本地便携 CMake/Ninja 只用于路由和 cache 测试，不是 CANN 环境，不能产生算子性能数据。

## 当前最佳有效版本

算子版本未改变，仍是冻结 P/r6。历史有效官方观察包括 A R002 P 任务 1381855、Pass、29.35 分和 A R001 P/r6 任务 1369815、Pass、29.67 分；这些不是本轮新评测，也不能证明稳定最佳。R004 仅改验收工具。

## 历史轮次保留

- R001：`Q06-R001-C-BOUNDARY-20261117`，`round-001`，`Q06-R001-C-E001` 至 `E005`。旧 reflect/污染 reference 事实保持原状。
- R002：`Q06-R002-C-REFERENCE-DEVICE-20261117`，`round-002`，`Q06-R002-C-E001` 至 `E005`。干净 reference、合法 edge 和设备接入 blocker 均保留。
- R003：`Q06-R003-C-NUMERICAL-BOUNDARY`，`round-003`，`Q06-R003-C-E001` 至 `E004`。runner 准备、输入/P/F/A 构建审计和 `npu_test_executed=false` 事实保留。

## 文件位置

- corrected runner：`artifacts/device-runner/`
- 原 runner 非改动副本：`artifacts/r004/original-device-runner/`
- 可移植补丁：`artifacts/diffs/R004-device-runner.patch`
- 严格测试：`artifacts/tests/`
- 合成结果与日志：`artifacts/r004/synth/`
- A/B CMake 切换证据：`artifacts/r004/synth/vendor-switch-v4/`
- 当前规则：`artifacts/results/R004-rule-snapshot.json`
- 基线审计：`artifacts/results/R004-baseline-audit.json`
- 设备阻塞探测：`artifacts/logs/R004-device-entry-probe.json`
- 冻结 P/F、case 与旧证据：`artifacts/source/`、`artifacts/device-case/`、`artifacts/reference/`
