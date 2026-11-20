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
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('dkat-pbi110-' + [guid]::NewGuid().ToString('N'))
$dataDir = Join-Path $testRoot 'data'
New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
$listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
$listener.Start()
$testPort = $listener.LocalEndpoint.Port
$listener.Stop()
$envNames = @('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DKAT_ADMIN_TOKEN', 'DKAT_PREORDER_TEST_DB', 'MYSQL_PWD', 'PYTHONIOENCODING')
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
    foreach ($scriptName in @('01_schema.sql', '06_public_preorders.sql', '06_public_preorders.sql')) {
        $schema = (Get-Content -LiteralPath (Join-Path $databaseDir $scriptName) -Raw -Encoding UTF8).Replace('dkat', 'dkat_pbi110_test')
        $schema | & $mysqlExe @mysqlArgs
        if ($LASTEXITCODE -ne 0) { throw "Test schema import failed: $scriptName" }
    }
    $testPassword = [guid]::NewGuid().ToString('N')
    & $mysqlExe @mysqlArgs "--execute=CREATE USER 'pbi110'@'127.0.0.1' IDENTIFIED BY '$testPassword'; GRANT ALL ON dkat_pbi110_test.* TO 'pbi110'@'127.0.0.1'"
    if ($LASTEXITCODE -ne 0) { throw 'Test user creation failed' }
    $env:DB_HOST = '127.0.0.1'
    $env:DB_PORT = [string]$testPort
    $env:DB_NAME = 'dkat_pbi110_test'
    $env:DB_USER = 'pbi110'
    $env:DB_PASSWORD = $testPassword
    $env:DKAT_ADMIN_TOKEN = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
    $env:DKAT_PREORDER_TEST_DB = '1'
    Push-Location $backendDir
    $pushedLocation = $true
    & $pythonExe -m integration_tests.test_public_preorders_mysql
    if ($LASTEXITCODE -ne 0) { throw 'PBI 110 integration tests failed' }
    Write-Host 'PBI 110: all MySQL integration tests passed.'
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
