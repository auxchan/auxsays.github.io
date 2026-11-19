#!/usr/bin/env python3
"""NVIDIA driver community evidence from the NVIDIA GeForce forum's default views.

WHAT THIS PROVES, IN ORDER.
  F  Fixture replay. The forum responses captured on 2026-11-19 (user names, ids and avatars replaced,
     long bodies trimmed; tests/fixtures/nvidia_forum) are served through the REAL lib.http transport
     and redirect handler over a fake HTTPS layer, and the shipped collector runs for BOTH driver
     families. Every request is a default-view call; every comment naming a tracked version lands on
     the decision recorded when it was captured: accepted reports, a Studio-named report in a Game
     Ready thread (vetoed), notebook reports, versions named only as environment, disclaimed
     attribution, a module crash without regression evidence, a fine-only post, a multi-version post
     the role reading cannot place, and the shared-component (SSD write) reports, which stay
     unassigned for both families. No comment is ever counted for both families.
  I  Identity unit checks on the shapes those decisions rest on (thread qualification, family,
     notebook, environment, typo version, links and quotes).
  G  The coverage-gap contract (GPT G47 s2): overlap, no overlap with the newest gone, a boundary tie,
     a comment appearing inside the span already read, more new comments than the window shows,
     edits and reordered results -- and the same through the collector across two cycles.
  S  Stop rules and the request guard: page 2+, oldest sort, comment anchors, search, reply
     expansion, the all-communities listing and other hosts are refused BEFORE a request; 401/403/
     429/451, a challenge, HTML for JSON and a refusing body suspend the method (persisted; the next
     cycle makes zero requests); a schema change and a redirect to another host publish nothing and
     send nothing there; robots disallowing the view skips the cycle; the 12-hour cadence; the
     request ceiling and spacing.
  W  The gates a dry run never reaches: registration, ownership (through the real validators),
     routing, the scoped promotion steps and their position, the writeback allow-list, the
     transaction surface; and the write path against a temporary store: excluded rows stored with
     reasons, the same comment observed again never a second row, health crediting accepted rows only.
  P  Public text: no names, @mentions or links in stored text; titles are thread titles; the stored
     URL is the forum's own link to the one comment; the date is the comment's own creation time.

Offline and deterministic: every socket is refused for the whole run. Run:
    PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_nvidia_forum_evidence.py
"""
from __future__ import annotations

import contextlib
import copy
import fnmatch
import http.client
import io
import json
import socket
import sys
import tempfile
import traceback
import urllib.parse
import urllib.request
import urllib.response
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

_REFUSED = [0]


class _NoNet(socket.socket):
    def connect(self, *args, **kwargs):  # noqa: D102
        _REFUSED[0] += 1
        raise OSError("network refused by test_nvidia_forum_evidence")


socket.socket = _NoNet  # type: ignore[misc]
socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(OSError("network refused"))  # type: ignore[assignment]

import run_patch_evidence_collection as runner  # noqa: E402
from lib import collector_ownership as ownership  # noqa: E402
from lib import http as http_lib  # noqa: E402
from lib import method_routing as routing  # noqa: E402
from lib import nvidia_driver_identity as identity  # noqa: E402
from lib import report_counts  # noqa: E402
from lib.method_routing import HEALTH_STATUSES  # noqa: E402
from patch_collectors import base  # noqa: E402
from patch_collectors import nvidia_forum as nf  # noqa: E402
from patch_collectors import nvidia_forum_source as src  # noqa: E402

FIX = _SCRIPTS / "tests" / "fixtures" / "nvidia_forum"
WORKFLOW = _REPO / ".github" / "workflows" / "obs-evidence-collection.yml"
GRD, NSD = identity.GAME_READY, identity.STUDIO
API, WWW = src.API_HOST, src.WWW_HOST

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
        print("  FAIL  " + label + ("  --  " + detail if detail else ""))
        _ERRORS.append(label)


def fixture(name: str):
    path = FIX / name
    return path.read_text(encoding="utf-8") if name.endswith(".txt") else json.loads(path.read_text(encoding="utf-8"))


def record(pid: str, version: str, published: str) -> base.PatchRecord:
    return base.PatchRecord(product_id=pid, update_version=version, path=Path(f"{pid}-{version}.md"),
                            update_published_at=published, update_status="current", update_product=pid)


DATES = {"621.14": "2026-11-04T00:00:00Z", "621.24": "2026-11-12T00:00:00Z"}
RECORDS = {pid: [record(pid, v, d) for v, d in DATES.items()] for pid in (GRD, NSD)}


@contextlib.contextmanager
def patched(pairs):
    saved = [(obj, name, getattr(obj, name)) for obj, name, _value in pairs]
    try:
        for obj, name, value in pairs:
            setattr(obj, name, value)
        yield
    finally:
        for obj, name, value in reversed(saved):
            setattr(obj, name, value)


# --- the wire: the REAL lib.http opener and redirect handler over a fake HTTPS transport ----------

def _respond(status: int, body, content_type: str = "application/json; charset=utf-8", headers=None):
    payload = body if isinstance(body, bytes) else (body if isinstance(body, str) else json.dumps(body)).encode("utf-8")
    return status, dict({"Content-Type": content_type}, **(headers or {})), payload


def default_routes(overrides: dict | None = None):
    """(host, path, id) -> response. Comments are served only for the anchor the topic names."""
    topics = {int(p.stem.split("_")[1]): fixture(p.name) for p in FIX.glob("topic_*.json")}

    def route(url: str):
        parts = urllib.parse.urlsplit(url)
        q = dict(urllib.parse.parse_qsl(parts.query))
        key = (parts.hostname, parts.path, q.get("id"))
        for candidate in (key, (parts.hostname, parts.path, None)):
            if overrides and candidate in overrides:
                return overrides[candidate](url)
        if parts.path == "/robots.txt":
            if parts.hostname == WWW:
                return _respond(200, fixture("robots_www.txt"), "text/plain; charset=UTF-8")
            return _respond(404, (FIX / "robots_api_404.json").read_bytes())
        if parts.path in ("/forums-api/1.0/communities/topics", "/forums-api/1.0/communities/pinned"):
            view = "topics" if parts.path.endswith("topics") else "pinned"
            return _respond(200, fixture(f"community{q['id']}_{view}.json"))
        if parts.path == "/forums-api/1.0/topics":
            tid = int(q["id"])
            return _respond(200, topics[tid]) if tid in topics else _respond(404, {"success": False})
        if parts.path == "/forums-api/1.0/topics/comments":
            tid = int(q["id"])
            want = topics[tid]["data"]["topic"]["lastComment"]["id"]
            if int(q.get("_anchorValue", -1)) != want:
                return _respond(400, {"success": False, "errors": {"anchor": "mismatch"}})
            return _respond(200, fixture(f"comments_{tid}.json"))
        return _respond(599, b"unrouted")
    return route


