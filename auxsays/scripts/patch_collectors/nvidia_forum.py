#!/usr/bin/env python3
"""Community evidence for NVIDIA's desktop drivers, from the NVIDIA GeForce forum's default views.

THE QUESTION THIS ANSWERS. "Is someone reporting a concrete problem on THIS exact driver, of THIS
family?" GeForce Game Ready and NVIDIA Studio are two products that share version numbers (621.14
and 621.24 each shipped as both, the same day), so a report counts for a family only when the
family is established -- never from the version alone (lib.nvidia_driver_identity).

WHAT IS READ is decided by nvidia_forum_source: the two default views, at most one cycle per 12
hours, shared by both family collectors in one run. This module decides what each comment is.

IDENTITY, IN ORDER (each refusal is stored as an excluded row with its reason, so it is auditable):

1. The comment's OWN text must name a tracked version exactly (the shared matcher, after links and
   quoted lines are removed -- a URL or a quote is not the reporter naming a version). A thread
   title alone never makes a comment a report: the title is not the commenter's words, and a
   "this driver" written after the next driver shipped names nothing. A comment naming no tracked
   version is not a candidate at all.
2. Family (GPT G47 C, lib.nvidia_driver_identity.report_family). A staff feedback thread
   establishes its family only when its TITLE names exactly one driver version AND exactly one
   family, and only for that version: "GeForce GRD 621.24 Feedback Thread" makes a 621.24 comment
   inside it Game Ready, but not a 621.14 comment. A user topic or a community never establishes a
   family. The reporter naming a family establishes it; naming the other family vetoes the thread's;
   naming both establishes nothing. A comment with no established family -- the shared-component
   defects (the SSD-write component both families install) are the measured case -- is stored as
   `driver_family_unassigned` for BOTH products and counted for neither: one report is never two
   family reports.
3. Desktop only. Both products are desktop driver packages; a laptop or notebook report is
   `notebook_driver_not_tracked`, never merged into a desktop record.
4. The version must be the subject (GPT G44 s4). Named only on a specification line ("Driver:
   621.14", "NVIDIA Driver Version: 621.24", "Using latest drivers 621.14") it is environment, not
   attribution: `driver_version_environment_only`. Named in a sentence where the reporter says they
   cannot tell whether it is the cause: `driver_attribution_disclaimed`. A crash in a driver module
   (nvlddmkm, TDR, LiveKernelEvent) with no rollback, contrast or "since updating" is investigated,
   not counted: `driver_module_crash_without_regression_evidence`. A post that only says the driver
   is fine and names no malfunction is not a problem report: `positive_report_not_a_problem`.
5. Role. With another tracked version named, silence is not enough: the shared role reading
   (lib.target_outcome) must say the version is the affected one; with none, a version named as
   working, fixed or rolled back to is vetoed (target_is_contradicted).

THEN THE SHARED AUTHORITY, UNCHANGED: base.apply_acceptance_gates (exact version, specific URL,
created on or after the release, concrete problem). No threshold, weight or acceptance rule of this
product's own exists. The report date is the comment's own creation time, never its last activity.
The stored URL is the forum's own link to that one comment, under its thread.

PUBLIC TEXT. Names, @mentions and e-mail addresses are removed from every stored text, and links are
replaced by a marker. Report titles are the thread's title.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from lib import evidence_classification as ec
from lib import nvidia_driver_identity as identity
from lib.method_routing import plan_methods
from lib.target_outcome import AFFECTED, classify_target_outcome, target_is_contradicted
from patch_collectors import base
from patch_collectors import nvidia_forum_source as src
from patch_collectors import runtime_budget as rb

# Module-level so the governed write-authority suite can repoint it (test_collector_write_authority O8b).
ROOT = base.ROOT

PRODUCTS = (identity.GAME_READY, identity.STUDIO)
METHOD_ID = "nvidia_forum_default_views"
SOURCE_TYPE = "nvidia_forum_comment"
SOURCE_NAME = src.PROVENANCE["source_origin"]

# --- text --------------------------------------------------------------------------------------------

_QUOTE_LINE_RE = re.compile(r"^[ \t]*>.*$", re.M)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_STAFF_NAME_RE = re.compile(r"\b[\w.-]+@NVIDIA\b")
_MENTION_RE = re.compile(r"(?<![\w.@])@[A-Za-z0-9_][\w.-]{0,40}")
_URL_RE = re.compile(r"https?://[^\s)\]>]+|\bwww\.[^\s)\]>]+", re.I)


def clean_text(text: Any) -> str:
    """The commenter's own words: quoted lines dropped, people's names and links removed."""
    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    value = _QUOTE_LINE_RE.sub("", value)
    value = _EMAIL_RE.sub("[email]", value)
    value = _STAFF_NAME_RE.sub("NVIDIA staff", value)
    value = _MENTION_RE.sub("@user", value)
    value = _URL_RE.sub("[link]", value)
    return value.strip()


_DRIVER_VERSION_RE = re.compile(r"(?<![\w.])(\d{3,4}\.\d{2})(?![\w]|\.\d)")


def driver_versions_in(text: Any) -> set[str]:
    """Every driver-version-shaped number (NNN.NN) the text names."""
    return set(_DRIVER_VERSION_RE.findall(str(text or "")))


def occurrences(text: str, version: str) -> list[tuple[int, int]]:
    """Every position the shared exact matcher accepts as this version."""
    out: list[tuple[int, int]] = []
    offset = 0
    while offset <= len(text):
        matched, _v, _basis, start, end = base.exact_version_match_span(text[offset:], version)
        if not matched:
            break
        out.append((offset + start, offset + end))
        offset += end
    return out


# --- thread qualification ------------------------------------------------------------------------------

def thread_profile(title: str, staff_author: bool) -> dict[str, Any]:
    """What a thread's TITLE establishes. A staff thread is patch-specific for a family only when
    the title names exactly one driver version and exactly one family."""
    versions = driver_versions_in(title)
    families = identity.families_named(title)
    patch_family = None
    title_version = None
    if staff_author and len(versions) == 1 and len(families) == 1:
        (title_version,) = versions
        (patch_family,) = families
    return {"title_versions": sorted(versions), "staff": bool(staff_author),
            "patch_family": patch_family, "title_version": title_version}


# --- attribution ---------------------------------------------------------------------------------------

_NOTEBOOK_RE = re.compile(r"\b(?:laptops?|notebooks?|max-q|mobile\s+gpu)\b", re.I)
# A notebook named as SOMEONE ELSE's machine ("works on another system with an RTX 4070 Laptop GPU",
# comment 3633451) says nothing about the reporter's own install.
_OTHER_MACHINE_RE = re.compile(r"\b(?:another|other|second|different|friend'?s|wife'?s|husband'?s)\b", re.I)

# A specification line names a version as environment: a short label (driver, driver version, ver.)
# immediately before the number, inside its own comma/sentence segment, with no defect word in the
# segment on either side. A label with a colon ("Driver: 621.14") is a field whatever follows in
# another segment; a bare label ("Using latest drivers 621.14", "driver 621.24" in a comma list) is a
# field only when its whole segment is short -- "Game Ready Driver 621.14 fucks up my system" is a
# sentence about the driver, not a field.
_SEGMENT_BREAK_RE = re.compile(r"[,;|\n]|(?<![Vv]er)\.(?=\s|$)|\s[-–—]\s")
_ENV_COLON_LABEL_RE = re.compile(
    r"\b(?:drivers?(?:\s+ver(?:sion|\.)?)?|ver(?:sion|\.)?)\s*[:=]\s*(?:nvidia\s+|geforce\s+)?v?\s*\Z", re.I)
_ENV_BARE_LABEL_RE = re.compile(
    r"\b(?:drivers?(?:\s+ver(?:sion|\.)?)?|ver(?:sion|\.)?)\s*(?:nvidia\s+|geforce\s+)?v?\s*\Z", re.I)
_DEFECT_WORDS = (r"crash\w*|freez\w*|froze|hang\w*|black|blank|flicker\w*|stutter\w*|broke\w*|break\w*"
                 r"|bug\w*|issue\w*|problem\w*|regress\w*|fail\w*|artifact\w*|tdrs?|bsod|error\w*|corrupt\w*"
                 r"|lag\w*|slow\w*|drops?|capped|locked|affected|bad|worse|glitch\w*|fuck\w*|mess\w*"
                 r"|screw\w*|ruin\w*|kill\w*|not\s+work\w*|doesn'?t\s+work|won'?t|can'?t|cannot")
_DEFECT_RE = re.compile(rf"\b(?:{_DEFECT_WORDS})\b", re.I)
# A field is environment only while nothing in its segment ties the version to a problem or a change.
_ENV_BREAK_RE = re.compile(rf"\b(?:{_DEFECT_WORDS}|caus\w*|introduc\w*|since|after|still|new)\b", re.I)
_ENV_MAX_WORDS = 6

# G44 s4 row 4: a crash in an NVIDIA driver module, without release-specific regression evidence, is
# investigated, never counted automatically. Regression evidence is a rollback, a contrast with a
# version that is not affected, or the reporter dating the problem to an update.
_MODULE_CRASH_RE = re.compile(
    r"\b(?:nvlddmkm(?:\.sys)?|video_tdr_failure|livekernelevent|tdrs?|0x116|0x141|0x1b8|bug\s*check)\b", re.I)
_REGRESSION_EVIDENCE_RE = re.compile(
    r"\b(?:roll(?:ed|ing|s)?\s*back|revert\w*|downgrad\w*|went\s+back|go(?:ing|es)?\s+back"
    r"|new\s+in|since\s+(?:updating|installing|upgrading|the\s+(?:update|new\s+driver))"
    r"|after\s+(?:updating|installing|upgrading|the\s+update)|driver\s+regression\s*:\s*yes"
    r"|not\s+affected|unaffected|is\s+clean|was\s+(?:fine|stable)|last\s+(?:known[\s-]+)?(?:good|working))\b",
    re.I)

# A post that only says the driver is fine is not a problem report, whatever the shared concreteness
# vocabulary makes of it ("Installed 621.24 over 591, clean install ... No issues at all": the word
# "install" is in that vocabulary). Only when it names no malfunction at all.
_POSITIVE_RE = re.compile(
    r"\b(?:no\s+(?:issues?|problems?)(?:\s+at\s+all)?|zero\s+issues?"
    r"|(?:looks|seems|is)\s+(?:like\s+)?an?\s+(?:good|great|solid|stable)\s+driver"
    r"|(?:works?|working|runs?|running|seems?|performs?)\s+(?:fine|great|perfectly|flawless\w*|very\s+well|well))\b",
    re.I)

_SENTENCE_BREAK_RE = re.compile(r"[!?;\n]|\.(?=\s|$)")
_DISCLAIMER_RE = re.compile(
    r"\b(?:cannot|can't|can not|not able to|unable to)\s+(?:confirm|tell|say|determine)\s+(?:whether|if)\b"
    r"|\bnot\s+(?:an?\s+)?(?:issue|problem|bug)\s+(?:specific|related|limited)\s+to\b"
    r"|\bnot\s+sure\s+(?:whether|if)\b", re.I)


def _bounds(text: str, start: int, end: int, pattern: re.Pattern[str]) -> tuple[int, int]:
    lo = 0
    for hit in pattern.finditer(text, 0, start):
        lo = hit.end()
    nxt = pattern.search(text, end)
    return lo, (nxt.start() if nxt else len(text))


def _words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+", text))


def is_environment_occurrence(text: str, start: int, end: int) -> bool:
    lo, hi = _bounds(text, start, end, _SEGMENT_BREAK_RE)
    prefix = re.sub(r"[*`_]", " ", text[lo:start])
    prefix = re.sub(r"\A[\s•#>-]+", "", prefix)
    suffix = text[end:hi]
    if _ENV_BREAK_RE.search(prefix) or _ENV_BREAK_RE.search(suffix):
        return False
    if _ENV_COLON_LABEL_RE.search(prefix):
        return _words(prefix) <= _ENV_MAX_WORDS
    if _ENV_BARE_LABEL_RE.search(prefix):
        return _words(prefix) + _words(suffix) <= _ENV_MAX_WORDS
    return False


def own_machine_is_notebook(text: str) -> bool:
    for hit in _NOTEBOOK_RE.finditer(text):
        if not _OTHER_MACHINE_RE.search(text[max(0, hit.start() - 50):hit.start()]):
            return True
    return False


def module_crash_without_regression(text: str) -> bool:
    return bool(_MODULE_CRASH_RE.search(text)) and not _REGRESSION_EVIDENCE_RE.search(text)


def positive_only(text: str) -> bool:
    """Says the driver is fine, and -- the positive phrases set aside -- names no problem at all."""
    if not _POSITIVE_RE.search(text):
        return False
    return not _DEFECT_RE.search(_POSITIVE_RE.sub(" ", text))


def attribution_disclaimed(text: str, spans: list[tuple[int, int]]) -> bool:
    for start, end in spans:
        lo, hi = _bounds(text, start, end, _SENTENCE_BREAK_RE)
        if _DISCLAIMER_RE.search(text[lo:hi]):
            return True
    return False


def family_reason(product_id: str, own: str, version: str, thread: dict[str, Any]) -> str:
    """'' when the family is established as `product_id`; else why not."""
    thread_family = thread.get("patch_family") if thread.get("title_version") == version else None
    named = identity.families_named(own)
    family = identity.report_family(own, thread_family)
    if family == product_id:
        return ""
    if family is not None:
        return "driver_family_is_other"
    if len(named) > 1:
        return "driver_family_both_named"
    if named and thread_family:
        return "driver_family_conflicts_with_thread"
    return "driver_family_unassigned"


# --- classification (presentation only, never acceptance) ----------------------------------------------

_THEME_RULES: tuple[ec.ThemeRule, ...] = (
    ec.ThemeRule("excessive disk writes", "storage", "high", "disk_writes",
                 re.compile(r"\b(?:(?:ssd|disk|nvme|drive)\s+writ\w*|writ\w*\s+(?:to\s+)?(?:the\s+)?(?:ssd|disk|nvme)"
                            r"|nvlog|nvtopps|gigabytes?\s+(?:per|an?)\s+hour)\b", re.I)),
    ec.ThemeRule("crash or driver reset", "system stability", "high", "crash",
                 re.compile(r"\b(?:crash\w*|tdr|bsod|blue\s+screen|nvlddmkm|freez\w*|froze|hang(?:s|ing)?"
                            r"|watchdog|reboots?|restarts?)\b", re.I), negatable=True),
    ec.ThemeRule("black screen or display loss", "display output", "high", "display",
                 re.compile(r"\b(?:black\s+screen\w*|blank\s+screen|no\s+signal|not\s+detected"
                            r"|monitor\w*\s+(?:goes|go|went|stays?)\s+black|won'?t\s+wake)\b", re.I),
                 negatable=True),
    ec.ThemeRule("flicker or wrong colors", "rendering", "medium", "visual",
                 re.compile(r"\b(?:flicker\w*|artifact\w*|washed\s+out|wrong\s+colou?rs?|incorrect\s+colou?rs?"
                            r"|corrupt\w*|raises?\s+black)\b", re.I), negatable=True),
    ec.ThemeRule("performance or stutter", "performance", "medium", "performance",
                 re.compile(r"\b(?:stutter\w*|fps\s+drops?|frame\s*drops?|slow\w*|lag\w*|hitch\w*"
                            r"|performance)\b", re.I)),
    ec.ThemeRule("power or thermal limit", "power and thermals", "medium", "power",
                 re.compile(r"\b(?:power\s+(?:limit\w*|capped|locked)|watts?\b|temperature\w*|thermal)\b", re.I)),
)
ec.validate_rules(_THEME_RULES)


def classify(title: str, text: str) -> tuple[str, str, str, str]:
    platform = ec.resolve_platform(text, heading=title or "").label
    verdict = ec.score_themes(title or "", text, _THEME_RULES)
    if verdict is None:
        return "", "", platform, ""
    return verdict.theme, verdict.area, platform, verdict.severity


# --- one decision per (product, record, comment) -------------------------------------------------------

def _iso(stamp: Any) -> str:
    try:
        return datetime.fromtimestamp(int(stamp), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def evaluate_comment(product_id: str, record: base.PatchRecord, tracked_versions: set[str],
                     thread: dict[str, Any], item: dict[str, Any], captured_at: str) -> dict[str, Any] | None:
    """The evidence row for one comment and one record, or None when the comment does not name the
    record's version (never a candidate)."""
    version = str(record.update_version or "")
    own = str(item.get("own_text") or "")
    spans = occurrences(own, version)
    if not spans:
        return None
    reason = family_reason(product_id, own, version, thread)
    if not reason and own_machine_is_notebook(own):
        reason = "notebook_driver_not_tracked"
    if not reason and all(is_environment_occurrence(own, s, e) for s, e in spans):
        reason = "driver_version_environment_only"
    if not reason and attribution_disclaimed(own, spans):
        reason = "driver_attribution_disclaimed"
    if not reason and module_crash_without_regression(own):
        reason = "driver_module_crash_without_regression_evidence"
    if not reason and positive_only(own):
        reason = "positive_report_not_a_problem"
    if not reason:
        # Another TRACKED version of this product named too: silence is not enough, the shared role
        # reading must say this one is the affected one (the Acrobat shared-build rule). Untracked
        # versions are left to the single-version veto, as every other collector does.
        named = {v for v in tracked_versions if v != version and occurrences(own, v)}
        if named:
            outcome = classify_target_outcome(own, version)
            if outcome.outcome != AFFECTED:
                reason = (f"version_role_{outcome.outcome}" if outcome.vetoes
                          else "multiple_tracked_versions_named")
        else:
            contradiction = target_is_contradicted(own, version, set())
            if contradiction is not None:
                reason = f"version_role_{contradiction.outcome}"

    title = str(thread.get("title") or "")
    theme, area, platform, severity = classify(title, own)
    start, end = spans[0]
    provenance = base.match_provenance([("report_text", own)], start, end)
    row = base.make_evidence_row(
        product_id=product_id,
        update_version=version,
        source_type=SOURCE_TYPE,
        source_name=SOURCE_NAME,
        source_url=str(item.get("url") or ""),
        parent_title=title,
        report_title=title,
        report_text=own,
        captured_at=captured_at,
        # The comment's own creation time. lastActivityStamp and updatedStamp move with replies,
        # votes and edits and are never read as the report date.
        source_date=_iso(item.get("created")),
        target_release_date=base.date_part(record.update_published_at or ""),
        patch_version_matched=True,
        matched_version=version,
        match_basis="exact_version_text",
        counted=False,
        exclusion_reason=reason or None,
        issue_theme=theme,
        workflow_area=area,
        platform=platform,
        severity=severity,
        sentiment="",
        row_id=f"{product_id}-{base.slug(version)}-nvidia-forum-{int(thread['topic_id'])}-{int(item['comment_id'])}",
        matched_text=provenance.get("matched_text", ""),
        matched_field=provenance.get("matched_field", ""),
        matched_context=provenance.get("matched_context", ""),
    )
    if reason:
        row["counted"] = False
        row["exclusion_reason"] = reason
        return base.normalize_evidence_row(row)
    gated = base.apply_acceptance_gates(row, report_text=own)
    # DERIVED, NOT INVENTED (the Teams rule): a counted row has passed the concreteness gate, and the
    # promotion refuses a counted row without a sentiment while reconciliation counts it.
    if gated.get("counted") is True:
        gated["sentiment"] = "negative"
    return base.normalize_evidence_row(gated)


