# PadV3Grad · 平台提交日志

> 每次提交追加一条。只记录平台实测数据；没有平台数据的结论标 💡。
> 平台取最后一次提交计分，改动前必须备份能 Pass 的版本。

## 0. 当前状态

- 最新分数：
- 当前代码：
- 下一个动作：

## 1. 提交记录总表

| 实验 | 改动（单变量） | 编译 | 精度 | 每点 t（μs） | 每点 t/T | 总分 | 结论 |
|---|---|---|---|---|---|---|---|
| exp0 | 初始版本 | | | | | | 基线 |
| exp1 | | | | | | | |

## 2. 每点得分明细

| case | T（μs） | exp0 | exp1 | exp2 | exp3 |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

## 3. 关键结论

1. …

## 4. 下一步

- …

## 5. 新提交模板

```markdown
## 提交 N · <日期> · <单变量改动>
- 编译：通过 / 失败 + 首条 error
- 精度：通过 / 失败 + 失败 dtype/case
- 每点：
  | case | t | T | t/T | score |
- 总分：X（上次 Y）
- 结论：保留 / 回退；下一步
```

## 提交 · 2026-11-03 · exp1_pad_neumaier（平台回贴）
- 编译：通过
- 精度：点1 Runtime Error 100%；点2–5 Skipped
- 总分：0
- 结论：NEEDS_FIX；需定位点1 RE（infershape no-op/输出 shape、paddings GM 读取、kernel 自划分、DataCopyPad）

## 提交 · 2026-11-04 · exp3_def4（自动提交 6aeabc161dac5d235bac53db）
- def：2→4 列 + paddings.ValueDepend；infershape 读值。
- 结果：Runtime Error，0/50；点1 `std::bad_alloc`，点2–5 Skipped。

## 提交 · 2026-11-04 · exp4_no_infer（6aeabcd41dac5d235bade2c3）
- 单变量：PADV3_INFER_FROM_PADDINGS 1→0。
- 结果：Runtime Error，0/50；点1 同样 `std::bad_alloc`。排除 infershape GetData 分支为唯一根因。

## 提交 · 2026-11-04 · exp5_no_valuedepend（6aeabeb51dac5d235bb1c0cd）
- 单变量：移除 paddings.ValueDepend；def 4 列保留，infershape no-op。
- 平台状态：**Pass**；可见 **5/5 Pass**，precision_ratio=1；theory_score=0（API 原值，待核实计分字段）。
- 可见 t/T：15.96/4.79、18.59/4.51、18.83/4.55、19.48/4.70、12.87/4.80（μs）。
- 结论：ValueDepend 是 bad_alloc 触发因素；当前版本可见精度通过，性能差，暂不封 good 分。

## 恢复 · 2026-11-07 · 排行榜丢行
- 排行榜曾出现 **NO ROW**（等同 0 分）。当前 `code/` 与已验证的 `exp5_no_valuedepend` 逐字节一致。
- 重提 `6aee14d16bd0f9be378dfb6b` → **Pass**，可见 16.09/18.77/19.29/19.41/12.73μs，**15.59**。
- 说明：此前用户要求"只优化不提交"，本轮按"改到高分"先恢复该已验证版本；后续优化仍可在此基础上做。

## 下一步（性能）
- 可见 t/T ≈ 3.3–4.0，瓶颈是 `ComputeChunk` 的逐元素标量：`BuildGroups` 每元素 rank 循环 +
  每元素 `xGm_.GetValue` + `outLocal_.SetValue`。结构性方向是按最内维分段 DMA/`Duplicate` 0，
  属于重写级改动（类似 01 的 rowbatch），需单独一轮设计与本地 CPU Debug。

## Stage D · exp7_odometer（2026-11-07，6aeead4c6bd0f9be370fcb30）
- 单变量：`ComputeChunk` 每元素的 rank 层 div/mod 解码 → chunk 起点解码一次 + 逐元素进位。
- 平台：**Pass**；可见 **15.52 / 17.94 / 17.90 / 18.55 / 12.46 μs**
  （基线 16.09 / 18.77 / 19.29 / 19.41 / 12.73，**五点全部变快**）。
- 排行榜：15.55 → **15.78（+0.23）**。
- 判定：**保留**（虽然 +0.23 在总分红噪声带内，但改动是严格更少的整数运算、
  索引序列 30000 例模型逐项一致，无正确性风险；可见点一致变快）。

## Stage D · exp8_incgroup（2026-11-07，6aeeb18d6bd0f9be37188007）
- 单变量：group 计算从每元素全 rank 维重算 → 只重算 index 变化的维度（进位链）。
- 平台：**Pass**；可见 14.75 / 16.46 / 16.59 / 16.90 / 12.19 μs（exp7：15.52/17.94/17.90/18.55/12.46）。
- 排行榜：15.78 → **16.34（+0.56）**。**KEEP**。

## Stage D · exp9_constodo（2026-11-07，判分中）
- 单变量：mode 0 的 `ComputeConstantChunk` 增量 odometer + 增量 src。
- 本地：编译通过；增量 src 模型 30000 例与逐元素解码一致。
