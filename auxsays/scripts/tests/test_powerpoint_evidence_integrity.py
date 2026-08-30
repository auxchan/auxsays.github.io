#!/usr/bin/env python3
"""Controls for five defects that shipped green.

Every one of these was reproducible on the merged tree while all 71 suites passed, so each control
here is written to FAIL on the pre-fix code. They fall into two classes:

  * ATTRIBUTION (S1, S2, S3) -- foreign text, fabricated roles, or a web/crash build becoming a
    reporter's exact patch evidence. These produce WRONG counted evidence, the worst failure AUXSAYS
    has, because a wrong count is indistinguishable from a right one downstream.
  * REACHABILITY (S4, S5) -- correct code that production never executes. Silent, and it looks like
    "the source has nothing" rather than "we never asked".

Offline: no network, no repo writes.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import context_resolution as cr  # noqa: E402
from lib import source_segments as ss  # noqa: E402
from lib.build_claims import OFFICE_FULL_VERSION_RE, extract_build_claims  # noqa: E402
from patch_collectors import github_officedev_source as gh  # noqa: E402
from patch_collectors import microsoft_powerpoint as ppt  # noqa: E402
from patch_collectors import stack_exchange_source as se  # noqa: E402

PASS = FAIL = 0
FAILURES: list[str] = []

THREAD = "https://learn.microsoft.com/answers/questions/5956657/copilot-unable-to-read-document-error"
AUTHOR = "4bf12226-06e6-4d29-81dd-92bb3ba0d634"
STRANGER = "11111111-2222-3333-4444-555555555555"


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


def comment(cid: str, author: str, text: str) -> str:
    return (f'<li id="comment-{cid}" data-test-id="comment-{cid}">'
            f'<a userid={author}>member</a><div class="body">{text}</div></li>')


def qa_page(question_text: str, qid: str = "5956657") -> str:
    """A Learn Q&A page carrying the schema.org block, shaped as measured on the live source."""
    payload = {
        "@context": "https://schema.org", "@type": "QAPage",
        "mainEntity": {
            "@type": "Question", "@id": f"https://learn.microsoft.com/en-us/questions/{qid}/x",
            "id": qid, "name": "PowerPoint crash", "text": f"<p>{question_text}</p>",
            "answerCount": 0, "author": "reporter", "authorId": AUTHOR,
            "acceptedAnswer": [], "suggestedAnswer": [], "moderatorRecommendedAnswers": [],
        },
    }
    return ('<html><head><script type="application/ld+json">' + json.dumps(payload)
            + '</script></head><body><div id="question">rendered</div></body></html>')


def run() -> int:
    print("=" * 96)
    print("S1  a comment is bounded by its own element, never by the end of the page")
    print("=" * 96)
    # The marker LOCATES a comment; it does not DELIMIT one. Ending each block at the next marker or
    # \\Z made the last comment absorb the remaining page -- measured live at 45,496 characters of
    # footer, nav and a "related questions" rail, all attributed to one author.
    page = ("<ul>"
            + comment("1001", AUTHOR, "Still happening for me.")
            + comment("1002", STRANGER, "Try repairing Office.")
            + "</ul>"
            + '<div class="footer">Most people hitting this are on Build 20228.20124. '
              "(c) Microsoft 2026</div>")
    segs = ss.parse_comment_segments(page, thread_url=THREAD, base_url=THREAD)
    check("S1.1 both comments are parsed", len(segs) == 2, str(len(segs)))
    check("S1.2 trailing page chrome is NOT absorbed into the last comment",
          all("20228.20124" not in s.segment_text for s in segs),
          repr(segs[-1].segment_text) if segs else "")
    check("S1.3 no markup residue leaks into a comment's text",
          all("<li" not in s.segment_text and "</" not in s.segment_text for s in segs),
          repr(segs[0].segment_text) if segs else "")
    check("S1.4 each comment keeps its OWN author",
          [s.author_id for s in segs] == [AUTHOR, STRANGER], str([s.author_id for s in segs]))

    # An answer rendered BETWEEN two comments must not be absorbed into the preceding one, which is
    # how a stranger's build reached a reporter's segment end-to-end.
    interleaved = ("<ul>" + comment("2001", AUTHOR, "Still happening for me.") + "</ul>"
                   '<div class="answer"><a userid=' + STRANGER + ">mod</a>"
                   "Most people hitting this are on Build 20228.20124.</div>"
                   "<ul>" + comment("2002", AUTHOR, "Thanks, I will try that.") + "</ul>")
    inter = ss.parse_comment_segments(interleaved, thread_url=THREAD, base_url=THREAD)
    check("S1.5 an answer between two comments is not absorbed by either",
          all("20228.20124" not in s.segment_text for s in inter),
          " | ".join(repr(s.segment_text) for s in inter))

    # Fail-closed, not fail-open: an unterminated element must still stop at the next comment.
    unterminated = ('<li data-test-id="comment-3001"><a userid=' + AUTHOR + ">m</a>first"
                    '<li data-test-id="comment-3002"><a userid=' + STRANGER + ">m</a>second"
                    "<div>Build 20228.20124 trailing chrome</div>")
    unterm = ss.parse_comment_segments(unterminated, thread_url=THREAD, base_url=THREAD)
    check("S1.6 an unterminated comment still stops at the next comment marker",
          len(unterm) == 2 and "second" not in unterm[0].segment_text,
          repr(unterm[0].segment_text) if unterm else "")
    check("S1.7 a comment with no identifiable author is still dropped",
          len(ss.parse_comment_segments('<li data-test-id="comment-9">no author here</li>',
                                        thread_url=THREAD, base_url=THREAD)) == 0)

    print()
    print("=" * 96)
    print("S2  segments are joined on a clause boundary, so roles never cross the junction")
    print("=" * 96)
    # _CLAUSE_SPLIT_RE breaks on newline but not on " ". Real comment text routinely ends without
    # terminal punctuation, so a space join merged two authors' sentences into ONE clause and cue
    # words from segment A classified a build named only in segment B.
    question = "PowerPoint crashes on save Started after the July update"      # no final period
    # A comment that states NO role of its own: the junction is the only thing that could supply one.
    neutral = "20228.20190 works correctly for me"
    alone = extract_build_claims(neutral)
    joined = extract_build_claims(question + "\n" + neutral)
    check("S2.1 the comment alone states no failing role",
          alone and alone[0].role != "current_failing", str(alone))
    check("S2.2 the clause join does NOT invent current_failing",
          joined and joined[0].role != "current_failing" and joined[0].build == "20228.20190",
          str(joined))
    check("S2.3 the space join is what fabricated it (the defect is real, not hypothetical)",
          extract_build_claims(question + " " + neutral)[0].role == "current_failing",
          str(extract_build_claims(question + " " + neutral)))

    # A build named as the one the reporter RETURNED to is never the failing build, in either word
    # order. The forward-only cue matched "rolled back to X" but not "X is the build I rolled back
    # to", so a build the author called fine was counted against itself.
    for phrasing in ("20228.20190 is the build I rolled back to and it is fine there",
                     "20228.20190 is what I reverted to",
                     "I rolled back to 20228.20190 and it works"):
        claims = extract_build_claims(phrasing)
        check(f"S2.8 rollback build not counted as failing: {phrasing[:44]!r}",
              claims and claims[0].role == "rollback_previous", str(claims))
    later = extract_build_claims("20228.20124 crashes constantly; I had to roll back")
    check("S2.9 a rollback phrase in a later clause does not demote the failing build",
          later and later[0].role == "current_failing", str(later))
    # Non-vacuity: a genuine same-author claim must still resolve across the same junction.
    genuine = "I am on Build 20228.20124 and the crash started right after installing it"
    ok = extract_build_claims(question + "\n" + genuine)
    check("S2.4 a genuine same-author failing claim still resolves",
          ok and ok[0].role == "current_failing" and ok[0].build == "20228.20124", str(ok))
    src = (ROOT / "scripts" / "lib" / "context_resolution.py").read_text(encoding="utf-8")
    check("S2.5 no space join survives in the resolver's own text assembly",
          'segment.segment_text + " " + same_author_text' not in src
          and '" ".join(seg.segment_text' not in src)

    # Behavioural, through the real resolver: the reporter's question ends without punctuation (as
    # rendered comment text routinely does) and their own later comment names the build they ROLLED
    # BACK TO. Resolution must not hand that build back as the failing one.
    page = (qa_page("PowerPoint crashes on save Started after the July update")
            + "<ul>" + comment("4001", AUTHOR,
                               "20228.20190 is the build I rolled back to and it is fine there")
            + "</ul>")
    out = cr.resolve_candidate(
        {"source_url": THREAD, "source_date": "2026-08-06T00:00:00Z",
         "source_type": "learn_qna_question", "source_name": "Microsoft Learn Q&A",
         "parent_title": "PowerPoint crash", "report_title": "PowerPoint crash",
         "report_text": "PowerPoint crashes on save Started after the July update"},
        "missing_powerpoint_version",
        fetch_thread=lambda _u: (page, "ok"), budget=cr.ResolutionBudget(max_fetches=4))
    check("S2.6 a rollback build is NOT resolved as the failing build",
          out.resolved_build != "20228.20190",
          f"{out.resolution_result} -> {out.resolved_build}")
    roles = {c.get("role") for c in (out.build_claims or [])}
    check("S2.7 and it is not classified current_failing",
          "current_failing" not in roles, str(out.build_claims))

    print()
    print("=" * 96)
    print("S3  a web build and a crash-record build are never desktop patch identity")
    print("=" * 96)
    for line in ("web: 16.0.20329.45605", "web 16.0.20329.45605",
                 "Office on the web 16.0.20329.45605", "web version 16.0.20329.45605",
                 "Web - 16.0.20329.45605"):
        desktop = gh.desktop_version_text("* Office version number: " + line)
        reduced = OFFICE_FULL_VERSION_RE.sub(lambda m: m.group(1), desktop)
        check(f"S3.1 web-only phrasing yields no desktop build: {line!r}",
              "20329.45605" not in reduced, f"desktop={desktop!r}")
    both = "* Office version number: desktop: Version 2607 Build 16.0.20228.20124, web: 16.0.20329.45605"
    dtext = gh.desktop_version_text(both)
    check("S3.2 a comma-separated web half is truncated off the desktop segment",
          "20329.45605" not in dtext and "16.0.20228.20124" in dtext, repr(dtext))
    # Non-vacuity: the real calibration line must still produce the desktop build.
    real = ("* Host [Excel, Word, PowerPoint, etc.]: PowerPoint\n"
            "* Office version number: web: 16.0.20329.45605; desktop: Version 2607 Build 16.0.20228.20124")
    real_reduced = OFFICE_FULL_VERSION_RE.sub(lambda m: m.group(1), gh.desktop_version_text(real))
    check("S3.3 the real web+desktop line still yields the desktop build",
          "20228.20124" in real_reduced and "20329.45605" not in real_reduced, repr(real_reduced))

    # lib.build_claims withholds 16.0.<build> until the application is proven, precisely because the
    # form appears in crash records. Pre-reducing it to a bare token defeated that guard.
    crash = "AppName: EXCEL.EXE AppVersion: 16.0.20228.20124"
    check("S3.4 a foreign-app crash record yields no claim while unreduced",
          extract_build_claims(crash) == [], str(extract_build_claims(crash)))
    check("S3.5 pre-reducing it WOULD have produced one (the defect is real)",
          bool(extract_build_claims(OFFICE_FULL_VERSION_RE.sub(lambda m: m.group(1), crash))))
    # Exercise the REAL collector path, not just the pattern: a control that only asserts the regex
    # exists passes even when nothing calls it.
    crash_candidate = {"github_declared_host": "powerpoint", "report_text": "PowerPoint crashes on save",
                       "github_desktop_version": crash}
    good_candidate = {"github_declared_host": "powerpoint", "report_text": "PowerPoint crashes on save",
                      "github_desktop_version": "Version 2607 Build 16.0.20228.20124"}
    crash_out = ppt.canonicalise_github_candidate(crash_candidate)["report_text"]
    good_out = ppt.canonicalise_github_candidate(good_candidate)["report_text"]
    check("S3.6 the collector leaves a crash record unreduced, so no build is injected",
          "20228.20124" not in crash_out, repr(crash_out))
    check("S3.6b a genuine desktop version IS still reduced and injected",
          "Office desktop version: Version 2607 Build 20228.20124" in good_out, repr(good_out))
    check("S3.6c a non-PowerPoint host is never canonicalised",
          ppt.canonicalise_github_candidate({**good_candidate, "github_declared_host": "excel"})
          ["report_text"] == "PowerPoint crashes on save")
    for marker in ("ModName: EXCEL.EXE", "Faulting application name: WINWORD.EXE"):
        check(f"S3.7 crash vocabulary recognised: {marker[:22]!r}",
              bool(ppt.CRASH_RECORD_MARKER_RE.search(marker)))

    print()
    print("=" * 96)
    print("S4  product-level discovery runs ONCE per run, not once per record")
    print("=" * 96)
    # The merged run drained GitHub's search allowance to `blocked` on two records because the three
    # product-level symptom queries were re-issued for each of 25 records.
    ppt.reset_symptom_cache()
    calls: list[list[str]] = []

    def produce() -> list[dict]:
        calls.append(["ran"])
        return [{"source_url": "https://example.invalid/1"}]

    for _record in range(25):
        ppt.cached_product_candidates("probe", ["q1", "q2"], produce)
    check("S4.1 25 records issue the product-level route exactly once", len(calls) == 1,
          str(len(calls)))
    ppt.reset_symptom_cache()
    ppt.cached_product_candidates("probe", ["q1", "q2"], produce)
    check("S4.2 a new run re-issues it (the cache is per-run, not permanent)", len(calls) == 2,
          str(len(calls)))
    check("S4.3 a different key is a different route",
          (ppt.cached_product_candidates("probe", ["other"], produce), len(calls))[1] == 3)
    check("S4.4 callers cannot mutate the cached list",
          ppt.cached_product_candidates("probe", ["q1", "q2"], produce) is not
          ppt.cached_product_candidates("probe", ["q1", "q2"], produce))

    orch_src = (ROOT / "scripts" / "orchestrate_evidence_run.py").read_text(encoding="utf-8")
    check("S4.5 the graph -- the only production path -- resets the cache each run",
          "reset_symptom_cache()" in orch_src)
    # Pace is asserted as a RATE against the documented limit, not as a magic number: 30 requests
    # per minute for authenticated search, and the run must stay strictly under it.
    per_minute = 60.0 / gh._MIN_INTERVAL if gh._MIN_INTERVAL else float("inf")
    check("S4.6 GitHub search is paced under its documented 30/min limit",
          per_minute < 30.0, f"{per_minute:.1f}/min at interval {gh._MIN_INTERVAL}")

    # The Stack Exchange budget must bound HTTP attempts, not successes: a 429 storm retried each
    # route three times while the counter stayed at zero.
    attempts: list[str] = []

    def boom(url: str) -> dict:
        attempts.append(url)
        raise se.StackExchangeError("rate_limited", status=429)

    saved_request, saved_sleep = se.request_json, se.time.sleep
    se.request_json = boom
    se.time.sleep = lambda _s: None
    try:
        errors: list[dict] = []
        se.collect_stack_exchange_candidates(
            sites=["superuser", "stackoverflow"], queries=["a", "b"],
            tags_by_site={"superuser": "microsoft-powerpoint", "stackoverflow": "powerpoint"},
            errors=errors, max_requests=4)
    finally:
        se.request_json, se.time.sleep = saved_request, saved_sleep
    check("S4.7 a 429 storm cannot exceed the declared request budget",
          len(attempts) <= 4, f"{len(attempts)} attempts against budget 4")

    # Each site has its own tag; sending one site's tag to the other costs a request and returns
    # nothing. The previous `[:1]` slice made the second site's tag dead configuration.
    urls: list[str] = []

    def capture(url: str) -> dict:
        urls.append(url)
        return {"items": [], "quota_remaining": 200}

    se.request_json = capture
    try:
        se.collect_stack_exchange_candidates(
            sites=["superuser", "stackoverflow"], queries=[],
            tags_by_site={"superuser": "microsoft-powerpoint", "stackoverflow": "powerpoint"},
            errors=[], max_requests=4)
    finally:
        se.request_json = saved_request
    su = [u for u in urls if "site=superuser" in u]
    so = [u for u in urls if "site=stackoverflow" in u]
    check("S4.8 Super User is queried with ITS tag",
          len(su) == 1 and "microsoft-powerpoint" in su[0], str(su))
    check("S4.9 Stack Overflow is queried with ITS OWN tag, not Super User's",
          len(so) == 1 and "tagged=powerpoint" in so[0], str(so))

    print()
    print("=" * 96)
    print("S5  the widened resolvable set is what production actually applies")
    print("=" * 96)
    # RESOLVABLE_REASONS existed and was correct, but the only production caller still filtered and
    # passed the SINGULAR constant -- so the report the whole method was built around was discovered,
    # rejected `missing_powerpoint_version`, and never resolved. Correct code, never executed.
    check("S5.1 the set is wider than the single constant",
          cr.RESOLVABLE_REASON in cr.RESOLVABLE_REASONS and len(cr.RESOLVABLE_REASONS) > 1,
          str(sorted(cr.RESOLVABLE_REASONS)))
    check("S5.2 the orchestrator selects rows by the SET",
          "in cr.RESOLVABLE_REASONS]" in orch_src)
    check("S5.3 no orchestrator row-selection compares against the single constant",
          '== cr.RESOLVABLE_REASON]' not in orch_src)
    check("S5.4 the row's OWN reason is passed to the resolver, not a hard-coded one",
          'str(row.get("exclusion_reason")' in orch_src)
    check("S5.5 a version-gate rejection is reconsidered",
          "missing_powerpoint_version" in cr.RESOLVABLE_REASONS)
    # Widening what may be RECONSIDERED must never widen what is ACCEPTED.
    check("S5.6 a non-resolvable rejection is still never reconsidered",
          "product_not_powerpoint" not in cr.RESOLVABLE_REASONS
          and "different_version_not_target" not in cr.RESOLVABLE_REASONS,
          str(sorted(cr.RESOLVABLE_REASONS)))
    check("S5.7 the resolver still gates on the reason it is handed",
          "if rejection_reason not in RESOLVABLE_REASONS" in
          (ROOT / "scripts" / "lib" / "context_resolution.py").read_text(encoding="utf-8"))

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
