# Q06 PadV3Grad / round-001 / Agent B

任务：`Q06-R001-B-COMBINE-20261117`。阅读 [summary.md](summary.md) 和 [experiments.jsonl](experiments.jsonl) 获取结果；任务全文为 [task-request.txt](task-request.txt)。

固定交接提交为 `8e245dab91700555bd619e95c70fa780305b1b37`，交付分支为 `q06/r001/b-r6-lastplan`。历史记录仍使用 `round_id=历史盘点`，本轮新组合使用 `round_id=round-001`；历史引用不构成本轮重复提交。

## 代码与身份

- `F/`：朋友原版，官方 1367558 的完整 `code/`。
- `P/`：r6 前缀合并，官方 1367774 的完整 `code/`；这是组合父版本。
- `L/`：r1 末轴缓存，官方 1362890 的完整 `code/`。
- `PL/`：P 中仅适配 r1 缓存的两个主头改动，完整38文件。

PL 七源码 SHA256：`988e491ec2d8d758adac5caa0e304cc81cb500ade732aadc9427fa1254267d41`。

可直接恢复的完整组合工程为 [PL-source.zip](artifacts/workflow/implementation/PL-source.zip)，内部根目录 `code/`。七源码与所有38文件哈希见 [candidate-identity.json](artifacts/workflow/implementation/candidate-identity.json)。官方实际工程与原始结果存放于 `artifacts/official/`，以对应任务的下载包身份核对为准。

## 证据与限制

`artifacts/workflow/` 保存恢复、分析契约、范围冻结、实施诊断和验收缺口。`artifacts/reporting/history/` 保留引用的历史官方证据，旧历史包未被覆盖。CPU 诊断为补充说明，不能用来推断 NPU 精度、资源压力或性能收益。

本机没有可用 CANN/NPU。真实设备、完整评分、计时和退化规则未核实的部分保持 pending；不把相同模板、历史 Pass 或单次分数差当作稳定性能收益。未提供的官方完成时间为 null，提交时间单独保存。

重新生成汇总可使用已安装的 Node：

```powershell
node .\artifacts\reporting\generate-reports.cjs --official .\artifacts\official\1369663.json
```

应先确认该官方结果文件与下载身份文件存在；不要从缺失文件补造测试结果。