class FakeHTTPS(urllib.request.HTTPSHandler):
    def __init__(self, route):
        super().__init__()
        self.route = route
        self.seen: list[str] = []

    def https_open(self, req):
        url = req.full_url
        self.seen.append(url)
        self.headers = dict(req.header_items())
        status, headers, payload = self.route(url)
        msg = http.client.HTTPMessage()
        for k, v in headers.items():
            msg[k] = v
        resp = urllib.response.addinfourl(io.BytesIO(payload), msg, url, status)
        resp.msg = http.client.responses.get(status, "")
        return resp

    def hosts(self):
        return [urllib.parse.urlsplit(u).hostname or "" for u in self.seen]


@contextlib.contextmanager
def wire(overrides: dict | None = None, *, records=None, state_path: Path | None = None):
    """Real lib.http over FakeHTTPS; records stubbed; state in a temp file; no sleeping."""
    fake = FakeHTTPS(default_routes(overrides))
    sleeps: list[float] = []
    recs = records if records is not None else RECORDS
    with tempfile.TemporaryDirectory() as tmp:
        path = state_path or (Path(tmp) / "nvidia_forum_state.json")
        real_opener = http_lib._OPENER
        http_lib._OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                                       http_lib._AuthStrippingRedirectHandler(), fake)
        try:
            with patched([(src, "fetch_text", http_lib.fetch_text), (src, "_sleep", sleeps.append),
                          (src, "STATE_PATH", path),
                          (base, "generated_records",
                           lambda pid, tv=None, **kw: [r for r in recs.get(pid, []) if not tv or r.update_version in tv])]):
                nf.reset_cycle()
                yield fake, path, sleeps
        finally:
            http_lib._OPENER = real_opener
            nf.reset_cycle()


def run_both(write: bool = False, target=None):
    nf.reset_cycle()
    ctx = base.CollectorContext(write=write, since=None, max_pages=5, target_versions=target)
    return {pid: nf.NvidiaForumCollector(pid).collect(ctx) for pid in (GRD, NSD)}


def decisions(records=None) -> dict[tuple[str, str, int], str]:
    """(product, version, comment) -> 'COUNT' or the exclusion reason, from this process's cycle."""
    recs = records if records is not None else RECORDS
    out = {}
    captured = base.utc_now()
    for pid, rows in recs.items():
        tracked = {r.update_version for r in rows}
        for rec in rows:
            for thread in (nf._CYCLE or {}).get("threads", []):
                for item in thread.get("items") or []:
                    row = nf.evaluate_comment(pid, rec, tracked, thread, item, captured)
                    if row is not None:
                        out[(pid, rec.update_version, item["comment_id"])] = (
                            "COUNT" if row["counted"] else row["exclusion_reason"])
    return out


def age_state(path: Path, hours: float = 12.5) -> None:
    state = json.loads(path.read_text(encoding="utf-8"))
    at = datetime.now(timezone.utc) - timedelta(hours=hours)
    state["last_cycle"]["at"] = at.strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps(state), encoding="utf-8")


# ---- the decisions recorded when the fixtures were captured (records 621.14 and 621.24) ----------
U, OTHER = "driver_family_unassigned", "driver_family_is_other"
EXPECTED_GRD = {
    ("621.14", 3633489): "COUNT", ("621.14", 3633451): "COUNT", ("621.14", 3633448): "COUNT",
    ("621.14", 3633356): "COUNT", ("621.14", 3633066): "COUNT", ("621.14", 3633062): "COUNT",
    ("621.14", 3633052): "COUNT",
    ("621.14", 3633447): "driver_module_crash_without_regression_evidence",
    ("621.14", 3633362): "driver_version_environment_only",
    ("621.14", 3633323): "driver_version_environment_only",
    ("621.14", 3633347): "notebook_driver_not_tracked",
    ("621.14", 3633148): "driver_family_conflicts_with_thread",
    ("621.14", 3633067): "not_a_real_issue_report",
    ("621.24", 3634576): "COUNT", ("621.24", 3634403): "COUNT", ("621.24", 3634344): "COUNT",
    ("621.24", 3634606): "driver_version_environment_only",
    ("621.24", 3634580): "driver_version_environment_only",
    ("621.24", 3634571): "driver_attribution_disclaimed",
    ("621.24", 3634314): "driver_attribution_disclaimed",
    ("621.24", 3634565): "multiple_tracked_versions_named",
    ("621.24", 3634183): "positive_report_not_a_problem",
    ("621.24", 3634174): "notebook_driver_not_tracked",
    ("621.24", 3634516): "notebook_driver_not_tracked",
    ("621.24", 3634201): OTHER,
}
# The SSD-write topic (a user topic) and other user topics: no family established anywhere.
SSD_TOPIC = {3633770, 3634625, 3634607, 3634650, 3634603, 3634600, 3634324}
for _cid in SSD_TOPIC:
    EXPECTED_GRD[("621.24", _cid)] = U
for _key in (("621.24", 3634466), ("621.24", 3633860), ("621.14", 3633860), ("621.14", 3634603),
             ("621.14", 3634576), ("621.14", 3634565), ("621.14", 3634269), ("621.14", 3634174),
             ("621.14", 3634516)):
    EXPECTED_GRD[_key] = U


