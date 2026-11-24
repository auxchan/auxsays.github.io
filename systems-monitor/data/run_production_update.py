from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from systems_monitor_data.production import update_production  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the cadence-aware Systems Monitor production data loop.")
    parser.add_argument("--runtime-root", type=Path, default=ROOT / "local" / "production-runner")
    parser.add_argument("--output", type=Path, default=ROOT / "production" / "systems-monitor-production.json")
    parser.add_argument("--now", help="ISO-8601 UTC test/recovery clock")
    parser.add_argument("--force", action="store_true", help="Evaluate every governed source regardless of cadence state")
    args = parser.parse_args(argv)
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else None
    result = update_production(package_root=ROOT, runtime_root=args.runtime_root, output_path=args.output, now=now, force=args.force)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
