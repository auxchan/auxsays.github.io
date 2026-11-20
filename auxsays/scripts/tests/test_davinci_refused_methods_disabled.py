#!/usr/bin/env python3
"""AUX-117 (G67): DaVinci's two Blackmagic-forum methods are switched off, truthfully.

THE DEFECT. `known_watchlist` and `vendor_forum_search` read only the Blackmagic Design forum, and the
forum refuses automated requests. Over every method-health row committed from 2026-08-01 to
2026-11-19 (333 passes, 6,725 executions of each), vendor_forum_search was blocked 6,725 times out of
6,725 and known_watchlist never had a Blackmagic probe answer. About 161 refused requests a pass. And
their `blocked` rows hid a real shortfall: DaVinci has one working community source (Creative COW),
but the card read MONITORING DEGRADED, because rule 7 (degraded) comes before rule 8 (coverage).

WHAT THIS SUITE PINS.
  A  the collector writes a genuine `disabled` row for both methods and NEVER calls their adapters
     (unlike the web_search branch, which labels its row disabled after calling its adapter); the row
     is built by its own function, not `method_status`; the validator accepts it without any change to
     its rules; the other three methods are untouched.
  B  the migration of the frozen rows of the 100 archived records (which no routine run visits) is
     zero-network and hash-scoped: exactly the in-scope rows change, only status / blocked_reason /
     notes move inside them, every other byte of every file in the tree is identical, a second run
     changes nothing, and an unexpected row shape is refused with nothing written.
  C  no refresh or freshness field moves: every migrated row keeps its last_run, no generated record
     is touched, and each archived page's newest usable run (the ladder's freshness input) is unchanged.
  D  the page states equal the list FROZEN BEFORE THE CODE CHANGE, version by version, over the base
     commit's real rows: the migration alone changes no page state; after the collector's first pass
     100 COLLECTION STALE stay STALE, 20 MONITORING DEGRADED become INSUFFICIENT COVERAGE and 3
     COLLECTION BLOCKED become MONITORING DEGRADED. INSUFFICIENT COVERAGE is visible (one healthy
     family against a floor of two), no page reads healthy, and the product-level state is unchanged.
     A counterfactual proves the row builder matters: through `method_status` the same rows would make
     20 pages read healthy.

Fixture: tests/fixtures/davinci_refused_methods/base_snapshot.json, the DaVinci rows and records of
base commit b5add67a and the expected states, frozen before the change. Thresholds are the published
values at freeze time (14 days, 2 families), held fixed so this suite tests the change, not the config.

Offline and deterministic: sockets and DNS are refused and counted; temp dirs only; the repository is
never written. Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_davinci_refused_methods_disabled.py
"""
from __future__ import annotations

import ast
import contextlib
import copy
import hashlib
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # auxsays/
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

NET = [0]


class _NoNetSocket(socket.socket):
    def connect(self, *args, **kwargs):          # noqa: D102
        NET[0] += 1
        raise OSError("network refused by test_davinci_refused_methods_disabled")

    def connect_ex(self, *args, **kwargs):       # noqa: D102
        NET[0] += 1
        raise OSError("network refused by test_davinci_refused_methods_disabled")


def _no_dns(*args, **kwargs):
    NET[0] += 1
    raise OSError("DNS refused by test_davinci_refused_methods_disabled")


socket.socket = _NoNetSocket                     # type: ignore[misc]
socket.getaddrinfo = _no_dns                     # type: ignore[assignment]

import yaml                                                              # noqa: E402

import build_coverage_projection as cov                                  # noqa: E402
import migrate_davinci_refused_method_health as mig                      # noqa: E402
from lib import collector_ownership as co                                # noqa: E402
from lib import monitoring_health as mh                                  # noqa: E402
from lib.reddit_access_policy import AUTHORIZATION_ENV                   # noqa: E402
from patch_collectors import base                                        # noqa: E402
from patch_collectors import davinci as dv                               # noqa: E402
from validate_evidence_method_health import validate                     # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "davinci_refused_methods" / "base_snapshot.json"
MIGRATION = SCRIPTS / "migrate_davinci_refused_method_health.py"
TWO = ("known_watchlist", "vendor_forum_search")
THRESHOLDS = mh.Thresholds(max_age_days=14, min_healthy_families=2)
PASS_AT = "2026-11-20T07:30:00Z"        # the simulated first pass: after every release, before `now`

