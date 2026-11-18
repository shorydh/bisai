param(
    [Parameter(Mandatory = $true)]
    [string]$ZipPath,
    [Parameter(Mandatory = $true)]
    [string]$IdentityPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'

$zip = (Resolve-Path -LiteralPath $ZipPath).Path
$identityFile = (Resolve-Path -LiteralPath $IdentityPath).Path
$identity = Get-Content -Raw -LiteralPath $identityFile | ConvertFrom-Json
$packageHash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($packageHash -ne $identity.package_sha256) {
    throw "Package hash mismatch: $packageHash != $($identity.package_sha256)"
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("q06-source-check-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot | Out-Null
try {
    Expand-Archive -LiteralPath $zip -DestinationPath $tempRoot
    $codeRoot = Join-Path $tempRoot 'code'
    $allFiles = Get-ChildItem -LiteralPath $codeRoot -Recurse -File |
        ForEach-Object {
            [pscustomobject]@{
                file = $_.FullName.Substring($codeRoot.Length + 1).Replace('\', '/')
                bytes = $_.Length
                sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            }
        } |
        Sort-Object file

    $seven = @(
        'op_host/pad_v3_grad_def.cpp',
        'op_host/pad_v3_grad_infershape.cpp',
        'op_host/pad_v3_grad_tiling.cpp',
        'op_kernel/pad_v3_grad.cpp',
        'op_kernel/pad_v3_grad.h',
        'op_kernel/pad_v3_grad_tiling_data.h',
        'op_kernel/pad_v3_grad_tiling_key.h'
    )
    $sevenRows = foreach ($file in $seven) {
        $row = $allFiles | Where-Object { $_.file -eq $file }
        if ($null -eq $row) { throw "Seven-source file missing: $file" }
        [pscustomobject]@{ file = $file; sha256 = $row.sha256 }
    }
    $sevenPayload = ($sevenRows | ForEach-Object { "$($_.file)`0$($_.sha256)`n" }) -join ''
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        $sevenTreeHash = ([BitConverter]::ToString(
            $hasher.ComputeHash($utf8NoBom.GetBytes($sevenPayload))
        )).Replace('-', '').ToLowerInvariant()
    } finally {
        $hasher.Dispose()
    }
    if ($sevenTreeHash -ne $identity.seven_source_sha256) {
        throw "Seven-source tree hash mismatch: $sevenTreeHash != $($identity.seven_source_sha256)"
    }

    foreach ($expected in $identity.build_and_source_files) {
        $actual = $allFiles | Where-Object { $_.file -eq $expected.file }
        if ($null -eq $actual -or $actual.sha256 -ne $expected.sha256) {
            throw "Tracked source/build hash mismatch: $($expected.file)"
        }
    }
    if ($allFiles.Count -ne 38) {
        throw "Expected 38 official code files, found $($allFiles.Count)"
    }

    $result = [pscustomobject]@{
        official_task_id = $identity.official_task_id
        zip_path = $zip
        package_sha256 = $packageHash
        file_count = $allFiles.Count
        seven_source_sha256 = $sevenTreeHash
        all_files = $allFiles
        verified = $true
    }
} finally {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force
}

$parent = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$result | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 -LiteralPath $OutputPath
$result | ConvertTo-Json -Depth 3
