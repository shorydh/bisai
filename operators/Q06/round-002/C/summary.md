# 第六题 PadV3Grad／round-002／Agent C

- **题目**：PadV3Grad
- **轮次**：round-002
- **执行者**：C
- **task_id**：Q06-R002-C-REFERENCE-DEVICE-20261117
- **任务**：验证方法修正、reference 复验、设备反例裁决及必要最小精度修复
- **起点**：C round-001 固定提交 `9f0c24f6609a8641f083249a815bdaddef4147cf`
- **冻结实现**：B `8e245dab91700555bd619e95c70fa780305b1b37` 中的 `1367774.zip`
- **共同基线**：仍未由 C 判定

## 结论

1. round-001 的 reference 驱动确实被污染：假 `ml_dtypes.bfloat16` 等于 float32，且摘要和误差字段硬编码。旧结论不再作为“原依赖 FP32 reference”证据。
2. 使用真实 `ml_dtypes 0.5.1`、CPU PyTorch `2.15.0+cpu` 和冻结 `reference.py` 后，BF16 转换分支被显式阻断，四次实际输出均由返回数组计算。原 reflect 候选仍返回 0，但它的 back pad 3 大于推理输出维度 2，不属于当前正式 reflect 合法范围。
3. 新增合法 edge 候选：`x.shape=[1,1,1,5]`、`x=[1.7e38,1,-1.7e38,0,0]`、末轴 pad `[2,0]`、输出 `[1,1,1,3]`。输出 0 来源 `[0,1,2]`，真实 reference 输出 `[0,0,0]`；精确实数和为 1，r6 `AddScalar` 源码镜像为 1。
4. 本机没有 CANN/NPU/WSL，也没有项目提供的可用云设备连接说明。因此合法 edge 候选仍为 **pending**，不能声明设备失败。
5. 只有设备确认合法输入不符后，才应建立最小修复。本轮没有修改冻结 kernel，没有创建 `r6-fix/`。

## 源码与 reference 身份

本机从官方 ZIP 独立恢复完整工程，并重新核验 38 文件：

| 版本 | ZIP SHA256 | 七源码 SHA256 | 本机位置 |
|---|---|---|---|
| r6 / 1367774 | `18679dad71f9ea7723ca524599b0d9363861aeadf8f8032202f6391199a5a85a` | `d0b680d59d1dfa088dd24fff5d3128feb2758251bcd8d3b34b39635bad68f949` | `artifacts/restored/r6-1367774/code` |
| F / 1367558 | `cbb5fa762f71555d27ce59414de73b30f37a24218e9f608edb91b09584b233df` | `700af8da3ef6679f48ebf8bbfa9d2f145d9357e9b6fd2e4f288542c662a1969b` | `artifacts/restored/friend-1367558/code` |

冻结 `samples/reference.py` SHA256 为 `1542d63e602aa3aaa60242e91ea0d6a8ac038bab788c6898dc4777557f040ed3`。r6 与 F 只有主 kernel 头的前导前缀合并差异，`AddScalar` 数值回退代码相同；差分见 `artifacts/results/R002-r6-vs-friend.diff`。

当前官方模板包 SHA256 为 `10ba23fcc0dbe3549640a678d255a073ca0c3300ab6a99367eb494854af4061f`。38 文件中 31 个只读模板/样例/测试文件与历史工程一致，7 个 editable 文件是当前模板桩，不能替代 r6 七源码。证据见 `artifacts/results/R002-template-diff.json`。

## 干净 reference 环境

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | 3.11.16 | `C:\Users\xi\.conda\envs\ai\python.exe` |
| NumPy | 1.26.4 | 系统环境模块 |
| PyTorch | 2.15.0+cpu | 临时隔离目录中的真实 CPU wheel |
| ml_dtypes | 0.5.1 | 临时隔离目录中的真实模块 |

驱动同时记录各模块路径和 wheel metadata SHA256。其 `torch.tensor` 被替换为禁止调用的探针，`forbidden_bfloat16_branch_calls=0`；`np.dtype('float32') == ml_dtypes.bfloat16` 为 false，reference 模块持有同一真实 BF16 类型。

## 统一实验表

| 实验编号 | 假设与改动 | 准确代码版本 | 测量来源 | 官方任务 | 官方状态及指标 | 与官方基线比较 | 结论及证据 |
|---|---|---|---|---|---|---|---|
| Q06-R002-C-E001 | 真实依赖下的 FP32 reference 实际输出可从返回数组推导，且不进入 BF16 分支 | r6 `d0b680d59d1d…`；无代码修改 | 官方 reference CPU；`artifacts/results/R002-E001-reference-clean.json` | null | null；非官方提交 | 不可作性能比较 | **verified（reference 事实）**：两组候选各 4 个 dtype/layout 变体全部执行成功，输出一致；BF16 分支调用 0 次 |
| Q06-R002-C-E002 | 上轮 reflect 候选是否属于合法反例；是否存在满足约束的等价抵消候选 | r6 与 F；无代码修改 | CANN 9.1 ops-math 规则 + CPU 源码镜像 | null | null | 不可作性能比较 | **verified（合法性裁决）**：reflect back pad 3 ≥ output 2，旧候选移出正式合法矩阵；edge pad 2 < output 3，合法候选成立但仍待设备 |
| Q06-R002-C-E003 | r6/F 完整 38 文件及当前官方模板身份可复现且差异被准确解释 | r6/F 固定 ZIP；无修改 | 本地 38 文件哈希 + 当前 package API | null | null | 无官方性能比较 | **verified**：两个 ZIP 与七源码哈希通过；当前包 31 文件一致、7 个 editable 文件为模板桩；旧 C A 副本或 A 裸快照的 CRLF 字节不能作为 A 官方送测身份 |
| Q06-R002-C-E004 | 本机或项目说明中存在可用的 CANN/NPU/云设备入口 | 无代码修改 | 环境探测；`artifacts/logs/R002-device-access-probe.json` | null | null；设备未执行 | 不可比较 | **pending**：无 `npu-smi`、`msprof`、`ASCEND_HOME_PATH`、WSL 发行版、SSH config 或项目设备连接说明 |
| Q06-R002-C-E005 | 合法 edge 候选可以生成四变体最小设备用例，golden 由真实 reference 生成 | r6 `d0b680d59d1d…`；无代码修改 | 真实 reference；`artifacts/device-case/edge-legal-cancellation/` | null | null；非官方提交 | 不可比较 | **verified（用例包）／设备待验证**：int32/int64 × contiguous/split 均生成 golden `[0,0,0]` 和 SHA256 清单 |

