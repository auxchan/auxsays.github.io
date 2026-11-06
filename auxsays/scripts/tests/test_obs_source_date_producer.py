#!/usr/bin/env python3
"""The OBS evidence producer records the day each new report was posted (AUX-092).

AUX-090 dated the 282 stored OBS rows by hand, from each report's own public source, because
`collect_obs_reports.evidence_row` never carried the date the acceptance check already reads. This
suite pins the producer fix: every new OBS row carries `source_date`, the UTC day of that same
creation stamp (the GitHub issue's `created_at`; the forum opening post's own <time>), and nothing
else moves.

  P  the producer's day equals the day AUX-090 pinned for all 282 rows (audit/obs_report_dates.json)
  U  the derivation: UTC day of a zoned stamp; nothing for a missing, naive or invalid one
  R  the row: placement after captured_at, no key when there is no day, nothing else depends on it
  D  the release-date gate is unchanged (it still reads the stamp's own calendar day)
  C  FROZEN CORPUS GUARD: the old producer's outputs (golden_base.json, frozen from base 173cbb55)
     against this producer over the same candidates: identical decisions, stored rows (apart from
     source_date), counts, maturity and live decisions
  N  the only difference: the new source_date, equal to a day computed independently of the producer
  F  a forum thread page end to end: the opening post's own time, never a reply's or last activity
  W  the collector's write path: stored rows are never rewritten, a rediscovered report is not re-added
  B  the bare-script entry points still import and run (--help, as a subprocess)

Offline. Reads the live store and the AUX-090 pins; writes only temporary files.

    python auxsays/scripts/tests/test_obs_source_date_producer.py
    python auxsays/scripts/tests/test_obs_source_date_producer.py --freeze-golden PATH
        (records the CURRENT producer's corpus outputs; golden_base.json was made this way from a
        checkout of the base commit, i.e. by the producer before this change)
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
SCRIPTS = _REPO / "auxsays" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import collect_obs_reports as obs  # noqa: E402
from lib import live_eligibility, maturity, monitoring_health  # noqa: E402
from lib.patch_identity import patch_key  # noqa: E402
from lib.report_counts import counted_evidence_rows  # noqa: E402
from patch_collectors import obs as obs_lane  # noqa: E402
from patch_collectors import obs_forum_source as forum  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "obs_source_date"
CORPUS = FIXTURES / "corpus.json"
GOLDEN = FIXTURES / "golden_base.json"
PINS = SCRIPTS / "audit" / "obs_report_dates.json"
STORE = _REPO / "auxsays" / "_data" / "consensus_evidence.yml"
FIELD = "source_date"
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

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
        msg = f"  FAIL  {label}"
        if detail:
            msg += f"\n        {detail}"
        print(msg)
        _ERRORS.append(label)


def sha(value) -> str:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------------------------------
# The corpus harness. It runs whichever producer is importable (this checkout's) over the frozen
# candidates, through the same functions a natural run uses: `collect` for GitHub (search and fetch
# replaced by the fixture), `forum_candidates` + `evaluate_forum_candidates` for the forum, and the one
# dedupe/write authority `write_evidence` into a temporary store. Counting and maturity come from the
# canonical authorities. Everything it returns is free of the run clock.

def _variant_issue(base: dict, variant: dict, index: int) -> dict:
    """The base candidate under its own new identity, so that variants of one report never dedupe
    into each other; only created_at differs otherwise ("created_at": null removes the key)."""
    issue = copy.deepcopy(base["issue"])
    if variant["created_at"] is None:
        issue.pop("created_at", None)
    else:
        issue["created_at"] = variant["created_at"]
    if base["family"] == "github":
        number = 9_000_000 + index
        issue["number"] = number
        issue["html_url"] = f"https://github.com/obsproject/obs-studio/issues/{number}"
    else:
        thread = forum.thread_id(issue["thread_path"])
        new_id = f"9{index:05d}"
        issue["thread_path"] = issue["thread_path"].replace(f".{thread}/", f".{new_id}/")
        issue["source_url"] = issue["source_url"].replace(f".{thread}/", f".{new_id}/")
    return issue


def corpus_modes(corpus: dict) -> list[tuple[str, list[dict], bool]]:
    """(mode, candidates, release_date_known). `cross` evaluates every real candidate against every
    tracked version, as the forum pool is; the others evaluate against the candidate's own version."""
    real = corpus["candidates"]
    by_key = {c["key"]: c for c in real}
    variants = []
    for index, item in enumerate(corpus["variants"]):
        base = by_key[item["base"]]
        variants.append({"key": item["key"], "family": base["family"], "version": base["version"],
                         "expected_source_date": item["expected_source_date"],
                         "issue": _variant_issue(base, item, index)})
    return [("cross", real, True), ("nogate", real, False),
            ("variant", variants, True), ("variant_nogate", variants, False)]