# --- the cycle: one per process, shared by both family collectors --------------------------------------

_CYCLE: dict[str, Any] | None = None


def reset_cycle() -> None:
    """Forget this process's cycle. Tests only; production runs one cycle per process."""
    global _CYCLE
    _CYCLE = None


def _items_for(thread: dict[str, Any], topic: dict[str, Any], comments: list[dict[str, Any]],
               community_id: int, community_slug: str) -> list[dict[str, Any]]:
    """Every user-authored, visible comment the default view shows, as candidates."""
    topic_id = int(topic["id"])
    topic_slug = src.forum_slug(topic.get("title"))
    out: list[dict[str, Any]] = []

    def add(comment: dict[str, Any], own: str) -> None:
        if src.is_staff(comment.get("user")) or comment.get("isOfficialReply") == 1 or not src.visible(comment):
            return
        out.append({"comment_id": int(comment["id"]), "created": int(comment["createdStamp"]),
                    "own_text": clean_text(own),
                    "url": src.comment_url(community_id, community_slug, topic_id, topic_slug, int(comment["id"]))})

    first = topic.get("firstComment") or {}
    if not thread["staff"] and isinstance(first.get("id"), int) and isinstance(first.get("createdStamp"), int) \
            and isinstance(first.get("body"), str):
        # The opening post of a user topic: its title IS the author's own words.
        add(first, f"{topic.get('title') or ''}\n{first.get('body') or ''}")
    for comment in comments:
        add(comment, str(comment.get("body") or ""))
        for reply in comment.get("comments") or []:
            add(reply, str(reply.get("body") or ""))
    return out


