#!/usr/bin/env python3
"""AUX-109: a NEW Adobe opening-post row stores its excerpt around the version it was accepted for.

`report_text_excerpt` is the first 280 characters of a report, so a row whose reporter named the
version further in cannot show the occurrence its own match rests on (132 Acrobat rows are like
that). For NEW rows of the three Adobe products whose candidate text is one opening post (the
Algolia/getTopics paths), the SAME field and the SAME 280-character cap are positioned around the
accepted occurrence -- only when the head does not already show the version. What this suite pins:

  A  the helper: head byte-identical whenever re-centring is unnecessary; otherwise <= 280
     characters, the occurrence inside, deterministic, word-aligned edges.
  B  the call sites: title occurrence, alias basis, Premiere's three-part join, Acrobat's
     "title + (title body)" join, a head that already shows an alias spelling, the build-65 basis,
     and every candidate that is not one opening post (the retired /t5 whole-thread path, the
     Premiere page scrapes) keep the head.
  C  excerpt independence: the row builders run three ways (shipped, SENTINEL excerpt, head-only);
     every field but the excerpt and every acceptance decision is identical.
  D  every other collector is untouched (only the two Adobe builders pass a span).
  E  no backfill, on a throwaway copy of the store: existing bytes unchanged, ownership validation
     passes, a rediscovered row is refused, and counts, labels, summaries, verdicts and maturity are
     identical whether the new rows carry the head or the centred excerpt.
  F  readers: Level 2/3 rows (no match) keep the head; a shared Pro/Reader report gets one excerpt.
  G  reviewed verdict reasons: support is unchanged by new rows; the cross-policy pair is documented.
  H  the shadow producer reads the excerpt, so its activation switch stays OFF with the dependency
     recorded beside it.
  I  privacy: a window never carries a greeting name, an @handle, an e-mail address, a sign-off or a
     signature that the post's text around the version would otherwise put in it.

Offline. Reads the live store and records; writes only to a temporary directory. The generated-record
scan is memoised (identical results) because the Acrobat builder re-reads every record per call.
Fixture text is synthetic (AUX-080): no recorded post text.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_version_centred_excerpt.py
"""
from __future__ import annotations

import ast
import hashlib
import re
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from patch_collectors import base                                    # noqa: E402
from patch_collectors import adobe_acrobat_community as ac           # noqa: E402
from patch_collectors import adobe_premiere as pr                    # noqa: E402
from patch_collectors.base import PatchRecord                        # noqa: E402

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


_REAL_GENERATED = base.generated_records
_GEN_CACHE: dict = {}


def _memo_generated(product_id, target_versions=None, *, include_archived=False):
    """`base.generated_records`, read once per product: the archived-inclusive list, filtered exactly as
    the real function filters (same order, same records)."""
    if product_id not in _GEN_CACHE:
        _GEN_CACHE[product_id] = _REAL_GENERATED(product_id, include_archived=True)
    return [r for r in _GEN_CACHE[product_id]
            if (include_archived or r.update_status != "archived")
            and (not target_versions or r.update_version in target_versions)]


ac.generated_records = _memo_generated
_ONCE: dict = {}


def once(name: str, fn):
    if name not in _ONCE:
        _ONCE[name] = fn()
    return _ONCE[name]

CAPTURED = "2026-11-19T00:00:00Z"
V = "26.001.21563"                     # a synthetic build shape; never a live record's identity here
REC_R = PatchRecord(ac.READER_ID, V, Path("synthetic-reader.md"), "2026-05-18T00:00:00Z", "current", "Adobe Acrobat Reader")
REC_P = PatchRecord(ac.PRO_ID, V, Path("synthetic-pro.md"), "2026-05-18T00:00:00Z", "current", "Adobe Acrobat Pro")
PV = "26.2"
REC_PR = PatchRecord("adobe-premiere-pro", PV, Path("synthetic-premiere.md"), "2026-04-16T00:00:00Z", "current", "Adobe Premiere Pro")
FILLER = ("Our office has used the same workstation setup for several years without trouble, and the team "
          "relies on it every day for contracts, scanned forms and printed reports. ")
PFILLER = ("I edit a weekly show on this workstation and the project has the same structure every week, "
           "with the same footage cards, the same proxies and the same export presets. ")


def acr_topic(body: str, *, title: str = "Reader stopped working", tid: int = 9990001, date: str = "2026-06-01") -> dict:
    """A getTopics-shaped record through the REAL Algolia candidate builder (sets FIRST_POST_ONLY)."""
    return ac._topic_to_candidate({"url": f"https://community.adobe.com/questions-9/g53-synthetic-{tid}",
                                   "title": title, "firstPost": {"content": f"<p>{body}</p>",
                                                                 "creationDate": f"{date}T00:00:00Z"}})


def pr_topic(body: str, *, title: str = "Timeline problem", tid: int = 9991001) -> dict:
    return pr.topic_candidate({"url": f"https://community.adobe.com/bug-reports-728/g53-synthetic-{tid}",
                               "title": title, "forum": {"id": pr.PREMIERE_BUG_FORUM_ID},
                               "category": {"categoryId": pr.PREMIERE_CATEGORY_ID},
                               "firstPost": {"content": f"<p>{body}</p>", "creationDate": "2026-04-20T10:00:00+0000"}})


