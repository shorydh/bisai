// Re-run with: node artifacts/reporting/generate-reports.cjs [--official artifacts/official/<id>.json]
// This script owns only the three reports and artifacts/reporting/.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '../..');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const read = file => JSON.parse(fs.readFileSync(path.resolve(root, file), 'utf8').replace(/^\uFEFF/, ''));
const exists = file => fs.existsSync(path.resolve(root, file));
const rel = file => path.relative(root, file).replaceAll('\\', '/');
const task = 'Q06-R001-B-COMBINE-20261117';
const fixed = '8e245dab91700555bd619e95c70fa780305b1b37';
const fields = ['experiment_id','operator','round_id','agent_id','task_id','base_version','candidate_version','hypothesis','change','official_task_id','official_result_ref','evaluated_at','evaluation_protocol','official_status','official_metrics','baseline_official_result_ref','comparison','finding_status','applicability','artifacts','notes'];
const baseline = 'artifacts/workflow/baseline/';
const audit = read(baseline + 'historical-evidence-audit.json');
const restore = read(baseline + 'restoration-identity.json');
const candidatePath = 'artifacts/workflow/implementation/candidate-identity.json';
const candidate = exists(candidatePath) ? read(candidatePath) : null;
const configPath = 'artifacts/reporting/report-input.json';
const config = exists(configPath) ? read(configPath) : {official_results:[], lifecycle:'ongoing'};
const argv = process.argv.slice(2);
for (let i=0; i<argv.length; i++) {
  if (argv[i] === '--official' && argv[i+1]) {
    const value = rel(path.resolve(root, argv[++i]));
    config.official_results ??= [];
    if (!config.official_results.includes(value)) {
      const incoming = read(value);
      const incomingId = incoming.id ?? incoming.official_task_id;
      const existingIndex = config.official_results.findIndex(file => { const old=read(file); return (old.id??old.official_task_id)===incomingId; });
      if (existingIndex>=0) {
        config.additional_artifacts ??= [];
        if (!config.additional_artifacts.includes(config.official_results[existingIndex])) config.additional_artifacts.push(config.official_results[existingIndex]);
        config.official_results[existingIndex]=value;
      } else config.official_results.push(value);
    }
  } else throw Error('Supported arguments: --official <path>, optionally repeated.');
}
fs.mkdirSync(__dirname, {recursive:true});
fs.writeFileSync(path.join(root, configPath), JSON.stringify(config,null,2)+'\n');
const historyOutput = path.join(__dirname, 'history');
fs.mkdirSync(historyOutput,{recursive:true});
const archiveManifest = [];
const copyEvidence = evidence => {
  const dest = path.join(historyOutput,path.basename(evidence.path));
  const localSource = fs.existsSync(dest) ? dest : evidence.path;
  const bytes = fs.readFileSync(localSource);
  if (sha(bytes)!==evidence.sha256) throw Error('Changed historical evidence: '+evidence.path);
  if (fs.existsSync(dest) && sha(fs.readFileSync(dest))!==evidence.sha256) throw Error('Conflicting report evidence: '+dest);
  fs.writeFileSync(dest,bytes);
  archiveManifest.push({file:rel(dest),sha256:evidence.sha256,original_path:evidence.path,source_commit:fixed});
  return rel(dest);
};
const armForHash = hash => restore.arms.find(x=>x.seven_source_sha256===hash)?.arm ?? 'unknown';
const rows = audit.historical_records.map(h => {
  const evidence = h.evidence.map(copyEvidence);
  const arm = armForHash(h.seven_source_sha256);
  const zip = evidence.find(x=>x.endsWith('.zip'));
  return {
    experiment_id:h.experiment_id,operator:'PadV3Grad',round_id:'历史盘点',agent_id:'B',task_id:null,
    base_version:null,candidate_version:{arm,source_commit:fixed,seven_source_sha256:h.seven_source_sha256,official_source_package:zip,package_sha256:h.package_sha256},
    hypothesis:'历史官方观察引用：'+arm+'局部对照；不计为本轮新实验',change:'无代码修改；准确官方历史包原样恢复，引用存档结果',
    official_task_id:h.official_task_id,official_result_ref:h.official_result_ref,evaluated_at:null,
    evaluation_protocol:{environment:'CANNJudge官方提交环境（历史存档）',problem_url:'https://cannjudge.cn/public/ictcompetition/padv3grad',submitted_at:h.submitted_at,observed_at:h.observed_at,completion_time_provided:false,source_identity:'官方ZIP/七源码与存档identity核对',public_cases:5,hidden_cases:45,scoring_formula:null,timing_protocol:null,actual_soc:null,cloud_metrics_used:false,reused_for_task:task,not_a_new_measurement:true},
    official_status:h.official_status,official_metrics:h.official_metrics,baseline_official_result_ref:null,
    comparison:{comparable:null,conclusion:'pending',explanation:'同题目、同日、完整模板相同；完整历史评分/计时/退化口径及设备未知，单次总分不能证明稳定收益。'},
    finding_status:'verified',applicability:'仅验证该准确源码该次官方Pass与实际存档指标；不证明稳定收益或全合法输入正确性。',artifacts:evidence,
    notes:[...h.notes,'任务编号保持历史原值null；本轮引用任务为'+task+'，不将历史编号/轮次改为新实验。','finding_status=verified仅指存档观察，性能比较仍pending。']
  };
});
const officialResults = (config.official_results ?? []).map(file=>({file,data:read(file)}));
if (officialResults.length > 1) throw Error('Only E001 allocated; preserve multiple observations inside one result bundle or obtain explicit experiment IDs before adding rows.');
const official = officialResults[0]?.data ?? null;
const officialFile = officialResults[0]?.file ?? null;
const approvalBlockPath = 'artifacts/official/submission-approval-block.json';
const approvalBlock = !official && !config.approval_block_resolved && exists(approvalBlockPath) ? read(approvalBlockPath) : null;
const officialId = official?.id ?? official?.official_task_id ?? null;
const actualOfficialZip = officialId && exists(`artifacts/official/${officialId}.zip`) ? `artifacts/official/${officialId}.zip` : null;
const status = official?.status ?? official?.official_status ?? null;
const score = official?.score ?? official?.official_metrics?.total_score ?? null;
const url = official?.url ?? official?.official_result_ref ?? null;
const parsePublic = text => (text ?? '').split(/\r?\n/).map(line=>line.split('\t')).filter(c=>/^\d+$/.test(c[0]) && Number(c[0])<=5 && c[1]!=='*（隐藏）').map(c=>({case:c[0],status:c[1],output_error_ratio:c[2]??null,time:c[3]??null,best_time_displayed:c[4]??null}));
const officialMetrics = official && (official.official_metrics || official.table_text || score!==null) ? (official.official_metrics ?? {total_score:score,public_cases:parsePublic(official.table_text),raw_public_table_text:official.table_text??null}) : null;
const p = restore.arms.find(x=>x.arm==='P');
const downloadedIdentityPath = official?.identity_evidence ?? (officialId && exists(`artifacts/official/${officialId}-identity.json`) ? `artifacts/official/${officialId}-identity.json` : null);
const downloadedIdentity = downloadedIdentityPath ? read(downloadedIdentityPath) : null;
const sourceIdentityVerified = Boolean(downloadedIdentity && candidate && actualOfficialZip && downloadedIdentity.all_files_match===true && downloadedIdentity.file_count===38 && downloadedIdentity.seven_source_sha256===candidate.seven_source_sha256 && downloadedIdentity.all_38_file_sha256===candidate.all_38_file_sha256 && downloadedIdentity.package_sha256===sha(fs.readFileSync(path.join(root,actualOfficialZip))) && downloadedIdentity.files.length===38 && downloadedIdentity.files.every(f=>f.match && f.expected_sha256===f.actual_sha256) && (downloadedIdentity.outside_code??[]).length===0);
if (official?.source_identity_verified===true && !sourceIdentityVerified) throw Error('Official claims verified identity without matching downloaded identity/ZIP evidence');
const protocolVerified = official?.formal_comparability_verified === true;
const snapshotPath = 'artifacts/workflow/implementation/PL-source.zip';
const candidateArtifacts = [candidatePath,snapshotPath,'artifacts/workflow/analysis/round1/implementation-contract-PL.json','artifacts/workflow/analysis/round1/source-isolation-PL.json'].filter(exists);
if (officialFile) candidateArtifacts.push(officialFile);
if (actualOfficialZip) candidateArtifacts.push(actualOfficialZip);
if (downloadedIdentityPath) candidateArtifacts.push(downloadedIdentityPath);
const diagnosticPath = 'artifacts/workflow/implementation/planner-result.json';
const diagnostic = exists(diagnosticPath) ? read(diagnosticPath) : null;
const reachabilityPath = 'artifacts/workflow/implementation/host-reachability.json';
const reachability = exists(reachabilityPath) ? read(reachabilityPath) : null;
for (const file of [diagnosticPath,reachabilityPath,'artifacts/workflow/implementation/scheme-conformance.json','artifacts/workflow/implementation/scheme-conformance-gate.json','artifacts/workflow/implementation/harness-extraction.json','artifacts/workflow/implementation/harness-build.log','artifacts/workflow/implementation/planner-result.raw.txt','artifacts/workflow/implementation/snapshot-manifest.json',official?.ranking_evidence,officialId?`artifacts/official/${officialId}-ranking.jpg`:null]) if (file && exists(file)) candidateArtifacts.push(file);
const descriptiveDeltas = score===null ? [] : audit.historical_records.map(h=>({baseline_official_task_id:h.official_task_id,arm:armForHash(h.seven_source_sha256),baseline_score:h.official_metrics.total_score,candidate_score:score,score_delta_points:Number((score-h.official_metrics.total_score).toFixed(2)),comparison_type:'descriptive_score_arithmetic_only',performance_gain_proven:false}));
if (approvalBlock) candidateArtifacts.push(approvalBlockPath);
for (const extra of config.additional_artifacts ?? []) if (exists(extra)) candidateArtifacts.push(extra);
rows.push({
  experiment_id:'Q06-R001-B-E001',operator:'PadV3Grad',round_id:'round-001',agent_id:'B',task_id:task,
  base_version:{arm:'P',source_commit:fixed,official_task_id:1367774,seven_source_sha256:p.seven_source_sha256,official_source_package:'artifacts/reporting/history/1367774.zip',package_sha256:p.package_sha256},
  candidate_version:candidate ? {arm:'PL',snapshot:candidateArtifacts.find(x=>x.endsWith('PL-source.zip'))??candidate.snapshot,seven_source_sha256:candidate.seven_source_sha256,all_38_file_sha256:candidate.all_38_file_sha256,main_header_sha256:candidate.main_header_sha256,identity:candidatePath,snapshot_package_sha256:exists(snapshotPath)?sha(fs.readFileSync(path.join(root,snapshotPath))):null,official_source_package:actualOfficialZip,package_sha256:actualOfficialZip?sha(fs.readFileSync(path.join(root,actualOfficialZip))):null} : null,
  hypothesis:'r6前导恒等轴合并后，r1末轴Contributors跨行缓存是否继续减少索引规划成本并带来可保留官方收益。',
  change:'相对P，仅在PL/op_kernel/pad_v3_grad.h移植L的两处缓存改动；保持outputWidth<=32且本核count>outputWidth守卫、原枚举顺序及其余37文件。',
  official_task_id:officialId,official_result_ref:url,evaluated_at:official?.evaluated_at??null,
  evaluation_protocol:{environment:'CANNJudge官方提交环境',problem_url:'https://cannjudge.cn/public/ictcompetition/padv3grad',submitted_at:official?.submitted_at??null,submission_header:official?.header??null,observed_at:official?.read_at??official?.observed_at??null,completion_time_provided:official?.evaluated_at!=null,source_identity_verified:sourceIdentityVerified,identity_evidence:downloadedIdentityPath,formal_comparability_verified:protocolVerified,scoring_formula:official?.scoring_formula??null,timing_protocol:official?.timing_protocol??null,actual_soc:official?.actual_soc??null,public_cases:5,hidden_cases:45,cloud_metrics_used:false,auxiliary_diagnostics:diagnostic?{source:diagnosticPath,device_execution:diagnostic.device_execution,status:diagnostic.status,cases:diagnostic.cases,ranges:diagnostic.ranges,scope:diagnostic.checker_scope}:null,submission_block:approvalBlock?{status:approvalBlock.status,reason:approvalBlock.reason,action:approvalBlock.action,official_task_created:false,next_action:approvalBlock.next_action,evidence:approvalBlockPath}:null},
  official_status:status,official_metrics:officialMetrics,baseline_official_result_ref:'https://cannjudge.cn/public/ictcompetition/padv3grad/submission/6afb1ec66bd0f9be37b4e0f3',
  comparison:{comparable:protocolVerified?true:null,conclusion:'pending',descriptive_score_deltas:descriptiveDeltas,explanation:'差值仅为归档总分算术，不是已验证性能收益。正式四臂性能结论须准确PL有效结果及同口径证据。完整计时/评分/退化规则与波动解释尚不足；不以P/L历史Pass替代PL，不叠加单项收益。'},
  finding_status:status && status!=='Pass' && !/Running|Pending|Queue/i.test(status)?'invalid':'pending',
  applicability:'仅本次冻结PL及实际已保存验证范围；CPU诊断只解释映射/顺序，不代替官方构建、精度或性能。',artifacts:[...new Set(candidateArtifacts)],
  notes:['evaluated_at只接受官方明确完成时间；提交时间另记，缺失填null。','无完整协议证据时不宣称稳定收益、无退化或团队共同最佳。','本轮唯一新实验E001；辅助边界诊断全部归同一准确PL快照。',...(config.notes??[])]
});
const localScreenshotsPath = 'artifacts/official/local-screenshots.json';
const imagesLocalOnly = exists(localScreenshotsPath) && read(localScreenshotsPath).status === 'images_local_only';
if (imagesLocalOnly) {
  rows.at(-1).notes.push('Three screenshots retained locally after automatic approval rejected image upload; remote package uses original ranking text/JSON/official ZIP. See artifacts/official/local-screenshots.json.');
  rows.at(-1).artifacts.push(localScreenshotsPath);
}
for (const row of rows) if (Object.keys(row).join(',')!==fields.join(',')) throw Error('21-field schema/order violation');
fs.writeFileSync(path.join(root,'experiments.jsonl'),rows.map(x=>JSON.stringify(x)).join('\n')+'\n');
const historyRows = rows.filter(x=>x.round_id==='历史盘点').map(x=>`| ${x.experiment_id} | ${x.candidate_version.arm}，无代码修改／历史引用 | \`${x.candidate_version.seven_source_sha256.slice(0,12)}\` | 官方存档 | [${x.official_task_id}](${x.official_result_ref}) | ${x.official_status}，${x.official_metrics.total_score}分 | 性能比较pending | [证据](${x.artifacts[0]}) |`);
const plRow = rows.at(-1);
const table = ['| 实验编号 | 假设与改动 | 准确代码版本 | 测量来源 | 官方任务 | 官方状态／实际指标 | 比较与结论 | 证据 |','|---|---|---|---|---|---|---|---|',...historyRows,`| Q06-R001-B-E001 | P上适配L末轴计划缓存，仅两处主头改动 | ${candidate?'`'+candidate.seven_source_sha256.slice(0,12)+'`':'待冻结'} | ${official?'官方结果已存档':'准备／静态诊断；无新官方结果'} | ${officialId?'['+officialId+']('+url+')':'null'} | ${status??'null'}；总分${score??'null'} | pending，${sourceIdentityVerified?'提交源码身份已核验':'官方送测源码身份待核验'} | [候选身份](${candidatePath})${officialFile?'／[官方结果]('+officialFile+')':''} |`].join('\n');
const buildState = official ? `官方任务[${officialId}](${url})返回${status??'未知状态'}${score!==null?'，实际总分'+score:''}。${sourceIdentityVerified?'下载工程全部38文件与冻结PL一致，ZIP及源码身份已核验。':'下载工程与冻结快照身份待核验，未将结果升级为准确候选结论。'}${/Running|Pending|Queue/i.test(status??'')?'任务尚未终态，编译、官方精度及官方性能未宣称完成。':''}` : approvalBlock ? `点击“提交代码”被自动审批审查拒绝，未创建官方任务（[原始拒绝](${approvalBlockPath})）。原因为当前可信直接用户授权不足以涵盖该具体外部提交动作。等待用户直接授权本次PL七源码\`${candidate?.seven_source_sha256??approvalBlock.candidate_seven_source_sha256}\`提交后继续；不重试或换接口绕过。编译、官方精度及官方性能均未完成，这不是算子失败。` : config.approval_block_resolved ? '用户已直接授权准确PL官方提交评测，主Agent已执行提交动作，任务编号与终态仍等待保存。先前自动审批拒绝仅作为流程历史保留，当前不再是授权阻塞。编译、官方精度和官方性能尚未宣称完成。' : '尚无本轮新官方结果；编译、官方精度和官方性能均未宣称完成。';
const summary = `# 第六题 PadV3Grad／round-001／Agent B\n\n任务：\`${task}\`。用户授权的实验为F/P/L/PL四臂局部比较；团队共同基线由A/中央核验，本报告不设定或覆盖。交付分支：\`q06/r001/b-r6-lastplan\`，起点固定提交\`${fixed}\`。当前文件来自隔离工作目录，发布映射为\`operators/Q06/round-001/B/\`；新的发布commit尚待主Agent登记。\n\n${table}\n\n## 已验证与待验证\n\n- 已验证：F/P/L完整38文件从指定官方ZIP恢复，ZIP与七源码一致；31个非编辑模板文件和所有37个非主头文件相同。固定提交ZIP的Git blob核对见[远端身份](artifacts/fixed-commit-zip-checks.json)。\n- 已验证：F两次28.61/28.66，P两次29.59/29.39，L两次29.23/28.84，全部历史观察保留；它们是历史引用，不能重复计为本轮新测。\n- ${candidate?'已冻结PL：七源码`'+candidate.seven_source_sha256+'`，仅主头两处移植，其余37文件保持P。':'PL候选身份待生成。'}\n- ${buildState}\n- 待验证：实际官方设备/计时/完整评分/退化规则及跨历史版本一致性，单次得分波动与PL四臂正式比较。相同模板只证明工程一致，不证明全部性能协议相同。\n- 数值/回退边界诊断与栈/寄存器压力须引用实际材料；CPU模型只作辅助，不能替代官方结论。\n\n## 当前保留版本与下一步\n\n当前沿用交接保留P/r6，依据1367774 Pass29.39；历史最高单次29.59对应1367629。尚未判定PL可替换P，也未判定团队共同最佳。F/P/L单项观察不能相加或相乘；正式比较pending时不据此切换。\n\n继续按同一冻结PL取得并保存官方终态、公开五点实际指标与准确总分绑定，下载本条工程核对全部38文件；保留失败与所有复测。A共同基线若不同再补列，C反例若出现另建明确实验，不能用历史Pass覆盖。\n\n## 异常、未完成事项与工作流边界\n\n本机Windows未发现可用CANN/NPU；python/python3仅WindowsApps占位。通用Python五阶段manifest/state、canonical采集、全case逐SoC目标及本地构建/加载门禁未完成，未伪造成功。用户指定官方协议优先，授权实验实际结果与通用工作流未完成分别报告。\n\n官方模板只提供首样例FP32 seed42、reflect、[1,1,8,8]→[1,1,4,4]，rtol=atol=1e-4，bad<=1e-4*N；-e不证明全量精度。真实UT旧fixture与README跳过描述不一致，仍含不存在的totalNum，尚未执行，不写实际编译失败。\n\n历史旧包evaluated_at实际为提交时间；本轮引用使用submitted_at，未提供完成时间均为null。固定历史包未修改。评分公式、隐藏测试耗时与精确测量口径未知，不推算或绕过隐藏数据。\n\n材料：[21字段JSONL](experiments.jsonl)、[恢复身份](${baseline}restoration-identity.json)、[环境报告](${baseline}环境检查报告.md)、[入口审计](${baseline}entrypoints-audit.json)、[历史观察](${baseline}historical-evidence-audit.json)、[分析契约](artifacts/workflow/analysis/round1/implementation-contract-PL.json)、[报告生成器](artifacts/reporting/generate-reports.cjs)。\n`;
const diagnosticText = diagnostic ? `辅助源码规划诊断${diagnostic.status}：[${diagnostic.cases}组形状、${diagnostic.ranges}核区间](${diagnosticPath})，其中真实Host切分${diagnostic.host_ranges}、人工边界区间${diagnostic.synthetic_ranges}；缓存活动${diagnostic.cache_active_ranges}区间，快路拒绝${diagnostic.rejected}。验证顺序/偏移/回退复位及调用间padding变化，seed=${diagnostic.seed}。device_execution=false，未执行设备Vector数学或half算术，不能冒充全量NPU精度；实际栈/寄存器压力仍未知。` : '数值/回退边界诊断与栈/寄存器压力须引用实际材料；CPU模型只作辅助，不能替代官方结论。';
const terminal = status && !/Running|Pending|Queue/i.test(status);
const currentNextAction = terminal ? '本次官方终态与下载工程身份已保存；下一步核验官方完整评分/计时/退化规则及四臂可比性，必要时按事前明确的比较计划补证。保留失败与全部重复观察；不因单次分数切换保留版本。' : '继续按同一冻结PL取得并保存官方终态、公开五点实际指标与准确总分绑定，下载本条工程核对全部38文件；保留失败与所有复测。';
const publicTimesText = officialMetrics?.public_cases?.length ? `\n\n本次官方公开耗时（按测试点1—5）：${officialMetrics.public_cases.map(x=>x.time).join('、')}；仅为公开点指标，不推算45个隐藏点或整体加速比。` : '';
const deltaTable = descriptiveDeltas.length ? '\n\n## 描述性分数观察\n\n以下仅为PL总分减历史总分的算术差，不是已验证的性能收益，也不是算子加速比。\n\n| 局部对照任务 | 臂／得分 | PL得分 | 分数差（点） |\n|---|---|---|---|\n'+descriptiveDeltas.map(x=>`| ${x.baseline_official_task_id} | ${x.arm}／${x.baseline_score.toFixed(2)} | ${x.candidate_score.toFixed(2)} | ${x.score_delta_points>0?'+':''}${x.score_delta_points.toFixed(2)} |`).join('\n')+'\n\nPL公开五点均比P最新存档1367774更快，但总分29.20低于29.39。公开点不足以解释总分方向；不反推隐藏点耗时，不宣称整体加速或稳定退化。' : '';
const hostText = reachability ? `\n\n辅助Host可达性枚举[${reachability.examined}项](${reachabilityPath})，${reachability.violations}违反条件结论。条件为${reachability.conditional_statement} 这是假设核数下的源码公式检查；官方实际核数未知，不能把人工count>width范围当作官方必经路径，也不能据此否定全部缓存价值。` : '';
const finalSummary = summary.replace('数值/回退边界诊断与栈/寄存器压力须引用实际材料；CPU模型只作辅助，不能替代官方结论。',diagnosticText+hostText).replace('继续按同一冻结PL取得并保存官方终态、公开五点实际指标与准确总分绑定，下载本条工程核对全部38文件；保留失败与所有复测。',currentNextAction).replace('## 当前保留版本与下一步',publicTimesText+deltaTable+'\n\n## 当前保留版本与下一步').replace('当前沿用交接保留P/r6，依据1367774 Pass29.39；历史最高单次29.59对应1367629。',terminal?`当前建议保留源码P/r6，依据其有效存档1367774 Pass29.39；历史最高单次29.59对应1367629。平台最后实际提交是PL任务${officialId} ${status} ${score?.toFixed(2)??'null'}分，未重新提交P，也不将建议源码与当前排行榜提交混为一谈。`:'当前沿用交接保留P/r6，依据1367774 Pass29.39；历史最高单次29.59对应1367629。')+'\n本轮只新增一个准确组合假设和一次官方实验E001；边界规划、回退、Host可达性诊断均归同一快照。六条历史引用不计作新实验；流程检查不为凑次数新增无关修改。\n';
const integrationPath = 'artifacts/workflow/integration/VERIFY_REPORT.md';
const integrationLink = exists(integrationPath) ? `\n最终隔离交付核验：[VERIFY_REPORT.md](${integrationPath})。\n` : '';
fs.writeFileSync(path.join(root,'summary.md'),finalSummary.replace('新的发布commit尚待主Agent登记。','精确发布commit见交付消息；该commit不写入自身文件以避免自引用。').replace('其中真实Host切分','其中按Host公式生成的区间')+`\n交付状态：\`${config.lifecycle??'ongoing'}\`。${terminal?'本次官方终态已取得，无活动授权阻塞；':'官方终态仍等待；'}正式性能可比性、稳定最佳与中央共同基线仍未判定。\n`+integrationLink);
fs.writeFileSync(path.join(root,'性能调优报告.md'),`# PadV3Grad本轮性能调优现场报告\n\n唯一报告事实源为[summary.md](summary.md)和[experiments.jsonl](experiments.jsonl)；本文件由同一脚本生成，不另维护并行阶段状态。\n\n任务\`${task}\`，当前${config.lifecycle??'ongoing'}。${buildState}\n\nP→PL仅适配L末轴缓存；F/P/L局部对照全部历史重复观察保留。正式四臂结论pending，当前仍保留P/r6。\n\n通用本地五阶段工作流未完成；源码隔离、官方实验取证与本地环境缺口分别如实报告。完整计时/评分/退化协议未知，未输出算法加速比或稳定收益。\n\n${table}\n`);
fs.writeFileSync(path.join(__dirname,'historical-artifacts-manifest.json'),JSON.stringify({source_commit:fixed,files:archiveManifest},null,2)+'\n');
if (imagesLocalOnly) fs.appendFileSync(path.join(root,'summary.md'),'\n\n## 共享证据范围\n\n自动审批拒绝截图上传；三份原图只保留在本地，未重试传输。截图文件名及SHA256见[本地图像清单](artifacts/official/local-screenshots.json)。仓库提供实际官方工程ZIP、JSON、排行榜原始文字和源码/测试证据。\n');
const verification = {schema_version:1,task_id:task,generated_at:new Date().toISOString(),lifecycle:config.lifecycle??'ongoing',records:rows.length,field_count:fields.length,historical_references:rows.filter(x=>x.round_id==='历史盘点').length,new_experiments:rows.filter(x=>x.round_id==='round-001').length,official_new_results:officialResults.length,official_terminal_result_observed:Boolean(terminal),new_official_source_identity_verified:sourceIdentityVerified,formal_performance_conclusion:'pending',all_evaluated_at_are_null:rows.every(x=>x.evaluated_at===null),files:['summary.md','experiments.jsonl','性能调优报告.md'].map(file=>({file,sha256:sha(fs.readFileSync(path.join(root,file)))}))};
fs.writeFileSync(path.join(__dirname,'validation.json'),JSON.stringify(verification,null,2)+'\n');
console.log(JSON.stringify(verification,null,2));