def _select_threads(listings: list[tuple[int, str, dict[str, Any]]], state: dict[str, Any],
                    versions: set[str]) -> list[dict[str, Any]]:
    """Threads to read this cycle, best first.

    1. Staff patch-specific threads: listed now, remembered from an earlier listing (a feedback
       thread stays relevant after it is unpinned), or a seed not read yet. Newest first.
    2. User topics whose title names a tracked version, ONLY while the community's default listing
       shows them (newest activity first). A user topic that dropped out of the listing is not
       re-read; it stays remembered, and its window is compared again when it reappears.
    A thread is tracked only if its title names a version a record exists for."""
    known: dict[int, dict[str, Any]] = {}
    for community_id, community_slug, topic in listings:
        title = str(topic.get("title") or "")
        profile = thread_profile(title, src.is_staff(topic.get("user")))
        if not set(profile["title_versions"]) & versions:
            continue
        tid = int(topic["id"])
        known[tid] = {"topic_id": tid, "community_id": community_id, "community_slug": community_slug,
                      "title": title, "listed_activity": int(topic["lastActivityStamp"]),
                      "created": int(topic.get("createdStamp") or 0), **profile}
    for tid_text, entry in (state.get("threads") or {}).items():
        tid = int(tid_text)
        profile = thread_profile(str(entry.get("title") or ""), bool(entry.get("staff")))
        if tid in known or not profile["patch_family"] or not set(profile["title_versions"]) & versions:
            continue
        known[tid] = {"topic_id": tid, "community_id": int(entry.get("community_id") or 0),
                      "community_slug": str(entry.get("community_slug") or ""),
                      "title": str(entry.get("title") or ""), "listed_activity": None,
                      "created": int(entry.get("created") or 0), **profile}
    slugs = dict(src.COMMUNITIES)
    seeds_read = {int(t) for t in state.get("seeds_read") or []}
    for community_id, tid in src.SEED_THREADS:
        if tid not in known and str(tid) not in (state.get("threads") or {}) and tid not in seeds_read:
            known[tid] = {"topic_id": tid, "community_id": community_id,
                          "community_slug": slugs.get(community_id, ""), "title": "", "listed_activity": None,
                          "created": 0, "title_versions": [], "staff": False, "patch_family": None,
                          "title_version": None, "seed": True}
    return sorted(known.values(), key=lambda t: (
        0 if (t.get("patch_family") or t.get("seed")) else 1,
        -int(t.get("created") or 0) if (t.get("patch_family") or t.get("seed")) else -int(t.get("listed_activity") or 0),
        -int(t["topic_id"])))


