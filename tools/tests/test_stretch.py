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

    def test_show_all_omits_noops(self):
        code, out, err = run(FIXTURES / "clean.json", "--show-all")
        self.assertEqual(code, 0, err)
        self.assertNotIn("terraform_data", out)


if __name__ == "__main__":
    unittest.main()
