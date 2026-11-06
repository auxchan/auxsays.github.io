#!/usr/bin/env python3
"""The audited fill of the day each stored OBS report was posted, and its N3 companion (AUX-090).

`fill_obs_report_dates.py` writes `source_date` -- the day the report ITSELF was posted -- onto every
surviving counted OBS row that had none, from a pinned manifest (audit/obs_report_dates.json). The AUX-088
withdrawal tool, with a second pinned manifest (audit/live_citation_withdrawal_v2.json), withdraws the
one forum copy of a GitHub issue that the same page already counts. Their contract, pinned here:

  A  the committed date manifest: one entry per surviving counted, undated OBS row, each a five-field
     identity with a day backed by a source timestamp of a kind that matches the row's URL; the one row
     it leaves undated is the one the v2 manifest withdraws
  B  the date is the report's OWN creation time: an issue's created_at, a comment's own (never its
     issue's), the opening post's own <time> (never the page's last activity), a reply's own (never the
     opening post's); the UTC day; a source that cannot be re-read is a disagreement, never a pass
  C  --write needs --confirm-write; the write changes exactly one line per pinned row (a null date
     replaced, or the date inserted right after captured_at), leaves captured_at, counted, every other
     field and every other row byte-identical, sets no acceptance field, moves no count, and the
     evidence-loss guard reads it as no loss
  D  a second run changes nothing
  E  every unsafe input refuses the WHOLE run and writes nothing: a date without a source, a day that is
     not the source's UTC day, a kind that does not match the URL, a moved block, a row that does not
     count or already has a date, a report dated after its own capture, a pinned block that touches
     anything but the date
  F  the v2 withdrawal manifest: exactly one forum row withdrawn as a same-page duplicate of a GitHub
     issue that stays counted, both labels recorded with who judged them, no row shared with any earlier
     withdrawal
  G  the committed store carries every pinned day, every pinned row that still counts is its pinned
     dated block, the v2 rows are in their pinned states, and this suite changed nothing real

B-E run on a synthetic store and synthetic source payloads (no recorded post text), with block hashes
pinned by the suite's OWN edit, never the tool's. The tool runs as a BARE script, so C-E run it as a
subprocess exactly as an operator would.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_fill_obs_report_dates.py
"""
from __future__ import annotations

import collections
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import yaml  # noqa: E402

import fill_obs_report_dates as fill  # noqa: E402
import withdraw_live_citation_rows as wd  # noqa: E402
from lib import evidence_loss as el  # noqa: E402

TOOL = SCRIPTS / "fill_obs_report_dates.py"
MANIFEST = SCRIPTS / "audit" / "obs_report_dates.json"
V2 = SCRIPTS / "audit" / "live_citation_withdrawal_v2.json"
NL = chr(10)
SEL = ("product_id", "update_version", "target_build", "id", "source_url")
OBS = "obs-studio"
GH = "https://github.com/obsproject/obs-studio/issues/"
FORUM = "https://obsproject.com/forum/threads/"
CAPTURED = "2026-09-01T00:00:00Z"
FORUM_196545 = FORUM + "video-capture-device-green-flickering.196545/"
GH_13997 = GH + "13997"

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


def sha(data: bytes | str) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def ident(row: dict) -> tuple[str, ...]:
    return tuple(str(row.get(key) or "") for key in SEL)


# --------------------------------------------------------------------------------------------------
# A synthetic store, serialised the way the OBS writer serialises the real one.

def obs_row(n: int, version: str, url: str, *, counted: bool = True, shape: str = "absent",
            date: str | None = None, source_type: str = "github_issue") -> dict:
    row = {"id": f"obs-studio-{version.replace('.', '-')}-synthetic-{n}", "product_id": OBS,
           "update_version": version, "source_type": source_type, "source_name": "synthetic source",
           "source_url": url, "parent_title": f"Synthetic report {n}", "report_title": f"Synthetic report {n}",
           "report_text_excerpt": f"SYNTHETIC REPORT TEXT {n} on {version}", "captured_at": CAPTURED}
    if shape == "null":
        row.update({"source_date": None, "target_release_date": None, "source_date_pass": None})
    elif shape == "dated":
        row.update({"source_date": date, "target_release_date": None, "source_date_pass": None})
    row.update({"patch_version_matched": True, "matched_version": version, "match_basis": "body",
                "counted": counted, "exclusion_reason": None if counted else "identity_not_the_subject",
                "issue_theme": "crash / stability", "workflow_area": "application stability",
                "platform": "windows", "severity": "high", "sentiment": "negative", "source_weight": 1})
    return row


