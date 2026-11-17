# 第六题 PadV3Grad／round-001／Agent C

- **题目**：PadV3Grad
- **轮次**：round-001
- **执行者**：C
- **task_id**：Q06-R001-C-BOUNDARY-20261117
- **任务类型**：独立边界与反例检查，必要时最小精度修复
- **本轮起点**：B 固定提交 `8e245dab91700555bd619e95c70fa780305b1b37` 中的 `operators/Q06/历史盘点/B/artifacts/official/1367774.zip`
- **r6 状态**：不是已批准团队共同基线；A 仍在补验收

## 基线与源码身份

本机从官方 ZIP 独立恢复 r6。ZIP、七源码及 38 文件清单已重新计算并核验：

| 项目 | 值 |
|---|---|
| 官方任务 | `1367774` |
| ZIP SHA256 | `18679dad71f9ea7723ca524599b0d9363861aeadf8f8032202f6391199a5a85a` |
| 七源码 SHA256 | `d0b680d59d1dfa088dd24fff5d3128feb2758251bcd8d3b34b39635bad68f949` |
| 文件数 | 38 |
| 本机源码快照 | `artifacts/r6-frozen/` |
| 官方 tests 副本 | `artifacts/tests/official-1367774/` |

对照版本：

- 朋友原版 `1367558`：ZIP `cbb5fa762f71555d27ce59414de73b30f37a24218e9f608edb91b09584b233df`，七源码 `700af8da3ef6679f48ebf8bbfa9d2f145d9357e9b6fd2e4f288542c662a1969b`。本机快照位于 `artifacts/friend-baseline/`。
- A `u64src` 固定快照：七源码 `119a5a5b9e4c1589e595a391c8867e75eb5901e192183c4ac5ad7a2a90ea1b86`。本机快照位于 `artifacts/a-u64src/`，仅用于差分理解，不是 golden，也没有被当作设备结果。
- r6 相对朋友原版只有主 kernel 头中的前导恒等前缀合并改动，完整差异见 `artifacts/results/r6-vs-friend.diff`。`AddScalar`、`StoreCertified` 等数值兜底代码在两版本中相同。

## 环境与边界

本机未检测到 `npu-smi`、`ASCEND_HOME_PATH`、CANN 工具链或 WSL 发行版，因此：

- 未执行 Ascend C 编译；
- 未执行 NPU `-e` 数值测试；
- 未执行 Profiler 或云性能测量；
- 未提交新的 CANNJudge 任务；
- 所有本轮测试均为 CPU 模型、静态代码镜像或官方 Python reference，不升级为设备或官方评测结论。

环境探测记录见 `artifacts/logs/environment.txt`。

## 统一实验表

| 实验编号 | 假设与改动 | 准确代码版本 | 测量来源 | 官方任务 | 官方状态及指标 | 基线比较 | 结论及证据 |
|---|---|---|---|---|---|---|---|
| Q06-R001-C-E001 | 前导恒等前缀合并不改变索引多重集；拒绝/缓存复用后 outer 状态不污染 | r6 `d0b680d59d1d…`；无代码修改 | CPU 镜像；`artifacts/results/E001-E003-model.json` | null | null；本轮未提交官方 | 与朋友原版状态机对照 | **verified（仅 CPU 模型）**：65,910 个正式索引检查、747 个状态检查均无差异；95,004 个带符号 pad 探索用例的多重集也无差异，但带符号支持仍未由题面/设备确认 |
| Q06-R001-C-E002 | r6 数值兜底在有限 FP32 强抵消时与官方 reference 精度一致 | r6 `d0b680d59d1d…`；无代码修改 | CPU 源码镜像；`artifacts/results/E001-E003-model.json` | null | null；本轮未提交官方 | 不可作性能比较 | **pending**：25,994 个有限序列与 48 个布局用例中出现差异；最小代表 `[1.7e38, 1, -1.7e38]`，官方 FP64 reference 为 0，r6 标量模型为 1，差异 1 大于 FP32 容差 1e-4。尚无 NPU 结果 |
| Q06-R001-C-E003 | 大索引字段在无显存分配的符号模型中保持 int64，超过 uint32 字节范围时不截断 | r6 `d0b680d59d1d…`；无代码修改 | CPU 符号模型；`artifacts/results/E001-E003-model.json` | null | null；本轮未提交官方 | 仅检查 r6 与未合并 outer 路径 | **verified（有限符号范围）**：16 项检查无差异；最大字节索引 `276023230464`，超过 `2^32` 且低于 int64 上限；未执行 NPU 大分配 |
| Q06-R001-C-E004 | 用官方 Python reference 精确确认 E002 最小用例的 golden | r6 `d0b680d59d1d…`；无代码修改 | 官方 `samples/reference.py`；PyTorch 2.15.0 CPU；`artifacts/results/E004-reference-minimal.json` | null | null；不是 CANNJudge 提交 | 不可作性能比较 | **pending（设备语义）**：输入 `1x1x1x6`、reflect、末轴 pad `[1,3]`、有限值；int32/int64 × 两种布局四种官方 reference 运行均输出 `[0,0]`；r6 标量模型输出首元素 1 |
| Q06-R001-C-E005 | 8192/256/128/32/64 阈值、rank0/1、两种 padding 布局及同 shape 不同 padding 的分派条件无差一错误 | r6 `d0b680d59d1d…`；无代码修改 | 静态源码镜像；`artifacts/results/E005-dispatch.json` | null | null；本轮未提交官方 | 仅检查 r6 | **verified（静态模型）**：30 项检查无差异；同 shape 不同 padding 的模型读取当前值，不沿用缓存样例 |

