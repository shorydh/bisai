# 第六题 PadV3Grad／round-003／Agent C

- **题目**：PadV3Grad
- **轮次**：round-003
- **执行者**：C
- **task_id**：Q06-R003-C-NUMERICAL-BOUNDARY
- **起点**：C 固定提交 `622d7f0064073dff249c23424330466ce510e3e2`
- **目标**：冻结 P 的合法 edge 设备裁决
- **基线状态**：共同基线仍未批准；P/r6 是工作起点

## 结论

本轮已完成 R002 输入复用、P/F 源码身份和 A CANNLab 构建证据核验，但没有完成真实 NPU 数值裁决。

原因是当前主机没有可用的本地 CANN/NPU、CANNLab SSH profile 或 `127.0.0.1:31640` 隧道。A 的固定记录证明曾连接真实 `910B3`、CANN 9.1 并成功编译相同的 P 源码，但该记录明确 `npu_test_executed=false`。因此不能把 A 的构建成功升级为合法 edge 用例的 NPU 结果。

合法 edge 候选继续保持 `pending`。没有设备差异证据前，不修改冻结 P，不删除补偿、不改求和顺序、不替换 golden 或放宽容差。

## 冻结版本与输入

| 项目 | 值 |
|---|---|
| P/r6 七源码 | `d0b680d59d1dfa088dd24fff5d3128feb2758251bcd8d3b34b39635bad68f949` |
| F 七源码 | `700af8da3ef6679f48ebf8bbfa9d2f145d9357e9b6fd2e4f288542c662a1969b` |
| reference SHA256 | `1542d63e602aa3aaa60242e91ea0d6a8ac038bab788c6898dc4777557f040ed3` |
| x SHA256 | `3579185fcbb48197725ba969c688363da3e791e77245b011307e62339aa85e26` |
| 四变体 golden | 均为 `[0,0,0]` |

P 与 F 的完整 38 文件均在本轮 `artifacts/source/` 下复核。四变体输入、padding、golden 和 case metadata 均与 R002 manifest 一致。

目标用例：

```text
x.shape = [1,1,1,5]
x = [1.7e38, 1, -1.7e38, 0, 0]  # float32
mode = edge
last-axis padding = [2,0]
output.shape = [1,1,1,3]
output 0 sources = [0,1,2]
```

预期分层：

- 精确实数和：1
- 顺序 FP64 累加：0
- 真实官方 Python reference：0
- r6 `AddScalar` 源码镜像：首元素 1
- 真实 NPU：尚未执行

## 环境与连接

- 当前主机：无 `npu-smi`、`msprof`、`ASCEND_HOME_PATH`、Git Bash、CANNLab SSH profile。
- 本机 `127.0.0.1:31640`：未监听。
- OpenSSH agent：停止。
- A 固定记录：`facfb39ece01643fa7f9452d09971f9ca4d2b246`，真实环境含 `910B3`、CANN 9.1.0；P 编译退出码 0，源码前后不变，但未运行 NPU。
- 当前 A CANNLab 记录被当作历史构建证据，不作为当前可复用连接或 NPU 数值结果。

环境证据：

- `artifacts/logs/R003-device-connection-probe.json`
- `artifacts/reference/a-cannlab-facfb39/completed_environment.json`
- `artifacts/reference/a-cannlab-facfb39/completed_P.json`
- `artifacts/reference/a-cannlab-facfb39/completed_P.log`

## 统一实验表

| 实验编号 | 假设与改动 | 准确代码版本 | 测量来源 | 官方任务 | 官方状态及指标 | 比较 | 结论与证据 |
|---|---|---|---|---|---|---|---|
| Q06-R003-C-E001 | R002 四变体输入、P/F 38 文件和 A CANNLab P 构建记录可以使用且身份一致 | P `d0b680…`、F `700af8…`；无代码修改 | 本地哈希 + A 固定提交只读证据 | P 构建记录绑定 1381855 | 非本轮官方运行；A 构建 Pass | 不可作性能比较 | **verified**：P/F 各 38 文件通过；四变体输入与 manifest 通过；A P.log SHA 与记录一致，且 `npu_test_executed=false` |
| Q06-R003-C-E002 | 当前账号可通过现有 CANNLab 或本地入口连接可用 NPU | 无代码修改 | 当前环境探测 | null | null | 不可比较 | **pending**：无本地 CANN/NPU、无 SSH profile、31640 未监听；设备未执行 |
| Q06-R003-C-E003 | 当前官方配置与 A/R002 规则一致，合法范围与 FP32 阈值可用于本次设备计划 | 无代码修改 | CANNJudge 公共 API 快照 | null | null | 不可比较 | **verified**：PadV3Grad、CANN 9.1.0、revision 0、score_mode 1、iterations 5、latest、50 testcases；float 阈值 1e-4 |
| Q06-R003-C-E004 | 可在不改冻结 P 的前提下准备四变体 NPU 执行器，待有设备时一次运行并比对 golden | P `d0b680…`；仅新增外部调用程序，无 kernel 修改 | 生成的 runner 与 case 包 | null | null | 不可比较 | **verified（准备）／设备 pending**：runner 覆盖 int32/int64 × contiguous/split，但本机未编译、未运行 |

