from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import copy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from schola import workspace_store as w


class WorkspaceStoreChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.vault = self.root / "private"
        self.public = self.root / "data/public"
        self.vault.mkdir(mode=0o700)
        self.public.mkdir(parents=True)
        environment = patch.dict(os.environ, {"STUDAB27_DEMO": "0"})
        environment.start()
        self.addCleanup(environment.stop)
        self.fixture = {
            "profile": {"snapshot": {"curriculum": "Fictional fixture", "empty": ""}, "unknown": {"preserve": [None, False, "日本語"]}},
            "overlays": [
                {"routeId": "retired-scholarship", "tracked": False, "mainTarget": False, "notes": "Retain older route notes", "unknown": {"nested": []}},
                {"routeId": "fictional-current", "tracked": True, "mainTarget": True, "pursuitLevel": "FOCUS", "notes": ""},
                {"routeId": "retired-empty-progress", "tracked": False},
            ],
            "milestones": [{"title": "Fixture milestone", "date": "2027-02-01", "custom": None}],
            "state": {
                "tasks": {"retired-task": {"status": "DONE", "custom": "old completion"}, "empty-task": {}},
                "bricks": {"retired-pack:retired-file": True, "fixture:empty": False},
                "requirements": {
                    "retired-scholarship": {"retired-guide-step": {"status": "DONE", "note": "", "evidence": ["fictional"]}},
                    "retired-empty-progress": {},
                },
                "updatedAt": "2026-11-07T00:00:00Z",
                "custom": {"empty": {}, "list": [], "null": None},
            },
            "inbox": [{"id": "fixture-1", "text": "Fictional inbox only", "createdAt": "2026-11-07", "status": "NEW", "custom": "retain"}],
        }
        self.write_legacy(self.fixture)
        self.demo_profile = {"snapshot": {"curriculum": "Fictional public demo"}}
        self.demo_overlays = [{"routeId": "demo-route", "tracked": False}]
        self.write_json(self.public / "profile.example.json", self.demo_profile)
        self.write_json(self.public / "overlay.example.json", self.demo_overlays)

    @staticmethod
    def write_json(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=3) + "\n", encoding="utf-8")

    def write_legacy(self, value):
        for key, filename in (("profile", "profile"), ("overlays", "overlay"), ("milestones", "milestones"), ("state", "state"), ("inbox", "inbox")):
            self.write_json(self.vault / f"{filename}.local.json", value[key])

    def assert_workspace(self, actual, expected):
        self.assertEqual({key: actual[key] for key in w.DATA_KEYS}, {key: expected[key] for key in w.DATA_KEYS})

    def test_legacy_migration_preserves_every_field_and_original_file(self):
        originals = {path.name: path.read_bytes() for path in self.vault.glob("*.local.json")}
        result = w.load(self.root)
        self.assertEqual((result["mode"], result["revision"]), ("PRIVATE", 1))
        self.assert_workspace(result, self.fixture)
        self.assert_workspace(w.load(self.root), self.fixture)
        self.assertEqual({name: (self.vault / name).read_bytes() for name in originals}, originals)
        seeds = list((self.vault / "backups").glob("workspace-seed-*.local.json"))
        self.assertEqual(len(seeds), 1)
        self.assert_workspace(json.loads(seeds[0].read_text()), self.fixture)
        with closing(sqlite3.connect(w.database_path(self.root))) as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_empty_requirements_object_and_empty_route_maps_roundtrip(self):
        self.fixture["state"]["requirements"] = {}
        self.write_legacy(self.fixture)
        current = w.load(self.root)
        self.assert_workspace(current, self.fixture)
        current["state"]["requirements"] = {"retired-scholarship": {}, "retired-empty-progress": {}}
        saved = w.save(self.root, current, current["revision"], current["mode"])
        self.assertEqual(saved["state"]["requirements"], current["state"]["requirements"])

    def test_transaction_failure_rolls_back_all_entities_and_revision(self):
        before = w.load(self.root)
        changed = copy.deepcopy(before)
        changed["profile"]["snapshot"]["curriculum"] = "Do not commit"
        changed["overlays"][0]["notes"] = "Do not commit"
        changed["state"]["tasks"] = {}
        real_write_rows = w._write_rows

        def interrupt_after_rows(connection, value, revision):
            real_write_rows(connection, value, revision)
            raise RuntimeError("Fictional interrupted import")

        with patch.object(w, "_write_rows", interrupt_after_rows):
            with self.assertRaisesRegex(RuntimeError, "interrupted import"):
                w.save(self.root, changed, before["revision"], before["mode"], backup=True)
        self.assertEqual(w.load(self.root), before)
        backup = list((self.vault / "backups").glob("before-import-*.local.json"))
        self.assertEqual(len(backup), 1)
        self.assert_workspace(json.loads(backup[0].read_text()), before)

    def test_concurrent_stale_saves_have_one_winner_without_mixed_records(self):
        before = w.load(self.root)
        barrier = threading.Barrier(2)

        def save_marker(marker):
            candidate = copy.deepcopy(before)
            candidate["profile"]["snapshot"]["marker"] = marker
            candidate["overlays"][0]["marker"] = marker
            candidate["state"]["marker"] = marker
            barrier.wait(timeout=5)
            try:
                return w.save(self.root, candidate, before["revision"], before["mode"])
            except w.Conflict:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save_marker, ("first", "second")))
        winners = [result for result in results if result is not None]
        self.assertEqual(len(winners), 1)
        current = w.load(self.root)
        self.assertEqual(current, winners[0])
        self.assertEqual(current["revision"], before["revision"] + 1)
        self.assertEqual(current["profile"]["snapshot"]["marker"], current["overlays"][0]["marker"])
        self.assertEqual(current["profile"]["snapshot"]["marker"], current["state"]["marker"])

    def test_hard_process_exit_before_commit_preserves_complete_previous_snapshot(self):
        before = w.load(self.root)
        interrupted_writer = r'''
import os, pathlib, sys
from schola import workspace_store as w
root = pathlib.Path(sys.argv[1])
current = w.load(root)
current["profile"]["snapshot"]["curriculum"] = "Never commit interrupted fixture"
current["overlays"][0]["notes"] = "Never commit interrupted fixture"
current["state"]["tasks"] = {}
real_write = w._write_rows
def terminate_after_writes(connection, value, revision):
    real_write(connection, value, revision)
    os._exit(91)
w._write_rows = terminate_after_writes
w.save(root, current, current["revision"], current["mode"])
'''
        result = subprocess.run([sys.executable, "-c", interrupted_writer, str(self.root)], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 91, result.stderr)
        self.assertEqual(w.load(self.root), before)
        with closing(sqlite3.connect(w.database_path(self.root))) as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_read_snapshots_remain_consistent_while_another_connection_commits(self):
        current = w.load(self.root)
        current["profile"]["snapshot"]["marker"] = 0
        current["overlays"][0]["marker"] = 0
        current["state"]["marker"] = 0
        current = w.save(self.root, current, current["revision"], current["mode"])
        barrier = threading.Barrier(2)

        def writer():
            value = current
            barrier.wait(timeout=5)
            for marker in range(1, 16):
                candidate = copy.deepcopy(value)
                candidate["profile"]["snapshot"]["marker"] = marker
                candidate["overlays"][0]["marker"] = marker
                candidate["state"]["marker"] = marker
                value = w.save(self.root, candidate, value["revision"], value["mode"])
            return value

        def reader():
            barrier.wait(timeout=5)
            for _ in range(30):
                value = w.snapshot_if_initialized(self.root)
                self.assertEqual(value["profile"]["snapshot"]["marker"], value["overlays"][0]["marker"])
                self.assertEqual(value["profile"]["snapshot"]["marker"], value["state"]["marker"])

        with ThreadPoolExecutor(max_workers=2) as pool:
            writing, reading = pool.submit(writer), pool.submit(reader)
            final = writing.result(timeout=15)
            reading.result(timeout=15)
        self.assertEqual(w.load(self.root), final)

    def test_forced_demo_cannot_read_write_or_activate_owner_database(self):
        owner = w.load(self.root)
        with patch.dict(os.environ, {"STUDAB27_DEMO": "1"}):
            demo = w.load(self.root)
            self.assertEqual(demo["mode"], "DEMO")
            self.assertEqual(demo["profile"], self.demo_profile)
            self.assertEqual(demo["overlays"], self.demo_overlays)
            self.assertNotEqual(w.database_path(self.root).name, "workspace.sqlite3")
            demo["profile"]["snapshot"]["curriculum"] = "Changed demo only"
            w.save(self.root, demo, demo["revision"], demo["mode"])
            with self.assertRaises(ValueError):
                w.save(self.root, demo, demo["revision"] + 1, demo["mode"], target_mode="PRIVATE")
        self.assertEqual(w.load(self.root), owner)

    def test_explicit_private_bootstrap_activates_existing_normal_demo(self):
        (self.vault / "profile.local.json").unlink()
        (self.vault / "overlay.local.json").unlink()
        demo = w.load(self.root)
        self.assertEqual(demo["mode"], "DEMO")
        self.write_legacy(self.fixture)
        activated = w.load(self.root)
        self.assertEqual((activated["mode"], activated["revision"]), ("PRIVATE", demo["revision"] + 1))
        self.assert_workspace(activated, self.fixture)
        self.assertTrue(list((self.vault / "backups").glob("before-import-*.local.json")))

    def test_larger_legal_inbox_export_can_be_saved_without_truncation(self):
        self.fixture["inbox"] = [{"id": f"fictional-{index}", "text": "x" * 4000, "status": "NEW", "createdAt": "2026-11-07"} for index in range(400)]
        self.write_legacy(self.fixture)
        original = w.load(self.root)
        exported = w.encoded({"format": "studab27-v1", **original})
        self.assertGreater(len(exported.encode()), 1_500_000)
        imported = w.save(self.root, json.loads(exported), original["revision"], original["mode"], backup=True)
        self.assert_workspace(imported, self.fixture)

    def test_future_schema_and_partial_private_vault_fail_without_replacing_records(self):
        current = w.load(self.root)
        with closing(sqlite3.connect(w.database_path(self.root))) as connection:
            connection.execute("PRAGMA user_version=99")
        with self.assertRaises(ValueError):
            w.load(self.root)
        with self.assertRaises(ValueError):
            w.save(self.root, current, current["revision"], current["mode"])
        with self.assertRaises(ValueError):
            w.snapshot_if_initialized(self.root)
        with closing(sqlite3.connect(w.database_path(self.root))) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 99)
            self.assertEqual(json.loads(connection.execute("SELECT body FROM profile").fetchone()[0]), current["profile"])
        second_root = self.root / "incomplete"
        (second_root / "private").mkdir(parents=True)
        original = b'{"snapshot":{"curriculum":"Preserve incomplete owner fixture"}}'
        (second_root / "private/profile.local.json").write_bytes(original)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            w.load(second_root)
        self.assertEqual((second_root / "private/profile.local.json").read_bytes(), original)

    def test_schema_rejects_missing_json_identity_status_and_invalid_main_target(self):
        w.load(self.root)
        with closing(w.connect(w.database_path(self.root))) as connection:
            invalid = [
                ("INSERT INTO route_plans(route_id,position,body) VALUES(?,?,?)", ("missing-id", 20, '{}')),
                ("INSERT INTO route_plans(route_id,position,body) VALUES(?,?,?)", ("bad-main", 21, '{"routeId":"bad-main","mainTarget":true,"tracked":true}')),
                ("INSERT INTO inbox(id,position,body) VALUES(?,?,?)", ("missing-status", 20, '{"id":"missing-status","text":"fixture"}')),
                ("INSERT INTO requirement_progress(route_id,item_id,body) VALUES(?,?,?)", ("retired-scholarship", "missing-status", '{}')),
            ]
            for statement, parameters in invalid:
                with self.subTest(statement=statement, parameters=parameters):
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(statement, parameters)


if __name__ == "__main__":
    unittest.main()
