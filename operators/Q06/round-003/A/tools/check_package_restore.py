"""Restore the delivered PL/PL-lazy pair in a fresh directory and compare bytes."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
WORK=HERE.parent
PACKAGE=WORK/'repo/operators/Q06/round-003/A'
report_path=HERE/'raw_to_public_audit.json'
audit=json.loads(report_path.read_text(encoding='utf-8'))
assert audit['status']=='passed'
records=[json.loads(x) for x in (PACKAGE/'experiments.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
temp=Path(tempfile.mkdtemp(prefix='package-restore-',dir=HERE))
script=PACKAGE/'artifacts/restoration/restore_frozen.py'
cmd=[sys.executable,str(script),'--source-pl',str(PACKAGE/records[0]['candidate_version']['snapshot']),
     '--destination',str(temp/'restored'),'--audit-dir',str(temp/'evidence')]
result=subprocess.run(cmd,cwd=WORK,capture_output=True,text=True,encoding='utf-8')
rec={'command':cmd,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
(temp/'invocation.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
result.check_returncode()
verified=[]
for label,record in zip(['PL','PL-lazy'],records):
    snap=PACKAGE/record['candidate_version']['snapshot']
    restored=temp/'restored'/label
    files={p.relative_to(snap).as_posix():p.read_bytes() for p in snap.rglob('*') if p.is_file()}
    copied={p.relative_to(restored).as_posix():p.read_bytes() for p in restored.rglob('*') if p.is_file()}
    assert files==copied and len(files)==38
    verified.append({'version':label,'files':38,'all_bytes_identical_to_official_bound_package':True})
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
audit['delivered_restore_script_test']={'status':'passed','executed_at':datetime.now(timezone.utc).isoformat(),
    'script_sha256':digest(script),'invocation_ref':(temp/'invocation.json').relative_to(WORK).as_posix(),
    'result_ref':(temp/'evidence/restoration_audit.json').relative_to(WORK).as_posix(),'versions':verified,
    'scope':'Actual local restoration and exact byte comparison, no build, network or NPU run.'}
audit['audited_document_sha256']={name:digest(PACKAGE/name) for name in ('summary.md','README.md','experiments.jsonl','publication-manifest.json','validation.json')}
audit['audit_script_sha256']=digest(HERE/'audit_public_r003.py')
report_path.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'passed','restored_files':76,'audit':str(report_path)},ensure_ascii=False))
