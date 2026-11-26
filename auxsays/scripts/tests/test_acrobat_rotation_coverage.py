#!/usr/bin/env python3
"""R4-ACR: the Acrobat collector's rotating record coverage.

Offline and read-only: the corpus and the stored method-health rows are READ from the checkout, the
transport is a stub, and every write in Part E goes to a temporary directory.

  A  the order is a pure function of stored timestamps (never array position), missing/future stamps
     count as "never", and only the primary method's row is a check
  B  replay over the REAL corpus and the REAL stored rows: every record is reached within the computed
     bound, recent releases keep priority, and the newest-first walk this replaces strands the tail
  C  the collector: the cap holds, Adobe requests per run cannot rise, targeted runs are unchanged,
     telemetry lands on the rows and in the coverage event and can be rebuilt from the rows
  D  the acceptance gates are untouched: vendor announcements never count, Reader/Pro stay separate
  E  N+1: a second rotation run that moves on to other records loses no counted row

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_acrobat_rotation_coverage.py
"""
from __future__ import annotations

import json
import math
import random
import shutil
import sys
import tempfile
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from lib import acrobat_rotation as rot  # noqa: E402
from lib import monitoring_health as mh  # noqa: E402
from patch_collectors import adobe_acrobat_community as ac  # noqa: E402
from patch_collectors import base  # noqa: E402
from patch_collectors import runtime_budget as rb  # noqa: E402
from patch_collectors.base import PatchRecord  # noqa: E402

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []
P, R = ac.PRO_ID, ac.READER_ID
NOW = datetime(2026, 11, 26, 22, 30, tzinfo=timezone.utc)
# The collector stamps rows with utc_now(); pinned BEFORE NOW, as in production, where a run's stamp is
# always earlier than the next run's clock. Left real, a stamp after NOW reads as a future (never) check.
CAPTURED = "2026-11-26T22:00:00Z"


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        _ERRORS.append(label)
        print(f"  FAIL  {label}  {detail}")


def rec(pid: str, version: str, published: str) -> PatchRecord:
    return PatchRecord(pid, version, Path(f"{published[:10]}-{pid}-{version}.md"), published, "current", pid)


def hrow(pid: str, version: str, last_run: str, method: str = rot.PRIMARY_METHOD) -> dict:
    return {"product_id": pid, "update_version": version, "target_build": "", "method_id": method,
            "status": "no_results", "last_run": last_run}


def iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def versions(records) -> list[str]:
    return [r.update_version for r in records]


# --- A. pure ordering --------------------------------------------------------------------------
def part_a() -> None:
    print("\n-- A. order is a pure function of stored timestamps --")
    recs = [rec(P, f"26.001.{20000 + i}", f"2026-{1 + i // 3:02d}-{1 + (i % 3) * 9:02d}T00:00:00Z")
            for i in range(12)]
    rows = [hrow(P, r.update_version, "2026-11-20T00:00:00Z") for r in recs[:6]]
    rows += [hrow(P, recs[6].update_version, "2026-10-01T00:00:00Z")]
    order = rot.rotation_order(recs, rows, NOW)
    check("A1 every record exactly once", sorted(versions(order)) == sorted(versions(recs)) and len(order) == len(recs))
    newest4 = set(versions(sorted(recs, key=lambda r: r.update_published_at, reverse=True)[:4]))
    check("A2 the first RECENT_SLOTS picks come from the RECENT_WINDOW newest",
          set(versions(order[:rot.RECENT_SLOTS])) <= newest4, str(versions(order[:2])))
    never = {r.update_version for r in recs[7:]} - newest4
    fill = [v for v in versions(order[rot.RECENT_SLOTS:]) if v not in newest4]
    check("A3 never-checked records lead the fill, then the oldest check",
          set(fill[:len(never)]) == never and fill[len(never)] == recs[6].update_version, str(fill))
    tied = [v for v in fill if v not in never and v != recs[6].update_version]
    expect = versions(sorted([r for r in recs if r.update_version in tied],
                             key=lambda r: (r.update_published_at, r.update_version), reverse=True))
    check("A4 equal timestamps break on release date then version, newest first", tied == expect, str(tied))
    stable = True
    for seed in range(25):
        rnd = random.Random(seed)
        r2, h2 = recs[:], rows[:]
        rnd.shuffle(r2)
        rnd.shuffle(h2)
        stable = stable and versions(rot.rotation_order(r2, h2, NOW)) == versions(order)
    check("A5 array position never matters (25 shuffles of records and rows, one order)", stable)
    same_day = [rec(P, v, "2026-03-03T00:00:00Z") for v in ("26.001.30002", "26.001.30010", "26.001.30001")]
    check("A6 a release-date tie breaks on version, deterministically",
          versions(rot.rotation_order(same_day, [], NOW, window=0, slots=0))
          == ["26.001.30010", "26.001.30002", "26.001.30001"])
    bad = [hrow(P, recs[0].update_version, "not-a-date"), hrow(P, recs[1].update_version, "2027-01-01T00:00:00Z"),
           hrow(P, recs[2].update_version, "")]
    checked = rot.last_checked(P, bad, NOW)
    check("A7 unparseable, future and empty last_run all count as never checked",
          all(checked.get(k, rot.NEVER) == rot.NEVER for k in checked) and len(checked) <= 3)
    noise = [hrow(R, recs[8].update_version, "2026-11-25T00:00:00Z"),
             hrow(P, recs[9].update_version, "2026-11-25T00:00:00Z", method="adobe_community_search")]
    check("A8 another edition's row or a retired method's fresh `disabled` row is not a check",
          rot.last_checked(P, noise, NOW) == {})
    check("A9 the order is the same with and without those rows",
          versions(rot.rotation_order(recs, rows + noise, NOW)) == versions(order))
    check("A10 an empty corpus is an empty order", rot.rotation_order([], rows, NOW) == [])


