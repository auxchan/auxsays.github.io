#!/usr/bin/env python3
"""G94 (AUX-131): every official withdrawal is kept; a later one never drops or replaces an earlier one.

THE DEFECT. `_data/patch_lifecycle.yml` is the only record of an official withdrawal (decide's R1,
AVOID). `lib/verdict_reasons.lifecycle_errors` refused any SECOND entry (`MAX_LIFECYCLE_ENTRIES = 1`),
valid or not, on another release or on the same one, and every consumer -- the deploy's projection, both
record writers and QA -- treats a refused file as empty. So recording a second withdrawal took the first
one's AVOID off both KB5079391 pages (AVOID -> INSUFFICIENT DATA, measured on the real corpus), and QA's
patch_lifecycle_invalid blocked every deploy and writeback lane until the entry was removed: a later
withdrawal could never be recorded. And `lib/patch_decision.lifecycle_for` returned the FIRST matching
entry in file order, so with two entries for one release the page's replacement KB and source depended
on the order of the file.

THE FIX. The count check is gone (each entry still passes every per-entry check, and a malformed entry
still refuses the whole file, a QA error), and `lifecycle_for` rests a page on the EARLIEST verified
matching entry. decide's precedence is unchanged: a withdrawal is AVOID before anything else.

  W1  two withdrawals on different releases are both kept, through the deploy's own loader
  W2  a second entry for the SAME release: still AVOID, the earlier entry's details, in either order
  W3  reordering the file changes nothing in the projection (every permutation)
  W4  re-ingesting the same fact (an exact duplicate, or the same file twice) changes nothing
  W5  a malformed entry fails closed: it is named, the file supports nothing, and QA errors (never silent)
  W6  decide's precedence with several entries: AVOID before SECURITY UPDATE and before a WAIT reason
  C1  the shipped corpus: exactly the two KB5079391 pages are AVOID
  C2  the shipped corpus with a further valid withdrawal appended: no verdict anywhere changes
  X1/X2  one mutant per fix, each caught by a named check above

Offline; reads the shipped tree, writes only in a temp dir.
Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_official_withdrawal_completeness.py
"""
from __future__ import annotations

import contextlib
import io
import itertools
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
sys.path.insert(0, str(_AUX / "scripts"))

import yaml  # noqa: E402

from lib import patch_decision as pd  # noqa: E402
from lib import verdict_projection as vp  # noqa: E402
from lib import verdict_reasons as vr  # noqa: E402

WIN = "microsoft-windows-11"
SHIPPED = vr.load_lifecycle(_AUX / "_data" / "patch_lifecycle.yml")
KB5079391_PAGES = {"microsoft-windows-11|24H2|26100.8116", "microsoft-windows-11|25H2|26200.8116"}

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}" + (f"  --  {detail}" if detail else ""))
        _ERRORS.append(label)


@contextlib.contextmanager
def captured():
    """Run checks silently and collect the labels that failed, leaving the real tally untouched."""
    global _PASS, _FAIL, _ERRORS
    saved = (_PASS, _FAIL, _ERRORS)
    _PASS, _FAIL, _ERRORS = 0, 0, []
    failures: list[str] = []
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            yield failures
    finally:
        failures.extend(_ERRORS)
        _PASS, _FAIL, _ERRORS = saved


# ------------------------------------------------------------------------ synthetic facts

def entry(kb: str, builds: list[str], replacement: str, verified: str, **over) -> dict:
    e = {"id": f"{WIN}:{kb}:withdrawn-for-new-installs", "product_id": WIN, "kb": kb, "builds": list(builds),
         "relationship": "withdrawn_for_new_installs", "replacement_kb": replacement,
         "released": "2026-03-26", "replacement_released": "2026-03-31",
         "official_url": f"https://support.microsoft.com/en-us/test/{kb.lower()}", "verified_at": verified}
    e.update(over)
    return e


def win(version: str, kb: str, build: str, update_type: str = "2026-03 D", **over) -> dict:
    r = {"product_id": WIN, "update_version": version, "target_kb": kb, "target_build": build,
         "update_type": update_type, "update_report_count": 0, "update_entry": True,
         "permalink": f"/updates/microsoft/{WIN}/{version.lower()}/{build}/"}
    r.update(over)
    return r