# ------------------------------------------------------------------------------------------------
def section_fixture() -> dict:
    print("\n[F] fixture replay through the real transport, both families")
    with wire() as (fake, _path, sleeps):
        results = run_both()
        cycle = nf._CYCLE
        got = decisions()
        seen = list(fake.seen)
        headers = getattr(fake, "headers", {})
    check("F1 the cycle made exactly the ceiling of 16 requests, no more", len(seen) == 16, str(len(seen)))
    bad = [(u, src.permitted_request(u, {int(t): fixture(f"topic_{t}.json")["data"]["topic"]["lastComment"]["id"]
                                          for t in (592433, 592767, 592907, 593067, 592933)})) for u in seen]
    check("F2 every request was a default-view call or a robots file", all(ok for _u, (ok, _r) in bad),
          str([b for b in bad if not b[1][0]][:2]))
    check("F3 the hosts were only www.nvidia.com (robots) and the forum API",
          set(fake.hosts()) == {WWW, API} and [h for h in fake.hosts()].count(WWW) == 1, str(set(fake.hosts())))
    forbidden = [u for u in seen if any(t in u for t in ("_page=2", "oldest", "comment=", "/search", "/children",
                                                         "/categories", "/users", "commentPage", "topicPage"))]
    check("F4 no page 2+, oldest sort, comment anchor, search, reply expansion, listing of all communities",
          not forbidden, str(forbidden))
    read = [t["topic_id"] for t in cycle["threads"] if t.get("outcome") == "read"]
    check("F5 five threads read: both staff feedback threads first, then the version-titled user topics",
          read == [592767, 592433, 592907, 593067, 592933], str(read))
    check("F6 one forum cycle served both families (the second family made no request)",
          len(seen) == int(cycle["requests"]) == 16)
    check("F7 requests were spaced (every request after the first waited)",
          len(sleeps) == 15 and all(s > 0 for s in sleeps), str(len(sleeps)))
    check("F8 an honest client name, no browser identity",
          headers.get("User-agent", "").startswith("AUXSAYS-Patch-Evidence/") and "Mozilla" not in headers.get("User-agent", ""),
          str(headers.get("User-agent")))

    want = {(GRD, v, c): d for (v, c), d in EXPECTED_GRD.items()}
    got_grd = {k: v for k, v in got.items() if k[0] == GRD}
    wrong = {k: (got_grd.get(k), v) for k, v in want.items() if got_grd.get(k) != v}
    extra = sorted(set(got_grd) - set(want))
    check(f"F9 every Game Ready candidate lands on its recorded decision ({len(want)})", not wrong and not extra,
          f"wrong={dict(list(wrong.items())[:4])} extra={extra[:4]}")
    counted = {k for k, v in got.items() if v == "COUNT"}
    check("F10 Game Ready 621.14 counts exactly its 7 recorded reports",
          {c for p, v, c in counted if p == GRD and v == "621.14"}
          == {3633489, 3633451, 3633448, 3633356, 3633066, 3633062, 3633052})
    check("F11 Game Ready 621.24 counts exactly its 3 recorded reports",
          {c for p, v, c in counted if p == GRD and v == "621.24"} == {3634576, 3634403, 3634344})
    check("F12 the 9-days-early SSD-write report (3633066, Game Ready thread) is counted for Game Ready only",
          got.get((GRD, "621.14", 3633066)) == "COUNT" and got.get((NSD, "621.14", 3633066)) == OTHER)
    check("F13 a Studio-named report inside the Game Ready thread is vetoed for both families",
          got.get((GRD, "621.14", 3633148)) == got.get((NSD, "621.14", 3633148)) == "driver_family_conflicts_with_thread")
    ssd = [got.get((p, "621.24", c)) for p in (GRD, NSD) for c in SSD_TOPIC]
    check("F14 every shared-component (SSD topic) report without a family is unassigned in BOTH families",
          ssd and all(d == U for d in ssd), str(ssd))
    check("F15 the Studio-named SSD report is Studio's alone (other for Game Ready) and the shared gate decides",
          got.get((GRD, "621.24", 3634201)) == OTHER and got.get((NSD, "621.24", 3634201)) == "not_a_real_issue_report",
          f"{got.get((GRD, '621.24', 3634201))} {got.get((NSD, '621.24', 3634201))}")
    both = sorted({(v, c) for p, v, c in counted if p == GRD} & {(v, c) for p, v, c in counted if p == NSD})
    check("F16 no comment is counted for both families", not both, str(both))
    unassigned_counted = [k for k, v in got.items() if v == "COUNT" and (k[1], k[2]) in
                          {(v2, c2) for (p2, v2, c2), d2 in got.items() if d2 == U}]
    check("F17 nothing unassigned in one family is counted in the other", not unassigned_counted, str(unassigned_counted))
    check("F18 Studio counts nothing from these windows (no Studio report passes identity and the shared gates)",
          not [k for k in counted if k[0] == NSD])
    check("F19 the staff posts (release notes, staff replies) are never candidates",
          not any(c in (3632042, 3634302, 3634218) for _p, _v, c in got))
    health = {(pid, r["version"]): r["method_health"][0] for pid, res in results.items() for r in res}
    check("F20 one canonical health row per record per family",
          len(health) == 4 and all(h["status"] in HEALTH_STATUSES for h in health.values())
          and all(len(r["method_health"]) == 1 for res in results.values() for r in res))
    check("F21 a first window with older comments outside it is healthy, and says so",
          health[(GRD, "621.14")]["status"] == "success"
          and "outside the visible window" in health[(GRD, "621.14")]["notes"], str(health[(GRD, "621.14")]))
    check("F22 health notes never claim comprehensive monitoring",
          all("comprehensive" not in h["notes"].lower() and "all comments" not in h["notes"].lower()
              and "default views only" in h["notes"] for h in health.values()))
    check("F23 Studio rows read no_results (nothing accepted), not success",
          health[(NSD, "621.14")]["status"] == health[(NSD, "621.24")]["status"] == "no_results")
    return {"results": results, "got": got}


# ------------------------------------------------------------------------------------------------
def thread(title="GeForce GRD 621.14 Feedback Thread (Released 11/4/26)", staff=True, tid=1):
    return dict(nf.thread_profile(title, staff), title=title, topic_id=tid)


def item(text: str, cid: int = 7, created: int = 1794154118):
    return {"comment_id": cid, "created": created, "own_text": nf.clean_text(text),
            "url": src.comment_url(13, "game-ready-drivers", 1, "t", cid)}


def decide(text: str, pid: str = GRD, version: str = "621.14", th=None, tracked=("621.14", "621.24")):
    row = nf.evaluate_comment(pid, record(pid, version, DATES.get(version, "2026-11-04T00:00:00Z")),
                              set(tracked), th or thread(), item(text), "2026-11-19T00:00:00Z")
    return None if row is None else ("COUNT" if row["counted"] else row["exclusion_reason"])


