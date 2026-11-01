"""Initialize an ignored vault from an explicitly supplied seed, or fictional demo.

Existing files are never overwritten. The source document stays outside Git.
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def seed_blocks(path):
    blocks = re.findall(r"```json\s*\n(.*?)\n```", path.read_text(), re.S)
    values = [json.loads(block) for block in blocks]
    if len(values) != 4 or len(values[0]) != 57 or len(values[3]) != 57:
        raise ValueError("Expected a catalogue, profile, milestones, and 57 overlays")
    if {r["id"] for r in values[0]} != {r["routeId"] for r in values[3]}:
        raise ValueError("Catalogue and overlay identifiers do not match")
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, help="Private source markdown; never committed")
    args = parser.parse_args()
    if args.seed:
        _, profile, milestones, overlays = seed_blocks(args.seed)
    else:
        profile = json.loads((ROOT / "data/public/profile.example.json").read_text())
        overlays = json.loads((ROOT / "data/public/overlay.example.json").read_text())
        milestones = []
    vault = ROOT / "private"
    vault.mkdir(exist_ok=True, mode=0o700)
    vault.chmod(0o700)
    for name, value in (("profile", profile), ("overlay", overlays), ("milestones", milestones), ("inbox", [])):
        target = vault / f"{name}.local.json"
        if target.exists():
            print(f"Preserved existing {target.name}")
            continue
        with target.open("x") as f:
            target.chmod(0o600)
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"Initialized ignored {target.name}")


if __name__ == "__main__":
    main()
