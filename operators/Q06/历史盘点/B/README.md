# Q06 PadV3Grad／历史盘点／Agent B

先读 [summary.md](summary.md)，结构化记录见 [experiments.jsonl](experiments.jsonl)。本轮包含40条原始官方历史与8次新增官方基线、补测和恢复，共48条记录；没有新增优化方案。

采用版本为 r6：首次官方任务1367629，Pass、29.59分；最终恢复任务1367774，Pass、29.39分。准确代码位于各记录对应的 `artifacts/official/<ID>.zip` 中，七源码相同；不要把最高单次分数当作每次复测必得分数。

所有源码包均直接从对应官方详情页下载。每包的SHA256、Host/Kernel及构建文件哈希见 `<ID>-identity.json`。原始官方总分快照缺失时保持null，二手笔记分数单独保存在 `artifacts/auxiliary/historical-reported-scores.json`，不混入正式指标。

v3c/1367477官方详情为Pass，查询排行榜时没有匹配记录，未取得总分；其原始页面、查询截图和时间已保留。历史1125548的二手总分存在冲突；朋友历史35.90也缺少本机可核对的官方总分快照。这些缺口不得补造。

完整官方ZIP包含配置、构建脚本及源码。`artifacts/platform/`是本机解压缓存，不重复上传。需要重建时在Windows PowerShell中执行：

```powershell
& .\tools\restore_sources.ps1
node .\tools\build_handoff.cjs
node .\tools\validate_handoff.cjs
```

重建时如原项目目录不存在，使用已保存且与官方源码核对过的本地版本清单，不在其他题目目录写入文件。CPU模型材料仅用于解释，不代表官方编译、正确性或性能验收。

本交接归属第六题。早期官方截图保留原图，其中本地聊天标题仍有当时的题号误称；应以官方算子PadV3Grad、本目录Q06和源码身份为准。

共享位置：`shorydh/bisai` 的 `agent-b` 分支，`operators/Q06/历史盘点/B/`；中央按明确提交编号审阅，不以main是否已有材料判断交接是否存在。