def acr_row(cand: dict, rec: PatchRecord = REC_R) -> dict:
    return ac.row_from_candidate(rec.product_id, rec, dict(cand), CAPTURED)


def pr_row(cand: dict, rec: PatchRecord = REC_PR) -> dict:
    return pr.row_from_candidate(rec, dict(cand), CAPTURED)


def span(text: str, token: str) -> tuple[int, int]:
    i = text.index(token)
    return i, i + len(token)


def word_aligned(window: str, collapsed: str) -> bool:
    body = window[3:] if window.startswith("...") else window
    body = body[:-3] if window.endswith("...") and len(window) > 3 else body
    lo = collapsed.find(body)
    if lo < 0:
        return False
    hi = lo + len(body)
    left_ok = lo == 0 or collapsed[lo - 1] in " ([{\"'" or not collapsed[lo].isalnum()
    right_ok = hi == len(collapsed) or collapsed[hi] in " .,;:!?)]}\"'" or not collapsed[hi - 1].isalnum()
    return left_ok and right_ok


def part_a() -> None:
    print("=" * 92)
    print("PART A  the helper: head when unnecessary, a bounded window around the occurrence otherwise")
    print("=" * 92)
    short = f"Reader {V} crashes when I open a scanned form."
    s, e = span(short, V)
    check("A1 a post of 280 characters or fewer keeps the head byte for byte",
          base.excerpt_at(short, s, e) == base.excerpt(short))
    longer = FILLER * 3
    check("A2 no span keeps the head", base.excerpt_at(longer, -1, -1) == base.excerpt(longer))
    check("A3 an inverted or out-of-range span keeps the head",
          base.excerpt_at(longer, 10, 5) == base.excerpt(longer)
          and base.excerpt_at(longer, 5, len(longer) + 9) == base.excerpt(longer))
    # The VISIBLE branch over many positions (the probe exercised it twice): wherever the occurrence
    # ends inside the head's visible text, the stored excerpt is today's head, byte for byte.
    visible_cases = same = 0
    for cut in range(0, 250, 7):
        text = FILLER[:cut] + f" Reader {V} crashes. " + FILLER * 2
        s, e = span(text, V)
        head = base.excerpt(text)
        if base._collapse_ws(text[:e]) and len(base._collapse_ws(text[:e])) <= len(base.excerpt_visible_head(text)):
            visible_cases += 1
            same += base.excerpt_at(text, s, e) == head
    check("A4 every occurrence visible in the head keeps the head byte for byte (36 positions)",
          visible_cases == 36 and same == visible_cases, f"{same}/{visible_cases}")
    # Past the head: a window of the same cap, the occurrence inside, deterministic, word-aligned.
    total = ok_len = ok_tok = ok_det = ok_words = ok_marks = 0
    for cut in range(300, 700, 23):
        text = (FILLER * 4)[:cut] + f" after the update to {V} it crashes on every scanned form " + FILLER
        s, e = span(text, V)
        got = base.excerpt_at(text, s, e)
        collapsed = base._collapse_ws(text)
        total += 1
        ok_len += len(got) <= 280
        ok_tok += V in got
        ok_det += got == base.excerpt_at(text, s, e)
        ok_words += word_aligned(got, collapsed)
        ok_marks += got.startswith("...") and got.endswith("...")
    check("A5 a window is never longer than the cap", ok_len == total, f"{ok_len}/{total}")
    check("A6 the occurrence is always inside the window", ok_tok == total, f"{ok_tok}/{total}")
    check("A7 the window is deterministic", ok_det == total, f"{ok_det}/{total}")
    check("A8 both edges are word-aligned", ok_words == total, f"{ok_words}/{total}")
    check("A9 a window inside the post says so with a placeholder at both ends",
          ok_marks == total, f"{ok_marks}/{total}")
    text = FILLER * 3 + f"Since {V} the form tool fails."
    s, e = span(text, V)
    got = base.excerpt_at(text, s, e)
    check("A10 a window that reaches the post's end carries no trailing placeholder",
          got.endswith("fails") or got.endswith("fails."), got[-30:])
    check("A11 the head is shorter than the post, so the window differs from it (non-vacuous)",
          got != base.excerpt(text) and V not in base.excerpt(text))
    parts = [("parent_title", "Crash"), ("report_title", "Reader crash"), ("report_text", f"on {V} it fails")]
    joined = " ".join(v for _n, v in parts)
    s, e = span(joined, V)
    check("A12 part_span names the part and local offsets",
          base.part_span(parts, s, e) == ("report_text", 3, 3 + len(V)), str(base.part_span(parts, s, e)))
    check("A13 a span crossing a join, or an invalid span, has no part",
          base.part_span(parts, len("Crash") - 2, len("Crash") + 3) is None and base.part_span(parts, -1, -1) is None)


