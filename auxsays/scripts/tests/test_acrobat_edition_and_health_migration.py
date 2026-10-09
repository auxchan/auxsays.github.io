#!/usr/bin/env python3
"""Two repairs from one demonstrated production regression (AUX-027).

A targeted Acrobat collector dispatch was used to clear a frozen method-health backlog. It was the
wrong mechanism -- a full collector dispatch discovers evidence -- and run 37871206618 / commit
de8ccb21 added five counted Reader evidence rows besides the health it was meant to fix. One of them
made Reader 15.009.20071 publish exactly one report, sourced from a thread titled "Acrobat DC Pro
will not update beyond 15.9.20069.15942", while Pro 15.009.20071 published none.

  1. EDITION IDENTITY. PRO_RE's `dc pro` alternative required the literal word "Adobe" in front of
     it, while its `pro dc` alternative had always treated that prefix as optional. So bare
     "Acrobat DC Pro" -- how people actually write it -- missed PRO_RE, missed READER_RE, hit
     ACROBAT_BARE_RE, fell through to generic_acrobat_without_edition, and the shared-DC-build
     fallback published an explicitly Pro report on the Reader page.

  2. A HEALTH-ONLY MIGRATION, so telemetry can be repaired without a collector ever running.
     Deterministic, idempotent, zero-network, and structurally incapable of touching evidence.

Offline: no network, no repo writes.
"""
from __future__ import annotations

import importlib.util
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from patch_collectors import adobe_acrobat_community as ac   # noqa: E402
from patch_collectors.base import method_health_row          # noqa: E402

READER = "adobe-acrobat-reader"
PRO = "adobe-acrobat-pro"
RETIRED = ("adobe_community_search", "reddit_search")

PASS = FAIL = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


