from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .pipeline import FirstSlicePipeline, candidate_from_observations, write_review_candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AUXSAYS Systems Monitor local Phase-3 collector")
    parser.add_argument("command", choices=("collect",))
    parser.add_argument("--local-root", type=Path, default=Path("local"))
    parser.add_argument("--review-output", type=Path, default=Path("review/factual-snapshot-candidate.local.json"))
    parser.add_argument("--year", type=int, default=datetime.now(timezone.utc).year)
    args = parser.parse_args(argv)
    package_root = Path(__file__).resolve().parents[2]
    pipeline = FirstSlicePipeline(package_root, args.local_root)
    observations = pipeline.collect_bls(args.year)
    observations.append(pipeline.collect_dol(args.year))
    candidate = candidate_from_observations(observations, generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    digest = write_review_candidate(args.review_output, candidate)
    print(json.dumps({"status": "LOCAL_REVIEW_ONLY_NOT_PUBLICLY_ACTIVATED", "candidate": str(args.review_output), "sha256": digest, "observations": len(observations)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
