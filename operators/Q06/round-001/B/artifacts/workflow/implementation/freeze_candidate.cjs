const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '../../..');
const p = path.join(root, 'P');
const pl = path.join(root, 'PL');
const sha = x => crypto.createHash('sha256').update(x).digest('hex');
const files = dir => fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?files(path.join(dir,e.name)): [path.join(dir,e.name)]);
if(!fs.existsSync(pl)) {
 fs.mkdirSync(pl,{recursive:true});
 for(const source of files(p)) { const dest=path.join(pl,path.relative(p,source)); fs.mkdirSync(path.dirname(dest),{recursive:true}); fs.copyFileSync(source,dest,fs.constants.COPYFILE_EXCL); }
}
const header = 'op_kernel/pad_v3_grad.h';
const baseline = fs.readFileSync(path.join(p,header),'utf8');
const anchor = '        int64_t outerBases[groupSize];\n';
const inserted = `        // Last-axis contributors depend only on the column and this call's
        // padding. Cache narrow rows only when this core processes >1 row's
        // worth of outputs; wider/shorter ranges keep the original mapping.
        constexpr int64_t lastPlanCapacity = 32;
        const bool reuseLast = outputWidth_ <= lastPlanCapacity && count > outputWidth_;
        Contributors lastPlans[lastPlanCapacity];
        if (reuseLast) {
            for (int64_t column = 0; column < outputWidth_; ++column) {
                lastPlans[column] = MakeContributors(column, inputWidth_, outputWidth_,
                    front_[rank_ - 1], data_->mode);
            }
        }
`;
const oldPlan = `                const auto last = MakeContributors(column + c, inputWidth_, outputWidth_,
                                                   front_[rank_ - 1], data_->mode);`;
const newPlan = `                const auto last = reuseLast ? lastPlans[column + c] :
                    MakeContributors(column + c, inputWidth_, outputWidth_,
                                     front_[rank_ - 1], data_->mode);`;
if(baseline.split(anchor).length!==2 || baseline.split(oldPlan).length!==2) throw Error('Unambiguous two hunks required');
const candidate = baseline.replace(anchor,anchor+inserted).replace(oldPlan,newPlan);
if(candidate.replace(inserted,'').replace(newPlan,oldPlan)!==baseline) throw Error('Reverse transplant failed');
const existing=fs.readFileSync(path.join(pl,header),'utf8');
if(existing!==baseline && existing!==candidate) throw Error('Existing PL changed; refusing overwrite');
if(existing!==candidate) fs.writeFileSync(path.join(pl,header),candidate);
const seven=['op_host/pad_v3_grad_def.cpp','op_host/pad_v3_grad_infershape.cpp','op_host/pad_v3_grad_tiling.cpp','op_kernel/pad_v3_grad.cpp','op_kernel/pad_v3_grad.h','op_kernel/pad_v3_grad_tiling_data.h','op_kernel/pad_v3_grad_tiling_key.h'];
const sourceFiles=files(pl).map(f=>path.relative(pl,f).replaceAll('\\','/')).sort();
const identities=sourceFiles.map(file=>({file,sha256:sha(fs.readFileSync(path.join(pl,file)))}));
const changed=identities.filter(x=>x.sha256!==sha(fs.readFileSync(path.join(p,x.file)))).map(x=>x.file);
if(sourceFiles.length!==38 || changed.length!==1 || changed[0]!==header) throw Error('Scope mismatch');
const digest=list=>sha(list.map(file=>file+'\0'+sha(fs.readFileSync(path.join(pl,file)))+'\n').join(''));
const identity={task_id:'Q06-R001-B-COMBINE-20261117',experiment_id:'Q06-R001-B-E001',scheme:'PL',snapshot:'PL-source.zip',snapshot_root:'code/',parent_official_task_id:1367774,parent_seven_source_sha256:'d0b680d59d1dfa088dd24fff5d3128feb2758251bcd8d3b34b39635bad68f949',seven_source_sha256:digest(seven),all_38_file_sha256:digest(sourceFiles),main_header_sha256:sha(candidate),files:identities,changed_files:changed,exact_r1_two_hunk_transplant:true,reverse_to_P_sha256:sha(candidate.replace(inserted,'').replace(newPlan,oldPlan)),device_execution:false,official_task_id:null,official_build:null,official_precision:null,official_performance:null};
fs.writeFileSync(path.join(__dirname,'candidate-identity.json'),JSON.stringify(identity,null,2)+'\n');
fs.writeFileSync(path.join(__dirname,'transplant-hunks.json'),JSON.stringify({anchor,inserted,oldPlan,newPlan},null,2)+'\n');
console.log(JSON.stringify({seven_source_sha256:identity.seven_source_sha256,main_header_sha256:identity.main_header_sha256,all_38_file_sha256:identity.all_38_file_sha256,files:sourceFiles.length,changed},null,2));
