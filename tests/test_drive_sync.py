from contextlib import closing
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from schola import drive_sync, workspace_store

ROOT = Path(__file__).resolve().parents[1]


class DriveExportChecks(unittest.TestCase):
    def fixture(self, root):
        shutil.copytree(ROOT / 'data/public', root / 'data/public')
        (root / 'private').mkdir(mode=0o700)
        for key in ('profile', 'overlay'):
            value = json.loads((root / f'data/public/{key}.example.json').read_text())
            if key == 'profile':
                value['mission'] = 'OWNER_ONLY_MARKER'
            (root / f'private/{key}.local.json').write_text(json.dumps(value))
        (root / 'private/hq.local.json').write_text(json.dumps({'private': 'OWNER_HQ_MARKER'}))

    def test_canonical_export_ignores_stale_legacy(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            current = workspace_store.load(root)
            current['profile']['mission'] = 'Current canonical mission'
            workspace_store.save(root, current, current['revision'], current['mode'])
            destination = drive_sync.export(root, root / 'private/exports/current')
            self.assertEqual(json.loads((destination / '00_HQ/profile.local.json').read_text())['mission'], 'Current canonical mission')
            self.assertEqual(json.loads((root / 'private/profile.local.json').read_text())['mission'], 'OWNER_ONLY_MARKER')

    def test_forced_demo_never_copies_owner_records_or_hq(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'STUDAB27_DEMO': '1'}):
            root = Path(directory)
            self.fixture(root)
            for initialized in (False, True):
                if initialized:
                    workspace_store.load(root)
                destination = drive_sync.export(root, root / f'private/exports/demo-{initialized}')
                contents = '\n'.join(path.read_text() for path in destination.rglob('*.json'))
                self.assertNotIn('OWNER_ONLY_MARKER', contents)
                self.assertNotIn('OWNER_HQ_MARKER', contents)
                self.assertFalse((destination / '00_HQ/hq.local.json').exists())


if __name__ == '__main__':
    unittest.main()
