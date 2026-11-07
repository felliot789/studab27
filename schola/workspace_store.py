"""Transactional private workspace. Public definitions and original files stay files.

Legacy JSON is imported once and retained unchanged. Entity rows preserve unknown
fields and retired catalogue identifiers so a definition update cannot erase work.
"""
from contextlib import closing
from datetime import date, datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

from .database import connect, ensure_wal
from .files import atomic_json

SCHEMA_VERSION = 1
MAX_WORKSPACE_BYTES = 16 * 1024 * 1024
MAX_REQUEST_BYTES = 32 * 1024 * 1024
DATA_KEYS = ('profile', 'overlays', 'milestones', 'state', 'inbox')

SCHEMA = [
    "CREATE TABLE workspace_meta(id INTEGER PRIMARY KEY CHECK(id=1),mode TEXT NOT NULL CHECK(mode IN ('PRIVATE','DEMO')),revision INTEGER NOT NULL CHECK(revision>0),state_extra TEXT NOT NULL CHECK(json_valid(state_extra) AND json_type(state_extra)='object'))",
    "CREATE TABLE profile(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL CHECK(json_valid(body) AND json_type(body)='object'))",
    "CREATE TABLE route_plans(route_id TEXT PRIMARY KEY NOT NULL,position INTEGER NOT NULL UNIQUE CHECK(position>=0),body TEXT NOT NULL CHECK(json_valid(body) AND json_type(body)='object' AND json_extract(body,'$.routeId') IS route_id),main_target INTEGER GENERATED ALWAYS AS (json_extract(body,'$.mainTarget') IS 1) STORED,CHECK(main_target=0 OR (json_extract(body,'$.tracked') IS 1 AND json_extract(body,'$.pursuitLevel') IS 'FOCUS')))",
    "CREATE UNIQUE INDEX one_main_target ON route_plans(main_target) WHERE main_target=1",
    "CREATE TABLE milestones(position INTEGER PRIMARY KEY CHECK(position>=0),body TEXT NOT NULL CHECK(json_valid(body) AND json_type(body)='object'))",
    "CREATE TABLE inbox(id TEXT PRIMARY KEY NOT NULL,position INTEGER NOT NULL UNIQUE CHECK(position>=0),body TEXT NOT NULL CHECK(json_valid(body) AND json_type(body)='object' AND json_extract(body,'$.id') IS id AND COALESCE(json_extract(body,'$.status') IN ('NEW','TRIAGED'),0)))",
    "CREATE TABLE task_progress(task_id TEXT PRIMARY KEY NOT NULL,body TEXT NOT NULL CHECK(json_valid(body) AND json_type(body)='object' AND (json_type(body,'$.status') IS NULL OR json_extract(body,'$.status') IS 'DONE')))",
    "CREATE TABLE brick_progress(item_key TEXT PRIMARY KEY NOT NULL,done INTEGER NOT NULL CHECK(done IN (0,1)))",
    "CREATE TABLE requirement_progress(route_id TEXT NOT NULL REFERENCES route_plans(route_id),item_id TEXT NOT NULL,body TEXT NOT NULL CHECK(json_valid(body) AND json_type(body)='object' AND COALESCE(json_extract(body,'$.status') IN ('TODO','DOING','DONE','NOT_NEEDED'),0)),PRIMARY KEY(route_id,item_id))",
    "CREATE TABLE migrations(version INTEGER PRIMARY KEY,applied_at TEXT NOT NULL,description TEXT NOT NULL)",
]


class Conflict(ValueError):
    pass


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def database_path(root):
    name = 'demo-workspace.sqlite3' if os.environ.get('STUDAB27_DEMO') == '1' else 'workspace.sqlite3'
    return Path(root) / 'private' / name


def _read_json(path, fallback=None):
    if not path.exists():
        return fallback
    return json.loads(path.read_text())


