from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile


package_root = Path(__file__).resolve().parents[1]
src = package_root / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from systems_monitor_data.pipeline import write_review_candidate  # noqa: E402
from systems_monitor_data.publication import AtomicPublisher  # noqa: E402


candidate_path = package_root / "review" / "factual-snapshot-candidate.json"
proof_path = package_root / "review" / "local-active-pdi-test-snapshot.json"
candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
activated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
with tempfile.TemporaryDirectory() as temporary:
    publisher = AtomicPublisher(Path(temporary) / "local-publication-proof")
    candidate_digest, _ = publisher.stage(candidate)
    active_digest, active_path = publisher.activate_local(candidate_digest, activated_at=activated_at)
    pointer = json.loads(publisher.pointer.read_text(encoding="utf-8"))
    if pointer["sha256"] != active_digest:
        raise RuntimeError("local activation proof pointer mismatch")
    active_snapshot = json.loads(active_path.read_text(encoding="utf-8"))
proof_digest = write_review_candidate(proof_path, active_snapshot)
if proof_digest != active_digest:
    raise RuntimeError("local activation proof hash mismatch")
print(json.dumps({"activatedAt": activated_at, "candidateSha256": candidate_digest, "activeSnapshot": str(proof_path), "activeSha256": active_digest, "publicActivation": False}, sort_keys=True))
