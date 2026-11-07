"""Local database migration and recovery health; never prints private records."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3

from .database import connect
from .workspace_store import load, SCHEMA_VERSION
from .assistant import db, CHAT_SCHEMA_VERSION
from .recovery import health


def migrate(root):
    path = root / 'private/schola.sqlite3'
    if path.exists():
        with closing(connect(path, readonly=True)) as connection:
            active = connection.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('QUEUED','RUNNING')").fetchone()[0]
            if active:
                raise ValueError('Wait for queued and running Schola jobs before migration.')
    workspace = load(root)
    with closing(db(root)) as connection:
        if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise ValueError('Conversation integrity check failed; preserve migration backups and inspect locally.')
    return {'ok': True, 'workspaceSchema': SCHEMA_VERSION, 'chatSchema': CHAT_SCHEMA_VERSION,
            'workspaceMode': workspace['mode'], 'workspaceRevision': workspace['revision'], 'sqlite': sqlite3.sqlite_version}


def status(root):
    stores = {}
    for name, expected in [('workspace', SCHEMA_VERSION), ('schola', CHAT_SCHEMA_VERSION)]:
        path = root / 'private' / f'{name}.sqlite3'
        if not path.exists():
            stores[name] = {'state': 'MISSING'}
            continue
        with closing(connect(path, readonly=True)) as connection:
            version = connection.execute('PRAGMA user_version').fetchone()[0]
            valid = connection.execute('PRAGMA quick_check').fetchone()[0] == 'ok' and connection.execute('PRAGMA foreign_key_check').fetchone() is None
            stores[name] = {'state': 'OK' if valid and version == expected else 'NEEDS_ATTENTION', 'schemaVersion': version, 'bytes': path.stat().st_size}
            if name == 'schola':
                metadata = {row['key']: json.loads(row['value']) for row in connection.execute("SELECT key,value FROM kv WHERE key IN ('heartbeat','worker_error','worker_last_error_at')")}
                heartbeat = metadata.get('heartbeat')
                alive = bool(heartbeat) and (datetime.now(timezone.utc) - datetime.fromisoformat(heartbeat)).total_seconds() < 240
                stores[name]['worker'] = {'alive': alive, 'errorCode': metadata.get('worker_error'), 'lastErrorAt': metadata.get('worker_last_error_at')}
                stores[name]['activeJobs'] = connection.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('QUEUED','RUNNING')").fetchone()[0]
    return {'sqlite': sqlite3.sqlite_version, 'stores': stores, 'recovery': health(root)}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('action', choices=['migrate', 'health'])
    args = parser.parse_args()
    try:
        result = migrate(args.root.resolve()) if args.action == 'migrate' else status(args.root.resolve())
        print(json.dumps(result))
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc) if isinstance(exc, ValueError) else 'Local database maintenance needs attention; existing records were preserved.'}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
