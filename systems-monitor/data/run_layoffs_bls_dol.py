from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from systems_monitor_data.layoffs_bls_dol import collect_layoffs_bls_dol_candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect BLS/DOL Layoffs branch candidates without accepting or publishing them.")
    parser.add_argument("--runtime-root", type=Path, required=True, help="Non-repository runtime root for raw evidence and candidate output.")
    parser.add_argument("--start-year", type=int)
    parser.add_argument("--end-year", type=int)
    args = parser.parse_args()
    result = collect_layoffs_bls_dol_candidates(
        registry_path=ROOT / "config" / "layoffs" / "sources_bls_dol.json",
        raw_root=args.runtime_root / "raw",
        candidate_path=args.runtime_root / "layoffs-batch-candidate.json",
        start_year=args.start_year,
        end_year=args.end_year,
    )
    summary = {
        "activationStatus": result["activationStatus"],
        "candidateCount": len(result["candidates"]),
        "candidatePath": str(args.runtime_root / "layoffs-batch-candidate.json"),
        "rawArtifactCount": len(result["rawArtifacts"]),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