ROWS = [
    obs_row(1, "32.1.2", GH + "90001"),
    obs_row(2, "32.1.2", GH + "90002", shape="null"),
    obs_row(3, "32.1.2", FORUM + "synthetic-thread.80001/", source_type="obs_forum_thread"),
    obs_row(4, "32.2.2", GH + "90003#issuecomment-70001"),
    obs_row(5, "32.2.2", FORUM + "synthetic-thread.80002/post-60002", source_type="obs_forum_thread"),
    obs_row(6, "32.1.2", GH + "90004", counted=False),
    obs_row(7, "32.1.2", GH + "90005", shape="dated", date="2026-05-01"),
    {"id": "microsoft-windows-11-25h2-synthetic-8", "product_id": "microsoft-windows-11", "update_version": "25H2",
     "source_type": "microsoft_learn_qna", "source_name": "Microsoft Q&A", "source_url": "https://example.invalid/q/8",
     "parent_title": "Synthetic report 8", "report_title": "Synthetic report 8",
     "report_text_excerpt": "SYNTHETIC REPORT TEXT 8", "captured_at": CAPTURED, "source_date": None,
     "patch_version_matched": True, "counted": True, "exclusion_reason": None, "target_build": "26200.1",
     "sentiment": "negative", "source_weight": 1},
    obs_row(9, "32.1.1", GH + "90001"),
]
# Row index -> (kind, the timestamp the source serves for the report itself, the parent's, if any).
SOURCES = {
    0: ("github_issue", "2026-04-25T23:30:00Z", None),
    1: ("github_issue", "2026-04-26T08:00:00Z", None),
    # +0100 just after midnight: the served local day is 04-27, the UTC day 04-26.
    2: ("forum_opening_post", "2026-04-27T00:30:00+0100", None),
    3: ("github_issue_comment", "2026-08-20T10:00:00Z", "2026-08-15T10:00:00Z"),
    4: ("forum_reply", "2026-08-21T12:00:00+0000", "2026-08-16T09:00:00+0000"),
}
DAYS = {0: "2026-04-25", 1: "2026-04-26", 2: "2026-04-26", 3: "2026-08-20", 4: "2026-08-21"}


def store_text(rows: list[dict] | None = None) -> str:
    payload = {"schema_version": 1, "evidence": rows if rows is not None else ROWS}
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=1000)


def blocks(text: str) -> list[tuple[int, int, dict]]:
    return wd.aux072.store_blocks(text)


def block_at(text: str, index: int) -> str:
    lo, hi, _row = blocks(text)[index]
    return text[lo:hi]


def own_edit(block: str, day: str) -> str:
    """The suite's own date edit, by line list, independent of the tool's string edit."""
    lines = block.split(NL)
    new = "  source_date: '" + day + "'"
    present = [i for i, line in enumerate(lines) if line.startswith("  source_date:")]
    if present:
        assert len(present) == 1 and lines[present[0]] == "  source_date: null"
        lines[present[0]] = new
    else:
        at = [i for i, line in enumerate(lines) if line.startswith("  captured_at: ")]
        assert len(at) == 1
        lines.insert(at[0] + 1, new)
    return NL.join(lines)


def utc_text(stamp: str) -> str:
    return fill.utc_text(stamp)


def manifest_for(text: str, which: tuple[int, ...] = (0, 1, 2, 3, 4)) -> dict:
    entries = []
    for index in which:
        row = blocks(text)[index][2]
        kind, stamp, _parent = SOURCES[index]
        block = block_at(text, index)
        entries.append({**dict(zip(SEL, ident(row))), "block_sha256_before": sha(block),
                        "block_sha256_after": sha(own_edit(block, DAYS[index])), "source_date": DAYS[index],
                        "source": {"kind": kind, "url": row["source_url"], "created_at": stamp,
                                   "created_at_utc": utc_text(stamp)}})
    return {"schema": 1, "ledger": "AUX-090", "selector": list(SEL), "product_id": OBS, "field": "source_date",
            "entries": entries}


