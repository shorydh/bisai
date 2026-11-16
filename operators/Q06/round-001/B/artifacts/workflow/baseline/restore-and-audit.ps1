$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$runRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$historyRoot = 'D:\算子比赛\346题\第六题\历史盘点\B'
$sha = [Security.Cryptography.SHA256]::Create()
function Hash-Bytes([byte[]]$bytes) {
    return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
}
function Hash-File([string]$path) { return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
$armSpecs = @(@{arm='F';id=1367558}, @{arm='P';id=1367774}, @{arm='L';id=1362890})
$arms = @()
foreach ($spec in $armSpecs) {
    $archivePath = Join-Path $historyRoot "artifacts\official\$($spec.id).zip"
    $identityPath = Join-Path $historyRoot "artifacts\official\$($spec.id)-identity.json"
    $identity = Get-Content -LiteralPath $identityPath -Raw | ConvertFrom-Json
    $zipHash = Hash-File $archivePath
    if ($zipHash -ne $identity.package_sha256) { throw "ZIP identity mismatch $($spec.id)" }
    $armRoot = [IO.Path]::GetFullPath((Join-Path $runRoot $spec.arm))
    New-Item -ItemType Directory -Path $armRoot -Force | Out-Null
    $zip = [IO.Compression.ZipFile]::OpenRead($archivePath)
    $files = @()
    try {
        foreach ($entry in $zip.Entries) {
            if (-not $entry.FullName.StartsWith('code/') -or $entry.FullName.EndsWith('/')) { continue }
            $relative = $entry.FullName.Substring(5)
            $destination = [IO.Path]::GetFullPath((Join-Path $armRoot $relative))
            if (-not $destination.StartsWith($armRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe ZIP path' }
            $stream = $entry.Open()
            $memory = [IO.MemoryStream]::new()
            try { $stream.CopyTo($memory); $bytes = $memory.ToArray() } finally { $stream.Dispose(); $memory.Dispose() }
            $expectedHash = Hash-Bytes $bytes
            if (Test-Path -LiteralPath $destination) {
                if ((Hash-File $destination) -ne $expectedHash) { throw "Existing arm file differs; not overwritten: $destination" }
            } else {
                New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($destination)) -Force | Out-Null
                [IO.File]::WriteAllBytes($destination, $bytes)
            }
            $actualHash = Hash-File $destination
            if ($actualHash -ne $expectedHash) { throw "Restored bytes mismatch: $destination" }
            $files += [pscustomobject]@{file=$relative;sha256=$actualHash;bytes=$bytes.Length;zip_entry_sha256=$expectedHash;match=$true}
        }
    } finally { $zip.Dispose() }
    if ($files.Count -ne 38) { throw "Unexpected file count for $($spec.arm): $($files.Count)" }
    $digestText = ''
    foreach ($source in $identity.seven_source_files) {
        $actualHash = Hash-File (Join-Path $armRoot $source.file)
        if ($actualHash -ne $source.sha256) { throw "Seven-source mismatch: $($source.file)" }
        $digestText += $source.file + [char]0 + $actualHash + "`n"
    }
    $sevenHash = Hash-Bytes ([Text.Encoding]::UTF8.GetBytes($digestText))
    if ($sevenHash -ne $identity.seven_source_sha256) { throw "Seven-source combined hash mismatch: $($spec.arm)" }
    $allFilesText = ($files | Sort-Object file | ForEach-Object { $_.file + [char]0 + $_.sha256 + "`n" }) -join ''
    $arms += [pscustomobject]@{arm=$spec.arm;official_task_id=$spec.id;official_zip=$archivePath;package_sha256=$zipHash;identity=$identityPath;root=$armRoot;file_count=$files.Count;seven_source_sha256=$sevenHash;all_38_file_sha256=(Hash-Bytes ([Text.Encoding]::UTF8.GetBytes($allFilesText)));files=$files}
}
$sevenPaths = @((Get-Content -LiteralPath (Join-Path $historyRoot 'artifacts\official\1367774-identity.json') -Raw | ConvertFrom-Json).seven_source_files.file)
$comparisons = @()
foreach ($arm in @($arms | Where-Object { $_.arm -ne 'P' })) {
    $p = $arms | Where-Object { $_.arm -eq 'P' }
    $different = @($arm.files | Where-Object { $f=$_; ($p.files | Where-Object { $_.file -eq $f.file }).sha256 -ne $f.sha256 } | ForEach-Object { $_.file })
    $templateDifferences = @($different | Where-Object { $_ -notin $sevenPaths })
    if ($templateDifferences.Count) { throw 'Non-editable template difference' }
    $comparisons += [pscustomobject]@{left=$arm.arm;right='P';changed_files=$different;non_editable_files=31;non_editable_files_equal=$true}
}
$result = [ordered]@{schema_version=1;task_id='Q06-R001-B-COMBINE-20261117';recorded_at=[DateTimeOffset]::Now.ToString('o');source_commit='8e245dab91700555bd619e95c70fa780305b1b37';remote_commit_verification='parent-owned pending';digest_algorithm='SHA256(concatenate ordered relative file path + NUL + hex SHA256 + LF); seven sources ordered as identity JSON; all 38 files sorted by path';arms=$arms;comparisons=$comparisons;all_checks_passed=$true}
$result | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'restoration-identity.json') -Encoding utf8
$arms | Select-Object arm,official_task_id,file_count,seven_source_sha256,all_38_file_sha256 | ConvertTo-Json -Depth 3