def _emh(version: str, last_run: str) -> list[dict]:
    common = {"product_id": obs.PRODUCT_ID, "update_version": version, "target_build": "",
              "last_run": last_run}
    return [dict(common, method_id="github_issues", source_type="github_issue", status="success"),
            dict(common, method_id="obs_forum", source_type=forum.SOURCE_TYPE, status="success"),
            dict(common, method_id="known_watchlist", source_type="curated_watchlist", status="disabled")]


def run_corpus(corpus: dict) -> dict:
    captured = corpus["captured_at"]
    now = datetime.strptime(corpus["now"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    last_run = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    thresholds = monitoring_health.Thresholds(max_age_days=14, min_healthy_families=2)
    releases = corpus["release_dates"]
    versions = sorted(releases)
    out: dict = {"decisions": [], "stored": {}, "counts": {}, "maturity": {}, "texts": {}, "expected": {}}
    saved = (obs.EVIDENCE_PATH, obs.search_issues, obs.fetch_issue, obs.utc_now)
    try:
        obs.utc_now = lambda: captured
        obs.fetch_issue = lambda item: item
        for mode, cands, gated in corpus_modes(corpus):
            with tempfile.TemporaryDirectory() as tmp:
                obs.EVIDENCE_PATH = Path(tmp) / "consensus_evidence.yml"
                expected_by_row: dict[tuple[str, str], dict] = {}
                for version in versions:
                    mine = cands if mode == "cross" else [c for c in cands if c["version"] == version]
                    if not mine:
                        continue
                    release = obs.parse_date(releases[version]) if gated else None
                    gh = [c for c in mine if c["family"] == "github"]
                    fo = [c for c in mine if c["family"] == "forum"]
                    for cand in gh:
                        basis, reason = obs.evaluate_issue(cand["issue"], version, release)
                        out["decisions"].append([mode, version, cand["key"], basis, reason])
                    obs.search_issues = (lambda batch: (lambda _v, _s, _p: [c["issue"] for c in batch]))(gh)
                    accepted, _rejected = obs.collect(version, None, 1, release)
                    pool = [c["issue"] for c in fo]
                    narrowed = obs_lane.forum_candidates(version, pool)
                    for cand in fo:
                        if not any(p is cand["issue"] for p in narrowed):
                            out["decisions"].append([mode, version, cand["key"], None, "not_a_candidate"])
                            continue
                        basis, reason = obs.evaluate_issue(cand["issue"], version, release)
                        if not reason and forum.row_identity(version, cand["issue"], obs.slug) is None:
                            basis, reason = None, "unresolvable_thread_identity"
                        out["decisions"].append([mode, version, cand["key"], basis, reason])
                    f_acc, _f_rej = obs_lane.evaluate_forum_candidates(version, release, narrowed, captured)
                    for cand in gh + fo:
                        url = cand["issue"].get("html_url") or cand["issue"].get("source_url")
                        expected_by_row.setdefault((version, url), cand)
                    obs.write_evidence(accepted + f_acc)
                stored = obs.parse_existing_rows(obs.EVIDENCE_PATH)
                text = obs.EVIDENCE_PATH.read_text(encoding="utf-8") if obs.EVIDENCE_PATH.exists() else ""
            out["texts"][mode] = text
            listing = []
            for row in stored:
                bare = {k: v for k, v in row.items() if k != FIELD}
                listing.append([row["update_version"], row["id"], sha(bare), [k for k in row if k != FIELD]])
                out["expected"][f"{mode}|{row['update_version']}|{row['id']}"] = (
                    expected_by_row.get((row["update_version"], row["source_url"])), row)
            out["stored"][mode] = listing
            groups = counted_evidence_rows(stored, windows_targets={})
            exclusive = live_eligibility.exclusive_url_counts(groups)
            for version in versions:
                key = patch_key(obs.PRODUCT_ID, version, "")
                rows = groups.get(key, [])
                record = {"product_id": obs.PRODUCT_ID, "update_version": version, "target_build": "",
                          "update_published_at": releases[version] if gated else None}
                decision = live_eligibility.evaluate(record, groups, emh_rows=_emh(version, last_run), now=now,
                                                     thresholds=thresholds, exclusive=exclusive)
                out["counts"][f"{mode}|{version}"] = obs.counted_evidence_count(stored, version)
                out["maturity"][f"{mode}|{version}"] = {
                    "rows": len(rows), "exclusive": int(exclusive.get(key, 0)),
                    "maturity": dataclasses.asdict(maturity.maturity_for(len(rows), live=decision.live)),
                    "live": decision.live, "reasons": list(decision.reasons)}
    finally:
        obs.EVIDENCE_PATH, obs.search_issues, obs.fetch_issue, obs.utc_now = saved
    return out


def golden_of(result: dict) -> dict:
    accepted: dict[str, list] = {}
    reasons: dict[str, list] = {}
    for mode, version, key, basis, reason in result["decisions"]:
        if reason:
            reasons.setdefault(reason, []).append(f"{mode}|{version}|{key}")
        else:
            accepted.setdefault(f"{mode}|{version}", []).append([key, basis])
    return {
        "decisions_sha256": sha(result["decisions"]),
        "decisions_total": len(result["decisions"]),
        "accepted": {g: {"n": len(k), "sha256": sha(k)} for g, k in sorted(accepted.items())},
        "rejected_by_reason": {r: {"n": len(k), "sha256": sha(sorted(k))} for r, k in sorted(reasons.items())},
        # One line per stored row: its identity and a 64-bit digest of every field but source_date.
        "stored": {mode: [f"{v}|{i}|{s[:16]}" for v, i, s, _k in rows] for mode, rows in result["stored"].items()},
        "key_orders": sorted({json.dumps(k) for rows in result["stored"].values() for _v, _i, _s, k in rows}),
        "counts": result["counts"],
        "maturity": result["maturity"],
    }


# ---------------------------------------------------------------------------------------------------

def _forum_page(open_stamp: str, reply_stamp: str, activity_stamp: str, version: str) -> str:
    return f"""<!doctype html><html><body>
<h1 class="p-title-value">OBS crashes when I start a recording</h1>
<article class="message message--post js-post" data-author="opener" data-content="post-7001" id="js-post-7001">
  <header><time class="u-dt" datetime="{open_stamp}">opened</time></header>
  <div class="bbWrapper">Since I updated to {version} OBS crashes every time I start a recording.</div>
</article>
<article class="message message--post js-post" data-author="replier" data-content="post-7002" id="js-post-7002">
  <header><time class="u-dt" datetime="{reply_stamp}">replied</time></header>
  <div class="bbWrapper">Same crash here on {version}.</div>
</article>
<time class="u-dt" datetime="{activity_stamp}">last activity</time>
</body></html>"""


def run() -> int:  # noqa: PLR0915
    live_before = STORE.read_bytes() if STORE.exists() else b""
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))

    print("P the producer's day equals every day AUX-090 pinned")
    pins = json.loads(PINS.read_text(encoding="utf-8"))["entries"]
    produced = [obs.report_source_day({"created_at": e["source"]["created_at"]}) for e in pins]
    check("P1 282 pinned rows, each with its served creation stamp", len(pins) == 282, str(len(pins)))
    mismatched = [e["id"] for e, day in zip(pins, produced) if day != e["source_date"]]
    check("P2 report_source_day(served stamp) == the pinned source_date for every pin", not mismatched,
          str(mismatched[:5]))
    local_differs = [e["id"] for e in pins
                     if obs.parse_date(e["source"]["created_at"]).isoformat() != e["source_date"]]
    check("P3 exactly the 3 forum posts made just after local midnight have a gate day != UTC day",
          len(local_differs) == 3 and all("forum" in i for i in local_differs), str(local_differs))
    gh_pins = [e for e in pins if e["source"]["kind"] == "github_issue"]
    check("P4 every GitHub pin: the UTC day is the gate's own day (GitHub serves UTC)",
          len(gh_pins) == 254 and all(obs.report_source_day({"created_at": e["source"]["created_at"]})
                                      == e["source"]["created_at"][:10] for e in gh_pins), str(len(gh_pins)))

    print("U the derivation")
    day = obs.report_source_day
    cases = [
        ("U1 GitHub 'Z' stamp -> its day", {"created_at": "2026-10-06T15:01:08Z"}, "2026-10-06"),
        ("U2 forum +0100 just after local midnight -> the UTC day before",
         {"created_at": "2026-08-14T00:20:00+0100"}, "2026-08-13"),
        ("U3 -0400 late evening -> the next UTC day", {"created_at": "2026-08-14T22:30:00-0400"}, "2026-08-15"),
        ("U4 colon offset +01:00 is read", {"created_at": "2026-08-15T00:40:00+01:00"}, "2026-08-14"),
        ("U5 fractional seconds are read", {"created_at": "2026-08-15T09:00:00.250Z"}, "2026-08-15"),
        ("U6 a naive stamp has no UTC day", {"created_at": "2026-08-15T09:00:00"}, None),
        ("U7 a bare day has no UTC day", {"created_at": "2026-08-15"}, None),
        ("U8 an empty stamp", {"created_at": ""}, None),
        ("U9 no created_at key", {}, None),
        ("U10 an impossible calendar day", {"created_at": "2026-02-30T10:00:00Z"}, None),
        ("U11 surrounding text is not a stamp", {"created_at": "on 2026-08-15T09:00:00Z"}, None),
        ("U12 updated_at and closed_at are never read",
         {"updated_at": "2026-09-01T00:00:00Z", "closed_at": "2026-09-02T00:00:00Z"}, None),
        ("U13 created_at wins over a later updated_at",
         {"created_at": "2026-08-15T09:00:00Z", "updated_at": "2026-09-30T00:00:00Z"}, "2026-08-15"),
    ]
    for label, issue, want in cases:
        got = day(issue)
        check(label, got == want, f"got {got!r}, want {want!r}")
    check("U14 the day is a plain 'YYYY-MM-DD' str",
          isinstance(day({"created_at": "2026-10-06T15:01:08Z"}), str)
          and DAY_RE.match(day({"created_at": "2026-10-06T15:01:08Z"})) is not None)

    print("R the row")
    ver = "32.2.2"
    issue = {"number": 4242, "title": "OBS crashes on startup", "body": f"Since {ver} OBS crashes on startup.",
             "labels": [], "created_at": "2026-09-01T23:30:00Z", "updated_at": "2026-10-20T08:00:00Z",
             "html_url": "https://github.com/obsproject/obs-studio/issues/4242"}
    row = obs.evidence_row(issue, ver, "body", "2026-11-06T12:00:00Z")
    keys = list(row)
    check("R1 the row carries the day the issue was opened", row.get(FIELD) == "2026-09-01", str(row.get(FIELD)))
    check("R2 source_date sits directly after captured_at",
          FIELD in keys and keys.index(FIELD) == keys.index("captured_at") + 1, str(keys))
    check("R3 captured_at is the collection time, untouched", row["captured_at"] == "2026-11-06T12:00:00Z")
    undated = dict(issue)
    undated.pop("created_at")
    bare = obs.evidence_row(undated, ver, "body", "2026-11-06T12:00:00Z")
    check("R4 no day -> no source_date key at all (not null)", FIELD not in bare, str(list(bare)))
    check("R5 nothing else in the row depends on the date",
          {k: v for k, v in row.items() if k != FIELD} == bare)
    naive = dict(issue, created_at="2026-09-01T23:30:00")
    check("R6 a naive stamp is not guessed into a day", FIELD not in obs.evidence_row(naive, ver, "body", "x"))
    post = {"title": "Crash", "body": f"{ver} crashes", "labels": [], "created_at": "2026-09-02T00:20:00+0100",
            "source_url": "https://obsproject.com/forum/threads/crash.196001/",
            "thread_path": "/forum/threads/crash.196001/"}
    frow = obs.evidence_row(post, ver, "body", "2026-11-06T12:00:00Z",
                            identity=forum.row_identity(ver, post, obs.slug))
    check("R7 a forum row carries the UTC day of the opening post's stamp", frow.get(FIELD) == "2026-09-01",
          str(frow.get(FIELD)))
    check("R8 the forum row keeps its own identity", frow["id"] == "obs-studio-32-2-2-obs-forum-thread-196001"
          and frow["source_type"] == forum.SOURCE_TYPE, frow["id"])
    check("R9 the producer emits only the store's format for the day",
          obs.normalize_row(row).get(FIELD) == "2026-09-01" and FIELD not in obs.normalize_row(bare))

    print("D the release-date gate is unchanged")
    release = obs.parse_date("2026-09-02")
    check("D1 a report before the release is still refused",
          obs.release_date_gate({"created_at": "2026-09-01T23:59:59Z"}, release) == "before_release_date")
    check("D2 an undated report is still refused when the release is known",
          obs.release_date_gate({}, release) == "missing_source_date")
    check("D3 the gate is still inactive when the release date is unknown",
          obs.release_date_gate({}, None) is None)
    check("D4 the gate still reads the stamp's own day: a forum post at 00:20+0100 on release day passes",
          obs.release_date_gate(post, release) is None)
    check("D5 ...and that same report stores the UTC day, the evening before (AUX-090 semantics)",
          frow.get(FIELD) == "2026-09-01" and obs.issue_source_date(post).isoformat() == "2026-09-02")
    check("D6 a naive stamp still passes the gate on its own day (and stores no day)",
          obs.release_date_gate({"created_at": "2026-09-02T10:00:00"}, release) is None)

    print("C frozen corpus guard: the old producer against this one")
    result = run_corpus(corpus)
    mine = golden_of(result)
    check("C1 every decision identical (mode, version, candidate, basis, reason)",
          mine["decisions_sha256"] == golden["decisions_sha256"]
          and mine["decisions_total"] == golden["decisions_total"],
          f"{mine['decisions_total']} vs {golden['decisions_total']}")
    check("C2 the accepted set per mode and version is identical", mine["accepted"] == golden["accepted"],
          str([g for g in sorted(set(mine["accepted"]) | set(golden["accepted"]))
               if mine["accepted"].get(g) != golden["accepted"].get(g)][:5]))
    check("C3 the rejected set per reason is identical",
          mine["rejected_by_reason"] == golden["rejected_by_reason"])

    def ids(stored: dict) -> dict:
        return {m: [r.rsplit("|", 1)[0] for r in rows] for m, rows in stored.items()}

    check("C4 the stored rows are the same rows in the same order", ids(mine["stored"]) == ids(golden["stored"]))
    differ = [f"{m}: {a} != {b}" for m in golden["stored"]
              for a, b in zip(mine["stored"].get(m, []), golden["stored"][m]) if a != b]
    check("C5 every stored row is identical apart from source_date", mine["stored"] == golden["stored"],
          "; ".join(differ[:3]))
    check("C6 field order identical apart from source_date", mine["key_orders"] == golden["key_orders"],
          str(mine["key_orders"]))
    check("C7 counts identical for every mode and version", mine["counts"] == golden["counts"])
    check("C8 maturity, exclusivity and live decisions identical", mine["maturity"] == golden["maturity"])
    n_acc = sum(v["n"] for v in mine["accepted"].values())
    check("C9 non-vacuous: the corpus accepts reports", n_acc >= 300, str(n_acc))
    need = {"before_release_date", "missing_source_date", "missing_exact_version", "not_a_candidate"}
    check("C10 non-vacuous: the gate and the matcher both refuse reports in this corpus",
          need <= set(mine["rejected_by_reason"]), str(sorted(mine["rejected_by_reason"])))
    lives = sorted(k for k, m in mine["maturity"].items() if m["live"])
    check("C11 non-vacuous: at least one identity is decided live by both producers", bool(lives), str(lives))
    check("C12 the golden is the OLD producer's: no stored row it describes carried a source_date",
          all(FIELD not in json.loads(k) for k in golden["key_orders"]))

    print("N the only difference: the new day, from the report itself")
    dated = undated_ok = 0
    wrong: list[str] = []
    for label, (cand, row) in result["expected"].items():
        want = cand["expected_source_date"] if cand else "?"
        if want == "?":
            wrong.append(f"{label}: no candidate")
        elif want is None:
            if FIELD in row:
                wrong.append(f"{label}: has {row[FIELD]!r}, expected none")
            else:
                undated_ok += 1
        elif row.get(FIELD) != want:
            wrong.append(f"{label}: {row.get(FIELD)!r} != {want!r}")
        else:
            dated += 1
    check("N1 every stored row carries exactly the independently computed day (or none)", not wrong,
          "; ".join(wrong[:4]))
    check("N2 non-vacuous: dated rows and rows that stay undated both occur", dated >= 300 and undated_ok >= 10,
          f"dated={dated} undated={undated_ok}")
    pairs = [(c, r) for c, r in result["expected"].values() if c]
    check("N3 the day sits directly after captured_at in every dated row",
          all(list(r).index(FIELD) == list(r).index("captured_at") + 1 for _c, r in pairs if FIELD in r))
    check("N4 the day is never the capture day",
          all(r[FIELD] != r["captured_at"][:10] for _c, r in pairs if FIELD in r))
    activity = [r for c, r in pairs if FIELD in r and c["issue"].get("updated_at")
                and c["issue"]["updated_at"][:10] != r[FIELD]]
    check("N5 non-vacuous: >= 50 dated rows whose issue was last active on another day", len(activity) >= 50,
          str(len(activity)))
    before_gate_day = [r for c, r in pairs if FIELD in r and obs.parse_date(c["issue"].get("created_at"))
                       and r[FIELD] != obs.parse_date(c["issue"].get("created_at")).isoformat()]
    check("N6 non-vacuous: accepted reports whose UTC day differs from the gate's own day occur",
          len(before_gate_day) >= 5, str(len(before_gate_day)))
    yaml_shape = re.compile(r"\n  captured_at: '[^'\n]+'\n  source_date: '\d{4}-\d{2}-\d{2}'\n")
    text = result["texts"]["cross"]
    n_cross = len(result["stored"]["cross"])
    check("N7 the store writes the day quoted, on the line after captured_at",
          n_cross > 0 and len(yaml_shape.findall(text)) == n_cross, f"{len(yaml_shape.findall(text))}/{n_cross}")
    print(f"  info  decisions={mine['decisions_total']} accepted={n_acc} stored="
          f"{ {m: len(r) for m, r in mine['stored'].items()} } dated={dated} undated={undated_ok} "
          f"last_active_elsewhere={len(activity)} utc_day_not_gate_day={len(before_gate_day)} live={lives}")

    print("F a forum thread page end to end")
    page = _forum_page("2026-09-02T00:20:00+0100", "2026-09-20T12:00:00+0100", "2026-10-01T09:00:00+0100", ver)
    opening = forum.parse_opening_post(page)
    opening["source_url"] = "https://obsproject.com/forum/threads/crash.196002/"
    opening["thread_path"] = "/forum/threads/crash.196002/"
    acc, rej = obs_lane.evaluate_forum_candidates(ver, release, obs_lane.forum_candidates(ver, [opening]),
                                                  "2026-11-06T12:00:00Z")
    check("F1 the opening post is accepted against its release (gate on its own day)", len(acc) == 1 and not rej,
          str(rej))
    check("F2 its row carries the opening post's UTC day, not the reply's or the page's last activity",
          bool(acc) and acc[0].get(FIELD) == "2026-09-01", str(acc and acc[0].get(FIELD)))
    late = forum.parse_opening_post(_forum_page("2026-09-03T10:00:00+0100", "2026-08-01T10:00:00+0100",
                                                "2026-08-01T10:00:00+0100", ver))
    late.update(source_url="https://obsproject.com/forum/threads/crash.196003/",
                thread_path="/forum/threads/crash.196003/")
    acc2, _ = obs_lane.evaluate_forum_candidates(ver, release, [late], "2026-11-06T12:00:00Z")
    check("F3 an earlier reply time never dates the report either", bool(acc2) and acc2[0].get(FIELD) == "2026-09-03",
          str(acc2 and acc2[0].get(FIELD)))

    print("W the collector's write path")
    orig = obs.EVIDENCE_PATH
    live_text = STORE.read_text(encoding="utf-8")
    live_hashes = _block_hashes(live_text)
    pins_present = [e for e in pins if e["block_sha256_after"] in live_hashes]
    new_rows = [r for _w, r in result["expected"].values() if FIELD in r][:5]
    with tempfile.TemporaryDirectory() as tmp:
        try:
            obs.EVIDENCE_PATH = Path(tmp) / "consensus_evidence.yml"
            obs.EVIDENCE_PATH.write_text(live_text, encoding="utf-8", newline="")
            before_rows = obs.parse_existing_rows(obs.EVIDENCE_PATH)
            fresh = [dict(r, id=r["id"] + "-w", source_url=r["source_url"] + "?w") for r in new_rows]
            added, total, _ = obs.write_evidence(fresh)
            after_text = obs.EVIDENCE_PATH.read_text(encoding="utf-8")
            after_rows = obs.parse_existing_rows(obs.EVIDENCE_PATH)
            check("W1 new rows are appended", added == len(fresh) == 5 and total == len(before_rows) + 5,
                  f"added={added} total={total}")
            check("W2 every stored row is unchanged and in place after the collector's full rewrite",
                  after_rows[:len(before_rows)] == before_rows)
            after_hashes = _block_hashes(after_text)
            check("W3 every AUX-090 dated block in the store survives the rewrite byte for byte",
                  len(pins_present) >= 250 and all(e["block_sha256_after"] in after_hashes for e in pins_present),
                  f"{len(pins_present)} present")
            check("W4 the appended rows carry their day on the line after captured_at",
                  len(yaml_shape.findall(after_text)) >= len(yaml_shape.findall(live_text)) + 5)
            # A stored row with no day (as the rows stored before this change are), then the same reports
            # found again by a run whose producer now dates them: nothing is re-added and nothing is rewritten.
            undated_issue = dict(issue, number=4243, html_url="https://github.com/obsproject/obs-studio/issues/4243")
            undated_issue.pop("created_at")
            seeded = obs.evidence_row(undated_issue, ver, "body", "2026-11-06T12:00:00Z")
            obs.write_evidence([seeded])
            reseen_text = obs.EVIDENCE_PATH.read_text(encoding="utf-8")
            stored_obs = [r for r in obs.parse_existing_rows(obs.EVIDENCE_PATH)
                          if r.get("product_id") == obs.PRODUCT_ID]
            again = [dict(r, **{FIELD: "2026-01-01"}) for r in stored_obs[:3]]
            again.append(obs.evidence_row(dict(undated_issue, created_at="2026-09-03T08:00:00Z"), ver, "body",
                                          "2026-11-07T12:00:00Z"))
            added2, _t2, _ = obs.write_evidence(again)
            check("W5 a rediscovered stored report is not re-added and no stored row gains a day",
                  FIELD not in seeded and added2 == 0
                  and obs.EVIDENCE_PATH.read_text(encoding="utf-8") == reseen_text, f"added={added2}")
        finally:
            obs.EVIDENCE_PATH = orig
    print(f"  info  AUX-090 pins present in the live store={len(pins_present)}")
    check("W6 the live store is untouched by this suite", (STORE.read_bytes() if STORE.exists() else b"") == live_before)

    print("B the bare-script entry points")
    for label, script in (("B1 collect_obs_reports.py --help", "collect_obs_reports.py"),
                          ("B2 run_patch_evidence_collection.py --help", "run_patch_evidence_collection.py")):
        proc = subprocess.run([sys.executable, str(SCRIPTS / script), "--help"], cwd=str(_REPO),
                              capture_output=True, text=True, timeout=120)
        check(label, proc.returncode == 0 and "usage" in proc.stdout.lower(), (proc.stderr or "")[-300:])

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed tests:")
        for err in _ERRORS:
            print(f"  - {err}")
    return 0 if _FAIL == 0 else 1


