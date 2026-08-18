from __future__ import annotations

import json
from pathlib import Path


candidate_path = Path(__file__).resolve().parents[1] / "review" / "factual-snapshot-candidate.json"
candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
encoded = json.dumps(json.dumps(candidate, separators=(",", ":")))
print(f'localStorage.setItem("auxsays.localFactualCandidate", {encoded}); location.reload();')

