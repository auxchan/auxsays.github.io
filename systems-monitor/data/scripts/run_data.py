from __future__ import annotations

import sys
from pathlib import Path


src = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(src))

from systems_monitor_data.cli import main  # noqa: E402

raise SystemExit(main())