PASS = FAIL = 0
FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


def warn(label: str, ok: bool, detail: str = "") -> None:
    """A corpus observation, not a gate (the live store moves with every production run)."""
    print(f"  {'ok  ' if ok else 'WARN'}  {label}" + ("" if ok else f"  [{detail}]"))


# ---- fixture ---------------------------------------------------------------------------------------
DOC = json.loads(FIXTURE.read_text(encoding="utf-8"))
NOW = datetime.fromisoformat(DOC["now"].replace("Z", "+00:00"))
RECORDS = [dict(zip(DOC["record_fields"], r)) for r in DOC["records"]]
ARCHIVED = {r["update_version"] for r in RECORDS if r["update_status"] == "archived"}
CURRENT = [r for r in RECORDS if r["update_status"] != "archived"]
EXPECTED = DOC["expected"]


def fixture_rows() -> list[dict]:
    """The base commit's DaVinci rows as full store rows (notes are not part of the fixture)."""
    out = []
    for values in DOC["rows"]:
        r = dict(zip(DOC["row_fields"], values))
        out.append(base.method_health_row(
            product_id=dv.PRODUCT_ID, update_version=r["update_version"], method_id=r["method_id"],
            source_type=r["source_type"], status=r["status"], candidates_found=0, accepted_reports=0,
            rejected_reports=0, blocked_reason=r["blocked_reason"], last_run=r["last_run"],
            notes=f"fixture note for {r['method_id']}"))
    return out


def ladder_states(rows: list[dict]) -> dict[str, str]:
    out = {}
    for rec in RECORDS:
        ident = {"product_id": dv.PRODUCT_ID, "update_version": rec["update_version"], "target_build": ""}
        out[rec["update_version"]] = mh.ladder(mh.rows_for(ident, rows), published_at=rec["update_published_at"],
                                               report_count=rec["update_report_count"], now=NOW,
                                               thresholds=THRESHOLDS)
    return out


def fresh_healthy_families(rows: list[dict], version: str, published_at: str) -> set[str]:
    now_s, pub_s = NOW.timestamp(), (mh._epoch(published_at) or 0)
    fams = set()
    for row in mh.rows_for({"product_id": dv.PRODUCT_ID, "update_version": version, "target_build": ""}, rows):
        run = mh._epoch(row.get("last_run"))
        if str(row.get("status")) in mh.HEALTHY_STATUSES and run and pub_s <= run <= now_s \
                and now_s - run <= THRESHOLDS.max_age_days * 86400:
            fams.add(mh._family(row))
    return fams


