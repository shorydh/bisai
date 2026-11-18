"""Prepare R003 A handoff from local evidence. No network, build, POST or Git mutation.

Default only reports readiness. --build requires terminal official evidence and a
reviewed cloud publication manifest; missing stages may be honestly recorded there.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil

W = Path(__file__).resolve().parent
RAW = W / 'raw_official'
OUT = W / 'repo/operators/Q06/round-003/A'
TASK = 'Q06-R003-A-LAZY-OFFICIAL'
BASE = 'facfb39ece01643fa7f9452d09971f9ca4d2b246'
PID = '6ad9ab403ff2fef7e80e2a1d'
HASHES = {'PL': '988e491ec2d8d758adac5caa0e304cc81cb500ade732aadc9427fa1254267d41',
          'PL-lazy': '03e6bc1bb81dc40ba71d4691aeb08feebdf38fe0a2ac12f2a59aeff0445afb39'}
FIELDS = 'experiment_id operator round_id agent_id task_id base_version candidate_version hypothesis change official_task_id official_result_ref evaluated_at evaluation_protocol official_status official_metrics baseline_official_result_ref comparison finding_status applicability artifacts notes'.split()
CONFIG = ['_id', 'name', 'title', 'version_no', 'version_label', 'code_template', 'cann_version', 'judge_revision', 'score_mode', 'use_baseline', 'iterations', 'ranking_submission_mode', 'ranking_testcase_count', 'judge_baseline_verified', 'difficulty']
OFIELDS = ['_id', 'ID', 'problem_id', 'create_time', 'status', 'valid', 'judge_revision', 'public_only', 'judge_missing_cases', 'theory_score', 'total_testcase_count', 'result']
RFIELDS = ['rank', 'submission_id', 'status', 'create_time', 'score', 'result']
TERMINAL = {'Pass', 'Accepted', 'Fail', 'Wrong Answer', 'Compile Error', 'Runtime Error', 'Time Limit Exceeded', 'Memory Limit Exceeded', 'System Error'}

def now(): return datetime.now(timezone.utc).isoformat()
def sha(b): return hashlib.sha256(b).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
def relative(path): return path.relative_to(W).as_posix()
def tree(files): return sha(''.join(k + '\0' + sha(files[k]) + '\n' for k in sorted(files)).encode('utf-8'))
def projection(data, fields): return {k: data[k] for k in fields if k in data}
def provenance(path, endpoint=None):
    return {'machine_A_raw_file': relative(path), 'source_file_sha256': sha(path.read_bytes()),
            'official_endpoint': endpoint, 'extraction': 'Explicit projection; retained metrics are unchanged. Account/profile and unrelated ranking rows omitted.'}
def official_project(path):
    d = read(path)
    return {**projection(d, OFIELDS), '_publication': provenance(path, f'https://cannjudge.cn/api/submissions/{d.get("_id")}')}
def public_scale(official):
    return sorted((r.get('testcase_id'), r.get('type'), r.get('best_time')) for r in official.get('result', []) if r.get('testcase_status') != 'Hidden')
def rank_signature(scale):
    return sorted(tuple(x.get(k) for k in ['_id', 'id', 'ID', 'baseline', 'tbest', 'type']) for x in scale)
def validate_relative(value):
    p = PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or ':' in value or '\\' in value:
        raise ValueError('Unsafe package path: ' + value)
    return value

def readiness(cloud_manifest):
    plan = read(W / 'plan.json')
    missing = []
    for item in plan['runs']:
        d = RAW / 'runs' / item['experiment_id']
        for name in ['attempt.json', 'request_files.json', 'submit_response.json', 'submit_response.meta.json', 'receipt.json', 'frozen_manifest.json', 'official_terminal.json', 'latest_check.json', 'problem_before.json', 'problem_after.json']:
            if not (d / name).exists(): missing.append(relative(d / name))
        if (d / 'official_terminal.json').exists():
            o = read(d / 'official_terminal.json')
            if o.get('status') not in TERMINAL: missing.append(item['experiment_id'] + ': nonterminal')
            if o.get('status') == 'Pass' and o.get('valid') is True and not list((d / 'ranking_exact').glob('*.json')):
                missing.append(item['experiment_id'] + ': exact ranking absent')
    if not cloud_manifest.exists(): missing.append(str(cloud_manifest))
    return {'ready': not missing, 'missing': missing, 'planned_runs': plan['runs'], 'action': 'Readiness only; no handoff files generated'}

def publish_config(source, target):
    d = read(source)
    save(target, {**{k: d.get(k) for k in CONFIG}, '_publication': provenance(source, f'https://cannjudge.cn/api/problems/{PID}')})

def common(cloud_manifest):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / '.gitattributes').write_text('* -text\n', encoding='utf-8')
    copy(W / 'task.txt', OUT / 'artifacts/task.txt')
    copy(W / 'plan.json', OUT / 'artifacts/plan.json')
    for p in sorted((W / 'restoration').iterdir()):
        if p.is_file(): copy(p, OUT / 'artifacts/restoration' / p.name)
    for name in ['reuse-audit.json', 'source-manifest.json', 'audit_prior.py', 'remote-heads.txt',
                 'current_protocol.json', 'report.md', 'scoring-rules-content.js',
                 'scoring-rules-content.meta.json', 'collector_review.json']:
        copy(W / 'prior_audit' / name, OUT / 'artifacts/prior_audit' / name)
    copy(Path(__file__), OUT / 'tools/build_handoff_r003.py')
    copy(W / 'official_r003.py', OUT / 'tools/official_r003.py')
    copy(W / 'wait_official.py', OUT / 'tools/wait_official.py')
    inspect_dir = W / read(RAW / 'latest_inspection.json')['path']
    observed = read(inspect_dir / 'inspection.json')
    # Do not copy arbitrary exact rows if a later inspection finds historical tasks.
    inspect_public = projection(observed, ['observed_at', 'configuration', 'tasks', 'scans', 'scope'])
    inspect_public['exact_ranking_matches'] = [{
        'submission_id': sid, 'score': data.get('row', {}).get('score'),
        'observed_at': data.get('response_meta', {}).get('observed_at'),
        'source_response_sha256': data.get('response_meta', {}).get('raw_response_sha256')
    } for sid, data in observed.get('exact_ranking_matches', {}).items()]
    inspect_public['_publication'] = provenance(inspect_dir / 'inspection.json')
    save(OUT / 'artifacts/reuse/inspection.json', inspect_public)
    for arm in ['P', 'PL']:
        source = inspect_dir / f'{arm}_official.json'
        if source.exists(): save(OUT / f'artifacts/reuse/{arm}_official_refreshed.json', official_project(source))
        meta = source.with_suffix('.meta.json')
        if meta.exists(): copy(meta, OUT / f'artifacts/reuse/{arm}_official_refreshed.meta.json')
    denied = inspect_dir / 'PL-lazy_official.json'
    denied_meta = denied.with_suffix('.meta.json')
    if denied.exists():
        raw = read(denied)
        save(OUT / 'artifacts/reuse/B_1379766_access.json', {
            'original_experiment_id': 'Q06-R002-B-E004', 'original_round_id': 'round-002',
            'official_numeric_id': 1379766, 'submission_id': '6afc1e5b6bd0f9be374a4c6d',
            'request_metadata': read(denied_meta), 'response_message': raw.get('message'),
            'historical_user_reported_score': 29.64, 'historical_user_reported_status': 'Pass',
            'score_source': 'User task text, not independently rebound to a current official ranking',
            'current_score': None, 'original_score_observed_at': None,
            'scope': 'Read-only access/reuse audit; not a new evaluation', '_publication': provenance(denied)})
    publish_config(inspect_dir / 'problem.json', OUT / 'artifacts/config/initial.json')
    raw_problem = read(inspect_dir / 'problem.json')
    save(OUT / 'artifacts/rules/current_problem.json', {
        **{k: raw_problem.get(k) for k in CONFIG}, 'desc': raw_problem.get('desc'),
        'response_metadata': read((inspect_dir / 'problem.json').with_suffix('.meta.json')),
        '_publication': provenance(inspect_dir / 'problem.json', f'https://cannjudge.cn/api/problems/{PID}')})
    historical = {'round_002_A_commit': BASE,
        'round_002_A_ref': f'https://github.com/shorydh/bisai/tree/{BASE}/operators/Q06/round-002/A',
        'B_1379766': {'experiment_id': 'Q06-R002-B-E004', 'round_id': 'round-002', 'task_id': None,
                      'official_numeric_id': 1379766, 'submission_id': '6afc1e5b6bd0f9be374a4c6d',
                      'source': 'User task plus access audit; original B task_id unavailable, not invented'},
        'C_fixed_commit': '622d7f0064073dff249c23424330466ce510e3e2',
        'C_latest_published_evidence': 'artifacts/prior_audit/reuse-audit.json',
        'scope': 'Historical records retain original IDs and times; GET refresh and references are not independent runs'}
    save(OUT / 'artifacts/historical_references.json', historical)
    cloud = read(cloud_manifest)
    if not isinstance(cloud.get('files'), list) or not isinstance(cloud.get('versions'), dict):
        raise ValueError('Cloud manifest requires reviewed files and per-version stages')
    for row in cloud['files']:
        source = W / validate_relative(row['source'])
        target = OUT / validate_relative(row['target'])
        if not row['target'].startswith('artifacts/cannlab/'): raise ValueError('Cloud target must be in artifacts/cannlab')
        if 'sha256' in row and sha(source.read_bytes()) != row['sha256']: raise ValueError('Cloud file hash mismatch')
        copy(source, target)
    save(OUT / 'artifacts/cannlab/publication_manifest.json', cloud)
    return cloud

def collect_run(item):
    label, arm = item['experiment_id'], item['version']
    d = RAW / 'runs' / label
    receipt, frozen, o, check = [read(d / n) for n in ['receipt.json', 'frozen_manifest.json', 'official_terminal.json', 'latest_check.json']]
    sid = receipt['submission_id']
    assert receipt['version'] == arm and receipt['source_tree_sha256'] == HASHES[arm]
    assert o['_id'] == sid and o['problem_id'] == PID and o['status'] in TERMINAL
    assert check['_id'] == sid and check['all_38_match'] is True
    assert frozen['source_tree_sha256'] == HASHES[arm]
    editable = {f['path'] for f in frozen['files'] if f['editable']}
    returned = {f['path']: f['content'].encode('utf-8') for f in o['files']}
    assert len(frozen['files']) == len(returned) == 38 and len(editable) == 7
    assert tree({k: returned[k] for k in editable}) == HASHES[arm]
    for f in frozen['files']:
        file = validate_relative(f['path'])
        data = (W / arm / file).read_bytes()
        assert sha(data) == f['sha256'] and data == returned[file]
        copy(W / arm / file, OUT / 'artifacts/code' / HASHES[arm] / file)
    manifest = {**frozen, 'submission_id': sid, 'official_numeric_id': o.get('ID'),
                'all_38_matches_official': True, 'official_zip_sha256': None,
                'zip_note': 'Reconstructed source tree; no claim that any newly packaged ZIP equals an official ZIP.'}
    save(OUT / f'artifacts/manifests/{sid}.json', manifest)
    save(OUT / f'artifacts/official/{sid}.json', official_project(d / 'official_terminal.json'))
    response, response_meta = read(d / 'submit_response.json'), read(d / 'submit_response.meta.json')
    assert set(response) <= {'code', 'msg', 'data'} and isinstance(response.get('data'), dict)
    assert set(response['data']) == {'submissionId'} and response['data']['submissionId'] == sid
    assert sha((d / 'submit_response.json').read_bytes()) == response_meta['raw_response_sha256']
    for name in ['attempt.json', 'submit_response.json', 'submit_response.meta.json', 'receipt.json', 'frozen_manifest.json', 'request_files.json', 'latest_check.json']:
        copy(d / name, OUT / 'artifacts/submissions' / label / name)
    save(OUT / f'artifacts/submissions/{label}/receipt_chain.json', {
        'official_task_id':sid,
        'request_files_sha256':sha((d/'request_files.json').read_bytes()),
        'attempt_sha256':sha((d/'attempt.json').read_bytes()),
        'raw_submit_response_sha256':sha((d/'submit_response.json').read_bytes()),
        'submit_response_meta_sha256':sha((d/'submit_response.meta.json').read_bytes()),
        'receipt_sha256':sha((d/'receipt.json').read_bytes()),
        'submission_id_in_raw_response_matches_receipt':True})
    for phase in ['before', 'after']:
        publish_config(d / f'problem_{phase}.json', OUT / f'artifacts/config/{label}_{phase}.json')
        meta = d / f'problem_{phase}.meta.json'
        if meta.exists(): copy(meta, OUT / f'artifacts/config/{label}_{phase}.meta.json')
    observations = []
    for p in sorted((d / 'observations').glob('*.json')):
        if p.name.endswith('.meta.json'): continue
        observed = read(p)
        observations.append({'official_result_projection': projection(observed, OFIELDS),
            'response_metadata': read(p.with_suffix('.meta.json')), '_publication': provenance(p),
            'source_verified_at_terminal': True})
    save(OUT / f'artifacts/submissions/{label}/observation_log.json', observations)
    ranks = []
    public_ids = {r[0] for r in public_scale(o)}
    for p in sorted((d / 'ranking_exact').glob('*.json')):
        r = read(p)
        raw_path = W / r['source_response']
        raw = read(raw_path)
        assert sha(raw_path.read_bytes()) == r['source_response_sha256']
        matches = [row for row in raw['rows'] if row.get('submission_id') == sid]
        assert len(matches) == 1 and matches[0] == r['row']
        public = [projection(case, ['_id', 'id', 'ID', 'baseline', 'tbest', 'type']) for case in raw['testcases'] if case['_id'] in public_ids]
        assert {case['_id'] for case in public} == public_ids
        row = projection(r['row'], RFIELDS)
        if isinstance(r['row'].get('submission'), dict):
            row['submission'] = projection(r['row']['submission'], ['_id', 'ID', 'status', 'create_time'])
        ref = f'artifacts/ranking/{sid}_{p.stem}.json'
        published = {'official_task_id': sid, 'row': row,
                     'observed_at': r['observed_at'], 'public_scoring_scale': public,
                     'source_response_sha256': r['source_response_sha256'],
                     'source_response_ref_on_machine_A': r['source_response'],
                     'endpoint': r['endpoint'], 'params': r['params'],
                     'scope': 'Exact task row and public testcase scale from the same HTTP response. Other accounts and hidden testcase definitions omitted.',
                     '_publication': provenance(p, r['endpoint'])}
        save(OUT / ref, published)
        ranks.append({'ref': ref, 'observed_at': r['observed_at'], 'score': row.get('score'), 'public_scale': public})
    for p in sorted((d / 'ranking_scans').glob('*.json')):
        copy(p, OUT / 'artifacts/submissions' / label / 'ranking_scans' / p.name)
    return {'item': item, 'arm': arm, 'label': label, 'sid': sid, 'official': o, 'receipt': receipt,
            'check': check, 'manifest': manifest, 'ranks': ranks,
            'score': ranks[0]['score'] if ranks else None,
            'before': read(d / 'problem_before.json'), 'after': read(d / 'problem_after.json')}

def compare(a, b):
    ar, br = (x['ranks'][0] if x['ranks'] else None for x in [a, b])
    checks = {
        'both_pass': all(x['official'].get('status') == 'Pass' for x in [a, b]),
        'both_valid': all(x['official'].get('valid') is True for x in [a, b]),
        'same_problem': all(x['official'].get('problem_id') == PID for x in [a, b]),
        'same_revision': a['official'].get('judge_revision') == b['official'].get('judge_revision') is not None,
        'same_public_only': a['official'].get('public_only') == b['official'].get('public_only') is not None,
        'same_count': a['official'].get('total_testcase_count') == b['official'].get('total_testcase_count') is not None,
        'no_missing_cases': all(x['official'].get('judge_missing_cases') is False for x in [a, b]),
        'all_source_identity_verified': all(x['check']['all_38_match'] is True for x in [a, b]),
        'same_readonly_template': sorted((x['path'], x['sha256']) for x in a['manifest']['files'] if not x['editable']) == sorted((x['path'], x['sha256']) for x in b['manifest']['files'] if not x['editable']),
        'same_before_after_config': all(x[p].get(k) == b['before'].get(k) for x in [a, b] for p in ['before', 'after'] for k in CONFIG),
        'same_visible_terminal_scale': public_scale(a['official']) == public_scale(b['official']),
        'both_visible_pass': all(r.get('testcase_status') == 'Pass' for x in [a, b] for r in x['official']['result'] if r.get('testcase_status') != 'Hidden'),
        'same_response_public_rank_scale': ar is not None and br is not None and rank_signature(ar['public_scale']) == rank_signature(br['public_scale']),
        'rank_scale_matches_terminal': all(x['ranks'] and sorted((r['_id'],r.get('type'),r.get('tbest')) for r in x['ranks'][0]['public_scale']) == public_scale(x['official']) for x in [a,b]),
        'both_exact_scores': all(isinstance(x['score'], (int, float)) and not isinstance(x['score'], bool) for x in [a, b]),
    }
    good = all(checks.values())
    invalid = any(x['official'].get('status') != 'Pass' or x['official'].get('valid') is False for x in [a, b])
    return {'baseline_official_task_id': b['sid'], 'baseline_role': 'PL direct-parent local control; P remains historical work starting point, not team common baseline',
        'metric': 'Official exact-submission ranking row.score', 'candidate_score_raw': a['score'], 'baseline_score_raw': b['score'],
        'observed_total_score_delta': float(Decimal(str(a['score'])) - Decimal(str(b['score']))) if good else None,
        'comparison_status': 'verified' if good else ('invalid' if invalid else 'pending'), 'checks': checks,
        'stable_gain': None, 'operator_speedup': None, 'team_baseline_qualification': 'pending',
        'scope': 'Bounded observed official score difference only; no stable/causal gain, cross-environment speedup or superiority over P inferred',
        'reason': 'All listed public conditions matched' if good else 'Not comparable: ' + ', '.join(k for k,v in checks.items() if not v)}

def version(x):
    return {'snapshot': 'artifacts/code/' + HASHES[x['arm']], 'source_tree_sha256': HASHES[x['arm']],
            'manifest': f'artifacts/manifests/{x["sid"]}.json', 'files_count': 38,
            'official_task_id': x['sid'], 'origin': 'R002 PL exact files' if x['arm'] == 'PL' else 'Task-supplied exact lazy patch on PL',
            'restore_evidence': 'artifacts/restoration/restoration_audit.json'}

def build(cloud_manifest):
    ready = readiness(cloud_manifest)
    if not ready['ready']: raise RuntimeError('Missing required evidence: ' + str(ready['missing']))
    plan = read(W / 'plan.json')
    assert [(x['experiment_id'], x['version']) for x in plan['runs']] == [('Q06-R003-A-E001','PL'), ('Q06-R003-A-E002','PL-lazy')]
    cloud = common(cloud_manifest)
    items = [collect_run(x) for x in plan['runs']]
    base = items[0]
    records = []
    for x in items:
        o, sid, label = x['official'], x['sid'], x['label']
        comp = compare(x, base)
        stages = cloud['versions'].get(x['arm'])
        if not isinstance(stages, dict): raise ValueError('Missing cloud stage record for ' + x['arm'])
        ranks = [{k:v for k,v in r.items() if k != 'public_scale'} for r in x['ranks']]
        artifacts = [f'artifacts/manifests/{sid}.json', f'artifacts/code/{HASHES[x["arm"]]}',
            f'artifacts/submissions/{label}/observation_log.json', f'artifacts/submissions/{label}/request_files.json',
            f'artifacts/submissions/{label}/receipt.json', 'artifacts/restoration/restoration_audit.json',
            f'artifacts/submissions/{label}/receipt_chain.json',
            f'artifacts/submissions/{label}/submit_response.json',
            f'artifacts/submissions/{label}/submit_response.meta.json',
            'artifacts/restoration/entrypoints.md', 'artifacts/prior_audit/reuse-audit.json',
            'artifacts/reuse/inspection.json', 'artifacts/plan.json', 'artifacts/task.txt',
            'artifacts/cannlab/publication_manifest.json'] + [r['ref'] for r in ranks]
        record = {
            'experiment_id': label, 'operator':'PadV3Grad', 'round_id':'round-003', 'agent_id':'A', 'task_id':TASK,
            'base_version': version(base), 'candidate_version': version(x),
            'hypothesis': '为冻结 PL-lazy 取得直接父版 PL 的同批局部对照' if x['arm']=='PL' else '延迟构造相对准确父版 PL 在同公开协议下产生可辨观察分差',
            'change': plan['runs'][len(records)]['change'], 'official_task_id':sid,
            'official_result_ref':f'artifacts/official/{sid}.json', 'evaluated_at':None,
            'evaluation_protocol': {'provider':'CANNJudge', 'problem_id':PID,
                'submission_url':f'https://cannjudge.cn/public/ictcompetition/padv3grad/submission/{sid}',
                'official_numeric_id':o.get('ID'), 'cann_version':x['before'].get('cann_version'),
                'judge_revision':o.get('judge_revision'), 'public_only':o.get('public_only'),
                'submitted_at':o.get('create_time'), 'request_started_at':x['receipt'].get('request_started_at'),
                'receipt_observed_at':x['receipt'].get('response_observed_at'),
                'terminal_observed_at':x['check'].get('observed_at'), 'evaluation_completion_timestamp':None,
                'problem_configuration_before_ref':f'artifacts/config/{label}_before.json',
                'problem_configuration_after_ref':f'artifacts/config/{label}_after.json',
                'public_rule_ref':'artifacts/rules/current_problem.json',
                'current_protocol_audit_ref':'artifacts/prior_audit/current_protocol.json',
                'rule_report_ref':'artifacts/prior_audit/report.md',
                'iterations':x['before'].get('iterations'), 'ranking_submission_mode':x['before'].get('ranking_submission_mode'),
                'all_38_source_files_verified':True, 'cloud':stages,
                'official_hardware':None, 'official_driver':None, 'official_load':None,
                'full_precision_algorithm':None, 'timing_warmup_sync_aggregation':None, 'degradation_threshold':None},
            'official_status':o.get('status'),
            'official_metrics': {**projection(o,['theory_score','total_testcase_count','judge_missing_cases','result']),
                                 'total_score':x['score'],'ranking_observations':ranks},
            'baseline_official_result_ref':f'artifacts/official/{base["sid"]}.json',
            'comparison':comp, 'finding_status':comp['comparison_status'],
            'applicability':'Source identity, official terminal result and bounded score comparison only; no stable best or team baseline approval',
            'artifacts':artifacts,
            'notes':{'version_label':x['arm'],'independent_official_run':True,'new_optimization':False,
                     'completion_time_reason':'Official actual completion time not supplied; create_time is submission time.',
                     'historical_B_reference':'Q06-R002-B-E004 / 1379766 retains its original identity; not a new A run.',
                     'P_comparison':'No superiority over P asserted or new P/F/L evaluation in this plan.'}}
        assert list(record)==FIELDS
        records.append(record)
    (OUT/'experiments.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records),encoding='utf-8')
    save(OUT/'artifacts/audit/bounded_comparison.json',{'checked_at':now(),'task_id':TASK,'PL_lazy_vs_PL':records[1]['comparison'],
         'all_observations_retained':True,'C_and_baseline_reference':'artifacts/prior_audit/reuse-audit.json','stable_best':None})
    docs(records,items,cloud)
    checked=[]
    for p in sorted(OUT.rglob('*')):
        if p.is_file() and p.name not in ['publication-manifest.json','validation.json']:
            checked.append({'path':p.relative_to(OUT).as_posix(),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size})
    save(OUT/'publication-manifest.json',{'generated_at':now(),'files':checked,'scope':'Package file hashes; not official ZIP hash'})
    save(OUT/'validation.json',{'builder_checked_at':now(),'records':len(records),'fields_each':21,
         'source_files_each':38,'official_source_identity_matches':True,
         'comparison_status':records[1]['comparison']['comparison_status'],
         'independent_review':'Not performed by this builder; parent agent must audit raw-to-public correspondence and package links.'})
    print(json.dumps({'package':str(OUT),'records':2,'comparison':records[1]['comparison'],'independent_review_required':True},ensure_ascii=False))

def docs(records,items,cloud):
    rows=[]
    for r,x in zip(records,items):
        delta=r['comparison']['observed_total_score_delta']
        rows.append(f'| {r["experiment_id"]} / {x["arm"]} | {r["hypothesis"]}；恢复既有冻结版本 | `{HASHES[x["arm"]]}` | 官方 {x["official"].get("ID")} / `{x["sid"]}` | {r["official_status"]}，valid={x["official"].get("valid")}，总分 {x["score"]} | {delta if delta is not None else "null：条件不足"} | {r["finding_status"]}，仅该次观察 | [结果]({r["official_result_ref"]}) / [源码清单](artifacts/manifests/{x["sid"]}.json) |')
    comparison=records[1]['comparison']
    comparable=comparison['comparison_status']=='verified'
    valid=[x for x in items if x['official'].get('status')=='Pass' and x['official'].get('valid') is True and isinstance(x['score'],(int,float))]
    best=max(valid,key=lambda x:x['score']) if valid and comparable else None
    best_text=(f'本轮可比的最高有效单次观察为 {best["arm"]}，{best["score"]} 分，任务 {best["official"]["ID"]}。' if best else '本轮最佳有效版本不能裁定，见比较条件与官方结果。')
    stage_lines=['| 版本 | 原样构建 | 源码身份 | 首个 NPU 样例 | msprof 实际采集 |',
                 '|---|---|---|---|---|']
    stage_notes=[]
    for arm in HASHES:
        stages=cloud['versions'][arm]
        build=stages.get('build',{})
        example=stages.get('example',{})
        profiler=stages.get('profiler',{})
        ut=stages.get('ut',{})
        perf=stages.get('performance',{})
        build_text=f"执行={build.get('executed')}，exit={build.get('exit_code')}"
        example_text=f"执行={example.get('executed')}，exit={example.get('exit_code')}，mismatched={example.get('mismatched')}/{example.get('total')}"
        profiler_text=f"执行={profiler.get('executed')}，exit={profiler.get('exit_code')}，op_summary={profiler.get('op_summary_count')}，复验 exit={profiler.get('verification_exit_code')}"
        stage_lines.append(f"| {arm} | {build_text} | 38文件前后一致={stages.get('source_unchanged')} | {example_text} | {profiler_text} |")
        ut_reason = '冻结 fixture 引用了不存在的 totalNum，且初始 tiling key/layout 与当前实现不符；本任务保持冻结版本，未修改 fixture' if not ut.get('executed') and 'totalNum' in (ut.get('reason') or '') else ut.get('reason')
        perf_reason = '仅采集一次首样例的插桩调用，缺少预热、重复统计及全用例覆盖' if not perf.get('executed') and 'one first-sample' in (perf.get('reason') or '') else perf.get('reason')
        stage_notes.append(f"- {arm} UT：执行={ut.get('executed')}；原因：{ut_reason}。")
        stage_notes.append(f"- {arm} Profiler 覆盖：首个公开 FP32 reflect 样例；warmup={profiler.get('warmup_calls')}，应用调用={profiler.get('application_calls')}。常规性能阶段：执行={perf.get('executed')}；原因：{perf_reason}。")
        raw_rows=profiler.get('actual_kernel_rows') or []
        if isinstance(raw_rows,list):
            durations=[row.get('Task Duration(us)') for row in raw_rows if isinstance(row,dict) and 'Task Duration(us)' in row]
            if durations: stage_notes.append(f"- {arm} 此次插桩单调用的原始 `Task Duration(us)`：{', '.join(str(x) for x in durations)}；只作诊断，不计算稳定收益或官方分差。")
    summary=f'''# 第六题 PadV3Grad／round-003／A

任务 `{TASK}`；起点 `{BASE}`，分支 `q06/r003/a-lazy-official`。本轮独立恢复既有 PL 与 PL-lazy，没有新增优化。PL 是直接父版局部对照；P 是此前工作起点，团队共同基线尚未确立。

## 统一实验表

| 实验 | 假设与改动 | 准确七源码版本 | 来源／官方任务 | 状态及原始总分 | 相对本轮 PL 分差 | 结论 | 证据 |
|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

官方返回的完整 result（包括 Hidden/null）见 [experiments.jsonl](experiments.jsonl)。`evaluated_at=null`：官方未给实际完成时间；提交、回执、终态观察、排行观察时间分别记录。`theory_score` 不替代排行总分，分差不换算算子加速比。

## 比较与发现

- **{comparison['comparison_status']}：PL-lazy 对 PL 的有界官方总分比较。** 分差为 {comparison['observed_total_score_delta']}；适用条件与逐项核对见 [比较审计](artifacts/audit/bounded_comparison.json)。全部重复观察保留；一次分差不证明稳定收益或因果贡献。
- **verified：独立恢复身份。** 两份完整 38 文件均绑定实际官方源码回读。PL-lazy 只有主头变化，其余 37 文件与 PL 字节一致，reference 保持任务单 SHA。见 [恢复审计](artifacts/restoration/restoration_audit.json)。
- **verified：历史记录不重编号。** B 的 `Q06-R002-B-E004 / 1379766` 详情在本次授权账号下返回 403；当前扫描缺旧 PL/P 的精确任务排行行。用户交付的旧29.64不混入当前分差，缺行不当作0分。旧四臂保留原轮次、任务与观察时间；详情 GET 不计新运行。见 [复用检查](artifacts/reuse/inspection.json)与[B 访问记录](artifacts/reuse/B_1379766_access.json)。
- **pending：稳定收益与共同基线。** 本轮没有主张优于工作 P，也没有追加 F/L/P。已核对的 C 固定提交 `622d7f0064073dff249c23424330466ce510e3e2` 验证了真实依赖 reference 与合法 edge 四变体，golden 为 `[0,0,0]`；其设备执行为 false、actual_npu_output=null。CPU 源码模型首元素为1不是 NPU 实测。本次可见发布记录仍缺冻结 r6/P 对同一合法输入的 NPU 输出与调用/分支证据，未发布进度未知；见[前序审计](artifacts/prior_audit/reuse-audit.json)。团队基线仍由中央结合该实际 NPU 裁决。
- **verified：旧 UT fixture 与当前 tiling 不匹配。** 这是源码静态发现，未自动改写为“本轮构建失败”。具体字段和 README/CMake 差异见[入口检查](artifacts/restoration/entrypoints.md)。

{best_text} 稳定最佳未确定；本轮单次观察不批准替换团队共同基线。是否继续研究延迟构造的设备缓存成本，结合 B 的对应设备证据；不因本轮分差擅自叠加新优化。

## 云环境与未完成项

{chr(10).join(stage_lines)}

{chr(10).join(stage_notes)}

首样例仅 FP32 reflect 输入 `[1,1,8,8]` 到 `[1,1,4,4]`，不是全量精度，也不包含 C 的合法 edge 数值门。静态 UT 缺项包括不存在的 totalNum 字段、初始 tiling key/layout 与当前实现不一致；本轮未改冻结模板以制造 UT 通过。详细记录与实际产物见 [云证据清单](artifacts/cannlab/publication_manifest.json)。

编译、首样例、UT、常规性能和 Profiler 分开记；构建耗时不是算子耗时。单次插桩采集有真实硬件时间，但没有重复预热统计，不能当作稳定性能比较；云结果不替代官方比较。完整误差算法、官方计时/预热/同步和退化阈值仍未知；不据此虚构指标或无限追加提交。

## 材料与下一步

完整代码在 `artifacts/code/<七源码SHA>/`，各目录 38 文件；冻结任务/方案、恢复补丁、官方状态与所有排行观察、同响应公开标尺和云证据位于 `artifacts/`。公开结果剔除其他账号与无关排行，保留原指标及原响应 SHA；完整原始响应留本机 `work/Q06/round-003/A/raw_official/`。

中央可从 [README](README.md) 校验并恢复准确工程，复核局部 PL 比较与 C 数值门；如需新优化或新的计时实现，应建立新快照并保留相应官方结果。本包不声称重建 ZIP 的外层哈希等于官方 ZIP。
'''
    (OUT/'summary.md').write_text(summary,encoding='utf-8')
    (OUT/'README.md').write_text('''# Q06 round-003 A 交接包

先读 [summary.md](summary.md)、[任务单](artifacts/task.txt) 与 [experiments.jsonl](experiments.jsonl)。

完整冻结工程位于 `artifacts/code/<source_tree_sha256>/`，无额外 code/ 层；以对应 `artifacts/manifests/<submission_id>.json` 校验全部38文件，不能只比较分支名。UTF-8/LF 源码按字节复制，本目录 `.gitattributes` 禁止 Git 自动转换。

构建和测试入口及旧 UT fixture 缺项见 [入口审计](artifacts/restoration/entrypoints.md)。不要修改冻结目录来调试；诊断副本另留源码差异。

[恢复脚本](artifacts/restoration/restore_frozen.py)可从准确 PL 工程和同目录补丁重建两臂；目标目录必须尚无 PL/PL-lazy，脚本拒绝覆盖。该脚本没有提交或构建动作。

`tools/official_r003.py` 与 `tools/build_handoff_r003.py` 是本机流程代码存档，默认路径依赖原 `work/Q06/round-003/A` 布局；不能在交接目录直接重跑来发送请求。官方请求已完成的计划不可直接复跑。

[文件清单](publication-manifest.json)记录交接文件 SHA，[构建器检查](validation.json)仅验证数据结构及身份，独立复核另记。原始账号会话、凭据和其他提交者排行没有收录。
''',encoding='utf-8')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build',action='store_true')
    ap.add_argument('--cloud-manifest',type=Path,default=W/'cloud/publication_manifest.json')
    args=ap.parse_args()
    if args.build: build(args.cloud_manifest)
    else: print(json.dumps(readiness(args.cloud_manifest),ensure_ascii=False,indent=2))
