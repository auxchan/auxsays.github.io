#!/usr/bin/env python3
"""Community evidence for Microsoft Teams: New Teams desktop, Windows, Public cloud, stable.

THE QUESTION THIS ANSWERS. "Are users reporting concrete problems after installing THIS exact Teams
patch?" Not "is anyone unhappy with Teams" -- a report counts only when the COMPLETE tracked build
appears in text its own author wrote, describing a concrete failure, on or after the release date.

WHY TEAMS NEEDS ITS OWN IDENTITY GATE. Teams ships the same calendar release as different builds per
platform, cloud and edition. The official lane tracks exactly one identity (New Teams / Windows /
Public cloud), and community evidence holds the same line: a Mac, Web, VDI, mobile, Government
(GCC/GCCH/DoD), Sovereign/Gallatin, Classic Teams or Insider-ring report is about a different
product state, however real the problem is.

WHY SEGMENTS, NOT PAGES. Measured on the live calibration threads: of the first eight Q&A threads
carrying a tracked build, the build belonged to the ORIGINAL POSTER once. In the others it was a
support agent's ("Reports point to it starting after Teams build X"), a responder's working
comparison ("I have tested this in version X and I am still able to..."), or a tenant-wide reference
("the most current version right now in our tenant is X"). Reading a build from "somewhere on the
page" would have attributed every one of them to the person asking for help. Attribution is scoped
to the authored SEGMENT via lib.source_segments, and a build in someone else's segment is someone
else's fact.

DISCOVERY IS NOT ACCEPTANCE. Two independent source families discover candidates -- Microsoft Learn
Q&A (search RSS) and Microsoft Tech Community (board sitemap walk) -- and both hand candidates to the
SAME acceptance authority here. Widening where AUXSAYS looks never widens what AUXSAYS accepts: every
row still passes the shared gates in patch_collectors.base (exact version, specific URL, release-date
order, concrete issue) on top of the Teams identity and role gates.

Registration is DEFAULT-OFF behind AUXSAYS_ENABLE_TEAMS_CONSENSUS (explicit "true" only).
"""
from __future__ import annotations

import re
from typing import Any

from lib import source_segments
from lib.post_dates import original_post_date_from_html
from lib.target_outcome import target_is_contradicted
from patch_collectors import base
from patch_collectors import runtime_budget as rb
from patch_collectors import microsoft_learn_qna_source as qna_source
from patch_collectors import techcommunity_source

# Module-level, so the governed write-authority suite can repoint it at a temp tree and drive this
# collector's REAL writeback -- the seam that catches a collector overwriting editorial prose. Same
# value as apply_consensus_to_records.ROOT; resolving it through the import inside the function made
# that suite unable to reach this collector at all.
ROOT = base.ROOT

TEAMS_PRODUCT_ID = "microsoft-teams"

QNA_METHOD_ID = "learn_qna_search_rss"
QNA_SOURCE_TYPE = "microsoft_learn_qna"
QNA_SOURCE_NAME = "Microsoft Learn Q&A"

TC_METHOD_ID = "tech_community_discussions"
TC_SOURCE_TYPE = "microsoft_tech_community"
TC_SOURCE_NAME = "Microsoft Tech Community"

# The Teams board on Tech Community. ONE board, ONE source family -- several queries against one
# corpus would not be a second family, and this module does not pretend otherwise.
TC_BOARD_SITEMAPS = ("sitemap_microsoftteams.xml.gz",)
TC_URL_RE = re.compile(r"techcommunity\.microsoft\.com/(discussions|t5)/", re.I)

# Symptom phrasings, deliberately NOT version-parameterised: a thread that never states a version in
# its indexed text is invisible to an identity query and ordinary to these. They widen discovery
# only; the exact-build gate still decides what counts.
SYMPTOM_QUERIES = (
    "Microsoft Teams crash after update",
    "New Teams not launching after update",
    "Teams meeting audio fails after update",
    "Teams screen sharing broken after update",
    "Teams sign in fails after update",
)

