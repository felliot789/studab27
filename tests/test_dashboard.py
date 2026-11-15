from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from schola.dashboard import evaluate_dashboard
from schola.evaluator import evaluate_all
from schola.spoonfeeder import briefing, task_pool


ROOT = Path(__file__).resolve().parents[1]


class DashboardChecks(unittest.TestCase):
    def test_combined_bridge_preserves_evaluations_and_generated_task_state(self):
        public = ROOT / "data/public"
        def read(name):
            return json.loads((public / name).read_text())
        payload = {
            "routes": read("scholarships_2027.json"),
            "profile": read("profile.example.json"),
            "overlays": read("overlay.example.json"),
            "tasks": read("tasks.json"),
            "bricks": read("bricks.json"),
            "milestones": [],
            "state": {"tasks": {}, "bricks": {}},
        }
        pool = task_pool(payload)
        generated = [task for task in pool if task.get("generated")]
        payload["state"]["tasks"] = {
            generated[0]["id"]: {"status": "DONE"},
            generated[1]["id"]: {"snoozedUntil": "2999-01-01T00:00:00Z"},
            generated[2]["id"]: {"replacedAt": "2026-01-01T00:00:00Z"},
        }
        before = deepcopy(payload)
        expected = {"evaluations": evaluate_all(payload), "briefing": briefing({**payload, "tasks": pool})}
        self.assertEqual(evaluate_dashboard(payload), expected)
        self.assertEqual(payload, before)
        self.assertLessEqual(len(expected["briefing"]["cards"]), 3)
        result = subprocess.run([sys.executable, "-m", "schola.dashboard"], cwd=ROOT,
                                input=json.dumps(payload), capture_output=True, text=True,
                                check=True, timeout=10)
        self.assertEqual(json.loads(result.stdout), expected)