def part_b() -> None:
    print()
    print("=" * 92)
    print("PART B  the call sites: only the accepted occurrence, only in one opening post")
    print("=" * 92)
    body = FILLER * 2 + f"Since installing Adobe Acrobat Reader {V} the app crashes whenever I open a scanned form."
    row = acr_row(acr_topic(body))
    check("B1 Acrobat: an accepted opening-post row past the cut is centred on its version",
          row.get("counted") is True and V in row["report_text_excerpt"] and len(row["report_text_excerpt"]) <= 280,
          f"{row.get('exclusion_reason')} {row['report_text_excerpt'][:60]!r}")
    cand = acr_topic(body)
    check("B2 Acrobat: the excerpt is cut from the candidate text, which for Algolia is 'title body'",
          cand["report_text"].startswith("Reader stopped working ")
          and row["report_text_excerpt"] != base.excerpt(cand["report_text"]))
    tcand = acr_topic(FILLER * 3 + "The app crashes whenever I open a scanned form.", title=f"Acrobat Reader {V} crashes")
    titled = acr_row(tcand)
    check("B3 Acrobat: an occurrence in the title keeps the head (the title is stored whole)",
          titled["report_text_excerpt"] == base.excerpt(tcand["report_text"]), titled["report_text_excerpt"][:50])
    alias = "2026.001.21563"
    arow = acr_row(acr_topic(FILLER * 2 + f"Adobe Acrobat Reader version {alias} crashes whenever I open a scanned form."))
    check("B4 Acrobat: the alias basis is centred on the alias occurrence",
          arow.get("match_basis") == "exact_version_alias" and alias in arow["report_text_excerpt"],
          f"{arow.get('match_basis')} {arow['report_text_excerpt'][:50]!r}")
    both = acr_row(acr_topic(f"Reader shows {alias} in About. " + FILLER * 2
                             + f"Adobe Acrobat Reader {V} crashes whenever I open a scanned form."))
    check("B5 Acrobat: a head that already shows an accepted spelling keeps the head",
          both["report_text_excerpt"] == base.excerpt(acr_topic(f"Reader shows {alias} in About. " + FILLER * 2
                                                                + f"Adobe Acrobat Reader {V} crashes whenever I open a scanned form.")["report_text"]))
    spaced = acr_topic(body)
    spaced["report_text"] = "   \n " + spaced["report_text"]
    srow = acr_row(spaced)
    check("B6 Acrobat: leading whitespace in the candidate text is accounted for",
          V in srow["report_text_excerpt"] and srow["report_text_excerpt"] == row["report_text_excerpt"])
    t5 = dict(cand)
    t5.pop(base.FIRST_POST_ONLY, None)
    check("B7 Acrobat: a candidate that is not one opening post (the /t5 thread page) keeps the head",
          acr_row(t5)["report_text_excerpt"] == base.excerpt(t5["report_text"]))
    check("B8 Acrobat: the Algolia builder marks its candidates as one opening post",
          cand.get(base.FIRST_POST_ONLY) is True)

    pbody = PFILLER * 2 + f"After updating to Premiere Pro {PV} the timeline crashes every time I drag a clip."
    pcand = pr_topic(pbody)
    prow = pr_row(pcand)
    check("B9 Premiere: the three-part join (title, title, body) maps the body occurrence correctly",
          prow.get("counted") is True and f"Premiere Pro {PV}" in prow["report_text_excerpt"]
          and len(prow["report_text_excerpt"]) <= 280, f"{prow.get('exclusion_reason')} {prow['report_text_excerpt'][:60]!r}")
    check("B10 Premiere: the excerpt is cut from the body alone (Premiere's candidate has no title in it)",
          not prow["report_text_excerpt"].startswith("...Timeline problem") and pcand.get(base.FIRST_POST_ONLY) is True)
    ptitled = pr_row(pr_topic(PFILLER * 3 + "The timeline crashes whenever I drag a clip.", title=f"Premiere Pro {PV} timeline crash"))
    check("B11 Premiere: an occurrence in the title keeps the head",
          ptitled["report_text_excerpt"] == base.excerpt(PFILLER * 3 + "The timeline crashes whenever I drag a clip."))
    b65 = pr_row(pr_topic(PFILLER * 2 + "Since build 65 the timeline crashes constantly and the program freezes."))
    check("B12 Premiere: a non-exact basis (no span) keeps the head",
          b65["report_text_excerpt"] == base.excerpt(PFILLER * 2 + "Since build 65 the timeline crashes constantly and the program freezes."))
    page = pr.adobe_bug_report_candidate("https://community.adobe.com/bug-reports-728/g53-synthetic-9991999",
                                         "<html><title>Crash</title><body><p>" + pbody + "</p></body></html>")
    check("B13 Premiere: a page-scrape candidate is not marked, so it keeps the head",
          page is not None and base.FIRST_POST_ONLY not in page
          and pr_row(page)["report_text_excerpt"] == base.excerpt(page["report_text"]))
    check("B14 Premiere: the accepted occurrence's basis is the alias the matcher accepted",
          prow.get("match_basis") in ("exact_version_text", "exact_version_alias"))


