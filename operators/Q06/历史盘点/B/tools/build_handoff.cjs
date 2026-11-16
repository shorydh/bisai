// Rebuild the handoff from saved official UI records and downloaded source packages.
// Does not submit, optimize, or alter any candidate source.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const cp = require('child_process');
const gitCommand=fs.existsSync('D:/nodegit/git/Git/cmd/git.exe')?'D:/nodegit/git/Git/cmd/git.exe':'git';
const root = path.resolve(__dirname, '..');
const project = path.resolve(root, '../..');
const officialDir = path.join(root, 'artifacts/official');
const sha = data => crypto.createHash('sha256').update(data).digest('hex');
const readJson = p => JSON.parse(fs.readFileSync(p, 'utf8').replace(/^\uFEFF/, ''));
const seven = ['op_host/pad_v3_grad_def.cpp', 'op_host/pad_v3_grad_infershape.cpp',
  'op_host/pad_v3_grad_tiling.cpp', 'op_kernel/pad_v3_grad.cpp', 'op_kernel/pad_v3_grad.h',
  'op_kernel/pad_v3_grad_tiling_data.h', 'op_kernel/pad_v3_grad_tiling_key.h'];
const localDirs = ['original', 'candidate', 'candidate_v2', 'candidate_v3', 'candidate_v3b',
  'candidate_v3c', 'friend_20261116/baseline',
  ...Array.from({ length: 10 }, (_, i) => `friend_20261116/candidate_r${i + 1}`)];