# --- identity: everything the official lane refuses, refused again here --------------------------
# Each token names a state the tracked identity is NOT. A report can be entirely genuine and still
# be about a different product state.
FOREIGN_CONTEXT: tuple[tuple[str, str], ...] = (
    ("teams_edition_classic", r"\bclassic teams\b|\bteams classic\b"),
    ("platform_mac", r"\bmac ?os\b|\bon (a |my )?mac\b|\bmacbook\b"),
    ("platform_web", r"\bteams (on the )?web\b|\bweb (client|app|version) of teams\b|\bbrowser version of teams\b"),
    # VDI runs the SAME Windows New Teams binary, so a VDI report carries the identical build and
    # the exact-build gate cannot help: this alternation is the only defence. Tokens are anchored
    # on purpose -- a bare "horizon" or "rds" vetoes ordinary English ("a fix is on the horizon",
    # "our RDS licensing"), and a veto that eats real reports costs more than the leak it closes.
    ("platform_vdi", r"\bvdi\b|\bcitrix\b|\bvmware horizon\b|\bhorizon (agent|client|pool|view|desktop)\b"
                     r"|\bazure virtual desktop\b|\bavd\b|\bwindows virtual desktop\b|\bwvd\b"
                     r"|\bwindows 365\b|\bw365\b|\bcloud pc\b|\brdsh\b"
                     r"|\brds (farm|host|server|session)\b|remote desktop (session host|services)"
                     r"|\bterminal server\b|\bpublished app\b|\bnon-?persistent\b"),
    ("platform_mobile", r"\b(ios|android|iphone|ipad) (teams|app)\b|\bteams (mobile|for ios|for android)\b"),
    ("cloud_government", r"\bgcc ?high\b|\bgcch\b|\bgcc\b|\bdod\b|\bgovernment cloud\b"),
    ("cloud_sovereign", r"\bgallatin\b|\bsovereign cloud\b|\b21vianet\b"),
    ("ring_preview", r"\bpublic preview\b|\bteams insider\b|\binsider (ring|build|program)\b|\btargeted release\b|\bbeta channel\b|\bdev ring\b|\brelease candidate\b|\btechnical preview\b"),
)

# A build stated as a REFERENCE rather than as the author's own failing state. These are not failure
# claims, and counting them would turn "here is my version for context" into a bug report.
REFERENCE_CUES: tuple[tuple[str, str], ...] = (
    ("version_is_current_reference", r"(most )?current version[^.]{0,40}\bis\b|latest (teams )?version[^.]{0,30}\bis\b|version (right now|currently) in our tenant"),
    ("version_is_working_reference", r"\bi (have )?tested (this )?(in|on|with)\b|\bworks? fine (on|in|with)\b|\bno (such )?(issue|problem)s? (on|in|with)\b|\bam still able to\b"),
    ("version_is_comparison", r"\bcompar(e|ing) your\b|\bmine is\b|\bwhat version are you\b|\bconfirm your version\b"),
    ("version_is_upgrade_target", r"\bplease (update|upgrade) to\b|\bupgrade to\b|\bupdate to version\b"),
    # "This crash is fixed in <build>" scores as `affected` in the shared target_outcome
    # primitive, because a failure noun before the fix language reads as target-then-failure.
    # Rather than change an authority other products depend on, Teams adds the cue on its own
    # side. The negative lookbehinds keep "still not fixed in <build>" -- which IS a failure
    # claim about the build -- countable.
    ("version_is_fix_target",
     "(?<!not )(?<!n't )(fixed|resolved|addressed|patched|corrected) in"),

)

# Directional cues: a build someone moved TO is their fix, a build they moved FROM is the failure.
# Checked only against the text PRECEDING the build, so "rolled back to X" vetoes while
# "rolled back from X" does not.
PRECEDING_CUES: tuple[tuple[str, str], ...] = (
    ("version_is_rollback_target",
     "(rolled? back|rolling back|revert(ed|ing)?|downgrad(ed|ing)?|went back) to[^.]{0,30}$"),
)

ISSUE_EXTRA_TERMS = (
    "cannot join", "can't join", "won't launch", "will not launch", "no audio", "no video",
    "black screen", "not receiving", "won't load", "will not load", "disconnect",
    "sign-in loop", "login loop", "stuck on", "unable to", "cut out", "chipmunk",
)


BUDGET_STOP_REASON = "run_budget_stop"