# E1 withdraws one update on two OS builds; E2 another update; E1B is a LATER statement about the same
# release as E1 (one of its builds), naming a different replacement and article.
E1 = entry("KB5000002", ["26200.2000", "26100.2000"], "KB5000003", "2026-11-06")
E2 = entry("KB5000012", ["26200.3000"], "KB5000013", "2026-12-06")
E1B = entry("KB5000002", ["26200.2000"], "KB5000099", "2026-12-10",
            id=f"{WIN}:KB5000002:withdrawn-for-new-installs:restated",
            official_url="https://support.microsoft.com/en-us/test/kb5000002-restated")
P25 = win("25H2", "KB5000002", "26200.2000")
P24 = win("24H2", "KB5000002", "26100.2000")
P2 = win("25H2", "KB5000012", "26200.3000")
NEIGHBOUR = win("25H2", "KB5000002", "26200.2001")
RECORDS = [P25, P24, P2, NEIGHBOUR]


def loaded(entries: list[dict]) -> tuple[list, list]:
    """lib/verdict_projection.load_fact_files over a temp tree holding this lifecycle file: exactly what a
    deploy hands decide."""
    with tempfile.TemporaryDirectory() as td:
        data = Path(td) / "_data"
        data.mkdir()
        (data / "patch_lifecycle.yml").write_text(
            yaml.safe_dump({"schema_version": 1, "entries": entries}, sort_keys=False), encoding="utf-8")
        (data / "verdict_reasons.yml").write_text(yaml.safe_dump({"schema_version": 1, "entries": []}),
                                                  encoding="utf-8")
        _reasons, life, problems = vp.load_fact_files(Path(td))
    return life, problems


def projection(life: list[dict], records: list[dict] = RECORDS) -> dict:
    return vp.project(records, {}, [], life)[0]


def shown(rec: dict, life: list[dict]) -> tuple[str, str, str]:
    d = pd.decide(rec, lifecycle=life)
    return d.verdict, str((d.lifecycle or {}).get("replacement_kb") or ""), pd.official_source(d)["url"]


# ------------------------------------------------------------------------ checks

def check_completeness() -> None:
    errs = vr.lifecycle_errors([E1, E2])
    life, problems = loaded([E1, E2])
    seen = {k: shown(r, life) for k, r in (("25", P25), ("24", P24), ("2", P2), ("n", NEIGHBOUR))}
    check("G94-W1 two withdrawals on different releases are both kept through the deploy's loader: no error, "
          "both entries loaded, all three withdrawn pages AVOID with their own replacement, a neighbour build not",
          not errs and not problems and len(life) == 2
          and seen["25"][:2] == ("AVOID", "KB5000003") and seen["24"][:2] == ("AVOID", "KB5000003")
          and seen["2"][:2] == ("AVOID", "KB5000013") and seen["n"][0] != "AVOID",
          f"errors={errs} problems={problems} loaded={len(life)} seen={seen}")


def check_same_release() -> None:
    errs = vr.lifecycle_errors([E1, E1B])
    forward, backward = loaded([E1, E1B])[0], loaded([E1B, E1])[0]
    first = (shown(P25, forward), shown(P25, backward), shown(P24, forward), shown(P24, backward))
    alone_late, alone_early = shown(P25, [E1B]), shown(P25, [E1])
    e1_url = E1["official_url"]
    check("G94-W2 a second entry for the SAME release is kept: the page stays AVOID and rests on the earlier "
          "verified entry (its replacement and article) in either file order; either entry alone still withdraws it",
          not errs and len(forward) == len(backward) == 2
          and first[0] == first[1] == ("AVOID", "KB5000003", e1_url)
          and first[2] == first[3] == ("AVOID", "KB5000003", e1_url)
          and alone_late[0] == alone_early[0] == "AVOID" and alone_late[1] == "KB5000099",
          f"errors={errs} first={first} alone={alone_late, alone_early}")


def check_reordering() -> None:
    entries = [E1, E2, E1B]
    projections = [projection(loaded(list(order))[0]) for order in itertools.permutations(entries)]
    avoid = sorted(k for k, row in projections[0]["pages"].items() if row["verdict"] == "AVOID")
    check("G94-W3 reordering the lifecycle file changes nothing: all 6 orders of three entries give the same "
          "projection, row for row (verdict, line, source)",
          len(projections) == 6 and all(p == projections[0] for p in projections) and len(avoid) == 3,
          f"distinct={len({repr(p) for p in projections})} avoid={avoid}")


