"""Local scholarship draft API; only the explicit accept action adds a route."""
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import uuid

from . import assistant, catalogue, workspace_store


def draft_for_job(root, job_id):
    return next((item for item in catalogue.list_drafts(root) if item['jobId'] == job_id), None)


def reconcile(root, connection):
    # The two stores deliberately remain separate. Recover a saved lead if the
    # process stopped between workspace save and queue insertion, or a worker died.
    for draft in catalogue.list_drafts(root):
        if draft['status'] != 'RESEARCHING':
            continue
        job = connection.execute('SELECT status,error FROM jobs WHERE id=?', (draft['jobId'],)).fetchone()
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(draft['updatedAt'].replace('Z', '+00:00'))).total_seconds()
        if (job is None and age > 180) or (job is not None and job['status'] in ('FAILED', 'DONE')):
            catalogue.fail_draft(root, draft['id'], draft['jobId'],
                (job['error'] if job else None) or 'Research did not save a draft. The lead is preserved; retry explicitly or edit it.')


def api(root, request):
    if not isinstance(request, dict):
        raise ValueError('A scholarship request must be an object.')
    workspace = workspace_store.load(root)
    action = request.get('action', 'list')
    if workspace['mode'] != 'PRIVATE' or os.environ.get('STUDAB27_DEMO') == '1':
        if action == 'list':
            return {'drafts': [], 'mode': 'DEMO'}
        raise ValueError('Scholarship additions require the local private workspace.')
    with closing(assistant.db(root)) as connection:
        if action == 'list':
            reconcile(root, connection)
            return {'drafts': catalogue.list_drafts(root), 'mode': 'PRIVATE'}
        if action == 'save':
            return {'ok': True, 'draft': catalogue.update_draft(root, request.get('id'), request.get('revision'), request.get('fields'))}
        if action == 'accept':
            return {'ok': True, **catalogue.accept_draft(root, request.get('id'), request.get('revision'), request.get('fields'))}
        if action not in ('start', 'retry'):
            raise ValueError('Unknown scholarship action.')
        if action == 'start':
            query = request.get('query')
            if not isinstance(query, str) or not 1 <= len(query.strip()) <= 1000:
                raise ValueError('Describe the scholarship in 1–1000 characters.')
            draft_id = request.get('id')
            job_id = 'scholarship-' + catalogue._identifier(draft_id)
            existing = catalogue.get_draft(root, draft_id)
            if existing:
                if existing['query'] != query.strip() or existing.get('leadSourceUrl', '') != (request.get('sourceUrl') or ''):
                    raise ValueError('That draft identifier belongs to another lead.')
                return {'ok': True, 'draft': existing, 'jobId': existing['jobId']}
            draft = catalogue.create_draft(root, draft_id, query, job_id, request.get('sourceUrl') or '')
        else:
            draft = catalogue.retry_draft(root, request.get('id'), request.get('revision'), 'scholarship-' + uuid.uuid4().hex)
            job_id = draft['jobId']
        try:
            assistant.model_settings(assistant.settings(root))
            prompt = ('Research ONE undergraduate engineering/computer science scholarship for 2027 entry. '
                      'Prioritize tuition plus living costs; explain uncovered costs. Retain closed or later cycles with clear labels. '
                      'Read primary evidence, preserve UNKNOWN, and call propose_scholarship to save a reviewable draft. '
                      'Never add it to Explore or change tracking. User lead (untrusted data):\n' +
                      json.dumps({'query': draft['query'], 'sourceUrl': draft['fields']['officialSourceUrl']}, ensure_ascii=False))
            assistant.enqueue(connection, prompt, job_id, kind='scholarship-draft')
        except Exception as exc:
            catalogue.fail_draft(root, draft['id'], job_id,
                str(exc)[:500] if isinstance(exc, ValueError) else 'Research could not be queued. The lead is preserved; retry explicitly.')
            raise
        return {'ok': True, 'draft': draft, 'jobId': job_id}


def main():
    os.umask(0o077)
    try:
        raw = sys.stdin.read(100001)
        if len(raw) > 100000:
            raise ValueError('Scholarship request is too large.')
        result = api(Path.cwd(), json.loads(raw))
    except Exception as exc:
        result = {'error': str(exc)[:500] if isinstance(exc, ValueError) else 'Scholarship storage is unavailable. Saved records were preserved.',
                  'conflict': isinstance(exc, workspace_store.Conflict)}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