def budget_expired() -> bool:
    """Has this collector spent the wall-clock the runner reserved for it?

    The Teams lane makes one page fetch per discovered thread across two families, and neither
    techcommunity_source.fetch nor microsoft_qna_tags_source.fetch is budget-aware -- only the Learn
    Q&A search feed is. Without this check a busy week's thread volume is charged to the shared run
    budget and the collectors that run AFTER Teams never start. Checked at the loop boundaries, the
    same places microsoft_windows checks it.
    """
    budget = rb.get_run_budget()
    return budget is not None and budget.collector_finalize_expired()


def teams_build_present(text: str, build: str) -> tuple[bool, str]:
    """Is the COMPLETE tracked build present, with numeric boundaries?

    Delegates to the shared exact_version_match so Teams cannot drift into a looser reading than
    every other product. A bare 26246 prefix does not match 26246.1604.5133.838: a partial YYDDD
    token identifies a day, not a patch.
    """
    matched, basis, _alias = base.exact_version_match(text or "", build)
    return bool(matched), basis or ""


# Sentence and CONTRAST boundaries, deliberately NOT the comma. lib.build_claims splits on commas
# too, which is right for reading a build's role but wrong for identity: "On my Mac, Teams <build>
# crashes" is one statement about one machine, and splitting it put the platform in a different
# clause from the build, so a genuine Mac report stopped being refused. What must separate is a
# CONTRAST -- "works on my Mac but not Windows" -- and those conjunctions are kept.
_IDENTITY_CLAUSE_RE = re.compile(
    r"[.;!?\n]+|\b(?:whilst|while|whereas|however|but|although|though|unlike)\b", re.I)

_BUILD_MASK = "\x00teamsbuild\x00"


# A marker the author DENIES is not their identity. "To be clear this is NOT a Citrix VDI problem,
# our physical Windows desktops crash" names Citrix in order to rule it out, and the comma no
# longer separates it from the build. Scoped tight: only an explicit denial immediately before the
# marker suppresses it, so an ordinary mention still vetoes.
_NEGATED_MARKER_RE = re.compile(r"\b(?:not|isn't|aren't|no)\b[^.;!?]{0,26}$", re.I)


def _marker_is_denied(scope: str, start: int) -> bool:
    return bool(_NEGATED_MARKER_RE.search(scope[max(0, start - 34): start]))


def foreign_context(text: str, build: str = "") -> str:
    """The first identity this text belongs to that is NOT the tracked one, or ''.

    SCOPED, like the role veto beside it. An unscoped whole-document search vetoes exactly the
    best-evidenced reports, because the way a Windows user proves a defect is Windows-specific is
    to contrast it: "works on my Mac but not Windows", "Teams web is fine, the desktop client
    crashes", "this is NOT a Citrix problem, physical desktops crash". Judged on the whole post,
    every one of those refused a genuine Windows report.

    Identity is therefore judged on the clause(s) containing the tracked build, plus the TITLE line
    when the caller prepended one -- a title is the author's own framing, so a thread titled "Teams
    crashes on Mac" is still refused when the build sits further down.

    THE BUILD IS MASKED BEFORE SPLITTING. The shared clause splitter breaks on ".", which takes
    26198.304.4946.9672 apart into four fragments -- no clause then contains the build, the scope
    silently fell back to the whole document, and the scoping did nothing at all. lib.build_claims
    masks for the same reason.
    """
    body = str(text or "")
    low = re.sub(r"\s+", " ", body).lower()
    token = str(build or "").lower()
    scope = low
    if token and token in low:
        masked = low.replace(token, _BUILD_MASK)
        clauses = [c for c in _IDENTITY_CLAUSE_RE.split(masked) if c and _BUILD_MASK in c]
        if clauses:
            scope = " ".join(c.replace(_BUILD_MASK, token) for c in clauses)
            # `own` is built as "title\ntext", so a newline means a real title is present.
            if "\n" in body:
                scope += " " + re.sub(r"\s+", " ", body.split("\n", 1)[0]).lower()
    for reason, pattern in FOREIGN_CONTEXT:
        for hit in re.finditer(pattern, scope, re.I):
            if not _marker_is_denied(scope, hit.start()):
                return reason
    return ""


