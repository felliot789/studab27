"""Shared SQLite connection policy for private, local stores."""
from pathlib import Path
import sqlite3


BUSY_TIMEOUT_MS = 5000


def ensure_wal(connection):
    """Restore normal journaling after schema validation, including restores."""
    mode = connection.execute("PRAGMA journal_mode").fetchone()[0].lower()
    if mode != "wal":
        mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower()
    if mode != "wal":
        raise ValueError("The local database could not enable WAL journaling; existing records were preserved.")


def connect(path: Path, readonly=False):
    path = Path(path).resolve()
    is_new = not path.exists()
    if not readonly:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    connection = sqlite3.connect(path.as_uri() + ("?mode=ro" if readonly else "?mode=rwc"),
                                 uri=True, timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        if readonly:
            connection.execute("PRAGMA query_only=ON")
        else:
            path.chmod(0o600)
            connection.execute("PRAGMA synchronous=FULL")
            if is_new:
                ensure_wal(connection)
        return connection
    except Exception:
        connection.close()
        raise
