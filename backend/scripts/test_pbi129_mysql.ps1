param(
    [string]$MySqlBin = 'C:\Program Files\MySQL\MySQL Server 8.0\bin'
)
$ErrorActionPreference = 'Stop'
$backendDir = Split-Path $PSScriptRoot -Parent
$pythonExe = Join-Path $backendDir '.venv\Scripts\python.exe'
$mysqldExe = Join-Path $MySqlBin 'mysqld.exe'
$mysqlExe = Join-Path $MySqlBin 'mysql.exe'
$adminExe = Join-Path $MySqlBin 'mysqladmin.exe'
foreach ($requiredPath in @($pythonExe, $mysqldExe, $mysqlExe, $adminExe)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) { throw "Missing: $requiredPath" }
}
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('dkat-pbi129-' + [guid]::NewGuid().ToString('N'))
$dataDir = Join-Path $testRoot 'data'
New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
$listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
$listener.Start()
$testPort = $listener.LocalEndpoint.Port
$listener.Stop()
$envNames = @('DB_HOST', 'DB_SSL_MODE', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DKAT_ADMIN_TOKEN', 'DKAT_FIFO_TEST_DB', 'MYSQL_PWD', 'PYTHONIOENCODING', 'PREORDER_READY_DAYS')
$savedEnv = @{}
foreach ($envName in $envNames) { $savedEnv[$envName] = [Environment]::GetEnvironmentVariable($envName, 'Process') }
$serverProcess = $null
$pushedLocation = $false
try {
    $env:MYSQL_PWD = ''
    $env:PYTHONIOENCODING = 'utf-8'
    & $mysqldExe --no-defaults --initialize-insecure "--datadir=$dataDir" --console
    if ($LASTEXITCODE -ne 0) { throw 'Could not initialize isolated MySQL' }
    $serverProcess = Start-Process -FilePath $mysqldExe -ArgumentList @(
        '--no-defaults', "--datadir=`"$dataDir`"", "--port=$testPort",
        '--bind-address=127.0.0.1', '--mysqlx=OFF', '--skip-log-bin'
    ) -WindowStyle Hidden -PassThru -RedirectStandardError (Join-Path $testRoot 'mysql-error.log')
    $mysqlArgs = @('--no-defaults', '--host=127.0.0.1', "--port=$testPort", '--user=root', '--default-character-set=utf8mb4')
    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if ($serverProcess.HasExited) { throw "Test MySQL exited; see $testRoot" }
        & $adminExe @mysqlArgs ping --silent 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) { throw "Test MySQL did not become ready; see $testRoot" }
    $databaseDir = Join-Path (Split-Path $backendDir -Parent) 'database'
    foreach ($scriptName in @(
        '01_schema.sql', '07_preorder_fifo_expiry.sql', '07_preorder_fifo_expiry.sql',
        '08_preorder_cancellation.sql', '08_preorder_cancellation.sql'
    )) {
        $schema = (Get-Content -LiteralPath (Join-Path $databaseDir $scriptName) -Raw -Encoding UTF8).Replace('dkat', 'dkat_pbi129_test')
        if ($scriptName -eq '01_schema.sql') {
            $schema = [regex]::Replace($schema, '(?m)^    (?:expires_at DATETIME,|KEY ix_preorders_expiry \([^)]+\),)\r?\n', '')
            $schema = [regex]::Replace($schema, '(?m)(^    fulfilled_at DATETIME,\r?\n)    cancel_reason VARCHAR\(255\),\r?\n    cancelled_at DATETIME,\r?\n', '$1')
        }
        $schema | & $mysqlExe @mysqlArgs
        if ($LASTEXITCODE -ne 0) { throw "Test schema import failed: $scriptName" }
        if ($scriptName -eq '01_schema.sql') {
            $legacySeed = @'
USE dkat_pbi129_test;
INSERT INTO stores (name) VALUES ('Legacy FIFO migration');
SET @legacy_store=LAST_INSERT_ID();
INSERT INTO branches (store_id,branch_code,name,address,status) VALUES (@legacy_store,'OLD','Legacy','QA','ACTIVE');
SET @legacy_branch=LAST_INSERT_ID();
INSERT INTO preorders (preorder_code,branch_id,customer_name,customer_phone,total_amount,payment_status,status,ready_at)
VALUES ('LEGACY-PBI129',@legacy_branch,'Legacy before FIFO','0900000000',0,'UNPAID','READY','2026-01-01');
'@
            $legacySeed | & $mysqlExe @mysqlArgs
            if ($LASTEXITCODE -ne 0) { throw 'Legacy FIFO fixture failed' }
        }
    }
    $testPassword = [guid]::NewGuid().ToString('N')
    & $mysqlExe @mysqlArgs "--execute=CREATE USER 'pbi129'@'127.0.0.1' IDENTIFIED BY '$testPassword'; GRANT ALL ON dkat_pbi129_test.* TO 'pbi129'@'127.0.0.1'"
    if ($LASTEXITCODE -ne 0) { throw 'Test user creation failed' }
    $env:DB_HOST = '127.0.0.1'
    $env:DB_SSL_MODE = 'disabled'  # isolated mysqld uses a self-signed certificate
    $env:DB_PORT = [string]$testPort
    $env:DB_NAME = 'dkat_pbi129_test'
    $env:DB_USER = 'pbi129'
    $env:DB_PASSWORD = $testPassword
    $env:DKAT_ADMIN_TOKEN = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
    $env:DKAT_FIFO_TEST_DB = '1'
    $env:PREORDER_READY_DAYS = '7'
    Push-Location $backendDir
    $pushedLocation = $true
    & $pythonExe -m integration_tests.test_preorder_fifo_mysql
    if ($LASTEXITCODE -ne 0) { throw 'PBI 129 integration tests failed' }
    Write-Host 'PBI 129: all MySQL integration tests passed.'
}
finally {
    if ($pushedLocation) { Pop-Location }
    if ($serverProcess -and -not $serverProcess.HasExited) {
        & $adminExe --no-defaults --host=127.0.0.1 "--port=$testPort" --user=root shutdown 2>$null | Out-Null
        if (-not $serverProcess.WaitForExit(10000)) { Stop-Process -Id $serverProcess.Id }
    }
    foreach ($envName in $envNames) { [Environment]::SetEnvironmentVariable($envName, $savedEnv[$envName], 'Process') }
    Write-Host "Isolated MySQL logs: $testRoot"
}
