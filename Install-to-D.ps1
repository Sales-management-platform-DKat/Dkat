param([string]$Destination = 'D:\Dkat')
$ErrorActionPreference = 'Stop'
$source = $PSScriptRoot
if ([IO.Path]::GetFullPath($source).TrimEnd('\') -eq [IO.Path]::GetFullPath($Destination).TrimEnd('\')) {
    Write-Host 'Du an da nam dung thu muc. Chay .\Start-DKat.ps1'; exit
}
$backup = Join-Path (Split-Path $Destination -Parent) ('Dkat-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
foreach ($file in Get-ChildItem -LiteralPath $source -File -Recurse) {
    $relative = $file.FullName.Substring($source.Length).TrimStart('\','/')
    $target = Join-Path $Destination $relative
    if (Test-Path -LiteralPath $target) {
        $old = Join-Path $backup $relative
        New-Item -ItemType Directory -Force -Path (Split-Path $old -Parent) | Out-Null
        Copy-Item -LiteralPath $target -Destination $old
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $target -Parent) | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $target -Force
}
Write-Host "Da cai vao $Destination. File cu neu co duoc sao luu tai $backup" -ForegroundColor Green
Write-Host "Chay: cd '$Destination'; .\Start-DKat.ps1"