def run_cycle(context: base.CollectorContext, versions: set[str], *, keep_versions: set[str] | None = None,
              now: datetime | None = None) -> dict[str, Any]:
    """This process's forum cycle (network, at most once). Returns what both collectors read.

    `versions` are the records this run walks (a targeted run narrows them); `keep_versions` are all
    tracked records, so a targeted run never forgets the other threads it remembers."""
    global _CYCLE
    if _CYCLE is not None:
        return _CYCLE
    current = now or datetime.now(timezone.utc)
    cycle: dict[str, Any] = {"stop": "", "stop_status": "", "detail": "", "skipped": "", "threads": [],
                             "deferred": [], "requests": 0, "state": None, "saved": False,
                             "ran": False, "at": current.replace(microsecond=0).isoformat().replace("+00:00", "Z")}
    _CYCLE = cycle
    try:
        state = src.load_state()
    except src.SchemaIntegrityStop as exc:
        cycle.update(stop="schema_changed", stop_status="broken", detail=str(exc))
        return cycle
    cycle["state"] = state
    disabled = METHOD_ID in plan_methods(identity.GAME_READY).get("disabled", []) \
        and METHOD_ID in plan_methods(identity.STUDIO).get("disabled", [])
    suspended = src.suspension(state, current)
    if disabled:
        cycle.update(stop="disabled", stop_status="disabled", detail="switched off in method routing")
        return cycle
    if suspended:
        cycle.update(stop="access_refused", stop_status="blocked", detail=suspended)
        return cycle
    if not versions:
        cycle["skipped"] = "no_tracked_records"
        return cycle
    if not src.cycle_due(state, current):
        cycle["skipped"] = "cadence"
        return cycle

    transport = src.Transport(state)
    cycle["ran"] = True
    read: list[dict[str, Any]] = []
    try:
        policies = src.read_robots(transport)
        listings: list[tuple[int, str, dict[str, Any]]] = []
        for community_id, community_slug in src.COMMUNITIES:
            for url in src.community_view_urls(community_id):
                src.check_robots(policies, url, f"{src.WWW_FORUM_PATH}/{community_slug}/{community_id}/")
                payload = transport.get_json(url)
                listings.extend((community_id, community_slug, topic)
                                for topic in src.listing_topics(payload, "a community listing"))
        candidates = _select_threads(listings, state, versions)
        for thread in candidates:
            if len(read) >= src.MAX_THREADS_PER_CYCLE or transport.remaining() < 2 or _budget_expired():
                cycle["deferred"].append(thread)
                continue
            stored = (state.get("threads") or {}).get(str(thread["topic_id"])) or {}
            if thread.get("listed_activity") is not None and stored.get("window") \
                    and int(stored.get("last_activity") or -1) == thread["listed_activity"]:
                read.append(dict(thread, outcome="unchanged", items=[], gap=[], coverage=[]))
                continue
            read.append(_read_thread(transport, policies, thread, stored, versions))
    except src.AccessRefused as exc:
        cycle.update(stop="access_refused", stop_status="blocked", detail=str(exc))
    except src.RobotsStop as exc:
        cycle.update(stop="robots_policy", stop_status="blocked", detail=str(exc))
    except src.SourceAuthorityStop as exc:
        cycle.update(stop="source_authority_stop", stop_status="broken", detail=str(exc))
    except src.SchemaIntegrityStop as exc:
        cycle.update(stop="schema_changed", stop_status="broken", detail=str(exc))
    except src.ForbiddenRequest as exc:
        cycle.update(stop="request_outside_default_views", stop_status="broken", detail=str(exc))
    except (src.TransportError, src.RequestBudgetExhausted) as exc:
        cycle.update(stop="network_error", stop_status="broken", detail=str(exc))
    cycle["requests"] = len(transport.requests)
    cycle["request_urls"] = list(transport.requests)
    state["last_cycle"] = {"at": cycle["at"], "requests": len(transport.requests),
                           "outcome": cycle["stop"] or "ok"}
    if not cycle["stop"]:
        # Windows are remembered only from a cycle that finished: a stop keeps the last good ones.
        cycle["threads"] = read
        for thread in read:
            if thread.get("outcome") == "read":
                state.setdefault("threads", {})[str(thread["topic_id"])] = thread["state_entry"]
            if thread.get("seed") and thread.get("outcome") in ("read", "unchanged", "not_tracked"):
                state["seeds_read"] = sorted({int(t) for t in state.get("seeds_read") or []}
                                             | {int(thread["topic_id"])})
        for thread in cycle["deferred"]:
            entry = (state.get("threads") or {}).get(str(thread["topic_id"]))
            if entry is None and thread.get("title"):
                state.setdefault("threads", {})[str(thread["topic_id"])] = {
                    "community_id": thread["community_id"], "community_slug": thread["community_slug"],
                    "title": thread["title"], "staff": thread["staff"],
                    "title_versions": thread["title_versions"], "created": thread.get("created") or 0,
                    "last_activity": None, "window": []}
        src.prune_threads(state, set(keep_versions or versions), current)
    return cycle


