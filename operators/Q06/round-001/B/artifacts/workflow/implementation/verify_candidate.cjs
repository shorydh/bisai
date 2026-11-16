const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../../..'),p=path.join(root,'P'),pl=path.join(root,'PL');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const load=file=>JSON.parse(fs.readFileSync(path.join(__dirname,file),'utf8'));
const identity=load('candidate-identity.json'),hunks=load('transplant-hunks.json');
const contract=JSON.parse(fs.readFileSync(path.join(__dirname,'../analysis/round1/implementation-contract-PL.json'),'utf8'));
const scopePath=path.join(__dirname,'../analysis/round1/source-isolation-PL.json');
const scope=JSON.parse(fs.readFileSync(scopePath,'utf8'));
const freeze=JSON.parse(fs.readFileSync(path.join(__dirname,'../analysis/round1/parent-freeze.json'),'utf8'));
const header='op_kernel/pad_v3_grad.h';
const files=dir=>fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?files(path.join(dir,e.name)):[path.join(dir,e.name)]);
const actualFiles=files(pl).map(f=>path.relative(pl,f).replaceAll('\\','/')).sort();
const baseFiles=files(p).map(f=>path.relative(p,f).replaceAll('\\','/')).sort();
const changed=[];
for(const file of actualFiles){const a=fs.readFileSync(path.join(pl,file)),b=fs.readFileSync(path.join(p,file));if(sha(b)!==scope.baseline_files[file])throw Error('P scope changed '+file);if(sha(a)!==identity.files.find(x=>x.file===file)?.sha256)throw Error('PL freeze changed '+file);if(!a.equals(b))changed.push(file);}
const parent=fs.readFileSync(path.join(p,header),'utf8'),candidate=fs.readFileSync(path.join(pl,header),'utf8');
const stripped=candidate.replace(hunks.inserted,'').replace(hunks.newPlan,hunks.oldPlan);
const checks={file_count:actualFiles.length===38,file_inventory:JSON.stringify(actualFiles)===JSON.stringify(baseFiles),only_main_header_changed:changed.length===1&&changed[0]===header,reverse_exact_parent:stripped===parent,scope_sha256:sha(fs.readFileSync(scopePath))===freeze.scope_sha256,contract_sha256:sha(fs.readFileSync(path.join(__dirname,'../analysis/round1/implementation-contract-PL.json')))===freeze.contract_sha256,candidate_identity:sha(candidate)===identity.main_header_sha256,cache_single_insert:candidate.split(hunks.inserted).length===2,selector_single_replace:candidate.split(hunks.newPlan).length===2};
if(!Object.values(checks).every(Boolean))throw Error(JSON.stringify(checks));
const snapshotSha=sha(fs.readFileSync(path.join(__dirname,'PL-source.zip')));
const required=contract.required_features.map(f=>({id:f.id,status:f.id==='boundary-verification'?'supplementary_cpu_pass_device_pending':'source_pass',evidence:f.id==='boundary-verification'?'planner-result.json':['candidate-identity.json','PL-vs-P.diff','verify_candidate.cjs']}));
fs.writeFileSync(path.join(__dirname,'scheme-conformance.json'),JSON.stringify({task_id:identity.task_id,experiment_id:identity.experiment_id,scheme:'PL',implementation_mode:'exact',substitution_policy:'forbidden',parent_seven_source_sha256:identity.parent_seven_source_sha256,candidate_seven_source_sha256:identity.seven_source_sha256,main_header_sha256:identity.main_header_sha256,scope_sha256:freeze.scope_sha256,contract_sha256:freeze.contract_sha256,checks,required_features:required,kb_unavailable:true,kb_unavailable_reason:'No installed knowledge-query or configured knowledge root in parent discovery',kb_cards:[],source_automatic_storage_bytes:1280,actual_device_stack_bytes:null,official_task_id:null,eligible_for_performance:false,missing:['Official target build','Official precision','Actual SoC/build/loaded binary identity','Comparable official performance','Canonical Python workflow gate'],device_execution:false},null,2)+'\n');
fs.writeFileSync(path.join(__dirname,'scheme-conformance-gate.json'),JSON.stringify({task_id:identity.task_id,decision:'source_scope_pass_dynamic_pending',checker:'verify_candidate.cjs; direct byte/hunk checks, not canonical Python validate_implementation_conformance.py',source_isolation:{decision:'pass',changed_files:changed,all_38_baseline_identity_matches:true,other_37_exact:true,reverse_hunks_recovers_P:true,scope_sha256:freeze.scope_sha256},candidate_safety:{decision:'static_pass_dynamic_pending',public_contract:'unchanged bytes',host_tiling:'unchanged bytes',UB_sync_reduction_certificate_fallback:'unchanged bytes except last-axis plan selection',new_cache_lifetime:'local function invocation',actual_stack_spill:'unknown',device_validation:'pending'},canonical_workflow_gate:'pending',eligible_for_performance:false,checks},null,2)+'\n');
fs.writeFileSync(path.join(__dirname,'snapshot-manifest.json'),JSON.stringify({snapshot:'PL-source.zip',sha256:snapshotSha,files:38,seven_source_sha256:identity.seven_source_sha256,main_header_sha256:identity.main_header_sha256,all_38_file_sha256:identity.all_38_file_sha256,source_root:'../../../PL',snapshot_root:'code/',immutable_after_freeze:true},null,2)+'\n');
const officialPath=path.join(__dirname,'../../official/1369663.json');
if(fs.existsSync(officialPath)){
 const official=JSON.parse(fs.readFileSync(officialPath,'utf8').replace(/^\uFEFF/,''));
 const conf=load('scheme-conformance.json'),gate=load('scheme-conformance-gate.json');
 Object.assign(conf,{official_task_id:official.id,official_status:official.status,official_result_evidence:'../../official/1369663.json',official_full_38_identity_match:official.source_identity_verified,missing:['Actual SoC/build/loaded binary details and stack/spill','Comparable official timing/scoring/degeneration protocol','Canonical Python workflow gate and independent device sequence stress']});
 gate.official_evaluation={task_id:official.id,status:official.status,source_full_38_match:official.source_identity_verified,evidence:'../../official/1369663.json',evaluated_at:official.evaluated_at};
 fs.writeFileSync(path.join(__dirname,'scheme-conformance.json'),JSON.stringify(conf,null,2)+'\n');
 fs.writeFileSync(path.join(__dirname,'scheme-conformance-gate.json'),JSON.stringify(gate,null,2)+'\n');
}
console.log(JSON.stringify({status:'PASS',checks,snapshot_sha256:snapshotSha,candidate_seven_source_sha256:identity.seven_source_sha256,device_execution:false},null,2));
