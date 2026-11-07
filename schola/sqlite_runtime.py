"""Pinned, app-only SQLite shared library; never replaces the system library."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


VERSION = "3.54.1"
SOURCE_ID = "2026-10-16 14:45:20 555e07ef33f69a0957d24d8e555b702464a131d6f1607f4c3c1e4551e8e6ca76"
ARCHIVE_URL = "https://sqlite.org/2026/sqlite-amalgamation-3540100.zip"
ARCHIVE_SHA3 = "92281c86e2957f9b9305890f9ac04204caa7b677cc868dc326d942689df28e30"
SOURCE_SHA3 = "e2b869d3003b33c942b7dd7063604fbc53553e1b66609570df39b9b7b558ee81"
# Pins published at https://sqlite.org/download.html and /releaselog/3_54_1.html.


def _library_environment(runtime: Path, env: dict[str, str]) -> dict[str, str]:
    library_path = str(runtime.resolve() / "lib")
    previous = env.get("LD_LIBRARY_PATH", "")
    if previous.split(os.pathsep)[0] != library_path:
        env["LD_LIBRARY_PATH"] = library_path + (os.pathsep + previous if previous else "")
    return env


def validate_runtime(runtime: Path) -> dict:
    """Reject partial installs or a runtime that no longer matches its receipt."""
    try:
        if runtime.is_symlink():
            raise ValueError("runtime directory is a symlink")
        receipt = json.loads((runtime / "manifest.json").read_text(encoding="utf-8"))
        library = runtime / "lib/libsqlite3.so.0"
        if library.is_symlink():
            raise ValueError("runtime library is a symlink")
        if (receipt.get("version"), receipt.get("source_id"), receipt.get("archive_sha3"), receipt.get("source_sha3")) != (VERSION, SOURCE_ID, ARCHIVE_SHA3, SOURCE_SHA3):
            raise ValueError("unexpected release")
        if hashlib.sha256(library.read_bytes()).hexdigest() != receipt.get("library_sha256"):
            raise ValueError("library checksum mismatch")
    except (OSError, ValueError, AttributeError) as exc:
        raise RuntimeError("The app-only SQLite runtime is incomplete or invalid; reinstall it before starting.") from exc
    return receipt


def runtime_environment(root: Path, env: dict[str, str] | None = None, *, required: bool = False) -> dict[str, str]:
    """Supply this environment before launching Python, not after importing sqlite3."""
    result = dict(os.environ if env is None else env)
    runtime = root / "private/runtime" / f"sqlite-{VERSION}"
    if not runtime.exists() and not runtime.is_symlink():
        if required:
            raise RuntimeError("Install the app-only SQLite runtime with scripts/install-sqlite-runtime.py first.")
        return result
    validate_runtime(runtime)
    return _library_environment(runtime, result)


def verify_python(interpreter: str | Path, runtime: Path) -> dict:
    """Attest the actual binding and mapped library without touching workspace data."""
    validate_runtime(runtime)
    probe = r'''
import contextlib, json, os, pathlib, sqlite3, tempfile
with tempfile.TemporaryDirectory(prefix="studab27-sqlite-probe-") as directory:
    path = pathlib.Path(directory) / "probe.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("pragma journal_mode=wal")
    connection.execute("pragma foreign_keys=on")
    connection.execute("create table parent(id integer primary key)")
    connection.execute("create table child(id integer references parent(id))")
    try:
        connection.execute("insert into child values(1)")
        raise RuntimeError("foreign keys are unavailable")
    except sqlite3.IntegrityError:
        pass
    connection.rollback()
    connection.execute("insert into parent values(1)")
    connection.execute("insert into child values(1)")
    connection.commit()
    other = sqlite3.connect(path)
    assert other.execute("select count(*) from child").fetchone()[0] == 1
    other.close()
    with contextlib.closing(sqlite3.connect(":memory:")) as backup:
        connection.backup(backup)
        assert backup.execute("pragma integrity_check").fetchone()[0] == "ok"
    source_id = connection.execute("select sqlite_source_id()").fetchone()[0]
    connection.close()
    mapped = sorted({str(pathlib.Path(line.split()[-1]).resolve()) for line in pathlib.Path("/proc/self/maps").read_text().splitlines() if "/libsqlite3.so" in line})
    print(json.dumps({"version": sqlite3.sqlite_version, "source_id": source_id, "libraries": mapped, "python": os.path.realpath(os.sys.executable)}))
'''
    try:
        result = subprocess.run([str(interpreter), "-I", "-c", probe], env=_library_environment(runtime, dict(os.environ)), capture_output=True, text=True, timeout=30, check=True)
        details = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise RuntimeError(f"SQLite runtime verification failed for {interpreter}.") from exc
    expected_library = str((runtime / "lib/libsqlite3.so.0").resolve())
    if details.get("version") != VERSION or details.get("source_id") != SOURCE_ID or details.get("libraries") != [expected_library]:
        raise RuntimeError(f"Python did not load the pinned SQLite library: {interpreter}.")
    return details


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    runtime = root / "private/runtime" / f"sqlite-{VERSION}"
    print(json.dumps(verify_python(sys.executable, runtime), sort_keys=True))


if __name__ == "__main__":
    main()