def role_veto(text: str, build: str) -> str:
    """Why this build is NOT the author's own failing version, or ''.

    Two layers. target_is_contradicted is the shared authority for "named as the fix" and "named as
    the known-good version", so Teams reads roles through the same primitive every other product
    does. The reference cues then cover phrasings carrying no outcome language at all -- a version
    offered as context, a comparison, or an instruction to upgrade -- and are scoped to a window
    around the build so an unrelated sentence elsewhere in a long post cannot veto the report.
    """
    contradiction = target_is_contradicted(text or "", build)
    if contradiction is not None:
        return f"version_role_{contradiction.outcome}"
    low = re.sub(r"\s+", " ", str(text or "")).lower()
    index = low.find(str(build).lower())
    if index < 0:
        return ""
    window = low[max(0, index - 220): index + 220]
    # Directional first: these are only meaningful in the text leading up to the build.
    preceding = low[max(0, index - 160): index]
    for reason, pattern in PRECEDING_CUES:
        if re.search(pattern, preceding, re.I):
            return reason
    for reason, pattern in REFERENCE_CUES:
        if re.search(pattern, window, re.I):
            return reason
    return ""


def describes_issue(text: str) -> bool:
    """Concrete failure, using the shared vocabulary plus Teams-shaped phrasings.

    Additive only: nothing the shared gate rejects for another reason becomes acceptable here.
    """
    if base.text_describes_issue(text):
        return True
    low = str(text or "").lower()
    return any(term in low for term in ISSUE_EXTRA_TERMS)


def evaluate_candidate(record: base.PatchRecord, candidate: dict[str, Any],
                       captured_at: str) -> dict[str, Any]:
    """ONE acceptance authority for every discovery method.

    The candidate must already be segment-scoped: report_text is the text of a single author.
    """
    build = str(record.update_version or "")
    # PatchRecord names this field update_published_at. A getattr default of "" here would
    # have emptied the release date silently, and an empty target date makes the shared
    # source_date gate unable to fail -- a report predating the patch would have counted.
    release_date = base.date_part(record.update_published_at or "")
    text = str(candidate.get("report_text") or "")
    title = str(candidate.get("report_title") or "")
    parent = str(candidate.get("parent_title") or "")
    # Identity and role are judged on the AUTHOR'S OWN text plus the thread title, never on replies.
    own = title + "\n" + text

    # REPLIES ARE NOT COUNTED IN V1. Segment scoping keeps a responder's build off the asker,
    # which is the safety property; counting the responder is a separate question and the live
    # calibration answered it badly. Answer segments came back carrying page furniture
    # ("class=\"margin-top-xxs\" > Nathan Alagappan - Follow 0 Reputation points"), and one such
    # row was accepted as a report. Reply text cannot currently be extracted cleanly, which is
    # exactly the stated condition for not using replies -- and a support agent writing "reports
    # point to it starting after build X" is not a user reporting their own failure either.
    # Tech Community already contributes opening posts only, so this also makes the two families
    # consistent. Replies are still discovered and stored for audit, just never counted.
    if str(candidate.get("segment_type") or "question") != "question":
        reply = base.make_evidence_row(
            product_id=TEAMS_PRODUCT_ID, update_version=build,
            source_type=str(candidate.get("source_type") or ""),
            source_name=str(candidate.get("source_name") or ""),
            source_url=str(candidate.get("source_url") or ""),
            parent_title=parent, report_title=title, report_text=text,
            captured_at=captured_at, source_date=str(candidate.get("source_date") or ""),
            target_release_date=release_date, patch_version_matched=False,
            matched_version="", match_basis="", counted=False,
            exclusion_reason="reply_segment_not_counted_v1",
            issue_theme="", workflow_area="", platform="Windows", severity="", sentiment="")
        reply["source_weight"] = 1
        return base.normalize_evidence_row(reply)

    matched, basis = teams_build_present(own, build)
    reason = None
    if not matched:
        reason = "missing_exact_patch_version_match"
    else:
        foreign = foreign_context(own, build)
        role = role_veto(own, build)
        if foreign:
            reason = foreign
        elif role:
            reason = role

    row = base.make_evidence_row(
        product_id=TEAMS_PRODUCT_ID,
        update_version=build,
        source_type=str(candidate.get("source_type") or ""),
        source_name=str(candidate.get("source_name") or ""),
        source_url=str(candidate.get("source_url") or ""),
        parent_title=parent,
        report_title=title,
        report_text=text,
        captured_at=captured_at,
        source_date=str(candidate.get("source_date") or ""),
        target_release_date=release_date,
        patch_version_matched=matched,
        matched_version=build if matched else "",
        match_basis=basis,
        counted=False,
        exclusion_reason=reason,
        issue_theme="",
        workflow_area="",
        platform="Windows",
        severity="",
        sentiment="",
    )
    if reason:
        row["counted"] = False
        row["exclusion_reason"] = reason
        row["source_weight"] = 1
        return base.normalize_evidence_row(row)

    gated = base.apply_acceptance_gates(row, report_text=own)
    # The shared gate uses the shared issue vocabulary. Teams phrasings ("no audio", "won't launch")
    # are additive, so a row rejected PURELY for that reason is re-tested against the wider list.
    if gated.get("exclusion_reason") == "not_a_real_issue_report" and describes_issue(own):
        gated["counted"] = True
        gated["exclusion_reason"] = None
    gated["source_weight"] = 1
    # DERIVED, NOT INVENTED. A counted row has already passed the concreteness gate, so "negative" is
    # a restatement of what acceptance means here, not a judgement added on top -- which is why every
    # counted row in the corpus carries one and no rejected row does. It is also load-bearing:
    # apply_consensus_to_records refuses a row whose sentiment is not in VALID_SENTIMENTS, while
    # reconcile_record_counts counts it regardless. Leaving it blank therefore publishes
    # update_report_count > 0 with no summary and no samples -- the blocking QA error that discards
    # every product's evidence for the cycle. Severity and issue_theme stay empty: those WOULD be
    # invented, and nothing downstream requires them.
    if gated.get("counted") is True:
        gated["sentiment"] = "negative"
    return base.normalize_evidence_row(gated)