def check_idempotent() -> None:
    once = projection(loaded([E1, E2])[0])
    duplicated = projection(loaded([E1, E2, dict(E1)])[0])
    again = projection(loaded([E1, E2])[0])
    check("G94-W4 re-ingesting the same fact changes nothing: an exact duplicate entry is valid and gives the "
          "same projection as one copy, and the same file read twice renders byte-identical projections",
          not vr.lifecycle_errors([E1, E2, dict(E1)]) and duplicated == once
          and vp.render(again) == vp.render(once),
          f"dup_equal={duplicated == once}")


def _qa_errors(entries: list[dict], tmp: Path) -> set[str]:
    """QA's scan_verdict_policy over a one-page fixture with this lifecycle file: the error codes."""
    import qa_patch_records as qa  # noqa: PLC0415
    tmp.mkdir(parents=True, exist_ok=True)
    rec = tmp / "r0.md"
    rec.write_text("---\n" + yaml.safe_dump(P25) + "---\nbody\n", encoding="utf-8")
    ev, rs, life = tmp / "ev.yml", tmp / "reasons.yml", tmp / "life.yml"
    ev.write_text(yaml.safe_dump({"schema_version": 1, "evidence": []}), encoding="utf-8")
    rs.write_text(yaml.safe_dump({"schema_version": 1, "entries": []}), encoding="utf-8")
    life.write_text(yaml.safe_dump({"schema_version": 1, "entries": entries}), encoding="utf-8")
    saved = (qa.REASONS_PATH, qa.LIFECYCLE_PATH, qa.EVIDENCE_PATH, qa.PROJECTION_PATH)
    try:
        qa.REASONS_PATH, qa.LIFECYCLE_PATH, qa.EVIDENCE_PATH, qa.PROJECTION_PATH = rs, life, ev, tmp / "none.yml"
        errors, _warnings = qa.scan_verdict_policy([rec])
    finally:
        qa.REASONS_PATH, qa.LIFECYCLE_PATH, qa.EVIDENCE_PATH, qa.PROJECTION_PATH = saved
    return {e["code"] for e in errors}


def check_malformed(tmp: Path) -> None:
    bad = dict(E2)
    bad.pop("verified_at")
    errs = vr.lifecycle_errors([E1, bad])
    life, problems = loaded([E1, bad])
    qa_bad, qa_good = _qa_errors([E1, bad], tmp / "bad"), _qa_errors([E1, E2], tmp / "good")
    check("G94-W5 a malformed entry fails closed: it alone is named (no entry-count refusal), the file then "
          "supports nothing, and QA reports patch_lifecycle_invalid as an ERROR -- the AVOID never disappears "
          "silently; the same file with the entry well formed is clean",
          len(errs) == 1 and bad["id"] in errs[0] and "verified_at" in errs[0]
          and life == [] and any("patch_lifecycle" in p for p in problems)
          and shown(P25, life)[0] != "AVOID"
          and "patch_lifecycle_invalid" in qa_bad and "patch_lifecycle_invalid" not in qa_good,
          f"errors={errs} problems={problems} qa_bad={qa_bad} qa_good={qa_good}")


def check_precedence() -> None:
    life = loaded([E2, E1, E1B])[0]
    wait = {"id": "w", "product_id": WIN, "update_version": "25H2", "target_build": "26200.2000",
            "verdict": "WAIT", "scope": "if you use the test setup", "reason_class": "regression",
            "reason": "A test regression."}
    sec_withdrawn = win("25H2", "KB5000002", "26200.2000", update_type="2026-03 B")
    sec_other = win("25H2", "KB5000021", "26200.4000", update_type="2026-03 B")
    a = pd.decide(sec_withdrawn, valid_reasons=[wait], lifecycle=life)
    b = pd.decide(sec_other, valid_reasons=[], lifecycle=life)
    c = pd.decide(dict(P25, update_type="2026-03 D"), valid_reasons=[wait], lifecycle=life)
    check("G94-W6 decide's precedence is unchanged with several entries: a withdrawn monthly security update "
          "with a supported WAIT is AVOID (R1), a security update no entry names is SECURITY UPDATE (R2), a "
          "withdrawn preview with a WAIT is AVOID (R1)",
          (a.verdict, a.rule) == ("AVOID", "R1") and (b.verdict, b.rule) == ("SECURITY UPDATE", "R2")
          and (c.verdict, c.rule) == ("AVOID", "R1"),
          f"{a!r} {b!r} {c!r}")


