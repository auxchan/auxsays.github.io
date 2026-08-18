from __future__ import annotations

import json
from pathlib import Path
import sys


package_root = Path(__file__).resolve().parents[1]
src = package_root / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from systems_monitor_data.pipeline import write_review_candidate  # noqa: E402
from systems_monitor_data.publication import export_public_pdi_candidate  # noqa: E402


internal_path = package_root / "review" / "internal-factual-review-model.json"
public_path = package_root / "review" / "factual-snapshot-candidate.json"
internal = json.loads(internal_path.read_text(encoding="utf-8"))
candidate = export_public_pdi_candidate(internal)
digest = write_review_candidate(public_path, candidate)
print(json.dumps({"candidate": str(public_path), "sha256": digest}, sort_keys=True))
