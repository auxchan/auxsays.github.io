from __future__ import annotations

import json
from pathlib import Path


candidate_path = Path(__file__).resolve().parents[1] / "review" / "factual-snapshot-candidate.json"
candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
phase4b_path = Path(__file__).resolve().parents[2] / "state" / "review" / "phase4b-read-model-candidate.json"
phase4b = json.loads(phase4b_path.read_text(encoding="utf-8"))
encoded_candidate = json.dumps(json.dumps(candidate, separators=(",", ":")))
encoded_phase4b = json.dumps(json.dumps(phase4b, separators=(",", ":")))
print(f'localStorage.setItem("auxsays.localFactualCandidate", {encoded_candidate}); localStorage.setItem("auxsays.localPhase4bState", {encoded_phase4b}); location.reload();')
