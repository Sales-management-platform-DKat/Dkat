$ErrorActionPreference = 'Stop'
$frontend = Join-Path $PSScriptRoot 'frontend'
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Can cai Node.js 22.12 tro len tu https://nodejs.org/ truoc.' }
Push-Location $frontend
try {
    if (-not (Test-Path 'node_modules')) {
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'Cai dependencies khong thanh cong.' }
    }
    Write-Host 'Mo dia chi Local do Vite hien thi. Nhan Ctrl+C de dung.' -ForegroundColor Green
    & npm.cmd run dev
} finally { Pop-Location }
