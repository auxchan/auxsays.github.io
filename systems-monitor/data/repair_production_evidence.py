"""Recover exact original raw objects and metadata; never rewrite accepted rows."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from systems_monitor_data.production import _atomic_json
from systems_monitor_data.production_integrity import payload_sha256, validate_production_evidence


def repair(output: Path, stores: list[Path]) -> dict:
    document = json.loads(output.read_text(encoding="utf-8"))
    if document["payloadSha256"] != payload_sha256(document):
        raise ValueError("refusing to repair a corrupted seed")
    original_history = copy.deepcopy(document["acceptedHistory"])
    records = {r["sha256"]: r for r in document["rawEvidence"]}
    missing = {r["artifactSha256"] for r in original_history["observations"]} - records.keys()
    found = {}
    for root in stores:
        for event in sorted((root / "events").glob("*.json")):
            record = json.loads(event.read_text(encoding="utf-8"))
            digest = record.get("sha256")
            if digest not in missing:
                continue
            source = (root / record["relative_path"]).resolve()
            if not source.is_relative_to(root.resolve()):
                raise ValueError("recovery path escapes supplied store")
            if source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() == digest:
                found.setdefault(digest, (record, source))
    if missing - found.keys():
        raise ValueError(f"unrecoverable original evidence: {sorted(missing - found.keys())}")
    for digest, (record, source) in sorted(found.items()):
        target = output.parent / "raw" / record["relative_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise ValueError("existing recovery target differs")
        if not target.exists():
            shutil.copyfile(source, target)
        records[digest] = {**record, "repositoryPath": "systems-monitor/data/production/raw/" + record["relative_path"]}
    document["rawEvidence"] = [records[key] for key in sorted(records)]
    document["payloadSha256"] = payload_sha256(document)
    result = validate_production_evidence(document, output.parent / "raw")
    assert document["acceptedHistory"] == original_history
    result.update({"recoveredRawArtifacts": len(found), "acceptedHistoryUnchanged": True, "changed": _atomic_json(output, document)})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-store", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "production/systems-monitor-production.json")
    args = parser.parse_args()
    print(json.dumps(repair(args.output, args.raw_store), indent=2))
