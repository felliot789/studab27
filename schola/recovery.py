"""Complete local vault snapshots; restore drills always use a new isolated directory.

No cloud upload or encryption is implied. Snapshot directories contain credentials
and documents and require the same protection as the original private vault.
"""
import argparse
from contextlib import ExitStack, closing, contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import uuid

FORMAT = "studab27-local-recovery-v1"
PREFIX = "studab27-recovery-"
SNAPSHOT_NAME = re.compile(r"studab27-recovery-\d{8}T\d{12}Z-[0-9a-f]{12}\Z")
DATABASES = ("private/workspace.sqlite3", "private/schola.sqlite3")
# These are disposable or previous copies, not the current owner's state.
EXCLUDED_DIRECTORIES = {"recovery", "backups", "deployments", "node_modules", ".next", "__pycache__", "artifacts", ".venv", ".venv-research"}
DEMO_FILES = {"demo-workspace.sqlite3", "demo-schola.sqlite3", "demo-profile.local.json", "demo-overlay.local.json", "demo-state.local.json", "demo-milestones.local.json", "demo-inbox.local.json"}
VERSION_FILES = ("package.json", "package-lock.json", "requirements-research.txt", "requirements-sqlite.txt")
EXCLUSIONS = ["recovery destination and known root-level previous recovery/backups/deployments or build/runtime cache directories", "known root-level demo workspace/chat/JSON stores and their sidecars", "root-level lock, temporary, log, pid and socket files; watcher snapshot temporaries and runtime installation lock/staging", "canonical SQLite WAL/SHM/journal sidecars (included through the SQLite backup API)", "source checkout, installed dependencies and build output (source/runtime versions recorded; reinstall separately); similarly named nested supporting-document folders are preserved"]


def _checked_path(value):
    path = Path(value).expanduser().absolute()
    if ".." in path.parts:
        raise ValueError("Parent traversal is not allowed")
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError("Symlink paths are not allowed")
    return path


def _relative(value):
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("Invalid snapshot path")
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(p in (".", "..") for p in path.parts):
        raise ValueError("Unsafe snapshot path")
    if not (value.startswith("private/") or value.startswith("data/public/") or value.startswith("runtime/")):
        raise ValueError("Unexpected snapshot path")
    return value


def _mkdir(path):
    if path.exists():
        if not path.is_dir():
            raise ValueError("Expected a directory")
        return
    _mkdir(path.parent)
    path.mkdir(mode=0o700)


def _fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write(path, content):
    _mkdir(path.parent)
    with path.open("xb") as output:
        os.fchmod(output.fileno(), 0o600)
        output.write(content)
        output.flush()
        os.fsync(output.fileno())


def _fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _read_regular(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Only regular recovery files are supported")
        content = source.read()
        if _fingerprint(before) != _fingerprint(os.fstat(source.fileno())):
            raise ValueError("A vault file changed during recovery capture; retry")
        return content, _fingerprint(before)


def _digest(content):
    return hashlib.sha256(content).hexdigest()


@contextmanager
def _lock(path):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(descriptor, "w") as lock:
        if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
            raise ValueError("Unsafe lock file")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("A source scan or recovery operation is running; retry later") from None
        yield


def _skip(relative, destination, root):
    parts = relative.parts
    name = parts[-1]
    if parts[0] != "private":
        return False
    if (root / relative).is_relative_to(destination):
        return True
    # Only known vault-root operational paths are disposable. A document folder
    # called cache/backups/deployments, or an attached .log/.tmp, is owner data.
    if len(parts) >= 2 and parts[1] in EXCLUDED_DIRECTORIES:
        return True
    if len(parts) == 2:
        if name in DEMO_FILES or any(name == demo + suffix for demo in DEMO_FILES for suffix in ("-wal", "-shm", "-journal")):
            return True
        if name.endswith((".lock", ".tmp", ".temp", ".log", ".pid", ".sock", "~")) or ".tmp-" in name:
            return True
        if relative.as_posix() in DATABASES or any(relative.as_posix() == database + suffix for database in DATABASES for suffix in ("-wal", "-shm", "-journal")):
            return True
    if parts[:3] == ("private", "watchtower", "snapshots") and name.endswith(".tmp"):
        return True
    if parts[:2] == ("private", "runtime") and len(parts) >= 3:
        return parts[2] == ".install.lock" or parts[2].startswith(".sqlite-")
    return False


def _inventory(root, destination):
    files = {}
    for directory in (root / "private", root / "data/public"):
        if not directory.exists():
            continue
        _checked_path(directory)
        pending = [directory]
        while pending:
            parent = pending.pop()
            for path in sorted(parent.iterdir()):
                relative = path.relative_to(root)
                if _skip(relative, destination, root):
                    continue
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode):
                    raise ValueError("Vault/public symlinks cannot be captured safely")
                if stat.S_ISDIR(info.st_mode):
                    pending.append(path)
                elif stat.S_ISREG(info.st_mode):
                    if path.suffix in (".sqlite", ".sqlite3", ".db"):
                        raise ValueError("Unexpected database in vault; define its online recovery policy first")
                    files[relative.as_posix()] = _fingerprint(info)
                else:
                    raise ValueError("Vault/public special files cannot be captured safely")
    for name in VERSION_FILES:
        path = root / name
        if path.exists():
            if path.is_symlink() or not path.is_file():
                raise ValueError("Runtime version files must be regular files")
            files[f"runtime/{name}"] = _fingerprint(path.stat())
    return files


