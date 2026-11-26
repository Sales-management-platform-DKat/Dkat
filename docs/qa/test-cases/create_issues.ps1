# Create one GitHub issue per integration test case (POS & Auth, Đặt trước & Thông báo) (bodies in issues/TC-PA-xx.md) plus labels.
# Needs the GitHub CLI logged in once:  winget install GitHub.cli ; gh auth login
# Run from the repository root:          powershell -ExecutionPolicy Bypass -File docs/qa/test-cases/create_issues.ps1
# Safe to run again: a test case whose issue already exists (same [TC-PA-xx] title) is skipped.
$ErrorActionPreference = "Stop"
$repo = "Sales-management-platform-DKat/Dkat"
$dir = Join-Path $PSScriptRoot "issues"

$labels = @{
  "test-case" = @("0E8A16", "Test case cần chạy");
  "pos-auth"  = @("1D76DB", "Test case tích hợp POS & Auth");
  "auth"      = @("5319E7", "Đăng nhập / xác thực");
  "rbac"      = @("B60205", "Phân quyền vai trò / chi nhánh");
  "pos"       = @("FBCA04", "Bán hàng POS / đơn bán");
  "inventory" = @("C2E0C6", "Tồn kho");
  "preorder-notify" = @("0052CC", "Test case tích hợp Đặt trước & Thông báo");
  "preorder"  = @("D4C5F9", "Đặt trước");
  "notification" = @("F9D0C4", "Thông báo SMS / email");
  "fifo"      = @("BFD4F2", "Phân bổ hàng theo thứ tự đặt (FIFO)");
  "retry"     = @("FEF2C0", "Gửi lại thông báo")
}
$existing = gh label list --repo $repo --limit 200 --json name --jq ".[].name"
foreach ($name in $labels.Keys) {
  if ($existing -notcontains $name) {
    gh label create $name --repo $repo --color $labels[$name][0] --description $labels[$name][1] | Out-Null
    Write-Host "label  $name"
  }
}

$titles = gh issue list --repo $repo --state all --label test-case --limit 200 --json title --jq ".[].title"
foreach ($line in Get-Content (Join-Path $dir "index.tsv") -Encoding UTF8) {
  if (-not $line.Trim()) { continue }
  $id, $title, $labelList = $line -split "`t"
  if ($titles | Where-Object { $_ -like "[$id]*" }) { Write-Host "skip   $id (đã có issue)"; continue }
  $url = gh issue create --repo $repo --title $title --body-file (Join-Path $dir "$id.md") --label $labelList
  Write-Host "issue  $id -> $url"
}