def load_migration():
    path = SCRIPTS / "migrate_acrobat_retired_method_health.py"
    spec = importlib.util.spec_from_file_location("aux_health_migration", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["aux_health_migration"] = mod
    spec.loader.exec_module(mod)
    return mod


def health(product_id: str, version: str, method_id: str, status: str,
           *, last_run: str = "2026-09-01T00:00:00Z", reason: str | None = "boom") -> dict:
    return method_health_row(
        product_id=product_id, update_version=version, method_id=method_id,
        source_type=("reddit_community_report" if method_id == "reddit_search"
                     else "adobe_community_bug_report"),
        status=status, candidates_found=2, accepted_reports=0, rejected_reports=2,
        blocked_reason=reason, last_run=last_run, notes="old")


def run_suite() -> int:
    print("=" * 92)
    print("A  every real Pro spelling is Pro, on both collection paths")
    print("=" * 92)
    PRO_FORMS = ("Acrobat Pro", "Acrobat Pro DC", "Acrobat DC Pro", "Adobe Acrobat DC Pro",
                 "Adobe Acrobat Pro DC")
    for i, form in enumerate(PRO_FORMS, start=1):
        text = f"{form} 15.009.20071 crashes on open after the update"
        check(f"A.{i} '{form}' is recognised as Pro",
              bool(ac.PRO_RE.search(text)), text)
        attributed, _alias, _appl, reason = ac.acrobat_edition_attribution(text, READER)
        check(f"A.{i}r Reader collection refuses '{form}' as wrong_product",
              attributed is False and reason == "wrong_product", f"{attributed} {reason}")
        attributed, alias, appl, reason = ac.acrobat_edition_attribution(text, PRO)
        check(f"A.{i}p Pro collection accepts '{form}' as explicit Pro",
              attributed is True and reason is None and appl == PRO, f"{attributed} {reason} {appl}")

    print()
    print("=" * 92)
    print("B  nothing else was broadened")
    print("=" * 92)
    # Generic "Acrobat DC" must STAY generic: the shared-build policy owns it, and that policy is
    # what lets a report that names the build but not the edition count at all.
    for text in ("Acrobat DC 15.009.20069 fails to install",
                 "Adobe Acrobat 15.009.20069 will not open after the update",
                 "Acrobat 15.009.20069 crashes"):
        attributed, _a, _b, reason = ac.acrobat_edition_attribution(text, READER)
        check(f"B.1 generic stays generic: {text[:34]!r}",
              attributed is False and reason == "generic_acrobat_without_edition",
              f"{attributed} {reason}")
    # Licensing-tier wording is not a product attribution, and this repair must not have made it one.
    lic = "Reader switches to licensed Acrobat Pro mode when the user signs in"
    attributed, _a, _b, reason = ac.acrobat_edition_attribution(lic, PRO)
    check("B.2 an Acrobat Pro LICENCE mention still does not attribute the patch to Pro",
          attributed is False, f"{attributed} {reason}")
    lic_dc = "Reader switches to a licensed Acrobat DC Pro subscription when the user signs in"
    attributed, _a, _b, reason = ac.acrobat_edition_attribution(lic_dc, PRO)
    check("B.3 and the newly recognised DC Pro spelling is held to the same licence rule",
          attributed is False, f"{attributed} {reason}")
    # Reader spellings are untouched.
    for text in ("Acrobat Reader DC 15.009.20069 crashes", "Adobe Reader 15.009.20069 crashes",
                 "Reader DC 15.009.20069 crashes"):
        attributed, _a, _b, reason = ac.acrobat_edition_attribution(text, READER)
        check(f"B.4 Reader spelling still attributes to Reader: {text[:28]!r}",
              attributed is True and reason is None, f"{attributed} {reason}")
    # The SYMMETRIC refusal. A Reader-only report on a Pro page must be wrong_product too --
    # the defect was one-directional but the contract is not, and without this the Pro branch
    # could stop refusing the opposite edition with every other check still green.
    for text in ("Acrobat Reader DC 15.009.20069 crashes on open",
                 "Adobe Reader 15.009.20069 will not print",
                 "Reader DC 15.009.20069 fails to open PDFs"):
        attributed, _a, _b, reason = ac.acrobat_edition_attribution(text, PRO)
        check(f"B.4p Pro collection refuses a Reader-only report: {text[:30]!r}",
              attributed is False and reason == "wrong_product", f"{attributed} {reason}")

    # Both editions named -> genuinely shared, as before.
    both = "Acrobat DC Pro and Acrobat Reader DC 15.009.20069 both crash on open"
    attributed, _alias, appl, reason = ac.acrobat_edition_attribution(both, READER)
    check("B.5 a report naming BOTH editions is still shared, not wrong_product",
          attributed is True and READER in appl and PRO in appl, f"{attributed} {appl} {reason}")
    # "Acrobat DC Reader" is NOT added: it does not occur anywhere in the measured corpus.
    check("B.6 no unmeasured alias was invented for Reader",
          not ac.READER_RE.search("Acrobat DC Reader 15.009.20069 crashes"))

    print()
    print("=" * 92)
    print("C  the demonstrated row: the exact stored text, both editions")
    print("=" * 92)
    STORED = ("Acrobat DC Pro will not update beyond 15.9.20069.15942 Acrobat DC Pro says it "
              "updates to but it doesn't. Always stays at 15.009.20071. I try to update manually "
              "and it states: The upgrade patch cannot be installed by the windows installer "
              "service because the program to be...")
    attributed, _a, _b, reason = ac.acrobat_edition_attribution(STORED, READER)
    check("C.1 the stored text is wrong_product for a Reader page",
          attributed is False and reason == "wrong_product", f"{attributed} {reason}")
    check("C.2 and it no longer reaches the shared-DC-build fallback at all",
          reason != "generic_acrobat_without_edition", str(reason))
    attributed, _a, appl, reason = ac.acrobat_edition_attribution(STORED, PRO)
    check("C.3 for a Pro page it is explicit Pro, not a shared-build guess",
          attributed is True and appl == PRO, f"{attributed} {appl}")

    print()
    print("=" * 92)
    print("D  the health-only migration: scope, shape, idempotence")
    print("=" * 92)
    mig = load_migration()
    rows = [
        health(READER, "15.009.20071", "adobe_community_search", "blocked"),
        health(READER, "15.009.20071", "reddit_search", "broken"),
        health(PRO, "15.009.20069", "adobe_community_search", "blocked"),
        health(READER, "26.001.21563", "adobe_community_algolia_search", "success", reason=None),
        health("blackmagic-davinci", "19.1", "web_search", "disabled", reason=None),
        health("microsoft-powerpoint", "2603", "reddit_search", "blocked"),
    ]
    out, changed = mig.migrate(rows, last_run="2026-10-09T12:00:00Z")
    by = {(str(r["product_id"]), str(r["method_id"])): r for r in out}
    check("D.1 nothing is added and nothing is deleted", len(out) == len(rows))
    check("D.2 both retired Acrobat methods become disabled",
          all(by[(p, m)]["status"] == "disabled"
              for p, m in ((READER, "adobe_community_search"), (READER, "reddit_search"),
                           (PRO, "adobe_community_search"))),
          str({k: v["status"] for k, v in by.items()}))
    check("D.3 the ACTIVE Acrobat method keeps its real health",
          by[(READER, "adobe_community_algolia_search")]["status"] == "success")
    check("D.4 another product's reddit_search row is NOT touched",
          by[("microsoft-powerpoint", "reddit_search")]["status"] == "blocked")
    check("D.5 another product's already-disabled row is NOT touched",
          by[("blackmagic-davinci", "web_search")] is rows[4])
    check("D.6 every repaired row drops its blocked_reason",
          all(not str(by[(p, m)].get("blocked_reason") or "")
              for p, m in ((READER, "adobe_community_search"), (READER, "reddit_search"))))
    check("D.7 every repaired row reports not-run counters",
          all(int(by[(p, m)].get("candidates_found") or 0) == 0
              and int(by[(p, m)].get("accepted_candidates") or 0) == 0
              and int(by[(p, m)].get("rejected_reports") or 0) == 0
              for p, m in ((READER, "adobe_community_search"), (READER, "reddit_search"))))
    check("D.8 identity is preserved verbatim",
          by[(READER, "15.009.20071" and "adobe_community_search")]["update_version"] == "15.009.20071"
          and by[(PRO, "adobe_community_search")]["update_version"] == "15.009.20069")
    check("D.9 each retired method keeps its OWN source family",
          by[(READER, "adobe_community_search")]["source_type"] == "adobe_community_bug_report"
          and by[(READER, "reddit_search")]["source_type"] == "reddit_community_report")
    check("D.10 the repaired rows carry the migration timestamp",
          all(by[(p, m)]["last_run"] == "2026-10-09T12:00:00Z"
              for p, m in ((READER, "adobe_community_search"), (PRO, "adobe_community_search"))))
    check("D.11 the notes a reader sees name no repository path",
          all(not any(t in str(by[(p, m)].get("notes") or "")
                      for t in ("lib/", ".py", "auxsays/"))
              for p, m in ((READER, "adobe_community_search"), (READER, "reddit_search"))))
    check("D.12 changed lists exactly the rows that moved", len(changed) == 3, str(len(changed)))

    # IDEMPOTENCE: a second pass over its own output changes nothing, and does not restamp.
    out2, changed2 = mig.migrate(out, last_run="2026-11-01T00:00:00Z")
    check("D.13 a second pass changes nothing", changed2 == [], str(len(changed2)))
    check("D.14 and does not restamp a row that was already correct",
          all(a["last_run"] == b["last_run"] for a, b in zip(out, out2)))
    # A row already correct keeps its OWN last_run rather than the migration's.
    pre_ok = health(READER, "15.009.20077", "reddit_search", "disabled",
                    last_run="2026-10-08T03:00:00Z", reason=None)
    pre_ok = mig.migrate([pre_ok], last_run="2026-10-08T03:00:00Z")[0][0]
    out3, changed3 = mig.migrate([pre_ok], last_run="2026-12-25T00:00:00Z")
    check("D.15 an already-correct row keeps its own timestamp, not the migration's",
          changed3 == [] and out3[0]["last_run"] == "2026-10-08T03:00:00Z",
          str(out3[0]["last_run"]))

    print()
    print("=" * 92)
    print("E  the migration cannot touch evidence, and needs no network")
    print("=" * 92)
    src = (SCRIPTS / "migrate_acrobat_retired_method_health.py").read_text(encoding="utf-8")
    check("E.1 it writes exactly one file, the health store",
          src.count("write_method_health_file(") == 1
          and "consensus_evidence" not in src
          and "update_linked" not in src
          and "recent_acrobat" not in src)
    # Checked over the AST, not the text: the module docstring legitimately NAMES the things it
    # must not do ("rewrote three generated records"), and a grep over prose would fail on its
    # own explanation while a grep that passed would prove nothing about the code.
    import ast as _ast
    tree = _ast.parse(src)
    called = {n.func.id for n in _ast.walk(tree)
              if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Name)}
    called |= {n.func.attr for n in _ast.walk(tree)
               if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Attribute)}
    imported = {a.name for n in _ast.walk(tree) if isinstance(n, _ast.ImportFrom) for a in n.names}
    forbidden = {"append_evidence_rows", "apply_consensus_to_records", "reconcile_record_counts",
                 "apply_consensus_writeback", "upsert_method_health", "load_evidence"}
    check("E.2 it calls and imports nothing that writes evidence, a record or a count",
          not (forbidden & (called | imported)), str(sorted(forbidden & (called | imported))))
    writers = {c for c in called if "write" in c or "replace_via" in c}
    check("E.2b the only writer it calls is the health-store writer",
          writers == {"write_method_health_file"}, str(sorted(writers)))
    check("E.3 it makes no network call and runs no collector",
          not any(t in src for t in ("urlopen", "requests", "urllib.request", "collect_for_record",
                                     "candidates(")))
    check("E.4 its scope is the two products and the two retired methods, named explicitly",
          set(mig.PRODUCTS) == {READER, PRO} and set(mig.SOURCE_TYPES) == set(RETIRED),
          f"{mig.PRODUCTS} {sorted(mig.SOURCE_TYPES)}")
    check("E.5 it refuses to write without an explicit flag", "--write" in src and "dry run" in src)
    check("E.6 the timestamp is required rather than defaulted to now()",
          'required=True' in src and "datetime.now" not in src and "utcnow" not in src)

    print()
    print("=" * 92)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed: " + ", ".join(FAILURES))
    print("=" * 92)
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run_suite())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
