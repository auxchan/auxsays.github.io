"""The evidence overview projection (G82-A, AUX-123): what a patch page may say about its reports and
about a newer release, computed at deploy from this tree and printed by
`_includes/patch-evidence-overview.html`, which decides nothing itself.

WHY IT EXISTS. OBS Studio 33.0.1 carried 47 counted reports, "Evidence strength: High" and the verdict
INSUFFICIENT DATA side by side. "High" was defined by report COUNT only (33 or more), so the page read
as if quantity were corroboration. G82 established that the 47 reports describe about 37 different
problems and that none of them has two known-independent reporters. The page now states the count as a
count, says what the reports do and do not establish, keeps every source link, and points to a newer
release where AUXSAYS tracks one. It is an evidence-and-hotfix improvement: it adds no verdict, no
grouping of reports and no corroboration of any problem.

WHAT A ROW HOLDS (keyed like the verdict projection: product_id|update_version|target_build):
  * reports       the page's counted population -- the SAME rows the verdict reads
                  (lib.report_counts.counted_evidence_rows, through verdict_projection.load_inputs).
  * count_line    "<n> accepted patch-specific reports." plus, on a page that prints no verdict
                  (INSUFFICIENT DATA), a clause. The universal clause (GPT clarification 2) is
                  UNIVERSAL_CLAUSE. A page may carry a stronger reviewed finding instead, only from
                  `_data/evidence_presentation.yml` `assessments`, and only while the page's counted
                  population still equals the one that was assessed (same size, same sha256 of the
                  sorted row ids): the moment one report is added or withdrawn the finding stops
                  showing and the universal clause returns. No recurring review is needed and none is
                  possible to forget.
  * sources_line  the counted rows by source family ("34 GitHub issues and 13 OBS forum threads").
                  Platform counts are deliberately absent (GPT: no new text classifier).
  * limitation    what the list below is: each report separately, not grouped by problem; or, on a
                  page whose verdict rests on reviewed reasons, how many of the reports those reasons
                  cite.
  * newer         a newer stable release named by the My Installed Versions rule (`installedState` in
                  assets/js/auxsays.js, UPDATE AVAILABLE), ported here and pinned to the shipped
                  JavaScript over the whole corpus by test_evidence_overview. Newer is never presented as
                  safer (owner order and GPT G85 ruling Q2, AUX-123 amendment A1): a caution comes first,
                  the vendor's own known-issue caution when the newer record declares one (G85's consumer
                  contract: `official_notes_known_issue: declared` from the release notes, or
                  `official_known_issues_present: true` from Windows Release Health), otherwise "Newer
                  is not necessarily safer. ...". Then the newer release's own verdict exactly as the
                  verdict projection prints it on its page -- the verdict word with its scope, or with the
                  volume-based precaution's label (verdict_projection.printed_qualifier) -- or that AUXSAYS has
                  not established one. It
                  never assigns a verdict and never says that its changes match a report on this page.
                  Windows 11 gets no note (NEWER_NOTE_EXCLUDED_PRODUCTS).

  * next_action   on every page whose printed verdict is WAIT (any reason), the way forward (G87, AUX-127),
                  chosen in this order and from stored facts only: the release is ARCHIVED ("This release
                  is archived." and "AUXSAYS has not established a better-supported alternative."); the
                  product gets no newer-release note (NEWER_NOTE_EXCLUDED_PRODUCTS: "AUXSAYS has not
                  established a better-supported alternative."); a NEWER RELEASE note is present (the note
                  above is the next action, unchanged, its vendor caution before its links); the record is
                  PROVEN NEWEST, i.e. the first stable entry of the product's record list with nothing
                  released at or after it ("AUXSAYS has no record of a newer release. If your current version
                  works, consider keeping it until one is."); otherwise NOT ESTABLISHED ("AUXSAYS has not
                  established a better-supported alternative."). Each of the three variants that says no
                  better-supported alternative is established (archived, excluded, not established) ends with
                  KEEP_LINE ("If your current version works, consider keeping it.") unless the page's verdict
                  box already gives that advice (keep_advice_printed: the volume-based precaution's "Next step"
                  does), so it is never said twice. A supported reviewed reason on the page that
                  names `fixed_in` adds "The reviewed problem that applies <its scope> was fixed in <product>
                  <fixed_in>." -- a fact in the reviewed scope, never a recommendation of that version (the
                  newer-release note may name a different, newer release with a vendor warning). None of these
                  strings goes into the newer-release note's own fields. A page that prints WAIT and has no
                  next action is a publication error in QA (qa_patch_records), so the exit never depends
                  silently on this git-ignored projection; so is one whose rendered way forward is not the
                  variant a recompute from the source facts gives, or whose newer-release note names another
                  release or date (next_action_mismatch).

VENDOR FIX LINES are a mechanism switched OFF for every source. Up to MAX_FIX_LINES attributed "Fixed
..." bullets may be shown from a newer release's official notes ONLY where that source's publication
permission is on record (PUBLICATION_PERMITTED_HOSTS). No source in the repository records one -- the
acquisition registry knows only `rights_status: unresolved`, and existing publication on AUXSAYS does
not establish permission -- so the set is empty and every page shows the official-notes link only. No
total ("N fixes") is ever printed: the parser cannot establish one reliably. Adding a host is an
owner's decision, never a code default.

LABELS. The per-report issue labels and the label-built "Current reports mention ..." sentence are
withheld, in the layout, for the products listed in `_data/evidence_presentation.yml`
`label_withheld_products` -- products where a binding human-read audit recorded counted labels that
contradict their reports. Every other product is unchanged. That list is read by Liquid directly (a
tracked, reviewed file), so it holds with or without this projection.

GENERATED AT DEPLOY, NEVER COMMITTED (git-ignored, like verdict_projection.yml). Absent, the page
renders no overview and no newer-release note: it fails closed. Present, it must equal `project` over
the same tree; `qa_patch_records` errors on any difference, on a failed build, and on a deploy that
built the verdict projection but not this one.

Reads YAML and the evidence store; no network, no collector run, no model.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

import yaml

from . import verdict_projection, verdict_reasons

PROJECTION_NAME = "evidence_overview_projection.yml"
REVIEWED_NAME = "evidence_presentation.yml"
SCHEMA_VERSION = 1
# Bump on ANY change to the wording, the family labels or the rule: QA compares a deploy's file with a
# recompute, and the version says which rule wrote it.
RULE_VERSION = "evidence-overview-v2"
HEADER = (
    "# GENERATED by auxsays/scripts/build_evidence_overview_projection.py -- do not edit by hand. Never committed.\n"
    "#\n"
    "# Per patch page: the counted report population stated as a count, its source families, what the list\n"
    "# below does and does not establish, and a newer release with its caution first (lib/evidence_overview).\n"
    "# _includes/patch-evidence-overview.html prints these rows and decides nothing itself.\n"
)

UNIVERSAL_CLAUSE = "No problem-specific installation recommendation has been established."
LIMITATION = "Each report is listed separately below; AUXSAYS has not grouped them by problem."
# The newer-release note (amendment A1). The verdict sentence follows the verdict projection: NO_VERDICT_YET
# when the newer page prints no verdict, VERDICT_PREFIX + the printed verdict otherwise.
NO_VERDICT_YET = "AUXSAYS has not established an installation verdict for this release."
VERDICT_PREFIX = "AUXSAYS verdict for this release: "
NOT_MATCHED = "AUXSAYS has not matched its changes to the reports on this page."
NEWER_NOT_SAFER = ("Newer is not necessarily safer. Check its official release notes, including any known "
                   "issues, before upgrading.")
# "<vendor>" + KNOWN_ISSUE_CAUTION, where <vendor> is the newer record's update_source_name.
KNOWN_ISSUE_CAUTION = (" has documented a known issue affecting this version. Review the official release notes "
                       "before upgrading.")
# Words the note's own strings never use: newer is not "available" as an upgrade, and AUXSAYS has not
# established that it "addresses", "fixes" or "resolves" anything (A1).
NEWER_FORBIDDEN_WORDS = ("available", "addresses", "fixes", "resolves")

# Public family names for the counted source types, (singular, plural). Two source types that name the
# same public family (GitHub issues on two trackers) are one family on the page. A source type missing
# here is shown as OTHER_FAMILY, never by its internal name, and QA warns so it gets a name.
FAMILY_LABELS: dict[str, tuple[str, str]] = {
    "adobe_community_bug_report": ("Adobe Community post", "Adobe Community posts"),
    "blackmagic_forum": ("Blackmagic Design forum post", "Blackmagic Design forum posts"),
    "creator_forum_report": ("creator forum post", "creator forum posts"),
    "github_issue": ("GitHub issue", "GitHub issues"),
    "github_officedev_issue": ("GitHub issue", "GitHub issues"),
    "microsoft_learn_qna": ("Microsoft Q&A question", "Microsoft Q&A questions"),
    "microsoft_tech_community": ("Microsoft Tech Community post", "Microsoft Tech Community posts"),
    "nvidia_forum_comment": ("NVIDIA forum comment", "NVIDIA forum comments"),
    "obs_forum_thread": ("OBS forum thread", "OBS forum threads"),
    "reddit_community_report": ("Reddit post", "Reddit posts"),
    "stack_exchange_question": ("Stack Exchange question", "Stack Exchange questions"),
}
OTHER_FAMILY = ("other public report", "other public reports")

# Vendor fix lines: the hosts whose publication permission is ON RECORD. Empty on purpose (see the
# module docstring). The mechanism below is complete and tested with this set forced non-empty.
PUBLICATION_PERMITTED_HOSTS: frozenset[str] = frozenset()
MAX_FIX_LINES = 5

# Products that get no newer-release note. Windows 11: auxsays/_data/patch_lifecycle.yml records that the
# general Windows "newer update available" links are not built and wait for the Microsoft KB source
# assessment and exact KB/build applicability checks, and this note must not contradict that recorded hold
# (an owner question, not done). Its overview is unchanged.
NEWER_NOTE_EXCLUDED_PRODUCTS: frozenset[str] = frozenset({"microsoft-windows-11"})

# The way forward on a WAIT page (G87, AUX-127). Kinds, in selection order, and the lines each one writes.
NEXT_ARCHIVED = "archived"
NEXT_EXCLUDED = "excluded_product"
NEXT_NEWER = "newer_release"
NEXT_NEWEST = "newest"
NEXT_NOT_ESTABLISHED = "not_established"
ARCHIVED_LINE = "This release is archived."
NO_BETTER_ALTERNATIVE = "AUXSAYS has not established a better-supported alternative."
NEWEST_LINE = ("AUXSAYS has no record of a newer release. If your current version works, consider keeping it until "
               "one is.")
NEXT_LINES: dict[str, tuple[str, ...]] = {
    NEXT_ARCHIVED: (ARCHIVED_LINE, NO_BETTER_ALTERNATIVE),
    NEXT_EXCLUDED: (NO_BETTER_ALTERNATIVE,),
    NEXT_NEWER: (),
    NEXT_NEWEST: (NEWEST_LINE,),
    NEXT_NOT_ESTABLISHED: (NO_BETTER_ALTERNATIVE,),
}
# GPT's execution review (G87 amendment A3, item 3): where no better-supported alternative is established, say so
# and advise keeping a working installation -- unless the page's verdict box already gives that advice, which the
# volume-based precaution's "Next step" does (patch_decision.VOLUME_BODY), so it is never said twice.
KEEP_LINE = "If your current version works, consider keeping it."
KEEP_ADVICE = "If your current version works, consider keeping it"
KEEP_KINDS = frozenset({NEXT_ARCHIVED, NEXT_EXCLUDED, NEXT_NOT_ESTABLISHED})
# The newer-release note's fields that name the release and what the reader is told about it: a rendered note
# that differs from the recompute in any of them points the reader at another release, date or verdict.
NEWER_IDENTITY_KEYS = ("identity", "published_at", "url", "notes_url", "known_issue", "caution", "verdict_line")
FIXED_LINE = "The reviewed problem that applies {scope} was fixed in {product} {fixed_in}."
_FIXED_RE = re.compile(r"^The reviewed problem that applies (?:if|when|for) .+ was fixed in .+\.$")

# Phrases the AUXSAYS-authored strings must never carry: an acceptance rule or a threshold stated to the
# reader (the page describes evidence; it does not explain how much would be enough).
FORBIDDEN_WORDING = ("threshold", "at least", "minimum", "two or more", "enough", "more reports",
                     "independently reported", "consensus")
# A stored report text that shares this many consecutive words with an AUXSAYS string is a leak.
SHINGLE_WORDS = 6

_REVIEWED_TOP = {"schema_version", "label_withheld_products", "assessments"}
_LABEL_KEYS = {"product_id", "measured", "basis", "reopen"}
_ASSESS_REQUIRED = {"id", "product_id", "update_version", "finding", "basis", "assessed_reports",
                    "assessed_population_sha256", "reviewed_at"}
_ASSESS_KEYS = _ASSESS_REQUIRED | {"target_build"}
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_BETA_WORDS = ("beta", "preview", "insider")
_BULLET_RE = re.compile(r"^[*-]\s+(.*\S)\s*$")
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
# A trailing contributor credit: "[Name] (#123)", "[Name] ([#123](url))" after link stripping, or "(#123)".
_CREDIT_RE = re.compile(r"\s*(\[[^\]]*\]\s*)?\((#\d+[^)]*)\)\s*$")


class ProjectionError(ValueError):
    """A projection file that is present but unreadable or malformed."""


class ReviewedFileError(ValueError):
    """`_data/evidence_presentation.yml` is unreadable."""


# --------------------------------------------------------------------------------- reviewed file

def load_reviewed(path: Path) -> dict[str, Any]:
    """The reviewed presentation file, parsed (not validated). Absent means nothing is reviewed."""
    path = Path(path)
    if not path.is_file():
        return {"schema_version": SCHEMA_VERSION, "label_withheld_products": [], "assessments": []}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - any parse failure is unreadable
        raise ReviewedFileError(f"{path.name}: unreadable YAML: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReviewedFileError(f"{path.name}: expected a mapping")
    return payload


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def reviewed_errors(doc: Mapping[str, Any]) -> list[str]:
    """Structural problems in the reviewed file. Any problem makes the whole file count for nothing
    (no label is withheld by it and no assessment applies), and QA reports it as an error."""
    problems: list[str] = []
    if not isinstance(doc, Mapping):
        return ["the file is not a mapping"]
    extra = set(doc) - _REVIEWED_TOP
    if extra:
        problems.append(f"unknown top-level keys {sorted(extra)}")
    if doc.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"schema_version must be {SCHEMA_VERSION}")
    labels = doc.get("label_withheld_products")
    if not isinstance(labels, list):
        problems.append("label_withheld_products must be a list")
        labels = []
    seen: set[str] = set()
    for i, entry in enumerate(labels):
        where = f"label_withheld_products[{i}]"
        if not isinstance(entry, Mapping):
            problems.append(f"{where} is not a mapping")
            continue
        if set(entry) != _LABEL_KEYS:
            problems.append(f"{where} must carry exactly {sorted(_LABEL_KEYS)}")
        pid = _text(entry.get("product_id"))
        if not pid or pid in seen:
            problems.append(f"{where}: product_id missing or listed twice")
        seen.add(pid)
        for key in ("measured", "basis", "reopen"):
            if not _text(entry.get(key)):
                problems.append(f"{where}: {key} is empty")
    assessments = doc.get("assessments")
    if not isinstance(assessments, list):
        problems.append("assessments must be a list")
        assessments = []
    ids: set[str] = set()
    pages: set[tuple[str, str, str]] = set()
    for i, entry in enumerate(assessments):
        where = f"assessments[{i}]"
        if not isinstance(entry, Mapping):
            problems.append(f"{where} is not a mapping")
            continue
        missing = _ASSESS_REQUIRED - set(entry)
        extra = set(entry) - _ASSESS_KEYS
        if missing or extra:
            problems.append(f"{where}: missing {sorted(missing)}, unknown {sorted(extra)}")
            continue
        aid = _text(entry.get("id"))
        if not aid or aid in ids:
            problems.append(f"{where}: id missing or repeated")
        ids.add(aid)
        page = assessment_identity(entry)
        if not page[0] or not page[1] or page in pages:
            problems.append(f"{where}: page identity missing or assessed twice")
        pages.add(page)
        finding = _text(entry.get("finding"))
        if not finding or not finding.endswith(".") or any(ch.isdigit() for ch in finding):
            problems.append(f"{where}: finding must be one sentence ending in '.', with no number in it")
        if any(phrase in finding.lower() for phrase in FORBIDDEN_WORDING):
            problems.append(f"{where}: finding states an acceptance rule or a threshold")
        reports = entry.get("assessed_reports")
        if not isinstance(reports, int) or isinstance(reports, bool) or reports < 1:
            problems.append(f"{where}: assessed_reports must be a positive integer")
        if not _SHA_RE.match(_text(entry.get("assessed_population_sha256"))):
            problems.append(f"{where}: assessed_population_sha256 must be 64 lower-case hex characters")
        if not _DATE_RE.match(_text(entry.get("reviewed_at"))):
            problems.append(f"{where}: reviewed_at must be YYYY-MM-DD")
        if not _text(entry.get("basis")):
            problems.append(f"{where}: basis is empty")
    return problems


def assessment_identity(entry: Mapping[str, Any]) -> tuple[str, str, str]:
    return (_text(entry.get("product_id")), _text(entry.get("update_version")), _text(entry.get("target_build")))


def label_withheld_products(doc: Mapping[str, Any]) -> list[str]:
    """The product ids whose labels the layout withholds (empty when the file has any problem)."""
    if reviewed_errors(doc):
        return []
    return [_text(e.get("product_id")) for e in doc.get("label_withheld_products") or []]


# --------------------------------------------------------------------------------- the count, the families

def population_digest(rows: Iterable[Mapping[str, Any]]) -> str:
    """sha256 of the page's counted row ids, sorted and joined by newlines: the identity of an
    assessed population. Any added or withdrawn report changes it."""
    ids = sorted(_text(r.get("id")) for r in rows)
    return hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()


def count_sentence(n: int) -> str:
    return f"{n} accepted patch-specific report{'' if n == 1 else 's'}."


def families(rows: Iterable[Mapping[str, Any]]) -> list[tuple[str, str, int]]:
    """(singular, plural, n) per public family, most reports first, then by name."""
    counts: Counter[tuple[str, str]] = Counter()
    for row in rows:
        counts[FAMILY_LABELS.get(_text(row.get("source_type")), OTHER_FAMILY)] += 1
    return [(s, p, n) for (s, p), n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0][1]))]


def unlabelled_source_types(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    return sorted({_text(r.get("source_type")) for r in rows} - set(FAMILY_LABELS))


def sources_sentence(fams: list[tuple[str, str, int]]) -> str:
    parts = [f"{n} {singular if n == 1 else plural}" for singular, plural, n in fams]
    if not parts:
        return ""
    joined = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    return f"Sources: {joined}."


def cited_counted(reason_ids: Iterable[str], reasons_by_id: Mapping[str, Mapping[str, Any]],
                  rows: Iterable[Mapping[str, Any]]) -> int:
    """How many of the page's counted rows its supported reasons cite."""
    counted = {_text(r.get("id")) for r in rows}
    cited: set[str] = set()
    for rid in reason_ids:
        for ev in (reasons_by_id.get(rid) or {}).get("evidence") or []:
            if isinstance(ev, Mapping) and _text(ev.get("id")) in counted:
                cited.add(_text(ev.get("id")))
    return len(cited)