# --- discovery: Microsoft Learn Q&A ---------------------------------------------------------------

def qna_segment_candidates(thread_url: str, page_html: str, *,
                           parent_title: str) -> list[dict[str, Any]]:
    """Authored segments of one Q&A thread, as candidates.

    The QUESTION segment is the report. An ANSWER may also be a report, but only as ITS OWN author's
    claim addressed by its own anchor URL -- never folded into the question. Machine-generated
    segments are dropped outright: AUXSAYS doctrine keeps AI out of the production evidence path.

    THE DATE IS THE ORIGINAL POST DATE, never the feed's. Microsoft Q&A search RSS re-stamps a
    thread every time somebody replies, and the release-date gate is the only thing standing between
    a report and the wrong patch: measured on the calibration threads, one report written
    2026-08-24 arrived stamped 2026-09-01 and another written 2026-09-25 arrived stamped with the
    day the collector ran. Last-activity is always LATER than the post, so using it makes the gate
    permissive in exactly the direction that misattributes an old report to a new build. A thread
    whose original date cannot be established gets no date at all and the gate refuses it -- see
    lib/post_dates.
    """
    parsed = source_segments.parse_learn_qna_thread(thread_url, page_html)
    if not getattr(parsed, "ok", False):
        return []
    original = original_post_date_from_html(page_html)
    out: list[dict[str, Any]] = []
    for seg in parsed.segments:
        if getattr(seg, "machine_generated", False):
            continue
        is_question = seg.segment_type == source_segments.SEGMENT_QUESTION
        out.append({
            "source_type": QNA_SOURCE_TYPE,
            "source_name": QNA_SOURCE_NAME,
            "source_url": source_segments.anchor_url(thread_url, seg),
            "parent_title": parent_title,
            "report_title": parent_title if is_question else "",
            "report_text": seg.segment_text,
            "source_date": seg.segment_date or original,
            "segment_type": seg.segment_type,
            "segment_key": seg.segment_key,
            "author_id": seg.author_id,
            "discovery_method": QNA_METHOD_ID,
        })
    return out


