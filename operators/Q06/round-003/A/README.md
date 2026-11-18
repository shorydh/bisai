# Q06 round-003 A 交接包

先读 [summary.md](summary.md)、[任务单](artifacts/task.txt) 与 [experiments.jsonl](experiments.jsonl)。

完整冻结工程位于 `artifacts/code/<source_tree_sha256>/`，无额外 code/ 层；以对应 `artifacts/manifests/<submission_id>.json` 校验全部38文件，不能只比较分支名。UTF-8/LF 源码按字节复制，本目录 `.gitattributes` 禁止 Git 自动转换。

构建和测试入口及旧 UT fixture 缺项见 [入口审计](artifacts/restoration/entrypoints.md)。不要修改冻结目录来调试；诊断副本另留源码差异。

[恢复脚本](artifacts/restoration/restore_frozen.py)可从准确 PL 工程和同目录补丁重建两臂；目标目录必须尚无 PL/PL-lazy，脚本拒绝覆盖。该脚本没有提交或构建动作。

`tools/official_r003.py` 与 `tools/build_handoff_r003.py` 是本机流程代码存档，默认路径依赖原 `work/Q06/round-003/A` 布局；不能在交接目录直接重跑来发送请求。官方请求已完成的计划不可直接复跑。

[文件清单](publication-manifest.json)记录交接文件 SHA，[构建器检查](validation.json)仅验证数据结构及身份，独立复核另记。原始账号会话、凭据和其他提交者排行没有收录。
