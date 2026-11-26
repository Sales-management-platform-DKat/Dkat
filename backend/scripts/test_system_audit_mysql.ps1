param(
    [string]$MySqlBin = 'C:\Program Files\MySQL\MySQL Server 8.0\bin'
)
# Runs integration_tests/test_system_audit_mysql.py against a brand-new disposable
# MySQL instance (see dev_isolated_mysql.ps1). Never touches backend/.env or TiDB.
$ErrorActionPreference = 'Continue'
$backendDir = Split-Path $PSScriptRoot -Parent
$pythonExe = Join-Path $backendDir '.venv\Scripts\python.exe'
$envFile = Join-Path ([IO.Path]::GetTempPath()) ('dkat-audit-' + [guid]::NewGuid().ToString('N') + '.env')
$listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
$listener.Start(); $port = $listener.LocalEndpoint.Port; $listener.Stop()
$helper = Start-Process powershell.exe -WindowStyle Hidden -PassThru -ArgumentList @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$(Join-Path $PSScriptRoot 'dev_isolated_mysql.ps1')`"",
    '-MySqlBin', "`"$MySqlBin`"", '-Database', 'dkat_audit_test', '-Port', $port, '-EnvFile', "`"$envFile`""
)
$names = @('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DKAT_DATABASE_URL', 'DKAT_ADMIN_TOKEN', 'DKAT_AUTH_SECRET_KEY', 'DKAT_AUDIT_TEST_DB')
$saved = @{}
foreach ($name in $names) { $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$exitCode = 1
try {
    for ($i = 0; $i -lt 240 -and -not (Test-Path $envFile); $i++) {
        if ($helper.HasExited) { throw 'Isolated MySQL failed to start' }
        Start-Sleep -Milliseconds 500
    }
    if (-not (Test-Path $envFile)) { throw 'Isolated MySQL did not become ready' }
    $values = @{}
    Get-Content $envFile | ForEach-Object { $key, $value = $_ -split '=', 2; $values[$key] = $value }
    # Mask DB_* so backend/.env cannot point the app at TiDB (an empty string would delete
    # the variable on Windows and let load_dotenv refill it; config strips the space).
    foreach ($name in @('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD')) { [Environment]::SetEnvironmentVariable($name, ' ', 'Process') }
    $env:DKAT_DATABASE_URL = "mysql+pymysql://$($values.DB_USER):$($values.DB_PASSWORD)@127.0.0.1:$($values.DB_PORT)/$($values.DB_NAME)?charset=utf8mb4"
    $env:DKAT_ADMIN_TOKEN = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
    $env:DKAT_AUTH_SECRET_KEY = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
    $env:DKAT_AUDIT_TEST_DB = '1'
    Push-Location $backendDir
    & $pythonExe -m unittest integration_tests.test_system_audit_mysql -v
    $exitCode = $LASTEXITCODE
    Pop-Location
} finally {
    $adminExe = Join-Path $MySqlBin 'mysqladmin.exe'
    & $adminExe --no-defaults --host=127.0.0.1 "--port=$port" --user=root shutdown 2>$null | Out-Null
    # The helper removes its temporary datadir once mysqld has stopped.
    if (-not $helper.WaitForExit(20000)) { Stop-Process -Id $helper.Id -Force -ErrorAction SilentlyContinue }
    Get-CimInstance Win32_Process -Filter "Name='mysqld.exe'" | Where-Object { $_.CommandLine -like "*--port=$port*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Remove-Item $envFile -ErrorAction SilentlyContinue
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process') }
}
if ($exitCode -ne 0) { Write-Host 'System audit MySQL tests FAILED'; exit 1 }
Write-Host 'System audit MySQL tests passed.'