def _three_ways(builder, cand: dict) -> tuple[dict, dict, dict]:
    real = builder(cand)
    saved = (base.excerpt, base.excerpt_at)
    try:
        base.excerpt = lambda _t, width=280: "<<SENTINEL>>"
        base.excerpt_at = lambda _t, _s, _e, width=280: "<<SENTINEL>>"
        sentinel = builder(cand)
    finally:
        base.excerpt, base.excerpt_at = saved
    head_only = dict(cand)
    head_only.pop(base.FIRST_POST_ONLY, None)
    return real, sentinel, builder(head_only)


def _corpus() -> list[tuple[str, object, dict]]:
    out: list[tuple[str, object, dict]] = []
    bodies = [
        FILLER * 2 + f"Since installing Adobe Acrobat Reader {V} the app crashes whenever I open a scanned form.",
        FILLER * 2 + f"Adobe Acrobat Reader {V} works fine for us, the problem is the older build on the other desk.",
        FILLER * 2 + f"We rolled back from Adobe Acrobat Reader {V} and printing works again.",
        FILLER * 2 + f"Adobe Acrobat Reader {V} is installed. Is there a dark mode setting anywhere?",
        f"Adobe Acrobat Reader {V} crashes on launch after the update.",
        FILLER * 3,
    ]
    for i, b in enumerate(bodies):
        out.append((f"reader#{i}", lambda c: acr_row(c, REC_R), acr_topic(b, tid=9992000 + i)))
        pb = b.replace("Reader", "Pro")
        out.append((f"pro#{i}", lambda c: acr_row(c, REC_P), acr_topic(pb, title="Acrobat Pro stopped working", tid=9993000 + i)))
    pbodies = [
        PFILLER * 2 + f"After updating to Premiere Pro {PV} the timeline crashes every time I drag a clip.",
        PFILLER * 2 + f"Rolling back to Premiere Pro {PV} fixed the export crash for me.",
        PFILLER * 2 + "Since build 65 the timeline crashes constantly and the program freezes.",
        f"Premiere Pro {PV} crashes every time I drag a clip on the timeline.",
    ]
    for i, b in enumerate(pbodies):
        out.append((f"premiere#{i}", lambda c: pr_row(c, REC_PR), pr_topic(b, tid=9994000 + i)))
    # Reconstructions of stored Adobe rows: a neutral prefix pushes each stored excerpt past the cut.
    stored = [r for r in once("store", lambda: base.load_evidence(base.EVIDENCE_PATH))
              if r.get("product_id") in (ac.READER_ID, ac.PRO_ID, "adobe-premiere-pro") and r.get("counted") is True]
    records = {}
    for pid in (ac.READER_ID, ac.PRO_ID, "adobe-premiere-pro"):
        for rec in _memo_generated(pid, include_archived=True):
            records[(pid, rec.update_version)] = rec
    picked = stored[:8] + stored[-8:]
    for r in picked:
        rec = records.get((r["product_id"], str(r.get("update_version"))))
        if rec is None:
            continue
        cand = {"source_type": r.get("source_type"), "source_name": r.get("source_name"),
                "source_url": r.get("source_url"), "parent_title": r.get("parent_title") or "",
                "report_title": r.get("report_title") or "",
                "report_text": FILLER * 2 + str(r.get("report_text_excerpt") or ""),
                "source_date": str(r.get("source_date") or "")[:10], base.FIRST_POST_ONLY: True}
        if r["product_id"] == "adobe-premiere-pro":
            cand["premiere_board_verified"] = True
            out.append((f"stored:{r['id'][:40]}", lambda c, _rec=rec: pr_row(c, _rec), cand))
        else:
            out.append((f"stored:{r['id'][:40]}", lambda c, _rec=rec: acr_row(c, _rec), cand))
    return out


def part_c() -> None:
    print()
    print("=" * 92)
    print("PART C  excerpt independence: shipped, SENTINEL and head-only builders agree on everything else")
    print("=" * 92)
    corpus = _corpus()
    decisions = fields = reached = centred = counted = 0
    for label, builder, cand in corpus:
        real, sentinel, head = _three_ways(builder, cand)
        strip = lambda r: {k: v for k, v in r.items() if k != "report_text_excerpt"}  # noqa: E731
        if (real["counted"], real["exclusion_reason"]) != (sentinel["counted"], sentinel["exclusion_reason"]) or \
                (real["counted"], real["exclusion_reason"]) != (head["counted"], head["exclusion_reason"]):
            decisions += 1
            print(f"        decision differs: {label}")
        if strip(real) != strip(sentinel) or strip(real) != strip(head):
            fields += 1
            print(f"        field differs: {label}")
        reached += sentinel["report_text_excerpt"] == "<<SENTINEL>>"
        centred += real["report_text_excerpt"] != head["report_text_excerpt"]
        counted += real["counted"] is True
    n = len(corpus)
    check(f"C1 no acceptance decision differs across the three builders ({n} candidates)", decisions == 0, str(decisions))
    check("C2 no field other than the excerpt differs", fields == 0, str(fields))
    check("C3 non-vacuous: the SENTINEL reaches the stored field on every row", reached == n, f"{reached}/{n}")
    check(f"C4 non-vacuous: the shipped builder re-centres a real share of the corpus ({centred}/{n})",
          centred >= 10 and centred < n, f"{centred}/{n}")
    check("C5 non-vacuous: the corpus holds accepted and refused candidates", 0 < counted < n, f"{counted}/{n}")


