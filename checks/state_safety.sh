#!/usr/bin/env bash
# State-safety check: would applying your refactor to EXISTING state destroy anything?
#
#   1. applies the frozen pre-refactor config (checks/legacy) to a throwaway local state
#   2. swaps in your root config + modules/service_fleet
#   3. plans, and asserts on the plan JSON
#
# Local state in a temp dir, built-in provider only: no network, no credentials.
set -euo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
fail=0

say() { printf '%s\n' "$*"; }
bad() { say "FAIL: $*"; fail=1; }

command -v jq >/dev/null || { say "jq is required"; exit 2; }

cp -R "$here/checks/legacy/." "$work/"
(
  cd "$work"
  terraform init -input=false -no-color >/dev/null
  terraform apply -auto-approve -input=false -no-color >/dev/null
)
say "legacy state applied ($(cd "$work" && terraform state list | wc -l | tr -d ' ') resources)"

root_files=("*.tf" "*.tf.json" "*.tfvars" "*.tfvars.json")
rm -rf "$work/modules"
for pattern in "${root_files[@]}"; do
  rm -f "$work"/$pattern
  for f in "$here"/$pattern; do
    if [ -e "$f" ]; then cp "$f" "$work/"; fi
  done
done
cp -R "$here/modules" "$work/modules"

cd "$work"
terraform init -input=false -no-color >/dev/null
terraform plan -input=false -no-color -out=plan.bin >/dev/null
terraform show -json plan.bin >plan.json

destroys="$(jq -r '.resource_changes[]? | select(.change.actions | index("delete")) | .address' plan.json)"
[ -z "$destroys" ] || bad "plan destroys or replaces: $(echo "$destroys" | tr '\n' ' ')"

for i in 0:web-a 1:web-b 2:worker-a; do
  idx="${i%%:*}"
  key="${i##*:}"
  addr="module.fleet.terraform_data.server[\"$key\"]"
  prev="$(jq -r --arg a "$addr" '.resource_changes[]? | select(.address == $a) | .previous_address // empty' plan.json)"
  [ "$prev" = "module.fleet.terraform_data.server[$idx]" ] || bad "$addr was not moved from server[$idx] (previous_address='${prev}')"
done

want='checkout-prod-web-a'
got="$(jq -r '.resource_changes[]? | select(.address == "module.fleet.terraform_data.server[\"web-a\"]") | .change.after.input.name // empty' plan.json)"
[ "$got" = "$want" ] || bad "web-a name in plan is '${got}', expected '${want}' (is ignore_changes hiding drift?)"

volume='module.fleet.terraform_data.data_volume'
if terraform plan -destroy -input=false -no-color >destroy.out 2>&1; then
  bad "destroying $volume is not blocked: add lifecycle prevent_destroy to it"
elif ! grep -qF "Resource $volume has" destroy.out || ! grep -q 'cannot be destroyed' destroy.out; then
  bad "'terraform plan -destroy' does not refuse to destroy $volume (prevent_destroy on that resource?). Output:"
  sed 's/^/    /' destroy.out | head -n 25
fi

if [ "$fail" -eq 0 ]; then
  say "state safety: OK (no destroys, servers moved, volume protected)"
else
  say
  say "--- plan against existing state (terraform show) ---"
  terraform show -no-color plan.bin | grep -E '^\s*(#|~|\+|-|Plan:)' | head -n 60 || true
  exit 1
fi
