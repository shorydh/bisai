# 报告重建

从本轮工作目录执行：

```powershell
& 'D:\nodegit\node\node.exe' .\artifacts\reporting\generate-reports.cjs
& 'D:\nodegit\node\node.exe' .\artifacts\reporting\generate-reports.cjs --official artifacts/official/<ID>.json
```

脚本仅写summary.md、experiments.jsonl、性能调优报告.md和artifacts/reporting/。输入为baseline审核、实施候选identity及主Agent正式保存的官方JSON。历史证据按SHA核验后复制到reporting/history，六次观察保留原编号和轮次；只有PL为新实验E001。

官方JSON支持id/url/status/score/table_text/read_at/header、submitted_at、evaluated_at字段；缺失值保留null。完成时间只能显式提供，header不推作完成时间。准确下载源码核验由主Agent完成后可写source_identity_verified=true和identity_evidence路径；单纯Pass不会自动判定组合收益。formal_comparability_verified应仅在完整规则与真实口径已验证后提供。

report-input.json可登记official_results（一个E001结果）、additional_artifacts及notes；不会生成虚假通用工作流state或manifest。--official从同一任务的submitted快照更新为terminal文件时，旧submitted文件保留为additional_artifacts，不新增实验；不同任务编号将拒绝，须先明确实验/观察映射，不覆盖旧观察。下载identity、38文件、ZIP哈希与冻结摘要全部匹配后才自动标记源码身份通过。生成后validation.json检查固定21字段和输出身份。
