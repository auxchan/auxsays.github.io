#!/usr/bin/env python3
"""Premiere's keyless Adobe Community discovery chain, and the gates it must not loosen.

WHY THIS SUITE EXISTS SEPARATELY. `test_adobe_premiere_collector.py` is in the [network] category
and does not gate a pull request. This one is fully offline -- every HTTP call is stubbed -- so the
acquisition chain and the identity gates it depends on are actually checked before merge.

WHAT THE CHAIN IS. searchToken -> Algolia -> getTopics. It DISCOVERS topic ids; it never supplies
evidence. The snippet, the title and the Algolia rank are all discarded, and the row is built from
the hydrated opening post and judged by the same authority every other Premiere method goes through.

WHAT SCOPES IT. Adobe's own taxonomy, measured live on 2026-10-07: category 726 "Adobe Premiere",
forum 728 "Bug Reports". The same index serves After Effects (526), Adobe Media Encoder (503),
Premiere Elements (723) and Premiere Rush (735) -- several with their own Bug Reports boards -- so a
URL shape or a product regex is not enough on its own.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_premiere_algolia_discovery.py
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402
from patch_collectors import adobe_premiere as premiere  # noqa: E402
from patch_collectors.base import CollectorContext, PatchRecord  # noqa: E402

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
        _ERRORS.append(label)
        print("  FAIL  " + label + ("  --  " + str(detail)[:300] if detail else ""))


RECORD = PatchRecord(product_id="adobe-premiere-pro", update_version="26.2",
                     path=Path("2026-04-30-premiere-pro-26-2.md"),
                     update_published_at="2026-04-16T00:00:00Z", update_status="current",
                     update_product="Adobe Premiere Pro")
RECORD_222 = PatchRecord(product_id="adobe-premiere-pro", update_version="26.2.2",
                         path=Path("2026-05-01-premiere-pro-26-2-2.md"),
                         update_published_at="2026-05-01T00:00:00Z", update_status="current",
                         update_product="Adobe Premiere Pro")
CTX = CollectorContext(write=False, since=None, max_pages=1)
URL = "https://community.adobe.com/bug-reports-728/premiere-pro-26-2-timeline-crash-1559001"


def topic(*, tid=1559001, forum=728, category=726, url=URL,
          title="Premiere Pro 26.2 timeline crash",
          content="<p>Premiere Pro 26.2 crashes every time I drag a clip on the timeline.</p>",
          created="2026-04-20T10:00:00+0000"):
    """A hydrated getTopics record, in the shape Adobe actually returns."""
    return {
        "id": tid, "title": title, "url": url,
        "forum": {"id": forum, "title": "Bug Reports"},
        "category": {"categoryId": category, "title": "Adobe Premiere"},
        "firstPost": {"id": tid, "content": content, "creationDate": created,
                      "author": {"id": 1, "name": "someone"}, "url": url},
        "lastPost": {"id": 99, "author": {"id": 2, "name": "someone else"}},
    }


def hit(*, tid=1559001, forum=728, category=726, title="Premiere Pro 26.2 timeline crash"):
    """An Algolia search hit. Only its id and facets are ever used."""
    return {"id": tid, "forum": forum, "category": category, "title": title,
            "first_post": "a snippet that must never become evidence",
            "date_added": 1776600000, "topic_url": f"/topic/show?tid={tid}&fid={forum}"}


def drive(*, token=None, hits=None, topics=None, record=RECORD, fail=None):
    """Run the real discovery method with every HTTP call stubbed. Returns (candidates, errors)."""
    token = token if token is not None else {
        "client_id": "APPID", "token": "KEY", "availableIndexes": [premiere.ALGOLIA_INDEX]}
    calls: list[str] = []

    def fake(url, *, data=None, timeout=30, max_bytes=0):
        calls.append(url)
        if fail and fail(url, data):
            raise premiere.AlgoliaChainError("http_429_error")
        if url == premiere.ADOBE_SEARCH_TOKEN_URL:
            return token
        if "algolia.net" in url:
            return {"hits": list(hits if hits is not None else [])}
        # Honour the ids the request actually asked for. A stub that returns everything regardless
        # would test the stub rather than the cap the collector applies at request time.
        wanted = {t for t in urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("topicIds[]", [])}
        return [t for t in (topics or []) if not wanted or str(t.get("id")) in wanted]

    original = premiere.algolia_request_json
    premiere.algolia_request_json = fake
    errors: list[dict] = []
    try:
        candidates = premiere.adobe_community_algolia_search_candidates(record, CTX, errors)
    finally:
        premiere.algolia_request_json = original
    return candidates, errors, calls


def judge(candidate, record=RECORD):
    return premiere.row_from_candidate(record, candidate, "2026-10-07T00:00:00Z")


def run() -> int:
    print("=" * 78)
    print("Premiere keyless Adobe Community discovery (searchToken -> Algolia -> getTopics)")
    print("=" * 78)

    # ---------- A: the index is pinned by NAME, and a wrong one fails closed ----------
    print("\n[A] the index")
    check("A1 the index is pinned to one exact name",
          premiere.ALGOLIA_INDEX == "adobedme-en-unified", premiere.ALGOLIA_INDEX)
    cands, errors, _ = drive(token={"client_id": "A", "token": "K",
                                    "availableIndexes": ["adobedme-en-unified"]})
    check("A2 the expected index is accepted", not any(
        "index_unavailable" in str(e.get("reason")) for e in errors), str(errors))
    _c, errors, calls = drive(token={"client_id": "A", "token": "K",
                                     "availableIndexes": ["something-else"]})
    check("A3 a missing index fails CLOSED rather than searching whatever is first",
          any(str(e.get("reason")) == "searchtoken_index_unavailable" for e in errors), str(errors))
    check("A4 and no query is sent after that refusal",
          not any("algolia.net" in c for c in calls), str(calls))
    _c, errors, _ = drive(token={"client_id": "", "token": "", "availableIndexes": [premiere.ALGOLIA_INDEX]})
    check("A5 incomplete credentials also fail closed",
          any("incomplete" in str(e.get("reason")) for e in errors), str(errors))

    # ---------- B: structural scope ----------
    print("\n[B] Adobe's own taxonomy is the scope")
    check("B1 the query is filtered to the Premiere category AND its Bug Reports forum",
          premiere.ALGOLIA_FILTERS == "category:726 AND forum:728", premiere.ALGOLIA_FILTERS)
    check("B2 the category and forum are named constants, not literals in a query string",
          premiere.PREMIERE_CATEGORY_ID == 726 and premiere.PREMIERE_BUG_FORUM_ID == 728)
    cands, _e, _c = drive(hits=[hit()], topics=[topic()])
    check("B3 a Premiere bug report on board 728 is discovered", len(cands) == 1, str(cands))
    # Announcements live inside the SAME Premiere category. Scoping on category alone would let an
    # Adobe release announcement into the funnel, and it passes the issue and URL gates.
    cands, _e, _c = drive(hits=[hit(forum=727)], topics=[topic(forum=727)])
    check("B4 an Announcements thread in the same category is not discovered", not cands, str(cands))
    # Foreign Adobe products share this index, several with their own Bug Reports board.
    for label, cat, frm in (("After Effects", 526, 529), ("Adobe Media Encoder", 503, 505),
                            ("Premiere Elements", 723, 725), ("Premiere (Beta)", 731, 733)):
        cands, _e, _c = drive(hits=[hit(category=cat, forum=frm)],
                              topics=[topic(category=cat, forum=frm)])
        check(f"B5 a {label} report is not discovered as Premiere", not cands, str(cands))
    # The hydrated record is re-checked, so a filter the search silently dropped cannot leak.
    cands, _e, _c = drive(hits=[hit()], topics=[topic(category=526, forum=529)])
    check("B6 a hit that passes search but hydrates foreign is still refused", not cands, str(cands))

    # ---------- C: the URL gate is pinned to Premiere's board ----------
    print("\n[C] the URL gate")
    spec = premiere.adobe_report_url_is_specific
    check("C1 a Premiere bug-report URL is specific", spec(URL))
    check("C2 another Adobe product's bug board is NOT accepted",
          not spec("https://community.adobe.com/bug-reports-505/media-encoder-26-2-crash-1234567"))
    check("C3 a board listing page is not a report",
          not spec("https://community.adobe.com/t5/premiere-pro-discussions/bd-p/premiere-pro?page=1"))
    check("C4 a search page is not a report",
          not spec("https://community.adobe.com/t5/forums/searchpage/tab/message"))
    cands, _e, _c = drive(hits=[hit()], topics=[topic(url="https://community.adobe.com/t5/premiere-pro-discussions/bd-p/premiere-pro?page=1")])
    check("C5 a hydrated topic whose URL is a listing page yields no candidate", not cands, str(cands))

    # ---------- D: evidence comes from the hydrated opening post ----------
    print("\n[D] discovery is not evidence")
    cands, _e, _c = drive(hits=[hit()], topics=[topic()])
    text = str(cands[0]["report_text"]) if cands else ""
    check("D1 the candidate's text is the opening post, not the search snippet",
          "snippet" not in text and "crashes every time" in text, text[:120])
    check("D2 a reply's text is never folded in",
          cands and "someone else" not in str(cands[0]), str(cands)[:160])
    check("D3 the date is the opening post's own creation date",
          cands and str(cands[0]["source_date"]) == "2026-04-20",
          str(cands[0]["source_date"]) if cands else "-")
    cands, _e, _c = drive(hits=[hit()], topics=[topic(created="")])
    check("D4 no establishable opening-post date means no candidate", not cands, str(cands))
    cands, _e, _c = drive(hits=[hit()], topics=[topic(content="")])
    check("D5 an empty opening post yields no candidate", not cands, str(cands))


    # ---------- E: product context, from the words OR from the board ----------
    print("\n[E] product context")
    def board_candidate(body, url=URL, verified=True):
        c = {"source_type": premiere.SOURCE_TYPE, "source_name": "Adobe Community Bug Report",
             "source_url": url, "parent_title": body.split(".")[0][:70], "report_title": body.split(".")[0][:70],
             "report_text": body, "source_date": "2026-04-20"}
        if verified:
            c["premiere_board_verified"] = True
        return c

    for label, body in (
            ("Premiere Pro 26.2", "Premiere Pro 26.2 crashes every time I drag a clip on the timeline."),
            ("Adobe Premiere 26.2", "Adobe Premiere 26.2 crashes every time I drag a clip on the timeline."),
            ("Premiere 26.2 build 65", "Premiere 26.2 build 65: the interface hangs and the timeline crashes."),
            ("bare version on the board", "Updated to 26.2 and now the timeline crashes whenever I drag a clip.")):
        row = judge(board_candidate(body))
        check(f"E1 {label} counts when the board established the product",
              row.get("counted") is True, str(row.get("exclusion_reason")))
    # Off the board, the phrase is still required -- Reddit and Creative COW have no taxonomy.
    row = judge(board_candidate("Updated to 26.2 and now the timeline crashes whenever I drag a clip.",
                                verified=False))
    check("E2 off-board, a report naming no product is still refused",
          row.get("counted") is not True and "product_context" in str(row.get("exclusion_reason")),
          str(row.get("exclusion_reason")))
    # The board establishes the PRODUCT. It must never establish the VERSION.
    row = judge(board_candidate("Build 65 makes the timeline crash constantly."))
    check("E3 the board cannot manufacture a patch identity from build 65 alone",
          row.get("counted") is not True, str(row.get("exclusion_reason")))
    # Asserted on the predicate too, not only on the row: the row is refused earlier by the version
    # gate, so a change letting provenance stand in for the version would pass the row-level check
    # while being exactly the defect. The version must come from the AUTHOR'S text either way.
    check("E3b board provenance alone never satisfies the build-65 version context",
          premiere.premiere_build_65_context("Build 65 makes the timeline crash.", "26.2",
                                             board_verified=True) is False)
    check("E3c with the version present, the board resolves the wording the phrase gate refused",
          premiere.premiere_build_65_context("Premiere 26.2 build 65 hangs the interface.", "26.2",
                                             board_verified=True) is True)
    check("E3d and off the board that same wording still needs the full phrase",
          premiere.premiere_build_65_context("Premiere 26.2 build 65 hangs the interface.", "26.2",
                                             board_verified=False) is False)
    # A foreign product named as the failing one is refused even on a Premiere URL.
    for other in ("Photoshop", "After Effects", "Audition", "Media Encoder"):
        row = judge(board_candidate(f"{other} 26.2 crashes on export every single time."))
        check(f"E4 a report blaming {other} does not become Premiere evidence",
              row.get("counted") is not True, str(row.get("exclusion_reason")))

    # ---------- F: which version is the AFFECTED one ----------
    print("\n[F] the tracked version must be the affected one")
    row = judge(board_candidate("Premiere Pro 26.2 crashes every time I drag a clip on the timeline."))
    check("F1 a plain failure claim about 26.2 counts", row.get("counted") is True,
          str(row.get("exclusion_reason")))
    for label, body in (
            ("rollback target", "Premiere Pro 26.3 crashes constantly. Rolling back to 26.2 fixed it."),
            ("fix target", "The timeline crash is fixed in Premiere Pro 26.2."),
            ("known-good comparison", "Premiere Pro 26.3 crashes on export. 26.2 works fine for me."),
            ("reverted to", "Reverting to Premiere Pro 26.2 stopped the crashing on 26.3.")):
        row = judge(board_candidate(body))
        check(f"F2 a {label} is not a failure claim about 26.2",
              row.get("counted") is not True, f"{row.get('counted')} {row.get('exclusion_reason')}")
    # 26.2 must not satisfy 26.2.2, in either direction.
    row = judge(board_candidate("Premiere Pro 26.2 crashes on the timeline."), record=RECORD_222)
    check("F3 a 26.2 report does not count for 26.2.2",
          row.get("counted") is not True, str(row.get("exclusion_reason")))
    row = judge(board_candidate("Premiere Pro 26.2.2 crashes on the timeline."), record=RECORD)
    check("F4 a 26.2.2 report does not count for 26.2",
          row.get("counted") is not True, str(row.get("exclusion_reason")))
    row = judge(board_candidate("Upgrade to Premiere Pro 26.2.2 to fix this crash."), record=RECORD_222)
    check("F5 an upgrade-target claim does not count for the version it names",
          row.get("counted") is not True, str(row.get("exclusion_reason")))
    check("F6 every counted row carries equal weight",
          judge(board_candidate("Premiere Pro 26.2 crashes on the timeline.")).get("source_weight") == 1)

    # KEEP-COUNTABLE counterparts. A veto that also eats real failure claims costs more than the
    # leak it closes, so each directional cue is paired with the phrasing it must NOT refuse.
    for label, body in (
            ("still not fixed in", "The timeline crash is still not fixed in Premiere Pro 26.2 and happens daily."),
            ("rolled back FROM", "I rolled back from Premiere Pro 26.2 because the timeline kept crashing."),
            ("mentions Media Encoder elsewhere",
             "Premiere Pro 26.2 crashes on the timeline. Media Encoder was updated at the same time."),
            ("mentions a rollback target later",
             "Premiere Pro 26.2 crashes constantly. I may have to roll back to 26.0.2.")):
        row = judge(board_candidate(body))
        check(f"F7 '{label}' remains a failure claim about 26.2",
              row.get("counted") is True, str(row.get("exclusion_reason")))


    # A version named as the one that STILL WORKS, measured on the live board. lib.target_outcome
    # reads a failure noun sitting BEFORE the version as "affected", so this real 26.2.2 report
    # was counted against the version its author named as working.
    for label, body, ver, want_veto in (
            ("known-good in a parenthetical",
             "Premiere Pro 26.3.0 Regression: Reconnect Full Resolution Media hangs indefinitely "
             "with attached proxies (26.2.2 works correctly)", "26.2.2", True),
            ("works until it crashes",
             "Premiere Pro 26.2.2 works fine until I export, then it crashes every time.", "26.2.2", False),
            ("still not working",
             "Premiere Pro 26.2.2 is still not working after the update; the timeline crashes.", "26.2.2", False),
            ("stopped working",
             "Premiere Pro 26.2.2 stopped working entirely after I updated.", "26.2.2", False)):
        veto = premiere.premiere_version_role_veto(body, ver)
        check(f"F8 {label} -> {'vetoed' if want_veto else 'counted'}",
              bool(veto) is want_veto, f"veto={veto!r}")
    # ---------- G: bounded, and honest about it ----------
    print("\n[G] bounds and method health")
    many_hits = [hit(tid=1559000 + i) for i in range(premiere.MAX_TOPIC_IDS_PER_RECORD + 7)]
    many_topics = [topic(tid=1559000 + i,
                         url=f"https://community.adobe.com/bug-reports-728/premiere-pro-26-2-crash-{1559000 + i}")
                   for i in range(premiere.MAX_TOPIC_IDS_PER_RECORD + 7)]
    cands, errors, calls = drive(hits=many_hits, topics=many_topics)
    truncation = [e for e in errors if str(e.get("reason", "")).startswith(premiere.ALGOLIA_TRUNCATED)]
    check("G1 a capped topic population is RECORDED, not absorbed", truncation, str(errors)[:200])
    check("G2 hydration is chunked rather than sent as one oversized request",
          sum(1 for c in calls if "getTopics" in c) >= 2, str([c[:40] for c in calls]))
    check("G3 the cap is honoured", len(cands) <= premiere.MAX_TOPIC_IDS_PER_RECORD, len(cands))

    status = premiere.adobe_community_method_status
    check("G4 a clean query with nothing to find is no_results",
          status([], [], [], []) == "no_results")
    check("G5 a transport refusal is blocked, never 'nothing found'",
          status([], [], [], [{"reason": "adobe_algolia_search_failed:http_429_error"}]) == "blocked")
    check("G6 a schema failure is broken",
          status([], [], [], [{"reason": "adobe_algolia_schema_unexpected"}]) == "broken")
    check("G7 a missing index is broken, not blocked",
          status([], [], [], [{"reason": "searchtoken_index_unavailable"}]) == "broken")
    _c, errors, _calls = drive(hits=[hit()], topics=[topic()],
                               fail=lambda url, data: "algolia.net" in url)
    check("G8 a refused Algolia query is recorded as a fetch failure",
          any("algolia_search_failed" in str(e.get("reason")) for e in errors), str(errors))

    # ---------- H: what the sprint before this one established must still hold ----------
    print("\n[H] the Phase-A state is not re-opened")
    store = yaml.safe_load((_REPO / "auxsays" / "_data" / "consensus_evidence.yml")
                           .read_text(encoding="utf-8")) or {}
    rows = [r for r in (store.get("evidence") or []) if r.get("product_id") == "adobe-premiere-pro"]
    withdrawn = [r for r in rows if r.get("counted") is False]
    check("H1 the three withdrawn rows are still withdrawn, with reasons",
          len(withdrawn) == 3 and all(str(r.get("exclusion_reason") or "").strip() for r in withdrawn),
          str([(str(r.get("id"))[:34], r.get("exclusion_reason")) for r in withdrawn]))
    check("H2 the board listing url still counts for nothing",
          not any(r.get("counted") is True and "bd-p/premiere-pro" in str(r.get("source_url"))
                  for r in rows))
    # Rediscovering a withdrawn report's TITLE must not rehabilitate it. The dead one 404s, so the
    # chain cannot hydrate it at all; the listing rows have no report URL to rediscover.
    dead = [r for r in withdrawn if "ui-lag-and-freezing" in str(r.get("source_url"))]
    check("H3 the unresolvable report is still refused under its own reason",
          len(dead) == 1 and str(dead[0].get("exclusion_reason")) == "source_report_no_longer_resolves",
          str([r.get("exclusion_reason") for r in dead]))

    from lib.collector_ownership import allowed_methods, allowed_source_types
    check("H4 the new method is authorised for this product",
          "adobe_community_algolia_search" in allowed_methods("adobe-premiere-pro"),
          str(sorted(allowed_methods("adobe-premiere-pro"))))
    check("H5 it reuses the existing source identity, so one report is not two rows",
          premiere.SOURCE_TYPE in allowed_source_types("adobe-premiere-pro")
          and premiere.method_source_type("adobe_community_algolia_search") == premiere.SOURCE_TYPE,
          premiere.method_source_type("adobe_community_algolia_search"))
    # Was: "first in the method tuple", asserted by reading collect_for_record.__code__.co_consts.
    # The flat tuple is gone -- the nine methods are now routed from the shared plan -- and the
    # guarantee is strictly stronger than position: Algolia is the sole PRIMARY and the chains
    # that no longer answer are not merely later, they do not run.
    from lib.method_routing import plan_methods
    _plan = plan_methods("adobe-premiere-pro")
    check("H6 it is the sole primary, and the chains that no longer answer are not run at all",
          _plan["primary"] == ["adobe_community_algolia_search"]
          and {"adobe_community_search", "adobe_community_bug_tab_index", "reddit_search",
               "brave_search_api", "creativecow_forum_index", "creativecow_brave_search"}
          <= set(_plan["disabled"]),
          f"primary={_plan['primary']} disabled={_plan['disabled']}")

    from lib.acquisition_methods import METHODS
    entry = next((m for m in METHODS if m.get("method_id") == "adobe_community_algolia_search"), None)
    check("H7 the method is catalogued in the acquisition registry", entry is not None)
    if entry:
        check("H8 it reuses an existing discovery family rather than inventing a vendor one",
              str(entry.get("method_family")) in {"json_api_search", "rss_search", "query_search"},
              str(entry.get("method_family")))
        check("H9 the registry records that discovery is not evidence",
              "evidence" in json.dumps(entry).lower() and "discover" in json.dumps(entry).lower())

    # ---------- I: who wrote the opening post ----------
    # A live 26.2 "Known issue:" post was counted as a user report. Its body opens "We are aware of
    # an issue in Premiere version 26.2 and 26.3" -- Adobe speaking -- and its author carries
    # userTitle "Principal Product Manager" while ordinary reporters carry "Participant". The rank
    # is a fact the platform hands over, so nothing is inferred from wording.
    print("\n[I] vendor-authored posts are not user reports")
    def with_author(user_title, rank_name=None):
        t = topic()
        t["firstPost"]["author"] = {"id": 7, "name": "someone", "userTitle": user_title,
                                    "rank": {"name": rank_name or user_title}}
        return t

    for title in ("Principal Product Manager", "Adobe Employee", "Community Manager", "Moderator",
                  "Staff", "Support Engineer"):
        cands, _e, _c = drive(hits=[hit()], topics=[with_author(title)])
        row = judge(cands[0]) if cands else {}
        check(f"I1 a post authored by '{title}' is not counted",
              row.get("counted") is not True
              and str(row.get("exclusion_reason")) == "vendor_release_announcement",
              f"{row.get('counted')} {row.get('exclusion_reason')}")
    # A community rank is a USER, however senior. The list is of vendor roles for exactly this
    # reason: Adobe's community ranks are open-ended and a new one must not become a refusal.
    for title in ("Participant", "Participating Frequently", "Community Expert", "Explorer",
                  "Enthusiast", "Legend", "Guide"):
        cands, _e, _c = drive(hits=[hit()], topics=[with_author(title)])
        row = judge(cands[0]) if cands else {}
        check(f"I2 a post authored by '{title}' still counts", row.get("counted") is True,
              f"{row.get('counted')} {row.get('exclusion_reason')}")
    check("I3 an author with no rank at all is not treated as vendor",
          premiere.author_is_vendor({}) is False and premiere.author_is_vendor(None) is False)


    # THE RANK IS A VETO SIGNAL ONLY. A known vendor role may EXCLUDE a report; an absent, unknown,
    # changed or ordinary community rank must never stand in for the other gates. Adobe can rename
    # its ranks at any time, and a rank the list does not recognise must leave the row exactly where
    # the authored text, the product, the version role, the URL, the date and the issue gates put it.
    for label, author in (("absent", None), ("empty", {}),
                          ("an unknown future rank", {"userTitle": "Mentor Level 4",
                                                      "rank": {"name": "Mentor Level 4"}}),
                          ("no rank object at all", {"name": "someone"})):
        t = topic()
        t["firstPost"]["author"] = author
        cands, _e, _c = drive(hits=[hit()], topics=[t])
        row = judge(cands[0]) if cands else {}
        check(f"I4 {label} rank does not veto on its own", row.get("counted") is True,
              f"{row.get('counted')} {row.get('exclusion_reason')}")
        # ... and does not excuse anything either: the same author with a bad report still fails.
        t2 = topic(content="<p>How do I change the workspace colour in 26.2.2?</p>")
        t2["firstPost"]["author"] = author
        cands2, _e, _c = drive(hits=[hit()], topics=[t2])
        row2 = judge(cands2[0]) if cands2 else {}
        check(f"I5 {label} rank grants nothing -- the other gates still decide",
              row2.get("counted") is not True, f"{row2.get('counted')} {row2.get('exclusion_reason')}")
    # And a vendor rank cannot rescue a row the other gates already refused, nor is it the only
    # thing standing between a vendor post and the count: order is irrelevant to the outcome.
    t3 = topic(content="<p>We are aware of an issue in Premiere 26.2.2.</p>")
    t3["firstPost"]["author"] = {"userTitle": "Community Manager", "rank": {"name": "Community Manager"}}
    cands3, _e, _c = drive(hits=[hit()], topics=[t3])
    row3 = judge(cands3[0]) if cands3 else {}
    check("I6 a vendor-authored post is refused regardless of which gate reaches it first",
          row3.get("counted") is not True, str(row3.get("exclusion_reason")))
    # ---------- J: who owns the version NUMBER ----------
    # Board provenance establishes the product, not the version. macOS 26.x shares Premiere's version
    # space exactly -- 17 live board-728 threads declare a macOS 26.2 -- and this board abbreviates
    # app names as a matter of course, so the owner test reads every occurrence and both registers.
    print("\n[J] the version number has an owner")
    for label, body, ver, owns in (
            ("macOS owns the only 26.2",
             "MacBook Pro M2 Pro, macOS Tahoe 26.2 Premiere 26.3.0 (Build 93)", "26.2", False),
            ("an OS line beside a Premiere line",
             "Premiere Version: 26.2.2 (Build 3) Operating System: Mac OS 26.2", "26.2", False),
            ("and Premiere still owns its own", 
             "Premiere Version: 26.2.2 (Build 3) Operating System: Mac OS 26.2", "26.2.2", True),
            ("AE short form", "AE 26.2.2 crashes on launch. Premiere Pro 26.3.0 is fine.", "26.2.2", False),
            ("AME short form", "AME 26.2.2 fails to render every export.", "26.2.2", False),
            ("Ps short form", "Ps 26.2.2 crashes on open.", "26.2.2", False),
            ("a driver line", "Studio Driver 26.2 installed; Premiere Pro 26.3 crashes.", "26.2", False),
            ("a bare version in a board title",
             "26.2.2 render crash. The timeline crashes on every export.", "26.2.2", True),
            ("the board's own Pr abbreviation",
             "Pr 26.2.2 timeremapped nest bug: the nest drifts and playback stutters.", "26.2.2", True),
            ("the long form", "Premiere Pro 26.2.2 crashes on the timeline.", "26.2.2", True),
            ("one Premiere occurrence among foreign ones",
             "Media Encoder 26.2.2 also updated. Premiere Pro 26.2.2 crashes on the timeline.", "26.2.2", True)):
        check(f"J1 {label}", premiere.premiere_owns_version(body, ver) is owns,
              f"owns={premiere.premiere_owns_version(body, ver)} want={owns}")
    # End to end: provenance cannot carry a version it does not own.
    row = judge(board_candidate("MacBook Pro M2 Pro, macOS Tahoe 26.2 Premiere 26.3.0 (Build 93). "
                                "The grow effect stops working and the timeline hangs."))
    check("J2 a thread whose only 26.2 is the OS is refused on a verified board",
          row.get("counted") is not True
          and str(row.get("exclusion_reason")) == "version_owned_by_another_product",
          f"{row.get('counted')} {row.get('exclusion_reason')}")
    # The ownership test is scoped to provenance-supplied product context: off the board the phrase
    # gate already requires Premiere in the text, and that path is unchanged.
    check("J3 the occurrence test uses numeric boundaries on both sides",
          premiere.premiere_owns_version("Premiere Pro 26.2.2 crashes", "26.2") is False)
    print()
    print('=' * 78)
    print(f'Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed')
    for e in _ERRORS:
        print('  - ' + e)
    print('=' * 78)
    return 1 if _FAIL else 0


if __name__ == '__main__':
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
