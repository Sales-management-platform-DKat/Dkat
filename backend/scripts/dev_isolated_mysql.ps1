param(
    [string]$MySqlBin = 'C:\Program Files\MySQL\MySQL Server 8.0\bin',
    [string]$Database = 'dkat_local_e2e',
    [int]$Port = 0,
    [string]$EnvFile = ''
)
# Starts a brand-new, disposable MySQL instance (own datadir, loopback only),
# loads database/01_schema.sql, every incremental database/0N_*.sql script and
# samples/02_auth_schema.sql, then keeps running until this process is stopped.
# It never reads backend/.env and never connects to TiDB or team data.
# Native tools log to stderr; PowerShell 5.1 would treat that as fatal, so rely on exit codes.
$ErrorActionPreference = 'Continue'
$backendDir = Split-Path $PSScriptRoot -Parent
$repoDir = Split-Path $backendDir -Parent
$mysqldExe = Join-Path $MySqlBin 'mysqld.exe'
$mysqlExe = Join-Path $MySqlBin 'mysql.exe'
$adminExe = Join-Path $MySqlBin 'mysqladmin.exe'
foreach ($requiredPath in @($mysqldExe, $mysqlExe, $adminExe)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) { throw "Missing: $requiredPath" }
}
if ($Database -notmatch '^dkat_[a-z0-9_]*(test|e2e)$') { throw 'Database name must look like dkat_*_test or dkat_*_e2e' }
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('dkat-local-' + [guid]::NewGuid().ToString('N'))
$dataDir = Join-Path $testRoot 'data'
New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
if ($Port -eq 0) {
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
    $listener.Start(); $Port = $listener.LocalEndpoint.Port; $listener.Stop()
}
$env:MYSQL_PWD = ''
& $mysqldExe --no-defaults --initialize-insecure "--datadir=$dataDir" --console 2>$null
if ($LASTEXITCODE -ne 0) { throw 'Could not initialize isolated MySQL' }
$server = Start-Process -FilePath $mysqldExe -ArgumentList @(
    '--no-defaults', "--datadir=`"$dataDir`"", "--port=$Port",
    '--bind-address=127.0.0.1', '--mysqlx=OFF', '--skip-log-bin'
) -WindowStyle Hidden -PassThru -RedirectStandardError (Join-Path $testRoot 'mysql-error.log')
try {
    $mysqlArgs = @('--no-defaults', '--host=127.0.0.1', "--port=$Port", '--user=root', '--default-character-set=utf8mb4')
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        if ($server.HasExited) { throw "Isolated MySQL exited; see $testRoot" }
        & $adminExe @mysqlArgs ping --silent 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) { throw 'Isolated MySQL did not become ready' }
    $scripts = @(Join-Path $repoDir 'database\01_schema.sql')
    $scripts += Join-Path $backendDir 'samples\02_auth_schema.sql'
    $scripts += Get-ChildItem (Join-Path $repoDir 'database') -Filter '0*.sql' |
        Where-Object { $_.Name -notlike '01_*' } | Sort-Object Name | ForEach-Object FullName
    foreach ($path in $scripts) {
        $sql = (Get-Content -LiteralPath $path -Raw -Encoding UTF8) -replace '\bdkat\b', $Database
        # Grants target the deployment user; the disposable instance has its own user.
        $sql = $sql -replace '(?m)^GRANT .*$', ''
        $sql | & $mysqlExe @mysqlArgs
        if ($LASTEXITCODE -ne 0) { throw "Schema import failed: $path" }
    }
    $password = [guid]::NewGuid().ToString('N')
    & $mysqlExe @mysqlArgs "--execute=CREATE USER 'dkatlocal'@'127.0.0.1' IDENTIFIED BY '$password'; GRANT ALL ON $Database.* TO 'dkatlocal'@'127.0.0.1'"
    if ($LASTEXITCODE -ne 0) { throw 'Test user creation failed' }
    $lines = @("DB_HOST=127.0.0.1", "DB_PORT=$Port", "DB_NAME=$Database", "DB_USER=dkatlocal", "DB_PASSWORD=$password")
    if ($EnvFile) { $lines | Set-Content -LiteralPath $EnvFile -Encoding ascii }
    Write-Output "READY port=$Port database=$Database datadir=$testRoot"
    Wait-Process -Id $server.Id
} finally {
    if (-not $server.HasExited) {
        & $adminExe --no-defaults --host=127.0.0.1 "--port=$Port" --user=root shutdown 2>$null | Out-Null
        Start-Sleep -Seconds 2
        if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    }
    Remove-Item -LiteralPath $testRoot -Recurse -Force -ErrorAction SilentlyContinue
}
