"""Frozen PL/PL-lazy build and first-sample execution. No source edits or official calls."""
from datetime import datetime, timezone
import ctypes
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'cloud_results'
OUT.mkdir(exist_ok=False)
def now(): return datetime.now(timezone.utc).isoformat()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name, data): (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def capture(command, timeout=20):
    try:
        p=subprocess.run(command,capture_output=True,text=True,timeout=timeout)
        return dict(command=command,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)
    except Exception as exc: return dict(command=command,error=str(exc))
def snapshot_load(): return capture(['npu-smi','info'])
def identity(arm):
    manifest=json.loads((ROOT/'manifests'/(arm+'.json')).read_text())
    observations=[dict(path=f['path'],expected_sha256=f['sha256'],sha256=sha(ROOT/arm/f['path'])) for f in manifest['files']]
    return dict(editable_text_tree_sha256=manifest['editable_text_tree_sha256'],file_count=len(observations),files=observations,all_match=all(r['expected_sha256']==r['sha256'] for r in observations))
environment={'observed_at':now(),'load':snapshot_load(),'commands':[], 'modules':{},'runtime':{},'files':{},'env':{k:os.environ.get(k) for k in ['ASCEND_HOME_PATH','ASCEND_OPP_PATH','DEVICE_ID','ASCEND_RT_VISIBLE_DEVICES']}}
for cmd in [ ['npu-smi','info','-m'], ['npu-smi','info','-t','board','-i','3','-c','0'], ['npu-smi','info','-t','device-share','-i','3','-c','0'], ['npu-smi','info','-t','usages','-i','3','-c','0'], ['cmake','--version'], ['g++','--version'], ['ccec','--version'], ['python3','--version'] ]:
    environment['commands'].append(capture(cmd))
for name in ['numpy','torch','ml_dtypes']:
    try:
        module=importlib.import_module(name)
        environment['modules'][name]={'version':getattr(module,'__version__',None),'file':getattr(module,'__file__',None)}
    except Exception as exc: environment['modules'][name]={'error':str(exc)}
ascend=Path(os.environ['ASCEND_HOME_PATH'])
for p in [ascend/'aarch64-linux/ascend_toolkit_install.info',Path('/usr/local/Ascend/driver/version.info')]:
    environment['files'][str(p)]=p.read_text() if p.exists() else None
try:
    lib=ctypes.CDLL(str(ascend/'lib64/libascendcl.so'))
    lib.aclInit.argtypes=[ctypes.c_char_p];lib.aclInit.restype=ctypes.c_int
    lib.aclrtGetDeviceCount.argtypes=[ctypes.POINTER(ctypes.c_uint32)];lib.aclrtGetDeviceCount.restype=ctypes.c_int
    rc=lib.aclInit(None);count=ctypes.c_uint32()
    count_rc=lib.aclrtGetDeviceCount(ctypes.byref(count))
    environment['runtime'].update(aclInit_rc=rc,device_count_rc=count_rc,device_count=count.value,logical_device_selected=0 if count_rc==0 and count.value>0 else None)
    if rc==0: environment['runtime']['aclFinalize_rc']=lib.aclFinalize()
except Exception as exc:environment['runtime']['error']=str(exc)
environment['ut_dependencies']={str(p):p.exists() for p in [Path('/usr/include/nlohmann/json.hpp'),Path('/usr/src/googletest/CMakeLists.txt'),Path('/usr/src/gtest/CMakeLists.txt')]}
environment['profiler']={n:shutil.which(n) for n in ['msprof','msopprof']}
for tool,path in environment['profiler'].items():
    if path:environment['commands'].append(capture([path,'--help']))
environment['runtime_headers']={}
for p in [ascend/'include/acl/acl_rt.h',ascend/'include/acl/acl_base.h']:
    if p.exists():
        lines=p.read_text(errors='replace').splitlines()
        chosen=set()
        for i,line in enumerate(lines):
            if any(t in line for t in ['ACL_DEV_ATTR_AICORE_CORE_NUM','ACL_DEV_ATTR_AIVECTOR_CORE_NUM','aclrtGetDeviceInfo']): chosen.update(range(max(0,i-3),min(len(lines),i+8)))
        environment['runtime_headers'][str(p)]='\n'.join(f'{i+1}: {lines[i]}' for i in sorted(chosen))
save('environment.json',environment)
summaries=[]
for arm in ['PL','PL-lazy']:
    before=identity(arm);save(arm+'_source_before.json',before)
    assert before['file_count']==38 and before['all_match']
    result={'arm':arm,'started_at':now(),'source_identity':before['editable_text_tree_sha256'],'stages':[]}
    for stage,command in [('build',['bash','build.sh','-j4']),('example',['bash','build.sh','-j4','-e'])]:
        if stage=='example' and (result['stages'][0]['exit_code']!=0 or environment['runtime'].get('logical_device_selected') is None):
            result['stages'].append({'stage':stage,'executed':False,'reason':'Build failed or logical ACL device unavailable','exit_code':None});continue
        before_load=snapshot_load();start=now();tic=time.monotonic()
        env=dict(os.environ,DEVICE_ID='0',PYTHONDONTWRITEBYTECODE='1')
        # Each source tree resolves its own vendor path; never reuse another arm's custom package.
        env.pop('ASCEND_CUSTOM_OPP_PATH',None)
        log=OUT/(arm+'_'+stage+'.log')
        print(f'START {arm} {stage}',flush=True)
        with log.open('wb') as f:
            p=subprocess.run(command,cwd=ROOT/arm,env=env,stdout=f,stderr=subprocess.STDOUT)
        row=dict(stage=stage,executed=True,command=command,device_id=0 if stage=='example' else None,started_at=start,ended_at=now(),exit_code=p.returncode,elapsed_seconds=time.monotonic()-tic,duration_scope='Whole command wall time, NOT operator execution time',log=log.name,load_before=before_load,load_after=snapshot_load())
        result['stages'].append(row);save(arm+'_progress.json',result)
        print(f'END {arm} {stage} exit={p.returncode}',flush=True)
    after=identity(arm);save(arm+'_source_after.json',after)
    result['source_unchanged']=after['all_match']
    result['artifacts']=[]
    for pattern in ['build/**/*.run','build/op_kernel/**/*.o','samples/build/**/*.bin','examples/build/sample']:
        for p in sorted((ROOT/arm).glob(pattern)):
            if p.is_file():result['artifacts'].append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
    result['ut']={'executed':False,'reason':'Frozen UT fixture references missing totalNum and incompatible initial tiling key/layout; dependencies separately observed. No fixture changes permitted in this frozen task.','exit_code':None}
    result['performance']={'executed':False,'reason':'Project example has one ACLNN call and no timer/warmup/repetition protocol; no general full-performance entry point provided. Profiler availability/help recorded separately.','operator_time':None}
    result['ended_at']=now();save(arm+'.json',result);summaries.append(result)
save('summary.json',{'observed_at':now(),'results':summaries,'official_evaluation':False,'npu_test_scope':'Only first public sample if example command succeeded; no full numerical gate or performance claim'})
