import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from schola.evaluator import budget_survivability_gate, curriculum_gate, evaluate, graduation_gate
from schola.spoonfeeder import briefing, task_pool
from schola.watcher import normalize, scan, validate_public_url

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("privacy_guard", ROOT / "scripts/privacy_guard.py")
privacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(privacy)


class GateChecks(unittest.TestCase):
    def test_budget_boundaries_and_unknown_values(self):
        self.assertEqual(budget_survivability_gate({"estimatedFamilyGapIdrMPerMonth": "2–4"}, 4)["status"], "PASS")
        self.assertEqual(budget_survivability_gate({"estimatedFamilyGapIdrMPerMonth": "3–5"}, 4)["status"], "UNKNOWN")
        self.assertEqual(budget_survivability_gate({"estimatedFamilyGapIdrMPerMonth": "5–8"}, 4)["status"], "FAIL")
        for value in (None, "TBD", "0 if funded, 20 otherwise", "6–2"):
            self.assertEqual(budget_survivability_gate({"estimatedFamilyGapIdrMPerMonth": value}, 4)["status"], "UNKNOWN")

    def test_total_cost_less_coverage_and_upfront_separate(self):
        cost = {"tuition": 12, "housing": 4, "food": 2, "insurance": .5, "other": .5, "coverage": 15, "upfront": 40}
        gate = budget_survivability_gate({"costEstimate": cost}, 4)
        self.assertEqual(gate["gapRange"], [4, 4])
        self.assertEqual(gate["status"], "PASS")
        cost["coverage"] = 100
        self.assertEqual(budget_survivability_gate({"costEstimate": cost}, 0)["gapRange"], [0, 0])
        del cost["housing"]
        self.assertEqual(budget_survivability_gate({"costEstimate": cost}, 4)["status"], "UNKNOWN")

    def test_seed_and_sat_target_never_prove_eligibility(self):
        route = {"id": "example", "satRole": "HIGH", "suggestedSatBenchmark": "1500+"}
        overlay = {"estimatedFamilyGapIdrMPerMonth": "0–2", "preGradApplyAllowed": "Yes"}
        result = evaluate(route, overlay, {"snapshot": {"maxFamilyContributionIdrMPerMonth": 4}}, 1560)
        self.assertEqual(result["sat"]["status"], "TARGET_MET")
        self.assertEqual(result["curriculum"]["status"], "UNKNOWN")
        self.assertEqual(result["graduation"]["status"], "UNKNOWN")
        self.assertEqual(result["overall"], "NEEDS_VERIFICATION")

    def test_program_cycle_and_graduation_document_cutoff(self):
        rule = {"cycle": "2027", "sourceUrl": "https://example.edu/call", "checkedAt": "2026-11-01", "program": "Engineering", "nationalCurriculumDirectEntry": True, "preGraduationApplicationAllowed": False, "finalDiplomaDeadline": "2027-05-01"}
        overlay = {"verifiedRules": rule}
        profile = {"snapshot": {"expectedGraduation": "June 2027"}}
        self.assertEqual(curriculum_gate(overlay)["status"], "PASS")
        self.assertEqual(graduation_gate(overlay, profile)["status"], "FAIL")
        rule["finalDiplomaDeadline"] = "2027-06-15"
        self.assertEqual(graduation_gate(overlay, profile)["status"], "UNKNOWN")
        rule["finalDiplomaDeadline"] = "2027-07-01"
        self.assertEqual(graduation_gate(overlay, profile)["status"], "PASS")
        rule["cycle"] = "2026"
        self.assertEqual(curriculum_gate(overlay)["status"], "UNKNOWN")


