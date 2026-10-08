#!/usr/bin/env python3
"""A retired Acrobat method must report that it is retired, not freeze at its last failure.

`adobe_community_search` and `reddit_search` stopped executing for Acrobat when the collector
retired them, and the comment that did it claimed "their health rows stay honest". They did not.
`upsert_method_health` keys rows on (product_id, update_version, target_build, method_id) and
RETAINS whatever a run does not emit, so 286 rows sat at status `blocked` with last_run
2026-08-07/2026-09-01 next to algolia rows that refreshed daily -- and three public surfaces read
status with NO freshness check:

  * apply_consensus_to_records.py           -> "Some community sources were unavailable during the
                                               last check"                     (143 identities)
  * _layouts/aux-update.html                -> "Collection blocked." / "methods are CURRENTLY
                                               blocked or returning errors"    (143 identities)
  * _includes/monitoring-status.html        -> a per-method line reading "Source request was
                                               blocked - last checked Aug 7, 2026"

All three were caused SOLELY by the frozen rows: across every Acrobat row the executing method
reports only success or no_results, never blocked. This suite pins the repair -- a fresh `disabled`
row every run -- and the properties that make `disabled` the right status rather than a cosmetic one.

Offline: no network, no repo writes.
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import yaml                                                    # noqa: E402
from patch_collectors import adobe_acrobat_community as ac      # noqa: E402
from patch_collectors.base import (                             # noqa: E402
    CollectorContext, METHOD_HEALTH_PATH, generated_records, load_method_health,
    normalize_method_health_row, upsert_method_health,
)

RETIRED = ("adobe_community_search", "reddit_search")
ACTIVE = "adobe_community_algolia_search"
EDITIONS = ("adobe-acrobat-pro", "adobe-acrobat-reader")
FLAG = "AUXSAYS_ACROBAT_RETIRED_METHODS"

# The exact predicates the three public consumers use, copied from their source so a change to
# either side shows up here as a failure rather than as a silent divergence.
UNAVAILABLE_COPY_STATUSES = {"blocked", "partial", "low_confidence", "broken"}   # apply_consensus_to_records.py
COLLECTION_BLOCKED_STATUSES = {"blocked", "broken"}                             # _layouts/aux-update.html
MONITORING_DEGRADED_STATUSES = {"blocked", "broken", "partial", "low_confidence",
                                "manual_review_needed", "stale"}                # both of the above

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


WARNINGS: list[str] = []


def warn(label: str, ok: bool, detail: str = "") -> None:
    """A CORPUS observation, not a gate.

    The repair is a PRODUCER fix: the collector stops writing frozen rows, and each record's
    rows are rewritten the next time THAT RECORD is walked. That is a standing backlog, not a
    one-run lag -- Acrobat is walked newest-first under a wall-clock budget and a scheduled run
    reaches roughly the first 20 of 196 records per edition, while 139 of the 143 frozen
    identities sit outside that prefix and some are from 2015. Clearing them needs scoped
    dispatches. Failing the build on the stored corpus would make this suite red on the very
    commit that fixes the producer, so the corpus is REPORTED with its count and the fail-closed
    assertion is made against what the collector EMITS (section A)."""
    if ok:
        print(f"  ok    {label}")
    else:
        WARNINGS.append(label)
        print(f"  WARN  {label}" + (f"  [{detail}]" if detail else ""))


def silence_discovery() -> None:
    """Replace every discovery function, so nothing can reach a transport."""
    for name in ("adobe_community_algolia_search_candidates",
                 "adobe_community_search_candidates", "reddit_search_candidates"):
        setattr(ac, name, lambda edition, record, context, errors: [])


def emit(product_id: str, *, enabled: bool) -> list[dict]:
    before = os.environ.get(FLAG)
    os.environ[FLAG] = "1" if enabled else ""
    try:
        collector = ac.AdobeAcrobatCollector(product_id)
        record = generated_records(product_id, [], include_archived=False)[0]
        context = CollectorContext(write=False, since="2026-01-01", max_pages=2, target_versions=[])
        _accepted, _rejected, health = collector.collect_for_record(
            record, context, "2026-10-08T14:00:00Z")
        return health
    finally:
        if before is None:
            os.environ.pop(FLAG, None)
        else:
            os.environ[FLAG] = before


def statuses(health: list[dict]) -> dict[str, str]:
    return {str(h["method_id"]): str(h["status"]) for h in health}


def run_suite() -> int:
    silence_discovery()

    print("=" * 92)
    print("A  a retired method reports every run, and reports `disabled`")
    print("=" * 92)
    for edition in EDITIONS:
        health = emit(edition, enabled=False)
        st = statuses(health)
        check(f"A.1 {edition}: all three methods report a row",
              set(st) == {ACTIVE, *RETIRED}, str(sorted(st)))
        check(f"A.2 {edition}: both retired methods report `disabled`",
              all(st.get(m) == "disabled" for m in RETIRED),
              str({m: st.get(m) for m in RETIRED}))
        check(f"A.3 {edition}: the executing method reports its REAL health, not disabled",
              st.get(ACTIVE) != "disabled", str(st.get(ACTIVE)))
        check(f"A.4 {edition}: every row carries this run's timestamp, so none can go stale",
              {str(h.get("last_run")) for h in health} == {"2026-10-08T14:00:00Z"},
              str({str(h.get('last_run')) for h in health}))
        check(f"A.5 {edition}: a disabled row carries no blocked_reason",
              all(not str(h.get("blocked_reason") or "")
                  for h in health if str(h["method_id"]) in RETIRED))
        check(f"A.6 {edition}: a disabled row claims no candidates and no reports",
              all(int(h.get("candidates_found") or 0) == 0
                  and int(h.get("accepted_candidates") or 0) == 0
                  and int(h.get("rejected_reports") or 0) == 0
                  for h in health if str(h["method_id"]) in RETIRED))
        check(f"A.7 {edition}: the row is attributed to this edition, not the sibling",
              all(str(h.get("product_id")) == edition for h in health))
        # A row must describe the method it names. adobe_community_search belongs to the Adobe
        # community family and reddit_search does not; collapsing them would file a Reddit row
        # under the family the ACTIVE method shares, which is the family used to attribute
        # stored evidence.
        by_id = {str(h["method_id"]): str(h.get("source_type")) for h in health}
        check(f"A.8 {edition}: each retired row carries its OWN source family",
              by_id.get("adobe_community_search") == ac.ADOBE_COMMUNITY_SOURCE_TYPE
              and by_id.get("reddit_search") == ac.REDDIT_SOURCE_TYPE,
              str({m: by_id.get(m) for m in RETIRED}))

    print()
    print("=" * 92)
    print("B  re-enabling a method replaces the disabled row normally")
    print("=" * 92)
    for edition in EDITIONS:
        health = emit(edition, enabled=True)
        st = statuses(health)
        check(f"B.1 {edition}: with the flag on, no method reports `disabled`",
              "disabled" not in st.values(), str(st))
        check(f"B.2 {edition}: still exactly one row per method -- never a duplicate pair",
              len(health) == 3 and len(st) == 3, f"{len(health)} rows, {len(st)} ids")
    # The identity key is what makes the replacement clean: same (product, version, build, method).
    off = {(str(h["product_id"]), str(h["update_version"]), str(h.get("target_build") or ""),
            str(h["method_id"])) for h in emit(EDITIONS[0], enabled=False)}
    on = {(str(h["product_id"]), str(h["update_version"]), str(h.get("target_build") or ""),
           str(h["method_id"])) for h in emit(EDITIONS[0], enabled=True)}
    check("B.3 enabled and disabled runs write the SAME identity keys, so one upserts over the other",
          off == on, str(off ^ on))

    # upsert_method_health is LAST-WINS over the list it is given, and the disabled loop runs
    # after the executed loop. If a run ever emitted both a real row and a disabled row for one
    # method, the disabled one would overwrite the truth. The collector forecloses it by
    # emptying the retired tuple when the flag turns the methods on; this pins that.
    for enabled in (False, True):
        for edition in EDITIONS:
            health = emit(edition, enabled=enabled)
            keys = [(str(h["method_id"])) for h in health]
            check(f"B.4 {edition} flag={enabled}: no method is written twice in one run",
                  len(keys) == len(set(keys)), str(sorted(keys)))

    print()
    print("=" * 92)
    print("C  `disabled` is not healthy, not a failure, and not 'unavailable'")
    print("=" * 92)
    check("C.1 disabled does not trigger the unavailable-source copy",
          "disabled" not in UNAVAILABLE_COPY_STATUSES)
    check("C.2 disabled does not trigger 'Collection blocked.'",
          "disabled" not in COLLECTION_BLOCKED_STATUSES)
    check("C.3 disabled is not a degraded/attempted-and-failed status",
          "disabled" not in MONITORING_DEGRADED_STATUSES)
    monitoring = (ROOT / "_includes" / "monitoring-status.html").read_text(encoding="utf-8")
    check("C.4 the monitoring ladder counts only success/no_results as healthy, so disabled is not",
          "m_status == 'success' or m_status == 'no_results'" in monitoring)
    check("C.5 the ladder treats a disabled row as not-usable",
          "m_status == 'disabled'" in monitoring and "m_is_disabled" in monitoring)
    # The fail-open this avoids: the collector's own mapper returns no_results for a method with
    # nothing to show, and no_results IS healthy to the ladder. A not-run method must never take
    # that path -- it would publish a method that never ran as a working source.
    # adobe_community_search shares the ACTIVE method's source family
    # (adobe_community_bug_report), and finalize_method_health_delta distributes a family's
    # stored rows across its rows by (identity, source_type). A disabled row must not be able to
    # collect any of that credit: _distribute_capped caps each row's share at its own
    # accepted_candidates, which is 0 here.
    #
    # The ACTIVE row is given a real accepted count on purpose. An earlier version built this
    # from the silenced collector, where algolia's own accepted_candidates was also 0 -- so the
    # cap was not load-bearing and the check passed even with _distribute_capped replaced by an
    # uncapped 'give it all to the first row' distributor. It has to be able to tell 'capped'
    # from 'the other row happened to take everything'.
    from patch_collectors.base import finalize_method_health_delta, method_health_row
    def family_row(method_id: str, status: str, accepted: int) -> dict:
        return method_health_row(
            product_id=EDITIONS[0], update_version="26.001.21563", method_id=method_id,
            source_type="adobe_community_bug_report", status=status, candidates_found=accepted,
            accepted_reports=accepted, rejected_reports=0, blocked_reason=None,
            last_run="2026-10-08T14:00:00Z", notes="probe")
    stored = [{"product_id": EDITIONS[0], "update_version": "26.001.21563",
               "target_build": "", "source_type": "adobe_community_bug_report"}] * 4
    for order in ("active_first", "disabled_first"):
        active = family_row(ACTIVE, "success", 4)
        dead = family_row(RETIRED[0], "disabled", 0)
        family = [active, dead] if order == "active_first" else [dead, active]
        finalize_method_health_delta(family, stored, [])
        check(f"C.7 ({order}) a disabled row is credited with none of its family's stored "
              "evidence, and the active row keeps all of it",
              int(dead.get("evidence_rows_added") or 0) == 0
              and int(dead.get("accepted_candidates") or 0) == 0
              and int(active.get("evidence_rows_added") or 0) == 4,
              f"disabled={dead.get('evidence_rows_added')} active={active.get('evidence_rows_added')}")

    check("C.6 the status mapper would call an unrun method healthy, which is why disabled is set "
          "explicitly rather than derived",
          ac._method_status([], [], [], []) == "no_results",
          str(ac._method_status([], [], [], [])))

    print()
    print("=" * 92)
    print("D  the live store: no Acrobat identity may be falsely current-blocked")
    print("=" * 92)
    live = load_method_health(METHOD_HEALTH_PATH)
    acro = [r for r in live if str(r.get("product_id") or "").startswith("adobe-acrobat")]
    check("D.1 the live store still holds Acrobat telemetry", len(acro) > 0, str(len(acro)))
    # Historical rows are KEPT. The repair changes what a row says, never whether it exists.
    retired_rows = [r for r in acro if str(r.get("method_id")) in RETIRED]
    check("D.2 the retired methods' rows are retained, not deleted",
          len(retired_rows) > 0, str(len(retired_rows)))
    # FAIL-CLOSED: the collector, as it stands, cannot produce a blocked row for a method it
    # does not run. That is the invariant this change owns.
    emitted = {str(h["method_id"]): str(h["status"])
               for e in EDITIONS for h in emit(e, enabled=False)}
    check("D.3 the collector cannot emit a blocked/broken row for a method it does not run",
          not any(emitted.get(m) in COLLECTION_BLOCKED_STATUSES for m in RETIRED),
          str({m: emitted.get(m) for m in RETIRED}))
    frozen = [r for r in retired_rows if str(r.get("status")) in COLLECTION_BLOCKED_STATUSES]
    warn("D.3b the stored corpus holds no retired row still claiming blocked/broken",
         not frozen,
         f"{len(frozen)} awaiting a walk of their record, newest last_run "
         f"{max((str(r.get('last_run')) for r in frozen), default='-')}")
    # The executing method must still be able to report a REAL failure. `isinstance(..., list)`
    # used to stand here, which no corpus and no collector behaviour could ever falsify. Drive
    # the active method into an error instead and read what it reports.
    saved = ac.adobe_community_algolia_search_candidates
    try:
        def failing(edition, record, context, errors):
            errors.append({"source_url": "https://community.adobe.com/",
                           "reason": "adobe_community_search_fetch_failed:blocked"})
            return []
        ac.adobe_community_algolia_search_candidates = failing
        broke = statuses(emit(EDITIONS[0], enabled=False))
    finally:
        ac.adobe_community_algolia_search_candidates = saved
    check("D.4 a REAL failure of the executing method is still reported, not suppressed",
          broke.get(ACTIVE) in COLLECTION_BLOCKED_STATUSES, str(broke))
    check("D.4b and the retired methods still report disabled in that same run, so a real "
          "failure is distinguishable from a method nobody ran",
          all(broke.get(m) == "disabled" for m in RETIRED), str(broke))
    identities = {(str(r.get("product_id")), str(r.get("update_version")),
                   str(r.get("target_build") or "")) for r in acro}
    falsely = {k for k in identities
               if {str(r.get("status")) for r in acro
                   if (str(r.get("product_id")), str(r.get("update_version")),
                       str(r.get("target_build") or "")) == k} & UNAVAILABLE_COPY_STATUSES}
    # Scope this to the UNRUN methods. The earlier form was
    #     set(emitted.values()) & UNAVAILABLE_COPY_STATUSES - {emitted.get(ACTIVE)}
    # and `-` binds tighter than `&`, so it removed the active method's status from the trigger
    # set for EVERY row: a genuinely blocked active method would have whitelisted `blocked`
    # everywhere and the check would still have passed.
    retired_statuses = {emitted.get(m) for m in RETIRED}
    check("D.5 no status the collector emits for an UNRUN method can trigger the unavailable-source copy",
          not (retired_statuses & UNAVAILABLE_COPY_STATUSES), str(retired_statuses))
    warn("D.5b no stored Acrobat identity triggers the unavailable-source copy from a method nobody ran",
         not falsely, f"{len(falsely)} of {len(identities)} identities awaiting a walk of their record")

    # KNOWN AND ACCEPTED CONSEQUENCE, pinned so it cannot change unnoticed.
    # 69 Acrobat identities never carried a retired row -- their records postdate the
    # retirement -- so they publish INSUFFICIENT COVERAGE today and will publish MONITORING
    # DEGRADED once they gain a disabled row, because partial disablement is itself a degraded
    # signal in the ladder. The substantive figure a reader acts on is identical either way
    # ("1 fresh (success / no reports) - need 2"), and the alternative -- emitting a disabled
    # row only where a stale row already exists -- would encode "the file already has a bad
    # row" as a business rule and let new records drift back into silence.
    check("D.6 partial disablement is a degraded signal, which is why 69 identities change label",
          "mon_partial_disabled" in monitoring
          and "mon_disabled > 0 and mon_disabled < mon_total" in monitoring)
    check("D.7 the healthy-source count is unmoved by a disabled row, so the figure a reader "
          "acts on does not change",
          "unless m_is_disabled" in monitoring)

    print()
    print("=" * 92)
    print("E  nothing else moves")
    print("=" * 92)
    src = (SCRIPTS / "patch_collectors" / "adobe_acrobat_community.py").read_text(encoding="utf-8")
    start = src.index("def collect_for_record(")
    body = src[start:src.index("\n    def ", start + 1) if "\n    def " in src[start:] else len(src)]
    check("E.1 the repair writes no evidence row and no record",
          not any(t in body for t in ("append_evidence_rows", "apply_consensus", "write_record")))
    check("E.2 the repair touches no count or verdict field",
          not any(t in body for t in ("update_report_count", "verdict", "evidence_state")))
    other = [r for r in live if not str(r.get("product_id") or "").startswith("adobe-acrobat")]
    check("E.3 the live store still holds every other product's telemetry",
          len({str(r.get("product_id")) for r in other}) >= 5,
          str(sorted({str(r.get("product_id")) for r in other})))
    # Emitting a row for a method this product is not authorised to write would be REFUSED by the
    # ownership gate, so the repair must stay inside the allow-list.
    from lib.collector_ownership import allowed_methods, allowed_source_types
    for edition in EDITIONS:
        check(f"E.4 {edition}: both retired method ids are still writable by this product",
              all(m in allowed_methods(edition) for m in RETIRED),
              str(sorted(allowed_methods(edition))))
        check(f"E.5 {edition}: both retired source types are still writable",
              {"adobe_community_bug_report", "reddit_community_report"}
              <= set(allowed_source_types(edition)))
    check("E.6 a disabled row survives normalization with every required field",
          all(normalize_method_health_row(h).get("status") == "disabled"
              for h in emit(EDITIONS[0], enabled=False)
              if str(h["method_id"]) in RETIRED))
    check("E.7 the notes a reader sees name no repository path",
          all(not any(t in str(h.get("notes") or "") for t in ("lib/", ".py", "auxsays/"))
              for h in emit(EDITIONS[0], enabled=False)))

    print()
    print("=" * 92)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if WARNINGS:
        print(f"Corpus warnings (clear as each record is walked; see warn()): {len(WARNINGS)}")
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
