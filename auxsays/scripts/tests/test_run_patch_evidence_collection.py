#!/usr/bin/env python3
"""Tests for the default-off Windows Learn Q&A activation gate in the shared runner.

Offline / hermetic: the gate is exercised with injected env dicts
(``build_collectors(env=...)``) so ``os.environ`` is never mutated and no collector is
instantiated or run. These prove the runner does NOT register ``microsoft-windows-11``
unless ``AUXSAYS_ENABLE_WINDOWS_LEARN_QNA_WRITEBACK`` is the explicit canonical value
``true``, that the always-on collectors are unaffected by the flag, that only the intended
``WindowsLearnQnaCollector`` class is registered when enabled, and that the Windows dry-run
entry still exposes no ``--write`` flag.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_run_patch_evidence_collection.py
"""
from __future__ import annotations

import contextlib
import io
import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import run_patch_evidence_collection as runner
import patch_collectors.microsoft_windows as win

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []

WIN_ID = "microsoft-windows-11"
FLAG = runner.WINDOWS_LEARN_QNA_ENABLE_ENV
BASE = ("adobe-acrobat-pro", "adobe-acrobat-reader", "adobe-premiere-pro", "blackmagic-davinci", "obs-studio")


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        msg = f"  FAIL  {label}"
        if detail:
            msg += f"\n        {detail}"
        print(msg)
        _ERRORS.append(label)


def registered(env: dict[str, str]) -> bool:
    return WIN_ID in runner.build_collectors(env)


def run() -> int:
    print("=" * 60)
    print("Windows Learn Q&A activation-gate (runner registration) tests")
    print("=" * 60)

    # --- flag name is the exact documented contract -------------------------
    check("activation flag name is AUXSAYS_ENABLE_WINDOWS_LEARN_QNA_WRITEBACK",
          FLAG == "AUXSAYS_ENABLE_WINDOWS_LEARN_QNA_WRITEBACK", FLAG)

    # --- OFF matrix: everything except canonical "true" -> NOT registered ----
    off_values = {
        "absent (empty dict)": {},
        "absent among unrelated keys": {"PATH": "/x", "AUXSAYS_OTHER": "true"},
        "empty string": {FLAG: ""},
        "false": {FLAG: "false"},
        "False": {FLAG: "False"},
        "FALSE": {FLAG: "FALSE"},
        "0": {FLAG: "0"},
        "1": {FLAG: "1"},
        "yes": {FLAG: "yes"},
        "on": {FLAG: "on"},
        "enabled": {FLAG: "enabled"},
        "truthy": {FLAG: "truthy"},
        "true false": {FLAG: "true false"},
        "whitespace only": {FLAG: "   "},
    }
    for label, env in off_values.items():
        check(f"OFF: flag={label!r} -> microsoft-windows-11 NOT registered",
              not registered(env), f"registry={sorted(runner.build_collectors(env))}")

    # --- ON matrix: only the canonical boolean "true" (normalized) ----------
    on_values = {
        "true": {FLAG: "true"},
        "TRUE": {FLAG: "TRUE"},
        "True": {FLAG: "True"},
        "  true  (surrounding whitespace)": {FLAG: "  true  "},
        "true\\n (trailing newline)": {FLAG: "true\n"},
    }
    for label, env in on_values.items():
        check(f"ON: flag={label!r} -> microsoft-windows-11 registered",
              registered(env), f"registry={sorted(runner.build_collectors(env))}")

    # --- when registered, it is exactly the intended collector class --------
    enabled_registry = runner.build_collectors({FLAG: "true"})
    check("registered-by-flag collector class is WindowsLearnQnaCollector",
          enabled_registry.get(WIN_ID) is win.WindowsLearnQnaCollector, str(enabled_registry.get(WIN_ID)))

    # --- the direct gate predicate matches the registry behavior ------------
    check("gate predicate True only for canonical true",
          runner.windows_learn_qna_writeback_enabled({FLAG: "true"}) is True
          and runner.windows_learn_qna_writeback_enabled({FLAG: "TRUE"}) is True
          and runner.windows_learn_qna_writeback_enabled({FLAG: " true "}) is True)
    check("gate predicate False for absent/false/0/empty/1/yes",
          runner.windows_learn_qna_writeback_enabled({}) is False
          and runner.windows_learn_qna_writeback_enabled({FLAG: "false"}) is False
          and runner.windows_learn_qna_writeback_enabled({FLAG: "0"}) is False
          and runner.windows_learn_qna_writeback_enabled({FLAG: ""}) is False
          and runner.windows_learn_qna_writeback_enabled({FLAG: "1"}) is False
          and runner.windows_learn_qna_writeback_enabled({FLAG: "yes"}) is False)

    # --- existing always-on collectors unaffected by the flag ---------------
    for label, env in (("flag off", {}), ("flag on", {FLAG: "true"})):
        reg = runner.build_collectors(env)
        check(f"existing collectors all present regardless of flag ({label})",
              all(pid in reg for pid in BASE), f"registry={sorted(reg)}")
        check(f"existing collector classes unchanged from base ({label})",
              all(reg[pid] is runner.COLLECTORS[pid] for pid in BASE))

    # --- static base + registry sizes ---------------------------------------
    check("static COLLECTORS base never contains Windows", WIN_ID not in runner.COLLECTORS, str(sorted(runner.COLLECTORS)))
    check("default runtime registry == base (3 collectors, no Windows)",
          sorted(runner.build_collectors({})) == sorted(BASE), str(sorted(runner.build_collectors({}))))
    check("enabled runtime registry == base + Windows (4 collectors)",
          sorted(runner.build_collectors({FLAG: "true"})) == sorted((*BASE, WIN_ID)),
          str(sorted(runner.build_collectors({FLAG: "true"}))))

    # --- scheduled-writeback safety: no --product-id run cannot reach Windows -
    # The hourly workflow runs `--write` with NO --product-id, so product_ids defaults to the
    # full registry. With the flag off (the default, and no workflow sets it), that registry
    # is exactly the base -> Windows Learn Q&A can never be a scheduled writeback target.
    default_scheduled_targets = sorted(runner.build_collectors({}))  # what a no-filter run iterates
    check("default scheduled (--write, no --product-id) cannot target Windows Learn Q&A",
          WIN_ID not in default_scheduled_targets, str(default_scheduled_targets))

    # --- Windows dry-run entry still exposes NO --write flag -----------------
    raised = False
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            win._dry_run_main(["--write"])
        except SystemExit as exc:
            raised = exc.code not in (0, None)
    check("Windows dry-run entry exposes NO --write flag (rejects --write)", raised)

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed tests:")
        for error in _ERRORS:
            print(f"  - {error}")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
