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
     cycle makes zero requests); a schema change and ANY redirect (another host, or the same host
     pointing at page 2, an older anchor, search or the all-communities listing) publish nothing and
     send nothing there; robots disallowing the view skips the cycle; the 12-hour cadence; the
     request ceiling and spacing.
  W  The gates a dry run never reaches: registration, ownership (through the real validators),
     routing, the scoped promotion steps and their position, the writeback allow-list, the
     transaction surface; and the write path against a temporary store: excluded rows stored with
     reasons, the same comment observed again never a second row (also when it is served again under
     another thread), health crediting accepted rows only.
  P  Public text: no names (staff names, @mentions, members' display names addressed in plain text),
     no links in stored text, and no name in any fixture; titles are thread titles; the stored URL is
     the forum's own link to the one comment; the date is the comment's own creation time.
  M  One comment served under two threads (a moderator's move) is stored once, under the thread it
     was first seen in; members addressed by plain name are not stored.
  T  A user topic whose title carries a member's @handle and display names: the stored titles (which
     the promotion copies into the record) go through the same name removal as the comment text, and
     no decision moves.
  Q  Deferred work persists (GPT G61 Q5). Threads the request ceiling, the thread cap and the time
     budget defer -- a title-less seed and never-read user topics among them -- stay queued in the
     state file with their reason through three exhausted cycles, while no longer listed and with
     no last activity; later cycles read them longest-waiting first under the unchanged ceilings,
     and the store ends with exactly the rows and decisions of one unconstrained cycle (9 counted,
     none twice, none credited twice). A read or unchanged thread leaves the queue; a thread whose
     topic view answers 404 is quarantined (thread_unreadable); one whose title names no tracked
     version and one with no record left leave with their reason recorded; a failed read stays owed
     at the end of the queue; a targeted run and a stop keep the queue; the prune keeps owed and
     never-read entries; queue depth and oldest age are in every health note and the runtime event;
     a seed read through the listing is recorded.
  QS A queued thread's own failure cannot stop collection for every thread (GPT G62 R1). A queued,
     unlisted user topic answering success:false is quarantined while the SAME cycle reads and counts
     the others (9 counted); it is never selected again (not even listed), never pruned or
     invalidated, and only a reviewed change releases it, after which the store equals one
     unconstrained cycle's. HTTP 401/403/451 (and an HTML page) suspend the method as before and
     quarantine the refused thread, which is not asked again once the refusal is cleared; a 429 keeps
     it queued. A 5xx, a timeout, another shape, a redirect and an unconfirmed success:false keep it
     queued for three cycles running without a stop. A listed thread and a seed never read keep their
     stops. A 410 is thread_unreadable and never retried. The prune and the release path, directly.
     A quarantine keeps the thread's entry; a refusal of a listed thread or an unread seed keeps its
     old stop; no timer releases a quarantine.

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
    ("621.24", 3634576): "COUNT", ("621.24", 3634403): "COUNT",
    # LiveKernelEvent 141/1b8 black screens "after upgrading to 621.01", "tried 617.42 but still
    # happened", then 621.24 "still do happen": the problem began on, and persists across, other
    # versions -- nothing release-specific to 621.24 (G44 s4 row 4). Investigated, not counted.
    ("621.24", 3634344): "driver_module_crash_without_regression_evidence",
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
    check("F10b comment 3633451 ('works on another system with an RTX 4070 Laptop GPU') still counts for Game Ready",
          got.get((GRD, "621.14", 3633451)) == "COUNT", str(got.get((GRD, "621.14", 3633451))))
    check("F11 Game Ready 621.24 counts exactly its 2 recorded reports",
          {c for p, v, c in counted if p == GRD and v == "621.24"} == {3634576, 3634403})
    check("F11b a module crash dated to another version (621.01) and still seen on 617.42 is investigated",
          got.get((GRD, "621.24", 3634344)) == "driver_module_crash_without_regression_evidence",
          str(got.get((GRD, "621.24", 3634344))))
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
    # None of the captured staff replies names a version, so pin the rule on one that does.
    staff_topic = copy.deepcopy(fixture("topic_592433.json")["data"]["topic"])
    staff_reply = {"id": 9, "createdStamp": 1794154118, "body": "Driver 621.14 crashes are being investigated.",
                   "user": {"id": "1", "aclactions": {"officialreply": True}}, "isOfficialReply": 1, "comments": []}
    user_reply = dict(staff_reply, id=10, user={"id": "2", "aclactions": {"officialreply": False}}, isOfficialReply=0)
    items = nf._items_for(dict(nf.thread_profile(staff_topic["title"], True), title=staff_topic["title"]),
                          staff_topic, [staff_reply, user_reply], 13, "game-ready-drivers")
    check("F19b a staff comment naming the version is still not a candidate; the same text by a user is",
          [i["comment_id"] for i in items] == [10], str([i["comment_id"] for i in items]))
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
    check("I18b an 'other' qualifying anything but a machine turns nothing off ('Like other users here, my laptop')",
          decide("Like other users here, my laptop crashes in every game since 621.14.") == "notebook_driver_not_tracked")
    check("I18c ...nor does 'different' ('Different games all crash on my laptop')",
          decide("Different games all crash on my laptop since 621.14.") == "notebook_driver_not_tracked")
    check("I18d a first-person notebook is always the reporter's ('My RTX 4060 laptop', 'my other laptop')",
          decide("My RTX 4060 laptop crashes since updating to 621.14.") == "notebook_driver_not_tracked"
          and decide("Since updating to 621.14 my games crash, on my other laptop too.") == "notebook_driver_not_tracked")
    check("I18e ...an unqualified 'the laptop' is a notebook report; someone else's ('my wife's laptop') is not",
          decide("Different games crash on the laptop since updating to 621.14.") == "notebook_driver_not_tracked"
          and decide("Since updating to 621.14 my desktop games crash. My wife's laptop is fine.") == "COUNT")
    check("I18f another machine named earlier in the sentence does not make a LATER laptop someone else's",
          decide("Since updating to 621.14 it works on another PC but the laptop crashes in every game.")
          == "notebook_driver_not_tracked")
    unowned = ("Another laptop user here: since 621.14 every game crashes on launch.",
               "Another laptop owner with the same problem, 621.14 crashes in every game.",
               "Same here on a different laptop, 621.14 crashes in every game since updating.",
               "Like other laptop users, since 621.14 every game crashes on launch.")
    check("I18g 'another laptop', 'a different laptop', 'other laptop users' say nothing of whose laptop: "
          "the reporter's notebook, never the desktop record",
          all(decide(t) == "notebook_driver_not_tracked" for t in unowned), str([decide(t) for t in unowned]))
    owned = ("Since updating to 621.14 my desktop games crash. My friend's laptop is fine.",
             "Since updating to 621.14 my desktop games crash. His laptop is fine.",
             "Since updating to 621.14 my desktop games crash. Her laptop is fine.",
             "Since updating to 621.14 my desktop games crash. Their laptop is fine.")
    check("I18h ...a laptop is another person's only through a possessive owner (friend's, his, her, their)",
          all(decide(t) == "COUNT" for t in owned), str([decide(t) for t in owned]))
    described = ("Same here on another machine with an RTX 4060 Laptop GPU: since 621.14 every game crashes on launch.",
                 "On my second system with an RTX 4070 Laptop GPU, since 621.14 every game crashes on launch.",
                 "Another PC running an RTX 4060 Laptop GPU here, since 621.14 every game crashes on launch.",
                 "My other rig with a 4080 laptop GPU: since 621.14 every game crashes on launch.")
    check("I18i a described other machine with a laptop GPU is the reporter's notebook unless the sentence "
          "says it works on it (VERIFY_3 S01-S04)",
          all(decide(t) == "notebook_driver_not_tracked" for t in described), str([decide(t) for t in described]))
    works_on = ("It works on another system with an RTX 4070 Laptop GPU, but on my desktop since 621.14 every game "
                "crashes on launch.",
                "Since 621.14 every game crashes on launch on my desktop. It works on another system with an RTX 4070 "
                "Laptop GPU.")
    check("I18j ...and 'it works on another system with a Laptop GPU' still leaves the desktop report counted "
          "(VERIFY_3 P08, S05)",
          all(decide(t) == "COUNT" for t in works_on), str([decide(t) for t in works_on]))
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
    check("I24b a regression cue about ANOTHER version is not evidence for this one",
          decide("nvlddmkm TDR crashes started after updating to 617.42 months ago. Still crashing on 621.14, "
                 "same as before.") == "driver_module_crash_without_regression_evidence")
    check("I24c ...nor when the problem began on one version and persisted on another (the 3634344 shape)",
          decide("Screen goes black after upgrading to 621.01. I tried 617.42 but still happened. Then clean "
                 "installed 621.14, still happens. LiveKernelEvent 141.")
          == "driver_module_crash_without_regression_evidence")
    check("I24d a rollback that does not fix it is not a contrast",
          decide("nvlddmkm.sys TDR crash on 621.14. Rolled back to 610.88 but it still crashes.")
          == "driver_module_crash_without_regression_evidence"
          and decide("nvlddmkm.sys TDR crash on 621.14. Rolled back to 610.88, still not working.")
          == "driver_module_crash_without_regression_evidence")
    check("I24e dated to this version, but a rollback with the same crash says it is not release-specific",
          decide("nvlddmkm TDR crashes since updating to 621.14. Rolled back to the previous driver, same crash.")
          == "driver_module_crash_without_regression_evidence")
    check("I25b dating the crash to THIS version is evidence ('since updating from 617.42 to 621.14', 'new in')",
          decide("Since updating from 617.42 to 621.14 I get nvlddmkm TDR crashes.") == "COUNT"
          and decide("nvlddmkm TDR crash, new in 621.14.") == "COUNT")
    check("I25c ...so is another version named as fine",
          decide("nvlddmkm TDR crashes on 621.14. 610.88 was fine.") == "COUNT")
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
    text = nf.clean_text("Thanks @SampleUser42 and Casey@NVIDIA, mail me at a.b@example.com https://x.example/y")
    check("I29 names, @mentions, e-mail addresses and links are removed from stored text",
          "SampleUser" not in text and "Casey" not in text and "a.b@" not in text and "x.example" not in text
          and "@user" in text and "[link]" in text, text)
    text = nf.clean_text("I don't know, plainmember7... ask PLAINMEMBER7 or Laptop about 621.14",
                         {"plainmember7", "Laptop", "ab"})
    check("I30 a member addressed by plain name (a display name in the same response) is removed",
          "plainmember7" not in text.lower() and text.count("[name]") == 2, text)
    check("I30b ...but a display name the identity rules read (here 'Laptop') is kept, so no decision moves",
          "Laptop" in text and not nf.scrubbable_name("Laptop") and not nf.scrubbable_name("Studio")
          and not nf.scrubbable_name("621.14") and not nf.scrubbable_name("ab") and nf.scrubbable_name("plainmember7"))
    check("I30c display names are collected from every user object of a response, nested replies included",
          nf.display_names({"user": {"displayName": "A1b2"}, "comments": [{"user": {"displayName": "C3d4"},
                                                                        "ghostedByUser": {"displayName": None}}]})
          == {"A1b2", "C3d4"})


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
    check("G6 timestamp ties INSIDE an overlapping window are no gap", cmp(ties_inside, list(reversed(ties_inside))) == [])
    check("G6b ...but a NEW comment at that same second sat inside the span already read: uncertainty retained",
          cmp(ties_inside, ties_inside + [[999, 1000]]) == ["comments_appeared_inside_previous_span"])
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
            try:
                res = run_both(write=False)
            except Exception as exc:  # noqa: BLE001 -- a crash is not the fail-closed stop
                res = {"crash": [{"accepted_count": 0, "rejected_count": 0,
                                  "method_health": [{"status": "crashed", "blocked_reason": repr(exc)[:80]}]}]}
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
    same_dest = f"https://{API}/forums-api/1.0/topics?id=593067&x=1"
    same = {(API, "/forums-api/1.0/topics", "593067"):
            lambda url: (_respond(301, b"", "text/html", {"Location": same_dest})
                         if "x=1" not in url else _respond(200, fixture("topic_593067.json")))}
    with wire(same) as (fake, _p, _s):
        res = run_both(write=False)
    reasons = {r["method_health"][0]["blocked_reason"] for rr in res.values() for r in rr}
    rows = sum(r["accepted_count"] + r["rejected_count"] for rr in res.values() for r in rr)
    check("S11 a SAME-host redirect is not followed either: nothing sent there, source-authority stop, no rows",
          same_dest not in fake.seen and reasons == {"source_authority_stop"} and rows == 0,
          f"{reasons} rows={rows} sent_there={same_dest in fake.seen}")

    def to(dest):
        return lambda url: _respond(302, b"", "text/html", {"Location": dest(url)})
    forbidden_hops = {
        "comments -> page 2": ((API, "/forums-api/1.0/topics/comments", None),
                               lambda url: url.replace("_page=1", "_page=2")),
        "comments -> older anchor, +after": ((API, "/forums-api/1.0/topics/comments", None),
                                             lambda url: url.replace("%2Bbefore", "%2Bafter")
                                             .split("_anchorValue=")[0] + "_anchorValue=3633066&_anchorDirection=%2Bafter"
                                             "&_anchorOffset=0&includeGhosted=0"),
        "topics -> search": ((API, "/forums-api/1.0/topics", None),
                             lambda url: f"https://{API}/forums-api/1.0/search?q=621.24"),
        "pinned -> all communities": ((API, "/forums-api/1.0/communities/pinned", None),
                                      lambda url: f"https://{API}/forums-api/1.0/categories/all/communities"),
        "www robots -> commentPage": ((WWW, "/robots.txt", None),
                                      lambda url: f"https://{WWW}/en-us/geforce/forums/game-ready-drivers/13/592433/x/"
                                                  "?commentPage=2"),
    }
    leaked = {}
    for label, (key, dest) in forbidden_hops.items():
        with wire({key: to(dest)}) as (fake, _p, _s):
            res = run_both(write=False)
        sources = [u for u in fake.seen if urllib.parse.urlsplit(u).path == key[1]]
        hop = dest(sources[0]) if sources else ""
        reasons = {r["method_health"][0]["blocked_reason"] for rr in res.values() for r in rr}
        # The hop must be one the guard refuses (else the shape proves nothing), must never be sent,
        # and the cycle must stop on it.
        if not sources or hop in fake.seen or src.permitted_request(hop, {})[0] \
                or reasons != {"source_authority_stop"}:
            leaked[label] = (bool(sources), hop in fake.seen, sorted(reasons))
    check(f"S11b a same-host redirect to a forbidden view sends NOTHING there ({len(forbidden_hops)} shapes)",
          not leaked, str(leaked))
    moved: list[str] = []
    with patched([(src, "fetch_text", lambda url, **kw: moved.append(url) or http_lib.FetchResult(
            url=url, status=200, headers={}, text="User-agent: *\n", final_url=url + "?moved=1"))]):
        try:
            src.Transport(src.empty_state()).get(src.ROBOTS_URLS[WWW])
            stopped = False
        except src.SourceAuthorityStop:
            stopped = True
    check("S11c an answer from any URL but the one asked is a source-authority stop", stopped and len(moved) == 1)

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
    saved = copy.deepcopy(routing.METHOD_PLANS)
    try:
        routing.METHOD_PLANS[GRD] = {"primary": [], "disabled": [nf.METHOD_ID]}
        with wire() as (fake, _p, _s):
            res = run_both(write=False)
    finally:
        routing.METHOD_PLANS.clear()
        routing.METHOD_PLANS.update(saved)
    check("S19b switched off for ONE family: that family reports disabled, the other still reads",
          {r["method_health"][0]["status"] for r in res[GRD]} == {"disabled"}
          and "disabled" not in {r["method_health"][0]["status"] for r in res[NSD]} and len(fake.seen) == 16,
          f"{len(fake.seen)} {[r['method_health'][0]['status'] for r in res[NSD]]}")
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
    check("S21 every request carries an EMPTY redirect bound (no redirect followed) and no retries",
          calls and calls[0].get("redirect_hosts") == frozenset() and calls[0].get("retries") == 0, str(calls))


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
        # A third cycle where the 621.14 thread gained ONE comment, which identity excludes
        # (environment only): the accepted rows are all already held, the only new row is excluded.
        topic3 = copy.deepcopy(fixture("topic_592433.json"))
        topic3["data"]["topic"]["lastComment"]["id"] = 3639999
        topic3["data"]["topic"]["lastActivityStamp"] = 1795300000
        comments3 = copy.deepcopy(fixture("comments_592433.json"))
        newcomer = dict(copy.deepcopy(comments3["data"]["comments"][0]), id=3639999, createdStamp=1795290000,
                        comments=[], replyCount=0,
                        body="GPU: RTX 4080\nDriver: 621.14\nMy shooter stutters since its own season patch.")
        comments3["data"]["comments"] = [newcomer] + comments3["data"]["comments"][:24]
        comments3["pagination"]["_totalRows"] += 1
        age_state(state_path)
        with wire({(API, "/forums-api/1.0/topics", "592433"): lambda url: _respond(200, topic3),
                   (API, "/forums-api/1.0/topics/comments", "592433"): lambda url: _respond(200, comments3)},
                  state_path=state_path) as (fake, _p, _s):
            with patched([(base, "append_evidence_rows", append),
                          (nf, "apply_consensus_writebacks", lambda pid, vs: {v: True for v in vs})]):
                third = run_both(write=True)
                stored_third = base.load_evidence(store)
        h3 = next(r for r in third[GRD] if r["version"] == "621.14")["method_health"][0]
        check("W18b a new EXCLUDED row is stored, never credited as a report this method added",
              len(stored_third) == len(stored) + 2 and h3["evidence_rows_added"] == 0
              and h3["duplicate_existing_evidence"] == h3["accepted_reports"] == 6
              and h3["status"] == "success", f"{len(stored)}->{len(stored_third)} {h3}")
        counted = [r for r in stored if r["counted"]]
        check("W13 the first write stores every candidate: 9 counted, every excluded row with its reason",
              len(counted) == 9 and all(r.get("exclusion_reason") for r in stored if not r["counted"]),
              f"{len(counted)} of {len(stored)}")
        check("W14 a shared-component report is stored once per family, excluded in both, counted in neither",
              {(r["product_id"], r["counted"], r["exclusion_reason"]) for r in stored
               if r["id"].endswith("-comment-3633770")}
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
        texts = " ".join(str(r.get(f) or "") for r in stored
                         for f in ("report_text_excerpt", "matched_context", "report_title", "parent_title"))
        name_fields: list[str] = []
        for path in sorted(FIX.glob("*.json")):
            stack = [json.loads(path.read_text(encoding="utf-8"))]
            while stack:
                node = stack.pop()
                if isinstance(node, dict):
                    name_fields += [f"{path.name}:{k}" for k in node
                                    if k in ("displayName", "name", "username", "nickname", "avatar", "email")]
                    stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
                elif isinstance(node, list):
                    stack.extend(v for v in node if isinstance(v, (dict, list)))
        check("P1 no fixture carries a person's name field (users are opaque ids), no stored text a staff name",
              not name_fields and "@NVIDIA" not in texts, str(name_fields[:3]))
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
        r66 = next((r for r in stored if r["id"] == f"{GRD}-621-14-nvidia-forum-comment-3633066"), {})
        check("P6 the report date is the comment's own creation time (2026-11-08 16:08:38Z), not its last activity",
              r66.get("source_date") == "2026-11-08T16:08:38Z" and r66.get("match_basis") == "exact_version_text"
              and r66.get("matched_text") == "621.14", str(r66.get("source_date")))
        check("P7 counted rows carry the sentiment the promotion requires", all(r["sentiment"] == "negative" for r in counted))
        check("P8 the state file carries ids, times and provenance only (no text, no user)",
              "body" not in state_path.read_text(encoding="utf-8")
              and "collection_authorization" in json.loads(state_path.read_text(encoding="utf-8"))["provenance"])


# ------------------------------------------------------------------------------------------------
def section_moved_comment() -> None:
    print("\n[M] one comment, two threads: identity is the comment; members' names never stored")
    created = 1794600000                                    # 2026-11-13, after both releases
    reporter = {"id": "9001", "displayName": "Reporter_Alpha7", "aclactions": {"officialreply": False}}
    helper = {"id": "9002", "displayName": "Helper_Bravo3", "aclactions": {"officialreply": False}}
    report = {"id": 3640001, "createdStamp": created, "updatedStamp": created, "lastActivityStamp": created,
              "isVisible": 1, "isGhosted": 0, "status": "default", "replyCount": 0, "isOfficialReply": 0,
              "topic": {"id": 592907}, "user": reporter, "comments": [],
              "body": "Game Ready 621.14 crashes in every game since updating. Thanks Helper_Bravo3 and "
                      "@Reporter_Alpha7 and Casey@NVIDIA, the tip did not help."}
    tip = dict(report, id=3640002, user=helper, createdStamp=created - 60, body="Try a clean install with DDU.")
    first = copy.deepcopy(fixture("comments_592907.json"))
    first["data"]["comments"] = [report, tip] + first["data"]["comments"]
    first["pagination"]["_totalRows"] += 2
    # The next cycle: a moderator moved the comment into the 621.14 feedback thread.
    topic2 = copy.deepcopy(fixture("topic_592433.json"))
    topic2["data"]["topic"]["lastComment"]["id"] = 3640001
    topic2["data"]["topic"]["lastActivityStamp"] = 1795300000
    second = copy.deepcopy(fixture("comments_592433.json"))
    second["data"]["comments"] = [dict(copy.deepcopy(report), topic={"id": 592433})] + second["data"]["comments"][:24]
    second["pagination"]["_totalRows"] += 1
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "consensus_evidence.yml"
        store.write_text(yaml.safe_dump({"schema_version": 1, "evidence": []}), encoding="utf-8")
        real_append = base.append_evidence_rows

        def append(rows, path=None, **kw):
            return real_append(rows, store, **kw)
        state_path = Path(tmp) / "state.json"
        quiet = [(base, "append_evidence_rows", append), (nf, "apply_consensus_writebacks", lambda pid, vs: {})]
        with wire({(API, "/forums-api/1.0/topics/comments", "592907"): lambda url: _respond(200, first)},
                  state_path=state_path) as (_fake, _p, _s):
            with patched(quiet):
                run_both(write=True)
                stored1 = base.load_evidence(store)
        age_state(state_path)
        with wire({(API, "/forums-api/1.0/topics", "592433"): lambda url: _respond(200, topic2),
                   (API, "/forums-api/1.0/topics/comments", "592433"): lambda url: _respond(200, second)},
                  state_path=state_path) as (fake, _p, _s):
            with patched(quiet):
                again = run_both(write=True)
                stored2 = base.load_evidence(store)
            reread = [u for u in fake.seen if "comments?id=592433" in u]
    # Found by the comment's own link, not by the row id under test.
    mine1 = [r for r in stored1 if str(r.get("source_url") or "").endswith("?comment=3640001")]
    mine2 = [r for r in stored2 if str(r.get("source_url") or "").endswith("?comment=3640001")]
    grd = next((r for r in mine1 if r["product_id"] == GRD), {})
    check("M1 the comment is stored once per family the first time (Game Ready counted: the reporter named it)",
          sorted((r["product_id"], r["counted"]) for r in mine1) == [(GRD, True), (NSD, False)], str(mine1)[:200])
    check("M2 served again under ANOTHER thread, it is never a second row (the second read happened)",
          len(mine2) == len(mine1) == 2 and len(stored2) == len(stored1) and reread, f"{len(stored1)}->{len(stored2)}")
    check("M3 the stored row keeps the thread it was first seen under",
          [r["source_url"] for r in mine2 if r["product_id"] == GRD] == [grd.get("source_url")]
          and "/592907/" in str(grd.get("source_url")) and str(grd.get("source_url")).endswith("?comment=3640001"))
    h = next(r for r in again[GRD] if r["version"] == "621.14")
    check("M4 the second sighting is credited as already held, not as a report this run added",
          h.get("evidence_rows_added") == 0 and h["method_health"][0]["duplicate_existing_evidence"] >= 1, str(h)[:200])
    texts = " ".join(str(r.get(f) or "") for r in stored2
                     for f in ("report_text_excerpt", "matched_context", "report_title", "parent_title"))
    check("P1b members' display names addressed in plain text, @handles and staff names are never stored",
          not any(n.lower() in texts.lower() for n in ("Reporter_Alpha7", "Helper_Bravo3", "Casey"))
          and "[name]" in str(grd.get("report_text_excerpt")) and "@user" in str(grd.get("report_text_excerpt")),
          str(grd.get("report_text_excerpt")))


# ------------------------------------------------------------------------------------------------
def section_title_names() -> None:
    print("\n[T] a user topic's title naming members: stored through the same name removal as comment text")
    created = 1794600000                                    # 2026-11-13, after both releases
    handle, poster, listed = "@Zorbix_Handle9", "Quillan_Fenwick5", "Ostrava_Listed2"
    plain = fixture("topic_592907.json")["data"]["topic"]["title"]
    named = f"{handle} and {poster} ({listed}): {plain}"
    # The poster's display name is in the topic response; the other name only in the listing entry.
    listing = copy.deepcopy(fixture("community13_topics.json"))
    for entry in listing["data"]["topics"]:
        if entry["id"] == 592907:
            entry["title"] = named
            entry["lastComment"] = dict(entry.get("lastComment") or {}, user={
                "id": "9101", "displayName": listed, "aclactions": {"officialreply": False}})
    topic = copy.deepcopy(fixture("topic_592907.json"))
    topic["data"]["topic"]["title"] = named
    topic["data"]["topic"]["user"] = dict(topic["data"]["topic"]["user"], displayName=poster)
    report = {"id": 3640101, "createdStamp": created, "updatedStamp": created, "lastActivityStamp": created,
              "isVisible": 1, "isGhosted": 0, "status": "default", "replyCount": 0, "isOfficialReply": 0,
              "topic": {"id": 592907}, "comments": [],
              "user": {"id": "9102", "displayName": "Reporter_Delta6", "aclactions": {"officialreply": False}},
              "body": "Game Ready 621.24 crashes in every game since updating."}
    comments = copy.deepcopy(fixture("comments_592907.json"))
    comments["data"]["comments"] = [report] + comments["data"]["comments"]
    comments["pagination"]["_totalRows"] += 1
    with_comment = {(API, "/forums-api/1.0/topics/comments", "592907"): lambda url: _respond(200, comments)}
    with_names = {**with_comment,
                  (API, "/forums-api/1.0/communities/topics", "13"): lambda url: _respond(200, listing),
                  (API, "/forums-api/1.0/topics", "592907"): lambda url: _respond(200, topic)}
    with wire(with_comment) as (_fake, _p, _s):
        run_both()
        plain_decisions = decisions()
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "consensus_evidence.yml"
        store.write_text(yaml.safe_dump({"schema_version": 1, "evidence": []}), encoding="utf-8")
        real_append = base.append_evidence_rows

        def append(rows, path=None, **kw):
            return real_append(rows, store, **kw)
        quiet = [(base, "append_evidence_rows", append), (nf, "apply_consensus_writebacks", lambda pid, vs: {})]
        with wire(with_names) as (_fake, state_path, _s):
            with patched(quiet):
                run_both(write=True)
                named_decisions = decisions()
                stored = base.load_evidence(store)
                read_state = state_path.read_text(encoding="utf-8")
        # The same topic DEFERRED (no thread read this cycle): its state entry is written from the
        # listing alone, so the names it can remove are the listing entry's (poster and last commenter).
        # The entries are observed as the cycle writes them, before the real retention prune runs.
        deferred_listing = copy.deepcopy(listing)
        for entry in deferred_listing["data"]["topics"]:
            if entry["id"] == 592907:
                entry["user"] = dict(entry.get("user") or {}, displayName=poster)
        written: list[str] = []
        real_prune = src.prune_threads

        def prune(state, keep, now=None):
            written.append(json.dumps(state, ensure_ascii=False))
            return real_prune(state, keep, now)
        with wire({(API, "/forums-api/1.0/communities/topics", "13"): lambda url: _respond(200, deferred_listing)}) \
                as (_fake, state_path, _s):
            with patched(quiet + [(src, "MAX_THREADS_PER_CYCLE", 0), (src, "prune_threads", prune)]):
                run_both(write=True)
                deferred_state = (written or ["{}"])[0]
                deferred_saved = state_path.read_text(encoding="utf-8")
    rows = [r for r in stored if "/592907/" in str(r.get("source_url") or "")]
    expected = f"@user and [name] ([name]): {plain}"
    check("P1c the stored report_title and parent_title of every row from that topic carry no @handle or name",
          rows and all(r.get("report_title") == r.get("parent_title") == expected for r in rows),
          str(sorted({(r.get("report_title"), r.get("parent_title")) for r in rows}))[:300])
    counted = [r for r in rows if r.get("counted")]
    texts = " ".join(str(r.get(f) or "") for r in rows
                     for f in ("report_text_excerpt", "matched_context", "report_title", "parent_title"))
    check("P1d ...the counted row the promotion copies carries the scrubbed title, and no stored text names them",
          [r["source_url"].rsplit("=", 1)[1] for r in counted] == ["3640101"]
          and counted[0]["report_title"] == expected
          and not any(n.lower() in texts.lower() for n in ("Zorbix_Handle9", poster, listed, "Reporter_Delta6")),
          str([(r.get("source_url", "")[-16:], r.get("report_title")) for r in counted]))
    topic_ids = {r["source_url"].rsplit("=", 1)[1] for r in rows}
    moved = {k: (plain_decisions.get(k), v) for k, v in named_decisions.items()
             if str(k[2]) in topic_ids and plain_decisions.get(k) != v}
    check("P1e no decision reads the stored title: the same comments decide the same with and without the names",
          rows and not moved and len([k for k in named_decisions if str(k[2]) in topic_ids]) == len(rows), str(moved))
    raw_titles = {fixture(p.name)["data"]["topic"]["title"] for p in FIX.glob("topic_*.json")}
    raw_titles |= {t["title"] for p in FIX.glob("community*_*.json") for t in fixture(p.name)["data"]["topics"]}
    needles = ("zorbix_handle9", poster.lower(), listed.lower(), "reporter_delta6")

    def state_scan(text: str) -> tuple[dict, list, list]:
        threads = json.loads(text)["threads"]
        staff = [(tid, e.get("title")) for tid, e in threads.items() if e.get("staff")]
        return threads.get("592907") or {}, staff, [n for n in needles if n in text.lower()]
    entry, staff, leaks = state_scan(read_state)
    check("P1f the state file keeps a READ user topic's title through the same name removal (0 names or handles "
          "in the file); a staff thread's title stays as read, for its family",
          entry.get("title") == expected and entry.get("staff") is False and not leaks
          and staff and all(title in raw_titles for _tid, title in staff),
          f"{entry.get('title')!r} leaks={leaks} staff={staff}")
    entry, staff, leaks = state_scan(deferred_state)
    saved_leaks = [n for n in needles if n in deferred_saved.lower()]
    check("P1g ...and a DEFERRED user topic's title through the listing entry's names (0 names or handles in the "
          "state written or saved); a deferred staff thread's title stays as listed",
          entry.get("title") == expected and entry.get("last_activity") is None and not leaks and not saved_leaks
          and staff and all(title in raw_titles for _tid, title in staff),
          f"{entry.get('title')!r} leaks={leaks}/{saved_leaks} staff={staff}")


# ------------------------------------------------------------------------------------------------
class _Clock:
    """The cycle's notion of now (nvidia_forum.datetime), advanced by the test between cycles."""

    def __init__(self, start: datetime) -> None:
        self.now = start

    def iso(self) -> str:
        return self.now.strftime("%Y-%m-%dT%H:%M:%SZ")

    def datetime_class(self):
        clock = self

        class _DT(datetime):
            @classmethod
            def now(cls, tz=None):  # noqa: D102
                return clock.now if tz is None else clock.now.astimezone(tz)
        return _DT


def _listing(name: str, drop: set[int]):
    payload = copy.deepcopy(fixture(name))
    payload["data"]["topics"] = [t for t in payload["data"]["topics"] if t["id"] not in drop]
    return lambda url: _respond(200, payload)


class _Lane:
    """One state file and one temporary evidence store, driven cycle by cycle through the shipped
    collectors (write mode, real append and dedupe), 12.5 hours apart."""

    def __init__(self, tmp: str, start: datetime) -> None:
        self.store = Path(tmp) / "consensus_evidence.yml"
        self.store.write_text(yaml.safe_dump({"schema_version": 1, "evidence": []}), encoding="utf-8")
        self.state_path = Path(tmp) / "state.json"
        self.clock = _Clock(start)
        self.events: list[tuple[str, dict]] = []
        self.results: list[dict] = []

    def cycle(self, overrides=None, extra=(), records=None, target=None):
        self.clock.now += timedelta(hours=12, minutes=30)
        real_append = base.append_evidence_rows
        store = self.store

        def append(rows, path=None, **kw):
            return real_append(rows, store, **kw)
        with wire(overrides, records=records, state_path=self.state_path) as (fake, _p, _s):
            with patched([(base, "append_evidence_rows", append),
                          (nf, "apply_consensus_writebacks", lambda pid, vs: {}),
                          (nf, "datetime", self.clock.datetime_class()),
                          (nf.rb, "emit", lambda event, **f: self.events.append((event, f)))] + list(extra)):
                res = run_both(write=True, target=target)
            cyc = nf._CYCLE or {}
            read = [t["topic_id"] for t in cyc.get("threads", []) if t.get("outcome") == "read"]
            seen = list(fake.seen)
        self.results.append(res)
        return res, cyc, read, seen

    def state(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def owed(self) -> dict[str, dict]:
        return {tid: e["deferred"] for tid, e in self.state()["threads"].items() if isinstance(e.get("deferred"), dict)}

    def rows(self) -> list[dict]:
        return base.load_evidence(self.store)


def _health(res) -> list[dict]:
    return [r["method_health"][0] for rr in res.values() for r in rr]


def _decision_map(rows) -> dict[str, tuple]:
    return {r["id"]: (bool(r["counted"]), r.get("exclusion_reason") or "") for r in rows}


def section_deferred_queue() -> None:
    print("\n[Q] deferred threads persist until read or invalidated (GPT G61 Q5)")
    check("Q0 the ceilings are unchanged: 16 requests and 5 threads per cycle",
          src.MAX_REQUESTS_PER_CYCLE == 16 and src.MAX_THREADS_PER_CYCLE == 5,
          f"{src.MAX_REQUESTS_PER_CYCLE} {src.MAX_THREADS_PER_CYCLE}")
    users = {592907, 593067, 592933}
    without_592933 = {(API, "/forums-api/1.0/communities/topics", "13"): _listing("community13_topics.json", {592933})}
    none_listed = {(API, "/forums-api/1.0/communities/topics", "13"): _listing("community13_topics.json", users),
                   (API, "/forums-api/1.0/communities/pinned", "13"): _listing("community13_pinned.json", {592767})}
    real_transport = src.Transport
    real_run_cycle = nf.run_cycle

    def robots_and_listings_only(state, **kw):
        return real_transport(state, max_requests=6)

    def time_budget_spent(*args, **kwargs):
        # The run's time budget is spent while the cycle selects threads (not afterwards, when the
        # collectors would stop before writing their health rows).
        with patched([(nf, "_budget_expired", lambda: True)]):
            return real_run_cycle(*args, **kwargs)
    # A clock with a fractional second, as production's datetime.now() always has: the old prune
    # expression only failed when the retention horizon was fractional.
    start = datetime.now(timezone.utc).replace(microsecond=250000)

    # The reference: one unconstrained cycle over the same captured windows.
    with tempfile.TemporaryDirectory() as tmp:
        lane = _Lane(tmp, start)
        _res, _cyc, ref_read, _seen = lane.cycle()
        reference = _decision_map(lane.rows())
        ref_state = lane.state()
    check("Q1 R3-T4: a seed read through the LISTING is recorded too (592767), not only one read as a seed",
          ref_state.get("seeds_read") == [592433, 592767] and sorted(ref_read) == [592433, 592767, 592907, 592933, 593067],
          f"{ref_state.get('seeds_read')} {ref_read}")

    with tempfile.TemporaryDirectory() as tmp:
        lane = _Lane(tmp, start)
        # Cycle 1: the request ceiling leaves nothing for any thread (592933 is not listed yet).
        res1, _c1, read1, seen1 = lane.cycle(without_592933, [(src, "Transport", robots_and_listings_only)])
        t1 = lane.clock.iso()
        owed1 = lane.owed()
        threads1 = lane.state()["threads"]
        check("Q2 cycle 1 (request ceiling): the 4 deferred threads are queued with their reason, the title-less "
              "seed and the never-read user topics included, and nothing was requested beyond the ceiling",
              set(owed1) == {"592767", "592433", "592907", "593067"} and not read1 and len(seen1) == 6
              and all(m["reason"] == "request_budget" and m["first_deferred_at"] == m["queued_at"] == t1
                      and m["times_deferred"] == 1 for m in owed1.values())
              and threads1["592433"]["title"] == "" and all(threads1[t]["last_activity"] is None for t in owed1),
              f"{owed1} {read1} {len(seen1)}")
        check("Q3 ...no row stored, and every version reads partial: a deferred seed whose title is not known "
              "yet counts for every version, 621.14 included",
              not lane.rows() and {(h["status"], h["blocked_reason"]) for h in _health(res1)}
              == {("partial", "threads_deferred_by_request_budget")}, str({h["status"] for h in _health(res1)}))
        # Cycle 2: the thread cap (0 here) defers all five; 592933 is listed now.
        _res2, _c2, read2, _s2 = lane.cycle(None, [(src, "MAX_THREADS_PER_CYCLE", 0)])
        t2 = lane.clock.iso()
        owed2 = lane.owed()
        check("Q4 cycle 2 (thread cap): the newcomer joins at the END (queued now); the four keep their place "
              "(queued in cycle 1), deferred twice, reason now thread_cap",
              set(owed2) == {"592767", "592433", "592907", "593067", "592933"} and not read2
              and owed2["592933"]["queued_at"] == owed2["592933"]["first_deferred_at"] == t2
              and all(owed2[t]["queued_at"] == owed2[t]["first_deferred_at"] == t1 and owed2[t]["times_deferred"] == 2
                      for t in ("592767", "592433", "592907", "593067"))
              and {m["reason"] for m in owed2.values()} == {"thread_cap"}, str(owed2))
        # Cycle 3: the time budget; and the listing shows none of them any more.
        lane.events.clear()
        res3, _c3, read3, _s3 = lane.cycle(none_listed, [(nf, "run_cycle", time_budget_spent)])
        owed3 = lane.owed()
        threads3 = lane.state()["threads"]
        check("Q5 cycle 3 (time budget, none of them listed any more): all five still queued, never read, "
              "no last activity, through the real retention prune",
              set(owed3) == set(owed2) and not read3 and {m["reason"] for m in owed3.values()} == {"runtime_budget"}
              and [owed3[t]["times_deferred"] for t in ("592767", "592433", "592907", "593067", "592933")]
              == [3, 3, 3, 3, 2] and all(threads3[t]["last_activity"] is None for t in owed3),
              str({t: (m["reason"], m["times_deferred"]) for t, m in owed3.items()}))
        note = f"Deferred-thread queue (whole forum): 5 waiting, oldest deferred {t1} (25 h ago)."
        event = [f for e, f in lane.events if e == "nvidia_forum_cycle"]
        check("Q6 queue depth and oldest deferred age are in EVERY health row's notes and in the runtime event",
              len(_health(res3)) == 4 and all(note in h["notes"] for h in _health(res3))
              and event and all(f.get("queue_depth") == 5 and f.get("queue_oldest_age_hours") == 25
                                and f.get("deferred") == 5 for f in event),
              f"{[h['notes'][-120:] for h in _health(res3)][:1]} {event[:1]}")
        # Cycles 4-6: a cap of 2, nothing listed: owed work is read longest-waiting first.
        cap2 = [(src, "MAX_THREADS_PER_CYCLE", 2)]
        res4, _c4, read4, _s4 = lane.cycle(none_listed, cap2)
        rows4 = lane.rows()
        state4 = lane.state()
        check("Q7 cycle 4 reads the two longest-waiting first (queued in cycle 1, staff thread then seed): "
              "592767, 592433; the other three stay queued in their place",
              read4 == [592767, 592433] and set(lane.owed()) == {"592907", "593067", "592933"}
              and all("deferred" not in state4["threads"][t] and state4["threads"][t]["window"]
                      for t in ("592767", "592433")), f"{read4} {sorted(lane.owed())}")
        check("Q8 ...the 9 reports are counted once they are read: 7 for 621.14, 2 for 621.24; both seeds recorded",
              sorted((r["update_version"], r["id"].rsplit("-", 1)[1]) for r in rows4 if r["counted"])
              == sorted([("621.14", str(c)) for c in (3633489, 3633451, 3633448, 3633356, 3633066, 3633062, 3633052)]
                        + [("621.24", "3634576"), ("621.24", "3634403")])
              and state4.get("seeds_read") == [592433, 592767],
              f"{len([r for r in rows4 if r['counted']])} {state4.get('seeds_read')}")
        h4 = {(h["product_id"], h["update_version"]): h for h in _health(res4)}
        check("Q9 ...621.14 (nothing of it deferred now) reads success; 621.24 (three of its threads still "
              "deferred) reads partial",
              h4[(GRD, "621.14")]["status"] == "success" and h4[(GRD, "621.24")]["status"] == "partial"
              and h4[(GRD, "621.24")]["blocked_reason"] == "threads_deferred_by_request_budget", str(h4)[:300])
        _r5, _c5, read5, _s5 = lane.cycle(none_listed, cap2)
        t5 = lane.clock.iso()
        _r6, c6, read6, _s6 = lane.cycle(none_listed, cap2)
        final = lane.state()
        owed6 = lane.owed()
        outcomes6 = {t["topic_id"]: t.get("outcome") for t in c6.get("threads", [])}
        check("Q10 cycles 5 and 6 read the rest in queue order (593067, 592907, then the later 592933); the two "
              "remembered feedback threads the cap of 2 pushed back in cycle 5 are owed in turn (592767 reached "
              "in cycle 6 and found unchanged, 592433 still waiting); nothing was invalidated",
              read5 == [593067, 592907] and read6 == [592933] and outcomes6.get(592767) == "unchanged"
              and set(owed6) == {"592433"} and owed6["592433"]["first_deferred_at"] == t5
              and owed6["592433"]["times_deferred"] == 2 and not final.get("deferred_invalidated"),
              f"{read5} {read6} {outcomes6} {owed6}")
        check("QP2 an owed thread read before (592433, with a window) counts in the queue depth",
              all(f"Deferred-thread queue (whole forum): 1 waiting, oldest deferred {t5}" in h["notes"]
                  for h in _health(_r6)), _health(_r6)[0]["notes"][-160:])
        rows = lane.rows()
        ids = [r["id"] for r in rows]
        added = sum(h.get("evidence_rows_added", 0) for res in lane.results for rr in res.values() for r in rr
                    for h in r["method_health"])
        dupes = sum(h.get("duplicate_existing_evidence", 0) for res in lane.results for rr in res.values()
                    for r in rr for h in r["method_health"])
        check("Q11 six cycles later the store holds exactly the rows and decisions of ONE unconstrained cycle: "
              "same ids, same counted/excluded and reasons, 9 counted, no id twice",
              _decision_map(rows) == reference and len(ids) == len(set(ids)) == len(reference)
              and sum(1 for c, _r in reference.values() if c) == 9,
              f"{len(rows)} vs {len(reference)}; diff={sorted(set(_decision_map(rows).items()) ^ set(reference.items()))[:3]}")
        check("Q12 ...and health credited each counted report once across the six cycles (9 added, 0 re-held)",
              added == 9 and dupes == 0, f"added={added} dupes={dupes}")
        _r7, _c7, _read7, _s7 = lane.cycle()
        check("Q13 a later cycle under the shipped cap empties the queue and stores nothing more (everything "
              "already held)", len(lane.rows()) == len(rows) and not lane.owed(),
              f"{len(lane.rows())} {sorted(lane.owed())}")

    # A thread unreadable (quarantined), a title that names no tracked version, a failed read, no record left.
    with tempfile.TemporaryDirectory() as tmp:
        lane = _Lane(tmp, start)
        lane.cycle(None, [(src, "MAX_THREADS_PER_CYCLE", 0)])
        ta = lane.clock.iso()
        renamed = copy.deepcopy(fixture("topic_592907.json"))
        renamed["data"]["topic"]["title"] = "Continuous writing to SSD, driver 999.99"
        broken = {(API, "/forums-api/1.0/topics", "593067"): lambda url: _respond(404, {"success": False}),
                  (API, "/forums-api/1.0/topics", "592933"): lambda url: _respond(503, b"busy", "text/plain"),
                  (API, "/forums-api/1.0/topics", "592907"): lambda url: _respond(200, renamed)}
        resb, _cb, readb, _sb = lane.cycle(broken)
        tb = lane.clock.iso()
        state_b = lane.state()
        log = {d["topic_id"]: d for d in state_b.get("deferred_invalidated") or []}
        check("Q14 a thread whose own topic view answers 404 is quarantined as thread_unreadable (GPT G62 R1): its "
              "identity and reason stay in the state file with when it was first deferred, and nothing is logged as "
              "invalidated",
              (state_b["threads"].get("593067") or {}).get("quarantined")
              == {"reason": "thread_unreadable", "detail": "HTTP 404", "at": tb, "first_deferred_at": ta,
                  "times_deferred": 1}
              and "deferred" not in state_b["threads"]["593067"] and 593067 not in log,
              str(state_b["threads"].get("593067")))
        check("Q15 a thread whose title now names no tracked version leaves as title_names_no_tracked_version",
              "592907" not in state_b["threads"] and (log.get(592907) or {}).get("reason") == "title_names_no_tracked_version",
              str(log.get(592907)))
        owed_b = lane.owed()
        check("Q16 a failed read (HTTP 503) is not an invalidation: still owed, reason thread_read_failed, sent to "
              "the end of the queue (queued now), its first deferral kept",
              set(owed_b) == {"592933"} and owed_b["592933"]["reason"] == "thread_read_failed"
              and owed_b["592933"]["queued_at"] == tb and owed_b["592933"]["first_deferred_at"] == ta
              and owed_b["592933"]["times_deferred"] == 2 and 592933 not in log, str(owed_b))
        check("Q17 the threads read left the queue as processed (window stored, no deferral, nothing logged)",
              sorted(readb) == [592433, 592767] and all("deferred" not in state_b["threads"][t]
                                                         and int(t) not in log for t in ("592433", "592767")),
              str(readb))
        check("Q18 the invalidation, the quarantine and the queue are in every health note of that cycle",
              all("1 deferred thread(s) invalidated this cycle: title_names_no_tracked_version." in h["notes"]
                  and "Quarantined, not read until a reviewed change releases them: 1 (thread_unreadable)." in h["notes"]
                  and "Deferred-thread queue (whole forum): 1 waiting" in h["notes"] for h in _health(resb)),
              _health(resb)[0]["notes"][-260:])
        check("QP1 the oldest deferral in the note is the FIRST deferral, not the requeue after a failed read",
              all(f"1 waiting, oldest deferred {ta} (12 h ago)." in h["notes"] for h in _health(resb)),
              _health(resb)[0]["notes"][-160:])
        only_1414 = {pid:[r for r in recs if r.update_version == "621.14"] for pid, recs in RECORDS.items()}
        _rc, _cc, _readc, seenc = lane.cycle(None, records=only_1414)
        state_c = lane.state()
        last = (state_c.get("deferred_invalidated") or [{}])[-1]
        check("Q19 no record left for the only version a queued thread names: it leaves as no_tracked_record, "
              "with no request for it",
              "592933" not in state_c["threads"] and last.get("topic_id") == 592933
              and last.get("reason") == "no_tracked_record" and not [u for u in seenc if "id=592933" in u],
              f"{last} {[u for u in seenc if '592933' in u]}")

    # A targeted run and a stop keep the queue.
    with tempfile.TemporaryDirectory() as tmp:
        lane = _Lane(tmp, start)
        lane.cycle(None, [(src, "MAX_THREADS_PER_CYCLE", 0)])
        before = lane.owed()
        _rt, _ct, readt, seent = lane.cycle(None, target={"621.14"})
        after = lane.owed()
        check("Q20 a run targeted at 621.14 reads only its own owed thread (the seed); the 621.24 threads stay "
              "queued untouched (no request, no invalidation)",
              readt == [592433] and set(after) == {"592767", "592907", "593067", "592933"}
              and all(after[t] == before[t] for t in after)
              and not [u for u in seent if any(f"id={t}" in u for t in after)], f"{readt} {sorted(after)}")
        threads_before = json.dumps(lane.state()["threads"], sort_keys=True)
        ress, _cs, _reads, _ss = lane.cycle({(API, "/robots.txt", None): lambda url: _respond(503, b"busy", "text/plain")})
        check("Q21 a cycle that stops keeps the queue exactly as it was, and its notes still report it",
              json.dumps(lane.state()["threads"], sort_keys=True) == threads_before
              and {h["status"] for h in _health(ress)} == {"blocked"}
              and all("Deferred-thread queue (whole forum): 4 waiting" in h["notes"] for h in _health(ress)),
              _health(ress)[0]["notes"][-160:])
        refused = lane.state()
        refused["access_refused"] = {"at": "2026-11-19T00:00:00Z", "detail": "HTTP 403"}
        lane.state_path.write_text(json.dumps(refused), encoding="utf-8")
        resr, _cr, _readr, seenr = lane.cycle()
        check("Q25 ...and so does a suspended cycle, which returns before any request",
              not seenr and {h["blocked_reason"] for h in _health(resr)} == {"access_refused"}
              and json.dumps(lane.state()["threads"], sort_keys=True) == threads_before
              and all("Deferred-thread queue (whole forum): 4 waiting" in h["notes"] for h in _health(resr)),
              _health(resr)[0]["notes"][-160:])

    # A seed whose FIRST read fails is not recorded as read (G61 R3-T4): the next cycle offers it again.
    with tempfile.TemporaryDirectory() as tmp:
        lane = _Lane(tmp, start)
        lane.cycle({(API, "/forums-api/1.0/topics", "592433"): lambda url: _respond(503, b"busy", "text/plain")})
        failed = lane.state()
        _rf, _cf, readf, _sf = lane.cycle()
        check("QP3 a seed whose first read fails is not recorded as read, and the next cycle reads it",
              592433 not in (failed.get("seeds_read") or []) and "592433" not in failed["threads"]
              and 592433 in readf, f"{failed.get('seeds_read')} {readf}")

    # The retention prune, directly, at a fractional second (production's clock always has one).
    now = datetime(2027, 3, 1, 0, 0, 0, 500000, tzinfo=timezone.utc)
    fresh = int((now - timedelta(days=1)).timestamp())
    stale = int((now - timedelta(days=60)).timestamp())
    marker = {"reason": "thread_cap", "first_deferred_at": "2027-01-01T00:00:00Z",
              "queued_at": "2027-01-01T00:00:00Z", "times_deferred": 9}
    windows = {str(1000 + i): {"title_versions": ["621.24"], "last_activity": fresh - i, "window": [[1, 1]]}
               for i in range(src.MAX_STATE_THREADS + 5)}
    owed_entries = {
        "1": {"title": "x 621.24", "title_versions": ["621.24"], "last_activity": None, "window": [],
              "deferred": dict(marker)},
        "2": {"title": "", "title_versions": [], "last_activity": None, "window": [], "deferred": dict(marker)},
        "3": {"title": "y 621.24", "title_versions": ["621.24"], "last_activity": stale, "window": [[5, 5]],
              "deferred": dict(marker)}}
    st = {"threads": {**windows, **owed_entries,
                      "4": {"title_versions": ["621.24"], "last_activity": stale, "window": [[6, 6]]}}}
    src.prune_threads(st, {"621.24"}, now)
    kept = st["threads"]
    check("Q22 the prune keeps every owed entry -- never read (no last activity), a title-less seed, one past "
          "the 45-day retention -- outside the 40-window cap, and still prunes a stale read window",
          {"1", "2", "3"} <= set(kept) and "4" not in kept and all(kept[t]["deferred"] == marker for t in "123")
          and len([t for t in kept if t not in owed_entries]) == src.MAX_STATE_THREADS,
          str(sorted(set(owed_entries) - set(kept))))
    small = {"threads": {"5": {"title_versions": ["621.24"], "last_activity": None, "window": []},
                         "6": {"title_versions": ["621.24"], "last_activity": fresh, "window": [[7, 7]]}}}
    src.prune_threads(small, {"621.24"}, now)
    horizon = (now - timedelta(days=src.THREAD_RETENTION_DAYS)).timestamp()
    check("Q23 ...and an entry never read is not dropped for lacking a last activity (the old "
          "int(None or horizon) >= horizon was False for every such entry at a fractional horizon)",
          set(small["threads"]) == {"5", "6"} and int(horizon) < horizon, str(sorted(small["threads"])))
    st_log = {"threads": {str(t): {"deferred": dict(marker)} for t in range(30)}}
    for t in range(30):
        nf._invalidate(st_log, {"at": "2027-03-01T00:00:00Z", "invalidated": []}, str(t), "no_tracked_record")
    check("Q24 the invalidation log keeps the last 20 (newest last); the queue itself has no cap",
          [d["topic_id"] for d in st_log["deferred_invalidated"]] == list(range(10, 30)) and not st_log["threads"],
          str(len(st_log.get("deferred_invalidated") or [])))


def _asked(seen: list[str], tid: int) -> list[str]:
    """The requests of a cycle that name this topic (its topic view or its comments view)."""
    return [u for u in seen if urllib.parse.urlsplit(u).path.startswith("/forums-api/1.0/topics")
            and urllib.parse.parse_qs(urllib.parse.urlsplit(u).query).get("id") == [str(tid)]]


def section_queued_failures() -> None:
    print("\n[QS] a queued thread's own failure cannot stop collection for every thread (GPT G62 R1)")
    topics = "/forums-api/1.0/topics"
    users = {592907, 593067, 592933}
    none_listed = {(API, "/forums-api/1.0/communities/topics", "13"): _listing("community13_topics.json", users),
                   (API, "/forums-api/1.0/communities/pinned", "13"): _listing("community13_pinned.json", {592767})}
    cap0 = [(src, "MAX_THREADS_PER_CYCLE", 0)]
    poison = 593067                          # a user topic: queued, never read, not listed when it fails
    others = [592433, 592767, 592907, 592933]

    def answer(status, body, ctype="application/json; charset=utf-8", headers=None):
        return lambda url: _respond(status, body, ctype, headers)
    success_false = answer(200, {"success": False, "errors": {"global": [{"message": "invalid"}]}})

    def poisoned(response):
        return {**none_listed, (API, topics, str(poison)): response}

    def counted(lane) -> int:
        return sum(1 for r in lane.rows() if r["counted"])

    def held(lane, tid=poison) -> dict:
        return (lane.state()["threads"].get(str(tid)) or {}).get("quarantined") or {}

    def outcomes(cyc) -> dict:
        return {t["topic_id"]: t.get("outcome") for t in cyc.get("threads", [])}

    start = datetime.now(timezone.utc).replace(microsecond=250000)
    with tempfile.TemporaryDirectory() as tmp:
        lane = _Lane(tmp, start)
        lane.cycle()
        reference = _decision_map(lane.rows())

    # Poisoned-thread progress, then the quarantine held, never pruned, released, and no evidence lost.
    with tempfile.TemporaryDirectory() as tmp:
        lane = _Lane(tmp, start)
        lane.cycle(None, cap0)
        t1 = lane.clock.iso()
        _rp, cycp, readp, _sp = lane.cycle(poisoned(success_false))
        tp = lane.clock.iso()
        state_p = lane.state()
        entry = state_p["threads"].get(str(poison)) or {}
        check("QS1 poisoned-thread progress: a queued, unlisted user topic answering success:false is quarantined "
              "(thread_invalid_response, with the time and its first deferral) and the SAME cycle reads the other four "
              "threads and keeps and counts their rows (9 counted); the cycle does not stop",
              not cycp.get("stop") and sorted(readp) == others
              and entry.get("quarantined") == {"reason": "thread_invalid_response", "detail": "success=false", "at": tp,
                                               "first_deferred_at": t1, "times_deferred": 1}
              and "deferred" not in entry and counted(lane) == 9 and not lane.owed(),
              f"stop={cycp.get('stop')} read={readp} held={entry.get('quarantined')} counted={counted(lane)}")
        lane.events.clear()
        resn, _cn, _readn, seenn = lane.cycle()
        note = "Quarantined, not read until a reviewed change releases them: 1 (thread_invalid_response)."
        events = [f for e, f in lane.events if e == "nvidia_forum_cycle"]
        check("QS2 ...and it is never selected again, not even while the listing shows it: no request for it, still "
              "quarantined as it was; the queue is empty, and every health note and the runtime event report the "
              "quarantine",
              not _asked(seenn, poison) and bool(held(lane)) and held(lane) == entry.get("quarantined") and not lane.owed()
              and all(note in h["notes"] and "Deferred-thread queue (whole forum): 0 waiting." in h["notes"]
                      for h in _health(resn))
              and events and all(f.get("quarantined") == 1 and f.get("queue_depth") == 0 for f in events),
              f"asked={_asked(seenn, poison)} {_health(resn)[0]['notes'][-200:]} {events[:1]}")
        only_1414 = {pid: [r for r in recs if r.update_version == "621.14"] for pid, recs in RECORDS.items()}
        lane.cycle(None, records=only_1414)
        state_3 = lane.state()
        check("QS3 ...never pruned and never invalidated: with no record left for the version its title names, the "
              "quarantined thread stays in the state file as it was, while the prune drops the 621.24 windows",
              bool(held(lane)) and held(lane) == entry.get("quarantined") and "592907" not in state_3["threads"]
              and not [d for d in state_3.get("deferred_invalidated") or [] if d.get("topic_id") == poison],
              f"{held(lane)} {sorted(state_3['threads'])}")
        release = ((poison, tp, "the topic answers again (checked by an operator)"),)
        _rr, cycr, readr, _sr = lane.cycle(none_listed, [(src, "QUARANTINE_RELEASES", release)])
        state_r = lane.state()
        check("QS4 release: a reviewed change naming the quarantine (topic id and its time) puts the thread back on the "
              "queue and logs the release with its reason; that same cycle reads it from the queue (not listed)",
              poison in readr and cycr.get("released") == [poison]
              and str(poison) in state_r["threads"]
              and not {"quarantined", "deferred"} & set(state_r["threads"].get(str(poison)) or {})
              and state_r.get("quarantine_released") == [
                  {"topic_id": poison, "quarantine_reason": "thread_invalid_response", "quarantined_at": tp,
                   "released_at": lane.clock.iso(), "reason": release[0][2]}],
              f"{readr} {cycr.get('released')} {state_r.get('quarantine_released')}")
        rows = lane.rows()
        ids = [r["id"] for r in rows]
        check("QS5 no evidence loss: the store ends with exactly the rows and decisions of one unconstrained cycle over "
              "the committed capture (same ids, same decisions, 9 counted, none twice)",
              _decision_map(rows) == reference and len(ids) == len(set(ids))
              and sum(1 for c, _r in reference.values() if c) == 9 == counted(lane),
              f"{len(rows)} vs {len(reference)}; "
              f"diff={sorted(set(_decision_map(rows).items()) ^ set(reference.items()))[:3]}")

    # Access refusals from a queued thread's own view: 401/403/451 hold it, 429 does not.
    for code in (401, 403, 451):
        with tempfile.TemporaryDirectory() as tmp:
            lane = _Lane(tmp, start)
            lane.cycle(None, cap0)
            t1 = lane.clock.iso()
            queued = lane.owed()
            resa, cyca, _ra, _sa = lane.cycle(poisoned(answer(code, b"Refused", "text/plain")))
            ta = lane.clock.iso()
            state_a = lane.state()
            hold = held(lane)
            stopped = (cyca.get("stop") == "access_refused" and {h["status"] for h in _health(resa)} == {"blocked"}
                       and "access_refused" in state_a and not lane.rows()
                       and hold == {"reason": "access_refused", "detail": f"HTTP {code}", "at": ta,
                                    "first_deferred_at": t1, "times_deferred": 1}
                       and lane.owed() == {t: m for t, m in queued.items() if t != str(poison)})
            cleared = (lane.clock.now + timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
            _rc, cycc, readc, seenc = lane.cycle(none_listed, [(src, "ACCESS_REFUSAL_CLEARED_AT", cleared)])
            check(f"QS6-{code} HTTP {code} from a queued thread's own view: the method stops and is suspended as before "
                  "(blocked, refusal persisted, no row) and the refused thread is quarantined for human disposition, the "
                  "rest of the queue untouched; once a reviewed change clears the refusal the method resumes, the refused "
                  "thread is NOT asked again, and the other threads are read and counted (9)",
                  stopped and not cycc.get("stop") and "access_refused" not in lane.state()
                  and not _asked(seenc, poison) and sorted(readc) == others and held(lane) == hold and counted(lane) == 9,
                  f"stopped={stopped} {cyca.get('stop')} {hold} next={cycc.get('stop')} read={readc}")
    with tempfile.TemporaryDirectory() as tmp:
        lane = _Lane(tmp, start)
        lane.cycle(None, cap0)
        before = json.dumps(lane.state()["threads"], sort_keys=True)
        _r9, cyc9, _read9, _s9 = lane.cycle(poisoned(answer(429, b"Too Many Requests", "text/plain")))
        state_9 = lane.state()
        cleared = (lane.clock.now + timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
        _rc, cycc, readc, _sc = lane.cycle(none_listed, [(src, "ACCESS_REFUSAL_CLEARED_AT", cleared)])
        check("QS7 HTTP 429 from a queued thread's own view: the method stops under the rate-limit rule (blocked, "
              "refusal persisted) and the thread stays queued exactly as it was, not quarantined; once the refusal is "
              "cleared it is read",
              cyc9.get("stop") == "access_refused" and "access_refused" in state_9
              and json.dumps(state_9["threads"], sort_keys=True) == before
              and not cycc.get("stop") and poison in readc and not lane.owed()
              and not any(src.is_quarantined(e) for e in lane.state()["threads"].values()),
              f"{cyc9.get('stop')} same_queue={json.dumps(state_9['threads'], sort_keys=True) == before} {readc}")
    with tempfile.TemporaryDirectory() as tmp:
        lane = _Lane(tmp, start)
        lane.cycle(None, cap0)
        _rh, cych, _readh, _sh = lane.cycle(poisoned(answer(200, b"<html><body>Topic unavailable</body></html>",
                                                             "text/html")))
        check("QS8 an HTML page where JSON was expected (the same access-refusal rule, with no status code) suspends the "
              "method as before and quarantines the refused queued thread too, so it cannot suspend it again after a "
              "clearing",
              cych.get("stop") == "access_refused" and "access_refused" in lane.state()
              and held(lane).get("reason") == "access_refused"
              and held(lane).get("detail") == "an HTML page was returned where JSON was expected",
              f"{cych.get('stop')} {held(lane)}")

    # A 5xx or a timeout keeps it owed, three cycles running, and never wedges the lane.
    def timeout(url):
        raise TimeoutError("timed out")
    with tempfile.TemporaryDirectory() as tmp:
        lane = _Lane(tmp, start)
        lane.cycle(None, cap0)
        t1 = lane.clock.iso()
        runs = []
        for failure in (answer(503, b"busy", "text/plain"), timeout, answer(502, b"bad gateway", "text/plain")):
            _res, cyc, _read, _seen = lane.cycle(poisoned(failure))
            marker = lane.owed().get(str(poison)) or {}
            runs.append((cyc.get("stop"), marker.get("reason"), marker.get("queued_at") == lane.clock.iso(),
                         marker.get("first_deferred_at") == t1, outcomes(cyc).get(poison), len(outcomes(cyc))))
        state_t = lane.state()
        check("QS9 a 5xx or a timeout from a queued thread, three cycles running (503, a timeout, 502): never a stop, "
              "never quarantined or invalidated; it stays queued (thread_read_failed, sent to the end, first deferral "
              "kept) while each cycle reaches the other threads, and all 9 counted reports are kept",
              all(r[0] == "" and r[1] == "thread_read_failed" and r[2] and r[3] and r[4] == "failed" and r[5] >= 3
                  for r in runs)
              and not any(src.is_quarantined(e) for e in state_t["threads"].values())
              and not state_t.get("deferred_invalidated") and counted(lane) == 9
              and (lane.owed().get(str(poison)) or {}).get("times_deferred") == 4, str(runs))

    # success:false is held only when confirmed as the thread's own.
    with tempfile.TemporaryDirectory() as tmp:
        lane = _Lane(tmp, start)
        lane.cycle(None, cap0)
        lane.cycle(poisoned(answer(503, b"busy", "text/plain")))           # the other four are read here
        _ru, cycu, readu, _su = lane.cycle(poisoned(success_false))
        marker = lane.owed().get(str(poison)) or {}
        check("QS10 an UNCONFIRMED success:false (no other thread read in full in that cycle: the two feedback threads "
              "were unchanged) holds nothing: the thread stays queued (thread_read_failed, sent to the end)",
              not cycu.get("stop") and not readu and set(outcomes(cycu).values()) == {"failed", "unchanged"}
              and marker.get("reason") == "thread_read_failed" and marker.get("queued_at") == lane.clock.iso()
              and not held(lane), f"{cycu.get('stop')} {outcomes(cycu)} {marker} {held(lane)}")
        newer = copy.deepcopy(fixture("topic_592433.json"))
        newer["data"]["topic"]["lastActivityStamp"] += 60
        _rk, _ck, readk, _sk = lane.cycle({**poisoned(success_false), (API, topics, "592433"): answer(200, newer)})
        check("QS11 ...and it is confirmed the next time another thread is read in full in the same cycle (592433, with "
              "new activity): then it is quarantined as thread_invalid_response",
              readk == [592433] and held(lane).get("reason") == "thread_invalid_response"
              and held(lane).get("at") == lane.clock.iso() and str(poison) not in lane.owed(),
              f"{readk} {held(lane)}")

    # Any other failure of its own views keeps it owed: never a stop, never classified as invalid.
    merged = copy.deepcopy(fixture("topic_592907.json"))       # another topic's answer, as after a merge
    shapes = (answer(200, merged),
              answer(302, b"", "text/html", {"Location": "https://forums-mirror.example.net/t/593067"}),
              answer(200, b"busy, try again later", "text/plain"))
    with tempfile.TemporaryDirectory() as tmp:
        lane = _Lane(tmp, start)
        lane.cycle(None, cap0)
        runs = []
        hosts: set[str] = set()
        for shape in shapes:
            _res, cyc, _read, seen = lane.cycle(poisoned(shape))
            marker = lane.owed().get(str(poison)) or {}
            runs.append((cyc.get("stop"), marker.get("reason"), marker.get("queued_at") == lane.clock.iso(),
                         outcomes(cyc).get(poison), len(outcomes(cyc))))
            hosts |= {urllib.parse.urlsplit(u).hostname or "" for u in seen}
        check("QS12 another shape from a queued thread's own view (another topic's id, as after a merge; a redirect, "
              "refused before the hop; a body that is not JSON), three cycles running: never a stop and never "
              "quarantined; it stays queued and goes to the end while each cycle reaches the other threads; nothing "
              "is sent to the redirect's host; all 9 counted reports are kept",
              all(r[0] == "" and r[1] == "thread_read_failed" and r[2] and r[3] == "failed" and r[4] >= 3 for r in runs)
              and "forums-mirror.example.net" not in hosts and not held(lane) and counted(lane) == 9, str(runs))

    # A listed thread and a seed never read keep the stops they had before the queue existed.
    with tempfile.TemporaryDirectory() as tmp:
        lane = _Lane(tmp, start)
        lane.cycle(None, cap0)
        before = json.dumps(lane.state()["threads"], sort_keys=True)
        _rl, cycl, _readl, _sl = lane.cycle({(API, topics, str(poison)): success_false})
        check("QS13 a queued thread the listing STILL shows keeps its stop: success:false is a schema stop (broken), "
              "nothing is quarantined, and the queue is kept exactly as it was",
              cycl.get("stop") == "schema_changed" and json.dumps(lane.state()["threads"], sort_keys=True) == before,
              f"{cycl.get('stop')} {held(lane)}")
        _rd, cycd, _readd, _sd = lane.cycle({**none_listed, (API, topics, "592433"): success_false})
        check("QS14 so does a seed never read (queued with its title unknown): success:false stops the cycle (broken), "
              "and the queue is kept exactly as it was",
              cycd.get("stop") == "schema_changed" and json.dumps(lane.state()["threads"], sort_keys=True) == before,
              f"{cycd.get('stop')} {held(lane, 592433)}")

    # HTTP 410: thread_unreadable, kept with its reason, never retried automatically.
    with tempfile.TemporaryDirectory() as tmp:
        lane = _Lane(tmp, start)
        lane.cycle(None, cap0)
        t1 = lane.clock.iso()
        lane.cycle(poisoned(answer(410, {"success": False})))
        tq = lane.clock.iso()
        hold = held(lane)
        _rn, _cn, _readn, seenn = lane.cycle()
        check("QS15 HTTP 410 from a queued thread's own view: thread_unreadable, its identity and reason kept in the "
              "state file; no automatic retry: the next cycle, whose listing shows it, sends no request for it",
              hold == {"reason": "thread_unreadable", "detail": "HTTP 410", "at": tq, "first_deferred_at": t1,
                       "times_deferred": 1}
              and held(lane) == hold and not _asked(seenn, poison), f"{hold} asked={_asked(seenn, poison)}")

    # A quarantine keeps the thread's identity and window: a thread READ before, then queued, then unreadable.
    with tempfile.TemporaryDirectory() as tmp:
        lane = _Lane(tmp, start)
        lane.cycle()
        lane.cycle(None, cap0)
        queued = copy.deepcopy(lane.state()["threads"]["592907"])
        lane.cycle({**none_listed, (API, topics, "592907"): answer(404, {"success": False})})
        entry = lane.state()["threads"].get("592907") or {}
        check("QS20 a quarantine keeps the thread's state entry as it was (title, community, versions, last activity, "
              "window), only its deferral replaced by the hold",
              bool(queued.get("window")) and src.is_owed(queued) and src.is_quarantined(entry)
              and {k: v for k, v in entry.items() if k != "quarantined"}
              == {k: v for k, v in queued.items() if k != "deferred"},
              f"{sorted(entry)} vs {sorted(queued)}")

    # A refusal of a queued thread the listing still shows, or of a seed never read, keeps its old stop.
    for tag, label, route in (
            ("listed", "a queued thread the listing still shows",
             {(API, topics, str(poison)): answer(403, b"Refused", "text/plain")}),
            ("seed", "a seed never read", {**none_listed, (API, topics, "592433"): answer(403, b"Refused", "text/plain")})):
        with tempfile.TemporaryDirectory() as tmp:
            lane = _Lane(tmp, start)
            lane.cycle(None, cap0)
            before = json.dumps(lane.state()["threads"], sort_keys=True)
            _rr, cycr, _readr, _sr = lane.cycle(route)
            state_r = lane.state()
            check(f"QS21-{tag} HTTP 403 from {label} keeps its old stop: the method is suspended (refusal persisted), "
                  "nothing is quarantined, and the queue is kept exactly as it was",
                  cycr.get("stop") == "access_refused" and "access_refused" in state_r
                  and json.dumps(state_r["threads"], sort_keys=True) == before
                  and not any(src.is_quarantined(e) for e in state_r["threads"].values()),
                  f"{cycr.get('stop')} {[t for t, e in state_r['threads'].items() if src.is_quarantined(e)]}")

    # Never a timer: with no release in code, a quarantine outlives any horizon.
    with tempfile.TemporaryDirectory() as tmp:
        lane = _Lane(tmp, start)
        lane.cycle(None, cap0)
        lane.cycle(poisoned(success_false))
        hold = held(lane)
        asks = []
        for days in (2, 30, 400):
            lane.clock.now += timedelta(days=days)
            _rt, _ct, _readt, seent = lane.cycle()
            asks += _asked(seent, poison)
        check("QS22 never a timer: with no release in code, the quarantine is unchanged and the thread is never asked "
              "2, 30 and 400 days later (while listed), and no release is logged",
              bool(hold) and held(lane) == hold and not asks and not lane.state().get("quarantine_released"),
              f"{held(lane)} asked={asks}")

    # The prune and the release path, directly.
    now = datetime(2027, 3, 1, 0, 0, 0, 500000, tzinfo=timezone.utc)
    fresh = int((now - timedelta(days=1)).timestamp())
    stale = int((now - timedelta(days=60)).timestamp())
    hold = {"reason": "thread_unreadable", "detail": "HTTP 404", "at": "2027-01-02T00:00:00Z",
            "first_deferred_at": "2027-01-01T00:00:00Z", "times_deferred": 2}
    windows = {str(1000 + i): {"title_versions": ["621.24"], "last_activity": fresh - i, "window": [[1, 1]]}
               for i in range(src.MAX_STATE_THREADS + 5)}
    held_entries = {
        "7": {"title": "x 621.24", "title_versions": ["621.24"], "last_activity": stale, "window": [[5, 5]],
              "quarantined": dict(hold)},
        "8": {"title": "y 999.99", "title_versions": ["999.99"], "last_activity": None, "window": [],
              "quarantined": dict(hold)},
        "9": {"title": "", "title_versions": [], "last_activity": None, "window": [], "quarantined": dict(hold)}}
    st = {"threads": {**windows, **held_entries}}
    src.prune_threads(st, {"621.24"}, now)
    check("QS16 the prune never removes a quarantined entry (past the retention, never read, naming only an untracked "
          "version, or untitled), and it takes no window's place under the 40-window cap",
          all((st["threads"].get(t) or {}).get("quarantined") == hold for t in held_entries)
          and len([t for t in st["threads"] if t not in held_entries]) == src.MAX_STATE_THREADS,
          str(sorted(set(held_entries) - set(st["threads"]))))
    queued_marker = {"reason": "thread_cap", "first_deferred_at": "2027-01-01T00:00:00Z",
                     "queued_at": "2027-01-01T00:00:00Z", "times_deferred": 1}
    rel = {"threads": {"5": {"title": "x 621.24", "quarantined": {**hold, "reason": "thread_invalid_response",
                                                                  "detail": "success=false", "times_deferred": 3}},
                       "6": {"title": "y 621.24", "deferred": dict(queued_marker)}}}
    before = json.dumps(rel, sort_keys=True)
    at = "2027-02-01T00:00:00Z"
    other_time = src.release_quarantined(rel, 5, "2027-01-03T00:00:00Z", "operator", at)
    only_queued = src.release_quarantined(rel, 6, "2027-01-02T00:00:00Z", "operator", at)
    unknown = src.release_quarantined(rel, 4, "2027-01-02T00:00:00Z", "operator", at)
    try:
        src.release_quarantined(rel, 5, "2027-01-02T00:00:00Z", "   ", at)
        no_reason = False
    except ValueError:
        no_reason = True
    untouched = json.dumps(rel, sort_keys=True) == before
    released = src.release_quarantined(rel, 5, "2027-01-02T00:00:00Z", "checked by an operator", at)
    twice = src.release_quarantined(rel, 5, "2027-01-02T00:00:00Z", "checked by an operator", at)
    check("QS17 release_quarantined releases only the quarantine it names: another time, a thread that is only queued "
          "or an unknown id change nothing, and a release without a reason is refused; the named thread goes back to "
          "the END of the queue (queued at the release) with its first deferral and count kept, the release logged "
          "with its reason; the same entry does not release it twice",
          not other_time and not only_queued and not unknown and no_reason and untouched and released and not twice
          and rel["threads"]["5"].get("deferred") == {"reason": "quarantine_released",
                                                      "first_deferred_at": "2027-01-01T00:00:00Z",
                                                      "queued_at": at, "times_deferred": 3}
          and "quarantined" not in rel["threads"]["5"] and rel["threads"]["6"]["deferred"] == queued_marker
          and rel.get("quarantine_released") == [
              {"topic_id": 5, "quarantine_reason": "thread_invalid_response", "quarantined_at": "2027-01-02T00:00:00Z",
               "released_at": at, "reason": "checked by an operator"}],
          f"{other_time} {only_queued} {unknown} {no_reason} {untouched} {released} {twice} {rel}")
    many = {"threads": {str(t): {"quarantined": {**hold, "at": f"2027-01-02T00:00:{t:02d}Z"}} for t in range(30)}}
    for t in range(30):
        src.release_quarantined(many, t, f"2027-01-02T00:00:{t:02d}Z", "operator", at)
    check("QS18 the release log keeps the last 20 (newest last); every released thread is queued again",
          [d["topic_id"] for d in many["quarantine_released"]] == list(range(10, 30))
          and all(src.is_owed(e) and not src.is_quarantined(e) for e in many["threads"].values()),
          str(len(many.get("quarantine_released") or [])))
    check("QS19 the shipped release list is empty (only a reviewed change names a quarantine to release)",
          src.QUARANTINE_RELEASES == ())


def run() -> int:
    print("=" * 74)
    print("NVIDIA GeForce forum evidence (default views, both driver families)")
    print("=" * 74)
    results = section_fixture()
    section_identity()
    section_gap()
    section_stops()
    section_wiring(results)
    section_moved_comment()
    section_title_names()
    section_deferred_queue()
    section_queued_failures()
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
