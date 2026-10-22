from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunTelemetry:
    run_id: str
    source_id: str
    started_time: str
    ended_time: str
    retrieval_status: str
    validation_status: str
    retry_count: int
    source_latency_ms: int
    records_accepted: int
    records_rejected: int
    artifact_sha256: str | None
    snapshot_candidate_id: str | None
    publication_candidate_result: str


def append_telemetry(path: Path, event: RunTelemetry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(asdict(event), sort_keys=True)
    lowered = serialized.lower()
    if any(token in lowered for token in ("registrationkey", "authorization", "api_key")):
        raise ValueError("telemetry contains secret-shaped content")
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(serialized + "\n")

