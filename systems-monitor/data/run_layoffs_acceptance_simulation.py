from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from systems_monitor_data.layoffs_acceptance import (
    load_acceptance_proposal,
    load_vintage_matrix,
    simulate_acceptance,
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simulate proposed Layoffs history acceptance without promoting observations.")
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--proposal", type=Path, default=Path("config/layoffs/history_acceptance_proposal.json"))
    parser.add_argument("--rights", type=Path, default=Path("config/rights/rights.json"))
    parser.add_argument("--vintage-matrix", type=Path, default=Path("config/layoffs/vintage_capability_matrix.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = simulate_acceptance(
        load(args.batch),
        load_acceptance_proposal(args.proposal),
        load(args.rights),
        load_vintage_matrix(args.vintage_matrix),
    )
    if args.output:
        write_atomic(args.output, report)
    else:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
