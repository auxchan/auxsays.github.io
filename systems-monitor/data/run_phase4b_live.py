"""Repository-local launcher for the bounded Phase-4B live BEA runner."""

from pathlib import Path
import sys


PACKAGE_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE_ROOT / "src"))

from systems_monitor_data.phase4b_live import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
