"""Optional senior stretch for tools/plan-risk: --format json and --show-all."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "plan-risk"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def run(*args):
    proc = subprocess.run(
        [str(CLI), *map(str, args)],
        capture_output=True,
        text=True,
        timeout=30,
        stdin=subprocess.DEVNULL,
    )
    return proc.returncode, proc.stdout, proc.stderr


class StretchTest(unittest.TestCase):
    def test_json_format(self):
        code, out, err = run(FIXTURES / "mixed.json", "--format", "json")
        self.assertEqual(code, 1, err)
        doc = json.loads(out)
        findings = doc["findings"]
        self.assertEqual(len(findings), 3)
        by_addr = {f["address"]: f for f in findings}
        self.assertEqual(by_addr["terraform_data.data_volume"]["reason"], "replace")
        self.assertEqual(by_addr['terraform_data.server["web-b"]']["reason"], "destroy")
        self.assertEqual(by_addr['terraform_data.ingress["office"]']["reason"], "open-to-world")
        self.assertTrue(all(f["severity"] == "HIGH" for f in findings))
        self.assertEqual(doc["summary"]["high"], 3)

    def test_json_format_on_clean_plan(self):
        code, out, err = run(FIXTURES / "clean.json", "--format", "json")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["findings"], [])

    def test_show_all_never_leaks_sensitive_values(self):
        code, out, err = run(FIXTURES / "secret_update.json", "--show-all")
        self.assertEqual(code, 0, err)
        combined = out + err
        self.assertIn("terraform_data.db_secret", out)
        self.assertNotIn("fixture-secret", combined)

    def test_show_all_explains_moved_resources(self):
        code, out, err = run(FIXTURES / "moved.json", "--show-all")
        self.assertEqual(code, 0, err)
        line = next(l for l in out.splitlines() if 'terraform_data.node["web-a"]' in l)
        self.assertTrue(line.startswith("INFO"), line)
        self.assertIn('terraform_data.server["web-a"]', line)
        self.assertIn("moved", line.lower())

    def test_show_all_marks_tags_only_updates(self):
        code, out, err = run(FIXTURES / "tags_only.json", "--show-all")
        self.assertEqual(code, 0, err)
        line = next(l for l in out.splitlines() if 'terraform_data.server["web-a"]' in l)
        self.assertTrue(line.startswith("INFO"), line)
        self.assertIn("tags-only", line.lower())
        self.assertIn("input", line, "changed top-level attribute names must be listed")

    def update_line(self, before, after, unknown):
        plan = {
            "format_version": "1.2",
            "planned_values": {},
            "resource_changes": [
                {
                    "address": "terraform_data.x",
                    "mode": "managed",
                    "change": {"actions": ["update"], "before": before, "after": after, "after_unknown": unknown},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(plan))
            code, out, err = run(path, "--show-all", "--format", "json")
        self.assertEqual(code, 0, err)
        return json.loads(out)["findings"][0]

    def test_bool_to_number_is_a_change(self):
        f = self.update_line({"input": True}, {"input": 1}, {"output": True})
        self.assertEqual(f["changed"], ["input"])

    def test_added_null_key_is_a_change(self):
        f = self.update_line({"input": {}}, {"input": {"optional": None}}, {"output": True})
        self.assertEqual(f["changed"], ["input"])

    def test_unknown_only_array_difference_is_not_a_change(self):
        before = {"input": {"tags": {"a": "1"}, "status": [{"id": "old"}]}}
        after = {"input": {"tags": {"a": "2"}, "status": [{}]}}
        unknown = {"input": {"status": [{"id": True}]}}
        f = self.update_line(before, after, unknown)
        self.assertEqual(f["reason"], "tags-only update")

    def run_change(self, change, *args, address="terraform_data.x", **extra):
        plan = {
            "format_version": "1.2",
            "planned_values": {},
            "resource_changes": [{"address": address, "mode": "managed", "change": change, **extra}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(plan))
            return run(path, *args)

    def test_unknown_only_update_is_a_plain_update_with_nothing_changed(self):
        change = {
            "actions": ["update"],
            "before": {"input": {"a": 1}, "output": {"a": 1}},
            "after": {"input": {"a": 1}},
            "after_unknown": {"output": True},
        }
        code, out, err = self.run_change(change, "--show-all")
        self.assertEqual(code, 0, err)
        self.assertIn("INFO terraform_data.x update", out.splitlines())
        code, out, err = self.run_change(change, "--show-all", "--format", "json")
        self.assertEqual(code, 0, err)
        finding = json.loads(out)["findings"][0]
        self.assertEqual((finding["reason"], finding["changed"]), ("update", []))

    def test_tags_all_counts_as_a_tag_change(self):
        cases = {
            "tags and tags_all": ({"tags": {"a": "1"}, "tags_all": {"a": "1"}}, {"tags": {"a": "2"}, "tags_all": {"a": "2"}}, ["tags", "tags_all"]),
            "nested tags_all": ({"input": {"tags_all": {"a": "1"}}}, {"input": {"tags_all": {"a": "2"}}}, ["input"]),
            "tags_all alone": ({"name": "n", "tags_all": {"a": "1"}}, {"name": "n", "tags_all": {"a": "2"}}, ["tags_all"]),
        }
        for name, (before, after, changed) in cases.items():
            with self.subTest(name=name):
                change = {"actions": ["update"], "before": before, "after": after, "after_unknown": {}}
                code, out, err = self.run_change(change, "--show-all", "--format", "json")
                self.assertEqual(code, 0, err)
                finding = json.loads(out)["findings"][0]
                self.assertEqual(finding["reason"], "tags-only update")
                self.assertEqual(sorted(finding["changed"]), changed)

    def test_tags_all_next_to_another_change_is_a_plain_update(self):
        change = {
            "actions": ["update"],
            "before": {"name": "a", "tags_all": {"a": "1"}},
            "after": {"name": "b", "tags_all": {"a": "2"}},
            "after_unknown": {},
        }
        code, out, err = self.run_change(change, "--show-all")
        self.assertEqual(code, 0, err)
        line = next(l for l in out.splitlines() if l.startswith("INFO terraform_data.x update"))
        prefix, _, names = line.partition(" (changed: ")
        self.assertEqual(prefix, "INFO terraform_data.x update")
        self.assertEqual(sorted(n.strip() for n in names.rstrip(")").split(",")), ["name", "tags_all"])

    def test_moved_and_replaced_resource_reports_both(self):
        change = {"actions": ["delete", "create"], "before": {"id": "1"}, "after": {"id": "2"}, "after_unknown": {}}
        previous = {"previous_address": "terraform_data.server[0]"}
        address = 'terraform_data.server["a"]'
        code, out, err = self.run_change(change, "--show-all", address=address, **previous)
        self.assertEqual(code, 1, err)
        lines = out.splitlines()
        self.assertIn('INFO terraform_data.server["a"] moved from terraform_data.server[0]', lines)
        self.assertIn('HIGH terraform_data.server["a"] replace', lines)
        self.assertEqual(len(lines), 2, out)

        code, out, err = self.run_change(change, address=address, **previous)
        self.assertEqual(code, 1, err)
        self.assertEqual(out.splitlines(), ['HIGH terraform_data.server["a"] replace'])

        code, out, err = self.run_change(change, "--format", "json", "--show-all", address=address, **previous)
        self.assertEqual(code, 1, err)
        doc = json.loads(out)
        self.assertEqual(
            sorted((f["severity"], f["reason"]) for f in doc["findings"]),
            [("HIGH", "replace"), ("INFO", "moved from terraform_data.server[0]")],
        )
        self.assertEqual(doc["summary"]["high"], 1)

    def test_moved_and_replaced_resource_keeps_its_other_findings(self):
        change = {
            "actions": ["delete", "create"],
            "before": {"cidr": "10.0.0.0/8"},
            "after": {"cidr": "0.0.0.0/0"},
            "after_unknown": {},
        }
        code, out, err = self.run_change(
            change, "--format", "json", "--show-all", address="terraform_data.ingress", previous_address="terraform_data.old"
        )
        self.assertEqual(code, 1, err)
        doc = json.loads(out)
        self.assertEqual(
            sorted((f["severity"], f["reason"]) for f in doc["findings"]),
            [("HIGH", "open-to-world"), ("HIGH", "replace"), ("INFO", "moved from terraform_data.old")],
        )
        self.assertEqual(doc["summary"]["high"], 2)

    def test_show_all_omits_noops(self):
        code, out, err = run(FIXTURES / "clean.json", "--show-all")
        self.assertEqual(code, 0, err)
        self.assertNotIn("terraform_data", out)


if __name__ == "__main__":
    unittest.main()