def _legacy(root):
    root = Path(root)
    vault, public = root / 'private', root / 'data/public'
    forced_demo = os.environ.get('STUDAB27_DEMO') == '1'
    present = [(vault / f'{name}.local.json').exists() for name in ('profile', 'overlay')]
    if not forced_demo and any(present) and not all(present):
        raise ValueError('The private vault is incomplete. Restore both profile and overlay; existing records were preserved.')
    private = not forced_demo and all(present)
    sources = {
        'profile': vault / 'profile.local.json' if private else public / 'profile.example.json',
        'overlays': vault / ('overlay.local.json' if private else 'demo-overlay.local.json'),
        'milestones': vault / 'milestones.local.json' if private else None,
        'state': vault / ('state.local.json' if private else 'demo-state.local.json'),
        'inbox': vault / ('inbox.local.json' if private else 'demo-inbox.local.json'),
    }
    def fingerprints():
        return {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in sources.items() if path and path.exists()}
    before = fingerprints()
    value = {
        'mode': 'PRIVATE' if private else 'DEMO',
        'profile': _read_json(sources['profile']),
        'overlays': _read_json(sources['overlays'], _read_json(public / 'overlay.example.json')),
        'milestones': _read_json(sources['milestones'], []) if private else [],
        'state': _read_json(sources['state'], {'tasks': {}, 'bricks': {}}),
        'inbox': _read_json(sources['inbox'], []),
    }
    if fingerprints() != before:
        raise Conflict('Legacy workspace changed during migration. Retry after the old writer has stopped.')
    return value


def validate(value):
    if not isinstance(value, dict) or not all(key in value for key in DATA_KEYS):
        raise ValueError('A complete workspace is required.')
    if len(encoded({key: value[key] for key in DATA_KEYS}).encode('utf-8')) > MAX_WORKSPACE_BYTES:
        raise ValueError('Workspace exceeds the supported 16 MiB limit; existing records were preserved.')
    if not isinstance(value['profile'], dict) or not isinstance(value['profile'].get('snapshot'), dict):
        raise ValueError('Invalid workspace profile.')
    if not all(isinstance(value[key], list) for key in ('overlays', 'milestones', 'inbox')):
        raise ValueError('Workspace lists are required.')
    state = value['state']
    if not isinstance(state, dict) or not all(isinstance(state.get(key), dict) for key in ('tasks', 'bricks')):
        raise ValueError('Workspace progress objects are required.')
    plans = [plan.get('routeId') if isinstance(plan, dict) else None for plan in value['overlays']]
    if any(not isinstance(key, str) or not 1 <= len(key) <= 150 for key in plans) or len(set(plans)) != len(plans):
        raise ValueError('Route plans require unique scholarship identifiers.')
    for milestone in value['milestones']:
        if not isinstance(milestone, dict) or not isinstance(milestone.get('title'), str) or len(milestone['title']) > 1000:
            raise ValueError('Milestones require a bounded title.')
        try:
            if date.fromisoformat(milestone['date']).isoformat() != milestone['date']:
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise ValueError('Milestones require a valid ISO calendar date.') from None
    inbox_ids = [item.get('id') if isinstance(item, dict) else None for item in value['inbox']]
    if any(not isinstance(key, str) or not key for key in inbox_ids) or len(set(inbox_ids)) != len(inbox_ids):
        raise ValueError('Inbox records require unique identifiers.')
    if len(value['inbox']) > 500 or any(not isinstance(item.get('text'), str) or len(item['text']) > 4000 or item.get('status') not in ('NEW', 'TRIAGED') for item in value['inbox']):
        raise ValueError('Invalid inbox records.')
    if any(not isinstance(progress, dict) for progress in state['tasks'].values()) or any(type(done) is not bool for done in state['bricks'].values()):
        raise ValueError('Invalid task or reusable document progress.')
    requirements = state.get('requirements', {})
    if not isinstance(requirements, dict):
        raise ValueError('Invalid scholarship progress.')
    for route_id, entries in requirements.items():
        if route_id not in plans or not isinstance(entries, dict):
            raise ValueError('Scholarship progress must reference a retained route plan.')
        for item_id, progress in entries.items():
            if not isinstance(item_id, str) or not item_id or not isinstance(progress, dict) or progress.get('status') not in ('TODO', 'DOING', 'DONE', 'NOT_NEEDED'):
                raise ValueError('Invalid scholarship progress record.')
            if 'note' in progress and (not isinstance(progress['note'], str) or len(progress['note']) > 2000):
                raise ValueError('Invalid scholarship progress note.')