def discover_learn_qna(record: base.PatchRecord, context: Any, errors: list[dict[str, Any]],
                       *, fetch_page: Any = None) -> list[dict[str, Any]]:
    """Identity + symptom queries -> thread URLs -> authored segments."""
    from patch_collectors import microsoft_qna_tags_source as qna_tags

    fetcher = fetch_page or qna_tags.fetch
    build = str(record.update_version or "")
    queries = ["Teams " + build, "Microsoft Teams " + build] + list(SYMPTOM_QUERIES)
    raw = qna_source.collect_learn_qna_candidates(
        queries=queries, context=context, errors=errors,
        source_type=QNA_SOURCE_TYPE, source_name=QNA_SOURCE_NAME)

    candidates: list[dict[str, Any]] = []
    seen_threads: set[str] = set()
    for cand in raw:
        if budget_expired():
            errors.append({"source_url": "", "reason": BUDGET_STOP_REASON})
            break
        url = str(cand.get("source_url") or "")
        canonical = qna_source.canonical_learn_qna_url(url) or url
        if not canonical or canonical in seen_threads:
            continue
        seen_threads.add(canonical)
        try:
            page = fetcher(canonical if canonical.endswith("/") else canonical + "/")
        except Exception as exc:                                  # noqa: BLE001
            errors.append({"source_url": canonical, "reason": qna_source.error_reason(exc)})
            continue
        if not page:
            continue
        candidates += qna_segment_candidates(
            canonical, page,
            parent_title=str(cand.get("parent_title") or cand.get("report_title") or ""))
    return candidates


# --- discovery: Microsoft Tech Community ----------------------------------------------------------

def discover_tech_community(context: Any, errors: list[dict[str, Any]],
                            *, fetch_page: Any = None) -> list[dict[str, Any]]:
    """Board sitemap walk -> thread pages -> OPENING POST only.

    techcommunity_source.thread_candidate reads the JSON-LD mainEntity and nothing else, so replies
    by other participants are structurally unreachable from here. That is why this family
    contributes question-shaped candidates only.
    """
    fetcher = fetch_page or techcommunity_source.fetch
    since = str(getattr(context, "since", "") or "")
    threads = techcommunity_source.enumerate_sitemaps(
        list(TC_BOARD_SITEMAPS), since=since, url_pattern=TC_URL_RE, errors=errors)
    # BOUNDED. The board carries every recent thread, and one fetch per thread is the whole
    # request cost of this family. Capped by the run context so a busy week cannot turn a
    # scheduled run into an unbounded crawl; the cap is a ceiling, not a target.
    max_threads = max(1, int(getattr(context, "max_pages", 0) or 0) * 40) if getattr(
        context, "max_pages", 0) else 120
    threads = threads[:max_threads]
    out: list[dict[str, Any]] = []
    for thread in threads:
        if budget_expired():
            errors.append({"source_url": "", "reason": BUDGET_STOP_REASON})
            break
        url = str(thread.get("source_url") or "")
        if not url:
            continue
        try:
            page = fetcher(url)
        except Exception as exc:                                  # noqa: BLE001
            errors.append({"source_url": url, "reason": techcommunity_source.error_reason(exc)})
            continue
        candidate = techcommunity_source.thread_candidate(
            url, date=str(thread.get("date") or ""), page_html=page,
            source_type=TC_SOURCE_TYPE, source_name=TC_SOURCE_NAME)
        if candidate:
            candidate["discovery_method"] = TC_METHOD_ID
            candidate.setdefault("segment_type", "question")
            # SAME RULE AS THE Q&A FAMILY. thread_candidate puts the SITEMAP's lastmod in
            # source_date and falls back to it when no dateCreated is served -- correct for its
            # other consumers, wrong for a release-date gate, because lastmod moves with the newest
            # reply and is therefore always later than the post. Derived here without that
            # fallback: no establishable post date means no date, and the gate refuses the row
            # rather than admitting it under a window that may belong to a different patch.
            candidate["source_date"] = original_post_date_from_html(page)
            out.append(candidate)
    return out


# --- de-duplication -------------------------------------------------------------------------------

