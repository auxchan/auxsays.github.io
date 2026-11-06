"""Verify immutable production evidence, including every historical observation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def payload_sha256(document: dict[str, Any]) -> str:
    body = {key: value for key, value in document.items() if key != "payloadSha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def validate_production_evidence(document: dict[str, Any], raw_root: Path) -> dict[str, int]:
    if document.get("payloadSha256") != payload_sha256(document):
        raise ValueError("production payload hash mismatch")
    root = raw_root.resolve()
    manifest: dict[str, Any] = {}
    for record in document["rawEvidence"]:
        digest = record["sha256"]
        if digest in manifest:
            raise ValueError("duplicate production raw hash")
        relative = Path(record["relative_path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or relative.parts[:1] != ("objects",):
            raise ValueError("raw evidence path escapes the production object store")
        if record["repositoryPath"] != "systems-monitor/data/production/raw/" + relative.as_posix():
            raise ValueError("raw evidence repository path mismatch")
        if not path.is_file():
            raise ValueError(f"missing production raw artifact: {digest}")
        body = path.read_bytes()
        if len(body) != record["byte_length"] or hashlib.sha256(body).hexdigest() != digest:
            raise ValueError(f"production raw artifact integrity failure: {digest}")
        if record["rights_result"] != "ALLOW":
            raise ValueError("production evidence has no allowed rights state")
        manifest[digest] = record
    observations = document["acceptedHistory"]["observations"]
    missing = {row["artifactSha256"] for row in observations} - manifest.keys()
    if missing:
        raise ValueError(f"accepted history has unmanifested raw evidence: {sorted(missing)}")
    return {"historyRows": len(observations), "verifiedHistoryRows": len(observations), "rawArtifacts": len(manifest), "missingHistoryArtifacts": 0}
