"""Build a checksum-pinned SQLite library for StudAb27 without system changes.

Requires Linux, Python 3, and an existing C compiler. The default destination is
ignored private/runtime/. Use --runtime-root to validate a separate staged copy.
No service is started or restarted, and an existing runtime is never replaced.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from schola.sqlite_runtime import ARCHIVE_SHA3, ARCHIVE_URL, SOURCE_ID, SOURCE_SHA3, VERSION, validate_runtime, verify_python

MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
BUILD_FLAGS = ["-O2", "-fPIC", "-shared", "-DSQLITE_THREADSAFE=1", "-DSQLITE_ENABLE_FTS5", "-DSQLITE_ENABLE_RTREE", "-DSQLITE_ENABLE_COLUMN_METADATA", "-Wl,-soname,libsqlite3.so.0"]


def source_from_archive(archive: bytes) -> bytes:
    """Only extract the verified amalgamation, never arbitrary archive paths."""
    if len(archive) > MAX_ARCHIVE_BYTES or hashlib.sha3_256(archive).hexdigest() != ARCHIVE_SHA3:
        raise ValueError("SQLite source archive checksum mismatch; nothing was installed.")
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        member = bundle.getinfo("sqlite-amalgamation-3540100/sqlite3.c")
        if member.file_size > MAX_ARCHIVE_BYTES:
            raise ValueError("SQLite amalgamation exceeds the supported size.")
        source = bundle.read(member)
    if hashlib.sha3_256(source).hexdigest() != SOURCE_SHA3 or SOURCE_ID.encode() not in source:
        raise ValueError("SQLite source identity mismatch; nothing was installed.")
    return source


def download_archive() -> bytes:
    with urlopen(ARCHIVE_URL, timeout=30) as response:
        final_url = urlsplit(response.url)
        if final_url.scheme != "https" or final_url.hostname not in ("sqlite.org", "www.sqlite.org"):
            raise ValueError("SQLite download redirected outside its official HTTPS host.")
        return response.read(MAX_ARCHIVE_BYTES + 1)


def install(runtime_root: Path, archive: bytes, interpreters: list[str]) -> Path:
    if sys.platform != "linux":
        raise ValueError("The app-only SQLite runtime currently supports Linux only.")
    source = source_from_archive(archive)
    compiler = shutil.which("cc")
    if not compiler:
        raise ValueError("An existing C compiler (cc) is required; no system packages were changed.")
    runtime_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = runtime_root / f"sqlite-{VERSION}"
    if destination.exists() or destination.is_symlink():
        raise ValueError("SQLite runtime already exists; use --check to verify it. It was preserved.")
    with tempfile.TemporaryDirectory(prefix=f".sqlite-{VERSION}-", dir=runtime_root) as temporary:
        staging = Path(temporary)
        build_source = staging / "sqlite3.c"
        build_source.write_bytes(source)
        library_directory = staging / "lib"
        library_directory.mkdir(mode=0o700)
        library = library_directory / "libsqlite3.so.0"
        subprocess.run([compiler, *BUILD_FLAGS, "-o", str(library), str(build_source), "-lm", "-ldl", "-pthread"], check=True, timeout=300)
        library.chmod(0o700)
        receipt = {"version": VERSION, "source_id": SOURCE_ID, "archive_url": ARCHIVE_URL, "archive_sha3": ARCHIVE_SHA3, "source_sha3": SOURCE_SHA3, "library_sha256": hashlib.sha256(library.read_bytes()).hexdigest(), "compiler": compiler, "build_flags": BUILD_FLAGS}
        manifest = staging / "manifest.json"
        manifest.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        manifest.chmod(0o600)
        for interpreter in interpreters:
            verify_python(interpreter, staging)
        build_source.unlink()
        with library.open("rb") as handle:
            os.fsync(handle.fileno())
        with manifest.open("rb") as handle:
            os.fsync(handle.fileno())
        for directory in (library_directory, staging):
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        # The lock excludes another installer; the final rename publishes a complete tree.
        os.rename(staging, destination)
        descriptor = os.open(runtime_root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    return destination


def main() -> None:
    import fcntl

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, default=ROOT / "private/runtime")
    parser.add_argument("--archive", type=Path, help="Use a previously downloaded, checksum-pinned official archive.")
    parser.add_argument("--python", action="append", dest="interpreters", help="Interpreter to attest (repeatable). Default: current Python and existing research venv.")
    parser.add_argument("--check", action="store_true", help="Verify the installed library and actual Python bindings without a download or build.")
    args = parser.parse_args()
    os.umask(0o077)
    runtime_root = args.runtime_root.expanduser().absolute()
    interpreters = args.interpreters or [sys.executable]
    research_python = ROOT / ".venv-research/bin/python"
    if not args.interpreters and research_python.exists():
        interpreters.append(str(research_python))
    runtime = runtime_root / f"sqlite-{VERSION}"
    try:
        if not args.check:
            runtime_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            with (runtime_root / ".install.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                if not runtime.exists() and not runtime.is_symlink():
                    archive = args.archive.read_bytes() if args.archive else download_archive()
                    runtime = install(runtime_root, archive, interpreters)
        validate_runtime(runtime)
        for interpreter in interpreters:
            print(json.dumps(verify_python(interpreter, runtime), sort_keys=True))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