## 关键发现

### 已验证

- r6 ZIP 的 38 个文件已重新展开核验；七源码树哈希与 B 记录一致。
- 在非负 padding 的正式索引矩阵中，`MakeContributors` 与独立反演公式的结果多重集一致。
- r6 前导前缀合并在所列 747 个状态检查中保持与未合并路径相同的 **有序 outer base 序列**，包括重复行、无效 outer 行后续调用以及部分/全部前缀合并。
- 静态分派矩阵未发现 `> / >=` 或容量边界差一。
- >`2^32` 字节的符号索引未截断。

### 待验证

**有限值强抵消候选**：

```text
x.shape = [1, 1, 1, 6]
paddings = [[0,0],[0,0],[0,0],[1,3]]
mode = reflect
output.shape = [1, 1, 1, 2]
x = [0, 1.7e38, 0, 1, 0, -1.7e38]  # float32
输出0来源 = [1, 3, 5]
来源值顺序 = [1.7e38, 1, -1.7e38]
官方 Python reference 输出0 = 0
r6 AddScalar 模型输出0 = 1
```

该输入全部有限，reflect 反演可由题面 reference 正常生成 golden，现有题面未排除这种数值范围。四个 int32/int64 × layout 官方 reference 运行均得到 0。尚缺真实 NPU 输出，因此当前只能标 `pending`，不能称为设备已证实失败。

该数值行为在朋友原版和 r6 中共同存在；r6 的差异只涉及 outer 前缀优化，不是由本次 r6 改动新增。A `u64src` 的 `PadAccStep` 在有限中间溢出时直接保留 Inf，与本候选属于不同实现路径；不能用 A 的 CPU 模型替代设备结论。

### 已证伪或无效

- 不能从 1367629/1367774 的官方 Pass 推断全部边界已覆盖；官方只公开 5 个点，隐藏 45 点未读取。
- 不能把 A 的 `local_model_check.log` 中 `overflow-cancel ref=0 kernel=inf OK` 当作正确性证明；该日志同时存在 38 个 reference-invalid 和 4 个 skip-family。
- 不能把 B `cpu-r6-outer-result.json` 的 60,000 行/241,210 bases 当作设备执行；文件明确 `device_execution=false`。
- 不能因 E003 符号检查通过而声称 NPU 已支持超大张量。

## 历史官方证据（非本轮新评测）

准确绑定 r6 七源码的历史官方任务：

| 官方任务 | 历史状态 | 历史总分 | 完成/评测时间字段 | 证据 |
|---|---:|---:|---|---|
| `1367629` | Pass | 29.59 | B 记录 `evaluated_at=2026-11-16T23:10:56+08:00` | B `experiments.jsonl`、官方结果与源码 ZIP |
| `1367774` | Pass | 29.39 | B 记录 `evaluated_at=2026-11-16T23:18:30+08:00` | B `experiments.jsonl`、官方结果与源码 ZIP，包哈希已在本机复核 |

这两条是既有官方历史，不是本轮新提交；本轮没有新的官方任务号、官方指标或性能比较。单次总分差不构成稳定收益或加速比。

## 当前最佳有效版本

本轮没有产生修复版，也没有新的官方有效结果。当前边界任务所指版本的来源身份是 r6 `d0b680d59d1d…`，其历史官方任务 1367774 为 Pass/29.39，1367629 为 Pass/29.59。

这不是 C 宣布的共同基线，也不能据此在 A/B 间选最终最佳版本。共同基线、跨版本选择及正式性能比较仍由 A 负责；B 负责 r6+r1 组合。

## 值得继续探索

1. 在与本机冻结工程相同 SHA 的 CANN 9.1/Ascend NPU 上运行上面的最小有限抵消用例，保存实际设备输出和分支日志。若设备确为 1，则需独立新建 `r6-fix/` 并重新官方评测；若设备为 0，则当前阻塞解除，CPU 模型与设备语义存在差异。
2. 在同一设备上覆盖 totalInput `8191/8192/8193`、totalOutput `255/256/257`、单核 count `127/128/129`、贡献数 `31/32/33/63/64/65` 的实际命中和拒绝。
3. 在同一 shape 上连续调用不同 padding 值，验证 tiling-cache key 仅含 shape 时 kernel 确实读取每次输入的 padding。
4. 对 FP16 近舍入边界和真正 NaN/Inf 做设备测试；这些未被 CPU 模型或官方 5 个公开点覆盖。

## 未完成事项

- 缺本机 NPU/CANN：未编译、未跑设备、未跑 Profiler、未做性能测量。
- 未提交本研究点的新官方任务；历史官方记录不能替代本候选用例覆盖。
- 官方 FP32 强抵消候选未完成设备裁决，因此未建立 `r6-fix/`，避免在只有 CPU 模型的情况下改变冻结路由。
- 负 padding、空维和极端索引的合法范围仍以题面/官方 reference 为准；带符号探索通过不等同于正式支持声明。

## 文件位置

- `summary.md`：本总结
- `experiments.jsonl`：固定字段实验记录
- `artifacts/r6-frozen/`：r6 七源码冻结快照
- `artifacts/friend-baseline/`：朋友原版七源码快照
- `artifacts/a-u64src/`：A u64src 七源码快照
- `artifacts/tests/`：独立边界测试、官方 tests 副本和源码校验脚本
- `artifacts/results/`：模型结果、官方 reference 结果、源码清单和 r6 差分
- `artifacts/logs/`：测试与环境日志
- `artifacts/official-refs/`：所用历史官方 JSON 与 ranking 文本的只读副本
