"""Offline integration checks for draft research, explicit acceptance and restore."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import uuid

from schola import assistant as a, catalogue as c, catalogue_api as api, workspace_store as w
from schola.drive_sync import export as mirror_export


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://www.monash.edu/fictional-fixture-scholarship"


class CatalogueFlowChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        shutil.copytree(ROOT / "data/public", self.root / "data/public")
        vault = self.root / "private"
        vault.mkdir(mode=0o700)
        environment = patch.dict(os.environ, {"STUDAB27_DEMO": "0"})
        environment.start()
        self.addCleanup(environment.stop)
        self.config = {"llm": {"baseUrl": "http://127.0.0.1:1234/v1", "model": "fictional-model", "apiKey": "fictional-test-key",
                                "maxToolRounds": 4, "researchRuntime": "builtin", "dailyCallLimit": 40},
                       "contextAllowed": True, "search": {"provider": "disabled"}, "background": {"enabled": False}}
        (vault / "schola.local.json").write_text(json.dumps(self.config))
        public_routes = json.loads((self.root / "data/public/scholarships_2027.json").read_text())
        self.original_route_id = public_routes[0]["id"]
        fixture = {"profile": {"snapshot": {"curriculum": "OWNER_ONLY_PROFILE_FIXTURE", "citizenship": "Indonesian",
                                             "expectedGraduation": "2027", "maxFamilyContributionIdrMPerMonth": 4}},
                   "overlays": [{"routeId": self.original_route_id, "tracked": True, "mainTarget": True, "pursuitLevel": "FOCUS",
                                  "notes": "OWNER_ONLY_PLAN_FIXTURE", "applicationStatus": "IN_PROGRESS"}],
                   "milestones": [], "inbox": [], "state": {"tasks": {}, "bricks": {}, "custom": "OWNER_ONLY_STATE_FIXTURE"}}
        for key, name in (("profile", "profile"), ("overlays", "overlay"), ("milestones", "milestones"), ("inbox", "inbox"), ("state", "state")):
            (vault / f"{name}.local.json").write_text(json.dumps(fixture[key]))
        self.before = w.load(self.root)
        self.fields = c.validate_fields({"country": "Australia", "institution": "Fictional Integration University",
                                         "scholarshipName": "Fictional Integration Award", "officialSourceUrl": SOURCE,
                                         "benefitsCoverage": "20% tuition; living costs UNKNOWN", "unresolvedQuestions": ["2027 call not established"]})
        # Any unpatched network operation fails this test suite immediately.
        network = patch.object(a, "json_request", side_effect=AssertionError("Unexpected real API request"))
        network.start()
        self.addCleanup(network.stop)

    def start(self):
        request = {"action": "start", "id": str(uuid.uuid4()), "query": "Fictional undergraduate engineering scholarship", "sourceUrl": SOURCE}
        return request, api.api(self.root, request)

    @staticmethod
    def call(name, arguments, call_id):
        return {"role": "assistant", "tool_calls": [{"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]}

    def replies(self, *, proposal_source=SOURCE):
        return [self.call("read_source", {"url": SOURCE}, "read-fixture"),
                self.call("propose_scholarship", {"fields": {**self.fields, "officialSourceUrl": proposal_source},
                                                 "sources": [{"url": proposal_source, "finding": "Partial tuition; living costs remain UNKNOWN."}]}, "propose-fixture"),
                {"role": "assistant", "content": "Research findings retained. A draft requires explicit owner review; eligibility remains UNKNOWN."}]

    def process(self, started, *, runtime="builtin", replies=None):
        captured, answers = [], iter(replies or self.replies())

        def complete(connection, config, messages, allow_tools=True):
            captured.append(messages)
            tools = {tool["function"]["name"] for tool in config["_toolSpecs"]}
            self.assertEqual(tools, {"search_catalogue", "search_web", "read_source", "propose_scholarship"})
            self.assertTrue(config["_draftMode"])
            for marker in ("OWNER_ONLY_PROFILE_FIXTURE", "OWNER_ONLY_PLAN_FIXTURE", "OWNER_ONLY_MEMORY_FIXTURE", "OWNER_ONLY_STATE_FIXTURE"):
                self.assertNotIn(marker, json.dumps(messages))
            return next(answers)

        config = {**self.config, "llm": {**self.config["llm"], "researchRuntime": runtime}}
        page = {"finalUrl": SOURCE, "text": "Fictional test page. Partial tuition of 20%. Living support and 2027 eligibility UNKNOWN.", "pdfLinks": [], "links": []}
        with closing(a.db(self.root)) as connection:
            connection.execute("INSERT INTO messages(role,content,created_at) VALUES('assistant',?,?)", ("OWNER_ONLY_MEMORY_FIXTURE", a.now()))
            job = connection.execute("SELECT * FROM jobs WHERE id=?", (started["jobId"],)).fetchone()
            with patch.object(a, "completion", side_effect=complete), patch.object(a, "fetch", return_value=page) as fetch:
                a.process_job(self.root, connection, job, config)
                self.assertEqual(fetch.call_count, 1)
            saved_job = connection.execute("SELECT status FROM jobs WHERE id=?", (started["jobId"],)).fetchone()
            self.assertEqual(saved_job["status"], "DONE")
        return captured

    def test_start_saves_lead_before_queue_and_repeated_delivery_is_idempotent(self):
        request, started = self.start()
        self.assertEqual(started["draft"]["status"], "RESEARCHING")
        self.assertEqual(started["draft"]["jobId"], started["jobId"])
        before = w.load(self.root)
        self.assertEqual(api.api(self.root, request), started)
        self.assertEqual(w.load(self.root), before)
        with closing(a.db(self.root)) as connection:
            job = connection.execute("SELECT * FROM jobs WHERE id=?", (started["jobId"],)).fetchone()
            self.assertEqual((job["kind"], job["status"]), ("scholarship-draft", "QUEUED"))
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 1)
            self.assertIn(SOURCE, job["prompt"])
        with self.assertRaises(ValueError):
            api.api(self.root, {**request, "query": "Different scholarship"})
        self.assertEqual(before["overlays"], self.before["overlays"])

    def test_repeated_start_after_proposal_and_source_edits_keeps_original_lead_identity(self):
        for original_url in ("", SOURCE):
            with self.subTest(original_url=original_url):
                request = {"action": "start", "id": str(uuid.uuid4()), "query": "Fictional original lead",
                           **({"sourceUrl": original_url} if original_url else {})}
                started = api.api(self.root, request)
                resolved_url = SOURCE + "/resolved"
                proposed = c.research_result(self.root, request["id"], started["jobId"],
                    {**self.fields, "officialSourceUrl": resolved_url},
                    [{"url": resolved_url, "checkedAt": "2026-11-16", "finding": "Fictional redirected source"}])
                edited = c.update_draft(self.root, request["id"], proposed["revision"],
                    {**proposed["fields"], "officialSourceUrl": SOURCE + "/owner-edited"})
                with closing(a.db(self.root)) as connection:
                    connection.execute("UPDATE jobs SET status='DONE' WHERE id=?", (started["jobId"],))
                    count = connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
                before = w.load(self.root)
                repeated = api.api(self.root, request)
                self.assertEqual(repeated["draft"], edited)
                self.assertEqual(repeated["jobId"], started["jobId"])
                self.assertEqual(w.load(self.root), before)
                with closing(a.db(self.root)) as connection:
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], count)

    def test_import_rejects_date_only_or_naive_draft_lifecycle_without_changing_state(self):
        request, _ = self.start()
        before = w.load(self.root)
        for field in ("createdAt", "updatedAt"):
            for value in ("2026-11-16", "2026-11-16T00:00:00", " 2026-11-16T00:00:00+00:00 "):
                with self.subTest(field=field, value=value):
                    imported = json.loads(json.dumps(before))
                    imported["state"]["scholarshipDrafts"][request["id"]][field] = value
                    with self.assertRaises(ValueError):
                        w.save(self.root, imported, before["revision"], before["mode"], backup=True)
                    self.assertEqual(w.load(self.root), before)
        self.assertEqual(api.api(self.root, {"action": "list"})["drafts"][0]["status"], "RESEARCHING")

    def test_builtin_proposal_uses_fetched_evidence_without_owner_memory_or_auto_add(self):
        _, started = self.start()
        captured = self.process(started)
        draft = c.get_draft(self.root, started["draft"]["id"])
        self.assertEqual(draft["status"], "READY")
        self.assertEqual(draft["sources"][0]["url"], SOURCE)
        self.assertIn("T", draft["sources"][0]["checkedAt"])
        self.assertEqual(draft["fields"]["indonesianApplicantNotes"], "UNKNOWN")
        self.assertTrue(any(message["role"] == "tool" for message in captured[-1]))
        self.assertNotIn("localScholarships", w.load(self.root)["state"])
        self.assertEqual(w.load(self.root)["overlays"], self.before["overlays"])

    @unittest.skipUnless(importlib.util.find_spec("langgraph"), "NOT RUN: use .venv-research/bin/python for LangGraph")
    def test_langgraph_saves_the_same_supported_reviewable_draft(self):
        _, started = self.start()
        self.process(started, runtime="langgraph")
        self.assertEqual(c.get_draft(self.root, started["draft"]["id"])["status"], "READY")
        self.assertNotIn("localScholarships", w.load(self.root)["state"])

    def reserved_proposal(self, runtime, retrieval_batches):
        _, started = self.start()
        config = {**self.config, "llm": {**self.config["llm"], "researchRuntime": runtime, "toolMode": "native"}}
        histories = []

        def complete(connection, current, messages, allow_tools=True):
            histories.append(messages)
            names = {tool["function"]["name"] for tool in current["_toolSpecs"]}
            self.assertTrue(allow_tools)
            self.assertEqual(current["llm"]["toolMode"], "native")
            index = len(histories) - 1
            if index < len(retrieval_batches):
                self.assertEqual(names, {"search_catalogue", "search_web", "read_source", "propose_scholarship"})
                calls = [self.call("read_source", {"url": SOURCE}, f"read-{index}-{number}")["tool_calls"][0]
                         for number in range(retrieval_batches[index])]
                return {"role": "assistant", "tool_calls": calls}
            self.assertEqual(index, len(retrieval_batches), "No extra inference after the reserved proposal")
            self.assertEqual(names, {"propose_scholarship"})
            return self.replies()[1]

        page = {"finalUrl": SOURCE, "text": "Fictional tuition evidence. Living costs and 2027 eligibility UNKNOWN.", "pdfLinks": [], "links": []}
        with closing(a.db(self.root)) as connection:
            job = connection.execute("SELECT * FROM jobs WHERE id=?", (started["jobId"],)).fetchone()
            with patch.object(a, "completion", side_effect=complete) as inference, patch.object(a, "fetch", return_value=page) as fetch:
                a.process_job(self.root, connection, job, config)
                self.assertEqual(inference.call_count, len(retrieval_batches) + 1)
                self.assertEqual(fetch.call_count, 1, "Repeated source reads must use the per-job cache")
            tool_names = [row["name"] for row in connection.execute("SELECT name FROM tools WHERE job_id=? ORDER BY id", (job["id"],))]
            actual_reads = min(11, sum(retrieval_batches))
            self.assertEqual(tool_names, ["read_source"] * actual_reads + ["propose_scholarship"])
            self.assertEqual(connection.execute("SELECT status FROM jobs WHERE id=?", (job["id"],)).fetchone()[0], "DONE")
        draft = c.get_draft(self.root, started["draft"]["id"])
        self.assertEqual(draft["status"], "READY")
        self.assertEqual(draft["sources"][0]["url"], SOURCE)
        self.assertIn("T", draft["sources"][0]["checkedAt"])
        self.assertNotIn("localScholarships", w.load(self.root)["state"])
        self.assertEqual(w.load(self.root)["overlays"], self.before["overlays"])
        results = [message for message in histories[-1] if message["role"] == "tool"]
        self.assertEqual(len(results), sum(retrieval_batches), "Every requested native tool call needs a protocol result")
        if retrieval_batches == [13]:
            self.assertEqual(len(tool_names), 12)
            self.assertEqual([json.loads(message["content"]).get("state") for message in results[-2:]],
                             ["BUDGET_RESERVED", "BUDGET_EXHAUSTED"])

    def test_builtin_exhausted_retrieval_budget_reserves_proposal(self):
        self.reserved_proposal("builtin", [13])

    @unittest.skipUnless(importlib.util.find_spec("langgraph"), "NOT RUN: use .venv-research/bin/python for LangGraph")
    def test_langgraph_exhausted_retrieval_budget_reserves_proposal(self):
        self.reserved_proposal("langgraph", [13])

    def test_builtin_final_configured_round_reserves_proposal(self):
        self.reserved_proposal("builtin", [1] * self.config["llm"]["maxToolRounds"])

    @unittest.skipUnless(importlib.util.find_spec("langgraph"), "NOT RUN: use .venv-research/bin/python for LangGraph")
    def test_langgraph_final_configured_round_reserves_proposal(self):
        self.reserved_proposal("langgraph", [1] * self.config["llm"]["maxToolRounds"])

    def test_model_cannot_read_owner_memory_or_invoke_owner_actions(self):
        _, started = self.start()
        for name in ("search_conversation", "inspect_route", "get_briefing", "accept_scholarship"):
            with self.subTest(tool=name), closing(a.db(self.root)) as connection:
                job = connection.execute("SELECT * FROM jobs WHERE id=?", (started["jobId"],)).fetchone()
                with patch.object(a, "completion", return_value=self.call(name, {}, "forbidden-tool")), patch.object(a, "fetch") as network:
                    with self.assertRaisesRegex(ValueError, "unavailable research tool"):
                        a.process_job(self.root, connection, job, self.config)
                    network.assert_not_called()
        self.assertEqual(c.get_draft(self.root, started["draft"]["id"])["status"], "RESEARCHING")
        self.assertNotIn("localScholarships", w.load(self.root)["state"])

    def test_explicit_accept_is_visible_in_local_context_and_roundtrips_export_restore(self):
        _, started = self.start()
        self.process(started)
        draft = c.get_draft(self.root, started["draft"]["id"])
        accepted = api.api(self.root, {"action": "accept", "id": draft["id"], "revision": draft["revision"]})
        route_id = accepted["routeId"]
        self.assertTrue(route_id.startswith("local-"))
        self.assertIn(route_id, {route["id"] for route in a.catalogue_routes(self.root)})
        self.assertEqual(a.validate_route_id(self.root, route_id), route_id)
        context = a.context(self.root, True, route_id)
        self.assertEqual([route["id"] for route in context["routes"]], [route_id])
        self.assertEqual(context["overlays"], [])
        self.assertNotIn(route_id, {route["id"] for route in a.context(self.root, False)["routes"]})
        current = w.load(self.root)
        self.assertEqual(current["overlays"], self.before["overlays"])
        exported = json.loads(w.encoded({"format": "studab27-v1", **current}))
        destination = mirror_export(self.root, self.root / "private/fixture-mirror")
        mirrored = json.loads((destination / "01_Catalogue/scholarships_2027.json").read_text())
        self.assertIn(route_id, {route["id"] for route in mirrored})
        restored_root = self.root / "restored"
        shutil.copytree(self.root / "data", restored_root / "data")
        restored_vault = restored_root / "private"
        restored_vault.mkdir(mode=0o700)
        for key, name in (("profile", "profile"), ("overlays", "overlay")):
            (restored_vault / f"{name}.local.json").write_text(json.dumps(self.before[key]))
        initial = w.load(restored_root)
        restored = w.save(restored_root, exported, initial["revision"], initial["mode"], backup=True)
        self.assertEqual(restored["state"], current["state"])
        self.assertEqual(restored["overlays"], self.before["overlays"])
        self.assertEqual(c.get_draft(restored_root, draft["id"])["status"], "ACCEPTED")
        self.assertIn(route_id, {route["id"] for route in a.catalogue_routes(restored_root)})

    def test_unread_proposal_source_fails_without_promoting_fabricated_evidence(self):
        _, started = self.start()
        histories = self.process(started, replies=self.replies(proposal_source="https://www.monash.edu/never-read-fixture"))
        draft = c.get_draft(self.root, started["draft"]["id"])
        self.assertEqual(draft["status"], "FAILED")
        self.assertEqual(draft["sources"], [])
        self.assertEqual(draft["fields"]["officialSourceUrl"], SOURCE)
        tool_results = [json.loads(message["content"]) for message in histories[-1] if message["role"] == "tool"]
        self.assertIn("read during this research", tool_results[-1]["error"])
        self.assertNotIn("localScholarships", w.load(self.root)["state"])

    def test_reconcile_preserves_fresh_orphan_and_recovers_old_or_terminal_leads(self):
        orphan_id = str(uuid.uuid4())
        orphan = c.create_draft(self.root, orphan_id, "Fictional orphan lead", "fixture-orphan-job", SOURCE)
        api.api(self.root, {"action": "list"})
        self.assertEqual(c.get_draft(self.root, orphan_id)["status"], "RESEARCHING")
        current = w.load(self.root)
        current["state"]["scholarshipDrafts"][orphan_id]["updatedAt"] = (datetime.now(timezone.utc) - timedelta(minutes=4)).isoformat()
        w.save(self.root, current, current["revision"], current["mode"])
        result = api.api(self.root, {"action": "list"})
        self.assertEqual(result["drafts"][0]["status"], "FAILED")
        self.assertEqual(c.get_draft(self.root, orphan_id)["fields"], orphan["fields"])
        _, started = self.start()
        with closing(a.db(self.root)) as connection:
            connection.execute("UPDATE jobs SET status='RUNNING' WHERE id=?", (started["jobId"],))
        # A restarted worker marks interrupted jobs; listing reconciles the lead.
        a.worker(self.root, once=True)
        api.api(self.root, {"action": "list"})
        self.assertEqual(c.get_draft(self.root, started["draft"]["id"])["status"], "FAILED")

    def test_configuration_and_queue_failures_preserve_the_saved_lead(self):
        for target, error in (("model_settings", ValueError("Missing fictional configuration")),
                              ("enqueue", ValueError("Another message is already running")),
                              ("enqueue", RuntimeError("Fictional queue failure"))):
            request = {"action": "start", "id": str(uuid.uuid4()), "query": "Fictional lead to preserve", "sourceUrl": SOURCE}
            with self.subTest(target=target, error=type(error).__name__), patch.object(a, target, side_effect=error):
                with self.assertRaises(type(error)):
                    api.api(self.root, request)
            saved = c.get_draft(self.root, request["id"])
            self.assertEqual(saved["status"], "FAILED")
            self.assertEqual(saved["query"], request["query"])
            self.assertEqual(saved["fields"]["officialSourceUrl"], SOURCE)
        self.assertEqual(w.load(self.root)["overlays"], self.before["overlays"])
        with closing(a.db(self.root)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 0)

    def test_provider_failure_marks_job_and_lead_failed_without_losing_input(self):
        _, started = self.start()
        with patch.object(a, "completion", side_effect=ValueError("Fictional provider unavailable")), patch.object(a, "fetch") as network:
            a.worker(self.root, once=True)
            network.assert_not_called()
        saved = c.get_draft(self.root, started["draft"]["id"])
        self.assertEqual(saved["status"], "FAILED")
        self.assertEqual(saved["fields"]["officialSourceUrl"], SOURCE)
        with closing(a.db(self.root)) as connection:
            self.assertEqual(connection.execute("SELECT status FROM jobs WHERE id=?", (started["jobId"],)).fetchone()[0], "FAILED")


if __name__ == "__main__":
    unittest.main()
