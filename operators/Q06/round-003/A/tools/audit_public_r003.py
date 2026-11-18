"""Independent local raw-to-public audit. Never imports builder or calls network."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
PACKAGE = WORK/'repo/operators/Q06/round-003/A'
RAW = WORK/'raw_official/runs'
FIELDS = 'experiment_id operator round_id agent_id task_id base_version candidate_version hypothesis change official_task_id official_result_ref evaluated_at evaluation_protocol official_status official_metrics baseline_official_result_ref comparison finding_status applicability artifacts notes'.split()
OFFICIAL = '_id ID problem_id create_time status valid judge_revision public_only judge_missing_cases theory_score total_testcase_count result'.split()
RANK = 'rank submission_id status create_time score result'.split()
CONFIG = '_id name title version_no version_label code_template cann_version judge_revision score_mode use_baseline iterations ranking_submission_mode ranking_testcase_count judge_baseline_verified difficulty'.split()
EXPECTED = [
    ('Q06-R003-A-E001','PL','988e491ec2d8d758adac5caa0e304cc81cb500ade732aadc9427fa1254267d41'),
    ('Q06-R003-A-E002','PL-lazy','03e6bc1bb81dc40ba71d4691aeb08feebdf38fe0a2ac12f2a59aeff0445afb39')]
PID='6ad9ab403ff2fef7e80e2a1d'

def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(b): return hashlib.sha256(b).hexdigest()
def hashfile(p): return sha(p.read_bytes())
def tree(fs): return sha(''.join(k+'\0'+sha(fs[k])+'\n' for k in sorted(fs)).encode('utf-8'))
def project(obj, keys): return {k:obj[k] for k in keys if k in obj}
def pkg(ref):
    p=(PACKAGE/ref).resolve()
    assert p.is_relative_to(PACKAGE.resolve()), 'Reference escapes package: '+ref
    assert p.exists(), 'Missing package reference: '+ref
    return p
def visible(o): return sorted((r['testcase_id'],r.get('type'),r.get('best_time')) for r in o['result'] if r.get('testcase_status')!='Hidden')
def rankscale(rows): return sorted((r['_id'],r.get('type'),r.get('tbest')) for r in rows)
def provenance(published,raw):
    assert published['_publication']['source_file_sha256']==hashfile(raw), 'Bad publication source digest'
    assert published['_publication']['machine_A_raw_file']==raw.relative_to(WORK).as_posix()

def check_arm(e, expected):
    label,arm,expected_hash=expected
    assert list(e)==FIELDS, '21 fields/order mismatch'
    assert (e['experiment_id'],e['operator'],e['round_id'],e['agent_id'],e['task_id'])==(label,'PadV3Grad','round-003','A','Q06-R003-A-LAZY-OFFICIAL')
    d=RAW/label
    receipt=read(d/'receipt.json'); terminal=read(d/'official_terminal.json'); frozen=read(d/'frozen_manifest.json'); check=read(d/'latest_check.json')
    sid=receipt['submission_id']
    assert terminal['_id']==check['_id']==e['official_task_id']==sid
    assert terminal['problem_id']==PID
    assert receipt['version']==arm and receipt['source_tree_sha256']==frozen['source_tree_sha256']==expected_hash
    assert check['all_38_match'] is True and check['source_tree_sha256']==expected_hash
    official_pub=read(pkg(e['official_result_ref']))
    assert {k:v for k,v in official_pub.items() if k!='_publication'}==project(terminal,OFFICIAL)
    provenance(official_pub,d/'official_terminal.json')
    assert e['official_status']==terminal['status']
    assert e['evaluated_at'] is None
    protocol=e['evaluation_protocol']
    assert protocol['evaluation_completion_timestamp'] is None
    for field,expected_value in [('problem_id',PID),('official_numeric_id',terminal['ID']),('submitted_at',terminal['create_time']),('request_started_at',receipt['request_started_at']),('receipt_observed_at',receipt['response_observed_at']),('terminal_observed_at',check['observed_at']),('judge_revision',terminal['judge_revision']),('public_only',terminal['public_only'])]:
        assert protocol[field]==expected_value, 'Protocol mismatch: '+field
    for field in ('theory_score','total_testcase_count','judge_missing_cases','result'):
        assert e['official_metrics'][field]==terminal[field], 'Metric changed: '+field
    cv=e['candidate_version']; manifest=read(pkg(cv['manifest']))
    assert cv['source_tree_sha256']==expected_hash and cv['files_count']==38 and cv['official_task_id']==sid
    assert manifest['source_tree_sha256']==expected_hash and manifest['submission_id']==sid
    assert manifest['files']==frozen['files'] and len(manifest['files'])==38
    assert manifest.get('official_zip_sha256') is None
    fdict={f['path']:f for f in frozen['files']}; returned={f['path']:f['content'].encode('utf-8') for f in terminal['files']}
    assert len(fdict)==len(returned)==38 and set(fdict)==set(returned)
    editable={k for k,v in fdict.items() if v['editable']}; assert len(editable)==7
    assert tree({k:returned[k] for k in editable})==expected_hash
    source_dir=pkg(cv['snapshot']); source_paths={p.relative_to(source_dir).as_posix() for p in source_dir.rglob('*') if p.is_file()}
    assert source_paths==set(fdict)
    for path,f in fdict.items():
        blob=(source_dir/path).read_bytes()
        assert blob==returned[path]==(WORK/arm/path).read_bytes()
        assert sha(blob)==f['sha256']
    request=read(d/'request_files.json')
    assert {f['path'] for f in request}==editable and len(request)==7
    assert all(f['content'].encode('utf-8')==returned[f['path']] for f in request)
    assert read(d/'attempt.json')['request_files_sha256']==hashfile(d/'request_files.json')
    for name in ('attempt.json','receipt.json','frozen_manifest.json','request_files.json','latest_check.json'):
        assert pkg('artifacts/submissions/'+label+'/'+name).read_bytes()==(d/name).read_bytes()
    template=read(d/'template_before.json'); template=template.get('data',template)['files']
    tdict={f['path']:f for f in template}; assert set(tdict)==set(fdict)
    assert {k for k,v in tdict.items() if v.get('editable')}==editable
    readonly={k:sha(returned[k]) for k in fdict if k not in editable}
    assert len(readonly)==31
    assert all(returned[k]==tdict[k]['content'].encode('utf-8') for k in readonly)
    configs=[]
    for phase in ('before','after'):
        raw=d/('problem_'+phase+'.json'); value=read(raw)
        pub=read(pkg(protocol['problem_configuration_'+phase+'_ref']))
        assert {k:v for k,v in pub.items() if k!='_publication'}=={k:value.get(k) for k in CONFIG}
        provenance(pub,raw); configs.append({k:value.get(k) for k in CONFIG})
    observations=sorted(p for p in (d/'observations').glob('*.json') if not p.name.endswith('.meta.json'))
    pubobs=read(pkg('artifacts/submissions/'+label+'/observation_log.json'))
    assert len(pubobs)==len(observations)>0, 'Lost official observations'
    for raw,pub in zip(observations,pubobs):
        o=read(raw); meta=read(raw.with_suffix('.meta.json'))
        assert pub['official_result_projection']==project(o,OFFICIAL)
        assert pub['response_metadata']==meta
        assert meta['raw_response_sha256']==hashfile(raw)
        provenance(pub,raw)
    terminal_raw=d/check['official_ref']
    assert read(terminal_raw)==terminal
    assert read(terminal_raw.with_suffix('.meta.json'))['observed_at']==check['observed_at']
    ranks=sorted((d/'ranking_exact').glob('*.json'))
    pubranks=e['official_metrics']['ranking_observations']
    assert len(ranks)==len(pubranks)>0, 'Lost exact ranking observations'
    rank_values=[]
    for raw,pubref in zip(ranks,pubranks):
        r=read(raw); response_file=WORK/r['source_response']; response=read(response_file)
        assert hashfile(response_file)==r['source_response_sha256']
        response_meta=read(response_file.with_suffix('.meta.json'))
        assert response_meta['raw_response_sha256']==hashfile(response_file)
        assert response_meta['observed_at']==r['observed_at']
        matches=[row for row in response['rows'] if row.get('submission_id')==sid]
        assert len(matches)==1 and matches[0]==r['row'] and r['official_task_id']==sid
        row=project(r['row'],RANK)
        if isinstance(r['row'].get('submission'),dict): row['submission']=project(r['row']['submission'],['_id','ID','status','create_time'])
        p=read(pkg(pubref['ref'])); assert p['row']==row
        assert p['official_task_id']==sid and pubref['observed_at']==p['observed_at']==r['observed_at']
        assert p['source_response_sha256']==r['source_response_sha256']
        assert pubref['score']==row['score']
        provenance(p,raw)
        public_ids={x[0] for x in visible(terminal)}
        expected_public=[project(case,['_id','id','ID','baseline','tbest','type']) for case in response['testcases'] if case['_id'] in public_ids]
        assert p['public_scoring_scale']==expected_public
        assert rankscale(expected_public)==visible(terminal)
        rank_values.append({'score':row['score'],'public_scale':rankscale(expected_public),'observed_at':r['observed_at']})
    assert e['official_metrics']['total_score']==rank_values[0]['score']
    scans=sorted((d/'ranking_scans').glob('*.json'))
    pub_scans=list(pkg('artifacts/submissions/'+label+'/ranking_scans').glob('*.json'))
    assert {p.name for p in scans}=={p.name for p in pub_scans}
    for p in scans: assert p.read_bytes()==pkg('artifacts/submissions/'+label+'/ranking_scans/'+p.name).read_bytes()
    for ref in e['artifacts']: pkg(ref)
    assert e['comparison']['stable_gain'] is None and e['comparison']['operator_speedup'] is None
    assert e['comparison']['team_baseline_qualification']=='pending'
    return {'experiment_id':label,'arm':arm,'submission_id':sid,'official_numeric_id':terminal['ID'],
            'official':terminal,'configs':configs,'readonly':readonly,'ranks':rank_values,
            'report':{'source_files_verified':38,'editable_verified':7,'official_observations_retained':len(observations),
                      'exact_ranking_observations_retained':len(ranks),'ranking_scans_retained':len(scans),
                      'score':rank_values[0]['score'],'public_only':terminal['public_only'],
                      'judge_revision':terminal['judge_revision'],'valid':terminal['valid'],'evaluated_at':None}}

def main():
    report={'task_id':'Q06-R003-A-LAZY-OFFICIAL','checked_at':datetime.now(timezone.utc).isoformat(),
            'status':'pending','errors':[],'missing':[],'scope':'Independent local source-to-public consistency audit only; no new official evaluation or network requests.'}
    required=[PACKAGE/'summary.md',PACKAGE/'experiments.jsonl',PACKAGE/'publication-manifest.json']
    for label,_,_ in EXPECTED:
        required += [RAW/label/name for name in ('receipt.json','official_terminal.json','frozen_manifest.json','latest_check.json','problem_before.json','problem_after.json')]
    report['missing']=[str(p) for p in required if not p.exists()]
    if not report['missing']:
        try:
            records=[json.loads(line) for line in (PACKAGE/'experiments.jsonl').read_text(encoding='utf-8-sig').splitlines() if line.strip()]
            assert len(records)==2
            arms=[check_arm(e,spec) for e,spec in zip(records,EXPECTED)]
            base=arms[0]
            for arm,e in zip(arms,records):
                o,b=arm['official'],base['official']
                assert o['status']==b['status']=='Pass' and o['valid'] is b['valid'] is True
                assert o['public_only'] is b['public_only'] is False
                assert o['judge_revision']==b['judge_revision']==0
                assert o['total_testcase_count']==b['total_testcase_count']==50
                assert o['judge_missing_cases'] is b['judge_missing_cases'] is False
                assert all(c==base['configs'][0] for c in arm['configs'])
                assert arm['readonly']==base['readonly']
                assert visible(o)==visible(b)
                assert all(r['testcase_status']=='Pass' for r in o['result'] if r['testcase_status']!='Hidden')
                assert arm['ranks'][0]['public_scale']==base['ranks'][0]['public_scale']
                difference=Decimal(str(arm['ranks'][0]['score']))-Decimal(str(base['ranks'][0]['score']))
                comparison=e['comparison']
                assert comparison['baseline_official_task_id']==base['submission_id']
                assert comparison['candidate_score_raw']==arm['ranks'][0]['score']
                assert comparison['baseline_score_raw']==base['ranks'][0]['score']
                assert Decimal(str(comparison['observed_total_score_delta']))==difference
                assert comparison['comparison_status']==e['finding_status']=='verified'
                assert all(comparison['checks'].values())
                assert e['base_version']==records[0]['candidate_version']
                assert e['baseline_official_result_ref']==records[0]['official_result_ref']
                arm['report']['exact_decimal_score_delta']=str(difference)
            published_compare=read(pkg('artifacts/audit/bounded_comparison.json'))
            assert published_compare['PL_lazy_vs_PL']==records[1]['comparison']
            assert published_compare['stable_best'] is None
            listed=read(PACKAGE/'publication-manifest.json')['files']; listed_names={r['path'] for r in listed}
            actual={p.relative_to(PACKAGE).as_posix() for p in PACKAGE.rglob('*') if p.is_file() and p.name not in ('publication-manifest.json','validation.json')}
            assert len(listed_names)==len(listed) and listed_names==actual
            for row in listed:
                p=pkg(row['path']); assert p.stat().st_size==row['bytes'] and hashfile(p)==row['sha256']
            links=0
            for name in ('summary.md','README.md'):
                for href in re.findall(r'\[[^\]]*\]\(([^)]+)\)',(PACKAGE/name).read_text(encoding='utf-8')):
                    if href.startswith(('https://','http://','#')): continue
                    pkg(href.split('#',1)[0]); links+=1
            report.update(status='passed',records=[{'experiment_id':a['experiment_id'],'arm':a['arm'],'submission_id':a['submission_id'],'official_numeric_id':a['official_numeric_id'],**a['report']} for a in arms],
                          checked_publication_files=len(listed),checked_top_level_links=links,
                          jsonl_sha256=hashfile(PACKAGE/'experiments.jsonl'),builder_sha256=hashfile(WORK/'build_handoff_r003.py'),
                          stable_gain=None,common_baseline_approved=False)
        except Exception as exc:
            report['status']='failed'; report['errors'].append({'type':type(exc).__name__,'message':str(exc)})
            import traceback
            report['failure_traceback']=traceback.format_exc()
    (HERE/'raw_to_public_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','errors','missing')},ensure_ascii=False))
    return 0 if report['status']=='passed' else (2 if report['status']=='pending' else 1)

if __name__=='__main__': raise SystemExit(main())
