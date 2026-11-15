"""Compute request-local dashboard views in one Python invocation."""
import json
import sys

from .evaluator import evaluate_all
from .spoonfeeder import briefing, task_pool


def evaluate_dashboard(payload):
    context = {**payload, "tasks": task_pool(payload)}
    return {"evaluations": evaluate_all(context), "briefing": briefing(context)}


if __name__ == "__main__":
    json.dump(evaluate_dashboard(json.load(sys.stdin)), sys.stdout)