def write_store(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    base.write_method_health_file(rows, path)


def write_record(directory: Path, product_id: str, version: str, status: str, published: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    front = yaml.safe_dump({"layout": "aux-update", "update_entry": True, "product_id": product_id,
                            "update_version": version, "update_status": status,
                            "update_published_at": published, "evidence_last_checked": "2026-05-01T00:00:00Z",
                            "record_last_updated": "2026-05-01T00:00:00Z"}, sort_keys=False)
    (directory / f"{published[:10]}-{product_id}-{version.replace('.', '-')}.md").write_text(
        f"---\n{front}---\nbody\n", encoding="utf-8")


def tree_digest(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def record(version: str = "21.2", status: str = "current", published: str = "2026-11-05") -> base.PatchRecord:
    return base.PatchRecord(product_id=dv.PRODUCT_ID, update_version=version, path=Path("x.md"),
                            update_published_at=published, update_status=status, update_product="DaVinci Resolve")


def ctx() -> base.CollectorContext:
    return base.CollectorContext(write=False, since="2026-01-01", max_pages=2, target_versions=None)


class Stubs:
    """Every DaVinci transport entry point replaced by a counter. The two refused methods' adapters
    raise, so a call cannot pass silently; Creative COW answers with nothing so the rest of the stack
    still runs."""
    NAMES = ("known_watchlist_candidates", "vendor_forum_search_candidates", "source_probe_candidates",
             "request_text", "request_json", "request_reddit_json_with_fallback", "request_reddit_feed",
             "creative_cow_forum_search_candidates", "utc_now")

    def __init__(self, captured_at: str = PASS_AT) -> None:
        self.calls: Counter = Counter()
        self.captured_at = captured_at

    def __enter__(self):
        self.saved = {n: getattr(dv, n) for n in self.NAMES}
        self.env = os.environ.pop(AUTHORIZATION_ENV, None)

        def raiser(name):
            def _f(*a, **k):
                self.calls[name] += 1
                raise AssertionError(f"{name} must not be called for a disabled method")
            return _f
        for n in self.NAMES[:7]:
            setattr(dv, n, raiser(n))

        def _cow(r, c, e):
            self.calls["creative_cow_forum_search_candidates"] += 1
            return []
        dv.creative_cow_forum_search_candidates = _cow
        dv.utc_now = lambda: self.captured_at
        return self

    def __exit__(self, *exc):
        for n, v in self.saved.items():
            setattr(dv, n, v)
        if self.env is not None:
            os.environ[AUTHORIZATION_ENV] = self.env
        return False

    def refused_calls(self) -> int:
        return sum(v for k, v in self.calls.items() if k != "creative_cow_forum_search_candidates")


def emit(rec: base.PatchRecord) -> tuple[list, list, list, Stubs]:
    with Stubs() as stubs:
        accepted, rejected, health = dv.collect_for_record(rec, ctx())
    return accepted, rejected, health, stubs


# =====================================================================================================
def section_a() -> None:
    print("A. the collector: genuinely disabled, adapter never called")
    net0 = NET[0]
    accepted, rejected, health, stubs = emit(record())
    by = {h["method_id"]: h for h in health}
    check("A1 both methods emit a `disabled` row",
          all(by[m]["status"] == "disabled" for m in TWO), str({m: by[m]["status"] for m in TWO}))
    check("A2 neither adapter, nor any DaVinci transport, was called (0 calls)",
          stubs.refused_calls() == 0, str(dict(stubs.calls)))
    check("A3 no socket or DNS lookup was attempted", NET[0] == net0, str(NET[0] - net0))
    check("A4 the reason is the refusal, not a fetch diagnostic",
          all(by[m]["blocked_reason"] == dv.REFUSED_SOURCE_DISABLED_REASON for m in TWO))
    check("A5 the notes keep the true fact: the Blackmagic forum refuses automated requests",
          all("Blackmagic Design forum has refused" in by[m]["notes"] and "automated requests" in by[m]["notes"]
              for m in TWO))
    counters = ("candidates_found", "accepted_candidates", "duplicate_existing_evidence", "evidence_rows_added",
                "public_counted_reports", "accepted_reports", "rejected_reports")
    check("A6 every counter is 0 (nothing was read)", all(by[m][f] == 0 for m in TWO for f in counters))
    check("A7 last_run is this walk's time (the record was reached), never empty",
          all(by[m]["last_run"] == PASS_AT for m in TWO), str([by[m]["last_run"] for m in TWO]))
    check("A8 the five-method stack and its order are unchanged",
          [h["method_id"] for h in health] == ["known_watchlist", "reddit_search", "creative_cow_forum_search",
                                               "vendor_forum_search", "web_search"], str(list(by)))
    check("A9 Creative COW still runs (called once), and the identities keep their families",
          stubs.calls["creative_cow_forum_search_candidates"] == 1
          and by["known_watchlist"]["source_type"] == "curated_watchlist"
          and by["vendor_forum_search"]["source_type"] == "blackmagic_forum")
    check("A10 Reddit stays a policy row and web_search is unchanged",
          by["reddit_search"]["status"] == "disabled" and by["reddit_search"]["last_run"] == ""
          and by["web_search"]["status"] == "disabled"
          and by["web_search"]["blocked_reason"] == "web_search_adapter_disabled_in_phase_a")
    check("A11 nothing is accepted or rejected from the switched-off methods", accepted == [] and rejected == [])

    # The row is built by its own function. Through method_status the same not-run method reads
    # no_results, which the ladder counts as HEALTHY (section D measures what that would publish).
    check("A12 the counterfactual is real: method_status calls a method with no candidates no_results",
          dv.method_status([], [], [], []) == "no_results")
    tree = ast.parse(Path(dv.__file__).read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "refused_source_disabled_row")
    called = {c.func.id for c in ast.walk(fn) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    check("A13 refused_source_disabled_row never consults method_status", "method_status" not in called
          and "method_health_row" in called, str(sorted(called)))

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "emh.yml"
        write_store(path, health)
        with contextlib.redirect_stdout(io.StringIO()):
            rc = validate(path)
        check("A14 the validator accepts the emitted rows", rc == 0)
        blank = copy.deepcopy(health)
        for h in blank:
            if h["method_id"] in TWO:
                h["last_run"] = ""
        write_store(path, blank)
        with contextlib.redirect_stdout(io.StringIO()):
            rc_blank = validate(path)
        check("A15 ...and its rules are not weakened: the same row with no last_run is still refused",
              rc_blank == 1)

        # Through the real writer, a disabled row replaces the frozen blocked row of the same key.
        prior = [h for h in fixture_rows() if h["update_version"] == "21.2"]
        write_store(path, prior)
        base.upsert_method_health([h for h in health if h["method_id"] in TWO], path)
        stored = {r["method_id"]: r for r in base.load_method_health(path)}
        check("A16 the real writer replaces the blocked rows in place (one row per key, now disabled)",
              len(stored) == 5 and all(stored[m]["status"] == "disabled" and stored[m]["last_run"] == PASS_AT
                                       for m in TWO))
    co.require_owned_methods(health)
    decision = mh.certify_monitoring(dv.PRODUCT_ID, health, published_at="2026-11-05",
                                     contributing_families=set(), now=NOW, thresholds=THRESHOLDS,
                                     owned_methods=co.ALLOWED_METHODS,
                                     manual_only_methods=co.MANUAL_ONLY_METHODS)
    check("A17 every owned method still has its row (no H7 missing telemetry, no H0 unowned method)",
          not any(r.startswith(("missing_method_telemetry:", "unowned_method:")) for r in decision.reasons),
          str(decision.reasons))


# =====================================================================================================
def build_tree(tmp: Path) -> tuple[Path, Path, list[dict]]:
    """A temp tree: the fixture's DaVinci rows plus foreign rows that must never move, and one record
    file per DaVinci record plus a foreign ARCHIVED record sharing a DaVinci version string."""
    store = tmp / "_data" / "evidence_method_health.yml"
    gen = tmp / "updates" / "generated"
    foreign = [
        base.method_health_row(product_id="obs-studio", update_version="19", method_id="known_watchlist",
                               source_type="curated_watchlist", status="blocked", candidates_found=0,
                               accepted_reports=0, rejected_reports=0, blocked_reason="probe_fetch_failed:x",
                               last_run="2026-11-05T00:30:00Z", notes="foreign: another product, same method id"),
        base.method_health_row(product_id="adobe-acrobat-pro", update_version="25.001.20001",
                               method_id="adobe_community_search", source_type="adobe_community_bug_report",
                               status="blocked", candidates_found=0, accepted_reports=0, rejected_reports=0,
                               blocked_reason="http_403", last_run="2026-09-01T00:00:00Z", notes="foreign"),
    ]
    rows = foreign[:1] + fixture_rows() + foreign[1:]
    write_store(store, rows)
    for rec in RECORDS:
        write_record(gen, dv.PRODUCT_ID, rec["update_version"], rec["update_status"], rec["update_published_at"])
    write_record(gen, "obs-studio", "19", "archived", "2017-01-01T00:00:00Z")
    (tmp / "_data" / "consensus_evidence.yml").write_text("schema_version: 1\nevidence: []\n", encoding="utf-8")
    return store, gen, rows


def section_b() -> None:
    print("B. the migration: zero-network, hash-scoped")
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        store, gen, rows = build_tree(tmp)
        before_text = store.read_text(encoding="utf-8")
        before_tree = tree_digest(tmp)
        proc = subprocess.run([sys.executable, "-I", str(MIGRATION), "--path", str(store),
                               "--generated-dir", str(gen), "--write"], capture_output=True, text=True,
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        after_text = store.read_text(encoding="utf-8")
        after_tree = tree_digest(tmp)
        changed_files = sorted(k for k in before_tree if before_tree[k] != after_tree.get(k))
        check("B1 the migration exits 0 and reports 200 changed", proc.returncode == 0
              and "rows changed         : 200" in proc.stdout, proc.stdout[-400:] + proc.stderr[-400:])
        check("B2 exactly one file in the tree changed: the method-health store",
              changed_files == ["_data/evidence_method_health.yml"] and set(before_tree) == set(after_tree),
              str(changed_files))

        def blocks(text: str) -> list[str]:
            out, cur = [], []
            for line in text.splitlines(keepends=True):
                if line.startswith("- product_id:") and cur:
                    out.append("".join(cur))
                    cur = []
                cur.append(line)
            out.append("".join(cur))
            return out
        bb, ab = blocks(before_text), blocks(after_text)
        new_rows = base.load_method_health(store)
        intended = {i for i, r in enumerate(rows) if r["product_id"] == dv.PRODUCT_ID
                    and r["method_id"] in TWO and r["update_version"] in ARCHIVED}
        changed = {i - 1 for i in range(1, len(bb)) if bb[i] != ab[i]}
        check("B3 the store keeps its envelope and row count", bb[0] == ab[0] and len(bb) == len(ab)
              and len(new_rows) == len(rows))
        check("B4 exactly the intended rows changed: DaVinci x archived x the two methods (200)",
              changed == intended and len(intended) == 200, f"changed={len(changed)} intended={len(intended)}")
        moved = Counter(k for i in changed for k in rows[i] if rows[i][k] != new_rows[i][k])
        check("B5 inside them only status, blocked_reason and notes moved",
              set(moved) == {"status", "blocked_reason", "notes"} and all(v == 200 for v in moved.values()),
              str(dict(moved)))
        check("B6 every other row is byte-identical, including the foreign product's blocked known_watchlist row",
              all(bb[i + 1] == ab[i + 1] for i in range(len(rows)) if i not in intended)
              and new_rows[0]["status"] == "blocked" and new_rows[-1]["status"] == "blocked")
        check("B7 every changed row is now disabled with the refusal reason",
              all(new_rows[i]["status"] == "disabled"
                  and new_rows[i]["blocked_reason"] == dv.REFUSED_SOURCE_DISABLED_REASON for i in intended))
        check("B8 the notes keep the refusal and the row's own last diagnostic",
              all(dv.REFUSED_SOURCE_DISABLED_NOTE in new_rows[i]["notes"]
                  and rows[i]["blocked_reason"] in new_rows[i]["notes"] for i in intended))
        with contextlib.redirect_stdout(io.StringIO()):
            rc_valid = validate(store)
        check("B9 the migrated store validates", rc_valid == 0)

        again = subprocess.run([sys.executable, "-I", str(MIGRATION), "--path", str(store),
                                "--generated-dir", str(gen), "--write"], capture_output=True, text=True,
                               env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        check("B10 a second run changes nothing (idempotent, store bytes identical)",
              again.returncode == 0 and "rows changed         : 0" in again.stdout
              and store.read_text(encoding="utf-8") == after_text, again.stdout[-300:])

    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        store, gen, rows = build_tree(tmp)
        odd = base.load_method_health(store)
        target = next(i for i, r in enumerate(odd) if r["product_id"] == dv.PRODUCT_ID
                      and r["method_id"] == "vendor_forum_search" and r["update_version"] in ARCHIVED)
        odd[target]["candidates_found"] = 3
        write_store(store, odd)
        before = store.read_bytes()
        proc = subprocess.run([sys.executable, "-I", str(MIGRATION), "--path", str(store),
                               "--generated-dir", str(gen), "--write"], capture_output=True, text=True,
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        check("B11 an in-scope row of an unexpected shape is refused and NOTHING is written",
              proc.returncode == 2 and "REFUSED" in proc.stdout and store.read_bytes() == before,
              proc.stdout[-300:])
        odd[target]["candidates_found"] = 0
        odd[target]["status"] = "partial"
        write_store(store, odd)
        try:
            mig.migrate(base.load_method_health(store), ARCHIVED)
            refused = False
        except mig.UnexpectedShape:
            refused = True
        check("B12 ...and a status other than blocked or disabled is refused too", refused)

    net0 = NET[0]
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        store, gen, _rows = build_tree(tmp)
        with contextlib.redirect_stdout(io.StringIO()):
            rc = mig.main(["--path", str(store), "--generated-dir", str(gen), "--write"])
    check("B13 zero network: an in-process run with sockets refused makes no attempt", rc == 0 and NET[0] == net0)
    tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(str(node.module or "").split(".")[0])
    check("B14 the migration imports no transport (urllib, http, socket, requests)",
          not imported & {"urllib", "http", "socket", "requests", "httpx"}, str(sorted(imported)))
    writes = {c.func.id if isinstance(c.func, ast.Name) else getattr(c.func, "attr", "")
              for c in ast.walk(tree) if isinstance(c, ast.Call)}
    check("B15 its only writer is the method-health writer (no evidence or record writer)",
          "write_method_health_file" in writes and not writes & {
              "write_evidence_file", "append_evidence_rows", "write_front_matter_and_body",
              "apply_collector_record_fields", "upsert_method_health", "atomic_write_text", "write_text"},
          str(sorted(writes)))


# =====================================================================================================
def section_c() -> None:
    print("C. no refresh or freshness field moves")
    rows = fixture_rows()
    new_rows, changed = mig.migrate(rows, ARCHIVED)
    check("C1 the migration keeps every row's last_run (nothing is marked newly checked)",
          all(a["last_run"] == b["last_run"] for a, b in zip(rows, new_rows)) and len(changed) == 200)
    check("C2 the input rows are not mutated", rows == fixture_rows())

    def newest_usable(rs: list[dict], version: str) -> str:
        return max((str(r["last_run"]) for r in rs if r["update_version"] == version and r["status"] != "disabled"),
                   default="")
    check("C3 every archived page's newest usable run is unchanged (the ladder's freshness input)",
          all(newest_usable(rows, v) == newest_usable(new_rows, v) for v in ARCHIVED))
    states = ladder_states(new_rows)
    check("C4 ...and all 100 archived pages still read COLLECTION STALE",
          len(ARCHIVED) == 100 and all(states[v] == mh.COLLECTION_STALE for v in ARCHIVED),
          str(Counter(states[v] for v in ARCHIVED)))
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        _store, gen, _rows = build_tree(tmp)
        before = tree_digest(gen)
        with contextlib.redirect_stdout(io.StringIO()):
            mig.main(["--path", str(tmp / "_data" / "evidence_method_health.yml"), "--generated-dir", str(gen),
                      "--write"])
        check("C5 no generated record is touched (evidence_last_checked / record_last_updated cannot move)",
              tree_digest(gen) == before)


# =====================================================================================================
def first_pass(rows_after_migration: list[dict], builder=None) -> list[dict]:
    """The collector's first routine pass, as far as AUX-117 changes it: for every CURRENT record the
    real collect_for_record runs (transports stubbed) and its two refused-method rows go through the
    real writer. The other methods keep their base rows, so the comparison isolates this change."""
    with tempfile.TemporaryDirectory() as t:
        path = Path(t) / "emh.yml"
        write_store(path, rows_after_migration)
        emitted = []
        for rec in CURRENT:
            _a, _r, health, stubs = emit(record(rec["update_version"], "current", rec["update_published_at"]))
            assert stubs.refused_calls() == 0
            emitted += [h for h in health if h["method_id"] in TWO]
        if builder is not None:
            emitted = [builder(h) for h in emitted]
        base.upsert_method_health(emitted, path)
        return base.load_method_health(path)


def section_d() -> None:
    print("D. page states equal the list frozen before the change")
    rows = fixture_rows()
    before = ladder_states(rows)
    check("D1 the fixture reproduces the frozen BEFORE state on every page (123)",
          len(before) == 123 and all(before[v] == EXPECTED[v][0] for v in EXPECTED),
          str([v for v in EXPECTED if before.get(v) != EXPECTED[v][0]][:5]))
    check("D2 before: 100 COLLECTION STALE, 20 MONITORING DEGRADED, 3 COLLECTION BLOCKED",
          Counter(before.values()) == Counter({mh.COLLECTION_STALE: 100, mh.MONITORING_DEGRADED: 20,
                                               mh.COLLECTION_BLOCKED: 3}), str(Counter(before.values())))
    migrated, _changed = mig.migrate(rows, ARCHIVED)
    after_m = ladder_states(migrated)
    check("D3 the migration alone changes NO page state (equals the frozen after-migration list)",
          all(after_m[v] == EXPECTED[v][1] == before[v] for v in EXPECTED),
          str([v for v in EXPECTED if after_m[v] != EXPECTED[v][1]][:5]))
    passed = first_pass(migrated)
    after_c = ladder_states(passed)
    mism = [v for v in EXPECTED if after_c[v] != EXPECTED[v][2]]
    check("D4 after the first collector pass every page equals the frozen list, version by version",
          not mism, str([(v, after_c[v], EXPECTED[v][2]) for v in mism][:5]))
    transitions = Counter(f"{before[v]} -> {after_c[v]}" for v in EXPECTED)
    check("D5 the transitions are exactly 100 STALE kept, 20 DEGRADED -> INSUFFICIENT, 3 BLOCKED -> DEGRADED",
          transitions == Counter({f"{mh.COLLECTION_STALE} -> {mh.COLLECTION_STALE}": 100,
                                  f"{mh.MONITORING_DEGRADED} -> {mh.INSUFFICIENT_COVERAGE}": 20,
                                  f"{mh.COLLECTION_BLOCKED} -> {mh.MONITORING_DEGRADED}": 3}), str(dict(transitions)))
    insufficient = [r for r in RECORDS if after_c[r["update_version"]] == mh.INSUFFICIENT_COVERAGE]
    check("D6 INSUFFICIENT COVERAGE is visible: 20 pages, each with ONE fresh healthy family (Creative COW) of 2",
          len(insufficient) == 20 and all(fresh_healthy_families(passed, r["update_version"], r["update_published_at"])
                                          == {dv.CREATIVE_COW_SOURCE_TYPE} for r in insufficient))
    healthy = {mh.MONITORING_ACTIVE, mh.NO_ACCEPTED_REPORTS}
    check("D7 no DaVinci page reads healthy before, after the migration, or after the first pass",
          not ({*before.values(), *after_m.values(), *after_c.values()} & healthy))

    def naive(h: dict) -> dict:
        out = dict(h)
        out["status"] = dv.method_status([], [], [], [])
        return out
    after_naive = ladder_states(first_pass(migrated, builder=naive))
    false_healthy = sum(1 for v in EXPECTED if after_naive[v] in healthy)
    check("D8 counterfactual: built through method_status, the same rows would make 20 pages read healthy",
          false_healthy == 20, str(Counter(after_naive.values())))
    states = {cov.community_state(r, now=NOW, max_age_days=THRESHOLDS.max_age_days)
              for r in (rows, migrated, passed)}
    check("D9 the product-level community state is unchanged by either step", states == {"operating"}, str(states))

    # The committed store, read-only. A corpus observation, not a gate: production runs rewrite it.
    live = [r for r in base.load_method_health() if r.get("product_id") == dv.PRODUCT_ID]
    archived_now = mig.archived_versions()
    frozen = [r for r in live if r["method_id"] in TWO and r["update_version"] in archived_now
              and r["status"] != "disabled"]
    warn("W1 the committed store holds no non-disabled refused-method row on an archived record",
         not frozen, f"{len(frozen)} rows; run migrate_davinci_refused_method_health.py --write")


def run() -> int:
    for section in (section_a, section_b, section_c, section_d):
        try:
            section()
        except Exception:                                                     # noqa: BLE001
            traceback.print_exc()
            check(f"{section.__name__} raised", False)
        print()
    print("=" * 96)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed: " + ", ".join(FAILURES))
    print("=" * 96)
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