def _budget_expired() -> bool:
    budget = rb.get_run_budget()
    return budget is not None and budget.collector_finalize_expired()


def _read_thread(transport: src.Transport, policies: dict[str, Any], thread: dict[str, Any],
                 stored: dict[str, Any], versions: set[str]) -> dict[str, Any]:
    tid = int(thread["topic_id"])
    path = src.www_topic_path(thread["community_id"], thread["community_slug"], tid,
                              src.forum_slug(thread["title"]) if thread.get("title") else "")
    url = src.topic_url(tid)
    src.check_robots(policies, url, path)
    try:
        topic = src.topic_view(transport.get_json(url), tid)
    except src.TransportError as exc:
        return dict(thread, outcome="failed", detail=str(exc), items=[], gap=[], coverage=[])
    community = topic["communities"][0]
    community_id = int(community["id"])
    community_slug = src.forum_slug(community.get("title"))
    profile = thread_profile(topic["title"], src.is_staff(topic.get("user")))
    merged = dict(thread, title=topic["title"], community_id=community_id, community_slug=community_slug,
                  created=int(topic["createdStamp"]), **profile)
    if not set(profile["title_versions"]) & versions:
        # A seed or remembered thread whose title no longer names a tracked version.
        return dict(merged, outcome="not_tracked", items=[], gap=[], coverage=[])
    last_activity = int(topic["lastActivityStamp"])
    if stored.get("window") and int(stored.get("last_activity") or -1) == last_activity:
        return dict(merged, outcome="unchanged", items=[], gap=[], coverage=[])
    last_comment = int(topic["lastComment"]["id"])
    transport.anchors[tid] = last_comment
    comments_url = src.topic_comments_url(tid, last_comment)
    src.check_robots(policies, comments_url, src.www_topic_path(community_id, community_slug, tid,
                                                                  src.forum_slug(topic["title"])))
    try:
        comments, total = src.comments_view(transport.get_json(comments_url))
    except src.TransportError as exc:
        return dict(merged, outcome="failed", detail=str(exc), items=[], gap=[], coverage=[])
    window = src.window_of(comments)
    gap = src.compare_windows(stored.get("window") or None, window,
                              stored.get("total_rows"), total)
    coverage: list[str] = []
    expected = min(src.COMMENT_PAGE_SIZE, total)
    if len([c for c in comments]) < expected:
        coverage.append("incomplete_window")
    if total > len(comments):
        coverage.append("older_comments_outside_window")
    if any(int(c.get("replyCount") or 0) > len(c.get("comments") or []) for c in comments):
        coverage.append("replies_not_embedded")
    entry = {"community_id": community_id, "community_slug": community_slug, "title": topic["title"],
             "staff": profile["staff"], "title_versions": profile["title_versions"],
             "created": int(topic["createdStamp"]), "last_activity": last_activity, "total_rows": total,
             "window": window, "last_read_at": base.utc_now(),
             "first_read_at": stored.get("first_read_at") or base.utc_now(),
             "gap_reasons": gap, "coverage": coverage}
    return dict(merged, outcome="read", items=_items_for(merged, topic, comments, community_id, community_slug),
                gap=gap, coverage=coverage, state_entry=entry)


