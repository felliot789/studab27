"""One local configuration file. Keys never cross the browser boundary."""
import json
from pathlib import Path
from urllib.parse import urlsplit


def load(root):
    path = Path(root) / "private/schola.local.json"
    if not path.exists():
        return {"llm": {}, "search": {"provider": "disabled"}, "background": {"enabled": False}}
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("Schola configuration must be an object")
    return value


def model_settings(config):
    llm = config.get("llm", {})
    endpoint = str(llm.get("baseUrl", "")).rstrip("/")
    parsed = urlsplit(endpoint)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Set llm.baseUrl to a trusted custom v1 endpoint")
    if parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("Remote model endpoints require HTTPS")
    if not llm.get("model") or not llm.get("apiKey"):
        raise ValueError("Set llm.model and llm.apiKey in the local configuration")
    return llm, endpoint


def public_status(config):
    llm = config.get("llm", {})
    return {"configured": bool(llm.get("baseUrl") and llm.get("model") and llm.get("apiKey")),
            "model": str(llm.get("model", "Not configured")),
            "contextAllowed": config.get("contextAllowed") is True,
            "dailyCallLimit": int(llm.get("dailyCallLimit", 80)),
            "searchProvider": config.get("search", {}).get("provider", "disabled"),
            "backgroundEnabled": config.get("background", {}).get("enabled") is True}
