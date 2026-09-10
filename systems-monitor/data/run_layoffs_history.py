from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from systems_monitor_data.layoffs_history import (  # noqa: E402
    append_history,
    history_artifact,
    load_acceptance_ledger,
    promote_candidate_batch,
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote explicitly authorized Layoffs candidates into revision-safe accepted history.")
    parser.add_argument("--candidate", type=Path, default=ROOT / "evidence" / "layoffs-runtime" / "layoffs-batch-candidate.json")
    parser.add_argument("--acceptance", type=Path, default=ROOT / "config" / "layoffs" / "history_acceptance.json")
    parser.add_argument("--history", type=Path, default=ROOT / "review" / "layoffs-accepted-history.json")
    parser.add_argument("--report", type=Path, default=ROOT / "review" / "layoffs-history-activation-report.json")
    parser.add_argument("--accepted-at", default=None)
    args = parser.parse_args(argv)

    accepted_at = args.accepted_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    ledger = load_acceptance_ledger(args.acceptance)
    existing = _load(args.history).get("observations", []) if args.history.exists() else []
    if not args.candidate.exists():
        report = {
            "schemaVersion": "layoffs-history-activation-report-1.0.0",
            "status": "BLOCKED_CANDIDATE_BATCH_MISSING",
            "acceptedAt": accepted_at,
            "acceptanceAuthority": ledger["authority"],
            "candidatePath": str(args.candidate),
            "acceptedObservationCount": len(existing),
            "newlyAcceptedObservationCount": 0,
            "acceptedComparableFactorCount": 0,
        }
        _write_atomic(args.report, report)
        print(json.dumps(report, sort_keys=True))
        return 2

    candidate = _load(args.candidate)
    promoted = promote_candidate_batch(candidate, ledger, accepted_at=accepted_at, existing_history=existing)
    combined = append_history(existing, promoted)
    if promoted:
        _write_atomic(args.history, history_artifact(combined, generated_at=accepted_at))
    comparable_keys = {
        (row["canonicalFactorId"], row["sourceSeriesId"])
        for row in combined
        if len({
            candidate_row["validTime"]
            for candidate_row in combined
            if candidate_row["canonicalFactorId"] == row["canonicalFactorId"]
            and candidate_row["sourceSeriesId"] == row["sourceSeriesId"]
        }) >= 2
    }
    status = (
        "ACTIVATED" if promoted
        else "BLOCKED_ACCEPTANCE_AUTHORITY_NONE" if ledger["authority"] == "NONE"
        else "BLOCKED_AUTOMATIC_ROUTINE_PROMOTION_DISABLED" if not ledger["automaticRoutinePromotionEnabled"]
        else "NO_MATCHING_ACCEPTANCE_RULE"
    )
    report = {
        "schemaVersion": "layoffs-history-activation-report-1.0.0",
        "status": status,
        "acceptedAt": accepted_at,
        "acceptanceAuthority": ledger["authority"],
        "candidateCount": len(candidate.get("candidates", [])),
        "acceptedObservationCount": len(combined),
        "newlyAcceptedObservationCount": len(promoted),
        "acceptedComparableFactorCount": len({key[0] for key in comparable_keys}),
        "acceptedComparableSeriesCount": len(comparable_keys),
        "historyWritten": bool(promoted),
    }
    _write_atomic(args.report, report)
    print(json.dumps(report, sort_keys=True))
    return 0 if promoted else 2


if __name__ == "__main__":
    raise SystemExit(main())
