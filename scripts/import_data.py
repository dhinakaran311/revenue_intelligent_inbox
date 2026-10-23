"""Import a delivery JSON file via the revision-aware importer.

Usage:
    python scripts/import_data.py data/01_initial.json

Loads the file, reads the delivery-level revision (DATA_CONTRACT.md stores
revision at the delivery level, applying it to every record), computes a
sha256 checksum of the file bytes, and calls importer.import_delivery().

Prints accepted / ignored / replaced / errors counts.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app import importer


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("Usage: python scripts/import_data.py <delivery.json>")
        return 2

    path = Path(argv[0])
    if not path.exists():
        print(f"ERROR: file not found: {path}")
        return 2

    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))

    records = data.get("records", [])
    revision = data.get("revision")
    checksum = hashlib.sha256(raw).hexdigest()

    if revision is None:
        print("ERROR: delivery file has no top-level 'revision' field.")
        return 2

    print(f"Importing {path.name}: {len(records)} records, delivery revision {revision}")
    result = importer.import_delivery(
        records, revision, filename=str(path), checksum=checksum
    )

    print(
        f"  accepted={result.get('accepted', 0)}  "
        f"ignored={result.get('ignored', 0)}  "
        f"replaced={result.get('replaced', 0)}  "
        f"errors={len(result.get('errors', []))}"
    )
    if result.get("errors"):
        print("  errors:")
        for e in result["errors"][:10]:
            print(f"    {e}")
        if len(result["errors"]) > 10:
            print(f"    ... and {len(result['errors']) - 10} more")
    return 0 if not result.get("errors") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