# --- health ---------------------------------------------------------------------------------------------

def _version_status(cycle: dict[str, Any], version: str, accepted: int) -> tuple[str, str, list[str]]:
    """(status, blocked_reason, gap_reasons) for one version, from what this cycle saw."""
    if cycle.get("stop"):
        return cycle["stop_status"], cycle["stop"], []
    relevant = [t for t in cycle.get("threads", []) if version in (t.get("title_versions") or [])]
    deferred = [t for t in cycle.get("deferred", []) if version in (t.get("title_versions") or [])]
    gaps = sorted({reason for t in relevant for reason in (t.get("gap") or [])})
    if gaps:
        return "partial", "possible_missed_comments", gaps
    if any("incomplete_window" in (t.get("coverage") or []) for t in relevant):
        return "partial", "incomplete_response", []
    if any(t.get("outcome") == "failed" for t in relevant):
        return "partial", "thread_read_failed", []
    if deferred:
        return "partial", "threads_deferred_by_request_budget", []
    return ("success" if accepted else "no_results"), "", []


def _notes(cycle: dict[str, Any], version: str, candidates: int, accepted: int, rejected: int,
           gaps: list[str]) -> str:
    if cycle.get("stop"):
        return (f"NVIDIA GeForce forum default views: no comment read this cycle ({cycle['stop']}). "
                f"Nothing already stored was removed.")
    relevant = [t for t in cycle.get("threads", []) if version in (t.get("title_versions") or [])]
    read = sum(1 for t in relevant if t.get("outcome") == "read")
    unchanged = sum(1 for t in relevant if t.get("outcome") == "unchanged")
    hidden = any("older_comments_outside_window" in (t.get("coverage") or []) for t in relevant)
    text = (f"NVIDIA GeForce forum default views only (latest {src.COMMENT_PAGE_SIZE} top-level comments "
            f"per thread and the replies the forum embeds). {read} thread(s) naming {version} read, "
            f"{unchanged} unchanged since their last read; {candidates} comment(s) name {version}: "
            f"accepted {accepted}, excluded {rejected}.")
    if hidden:
        text += " Older comments in these threads are outside the visible window and were not read."
    if gaps:
        text += f" Possible missed comments since the last read: {', '.join(gaps)}."
    return text


