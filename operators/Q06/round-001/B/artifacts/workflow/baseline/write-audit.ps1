$ErrorActionPreference = 'Stop'
$runRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$historyRoot = 'D:\算子比赛\346题\第六题\历史盘点\B'
function Hash-File([string]$path) { return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
$records = @(Get-Content -LiteralPath (Join-Path $historyRoot 'experiments.jsonl') | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json })
$selected = @($records | Where-Object { $_.official_task_id -in @(1362811,1362890,1364006,1367558,1367629,1367774) })
$reused = @()
foreach ($record in $selected) {
    $taskId = $record.official_task_id
    $identityPath = Join-Path $historyRoot "artifacts\official\$taskId-identity.json"
    $identity = Get-Content -LiteralPath $identityPath -Raw | ConvertFrom-Json
    $zipPath = Join-Path $historyRoot "artifacts\official\$taskId.zip"
    if ((Hash-File $zipPath) -ne $identity.package_sha256) { throw 'Historical ZIP hash mismatch' }
    if ($identity.seven_source_sha256 -ne $record.candidate_version.seven_source_sha256) { throw 'Historical seven-source mismatch' }
    $officialPath = Join-Path $historyRoot "artifacts\official\$taskId.json"
    $official = Get-Content -LiteralPath $officialPath -Raw | ConvertFrom-Json
    $rankingPath = Join-Path $historyRoot $record.evaluation_protocol.total_score_provenance
    $ranking = Get-Content -LiteralPath $rankingPath -Raw
    if (-not $ranking.Contains([string]$record.official_metrics.total_score)) { throw 'Ranking score not present' }
    if ($official.status -ne $record.official_status) { throw 'Status mismatch' }
    $reused += [pscustomobject]@{
        experiment_id=$record.experiment_id;round_id='历史盘点';official_task_id=$taskId;official_result_ref=$record.official_result_ref;
        submitted_at=$record.evaluated_at;evaluated_at=$null;observed_at=$official.read_at;official_status=$record.official_status;
        official_metrics=$record.official_metrics;seven_source_sha256=$identity.seven_source_sha256;package_sha256=$identity.package_sha256;
        ranking_binding='Archived ranking submission timestamp and 5 public timings agree with selected official task; latest ranking is not historical source';
        evidence=@(@{path=$officialPath;sha256=(Hash-File $officialPath)},@{path=$identityPath;sha256=(Hash-File $identityPath)},@{path=$rankingPath;sha256=(Hash-File $rankingPath)},@{path=$zipPath;sha256=(Hash-File $zipPath)});
        comparability=[ordered]@{same_problem=$true;same_31_non_editable_template_files=$true;official_valid_observation=$true;stable_performance_gain_proven=$false;full_historical_scoring_protocol=$null;actual_device_and_frequency=$null;formal_four_arm_conclusion='pending current official configuration/rules audit and PL result'};
        notes=@('历史 JSONL evaluated_at 按其原 notes 实为官方提交时间；本轮引用改记 submitted_at，完成时间缺失为 null；不修改固定历史包。','仅为引用，同一任务不计成新实验或额外复测。')
    }
}
[ordered]@{task_id='Q06-R001-B-COMBINE-20261117';historical_records=$reused;reuse_status='Identity/status/score observations verified; formal comparability pending unknown official rule/timing details';no_new_submissions=$true} | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'historical-evidence-audit.json') -Encoding utf8
$commands = @('node','python','python3','npu-smi','msprof','atc','asys') | ForEach-Object { $name=$_; $command=Get-Command $name -ErrorAction SilentlyContinue; [pscustomobject]@{command=$name;path=$command.Source;present=($null -ne $command);usable_for_npu_work=($name -eq 'node')} }
$checks = @(
    @{id='source_identity';status='pass';detail='F/P/L complete 38-file source trees, ZIP and 7-source identities verified; see restoration-identity.json'},
    @{id='template_identity';status='pass';detail='31 non-editable files equal; all 37 files other than main header equal across F/P/L'},
    @{id='historical_results';status='pass';detail='Six archived Pass results/score observations and package identities verified; no new submits'},
    @{id='local_npu_cann';status='fail';detail='npu-smi/msprof/atc/asys unavailable; ASCEND_HOME_PATH/ASCEND_OPP_PATH unset; no local NPU validation claimed'},
    @{id='local_python';status='fail';detail='python/python3 resolve only to WindowsApps placeholders; no Python environment invoked or installed'},
    @{id='official_device';status='pending';detail='Official actual SoC/driver/frequency/counter protocol not available from archived results. build.sh target ascend910b does not identify remote hardware.'},
    @{id='official_rules';status='pending';detail='Full score formula/timing/degradation rule and historical version equivalence require parent current-page audit'},
    @{id='generic_workflow_freeze';status='not_run';detail='Python unavailable and local preflight fails; generic Python workflow scripts not invoked; no fabricated run-manifest or complete gate'},
    @{id='functional_inventory';status='partial';detail='Only public first sample frozen in actual restored tree; hidden 45 cases not accessed; boundary inventory belongs to candidate validation'},
    @{id='knowledge_base';status='warn';detail='kb_unavailable true per parent dispatch; not a blocker'},
    @{id='user_authorized_official_work';status='applicable';detail='User task mandates official evaluation and allows independent preparation; local missing NPU does not prohibit parent official browser path'}
)
[ordered]@{schema_version=1;producer='Manual PowerShell source/env audit (not preflight_dependencies.py)';task_id='Q06-R001-B-COMBINE-20261117';recorded_at=[DateTimeOffset]::Now.ToString('o');request=@{path=(Join-Path $runRoot 'optimization-request.json');sha256=(Hash-File (Join-Path $runRoot 'optimization-request.json'))};local_platform=$PSVersionTable.OS;commands=$commands;environment=@{ASCEND_HOME_PATH=[Environment]::GetEnvironmentVariable('ASCEND_HOME_PATH');ASCEND_OPP_PATH=[Environment]::GetEnvironmentVariable('ASCEND_OPP_PATH')};target_socs=$null;kb_unavailable=$true;checks=$checks;source_restoration_gate='pass';generic_local_execution_gate='fail';official_execution_gate='pending parent audit';frozen_by_workflow_script=$false} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'preflight-report.json') -Encoding utf8
$entryFiles=@('README.md','build.sh','examples/run.sh','examples/test_aclnn_pad_v3_grad.cpp','samples/reference.py','samples/sample.py','samples/case.json','tests/ut/run.sh','tests/ut/CMakeLists.txt','tests/ut/op_kernel/CMakeLists.txt','tests/ut/op_kernel/test_pad_v3_grad.cpp','op_kernel/pad_v3_grad_tiling_data.h')
$entryEvidence=@($entryFiles | ForEach-Object { $path=Join-Path (Join-Path $runRoot 'P') $_; @{file=$_;path=$path;sha256=(Hash-File $path)} })
[ordered]@{task_id='Q06-R001-B-COMBINE-20261117';entry_files=$entryEvidence;build=@{command='source <actual CANN>/set_env.sh; bash build.sh -j4';actual_execution='not run';compile_unit_in_script='ascend910b';remote_hardware_proven=$false};sample=@{command='DEVICE_ID=<confirmed device> bash build.sh -j4 -e';actual_execution='not run';coverage='samples only npu_cases[0]';seed=42;dtype='float32';input_shape=@(1,1,8,8);output_shape=@(1,1,4,4);mode='reflect';paddings_contiguous=$true;rtol=0.0001;atol=0.0001;bad_fraction_limit=0.0001;equal_nan=$true;exact_output_bytes=64};reference=@{implementation='Per-axis padding index map; torch.float64 accumulation via index_select/autograd except constant crop, then cast to original dtype';padding_true='interleaved front/back';padding_false='front half then back half';declared_modes=@('constant','edge','replicate','reflect','symmetric','circular');scope_warning='Source reference accepts these modes; current official legal scope still needs rule audit'};ut=@{command='NLOHMANN_JSON_INCLUDE_DIR=<actual>/include GTEST_SOURCE_DIR=<actual> bash build.sh -j4 -u';actual_execution='not run';readme_claim='Default skip inner numeric assertion; ENABLE_INNER_KERNEL_UT enables';actual_cmake='Unconditional add_subdirectory(op_kernel); run.sh invokes kernel UT and sample verify, without ENABLE_INNER_KERNEL_UT gate in inspected files';stale_fixture='kernel test writes totalNum not present in current PadV3GradTilingData (totalInput/totalOutput); not a valid precision proof';status='static incompatibility, no actual compile failure claimed'}} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'entrypoints-audit.json') -Encoding utf8
Write-Output 'Wrote historical-evidence-audit.json, preflight-report.json, entrypoints-audit.json; no build or submissions executed.'
