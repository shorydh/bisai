"""Supplemental CANNLab compilation of frozen R002 sources; no NPU execution."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time

def now():
    return datetime.now(timezone.utc).isoformat()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def identities(root, expected):
    if len(expected) != 38:
        raise RuntimeError('Expected exactly 38 frozen source files')
    actual = {name: sha(root / name) for name in expected}
    if actual != expected:
        raise RuntimeError('Frozen source mismatch: ' + str(root))
    return actual

def capture(command):
    try:
        p = subprocess.run(command, capture_output=True, text=True, timeout=30)
        return {'command': command, 'exit_code': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'command': command, 'error': str(exc)}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve(strict=True)
    manifest = json.loads((root / 'source_manifest.json').read_text(encoding='utf-8'))
    if not os.environ.get('ASCEND_HOME_PATH'):
        raise RuntimeError('Activate the confirmed CANN environment before running; ASCEND_HOME_PATH is absent')
    results = root / 'cloud_results'
    results.mkdir(exist_ok=False)
    environment = {'observed_at': now(), 'platform': platform.platform(), 'machine': platform.machine(), 'python': platform.python_version(), 'cpu_count': os.cpu_count(), 'environment': {key: os.environ.get(key) for key in ['ASCEND_HOME_PATH','ASCEND_TOOLKIT_HOME','ASCEND_OPP_PATH','CONDA_DEFAULT_ENV']}, 'scope': 'Cloud build environment only; not the official evaluation environment'}
    environment['cann_paths'] = {key: str(Path(os.environ[key]).resolve()) for key in ['ASCEND_HOME_PATH','ASCEND_TOOLKIT_HOME','ASCEND_OPP_PATH'] if os.environ.get(key)}
    environment['version_files'] = []
    for base in set(environment['cann_paths'].values()):
        for name in ['version.cfg','version.info','ascend_toolkit_install.info']:
            version_file = Path(base)/name
            if version_file.is_file():
                environment['version_files'].append({'path':str(version_file),'sha256':sha(version_file),'content':version_file.read_text(errors='replace')})
    environment['tools'] = [capture([cmd, '--version']) for cmd in ['cmake', 'g++', 'make', 'ccec'] if shutil.which(cmd)]
    environment['npu_info'] = capture(['npu-smi', 'info']) if shutil.which('npu-smi') else None
    write(results / 'environment.json', environment)
    builds = []
    for arm in ['P', 'PL', 'F', 'L']:
        spec = manifest['versions'][arm]
        project = root / arm
        if project.is_symlink() or (project/'build').exists() or (project/'build_out').exists():
            raise RuntimeError('Requires a fresh, separate project with no prior build: ' + arm)
        before = identities(project, spec['files'])
        editable = ['op_host/pad_v3_grad_def.cpp','op_host/pad_v3_grad_infershape.cpp','op_host/pad_v3_grad_tiling.cpp','op_kernel/pad_v3_grad.cpp','op_kernel/pad_v3_grad.h','op_kernel/pad_v3_grad_tiling_data.h','op_kernel/pad_v3_grad_tiling_key.h']
        tree = hashlib.sha256(''.join(name+'\0'+before[name]+'\n' for name in sorted(editable)).encode('utf-8')).hexdigest()
        if tree != spec['source_tree_sha256']:
            raise RuntimeError('Seven-source tree mismatch: '+arm)
        start = now()
        timer = time.perf_counter()
        with (results / (arm + '.log')).open('wb') as log:
            proc = subprocess.run(['bash', 'build.sh', '-j4'], cwd=project, stdout=log, stderr=subprocess.STDOUT)
        elapsed = time.perf_counter() - timer
        after = identities(project, spec['files'])
        output_files = sorted(list((project/'build').glob('custom_opp_*.run')) + list((project/'build/op_kernel/ascendc_kernels/binary/ascend910b').rglob('*.o')))
        artifacts = [{'path': p.relative_to(root).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in output_files if p.is_file()]
        record = {'arm': arm, 'source_tree_sha256': spec['source_tree_sha256'], 'official_task_id': spec['official_task_id'], 'started_at': start, 'ended_at': now(), 'build_elapsed_seconds': elapsed, 'command': ['bash','build.sh','-j4'], 'exit_code': proc.returncode, 'log': arm+'.log', 'log_sha256': sha(results/(arm+'.log')), 'source_files_before': before, 'source_files_after': after, 'source_unchanged': before==after, 'generated_artifacts': artifacts, 'npu_test_executed': False, 'official_metrics': None, 'scope': 'Supplemental cloud compilation after the official run; elapsed seconds describe build duration, not operator performance'}
        record['artifact_checks'] = {'nonempty_package':any(a['path'].endswith('.run') and a['bytes']>0 for a in artifacts), 'nonempty_kernel_object':any(a['path'].endswith('.o') and a['bytes']>0 for a in artifacts)}
        record['build_pass'] = proc.returncode == 0 and all(record['artifact_checks'].values())
        write(results / (arm + '.json'), record)
        builds.append(record)
        print(json.dumps({'arm':arm, 'exit_code':proc.returncode, 'source_unchanged':True, 'generated_artifacts':len(artifacts)}), flush=True)
    write(results/'summary.json', {'created_at':now(), 'builds':builds, 'official_runs_added':0, 'source_code_changed':False})

if __name__ == '__main__':
    main()
