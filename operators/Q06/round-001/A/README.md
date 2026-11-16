# PadV3Grad round-001 A 交接

先读 [summary.md](summary.md)，结构化记录为 [experiments.jsonl](experiments.jsonl)。任务 `Q06-R001-A-BASELINE-20261117`，没有批准或覆盖中央共同基线。

## 校验

使用 Python 3.10+ 标准库，在本目录执行：

```sh
python -B tools/validate_handoff.py
```

该工具核验固定 schema、源码、官方任务/指标、排行绑定及发布文件 SHA256；不调用官方评测。`.gitattributes` 禁用换行转换以保留证据和源码的准确字节。

## 恢复完整工程

先从 [官方入口](https://cannjudge.cn/public/ictcompetition/padv3grad) 取得匹配模板（当前包接口 `https://cannjudge.cn/api/problems/6ad9ab403ff2fef7e80e2a1d/package`）。也可按权限读取 [B 固定历史包](https://github.com/shorydh/bisai/blob/8e245dab91700555bd619e95c70fa780305b1b37/operators/Q06/历史盘点/B/artifacts/official/1367774.zip)，先核对 ZIP SHA256 `18679dad71f9ea7723ca524599b0d9363861aeadf8f8032202f6391199a5a85a`，其 `code/` 已证明与 A 的 31 readonly 文件相同。

```sh
python -B tools/restore_sources.py --submission 6afb3e276bd0f9be37ed9f96 --template /path/to/matching/official/code --output /path/to/new-restored-project
```

`--submission` 换成 JSONL 对应任务，也可用 `--version` 指定完整七源码哈希。输出目录必须不存在。工具验证 31 模板+7提交文件并恢复完整38文件；模板变化会明确失败，不会悄悄覆盖或修改冻结代码。

## 目录与边界

- `artifacts/code/`：三个去重的七源码原样快照。
- `artifacts/manifests/`：每个官方任务实际38文件哈希。
- `artifacts/official/`：带源文件SHA和官方URL的明确字段摘取；全部result指标原样保留。
- `artifacts/ranking/`：只摘取准确 submission_id 的排行行，保留所有重复观测。
- `artifacts/submissions/`：实际七文件输入、冻结清单、回执、状态观察与一致性核对。
- `artifacts/config/`、`artifacts/rules/`：每次任务前后官方配置和规则核验。
- `artifacts/audit/`：三工程恢复、配置/入口审计、历史任务访问限制。
- `artifacts/historical_references.json`：固定Git提交与历史身份，不重命名为本轮实验。
- `publication-manifest.json`、`validation.json`：交接一致性校验，不是官方精度/性能新结果。

`evaluated_at` 不填提交时间。总分只取精确绑定的官方排行行；动态 TBest 和计时/退化定义的证据缺口见摘要。当前最高单次分数不代表稳定最佳，团队共同基线仍待中央审批。
