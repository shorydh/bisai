"""Use the existing authorized CANNLab SSH profile; retain every build artifact log."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import uuid

W = Path(__file__).resolve().parent
BASH = r'C:\Program Files\Git\bin\bash.exe'
HOST = 'devenvc_cqjbt.6f03672c932a41d697bbe7c90e658d43.atomgit.0'
OPTIONS = '-F "$HOME/.atomgitdevenv/.ssh/config" -o BatchMode=yes -o ConnectTimeout=15 -o ProxyCommand=none -o HostName=127.0.0.1 -o Port=31640'

def now(): return datetime.now(timezone.utc).isoformat()
def save(name, value): (W/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def posix(p): return '/'+p.drive[0].lower()+p.as_posix()[2:]

def run(label, command):
    start=now()
    with (W/(label+'.log')).open('wb') as log:
        process=subprocess.Popen([BASH,'-lc',command],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        for line in iter(process.stdout.readline,b''):
            log.write(line); log.flush()
            print(line.decode('utf-8',errors='replace').rstrip(),flush=True)
        code=process.wait()
    save(label+'.json',{'started_at':start,'ended_at':now(),'exit_code':code,'command':command,'log':label+'.log'})
    if code: raise RuntimeError(label+' exited '+str(code))

def ssh(label, command): run(label, 'ssh '+OPTIONS+' '+shlex.quote(HOST)+' '+shlex.quote(command))

def transfer_stream(label, command, source=None, destination=None):
    start=now()
    cmd='ssh '+OPTIONS+' '+shlex.quote(HOST)+' '+shlex.quote(command)
    with (W/(label+'.log')).open('wb') as log:
        if source:
            with source.open('rb') as stream:
                p=subprocess.run([BASH,'-lc',cmd],stdin=stream,stdout=log,stderr=subprocess.STDOUT)
        else:
            with destination.open('xb') as stream:
                p=subprocess.run([BASH,'-lc',cmd],stdout=stream,stderr=log)
    save(label+'.json',{'started_at':start,'ended_at':now(),'exit_code':p.returncode,'command':cmd,'log':label+'.log'})
    print(json.dumps({'stage':label,'exit_code':p.returncode}),flush=True)
    if p.returncode:raise RuntimeError(label+' failed')

resume = sys.argv[1:] == ['--resume-upload-stream']
if (W/'transfer.json').exists() and not resume:
    raise RuntimeError('A transfer record already exists. Inspect/resume explicitly; never duplicate a build automatically.')
if resume:
    previous=json.loads((W/'transfer.json').read_text())
    assert previous['uploaded'] is False and previous['build_executed'] is False
    remote=previous['remote_directory']
else:
    remote='/mnt/workspace/q06_r002_a_cloud_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
bundle=W/'source_bundle_v2.tar.gz'
expected=json.loads((W/'preparation_v2.json').read_text())['sha256']
assert hashlib.sha256(bundle.read_bytes()).hexdigest()==expected
with tarfile.open(bundle) as archive:
    assert len(archive.getmembers())==154 and all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in archive.getmembers())
if not resume:
    save('transfer.json',{'created_at':now(),'remote_directory':remote,'bundle_sha256':expected,'bundle':bundle.name,'uploaded':False,'build_executed':False})
    ssh('remote_create','test -d /mnt/workspace && mkdir '+shlex.quote(remote))
transfer_stream('upload_stream','test -d '+shlex.quote(remote)+' && test ! -e '+shlex.quote(remote+'/source_bundle.tar.gz')+' && cat > '+shlex.quote(remote+'/source_bundle.tar.gz'),source=bundle)
extract="import hashlib,tarfile,pathlib; p=pathlib.Path('source_bundle.tar.gz'); assert hashlib.sha256(p.read_bytes()).hexdigest()=="+repr(expected)+"; t=tarfile.open(p); assert len(t.getmembers())==154 and all(m.isfile() and not m.name.startswith('/') and '..' not in pathlib.PurePosixPath(m.name).parts for m in t.getmembers()); t.extractall('.'); print('REMOTE_BUNDLE_HASH_AND_MEMBERS_VERIFIED')"
ssh('remote_unpack','cd '+shlex.quote(remote)+' && python3 -c '+shlex.quote(extract))
save('transfer.json',{'created_at':now(),'remote_directory':remote,'bundle_sha256':expected,'bundle':bundle.name,'uploaded':True,'build_executed':False})
ssh('build_console','source /home/developer/Ascend/cann-9.1.0/bin/setenv.bash && cd '+shlex.quote(remote)+' && python3 -u remote_build.py --root '+shlex.quote(remote))
ssh('remote_collect','cd '+shlex.quote(remote)+' && tar -czf cloud_results.tar.gz cloud_results')
transfer_stream('download_stream','cat '+shlex.quote(remote+'/cloud_results.tar.gz'),destination=W/'cloud_results.tar.gz')
out=W/'completed_results'
out.mkdir(exist_ok=False)
with tarfile.open(W/'cloud_results.tar.gz') as archive:
    assert all(not m.name.startswith('/') and '..' not in Path(m.name).parts and (m.isfile() or m.isdir()) for m in archive.getmembers())
    archive.extractall(out,filter='data')
report=json.loads((out/'cloud_results/summary.json').read_text())
save('completion.json',{'recorded_at':now(),'remote_directory':remote,'bundle_sha256':expected,'results_archive_sha256':hashlib.sha256((W/'cloud_results.tar.gz').read_bytes()).hexdigest(),'build_executed':True,'official_runs_added':0,'builds':[{'arm':r['arm'],'exit_code':r['exit_code'],'build_pass':r['build_pass'],'source_unchanged':r['source_unchanged']} for r in report['builds']]})
print('CLOUD_BUILD_EVIDENCE_DOWNLOADED',flush=True)