## 合法候选与结果分层

```text
x.shape = [1, 1, 1, 5]
x = [1.7e38, 1, -1.7e38, 0, 0]  # float32
mode = edge
last-axis padding = [2, 0]
output.shape = [1, 1, 1, 3]
output 0 sources = [0, 1, 2]
```

| 层次 | 输出 0 |
|---|---:|
| 精确实数和 | 1 |
| 顺序 FP64 累加 | 0 |
| 官方 Python reference 实际输出 | 0 |
| r6 `AddScalar` 源码镜像 | 1 |
| NPU 实际输出 | 尚未执行 |

这次不能把“精确结果 1”当作改 golden 或放宽容差的理由，也不能仅凭源码镜像改 kernel。1 与 reference 0 的误差为 1，超过 FP32 `1e-4`；设备裁决仍是必需步骤。

## 发现清单

### 已验证

- round-001 reference 驱动污染已被新驱动隔离；旧实验 ID 和失败事实保留，未覆盖。
- 真实 `ml_dtypes.bfloat16` 与 float32 不相等，FP32 运行没有调用 reference 的 BF16 转换分支。
- 原 reflect 候选的输出虽然可生成，但 back pad 3 不满足 CANN 9.1 ops-math 当前 reflect 约束。
- edge 合法候选的真实 reference 四变体输出均为 0。
- r6/F 两个官方 ZIP 各 38 文件恢复身份一致；`AddScalar` 在两版本中相同。
- 当前官方模板 31 个只读文件未变化，7 个 editable 桩与历史 r6 不同是模板身份差异，不是 r6 源码变更。
- 旧 C `artifacts/a-u64src` 七个文件为 CRLF，不能直接与官方 hash 对齐；未纳入 R002 结论。

### 待验证

- 在相同 CANN 9.1/Ascend 设备上编译 r6，运行合法 edge 四变体，保存 Host 输出、实际快路/证书拒绝和标量回退证据。
- 同设备扩展合法范围内的 FP16 邻界、实际证书接受/拒绝、8192/256/128/32/64 邻界及同 shape 不同 padding 连续调用。
- 若 NPU 合法 edge 输出确为 1，最小化并确认 F 是否共同存在，再另建修复目录并做官方评测。

### 已证伪或无效

- 旧 reflect 候选不能作为正式合法反例，因为 current reflect 约束要求 pad 小于 inferred output shape。
- “reference 能运行”不等于输入属于正式合法范围。
- 不能把精确实数 1 直接覆盖 reference 0；也不能因为 reference 0 就删除 r6 补偿。
- 不能把 CPU 源码镜像、官方 Python reference 或历史官方 Pass 冒充 NPU 执行。

## 历史官方结果

本轮没有新的 CANNJudge 提交。只引用固定材料中的既存结果：

- A round-001 E003：r6 七源码 `d0b680d59d1d…`，官方 1369815 Pass，29.67 分。
- B round-001 E001：PL 七源码 `988e491ec2d8…`，官方 1369663 Pass，29.20 分。
- B 历史 r6：1367629 Pass 29.59；1367774 Pass 29.39。

这些历史结果不能替代本合法 edge 用例覆盖，也不构成本轮性能比较。

## 当前最佳有效版本

C 本轮没有产生修复版或新官方结果。用于后续设备裁决的源码身份仍是 r6 `d0b680d59d1d…`；它不是 C 宣布的共同基线。A 的历史 1369815 是当前已知 r6 最高单次观察 29.67，但稳定最佳与共同基线仍未判定。

## 未完成与下一步

- 无本机 CANN/NPU/WSL，未编译、未跑设备、未跑 Profiler 或性能。
- 未提交新的官方任务；本轮没有可用于正式结论的新官方结果。
- 可转交设备用例：`artifacts/device-case/edge-legal-cancellation/`，含四变体输入、golden、case.json 和 manifest。
- 中央有设备时，直接用同一七源码、同一模板配置进行四变体运行；不要修改 golden 或 `1e-4` 容差。
- 设备不可用前，合法 edge 候选保持 `pending`；旧 reflect 候选保持 `invalid-for-formal-legal-matrix`。

## 文件位置

- `artifacts/restored/r6-1367774/code/`、`artifacts/restored/friend-1367558/code/`：完整恢复工程
- `artifacts/tests/reference_fp32_r002.py`：干净 reference 驱动
- `artifacts/tests/make_device_case.py`：设备用例生成器
- `artifacts/results/R002-E001-reference-clean.json`：真实 reference 结果
- `artifacts/results/R002-E002-source-branch-trace.json`：合法 edge 源码分支跟踪
- `artifacts/results/R002-template-diff.json`：当前官方模板差异
- `artifacts/rules/legality.json`、`artifacts/rules/ops-math-evidence/`：合法范围证据
- `artifacts/device-case/edge-legal-cancellation/`：可转交 NPU 用例与 golden
- `artifacts/logs/`：环境、reference、生成器日志
