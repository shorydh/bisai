"""R003 official evidence collector. Inspection is GET-only; preserves every response."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WORK=Path(__file__).resolve().parent
ROOT=WORK.parents[3]
RAW=WORK/'raw_official'
PID='6ad9ab403ff2fef7e80e2a1d'
sys.path.insert(0,str(ROOT/'.claude/skills/cannjudge-submit'))
from cannjudge_cli import CANNJudgeClient
VERSIONS={'P':'d0b680d59d1dfa088dd24fff5d3128feb2758251bcd8d3b34b39635bad68f949','PL':'988e491ec2d8d758adac5caa0e304cc81cb500ade732aadc9427fa1254267d41','PL-lazy':'03e6bc1bb81dc40ba71d4691aeb08feebdf38fe0a2ac12f2a59aeff0445afb39'}
HISTORY={'PL-lazy':'6afc1e5b6bd0f9be374a4c6d','PL':'6afc3bd16bd0f9be3780fbd0','P':'6afc3b166bd0f9be377f93c5'}

def now():return datetime.now(timezone.utc).isoformat()
def sha(data):return hashlib.sha256(data).hexdigest()
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def tree(files):return sha(''.join(k+'\0'+sha(files[k].encode('utf-8'))+'\n' for k in sorted(files)).encode('utf-8'))
def client():
    c=CANNJudgeClient()
    if not c.load_session():raise RuntimeError('No existing authorized session')
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    c.session.mount('https://',HTTPAdapter(max_retries=Retry(total=2,backoff_factor=0.5,allowed_methods=['GET'])))
    return c
def get(c,path,dest,params=None):
    started=now()
    response=c.session.get(c.BASE_URL+path,params=params,timeout=40)
    observed=now()
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_bytes(response.content)
    meta={'method':'GET','endpoint':c.BASE_URL+path,'request_started_at':started,'observed_at':observed,'http_status':response.status_code,'raw_response_sha256':sha(response.content)}
    save(dest.with_suffix('.meta.json'),meta)
    c._check_response(response)
    return response.json(),meta
def inspect():
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    d=RAW/'inspection'/stamp; d.mkdir(parents=True)
    c=client()
    p,_=get(c,f'/api/problems/{PID}',d/'problem.json')
    t,_=get(c,f'/api/problems/{PID}/template',d/'template.json',{'userId':c.user_id})
    entries=t.get('data',t)['files']; editable=[f['path'] for f in entries if f.get('editable')]
    assert len(entries)==38 and len(editable)==7
    reports=[]
    for label,sid in HISTORY.items():
        try:
            official,meta=get(c,f'/api/submissions/{sid}',d/f'{label}_official.json')
            fs={f['path']:f['content'] for f in official.get('files',[])}
            identity=tree({k:fs[k] for k in editable}) if all(k in fs for k in editable) else None
            record={k:official.get(k) for k in ('_id','ID','status','valid','judge_revision','create_time','total_testcase_count','judge_missing_cases','public_only')}
            record.update(label=label,observed_at=meta['observed_at'],source_tree_sha256=identity,expected_tree_match=identity==VERSIONS[label],files_count=len(fs),readonly_matches_current_template=all(fs.get(f['path'])==f['content'] for f in entries if not f.get('editable')))
            folder=WORK/label
            record['all_38_match_restored']=all((folder/k).is_file() and (folder/k).read_bytes()==v.encode('utf-8') for k,v in fs.items()) if folder.exists() and len(fs)==38 else None
        except Exception as exc:
            record={'label':label,'official_task_id':sid,'error_type':type(exc).__name__,'observed_at':now()}
        reports.append(record)
        print(json.dumps(record,ensure_ascii=False),flush=True)
    wanted=set(HISTORY.values()); scans=[]; matches={}
    for page in range(1,51):
        data,meta=get(c,f'/api/problems/{PID}/ranking',d/'ranking_raw'/f'page_{page}.json',{'page':page,'size':100})
        scans.append({'page':page,'rows':len(data.get('rows',[])),'total':data.get('total'),**meta})
        for row in data.get('rows',[]):
            if row.get('submission_id') in wanted:
                matches[row['submission_id']]={'row':row,'response_ref':f'ranking_raw/page_{page}.json','response_meta':meta,'non_row_keys':[k for k in data if k!='rows']}
        if wanted<=matches.keys() or page*100>=data.get('total',0):break
    report={'observed_at':now(),'configuration':{k:p.get(k) for k in ('cann_version','judge_revision','score_mode','iterations','ranking_submission_mode','code_template')},'tasks':reports,'exact_ranking_matches':matches,'scans':scans,'scope':'Current observations only; not backfilled historical score or a new evaluation'}
    save(d/'inspection.json',report)
    save(RAW/'latest_inspection.json',{'path':d.relative_to(WORK).as_posix(),'observed_at':now()})
    print(json.dumps({'inspection':str(d),'config':report['configuration'],'ranking':[{'submission_id':sid,'score':r['row'].get('score'),'status':r['row'].get('status'),'response_keys':r['non_row_keys']} for sid,r in matches.items()],'missing':sorted(wanted-matches.keys())},ensure_ascii=False),flush=True)

def submit(label,version):
    plan=read(WORK/'plan.json')
    assert any(x['experiment_id']==label and x['version']==version for x in plan['runs'])
    position=next(i for i,x in enumerate(plan['runs']) if x['experiment_id']==label)
    for predecessor in plan['runs'][:position]:
        prior=RAW/'runs'/predecessor['experiment_id']
        assert (prior/'official_terminal.json').is_file(), 'Previous planned task has no terminal observation'
        assert any((prior/'ranking_exact').glob('*.json')), 'Capture previous exact ranking before superseding latest task'
    d=RAW/'runs'/label
    if d.exists():raise RuntimeError('Attempt already exists; reconcile receipt/history instead of repeating POST')
    c=client()
    # Disable transport retries entirely for the mutating request.
    from requests.adapters import HTTPAdapter
    c.session.mount('https://',HTTPAdapter(max_retries=0))
    d.mkdir(parents=True)
    p,_=get(c,f'/api/problems/{PID}',d/'problem_before.json')
    t,_=get(c,f'/api/problems/{PID}/template',d/'template_before.json',{'userId':c.user_id})
    entries=t.get('data',t)['files']; editable=[f['path'] for f in entries if f.get('editable')]
    assert len(entries)==38 and len(editable)==7
    source=WORK/version
    all_files={f['path']:(source/f['path']).read_bytes() for f in entries}
    files={k:all_files[k].decode('utf-8') for k in editable}
    assert tree(files)==VERSIONS[version]
    assert all(all_files[f['path']]==f['content'].encode('utf-8') for f in entries if not f.get('editable'))
    save(d/'request_files.json',[{'path':k,'content':v} for k,v in files.items()])
    save(d/'frozen_manifest.json',{'prepared_at':now(),'version':version,'source_tree_sha256':tree(files),'files':[{'path':k,'sha256':sha(v),'editable':k in editable} for k,v in sorted(all_files.items())]})
    started=now();save(d/'attempt.json',{'experiment_id':label,'version':version,'request_started_at':started,'request_files_sha256':sha((d/'request_files.json').read_bytes()),'post_retry_enabled':False})
    def capture(response,*unused,**kwargs):
        if response.request.method=='POST':
            (d/'submit_response.json').write_bytes(response.content)
            save(d/'submit_response.meta.json',{'observed_at':now(),'http_status':response.status_code,'raw_response_sha256':sha(response.content)})
    c.session.hooks['response'].append(capture)
    try:
        sid=c.submit_payload({'problemId':PID,'userId':c.user_id,'files':[{'path':k,'content':v} for k,v in files.items()]})
    except Exception as exc:
        save(d/'submit_error.json',{'observed_at':now(),'error_type':type(exc).__name__,'requires_reconciliation':True})
        raise
    save(d/'receipt.json',{'submission_id':sid,'request_started_at':started,'response_observed_at':now(),'version':version,'source_tree_sha256':tree(files)})
    print(json.dumps({'experiment_id':label,'version':version,'submission_id':sid,'event':'submitted'},ensure_ascii=False),flush=True)

def poll(label):
    d=RAW/'runs'/label;r=read(d/'receipt.json');sid=r['submission_id'];c=client()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    official,meta=get(c,f'/api/submissions/{sid}',d/'observations'/f'{stamp}.json')
    assert official.get('_id')==sid and official.get('problem_id')==PID, 'Returned task identity mismatch'
    fs={f['path']:f['content'] for f in official.get('files',[])}
    manifest=read(d/'frozen_manifest.json');editable=[f['path'] for f in manifest['files'] if f['editable']]
    report={k:official.get(k) for k in ('_id','ID','status','valid','judge_revision','create_time','total_testcase_count','judge_missing_cases')}
    report.update(observed_at=meta['observed_at'],official_ref=f'observations/{stamp}.json',all_38_match=len(fs)==38 and all(sha(fs.get(f['path'],'').encode('utf-8'))==f['sha256'] for f in manifest['files']),source_tree_sha256=tree({k:fs[k] for k in editable}) if all(k in fs for k in editable) else None)
    save(d/'latest_check.json',report)
    print(json.dumps(report,ensure_ascii=False),flush=True)
    if official.get('status') in ('Pass','Accepted','Fail','Wrong Answer','Compile Error','Runtime Error','Time Limit Exceeded','Memory Limit Exceeded','System Error'):
        save(d/'official_terminal.json',official)
        get(c,f'/api/problems/{PID}',d/'problem_after.json')

def rank(label):
    d=RAW/'runs'/label;r=read(d/'receipt.json');sid=r['submission_id'];c=client()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');scans=[];match=None
    for page in range(1,51):
        dest=d/'ranking_raw'/f'{stamp}_page_{page}.json'
        data,meta=get(c,f'/api/problems/{PID}/ranking',dest,{'page':page,'size':100})
        scans.append({'page':page,'total':data.get('total'),'rows_returned':len(data.get('rows',[])),**meta})
        matches=[row for row in data.get('rows',[]) if row.get('submission_id')==sid]
        if matches:
            assert len(matches)==1;match=matches[0]
            save(d/'ranking_exact'/f'{stamp}.json',{'official_task_id':sid,'row':match,'testcases':data.get('testcases'),'total_testcase_count':data.get('total_testcase_count'),'observed_at':meta['observed_at'],'source_response':dest.relative_to(WORK).as_posix(),'source_response_sha256':meta['raw_response_sha256'],'endpoint':meta['endpoint'],'params':{'page':page,'size':100}})
            break
        if page*100>=data.get('total',0):break
    save(d/'ranking_scans'/f'{stamp}.json',{'official_task_id':sid,'found':match is not None,'scans':scans})
    print(json.dumps({'label':label,'submission_id':sid,'found':match is not None,'score':match.get('score') if match else None},ensure_ascii=False),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['inspect','submit','poll','rank']);ap.add_argument('--label');ap.add_argument('--version',choices=['PL','PL-lazy']);args=ap.parse_args()
    if args.action=='inspect':inspect()
    elif args.action=='submit':submit(args.label,args.version)
    elif args.action=='poll':poll(args.label)
    else:rank(args.label)