def section_identity() -> None:
    print("\n[I] identity: thread qualification, family, notebook, environment, typo")
    p = nf.thread_profile("GeForce GRD 621.24 Feedback Thread (Released 11/12/26)", True)
    check("I1 a staff title naming one version AND one family qualifies, for that version",
          p["patch_family"] == GRD and p["title_version"] == "621.24")
    check("I2 a staff title without a family never establishes one",
          nf.thread_profile("Driver 621.24 Feedback Thread", True)["patch_family"] is None)
    check("I3 a generic staff thread (no version) establishes nothing",
          nf.thread_profile("DLSS 5 FAQ [9/3/2026]", True)["patch_family"] is None)
    check("I4 a user topic never establishes a family, whatever its title says",
          nf.thread_profile("Game Ready Driver 621.24 crashes everything", False)["patch_family"] is None)
    check("I5 a staff title naming two versions is not patch-specific",
          nf.thread_profile("GeForce GRD 621.14 and 621.24 Feedback", True)["patch_family"] is None)
    concrete = "Since updating to 621.14 my games crash on launch."
    check("I6 thread family applies to its own version", decide(concrete) == "COUNT")
    check("I7 ...and never to another version in the same thread",
          decide("Since updating to 621.24 my games crash on launch.", version="621.24") == "driver_family_unassigned")
    check("I8 the reporter naming the other family vetoes the thread",
          decide("621.14 Studio Driver crashes my renders.") == "driver_family_conflicts_with_thread")
    check("I9 naming both families establishes neither",
          decide("Game Ready and Studio Driver 621.14 both crash.", th=thread("User topic 621.14", False))
          == "driver_family_both_named")
    check("I10 in a user topic the reporter naming the family establishes it",
          decide("Game Ready 621.14 crashes in every game.", th=thread("Crash 621.14", False)) == "COUNT")
    check("I11 'Studio Ready drivers' names the Studio family",
          identity.families_named("621.24 Studio Ready drivers") == {NSD}
          and decide("621.14 Studio Ready drivers crash.", pid=NSD, th=thread("Crash 621.14", False)) == "COUNT")
    check("I12 'OBS Studio' is not a Studio driver mention",
          identity.families_named("OBS Studio 32 crashes with 621.14") == set())
    check("I13 a typo version (612.14) is not 621.14: not a candidate at all",
          decide("612.14 crashes everything since the update.") is None)
    check("I14 a version only inside a link is not the reporter naming it",
          decide("Same crash, see https://us.download.nvidia.com/Windows/621.14/notes.pdf") is None)
    check("I15 a quoted version is the quoted author's, not the reporter's",
          decide("> 621.14 crashes for me\nSame here, crashes constantly.") is None)
    check("I16 a version in the thread title alone is never the commenter naming it",
          decide("This driver crashes my PC when I play.") is None)
    check("I17 a laptop GPU is a notebook report, never merged into the desktop record",
          decide("RTX 4060 Laptop GPU: 621.14 crashes since updating.") == "notebook_driver_not_tracked")
    check("I18 ...but a laptop named as ANOTHER machine says nothing about the reporter's",
          decide("Since updating to 621.14 my games crash. It works on another system with an RTX 4070 Laptop GPU.")
          == "COUNT")
    check("I19 a version only on a specification line is environment",
          decide("GPU: RTX 4090\nDriver: 621.14\nGame crashes after the new season patch.")
          == "driver_version_environment_only")
    check("I19b ...but a field whose own segment names the failure is attribution",
          decide("GPU: RTX 4090\nDriver: 621.14 crashes in every game\n") == "COUNT")
    check("I20 ...a bare spec item in a list too",
          decide("System: RTX 4090, Windows 11, driver 621.14, 2TB SSD.\nThe game crashes.")
          == "driver_version_environment_only")
    check("I21 ...but 'Driver 621.14 crashes my games' is a sentence about the driver",
          decide("Game Ready Driver 621.14 crashes my games constantly.") == "COUNT")
    check("I22 ...and a regression field ('Driver Regression: new in 621.14') is attribution",
          decide("Driver Regression: Yes, new in 621.14. Games crash.") == "COUNT")
    check("I23 a disclaimer in the same sentence refuses",
          decide("I cannot confirm whether this crash was introduced by driver 621.14 or Windows.")
          == "driver_attribution_disclaimed")
    check("I24 a module crash without regression evidence is investigated, not counted",
          decide("nvlddmkm.sys VIDEO_TDR_FAILURE crash on 621.14, happened on older drivers too.")
          == "driver_module_crash_without_regression_evidence")
    check("I25 ...with a rollback it is regression evidence",
          decide("nvlddmkm.sys TDR crash on 621.14. Rolling back to 610.88 fixes it.") == "COUNT")
    check("I26 a fine-only post is not a problem report",
          decide("Installed 621.14, clean install. No issues at all, seems fine.") == "positive_report_not_a_problem")
    user_topic = thread("Crash report 621.14 621.24", False)
    check("I27 two tracked versions named: silence is not enough (the shared role reading must place it)",
          decide("Game Ready 621.14 and 621.24 are both installed somewhere, crash.", th=user_topic)
          == "multiple_tracked_versions_named")
    rollback = "Game Ready: 621.24 crashes in every game. Rolling back to 621.14 fixes it."
    check("I28 the version the reporter rolled back TO is vetoed for that version",
          decide(rollback, th=user_topic) == "version_role_rollback_target")
    row = nf.evaluate_comment(GRD, record(GRD, "621.24", DATES["621.24"]), {"621.14", "621.24"}, user_topic,
                              item(rollback, created=1794700000), "2026-11-19T00:00:00Z")
    check("I28b ...and counted for the version it says crashes",
          row is not None and row["counted"] is True, str(row and row.get("exclusion_reason")))
    early = nf.evaluate_comment(GRD, record(GRD, "621.24", DATES["621.24"]), {"621.14", "621.24"}, user_topic,
                                item(rollback, created=1794154118), "2026-11-19T00:00:00Z")
    check("I28c a comment created before the release cannot count for it (the shared date gate)",
          early is not None and early["exclusion_reason"] == "source_date_before_or_unverified_against_release")
    text = nf.clean_text("Thanks @Mexicola9302 and Manuel@NVIDIA, mail me at a.b@example.com https://x.example/y")
    check("I29 names, @mentions, e-mail addresses and links are removed from stored text",
          "Mexicola" not in text and "Manuel" not in text and "a.b@" not in text and "x.example" not in text
          and "@user" in text and "[link]" in text, text)