_CORPUS: dict = {}


def corpus() -> tuple[list, dict]:
    if not _CORPUS:
        _CORPUS["records"], _CORPUS["groups"] = vp.load_inputs(_AUX)
        _CORPUS["reasons"] = vr.load_reasons(_AUX / "_data" / "verdict_reasons.yml")
    return _CORPUS["records"], _CORPUS["groups"]


def corpus_projection(life: list[dict]) -> dict:
    records, groups = corpus()
    return vp.project(records, groups, _CORPUS["reasons"], life)[0]


def check_corpus() -> None:
    shipped = corpus_projection(SHIPPED)
    avoid = {k: row for k, row in shipped["pages"].items() if row["verdict"] == "AVOID"}
    check("G94-C1 the shipped file passes and, over the shipped records and counted evidence, exactly the two "
          "KB5079391 pages are AVOID, each naming KB5086672",
          not vr.lifecycle_errors(SHIPPED) and len(SHIPPED) == 1 and set(avoid) == KB5079391_PAGES
          and all("Replacement: KB5086672." in row["body"] for row in avoid.values()),
          f"avoid={sorted(avoid)}")
    further = entry("KB5099991", ["26100.9001", "26200.9001"], "KB5099992", "2026-12-06")
    life, problems = loaded(SHIPPED + [further])
    grown = corpus_projection(life)
    changed = sorted(k for k in set(shipped["pages"]) | set(grown["pages"])
                     if shipped["pages"].get(k) != grown["pages"].get(k))
    check("G94-C2 the shipped corpus with a further valid withdrawal appended (a KB no record carries): the file "
          "loads both entries and no page's row changes -- before G94 both KB5079391 pages fell to INSUFFICIENT DATA",
          not problems and len(life) == 2 and not changed,
          f"problems={problems} loaded={len(life)} changed={changed[:4]}")


# ------------------------------------------------------------------------ mutants

def first_match_lifecycle_for(record, lifecycle=()):
    """lib/patch_decision.lifecycle_for before G94: the first matching entry in file order."""
    rec = record or {}
    kb, build = pd._text(rec.get("target_kb")), pd._text(rec.get("target_build"))
    if not kb or not build:
        return None
    for e in lifecycle or ():
        if (pd._text(e.get("product_id")) == pd._text(rec.get("product_id")) and pd._text(e.get("kb")) == kb
                and pd._text(e.get("relationship")) == "withdrawn_for_new_installs"
                and build in [pd._text(b) for b in e.get("builds") or []]):
            return dict(e)
    return None


def check_mutations(tmp: Path) -> None:
    real_errors = vr.lifecycle_errors

    def capped(entries):
        """lib/verdict_reasons.lifecycle_errors before G94: a second entry is refused."""
        return real_errors(entries) + ([f"{len(entries)} lifecycle entries"] if len(entries) > 1 else [])

    cases = [
        ("G94-X1 the one-entry cap restored (a second withdrawal refuses the whole file)",
         lambda: (check_completeness(), check_corpus()), vr, "lifecycle_errors", capped),
        ("G94-X2 first match in file order restored (a later entry for the same release can win)",
         lambda: (check_same_release(), check_reordering()), pd, "lifecycle_for", first_match_lifecycle_for),
    ]
    for label, body, owner, name, replacement in cases:
        original = getattr(owner, name)
        with captured() as baseline:
            body()
        setattr(owner, name, replacement)
        try:
            with captured() as failures:
                body()
        except Exception as exc:  # noqa: BLE001
            check(f"{label} -> caught", False, f"mutant crashed instead of being caught: {exc}")
            continue
        finally:
            setattr(owner, name, original)
        caught = [f for f in failures if f not in set(baseline)]
        check(f"{label} -> caught", bool(caught), "no named check failed that was not already failing")
        if caught:
            print(f"        by: {', '.join(c.split(' ', 1)[0] for c in caught)}")


def run() -> int:
    print("=" * 78)
    print("G94 OFFICIAL WITHDRAWAL COMPLETENESS")
    print("=" * 78)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        print("\n[W] every withdrawal kept, file order deciding nothing")
        check_completeness()
        check_same_release()
        check_reordering()
        check_idempotent()
        check_malformed(tmp / "w5")
        check_precedence()
        print("\n[C] the shipped corpus")
        check_corpus()
        print("\n[X] one mutant per fix, each caught by a named check")
        check_mutations(tmp)
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