# --- writeback (freshness only) -----------------------------------------------------------------------

def apply_consensus_writeback(product_id: str, update_version: str) -> bool:
    return apply_consensus_writebacks(product_id, [update_version]).get(update_version, False)


def apply_consensus_writebacks(product_id: str, update_versions: list[str]) -> dict[str, bool]:
    """Freshness for several patches from ONE dry run of the shared consensus authority (the ComfyUI
    shape). apply_collector_record_fields filters every proposal to COLLECTOR_WRITABLE_FIELDS: the
    count, summary and samples belong to reconciliation and the scoped promotion step."""
    from apply_consensus_to_records import (_index_generated_records,  # noqa: PLC0415
                                            apply_collector_record_fields, run_dry_run)

    wanted = [str(v) for v in update_versions if str(v or "")]
    out = {version: False for version in wanted}
    if not wanted:
        return out
    results = run_dry_run(evidence_path=base.EVIDENCE_PATH, product_id_filter=product_id,
                          is_candidate_mode=False, records_index=_index_generated_records(),
                          write_requested=True)
    for version in wanted:
        matches = [item for item in results if item.get("update_version") == version]
        if len(matches) != 1 or not matches[0].get("would_write"):
            continue
        record_rel = matches[0].get("matched_generated_record_path")
        if not record_rel:
            continue
        fields = dict(matches[0].get("proposed_fields_if_written") or {})
        applied = apply_collector_record_fields(ROOT / record_rel, fields) or {}
        out[version] = bool((applied.get("write_plan") or {}).get("fields"))
    return out


