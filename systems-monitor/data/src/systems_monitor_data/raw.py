from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class RawArtifactRecord:
    source_id: str
    run_id: str
    request_identity: str
    retrieved_time: str
    release_id: str
    content_type: str
    byte_length: int
    sha256: str
    parser_version: str
    rights_result: str
    relative_path: str


class RawStore:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def capture(self, *, source_id: str, run_id: str, request_identity: str, retrieved_time: str, release_id: str, content_type: str, body: bytes, parser_version: str, rights_result: str) -> RawArtifactRecord:
        digest = hashlib.sha256(body).hexdigest()
        suffix = ".json" if content_type == "application/json" else ".pdf" if content_type == "application/pdf" else ".bin"
        object_dir = self.root / "objects" / digest[:2]
        object_dir.mkdir(parents=True, exist_ok=True)
        object_path = object_dir / f"{digest}{suffix}"
        if not object_path.exists():
            try:
                descriptor = os.open(object_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(body)
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError:
                pass
        if hashlib.sha256(object_path.read_bytes()).hexdigest() != digest:
            raise RuntimeError("content-addressed object verification failed")
        record = RawArtifactRecord(source_id, run_id, request_identity, retrieved_time, release_id, content_type, len(body), digest, parser_version, rights_result, object_path.relative_to(self.root).as_posix())
        event_dir = self.root / "events"
        event_dir.mkdir(parents=True, exist_ok=True)
        event_key = hashlib.sha256(f"{source_id}|{run_id}|{release_id}|{digest}".encode()).hexdigest()
        event_path = event_dir / f"{event_key}.json"
        if not event_path.exists():
            event_path.write_text(json.dumps(asdict(record), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return record

    def tombstone(self, sha256: str, cause: str, effective_time: str) -> Path:
        candidates = list((self.root / "objects" / sha256[:2]).glob(f"{sha256}.*"))
        for path in candidates:
            path.unlink()
        tombstones = self.root / "tombstones"
        tombstones.mkdir(parents=True, exist_ok=True)
        path = tombstones / f"{sha256}.json"
        path.write_text(json.dumps({"sha256": sha256, "cause": cause, "effective_time": effective_time, "bytes_deleted": True, "reproduction_degraded": True}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

