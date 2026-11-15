from concurrent.futures import ThreadPoolExecutor
import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid

from schola import catalogue as c, workspace_store as w


class CatalogueChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        vault = self.root / "private"
        public = self.root / "data/public"
        vault.mkdir(mode=0o700)
        public.mkdir(parents=True)
        environment = patch.dict(os.environ, {"STUDAB27_DEMO": "0"})
        environment.start()
        self.addCleanup(environment.stop)
        self.public_routes = [{"id": "fixture-public", "country": "Fictional", "institution": "Example University", "scholarshipName": "Existing Award"}]
        self.fixture = {
            "profile": {"snapshot": {"curriculum": "Fictional"}},
            "overlays": [{"routeId": "fixture-public", "tracked": True, "mainTarget": True, "pursuitLevel": "FOCUS", "notes": "Keep this plan"}],
            "milestones": [{"title": "Keep this milestone", "date": "2027-03-01"}],
            "inbox": [{"id": "fixture-inbox", "text": "Keep this capture", "status": "NEW"}],
            "state": {"tasks": {"fixture-task": {"status": "DONE"}}, "bricks": {"fixture:doc": True},
                      "requirements": {"fixture-public": {"fixture-step": {"status": "DONE", "note": "Keep this progress"}}},
                      "custom": {"unknown": [None, False, "日本語"]}},
        }
        for key, name in (("profile", "profile"), ("overlays", "overlay"), ("milestones", "milestones"), ("inbox", "inbox"), ("state", "state")):
            (vault / f"{name}.local.json").write_text(json.dumps(self.fixture[key]))
        (public / "scholarships_2027.json").write_text(json.dumps(self.public_routes))
        self.fields = c.validate_fields({"country": "Fictional", "institution": "Example University", "scholarshipName": "New Undergraduate Award",
                                         "officialSourceUrl": "https://university.edu/scholarships", "benefitsCoverage": "Tuition; living costs UNKNOWN",
                                         "unresolvedQuestions": ["2027 cycle requirements"]})
        self.sources = [{"url": self.fields["officialSourceUrl"], "title": "Fictional source", "finding": "Tuition; living costs not established", "checkedAt": "2026-11-15"}]

    def ready(self, fields=None):
        draft_id = str(uuid.uuid4())
        draft = c.create_draft(self.root, draft_id, "Fictional undergraduate scholarship", "fixture-job-" + draft_id)
        return c.research_result(self.root, draft_id, draft["jobId"], fields or self.fields, self.sources)

    def test_read_without_catalogue_does_not_add_optional_state(self):
        before = w.load(self.root)
        self.assertEqual(c.list_drafts(self.root), [])
        self.assertIsNone(c.get_draft(self.root, str(uuid.uuid4())))
        self.assertEqual(w.load(self.root), before)
        c.validate_catalogue_state(before["state"])

    def test_pending_draft_survives_reload_and_repeated_create(self):
        draft_id = uuid.uuid4().hex
        first = c.create_draft(self.root, draft_id, "Fictional scholarship", "fixture-job")
        before = w.load(self.root)
        self.assertEqual(c.create_draft(self.root, draft_id, "Fictional scholarship", "fixture-job"), first)
        self.assertEqual(w.load(self.root), before)
        self.assertEqual(c.get_draft(self.root, draft_id), first)
        self.assertEqual(first["fields"]["benefitsCoverage"], "UNKNOWN")
        with self.assertRaises(ValueError):
            c.create_draft(self.root, draft_id, "A different request", "fixture-job")

    def test_research_does_not_add_route_until_explicit_acceptance(self):
        ready = self.ready()
        self.assertEqual(ready["status"], "READY")
        self.assertNotIn("localScholarships", w.load(self.root)["state"])
        self.assertEqual(ready["matches"][0]["kind"], "POSSIBLE")
        accepted = c.accept_draft(self.root, ready["id"], ready["revision"])
        self.assertFalse(accepted["duplicate"])
        route = w.load(self.root)["state"]["localScholarships"][accepted["routeId"]]
        self.assertEqual(route["id"], "local-" + ready["id"])
        self.assertEqual(route["deadlineWindow2027"], "UNKNOWN")
        self.assertEqual(route["satRole"], "UNKNOWN")
        self.assertEqual(route["benefitsCoverage"], self.fields["benefitsCoverage"])
        self.assertNotIn("applicationGuide", route)
        self.assertNotIn("scholarshipOutlook", route)
        self.assertEqual(len(c.all_routes(self.root)), 2)
        before = w.load(self.root)
        self.assertEqual(c.accept_draft(self.root, ready["id"], ready["revision"]), accepted)
        self.assertEqual(w.load(self.root), before)

    def test_exact_public_duplicate_is_noop_but_distinct_award_is_allowed(self):
        fields = {**self.fields, "institution": "EXAMPLE  UNIVERSITY", "scholarshipName": "Existing-Award"}
        ready = self.ready(fields)
        self.assertEqual(ready["matches"][0]["kind"], "EXACT")
        before = w.load(self.root)
        duplicate = c.accept_draft(self.root, ready["id"], ready["revision"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(duplicate["routeId"], "fixture-public")
        self.assertEqual(w.load(self.root), before)
        edited = c.update_draft(self.root, ready["id"], ready["revision"], {**fields, "scholarshipName": "Distinct Engineering Award"})
        self.assertFalse(c.accept_draft(self.root, edited["id"], edited["revision"])["duplicate"])

    def test_exact_local_duplicate_does_not_create_another_record(self):
        first = self.ready()
        accepted = c.accept_draft(self.root, first["id"], first["revision"])
        second = self.ready()
        result = c.accept_draft(self.root, second["id"], second["revision"])
        self.assertTrue(result["duplicate"])
        self.assertEqual(result["routeId"], accepted["routeId"])
        self.assertEqual(len(w.load(self.root)["state"]["localScholarships"]), 1)

    def test_institution_variants_and_shared_source_warn_without_merging_awards(self):
        route = {**self.public_routes[0], "officialSourceUrl": self.fields["officialSourceUrl"]}
        variant = {**self.fields, "institution": "Example University (Faculty of Engineering)"}
        self.assertEqual(c._matches(variant, [route])[0]["kind"], "POSSIBLE")
        shared = {**self.fields, "institution": "Different Sponsor", "scholarshipName": "Distinct Award"}
        self.assertEqual(c._matches(shared, [route])[0]["kind"], "POSSIBLE")
        unrelated = {**shared, "officialSourceUrl": "https://another.edu/distinct"}
        self.assertEqual(c._matches(unrelated, [route]), [])

    def test_pending_draft_rejects_edit_and_completed_edit_rejects_stale_results(self):
        draft = c.create_draft(self.root, str(uuid.uuid4()), "Fictional undergraduate funding", "fixture-job")
        with self.assertRaises(ValueError):
            c.update_draft(self.root, draft["id"], draft["revision"], self.fields)
        ready = c.research_result(self.root, draft["id"], draft["jobId"], self.fields, self.sources)
        edited = c.update_draft(self.root, draft["id"], ready["revision"], self.fields)
        for revision in (None, False, 0):
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                c.update_draft(self.root, draft["id"], revision, self.fields)
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                c.accept_draft(self.root, draft["id"], revision)
        with self.assertRaises(w.Conflict):
            c.research_result(self.root, draft["id"], draft["jobId"], {**self.fields, "benefitsCoverage": "Must not replace"}, self.sources)
        with self.assertRaises(w.Conflict):
            c.update_draft(self.root, draft["id"], draft["revision"], self.fields)
        self.assertEqual(c.fail_draft(self.root, draft["id"], draft["jobId"], "Late failure"), edited)
        self.assertEqual(c.get_draft(self.root, draft["id"]), edited)

    def test_explicit_retry_retains_draft_and_rejects_previous_job_result(self):
        ready = self.ready()
        retried = c.retry_draft(self.root, ready["id"], ready["revision"], "fixture-retry-job")
        self.assertEqual(retried["status"], "RESEARCHING")
        self.assertEqual(retried["fields"], ready["fields"])
        self.assertEqual(retried["sources"], ready["sources"])
        self.assertEqual(retried["revision"], ready["revision"] + 1)
        with self.assertRaises(w.Conflict):
            c.research_result(self.root, ready["id"], ready["jobId"], self.fields, self.sources)
        with self.assertRaises(ValueError):
            c.retry_draft(self.root, retried["id"], retried["revision"], "another-job")
        completed = c.research_result(self.root, retried["id"], retried["jobId"], self.fields, self.sources)
        accepted = c.accept_draft(self.root, completed["id"], completed["revision"])
        with self.assertRaises(ValueError):
            c.retry_draft(self.root, completed["id"], accepted["draft"]["revision"], "final-job")

    def test_wrong_job_and_unread_proposal_url_are_rejected_without_mutation(self):
        draft = c.create_draft(self.root, str(uuid.uuid4()), "Fictional undergraduate funding", "fixture-job")
        before = w.load(self.root)
        with self.assertRaises(w.Conflict):
            c.research_result(self.root, draft["id"], "another-job", self.fields, self.sources)
        with self.assertRaises(ValueError):
            c.research_result(self.root, draft["id"], draft["jobId"], {**self.fields, "officialSourceUrl": "https://unread.edu/award"}, self.sources)
        self.assertEqual(w.load(self.root), before)

    def test_failure_keeps_partial_input_and_can_be_manually_completed(self):
        draft = c.create_draft(self.root, str(uuid.uuid4()), "Fictional undergraduate funding", "fixture-job", self.fields["officialSourceUrl"])
        failed = c.fail_draft(self.root, draft["id"], draft["jobId"], "Official page unreadable")
        self.assertEqual(failed["status"], "FAILED")
        self.assertEqual(failed["fields"]["officialSourceUrl"], self.fields["officialSourceUrl"])
        with self.assertRaises(ValueError):
            c.accept_draft(self.root, failed["id"], failed["revision"])
        ready = c.update_draft(self.root, failed["id"], failed["revision"], self.fields)
        self.assertNotIn("error", ready)
        self.assertFalse(c.accept_draft(self.root, ready["id"], ready["revision"])["duplicate"])

    def test_export_restore_roundtrip_preserves_local_catalogue_and_owner_plan(self):
        before = w.load(self.root)
        ready = self.ready()
        c.accept_draft(self.root, ready["id"], ready["revision"])
        exported = json.loads(w.encoded({"format": "studab27-v1", **w.load(self.root)}))
        for key in ("profile", "overlays", "milestones", "inbox"):
            self.assertEqual(exported[key], before[key])
        for key in before["state"]:
            self.assertEqual(exported["state"][key], before["state"][key])
        current = w.load(self.root)
        restored = w.save(self.root, exported, current["revision"], current["mode"], backup=True)
        self.assertEqual(restored["state"], exported["state"])
        c.validate_catalogue_state(restored["state"], self.public_routes)
        self.assertEqual(c.get_draft(self.root, ready["id"])["status"], "ACCEPTED")

    def test_concurrent_workspace_write_cannot_be_lost_during_acceptance(self):
        ready = self.ready()
        original_save = w.save
        barrier = threading.Barrier(2)

        def coordinated_save(*args, **kwargs):
            barrier.wait(timeout=5)
            return original_save(*args, **kwargs)

        def accept():
            try:
                return c.accept_draft(self.root, ready["id"], ready["revision"])
            except w.Conflict:
                return None

        def write_plan():
            current = w.load(self.root)
            current["overlays"][0]["notes"] = "Concurrent plan change"
            try:
                return w.save(self.root, current, current["revision"], current["mode"])
            except w.Conflict:
                return None

        with patch.object(w, "save", coordinated_save), ThreadPoolExecutor(max_workers=2) as pool:
            accepting, writing = pool.submit(accept), pool.submit(write_plan)
            accepted, written = accepting.result(timeout=10), writing.result(timeout=10)
        self.assertEqual(sum(result is not None for result in (accepted, written)), 1)
        final = w.load(self.root)
        if written:
            self.assertEqual(final["overlays"][0]["notes"], "Concurrent plan change")
            self.assertNotIn("localScholarships", final["state"])
        else:
            self.assertEqual(final["overlays"][0]["notes"], "Keep this plan")
            self.assertEqual(len(final["state"]["localScholarships"]), 1)

    def test_invalid_fields_and_private_urls_fail_closed(self):
        bad_urls = ["http://localhost:3270/", "http://127.0.0.1/", "http://127.1/", "http://[::1]/", "http://10.0.0.2/",
                    "http://169.254.169.254/", "http://server.local/", "http://localhost./", "https://owner:secret@university.edu/",
                    "file:///etc/passwd", "https://drive.google.com/file/d/private", "https://calendar.google.com/calendar/u/0/",
                    "https://docs.google.com/document/d/private", "https://university.edu/?api_key=private",
                    "https://university.edu/#access_token=private", "https://university.edu\\@localhost/", "https://university.edu:8443/",
                    "https://university.invalid/", "https://university.test/", "https://university.example/", "http://224.0.0.1/"]
        for url in bad_urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                c.validate_fields({"officialSourceUrl": url})
        for fields in ({"benefitsCoverage": {"invented": True}}, {"unresolvedQuestions": "not a list"}, {"institution": "x" * 301},
                       {"__proto__": {}}, {"applicationGuide": {}}, {"benefitsCoverage": 1}, {"unresolvedQuestions": [None]}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                c.validate_fields(fields)
        for url in ("https://university.edu/award#eligibility", "https://university.edu/award?year=2027", "https://8.8.8.8/award"):
            self.assertEqual(c.public_source_url(url), url)

    def test_import_rejects_shadowed_ids_corrupt_drafts_and_injected_dates(self):
        ready = self.ready()
        c.accept_draft(self.root, ready["id"], ready["revision"])
        state = w.load(self.root)["state"]
        changed = copy.deepcopy(state)
        changed["localScholarships"]["fixture-public"] = next(iter(changed["localScholarships"].values()))
        with self.assertRaises(ValueError):
            c.validate_catalogue_state(changed, self.public_routes)
        for mutate in (
            lambda item: item["scholarshipDrafts"][ready["id"]].update(revision=True),
            lambda item: item["scholarshipDrafts"][ready["id"]].update(status=[]),
            lambda item: item["scholarshipDrafts"][ready["id"]].update(acceptedRouteId="missing-route"),
            lambda item: item["scholarshipDrafts"][ready["id"]]["fields"].update(institution="Different University"),
            lambda item: item["localScholarships"]["local-" + ready["id"]].update(applicationGuide={"cycle": "2027"}),
            lambda item: item["localScholarships"]["local-" + ready["id"]].update(officialSourceUrl="http://localhost/"),
            lambda item: item["localScholarships"]["local-" + ready["id"]]["fieldReview"]["benefitsCoverage"].update(status="HUMAN_VERIFIED"),
            lambda item: item["localScholarships"]["local-" + ready["id"]]["fieldReview"]["benefitsCoverage"].update(evidence=[self.sources[0]]),
        ):
            changed = copy.deepcopy(state)
            mutate(changed)
            with self.assertRaises(ValueError):
                c.validate_catalogue_state(changed, self.public_routes)
        self.assertEqual(w.load(self.root)["state"], state)


if __name__ == "__main__":
    unittest.main()