def _block_hashes(text: str) -> set[str]:
    """sha256 of every stored row block, split exactly as AUX-090 hashed its pins."""
    import withdraw_windows_identity_not_the_subject_rows as aux072  # noqa: PLC0415
    return {aux072.sha(text[lo:hi]) for lo, hi, _row in aux072.store_blocks(text)}


def freeze(path: Path) -> int:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    golden = golden_of(run_corpus(corpus))
    golden = {
        "schema": "auxsays-obs-source-date-golden/1",
        "purpose": ("The OLD OBS producer's outputs over corpus.json, recorded by running this suite's "
                    "--freeze-golden in a checkout of the base commit, before the producer stored source_date. "
                    "The suite compares this producer against it."),
        "producer_sha256": hashlib.sha256((SCRIPTS / "collect_obs_reports.py").read_bytes()).hexdigest(),
        **golden,
    }
    lines = ["{"]
    for n, (key, value) in enumerate(golden.items()):
        tail = "," if n < len(golden) - 1 else ""
        if key == "stored":
            lines.append('  "stored": {')
            for m, (mode, rows) in enumerate(value.items()):
                body = ",\n".join("      " + json.dumps(r) for r in rows)
                lines.append(f'    "{mode}": [\n{body}\n    ]' + ("," if m < len(value) - 1 else ""))
            lines.append("  }" + tail)
        else:
            lines.append(f"  {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)}{tail}")
    lines.append("}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    json.loads(path.read_text(encoding="utf-8"))
    print(f"froze {golden['decisions_total']} decisions to {path}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--freeze-golden":
        sys.exit(freeze(Path(sys.argv[2])))
    try:
        sys.exit(run())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        print(f"Results: {_PASS}/{_PASS + _FAIL + 1} passed, {_FAIL + 1} failed")
        sys.exit(1)