def dedupe_candidates(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    """One real report is one row, however many methods found it.

    Keyed on the canonical URL, which carries the segment anchor -- so two segments of one thread
    stay distinct while one segment found twice collapses. Discovery provenance is retained for
    auditability; the consensus count is unaffected because the extra method adds no row.
    """
    kept: dict[str, dict[str, Any]] = {}
    provenance: dict[str, list[str]] = {}
    for cand in candidates:
        key = base.normalize_url(str(cand.get("source_url") or ""))
        if not key:
            continue
        method = str(cand.get("discovery_method") or "")
        provenance.setdefault(key, [])
        if method and method not in provenance[key]:
            provenance[key].append(method)
        if key not in kept:
            kept[key] = cand
    return list(kept.values()), provenance


_REFUSAL_TOKENS = ("403", "401", "429", "blocked", "captcha", "challenge",
                   "rate_limit", "rate limited", "forbidden", "login")
_BREAKAGE_TOKENS = ("parse", "schema", "broken", "decode", "unexpected")


def method_status(candidates: list, errors: list, accepted: int) -> str:
    """Canonical health. A transport or parser failure is NEVER "nothing found".

    An empty result from a source we actually read is no_results -- "we looked and there was
    nothing". An empty result from a source we could not read is blocked or broken, because
    reporting that as no_results is how a dead source publishes as healthy.
    """
    reasons = " ".join(str(e.get("reason") or "") for e in (errors or [])).lower()
    if any(tok in reasons for tok in _REFUSAL_TOKENS):
        return "blocked"
    if any(tok in reasons for tok in _BREAKAGE_TOKENS):
        return "broken"
    # A BUDGET STOP IS NOT A REFUSAL AND NOT AN EMPTY SOURCE. We stopped looking; the source said
    # nothing. Reporting it as blocked would raise a transport alarm that is not true, and
    # reporting it as no_results would publish "we looked and there was nothing" about pages this
    # run never opened. Partial is the honest reading, and it is checked before the transport
    # branches below so a run that is both truncated and refused still surfaces the refusal.
    truncated = BUDGET_STOP_REASON in reasons
    if truncated and not any(tok in reasons for tok in _REFUSAL_TOKENS + _BREAKAGE_TOKENS):
        return "partial"
    if errors and not candidates:
        return "blocked"
    # PARTIAL OUTRANKS SUCCESS. A run that accepted a report AND failed to read some of its sources
    # did not fully succeed, and reporting it as "success" is how an eroding source publishes as
    # healthy -- the same silent-green shape the ingestion-health work closed upstream. Signature
    # failures (403/429/challenge/parse) have already returned above; what reaches here is the
    # ordinary per-thread failure, which is exactly what "partial" is for.
    if errors and candidates:
        return "partial"
    if accepted:
        return "success"
    if candidates:
        return "no_results"
    return "no_results"


def apply_consensus_writeback(update_version: str) -> bool:
    """Hand this patch to the SHARED consensus authority. No Teams-specific scoring exists.

    THE COLLECTOR WRITES FRESHNESS, NOT FINDINGS. `apply_collector_record_fields` filters every
    proposal through COLLECTOR_WRITABLE_FIELDS, so what lands here is evidence_last_checked and
    record_last_updated -- never the count, the summary or the samples. Those belong to the
    promotion stage that runs after reconciliation, which is why microsoft-teams is in
    CONSENSUS_PROMOTION_PRODUCTS and has its own scoped step in the collection workflow. A product
    that writes counted evidence with no promotion step wedges the ENTIRE lane on
    report_count_without_consensus_summary, discarding every other product's cycle with it.

    Selects by canonical identity and REFUSES an ambiguous resolution: more than one group under one
    version is not a record this collector may pick a winner from.
    """
    from apply_consensus_to_records import (_index_generated_records,  # noqa: PLC0415
                                            apply_collector_record_fields, run_dry_run)

    results = run_dry_run(evidence_path=base.EVIDENCE_PATH, product_id_filter=TEAMS_PRODUCT_ID,
                          is_candidate_mode=False, records_index=_index_generated_records(),
                          write_requested=True)
    matches = [item for item in results if item.get("update_version") == update_version]
    if len(matches) != 1 or not matches[0].get("would_write"):
        return False
    record_rel = matches[0].get("matched_generated_record_path")
    if not record_rel:
        return False
    fields = dict(matches[0].get("proposed_fields_if_written") or {})
    applied = apply_collector_record_fields(ROOT / record_rel, fields) or {}
    return bool((applied.get("write_plan") or {}).get("fields"))


class TeamsCommunityCollector(base.ProductCollector):
    """Default-off community evidence for the single tracked Teams identity.

    Patch targets come from the EXISTING generated records, never from version arithmetic: a
    community report can only attach to a patch AUXSAYS already tracks officially.
    """

    product_id = TEAMS_PRODUCT_ID

    def collect(self, context: base.CollectorContext) -> list[dict[str, Any]]:
        records = base.newest_first(base.generated_records(
            TEAMS_PRODUCT_ID, getattr(context, "target_versions", None)))
        captured_at = base.utc_now()
        results: list[dict[str, Any]] = []

        # Tech Community is walked ONCE per run, not once per record: the board sitemap is the same
        # corpus for every patch, and re-walking it per record would multiply requests for nothing.
        tc_errors: list[dict[str, Any]] = []
        tc_candidates = discover_tech_community(context, tc_errors)

        for record in records:
            if budget_expired():
                rb.emit("collector_budget_stop", product_id=TEAMS_PRODUCT_ID,
                        reason="collector_finalize")
                break
            qna_errors: list[dict[str, Any]] = []
            qna_candidates = discover_learn_qna(record, context, qna_errors)
            merged, provenance = dedupe_candidates(qna_candidates + tc_candidates)

            accepted: list[dict[str, Any]] = []
            rejected: list[dict[str, Any]] = []
            # Per METHOD, not per run: both health rows used to receive the run's whole accepted
            # total, so each method published the other's accepted reports as its own.
            by_method: dict[str, list[int]] = {QNA_METHOD_ID: [0, 0], TC_METHOD_ID: [0, 0]}
            for cand in merged:
                row = evaluate_candidate(record, cand, captured_at)
                counted = bool(row.get("counted"))
                (accepted if counted else rejected).append(row)
                key = base.normalize_url(str(cand.get("source_url") or ""))
                for method in provenance.get(key, [str(cand.get("discovery_method") or "")]):
                    if method in by_method:
                        by_method[method][0 if counted else 1] += 1

            method_health: list[dict[str, Any]] = []
            for method_id, source_type, cands, errs in (
                (QNA_METHOD_ID, QNA_SOURCE_TYPE, qna_candidates, qna_errors),
                (TC_METHOD_ID, TC_SOURCE_TYPE, tc_candidates, tc_errors),
            ):
                m_accepted, m_rejected = by_method.get(method_id, [0, 0])
                status = method_status(cands, errs, m_accepted)
                blocked = ""
                if status in ("blocked", "broken") and errs:
                    blocked = str(errs[0].get("reason") or "")[:120]
                method_health.append(base.method_health_row(
                    product_id=TEAMS_PRODUCT_ID,
                    update_version=str(record.update_version or ""),
                    method_id=method_id, source_type=source_type, status=status,
                    candidates_found=len(cands), accepted_reports=m_accepted,
                    rejected_reports=m_rejected, blocked_reason=blocked, last_run=captured_at,
                    notes=(source_type + " discovery for microsoft-teams "
                           + str(record.update_version or "") + ". Candidates " + str(len(cands))
                           + ", accepted " + str(m_accepted) + ", rejected " + str(m_rejected) + ".")))

            result: dict[str, Any] = {
                "product_id": TEAMS_PRODUCT_ID,
                "version": record.update_version,
                "mode": "write" if context.write else "dry-run",
                "candidates_reviewed": len(accepted) + len(rejected),
                "accepted_count": len(accepted),
                "rejected_count": len(rejected),
                "accepted_urls": [r["source_url"] for r in accepted],
                "method_health": method_health,
            }
            if context.write:
                persisted: list[dict[str, Any]] = []
                already_held: list[dict[str, Any]] = []
                added, total, _rows = base.append_evidence_rows(
                    accepted + rejected, out_added=persisted, out_already_held=already_held)
                # evidence_rows_added must state what actually REACHED the store, not what was
                # accepted this run -- a collector re-finds the same threads every run.
                base.finalize_method_health_delta(method_health, persisted, already_held)
                result["evidence_rows_added"] = added
                result["record_updated"] = (
                    apply_consensus_writeback(str(record.update_version or "")) if accepted else False)
            results.append(result)
        return results