## 已验证

- P/F 七源码和完整 38 文件与 R002 固定版本一致。
- R002 四个合法 edge 变体的二进制输入与 golden 完整，x SHA256 正确，golden 均由真实 reference 生成。
- A 的 P 构建记录与本轮 P 源码逐文件匹配；P.log SHA256 为 `e1fd63f6fb42fe9c9eff53d9c3059710e064436e6cdf4d77914da662472a0f7b`，对应记录一致。
- A 的 P 构建明确未执行 NPU 数值测试。
- 当前题面与 A 归档的核心配置一致，公开 50 个测试点入口仍存在。

## 待验证

- 在有 CANN 9.1 和 `910B3` 的实际设备上，用无插桩冻结 P 编译并执行四合法变体。
- 保存 Host 输出、输出字节、逐元素误差、实际快路/证书拒绝与标量回退证据。
- 四例若全部 `PASS`，说明该合法候选在设备上符合 reference/精度；若某合法输入 `FAIL`，再在冻结 F 上复核共因。

## 已证伪或无效

- A 的 CANNLab P 编译成功不能证明 NPU 数值通过。
- 历史官方 P/PL Pass 不能覆盖自定义合法 edge 候选。
- 不能用 `AddScalar` 源码镜像直接修改 kernel、替换 golden 或放宽 1e-4。
- 旧 reflect 候选已被 R002 移出正式合法矩阵，本轮不重测。

## 历史官方结果

本轮没有新增官方提交。固定材料中的有效观察包括：

- A R002 P：任务 1381855，Pass，29.35 分。
- A R002 PL：任务 1381889，Pass，29.36 分。
- A R001 P/r6：任务 1369815，Pass，29.67 分。
- C 无新官方任务；A/B 历史结果仅作上下文。

## 当前最佳有效版本

数值边界裁决尚未完成，不能据此刷新共同基线。按既有官方观察，r6/P 的历史最高单次为 29.67；A 最近一轮 P/PL 为 29.35/29.36，PL 仅高 0.01 分，不能据此认定稳定性能收益。当前建议仍保留 P/r6 作为工作起点，共同基线和稳定最佳由 A/中央决定。

## 设备执行材料

R003 准备的无插桩执行器：

- `artifacts/device-runner/edge_case_runner.cpp`
- `artifacts/device-runner/run_four_variants.sh`
- `artifacts/device-runner/verify_outputs.py`
- `artifacts/device-case/edge-legal-cancellation/`

实际设备端命令（需先 `source` CANN 的 `setenv`）：

```bash
DEVICE_ID=<实际设备号> bash artifacts/device-runner/run_four_variants.sh \
  /absolute/path/to/artifacts/source/P
```

runner 会编译未修改的 P、执行四变体、保存 `output/y.bin`，并按 `rtol=atol=1e-4` 对比既有 golden。本轮未执行该命令。

## 未完成事项

- 未编译 runner：当前无 CANN 编译器。
- 未执行 NPU：当前无可用设备或 CANNLab 隧道。
- 未执行 Profiler、性能或官方新评测；没有可以宣称的性能收益。
- 不应在设备结果出现前建立 `r6-fix/`。

## 文件位置

- `artifacts/results/R003-E001-asset-audit.json`：输入、P/F 和 A 构建审计
- `artifacts/logs/R003-device-connection-probe.json`：当前设备接入探测
- `artifacts/results/R003-E003-rule-snapshot.json`：当前题面配置快照
- `artifacts/results/R003-E004-runner-status.json`：runner 准备和未执行原因
- `artifacts/reference/a-cannlab-facfb39/`：A 构建与连接证据只读副本
- `artifacts/source/P/`、`artifacts/source/F/`：完整 38 文件工程
- `artifacts/device-case/`、`artifacts/device-runner/`：四变体设备测试材料
