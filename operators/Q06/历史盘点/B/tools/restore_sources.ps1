$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$taskArchiveRoot = Join-Path $taskRoot 'artifacts\official'
$taskCacheRoot = Join-Path $taskRoot 'artifacts\platform'
foreach ($taskArchive in (Get-ChildItem -LiteralPath $taskArchiveRoot -File -Filter '*.zip')) {
    if ($taskArchive.BaseName -notmatch '^\d+$') { continue }
    $taskDestination = [IO.Path]::GetFullPath((Join-Path $taskCacheRoot $taskArchive.BaseName))
    if (-not $taskDestination.StartsWith($taskCacheRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Source restore path escaped the handoff directory.'
    }
    if (-not (Test-Path -LiteralPath $taskDestination)) {
        Expand-Archive -LiteralPath $taskArchive.FullName -DestinationPath $taskDestination
    }
}
Write-Output 'Official source packages restored to artifacts/platform. Existing directories were retained.'