def _source(root, relative):
    return root / (relative.removeprefix("runtime/") if relative.startswith("runtime/") else relative)


def _database_info(path):
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=10)) as connection:
            if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("Recovery database integrity check failed")
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ValueError("Recovery database foreign-key check failed")
            return {"userVersion": connection.execute("PRAGMA user_version").fetchone()[0], "applicationId": connection.execute("PRAGMA application_id").fetchone()[0]}
    except sqlite3.Error as error:
        raise ValueError("Recovery database could not be verified") from error


def _version(root):
    result = {"python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version, "sourceCommit": None, "sourceDirty": None}
    try:
        result["sourceCommit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, stderr=subprocess.DEVNULL, text=True, timeout=5).strip()
        result["sourceDirty"] = bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root, stderr=subprocess.DEVNULL, timeout=5))
    except (OSError, subprocess.SubprocessError):
        pass
    return result


def create_snapshot(root, destination=None, keep=14):
    """Publish only verified, stable snapshots; failure leaves prior copies intact."""
    root = _checked_path(root)
    vault = _checked_path(root / "private")
    if not vault.is_dir():
        raise ValueError("The private vault does not exist")
    destination = _checked_path(destination if destination is not None else vault / "recovery")
    if not destination.is_relative_to(vault) or destination == vault:
        raise ValueError("Local recovery destination must be a directory inside the ignored vault")
    if not isinstance(keep, int) or isinstance(keep, bool) or keep < 1:
        raise ValueError("Retention must preserve at least one snapshot")
    _mkdir(destination)
    if destination.stat().st_mode & 0o077:
        raise ValueError("Recovery destination must be private (mode 0700)")
    with ExitStack() as stack:
        stack.enter_context(_lock(vault / "recovery.lock"))
        stack.enter_context(_lock(vault / "watchtower.lock"))
        identifier = PREFIX + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ-") + uuid.uuid4().hex[:12]
        temporary = Path(tempfile.mkdtemp(prefix=".pending-", dir=destination))
        stage = temporary / identifier
        stage.mkdir(mode=0o700)
        try:
            before = _inventory(root, destination)
            entries = []
            sources = []
            missing = []
            # Pin independent read transactions before copying either store. There
            # is no distributed transaction across these independent databases.
            for relative in DATABASES:
                source = _checked_path(root / relative)
                for suffix in ("-wal", "-shm", "-journal"):
                    sidecar = _checked_path(source.with_name(source.name + suffix))
                    if sidecar.exists() and not sidecar.is_file():
                        raise ValueError("SQLite sidecars must be regular files")
                if not source.exists():
                    missing.append(relative)
                    continue
                if not source.is_file():
                    raise ValueError("Canonical database must be a regular file")
                connection = stack.enter_context(closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=10)))
                connection.execute("BEGIN")
                connection.execute("SELECT name FROM sqlite_schema LIMIT 1").fetchall()
                sources.append((relative, source, connection, _fingerprint(source.stat())[:2]))
            for relative, source, connection, identity in sources:
                target = stage / relative
                _mkdir(target.parent)
                with closing(sqlite3.connect(target)) as output:
                    connection.backup(output)
                    output.execute("PRAGMA journal_mode=DELETE")
                target.chmod(0o600)
                metadata = _database_info(target)
                content, _ = _read_regular(target)
                with target.open("rb") as output:
                    os.fsync(output.fileno())
                entries.append({"path": relative, "kind": "sqlite", "size": len(content), "sha256": _digest(content), **metadata})
            copied = {}
            for relative, fingerprint in sorted(before.items()):
                content, observed = _read_regular(_source(root, relative))
                if fingerprint != observed:
                    raise ValueError("A vault file changed during recovery capture; retry")
                _write(stage / relative, content)
                copied[relative] = _digest(content)
                entries.append({"path": relative, "kind": "file", "size": len(content), "sha256": copied[relative]})
            if before != _inventory(root, destination):
                raise ValueError("Vault files changed during recovery capture; retry")
            for relative, digest in copied.items():
                content, _ = _read_regular(_source(root, relative))
                if _digest(content) != digest:
                    raise ValueError("A vault file changed during recovery capture; retry")
            for relative, source, connection, identity in sources:
                if _fingerprint(source.stat())[:2] != identity:
                    raise ValueError("A canonical database was replaced during recovery capture; retry")
            if any((root / relative).exists() for relative in missing):
                raise ValueError("A database appeared during recovery capture; retry")
            manifest = {"format": FORMAT, "snapshotId": identifier, "createdAt": datetime.now(timezone.utc).isoformat(), "verified": True,
                        "localOnly": True, "offDeviceVerified": False, "encryption": "filesystem-permissions-only",
                        "completeness": {"currentVault": True, "publicDefinitions": (root / "data/public").is_dir(), "databases": [r for r, *_ in sources], "absentDatabases": missing,
                                         "consistency": "SQLite online backup from independently pinned read transactions; eligible supporting files unchanged across capture; watcher scan lock held",
                                         "exclusions": EXCLUSIONS}, "runtime": _version(root), "files": sorted(entries, key=lambda entry: entry["path"])}
            _write(stage / "manifest.json", (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode())
            verify_snapshot(stage)
            for parent, directories, filenames in os.walk(stage, topdown=False):
                _fsync_directory(Path(parent))
            published = destination / identifier
            stage.replace(published)
            _fsync_directory(destination)
            _retain(destination, keep)
            return published
        finally:
            shutil.rmtree(temporary)


def verify_snapshot(snapshot):
    """Verify every recorded byte and database; reject unrecorded files/links."""
    snapshot = _checked_path(snapshot)
    if not snapshot.is_dir():
        raise ValueError("Recovery snapshot directory is missing")
    if snapshot.stat().st_mode & 0o077:
        raise ValueError("Recovery snapshot permissions must remain private")
    try:
        raw, _ = _read_regular(snapshot / "manifest.json")
        manifest = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeError) as error:
        raise ValueError("Recovery manifest is missing or invalid") from error
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT or manifest.get("snapshotId") != snapshot.name or not SNAPSHOT_NAME.fullmatch(snapshot.name) or manifest.get("verified") is not True:
        raise ValueError("Unrecognized or incomplete recovery snapshot")
    if not isinstance(manifest.get("files"), list) or not isinstance(manifest.get("completeness"), dict):
        raise ValueError("Invalid recovery manifest")
    expected = {"manifest.json"}
    databases = []
    for entry in manifest["files"]:
        if not isinstance(entry, dict):
            raise ValueError("Invalid recovery file entry")
        relative = _relative(entry.get("path"))
        if relative in expected or entry.get("kind") not in ("file", "sqlite") or type(entry.get("size")) is not int or entry["size"] < 0 or not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256", ""))):
            raise ValueError("Invalid or duplicate recovery file entry")
        expected.add(relative)
        target = _checked_path(snapshot / relative)
        try:
            content, _ = _read_regular(target)
        except OSError as error:
            raise ValueError("Recovery snapshot file is missing or unreadable") from error
        if len(content) != entry["size"] or _digest(content) != entry["sha256"]:
            raise ValueError("Recovery snapshot file hash mismatch")
        if entry["kind"] == "sqlite":
            if relative not in DATABASES:
                raise ValueError("Unexpected recovery database")
            info = _database_info(target)
            if any(entry.get(key) != value for key, value in info.items()):
                raise ValueError("Recovery database schema metadata mismatch")
            databases.append(relative)
        elif relative in DATABASES:
            raise ValueError("Canonical database must use an online snapshot")
    completeness = manifest["completeness"]
    absent = completeness.get("absentDatabases")
    if completeness.get("currentVault") is not True or completeness.get("databases") != [relative for relative in DATABASES if relative in databases] or not isinstance(absent, list) or any(not isinstance(value, str) for value in absent) or sorted(databases + absent) != sorted(DATABASES):
        raise ValueError("Recovery manifest does not account for both canonical databases")
    actual = set()
    for parent, directories, filenames in os.walk(snapshot, followlinks=False):
        for name in directories + filenames:
            target = Path(parent) / name
            info = target.lstat()
            if not stat.S_ISREG(info.st_mode) and not stat.S_ISDIR(info.st_mode):
                raise ValueError("Recovery snapshot contains a link or special file")
            if info.st_mode & 0o077:
                raise ValueError("Recovery snapshot permissions must remain private")
        actual.update((Path(parent) / name).relative_to(snapshot).as_posix() for name in filenames)
    if actual != expected:
        raise ValueError("Recovery snapshot contains unrecorded or missing files")
    return manifest


