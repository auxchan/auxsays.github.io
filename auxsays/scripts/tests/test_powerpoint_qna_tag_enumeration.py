#!/usr/bin/env python3
"""The Microsoft Q&A PowerPoint tag lane: enumerate the community, do not query a search box.

WHY A SEPARATE LANE. learn_qna_search_rss asks a search index for a fixed set of phrasings, so a
report is only ever as findable as the words its author happened to choose. The Q&A PowerPoint
communities are also published as browsable, paginated, server-rendered inventories -- measured at
12,969 questions in "For home | Windows" alone -- and those can be walked in recency order with no
search engine involved. Same source FAMILY, genuinely different discovery path.

WHAT THIS LOCKS. Discovery is broad (a recent date plus a concrete symptom is enough to spend one
hydration request); acceptance is the unchanged authority. The two must never be confused, and the
lane must never be able to turn a foreign application's version string into PowerPoint evidence.

Offline: every page is a fixture. No network, no repo writes.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.build_claims import build_tokens  # noqa: E402
from lib.source_segments import parse_learn_qna_thread  # noqa: E402
from patch_collectors import microsoft_learn_qna_source as rss  # noqa: E402
from patch_collectors import microsoft_powerpoint as ppt  # noqa: E402
from patch_collectors import microsoft_qna_tags_source as tags  # noqa: E402

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


def card(qid: str, slug: str, title: str, asked: str, answered: str = "") -> str:
    """One tag-listing card, shaped as the live listing renders it."""
    stamps = (f'<span> asked <local-time format="datetime" datetime="{asked}T09:00:00.0+00:00"'
              f' class="is-visually-hidden">{asked}</local-time></span>')
    if answered:
        stamps += (f'<span> answered <local-time format="datetime" datetime="{answered}T10:00:00.0+00:00"'
                   f' class="is-visually-hidden">{answered}</local-time></span>')
    return (f'<div class="card"><a href="/en-us/answers/questions/{qid}/{slug}/">{title}</a>'
            f'{stamps}</div>')


def run() -> int:
    print("=" * 96)
    print("T1  the community inventory is enumerated, not guessed")
    print("=" * 96)
    ids = [t[0] for t in tags.POWERPOINT_TAGS]
    check("T1.1 the four surfaces the brief names are all present",
          {"1464", "363", "1277", "1165"} <= set(ids), str(sorted(ids)))
    check("T1.2 tags are ordered by measured volume, biggest inventory first",
          [t[3] for t in tags.POWERPOINT_TAGS] == sorted((t[3] for t in tags.POWERPOINT_TAGS),
                                                         reverse=True))
    check("T1.3 the largest surface is the ~13k 'for home, Windows' community",
          tags.POWERPOINT_TAGS[0][0] == "1464" and tags.POWERPOINT_TAGS[0][3] > 10000)
    check("T1.4 the Microsoft 365 Insider PowerPoint community is included",
          any(t[0] == "1310" for t in tags.POWERPOINT_TAGS))
    # A Click-to-Run desktop build cannot be the patch identity of a phone report, so those
    # inventories are excluded ON PURPOSE and the exclusion is recorded rather than silent.
    excluded = {t[0] for t in tags.EXCLUDED_TAGS}
    check("T1.5 mobile-only inventories are excluded deliberately, not forgotten",
          excluded and not (excluded & set(ids)), str(sorted(excluded)))
    check("T1.6 every tag carries a human-readable public label",
          all(t[2] and "powerpoint" in t[2].lower() for t in tags.POWERPOINT_TAGS))

    print()
    print("=" * 96)
    print("T2  a listing page is parsed into questions with the RIGHT dates")
    print("=" * 96)
    page = ("<html><body>"
            + card("111", "crash-on-save", "PowerPoint crashes on save", "2026-08-28", "2026-08-29")
            + card("222", "how-to-theme", "How do I change a theme", "2026-08-20")
            + card("333", "wont-open", "PowerPoint will not open", "2026-07-05", "2026-08-27")
            + "</body></html>")
    rows = tags.parse_tag_page(page)
    check("T2.1 every card becomes exactly one row", len(rows) == 3, str(len(rows)))
    by_id = {r["question_id"]: r for r in rows}
    check("T2.2 titles are attached to their own question",
          by_id["111"]["title"] == "PowerPoint crashes on save"
          and by_id["333"]["title"] == "PowerPoint will not open", str(by_id["111"]))
    check("T2.3 `asked` is the creation date, not the latest activity",
          by_id["111"]["asked"] == "2026-08-28" and by_id["333"]["asked"] == "2026-07-05",
          f"{by_id['111']['asked']} / {by_id['333']['asked']}")
    check("T2.4 `date` is the most recent activity, so a revived thread stays visible",
          by_id["111"]["date"] == "2026-08-29" and by_id["333"]["date"] == "2026-08-27")
    check("T2.5 a card with only an asked stamp does not borrow its neighbour's date",
          by_id["222"]["asked"] == "2026-08-20" and by_id["222"]["date"] == "2026-08-20",
          str(by_id["222"]))
    # A wrong date silently moves a report into or out of a release window, so an unparsed card
    # must stay empty rather than inherit.
    nostamp = tags.parse_tag_page('<a href="/en-us/answers/questions/999/x/">Untimed</a>')
    check("T2.6 a card with no stamp at all yields an empty date, never a guess",
          nostamp and nostamp[0]["date"] == "" and nostamp[0]["asked"] == "")
    check("T2.7 the same question listed twice on a page is ONE row",
          len(tags.parse_tag_page(card("111", "a", "t", "2026-08-01")
                                  + card("111", "a", "t", "2026-08-01"))) == 1)

    print()
    print("=" * 96)
    print("T3  de-duplication against the search lane is exact")
    print("=" * 96)
    # Both lanes discover the same threads. If their URL forms differ by so much as a trailing
    # slash, one report becomes two evidence rows.
    mine = tags.question_url("5975138", "version-2607-powerpoint-crashing-when-using-an-add")
    stored = ("https://learn.microsoft.com/en-us/answers/questions/5975138/"
              "version-2607-powerpoint-crashing-when-using-an-add")
    check("T3.1 the tag lane emits the SAME canonical URL the search lane stores",
          mine == stored, f"{mine!r} vs {stored!r}")
    check("T3.2 it uses the shared canonicaliser rather than its own string handling",
          mine == rss.canonical_learn_qna_url(mine + "/"))
    check("T3.3 a slug-less URL still canonicalises consistently",
          tags.question_url("5975138") == rss.canonical_learn_qna_url(tags.question_url("5975138")))

    print()
    print("=" * 96)
    print("T4  discovery is BROAD, and stays discovery")
    print("=" * 96)
    admitted = ["PowerPoint crashes on save", "Slides will not advance",
                "Unable to save a new PowerPoint presentation", "Designer feature not working",
                "Copilot error in PowerPoint", "Fonts missing after update",
                "Export to PDF fails", "Presentation is very slow", "Add-in stopped working",
                "Video will not play", "Animation timing broken", "Images disappear"]
    for title in admitted:
        check(f"T4.1 admitted for hydration: {title!r}",
              bool(ppt.QNA_TAG_SYMPTOM_RE.search(title)))
    check("T4.2 admission is broader than acceptance, by construction",
          bool(ppt.QNA_TAG_SYMPTOM_RE.search("Slides will not advance"))
          and ppt.QNA_TAG_SYMPTOM_RE is not getattr(ppt, "POWERPOINT_ISSUE_RE", None))
    # Broad, not unbounded: a pure how-to still costs a request, so it should not be admitted.
    for title in ("How do I change a theme", "Where is the design tab",
                  "Tips for a good presentation"):
        check(f"T4.3 not admitted: {title!r}", not ppt.QNA_TAG_SYMPTOM_RE.search(title))

    print()
    print("=" * 96)
    print("T5  a hydrated question is the ASKER's report, and only theirs")
    print("=" * 96)
    import json  # noqa: PLC0415

    payload = {
        "@context": "https://schema.org", "@type": "QAPage",
        "mainEntity": {
            "@type": "Question", "@id": "https://learn.microsoft.com/en-us/questions/700/x",
            "id": "700", "name": "PowerPoint crashes on save",
            "text": "<p>PowerPoint crashes every time I save since the update.</p>",
            "answerCount": 1, "author": "asker", "authorId": "aaaaaaaa-0000-0000-0000-000000000001",
            "acceptedAnswer": [],
            "suggestedAnswer": [{"@type": "Answer", "@id": "https://x/a/1", "id": "1",
                                 "text": "<p>I am on Build 20326.20112 and it is fine.</p>",
                                 "author": "helper",
                                 "authorId": "bbbbbbbb-0000-0000-0000-000000000002",
                                 "authorRole": "Independent Advisor",
                                 "updatedAt": "2026-08-27T00:00:00Z", "url": "https://x/a/1"}],
            "moderatorRecommendedAnswers": [],
        },
    }
    html = ('<html><head><script type="application/ld+json">' + json.dumps(payload)
            + "</script></head><body></body></html>")
    cand = tags.question_candidate("700", "x", title="PowerPoint crashes on save",
                                   date="2026-08-27", page_html=html,
                                   source_type=ppt.LEARN_QNA_SOURCE_TYPE,
                                   source_name=ppt.LEARN_QNA_SOURCE_NAME,
                                   parse_thread=parse_learn_qna_thread)
    check("T5.1 the candidate carries the asker's own opening text",
          cand is not None and "crashes every time I save" in cand["report_text"])
    check("T5.2 a DIFFERENT participant's build never enters the report text",
          cand is not None and "20326.20112" not in cand["report_text"], str(cand)[:150])
    check("T5.3 the asker's author id is retained for same-author resolution",
          cand is not None and cand["qna_author_id"].startswith("aaaaaaaa"))
    check("T5.4 the source type matches the Q&A family, so existing gates apply unchanged",
          cand is not None and cand["source_type"] == ppt.LEARN_QNA_SOURCE_TYPE)
    check("T5.5 a page with no parsable thread and no title yields no candidate",
          tags.question_candidate("701", "y", title="", date="", page_html="<html></html>",
                                  source_type="t", source_name="n",
                                  parse_thread=parse_learn_qna_thread) is None)

    print()
    print("=" * 96)
    print("T6  a foreign application's version string is never PowerPoint evidence")
    print("=" * 96)
    # Measured on the live thread 5976427: the only build on the page is the reporter's EXCEL
    # version string. It is the same author, so same-author resolution WOULD reach it -- the
    # protection is that lib.build_claims withholds the 16.0. full form until the application is
    # proven. This lane must not weaken that.
    excel = ("My excel is 'Microsoft(R) Excel(R) for Microsoft 365 MSO "
             "(Version 2607 Build 16.0.20228.20124) 64-bit'")
    check("T6.1 an Excel version string yields NO PowerPoint build token",
          build_tokens(excel) == [], str(build_tokens(excel)))
    check("T6.2 and the bare form still does, so the guard is not blanket suppression",
          build_tokens("I am on Build 20228.20124") == ["20228.20124"],
          str(build_tokens("I am on Build 20228.20124")))

    print()
    print("=" * 96)
    print("T7  health distinguishes 'read the community, found nothing' from 'never read it'")
    print("=" * 96)
    # This is the lane's whole diagnostic value: an honest zero has to be provable.
    # A NEAR MISS is a report that named a version and just missed this patch -- that is the signal
    # worth flagging. A report that never named one is not "close", so it must not read as low
    # confidence; measured live, the tag lane hits exactly this via different_version_not_target.
    check("T7.1 a report that named a version but not this build -> low_confidence",
          ppt.qna_tag_method_status([{}], [], [{"exclusion_reason": "different_version_not_target"}],
                                    [], enumerated=460) == "low_confidence")
    check("T7.1b reading a large corpus where nothing names a version -> no_results, not low_confidence",
          ppt.qna_tag_method_status([{}], [], [{"exclusion_reason": "missing_powerpoint_version"}],
                                    [], enumerated=460) == "no_results",
          "an honest absence over a corpus that WAS read is a healthy zero")
    check("T7.2 enumerated NOTHING and errored -> broken, never a quiet no_results",
          ppt.qna_tag_method_status([], [], [], [{"reason": "network_unreachable"}],
                                    enumerated=0) == "broken")
    check("T7.3 rate limited -> blocked",
          ppt.qna_tag_method_status([], [], [], [{"reason": "rate_limited"}],
                                    enumerated=100) == "blocked")
    check("T7.4 an accepted report -> success",
          ppt.qna_tag_method_status([{}], [{}], [], [], enumerated=460) == "success")
    check("T7.5 accepted but with errors -> partial, not success",
          ppt.qna_tag_method_status([{}], [{}], [], [{"reason": "http_500_error"}],
                                    enumerated=460) == "partial")
    check("T7.6 a walked community with genuinely nothing relevant -> no_results",
          ppt.qna_tag_method_status([], [], [], [], enumerated=460) == "no_results")

    print()
    print("=" * 96)
    print("T8  the lane is wired as an independent PRIMARY, and is bounded")
    print("=" * 96)
    from lib.method_routing import plan_methods  # noqa: PLC0415
    import orchestrate_evidence_run as orch  # noqa: PLC0415

    plan = plan_methods("microsoft-powerpoint")
    check("T8.1 it runs every cycle as a primary, not only when another method fails",
          ppt.QNA_TAG_METHOD_ID in plan["primary"], str(plan["primary"]))
    check("T8.2 it has a distinct method identity from the search lane",
          ppt.QNA_TAG_METHOD_ID != ppt.LEARN_QNA_METHOD_ID)
    bound = orch.default_powerpoint_methods()
    check("T8.3 every planned method is actually bound in the graph",
          all(m in bound for m in plan["primary"] + plan["fallback"]), str(sorted(bound)))
    check("T8.4 hydration is hard-capped so one run cannot become a crawl",
          0 < ppt.QNA_TAG_MAX_HYDRATIONS <= 100 and 0 < ppt.QNA_TAG_MAX_PAGES <= 20,
          f"{ppt.QNA_TAG_MAX_HYDRATIONS} hydrations, {ppt.QNA_TAG_MAX_PAGES} pages/tag")
    check("T8.5 the walk stops early once a page falls out of the window",
          "max(dated) < since" in (ROOT / "scripts" / "patch_collectors"
                                   / "microsoft_qna_tags_source.py").read_text(encoding="utf-8"))

    print()
    print("=" * 96)
    print("T9  Tech Community is a second community, enumerated honestly")
    print("=" * 96)
    from patch_collectors import techcommunity_source as tc  # noqa: PLC0415

    # A prior audit concluded this source was unusable because no PowerPoint BOARD exists. That is
    # still true and still irrelevant: the threads are dispersed across general boards, and the
    # sitemaps expose them. Boards are chosen by measured PowerPoint yield, not by name.
    check("T9.1 boards are chosen by measured yield and ordered by it",
          [b[1] for b in tc.POWERPOINT_BOARDS]
          == sorted((b[1] for b in tc.POWERPOINT_BOARDS), reverse=True)
          and tc.POWERPOINT_BOARDS[0][0] == "sitemap_microsoft-365.xml.gz")
    sitemap = (
        "<urlset>"
        "<url><loc>https://techcommunity.microsoft.com/discussions/microsoft-365/powerpoint-crash</loc>"
        "<lastmod>2026-08-02T00:00:00Z</lastmod></url>"
        "<url><loc>https://techcommunity.microsoft.com/blog/microsoft_365blog/whats-new-in-powerpoint</loc>"
        "<lastmod>2026-08-05T00:00:00Z</lastmod></url>"
        "<url><loc>https://techcommunity.microsoft.com/discussions/microsoft-365/excel-slow</loc>"
        "<lastmod>2026-08-04T00:00:00Z</lastmod></url>"
        "<url><loc>https://techcommunity.microsoft.com/discussions/microsoft-365/powerpoint-old</loc>"
        "<lastmod>2026-01-04T00:00:00Z</lastmod></url>"
        "<url><loc>https://techcommunity.microsoft.com/discussions/microsoft-365/powerpoint-undated</loc>"
        "</url>"
        "</urlset>")
    found = tc.powerpoint_threads(sitemap, since="2026-07-01")
    urls = [r["source_url"] for r in found]
    check("T9.2 a recent PowerPoint discussion is picked up",
          any(u.endswith("powerpoint-crash") for u in urls), str(urls))
    check("T9.3 a vendor BLOG post is excluded at discovery, not argued about later",
          not any("/blog/" in u for u in urls), str(urls))
    check("T9.4 a non-PowerPoint discussion is not picked up",
          not any("excel-slow" in u for u in urls))
    check("T9.5 a thread older than the window is not picked up",
          not any("powerpoint-old" in u for u in urls))
    check("T9.6 a thread with NO lastmod is skipped, not assumed recent",
          not any("powerpoint-undated" in u for u in urls),
          "an undated entry would otherwise be re-hydrated forever")

    ld = ('<script type="application/ld+json">{"@type":"QAPage","mainEntity":'
          '{"@type":"Question","name":"PowerPoint crashes when saving",'
          '"text":"<p>It crashes every save since the update.</p>"},'
          '"suggestedAnswer":[{"text":"I am on Build 20326.20112"}]}</script>')
    cand = tc.thread_candidate("https://techcommunity.microsoft.com/discussions/microsoft-365/x",
                               date="2026-08-02", page_html=ld,
                               source_type=tc.DEFAULT_SOURCE_TYPE, source_name=tc.DEFAULT_SOURCE_NAME)
    check("T9.7 the candidate is built from the opening post",
          cand is not None and "crashes every save" in cand["report_text"])
    check("T9.8 a REPLY's build never enters the opening poster's report text",
          cand is not None and "20326.20112" not in cand["report_text"], str(cand)[:140])
    check("T9.9 it is a distinct source identity from Microsoft Q&A",
          ppt.TECH_COMMUNITY_SOURCE_TYPE != ppt.LEARN_QNA_SOURCE_TYPE
          and ppt.TECH_COMMUNITY_METHOD_ID != ppt.QNA_TAG_METHOD_ID)

    # Both new lanes write evidence, so both identities must be declared at the ownership control
    # point or the write transaction refuses them.
    from lib.collector_ownership import ALLOWED_METHODS, ALLOWED_SOURCE_TYPES  # noqa: PLC0415
    check("T9.10 both new methods are declared in the ownership manifest",
          {ppt.QNA_TAG_METHOD_ID, ppt.TECH_COMMUNITY_METHOD_ID}
          <= ALLOWED_METHODS["microsoft-powerpoint"])
    check("T9.11 the Tech Community source identity is declared",
          ppt.TECH_COMMUNITY_SOURCE_TYPE in ALLOWED_SOURCE_TYPES["microsoft-powerpoint"],
          ppt.TECH_COMMUNITY_SOURCE_TYPE)
    check("T9.12 the tag lane deliberately reuses the Q&A source identity, so one report is one row",
          ppt.LEARN_QNA_SOURCE_TYPE in ALLOWED_SOURCE_TYPES["microsoft-powerpoint"])

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