# ------------------------------------------------------------------------------------------------
def section_gap() -> None:
    print("\n[G] the coverage-gap contract")
    w = [[100 + i, 1000 + i * 10] for i in range(25)]          # ids 100..124, stamps 1000..1240
    cmp = src.compare_windows
    check("G1 a first window makes no between-poll claim", cmp(None, w) == [])
    shifted = [[125 + i, 1250 + i * 10] for i in range(3)] + w[3:]
    check("G2 an overlapping window (three new comments) is no gap", cmp(w, shifted, 30, 33) == [])
    fresh = [[200 + i, 2000 + i * 10] for i in range(25)]
    check("G3 no overlap and the previous newest gone: possible gap",
          "no_overlap_and_previous_newest_gone" in cmp(w, fresh))
    check("G4 ...even when all 25 visible comments were processed (the reason, never a count)",
          all(isinstance(r, str) and not any(ch.isdigit() for ch in r) for r in cmp(w, fresh)))
    newest = max(w, key=lambda x: (x[1], x[0]))
    tie = [[300, newest[1]]] + [[301 + i, newest[1] + 10 + i] for i in range(24)]
    check("G5 the previous newest gone with a comment at the same second on the boundary: tie retained",
          "boundary_timestamp_tie" in cmp(w, tie))
    ties_inside = [[c, 1000] for c, _t in w]
    check("G6 timestamp ties INSIDE an overlapping window are no gap",
          cmp(ties_inside, ties_inside + [[999, 1000]]) in ([], ["comments_appeared_inside_previous_span"]))
    edited = copy.deepcopy(w)
    check("G7 an edit (same id and creation time) is no gap", cmp(w, edited, 25, 25) == [])
    check("G8 reordered results decide the same", cmp(w, list(reversed(shifted)), 30, 33) == cmp(w, shifted, 30, 33))
    late = w[1:] + [[150, 1005]]
    check("G9 a comment appearing inside the span already read: uncertainty retained",
          "comments_appeared_inside_previous_span" in cmp(w, late))
    check("G10 more new comments than the window shows: possible gap",
          "more_new_comments_than_the_window_shows" in cmp(w, shifted, 30, 40))
    check("G11 a window now empty after a non-empty one is flagged", cmp(w, []) == ["window_now_empty"])
    check("G12 window_of keeps visible top-level comments only, ordered by creation",
          src.window_of([{"id": 2, "createdStamp": 5}, {"id": 3, "createdStamp": 9, "isGhosted": 1},
                         {"id": 1, "createdStamp": 7}]) == [[1, 7], [2, 5]])
    check("G12b a thread read before with NO visible comment is a read window: only the totals speak",
          cmp([], [], 0, 0) == [] and cmp([], [[1, 1]], 0, 30) == ["more_new_comments_than_the_window_shows"]
          and cmp([], [[1, 1]], 0, 1) == [])

    # Through the collector: cycle 1 reads the captured windows; cycle 2 (12.5 h later) serves a
    # 621.14 thread whose window no longer overlaps; cycle 3 serves it unchanged again.
    print("  -- across cycles")
    original = fixture("comments_592433.json")
    moved = copy.deepcopy(original)
    for idx, comment in enumerate(moved["data"]["comments"]):
        comment["id"] = 3700000 + idx
        comment["createdStamp"] = 1795100000 + (100 - idx) * 60
        comment["comments"] = []
    moved["pagination"]["_totalRows"] = 140
    topic = fixture("topic_592433.json")
    topic2 = copy.deepcopy(topic)
    topic2["data"]["topic"]["lastComment"]["id"] = 3700000
    topic2["data"]["topic"]["lastActivityStamp"] = 1795200000

    def serve(payload):
        return lambda url: _respond(200, payload)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        with wire(state_path=path) as (fake, _p, _s):
            with patched([(base, "append_evidence_rows", lambda rows, *a, **k: (0, 0, [])),
                          (nf, "apply_consensus_writebacks", lambda pid, vs: {})]):
                run_both(write=True)
            first_requests = len(fake.seen)
            stored = json.loads(path.read_text(encoding="utf-8"))
        check("G13 the first write cycle persists each read thread's window (ids and creation times only)",
              len(stored["threads"]["592433"]["window"]) == 25
              and all(len(pair) == 2 for pair in stored["threads"]["592433"]["window"]), str(first_requests))
        age_state(path)
        overrides = {(API, "/forums-api/1.0/topics", "592433"): serve(topic2),
                     (API, "/forums-api/1.0/topics/comments", "592433"): serve(moved)}
        with wire(overrides, state_path=path) as (fake, _p, _s):
            with patched([(base, "append_evidence_rows", lambda rows, *a, **k: (0, 0, [])),
                          (nf, "apply_consensus_writebacks", lambda pid, vs: {})]):
                second = run_both(write=True)
            stored2 = json.loads(path.read_text(encoding="utf-8"))
        h = next(r for r in second[GRD] if r["version"] == "621.14")["method_health"][0]
        check("G14 a window that no longer overlaps reports partial: possible_missed_comments",
              h["status"] == "partial" and h["blocked_reason"] == "possible_missed_comments", str(h))
        check("G15 the reason is stored separately (notes and state), never as a count",
              "no_overlap_and_previous_newest_gone" in h["notes"]
              and "no_overlap_and_previous_newest_gone" in stored2["threads"]["592433"]["gap_reasons"])
        check("G16 no page was read to repair it", not [u for u in fake.seen if "_page=2" in u or "comment=" in u])
        h24 = next(r for r in second[GRD] if r["version"] == "621.24")["method_health"][0]
        check("G17 a gap in one thread does not mark another version's health", h24["status"] != "partial"
              or h24["blocked_reason"] != "possible_missed_comments", str(h24))
        age_state(path)
        with wire(overrides, state_path=path) as (fake, _p, _s):
            with patched([(base, "append_evidence_rows", lambda rows, *a, **k: (0, 0, [])),
                          (nf, "apply_consensus_writebacks", lambda pid, vs: {})]):
                third = run_both(write=True)
            third_requests = list(fake.seen)
        h3 = next(r for r in third[GRD] if r["version"] == "621.14")["method_health"][0]
        check("G18 the next cycle, overlapping again, is healthy (no stale gap)", h3["status"] != "partial", str(h3))
        check("G19 an unchanged listed thread is not re-read (no topic or comments request for it)",
              not [u for u in third_requests if "id=592907" in u or "id=592767" in u], str(len(third_requests)))
        check("G19b ...including one whose window was empty when read (593067 has no comment)",
              not [u for u in third_requests if "id=593067" in u], str([u for u in third_requests if "593067" in u]))


