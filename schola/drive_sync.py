"""Offline Drive mirror export. No cloud credentials or automatic uploads."""
import argparse
import json
from pathlib import Path

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
    for filename, folder in (("profile", "00_HQ"), ("hq", "00_HQ"), ("overlay", "00_HQ"), ("milestones", "00_HQ"), ("state", "00_HQ"), ("inbox", "07_Inbox")):
        source = vault / f"{filename}.local.json"
        if source.exists():
            target = destination / folder / source.name
            target.write_bytes(source.read_bytes())
            target.chmod(0o600)
    target = destination / "01_Catalogue" / "scholarships_2027.json"
    target.write_bytes((root / "data/public/scholarships_2027.json").read_bytes())
    (destination / "00_HQ/export-manifest.local.json").write_text(json.dumps({"format": "studab27-drive-mirror-v1", "cloudSynced": False, "folders": FOLDERS}, indent=2))
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(export(Path(__file__).resolve().parents[1], args.destination))
