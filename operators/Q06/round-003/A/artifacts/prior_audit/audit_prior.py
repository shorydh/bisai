"""Read fixed prior evidence and current remote refs without evaluating kernels."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
REPO = OUT.parent / 'repo'
A = 'facfb39ece01643fa7f9452d09971f9ca4d2b246'
C = '622d7f0064073dff249c23424330466ce510e3e2'
AP = 'operators/Q06/round-002/A/'
CP = 'operators/Q06/round-002/C/'
sources = {}

def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO)

def raw(commit, path):
    data = git('show', f'{commit}:{path}')
    sources[commit + ':' + path] = {
        'commit': commit, 'path': path, 'sha256': hashlib.sha256(data).hexdigest(),
        'url': f'https://github.com/shorydh/bisai/blob/{commit}/{path}'}
    return data

def doc(commit, path):
    return json.loads(raw(commit, path).decode('utf-8-sig'))

def jsonl(commit, path):
    return [json.loads(line) for line in raw(commit, path).decode('utf-8-sig').splitlines() if line.strip()]

head_before = git('rev-parse', 'HEAD').decode().strip()
refs_at = datetime.now(timezone.utc).isoformat()
refs_text = git('ls-remote', '--heads', 'origin').decode()
refs = [{'commit': s.split()[0], 'ref': s.split()[1]} for s in refs_text.splitlines()]
(OUT / 'remote-heads.txt').write_text(refs_text, encoding='utf-8')

raw(A, AP + 'summary.md')
raw(A, AP + 'artifacts/rules/report.md')
doc(A, AP + 'artifacts/rules/evidence.json')
bounded = doc(A, AP + 'artifacts/audit/bounded_comparison.json')
experiments = jsonl(A, AP + 'experiments.jsonl')
arms = []
configs = []
for e in experiments:
    assert len(e) == 21
    sid = e['official_task_id']
    off = doc(A, AP + e['official_result_ref'])
    manifest = doc(A, AP + e['candidate_version']['manifest'])
    before = doc(A, AP + e['evaluation_protocol']['problem_configuration_before_ref'])
    after = doc(A, AP + e['evaluation_protocol']['problem_configuration_after_ref'])
    before = {k: v for k, v in before.items() if not k.startswith('_publication')}
    after = {k: v for k, v in after.items() if not k.startswith('_publication')}
    assert before == after
    configs.append(before)
    assert off['_id'] == sid and off['status'] == e['official_status'] == 'Pass'
    assert off['valid'] is True and off['judge_revision'] == 0
    assert off['public_only'] is False and off['judge_missing_cases'] is False
    assert off['total_testcase_count'] == 50
    assert off['result'] == e['official_metrics']['result']
    assert manifest['submission_id'] == sid and len(manifest['files']) == 38
    assert len([f for f in manifest['files'] if f['editable']]) == 7
    assert manifest['editable_text_tree_sha256'] == e['candidate_version']['editable_text_tree_sha256']
    observations = []
    for observation in e['official_metrics']['ranking_observations']:
        rank = doc(A, AP + observation['ref'])
        assert rank['row']['submission_id'] == sid
        assert rank['row']['submission']['ID'] == off['ID']
        assert rank['row']['score'] == observation['score'] == e['official_metrics']['total_score']
        signature = [(t['id'], t['type'], t['tbest']) for t in rank['public_scoring_scale']['testcases']]
        visible = [(t['testcase_id'], t['type'], t['best_time']) for t in off['result'] if t['testcase_status'] != 'Hidden']
        assert signature == visible
        assert rank['source_response_sha256'] == rank['public_scoring_scale']['source_response_sha256']
        observations.append({'ref': observation['ref'], 'observed_at': observation['observed_at'],
                             'score': observation['score'], 'public_signature': signature})
    arms.append({
        'experiment_id': e['experiment_id'], 'arm': e['notes']['arm'],
        'official_numeric_id': off['ID'], 'submission_id': sid,
        'seven_source_sha256': manifest['editable_text_tree_sha256'],
        'official_status': off['status'], 'valid': off['valid'],
        'judge_revision': off['judge_revision'], 'official_result_ref': AP + e['official_result_ref'],
        'submitted_at': off['create_time'], 'evaluated_at': e['evaluated_at'],
        'terminal_observed_at': e['evaluation_protocol']['official_result_observed_at'],
        'ranking_observations': observations,
        'reuse_scope': 'Archived valid official result and same-observation total score; not a new run or current ranking claim.'})
assert all(c == configs[0] for c in configs)
assert all(all(p['checks'].values()) for p in bounded['pairs'])

raw(C, CP + 'summary.md')
ce = jsonl(C, CP + 'experiments.jsonl')
manifest = doc(C, CP + 'artifacts/device-case/edge-legal-cancellation/manifest.json')
probe = doc(C, CP + 'artifacts/logs/R002-device-access-probe.json')
clean = doc(C, CP + 'artifacts/results/R002-E001-reference-clean.json')
trace = doc(C, CP + 'artifacts/results/R002-E002-source-branch-trace.json')
legality = doc(C, CP + 'artifacts/rules/legality.json')
assert manifest['device_execution'] is False and probe['device_execution'] is False
assert len(manifest['variants']) == 4
assert all(v['golden_y'] == [0.0, 0.0, 0.0] for v in manifest['variants'])
assert all(e['official_task_id'] is None for e in ce)
c_tree = git('ls-tree', '-r', '--name-only', C, '--', CP).decode().splitlines()
c_log = git('log', '--all', '--format=%H %cs %s', '--', CP).decode().splitlines()

audit = {
    'task_id': 'Q06-R003-A-LAZY-OFFICIAL', 'checked_at': datetime.now(timezone.utc).isoformat(),
    'mode': 'Read-only fixed Git evidence and remote-ref discovery; no official GET/POST, no new experiment, no kernel/device execution.',
    'round_002_A': {
        'commit': A, 'all_four_records_consistent': True, 'all_21_fields': True,
        'same_archived_public_configuration': configs[0], 'records': arms,
        'prior_bounded_pairs': bounded['pairs'], 'stable_best': None,
        'reuse_policy': 'Reuse all four as historical accepted evidence; no F/L reevaluation. Prior P/PL score values retain their original observation times and scale.',
    },
    'C_latest_published': {
        'observed_remote_refs_at': refs_at, 'remote_heads_ref': 'remote-heads.txt',
        'heads': refs, 'latest_known_C_round_002_commit': C,
        'C_path_history_in_fetched_refs': c_log,
        'C_round_002_file_count': len(c_tree),
        'device_execution': False, 'actual_npu_output': None,
        'reference': {'sha256': clean['source']['reference_sha256'],
                      'dependency_versions': {k: v['version'] for k, v in clean['dependencies'].items()}},
        'legal_case': {'x_shape': [1,1,1,5], 'x_fp32': [1.7e38,1,-1.7e38,0,0],
                       'mode': 'edge', 'last_axis_padding': [2,0], 'output_shape': [1,1,1,3],
                       'variants': manifest['variants'],
                       'frozen_r6_seven_source_sha256': manifest['source']['r6_seven_source_sha256']},
        'interpretation': 'C true-dependency reference and four-variant package are published. CPU source model returns 1 at output 0; this is NOT an NPU result. Old reflect candidate is outside current formal legal matrix. No later published C branch or NPU verdict is visible in discovered refs.',
        'baseline_qualification': 'Pending actual NPU output plus call/branch evidence for the frozen r6/P on the same legal input; central decides. Cannot promote CPU evidence or archived official Pass to this case verdict.',
        'limitation': 'Only published refs observed at this time; unpublished work is unknown.',
    },
    'round_003_required_comparison_conditions': [
        'Root operator audit must query 1379766 / 6afc1e5b6bd0f9be374a4c6d for actual source, terminal status, native valid/revision/public_only, configuration and exact-submission ranking; this subtask did not query it.',
        'PL-lazy is frozen at seven-source SHA 03e6bc1bb81dc40ba71d4691aeb08feebdf38fe0a2ac12f2a59aeff0445afb39; compare against direct parent PL 988e491ec2d8d758adac5caa0e304cc81cb500ade732aadc9427fa1254267d41 with the same 31-file template.',
        'A score must bind exact submission_id and observation time; save same-response public case IDs and unrounded TBest. Current details cannot backfill fields for B old UI score 29.64 or yesterday archived ranking.',
        'Reuse existing PL or P only to the extent actual observation/protocol/scale allows. If gaps affect the PL-lazy vs PL decision, evaluate only frozen PL-lazy and necessary PL control; P only if claiming superiority to P and no adequate reusable control.',
        'Do not reevaluate F/L or exp5/u64. Do not create experiments merely to meet an arbitrary run count.',
        'Record bounded observed official score differences only; stability pending if evidence insufficient or observations disagree. Do not require hidden server details or infer hidden timings/speedup from scores.',
        'Cloud build, sample/precision, performance and profiling are separate evidence with actual execution reasons. None replaces official comparison. Common-baseline numerical eligibility is separate from score comparison.',
    ],
    'source_hash_manifest': 'source-manifest.json',
    'branch_head_unchanged': git('rev-parse','HEAD').decode().strip() == head_before,
}
(OUT / 'source-manifest.json').write_text(json.dumps(list(sources.values()), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(OUT / 'reuse-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'all_four_consistent': True, 'C_device_execution': False,
                  'C_latest': C, 'sources': len(sources), 'branch_head_unchanged': audit['branch_head_unchanged']}))