# ------------------------------------------------------------------------------------------------
def section_stops() -> None:
    print("\n[S] stop rules, the request guard, robots, cadence")
    anchors = {592433: 3633652}
    good = src.topic_comments_url(592433, 3633652)
    check("S1 the default comments call is permitted only with the topic's own last comment",
          src.permitted_request(good, anchors)[0] and not src.permitted_request(good, {})[0])
    base_q = "id=592433&_page=1&_pageSize=25&_anchorValue=3633652&_anchorDirection=%2Bbefore&_anchorOffset=0&includeGhosted=0"
    refused = {
        "page 2": good.replace("_page=1", "_page=2"),
        "oldest sort": good.replace("%2Bbefore", "%2Bafter"),
        "comment anchor": good.replace("3633652", "3633066"),
        "commentPage": f"https://{API}/forums-api/1.0/topics/comments?{base_q}&commentPage=2",
        "extra parameter": good + "&sort=oldest",
        "bigger page": good.replace("_pageSize=25", "_pageSize=100"),
        "reply expansion": f"https://{API}/forums-api/1.0/comments/children?id=3633066",
        "search": f"https://{API}/forums-api/1.0/search?q=621.14",
        "all communities": f"https://{API}/forums-api/1.0/categories/all/communities",
        "user page": f"https://{API}/forums-api/1.0/users/123",
        "unconfigured community": src.community_view_urls(99)[1],
        "community page 2": src.community_view_urls(13)[1].replace("_page=1", "_page=2"),
        "topicPage": src.community_view_urls(13)[1] + "&topicPage=2",
        "www page": f"https://{WWW}/en-us/geforce/forums/game-ready-drivers/13/592433/x/?commentPage=2",
        "other host": "https://forums.example.com/forums-api/1.0/topics?id=1",
        "http": good.replace("https://", "http://"),
        "port": good.replace(API, API + ":8443"),
        "userinfo": good.replace("https://", "https://u:p@"),
        "fragment": good + "#x",
        "robots with query": f"https://{WWW}/robots.txt?x=1",
    }
    leaks = {name: src.permitted_request(url, anchors) for name, url in refused.items()}
    check(f"S2 every forbidden shape is refused ({len(refused)})", not [n for n, (ok, _r) in leaks.items() if ok],
          str([n for n, (ok, _r) in leaks.items() if ok]))
    t = src.Transport(src.empty_state())
    sent: list[str] = []
    with patched([(src, "fetch_text", lambda url, **kw: sent.append(url))]):
        try:
            t.get(refused["page 2"])
            raised = False
        except src.ForbiddenRequest:
            raised = True
    check("S3 a forbidden request raises BEFORE anything is sent", raised and not sent and not t.requests)

    def refusal(status, body=b"", ctype="application/json"):
        return lambda url: _respond(status, body, ctype)
    for label, override in (
            ("403", {(API, "/forums-api/1.0/communities/pinned", None): refusal(403, b"Forbidden", "text/html")}),
            ("429", {(API, "/forums-api/1.0/topics", None): refusal(429, b"Too Many Requests", "text/plain")}),
            ("401", {(WWW, "/robots.txt", None): refusal(401, b"Unauthorized", "text/plain")}),
            ("451", {(API, "/forums-api/1.0/communities/topics", None): refusal(451, b"", "text/plain")}),
            ("challenge", {(API, "/forums-api/1.0/topics", None): refusal(
                200, b"<html><title>Just a moment...</title><body>cf-chl captcha</body></html>", "text/html")}),
            ("html for json", {(API, "/forums-api/1.0/topics", None): refusal(200, b"<html><body>hi</body></html>", "text/html")}),
            ("refusing body", {(API, "/forums-api/1.0/topics", None): refusal(
                200, b'{"success": false, "errors": {"global": [{"message": "Automated access is not permitted"}]}}')}),
    ):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            with wire(override, state_path=path) as (fake, _p, _s):
                with patched([(base, "append_evidence_rows", lambda rows, *a, **k: (0, 0, [])),
                              (nf, "apply_consensus_writebacks", lambda pid, vs: {})]):
                    res = run_both(write=True)
                n1 = len(fake.seen)
            stored = json.loads(path.read_text(encoding="utf-8"))
            statuses = {r["method_health"][0]["status"] for rr in res.values() for r in rr}
            rows = sum(r["accepted_count"] + r["rejected_count"] for rr in res.values() for r in rr)
            age_state(path)
            with wire(None, state_path=path) as (fake2, _p, _s):
                res2 = run_both(write=False)
            statuses2 = {r["method_health"][0]["status"] for rr in res2.values() for r in rr}
            check(f"S4 {label}: blocked, no rows, refusal persisted; the next cycle makes 0 requests",
                  statuses == {"blocked"} and rows == 0 and "access_refused" in stored
                  and len(fake2.seen) == 0 and statuses2 == {"blocked"},
                  f"{statuses} rows={rows} n1={n1} next={len(fake2.seen)} {statuses2}")
    st = {"access_refused": {"at": "2026-11-19T00:00:00Z", "detail": "HTTP 403"}}
    now = datetime(2026, 11, 20, tzinfo=timezone.utc)
    check("S5 a clearing time in the future clears nothing",
          src.suspension(dict(st), now, "2099-01-01T00:00:00Z") != "")
    check("S6 a clearing time equal to the refusal clears nothing",
          src.suspension(dict(st), now, "2026-11-19T00:00:00Z") != "")
    cleared = dict(st)
    check("S7 a passed clearing time after the refusal clears it, once",
          src.suspension(cleared, now, "2026-11-19T12:00:00Z") == "" and "access_refused" not in cleared)
    check("S8 the shipped clearing time is empty (only a reviewed change sets it)", src.ACCESS_REFUSAL_CLEARED_AT == "")

    schema_breaks = {
        "comments without data.comments": {(API, "/forums-api/1.0/topics/comments", None):
                                           lambda url: _respond(200, {"success": True, "pagination": {"_totalRows": 1}, "data": {}})},
        "comments without _totalRows": {(API, "/forums-api/1.0/topics/comments", None):
                                        lambda url: _respond(200, {"success": True, "pagination": {}, "data": {"comments": []}})},
        "comment without createdStamp": {(API, "/forums-api/1.0/topics/comments", None):
                                         lambda url: _respond(200, {"success": True, "pagination": {"_totalRows": 1},
                                                                    "data": {"comments": [{"id": 1, "body": "x", "user": {}}]}})},
        "listing without topics": {(API, "/forums-api/1.0/communities/topics", None):
                                   lambda url: _respond(200, {"success": True, "data": {}})},
        "success false": {(API, "/forums-api/1.0/topics", None):
                          lambda url: _respond(200, {"success": False, "errors": {"global": [{"message": "invalid"}]}})},
    }
    for label, override in schema_breaks.items():
        with wire(override) as (fake, _p, _s):
            res = run_both(write=False)
        statuses = {r["method_health"][0]["status"] for rr in res.values() for r in rr}
        reasons = {r["method_health"][0]["blocked_reason"] for rr in res.values() for r in rr}
        rows = sum(r["accepted_count"] + r["rejected_count"] for rr in res.values() for r in rr)
        check(f"S9 schema change ({label}): broken, no rows at all", statuses == {"broken"} and rows == 0
              and reasons == {"schema_changed"}, f"{statuses} {reasons} rows={rows}")

    redirect = {(API, "/forums-api/1.0/topics", "592767"):
                lambda url: _respond(302, b"", "text/html", {"Location": "https://forums-mirror.example.net/t/592767"})}
    with wire(redirect) as (fake, _p, _s):
        res = run_both(write=False)
    statuses = {r["method_health"][0]["status"] for rr in res.values() for r in rr}
    rows = sum(r["accepted_count"] + r["rejected_count"] for rr in res.values() for r in rr)
    check("S10 a redirect to another host: source-authority stop, 0 requests to that host, no rows",
          statuses == {"broken"} and rows == 0 and "forums-mirror.example.net" not in fake.hosts()
          and {r["method_health"][0]["blocked_reason"] for rr in res.values() for r in rr} == {"source_authority_stop"},
          f"{statuses} {fake.hosts()[-3:]}")
    same = {(API, "/forums-api/1.0/topics", "593067"):
            lambda url: (_respond(301, b"", "text/html", {"Location": f"https://{API}/forums-api/1.0/topics?id=593067&x=1"})
                         if "x=1" not in url else _respond(200, fixture("topic_593067.json")))}
    with wire(same) as (fake, _p, _s):
        run_both(write=False)
    check("S11 a redirect is bounded to the host asked (lib.http redirect_hosts): a same-host hop is sent there only",
          all(h in (WWW, API) for h in fake.hosts()))

    disallow = fixture("robots_www.txt") + "\nUser-agent: *\nDisallow: /en-us/geforce/forums/\n"
    with wire({(WWW, "/robots.txt", None): lambda url: _respond(200, disallow, "text/plain")}) as (fake, _p, _s):
        res = run_both(write=False)
    check("S12 www robots disallowing the forum pages skips the cycle after the robots reads",
          len(fake.seen) == 2 and {r["method_health"][0]["blocked_reason"] for rr in res.values() for r in rr}
          == {"robots_policy"}, str(fake.seen))
    with wire({(API, "/robots.txt", None): lambda url: _respond(503, b"busy", "text/plain")}) as (fake, _p, _s):
        res = run_both(write=False)
    check("S13 an API robots that is unreachable (5xx) skips the cycle as disallowed",
          len(fake.seen) == 2 and {r["method_health"][0]["status"] for rr in res.values() for r in rr} == {"blocked"})
    api_policy = "User-agent: *\nDisallow: /forums-api/1.0/topics\n"
    with wire({(API, "/robots.txt", None): lambda url: _respond(200, api_policy, "text/plain")}) as (fake, _p, _s):
        res = run_both(write=False)
    check("S14 an API robots policy that appears is applied before the next read",
          not [u for u in fake.seen if "/1.0/topics?" in u] and
          {r["method_health"][0]["blocked_reason"] for rr in res.values() for r in rr} == {"robots_policy"})
    with wire({(WWW, "/robots.txt", None): lambda url: _respond(404, b"nope", "text/plain")}) as (fake, _p, _s):
        res = run_both(write=False)
    check("S15 an unreadable www robots skips the cycle (treated conservatively)",
          len(fake.seen) == 1 and {r["method_health"][0]["status"] for rr in res.values() for r in rr} == {"blocked"})
    check("S16 the robots matcher: longest rule wins, wildcards and $ honoured",
          not src.parse_robots("User-agent: *\nAllow: /\nDisallow: /*?commentPage=").allows("/x/?commentPage=2")
          and src.parse_robots("User-agent: *\nDisallow: /a$").allows("/ab")
          and not src.parse_robots("User-agent: *\nDisallow: /a$").allows("/a"))

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        with wire(state_path=path) as (fake, _p, _s):
            with patched([(base, "append_evidence_rows", lambda rows, *a, **k: (0, 0, [])),
                          (nf, "apply_consensus_writebacks", lambda pid, vs: {})]):
                run_both(write=True)
        with wire(state_path=path) as (fake, _p, _s):
            res = run_both(write=True)
        check("S17 within 12 hours of a cycle nothing is requested and no health row is claimed",
              len(fake.seen) == 0 and all(r == [] for r in res.values()), str(len(fake.seen)))
    with wire(records={}) as (fake, _p, _s):
        res = run_both(write=False)
    check("S18 with no tracked record (the official lane has not published yet) nothing is requested",
          len(fake.seen) == 0 and all(r == [] for r in res.values()))
    saved = copy.deepcopy(routing.METHOD_PLANS)
    try:
        for pid in (GRD, NSD):
            routing.METHOD_PLANS[pid] = {"primary": [], "disabled": [nf.METHOD_ID]}
        with wire() as (fake, _p, _s):
            res = run_both(write=False)
    finally:
        routing.METHOD_PLANS.clear()
        routing.METHOD_PLANS.update(saved)
    check("S19 switched off in method routing: 0 requests, an honest disabled row, nothing stored",
          len(fake.seen) == 0 and {r["method_health"][0]["status"] for rr in res.values() for r in rr} == {"disabled"}
          and all(r["method_health"][0]["last_run"] == "" for rr in res.values() for r in rr))
    t2 = src.Transport(src.empty_state(), max_requests=2)
    with patched([(src, "fetch_text", lambda url, **kw: http_lib.FetchResult(url=url, status=200, headers={},
                                                                              text="x", final_url=url)),
                  (src, "_sleep", lambda s: None)]):
        t2.get(src.ROBOTS_URLS[WWW])
        t2.get(src.ROBOTS_URLS[API])
        try:
            t2.get(src.ROBOTS_URLS[WWW])
            over = False
        except src.RequestBudgetExhausted:
            over = True
    check("S20 the per-cycle request ceiling is enforced in the transport", over and len(t2.requests) == 2)
    calls: list[dict] = []
    with patched([(src, "fetch_text", lambda url, **kw: calls.append(kw) or http_lib.FetchResult(
            url=url, status=200, headers={}, text="x", final_url=url))]):
        src.Transport(src.empty_state()).get(src.ROBOTS_URLS[API])
    check("S21 every request carries the redirect bound (its own host) and no retries",
          calls and calls[0].get("redirect_hosts") == frozenset({API}) and calls[0].get("retries") == 0, str(calls))


