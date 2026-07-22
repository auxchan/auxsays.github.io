#!/usr/bin/env python3
"""Tests for the default-off activation gates in the shared runner.

Offline / hermetic: the gates are exercised with injected env dicts
(``build_collectors(env=...)``) so ``os.environ`` is never mutated and no collector is
instantiated or run. These prove the runner does NOT register ``microsoft-windows-11``
unless ``AUXSAYS_ENABLE_WINDOWS_LEARN_QNA_WRITEBACK`` is the explicit canonical value
``true``, that it likewise does NOT register the Acrobat consensus collectors
(``adobe-acrobat-reader`` / ``adobe-acrobat-pro``) unless ``AUXSAYS_ENABLE_ACROBAT_CONSENSUS``
is the explicit canonical ``true`` (held off because both discovery methods are blocked from
CI -- see PR #23), that the always-on collectors are unaffected by either flag, that only the
intended collector classes are registered when enabled, and that the Windows dry-run entry
still exposes no ``--write`` flag.

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
ACR_FLAG = runner.ACROBAT_CONSENSUS_ENABLE_ENV
ACR_IDS = runner.ACROBAT_CONSENSUS_PRODUCT_IDS  # ("adobe-acrobat-reader", "adobe-acrobat-pro")
BASE = ("adobe-premiere-pro", "blackmagic-davinci", "obs-studio")


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

    # === Adobe Acrobat consensus: default-off activation gate ================
    # PR #23 proved both discovery methods (Adobe Community + Reddit) are blocked from CI, so
    # the Acrobat consensus collectors are held out of the always-on base and registered ONLY
    # when AUXSAYS_ENABLE_ACROBAT_CONSENSUS is the canonical "true". This mirrors the Windows
    # gate: a scheduled --write run must never treat Acrobat consensus as active while blocked.
    print("-" * 60)
    print("Adobe Acrobat consensus activation-gate tests")
    print("-" * 60)

    check("Acrobat flag name is AUXSAYS_ENABLE_ACROBAT_CONSENSUS",
          ACR_FLAG == "AUXSAYS_ENABLE_ACROBAT_CONSENSUS", ACR_FLAG)
    check("Acrobat product ids are Reader + Pro",
          tuple(ACR_IDS) == ("adobe-acrobat-reader", "adobe-acrobat-pro"), str(ACR_IDS))

    # static base never carries Acrobat consensus
    check("static COLLECTORS base contains NEITHER Acrobat edition",
          all(pid not in runner.COLLECTORS for pid in ACR_IDS), str(sorted(runner.COLLECTORS)))

    # OFF matrix -> neither edition registered
    acr_off = {
        "absent": {},
        "empty string": {ACR_FLAG: ""},
        "false": {ACR_FLAG: "false"},
        "False": {ACR_FLAG: "False"},
        "0": {ACR_FLAG: "0"},
        "1": {ACR_FLAG: "1"},
        "yes": {ACR_FLAG: "yes"},
        "on": {ACR_FLAG: "on"},
        "whitespace only": {ACR_FLAG: "   "},
        "the Windows flag (wrong flag)": {FLAG: "true"},
    }
    for label, env in acr_off.items():
        reg = runner.build_collectors(env)
        check(f"OFF: acrobat flag={label!r} -> NEITHER Acrobat edition registered",
              all(pid not in reg for pid in ACR_IDS), f"registry={sorted(reg)}")

    # ON matrix -> BOTH editions registered (canonical true only)
    acr_on = {
        "true": {ACR_FLAG: "true"},
        "TRUE": {ACR_FLAG: "TRUE"},
        "True": {ACR_FLAG: "True"},
        "  true  (surrounding whitespace)": {ACR_FLAG: "  true  "},
        "true\\n (trailing newline)": {ACR_FLAG: "true\n"},
    }
    for label, env in acr_on.items():
        reg = runner.build_collectors(env)
        check(f"ON: acrobat flag={label!r} -> BOTH Acrobat editions registered",
              all(pid in reg for pid in ACR_IDS), f"registry={sorted(reg)}")

    # gate predicate matches registry behavior
    check("acrobat gate predicate True only for canonical true",
          runner.acrobat_consensus_enabled({ACR_FLAG: "true"}) is True
          and runner.acrobat_consensus_enabled({ACR_FLAG: " TRUE "}) is True
          and runner.acrobat_consensus_enabled({}) is False
          and runner.acrobat_consensus_enabled({ACR_FLAG: "false"}) is False
          and runner.acrobat_consensus_enabled({ACR_FLAG: "1"}) is False)

    # when enabled, each edition binds to a distinct AdobeAcrobatCollector with the right id
    import patch_collectors.adobe_acrobat_community as acmod
    acr_reg = runner.build_collectors({ACR_FLAG: "true"})
    reader_coll = acr_reg["adobe-acrobat-reader"]()
    pro_coll = acr_reg["adobe-acrobat-pro"]()
    check("enabled Reader factory yields AdobeAcrobatCollector(product_id=adobe-acrobat-reader)",
          isinstance(reader_coll, acmod.AdobeAcrobatCollector) and reader_coll.product_id == "adobe-acrobat-reader",
          str(getattr(reader_coll, "product_id", None)))
    check("enabled Pro factory yields AdobeAcrobatCollector(product_id=adobe-acrobat-pro)",
          isinstance(pro_coll, acmod.AdobeAcrobatCollector) and pro_coll.product_id == "adobe-acrobat-pro",
          str(getattr(pro_coll, "product_id", None)))
    check("the two enabled factories bind DISTINCT product ids (no closure-capture bug)",
          reader_coll.product_id != pro_coll.product_id)

    # scheduled-writeback safety: default (--write, no --product-id) cannot target Acrobat
    default_targets = sorted(runner.build_collectors({}))
    check("default scheduled run cannot target either Acrobat edition",
          all(pid not in default_targets for pid in ACR_IDS), str(default_targets))

    # both gates independent + composable
    both_on = sorted(runner.build_collectors({FLAG: "true", ACR_FLAG: "true"}))
    check("both flags on -> base + Windows + both Acrobat editions (6 collectors)",
          both_on == sorted((*BASE, WIN_ID, *ACR_IDS)), str(both_on))

    # === Microsoft PowerPoint consensus: default-off activation gate ==========
    # A default-off community-evidence PILOT. It must never be a scheduled writeback target;
    # registration requires the canonical "true", exactly like the Windows/Acrobat gates.
    print("-" * 60)
    print("Microsoft PowerPoint consensus activation-gate tests")
    print("-" * 60)
    PP_ID = runner.POWERPOINT_CONSENSUS_PRODUCT_ID
    PP_FLAG = runner.POWERPOINT_CONSENSUS_ENABLE_ENV
    import patch_collectors.microsoft_powerpoint as ppmod

    check("PowerPoint flag name is AUXSAYS_ENABLE_POWERPOINT_CONSENSUS", PP_FLAG == "AUXSAYS_ENABLE_POWERPOINT_CONSENSUS", PP_FLAG)
    check("static COLLECTORS base never contains PowerPoint", PP_ID not in runner.COLLECTORS, str(sorted(runner.COLLECTORS)))

    pp_off = {"absent": {}, "empty": {PP_FLAG: ""}, "false": {PP_FLAG: "false"}, "False": {PP_FLAG: "False"},
              "0": {PP_FLAG: "0"}, "1": {PP_FLAG: "1"}, "yes": {PP_FLAG: "yes"}, "on": {PP_FLAG: "on"},
              "whitespace": {PP_FLAG: "  "}, "the Windows flag (wrong flag)": {FLAG: "true"}}
    for label, env in pp_off.items():
        check(f"OFF: powerpoint flag={label!r} -> microsoft-powerpoint NOT registered",
              PP_ID not in runner.build_collectors(env), f"registry={sorted(runner.build_collectors(env))}")

    pp_on = {"true": {PP_FLAG: "true"}, "TRUE": {PP_FLAG: "TRUE"}, "  true  ": {PP_FLAG: "  true  "}, "true\\n": {PP_FLAG: "true\n"}}
    for label, env in pp_on.items():
        reg = runner.build_collectors(env)
        check(f"ON: powerpoint flag={label!r} -> registered as PowerPointLearnQnaCollector",
              reg.get(PP_ID) is ppmod.PowerPointLearnQnaCollector, f"registry={sorted(reg)}")

    check("powerpoint gate predicate True only for canonical true",
          runner.powerpoint_consensus_enabled({PP_FLAG: "true"}) is True
          and runner.powerpoint_consensus_enabled({PP_FLAG: " TRUE "}) is True
          and runner.powerpoint_consensus_enabled({}) is False
          and runner.powerpoint_consensus_enabled({PP_FLAG: "false"}) is False
          and runner.powerpoint_consensus_enabled({PP_FLAG: "1"}) is False)

    # scheduled-writeback safety + no unrelated behavior change
    check("default scheduled run (--write, no --product-id) cannot target PowerPoint",
          PP_ID not in sorted(runner.build_collectors({})), str(sorted(runner.build_collectors({}))))
    reg_pp = runner.build_collectors({PP_FLAG: "true"})
    check("enabling PowerPoint leaves all base collectors unchanged (Windows rules untouched)",
          all(reg_pp.get(pid) is runner.COLLECTORS[pid] for pid in runner.COLLECTORS) and WIN_ID not in reg_pp)

    # all three gates independent + composable
    all_on = sorted(runner.build_collectors({FLAG: "true", ACR_FLAG: "true", PP_FLAG: "true"}))
    check("all three flags on -> base + Windows + both Acrobat + PowerPoint (7 collectors)",
          all_on == sorted((*BASE, WIN_ID, *ACR_IDS, PP_ID)), str(all_on))

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