def _write_rows(connection, value, revision):
    validate(value)
    state = value['state']
    for table in ('requirement_progress', 'route_plans', 'profile', 'milestones', 'inbox', 'task_progress', 'brick_progress', 'workspace_meta'):
        connection.execute(f'DELETE FROM {table}')
    extra = {key: item for key, item in state.items() if key not in ('tasks', 'bricks', 'requirements')}
    if 'requirements' in state:
        extra['requirements'] = {key: {} for key in state['requirements']}
    connection.execute('INSERT INTO workspace_meta VALUES(1,?,?,?)', (value['mode'], revision, encoded(extra)))
    connection.execute('INSERT INTO profile VALUES(1,?)', (encoded(value['profile']),))
    connection.executemany('INSERT INTO route_plans(route_id,position,body) VALUES(?,?,?)', [(plan['routeId'], index, encoded(plan)) for index, plan in enumerate(value['overlays'])])
    connection.executemany('INSERT INTO milestones VALUES(?,?)', [(index, encoded(item)) for index, item in enumerate(value['milestones'])])
    connection.executemany('INSERT INTO inbox VALUES(?,?,?)', [(item['id'], index, encoded(item)) for index, item in enumerate(value['inbox'])])
    connection.executemany('INSERT INTO task_progress VALUES(?,?)', [(key, encoded(item)) for key, item in state['tasks'].items()])
    connection.executemany('INSERT INTO brick_progress VALUES(?,?)', [(key, int(done)) for key, done in state['bricks'].items()])
    connection.executemany('INSERT INTO requirement_progress VALUES(?,?,?)', [(route_id, key, encoded(item)) for route_id, items in state.get('requirements', {}).items() for key, item in items.items()])


def _snapshot(connection):
    meta = connection.execute('SELECT * FROM workspace_meta WHERE id=1').fetchone()
    if meta is None:
        raise ValueError('Workspace initialization is incomplete; existing files were preserved.')
    state = json.loads(meta['state_extra'])
    state['tasks'] = {row['task_id']: json.loads(row['body']) for row in connection.execute('SELECT * FROM task_progress')}
    state['bricks'] = {row['item_key']: bool(row['done']) for row in connection.execute('SELECT * FROM brick_progress')}
    entries = connection.execute('SELECT * FROM requirement_progress').fetchall()
    if entries:
        state.setdefault('requirements', {})
        for row in entries:
            state['requirements'].setdefault(row['route_id'], {})[row['item_id']] = json.loads(row['body'])
    return {'mode': meta['mode'], 'revision': meta['revision'],
            'profile': json.loads(connection.execute('SELECT body FROM profile WHERE id=1').fetchone()[0]),
            'overlays': [json.loads(row['body']) for row in connection.execute('SELECT body FROM route_plans ORDER BY position')],
            'milestones': [json.loads(row['body']) for row in connection.execute('SELECT body FROM milestones ORDER BY position')],
            'inbox': [json.loads(row['body']) for row in connection.execute('SELECT body FROM inbox ORDER BY position')], 'state': state}


def snapshot_if_initialized(root):
    path = database_path(root)
    if not path.exists():
        return None
    with closing(connect(path, readonly=True)) as connection:
        version = connection.execute('PRAGMA user_version').fetchone()[0]
        if version != SCHEMA_VERSION:
            raise ValueError('Workspace schema needs a compatible migration; existing records were preserved.')
        connection.execute('BEGIN')
        try:
            result = _snapshot(connection)
            connection.execute('COMMIT')
            return result
        except Exception:
            connection.execute('ROLLBACK')
            raise


