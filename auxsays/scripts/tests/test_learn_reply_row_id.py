#!/usr/bin/env python3
"""A Microsoft Q&A reply to a PowerPoint question gets its own row id (AUX-083).

`patch_collectors.base.slug` keeps 96 characters. A Learn question URL already slugs to about that,
because its title slug is long, so the `#answer-<id>` anchor of a reply was cut off and the reply's row
id equalled its question's id (or a sibling reply's). The append guard refused it on id equality and
published the refusal as "already held". On one PowerPoint patch two accepted, counted, independently
authored replies were discarded that way on every run.

The repair is two separate things, and this suite pins both:

  * PowerPoint's row id uses `base.report_id_slot`: `slug(learn_report_key(url))` for a reply or a
    comment, `slug(url)` byte for byte for everything else. Teams -- the only caller of the base
    default id -- is deliberately NOT changed (deferred: no new Teams rows).
  * The append guard names an id-only collision (`out_id_collision`; health field
    `id_collision_refused`) instead of calling a report the store never had "already held". What is
    refused is unchanged.

  A  the slot: reply and comment get their own slot; every question and every non-Learn URL keeps
     `slug(url)` byte for byte
  B  PowerPoint row ids through the shipped `row_from_candidate`, in every headroom regime
  C  the append guard stores PowerPoint replies, keeps a legacy truncated-id reply held, writes nothing
     on a re-find
  D  the id-only collision outcome (PowerPoint and Teams) and the readings it must not take over
  E  Teams: default ids byte-identical, and the real collector stores no new row but reports the
     collision
  F  method-health telemetry: the field, its absence, its round trip, its validator, its attribution
  G  the orchestrator: independent replies harvested from a thread are stored, counted and re-held;
     and with the old id the same run reports a collision, not "already held"
  H  every other collector that appends forwards the new outcome
  I  the write-authority validator accepts the batch the guard stored
  J  the bare-script entry points run as subprocesses under a network fence
  K  this suite touched no network and no real data

Frozen synthetic fixtures only: question ids 750000x, answer ids 7500001x, invented titles and texts,
no stored row, no live total. Network is refused in-process before any collector is imported, and every
subprocess runs under a sitecustomize fence that refuses non-loopback DNS/TCP and records attempts.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_learn_reply_row_id.py
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import os
import socket
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]          # auxsays/
SCRIPTS = ROOT / "scripts"
REPO = ROOT.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# ---- network refusal, installed before any collector module is imported --------------------------
ATTEMPTS = [0]


class _NoNetSocket(socket.socket):
    def connect(self, *args, **kwargs):          # noqa: D102
        ATTEMPTS[0] += 1
        raise OSError("network refused by test_learn_reply_row_id")

    def connect_ex(self, *args, **kwargs):       # noqa: D102
        ATTEMPTS[0] += 1
        raise OSError("network refused by test_learn_reply_row_id")


def _no_dns(*args, **kwargs):
    ATTEMPTS[0] += 1
    raise OSError("DNS refused by test_learn_reply_row_id")


socket.socket = _NoNetSocket                     # type: ignore[misc]
socket.getaddrinfo = _no_dns                     # type: ignore[assignment]

import yaml                                                              # noqa: E402

import orchestrate_evidence_run as orch                                  # noqa: E402
import validate_evidence_method_health as vmh                            # noqa: E402
from lib import collector_ownership as co                                # noqa: E402
from lib import source_segments as ss                                    # noqa: E402
from lib.orchestration import OrchestrationState                         # noqa: E402
from patch_collectors import base                                        # noqa: E402
from patch_collectors import microsoft_powerpoint as ppt                 # noqa: E402
from patch_collectors import microsoft_teams as teams                    # noqa: E402

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
        print(f"  FAIL  {label}" + (f"  -- {detail}" if detail else ""))


# ---- frozen synthetic fixtures -------------------------------------------------------------------
QA = "https://learn.microsoft.com/en-us/answers/questions"
PPT = "microsoft-powerpoint"
TEAMS = "microsoft-teams"
SRC = "microsoft_learn_qna"
VER, BUILD = "2608", "20000.20100"
PKEY = f"{PPT}|{VER}|{BUILD}"
TEAMS_VER = "25200.1000.0000.0001"
CAPTURED = "2026-08-20T00:00:00Z"

# One thread per headroom regime, h = 96 - len(slug(question url)) (sanity-checked in A0):
#   A h <= 1     the reply id equals the question id
#   B 2..8       every reply of the thread shares one id
#   C 9..15      replies whose ids share the first h-8 digits collide
#   D >= 16      distinct even before the repair
THREADS = {
    "A": ("7500001", "powerpoint-closes-when-exporting-a-deck-to-pdf-after-the-june-feature-update"),
    "B": ("7500003", "powerpoint-hangs-on-save-as-pdf"),
    "C": ("7500006", "powerpoint-hangs-on-save"),
    "D": ("7500004", "powerpoint-crash"),
}
A1, A2, C1 = "75000011", "75000012", "75000013"   # sequential, as Learn answer ids are


def q(regime: str, frag: str = "", locale: str = "en-us/") -> str:
    qid, title = THREADS[regime]
    return f"https://learn.microsoft.com/{locale}answers/questions/{qid}/{title}" + (f"#{frag}" if frag else "")


def headroom(url: str) -> int:
    import re
    return 96 - len(re.sub(r"[^a-z0-9]+", "-", url.lower()).strip("-"))


def legacy_id(product: str, version: str, url: str, source_type: str = SRC) -> str:
    """The id every builder produced before AUX-083: `slug(url)` in the URL slot."""
    return f"{product}-{base.slug(version)}-{base.slug(source_type)}-{base.slug(url)}"


REPORT_TEXT = f"PowerPoint crashes on open every time since Version {VER} (Build {BUILD})."
REC = base.PatchRecord(PPT, VER, Path("p.md"), "2026-08-01", "current", "Microsoft PowerPoint", BUILD)
TARGET = {"update_version": VER, "target_build": BUILD, "target_release_date": "2026-08-01",
          "version_ambiguous": False}


def ppt_row(url: str, *, text: str = REPORT_TEXT, source_type: str = SRC) -> dict:
    cand = {"source_type": source_type, "source_name": "synthetic", "source_url": url,
            "parent_title": "PowerPoint crash", "report_title": "", "report_text": text,
            "source_date": "2026-08-12"}
    return ppt.row_from_candidate(REC, TARGET, cand, CAPTURED)


TEAMS_REC = SimpleNamespace(update_version=TEAMS_VER, update_published_at="2026-08-01T00:00:00Z")


def teams_cand(url: str, segment_type: str = "answer", text: str = "Same here since the update.") -> dict:
    return {"segment_type": segment_type, "source_type": SRC, "source_name": "Microsoft Q&A",
            "source_url": url, "parent_title": "Teams crash", "report_title": "",
            "report_text": text, "source_date": "2026-08-12",
            "discovery_method": teams.QNA_METHOD_ID}


def teams_row(url: str, segment_type: str = "answer") -> dict:
    return teams.evaluate_candidate(TEAMS_REC, teams_cand(url, segment_type), CAPTURED)


def health(method_id: str, accepted: int, rejected: int = 0, *, product: str = PPT,
           version: str = VER, build: str = BUILD) -> dict:
    return base.method_health_row(
        product_id=product, update_version=version, target_build=build, method_id=method_id,
        source_type=SRC, status="success", candidates_found=accepted + rejected,
        accepted_reports=accepted, rejected_reports=rejected, blocked_reason="",
        last_run="2026-08-20T00:00:00Z", notes="fixture")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fresh_store(tmp: Path, name: str, rows: list[dict]) -> Path:
    path = tmp / name
    base.write_evidence_file([], path)
    if rows:
        base.append_evidence_rows(rows, path)
    return path


def append(rows: list[dict], path: Path) -> tuple[int, list, list, list]:
    added_rows: list = []
    held: list = []
    collided: list = []
    added, _total, _ = base.append_evidence_rows(rows, path, out_added=added_rows,
                                                 out_already_held=held, out_id_collision=collided)
    return added, added_rows, held, collided


NON_LEARN = [
    "https://community.adobe.com/t5/premiere-pro-bugs/export-hangs-at-99-percent-after-update/idi-p/7500090",
    "https://techcommunity.microsoft.com/discussions/microsoftteams/teams-crashes-on-join/7500091",
    "https://obsproject.com/forum/threads/obs-crashes-on-start-after-update.7500092/",
    "https://www.reddit.com/r/PowerPoint/comments/7500093/slides_vanish_after_the_june_update/",
    "https://github.com/OfficeDev/office-js/issues/7500094",
    "https://superuser.com/questions/7500095/powerpoint-freezes-when-exporting",
    "https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=7500096",
    "https://learn.microsoft.com/en-us/windows/release-health/status-windows-11-25h2",
    "https://learn.microsoft.com/en-us/answers/a/7500097",
    q("A", "comments"),
    "",
]


# ---- A: the slot ---------------------------------------------------------------------------------
def part_a() -> None:
    print("A  the id slot")
    regimes = {r: headroom(q(r)) for r in THREADS}
    check("A0 fixture sanity: the four threads sit in regimes A, B, C and D",
          regimes["A"] <= 1 and 2 <= regimes["B"] <= 8 and 9 <= regimes["C"] <= 15 and regimes["D"] >= 16,
          str(regimes))
    qid = THREADS["A"][0]
    check("A1 a Learn #answer- reply gets the short canonical slot",
          base.report_id_slot(q("A", f"answer-{A1}")) == f"learn-{qid}-reply-{A1}",
          base.report_id_slot(q("A", f"answer-{A1}")))
    check("A2 a Learn #comment- gets its OWN slot, not the question's and not a reply's",
          base.report_id_slot(q("A", f"comment-{C1}")) == f"learn-{qid}-comment-{C1}",
          base.report_id_slot(q("A", f"comment-{C1}")))
    slots = {base.report_id_slot(q(r, f"answer-{a}")) for r in THREADS for a in (A1, A2)}
    check("A3 two replies of every thread, in every regime, get eight distinct slots", len(slots) == 8,
          str(sorted(slots)))
    questions = [q(r) for r in THREADS] + [q("A", locale=""), q("A") + "/", q("A").replace("https:", "http:"),
                                           q("A").upper(), q("A") + "?page=2"]
    moved = [u for u in questions if base.report_id_slot(u) != base.slug(u)]
    check("A4 every question URL keeps slug(url) byte for byte (locale, slash, scheme, case, query)",
          not moved, str(moved))
    moved = [u for u in NON_LEARN if base.report_id_slot(u) != base.slug(u)]
    check("A5 every non-Learn URL (Adobe, Tech Community, OBS, Reddit, GitHub, Stack Exchange, Blackmagic, "
          "a Learn docs page, a Learn short link, an unknown fragment, empty) keeps slug(url)", not moved, str(moved))
    long_reply = q("A", "answer-" + "9" * 40)
    check("A6 a reply slot stays inside the id budget and is stable",
          len(base.report_id_slot(long_reply)) <= 96
          and base.report_id_slot(long_reply) == base.report_id_slot(long_reply))


# ---- B: PowerPoint row ids ------------------------------------------------------------------------
def part_b() -> None:
    print("B  PowerPoint row ids through row_from_candidate")
    rows = {r: ppt_row(q(r)) for r in THREADS}
    check("B0 control: the synthetic question passes the unchanged authority (counted, exact build)",
          all(row.get("counted") is True and row.get("target_build") == BUILD for row in rows.values()),
          str({r: row.get("exclusion_reason") for r, row in rows.items()}))
    moved = [r for r, row in rows.items() if row["id"] != legacy_id(PPT, VER, q(r))]
    check("B1 a PowerPoint question's id is byte-identical to the pre-AUX-083 id in every regime",
          not moved, str(moved))
    others = [("stack_exchange_question", NON_LEARN[5]), ("github_officedev_issue", NON_LEARN[4]),
              ("microsoft_tech_community", NON_LEARN[1]), ("reddit_community_report", NON_LEARN[3])]
    moved = [st for st, url in others if ppt_row(url, source_type=st)["id"] != legacy_id(PPT, VER, url, st)]
    check("B2 a PowerPoint row from every non-Learn family keeps its id byte for byte", not moved, str(moved))
    reply = ppt_row(q("A", f"answer-{A1}"))
    qid = THREADS["A"][0]
    check("B3 a PowerPoint reply on a regime-A thread gets its own id, not its question's",
          reply["id"] == f"{PPT}-{VER}-microsoft-learn-qna-learn-{qid}-reply-{A1}"
          and reply["id"] != rows["A"]["id"], reply["id"])
    comment = ppt_row(q("A", f"comment-{C1}"))
    check("B4 a PowerPoint comment gets the comment slot",
          comment["id"] == f"{PPT}-{VER}-microsoft-learn-qna-learn-{qid}-comment-{C1}", comment["id"])
    for regime in ("B", "C"):
        one, two = ppt_row(q(regime, f"answer-{A1}")), ppt_row(q(regime, f"answer-{A2}"))
        check(f"B5{regime} two PowerPoint replies of a regime-{regime} thread get distinct ids",
              one["id"] != two["id"], one["id"])


# ---- C: the guard stores PowerPoint replies --------------------------------------------------------
def part_c(tmp: Path) -> None:
    print("C  the append guard and PowerPoint replies")
    question = ppt_row(q("A"))
    store = fresh_store(tmp, "c_held.yml", [question])
    reply = ppt_row(q("A", f"answer-{A1}"))
    added, added_rows, held, collided = append([reply], store)
    stored = base.load_evidence(store)
    check("C1 an independent reply on a HELD long-slug question is stored",
          added == 1 and [r["source_url"] for r in added_rows] == [q("A", f"answer-{A1}")], f"{added}")
    check("C2 ...it is not reported as already held, and it is no collision", not held and not collided,
          f"held={len(held)} collided={len(collided)}")
    check("C3 ...the question is not duplicated",
          sum(1 for r in stored if base.report_url_key(r["source_url"]) == ss.learn_report_key(q("A"))) == 1)
    check("C4 ...and the patch now counts both (1 -> 2)",
          len(base.counted_rows(stored, PPT, VER)) == 2, str(len(base.counted_rows(stored, PPT, VER))))

    store = fresh_store(tmp, "c_unheld.yml", [])
    added, _rows, held, collided = append(
        [ppt_row(q("A", f"answer-{A1}")), ppt_row(q("A", f"answer-{A2}"))], store)
    check("C5 two independent replies on an UNHELD long-slug thread are both stored",
          added == 2 and not held and not collided, f"{added} {len(held)} {len(collided)}")
    before = store.read_bytes()
    added, _rows, held, collided = append(
        [ppt_row(q("A", f"answer-{A1}")), ppt_row(q("A", f"answer-{A2}"))], store)
    check("C6 re-finding them adds nothing, holds both, and writes no byte",
          added == 0 and len(held) == 2 and not collided and store.read_bytes() == before,
          f"{added} {len(held)} {len(collided)}")

    # A reply stored under the OLD truncated id (regime D, where the old id was distinct) is re-found
    # under the new id: the URL slot already separates anchors, so it is held -- never a second row.
    legacy_reply = dict(ppt_row(q("D", f"answer-{A1}")), id=legacy_id(PPT, VER, q("D", f"answer-{A1}")))
    store = fresh_store(tmp, "c_legacy.yml", [legacy_reply])
    before = store.read_bytes()
    refound = ppt_row(q("D", f"answer-{A1}"))
    added, _rows, held, collided = append([refound], store)
    check("C7 fixture sanity: the re-found reply's id differs from the legacy stored id",
          refound["id"] != legacy_reply["id"], refound["id"])
    check("C8 a legacy truncated-id reply re-found under its new id is held, with the store bytes unchanged",
          added == 0 and len(held) == 1 and not collided and store.read_bytes() == before,
          f"{added} {len(held)} {len(collided)}")
    added, _rows, held, _c = append([ppt_row(q("D", f"answer-{A1}", locale=""))], store)
    check("C9 ...and so is the same reply re-found under another URL spelling (no locale)",
          added == 0 and len(held) == 1 and store.read_bytes() == before, f"{added} {len(held)}")


# ---- D: the id-only collision outcome -------------------------------------------------------------
def part_d(tmp: Path) -> None:
    print("D  an id-only collision is its own outcome")
    question = ppt_row(q("A"))
    store = fresh_store(tmp, "d_ppt.yml", [question])
    before = store.read_bytes()
    old_reply = dict(ppt_row(q("A", f"answer-{A1}")), id=legacy_id(PPT, VER, q("A", f"answer-{A1}")))
    check("D0 fixture sanity: the old reply id equals the held question's id (the AUX-083 defect)",
          old_reply["id"] == question["id"])
    added, _rows, held, collided = append([old_reply], store)
    check("D1 PowerPoint: a reply refused only by id is reported as an id collision",
          added == 0 and [r["source_url"] for r in collided] == [q("A", f"answer-{A1}")],
          f"{added} {len(collided)}")
    check("D2 ...and NOT as already held", not held, str(len(held)))
    check("D3 ...and it is still refused: the store bytes are unchanged", store.read_bytes() == before)

    store = fresh_store(tmp, "d_batch.yml", [])
    one = dict(ppt_row(q("B", f"answer-{A1}")), id=legacy_id(PPT, VER, q("B", f"answer-{A1}")))
    two = dict(ppt_row(q("B", f"answer-{A2}")), id=legacy_id(PPT, VER, q("B", f"answer-{A2}")))
    added, _rows, held, collided = append([one, two], store)
    check("D4 an id-only collision with an EARLIER row of the same batch is reported too, never as held",
          one["id"] == two["id"] and added == 1 and len(collided) == 1 and not held,
          f"{added} {len(collided)} {len(held)}")

    store = fresh_store(tmp, "d_url.yml", [question])
    added, _rows, held, collided = append([dict(question, id="microsoft-powerpoint-a-new-label")], store)
    check("D5 control: a report whose URL key is held is still 'already held', not a collision",
          added == 0 and len(held) == 1 and not collided, f"{len(held)} {len(collided)}")
    card = dict(question, id="card-7500001-1", match_basis="embedded_listing_report_card",
                source_url="https://community.example.invalid/listing")
    store = fresh_store(tmp, "d_card.yml", [card])
    added, _rows, held, collided = append(
        [dict(card, source_url="https://community.example.invalid/listing?page=2")], store)
    check("D6 control: a listing card re-found by its id keeps the historical 'already held' reading",
          added == 0 and len(held) == 1 and not collided, f"{len(held)} {len(collided)}")
    blank = dict(question, id="microsoft-powerpoint-row-without-a-url", source_url="")
    store = fresh_store(tmp, "d_blank.yml", [blank])
    added, _rows, held, collided = append([dict(blank)], store)
    check("D6b control: a row with no URL re-found by its id keeps the historical 'already held' reading",
          added == 0 and len(held) == 1 and not collided, f"{len(held)} {len(collided)}")
    store = fresh_store(tmp, "d_twin.yml", [])
    added, _rows, held, collided = append([question, dict(question, id="microsoft-powerpoint-twin")], store)
    check("D7 control: an in-batch duplicate of the same report is neither held nor a collision",
          added == 1 and not held and not collided, f"{len(held)} {len(collided)}")

    # Teams, unchanged ids: its reply on a held long-slug question is refused by id equality.
    t_question = teams_row(q("A"), "question")
    store = fresh_store(tmp, "d_teams.yml", [t_question])
    before = store.read_bytes()
    added, _rows, held, collided = append([teams_row(q("A", f"answer-{A1}"))], store)
    check("D8 Teams: a reply refused only by id is reported as an id collision, not as already held",
          added == 0 and len(collided) == 1 and not held, f"{added} {len(collided)} {len(held)}")
    check("D9 Teams: ...and stays refused (no new Teams row)", store.read_bytes() == before)


# ---- E: Teams ------------------------------------------------------------------------------------
def part_e(tmp: Path) -> None:
    print("E  Teams ids and the Teams collector")
    urls = [q(r, f"answer-{a}") for r in THREADS for a in (A1, A2)] + [q(r) for r in THREADS]
    moved = [u for u in urls
             if teams_row(u, "answer" if "#" in u else "question")["id"] != legacy_id(TEAMS, TEAMS_VER, u)]
    check("E1 every Teams row id (questions and replies, all four regimes) is byte-identical to before",
          not moved, str(moved[:2]))
    check("E2 control: a Teams regime-A reply still takes its question's id (the deferred defect)",
          teams_row(q("A", f"answer-{A1}"))["id"] == teams_row(q("A"), "question")["id"])

    # The REAL collector loop, discovery stubbed and the append pointed at a temporary store.
    question = teams_row(q("A"), "question")
    store = fresh_store(tmp, "e_teams.yml", [question])
    before = store.read_bytes()
    cands = [teams_cand(q("A"), "question", "Teams closes when I join a meeting."),
             teams_cand(q("A", f"answer-{A1}")), teams_cand(q("A", f"answer-{A2}"))]
    record = base.PatchRecord(TEAMS, TEAMS_VER, Path("t.md"), "2026-08-01T00:00:00Z", "current",
                              "Microsoft Teams")
    real = (base.generated_records, teams.discover_learn_qna, teams.discover_tech_community,
            teams.budget_expired, base.append_evidence_rows)
    real_append = base.append_evidence_rows
    base.generated_records = lambda *_a, **_k: [record]
    teams.discover_learn_qna = lambda _rec, _ctx, _errs, *a, **k: [dict(c) for c in cands]
    teams.discover_tech_community = lambda _ctx, _errs, *a, **k: []
    teams.budget_expired = lambda: False
    base.append_evidence_rows = lambda rows, path=None, **kw: real_append(rows, store, **kw)
    try:
        results = teams.TeamsCommunityCollector().collect(
            base.CollectorContext(write=True, since=None, max_pages=1))
    finally:
        (base.generated_records, teams.discover_learn_qna, teams.discover_tech_community,
         teams.budget_expired, base.append_evidence_rows) = real
    result = results[0] if results else {}
    qna = next((h for h in result.get("method_health") or [] if h.get("method_id") == teams.QNA_METHOD_ID), {})
    check("E3 control: the collector ran one record and accepted nothing (no consensus write)",
          len(results) == 1 and result.get("accepted_count") == 0 and result.get("rejected_count") == 3,
          str({k: result.get(k) for k in ("accepted_count", "rejected_count")}))
    check("E4 the Teams collector stores NO new row (the store bytes are unchanged)",
          result.get("evidence_rows_added") == 0 and store.read_bytes() == before,
          str(result.get("evidence_rows_added")))
    check("E5 its Q&A health row names the two id collisions instead of calling them held",
          qna.get(base.ID_COLLISION_FIELD) == 2 and qna.get("duplicate_existing_evidence") == 0,
          str({k: qna.get(k) for k in (base.ID_COLLISION_FIELD, "duplicate_existing_evidence",
                                       "accepted_candidates", "rejected_reports")}))


# ---- F: telemetry -----------------------------------------------------------------------------------
def part_f(tmp: Path) -> None:
    print("F  method-health telemetry")
    # The PowerPoint shape that was published for months: 3 accepted, the question held, 2 replies
    # refused by their truncated ids.
    question = ppt_row(q("A"))
    store = fresh_store(tmp, "f_ppt.yml", [question])
    old = [dict(ppt_row(q("A", f"answer-{a}")), id=legacy_id(PPT, VER, q("A", f"answer-{a}"))) for a in (A1, A2)]
    _added, added_rows, held, collided = append([question] + old, store)
    rows = [health("learn_qna_segment_context", 3)]
    base.finalize_method_health_delta(rows, added_rows, held, collided)
    row = rows[0]
    check("F1 the old-id PowerPoint run reports 1 held and 2 id collisions, not 3 held",
          row["duplicate_existing_evidence"] == 1 and row.get(base.ID_COLLISION_FIELD) == 2
          and row["evidence_rows_added"] == 0,
          str({k: row.get(k) for k in ("duplicate_existing_evidence", base.ID_COLLISION_FIELD)}))

    clean = [health("learn_qna_search_rss", 2)]
    base.finalize_method_health_delta(clean, [], [], [])
    check("F2 a row with no collision carries no new key: its keys are exactly the historical schema",
          tuple(clean[0]) == base.METHOD_HEALTH_FIELDS and tuple(base.normalize_method_health_row(clean[0]))
          == base.METHOD_HEALTH_FIELDS, str(tuple(clean[0])[-3:]))
    stale = dict(health("learn_qna_segment_context", 2), **{base.ID_COLLISION_FIELD: 4})
    base.finalize_method_health_delta([stale], [], [], [])
    check("F3 finalizing a row with no collision this run clears a stale value", base.ID_COLLISION_FIELD not in stale)

    path = tmp / "f_health.yml"
    base.write_method_health_file([row, clean[0]], path)
    loaded = base.load_method_health(path)
    check("F4 the field survives the writer's normalisation and a reload, LAST in key order",
          loaded[0].get(base.ID_COLLISION_FIELD) == 2 and list(loaded[0])[-1] == base.ID_COLLISION_FIELD
          and base.ID_COLLISION_FIELD not in loaded[1], str(list(loaded[0])[-2:]))
    # The validator prints its own "FAIL row ..." lines; they are captured, never echoed, because the
    # CI runner reads every printed FAIL line as one of this suite's checks.
    said = io.StringIO()
    with contextlib.redirect_stdout(said):
        accepted = vmh.validate(path)
    check("F5 the method-health validator accepts the file", accepted == 0, said.getvalue()[-200:])
    bad = tmp / "f_bad.yml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    payload["methods"][0][base.ID_COLLISION_FIELD] = -1
    bad.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    said = io.StringIO()
    with contextlib.redirect_stdout(said):
        refused = vmh.validate(bad)
    check("F6 ...and refuses a negative value, naming the field (it is really checked)",
          refused == 1 and f"field {base.ID_COLLISION_FIELD}: must be a nonnegative integer" in said.getvalue(),
          said.getvalue()[-200:])

    # Attribution inside one family: counted room first, then the rows a collector also appends
    # uncounted. A method that only REJECTED must not be credited with a counted row's collision.
    family = [health("learn_qna_search_rss", 0, 5), health("learn_qna_segment_context", 2)]
    base.finalize_method_health_delta(family, [], [], old)
    check("F7 a counted collision is credited to the method that accepted it, not to one that only rejected",
          family[1].get(base.ID_COLLISION_FIELD) == 2 and base.ID_COLLISION_FIELD not in family[0],
          f"{family[0].get(base.ID_COLLISION_FIELD)} {family[1].get(base.ID_COLLISION_FIELD)}")
    over = [health("learn_qna_segment_context", 1, 1)]
    base.finalize_method_health_delta(over, [], [], old + old)
    check("F8 no row claims more collisions than it accepted plus rejected",
          over[0].get(base.ID_COLLISION_FIELD) == 2, str(over[0].get(base.ID_COLLISION_FIELD)))


# ---- G: the orchestrator ----------------------------------------------------------------------------
PAGE = (
    '<html><head><script type="application/ld+json">{"@context":"https://schema.org",'
    '"@type":"QAPage","mainEntity":{"@type":"Question","id":"' + THREADS["A"][0] + '",'
    '"name":"PowerPoint crash","dateCreated":"2026-08-10T09:00:00Z",'
    '"text":"<p>PowerPoint closes when I open a deck.</p>","author":"Asker",'
    '"authorId":"aaaaaaaa-0000-4000-8000-000000000001","suggestedAnswer":['
    '{"@type":"Answer","id":"' + A1 + '","text":"<p>' + REPORT_TEXT + '</p>","author":"Replier One",'
    '"authorId":"bbbbbbbb-0000-4000-8000-000000000002","updatedAt":"2026-08-12T09:00:00Z"},'
    '{"@type":"Answer","id":"' + A2 + '","text":"<p>Same here. ' + REPORT_TEXT + '</p>","author":"Replier Two",'
    '"authorId":"cccccccc-0000-4000-8000-000000000003","updatedAt":"2026-08-13T09:00:00Z"}'
    ']}}</script></head><body></body></html>')


def orchestrated_run(store: Path, health_path: Path) -> tuple[OrchestrationState, list]:
    """resolve_context -> finalize_evidence on the SHIPPED Pipeline methods; fetch is a fixture."""
    state = OrchestrationState()
    state.method_results = [{
        "method_id": "learn_qna_search_rss", "patch_key": PKEY, "accepted_rows": [],
        "health_row": health("learn_qna_search_rss", 0, 1),
        "resolvable_rows": [{"source_url": q("A"), "exclusion_reason": "missing_exact_build",
                             "report_text": "PowerPoint closes when I open a deck.",
                             "parent_title": "PowerPoint crash", "report_title": "",
                             "source_date": "2026-08-10", "source_type": SRC,
                             "source_name": "Microsoft Learn Q&A"}]}]
    pipe = SimpleNamespace(_records={PKEY: REC}, _seen={PKEY: set()},
                           context_fetch=lambda _u: (PAGE, "ok"), context_max_fetches=4,
                           _persist_url_state=lambda *a, **k: None, write=True,
                           evidence_path=store, health_path=health_path,
                           _write_tier2=lambda *_a, **_k: None)
    orch.Pipeline.resolve_context(pipe, state)
    orch.Pipeline.finalize_evidence(pipe, state)
    return state, base.load_method_health(health_path)


def part_g(tmp: Path) -> None:
    print("G  the orchestrator: resolve_context -> finalize_evidence")
    question = ppt_row(q("A"))
    store = fresh_store(tmp, "g_store.yml", [question])
    hpath = tmp / "g_health.yml"
    count_before = len(base.counted_rows(base.load_evidence(store), PPT, VER))
    state, healths = orchestrated_run(store, hpath)
    ctx = next((r for r in state.method_results if r.get("method_id") == "learn_qna_segment_context"), {})
    independents = ctx.get("accepted_rows") or []
    check("G1 control: the thread yields two counted independent replies through the shipped authority",
          len(independents) == 2 and all(r.get("counted") is True for r in independents), str(len(independents)))
    qid = THREADS["A"][0]
    check("G2 their ids are the reply slots",
          sorted(r["id"] for r in independents)
          == [f"{PPT}-{VER}-microsoft-learn-qna-learn-{qid}-reply-{a}" for a in (A1, A2)],
          str([r.get("id") for r in independents]))
    stored = base.load_evidence(store)
    check("G3 the graph stores both, beside the held question (count 1 -> 3)",
          (state.evidence_changes or {}).get("added") == 2 and count_before == 1
          and len(base.counted_rows(stored, PPT, VER)) == 3,
          f"{state.evidence_changes} {count_before}")
    ctx_health = next((h for h in healths if h.get("method_id") == "learn_qna_segment_context"), {})
    check("G4 its health row says 2 stored, 0 held, no collision",
          ctx_health.get("evidence_rows_added") == 2 and ctx_health.get("duplicate_existing_evidence") == 0
          and base.ID_COLLISION_FIELD not in ctx_health, str(ctx_health))
    before = store.read_bytes()
    state, healths = orchestrated_run(store, tmp / "g_health_2.yml")
    ctx_health = next((h for h in healths if h.get("method_id") == "learn_qna_segment_context"), {})
    check("G5 the next run re-finds them: 0 stored, 2 held, the store bytes unchanged",
          (state.evidence_changes or {}).get("added") == 0 and store.read_bytes() == before
          and ctx_health.get("duplicate_existing_evidence") == 2, str(ctx_health))

    # The same graph with the OLD id slot: the run that was published for months.
    real_slot = ppt.report_id_slot
    ppt.report_id_slot = base.slug
    try:
        store = fresh_store(tmp, "g_old.yml", [question])
        before = store.read_bytes()
        state, healths = orchestrated_run(store, tmp / "g_health_old.yml")
    finally:
        ppt.report_id_slot = real_slot
    ctx_health = next((h for h in healths if h.get("method_id") == "learn_qna_segment_context"), {})
    check("G6 with the old id the graph stores nothing and its health names 2 id collisions, 0 held",
          store.read_bytes() == before and ctx_health.get(base.ID_COLLISION_FIELD) == 2
          and ctx_health.get("duplicate_existing_evidence") == 0, str(ctx_health))


# ---- H: wiring of the other collectors ----------------------------------------------------------------
def part_h() -> None:
    print("H  every other collector that appends forwards the new outcome")
    # The orchestrator and Teams are pinned by behaviour (G6, E5). These five are the collector-side
    # appends: the segment from the append call to the end of its finalize call must carry the sink
    # AND hand it on, or their health rows would silently drop the outcome again.
    for number, name in enumerate(("adobe_acrobat_community.py", "adobe_premiere.py", "davinci.py",
                                   "microsoft_windows.py", "microsoft_powerpoint.py"), start=1):
        src = (SCRIPTS / "patch_collectors" / name).read_text(encoding="utf-8")
        start = src.index("out_already_held=already_held")
        fin = src.index("finalize_method_health_delta(", start)
        segment = src[start:src.index(")", fin) + 1]
        check(f"H{number} {name} captures the id collisions and forwards them to the health rows",
              "out_id_collision=collided" in segment
              and segment.rstrip(")").rstrip().endswith("already_held, collided"), segment[-120:])


# ---- I: the write-authority validator ------------------------------------------------------------------
def part_i(tmp: Path) -> None:
    print("I  the write-authority validator accepts what the guard stored")
    question = ppt_row(q("A"))
    store = fresh_store(tmp, "i_store.yml", [question])
    before_text = store.read_text(encoding="utf-8")
    append([ppt_row(q("A", f"answer-{a}")) for a in (A1, A2)] + [ppt_row(q("A", f"comment-{C1}"))], store)
    after_text = store.read_text(encoding="utf-8")
    real = co._existing_patch_keys
    co._existing_patch_keys = lambda _pid: {(PPT, VER, BUILD)}
    try:
        code = ""
        try:
            co.validate_evidence(PPT, before_text, after_text)
        except co.OwnershipViolation as exc:
            code = str(getattr(exc, "code", "") or exc)
        check("I1 validate_evidence accepts the question, two replies and a comment", not code, code)
        old = dict(ppt_row(q("A", f"answer-{A1}")), id=question["id"])
        empty_text = yaml.safe_dump({"schema_version": 1, "evidence": []})
        dup_text = yaml.safe_dump({"schema_version": 1, "evidence": [question, old]})
        try:
            co.validate_evidence(PPT, empty_text, dup_text)
        except co.OwnershipViolation as exc:
            code = str(getattr(exc, "code", "") or exc)
        check("I2 control: the old truncated id appended behind the guard's back is a duplicate id to it",
              "evidence_duplicate_id" in code, code)
    finally:
        co._existing_patch_keys = real


# ---- J: bare-script entry points, fenced ----------------------------------------------------------
FENCE = r'''
import os, socket
_LOG = os.environ.get("AUX_TEST_NETFENCE_LOG", "")
def _note(kind, what):
    if _LOG:
        with open(_LOG, "a", encoding="utf-8") as fh:
            fh.write(kind + "\t" + str(os.getpid()) + "\t" + what + "\n")
def _loop(host):
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    host = str(host).strip().lower().strip("[]")
    return host in ("", "localhost", "::1", "0.0.0.0") or host.startswith("127.")
_oc, _ox, _og = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo
def _guard(sock, address):
    if getattr(sock, "family", None) not in (socket.AF_INET, socket.AF_INET6):
        return
    host = address[0] if isinstance(address, tuple) and address else address
    if not _loop(host):
        _note("ATTEMPT", "connect " + repr(host))
        raise OSError("fenced: non-loopback connect refused")
def _connect(self, address):
    _guard(self, address)
    return _oc(self, address)
def _connect_ex(self, address):
    _guard(self, address)
    return _ox(self, address)
def _gai(host, *a, **k):
    if not _loop(host):
        _note("ATTEMPT", "dns " + repr(host))
        raise socket.gaierror("fenced: DNS refused")
    return _og(host, *a, **k)
socket.socket.connect = _connect
socket.socket.connect_ex = _connect_ex
socket.getaddrinfo = _gai
_note("loaded", "fence")
'''


def part_j(tmp: Path) -> None:
    print("J  bare-script entry points run as subprocesses, network-fenced")
    fence_dir = tmp / "fence"
    fence_dir.mkdir()
    (fence_dir / "sitecustomize.py").write_text(FENCE, encoding="utf-8")
    log = tmp / "fence.log"
    env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY")}
    env.update({"PYTHONPATH": str(fence_dir), "AUX_TEST_NETFENCE_LOG": str(log),
                "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"})
    hfile = tmp / "j_health.yml"
    row = dict(health("learn_qna_segment_context", 3), **{base.ID_COLLISION_FIELD: 2})
    base.write_method_health_file([row], hfile)
    reply = q("A", f"answer-{A1}")
    runs = [
        ("J1 the orchestrator imports as a bare script",
         [sys.executable, str(SCRIPTS / "orchestrate_evidence_run.py"), "--help"], REPO, None),
        ("J2 the collection runner imports as a bare script",
         [sys.executable, str(SCRIPTS / "run_patch_evidence_collection.py"), "--help"], REPO, None),
        ("J3 the writeback entry point imports as a bare script",
         [sys.executable, str(SCRIPTS / "lib" / "automation_writeback.py"), "--help"], REPO, None),
        ("J4 the method-health validator, as a bare script, accepts a row carrying the new field",
         [sys.executable, str(SCRIPTS / "validate_evidence_method_health.py"), str(hfile)], REPO,
         lambda out: "validation passed" in out),
        ("J5 the collector base imports with only the scripts directory on its path",
         [sys.executable, "-c", "import patch_collectors.base as b; print(b.report_id_slot('" + reply + "'))"],
         SCRIPTS, lambda out: f"learn-{THREADS['A'][0]}-reply-{A1}" in out),
    ]
    for label, cmd, cwd, expect in runs:
        try:
            proc = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=300)
            ok = proc.returncode == 0 and (expect is None or expect(proc.stdout))
            detail = f"rc={proc.returncode} {proc.stderr.strip()[-300:]}"
        except subprocess.TimeoutExpired:
            ok, detail = False, "timeout"
        check(label, ok, detail)
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    loaded = sum(1 for ln in lines if ln.startswith("loaded"))
    attempts = [ln for ln in lines if ln.startswith("ATTEMPT")]
    check("J6 the fence was active in every subprocess", loaded >= len(runs), f"loaded={loaded}")
    check("J7 and no subprocess attempted a non-loopback connection or lookup", not attempts, str(attempts))


def tracked_data_digest() -> str:
    digest = hashlib.sha256()
    for sub in ("_data", "updates"):
        for path in sorted((ROOT / sub).rglob("*")):
            if path.is_file():
                digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
                digest.update(sha(path.read_bytes()).encode("ascii"))
    return digest.hexdigest()


def run() -> int:
    print("=" * 78)
    print("AUX-083  a Microsoft Q&A reply to a PowerPoint question gets its own row id")
    print("=" * 78)
    data_before = tracked_data_digest()
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for part in (part_a, part_b, lambda: part_c(tmp), lambda: part_d(tmp), lambda: part_e(tmp),
                     lambda: part_f(tmp), lambda: part_g(tmp), part_h, lambda: part_i(tmp),
                     lambda: part_j(tmp)):
            try:
                part()
            except Exception as exc:  # noqa: BLE001 - a crash is a NAMED failure, never a lost tail
                check(f"part raised {type(exc).__name__}", False, traceback.format_exc()[-600:])
    print("K  this suite changed nothing real")
    check("K1 auxsays/_data and auxsays/updates are byte-identical after the suite",
          tracked_data_digest() == data_before)
    check("K2 no in-process network attempt", ATTEMPTS[0] == 0, str(ATTEMPTS[0]))
    print()
    for label in FAILURES:
        print(f"  failed: {label}")
    print("=" * 78)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