def limitation_sentence(n: int, cited: int, reasoned: bool, reasons: int = 1) -> str:
    """What the report list is. `reasons`: how many supported reasons the verdict line states (a page
    can print a WAIT and an "Also TEST FIRST" together)."""
    if not reasoned:
        return LIMITATION
    subject = "The reasons above cite" if reasons > 1 else "The reason above cites"
    if cited >= n:
        return f"{subject} this report." if n == 1 else f"{subject} every one of them."
    return (f"{subject} {cited} of them; the others are listed separately below, and AUXSAYS has not grouped "
            "them by problem.")


def valid_assessment(record: Mapping[str, Any], rows: list[Mapping[str, Any]],
                     assessments: Iterable[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """The reviewed assessment for this page, only while its counted population is the assessed one."""
    ident = verdict_reasons.record_identity(record)
    for entry in assessments:
        if assessment_identity(entry) != ident:
            continue
        if entry.get("assessed_reports") == len(rows) \
                and _text(entry.get("assessed_population_sha256")) == population_digest(rows):
            return entry
        return None
    return None


# --------------------------------------------------------------------------------- the newer release
# A PORT of installedState (assets/js/auxsays.js), the My Installed Versions rule, for the one state
# that is a definite claim: UPDATE AVAILABLE. The payload it reads is My Patch Stack's per-product
# record list (updates/my-stack.md): every record with a release time that is not archived, newest
# first, as [version, build, date, url, beta, ..., notes platform, verdict scope, release track]. My
# Patch Stack caps that list at 24 per product for page weight; a patch page reads the whole list,
# which is the same rule over a longer window. test_evidence_overview runs the shipped JavaScript over
# every record of the corpus and requires the same answer from this port, so the two cannot part.

def _date(record: Mapping[str, Any]) -> str:
    """`update_published_at | date: "%Y-%m-%d"`: Liquid parses the stored timestamp with its own offset
    and prints that wall-clock date, which is the date as written."""
    value = record.get("update_published_at")
    if hasattr(value, "isoformat"):
        value = value.isoformat()
    text = _text(value)
    return text[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", text) else ""


def _beta(record: Mapping[str, Any]) -> bool:
    """The payload's beta flag: a version that starts with a digit and names a beta, preview or insider
    channel, or any release_channel_label at all (Liquid truthiness: only nil and false are falsy)."""
    version = str(record.get("update_version") if record.get("update_version") is not None else "")
    named = version[:1] in "0123456789" and version[:1] != "" and any(w in version.lower() for w in _BETA_WORDS)
    channel = record.get("release_channel_label")
    return named or (channel is not None and channel is not False)


def _ver(record: Mapping[str, Any]) -> str:
    v = record.get("update_version")
    return "" if v is None else str(v)


def _build(record: Mapping[str, Any]) -> str:
    b = record.get("target_build")
    return "" if b is None else str(b)


def _platform(record: Mapping[str, Any]) -> str:
    return _text(record.get("official_notes_platform"))


def _version_order(a: str, b: str) -> int | None:
    def parse(v: str) -> list[int] | None:
        t = str(v or "").strip()
        return [int(x) for x in t.split(".")] if re.fullmatch(r"\d+(\.\d+)*", t) else None
    x, y = parse(a), parse(b)
    if x is None or y is None:
        return None
    for i in range(max(len(x), len(y))):
        d = (x[i] if i < len(x) else 0) - (y[i] if i < len(y) else 0)
        if d:
            return 1 if d > 0 else -1
    return 0


def product_payload(product_records: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """My Patch Stack's record list for one product: dated, not archived, newest first. Liquid sorts the
    raw release-time strings; Python's sort is stable where Liquid's is not, which only reorders records
    with the very same release time -- and the rule never reads an order between same-day records."""
    recs = [r for r in product_records
            if r.get("update_published_at") and _text(r.get("update_status")) != "archived"]
    return sorted(recs, key=lambda r: _text(r.get("update_published_at")), reverse=True)


def _platform_scoped(recs: list[Mapping[str, Any]], index: int, my_date: str) -> Mapping[str, Any] | None:
    mine = recs[index]
    my_platform = _platform(mine)
    if not my_platform:
        return None
    others = [r for i, r in enumerate(recs) if i != index]

    def applies(r: Mapping[str, Any]) -> bool:
        return _platform(r) == my_platform or (my_platform != "windows_macos" and _platform(r) == "windows_macos")
    applicable = [r for r in others if applies(r)]
    if any(_date(r) < my_date and _version_order(_ver(r), _ver(mine)) != -1 for r in applicable):
        return None
    later = [r for r in applicable if _date(r) > my_date]
    if not later or any(_version_order(_ver(r), _ver(mine)) != 1 for r in later):
        return None
    stable = [r for r in later if not _beta(r)]
    if _beta(mine) or not stable:
        return None
    return stable[0]


# PARALLEL RELEASE TRACKS (G93). Adobe services Acrobat and Acrobat Reader on two tracks at the same
# time, Continuous (26.003.22110) and Classic (20.005.30838), and every Acrobat record stores which one
# in `target_track`. A Continuous release is not an update to a Classic installation, so for these
# products the newer release must carry the SAME non-empty track as the reader's release. A Classic
# release with no newer Classic release gets no target, never a Continuous one, and a track missing on
# either side names nothing (fail closed). Only these products: another product's behaviour does not
# change, whatever its records carry. installedState (assets/js/auxsays.js) holds the same list and
# reads the same field from the payload's rec[13]; test_acrobat_track_scope pins the two lists equal and
# runs one fixture set through both implementations.
TRACK_SCOPED_PRODUCTS: frozenset[str] = frozenset({"adobe-acrobat-pro", "adobe-acrobat-reader"})


def _track(record: Mapping[str, Any]) -> str:
    return _text(record.get("target_track"))


def update_available(record: Mapping[str, Any], recs: list[Mapping[str, Any]], *,
                     split: bool) -> Mapping[str, Any] | None:
    """installedState's UPDATE AVAILABLE target for a reader on `record`, or None for every other state."""
    if not recs:
        return None
    index = next((i for i, r in enumerate(recs)
                  if _ver(r) == _ver(record) and _build(r) == _build(record)), -1)
    if index < 0:
        return None
    my_date = _date(record) or _date(recs[index])
    if split:
        return _platform_scoped(recs, index, my_date)
    build_aware = any(_build(r) != "" for r in recs)

    def on_my_line(r: Mapping[str, Any]) -> bool:
        return (not build_aware) or _ver(r) == _ver(record)
    tied = [] if not my_date else [r for i, r in enumerate(recs)
                                   if i != index and _date(r) == my_date and on_my_line(r)]
    newer = [r for r in recs[:index] if not any(r is t for t in tied)]
    if not newer or _beta(recs[index]):
        return None
    newer_stable = [r for r in newer if not _beta(r)]
    if not newer_stable:
        return None
    same_train = [r for r in newer_stable if _ver(r) == _ver(record)]
    if build_aware and not same_train:
        return None
    applicable = same_train if build_aware else newer_stable
    if _text(record.get("product_id")) in TRACK_SCOPED_PRODUCTS:
        my_track = _track(recs[index])
        applicable = [r for r in applicable if my_track and _track(r) == my_track]
    return applicable[0] if applicable else None


def version_shaped(record: Mapping[str, Any]) -> bool:
    """A version string, not a changelog headline. For Figma and GitHub `update_version` is the title of
    a changelog entry; a later entry describes a different change, not a newer release of the same
    thing, so no newer-release note is offered there. The test is the one the payload itself uses to
    decide whether a version string can carry channel meaning: it starts with a digit."""
    return _ver(record)[:1] in "0123456789" and _ver(record)[:1] != ""


def identity_text(record: Mapping[str, Any]) -> str:
    name = _text(record.get("update_product")) or _text(record.get("product_id"))
    build = _text(record.get("target_build"))
    return f"{name} {_text(record.get('update_version'))}{f' (Build {build})' if build else ''}".strip()


def notes_url(record: Mapping[str, Any]) -> str:
    return _text(record.get("official_patch_notes_source_url")) or _text(record.get("update_source_url"))


def publication_permitted(url: str) -> bool:
    host = (urlparse(_text(url)).hostname or "").lower()
    return bool(host) and host in PUBLICATION_PERMITTED_HOSTS


def fix_lines(body: str, limit: int = MAX_FIX_LINES) -> list[str]:
    """Up to `limit` top-level "Fixed ..." bullets from official release-notes markdown, in document
    order, with markdown links reduced to their text and a trailing contributor credit removed. Used
    ONLY for a source whose publication permission is on record (publication_permitted)."""
    out: list[str] = []
    for raw in str(body or "").replace("\r\n", "\n").split("\n"):
        m = _BULLET_RE.match(raw)
        if not m:
            continue
        text = _MD_LINK_RE.sub(lambda mm: mm.group(1), m.group(1))
        text = _CREDIT_RE.sub("", text).strip()
        text = re.sub(r"\s+", " ", text)
        if text.startswith("Fixed ") and text not in out:
            out.append(text if text.endswith(".") else text + ".")
        if len(out) >= limit:
            break
    return out


def vendor_known_issue(record: Mapping[str, Any]) -> bool:
    """Whether the record's vendor has documented a known issue for it, read exactly as the writers store it
    (G85 consumer contract, AUX-125): `official_notes_known_issue: declared` (official release notes) or
    `official_known_issues_present: true` (Windows Release Health). An absent field never means "no known
    issue"; it only means none is declared, and the note then says newer is not necessarily safer."""
    return (_text(record.get("official_notes_known_issue")) == "declared"
            or record.get("official_known_issues_present") is True)


def caution_line(target: Mapping[str, Any]) -> str:
    if vendor_known_issue(target):
        return f"{_text(target.get('update_source_name')) or 'The vendor'}{KNOWN_ISSUE_CAUTION}"
    return NEWER_NOT_SAFER


def newer_row(record: Mapping[str, Any], target: Mapping[str, Any], verdict_rows: Mapping[str, Any],
              reports_here: int) -> dict[str, Any]:
    # The newer page's verdict exactly as its own gate prints it: the verdict word and its qualifier
    # (printed_qualifier: the scope, or the volume-based precaution's label), never the bare scope -- a
    # volume WAIT has none, and "WAIT." alone would read as a confirmed, universal WAIT (G87 review 1).
    printed = verdict_projection.printed_row(target, verdict_rows)
    if printed is None:
        verdict_line = NO_VERDICT_YET
    else:
        verdict_line = (f"{VERDICT_PREFIX}"
                        f"{verdict_projection.phrase(_text(printed.get('verdict')), verdict_projection.printed_qualifier(printed))}.")
    url = notes_url(target)
    lines = fix_lines(_text(target.get("official_patch_notes_body"))) if publication_permitted(url) else []
    return {
        "identity": identity_text(target),
        "url": _text(target.get("permalink") or target.get("url")),
        "published_at": _text(target.get("update_published_at")),
        "notes_url": url,
        "known_issue": vendor_known_issue(target),
        "caution": caution_line(target),
        "verdict_line": verdict_line,
        "match_note": NOT_MATCHED if reports_here > 0 else "",
        "fix_lines": lines,
        "fix_source": (f"{_text(target.get('update_source_name')) or 'the vendor'}'s release notes"
                       if lines else ""),
    }


# --------------------------------------------------------------------------------- the way forward (G87)

def proven_newest(record: Mapping[str, Any], recs: list[Mapping[str, Any]]) -> bool:
    """POSITIVE proof that no newer release is on record: the record is a dated, non-archived, stable,
    version-shaped entry of its product's record list (`product_payload`), and no other stable entry was
    released at or after it. A tie on the release time is NOT proof (array position is not chronology), and
    "update_available returned None" is not proof either."""
    if not version_shaped(record) or _beta(record):
        return False
    mine = [r for r in recs if _ver(r) == _ver(record) and _build(r) == _build(record)]
    if len(mine) != 1:
        return False
    stamp = _text(mine[0].get("update_published_at"))
    return bool(stamp) and not any(_text(r.get("update_published_at")) >= stamp
                                   for r in recs if r is not mine[0] and not _beta(r))


def fixed_lines(record: Mapping[str, Any], printed: Mapping[str, Any],
                reasons_by_id: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """One line per supported reviewed reason on the page that names fixed_in, in its reviewed scope."""
    out: list[str] = []
    product = _text(record.get("update_product")) or _text(record.get("product_id"))
    for rid in printed.get("reasons") or []:
        entry = reasons_by_id.get(_text(rid)) or {}
        fixed, scope = _text(entry.get("fixed_in")), _text(entry.get("scope"))
        if fixed and scope:
            line = FIXED_LINE.format(scope=scope, product=product, fixed_in=fixed)
            if line not in out:
                out.append(line)
    return out


def keep_advice_printed(printed: Mapping[str, Any] | None) -> bool:
    """Does the page's verdict box already advise keeping a working installation? Read from the line the gate
    prints (the row's body), so a page that says it is never told it twice."""
    return isinstance(printed, Mapping) and KEEP_ADVICE in _text(printed.get("body"))


def next_action(record: Mapping[str, Any], row: Mapping[str, Any], recs: list[Mapping[str, Any]],
                printed: Mapping[str, Any], reasons_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """The way forward for a page that prints WAIT: archived -> excluded product -> a newer-release note ->
    proven newest -> not established, plus any reviewed fixed_in line (module docstring). A variant that says
    no better-supported alternative is established ends with KEEP_LINE unless the verdict box already says it."""
    pid = _text(record.get("product_id"))
    if _text(record.get("update_status")) == "archived":
        kind = NEXT_ARCHIVED
    elif pid in NEWER_NOTE_EXCLUDED_PRODUCTS:
        kind = NEXT_EXCLUDED
    elif newer_printable(row.get("newer")):
        kind = NEXT_NEWER
    elif proven_newest(record, recs):
        kind = NEXT_NEWEST
    else:
        kind = NEXT_NOT_ESTABLISHED
    lines = list(NEXT_LINES[kind])
    if kind in KEEP_KINDS and not keep_advice_printed(printed):
        lines.append(KEEP_LINE)
    return {"kind": kind, "lines": lines, "fixed": fixed_lines(record, printed, reasons_by_id)}


def newer_printable(newer: Any) -> bool:
    """Whether _includes/patch-evidence-overview.html prints this newer-release note (its own condition)."""
    if not isinstance(newer, Mapping):
        return False
    return all(_text(newer.get(k)) for k in ("url", "identity", "verdict_line", "caution"))


def has_next_action(row: Mapping[str, Any] | None) -> bool:
    """Whether the page prints a next action from this overview row: way-forward lines, or (for a newer
    release) the newer-release note itself. A fixed_in line alone is not a next action."""
    nxt = row.get("next_action") if isinstance(row, Mapping) else None
    if not isinstance(nxt, Mapping):
        return False
    if nxt.get("kind") == NEXT_NEWER:
        return newer_printable(row.get("newer"))
    return nxt.get("kind") in NEXT_LINES and any(_text(s) for s in nxt.get("lines") or [])


def _variant(row: Mapping[str, Any] | None) -> tuple[Any, list[str], list[str]]:
    nxt = row.get("next_action") if isinstance(row, Mapping) else None
    nxt = nxt if isinstance(nxt, Mapping) else {}
    return (nxt.get("kind"), [_text(s) for s in nxt.get("lines") or []], [_text(s) for s in nxt.get("fixed") or []])


def _release(row: Mapping[str, Any] | None) -> dict[str, Any]:
    newer = row.get("newer") if isinstance(row, Mapping) else None
    newer = newer if isinstance(newer, Mapping) else {}
    return {k: (newer.get(k) if k == "known_issue" else _text(newer.get(k))) for k in NEWER_IDENTITY_KEYS}


def next_action_mismatch(rendered: Mapping[str, Any] | None, expected: Mapping[str, Any] | None) -> list[str]:
    """Why the way forward a page RENDERS (its row in the deploy's overview projection) is not the one a recompute
    from the source facts gives (`expected`: the row `project` writes over the same tree, from the archived flag,
    NEWER_NOTE_EXCLUDED_PRODUCTS, the newer-release note, the first-stable proof and the reviewed fixed_in): another
    variant -- its kind, its lines or its fixed_in lines -- or, where either side's way forward is a newer
    release, a note naming another release, date, link, caution or verdict. [] when they agree."""
    problems: list[str] = []
    got_kind, got_lines, got_fixed = _variant(rendered)
    want_kind, want_lines, want_fixed = _variant(expected)
    if (got_kind, got_lines, got_fixed) != (want_kind, want_lines, want_fixed):
        problems.append(f"renders the {got_kind or 'missing'} way forward {got_lines + got_fixed}, but the source "
                        f"facts give {want_kind or 'none'} {want_lines + want_fixed}")
    if NEXT_NEWER in (got_kind, want_kind):
        got, want = _release(rendered), _release(expected)
        differs = [k for k in NEWER_IDENTITY_KEYS if got[k] != want[k]]
        if differs:
            problems.append(f"its newer-release note names {got['identity'] or 'nothing'} "
                            f"({got['published_at'] or 'no date'}), but the source facts give "
                            f"{want['identity'] or 'nothing'} ({want['published_at'] or 'no date'}); "
                            f"it differs in {differs}")
    return problems


_RECOMMENDING_RE = re.compile(r"\b(?:upgrade|update to|install|recommend|safer|available)\b", re.I)


def next_action_problems(nxt: Mapping[str, Any]) -> list[str]:
    """A next action must be one this module writes: a known kind, exactly that kind's lines, and fixed lines of
    the one shape (a fact in the reviewed scope, never an upgrade instruction)."""
    problems: list[str] = []
    kind = nxt.get("kind")
    if kind not in NEXT_LINES:
        return [f"the next action's kind is not one this module writes: {kind!r}"]
    allowed = [list(NEXT_LINES[kind])] + ([list(NEXT_LINES[kind]) + [KEEP_LINE]] if kind in KEEP_KINDS else [])
    if list(nxt.get("lines") or []) not in allowed:
        problems.append(f"the next action's lines are not the {kind} lines this module writes")
    for line in nxt.get("fixed") or []:
        if not _FIXED_RE.match(_text(line)):
            problems.append(f"a fixed_in line is not the shape this module writes: {_text(line)[:80]!r}")
        if _RECOMMENDING_RE.search(_text(line)):
            problems.append(f"a fixed_in line reads as a recommendation: {_text(line)[:80]!r}")
    return problems


# --------------------------------------------------------------------------------- the projection

def project(records: Iterable[Mapping[str, Any]],
            counted_by_identity: Mapping[tuple[str, str, str], list[Mapping[str, Any]]],
            verdict_rows: Mapping[str, Any], reasons: Iterable[Mapping[str, Any]],
            reviewed: Mapping[str, Any], split_products: Iterable[str] = ()) -> dict[str, Any]:
    """The projection: one row per page that has counted reports or a newer release to point to.

    `verdict_rows` is the verdict projection's `pages` for the same tree (what each page's verdict gate
    prints); `reasons` the reviewed reason entries (to count the rows a supported reason cites);
    `reviewed` the parsed `_data/evidence_presentation.yml` (a file with any problem contributes no
    assessment); `split_products` the products whose vendor publishes release notes per platform."""
    records = [r for r in records if isinstance(r, Mapping)]
    reasons_by_id = {_text(e.get("id")): e for e in reasons or () if isinstance(e, Mapping)}
    assessments = [] if reviewed_errors(reviewed) else list(reviewed.get("assessments") or [])
    split = set(split_products or ())
    payloads: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for rec in records:
        payloads[_text(rec.get("product_id"))].append(rec)
    payloads = {pid: product_payload(recs) for pid, recs in payloads.items()}

    pages: dict[str, dict[str, Any]] = {}
    for rec in records:
        rows = list(counted_by_identity.get(verdict_reasons.record_identity(rec), []) or [])
        n = len(rows)
        row: dict[str, Any] = {"url": _text(rec.get("permalink") or rec.get("url"))}
        printed = verdict_projection.printed_row(rec, verdict_rows)
        if n > 0:
            reason_ids = [str(x) for x in (printed or {}).get("reasons") or []]
            reasoned = bool(reason_ids)
            # The clause, or a reviewed finding in its place, belongs only to a page that prints NO verdict
            # (INSUFFICIENT DATA). An official AVOID or SECURITY UPDATE is itself an installation
            # recommendation, so "No problem-specific installation recommendation has been established."
            # beside it would contradict the verdict box. ONE exception (G87, A2 item 7): under a
            # volume-based WAIT a still-valid reviewed finding about the reports keeps its place -- the WAIT
            # rests on their volume and the finding says what they do not show; the universal clause never
            # returns beside a printed verdict.
            verdict_printed = printed is not None
            volume = printed is not None and verdict_projection.is_volume_row(printed)
            assessment = valid_assessment(rec, rows, assessments) if (not verdict_printed or volume) else None
            if verdict_printed:
                clause = _text(assessment.get("finding")) if assessment else ""
            else:
                clause = _text(assessment.get("finding")) if assessment else UNIVERSAL_CLAUSE
            row.update({
                "reports": n,
                "count_line": f"{count_sentence(n)} {clause}".strip(),
                "sources_line": sources_sentence(families(rows)),
                "limitation": limitation_sentence(n, cited_counted(reason_ids, reasons_by_id, rows), reasoned,
                                                  len(reason_ids)),
                "assessment": _text(assessment.get("id")) if assessment else "",
            })
        pid = _text(rec.get("product_id"))
        if version_shaped(rec) and pid not in NEWER_NOTE_EXCLUDED_PRODUCTS:
            target = update_available(rec, payloads.get(pid, []), split=pid in split)
            if target is not None and version_shaped(target) and _text(target.get("permalink") or target.get("url")):
                row["newer"] = newer_row(rec, target, verdict_rows, n)
        if printed is not None and _text(printed.get("verdict")) == "WAIT":
            row["next_action"] = next_action(rec, row, payloads.get(pid, []), printed, reasons_by_id)
        if len(row) > 1:
            pages[verdict_projection.page_key(rec)] = row
    return {"schema_version": SCHEMA_VERSION, "rule_version": RULE_VERSION, "pages": dict(sorted(pages.items()))}


def split_products_from(aux_root: Path) -> list[str]:
    """Products whose vendor publishes release notes per platform (patch_products.yml), as My Patch
    Stack reads them."""
    path = Path(aux_root) / "_data" / "patch_products.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else []
    items = data if isinstance(data, list) else (data or {}).get("products") or []
    return sorted(_text(p.get("id") or p.get("product_id")) for p in items
                  if isinstance(p, Mapping) and p.get("official_notes_by_platform"))


def build(aux_root: Path) -> tuple[dict[str, Any], list[str]]:
    """(projection, problems) for a site tree. Raises on an unreadable evidence store or reviewed file
    (the caller decides what that means)."""
    aux_root = Path(aux_root)
    records, groups = verdict_projection.load_inputs(aux_root)
    reasons, lifecycle, problems = verdict_projection.load_fact_files(aux_root)
    verdict, _unsupported = verdict_projection.project(records, groups, reasons, lifecycle)
    reviewed = load_reviewed(aux_root / "_data" / REVIEWED_NAME)
    problems = list(problems) + [f"{REVIEWED_NAME}: {p}" for p in reviewed_errors(reviewed)]
    projection = project(records, groups, verdict["pages"], reasons, reviewed, split_products_from(aux_root))
    return projection, problems


def render(projection: Mapping[str, Any]) -> str:
    return HEADER + yaml.safe_dump(dict(projection), sort_keys=False, allow_unicode=True, width=100)


def load(path: Path) -> dict[str, Any] | None:
    """The projection a deploy built, or None when there is none. Present but malformed raises."""
    path = Path(path)
    if not path.is_file():
        return None
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - any parse failure is malformed, never "absent"
        raise ProjectionError(f"{path.name}: unreadable YAML: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION \
            or not isinstance(payload.get("pages"), dict):
        raise ProjectionError(f"{path.name}: expected schema_version {SCHEMA_VERSION} and a 'pages' mapping")
    return payload


# --------------------------------------------------------------------------------- public-text guard

def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text or "").lower())


def _shingles(text: str, n: int = SHINGLE_WORDS) -> set[tuple[str, ...]]:
    w = _words(text)
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def row_strings(row: Mapping[str, Any]) -> list[str]:
    """The strings this module composes for a row. Not in it: the newer release's identity (its product,
    version and build), the verdict line (the newer page's own verdict and its reviewed scope, already
    public on that page, checked by shape below) and vendor fix lines (checked by permission below). The
    caution is in it; its vendor name is the newer record's own update_source_name."""
    out = [_text(row.get(k)) for k in ("count_line", "sources_line", "limitation")]
    newer = row.get("newer") if isinstance(row.get("newer"), Mapping) else {}
    out += [_text(newer.get(k)) for k in ("caution", "match_note", "fix_source")]
    # The way-forward lines this module writes (G87). Not the fixed_in lines: they restate a reviewed
    # reason's own public scope and version, checked by shape below, as the verdict line is.
    nxt = row.get("next_action") if isinstance(row.get("next_action"), Mapping) else {}
    out += [_text(s) for s in nxt.get("lines") or []]
    return [s for s in out if s]


def caution_problems(newer: Mapping[str, Any]) -> list[str]:
    """A newer-release note must carry exactly one of the two cautions, the one its known_issue flag names,
    and none of its own strings may say "available", "addresses", "fixes" or "resolves" (A1)."""
    problems: list[str] = []
    caution = _text(newer.get("caution"))
    declared = newer.get("known_issue") is True
    if declared and not (caution.endswith(KNOWN_ISSUE_CAUTION) and len(caution) > len(KNOWN_ISSUE_CAUTION)):
        problems.append(f"the newer release declares a known issue but its caution is not the vendor's: {caution[:80]!r}")
    if not declared and caution != NEWER_NOT_SAFER:
        problems.append(f"the newer release's caution is not one this module writes: {caution[:80]!r}")
    own = " ".join(_text(newer.get(k)) for k in ("caution", "match_note", "fix_source")).lower()
    line = _text(newer.get("verdict_line"))
    own += " " + (line[:len(VERDICT_PREFIX)] if line.startswith(VERDICT_PREFIX) else line).lower()
    for word in NEWER_FORBIDDEN_WORDS:
        if re.search(rf"\b{word}\b", own):
            problems.append(f"the newer-release note says {word!r}")
    return problems


def public_text_problems(row: Mapping[str, Any], counted_rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """Why a row's strings may not be printed: a stored report title or excerpt reproduced (a shared run
    of SHINGLE_WORDS words, or a whole title of three or more words), an author-like field, an
    acceptance or threshold phrase, a verdict line that is not one of the two shapes this module writes,
    a newer-release caution that is not the one its known-issue flag names or a note that says "available",
    "addresses", "fixes" or "resolves" (caution_problems), or vendor text from a source with no publication
    permission."""
    problems: list[str] = []
    strings = row_strings(row)
    joined = " ".join(strings)
    mine = _shingles(joined)
    norm_joined = " ".join(_words(joined))
    for r in counted_rows:
        for field in ("report_title", "parent_title", "report_text_excerpt"):
            text = _text(r.get(field))
            if not text:
                continue
            if mine & _shingles(text):
                problems.append(f"shares {SHINGLE_WORDS} consecutive words with the stored {field} of {r.get('id')}")
            title_words = _words(text)
            if field != "report_text_excerpt" and len(title_words) >= 3 and " ".join(title_words) in norm_joined:
                problems.append(f"reproduces the stored {field} of {r.get('id')}")
    lowered = joined.lower()
    for phrase in FORBIDDEN_WORDING:
        if phrase in lowered:
            problems.append(f"states {phrase!r}")
    for key in row:
        if re.search(r"author|login|user(name)?|reporter|handle", str(key), re.I):
            problems.append(f"carries an author-like field {key!r}")
    newer = row.get("newer") if isinstance(row.get("newer"), Mapping) else {}
    for key in newer:
        if re.search(r"author|login|user(name)?|reporter|handle", str(key), re.I):
            problems.append(f"carries an author-like field newer.{key!r}")
    line = _text(newer.get("verdict_line"))
    if newer and not (line == NO_VERDICT_YET or (line.startswith(VERDICT_PREFIX) and line.endswith("."))):
        problems.append(f"the newer release's verdict line is not one this module writes: {line[:80]!r}")
    if newer:
        problems += caution_problems(newer)
    if newer.get("fix_lines") and not publication_permitted(_text(newer.get("notes_url"))):
        problems.append("prints vendor fix text from a source whose publication permission is not on record")
    nxt = row.get("next_action")
    if nxt is not None:
        problems += next_action_problems(nxt) if isinstance(nxt, Mapping) else ["the next action is not a mapping"]
    return problems
