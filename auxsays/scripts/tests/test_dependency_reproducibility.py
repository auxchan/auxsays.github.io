#!/usr/bin/env python3
"""The deployed dependency set must come from a tracked lock, not from a deploy-time resolve.

WHAT WAS WRONG. `auxsays/Gemfile` declared seven gems and constrained two. Five were
unconstrained, INCLUDING `jekyll-theme-chirpy` -- the theme every layout inherits from. No
`Gemfile.lock` was tracked, and `pages.yml` ran `gem install bundler; bundle install` with no
lock and no cache, so CI RE-RESOLVED every gem on every deploy.

That was not theoretical. Measured on 2026-10-21: the live page emitted `jekyll-seo-tag 2.9.1`
while a local build of the same commit emitted `2.9.0`. An upstream release could change the
published markup of every page with no commit touching the repository.

THE TRAP THIS SUITE ALSO GUARDS. The obvious repair -- generate a lock and commit it -- is
dangerous if the lock is resolved from a developer machine. Resolving locally would have pinned
`chirpy 7.0.1`, `seo-tag 2.9.0` and `include-cache 0.2.2`, silently DOWNGRADING the live theme by
six minor versions. The lock was therefore frozen to the set a known-good Linux CI build actually
installed, verified gem by gem against that build's own install log: 40 production gems, zero
version mismatches.

WHY THE SHELL GUARD IS EXECUTED HERE RATHER THAN GREPPED. A suite that greps a workflow for a
guard passes after the guard is deleted -- a recorded failure in this repository. So the
lock-integrity step's `run:` scalar is extracted from the workflow and EXECUTED against a
temporary checkout with no lock, and it must exit non-zero. If someone replaces that step with a
no-op, this fails.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_dependency_reproducibility.py
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
GEMFILE = _AUX / "Gemfile"
LOCKFILE = _AUX / "Gemfile.lock"
WORKFLOW = _REPO / ".github" / "workflows" / "pages.yml"

# The platform CI actually runs on, and the one local development uses.
PRODUCTION_PLATFORM = "x86_64-linux"
DEV_PLATFORM = "x64-mingw-ucrt"

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print("  PASS  " + label)
    else:
        _FAIL += 1
        print("  FAIL  " + label)
        if detail:
            print("        " + detail)
        _ERRORS.append(label)


def tracked(rel: str) -> bool:
    out = subprocess.run(["git", "ls-files", "--error-unmatch", rel],
                         cwd=_REPO, capture_output=True, text=True)
    return out.returncode == 0


def lock_platforms() -> list[str]:
    body = LOCKFILE.read_text(encoding="utf-8")
    block = body.split("PLATFORMS", 1)[1].split("\n\n", 1)[0]
    return [ln.strip() for ln in block.splitlines() if ln.strip()]


def locked_versions() -> dict:
    body = LOCKFILE.read_text(encoding="utf-8")
    spec = body.split("specs:", 1)[1].split("PLATFORMS", 1)[0]
    return {m.group(1): m.group(2).split("-")[0]
            for m in re.finditer(r"^    ([A-Za-z0-9_.-]+) \(([^)]+)\)$", spec, re.M)}


def section_a_lock_is_tracked_and_covers_production() -> None:
    print("\n[A] the lock is tracked and covers the platform CI deploys from")
    check("A1 Gemfile.lock exists", LOCKFILE.is_file())
    check("A2 Gemfile.lock is TRACKED, not merely present on disk",
          tracked("auxsays/Gemfile.lock"),
          "an untracked lock is invisible to CI and was how this defect hid")
    plats = lock_platforms() if LOCKFILE.is_file() else []
    check("A3 the lock declares the production Linux platform",
          PRODUCTION_PLATFORM in plats,
          f"PLATFORMS={plats}; without it CI cannot install from the lock and re-resolves")
    check("A4 the lock also declares the development platform",
          DEV_PLATFORM in plats,
          f"PLATFORMS={plats}; a lock that only covers Linux breaks local builds")


def section_b_theme_is_bounded() -> None:
    print("\n[B] the theme is bounded, and the lock agrees with the bound")
    gem = GEMFILE.read_text(encoding="utf-8")
    stripped = "\n".join(ln for ln in gem.splitlines() if not ln.strip().startswith("#"))
    m = re.search(r'gem\s+"jekyll-theme-chirpy"\s*,\s*"([^"]+)"', stripped)
    check("B1 the theme carries an explicit version bound", m is not None,
          "the theme was unconstrained; a major release restructures every page's markup")
    locked = locked_versions()
    chirpy = locked.get("jekyll-theme-chirpy")
    check("B2 the lock pins a theme version", bool(chirpy), f"locked={locked.get('jekyll-theme-chirpy')}")
    if m and chirpy:
        # The bound must actually admit the pinned version, or a future `bundle install`
        # cannot satisfy both and the build breaks in a way nobody sees until deploy.
        want = m.group(1).replace("~>", "").strip()
        family = ".".join(want.split(".")[:2])
        check("B3 the pinned version is inside the declared bound",
              chirpy.startswith(family),
              f"bound {m.group(1)!r} vs pinned {chirpy!r}")
    else:
        check("B3 SKIPPED - no bound or no pin to compare", True)

    # Windows-only gems must NOT become unconditional dependencies: the Linux runner does not
    # need them, and an unguarded tzinfo would enter the production resolution.
    check("B4 the Windows timezone gems are platform-gated",
          bool(re.search(r'gem\s+"tzinfo"\s*,\s*platforms:', stripped))
          and bool(re.search(r'gem\s+"tzinfo-data"\s*,\s*platforms:', stripped)),
          "ungated, these would join the Linux dependency set")


def section_c_workflow_installs_from_the_lock() -> None:
    print("\n[C] the deploy installs FROM the lock, and says which Gemfile")
    wf = WORKFLOW.read_text(encoding="utf-8")
    check("C1 setup-ruby installs and caches from the lock",
          "bundler-cache: true" in wf,
          "without it the job resolves dependencies at deploy time")
    check("C2 BUNDLE_GEMFILE names the project explicitly",
          "BUNDLE_GEMFILE: auxsays/Gemfile" in wf,
          "the Gemfile is not at the repository root, so the action would resolve the wrong one")
    check("C3 the old unpinned install is gone",
          "gem install bundler" not in wf,
          "a manual `bundle install` alongside the cached one can re-resolve")


def lock_guard_script() -> str | None:
    """The lock-integrity step's shell, extracted from the workflow.

    Extracted rather than restated so this cannot drift from what CI runs.
    """
    wf = WORKFLOW.read_text(encoding="utf-8")
    marker = "name: Verify the dependency lock was used, not rewritten"
    if marker not in wf:
        return None
    after = wf.split(marker, 1)[1]
    m = re.search(r"run: \|\n(.*?)(?=\n      - name:|\n  [a-z_]+:\n|\Z)", after, re.S)
    if not m:
        return None
    body = m.group(1)
    # strip the YAML block indentation
    lines = [ln[10:] if ln.startswith(" " * 10) else ln.lstrip() for ln in body.splitlines()]
    return "\n".join(lines)


def section_d_guard_actually_refuses() -> None:
    print("\n[D] the lock guard EXECUTES and refuses a missing or rewritten lock")
    script = lock_guard_script()
    check("D1 the lock-integrity step exists and its shell is extractable", script is not None,
          "a deleted step must fail here, not pass silently")
    if script is None:
        for n in ("D2", "D3"):
            check(f"{n} SKIPPED - no step to execute", True)
        return

    bash = shutil.which("bash")
    if not bash:
        check("D2 SKIPPED - no bash available", True)
        check("D3 SKIPPED - no bash available", True)
        return

    # D2: no lock at all -> must exit non-zero. This is the fallback the whole repair removes.
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "Gemfile").write_text('source "https://rubygems.org"\n', encoding="utf-8")
        proc = subprocess.run([bash, "-c", script], cwd=d, capture_output=True, text=True,
                              timeout=180)
        check("D2 a MISSING lock makes the step fail", proc.returncode != 0,
              f"exit {proc.returncode}; a missing lock must never fall back to resolving")
        check("D3 and it says why, so the failure is diagnosable",
              "Gemfile.lock" in (proc.stdout + proc.stderr),
              f"stdout/stderr carried no mention of the lock: {(proc.stdout + proc.stderr)[:160]!r}")


def section_e_parity_is_recorded() -> None:
    print("\n[E] the lock records the production set, not a developer machine's")
    locked = locked_versions()
    check("E1 the lock resolved a full dependency graph", len(locked) >= 30,
          f"{len(locked)} gems; a truncated lock would silently narrow the install")
    # These three are where a locally-resolved lock would have differed from production, and
    # each is pinned to the version the known-good Linux CI build installed.
    expected = {"jekyll": "4.4.1", "jekyll-theme-chirpy": "7.6.0",
                "jekyll-seo-tag": "2.9.1", "jekyll-include-cache": "0.3.1",
                "liquid": "4.0.4"}
    for name, want in expected.items():
        got = locked.get(name)
        check(f"E2 {name} is pinned to the production version",
              got == want,
              f"locked {got!r}, production installed {want!r}")
    # liquid is called out because every rendered-Liquid assertion in the other suites is only
    # faithful to production while this matches.
    check("E3 the lock is tracked alongside the Gemfile that produced it",
          tracked("auxsays/Gemfile") and tracked("auxsays/Gemfile.lock"))


def run() -> int:
    section_a_lock_is_tracked_and_covers_production()
    section_b_theme_is_bounded()
    section_c_workflow_installs_from_the_lock()
    section_d_guard_actually_refuses()
    section_e_parity_is_recorded()
    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2) from None