def _calls_with_span(tree: ast.AST) -> list[str]:
    owners = []
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", "")) == "make_evidence_row" \
                        and any(k.arg == "excerpt_span" for k in node.keywords):
                    owners.append(fn.name)
    return owners


def part_d() -> None:
    print()
    print("=" * 92)
    print("PART D  every other collector is untouched")
    print("=" * 92)
    holders: dict[str, list[str]] = {}
    markers: dict[str, int] = {}
    for path in sorted((SCRIPTS / "patch_collectors").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        owners = _calls_with_span(tree)
        if owners:
            holders[path.name] = owners
        n = sum(1 for node in ast.walk(tree) if isinstance(node, ast.Dict)
                for k in node.keys if isinstance(k, ast.Name) and k.id == "FIRST_POST_ONLY")
        if n:
            markers[path.name] = n
    check("D1 only the two Adobe row builders pass an excerpt span",
          holders == {"adobe_acrobat_community.py": ["row_from_candidate"], "adobe_premiere.py": ["row_from_candidate"]},
          str(holders))
    check("D2 only the two opening-post candidate builders mark a candidate",
          markers == {"adobe_acrobat_community.py": 1, "adobe_premiere.py": 1}, str(markers))
    long_text = FILLER * 3 + "Now on 20.3.2 it freezes on launch."
    row = base.make_evidence_row(
        product_id="x", update_version="20.3.2", source_type="t", source_name="n", source_url="https://e.x/1",
        parent_title="", report_title="", report_text=long_text, captured_at=CAPTURED, source_date="",
        target_release_date="", patch_version_matched=True, matched_version="20.3.2", match_basis="exact_version_text",
        counted=True, exclusion_reason=None, issue_theme="", workflow_area="", platform="", severity="", sentiment="")
    check("D3 make_evidence_row without a span stores excerpt(report_text) exactly",
          row["report_text_excerpt"] == base.excerpt(long_text) and "20.3.2" not in row["report_text_excerpt"])
    from patch_collectors import davinci as dv                     # noqa: PLC0415
    drec = PatchRecord(product_id="blackmagic-davinci", update_version="20.3.2", path=Path("x.md"),
                       update_published_at="2026-02-01", update_status="stable", update_product="DaVinci Resolve")
    drow = dv.row_from_candidate(drec, {"source_url": "https://www.reddit.com/r/davinciresolve/comments/abc/crash",
                                        "source_type": "reddit_community_report", "parent_title": "Resolve crash",
                                        "report_title": "Resolve crash", "source_date": "2026-02-10",
                                        "report_text": long_text, base.FIRST_POST_ONLY: True}, CAPTURED)
    check("D4 a collector outside the scope keeps the head even for a marked candidate (DaVinci)",
          drow["report_text_excerpt"] == base.excerpt(long_text))


def part_e(store_rows: list[dict]) -> None:
    print()
    print("=" * 92)
    print("PART E  no backfill: a throwaway store, head versus centred new rows")
    print("=" * 92)
    from lib import collector_ownership, maturity                   # noqa: PLC0415
    import build_consensus_from_evidence as bc                      # noqa: PLC0415
    reader_recs = sorted(_memo_generated(ac.READER_ID), key=lambda r: (r.update_published_at, r.update_version))
    rec = reader_recs[-1]
    day = (rec.update_published_at or "2026-01-01")[:10]
    new_rows = []
    for i, theme in enumerate(("crashes whenever I open a scanned form", "freezes when printing a long contract",
                               "fails to save a signed form")):
        body = FILLER * 2 + f"Since installing Adobe Acrobat Reader {rec.update_version} the app {theme}."
        cand = ac._topic_to_candidate({"url": f"https://community.adobe.com/questions-9/g53-replay-{9995000 + i}",
                                       "title": "Reader problem after the update",
                                       "firstPost": {"content": f"<p>{body}</p>", "creationDate": f"{day}T12:00:00Z"}})
        new_rows.append((ac.row_from_candidate(ac.READER_ID, rec, cand, CAPTURED), cand))
    centred = [r for r, _c in new_rows]
    heads = [dict(r, report_text_excerpt=base.excerpt(c["report_text"])) for r, c in new_rows]
    check("E1 the replay rows are accepted, new, and centred (non-vacuous)",
          all(r["counted"] is True for r in centred) and all(a["report_text_excerpt"] != b["report_text_excerpt"]
                                                             for a, b in zip(centred, heads)),
          str([(r["counted"], r["exclusion_reason"]) for r in centred]))
    original = base.EVIDENCE_PATH.read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        stores = {}
        for name, rows in (("head", heads), ("centred", centred)):
            path = Path(tmp) / f"{name}.yml"
            path.write_bytes(original)
            added, _total, _all = base.append_evidence_rows([dict(r) for r in rows], path)
            data = path.read_bytes()
            stores[name] = (added, data)
            check(f"E2 {name}: every existing byte is kept (sha256 of the original prefix unchanged)",
                  hashlib.sha256(data[:len(original)]).hexdigest() == hashlib.sha256(original).hexdigest())
            try:
                collector_ownership.validate_evidence(ac.READER_ID, original.decode("utf-8"), data.decode("utf-8"))
                ok = True
            except Exception as exc:                                  # noqa: BLE001
                ok = False
                print(f"        {exc}")
            check(f"E3 {name}: collector ownership validation passes", ok and added == len(rows), f"added={added}")
        held = next(r for r in store_rows if r.get("product_id") == ac.READER_ID and r.get("counted") is True)
        again = dict(held, report_text_excerpt="...a centred excerpt a rediscovery would carry...")
        path = Path(tmp) / "rediscovery.yml"
        path.write_bytes(original)
        added, _t, _a = base.append_evidence_rows([again], path)
        check("E4 a rediscovered stored row is refused and the stored bytes are untouched",
              added == 0 and path.read_bytes() == original)
        loaded = {name: base.load_evidence(Path(tmp) / f"{name}.yml") for name in ("head", "centred")}
    facts = once("facts", bc.record_fact_index)

    def aggregate(rows):
        groups = bc.counted_evidence_rows(rows, windows_targets=once("targets", bc.windows_target_index))
        out = {}
        statuses = {k: str(v.get("update_status") or "") for k, v in facts.items()}
        for (pid, ver, build), items in sorted(groups.items()):
            if pid != ac.READER_ID or ver != rec.update_version:
                continue
            sentiments = bc.Counter(str(i.get("sentiment")).lower() for i in items)
            themes = bc.issue_counter(pid, items)
            key = bc.patch_key(pid, ver, build)
            decision, _f = bc.policy_decision(pid, ver, build, items, facts.get(key), facts)
            out[(pid, ver, build)] = {
                "ids": sorted(str(i.get("id")) for i in items), "label": bc.consensus_label(sentiments),
                "confidence": bc.confidence(len(items)), "state": bc.evidence_state(len(items)),
                "themes": dict(themes), "summary": bc.consensus_summary(pid, ver, items, sentiments, themes, build,
                                                                       statuses.get(key, ""), record=facts.get(key), records=facts),
                "decision": repr(decision),
                "maturity": maturity.maturity_for(len(items)),
            }
        return out
    a_head, a_cent = aggregate(loaded["head"]), aggregate(loaded["centred"])
    check("E5 the page's counted population includes the new rows (non-vacuous)",
          bool(a_head) and all(r["id"] in next(iter(a_head.values()))["ids"] for r in centred))
    check("E6 counts, labels, themes, summary, verdict and maturity are identical, head versus centred",
          a_head == a_cent, str([k for k in (next(iter(a_head.values())) if a_head else {}) if a_head and a_cent
                                 and next(iter(a_head.values()))[k] != next(iter(a_cent.values()))[k]]))
    # The excerpt's structured fact (G68, lib.evidence_facts) is derived from the excerpt by the persistence
    # boundary, so it moves with it and is not a second difference.
    derived = set(base.evidence_facts.STORED_FIELDS)
    diff = [(x.get("id"), k) for x, y in zip(loaded["head"], loaded["centred"]) for k in set(x) | set(y)
            if k not in derived and x.get(k) != y.get(k)]
    facts_follow = all(y.get(k) == base.evidence_facts.compute_facts(y)[k]
                       for y in loaded["centred"] for k in derived if base.evidence_facts.carries_facts(y))
    check("E7 the only difference between the two stores is the new rows' excerpt",
          len(diff) == len(centred) and all(k == "report_text_excerpt" for _i, k in diff) and facts_follow,
          str(diff[:4]))


def part_f() -> None:
    print()
    print("=" * 92)
    print("PART F  readers: Level 2/3 inputs keep the head, a shared report gets one excerpt")
    print("=" * 92)
    unmatched = acr_topic(FILLER * 2 + "Since the latest Adobe Acrobat Reader update the app crashes whenever I open a scanned form.")
    accepted, rejected = ac.evaluate_candidates(ac.READER_ID, REC_R, [unmatched], CAPTURED)
    row = (rejected or accepted or [{}])[0]
    check("F1 a no-match row (the only reason Levels 2/3 tier) keeps the head excerpt",
          row.get("exclusion_reason") == "missing_exact_patch_version_match"
          and row.get("report_text_excerpt") == base.excerpt(unmatched["report_text"]), str(row.get("exclusion_reason")))
    shared = acr_topic(FILLER * 2 + f"Both Adobe Acrobat Reader and Acrobat Pro {V} crash whenever I open a scanned form.",
                       title="Acrobat crash")
    r1, r2 = acr_row(shared, REC_R), acr_row(shared, REC_P)
    check("F2 a report shared by Reader and Pro stores one identical, centred excerpt on both",
          r1["report_text_excerpt"] == r2["report_text_excerpt"] and V in r1["report_text_excerpt"]
          and r1["counted"] is True and r2["counted"] is True)


def part_g(store_rows: list[dict]) -> None:
    print()
    print("=" * 92)
    print("PART G  reviewed verdict reasons")
    print("=" * 92)
    from lib import report_counts, verdict_reasons                   # noqa: PLC0415
    import build_consensus_from_evidence as bc                      # noqa: PLC0415
    entries = verdict_reasons.load_reasons()
    targets = once("targets", bc.windows_target_index)
    by_identity = {verdict_reasons.record_identity(r): r for r in once("facts", bc.record_fact_index).values()}

    def support(rows):
        groups = report_counts.counted_evidence_rows(rows, windows_targets=targets)
        return {e["id"]: verdict_reasons.support_problems(
            e, groups.get(verdict_reasons.reason_identity(e), []), by_identity) for e in entries}
    before = support(store_rows)
    acr_entries = [e for e in entries if e.get("product_id") in (ac.READER_ID, ac.PRO_ID)]
    extra = []
    for e in acr_entries:
        rec = next((r for r in _memo_generated(e["product_id"], include_archived=True)
                    if r.update_version == str(e["update_version"])), None)
        if rec is None:
            continue
        body = FILLER * 2 + f"Installing Adobe Acrobat Pro {rec.update_version} fails with Exit Code 7 every time."
        cand = ac._topic_to_candidate({"url": f"https://community.adobe.com/questions-9/g53-support-{len(extra) + 9996000}",
                                       "title": "Install fails", "firstPost": {"content": f"<p>{body}</p>",
                                                                              "creationDate": "2026-11-01T00:00:00Z"}})
        extra.append(ac.row_from_candidate(rec.product_id, rec, cand, CAPTURED))
    after = support(store_rows + extra)
    check("G1 new centred rows on a reviewed page change no live entry's support (non-vacuous: rows added)",
          bool(acr_entries) and len(extra) == len(acr_entries) and before == after, f"{len(extra)} rows")
    # The cross-policy pair (documented, not fixed: support_problems is out of scope). Two copies of one
    # post, one stored under the head rule and one under the window, no longer compare equal, so the
    # "identical excerpt = one reporter" reduction misses them. Two NEW copies still compare equal.
    text = FILLER * 2 + f"Adobe Acrobat Pro {V} fails with Exit Code 7."
    s, e = span(text, V)
    head, window = base.excerpt(text), base.excerpt_at(text, s, e)
    norm = verdict_reasons._norm_excerpt
    check("G2 two new copies of one post carry identical excerpts (the reduction still holds for them)",
          norm({"report_text_excerpt": base.excerpt_at(text, s, e)}) == norm({"report_text_excerpt": window}))
    check("G3 documented: a head-rule copy and a window-rule copy of one post do NOT compare equal",
          norm({"report_text_excerpt": head}) != norm({"report_text_excerpt": window}))
    header = (ROOT / "_data" / "verdict_reasons.yml").read_text(encoding="utf-8").split("schema_version:", 1)[0]
    check("G4 the reviewed file's header tells reviewers about the cross-policy pair",
          "AUX-109" in header and "excerpt" in header)


def part_h() -> None:
    print()
    print("=" * 92)
    print("PART H  the shadow producer reads the excerpt, so its activation switch stays off")
    print("=" * 92)
    from lib import verdict_reason_producer as vrp                  # noqa: PLC0415
    body = ("Exit Code 7 again on the Acrobat Pro installer, error DW003, the log shows it. " + FILLER * 2
            + f"The build is Adobe Acrobat Pro {V} and it never finishes installing.")
    row = acr_row(acr_topic(body, title="Installer fails"), REC_P)
    head_row = dict(row, report_text_excerpt=base.excerpt(acr_topic(body, title="Installer fails")["report_text"]))
    a, b = vrp.acrobat_install_row(head_row, ac.PRO_ID, V), vrp.acrobat_install_row(row, ac.PRO_ID, V)
    check("H1 documented dependency: one post read through the head and through the window gives a different "
          "install-row outcome", a["ok"] != b["ok"] or a["codes"] != b["codes"], f"head={a} window={b}")
    check("H2 the activation switch is OFF", vrp.PUBLIC_AUTO_ACTIVATION is False)
    # Scoped to the comment block DIRECTLY above the assignment (statement-scoped, not module-scoped),
    # and to the sentences that carry the governance, not to words that occur anywhere near them.
    lines = (SCRIPTS / "lib" / "verdict_reason_producer.py").read_text(encoding="utf-8").splitlines()
    at = lines.index("PUBLIC_AUTO_ACTIVATION = False") if "PUBLIC_AUTO_ACTIVATION = False" in lines else -1
    block: list[str] = []
    i = at - 1
    while at > 0 and i >= 0 and lines[i].startswith("#"):
        block.insert(0, lines[i].lstrip("# ").rstrip())
        i -= 1
    note = " ".join(" ".join(block).split())
    needed = ("THE ONE ACTIVATION SWITCH. TEMPORARY", "EXCERPT DEPENDENCY (AUX-109)",
              "This producer reads `report_text_excerpt`",
              "Turning this switch on therefore needs its own approval covering this dependency")
    check("H3 the switch's TEMPORARY note records the excerpt dependency (AUX-109) directly above it",
          at > 0 and all(s in note for s in needed), str([s for s in needed if s not in note]))


def part_i() -> None:
    print()
    print("=" * 92)
    print("PART I  privacy: what a window must not carry")
    print("=" * 92)

    def win(text: str, token: str = V) -> str:
        """The window, or a marker the checks below fail on when the text was not re-centred at all."""
        s, e = span(text, token)
        got = base.excerpt_at(text, s, e)
        return got if token in got and got != base.excerpt(text) else "<<NOT CENTRED>>"

    def keeps_out(label: str, text: str, *words: str) -> None:
        w = win(text)
        check(label, V in w and not any(word in w for word in words), w)
    keeps_out("I1 a greeting and the name it addresses stay out of the window",
              FILLER * 2 + f"Hi Maria Lopez, after updating to {V} the form tool crashes when I sign. " + FILLER, "Maria")
    keeps_out("I2 an @handle and its display name stay out",
              FILLER * 2 + f"Hi @jsmith_77 Jane Smith, after updating to {V} the form tool crashes. " + FILLER,
              "jsmith", "Jane")
    keeps_out("I3 an e-mail address stays out",
              FILLER * 2 + f"Write to jane.smith@example.com about it: after updating to {V} the form tool crashes. "
              + FILLER, "@", "jane")
    keeps_out("I4 a sign-off and the name after it stay out",
              FILLER * 3 + f"After updating to {V} the form tool crashes. Thanks in advance, Maria Lopez",
              "Maria", "Thanks")
    # The version's own sentence runs into the tail here, so the tail rule alone would let the
    # signature through: the dash rule is what keeps it out.
    keeps_out("I5 a dash signature closing the version's own sentence stays out",
              FILLER * 3 + f"After updating to {V} the form tool crashes every time I sign a contract in the "
              "office on the second floor -- Bob Jones.", "Bob")
    # Far from the post's end, so only the sign-off rule stops the window at "thanks".
    keeps_out("I6 a thanks to a named person after the version stays out",
              FILLER * 3 + f"After updating to {V} the form tool crashes every time, thanks to Maria Lopez for "
              "checking it on her desk. " + FILLER, "Maria")
    keeps_out("I7 an unrecognised sign-off after the version's sentence stays out (the tail rule)",
              FILLER * 3 + f"After updating to {V} the form tool crashes. Bob from accounting", "Bob")
    keeps_out("I8 a signature block in the post's last characters stays out when the version is earlier",
              FILLER * 4 + f"After updating to {V} the form tool crashes. " + FILLER
              + "Regards, Maria Lopez, IT, Contoso Ltd.", "Maria", "Contoso")
    keeps_out("I9 a 'Sent from my' line stays out",
              FILLER * 3 + f"After updating to {V} the form tool crashes. Sent from my phone", "phone")
    keeps_out("I10 a sign-off with no sentence end before it stays out",
              FILLER * 3 + f"After updating to {V} the form tool crashes cheers Bob", "Bob")
    keeps_out("I11 an @mention after the version stays out",
              FILLER * 3 + f"After updating to {V} the form tool crashes, same as @kim_r reported on her desk. "
              + FILLER, "kim_r")
    keeps_out("I12 a sign-off BEFORE a postscript that names the version stays out",
              FILLER * 3 + f"The form tool crashes when I sign. Thanks, Maria Lopez. Edit: the version is {V} on "
              "every desk here. " + FILLER, "Maria", "Thanks")
    keeps_out("I13 ... also when no sentence end separates that sign-off from the version",
              FILLER * 3 + f"The form tool crashes when I sign. Regards Maria Lopez PS version {V} on every desk "
              "here. " + FILLER, "Maria", "Regards")
    t = FILLER * 3 + f"Contact {V}@example.com for the crash log please, the tool crashes."
    s, e = span(t, V)
    check("I14 an occurrence inside an e-mail address keeps the head (no window is cut through it)",
          base.excerpt_at(t, s, e) == base.excerpt(t))
    t = f"Hi Maria, Adobe Acrobat Reader {V} crashes. " + FILLER
    s, e = span(t, V)
    check("I15 out of scope, stated: a head the change does not touch is stored as today, names included",
          base.excerpt_at(t, s, e) == base.excerpt(t) and "Maria" in base.excerpt(t))
    t = FILLER * 2 + f"After updating to {V} the form tool crashes and I see an error. " + FILLER
    check("I16 a window with nothing to keep out still uses (almost) the whole cap",
          V in win(t) and len(win(t)) >= 260, str(len(win(t))))


def run_suite() -> int:
    store_rows = once("store", lambda: base.load_evidence(base.EVIDENCE_PATH))
    for part in (part_a, part_b, part_c, part_d, part_f, part_h, part_i):
        try:
            part()
        except Exception:                                             # noqa: BLE001
            check(f"{part.__name__} ran without an exception", False, traceback.format_exc(limit=3))
    for part in (part_e, part_g):
        try:
            part(store_rows)
        except Exception:                                             # noqa: BLE001
            check(f"{part.__name__} ran without an exception", False, traceback.format_exc(limit=3))
    print()
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        for label in FAILURES:
            print(f"  - {label}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(run_suite())
