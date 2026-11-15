from contextlib import closing, redirect_stdout
import fcntl
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from schola import recovery as r


class RecoveryChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "live"
        self.vault = self.root / "private"
        self.vault.mkdir(parents=True, mode=0o700)
        (self.root / "data/public").mkdir(parents=True)
        (self.root / "data/public/catalogue.json").write_text('[{"id":"fictional"}]')
        (self.root / "package.json").write_text('{"version":"fixture"}')
        (self.vault / "schola.local.json").write_text('{"fixture":"private-configuration"}')
        (self.vault / "documents").mkdir()
        (self.vault / "documents/transcript.pdf").write_bytes(b"fictional document")
        (self.vault / "watchtower/snapshots").mkdir(parents=True)
        (self.vault / "watchtower/snapshots/source.txt").write_text("fixture baseline")
        (self.vault / "watchtower_state.local.json").write_text('{"hash":"fixture"}')
        for name in ("workspace.sqlite3", "schola.sqlite3"):
            with closing(sqlite3.connect(self.vault / name)) as connection:
                connection.executescript("PRAGMA journal_mode=WAL; CREATE TABLE entries(id INTEGER PRIMARY KEY, value TEXT); INSERT INTO entries VALUES(1,'fictional state'); PRAGMA user_version=1;")
                connection.commit()

    def test_complete_snapshot_restore_and_permissions(self):
        for directory in ("deployments", "releases", "lan-previous-build", "backups", "node_modules", "recovery"):
            (self.vault / directory).mkdir(exist_ok=True, mode=0o700)
            (self.vault / directory / "excluded.txt").write_text("old copy")
        for name in ("demo-workspace.sqlite3", "demo-state.local.json", "runtime.tmp", "runtime.log"):
            (self.vault / name).write_text("not current owner state")
        snapshot = r.create_snapshot(self.root)
        manifest = r.verify_snapshot(snapshot)
        paths = {entry["path"] for entry in manifest["files"]}
        self.assertEqual(set(manifest["completeness"]["databases"]), set(r.DATABASES))
        self.assertIn("private/schola.local.json", paths)
        self.assertIn("private/documents/transcript.pdf", paths)
        self.assertIn("private/watchtower/snapshots/source.txt", paths)
        self.assertIn("data/public/catalogue.json", paths)
        self.assertIn("runtime/package.json", paths)
        self.assertFalse(any("excluded" in path or "demo-" in path or path.endswith((".log", ".tmp", "-wal", "-shm", ".lock")) for path in paths))
        self.assertFalse(manifest["offDeviceVerified"])
        for path in snapshot.rglob("*"):
            self.assertEqual(path.stat().st_mode & 0o777, 0o700 if path.is_dir() else 0o600)
        destination = Path(self.temporary.name) / "drill"
        r.restore_snapshot(snapshot, destination, self.root)
        self.assertEqual((destination / "private/documents/transcript.pdf").read_bytes(), b"fictional document")
        self.assertEqual((destination / "private/schola.local.json").read_bytes(), (self.vault / "schola.local.json").read_bytes())
        with closing(sqlite3.connect(destination / "private/workspace.sqlite3")) as connection:
            self.assertEqual(connection.execute("SELECT value FROM entries").fetchone()[0], "fictional state")
        with self.assertRaises(ValueError):
            r.restore_snapshot(snapshot, destination, self.root)
        self.assertEqual(r.health(self.root)["status"], "OK")

    def test_wal_commits_are_included_and_source_unchanged(self):
        source = self.vault / "schola.sqlite3"
        with closing(sqlite3.connect(source)) as connection:
            connection.execute("PRAGMA wal_autocheckpoint=0")
            connection.execute("INSERT INTO entries VALUES(2,'committed in WAL')")
            connection.commit()
            self.assertTrue(source.with_name(source.name + "-wal").exists())
            before = source.read_bytes()
            snapshot = r.create_snapshot(self.root)
            self.assertEqual(source.read_bytes(), before)
            with closing(sqlite3.connect(snapshot / "private/schola.sqlite3")) as restored:
                self.assertEqual(restored.execute("SELECT value FROM entries WHERE id=2").fetchone()[0], "committed in WAL")
        r.verify_snapshot(snapshot)

    def test_tamper_missing_and_unrecorded_files_fail(self):
        snapshot = r.create_snapshot(self.root)
        target = snapshot / "private/documents/transcript.pdf"
        target.write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            r.verify_snapshot(snapshot)
        self.assertEqual(r.health(self.root)["status"], "INVALID")
        target.write_bytes(b"fictional document")
        target.unlink()
        with self.assertRaises(ValueError):
            r.verify_snapshot(snapshot)
        target.write_bytes(b"fictional document")
        (snapshot / "unrecorded").write_text("unexpected")
        with self.assertRaises(ValueError):
            r.verify_snapshot(snapshot)

    def test_symlinks_traversal_and_live_restore_targets_rejected(self):
        source = self.vault / "documents/transcript.pdf"
        source.unlink()
        source.symlink_to(self.root / "package.json")
        with self.assertRaises(ValueError):
            r.create_snapshot(self.root)
        source.unlink()
        source.write_bytes(b"fictional document")
        snapshot = r.create_snapshot(self.root)
        with self.assertRaises(ValueError):
            r.restore_snapshot(snapshot, self.vault / "overwrite", self.root)
        target = snapshot / "private/documents/transcript.pdf"
        target.unlink()
        target.symlink_to(source)
        with self.assertRaises(ValueError):
            r.verify_snapshot(snapshot)
        target.unlink()
        target.write_bytes(b"fictional document")
        path = snapshot / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["files"][0]["path"] = "private/../../escape"
        path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            r.verify_snapshot(snapshot)

    def test_missing_database_is_explicit_and_bad_fk_is_rejected(self):
        (self.vault / "workspace.sqlite3").unlink()
        snapshot = r.create_snapshot(self.root)
        self.assertEqual(r.verify_snapshot(snapshot)["completeness"]["absentDatabases"], ["private/workspace.sqlite3"])
        with closing(sqlite3.connect(self.vault / "schola.sqlite3")) as connection:
            connection.executescript("CREATE TABLE child(parent INTEGER REFERENCES entries(id)); INSERT INTO child VALUES(999);")
        with self.assertRaisesRegex(ValueError, "foreign-key"):
            r.create_snapshot(self.root)
        self.assertEqual(len(list((self.vault / "recovery").glob(r.PREFIX + "*"))), 1)

    def test_changed_supporting_file_fails_without_publishing(self):
        original = r._write
        mutated = False

        def write_then_mutate(path, content):
            nonlocal mutated
            original(path, content)
            if path.name == "schola.local.json" and not mutated:
                (self.vault / "schola.local.json").write_text('{"fixture":"changed configuration"}')
                mutated = True

        with patch.object(r, "_write", side_effect=write_then_mutate):
            with self.assertRaisesRegex(ValueError, "changed"):
                r.create_snapshot(self.root)
        self.assertFalse(list((self.vault / "recovery").glob(r.PREFIX + "*")))
        self.assertFalse(list((self.vault / "recovery").glob(".pending-*")))

    def test_database_integrity_is_checked_beyond_file_hashes(self):
        snapshot = r.create_snapshot(self.root)
        target = snapshot / "private/workspace.sqlite3"
        target.write_bytes(b"this is not a SQLite database")
        path = snapshot / "manifest.json"
        manifest = json.loads(path.read_text())
        for entry in manifest["files"]:
            if entry["path"] == "private/workspace.sqlite3":
                entry["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
                entry["size"] = target.stat().st_size
        path.write_text(json.dumps(manifest))
        with self.assertRaises((ValueError, sqlite3.Error)):
            r.verify_snapshot(snapshot)

    def test_outside_destination_and_public_directory_symlink_rejected(self):
        with self.assertRaises(ValueError):
            r.create_snapshot(self.root, Path(self.temporary.name) / "public-backup")
        public = self.root / "data/public"
        public.rename(self.root / "data/original-public")
        public.symlink_to(self.root / "data/original-public", target_is_directory=True)
        with self.assertRaises(ValueError):
            r.create_snapshot(self.root)

    def test_snapshot_privacy_permissions_and_sqlite_sidecar_links(self):
        snapshot = r.create_snapshot(self.root)
        (snapshot / "private/schola.local.json").chmod(0o644)
        with self.assertRaisesRegex(ValueError, "permissions"):
            r.verify_snapshot(snapshot)
        self.assertEqual(r.health(self.root)["status"], "INVALID")
        sidecar = self.vault / "workspace.sqlite3-wal"
        sidecar.unlink(missing_ok=True)
        sidecar.symlink_to(self.root / "package.json")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            r.create_snapshot(self.root)

    def test_app_only_runtime_restores_completely(self):
        from schola.sqlite_runtime import ARCHIVE_SHA3, SOURCE_ID, SOURCE_SHA3, VERSION, runtime_environment, validate_runtime
        runtime = self.vault / "runtime" / f"sqlite-{VERSION}"
        (runtime / "lib").mkdir(parents=True)
        library = runtime / "lib/libsqlite3.so.0"
        library.write_bytes(b"fictional runtime library")
        library.chmod(0o700)
        receipt = {"version": VERSION, "source_id": SOURCE_ID, "archive_sha3": ARCHIVE_SHA3, "source_sha3": SOURCE_SHA3, "library_sha256": hashlib.sha256(library.read_bytes()).hexdigest()}
        (runtime / "manifest.json").write_text(json.dumps(receipt))
        (runtime.parent / ".install.lock").write_text("excluded lock")
        snapshot = r.create_snapshot(self.root)
        restored = Path(self.temporary.name) / "runtime-drill"
        r.restore_snapshot(snapshot, restored, self.root)
        restored_runtime = restored / "private/runtime" / f"sqlite-{VERSION}"
        self.assertEqual(validate_runtime(restored_runtime), receipt)
        self.assertFalse((restored_runtime.parent / ".install.lock").exists())
        self.assertEqual(runtime_environment(restored, {}, required=True)["LD_LIBRARY_PATH"], str(restored_runtime / "lib"))

    def test_nested_supporting_files_are_never_mistaken_for_runtime_caches(self):
        expected = []
        for name in ("cache", "caches", ".cache", "backups", "deployments", "releases", "lan-previous-build", "artifacts", "demo-reference"):
            path = self.vault / "documents" / name / "original.txt"
            path.parent.mkdir(parents=True)
            path.write_text("fictional original supporting file")
            expected.append(path.relative_to(self.root).as_posix())
        for name in ("trace.log", "evidence.tmp", "demo-state.local.json"):
            path = self.vault / "documents" / name
            path.write_text("fictional supporting evidence")
            expected.append(path.relative_to(self.root).as_posix())
        snapshot = r.create_snapshot(self.root)
        captured = {entry["path"] for entry in r.verify_snapshot(snapshot)["files"]}
        self.assertTrue(set(expected).issubset(captured))

    def test_active_watcher_is_never_interrupted(self):
        with (self.vault / "watchtower.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, "running"):
                r.create_snapshot(self.root)
        self.assertFalse(list((self.vault / "recovery").glob(r.PREFIX + "*")))

    def test_retention_only_removes_verified_tool_owned_snapshots(self):
        first = r.create_snapshot(self.root)
        damaged = r.create_snapshot(self.root)
        (damaged / "private/documents/transcript.pdf").write_bytes(b"damaged")
        arbitrary = self.vault / "recovery/personal-archive"
        arbitrary.mkdir()
        (arbitrary / "keep").write_text("keep")
        final = r.create_snapshot(self.root, keep=1)
        self.assertFalse(first.exists())
        self.assertTrue(damaged.exists())
        self.assertTrue(arbitrary.exists())
        self.assertTrue(final.exists())

    def test_cli_create_verify_restore_and_health(self):
        checkout = Path(__file__).resolve().parents[1]
        command = [sys.executable, "-m", "schola.recovery", "--root", str(self.root)]
        missing = subprocess.run(command + ["health"], cwd=checkout, capture_output=True, text=True)
        self.assertEqual(missing.returncode, 1)
        created = subprocess.run(command + ["create"], cwd=checkout, capture_output=True, text=True, check=True)
        snapshot = json.loads(created.stdout)["snapshot"]
        verified = subprocess.run(command + ["verify", snapshot], cwd=checkout, capture_output=True, text=True, check=True)
        self.assertTrue(json.loads(verified.stdout)["verified"])
        destination = Path(self.temporary.name) / "cli-drill"
        subprocess.run(command + ["restore", snapshot, str(destination)], cwd=checkout, capture_output=True, text=True, check=True)
        healthy = subprocess.run(command + ["health"], cwd=checkout, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(healthy.stdout)["status"], "OK")
        self.assertTrue((destination / "private/workspace.sqlite3").exists())

    def test_timer_is_opt_in_and_runs_through_runtime_wrapper(self):
        path = Path(__file__).resolve().parents[1] / "scripts/install-recovery-service.py"
        spec = importlib.util.spec_from_file_location("recovery_installer", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        units = module.units_for(Path("/fixture checkout"), Path("/fixture python"))
        self.assertIn('"/fixture checkout/scripts/run-python.py" -m schola.recovery create --keep 14', units["studab27-recovery.service"])
        self.assertIn("OnCalendar=*-*-* 03:17:00 Asia/Jakarta", units["studab27-recovery.timer"])
        self.assertIn("UMask=0077", units["studab27-recovery.service"])
        self.assertIn("Environment=STUDAB27_REQUIRE_SQLITE_RUNTIME=1", units["studab27-recovery.service"])
        scripts = self.root / "scripts"
        scripts.mkdir()
        (scripts / "run-python.py").write_text("# fixture runtime wrapper")
        module.__file__ = str(scripts / "install-recovery-service.py")
        home = Path(self.temporary.name) / "home"
        with patch.object(module.Path, "home", return_value=home), patch.object(module.subprocess, "run") as execute, redirect_stdout(io.StringIO()):
            module.main([])
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(execute.call_args.args[0], ["systemctl", "--user", "daemon-reload"])
        self.assertTrue((home / ".config/systemd/user/studab27-recovery.timer").is_file())
