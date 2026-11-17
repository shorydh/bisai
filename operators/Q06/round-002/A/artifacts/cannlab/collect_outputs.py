"""Download and independently hash the exact compiled output files."""
from datetime import datetime,timezone
import hashlib,json,shlex,subprocess,tarfile
from pathlib import Path,PurePosixPath
W=Path(__file__).resolve().parent
C=json.loads((W/'completion.json').read_text())
S=json.loads((W/'completed_results/cloud_results/summary.json').read_text())
remote=C['remote_directory']
expected=[a for r in S['builds'] for a in r['generated_artifacts']]
assert expected
for a in expected:
 p=PurePosixPath(a['path'])
 assert not p.is_absolute() and '..' not in p.parts and p.parts[0] in {'P','PL','F','L'} and p.parts[1]=='build'
base='ssh -F "$HOME/.atomgitdevenv/.ssh/config" -o BatchMode=yes -o ConnectTimeout=15 -o ProxyCommand=none -o HostName=127.0.0.1 -o Port=31640 devenvc_cqjbt.6f03672c932a41d697bbe7c90e658d43.atomgit.0 '
bash=r'C:\Program Files\Git\bin\bash.exe'
cmd='cd '+shlex.quote(remote)+' && test ! -e compiled_artifacts.tar.gz && tar -czf compiled_artifacts.tar.gz -- '+' '.join(shlex.quote(a['path']) for a in expected)
with (W/'artifact_transfer.log').open('wb') as log:
 subprocess.run([bash,'-lc',base+shlex.quote(cmd)],stdout=log,stderr=subprocess.STDOUT,check=True)
 with (W/'compiled_artifacts.tar.gz').open('xb') as f:
  subprocess.run([bash,'-lc',base+shlex.quote('cat '+shlex.quote(remote+'/compiled_artifacts.tar.gz'))],stdout=f,stderr=log,check=True)
out=W/'compiled_outputs'
out.mkdir(exist_ok=False)
with tarfile.open(W/'compiled_artifacts.tar.gz') as t:
 assert {m.name for m in t.getmembers()}=={a['path'] for a in expected}
 assert all(m.isfile() for m in t.getmembers())
 t.extractall(out,filter='data')
checks=[]
for a in expected:
 p=out/a['path']
 assert p.stat().st_size==a['bytes']
 assert hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256']
 checks.append({**a,'independently_verified_after_download':True})
report={'verified_at':datetime.now(timezone.utc).isoformat(),'status':'PASS','files':checks,'archive_sha256':hashlib.sha256((W/'compiled_artifacts.tar.gz').read_bytes()).hexdigest(),'archive_bytes':(W/'compiled_artifacts.tar.gz').stat().st_size,'scope':'Downloaded build outputs independently match hashes in the remote build results; no execution of downloaded binaries.'}
(W/'compiled_output_audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'PASS','files':len(checks),'archive_bytes':report['archive_bytes']}))