# --- B. replay over the real corpus ------------------------------------------------------------
def simulate(records, rows, *, runs: int, per_run, start: datetime, step_hours: float, order_fn):
    """Run `runs` cycles; each attempts per_run(i) records of order_fn and stamps them."""
    rows = [dict(r) for r in rows]
    visits: dict[str, list[int]] = {r.update_version: [] for r in records}
    for i in range(runs):
        now = start + timedelta(hours=step_hours * i)
        order = order_fn(records, rows, now)[:per_run(i)]
        stamp = iso(now)
        for r in order:
            visits[r.update_version].append(i)
            rows.append(hrow(r.product_id, r.update_version, stamp))
    return visits, rows


def part_b() -> None:
    print("\n-- B. replay: real corpus + real stored rows at this checkout --")
    stored = base.load_method_health(base.METHOD_HEALTH_PATH)
    cap = rot.max_records_per_run({})
    for pid in (P, R):
        records = base.generated_records(pid)
        n = len(records)
        bound = rot.revisit_bound_runs(n, cap)
        check(f"B1 {pid}: a bound exists and equals ceil((N - W) / (C - R)) = {bound}",
              bound == math.ceil((n - rot.RECENT_WINDOW) / (cap - rot.RECENT_SLOTS)), f"n={n}")
        visits, _ = simulate(records, stored, runs=3 * bound, per_run=lambda i: cap, start=NOW,
                             step_hours=12, order_fn=rot.rotation_order)
        first = max(v[0] if v else 10 ** 6 for v in visits.values())
        check(f"B2 {pid}: every one of {n} records is attempted within {bound} runs (last first visit: run {first + 1})",
              first < bound)
        recent = set(versions(sorted(records, key=lambda r: (r.update_published_at, r.update_version),
                                     reverse=True)[:rot.RECENT_WINDOW]))
        gaps = []
        for version, seen in visits.items():
            # A record never visited waits the whole simulation (and more): its gap is runs + 1.
            seq = ([-1] + seen if version not in recent else seen) or [-1]
            if not seen:
                gaps.append((3 * bound + 1, version))
            gaps += [(b - a, version) for a, b in zip(seq, seq[1:])]
        worst = max((g for g, v in gaps if v not in recent), default=0)
        check(f"B3 {pid}: no record outside the recent window waits more than {bound} runs (worst {worst})",
              worst <= bound)
        recent_gap = max((g for g, v in gaps if v in recent), default=0)
        check(f"B4 {pid}: each recent release is revisited at least every "
              f"{math.ceil(rot.RECENT_WINDOW / rot.RECENT_SLOTS)} runs (worst {recent_gap})",
              recent_gap <= math.ceil(rot.RECENT_WINDOW / rot.RECENT_SLOTS)
              and all(len(visits[v]) >= (3 * bound) // 2 for v in recent))
        days = bound / 2.1
        check(f"B5 {pid}: at the delivered ~2.1 runs/day the bound is {days:.1f} days, inside the 14-day freshness window",
              days < mh.load_thresholds(base.ROOT / "_config.yml").max_age_days)
        # The measured per-run attempts (12 scheduled runs, 2026-11-20..26), capped: the deadline can
        # stop a run early, so the bound must also hold on the real throughput, with a little slack.
        series = {P: [11, 9, 9, 9, 16, 9, 11, 16, 13, 14, 5, 10],
                  R: [11, 9, 9, 9, 13, 9, 11, 13, 11, 11, 5, 10]}[pid]
        measured = [min(cap, a) for a in series]
        visits_m, _ = simulate(records, stored, runs=60, per_run=lambda i: measured[i % len(measured)],
                               start=NOW, step_hours=12, order_fn=rot.rotation_order)
        fill_mean = sum(measured) / len(measured) - rot.RECENT_SLOTS
        bound_m = math.ceil((n - rot.RECENT_WINDOW) / fill_mean)
        first_m = max(v[0] if v else 10 ** 6 for v in visits_m.values())
        check(f"B6 {pid}: on the measured throughput every record is reached by run {first_m + 1} "
              f"(computed {bound_m})", first_m < bound_m + 2)
        old, _ = simulate(records, stored, runs=bound, per_run=lambda i: measured[i % len(measured)],
                          start=NOW, step_hours=12, order_fn=lambda rs, _rows, _now: ac._newest_first(rs))
        reached_old = sum(1 for v in old.values() if v)
        check(f"B7 {pid}: the newest-first walk it replaces reaches only {reached_old} of {n} in the same {bound} runs",
              reached_old <= max(measured) and reached_old < n // 4)
        # Stale after one full bound of rotation at 12 h spacing, by the repo's own ladder.
        end = NOW + timedelta(hours=12 * (bound - 1))
        _v, rows_after = simulate(records, stored, runs=bound, per_run=lambda i: cap, start=NOW,
                                  step_hours=12, order_fn=rot.rotation_order)
        state = rot.coverage_state(records, rows_after, end, mh.load_thresholds(base.ROOT / "_config.yml"))
        before = rot.coverage_state(records, stored, NOW, mh.load_thresholds(base.ROOT / "_config.yml"))
        check(f"B8 {pid}: never-attempted {before['never_attempted_remaining']} -> {state['never_attempted_remaining']} "
              f"after {bound} runs", state["never_attempted_remaining"] == 0)
        print(f"        {pid}: stale {before['stale_remaining']} -> {state['stale_remaining']} "
              f"(ladder, now+{bound} runs at 12 h; reported, not asserted: release dates bound some)")


# --- C. the collector with a stub transport ---------------------------------------------------
class _Budget:
    def note_request(self):
        pass

    def collector_finalize_expired(self):
        return False

    def start_method(self, _m):
        pass


class _Resp:
    def __init__(self, payload):
        self.status, self.headers, self.body = 200, {"Content-Type": "application/json"}, json.dumps(payload).encode()


class _Ctx:
    def __init__(self, write=False, target_versions=None):
        self.write, self.since, self.max_pages = write, None, 1
        self.target_versions, self.budget = target_versions, _Budget()


TOPICS: dict[int, dict] = {}


def _fake_request(url, *, budget, endpoint_family="", headers=None, data=None, method=None, max_bytes=0):
    if "searchToken" in url:
        return _Resp({"client_id": "APP", "token": "T", "availableIndexes": ["idx"]})
    if "algolia.net" in url:
        query = json.loads(data.decode())["params"]
        base_id = abs(hash(query)) % 10 ** 6 * 10
        return _Resp({"hits": [{"id": base_id + i} for i in range(ac.MAX_ALGOLIA_HITS_PER_QUERY)]})
    if "getTopics" in url:
        import urllib.parse as up  # noqa: PLC0415
        ids = [int(v) for k, v in up.parse_qsl(up.urlsplit(url).query) if k == "topicIds[]"]
        return _Resp([TOPICS[i] for i in ids if i in TOPICS])
    raise AssertionError(f"unexpected url {url}")


class _Patched:
    """Swap module attributes for the duration of a block, restoring them on every exit."""

    def __init__(self, **swaps):
        self.swaps, self.saved = swaps, {}

    def __enter__(self):
        for dotted, value in self.swaps.items():
            mod, attr = dotted.split("__", 1)
            target = {"ac": ac, "rb": rb}[mod]
            self.saved[(target, attr)] = getattr(target, attr)
            setattr(target, attr, value)
        return self

    def __exit__(self, *exc):
        for (target, attr), value in self.saved.items():
            setattr(target, attr, value)
        return False


def synthetic(pid: str, n: int = 30) -> list[PatchRecord]:
    start = datetime(2024, 1, 5, tzinfo=timezone.utc)
    return [rec(pid, f"24.00{1 + i // 10}.{21000 + i}", iso(start + timedelta(days=21 * i))) for i in range(n)]


def part_c() -> None:
    print("\n-- C. collector: cap, request ceiling, targeted runs, telemetry --")
    records = synthetic(P)
    stored = [hrow(P, r.update_version, "2026-11-01T00:00:00Z") for r in records[:20]]
    expected = versions(rot.rotation_order(records, stored, NOW))
    with _Patched(ac__generated_records=lambda pid, tv=None, include_archived=False:
                  [r for r in records if not tv or r.update_version in tv],
                  ac__load_method_health=lambda path=None: list(stored), ac___now=lambda: NOW,
                  ac__utc_now=lambda: CAPTURED,
                  rb__bounded_request=_fake_request):
        collector = ac.AdobeAcrobatCollector(P)
        results = collector.collect(_Ctx())
        event = collector.last_coverage
        cap = rot.max_records_per_run()
        check("C1 an untargeted run attempts exactly the cap (10) of 30 records", len(results) == cap == 10)
        check("C2 ...in rotation order (recent picks, then never-checked fill)", [r["version"] for r in results]
              == expected[:cap], str([r["version"] for r in results]))
        primary = [row for r in results for row in r["method_health"] if row["method_id"] == rot.PRIMARY_METHOD]
        per_record = [row.get("requests") for row in primary]
        check("C3 each record costs the method's fixed maximum, 1 token + 3 Algolia + 1 getTopics = 5",
              per_record == [rot.MAX_REQUESTS_PER_RECORD] * cap
              and rot.MAX_REQUESTS_PER_RECORD == 1 + ac.MAX_ALGOLIA_QUERIES + 1, str(per_record))
        check("C4 requests per run <= cap x 5 = 50, below the newest-first walk's measured ~55 (Pro) a run",
              event["requests_total"] == sum(per_record) <= cap * rot.MAX_REQUESTS_PER_RECORD < round(11.0 * 5))
        check("C5 requests are counted per host (community.adobe.com 2/record, Algolia 3/record)",
              event["requests_by_host"] == {"app-dsn.algolia.net": 3 * cap, "community.adobe.com": 2 * cap},
              str(event["requests_by_host"]))
        check("C6 the cap cannot be raised by configuration (50 -> 10; junk and 0 -> 10; 3 -> 3)",
              [rot.max_records_per_run({rot.MAX_RECORDS_ENV: v}) for v in ("50", "abc", "0", "-4", "3")]
              == [10, 10, 10, 10, 3])
        check("C7 the coverage event reports the run",
              event["order"] == "rotation" and event["records_attempted"] == cap and event["records_total"] == 30
              and event["recent_attempted"] == rot.RECENT_SLOTS and event["successful_searches"] == cap
              and event["revisit_bound_runs"] == rot.revisit_bound_runs(30, cap), str(event))
        check("C8 never-attempted remaining drops by the records this run reached for the first time",
              event["never_attempted_remaining"] == 10 - sum(1 for v in expected[:cap]
                                                             if v not in {r["update_version"] for r in stored})
              and "coverage_state_error" not in event, str(event))
        rows_all = [row for r in results for row in r["method_health"]]
        check("C9 every primary row carries measured requests, duration_ms and rejection counts",
              all("requests" in row and "duration_ms" in row for row in primary)
              and all(isinstance(row.get("rejection_reasons", {}), dict) for row in primary))
        summary = rot.coverage_summary(P, stored + rows_all)
        check("C10 the run summary is rebuilt from the persisted rows alone",
              summary["records_attempted"] == cap and summary["requests"] == event["requests_total"]
              and summary["accepted_reports"] == event["accepted_reports"], str(summary))
        targeted = {r.update_version for r in records[:12]}
        collector2 = ac.AdobeAcrobatCollector(P)
        res2 = collector2.collect(_Ctx(target_versions=targeted))
        check("C11 a targeted dispatch is unchanged: newest-first, every named version, no cap",
              [r["version"] for r in res2] == versions(ac._newest_first([r for r in records if r.update_version in targeted]))
              and collector2.last_coverage["order"] == "targeted" and collector2.last_coverage["cap"] is None)
        check("C12 the request counter restarts with each invocation (no leak between Reader and Pro)",
              collector2.last_coverage["requests_total"] == 12 * rot.MAX_REQUESTS_PER_RECORD)
        check("C13 a rotation run never starts more records than the cap even with no deadline", len(results) <= cap)


# --- D + E. acceptance untouched; N+1 keeps counted rows --------------------------------------
def part_de() -> None:
    print("\n-- D. acceptance gates untouched / E. N+1 keeps counted rows --")
    records = synthetic(P, 24) + []
    target = records[-1]           # newest: picked by the first rotation run
    vendor = records[-2]
    TOPICS.clear()

    # Map the FIRST hit id of each record's first query to a topic.
    import urllib.parse as up  # noqa: PLC0415
    for record, title, body in (
            (target, "Acrobat Pro crash", f"Adobe Acrobat Pro {target.update_version} crashes on launch after the update."),
            (vendor, "Adobe Acrobat and Reader DC – June 2021 Update Release",
             f"Adobe Acrobat Pro {vendor.update_version} crashes on launch after the update.")):
        params = up.urlencode({"query": f'"{record.update_version}" "Acrobat Pro"', "hitsPerPage": ac.MAX_ALGOLIA_HITS_PER_QUERY})
        first_id = abs(hash(params)) % 10 ** 6 * 10
        TOPICS[first_id] = {"id": first_id, "url": f"https://community.adobe.com/questions-9/report-{first_id}",
                            "title": title, "firstPost": {"content": f"<p>{body}</p>",
                                                          "creationDate": "2026-03-01T00:00:00Z"}}
    tmp = Path(tempfile.mkdtemp(prefix="acr_rot_"))
    try:
        ev = tmp / "consensus_evidence.yml"
        shutil.copyfile(base.EVIDENCE_PATH, ev)
        before = [r for r in base.load_evidence(ev) if r.get("counted") is True]
        state = {"rows": []}

        def _append(rows, **kw):
            return base.append_evidence_rows(rows, ev, **kw)
        swaps = dict(ac__generated_records=lambda pid, tv=None, include_archived=False: list(records),
                     ac__load_method_health=lambda path=None: list(state["rows"]), ac___now=lambda: NOW,
                     ac__utc_now=lambda: CAPTURED,
                     rb__bounded_request=_fake_request, ac__append_evidence_rows=_append,
                     ac__apply_consensus_writeback=lambda pid, ver: False, ac__EVIDENCE_PATH=ev,
                     ac__TIER2_PATH=tmp / "t2.yml", ac__TIER3_PATH=tmp / "t3.yml")
        with _Patched(**swaps):
            run1 = ac.AdobeAcrobatCollector(P).collect(_Ctx(write=True))
            state["rows"] = [row for r in run1 for row in r["method_health"]]
            after1 = [r for r in base.load_evidence(ev) if r.get("counted") is True]
            run2 = ac.AdobeAcrobatCollector(P).collect(_Ctx(write=True))
            after2 = [r for r in base.load_evidence(ev) if r.get("counted") is True]
        by_ver = {r["version"]: r for r in run1}
        check("D1 a member report on the newest record is accepted through the rotation path",
              by_ver.get(target.update_version, {}).get("accepted_count") == 1, str(by_ver.get(target.update_version)))
        check("D2 a vendor release announcement is rejected as vendor_release_announcement, never counted",
              by_ver.get(vendor.update_version, {}).get("accepted_count") == 0
              and "vendor_release_announcement" in by_ver.get(vendor.update_version, {}).get("rejection_reasons", {}),
              str(by_ver.get(vendor.update_version)))
        new_rows = [r for r in after1 if r not in before]
        check("D3 the accepted row is Pro-only: no Reader row is written by a Pro run",
              len(new_rows) == 1 and new_rows[0]["product_id"] == P and all(r["product_id"] != R for r in new_rows))
        visited2 = {r["version"] for r in run2}
        check("E1 run 2 moved on: it did not revisit run 1's records",
              not (visited2 & {r["version"] for r in run1}), str(sorted(visited2)))

        def ident(r):
            return (r.get("product_id"), r.get("update_version"), r.get("source_url"))
        check("E2 N+1: every counted row before the runs is still counted after run 1 and run 2",
              {ident(r) for r in before} <= {ident(r) for r in after1} <= {ident(r) for r in after2},
              f"{len(before)} -> {len(after1)} -> {len(after2)}")
        check("E3 ...including the row run 1 added, on a record run 2 did not visit",
              target.update_version not in visited2 and ident(new_rows[0]) in {ident(r) for r in after2})
        check("E4 counted rows: before + 1 == after run 1 == after run 2 (nothing withdrawn, nothing doubled)",
              len(before) + 1 == len(after1) == len(after2), f"{len(before)} {len(after1)} {len(after2)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        TOPICS.clear()


def run() -> int:
    part_a()
    part_b()
    part_c()
    part_de()
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