# ------------------------------------------------------------------------------------------------
def section_wiring(fixture_results: dict) -> None:
    print("\n[W] the gates a dry run never reaches, and the write path")
    check("W1 not registered by default", not set(runner.NVIDIA_FORUM_PRODUCT_IDS) & set(runner.build_collectors({})))
    on = runner.build_collectors({runner.NVIDIA_FORUM_ENABLE_ENV: "true"})
    check("W2 registered for both families for the exact string 'true', one instance per family",
          all(pid in on and on[pid]().product_id == pid and type(on[pid]()).__name__ == "NvidiaForumCollector"
              for pid in (GRD, NSD)))
    traps = {v: bool(set(runner.NVIDIA_FORUM_PRODUCT_IDS) & set(runner.build_collectors({runner.NVIDIA_FORUM_ENABLE_ENV: v})))
             for v in ("false", "0", "1", "yes", "on", "")}
    check("W3 no truthy-looking value registers it", not any(traps.values()), str(traps))
    check("W4 ownership authorises exactly the forum method and source type for both families",
          all(ownership.allowed_methods(p) == {nf.METHOD_ID} and ownership.allowed_source_types(p) == {nf.SOURCE_TYPE}
              for p in (GRD, NSD)))
    check("W5 both families are promotion products", {GRD, NSD} <= report_counts.CONSENSUS_PROMOTION_PRODUCTS)
    check("W6 method routing declares the one primary for both families",
          all(routing.plan_methods(p)["primary"] == [nf.METHOD_ID] for p in (GRD, NSD)))
    check("W7 the forum state file is in both families' transaction surface",
          all(runner._extra_write_surface(p) == [src.STATE_PATH] for p in (GRD, NSD)))

    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = (((wf.get("jobs") or {}).get("collect") or {}).get("steps") or [])
    names = [str(s.get("name") or "") for s in steps]
    collect_step = next((s for s in steps if "run_patch_evidence_collection.py" in str(s.get("run") or "")), {})
    check("W8 the scheduled collection step activates it with the exact string 'true'",
          (collect_step.get("env") or {}).get(runner.NVIDIA_FORUM_ENABLE_ENV) == "true")

    def body(step):
        return " ".join(ln.strip() for ln in str(step.get("run") or "").splitlines()
                        if ln.strip() and not ln.strip().startswith("#"))
    consensus_i = next((i for i, s in enumerate(steps) if "build_consensus_from_evidence.py" in str(s.get("run") or "")), -1)
    qa_i = next((i for i, n in enumerate(names) if n == "QA patch records"), -1)
    for pid in (GRD, NSD):
        idx = [i for i, s in enumerate(steps)
               if "apply_consensus_to_records.py" in body(s) and f"--product-id {pid} " in body(s) + " "]
        check(f"W9 one scoped {pid} promotion, after reconciliation and before the first QA, skipped on dry runs",
              len(idx) == 1 and consensus_i < idx[0] < qa_i and "--write-all --confirm-write" in body(steps[idx[0]])
              and "dry_run != 'true'" in str(steps[idx[0]].get("if") or ""), f"{idx} {consensus_i} {qa_i}")
    writeback = next((s for s in steps if "automation_writeback.py" in str(s.get("run") or "")), {})
    toks = str(writeback.get("run") or "").replace("\\\n", " ").split()
    globs = [toks[i + 1].strip("'\"") for i, t in enumerate(toks[:-1]) if t == "--allow"]
    # The official lane names records after the product's own name (patch_ingest), not the product id.
    expected_paths = ["auxsays/updates/generated/2026-11-04-geforce-game-ready-driver-621-14.md",
                      "auxsays/updates/generated/2026-11-12-nvidia-studio-driver-621-24.md",
                      "auxsays/_data/nvidia_forum_state.json"]
    check("W10 the writeback commits both families' records and the forum state file",
          all(any(fnmatch.fnmatch(p, g) for g in globs) for p in expected_paths), str(globs[-4:]))
    stray = [p.name for p in (_REPO / "auxsays" / "updates" / "generated").glob("*.md")
             if any(fnmatch.fnmatch("auxsays/updates/generated/" + p.name, g)
                    for g in ("auxsays/updates/generated/*geforce-game-ready-driver*.md",
                              "auxsays/updates/generated/*nvidia-studio-driver*.md"))
             and base.load_front_matter_and_body(p)[0].get("product_id") not in (GRD, NSD)]
    check("W11 the NVIDIA globs commit no other product's record", not stray, str(stray))
    check("W12 the state file lives in _data and is not published as a page",
          src.STATE_PATH.parent.name == "_data" and src.STATE_PATH.suffix == ".json")

    # --- the write path against a temporary store -------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "consensus_evidence.yml"
        store.write_text(yaml.safe_dump({"schema_version": 1, "evidence": []}), encoding="utf-8")
        real_append = base.append_evidence_rows
        writebacks: list[tuple[str, tuple]] = []

        def append(rows, path=None, **kw):
            return real_append(rows, store, **kw)
        state_path = Path(tmp) / "state.json"
        with wire(state_path=state_path) as (fake, _p, _s):
            with patched([(base, "append_evidence_rows", append),
                          (nf, "apply_consensus_writebacks",
                           lambda pid, vs: writebacks.append((pid, tuple(vs))) or {v: True for v in vs})]):
                first = run_both(write=True)
                stored = base.load_evidence(store)
                age_state(state_path)
                second = run_both(write=True)
                stored_again = base.load_evidence(store)
                n_second = len(fake.seen)
        counted = [r for r in stored if r["counted"]]
        check("W13 the first write stores every candidate: 10 counted, every excluded row with its reason",
              len(counted) == 10 and all(r.get("exclusion_reason") for r in stored if not r["counted"]),
              f"{len(counted)} of {len(stored)}")
        check("W14 a shared-component report is stored once per family, excluded in both, counted in neither",
              {(r["product_id"], r["counted"], r["exclusion_reason"]) for r in stored
               if r["id"].endswith("-592907-3633770")}
              == {(GRD, False, U), (NSD, False, U)})
        check("W15 every stored row belongs to its family, a tracked version and the one source type",
              all(r["product_id"] in (GRD, NSD) and r["update_version"] in DATES and r["source_type"] == nf.SOURCE_TYPE
                  for r in stored))
        check("W16 the same comment observed again (next cycle) is never a second row",
              len(stored_again) == len(stored) and n_second > 0, f"{len(stored)} -> {len(stored_again)}")
        h = next(r for r in first[GRD] if r["version"] == "621.14")["method_health"][0]
        check("W17 health credits exactly the accepted rows it stored, never the excluded ones",
              h["evidence_rows_added"] == h["accepted_reports"] == 7 and h["duplicate_existing_evidence"] == 0, str(h))
        h2 = next(r for r in second[GRD] if r["version"] == "621.14")
        check("W18 the next cycle adds nothing (unchanged threads are not re-read)",
              h2.get("evidence_rows_added", 0) == 0, str(h2.get("evidence_rows_added")))
        check("W19 the collector hands only newly accepted patches to the shared writeback, per family",
              sorted(w for w in writebacks if w[1]) == [(GRD, ("621.14", "621.24"))], str(writebacks))
        before = yaml.safe_dump({"schema_version": 1, "evidence": []}, sort_keys=False)
        for pid in (GRD, NSD):
            mine = [r for r in stored if r["product_id"] == pid]
            after = yaml.safe_dump({"schema_version": 1, "evidence": mine}, sort_keys=False, allow_unicode=True)
            with patched([(ownership, "generated_records",
                           lambda p, tv=None, **kw: [r for r in RECORDS.get(p, []) if not tv or r.update_version in tv])]):
                try:
                    ownership.validate_evidence(pid, before, after)
                    ownership.validate_method_health(pid, [row for r in first[pid] for row in r["method_health"]])
                    err = None
                except Exception as exc:  # noqa: BLE001
                    err = exc
            check(f"W20 {pid}: its rows and health pass the real ownership validators", err is None, repr(err))
        foreign = [r for r in stored if r["product_id"] == NSD][:1]
        after = yaml.safe_dump({"schema_version": 1, "evidence": foreign}, sort_keys=False, allow_unicode=True)
        with patched([(ownership, "generated_records",
                       lambda p, tv=None, **kw: [r for r in RECORDS.get(p, []) if not tv or r.update_version in tv])]):
            try:
                ownership.validate_evidence(GRD, before, after)
                err = None
            except Exception as exc:  # noqa: BLE001
                err = exc
        check("W21 and a row of the other family is refused for Game Ready", err is not None)

        # Public text of what was stored.
        print("\n[P] public text of the stored rows")
        names = ("Manuel", "koroush", "Mexicola", "postictal", "jaafaman", "mertuygr", "darky")
        texts = " ".join(str(r.get(f) or "") for r in stored
                         for f in ("report_text_excerpt", "matched_context", "report_title", "parent_title"))
        check("P1 no person's name or @handle in any stored text", not any(n.lower() in texts.lower() for n in names)
              and "@NVIDIA" not in texts)
        check("P2 no link inside stored report text", "http" not in " ".join(
            str(r.get("report_text_excerpt") or "") + str(r.get("matched_context") or "") for r in stored))
        thread_titles = {fixture(f"topic_{t}.json")["data"]["topic"]["title"]
                         for t in (592433, 592767, 592907, 593067, 592933)}
        check("P3 report titles are thread titles", all(r["report_title"] in thread_titles for r in stored))
        check("P4 the stored URL is the forum's own link to that one comment",
              all(r["source_url"].startswith("https://www.nvidia.com/en-us/geforce/forums/")
                  and r["source_url"].endswith("?comment=" + r["id"].rsplit("-", 1)[1]) for r in stored))
        check("P5 ...and the shared gate reads it as a specific report URL",
              all(base.source_url_is_specific(r["source_url"]) for r in stored))
        r66 = next(r for r in stored if r["id"] == f"{GRD}-621-14-nvidia-forum-592433-3633066")
        check("P6 the report date is the comment's own creation time (2026-11-08 16:08:38Z), not its last activity",
              r66["source_date"] == "2026-11-08T16:08:38Z" and r66["match_basis"] == "exact_version_text"
              and r66["matched_text"] == "621.14", str(r66.get("source_date")))
        check("P7 counted rows carry the sentiment the promotion requires", all(r["sentiment"] == "negative" for r in counted))
        check("P8 the state file carries ids, times and provenance only (no text, no user)",
              "body" not in state_path.read_text(encoding="utf-8")
              and "collection_authorization" in json.loads(state_path.read_text(encoding="utf-8"))["provenance"])


def run() -> int:
    print("=" * 74)
    print("NVIDIA GeForce forum evidence (default views, both driver families)")
    print("=" * 74)
    results = section_fixture()
    section_identity()
    section_gap()
    section_stops()
    section_wiring(results)
    check("Z no socket was opened by the whole suite", _REFUSED[0] == 0, str(_REFUSED[0]))
    print()
    print("=" * 74)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 74)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
