# PadV3Grad round-002 A 交接

先读 [summary.md](summary.md)，再读 [experiments.jsonl](experiments.jsonl)。任务 `Q06-R002-A-OFFICIAL-COMPARABILITY-20261117`，交付分支 `q06/r002/a-official-comparability`。本轮四次原样官方结果用于有界总分比较；中央共同基线未批准。

## 校验

Python 3.10+ 标准库：

```sh
python -B tools/validate_handoff.py
```

维护者审阅材料变更后可用 `--write-report --write-manifest` 刷新报告/清单。校验器只核对证据一致性，不提交评测；`.gitattributes` 保留准确字节。

## 恢复完整38文件工程

获取[官方匹配模板](https://cannjudge.cn/api/problems/6ad9ab403ff2fef7e80e2a1d/package)，或从 [P 固定官方包](https://github.com/shorydh/bisai/blob/8e245dab91700555bd619e95c70fa780305b1b37/operators/Q06/历史盘点/B/artifacts/official/1367774.zip) 解出 code/ 作为模板；后者ZIP SHA为 `18679dad71f9ea7723ca524599b0d9363861aeadf8f8032202f6391199a5a85a`。四臂31个非编辑文件逐一相同。

```sh
python -B tools/restore_sources.py --submission 6afc3b166bd0f9be377f93c5 --template /path/to/matching/code --output /path/to/new-project
```

也可 `--version <完整七源码SHA256>`；输出目录必须不存在。工具核验31模板+7源码，模板字节不匹配会拒绝，不覆盖旧目录。各臂原ZIP、包SHA及固定提交在 [恢复审计](artifacts/audit/restoration_identity.json)。

## 目录

- artifacts/code/、manifests/：四份七源码及每任务完整38文件hash。
- artifacts/official/、ranking/：带出处/源SHA的官方摘取，只保留本题准确任务指标；全量result和所有排名观察不改数。
- artifacts/submissions/、diffs/、config/：实际提交文本、回执、观察、无改动证据和前后配置。
- artifacts/plan/、reuse/：提交前冻结方案、历史P复核与当前rank缺行。
- artifacts/rules/、audit/：公开协议、C未关闭数值门、完整恢复及四臂比较。
- publication-manifest.json、validation.json：交接一致性证明，不是新官方运行。

完整raw只在机器A留存，引用的machine_A路径不是包内文件。31个官方只读模板/测试正文不重新分发；包内7源码原样，完整恢复需匹配模板。历史task不计新实验，evaluated_at未知保持null。