def _retain(destination, keep):
    verified = []
    for candidate in destination.iterdir():
        if SNAPSHOT_NAME.fullmatch(candidate.name) and candidate.is_dir() and not candidate.is_symlink():
            try:
                verify_snapshot(candidate)
            except (ValueError, OSError, sqlite3.Error):
                continue  # Damaged or foreign copies are preserved for investigation.
            verified.append(candidate)
    for candidate in sorted(verified, reverse=True)[keep:]:
        shutil.rmtree(candidate)
    _fsync_directory(destination)


def restore_snapshot(snapshot, destination, root=None):
    """Restore data only into a new directory outside the live checkout."""
    snapshot = _checked_path(snapshot)
    manifest = verify_snapshot(snapshot)
    destination = _checked_path(destination)
    live_root = _checked_path(root if root is not None else Path.cwd())
    if destination.exists() or destination.is_relative_to(live_root) or destination.is_relative_to(snapshot.parent):
        raise ValueError("Restore requires a new isolated directory outside the live checkout and recovery storage")
    _mkdir(destination.parent)
    temporary = Path(tempfile.mkdtemp(prefix=".studab27-restore-", dir=destination.parent))
    try:
        for entry in manifest["files"]:
            relative = _relative(entry["path"])
            content, _ = _read_regular(_checked_path(snapshot / relative))
            if len(content) != entry["size"] or _digest(content) != entry["sha256"]:
                raise ValueError("Recovery snapshot changed during restore")
            _write(temporary / relative, content)
        for relative in manifest["completeness"]["databases"]:
            _database_info(temporary / relative)
        _write(temporary / "recovery-manifest.json", (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode())
        for parent, directories, filenames in os.walk(temporary, topdown=False):
            _fsync_directory(Path(parent))
        # mkdir reserves the new target without replacing an existing directory.
        destination.mkdir(mode=0o700)
        temporary.replace(destination)
        _fsync_directory(destination.parent)
        return destination
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def health(root, destination=None):
    """Small read-only operational summary; this never certifies off-device safety."""
    root = _checked_path(root)
    destination = _checked_path(destination if destination is not None else root / "private/recovery")
    result = {"status": "MISSING", "localOnly": True, "offDeviceVerified": False, "verified": False, "latestSnapshot": None, "ageHours": None}
    if not destination.exists():
        return result
    candidates = sorted((path for path in destination.iterdir() if SNAPSHOT_NAME.fullmatch(path.name)), reverse=True)
    if not candidates:
        return result
    result["latestSnapshot"] = candidates[0].name
    try:
        manifest = verify_snapshot(candidates[0])
        created = datetime.fromisoformat(manifest["createdAt"])
        age = (datetime.now(timezone.utc) - created).total_seconds() / 3600
        if age < -0.1:
            raise ValueError("Snapshot timestamp is in the future")
        result.update(status="OK" if age <= 48 else "STALE", verified=True, ageHours=round(max(0, age), 2))
    except (ValueError, TypeError, KeyError, OSError, sqlite3.Error):
        result["status"] = "INVALID"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="Create and verify a complete local snapshot")
    create.add_argument("--destination", type=Path)
    create.add_argument("--keep", type=int, default=14)
    verify = commands.add_parser("verify", help="Verify all hashes and SQLite integrity")
    verify.add_argument("snapshot", type=Path)
    restore = commands.add_parser("restore", help="Restore into a NEW isolated directory only")
    restore.add_argument("snapshot", type=Path)
    restore.add_argument("destination", type=Path)
    status = commands.add_parser("health", help="Show local recovery health")
    status.add_argument("--destination", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            print(json.dumps({"snapshot": str(create_snapshot(args.root, args.destination, args.keep)), "verified": True, "localOnly": True, "offDeviceVerified": False}))
        elif args.command == "verify":
            manifest = verify_snapshot(args.snapshot)
            print(json.dumps({"snapshot": manifest["snapshotId"], "verified": True, "files": len(manifest["files"]), "localOnly": True, "offDeviceVerified": False}))
        elif args.command == "restore":
            print(json.dumps({"restoredTo": str(restore_snapshot(args.snapshot, args.destination, args.root)), "isolated": True}))
        else:
            result = health(args.root, args.destination)
            print(json.dumps(result))
            return 0 if result["status"] == "OK" else 1
    except (ValueError, OSError, sqlite3.Error) as error:
        parser.exit(1, f"Recovery failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