function sourceIdentity(dir) {
  const files = seven.map(file => ({file, sha256: sha(fs.readFileSync(path.join(dir, file)))}));
  return {sha256: sha(files.map(f => `${f.file}\0${f.sha256}\n`).join('')), files};
}
const savedInventoryPath=path.join(root,'artifacts/version-inventory.json');
const savedLocal=fs.existsSync(savedInventoryPath)?readJson(savedInventoryPath).local:[];
const local = localDirs.map(dir => {
  if(fs.existsSync(path.join(project,dir)))return {dir,...sourceIdentity(path.join(project,dir))};
  const saved=savedLocal.find(v=>v.dir===dir);
  if(!saved)throw Error('Local snapshot inventory missing: '+dir);
  return {dir,sha256:saved.sha256,files:saved.files};
});
const known = {
  1122011: ['初始提交缺少索引头文件', null, '主头包含 pad_v3_grad_index.h，平台源码包未包含该文件。'],
  1124074: ['首个官方通过版本', null, '初始可运行实现，具体设计日志未在本机恢复。'],
  1125548: ['H2 / 早期 original 基线', 1124074, '小张量快速归约、紧凑元数据；历史报告与朋友复盘的总分转述存在冲突。'],
  1137274: ['早期 v1：唯一来源直拷等', 1125548, 'identity 减少缓冲分配；唯一连续区域直接 DMA；扩大直拷 tile；避免重复快路尝试。'],
  1137595: ['早期 v2：行缓存与外置 TPipe', 1125548, '缓存外轴 Contributors 与初始 base，TPipe 移到入口作用域。'],
  1137852: ['早期 v3：8/16/32/64 紧凑槽', 1137595, '按贡献上界缩减 Gather 和归约槽位；原提交遇到机器不可用。'],
  1137948: ['早期 v3b：32/64 槽', 1137595, '将紧凑槽位限制为 32/64；原提交遇到机器不可用。'],
  1138807: ['H2 原样恢复', 1125548, '七源码与 original 一致。'],
  1138972: ['朋友 TPipe 单变量实验：机器失败', 1125548, 'TPipe 布置改动；与 1139103 的七源码一致。'],
  1139103: ['朋友 TPipe 单变量实验重试', 1125548, '重试同一源码；假设来自朋友复盘。'],
  1139232: ['H2 原样恢复', 1125548, '七源码与 original 一致。'],
  1139896: ['行缓存实验前 H2 同期基线', 1125548, '七源码与 original 一致。'],
  1140060: ['朋友行索引缓存首测', 1139896, '外轴来源与基址按行缓存；与 1140175、1147615 七源码一致。'],
  1140175: ['朋友行索引缓存复测', 1139896, '七源码与 1140060 一致。'],
  1147615: ['结构实验前行缓存同期基线', 1140175, '行缓存源码原样复测。'],
  1147721: ['朋友按行展开来源计划首测', 1147615, '按行展开来源计划；与 1147881、1148133 七源码一致。'],
  1147813: ['朋友自适应槽布局', 1147615, '来源计划与自适应槽布局实验；设计解释来自朋友复盘。'],
  1147881: ['朋友来源计划恢复复测', 1147615, '七源码与 1147721 一致。'],
  1148133: ['朋友最后一轮结构基线', 1147881, '来源计划源码原样复测。'],
  1148294: ['朋友单核合并', 1148133, '减少重复读取的单核方案；假设来自朋友复盘。'],
  1148481: ['朋友输入范围检查', 1148133, '归约前输入范围检查；假设来自朋友复盘。'],
  1148685: ['朋友树形归约误差界首测', 1148133, '调整归约误差界；与朋友最终版和本机 baseline 七源码一致。'],
  1148765: ['朋友最终版恢复复测', 1148133, '与 1148685、1362811 七源码一致；35.90 仅在朋友复盘转述中可见。'],
  1362811: ['本机朋友原版官方基线', null, '朋友原始七源码原样提交。'],
  1362890: ['r1：末轴计划跨行复用', 1362811, '宽度不超过 32 且本核跨行时缓存每列 Contributors。'],
  1363030: ['r2：证书充分条件快检', 1362811, '先检查 sumAbs 阈值充分条件，再决定是否执行完整证书。'],
  1363127: ['r3：32 位字节偏移递推', 1362811, '小张量来源地址改用 32 位字节偏移和等差递推。'],
  1363194: ['r4：FP32 至多两来源免证书', 1362811, '仅 FP32 至多两来源路径跳过误差证书。'],
  1363392: ['r5：输入 DMA 与索引规划重叠', 1362811, '提前输入搬运并保留成功和回退路径的排空等待。'],
  1363490: ['r7：单次 UB 分配与 11 个视图', 1362811, '合并分配，保留视图偏移、容量和同步。'],
  1363597: ['r8：padding 合并搬入 UB', 1362811, 'rank>=4 时批量读取本次 padding，保留原回退。'],
  1363916: ['r9：constant 紧凑 Gather', 1362811, 'constant 小张量零或单来源直接 Gather，条件内只分配三个缓冲。'],
  1364006: ['r1 原样恢复复测', 1362811, '七源码与 1362890 一致，记录全部复测结果。'],
};
const reportedScores={1124074:18.41,1137274:30.80,1137595:32.40,1139103:29.89,1140175:31.88,1147881:34.60,1147813:34.06,1148294:31.16,1148481:34.70,1148685:35.17,1148765:35.90};
fs.writeFileSync(path.join(root,'artifacts/auxiliary/historical-reported-scores.json'),JSON.stringify({classification:'secondary_reports_only; not official_metrics without independent official snapshot',sources:['本机早期性能调优报告.md','朋友提供的friend_review.md'],reported_scores:reportedScores,conflict:{official_task_id:1125548,local_report:30.76,friend_review:30.95}},null,2)+'\n');
const newDefinitions = {
  'early-v2-baseline-current': ['早期 v2 同期基线', null, '原样重测 v2，为未取得有效结果的早期紧凑槽实验提供同期官方基线。'],
  'early-v3-retry': ['早期 v3 机器失败后原样补测', 'early-v2-baseline-current', known[1137852][2]],
  'early-v3b-retry': ['早期 v3b 机器失败后原样补测', 'early-v2-baseline-current', known[1137948][2]],
  'early-v3c-first': ['早期 v3c 首次官方评测', 'early-v2-baseline-current', '固定使用 32 槽，移除动态槽数计算；原样评测，不新增改动。'],
  'friend-baseline-current': ['朋友原版同期基线复测', null, '为 r6 与 r10 提供同期官方基线。'],
  'r6-first': ['r6：前导恒等外轴合并', 'friend-baseline-current', 'front=0 且输入输出轴长相等的前导外轴合并，跳过重复外轴枚举。'],
  'r10-first': ['r10：唯一连续 tile 直接 DMA', 'friend-baseline-current', '末轴连续且外轴唯一时直接 Load→DMA；多来源时恢复原枚举。'],
  'final-restore': ['整理结束后原样恢复所选版本', 'friend-baseline-current', '按已有有效官方证据选择r6源码并原样恢复；没有组合或新增优化。'],
};
const newRunsPath = path.join(officialDir, 'new-runs.json');
const newRuns = fs.existsSync(newRunsPath) ? readJson(newRunsPath) : [];
for (const run of newRuns) {
  const definition = newDefinitions[run.name];
  if (definition) known[run.id] = [definition[0], typeof definition[1] === 'string' ?
    newRuns.find(r => r.name === definition[1])?.id ?? null : definition[1], definition[2]];
}
const ids = fs.readdirSync(officialDir).filter(f => /^\d+\.json$/.test(f)).map(f => +f.slice(0, -5)).sort((a,b)=>a-b);
let normalized = [];
for (const id of ids) {
  const raw = readJson(path.join(officialDir, `${id}.json`));
  const platformRoot = path.join(root, `artifacts/platform/${id}/code`);
  const identity = sourceIdentity(platformRoot);
  const sentRun=newRuns.find(run=>run.id===id);
  if(sentRun) {
    const frozen=sourceIdentity(path.join(root,'artifacts/local-versions',sentRun.name));
    if(frozen.sha256!==identity.sha256)throw Error(`Official/frozen source mismatch for ${id}`);
  }
  const matches = local.filter(l => l.sha256 === identity.sha256).map(l => l.dir);
  const packageHash = sha(fs.readFileSync(path.join(officialDir, `${id}.zip`)));
  const sourceFiles = [];
  function walk(dir) { for (const e of fs.readdirSync(dir, {withFileTypes:true})) {
    const p=path.join(dir,e.name); if(e.isDirectory()) walk(p); else sourceFiles.push({file:path.relative(platformRoot,p).replaceAll('\\','/'),sha256:sha(fs.readFileSync(p))});
  }}
  for (const sub of ['op_host','op_kernel']) walk(path.join(platformRoot,sub));
  for (const file of ['build.sh','CMakeLists.txt']) if(fs.existsSync(path.join(platformRoot,file))) sourceFiles.push({file,sha256:sha(fs.readFileSync(path.join(platformRoot,file)))});
  const identityRecord = {official_task_id:id, official_result_ref:raw.url,
    seven_source_sha256:identity.sha256, seven_source_files:identity.files,
    package_sha256:packageHash, build_and_source_files:sourceFiles, matching_local_directories:matches};
  fs.writeFileSync(path.join(officialDir, `${id}-identity.json`), JSON.stringify(identityRecord,null,2)+'\n');
  const text = raw.table_text.replace(/\r/g,'');
  const cases = [];
  const re = /(?:^|\n)([1-5])\t\s*([^\t]+?)\s*\t([^\t]+)\t([^\t]+)\t([^\n]+)/g;
  for (const m of text.matchAll(re)) cases.push({case:m[1],status:m[2].trim(),output_error_ratio:m[3].trim(),time:m[4].trim(),best_time_displayed:m[5].trim()});
  if(cases.length !== 5) throw Error(`Expected five public rows for ${id}`);
  const rankingPaths = [`${id}-ranking.txt`, `${id}-ranking-saved.txt`].filter(p=>fs.existsSync(path.join(officialDir,p)));
  const header = raw.submission_header || raw.header;
  const time = header.match(/提交时间：(\d{4}\/\d{2}\/\d{2} \d{2}:\d{2}:\d{2})/)[1];
  let score=null, rankRef=null;
  for(const file of rankingPaths) {
    const row=fs.readFileSync(path.join(officialDir,file),'utf8').split(/\r?\n/).find(l=>l.includes('shorydh')&&l.includes(time));
    if(!row)throw Error(`Ranking timestamp mismatch for ${id}`);
    const value=Number(row.split('\t')[4]);if(!Number.isFinite(value))throw Error(`Invalid score for ${id}`);
    if(score!==null&&score!==value)throw Error(`Conflicting score snapshots for ${id}`);
    score=value;rankRef=`artifacts/official/${file}`;
  }
  const def = known[id] || [`历史提交 ${id}（设计说明未恢复）`, null, '准确源码已从官方工程恢复；不臆造作者假设或基线。'];
  const diagPath=path.join(officialDir,`${id}-diagnostic.txt`), diagnostic=fs.existsSync(diagPath)?fs.readFileSync(diagPath,'utf8'):null;
  const infra=!!diagnostic?.includes('evaluation machine unavailable');
  const rawStatus=raw.status;
  normalized.push({id,raw,identity:identityRecord,title:def[0],baseId:def[1],change:def[2],cases,score,rankRef,time,infra,diagnostic,rawStatus});
}
const byId=new Map(normalized.map(r=>[r.id,r]));
const experiments=[];
for(const r of normalized) {
  const base=byId.get(r.baseId);
  const valid=r.rawStatus==='Pass';
  const baseValid=base?.rawStatus==='Pass';
  const sameEpoch=baseValid&&r.time.slice(0,10)===base.time.slice(0,10);
  const timeNumber=s=>/^[0-9.]+μs$/.test(s)?Number(s.slice(0,-2)):null;
  const comparison=base?{baseline_official_task_id:base.id,comparable:valid&&sameEpoch,
    total_score_delta_points:valid&&sameEpoch&&r.score!==null&&base.score!==null?+(r.score-base.score).toFixed(2):null,
    public_case_delta_us:valid&&sameEpoch?r.cases.map((c,i)=>timeNumber(c.time)!==null&&timeNumber(base.cases[i].time)!==null?+(timeNumber(c.time)-timeNumber(base.cases[i].time)).toFixed(2):null):null,
    explanation:!valid?'没有有效性能结果，不计算收益。':!sameEpoch?'不同日期或基线无有效结果，不作同期性能收益判断。':'同一官方题目同日结果；分数差不是加速比，也不构成稳定性统计。'}:
    {comparable:null,total_score_delta_points:null,explanation:'基线自身或缺少可证实的实验基线关系，不造比较。'};
  const notes=['evaluated_at 使用官方提交时间；平台未提供独立评测完成时间。',
    'agent_id=B 表示本轮整理与补测执行者，不表示全部历史实验都由本机B设计或执行。',
    '官方页面仅公开5个测试点，45个隐藏点未读取；不从公开点推算总分、隐藏耗时或整体加速比。',
    'best_time_displayed 是整理时页面展示值，可能随榜单更新，不能当作历史提交时的固定基线。'];
  if(r.score===null)notes.push('未取得可核对的官方总分原始快照，total_score=null；报告或复盘转述不填入正式指标。');
  if(r.raw.ranking_unavailable_reason)notes.push(r.raw.ranking_unavailable_reason);
  if(r.rawStatus==='Time Limit Exceeded')notes.push('公开5点Pass不代表总任务Pass；官方整体Time Limit Exceeded，无完整有效性能结论。');
  if(r.infra)notes.push('官方诊断：评测机器不可用。页面100%占比和Fail不能解释为算法精度失败。');
  if(r.id===1122011)notes.push('官方构建诊断：pad_v3_grad_index.h file not found。未新增修复版本。');
  if(r.id===1125548)notes.push('本机报告转述30.76，朋友复盘转述30.95；没有原始官方总分快照可消解，均不写入正式total_score。');
  if([1148685,1148765].includes(r.id))notes.push('朋友复盘转述35.17/35.90；本机保留源码同源证明，但旧总分缺少官方原始快照。');
  if(r.id===1364006)notes.push('r1同源码首测29.23，恢复复测28.84；不能只挑最高一次宣称稳定收益。');
  if(reportedScores[r.id]!==undefined)notes.push(`历史笔记/朋友复盘转述分数${reportedScores[r.id]}；仅在独立官方原始快照存在时才填入official_metrics。`);
  if(r.id===1137274)notes.push('总分30.80已从保存的官方排行榜截图人工核对，时间23:10:10及公开五点与本条提交吻合；ranking-saved.txt是本轮转录，原始PNG保留。截图中的旧本地题号属于历史UI，不改变本项目Q06归属。');
  if(!known[r.id])notes.push('原始假设和作者说明缺失；可恢复代码与官方结果完整，设计意图保持未知。');
  const artifacts=[`artifacts/official/${r.id}.json`,`artifacts/official/${r.id}.txt`,
    `artifacts/official/${r.id}.zip`,`artifacts/official/${r.id}-identity.json`];
  if(base) {
    fs.mkdirSync(path.join(root,'artifacts/diffs'),{recursive:true});
    let diff='';
    for(const sub of ['op_host','op_kernel']) {
      const args=['-c','core.autocrlf=false','diff','--no-index','--no-ext-diff','--',
        `artifacts/platform/${base.id}/code/${sub}`,`artifacts/platform/${r.id}/code/${sub}`];
      try { diff+=cp.execFileSync(gitCommand,args,{cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe']}); }
      catch(error) { if(error.status!==1)throw error; diff+=error.stdout; }
    }
    const diffFile=`artifacts/diffs/${r.id}-vs-${base.id}.diff`;
    fs.writeFileSync(path.join(root,diffFile),diff||'# Source trees are byte-identical.\n');
    artifacts.push(diffFile);
  }
  if(r.rankRef)artifacts.push(r.rankRef);
  if(r.id===1137274)artifacts.push('artifacts/official/1137274-ranking-historical.png','artifacts/official/1137274-ranking-transcription.json');
  if(r.raw.ranking_unavailable_reason)artifacts.push(`artifacts/official/${r.id}-ranking-unavailable.txt`,`artifacts/official/${r.id}-ranking-unavailable.jpg`);
  if(r.diagnostic)artifacts.push(`artifacts/official/${r.id}-diagnostic.txt`);
  experiments.push({experiment_id:`B-HIST-${r.id}`,operator:'PadV3Grad',round_id:'历史盘点',agent_id:'B',task_id:null,
    base_version:base?{seven_source_sha256:base.identity.seven_source_sha256,official_source_package:`artifacts/official/${base.id}.zip`,official_task_id:base.id}:null,
    candidate_version:{seven_source_sha256:r.identity.seven_source_sha256,official_source_package:`artifacts/official/${r.id}.zip`,package_sha256:r.identity.package_sha256,source_identity:`artifacts/official/${r.id}-identity.json`,matching_local_directories:r.identity.matching_local_directories},
    hypothesis:known[r.id]?r.title:null,change:r.change,official_task_id:r.id,official_result_ref:r.raw.url,
    evaluated_at:r.time.replaceAll('/','-').replace(' ','T')+'+08:00',
    evaluation_protocol:{environment:'CANNJudge官方提交环境',problem_url:'https://cannjudge.cn/public/ictcompetition/padv3grad',source_verification:'下载本条官方工程，计算包SHA256及源码/构建文件SHA256；与本机快照逐文件匹配',public_cases:5,hidden_cases:45,total_score_provenance:r.rankRef,cloud_metrics_used:false},
    official_status:r.rawStatus,official_metrics:{total_score:r.score,public_cases:r.cases,raw_public_table_text:r.raw.table_text},
    baseline_official_result_ref:base?.raw.url??null,comparison,finding_status:valid?'verified':'invalid',
    applicability:valid?'限该准确版本在本条官方评测下Pass与实际公开指标，不等于全输入数学证明或稳定加速。':r.infra?'基础设施失败；该次运行不支持正确性或性能结论。':'官方构建/运行失败；无有效性能收益结论。',artifacts,notes});
}
fs.writeFileSync(path.join(root,'experiments.jsonl'),experiments.map(e=>JSON.stringify(e)).join('\n')+'\n');
const inv={digest_algorithm:'SHA256(concatenate ordered relative file path + NUL + hex SHA256 + LF); full official ZIP independently hashed',
  official:normalized.map(r=>({id:r.id,status:r.rawStatus,version:r.identity.seven_source_sha256,matching_local_directories:r.identity.matching_local_directories})),
  local:local.map(l=>({...l,matches:normalized.filter(r=>r.identity.seven_source_sha256===l.sha256).map(r=>({id:r.id,status:r.rawStatus}))}))};
fs.writeFileSync(path.join(root,'artifacts/version-inventory.json'),JSON.stringify(inv,null,2)+'\n');
const pending=inv.local.filter(l=>!l.matches.some(m=>m.status==='Pass')&&!l.matches.some(m=>m.status!=='Fail'));
const scored=normalized.filter(r=>r.rawStatus==='Pass'&&r.score!==null);
const today=scored.filter(r=>r.time.startsWith('2026/11/16'));
const best=today.reduce((a,b)=>!a||b.score>a.score?b:a,null);
let lines=['# 第六题 PadV3Grad／历史盘点／B','',
  '执行者：本机 B。中央任务编号未提供，JSONL 的 task_id 为 null。本轮只恢复历史、补齐官方评测和整理证据，不新增优化方案。','',
  '本机项目没有 Git 仓库及可读取的本地提交历史（git rev-parse 返回 not a git repository）。准确版本以官方下载工程、ZIP SHA256 和逐源码 SHA256 恢复；共享交接提交到 shorydh/bisai 的 agent-b 分支。','',
  'B为本轮整理与补测执行者；历史实验的原作者、机器和环境不能从本轮agent_id推断。历史二手分数保存在artifacts/auxiliary/historical-reported-scores.json，未有官方快照的值不进入正式指标。','',
  '共同基线须区分两条来源：早期 original/H2（1125548），以及朋友最终版（1148765，与 1148685、1362811 七源码一致）。本轮早期紧凑槽补测使用同期 v2 原样重测，r6/r10 使用同期朋友原版重测。没有中央审核过的跨题共同基线，不擅自更新 central。','',
  '## 统一实验表','',
  '| 实验编号 | 假设与改动 | 准确代码版本（七源码SHA前12位；完整包见证据） | 官方任务 | 官方状态与实际指标 | 官方基线比较 | 结论 | 原始证据 |',
  '|---|---|---|---|---|---|---|---|'];
for(const r of normalized){const e=experiments.find(e=>e.official_task_id===r.id);const delta=e.comparison.total_score_delta_points;
  lines.push(`| B-HIST-${r.id} | ${r.title}；${r.change.replaceAll('|','／')} | \`${r.identity.seven_source_sha256.slice(0,12)}\` | [${r.id}](${r.raw.url}) | ${r.rawStatus}；总分${r.score===null?'null（无官方总分快照）':r.score}；公开µs：${r.cases.map(c=>c.time).join(', ')} | ${r.baseId??'null'}；${delta===null?'不填写总分收益':`${delta>=0?'+':''}${delta.toFixed(2)}分`} | ${r.infra?'invalid：机器不可用':r.rawStatus==='Pass'?'verified：该次官方Pass与指标；稳定收益另论':'invalid：无有效性能'} | [结果](artifacts/official/${r.id}.json)／[源码包](artifacts/official/${r.id}.zip)／[身份](artifacts/official/${r.id}-identity.json) |`);
}
lines.push('', '## 已验证、待验证及无效发现','',
  '- **verified**：官方历史索引保存了40条原始记录（2026-11-04 至 2026-11-16）。每条下载工程可恢复真实源码，后续补测单独追加，不覆盖旧结果。依据：artifacts/official/history-index.json 与各ID的ZIP、identity.json。',
  '- **verified**：v3/1137852、v3b/1137948、TPipe/1138972 的官方原始诊断均为 evaluation machine unavailable。它们的失败是无效运行，不能当作算法精度失败。依据：对应 diagnostic.txt。',
  '- **verified**：1122011 的官方构建失败是缺少 pad_v3_grad_index.h；已保留该失败源码包和日志，不编造数值或性能收益。',
  '- **已证伪/本次无效**：原样v3补测1367338的整体官方状态是Time Limit Exceeded，公开5点Pass不能支持“全部通过”或有效性能收益。只记录本条运行，不外推尚未测试的新修复。',
  '- **verified**：朋友最后两次源码与本机朋友基线逐文件相同；r1/1362890 与恢复/1364006 同源码，但总分29.23与28.84不同。适用条件：源码身份可证明，单次总分不能证明稳定收益。',
  '- **invalid**：将旧Fail直接判作精度失败、用CPU模型代替官方Pass、以公开5点推算隐藏45点、把分数差当整体加速比，均没有证据支持。',
  '- **pending**：索引复用、唯一来源连续DMA等已有方案的稳定收益及组合收益仍未证明；本轮没有实现或测试新组合。原已实现的版本均按官方记录逐项列出，不用pending跳过评测。',
  '- **异常/冲突**：1125548 的历史总分在两份二手记录中分别为30.76和30.95；1148765的35.90仅有朋友复盘转述。本轮官方详情可验证Pass及公开点，但没有旧总分原始快照，正式JSONL中对应total_score保持null。', '',
  '- **异常/缺失**：v3c/1367477官方详情Pass，但本轮查询排行榜时返回未找到匹配记录；已保存页面与时间，总分null。不能据公开5点推算该总分。', '',
  '## 当前最佳有效版本及下一步','',
  best?`在有原始官方总分快照的2026-11-16记录中，最高观察值为 **${best.score} 分，提交 ${best.id}**，七源码SHA256为 \`${best.identity.seven_source_sha256}\`。这不是稳定提速声明。`:'尚无可核对的官方总分快照。', '',
  `本轮当前新增官方任务：${newRuns.map(r=>`${r.name}=${r.id}（${byId.get(r.id)?.rawStatus??'尚未完成'}）`).join('；')||'尚未登记'}。`, '',
  `最终恢复：${newRuns.find(r=>r.name==='final-restore')?`${newRuns.find(r=>r.name==='final-restore').id}，${byId.get(newRuns.find(r=>r.name==='final-restore').id)?.rawStatus??'尚未完成'}，总分${byId.get(newRuns.find(r=>r.name==='final-restore').id)?.score??'null'}。采用r6原样源码；首次1367629为29.59，恢复1367774为29.39，均保留，不择优删除复测。`:'尚未执行恢复。'}`, '',
  `尚未取得有效官方运行的可恢复本地版本：${pending.map(p=>p.dir).join('、')||'无（所有17个本地源码快照均已存在有效官方运行或明确官方构建/正确性失败记录）'}。具体状态以实验表为准；Running不声称完成。`, '',
  '可继续探索：把已验证索引复用与唯一来源直拷作为中央后续分析输入；组合必须新建实验并重新官方评测，不能假定收益相加。本轮不新增方案。', '',
  '官方只公开5个点；本轮未读取或推断隐藏数据。没有云性能数据替代正式结果。配置、构建脚本和全工程以每条官方ZIP为准，源码身份以对应identity.json为准。', '',
  '## 文件使用','',
  '- experiments.jsonl：固定字段，一行一条官方提交，含失败和复测；缺失指标为null。',
  '- artifacts/official/：官方详情、可公开的状态诊断、总分快照、工程ZIP和逐文件身份。',
  '- artifacts/version-inventory.json：17个本地源码快照与官方提交的哈希映射。',
  '- artifacts/local-versions/：本轮送测前冻结的七源码快照和网页回读记录对应版本。',
  '- artifacts/auxiliary/：朋友原始包与CPU模型结果，仅辅助解释，不作为官方评测结论。',
  '- artifacts/platform/：本机解压缓存；共享仓库可从官方ZIP完整恢复，不重复上传。',
  '- tools/build_handoff.cjs：依据保存证据重绘本总结与JSONL，不执行优化或官方提交。', '');
fs.writeFileSync(path.join(root,'summary.md'),lines.join('\n'));
console.log(JSON.stringify({official_records:normalized.length,distinct_seven_source_versions:new Set(normalized.map(r=>r.identity.seven_source_sha256)).size,best_observed:best?{id:best.id,score:best.score}:null,local_missing_effective_result:pending.map(p=>p.dir)},null,2));
