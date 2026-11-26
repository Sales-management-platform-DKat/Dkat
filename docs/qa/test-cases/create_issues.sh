#!/usr/bin/env bash
# Create one GitHub issue per integration test case (POS & Auth, Đặt trước & Thông báo) (bodies in issues/TC-PA-xx.md) plus labels.
# Needs the GitHub CLI logged in once: gh auth login
# Run from the repository root:         bash docs/qa/test-cases/create_issues.sh
# Safe to run again: a test case whose issue already exists (same [TC-PA-xx] title) is skipped.
set -euo pipefail
repo="Sales-management-platform-DKat/Dkat"
dir="$(cd "$(dirname "$0")" && pwd)/issues"

existing="$(gh label list --repo "$repo" --limit 200 --json name --jq '.[].name')"
while IFS='|' read -r name color desc; do
  grep -qx "$name" <<<"$existing" || { gh label create "$name" --repo "$repo" --color "$color" --description "$desc" >/dev/null; echo "label  $name"; }
done <<'EOF'
test-case|0E8A16|Test case cần chạy
pos-auth|1D76DB|Test case tích hợp POS & Auth
auth|5319E7|Đăng nhập / xác thực
rbac|B60205|Phân quyền vai trò / chi nhánh
pos|FBCA04|Bán hàng POS / đơn bán
inventory|C2E0C6|Tồn kho
preorder-notify|0052CC|Test case tích hợp Đặt trước & Thông báo
preorder|D4C5F9|Đặt trước
notification|F9D0C4|Thông báo SMS / email
fifo|BFD4F2|Phân bổ hàng theo thứ tự đặt (FIFO)
retry|FEF2C0|Gửi lại thông báo
EOF

titles="$(gh issue list --repo "$repo" --state all --label test-case --limit 200 --json title --jq '.[].title')"
while IFS=$'\t' read -r id title labels; do
  labels="${labels%$'\r'}"  # index.tsv may have Windows line endings
  [ -n "$id" ] || continue
  if grep -qF "[$id]" <<<"$titles"; then echo "skip   $id (đã có issue)"; continue; fi
  url="$(gh issue create --repo "$repo" --title "$title" --body-file "$dir/$id.md" --label "$labels")"
  echo "issue  $id -> $url"
done < "$dir/index.tsv"
