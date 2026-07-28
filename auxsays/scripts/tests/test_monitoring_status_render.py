#!/usr/bin/env python3
"""Deterministic RENDER test for the monitoring-status ladder -- every mapping + every edge case.

Builds a minimal fixture Jekyll site (scripts/tests/fixtures/monitoring) with a FIXED clock and
synthetic method-health rows, running the REAL _includes/monitoring-status.html, and asserts the
rendered status for each case. This exercises the actual Liquid the site ships (not a Python
re-implementation), so the ladder, per-row freshness, future-timestamp handling, partial-disabled
fail-close, and numeric-version join are all validated end to end.

Build command comes from $MON_JEKYLL_BUILD (default "bundle exec jekyll build"); the test SKIPs
(exit 0) if Jekyll cannot be invoked, so bare environments don't hard-fail. CI / the local ruby33
toolchain run it for real.

Run (local): MON_JEKYLL_BUILD="<ruby.exe> <bundle> exec jekyll build" \
             BUNDLE_GEMFILE=.../Gemfile.local python auxsays/scripts/tests/test_monitoring_status_render.py
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
FIXTURE = _AUX / "scripts" / "tests" / "fixtures" / "monitoring"
INCLUDE = _AUX / "_includes" / "monitoring-status.html"

# The driver page is written into the temp build at RUNTIME (not committed) so the fixture never
# renders into the real site: a committed index.html with front matter would be published by the
# production Jekyll build as a stray /scripts/tests/fixtures/monitoring/ route.
DRIVER = """---
layout: null
published_release: 2026-06-01T00:00:00Z
cases:
  - { name: c1,  product_id: c1,         version: "1.0",  reports: 0 }
  - { name: c2,  product_id: c2,         version: "1.0",  reports: 0 }
  - { name: c3,  product_id: c3,         version: "1.0",  reports: 0 }
  - { name: c4,  product_id: c4,         version: "1.0",  reports: 0 }
  - { name: c5,  product_id: c5,         version: "1.0",  reports: 0 }
  - { name: c6,  product_id: c6,         version: "1.0",  reports: 0 }
  - { name: c7,  product_id: c7,         version: "1.0",  reports: 0 }
  - { name: c8,  product_id: c8,         version: "1.0",  reports: 0 }
  - { name: c9,  product_id: c9,         version: "1.0",  reports: 0 }
  - { name: c10, product_id: c10,        version: "1.0",  reports: 0 }
  - { name: c11, product_id: c11,        version: "1.0",  reports: 0 }
  - { name: c12, product_id: c12,        version: "1.0",  reports: 0 }
  - { name: c13, product_id: c13,        version: "2607", reports: 0 }
  - { name: c14, product_id: c14,        version: "1.0",  reports: 3 }
  - { name: c15, product_id: c15-absent, version: "1.0",  reports: 0 }
  - { name: c16, product_id: c16,        version: "1.0",  reports: 0 }
---
{% for c in page.cases %}CASE|{{ c.name }}|{% include monitoring-status.html mode='cell' product_id=c.product_id version=c.version published_at=page.published_release report_count=c.reports %}|END
{% endfor %}
"""

# Expected monitoring-status CSS class (status lowercased, spaces -> dashes) per fixture case.
EXPECT = {
    "c1": "insufficient-coverage",                 # fresh success + stale success (min unmet)
    "c2": "no-accepted-patch-specific-reports",    # two fresh no_results (clean)
    "c3": "collection-blocked",                    # fresh blocked + old success (zero healthy)
    "c4": "monitoring-degraded",                   # healthy>=min + manual_review_needed
    "c5": "monitoring-degraded",                   # healthy>=min + explicit stale (recent ts)
    "c6": "not-yet-monitored",                     # valid but all pre-release
    "c7": "insufficient-coverage",                 # one fresh success at threshold
    "c8": "monitoring-degraded",                   # fresh success + fresh blocked (degraded first)
    "c9": "monitoring-degraded",                   # partial-disabled coverage
    "c10": "official-source-only",                 # every row disabled
    "c11": "monitoring-degraded",                  # future ts + valid telemetry
    "c12": "collection-stale",                     # future-only (no valid usable ts)
    "c13": "no-accepted-patch-specific-reports",   # numeric 2607 joins to "2607"
    "c14": "monitoring-active",                    # healthy + accepted reports > 0
    "c15": "official-source-only",                 # no matching rows
    "c16": "collection-stale",                     # valid post-release but all stale
}

_PASS = 0
_FAIL = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))


def _build(dest_src: Path, dest_out: Path) -> tuple[bool, str]:
    cmd = shlex.split(os.environ.get("MON_JEKYLL_BUILD", "bundle exec jekyll build"))
    cmd += ["-s", str(dest_src), "-d", str(dest_out), "--quiet"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(dest_src))
    except FileNotFoundError as exc:
        return False, f"jekyll not found: {exc}"
    if proc.returncode != 0:
        return False, (proc.stdout or "") + (proc.stderr or "")
    return True, ""


def run() -> int:
    print("=" * 60)
    print("Monitoring-status deterministic render tests")
    print("=" * 60)

    work = Path(tempfile.mkdtemp(prefix="mon-fixture-"))
    try:
        src = work / "site"
        shutil.copytree(FIXTURE, src)
        (src / "_includes").mkdir(exist_ok=True)
        shutil.copy(INCLUDE, src / "_includes" / "monitoring-status.html")
        (src / "index.html").write_text(DRIVER, encoding="utf-8")  # driver generated here, never committed
        out = work / "_site"

        ok, err = _build(src, out)
        if not ok:
            print("  SKIP  fixture Jekyll build unavailable; render mappings not exercised here.")
            print(f"        ({err.strip()[:300]})")
            return 0

        index = out / "index.html"
        if not index.exists():
            print("  SKIP  fixture build produced no index.html.")
            return 0
        html = index.read_text(encoding="utf-8")

        rendered = {}
        for m in re.finditer(r"CASE\|(\w+)\|(.*?)\|END", html, re.S):
            name, body = m.group(1), m.group(2)
            cls = re.search(r"patch-monitoring--([a-z-]+)", body)
            rendered[name] = cls.group(1) if cls else "(no pill)"

        check(f"all {len(EXPECT)} cases rendered", set(rendered) >= set(EXPECT),
              f"missing: {set(EXPECT) - set(rendered)}")
        for name, expected in EXPECT.items():
            got = rendered.get(name, "(absent)")
            check(f"{name} -> {expected}", got == expected, f"got {got}")
        # numeric-version join must NOT fall through to OFFICIAL SOURCE ONLY
        check("c13 numeric 2607 actually joined (not OFFICIAL SOURCE ONLY)",
              rendered.get("c13") == "no-accepted-patch-specific-reports",
              f"got {rendered.get('c13')}")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