def run_tool(store: Path, manifest: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, str(TOOL), "--store", str(store), "--manifest", str(manifest), *args],
                          capture_output=True, text=True, encoding="utf-8", env=env, timeout=600)


def tree(tmp: Path, text: str, doc: dict) -> tuple[Path, Path]:
    store, man = tmp / "consensus_evidence.yml", tmp / "manifest.json"
    store.write_bytes(text.encode("utf-8"))
    man.write_bytes(json.dumps(doc).encode("utf-8"))
    return store, man


def refused_run(text: str, doc: dict) -> tuple[subprocess.CompletedProcess, bool]:
    """--write --confirm-write on a tree: (process, store came back byte-identical)."""
    with tempfile.TemporaryDirectory(prefix="aux090-e-") as tmp:
        store, man = tree(Path(tmp), text, doc)
        proc = run_tool(store, man, "--write", "--confirm-write")
        return proc, store.read_bytes() == text.encode("utf-8")


def refusal(doc: dict, text: str | None = None) -> str:
    """The in-process refusal message for a manifest and store ('' when it plans)."""
    try:
        fill.plan(text if text is not None else store_text(), fill.manifest_entries(doc))
        return ""
    except fill.Refusal as exc:
        return str(exc)


def thread_html(posts: list[tuple[str, str, str]], last_activity: str) -> str:
    """A synthetic XenForo thread: (author, post id, served time) per post, then a page-level last-activity time."""
    articles = "".join(
        f'<article class="message message--post js-post" data-author="{a}" data-content="post-{p}" id="js-post-{p}">'
        f'<header><time class="u-dt" datetime="{t}">x</time></header>'
        f'<div class="bbWrapper">SYNTHETIC POST TEXT {p}</div></article>' for a, p, t in posts)
    return (f'<html><body><h1 class="p-title-value">Synthetic thread</h1>{articles}'
            f'<time class="u-dt" datetime="{last_activity}">y</time></body></html>')


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Audited fill of the day each stored OBS report was posted (AUX-090)")
    print("=" * 78)
    live_store = ROOT / "_data" / "consensus_evidence.yml"
    live_before = sha(live_store.read_bytes())
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = doc["entries"]

    print("A  the committed date manifest")
    check("A1 282 entries, every one an OBS row with no build and a unique five-field identity",
          len(entries) == 282 and all(e["product_id"] == OBS and e["target_build"] == "" for e in entries)
          and len({ident(e) for e in entries}) == 282, str(len(entries)))
    kinds = collections.Counter(e["source"]["kind"] for e in entries)
    check("A2 254 GitHub issue openers and 28 forum opening posts; no reply is among today's rows",
          kinds == {"github_issue": 254, "forum_opening_post": 28}, str(kinds))
    check("A3 every entry passes the shipped validator: a day backed by its source's own timestamp, of the right kind",
          not validator_refusal(doc), validator_refusal(doc))
    check("A4 every day is the UTC day of its source timestamp, and every source is the row's own URL",
          all(fill.utc_day(e["source"]["created_at"]) == e["source_date"] and e["source"]["url"] == e["source_url"]
              for e in entries))
    pop = doc.get("population") or {}
    check("A5 the one surviving counted row left undated is forum 196545 on 32.1.2, the row the v2 manifest withdraws",
          [(x["update_version"], x["source_url"]) for x in pop.get("not_dated", [])] == [("32.1.2", FORUM_196545)]
          and pop.get("unverifiable") == [] and pop.get("counted_obs_rows_without_a_date_at_pin") == 283
          and pop.get("dated_here") == 282)
    check("A6 the manifest names the field, the product and the five-field selector, and no acceptance field",
          doc.get("field") == "source_date" and doc.get("product_id") == OBS and tuple(doc.get("selector")) == SEL
          and "source_date_pass" not in json.dumps(entries) and "target_release_date" not in json.dumps(entries))

    print("B  the date is the report's own")
    issue = {"number": 90001, "created_at": "2026-04-25T23:30:00Z", "updated_at": "2026-10-01T00:00:00Z",
             "closed_at": "2026-10-02T00:00:00Z"}
    check("B1 an issue is dated by its created_at, not by updated_at or closed_at",
          fill.created_at_from_github(GH + "90001", issue) == "2026-04-25T23:30:00Z")
    comment = {"id": 70001, "issue_url": "https://api.github.com/repos/obsproject/obs-studio/issues/90003",
               "created_at": "2026-08-20T10:00:00Z"}
    parent = {"number": 90003, "created_at": "2026-08-15T10:00:00Z"}
    check("B2 a reply on GitHub is dated by the comment's own created_at, never its parent issue's",
          fill.created_at_from_github(GH + "90003#issuecomment-70001", comment) == "2026-08-20T10:00:00Z"
          and raises(lambda: fill.created_at_from_github(GH + "90003#issuecomment-70001", parent)))
    opening_page = thread_html([("first", "60001", "2026-04-27T00:30:00+0100"),
                                ("second", "60009", "2026-05-03T10:00:00+0000")], "2026-10-01T00:00:00+0000")
    check("B3 a forum opening post is dated by the first <time> in its own article, not a reply's or the page's last activity",
          fill.created_at_from_forum(FORUM + "synthetic-thread.80001/", opening_page) == "2026-04-27T00:30:00+0100")
    reply_page = thread_html([("first", "60001", "2026-08-16T09:00:00+0000"),
                              ("second", "60002", "2026-08-21T12:00:00+0000"),
                              ("third", "60003", "2026-08-25T12:00:00+0000")], "2026-10-01T00:00:00+0000")
    check("B4 a forum reply is dated by the <time> in its own article, never the opening post's or a later post's",
          fill.created_at_from_forum(FORUM + "synthetic-thread.80002/post-60002", reply_page) == "2026-08-21T12:00:00+0000"
          and fill.created_at_from_forum(FORUM + "synthetic-thread.80002/#post-60003", reply_page) == "2026-08-25T12:00:00+0000"
          and fill.created_at_from_forum(FORUM + "synthetic-thread.80002/post-69999", reply_page) == "")
    check("B5 a payload that is not the named issue, a pull request, or another comment is refused",
          raises(lambda: fill.created_at_from_github(GH + "90001", {"number": 90002, "created_at": "x"}))
          and raises(lambda: fill.created_at_from_github(GH + "90001", {"number": 90001, "pull_request": {}}))
          and raises(lambda: fill.created_at_from_github(GH + "90003#issuecomment-70001", dict(comment, id=70002)))
          and raises(lambda: fill.created_at_from_github(
              GH + "90003#issuecomment-70001",
              dict(comment, issue_url="https://api.github.com/repos/obsproject/obs-studio/issues/90004"))))
    shapes = {GH + "1": "github_issue", GH + "1#issuecomment-2": "github_issue_comment",
              FORUM + "a-b.3/": "forum_opening_post", FORUM + "3/": "forum_opening_post",
              FORUM + "a-b.3/post-4": "forum_reply", FORUM + "a-b.3/#post-4": "forum_reply",
              "https://github.com/obsproject/obs-studio/pull/1": "", "https://obsproject.com/forum/posts/4/": "",
              GH + "1#issue-2": ""}
    check("B6 the URL decides the kind: issue, comment, opening post or reply; anything else has none",
          all(fill.source_kind(u)[0] == k for u, k in shapes.items()),
          str({u: fill.source_kind(u)[0] for u, k in shapes.items() if fill.source_kind(u)[0] != k}))
    check("B7 the day is the UTC day: +0100 at 00:30 is the previous UTC day; a naive timestamp has no day",
          fill.utc_day("2026-04-27T00:30:00+0100") == "2026-04-26" and fill.utc_day("2026-04-27T00:30:00+01:00") == "2026-04-26"
          and fill.utc_day("2026-04-25T23:30:00Z") == "2026-04-25" and fill.utc_day("2026-04-25T23:30:00") == ""
          and fill.utc_day("2026-08-21T12:00:00.123+0000") == "2026-08-21")
    text = store_text()
    fixture_doc = manifest_for(text)
    gh_payloads = {"/issues/90001": issue, "/issues/90002": {"number": 90002, "created_at": "2026-04-26T08:00:00Z"},
                   "/issues/comments/70001": comment, "/issues/90003": parent}
    pages = {FORUM + "synthetic-thread.80001/": opening_page, FORUM + "synthetic-thread.80002/": reply_page}
    agree = fill.verify_sources(fixture_doc["entries"], gh_payloads.__getitem__, pages.__getitem__)
    stale = copy.deepcopy(fixture_doc)
    stale["entries"][3]["source"]["created_at"] = "2026-08-15T10:00:00Z"
    stale["entries"][3]["source_date"] = "2026-08-15"
    parent_dated = fill.verify_sources(stale["entries"], gh_payloads.__getitem__, pages.__getitem__)
    unreadable = fill.verify_sources(fixture_doc["entries"][:1], lambda _p: (_ for _ in ()).throw(OSError("down")),
                                     pages.__getitem__)
    check("B8 re-reading the sources: all five agree; a reply pinned with its parent's date disagrees; an unreadable source disagrees",
          agree == [] and [d["id"] for d in parent_dated] == [ROWS[3]["id"]]
          and len(unreadable) == 1 and unreadable[0]["served"].startswith("unreadable"),
          json.dumps([agree, parent_dated, unreadable])[:300])

    print("C  the write, as the bare script")
    with tempfile.TemporaryDirectory(prefix="aux090-c-") as tmp:
        store, man = tree(Path(tmp), text, fixture_doc)
        dry = run_tool(store, man)
        dry_same = store.read_bytes() == text.encode("utf-8")
        nowrite = run_tool(store, man, "--write")
        after_nowrite = store.read_bytes() == text.encode("utf-8")
        audit = Path(tmp) / "audit.json"
        wrote = run_tool(store, man, "--write", "--confirm-write", "--audit", str(audit))
        after = store.read_bytes().decode("utf-8")
        second = run_tool(store, man, "--write", "--confirm-write")
        after2 = store.read_bytes().decode("utf-8")
        result = json.loads(audit.read_text(encoding="utf-8")) if audit.exists() else {}
    check("C1 a dry run (the default) plans five dates and writes nothing",
          dry.returncode == 0 and dry_same and "rows to date: 5 (written: no)" in dry.stdout
          and '"date": 5' in dry.stdout, dry.stdout[-300:] + dry.stderr[-300:])
    check("C2 --write without --confirm-write is a usage error and writes nothing",
          nowrite.returncode == 2 and after_nowrite)
    old_lines, new_lines = text.split(NL), after.split(NL)
    added = collections.Counter(new_lines) - collections.Counter(old_lines)
    removed = collections.Counter(old_lines) - collections.Counter(new_lines)
    check("C3 the write changes exactly one line per pinned row: four inserted after captured_at, one null replaced",
          wrote.returncode == 0 and result.get("dated_now") == 5 and len(new_lines) == len(old_lines) + 4
          and added == collections.Counter(fill.date_line(DAYS[i]) for i in range(5))
          and removed == {"  source_date: null": 1} and old_lines.count("  source_date: null") == 2,
          wrote.stdout[-300:] + wrote.stderr[-300:])
    before_rows, after_rows = [r for _l, _h, r in blocks(text)], [r for _l, _h, r in blocks(after)]
    check("C4 captured_at is byte-identical on every row, the pinned ones included",
          [r.get("captured_at") for r in before_rows] == [r.get("captured_at") for r in after_rows]
          and all(f"  captured_at: '{CAPTURED}'" in block_at(after, i) for i in range(5)))
    check("C5 each pinned row gains only its own day, right after captured_at; every other row is byte-identical",
          all(after_rows[i] == dict(before_rows[i], source_date=DAYS[i]) for i in range(5))
          and all(list(after_rows[i])[list(after_rows[i]).index("captured_at") + 1] == "source_date" for i in range(5))
          and all(block_at(after, i) == block_at(text, i) for i in range(5, len(ROWS)))
          and all(sha(block_at(after, i)) == fixture_doc["entries"][i]["block_sha256_after"] for i in range(5)))
    check("C6 no acceptance field is set, no row starts or stops counting, and the evidence-loss guard sees no loss",
          all(r.get("source_date_pass") is None and r.get("target_release_date") is None for r in after_rows)
          and [r.get("counted") for r in before_rows] == [r.get("counted") for r in after_rows]
          and el.losses_between(text, after) == [])
    check("C7 the run's audit records the five dated rows with their kinds; only the unpinned same-URL row on 32.1.1 stays undated",
          result.get("counted_obs_rows_still_undated") == ["32.1.1 obs-studio-32-1-1-synthetic-9"]
          and result.get("counted_obs_rows") == 7
          and collections.Counter(e["kind"] for e in result.get("entries", []))
          == {"github_issue": 2, "forum_opening_post": 1, "github_issue_comment": 1, "forum_reply": 1})

    with tempfile.TemporaryDirectory(prefix="aux090-c8-") as tmp:
        store, man = tree(Path(tmp), text, fixture_doc)
        regen_elsewhere = run_tool(store, man, "--write", "--confirm-write", "--regenerate")
        regen_dry = run_tool(store, man, "--regenerate")
        verify_write = run_tool(store, man, "--verify-sources", "--write", "--confirm-write")
        untouched = store.read_bytes() == text.encode("utf-8")
    check("C8 usage errors write nothing: --regenerate off the default store or without --write, --verify-sources with --write",
          regen_elsewhere.returncode == 2 and regen_dry.returncode == 2 and verify_write.returncode == 2 and untouched,
          f"{regen_elsewhere.returncode} {regen_dry.returncode} {verify_write.returncode}")

    print("D  idempotence")
    check("D1 a second run finds every row already dated and changes nothing",
          second.returncode == 0 and after2 == after and '"already_dated": 5' in second.stdout
          and "rows to date: 0" in second.stdout
          and "nothing to write" in second.stdout, second.stdout[-300:])

    print("E  every unsafe input refuses the whole run and writes nothing")
    unsourced = copy.deepcopy(fixture_doc)
    del unsourced["entries"][0]["source"]["created_at"]
    proc, same = refused_run(text, unsourced)
    check("E1 a date without a source timestamp is refused",
          proc.returncode == 1 and same and "a date without a source timestamp" in proc.stdout, proc.stdout[-300:])
    nosource = copy.deepcopy(fixture_doc)
    del nosource["entries"][1]["source"]
    check("E2 a date with no source at all is refused", "a date without a source timestamp" in refusal_of(nosource))
    wrongday = copy.deepcopy(fixture_doc)
    wrongday["entries"][2]["source_date"] = "2026-04-27"   # the served LOCAL day, not the UTC day
    wrongday["entries"][2]["block_sha256_after"] = sha(own_edit(block_at(text, 2), "2026-04-27"))
    check("E3 a day that is not the source timestamp's UTC day is refused",
          "is not the UTC day of the source timestamp" in refusal_of(wrongday))
    wrongkind = copy.deepcopy(fixture_doc)
    wrongkind["entries"][3]["source"]["kind"] = "github_issue"
    check("E4 a kind that does not match the URL (a reply dated as an issue) is refused",
          "does not match the URL" in refusal_of(wrongkind))
    naive = copy.deepcopy(fixture_doc)
    naive["entries"][0]["source"]["created_at"] = "2026-04-25T23:30:00"
    check("E5 a timestamp without a zone is refused", "has no zone or does not parse" in refusal_of(naive))
    otherurl = copy.deepcopy(fixture_doc)
    otherurl["entries"][0]["source"]["url"] = GH + "90002"
    check("E6 a source that is not the row's own URL is refused", "is not the row's own URL" in refusal_of(otherurl))
    badutc = copy.deepcopy(fixture_doc)
    badutc["entries"][0]["source"]["created_at_utc"] = "2026-04-25T23:31:00Z"
    check("E7 a recorded UTC instant that disagrees with the served timestamp is refused",
          "recorded UTC instant disagrees" in refusal_of(badutc))
    moved = text.replace("SYNTHETIC REPORT TEXT 1 on", "SYNTHETIC REPORT TEXT 1 changed on", 1)
    proc, same = refused_run(moved, fixture_doc)
    check("E8 a block that moved since it was pinned refuses the whole run (no other row is dated)",
          proc.returncode == 1 and same and "block changed since the manifest was pinned" in proc.stdout)
    uncounted = manifest_for(text)
    row6 = blocks(text)[5][2]
    uncounted["entries"].append({**dict(zip(SEL, ident(row6))), "block_sha256_before": sha(block_at(text, 5)),
                                 "block_sha256_after": sha(own_edit(block_at(text, 5), "2026-04-20")),
                                 "source_date": "2026-04-20",
                                 "source": {"kind": "github_issue", "url": row6["source_url"],
                                            "created_at": "2026-04-20T10:00:00Z", "created_at_utc": "2026-04-20T10:00:00Z"}})
    check("E9 a row that does not count is refused", "not a counted row" in refusal_of(uncounted))
    dated = manifest_for(text)
    row7 = blocks(text)[6][2]
    dated["entries"].append({**dict(zip(SEL, ident(row7))), "block_sha256_before": sha(block_at(text, 6)),
                             "block_sha256_after": "0" * 64, "source_date": "2026-04-20",
                             "source": {"kind": "github_issue", "url": row7["source_url"],
                                        "created_at": "2026-04-20T10:00:00Z", "created_at_utc": "2026-04-20T10:00:00Z"}})
    check("E10 a row that already carries a date is refused", "the row already carries a date" in refusal_of(dated))
    late = copy.deepcopy(fixture_doc)
    late["entries"][0]["source"].update(created_at="2026-09-02T00:00:00Z", created_at_utc="2026-09-02T00:00:00Z")
    late["entries"][0]["source_date"] = "2026-09-02"
    late["entries"][0]["block_sha256_after"] = sha(own_edit(block_at(text, 0), "2026-09-02"))
    check("E11 a report dated after its own capture is refused", "dated after it was captured" in refusal_of(late))
    touched = copy.deepcopy(fixture_doc)
    touched_block = own_edit(block_at(text, 0), DAYS[0]).replace(f"captured_at: '{CAPTURED}'",
                                                                 "captured_at: '2026-09-01T00:00:01Z'", 1)
    touched["entries"][0]["block_sha256_after"] = sha(touched_block)
    check("E12 an edit pinned to a block that also moved captured_at is refused",
          "the edit does not produce the pinned block" in refusal_of(touched))
    other_day = copy.deepcopy(fixture_doc)
    other_day["entries"][0]["block_sha256_after"] = sha(own_edit(block_at(text, 0), "2026-04-24"))
    pre_dated = text.replace(block_at(text, 0), own_edit(block_at(text, 0), "2026-04-24"), 1)
    check("E13 a pinned dated block that carries another day than the entry's is refused",
          "pinned dated block carries another date" in refusal_of(other_day, pre_dated))
    twice = copy.deepcopy(fixture_doc)
    twice["entries"].append(copy.deepcopy(twice["entries"][0]))
    foreign = copy.deepcopy(fixture_doc)
    foreign["entries"][0]["product_id"] = "microsoft-windows-11"
    build = copy.deepcopy(fixture_doc)
    build["entries"][0]["target_build"] = "1"
    wrong_field = dict(copy.deepcopy(fixture_doc), field="captured_at")
    missing = copy.deepcopy(fixture_doc)
    missing["entries"][0]["id"] = "obs-studio-32-1-2-synthetic-404"
    check("E14 a repeated identity, another product, a build, another field, or an identity matching no block is refused",
          "identity listed twice" in refusal_of(twice) and "not an OBS row" in refusal_of(foreign)
          and "not an OBS row" in refusal_of(build) and "not an OBS source_date manifest" in refusal_of(wrong_field)
          and "0 blocks match" in refusal_of(missing))
    two = store_text(ROWS + [dict(ROWS[0])])
    check("E15 an identity stored twice is refused", "2 blocks match" in refusal_of(manifest_for(two), two))
    real_edit = fill.date_block
    try:
        fill.date_block = lambda block, day: real_edit(block, day).replace(
            f"captured_at: '{CAPTURED}'", "captured_at: '2026-09-01T00:00:01Z'", 1)
        forged = manifest_for(text, (0,))
        forged["entries"][0]["block_sha256_after"] = sha(fill.date_block(block_at(text, 0), DAYS[0]))
        message = refusal_of(forged)
    finally:
        fill.date_block = real_edit
    check("E16 even an edit and a pin that agree cannot move captured_at: the field-by-field proof refuses",
          "changed more than the date" in message, message[:200])

    print("F  the v2 withdrawal manifest (N3)")
    v2 = json.loads(V2.read_text(encoding="utf-8"))
    w = [e for e in v2["entries"] if e["role"] == "withdraw"]
    k = [e for e in v2["entries"] if e["role"] == "retain"]
    check("F1 it withdraws exactly forum 196545 on OBS 32.1.2 as a duplicate of GitHub issue 13997 on the same page, which is kept",
          len(w) == 1 and len(k) == 1 and (w[0]["update_version"], w[0]["source_url"]) == ("32.1.2", FORUM_196545)
          and w[0]["exclusion_reason"] == "duplicate_existing_evidence"
          and tuple(w[0]["duplicate_of"][x] for x in SEL) == ident(k[0])
          and (k[0]["update_version"], k[0]["source_url"]) == ("32.1.2", GH_13997))
    adj = w[0].get("adjudication") or {}
    check("F2 both labels are INCORRECT, the duplicate ground is the one used, and who judged it is recorded",
          (adj.get("first_audit") or {}).get("label") == "INCORRECT"
          and (adj.get("second_blind") or {}).get("label") == "INCORRECT"
          and (adj.get("second_blind") or {}).get("reason_class") == "duplicate_same_page"
          and "same worker" in str((adj.get("second_blind") or {}).get("judge") or "")
          and "same uploaded OBS log URL" in str(w[0].get("basis") or ""))
    check("F3 the shipped tool accepts it, with the same selector, scope and closed vocabulary as AUX-088",
          not v2_refusal(v2) and tuple(v2["selector"]) == wd.SELECTOR and tuple(v2["products"]) == wd.PRODUCTS)
    earlier = set()
    for name in ("live_citation_withdrawal.json", "windows_identity_not_the_subject_withdrawal.json",
                 "windows_confirmed_and_duplicate_withdrawal.json"):
        earlier |= {ident(e) for e in json.loads((SCRIPTS / "audit" / name).read_text(encoding="utf-8"))["entries"]}
    check("F4 it shares no row with AUX-088's, AUX-079's or AUX-072's manifest, and dates none of its own withdrawal",
          not (earlier & {ident(e) for e in v2["entries"]}) and ident(w[0]) not in {ident(e) for e in entries})

    print("G  the committed store, and this suite changed nothing real")
    live_text = live_store.read_bytes().decode("utf-8")
    live = {}
    for lo, hi, row in blocks(live_text):
        live.setdefault(ident(row), []).append((live_text[lo:hi], row))
    check("G1 every pinned row is stored once and carries exactly its pinned day",
          all(len(live.get(ident(e), [])) == 1 and live[ident(e)][0][1].get("source_date") == e["source_date"]
              for e in entries),
          str([e["id"] for e in entries if len(live.get(ident(e), [])) != 1][:5]))
    still = [e for e in entries if len(live.get(ident(e), [])) == 1 and live[ident(e)][0][1].get("counted") is True]
    check("G2 every pinned row that still counts is byte-identical to its pinned dated block",
          len(still) > 0 and all(sha(live[ident(e)][0][0]) == e["block_sha256_after"] for e in still),
          str([e["id"] for e in still if sha(live[ident(e)][0][0]) != e["block_sha256_after"]][:5]))
    baseline = wd.load_baseline(wd.BASELINE)
    check("G3 the v2 rows are in their pinned states: the forum copy withdrawn with its reason, the issue still counted",
          len(live.get(ident(w[0]), [])) == 1 and sha(live[ident(w[0])][0][0]) == w[0]["block_sha256_after"]
          and live[ident(w[0])][0][1].get("counted") is False
          and live[ident(w[0])][0][1].get("exclusion_reason") == "duplicate_existing_evidence"
          and len(live.get(ident(k[0]), [])) == 1 and live[ident(k[0])][0][1].get("counted") is True
          and wd._pin_holds(k[0], "block_sha256_before", sha(live[ident(k[0])][0][0]), baseline))  # noqa: SLF001
    check("G4 the live store is byte-identical after the suite", sha(live_store.read_bytes()) == live_before)

    print()
    for label in FAILURES:
        print(f"  failed: {label}")
    print("=" * 78)
    # The governed count line comes LAST: the runner and the manifest read it.
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    return 1 if FAIL else 0


def raises(fn) -> bool:
    try:
        fn()
    except fill.Refusal:
        return True
    return False


def refusal_of(doc: dict, text: str | None = None) -> str:
    return refusal(doc, text)


def validator_refusal(doc: dict) -> str:
    try:
        fill.manifest_entries(copy.deepcopy(doc))
        return ""
    except fill.Refusal as exc:
        return str(exc)


def v2_refusal(doc: dict) -> str:
    try:
        wd.manifest_entries(copy.deepcopy(doc))
        return ""
    except wd.Refusal as exc:
        return str(exc)


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