class BriefingChecks(unittest.TestCase):
    def setUp(self):
        self.payload = {"tasks": [{"id": str(i), "priority": i, "routeIds": [], "sources": []} for i in range(5)], "routes": [], "overlays": [], "state": {"tasks": {}}}

    def test_max_three_and_replacement_preserves_work(self):
        self.assertEqual([c["id"] for c in briefing(self.payload)["cards"]], ["0", "1", "2"])
        self.payload["state"]["tasks"]["0"] = {"replacedAt": "2026-11-01T00:00:00Z"}
        result = briefing(self.payload)
        self.assertEqual([c["id"] for c in result["cards"]], ["1", "2", "3"])
        self.assertEqual(result["remaining"], 5)

    def test_completed_snoozed_and_dropped_routes(self):
        self.payload["state"]["tasks"] = {"0": {"status": "DONE"}, "1": {"snoozedUntil": "2999-01-01T00:00:00Z"}}
        self.payload["tasks"][2].update({"requiresActiveRoute": True, "routeIds": ["r"]})
        self.payload["overlays"] = [{"routeId": "r", "applicationStatus": "DROP"}]
        result = briefing(self.payload)
        self.assertEqual([c["id"] for c in result["cards"]], ["3", "4"])
        self.assertEqual(result["completed"], 1)

    def test_active_routes_and_document_steps_continue_after_seed_tasks(self):
        payload = {"tasks": [], "routes": [{"id": "r", "institution": "Example University", "officialSourceUrl": "https://example.edu/call"}], "overlays": [{"routeId": "r", "applicationStatus": "IN_PROGRESS"}], "profile": {"snapshot": {}}, "bricks": [{"id": "school", "folder": "03_School_Documents", "items": [{"id": "transcript", "label": "Locate a transcript"}]}], "state": {"tasks": {}, "bricks": {}}}
        payload["tasks"] = task_pool(payload)
        result = briefing(payload)
        self.assertEqual(len(result["cards"]), 3)
        self.assertTrue(all(c["minutes"] <= 15 for c in result["cards"]))
        payload["overlays"][0]["applicationStatus"] = "DROP"
        payload["state"]["bricks"]["school:transcript"] = True
        self.assertEqual(briefing(payload)["cards"], [])


class MonitoringChecks(unittest.TestCase):
    def test_html_normalization_and_pdf_discovery(self):
        html = ("<html><script>private script noise</script><p>2027 engineering scholarship details and eligibility. " + "Benefits and instructions. " * 8 + '</p><a href="/call.pdf">Call</a></html>').encode()
        text, pdfs = normalize(html, "text/html", "https://example.edu/apply")
        self.assertNotIn("private script noise", text)
        self.assertEqual(pdfs, ["https://example.edu/call.pdf"])
        with self.assertRaises(ValueError):
            normalize(b"<h1>Access denied</h1>", "text/html", "https://example.edu/")

    def test_block_local_sources_and_redirect_targets(self):
        for url in ("file:///etc/passwd", "https://user:password@example.edu/", "http://127.0.0.1/", "http://[::1]/"):
            with self.assertRaises(ValueError): validate_public_url(url)

    def test_baseline_then_change_then_failure_preserves_hash(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            public = root / "data/public"
            public.mkdir(parents=True)
            (public / "scholarships_2027.json").write_text(json.dumps([{"id": "r", "officialSourceUrl": "https://example.edu/apply", "secondarySourceUrl": ""}]))
            first = {"text": "Engineering call 2027. " * 12, "pdfLinks": [], "finalUrl": "https://example.edu/apply"}
            with patch("schola.watcher.fetch", return_value=first): state = scan(root)
            self.assertEqual(state["events"][0]["kind"], "BASELINE")
            second = {**first, "text": "Deadline updated for engineering 2027. " * 12}
            with patch("schola.watcher.fetch", return_value=second): state = scan(root)
            self.assertEqual(state["events"][0]["kind"], "CHANGED")
            good_hash = state["sources"][first["finalUrl"]]["hash"]
            with patch("schola.watcher.fetch", side_effect=TimeoutError("timeout")): state = scan(root)
            self.assertEqual(state["sources"][first["finalUrl"]]["hash"], good_hash)
            self.assertEqual(state["sources"][first["finalUrl"]]["status"], "ERROR")
            self.assertEqual(state["summary"]["errors"], 1)


class PrivacyChecks(unittest.TestCase):
    def test_private_paths_identifiers_and_credentials(self):
        for path in ("private/a.json", "a.local.md", ".env.production"):
            self.assertIsNotNone(privacy.violation(path, b"safe"))
        for denied in privacy.DENIED:
            self.assertIsNotNone(privacy.violation("public.txt", denied.lower().encode()))
        self.assertIsNone(privacy.violation(".env.example", b"SCHOLA_PYTHON=python3"))
        self.assertIsNotNone(privacy.violation("image.png", b"\0binary"))

    def test_guard_reads_staged_blob_not_working_copy(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init", "-q", d], check=True)
            source = Path(d) / "example.txt"
            source.write_text(privacy.DENIED[0])
            subprocess.run(["git", "add", "example.txt"], cwd=d, check=True)
            source.write_text("safe working copy")
            result = subprocess.run(["python3", str(ROOT / "scripts/privacy_guard.py")], cwd=d, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn(privacy.DENIED[0].encode(), result.stderr)


if __name__ == "__main__":
    unittest.main()
