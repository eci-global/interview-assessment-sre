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

legacy_id() { # legacy_id <server index>: the id terraform recorded for that server
  (cd "$work" && terraform show -json | jq -r --arg a "module.fleet.terraform_data.server[$1]" '.. | objects | select(.address? == $a) | .values.id')
}
id_web_a="$(legacy_id 0)"
id_web_b="$(legacy_id 1)"
id_worker_a="$(legacy_id 2)"

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

# Second plan against the same existing state, with web-b removed from the servers.
servers_json="$(jq -c '.configuration.root_module.module_calls.fleet.expressions.servers.constant_value // empty' plan.json)"
if [ -z "$servers_json" ]; then
  bad "removing web-b: the root config's module call needs a literal servers list"
else
  jq -n --argjson s "$servers_json" '{module: {fleet: {servers: ($s | map(select(.name != "web-b")))}}}' >zz_removal_override.tf.json
fi
if ! terraform plan -input=false -no-color -out=plan-remove.bin >plan-remove.out 2>&1; then
  bad "removing web-b from the root config: terraform plan failed"
  sed -n 's/^/    /;1,25p' plan-remove.out
else
  terraform show -json plan-remove.bin >plan-remove.json
  deleted="$(jq -c '[.resource_changes[]? | select(.change.actions | index("delete")) | [.change.before.id, .change.actions]]' plan-remove.json)"
  [ "$deleted" = "[[\"$id_web_b\",[\"delete\"]]]" ] || bad "removing web-b must only destroy the web-b server (no replacement); planned deletions: $(jq -r '[.resource_changes[]? | select(.change.actions | index("delete")) | .address + " " + (.change.actions | join("+"))] | join(", ")' plan-remove.json)"
  for i in web-a:"$id_web_a" worker-a:"$id_worker_a"; do
    key="${i%%:*}"
    of_id='[.resource_changes[]? | select(.change.before.id? == $id) | .change | {actions, before, after, after_unknown}] | first // "missing"'
    before="$(jq -c --arg id "${i#*:}" "$of_id" plan.json)"
    after="$(jq -c --arg id "${i#*:}" "$of_id" plan-remove.json)"
    [ "$before" = "$after" ] || bad "removing web-b changes the plan for server $key"
  done
fi

if [ "$fail" -eq 0 ]; then
  say "state safety: OK (no destroys, servers moved, volume protected, removing web-b destroys only web-b)"
else
  say
  say "--- plan against existing state (terraform show) ---"
  terraform show -no-color plan.bin | grep -E '^\s*(#|~|\+|-|Plan:)' | head -n 60 || true
  if [ -f plan-remove.json ]; then
    say
    say "--- plan with web-b removed (terraform show) ---"
    terraform show -no-color plan-remove.bin | grep -E '^\s*(#|~|\+|-|Plan:)' | sed -n '1,60p' || true
  fi
  exit 1
fi
