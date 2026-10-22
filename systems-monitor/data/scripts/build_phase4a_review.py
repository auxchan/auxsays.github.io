from __future__ import annotations

import json
from pathlib import Path
import sys
import time
import tracemalloc

PACKAGE = Path(__file__).resolve().parents[1]
SRC = PACKAGE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from systems_monitor_data.phase4a import build_phase4a_candidate


def main() -> None:
    repo = PACKAGE.parents[1]
    review_dir = repo / "systems-monitor" / "state" / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    tracemalloc.start()
    start = time.perf_counter()
    candidate = build_phase4a_candidate(
        review_model_path=PACKAGE / "review" / "internal-factual-review-model.json",
        config_root=PACKAGE / "config",
    )
    runtime_ms = (time.perf_counter() - start) * 1000
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    output = review_dir / "phase4a-read-model-candidate.json"
    payload = (json.dumps(candidate, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    output.write_bytes(payload)
    print(json.dumps({
        "candidateId": candidate["candidateId"],
        "runtimeMs": round(runtime_ms, 3),
        "peakMemoryBytes": peak_bytes,
        "outputBytes": len(payload),
        "relationships": len(candidate["acceptedRelationships"]),
        "traversals": candidate["propagationRun"]["traversalCount"],
        "contributions": candidate["propagationRun"]["contributionCount"],
        "maxDepthReached": candidate["propagationRun"]["maxDepthReached"],
        "roundsUsed": candidate["propagationRun"]["roundsUsed"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
