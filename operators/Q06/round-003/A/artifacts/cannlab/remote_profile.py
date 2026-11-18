"""Single-launch msprof diagnostics on the frozen first sample, not a benchmark."""
from datetime import datetime,timezone
import csv,hashlib,json,os,shutil,signal,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'profiler_results'
OUT.mkdir(exist_ok=False)
def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def hashes(path):return {p.relative_to(path).as_posix():sha(p) for p in sorted(path.rglob('*')) if p.is_file()}
def call(command,cwd,env,log,timeout=150):
    start=now()
    with log.open('wb') as f:
        p=subprocess.Popen(command,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        timed_out=False
        try:rc=p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(p.pid,signal.SIGTERM)
            try:rc=p.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);rc=p.wait()
    return dict(command=command,started_at=start,ended_at=now(),exit_code=rc,timed_out=timed_out,log=log.relative_to(OUT).as_posix())
def load():
    p=subprocess.run(['npu-smi','info'],capture_output=True,text=True,timeout=15)
    return dict(observed_at=now(),exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)
results=[]
for arm in ['PL','PL-lazy']:
    stage=json.loads((ROOT/'cloud_results'/(arm+'.json')).read_text())
    result=dict(arm=arm,source_identity=stage['source_identity'],scope='Single first public FP32 reflect sample diagnostic; no warmup; one app/ACLNN call; no stable-speedup claim',warmup_calls=0,application_calls=1,logical_device=0,official_evaluation=False)
    target=OUT/arm;target.mkdir()
    if not all(r.get('exit_code')==0 for r in stage['stages']):
        result.update(executed=False,reason='Prior frozen build/example did not succeed');results.append(result);continue
    vendor=ROOT/arm/'build/packages/vendors/pad_v3_grad_custom'
    env=dict(os.environ,DEVICE_ID='0',PYTHONDONTWRITEBYTECODE='1',ASCEND_CUSTOM_OPP_PATH=str(vendor),LD_LIBRARY_PATH=str(vendor/'op_api/lib')+':'+os.environ['ASCEND_HOME_PATH']+'/lib64:'+os.environ.get('LD_LIBRARY_PATH',''))
    result['environment']={k:env[k] for k in ['DEVICE_ID','ASCEND_CUSTOM_OPP_PATH','LD_LIBRARY_PATH']}
    data=target/'sample';data.mkdir()
    for sub in ['input','golden']:shutil.copytree(ROOT/arm/'samples/build'/sub,data/sub)
    (data/'output').mkdir()
    result['input_hashes']=hashes(data/'input');result['golden_hashes']=hashes(data/'golden')
    exe=ROOT/arm/'examples/build/sample';result['application_sha256']=sha(exe)
    manifest=json.loads((ROOT/'manifests'/(arm+'.json')).read_text())
    result['source_before_matches']=all(sha(ROOT/arm/f['path'])==f['sha256'] for f in manifest['files'])
    assert result['source_before_matches']
    result['load_before']=load()
    command=['msprof','--output='+str(target/'raw'),'--ai-core=on','--aic-mode=task-based','--aic-metrics=PipeUtilization','--task-time=on','--runtime-api=on','--ascendcl=on',str(exe),str(data),'0']
    print('PROFILE_START '+arm,flush=True)
    result['execution']=call(command,ROOT/arm,env,target/'collection.log')
    result['executed']=True;result['load_after']=load()
    if result['execution']['exit_code']==0:
        result['verification']=call(['python3',str(ROOT/arm/'samples/sample.py'),'verify','--directory',str(data)],ROOT/arm,env,target/'verify.log',timeout=45)
    result['output_hashes']=hashes(data/'output')
    result['source_after_matches']=all(sha(ROOT/arm/f['path'])==f['sha256'] for f in manifest['files'])
    summaries=[]
    for p in sorted(target.rglob('op_summary*.csv')):
        with p.open(newline='',encoding='utf-8-sig') as f:
            reader=csv.DictReader(f);rows=list(reader)
        summaries.append(dict(path=p.relative_to(OUT).as_posix(),sha256=sha(p),fields=reader.fieldnames,rows=rows))
    result['op_summaries']=summaries
    result['metric_policy']='CSV values are raw profiler diagnostics from this single instrumented call. No score conversion, inferred hidden cases, or stable comparison.'
    save(target/'result.json',result);results.append(result)
    print('PROFILE_END '+arm+' exit='+str(result['execution']['exit_code'])+' summaries='+str(len(summaries)),flush=True)
save(OUT/'summary.json',dict(observed_at=now(),results=results,scope='Only single first-public-sample diagnostic; official benchmark remains separate'))