# --- the collector -------------------------------------------------------------------------------------

class NvidiaForumCollector(base.ProductCollector):
    """One driver family's evidence from the forum. Registered once per family; both share the cycle."""

    def __init__(self, product_id: str = identity.GAME_READY) -> None:
        if product_id not in PRODUCTS:
            raise ValueError(f"not an NVIDIA driver product: {product_id!r}")
        self.product_id = product_id

    def collect(self, context: base.CollectorContext) -> list[dict[str, Any]]:
        target = getattr(context, "target_versions", None)
        records = base.newest_first(base.generated_records(self.product_id, target))
        tracked = {r.update_version for r in base.generated_records(self.product_id)}
        everything = [r for pid in PRODUCTS for r in base.generated_records(pid)]
        versions = {r.update_version for r in everything if not target or r.update_version in target}
        cycle = run_cycle(context, versions, keep_versions={r.update_version for r in everything})
        if context.write and cycle.get("state") is not None and cycle.get("ran") and not cycle.get("saved"):
            src.save_state(cycle["state"])
            cycle["saved"] = True
        rb.emit("nvidia_forum_cycle", product_id=self.product_id, ran=bool(cycle.get("ran")),
                skipped=cycle.get("skipped") or "", stop=cycle.get("stop") or "",
                requests=int(cycle.get("requests") or 0),
                threads=sum(1 for t in cycle.get("threads", []) if t.get("outcome") == "read"))
        if cycle.get("skipped"):
            # Between cycles nothing is read and nothing is claimed: the last rows stand as written,
            # with their own timestamps (the keyed upsert retains what it is not given).
            return []
        captured_at = base.utc_now()
        results: list[dict[str, Any]] = []
        run_rows: list[dict[str, Any]] = []
        for record in records:
            if _budget_expired():
                rb.emit("collector_budget_stop", product_id=self.product_id, reason="collector_finalize")
                break
            version = str(record.update_version or "")
            accepted: list[dict[str, Any]] = []
            rejected: list[dict[str, Any]] = []
            for thread in cycle.get("threads", []):
                for item in thread.get("items") or []:
                    row = evaluate_comment(self.product_id, record, tracked, thread, item, captured_at)
                    if row is not None:
                        (accepted if row.get("counted") else rejected).append(row)
            status, blocked, gaps = _version_status(cycle, version, len(accepted))
            health = [base.method_health_row(
                product_id=self.product_id, update_version=version, method_id=METHOD_ID,
                source_type=SOURCE_TYPE, status=status, candidates_found=len(accepted) + len(rejected),
                accepted_reports=len(accepted), rejected_reports=len(rejected),
                blocked_reason=blocked, last_run="" if status == "disabled" else captured_at,
                notes=_notes(cycle, version, len(accepted) + len(rejected), len(accepted), len(rejected), gaps))]
            results.append({
                "product_id": self.product_id,
                "version": version,
                "mode": "write" if context.write else "dry-run",
                "candidates_reviewed": len(accepted) + len(rejected),
                "accepted_count": len(accepted),
                "rejected_count": len(rejected),
                "accepted_urls": [r["source_url"] for r in accepted],
                "rejection_reasons": dict(sorted(
                    {reason: sum(1 for r in rejected if r.get("exclusion_reason") == reason)
                     for reason in {str(r.get("exclusion_reason") or "") for r in rejected}}.items())),
                "method_health": health,
            })
            run_rows.extend(accepted + rejected)

        if context.write:
            persisted: list[dict[str, Any]] = []
            already_held: list[dict[str, Any]] = []
            if run_rows:
                base.append_evidence_rows(run_rows, out_added=persisted, out_already_held=already_held)
            base.finalize_method_health_delta(
                [row for result in results for row in result["method_health"]],
                [r for r in persisted if r.get("counted")],
                [r for r in already_held if r.get("counted")])
            new_accepted = sorted({str(r.get("update_version") or "") for r in persisted if r.get("counted")})
            updated = apply_consensus_writebacks(self.product_id, new_accepted)
            for result in results:
                version = str(result["version"])
                result["evidence_rows_added"] = sum(
                    1 for r in persisted if str(r.get("update_version") or "") == version)
                result["record_updated"] = bool(updated.get(version, False))
        return results
