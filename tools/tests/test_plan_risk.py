"""CLI-contract tests for tools/plan-risk. Language-agnostic: only the executable is run."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLI = TOOLS / "plan-risk"


def run(*args):
    proc = subprocess.run(
        [str(CLI), *map(str, args)],
        capture_output=True,
        text=True,
        timeout=30,
        stdin=subprocess.DEVNULL,
    )
    return proc.returncode, proc.stdout + proc.stderr


def high_lines(output):
    return [line for line in output.splitlines() if line.startswith("HIGH")]


def plan_with(*changes):
    """Minimal hand-built plan JSON; each change is (address, actions, after)."""
    resource_changes = [
        {
            "address": address,
            "mode": "managed",
            "type": address.split(".")[-2] if "." in address else address,
            "change": {"actions": actions, "before": {}, "after": after or {}},
        }
        for address, actions, after in changes
    ]
    return {"format_version": "1.2", "planned_values": {}, "resource_changes": resource_changes}


class PlanRiskTest(unittest.TestCase):
    def run_plan(self, plan):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(plan))
            return run(path)

    def test_clean_plan_is_not_risky(self):
        code, out = run(FIXTURES / "clean.json")
        self.assertEqual(code, 0, out)
        self.assertEqual(high_lines(out), [])
        self.assertIn("no risky changes", out)

    def test_plan_without_resource_changes_key_is_not_risky(self):
        # terraform omits the key entirely when there is nothing to report
        code, out = run(FIXTURES / "empty.json")
        self.assertEqual(code, 0, out)
        self.assertIn("no risky changes", out)

    def test_create_only_is_not_risky(self):
        code, out = run(FIXTURES / "create_only.json")
        self.assertEqual(code, 0, out)
        self.assertIn("no risky changes", out)

    def test_destroy_is_flagged(self):
        code, out = run(FIXTURES / "destroy_server.json")
        self.assertEqual(code, 1, out)
        lines = high_lines(out)
        self.assertEqual(len(lines), 1, out)
        self.assertIn('terraform_data.server["web-b"]', lines[0])
        self.assertIn("destroy", lines[0].lower())

    def test_replace_is_flagged_as_replace_not_just_destroy(self):
        code, out = run(FIXTURES / "replace_volume.json")
        self.assertEqual(code, 1, out)
        lines = high_lines(out)
        self.assertEqual(len(lines), 1, out)
        self.assertIn("terraform_data.data_volume", lines[0])
        self.assertIn("replace", lines[0].lower())

    def test_create_before_destroy_replace_is_flagged(self):
        code, out = self.run_plan(plan_with(("aws_db_instance.main", ["create", "delete"], {})))
        self.assertEqual(code, 1, out)
        self.assertIn("replace", out.lower())

    def test_open_to_world_is_flagged_on_update(self):
        code, out = run(FIXTURES / "open_world.json")
        self.assertEqual(code, 1, out)
        lines = high_lines(out)
        self.assertEqual(len(lines), 1, out)
        self.assertIn('terraform_data.ingress["office"]', lines[0])
        self.assertIn("open-to-world", lines[0].lower())

    def test_open_to_world_is_flagged_on_create_including_ipv6_and_nesting(self):
        for cidr in ("0.0.0.0/0", "::/0"):
            with self.subTest(cidr=cidr):
                plan = plan_with(("module.net.aws_security_group_rule.in", ["create"], {"rules": [{"cidr_blocks": [cidr]}]}))
                code, out = self.run_plan(plan)
                self.assertEqual(code, 1, out)
                self.assertIn("module.net.aws_security_group_rule.in", out)
                self.assertIn("open-to-world", out.lower())

    def test_one_resource_can_have_several_findings(self):
        plan = plan_with(("aws_security_group_rule.in", ["delete", "create"], {"cidr": "0.0.0.0/0"}))
        code, out = self.run_plan(plan)
        self.assertEqual(code, 1, out)
        lines = [l.lower() for l in high_lines(out)]
        self.assertEqual(len(lines), 2, out)
        self.assertTrue(any("replace" in l for l in lines), out)
        self.assertTrue(any("open-to-world" in l for l in lines), out)

    def test_deleting_an_open_rule_is_not_reported_as_open_to_world(self):
        plan = plan_with(("aws_security_group_rule.in", ["delete"], None))
        plan["resource_changes"][0]["change"]["before"] = {"cidr": "0.0.0.0/0"}
        code, out = self.run_plan(plan)
        self.assertEqual(code, 1, out)
        self.assertNotIn("open-to-world", out.lower())

    def test_data_source_reads_are_ignored(self):
        plan = plan_with(("data.aws_caller_identity.me", ["read"], {}))
        code, out = self.run_plan(plan)
        self.assertEqual(code, 0, out)

    def test_mixed_plan_reports_every_finding_once(self):
        code, out = run(FIXTURES / "mixed.json")
        self.assertEqual(code, 1, out)
        lines = high_lines(out)
        self.assertEqual(len(lines), 3, out)
        for needle in ("data_volume", 'server["web-b"]', 'ingress["office"]'):
            self.assertEqual(sum(needle in line for line in lines), 1, out)

    def test_moved_resources_are_not_risky(self):
        code, out = run(FIXTURES / "moved.json")
        self.assertEqual(code, 0, out)

    def test_tags_only_update_is_not_risky(self):
        code, out = run(FIXTURES / "tags_only.json")
        self.assertEqual(code, 0, out)

    def test_unusable_input_exits_2(self):
        # state.json is `terraform show -json` of a state file: it has format_version but is no plan
        for name in ("not_a_plan.json", "state.json", "truncated.json", "does_not_exist.json"):
            with self.subTest(name=name):
                code, out = run(FIXTURES / name)
                self.assertEqual(code, 2, out)

    def test_malformed_resource_changes_exits_2(self):
        bad_actions = ([None], [], ["frobnicate"], ["delete", "update"], [{}], [[]])
        malformed_actions = [{"address": "a.b", "change": {"actions": a}} for a in bad_actions]
        for bad in ([{}], [{"address": "a.b"}], {"not": "a list"}, *[[m] for m in malformed_actions]):
            with self.subTest(bad=bad):
                plan = plan_with()
                plan["resource_changes"] = bad
                code, out = self.run_plan(plan)
                self.assertEqual(code, 2, out)

    def test_no_arguments_exits_2(self):
        code, out = run()
        self.assertEqual(code, 2, out)


if __name__ == "__main__":
    unittest.main()
