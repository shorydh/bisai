$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$roundRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
function ReadJson([string]$relative) { Get-Content -LiteralPath (Join-Path $roundRoot $relative) -Raw | ConvertFrom-Json }
function HashFile([string]$file) { (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() }
$candidate = ReadJson 'artifacts/workflow/implementation/candidate-identity.json'
$scope = ReadJson 'artifacts/workflow/analysis/round1/source-isolation-PL.json'
$restore = ReadJson 'artifacts/workflow/baseline/restoration-identity.json'
$hunks = ReadJson 'artifacts/workflow/implementation/transplant-hunks.json'
$official = ReadJson 'artifacts/official/1369663.json'
$officialIdentity = ReadJson 'artifacts/official/1369663-identity.json'
$planner = ReadJson 'artifacts/workflow/implementation/planner-result.json'
$plFiles = @(Get-ChildItem -LiteralPath (Join-Path $roundRoot 'PL') -Recurse -File)
$sourceChecks = @($candidate.files | ForEach-Object {
    $actual = HashFile (Join-Path "$roundRoot/PL" $_.file)
    [pscustomobject]@{file=$_.file;sha256=$actual;match=($actual -eq $_.sha256)}
})
$parentChecks = @($scope.baseline_files.PSObject.Properties | ForEach-Object {
    $actual = HashFile (Join-Path "$roundRoot/P" $_.Name)
    [pscustomobject]@{file=$_.Name;match=($actual -eq $_.Value)}
})
$changed = @($candidate.files | Where-Object {
    (HashFile (Join-Path "$roundRoot/P" $_.file)) -ne $_.sha256
} | ForEach-Object {$_.file})
$plHeader = [IO.File]::ReadAllText((Join-Path $roundRoot 'PL/op_kernel/pad_v3_grad.h'))
$pHeader = [IO.File]::ReadAllText((Join-Path $roundRoot 'P/op_kernel/pad_v3_grad.h'))
$exactHunks = ($plHeader.Split([string[]]@($hunks.inserted),[StringSplitOptions]::None).Count -eq 2) -and
              ($plHeader.Split([string[]]@($hunks.newPlan),[StringSplitOptions]::None).Count -eq 2) -and
              ($plHeader.Replace($hunks.inserted,'').Replace($hunks.newPlan,$hunks.oldPlan) -ceq $pHeader)
$controls = @($restore.arms | ForEach-Object {
    $arm = $_
    $mismatches = @($arm.files | Where-Object { (HashFile (Join-Path "$roundRoot/$($arm.arm)" $_.file)) -ne $_.sha256 })
    [pscustomobject]@{arm=$arm.arm;file_count=$arm.files.Count;all_files_unchanged=($mismatches.Count -eq 0);seven_source_sha256=$arm.seven_source_sha256}
})
$zipPath = Join-Path $roundRoot 'artifacts/official/1369663.zip'
$zip = [IO.Compression.ZipFile]::OpenRead($zipPath)
try {
    $zipChecks = @($candidate.files | ForEach-Object {
        $entry = $zip.GetEntry('code/'+$_.file)
        $actual = $null
        if ($entry) {
            $stream=$entry.Open(); $hasher=[Security.Cryptography.SHA256]::Create()
            try {$actual=[Convert]::ToHexString($hasher.ComputeHash($stream)).ToLowerInvariant()} finally {$stream.Dispose();$hasher.Dispose()}
        }
        [pscustomobject]@{file=$_.file;sha256=$actual;match=($actual -eq $_.sha256)}
    })
    $zipFileCount = @($zip.Entries | Where-Object {$_.Length -gt 0 -and $_.FullName.StartsWith('code/')}).Count
} finally {$zip.Dispose()}
$zipHash=HashFile $zipPath
$allSource = $plFiles.Count -eq 38 -and @($sourceChecks | Where-Object {-not $_.match}).Count -eq 0
$allParent = $parentChecks.Count -eq 38 -and @($parentChecks | Where-Object {-not $_.match}).Count -eq 0
$allControls = @($controls | Where-Object {-not $_.all_files_unchanged}).Count -eq 0
$allZip = $zipFileCount -eq 38 -and @($zipChecks | Where-Object {-not $_.match}).Count -eq 0 -and $zipHash -eq $officialIdentity.package_sha256
$rankText = Get-Content -LiteralPath (Join-Path $roundRoot 'artifacts/official/1369663-ranking.txt') -Raw
$rankBound = $rankText.Contains("三溯`tshorydh`tPass`t29.20`t2026/11/17 01:19:03")
$result = [ordered]@{
    task_id='Q06-R001-B-COMBINE-20261117'; audit_kind='independent_readonly_delivery_audit';
    observed_at=[DateTimeOffset]::Now.ToString('o');
    source_scope_decision=if($allSource -and $allParent -and $allControls -and $exactHunks -and $changed.Count -eq 1 -and $changed[0] -eq 'op_kernel/pad_v3_grad.h') {'pass'} else {'fail'};
    source_seven_sha256=$candidate.seven_source_sha256; source_file_count=$plFiles.Count; changed_files=$changed;
    exact_two_hunks_reverse_to_P=$exactHunks; PL_identity_unchanged=$allSource; P_frozen_scope_unchanged=$allParent; controls=$controls;
    downloaded_official_engineering=[ordered]@{id=1369663;package_sha256=$zipHash;all_38_match_frozen_PL=$allZip;files=$zipChecks};
    official_result=[ordered]@{id=$official.id;status=$official.status;score=$official.score;submitted_at=$official.submitted_at;evaluated_at=$official.evaluated_at;ranking_time_and_score_bound=$rankBound};
    auxiliary_diagnostic=[ordered]@{status=$planner.status;device_execution=$planner.device_execution;cases=$planner.cases;ranges=$planner.ranges;scope=$planner.checker_scope};
    actual_last_official_version='PL / 1369663 / Pass / 29.20';
    recommendation='Retain local P/r6 source; PL benefit not established; do not resubmit historical P merely to restore leaderboard';
    formal_performance_comparison='pending'; generic_integration_stage='pending_not_performed';
    full_inventory_no_regression='not_proven'; actual_target_soc=$null; actual_stack_spill=$null;
    original_writeback_performed=$false; historical_resubmission_performed=$false;
    limitations=@('Exact official source and Pass are verified, not a whole-input proof','Official hardware, exact timing/scoring and regression requirements remain unknown','Single new PL score below both archived P scores is descriptive, not a statistical performance verdict','CPU planning and pairwise arithmetic checks do not execute AscendC device kernels','No original-tree integration or generic full-inventory gates are claimed');
    source_files=$sourceChecks
}
$result | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'delivery-audit.json') -Encoding utf8
if ($result.source_scope_decision -ne 'pass' -or -not $allZip -or -not $rankBound -or $official.status -ne 'Pass') { throw 'Delivery audit failed; see delivery-audit.json' }
[pscustomobject]@{source_scope=$result.source_scope_decision;file_count=$plFiles.Count;downloaded_all38_match=$allZip;ranking_bound=$rankBound;official_status=$official.status;official_score=$official.score;formal_comparison='pending'} | ConvertTo-Json
