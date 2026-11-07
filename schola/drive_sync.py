"""Offline Drive mirror export. No cloud credentials or automatic uploads."""
import argparse
import json
from pathlib import Path

from .files import atomic_json, atomic_write
from .workspace_store import snapshot_if_initialized, _legacy

FOLDERS = ["00_HQ", "01_Catalogue", "02_Applications", "03_School_Documents", "04_Financial_Documents", "05_Profile_Evidence", "06_Offers_and_Decisions", "07_Inbox", "99_Archive"]


def export(root, destination):
    vault = root / "private"
    destination = destination.resolve()
    if not destination.is_relative_to(vault.resolve()):
        raise ValueError("Export destination must stay inside the ignored private vault")
    if destination.exists():
        raise ValueError("Existing exports are preserved; choose a new destination")
    for folder in FOLDERS:
        (destination / folder).mkdir(parents=True, mode=0o700)
    workspace = snapshot_if_initialized(root) or _legacy(root)
    for filename, folder in (("profile", "00_HQ"), ("hq", "00_HQ"), ("overlay", "00_HQ"), ("milestones", "00_HQ"), ("state", "00_HQ"), ("inbox", "07_Inbox")):
        source = vault / f"{filename}.local.json"
        key = "overlays" if filename == "overlay" else filename
        target = destination / folder / source.name
        if workspace is not None and key in workspace:
            atomic_json(target, workspace[key])
        elif filename == "hq" and workspace["mode"] == "PRIVATE" and source.exists():
            atomic_write(target, source.read_bytes())
    target = destination / "01_Catalogue" / "scholarships_2027.json"
    atomic_write(target, (root / "data/public/scholarships_2027.json").read_bytes())
    atomic_json(destination / "00_HQ/export-manifest.local.json", {"format": "studab27-drive-mirror-v1", "cloudSynced": False, "folders": FOLDERS, "workspaceRevision": workspace.get("revision")})
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(export(Path(__file__).resolve().parents[1], args.destination))
