from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from schola import assistant as a
from schola import workspace_store
from schola.database import BUSY_TIMEOUT_MS, connect


ROOT = Path(__file__).resolve().parents[1]


class ConversationDatabaseChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "data", self.root / "data")
        (self.root / "private").mkdir()
        self.path = self.root / "private/schola.sqlite3"
        self.config = {"llm": {"baseUrl": "http://127.0.0.1:1234/v1", "model": "fixture", "apiKey": "fixture-secret"}}
        (self.root / "private/schola.local.json").write_text(json.dumps(self.config))

    def test_connection_policy_constraints_and_future_schema_fail_closed(self):
        with closing(a.db(self.root)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], a.CHAT_SCHEMA_VERSION)
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA synchronous").fetchone()[0], 2)
            self.assertEqual(connection.execute("PRAGMA busy_timeout").fetchone()[0], BUSY_TIMEOUT_MS)
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            for statement in (
                "INSERT INTO messages(role,content,job_id,created_at) VALUES('user','saved','missing','date')",
                "INSERT INTO jobs VALUES('invalid-status','chat','saved','INVALID',NULL,'date','date')",
                "INSERT INTO calls VALUES('2026-01-01',-1)",
            ):
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(statement)
            connection.execute("PRAGMA user_version=999")
            connection.execute("PRAGMA journal_mode=DELETE")
        with self.assertRaisesRegex(ValueError, "newer"):
            a.db(self.root)
        with closing(connect(self.path, readonly=True)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 999)
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "delete")
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("DELETE FROM jobs")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_restored_current_schema_reenables_wal_after_version_validation(self):
        with closing(a.db(self.root)) as connection:
            a.enqueue(connection, "Restored history", "restored-message-0001")
            connection.execute("PRAGMA journal_mode=DELETE")
        with closing(a.db(self.root)) as connection:
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            self.assertEqual(connection.execute("SELECT content FROM messages").fetchone()[0], "Restored history")

    def test_legacy_orphan_history_is_preserved_and_recovery_copy_is_complete(self):
        with closing(sqlite3.connect(self.path)) as connection:
            connection.executescript("""
                CREATE TABLE jobs(id TEXT PRIMARY KEY,kind TEXT NOT NULL,prompt TEXT NOT NULL,status TEXT NOT NULL,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
                CREATE TABLE messages(id INTEGER PRIMARY KEY,role TEXT NOT NULL,content TEXT NOT NULL,job_id TEXT,created_at TEXT NOT NULL,meta TEXT NOT NULL DEFAULT '{}');
                CREATE TABLE tools(id INTEGER PRIMARY KEY,job_id TEXT,name TEXT,summary TEXT,created_at TEXT NOT NULL);
                INSERT INTO jobs VALUES('legacy-live-0001','chat','Original question','DONE',NULL,'2026-01-01','2026-01-02');
                INSERT INTO messages VALUES(7,'user','Original question','legacy-live-0001','2026-01-01','{}');
                INSERT INTO messages VALUES(19,'assistant','Retain orphan answer','legacy-missing-0001','2026-01-03','{"sources":[]}');
                INSERT INTO tools VALUES(31,'legacy-missing-0001','read_source','Retain orphan provenance','2026-01-03');
            """)
            before = {name: connection.execute(f"SELECT * FROM {name} ORDER BY 1").fetchall() for name in ("jobs", "messages", "tools")}
        state = a.api(self.root, {})
        self.assertEqual([row["id"] for row in state["messages"]], [7, 19])
        self.assertEqual([row["id"] for row in state["jobs"]], ["legacy-live-0001"])
        with closing(a.db(self.root)) as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(connection.execute("SELECT status FROM jobs WHERE id='legacy-missing-0001'").fetchone()[0], "DONE")
            for name in ("messages", "tools"):
                columns = "id,role,content,job_id,created_at,meta" if name == "messages" else "id,job_id,name,summary,created_at"
                self.assertEqual([tuple(row) for row in connection.execute(f"SELECT {columns} FROM {name} ORDER BY id")], before[name])
        backups = list((self.root / "private/backups").glob("*.sqlite3"))
        self.assertEqual(len(backups), 1)
        with closing(connect(backups[0], readonly=True)) as connection:
            self.assertEqual(connection.execute("PRAGMA quick_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 0)
            for name in before:
                self.assertEqual([tuple(row) for row in connection.execute(f"SELECT * FROM {name} ORDER BY 1")], before[name])
        with self.assertRaisesRegex(ValueError, "not available"):
            a.api(self.root, {"action": "retry", "jobId": "legacy-missing-0001"})
        a.api(self.root, {})
        self.assertEqual(len(list((self.root / "private/backups").glob("*.sqlite3"))), 1)

    def test_current_schema_status_does_not_acquire_writer_lock(self):
        with closing(a.db(self.root)) as writer:
            writer.execute("BEGIN IMMEDIATE")
            try:
                # This would time out if status performed migrations/DDL or
                # BEGIN IMMEDIATE on every read, as the legacy initializer did.
                state = a.api(self.root, {})
                self.assertEqual(state["messages"], [])
            finally:
                writer.execute("ROLLBACK")

    def test_inconsistent_legacy_data_rolls_back_without_rewriting_history(self):
        with closing(sqlite3.connect(self.path)) as connection:
            connection.executescript("""
                CREATE TABLE jobs(id TEXT PRIMARY KEY,kind TEXT NOT NULL,prompt TEXT NOT NULL,status TEXT NOT NULL,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
                CREATE TABLE messages(id INTEGER PRIMARY KEY,role TEXT NOT NULL,content TEXT NOT NULL,job_id TEXT,created_at TEXT NOT NULL,meta TEXT NOT NULL DEFAULT '{}');
                INSERT INTO jobs VALUES('legacy-bad-meta-0001','chat','Question','DONE',NULL,'date','date');
                INSERT INTO messages VALUES(42,'assistant','Keep this text','legacy-bad-meta-0001','date','malformed historical metadata');
            """)
        with self.assertRaises(sqlite3.IntegrityError):
            a.db(self.root)
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT id,content,meta FROM messages").fetchone(), (42, "Keep this text", "malformed historical metadata"))
            self.assertNotIn("__legacy_messages", {row[0] for row in connection.execute("SELECT name FROM sqlite_master")})
        backups = list((self.root / "private/backups").glob("*.sqlite3"))
        self.assertEqual(len(backups), 1)
        with closing(connect(backups[0], readonly=True)) as connection:
            self.assertEqual(connection.execute("SELECT content FROM messages").fetchone()[0], "Keep this text")

    def test_database_rejects_cross_conversation_history_and_scope_moves(self):
        with closing(a.db(self.root)) as connection:
            job_id = a.enqueue(connection, "Scholarship question", "scope-immutable-0001", route_id="first-scholarship")
            for statement, params in (
                ("INSERT INTO messages(role,content,job_id,created_at,route_id) VALUES('assistant','Wrong conversation',?,'date','second-scholarship')", (job_id,)),
                ("INSERT INTO tools(job_id,name,created_at,route_id) VALUES(?,'read_source','date',NULL)", (job_id,)),
                ("UPDATE job_scopes SET route_id='second-scholarship' WHERE job_id=?", (job_id,)),
                ("DELETE FROM job_scopes WHERE job_id=?", (job_id,)),
            ):
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(statement, params)
            general_id = a.enqueue(connection, "General question", "scope-general-0001")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO job_scopes VALUES(?,'first-scholarship')", (general_id,))
            self.assertEqual(connection.execute("SELECT route_id FROM messages WHERE job_id=?", (job_id,)).fetchone()[0], "first-scholarship")

    def test_model_context_uses_canonical_snapshot_and_rejects_stale_fallback(self):
        workspace = workspace_store.load(self.root)
        workspace["profile"]["snapshot"]["curriculum"] = "canonical curriculum"
        workspace["overlays"] = []
        workspace_store.save(self.root, workspace, workspace["revision"], workspace["mode"], target_mode="PRIVATE")
        (self.root / "private/profile.local.json").write_text(json.dumps({"snapshot": {"curriculum": "stale legacy curriculum"}}))
        (self.root / "private/overlay.local.json").write_text((self.root / "data/public/overlay.example.json").read_text())
        data = a.context(self.root, True)
        self.assertEqual(data["profile"]["snapshot"]["curriculum"], "canonical curriculum")
        self.assertEqual(data["overlays"], [])
        self.assertNotIn("stale legacy curriculum", json.dumps(data))
        with closing(connect(workspace_store.database_path(self.root))) as connection:
            connection.execute("PRAGMA user_version=999")
        with self.assertRaisesRegex(ValueError, "compatible"):
            a.context(self.root, True)
        self.assertEqual(a.context(self.root, False)["contextMode"], "FICTIONAL_DEMO")

    def test_waiting_retry_cannot_overwrite_a_completed_reply(self):
        job_id = "fixture-retry-race-0001"
        with closing(a.db(self.root)) as writer:
            a.enqueue(writer, "One answer", job_id)
            writer.execute("UPDATE jobs SET status='FAILED' WHERE id=?", (job_id,))
            writer.execute("BEGIN IMMEDIATE")
            attempted_write = threading.Event()
            original_connect = a.connect

            def observed_connect(*args, **kwargs):
                connection = original_connect(*args, **kwargs)
                connection.set_trace_callback(lambda query: attempted_write.set() if query == "BEGIN IMMEDIATE" else None)
                return connection

            def retry():
                try:
                    a.api(self.root, {"action": "retry", "jobId": job_id})
                except ValueError as error:
                    return str(error)
                return "unexpectedly requeued"

            with patch.object(a, "connect", side_effect=observed_connect), ThreadPoolExecutor(max_workers=1) as executor:
                waiting = executor.submit(retry)
                self.assertTrue(attempted_write.wait(3), "Retry did not reach its transaction")
                writer.execute("UPDATE jobs SET status='DONE' WHERE id=?", (job_id,))
                writer.execute("COMMIT")
                self.assertIn("already completed", waiting.result(timeout=3))
            self.assertEqual(writer.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()[0], "DONE")

    def test_retry_request_is_idempotent_even_after_worker_completion(self):
        job_id = "fixture-retry-once-0001"
        request = {"action": "retry", "jobId": job_id, "id": "fixture-retry-intent-0001"}
        with closing(a.db(self.root)) as connection:
            a.enqueue(connection, "One answer", job_id)
            connection.execute("UPDATE jobs SET status='FAILED' WHERE id=?", (job_id,))
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: a.api(self.root, request), range(4)))
        self.assertTrue(all(result["jobId"] == job_id for result in results))
        with patch.object(a, "completion", return_value={"role": "assistant", "content": "Exactly one saved answer."}) as provider:
            a.worker(self.root, once=True)
            self.assertEqual(provider.call_count, 1)
        self.assertEqual(a.api(self.root, request)["jobId"], job_id)
        with closing(a.db(self.root)) as connection:
            self.assertEqual(connection.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()[0], "DONE")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM retry_requests").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM messages WHERE role='assistant'").fetchone()[0], 1)
        health = a.api(self.root, {})["workerHealth"]
        self.assertEqual(health["state"], "OK")
        self.assertIsNotNone(health["lastSuccessfulJobAt"])
        self.assertNotIn("fixture-secret", json.dumps(health))


if __name__ == "__main__":
    unittest.main()
