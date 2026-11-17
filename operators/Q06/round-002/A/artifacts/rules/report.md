# Q06 PadV3Grad · round-002 · A：公开协议与 C 数值门复核

任务 `Q06-R002-A-OFFICIAL-COMPARABILITY-20261117`。本审查只执行既有授权会话的官方 GET 和固定 Git 源码静态读取，未提交评测、修改算子或重做 C 的数值实验。观测时间、URL、原始响应 SHA-256、条件及分类见 [evidence.json](evidence.json)。

## 可执行的比较口径

本轮可以比较**准确绑定版本、任务及观测时刻的有效官方总分**。隐藏输入、隐藏耗时、隐藏 TBest、完整后台实现以及未公开的计时细节，不应成为无限前置条件。该结论的边界是“所记录官方观测分数的比较”；不能改写为稳定因果性能提升、固定隐藏标尺下的提升、算子加速比或全规格正确性证明。

每个纳入正式比较的记录应完成以下有限核验：

1. 同题目 ID，实际提交源码可恢复；七个可改文件与完整 38 文件及模板的身份绑定准确。
2. 记录官方终态、`valid`、`judge_revision`、`public_only`、测试数及缺项标记；有效性能比较要求 Pass 且 valid=true。
3. 公开配置与协议一致，或明确列出已知差异并缩小比较范围。
4. 总分绑定准确 `submission_id`，保存官方原始值、结果引用及观测时间；保留全部重复运行。
5. 记录公开用例身份及能取得的精确 TBest；仅有页面舍入值时说明精度不足，不能假定隐藏标尺固定。

符合这些条件即可做有界官方分数比较，无需请求隐藏数据；某记录缺少具体有效性字段时，针对该缺项补取或重提即可。历史任务证据齐全可复用，保留原轮次与任务身份，GET 刷新不计作新实验。B 既有页面档案未独立确证 valid/revision，TBest 只有显示精度；应由本轮逐任务审计决定是否足够，必要时由 A 授权重提补齐，不能拿旧分数直接填空。

四臂 F/L/P/PL 组合结论要求四臂均满足同一核验条件。若只有 P/PL 满足，先报告该对比，四臂结论保留 pending。公开 TBest 一致只支持公开可观测部分一致；总分的数值差可直接报告，不能反推未提供的逐用例性能或速度比。数值门另行约束是否能无条件推荐共同基线。

## 本轮公开协议复核

2026-11-17 11:26:46–47 UTC（北京时间 19:26:46–47）刷新了 [题目 API](https://cannjudge.cn/api/problems/6ad9ab403ff2fef7e80e2a1d) 和[官方默认评分说明源码](https://cannjudge.cn/js/pages/scoring-rules-content.js)，均返回 HTTP 200。题目指定配置与上轮 A 证据一致：v1、`gitcode_template_noopapi`、CANN 9.1.0、revision 0、score_mode 1、use_baseline false、iterations 5、ranking_submission_mode latest、ranking_testcase_count null、judge_baseline_verified false、difficulty 3。

默认评分 JS 的 SHA-256 为 `403196242914b295dd27e81e1faa542649f5a4f940f79258ad5c7807093ba60a`，与上轮完全相同。本轮沿用[上轮 A 固定提交的规则证据](https://github.com/shorydh/bisai/blob/cb4016d4406b245461f57998f693d7feacc0e297/operators/Q06/round-001/A/artifacts/rules/report.md)，并明确上述两项本轮已复核。

已取得的官方默认说明展示单点 `100/(1+log(time/TBest)/log(1.5))`、普通题对测试点取平均并保留两位小数，TBest 随历史最佳提交动态更新；latest 选择最新提交。它是公开前端默认规则生成器，不等于独立取得并验证了当前竞赛全部后台实现。赛事文章中的基础分、难度权重与首名奖励属于另外的赛制层，不应和单点公式混写。

题面当前仍要求所有合法场景泛化，阈值 float 1e-4、half 1e-3、int 0。阈值不等于已取得完整比较器算法。iterations=5 不足以确定预热、同步或聚合统计。计时口径、硬件/负载、降级阈值、公式边界实现及隐藏 TBest 是否跨时刻固定均保留未知；不猜测公式边界。这些未知限制性能因果归因，不否定有界官方观测分比较。

## C 的具体未关闭数值门

审查固定 C commit `9f0c24f6609a8641f083249a815bdaddef4147cf`。C 原始 summary/JSONL 位于 `operators/Q06/round-001/C`，实验 artifacts 在仓库根目录。该固定提交中没有 C 包目录下的 README.md，已用 git show/ls-tree 核对，并读取实际存在的 `artifacts/tests/README.md`。原任务 `Q06-R001-C-BOUNDARY-20261117`，E004 不是官方提交或 NPU 运行；不能沿用其旧 `verified` 标签声称已通过原依赖 reference 裁决。

[E004 包装脚本第 32–35 行](https://github.com/shorydh/bisai/blob/9f0c24f6609a8641f083249a815bdaddef4147cf/artifacts/tests/reference_minimal_case.py#L32-L35) 在 `ml_dtypes` 尚未导入时，把 `bfloat16` 替成 `np.dtype("float32")`。未改动的官方 reference 会判断 `x.dtype == bfloat16`，因此原 FP32 输入走 `torch.bfloat16` 转换分支，在 FP64 累积之前改变了数值。这是依赖语义被改变，不是“原依赖 FP32 reference”。官方 reference 文件 SHA-256 为 `1542d63e602aa3aaa60242e91ea0d6a8ac038bab788c6898dc4777557f040ed3`。

同脚本第 83、102、106、108 行另将 `official_zero=0.0` 写死，再据此生成摘要及误差判断，未从实际 reference 返回值派生。原四次 reference_runs 确实记录了替代依赖条件下的零输出，不能据此认定记录造假；问题是该执行条件不能认证真实依赖路径。

保留的候选输入为 FP32 `[1,1,1,6]`、`[0,1.7e38,0,1,0,-1.7e38]`、最后维 reflect padding `[1,3]`，输入字节 SHA-256 为 `daa2b4341c6f1f56616b24a8195cbfd4bdd8ede0201f9370f72d415c7e4559b7`。CPU 模型风险线索仍可保留，但上述静态缺陷既不证明真实 reference 会得到另一个输出，也不证明真实 NPU 内核已失败。

关闭此门需要 C：用真实 numpy/torch/ml_dtypes 依赖运行同一 SHA 的原 reference，保存依赖版本、输入字节、dtype/padding/layout 与实际输出；断言和摘要从实际输出计算；再取得冻结版本在 NPU 上对同一合法输入的实际输出及调用/分支证据，按明确的精度口径裁决。若修复，需新不可变源码版本及其官方验证。r6 与 friend 的外层前缀优化不自动解决此数值风险，PL 也不能被默认认为已做过该候选测试。

本审查将旧 E004 的“真实原依赖 reference 已验证”资格记 invalid，将真实 reference 与 NPU 裁决记 pending。该具体数值门阻止无条件批准团队共同基线；不阻止记录合格官方任务并比较其有界总分。

## 交接范围

最小公开材料为本文件和 `evidence.json`；引用固定 Git 原件并列出 SHA，不复制身份、Cookie 或无关参赛者信息。`raw/` 和 `source-c-summary/` 是 A 本地取证副本，公开交接不需要上传。这里没有新增官方实验结果；实际任务状态与每次总分由主执行者的提交/取证记录补齐。
