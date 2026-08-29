#!/usr/bin/env python3
"""A workflow may only promote consensus for the products it owns.

THE HAZARD. `.github/workflows/davinci-updates.yml` collects exactly one product --
`run_patch_evidence_collection.py --product-id blackmagic-davinci` -- and then ran
`apply_consensus_to_records.py --write-all --confirm-write` with NO scope, so it promoted all 905
records. Measured on main `35fb9692`, one dispatch would rewrite 8 records across 4 products and
change DaVinci's own records not at all:

    adobe-premiere-pro    1 record   <- quick_verdict, update_decision_label,
                                        update_decision_body, practical_recommendations
    obs-studio            1 record
    adobe-acrobat-reader  5 records
    adobe-acrobat-pro     1 record
    blackmagic-davinci    0 records

That is not hypothetical. 23 minutes after the unscoped form was introduced (`b5259931`,
2026-05-14), run `d0fd2b81` rewrote `2026-04-30-premiere-pro-26-2.md`, replacing a hand-authored
`consensus_report` -- "Manually reviewed Adobe Community reports naming Premiere Pro 26.2 or 26.2.0
Build 65 describe timeline..." -- with "3 user reports found for Premiere Pro 26.2...". That damage
is still on main. `--product-id` already existed three days earlier (`8d93b72c`), so the breadth was
an unremarked side effect of a wording-cleanup commit, never a contract.

WHY THE OWNED SET IS EXACTLY {blackmagic-davinci}. DaVinci is deliberately NOT in
`CONSENSUS_PROMOTION_PRODUCTS`, so a DaVinci-scoped promotion carries no retraction obligation.

The unscoped form DID act as a projection-rebuild path for other products -- an earlier draft of this
file claimed otherwise and was wrong. Running it rebuilds obs-studio 32.2.2 from 3 accepted sources
to 7, and #75 says so outright. The retraction-vs-skip argument (retraction fires only at count 0
while promotion skips at count <= 0) proves a WITHIN-RUN property and does not license the
across-run claim it was used for. Removing it is safe only because every product that depended on it
now has its own scoped step on `obs-evidence-collection.yml`, which runs on cron rather than
dispatch: obs-studio / powerpoint / windows-11 from #75, and Acrobat Pro / Reader added alongside
this change -- without those two, scoping this lane would have left 83 positive-count Acrobat records
with no rebuild path at all.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_davinci_promotion_scope.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402

import apply_consensus_to_records as acr  # noqa: E402
from lib.patch_identity import patch_key  # noqa: E402
from lib.report_counts import CONSENSUS_PROMOTION_PRODUCTS  # noqa: E402

WORKFLOW = _REPO / ".github" / "workflows" / "davinci-updates.yml"
OWNED = "blackmagic-davinci"
NOT_OWNED = ("adobe-premiere-pro", "obs-studio", "adobe-acrobat-reader",
             "adobe-acrobat-pro", "microsoft-windows-11", "microsoft-powerpoint")

NEWLINE = chr(10)

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
        _ERRORS.append(label)
        print(f"  FAIL  {label}" + (f"{NEWLINE}        {detail}" if detail else ""))


def steps() -> list[dict]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["collect"]["steps"]


def flag_value(command: str, flag: str) -> str | None:
    """Value of `flag`, accepting both `--flag value` and `--flag=value`. Property, not spelling."""
    tokens = command.replace("\\" + NEWLINE, " ").split()
    for i, tok in enumerate(tokens):
        if tok == flag:
            return tokens[i + 1] if i + 1 < len(tokens) else None
        if tok.startswith(flag + "="):
            return tok.split("=", 1)[1]
    return None


def promotion_steps() -> list[tuple[int, dict, str]]:
    out = []
    for i, st in enumerate(steps()):
        run = str(st.get("run") or "")
        if "apply_consensus_to_records" in run:
            out.append((i, st, run))
    return out


def run_cli(*args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(_REPO / "auxsays" / "scripts" / "apply_consensus_to_records.py"), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(_REPO), timeout=900)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def groups_for(product: str) -> int:
    """How many canonical groups a scoped run would evaluate for `product`."""
    rows = acr._load_yaml_list(_REPO / "auxsays" / "_data" / "consensus_evidence.yml")
    groups = acr._group_rows(rows, is_candidate_mode=False)
    return sum(1 for (pid, _v, _b) in groups if pid == product)


def run() -> int:
    print("=" * 78)
    print("DaVinci consensus promotion is scoped to the product the lane owns")
    print("=" * 78)

    # ---------- D8 ----------
    print(NEWLINE + "[D8] no production-reachable unscoped --write-all")
    # Parsed as YAML and asserted as a PROPERTY. A raw-string search for "--write-all" would pass on
    # a scoped call and fail on a harmless reformat; what matters is whether every promotion names a
    # product.
    proms = promotion_steps()
    check("D8 the lane has at least one promotion step", bool(proms),
          str([st.get("name") for st in steps()]))
    unscoped = [(i, st.get("name")) for i, st, run_text in proms
                if "--write-all" in run_text and not (flag_value(run_text, "--product-id") or "").strip()]
    check("D8 every --write-all invocation names a product", not unscoped, str(unscoped))
    for _i, st, run_text in proms:
        check(f"D8 {st.get('name')!r} is scoped to the owned product",
              flag_value(run_text, "--product-id") == OWNED,
              f"scope={flag_value(run_text, '--product-id')!r}")
        check(f"D8 {st.get('name')!r} carries exactly one scope",
              run_text.count("--product-id") == 1, run_text)

    # ---------- D9 ----------
    print(NEWLINE + "[D9] the lane still does what it exists to do")
    names = [str(st.get("name") or "") for st in steps()]
    runs = [str(st.get("run") or "") for st in steps()]
    collect = [r for r in runs if "run_patch_evidence_collection" in r]
    check("D9 it still collects DaVinci evidence",
          any(flag_value(r, "--product-id") == OWNED for r in collect), str(collect)[:160])
    check("D9 it still builds consensus status",
          any("build_consensus_from_evidence" in r for r in runs), str(names))
    check("D9 it still runs QA and audit",
          any("qa_patch_records" in r for r in runs) and any("audit_consensus_evidence" in r for r in runs))
    check("D9 the promotion runs after collection",
          next(i for i, r in enumerate(runs) if "run_patch_evidence_collection" in r)
          < next(i for i, r in enumerate(runs) if "apply_consensus_to_records" in r))

    # ---------- D1 ----------
    print(NEWLINE + "[D1] the owned product can still be promoted")
    owned_groups = groups_for(OWNED)
    check("D1 DaVinci has canonical groups to promote", owned_groups > 0, str(owned_groups))
    rc, out = run_cli("--product-id", OWNED, "--write-all", "--confirm-write")
    check("D1 a DaVinci-scoped promotion succeeds", rc == 0, out[-200:])
    check("D1 it evaluates exactly DaVinci's groups",
          f"{owned_groups} group(s)" in out, out[-200:])

    # ---------- D2-D6 ----------
    print(NEWLINE + "[D2-D6] no other product is reachable from this lane")
    # The scope is a literal in the workflow, so this asserts the property that matters: the value the
    # lane passes is the owned product and nothing else can be named by it.
    for _i, _st, run_text in proms:
        scope = flag_value(run_text, "--product-id")
        for other in NOT_OWNED:
            check(f"D2-D6 the lane cannot promote {other}", scope != other,
                  f"scope={scope!r}")
    # And a scoped run genuinely confines itself: evaluate what each scope would touch.
    for other in NOT_OWNED:
        n = groups_for(other)
        rc2, out2 = run_cli("--product-id", OWNED, "--write-all", "--confirm-write")
        check(f"D2-D6 a DaVinci-scoped run reports no {other} group",
              f"{owned_groups} group(s)" in out2 and rc2 == 0,
              f"{other} has {n} groups of its own")
        break  # one representative CLI run; the per-product property is the scope assertion above

    # ---------- D2 in the strong form ----------
    print(NEWLINE + "[D2] Premiere's hand-authored prose survives a dispatch")
    premiere = _REPO / "auxsays" / "updates" / "generated" / "2026-04-30-premiere-pro-26-2.md"
    if premiere.exists():
        before = premiere.read_bytes()
        rc3, _o = run_cli("--product-id", OWNED, "--write-all", "--confirm-write")
        check("D2 the scoped promotion leaves Premiere byte-identical",
              premiere.read_bytes() == before and rc3 == 0, "Premiere record changed")
        text = premiere.read_text(encoding="utf-8")
        check("D2 its human decision prose is still present",
              "WAIT for production systems" in text,
              "the hand-authored quick_verdict is gone")
    else:
        check("D2 the Premiere record exists to protect", False, str(premiere))

    # ---------- D7 ----------
    print(NEWLINE + "[D7] build-aware identity is untouched by scoping")
    rows = acr._load_yaml_list(_REPO / "auxsays" / "_data" / "consensus_evidence.yml")
    groups = acr._group_rows(rows, is_candidate_mode=False)
    ppt = sorted(k for k in groups if k[0] == "microsoft-powerpoint")
    check("D7 PowerPoint groups keep their exact build slot",
          all(k[2] for k in ppt), str(ppt))
    check("D7 Candidate 1 is addressed by its canonical triple",
          patch_key("microsoft-powerpoint", "2607", "20228.20110") in groups
          or not ppt, str(ppt))
    dav = sorted(k for k in groups if k[0] == OWNED)
    check("D7 DaVinci is version-only, so its build slot collapses to ''",
          all(k[2] == "" for k in dav), str(dav[:3]))

    # ---------- the empty-scope trap ----------
    print(NEWLINE + "[D8b] an empty --product-id must not mean 'every product'")
    # The filter is applied as `if product_id_filter:`, so an empty string is FALSY and silently
    # widens the run to the whole corpus. Measured before the guard: `--product-id ""` with
    # --write-all rewrote 8 records across 4 products, byte-identical to passing no scope, while a
    # MISSPELLED id correctly wrote nothing. A caller whose variable expanded to nothing would get
    # the full blast radius and no error.
    for empty in ("", "   "):
        rc4, out4 = run_cli("--product-id", empty, "--write-all", "--confirm-write")
        check(f"D8b --product-id {empty!r} is refused", rc4 == 2, f"rc={rc4} {out4[:120]}")
        check(f"D8b ... with an explanation naming the flag", "--product-id" in out4, out4[:160])
    rc5, out5 = run_cli("--product-id", "definitely-not-a-product", "--write-all", "--confirm-write")
    # It writes nothing, which is the safety property that matters here. It is NOT "fail closed" in
    # the loud sense: exit 0 is indistinguishable from a known product that simply had no groups, so
    # a typo in a workflow promotes nothing and still goes green. Recorded rather than dressed up.
    check("D8b an unknown product does not widen the run", "0 group(s)" in out5, out5[-160:])
    check("D8b ... though it exits 0, so a typo would be silent",
          rc5 == 0, f"rc={rc5} -- if this ever becomes 2, update the note above")

    # ---------- D10 ----------
    print(NEWLINE + "[D10] writeback and deploy still cover what the lane produces")
    wb = [r for r in runs if "automation_writeback" in r]
    check("D10 the lane still has a writeback step", bool(wb), str(names))
    blob = " ".join(wb)
    check("D10 generated records remain committable",
          "auxsays/updates/generated" in blob, blob[:200])
    check("D10 the evidence and method-health files remain committable",
          "consensus_evidence.yml" in blob and "evidence_method_health.yml" in blob)
    check("D10 a Pages deploy is still triggered", "--pages-cmd" in blob)
    # The broad allow is deliberate: the GLOBAL reconcile in the consensus step can legitimately
    # change any product's count, and automation_writeback fails the run when the tree holds material
    # the commit candidate omits. Narrowing it without restoring those records would fail-close.
    #
    # This asserts the ACTUAL glob. The previous form asked whether "auxsays/updates/generated"
    # appeared anywhere in the step -- which a narrowed `*davinci*.md` also satisfies, so it passed
    # under the very mutation it existed to catch.
    allows = []
    for st in steps():
        run_text = str(st.get("run") or "")
        if "automation_writeback" not in run_text:
            continue
        toks = run_text.replace("\\" + NEWLINE, " ").split()
        allows += [toks[i + 1].strip("'\"") for i, tok in enumerate(toks[:-1]) if tok == "--allow"]
    check("D10 the allow still covers EVERY generated record, not just DaVinci's",
          "auxsays/updates/generated/*.md" in allows, str(allows))

    # ---------- ownership invariant ----------
    print(NEWLINE + "[D11] the owned set is derived, not assumed")
    check("D11 DaVinci is not retraction-eligible, so scoping adds no obligation",
          OWNED not in CONSENSUS_PROMOTION_PRODUCTS, str(sorted(CONSENSUS_PROMOTION_PRODUCTS)))
    # The PROPERTY, not the membership list. This asserted set equality against three literal ids,
    # so it failed the moment Acrobat was legitimately granted retraction-eligibility -- reporting a
    # scope violation in THIS workflow when nothing here had changed. What it means to protect is
    # that no retractable product is promoted by this manual-dispatch lane; where they ARE promoted
    # (the cron lane) is pinned by R7 in test_windows_count_authority.py.
    promoted_here = {pid
                     for st in steps()
                     if "apply_consensus_to_records" in str(st.get("run") or "")
                     for pid in [flag_value(str(st.get("run") or ""), "--product-id")]
                     if pid}
    check("D11 the retractable products are promoted by the cron lane, not this one",
          not (set(CONSENSUS_PROMOTION_PRODUCTS) & promoted_here),
          f"promoted_here={sorted(promoted_here)} retractable={sorted(CONSENSUS_PROMOTION_PRODUCTS)}")

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
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
