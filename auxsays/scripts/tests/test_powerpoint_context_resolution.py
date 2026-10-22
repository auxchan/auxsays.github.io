#!/usr/bin/env python3
"""PowerPoint R2: deterministic, SEGMENT-SCOPED exact-build context resolution.

Every case drives the REAL acceptance authority (``ppt.row_from_candidate``) before and after
resolution. The resolver only reads more of the SAME thread, attributes a build strictly to the
segment whose author stated it, and hands that segment's own words back; it never decides
acceptance, never infers a build, and never transfers identity between participants.

Fixture pages are real schema.org ``QAPage`` markup of the shape measured live on
learn.microsoft.com/answers, so the parser is exercised against the structure it actually meets.

Deterministic and offline: the thread fetch is injected. No network, no repo mutation.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_powerpoint_context_resolution.py
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from lib import context_resolution as cr  # noqa: E402
from lib import source_segments as ss  # noqa: E402
from patch_collectors import microsoft_powerpoint as ppt  # noqa: E402
from patch_collectors.base import PatchRecord, source_url_is_specific  # noqa: E402

PRODUCT = "microsoft-powerpoint"
VERSION = "2607"
BUILD = "20228.20110"
OTHER_BUILD = "20228.20200"
SIBLING_BUILD = "20228.20300"
RELEASE = "2026-07-23T00:00:00Z"
CAPTURED = "2026-08-01T00:00:00Z"
QID = "5975138"
URL = f"https://learn.microsoft.com/en-us/answers/questions/{QID}/powerpoint-crash"

OP_AUTHOR = ("Martin Wollmann", "5eee431a-ba0c-439a-961f-fe3092adbd65")
REPLY_AUTHOR = ("Aetherin", "7bf13722-2ad4-4e15-a104-eca51777522d")
AI_AUTHOR = ("AI answer", "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1")

ISSUE = "PowerPoint crashes on save and the presentation window closes every time."

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
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERRORS.append(label)


def target(build: str = BUILD) -> dict:
    return {"update_version": VERSION, "target_build": build,
            "target_release_date": RELEASE, "version_ambiguous": False}


def record(build: str = BUILD) -> PatchRecord:
    return PatchRecord(product_id=PRODUCT, update_version=VERSION, path=Path("x.md"),
                       update_published_at=RELEASE, update_status="current",
                       update_product="Microsoft PowerPoint", target_build=build)


def candidate(url: str = URL, title: str = "", text: str = "") -> dict:
    return {"source_url": url, "parent_title": title or f"PowerPoint Version {VERSION} crash",
            "report_title": "", "report_text": text or ISSUE,
            "source_date": "2026-08-14", "source_type": "microsoft_learn_qna",
            "source_name": "Microsoft Learn Q&A"}


# --- fixture page builder ----------------------------------------------------

def qapage(question_text: str, answers=(), qid: str = QID,
           question_title: str = "PowerPoint crash") -> str:
    """A page carrying the schema.org QAPage block, shaped as measured on the live source.

    ``answers`` items are (text, (author_name, author_id), updatedAt)."""
    payload = {
        "@context": "https://schema.org", "@type": "QAPage",
        "mainEntity": {
            "@type": "Question", "@id": f"https://learn.microsoft.com/en-us/questions/{qid}/x",
            "id": qid, "name": question_title, "text": f"<p>{question_text}</p>",
            "answerCount": len(answers), "author": OP_AUTHOR[0], "authorId": OP_AUTHOR[1],
            "acceptedAnswer": [],
            "suggestedAnswer": [
                {"@type": "Answer",
                 "@id": f"https://learn.microsoft.com/en-us/answers/a/{9000 + i}",
                 "id": str(9000 + i), "text": f"<p>{text}</p>", "author": who[0],
                 "authorId": who[1], "authorRole": "Independent Advisor", "updatedAt": when,
                 "url": f"https://learn.microsoft.com/en-us/answers/a/{9000 + i}"}
                for i, (text, who, when) in enumerate(answers)
            ],
            "moderatorRecommendedAnswers": [],
        },
    }
    return ('<html><head><script type="application/ld+json">'
            + json.dumps(payload)
            + '</script></head><body><div id="question">rendered</div></body></html>')


def fetcher(page: str, status: str = "ok", counter: list | None = None):
    def _fetch(url: str) -> tuple[str, str]:
        if counter is not None:
            counter.append(url)
        return page, status
    return _fetch


def resolve(page: str, cand: dict | None = None, status: str = "ok",
            budget: cr.ResolutionBudget | None = None, counter: list | None = None):
    cand = cand if cand is not None else candidate()
    budget = budget if budget is not None else cr.ResolutionBudget()
    outcome = cr.resolve_candidate(cand, cr.RESOLVABLE_REASON,
                                   fetch_thread=fetcher(page, status, counter), budget=budget)
    return outcome, budget, cand


def row(cand: dict, rec: PatchRecord | None = None, tgt: dict | None = None) -> dict:
    return ppt.row_from_candidate(rec or record(), tgt or target(), cand, CAPTURED)


def run() -> int:
    print("=" * 72)
    print("R2 SEGMENT-SCOPED CONTEXT RESOLUTION")
    print("=" * 72)

    # --- baseline: the gap this stage exists to close ------------------------
    print("\n[baseline] a version-only report is rejected missing_exact_build")
    base = row(candidate())
    check("version-only candidate is rejected missing_exact_build",
          base.get("counted") is False
          and base.get("exclusion_reason") == cr.RESOLVABLE_REASON, str(base))
    check("rejected row carries no build", not base.get("target_build"))

    # --- A: no build anywhere on the thread ----------------------------------
    print("\n[A] thread contains no build at all")
    page = qapage(f"PowerPoint {VERSION} crashes on save.",
                  [("Try repairing Office.", REPLY_AUTHOR, "2026-08-14T07:47:43Z")])
    out, _, cand = resolve(page)
    check("A result is no_explicit_build", out.resolution_result == cr.NO_EXPLICIT_BUILD, out.detail)
    check("A no build resolved", out.resolved_build == "" and out.explicit_build_found is False)
    after = row(cr.augmented_candidate(cand, out))
    check("A stays uncounted", after.get("counted") is False)
    check("A still missing_exact_build", after.get("exclusion_reason") == cr.RESOLVABLE_REASON)

    # --- B: the OP's OWN segment states the exact build ----------------------
    print("\n[B] the reporter's own segment explicitly names the exact build")
    page = qapage(f"PowerPoint {VERSION} (Build {BUILD}) crashes on save every time.",
                  [("Thanks, I will look into it.", REPLY_AUTHOR, "2026-08-14T07:47:43Z")])
    out, _, cand = resolve(page)
    check("B resolves the exact build", out.resolution_result == cr.RESOLVED_EXACT_BUILD, out.detail)
    check("B resolved build is the source's own", out.resolved_build == BUILD)
    check("B attributed to the question segment", out.segment_type == ss.SEGMENT_QUESTION)
    check("B attributed to the OP author id", out.segment_author_id == OP_AUTHOR[1])
    check("B match basis names the own-segment rule",
          out.resolution_match_basis == "explicit_build_in_own_question_segment",
          out.resolution_match_basis)
    check("B excerpt shows where the build came from", BUILD in out.provenance_excerpt)
    after = row(cr.augmented_candidate(cand, out))
    check("B ACCEPTED by the unchanged authority", after.get("counted") is True, str(after))
    check("B accepted row carries the exact build", after.get("target_build") == BUILD)

    # --- C: the OP's own segment states the WRONG build ----------------------
    print("\n[C] the reporter's own segment names a different build")
    page = qapage(f"PowerPoint {VERSION} (Build {OTHER_BUILD}) crashes on save.")
    out, _, cand = resolve(page)
    check("C resolves (resolution is not acceptance)",
          out.resolution_result == cr.RESOLVED_EXACT_BUILD and out.resolved_build == OTHER_BUILD)
    after = row(cr.augmented_candidate(cand, out))
    check("C REJECTED by the authority", after.get("counted") is False, str(after))
    check("C rejected as build_mismatch",
          after.get("exclusion_reason") == "build_mismatch", str(after.get("exclusion_reason")))
    check("C carries no build", not after.get("target_build"))

    # --- D: two builds inside the reporter's own segment ---------------------
    # R3 note: two builds are no longer automatically a conflict. When the author explicitly says
    # which is which, the source has answered the question -- see test_powerpoint_build_roles.py.
    # A conflict is now two builds whose roles the author did NOT distinguish.
    print("\n[D] two builds the author did NOT distinguish")
    page = qapage(f"Seen on Build {BUILD} and Build {OTHER_BUILD} in our estate.")
    out, _, cand = resolve(page)
    check("D result is conflicting_build", out.resolution_result == cr.CONFLICTING_BUILD, out.detail)
    check("D chooses NO build", out.resolved_build == "" and out.explicit_build_found is False)
    check("D names both builds in the detail",
          BUILD in out.detail and OTHER_BUILD in out.detail, out.detail)
    after = row(cr.augmented_candidate(cand, out))
    check("D stays uncounted", after.get("counted") is False)

    print("\n[D2] the SAME two builds, with the author's roles stated -> resolves")
    page = qapage(f"On {VERSION} (Build {BUILD}) it crashes; rolling back to Build "
                  f"{OTHER_BUILD} works.")
    out, _, cand = resolve(page)
    check("D2 resolves the build the author called current",
          out.resolution_result == cr.RESOLVED_EXACT_BUILD and out.resolved_build == BUILD,
          out.detail)
    check("D2 the rollback build is not selected", out.resolved_build != OTHER_BUILD)
    check("D2 the basis names explicit role attribution",
          out.resolution_match_basis.startswith("explicit_role_"), out.resolution_match_basis)
    check("D2 ACCEPTED by the unchanged authority",
          row(cr.augmented_candidate(cand, out)).get("counted") is True)

    # --- E: fetch blocked / broken / unparseable -----------------------------
    print("\n[E] context fetch blocked, broken, and structurally unparseable")
    out, _, cand = resolve(qapage("no build"), status="blocked")
    check("E blocked -> fetch_blocked", out.resolution_result == cr.FETCH_BLOCKED)
    check("E blocked stays uncounted",
          row(cr.augmented_candidate(cand, out)).get("counted") is False)

    def boom(url: str):
        raise TimeoutError("transport died")
    out2 = cr.resolve_candidate(candidate(), cr.RESOLVABLE_REASON,
                                fetch_thread=boom, budget=cr.ResolutionBudget())
    check("E exception -> fetch_broken (telemetry, not a crash)",
          out2.resolution_result == cr.FETCH_BROKEN, out2.detail)
    out3, _, _ = resolve("<html><body>no structured data</body></html>")
    check("E no QAPage block -> fetch_broken, never a guess",
          out3.resolution_result == cr.FETCH_BROKEN, out3.detail)
    check("E unparseable resolves no build", not out3.resolved_build)

    # --- F: restart / receipts ----------------------------------------------
    print("\n[F] restart does no duplicate network work and does not confuse segments")
    page = qapage(f"PowerPoint {VERSION} (Build {BUILD}) crashes on save.",
                  [(f"I see it on Build {SIBLING_BUILD} too, same crash on save.",
                    REPLY_AUTHOR, "2026-08-14T07:47:43Z")])
    seen: list[str] = []
    budget = cr.ResolutionBudget()
    first, _, cand = resolve(page, budget=budget, counter=seen)
    again = cr.resolve_candidate(cand, cr.RESOLVABLE_REASON,
                                 fetch_thread=fetcher(page, counter=seen), budget=budget)
    check("F thread fetched exactly once across the restart", len(seen) == 1, str(seen))
    check("F receipt returns the identical outcome",
          again is first or again.as_dict() == first.as_dict())
    anchored = candidate(url=f"{URL}#answer-9000")
    cr.resolve_candidate(anchored, cr.RESOLVABLE_REASON,
                         fetch_thread=fetcher(page, counter=seen), budget=budget)
    other = budget.receipts.get(f"{URL}#answer-9000")
    check("F second segment of the same thread does NOT refetch", len(seen) == 1, str(seen))
    check("F second segment gets its OWN receipt, not the first one's",
          other is not None and other.segment_key != first.segment_key,
          f"{getattr(other, 'segment_key', None)} vs {first.segment_key}")
    check("F segment keys are distinct per segment",
          len({s.segment_key for s in ss.parse_learn_qna_thread(URL, page).segments}) == 2)

    # --- G: sibling same-YYMM builds ----------------------------------------
    print("\n[G] a resolved build lands only on the record whose build it actually is")
    page = qapage(f"PowerPoint {VERSION} (Build {BUILD}) crashes on save.")
    out, _, cand = resolve(page)
    enriched = cr.augmented_candidate(cand, out)
    check("G exact-match record accepts",
          row(enriched, record(BUILD), target(BUILD)).get("counted") is True)
    sibling = row(enriched, record(SIBLING_BUILD), target(SIBLING_BUILD))
    check("G sibling same-YYMM record REFUSES", sibling.get("counted") is False)
    check("G sibling refuses as build_mismatch",
          sibling.get("exclusion_reason") == "build_mismatch", str(sibling.get("exclusion_reason")))

    # --- H: zero AI environment ---------------------------------------------
    print("\n[H] the whole path works with no AI credentials of any kind")
    saved = {k: v for k, v in os.environ.items()
             if "OPENAI" in k or "ANTHROPIC" in k or "AI_" in k or k.endswith("_API_KEY")}
    for k in saved:
        os.environ.pop(k, None)
    try:
        page = qapage(f"PowerPoint {VERSION} (Build {BUILD}) crashes on save.")
        out, _, cand = resolve(page)
        check("H resolves with no AI credentials present",
              out.resolution_result == cr.RESOLVED_EXACT_BUILD)
        check("H accepted with no AI credentials present",
              row(cr.augmented_candidate(cand, out)).get("counted") is True)
    finally:
        os.environ.update(saved)
    check("H no AI provider package is imported",
          not any(m.split(".")[0] in {"openai", "anthropic", "langchain", "langgraph",
                                      "transformers", "litellm"} for m in set(sys.modules)))

    # ======================================================================
    # ATTRIBUTION CORRECTION -- the reason this module is segment-scoped
    # ======================================================================

    # --- I: a DIFFERENT participant states the build -------------------------
    print("\n[I] a build stated by ANOTHER participant is never transferred to the OP")
    page = qapage(f"PowerPoint {VERSION} crashes when I save.",
                  [(f"I'm on Build {BUILD} and see the same thing.", REPLY_AUTHOR,
                    "2026-08-14T07:47:43Z")])
    out, budget, cand = resolve(page)
    check("I result is cross_segment_build_ignored",
          out.resolution_result == cr.CROSS_SEGMENT_BUILD_IGNORED, out.detail)
    check("I NO build is resolved for the OP",
          out.resolved_build == "" and out.explicit_build_found is False)
    check("I the other segment's build is reported, not borrowed",
          out.cross_segment_builds == [BUILD], str(out.cross_segment_builds))
    after = row(cr.augmented_candidate(cand, out))
    check("I the OP stays UNCOUNTED", after.get("counted") is False, str(after))
    check("I the OP carries no build", not after.get("target_build"))
    check("I the OP is still missing_exact_build",
          after.get("exclusion_reason") == cr.RESOLVABLE_REASON)

    # --- J: that reply, judged on its own merits -----------------------------
    print("\n[J] a qualifying reply becomes its OWN candidate, not context on someone else's")
    reply_text = (f"I'm on Build {BUILD} and PowerPoint crashes on save every time I use the "
                  f"add-in; the window closes and the file is lost.")
    page = qapage(f"PowerPoint {VERSION} crashes when I save.",
                  [(reply_text, REPLY_AUTHOR, "2026-08-14T07:47:43Z")])
    out, budget, cand = resolve(page)
    reports = cr.independent_reports(cand, budget=budget, exclude_segment_key=out.segment_key)
    check("J one independent report is offered", len(reports) == 1, str(len(reports)))
    if reports:
        rep = reports[0]
        check("J it is attributed to the REPLY author, not the OP",
              rep.author_id == REPLY_AUTHOR[1] and rep.author_id != OP_AUTHOR[1])
        check("J it states exactly one build itself", rep.explicit_build == BUILD)
        check("J its URL is a platform anchor on the thread",
              rep.segment_url.startswith(URL + "#answer-"), rep.segment_url)
        check("J its URL still passes the UNCHANGED specificity gate",
              source_url_is_specific(rep.segment_url) is True)
        check("J its URL does not collide with the OP's under the collector dedup key",
              rep.segment_url.strip().rstrip("/").lower() != URL.strip().rstrip("/").lower())
        own = row(rep.candidate)
        check("J the authority judges it on its own merits", own.get("counted") is True, str(own))
        check("J it carries its own stated build", own.get("target_build") == BUILD)
    check("J offering independent reports costs no extra fetch", budget.fetched == 1)

    # --- K: machine-generated segments are never evidence --------------------
    print("\n[K] a machine-generated reply is never offered as evidence")
    page = qapage(f"PowerPoint {VERSION} crashes when I save.",
                  [(f"Try these checks in order. Build {BUILD} crashes on save for many users.",
                    AI_AUTHOR, "2026-08-13T00:16:21Z")])
    out, budget, cand = resolve(page)
    reports = cr.independent_reports(cand, budget=budget, exclude_segment_key=out.segment_key)
    check("K the AI answer is NOT offered as a candidate", reports == [], str(reports))
    check("K the AI answer's build is not transferred to the OP", out.resolved_build == "")
    check("K the AI segment is flagged machine-generated",
          all(s.machine_generated for s in ss.parse_learn_qna_thread(URL, page).answers()))
    check("K sentinel author id is detected", ss.is_machine_generated("Someone", AI_AUTHOR[1]))
    check("K machine byline is detected", ss.is_machine_generated("AI answer", "x"))
    check("K a human byline is NOT flagged",
          not ss.is_machine_generated(*REPLY_AUTHOR) and not ss.is_machine_generated(*OP_AUTHOR))

    # --- L: an anchored candidate resolves against its answer segment --------
    print("\n[L] an already-anchored candidate is attributed to that answer segment")
    page = qapage(f"PowerPoint {VERSION} crashes when I save.",
                  [(f"I'm on Build {BUILD}, {ISSUE}", REPLY_AUTHOR, "2026-08-14T07:47:43Z")])
    out, _, _ = resolve(page, cand=candidate(url=f"{URL}#answer-9000"))
    check("L attributed to the ANSWER segment",
          out.segment_type == ss.SEGMENT_ANSWER, out.segment_type)
    check("L attributed to the reply author", out.segment_author_id == REPLY_AUTHOR[1])
    check("L resolves that segment's own build", out.resolved_build == BUILD)
    check("L match basis names the answer segment",
          out.resolution_match_basis == "explicit_build_in_own_answer_segment")

    # --- M: a page for a different thread never resolves ---------------------
    print("\n[M] a page that is not this candidate's thread resolves nothing")
    page = qapage(f"Some other question. Build {BUILD} crashes.", qid="9999999")
    out, _, cand = resolve(page)
    check("M result is segment_not_identified",
          out.resolution_result == cr.SEGMENT_NOT_IDENTIFIED, out.detail)
    check("M no build is taken from a foreign thread", out.resolved_build == "")
    check("M stays uncounted", row(cr.augmented_candidate(cand, out)).get("counted") is False)

    # --- N: provenance is described honestly ---------------------------------
    print("\n[N] provenance is named and documented honestly")
    check("N the field is not called verbatim",
          not hasattr(cr.ResolutionOutcome(), "provenance_snippet")
          and hasattr(cr.ResolutionOutcome(), "provenance_excerpt"))
    check("N the excerpt is whitespace-normalized, as documented",
          ss.strip_html("<p>Build  20228.20110\n\n crashes</p>") == "Build 20228.20110 crashes")
    check("N the module documents the excerpt as normalized, not verbatim",
          "normalized" in (cr.__doc__ or "").lower()
          and "verbatim" not in (cr.ResolutionOutcome.__doc__ or "").lower())

    # --- segment model contract ---------------------------------------------
    print("\n[segment model] the measured Learn Q&A structure")
    parsed = ss.parse_learn_qna_thread(URL, qapage(
        "q body", [("a one", REPLY_AUTHOR, "2026-08-14T07:47:43Z"),
                   ("a two", AI_AUTHOR, "2026-08-15T00:00:00Z")]))
    check("model parses question + every answer", len(parsed.segments) == 3, parsed.detail)
    check("model exposes an honest parse status", parsed.parse_status == ss.PARSE_OK)
    q = parsed.question()
    check("question segment carries author identity", q is not None and q.author_id == OP_AUTHOR[1])
    check("question segment url is the thread url", q is not None and q.segment_url == URL)
    check("question segment has no invented timestamp", q is not None and q.segment_date == "")
    a = parsed.answers()[0]
    check("answer segment carries its own timestamp", a.segment_date == "2026-08-14T07:47:43Z")
    check("answer segment carries its own author", a.author_id == REPLY_AUTHOR[1])
    check("answer segment url is anchored", a.segment_url == f"{URL}#answer-9000")
    check("by_key round-trips", parsed.by_key(a.segment_key) is a)
    bad = ss.parse_learn_qna_thread(URL, "<html><body>nothing</body></html>")
    check("no structured data is reported, not guessed",
          bad.parse_status == ss.PARSE_NO_STRUCTURED_DATA and not bad.ok)
    shape = ss.parse_learn_qna_thread(URL, '<script type="application/ld+json">'
                                           '{"@type":"QAPage","mainEntity":{"@type":"Article"}}'
                                           '</script>')
    check("an unexpected shape is refused", shape.parse_status == ss.PARSE_UNEXPECTED_SHAPE)

    # --- doctrine guards -----------------------------------------------------
    print("\n[doctrine] what this stage must never do")
    page = qapage(f"PowerPoint {VERSION} (Build {BUILD}) crashes on save.")
    for reason in ("product_mismatch", "version_mismatch", "source_url_not_specific",
                   "no_concrete_issue", "source_date_before_release", "build_mismatch"):
        o = cr.resolve_candidate(candidate(), reason,
                                 fetch_thread=fetcher(page), budget=cr.ResolutionBudget())
        check(f"doctrine: {reason} is not resolvable",
              o.resolution_result == cr.NOT_APPLICABLE and o.resolution_attempted is False)

    tight = cr.ResolutionBudget(max_fetches=1)
    cr.resolve_candidate(candidate(url=URL + "-a"), cr.RESOLVABLE_REASON,
                         fetch_thread=fetcher(page), budget=tight)
    spilled = cr.resolve_candidate(candidate(url=URL + "-b"), cr.RESOLVABLE_REASON,
                                   fetch_thread=fetcher(page), budget=tight)
    check("doctrine: the fetch budget bounds the work",
          spilled.resolution_result == cr.NOT_APPLICABLE and tight.fetched == 1, spilled.detail)

    for result in (cr.NO_EXPLICIT_BUILD, cr.CONFLICTING_BUILD, cr.FETCH_BLOCKED, cr.FETCH_BROKEN,
                   cr.NOT_APPLICABLE, cr.CROSS_SEGMENT_BUILD_IGNORED, cr.SEGMENT_NOT_IDENTIFIED):
        enriched = cr.augmented_candidate(candidate(),
                                          cr.ResolutionOutcome(resolution_result=result,
                                                               resolved_build=BUILD))
        check(f"doctrine: {result} never carries a build into acceptance",
              enriched.get("context_resolved_build") is None
              and BUILD not in str(enriched.get("report_text")))

    check("doctrine: the required result vocabulary is intact",
          cr.RESOLUTION_RESULTS.issuperset({cr.RESOLVED_EXACT_BUILD, cr.NO_EXPLICIT_BUILD,
                                            cr.CONFLICTING_BUILD, cr.FETCH_BLOCKED,
                                            cr.FETCH_BROKEN, cr.NOT_APPLICABLE}))
    check("doctrine: the required provenance fields are all present",
          all(hasattr(cr.ResolutionOutcome(), f) for f in
              ("original_candidate_url", "original_rejection_reason", "resolution_attempted",
               "resolution_method", "resolution_source_url", "resolution_source_scope",
               "explicit_build_found", "resolved_build", "resolution_match_basis",
               "resolution_result")))
    check("doctrine: segment attribution is part of the audit record",
          all(hasattr(cr.ResolutionOutcome(), f) for f in
              ("segment_key", "segment_type", "segment_id", "segment_author_id",
               "segments_discovered", "cross_segment_builds")))

    print()
    print("=" * 72)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 72)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
