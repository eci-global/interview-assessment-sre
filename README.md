# Checkout Fleet — SRE Terraform Assessment

Welcome! The `checkout` team's Terraform module (`modules/service_fleet`) was written in a hurry and has been limping along in production. Before the next release the team wants it cleaned up, made safe to change, and paired with a small tool that reviews plans before anyone applies them. Your job is to get it there.

You can work through this live with an interviewer or on your own; either way, explain your reasoning as you go.

**Time box: 45 minutes.** The core work is sized for about 35; the rest is slack for reading and thinking out loud. Don't polish — prioritise, and tell us what you would do with more time. If you finish early, there is an optional stretch at the end.

## Ground rules

- Everything runs **offline with no cloud account and no credentials**. The module uses the built-in `terraform_data` resource, so there is nothing to download. Do not point anything at a real cloud.
- Use any tools you would use on the job: docs, search, your editor. We care about how you think, so narrate your decisions and be ready to explain every line you keep.
- Don't edit the tests under `tests/` or `tools/tests/`, or anything under `checks/`. Everything else is fair game.
- Prefer small, reviewable changes. Treat the existing infrastructure as **live production**: assume state already exists for what the root config describes.

## Setup

Requires Terraform `>= 1.9, < 2.0` (tested on 1.15; install from https://developer.hashicorp.com/terraform/install), `python3` (3.9+), `jq`, and `bash`. No `make` needed.

```bash
./run            # every core check, with a pass/fail summary (plus an optional stretch line)
./run fmt        # terraform fmt -check
./run validate   # terraform init + validate
./run test       # terraform test (plan-only, one file per behaviour)
./run state      # state-safety check, see Task B
./run script     # tests for tools/plan-risk, see Task C
./run stretch    # optional, see Stretch
```

At the start every check fails. You're done when `./run` is green. The summary also shows the stretch result on an `OPTIONAL` line; it never affects the exit code.

## Tasks

### Task A — Make the module correct (≈ 15 min)

Start with `./run fmt`, `./run validate`, then `./run test`. The tests under `tests/` describe how the module is supposed to behave; read them, then read the module. Fix the module so they pass.

`environment` accepts exactly `dev` and `prod`; any other value, such as `production`, must be rejected by validation.

Beyond the tests: the module has problems the tests don't cover or only partly cover. Anything you find that could hurt in production is worth fixing or at least calling out, and tell us which you chose and why.

### Task B — Refactor without destroying anything (≈ 10 min)

The module uses `count` for its servers. The team wants servers addressed by name instead, so removing one doesn't shuffle the others. The root config in `main.tf` is already applied in production; `checks/legacy/` is a frozen copy of the pre-refactor code, and `./run state` applies it to a throwaway local state, swaps in your code and asserts on the resulting plan.

Make the refactor so that `./run state` passes: nothing is destroyed or replaced, existing servers keep their identity, and the data volume can't be destroyed by accident. Read the plan output when it fails; it tells you a lot.

`./run state` also plans a second time against the same state with the `web-b` entry removed from the `servers` list of the root config (the module call's `servers` is a literal list in `main.tf`): that plan must destroy only the `web-b` server and plan the other servers exactly as before.

### Task C — Review plans with a script (≈ 12 min)

Implement `tools/plan-risk`, a CLI that reads the JSON from `terraform show -json plan.bin` and flags risky changes. Python is provided as a skeleton; you may rewrite it in bash+jq if you prefer. Only the CLI behaviour is tested (`./run script`). Real plan fixtures are in `tools/tests/fixtures/`; poke at them with `jq`. Once the module validates, you can make a plan of your own from the root config:

```bash
terraform init -input=false && terraform plan -out plan.bin
terraform show -json plan.bin > plan.json
```

Contract:

```
plan-risk PLAN.json
```

- For each **risky** resource change print one line `HIGH <address> <reason>` where `<reason>` is one of:
  - `destroy` — the resource is deleted
  - `replace` — it is deleted and re-created (either order)
  - `open-to-world` — a resource being created or updated contains the CIDR `0.0.0.0/0` or `::/0` anywhere in its planned values
- A resource can have more than one finding.
- Everything else (no-ops, creates, in-place updates, data source reads, `forget` actions that drop a resource from state without destroying it, resources that merely moved address) is not risky.
- If nothing is risky, print `no risky changes`.
- Exit code: `0` nothing risky, `1` at least one `HIGH` finding, `2` the input can't be used: missing file, invalid JSON, JSON that is not a Terraform plan (a plan has `format_version` and `planned_values`; `terraform show -json` of a *state* has no `planned_values`), or a malformed `resource_changes`. Never crash with a traceback.

## Stretch (optional, mainly for senior candidates)

Extend `plan-risk` (`./run stretch`):

- `--format json` prints `{"findings": [{"address", "severity", "reason", "changed"}], "summary": {"high": N}}`.
- `--show-all` also lists non-`HIGH` changes as `INFO <address> <reason>` lines: `create`, `update`, `tags-only update`, and `moved from <previous address>` (a moved resource may also have an update). No-ops without a move are omitted. `update` and `tags-only update` lines end with `(changed: <top-level attribute names>)` (comma-separated), **never values** — plans contain secrets. Attributes that are only "known after apply" are not user changes.
- An `update` whose only differences are "known after apply" values is still reported as `update`, with nothing changed: the text line has no `(changed: ...)` suffix (`INFO <address> update`) and the JSON `changed` is `[]`.
- An update is a `tags-only update` when every changed attribute is, or sits under, a key named `tags` or `tags_all` (at any depth). A change to `tags_all` counts as a tag change, alone or together with `tags`.
- A resource that was both moved and replaced gets two entries: `INFO <address> moved from <previous address>` and `HIGH <address> replace`. Without `--show-all` only the `HIGH` line is printed; with `--format json --show-all` both are in `findings`, and `summary.high` counts the `HIGH` one. Any other applicable finding for that resource (for example `open-to-world`) is reported as well. The order of lines, and of attribute names inside `(changed: ...)`, is not specified.

## What to submit

Leave your changes in the working tree; there is nothing to build or upload. Be ready to say, for each task, what you changed and why, what you chose to leave alone, and what you would do with more time. Your interviewer will tell you how to hand the work in: a walkthrough, a zip, or a branch. If you write notes, put them in a `NOTES.md` at the repo root.

## What we're looking at

- How you orient yourself in someone else's code and read tool output
- Judgement: what is risky, what to fix first, what to leave alone
- Terraform fundamentals and state safety, not just making the tests green
- The quality of your fixes and how clearly you explain them

## Layout

```
main.tf, versions.tf        root config (applied in production)
modules/service_fleet/      the module under repair
tests/                      terraform test files (plan-only)
checks/state_safety.sh      state-safety check (do not edit)
checks/legacy/              frozen pre-refactor code (do not edit)
tools/plan-risk             Task C
tools/tests/                tests and plan fixtures for Task C
run                         single entry point for all checks
```