def load(root):
    path = database_path(root)
    vault = path.parent
    vault.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (vault / 'workspace-migration.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with closing(connect(path)) as connection:
            version = connection.execute('PRAGMA user_version').fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError('This workspace was written by a newer application; use a compatible release.')
            ensure_wal(connection)
            if version == 0:
                value = _legacy(root)
                validate(value)
                backup = vault / 'backups' / ('workspace-seed-' + uuid.uuid4().hex + '.local.json')
                atomic_json(backup, {'format': 'studab27-v1', **value})
                connection.execute('BEGIN IMMEDIATE')
                try:
                    for statement in SCHEMA:
                        connection.execute(statement)
                    _write_rows(connection, value, 1)
                    connection.execute('INSERT INTO migrations VALUES(?,?,?)', (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat(), 'Legacy JSON imported without changing source files'))
                    connection.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
                    connection.execute('COMMIT')
                except Exception:
                    connection.execute('ROLLBACK')
                    raise
    result = snapshot_if_initialized(root)
    # bootstrap-private remains an explicit way to activate an owner vault after
    # a fresh clone has already been used in demo mode.
    if result['mode'] == 'DEMO' and os.environ.get('STUDAB27_DEMO') != '1' and all((vault / f'{name}.local.json').exists() for name in ('profile', 'overlay')):
        value = _legacy(root)
        return save(root, value, result['revision'], 'DEMO', target_mode='PRIVATE', backup=True)
    return result


def save(root, value, expected_revision, expected_mode, *, target_mode=None, backup=False):
    if type(expected_revision) is not int or expected_revision < 1 or expected_mode not in ('PRIVATE', 'DEMO'):
        raise ValueError('A workspace revision is required.')
    path = database_path(root)
    target_mode = target_mode or expected_mode
    if target_mode not in ('PRIVATE', 'DEMO') or (os.environ.get('STUDAB27_DEMO') == '1' and target_mode != 'DEMO'):
        raise ValueError('Import is disabled while demo mode is forced.')
    if target_mode != expected_mode and not (expected_mode == 'DEMO' and target_mode == 'PRIVATE'):
        raise ValueError('A private workspace cannot be downgraded to demo mode.')
    value = {**value, 'mode': target_mode}
    validate(value)
    with closing(connect(path)) as connection:
        if connection.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION:
            raise ValueError('A compatible workspace migration is required.')
        connection.execute('BEGIN IMMEDIATE')
        try:
            current = _snapshot(connection)
            if current['revision'] != expected_revision or current['mode'] != expected_mode:
                raise Conflict('Another request changed the workspace. Refresh and retry; no changes from this request were saved.')
            if backup:
                stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
                atomic_json(path.parent / 'backups' / f'before-import-{stamp}.local.json', {'format': 'studab27-v1', **current})
            _write_rows(connection, value, expected_revision + 1)
            result = _snapshot(connection)
            connection.execute('COMMIT')
            return result
        except Exception:
            connection.execute('ROLLBACK')
            raise


def api(root, request):
    current = load(root)
    if request.get('action', 'load') == 'load':
        return current
    if request.get('action') == 'save':
        result = save(root, request.get('workspace'), request.get('revision'), request.get('mode'), target_mode=request.get('targetMode'), backup=request.get('backup') is True)
        return {'ok': True, 'revision': result['revision'], 'mode': result['mode']}
    raise ValueError('Unknown workspace action.')


def main():
    os.umask(0o077)
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES:
            raise ValueError('Workspace request is too large.')
        request = json.loads(raw or b'{}')
        if not isinstance(request, dict):
            raise ValueError('A workspace request object is required.')
        print(encoded(api(Path.cwd(), request)))
    except Conflict as exc:
        print(encoded({'error': str(exc), 'conflict': True}))
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else 'The local workspace needs attention. Existing records were preserved.'
        print(encoded({'error': message[:500]}))


if __name__ == '__main__':
    main()
