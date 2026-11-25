"""Source-supplied report facts: what each tracker's own record of a counted report says (AUX-137; owner ruling of 2026-11-24).

WHY. The published assessment (AUX-134) printed "Not established" for problem confirmation and the maintainers'
response, because no stored field said what a project did with a report. An issue tracker's own record says it:
its state, why it was closed (completed, not planned, duplicate), and the labels only an account with triage rights
can apply (confirmed, bug, regression, crash, a platform, a dismissal such as "cannot reproduce"). Its issue FORM
carries fields the reporter filled from a closed list (the operating system, the version) or a dedicated slot (a
crash-log link). None of it is prose read by a phrase list, and none of it is a judgement AUXSAYS makes.
scripts/backfill_report_source_facts.py reads that record for reports ALREADY stored as counted rows and writes
`_data/report_source_facts.yml`: one entry per report link.

THIS MODULE IS THE DATA LAYER. It reads, validates and counts the stored entries (`weigh`); it decides NO verdict.
The weighing of a page (what the counts mean for a recommendation) is computed by a separate scheduled step and
read back through lib.assessment_output, behind the one call site in lib.patch_decision.assess. Maintainer decisions are SUPPLEMENTARY evidence there (owner
ruling of 2026-11-24, section 3): they never gate whether a page can be assessed.

OPTION B (owner ruling of 2026-11-24, section 2): `closed_by_reporter`. When the tracker's record is read, the
reporter's account and the closing account are compared IN MEMORY and only the outcome is stored: true, false, or
"unknown" (the report is open, an account was deleted, or either side is missing). No login, account id, profile or
hash of one is stored, logged or returned. What the fact means, and what it does not:
  * a report closed by its own reporter is NEVER a resolution and NEVER a maintainer decision;
  * a report closed by another account is NOT proof that a maintainer was involved: any account with triage rights,
    a bot or an integration can close it. Maintainer authority comes ONLY from the labels the tracker's declared
    vocabulary lists (on GitHub a label needs triage rights);
  * provenance: every entry keeps its source, the day it was read and the rule that wrote it.
(Round 2's "close reasons only the maintainers give" basis is withdrawn: a GitHub author can close their own report
as "not planned" too. A close reason is now only a fact about the closure, never authority.)

WHAT A FACT MEANS.
  decided        the record carries a label from the tracker's vocabulary (confirmation, type, dismissal, workaround):
                 a maintainer acted on it. Nothing else is a maintainer decision; a closure alone is not.
  confirmed      the tracker's OWN confirmation label, the report not closed as not planned. It says the maintainers
                 treat the report as a real defect, not how many users it affects.
  regression     a confirmed report that also carries the regression label.
  version        the form's own version field against the page's version: "same", "earlier", "later" or "" (not
                 established). A conflict is WEIGHED by the weighing step with this provenance; it never
                 silently removes a report. A report that is genuinely about another version leaves the count only
                 through the audited withdrawal path (counted: false with an exclusion_reason; lib.evidence_loss).
  dismissal      how a CLOSED report that is not a confirmed fix was closed, in one class (`DISMISSALS`): reporter
                 self-closure, duplicate, invalid, unsupported configuration, cannot reproduce, declined,
                 administrative (closed as not planned with no stated cause, or by an inactivity label), closed by
                 another account with no maintainer label ("unexplained"), or closed with the closer not established.
                 NO DISMISSAL IS POSITIVE EVIDENCE, and no number of them makes a page less cautious.
  confirmed fix  a confirmed report closed as completed by an account other than its reporter: the tracker records
                 the confirmed defect as done. The record does not name the release that contains a fix.
  workaround     the maintainers' workaround label: a workaround is documented for the report.
  crash          the form's crash-log slot holds a link, or the maintainers applied a crash label.
  platform       the maintainers' platform label, else the operating-system family the reporter chose in the form.
  stale          read more than STALE_AFTER_DAYS days before the newest report the evidence store collected (or no
                 such date can be read). A stale record is not used.

Pure: standard library and PyYAML. No network, no clock, no collector import.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

from .source_segments import report_url_key

FACTS_NAME = "report_source_facts.yml"
VOCABULARY_NAME = "report_source_vocabularies.yml"
EVIDENCE_NAME = "consensus_evidence.yml"
ROOT = Path(__file__).resolve().parents[2]
FACTS_PATH = ROOT / "_data" / FACTS_NAME
VOCABULARY_PATH = ROOT / "_data" / VOCABULARY_NAME
EVIDENCE_PATH = ROOT / "_data" / EVIDENCE_NAME
SCHEMA_VERSION = 3
VOCABULARY_SCHEMA_VERSION = 2
# The rule that reads a source record into an entry. An entry written under another rule is not read: the refresh
# rewrites it, and until then its report has no fact (fail closed). source-facts-3 added `closed_by_reporter`.
RULE_VERSION = "source-facts-3"
STALE_AFTER_DAYS = 7

STATES = ("open", "closed")
STATE_REASONS = ("", "completed", "not_planned", "duplicate", "reopened")
REPORTER_UNKNOWN = "unknown"
CLOSED_BY_REPORTER = (True, False, REPORTER_UNKNOWN)
# How a closed report was closed (`ReportFacts.dismissal`), most specific first in `classify_closure`. None is
# positive evidence. The words each class is printed with.
DISMISSALS = {
    "reporter": "closed by its own reporter",
    "duplicate": "closed as a duplicate",
    "invalid": "closed as invalid or as intended behaviour",
    "unsupported": "closed as an unsupported or external configuration",
    "unreproducible": "closed as not reproducible",
    "declined": "closed as declined (will not be fixed)",
    "administrative": "closed administratively (not planned with no stated cause, or for inactivity)",
    "unexplained": "closed as completed by another account with no maintainer label (what was done is not stated)",
    "unknown_closer": "closed, with who closed it not established",
}
DISMISSAL_LABEL_CLASSES = ("duplicate", "invalid", "unsupported", "unreproducible", "declined", "administrative")
OS_FAMILIES = ("windows", "macos", "linux", "other")
OS_DISPLAY = {"windows": "Windows", "macos": "macOS", "linux": "Linux", "other": "Other (not in the form's list)"}
PLATFORM_FAMILIES = ("windows", "macos", "linux")
ENTRY_KEYS = ("key", "source", "state", "state_reason", "labels", "os", "crash_log", "form_version",
              "closed_by_reporter", "checked_at", "rule")
_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 /:._+';-]{0,49}$", re.ASCII)
_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", re.ASCII)
_VERSION_RE = re.compile(r"^[0-9][0-9A-Za-z.+-]{0,39}$", re.ASCII)
_SOURCE_RE = re.compile(r"^github\.com/[a-z0-9_.-]+/[a-z0-9_.-]+$", re.ASCII)
_ISSUE_KEY_RE = re.compile(r"^https://(github\.com/[a-z0-9_.-]+/[a-z0-9_.-]+)/issues/([0-9]+)$", re.ASCII)

MARK_CONFIRMED = "confirmed"
MARK_REGRESSION = "confirmed, labelled a regression"
MARK_EARLIER = "confirmed, filed against an earlier version"
MARK_LATER = "confirmed, filed against a later version"
MARKS = (MARK_CONFIRMED, MARK_REGRESSION, MARK_EARLIER, MARK_LATER)


class Vocabulary:
    """What one source's own structure means. `authority` is how a page names who applies the labels. The label
    sets are the source's vocabulary as its maintainers use it; `dismissal` maps a label to its DISMISSAL class;
    `form_os`, `form_crash` and `form_version` name the issue form's fields, `os_values` the form's closed list
    (a whole-value pattern and the family it belongs to) and `version_values` the whole-value pattern of a
    version the form's field may hold."""

    __slots__ = ("authority", "confirmed", "defect", "regression", "crash", "dismissal", "workaround", "platform",
                 "form_os", "os_values", "form_crash", "form_version", "version_values")

    def __init__(self, *, authority: str, confirmed: Iterable[str] = (), defect: Iterable[str] = (),
                 regression: Iterable[str] = (), crash: Iterable[str] = (),
                 dismissal: Mapping[str, str] | None = None, workaround: Iterable[str] = (),
                 platform: Mapping[str, str] | None = None, form_os: str = "",
                 os_values: Iterable[tuple[str, str]] = (), form_crash: str = "", form_version: str = "",
                 version_values: str = "") -> None:
        self.authority = authority
        self.confirmed = frozenset(confirmed)
        # A regression or crash label is NOT a confirmation and is never folded into one (review round 1, M4).
        self.defect = frozenset(defect)
        self.regression = frozenset(regression)
        self.crash = frozenset(crash)
        self.dismissal = dict(dismissal or {})
        if any(v not in DISMISSAL_LABEL_CLASSES for v in self.dismissal.values()):
            raise ValueError(f"dismissal labels map to one of {DISMISSAL_LABEL_CLASSES}")
        self.workaround = frozenset(workaround)
        self.platform = dict(platform or {})
        self.form_os = form_os
        self.os_values = tuple((re.compile(pattern, re.ASCII), family) for pattern, family in os_values)
        self.form_crash = form_crash
        self.form_version = form_version
        self.version_values = re.compile(version_values, re.ASCII) if version_values else None

    @property
    def confirmable(self) -> bool:
        """Does this tracker have a confirmation label at all? Without one, "confirmed" and "not confirmed" are
        both not established for its reports."""
        return bool(self.confirmed)

    @property
    def typed(self) -> frozenset:
        return self.confirmed | self.defect | self.regression | self.crash

    @property
    def marks(self) -> frozenset:
        """Every label only the maintainers apply: a report that carries one was acted on by them."""
        return self.typed | frozenset(self.dismissal) | self.workaround


class FactsFileError(ValueError):
    """The facts file is present but unreadable or malformed. It then supports nothing (fail closed)."""


class VocabularyFileError(ValueError):
    """The vocabulary file is missing, unreadable or malformed. No tracker is then read (fail closed)."""


# ------------------------------------------------------------------------------------- the vocabularies (data)

_VOCABULARY_KEYS = ("authority", "verified_at", "note", "confirmed", "defect", "regression", "crash", "dismissal",
                    "workaround", "platform", "form_os", "os_values", "form_crash", "form_version", "version_values")


def _pattern_problem(pattern: Any) -> str:
    if not isinstance(pattern, str) or not pattern.strip():
        return "is not a pattern"
    try:
        re.compile(pattern, re.ASCII)
    except re.error as exc:
        return f"does not compile ({exc})"
    return ""


def vocabulary_errors(doc: Any) -> list[str]:
    """Structural problems of the vocabulary file. Any problem refuses the whole file."""
    if not isinstance(doc, Mapping) or doc.get("schema_version") != VOCABULARY_SCHEMA_VERSION \
            or not isinstance(doc.get("sources"), Mapping):
        return [f"expected schema_version {VOCABULARY_SCHEMA_VERSION} and a 'sources' mapping"]
    errors: list[str] = []
    for name, entry in doc["sources"].items():
        if not isinstance(name, str) or not _SOURCE_RE.fullmatch(name):
            errors.append(f"{name!r}: not a tracker name (github.com/<owner>/<repository>, lower case)")
            continue
        if not isinstance(entry, Mapping):
            errors.append(f"{name}: not a mapping")
            continue
        unknown = sorted(set(entry) - set(_VOCABULARY_KEYS))
        if unknown:
            errors.append(f"{name}: unknown keys {unknown}")
        if not isinstance(entry.get("authority"), str) or not entry["authority"].strip():
            errors.append(f"{name}: authority must say how a page names who applies the labels")
        if not isinstance(entry.get("verified_at"), str) or not _DATE_RE.fullmatch(entry["verified_at"]):
            errors.append(f"{name}: verified_at must be YYYY-MM-DD")
        for field in ("confirmed", "defect", "regression", "crash", "workaround"):
            labels = entry.get(field, [])
            if not isinstance(labels, list) or any(not isinstance(n, str) or not _LABEL_RE.fullmatch(n)
                                                   for n in labels):
                errors.append(f"{name}: {field} must be a list of label names")
        dismissal = entry.get("dismissal", {})
        if not isinstance(dismissal, Mapping) or any(not isinstance(k, str) or not _LABEL_RE.fullmatch(k)
                                                     or v not in DISMISSAL_LABEL_CLASSES
                                                     for k, v in dismissal.items()):
            errors.append(f"{name}: dismissal must map label names to one of {DISMISSAL_LABEL_CLASSES}")
        platform = entry.get("platform", {})
        if not isinstance(platform, Mapping) or any(not isinstance(k, str) or not _LABEL_RE.fullmatch(k)
                                                    or v not in PLATFORM_FAMILIES for k, v in platform.items()):
            errors.append(f"{name}: platform must map label names to one of {PLATFORM_FAMILIES}")
        for field in ("form_os", "form_crash", "form_version", "note"):
            if not isinstance(entry.get(field, ""), str):
                errors.append(f"{name}: {field} must be text")
        values = entry.get("os_values", [])
        if not isinstance(values, list) or any(not isinstance(v, (list, tuple)) or len(v) != 2
                                               or _pattern_problem(v[0]) or v[1] not in OS_FAMILIES for v in values):
            errors.append(f"{name}: os_values must be [pattern, family] pairs with a family of {OS_FAMILIES}")
        if entry.get("form_version") and _pattern_problem(entry.get("version_values")):
            errors.append(f"{name}: form_version needs version_values, the whole-value pattern of a version")
        if "version_values" in entry and _pattern_problem(entry["version_values"]):
            errors.append(f"{name}: version_values {_pattern_problem(entry['version_values'])}")
    return errors


def load_vocabularies(path: Path) -> dict[str, Vocabulary]:
    """The vocabularies a file declares. VocabularyFileError when it is missing, unreadable or malformed."""
    import yaml  # noqa: PLC0415

    path = Path(path)
    if not path.is_file():
        raise VocabularyFileError(f"{path.name}: the file does not exist")
    try:
        doc = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.SafeLoader)
    except Exception as exc:  # noqa: BLE001 - any parse failure is malformed
        raise VocabularyFileError(f"{path.name}: unreadable YAML: {exc}") from exc
    errors = vocabulary_errors(doc)
    if errors:
        raise VocabularyFileError(f"{path.name}: {len(errors)} schema error(s), first: {errors[0]}")
    return {name: Vocabulary(authority=entry["authority"].strip(), confirmed=entry.get("confirmed", ()),
                             defect=entry.get("defect", ()), regression=entry.get("regression", ()),
                             crash=entry.get("crash", ()), dismissal=entry.get("dismissal"),
                             workaround=entry.get("workaround", ()), platform=entry.get("platform"),
                             form_os=entry.get("form_os", ""),
                             os_values=[tuple(v) for v in entry.get("os_values", ())],
                             form_crash=entry.get("form_crash", ""), form_version=entry.get("form_version", ""),
                             version_values=entry.get("version_values", ""))
            for name, entry in doc["sources"].items()}


SOURCES: dict[str, Vocabulary] = {}
_SOURCES_STATE: dict[str, Any] = {}
GENERIC_AUTHORITY = "the maintainers"


def sources() -> dict[str, Vocabulary]:
    """tracker -> vocabulary, from the tracked vocabulary file, read once per process. A missing or malformed
    file declares no tracker (`sources_problem` names it, and QA reports it as an error)."""
    if not _SOURCES_STATE.get("loaded"):
        _SOURCES_STATE["loaded"] = True
        try:
            SOURCES.update(load_vocabularies(VOCABULARY_PATH))
            _SOURCES_STATE["problem"] = ""
        except VocabularyFileError as exc:
            _SOURCES_STATE["problem"] = str(exc)
    return SOURCES


def sources_problem() -> str:
    sources()
    return _SOURCES_STATE.get("problem", "")


# ------------------------------------------------------------------------------------------- reading a source

_FORM_SPLIT_RE = re.compile(r"^###[ \t]+(.+?)[ \t]*$", re.M)
_URL_RE = re.compile(r"https?://\S+")
_NO_RESPONSE = ("", "_No response_")


def form_fields(body: Any) -> dict[str, str]:
    """An issue form's fields as the tracker renders them: a `### <field name>` line, then the value. A field
    that appears twice is ambiguous and is left out (a reporter can type a heading inside a free-text field)."""
    parts = _FORM_SPLIT_RE.split(str(body or "").replace("\r\n", "\n"))
    seen: Counter = Counter(parts[i].strip() for i in range(1, len(parts) - 1, 2))
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)
            if seen[parts[i].strip()] == 1}


def source_of(key: str) -> str:
    """The source a report key belongs to ("github.com/<owner>/<repository>"), or "" when it is not an issue of
    a tracker this module reads."""
    match = _ISSUE_KEY_RE.match(str(key or ""))
    return match.group(1) if match and match.group(1) in sources() else ""


def reporter_closed(issue: Mapping[str, Any]) -> bool | str:
    """OPTION B, the one comparison: did the account that reported this issue close it? True, False, or "unknown"
    (open, a deleted account, or either account missing). Both accounts are read from the tracker's own record and
    compared here, in memory; neither is returned, stored, logged or hashed."""
    if str(issue.get("state") or "").strip().lower() != "closed":
        return REPORTER_UNKNOWN
    sides = []
    for field in ("user", "closed_by"):
        account = issue.get(field)
        name = str(account.get("login") or "").strip().lower() if isinstance(account, Mapping) else ""
        sides.append(name)
    if not all(sides) or "ghost" in sides:
        return REPORTER_UNKNOWN
    return sides[0] == sides[1]


def entry_from_issue(key: str, issue: Mapping[str, Any], checked_at: str) -> dict[str, Any] | None:
    """One stored entry from a tracker's own record of an issue (the REST issue object), or None when the key
    is not one this module reads or the object is not that issue. Reads the state, the close reason, the label
    names, three form fields and whether the reporter closed it. NEVER returns an account, a title or any text."""
    source = source_of(key)
    match = _ISSUE_KEY_RE.match(str(key or ""))
    if not source or not isinstance(issue, Mapping) or issue.get("pull_request") is not None:
        return None
    if str(issue.get("number")) != match.group(2):
        return None
    state = str(issue.get("state") or "").strip().lower()
    reason = str(issue.get("state_reason") or "").strip().lower()
    if state not in STATES or reason not in STATE_REASONS:
        return None
    labels = sorted({str((label or {}).get("name") or "").strip() for label in issue.get("labels") or []
                     if isinstance(label, Mapping)})
    labels = [name for name in labels if _LABEL_RE.fullmatch(name)]
    vocab = sources()[source]
    fields = form_fields(issue.get("body"))
    os_family = ""
    if vocab.form_os and vocab.form_os in fields:
        value = fields[vocab.form_os]
        os_family = next((family for pattern, family in vocab.os_values if pattern.fullmatch(value)), "")
    crash: bool | None = None
    if vocab.form_crash and vocab.form_crash in fields:
        value = fields[vocab.form_crash]
        crash = True if _URL_RE.search(value) else False if value in _NO_RESPONSE else None
    version = ""
    if vocab.form_version and vocab.version_values is not None and vocab.form_version in fields:
        value = fields[vocab.form_version]
        version = value if vocab.version_values.fullmatch(value) and _VERSION_RE.fullmatch(value) else ""
    return {"key": key, "source": source, "state": state, "state_reason": reason, "labels": labels,
            "os": os_family, "crash_log": crash, "form_version": version,
            "closed_by_reporter": reporter_closed(issue), "checked_at": checked_at, "rule": RULE_VERSION}


# ------------------------------------------------------------------------------------------------ the store

def entry_errors(entry: Any) -> list[str]:
    """Why one stored entry may not be read, or []."""
    if not isinstance(entry, Mapping):
        return ["not a mapping"]
    errors: list[str] = []
    unknown = sorted(set(entry) - set(ENTRY_KEYS))
    missing = [k for k in ENTRY_KEYS if k not in entry]
    if unknown:
        errors.append(f"unknown keys {unknown}")
    if missing:
        return errors + [f"missing {missing}"]
    key, source = entry.get("key"), entry.get("source")
    if not isinstance(key, str) or not _ISSUE_KEY_RE.fullmatch(key) or report_url_key(key) != key:
        errors.append("key is not a canonical report link of a tracker issue")
    if not isinstance(source, str) or not _SOURCE_RE.fullmatch(source) or (isinstance(key, str)
                                                                         and not key.startswith(f"https://{source}/")):
        errors.append("source does not name the tracker of its key")
    if entry.get("state") not in STATES:
        errors.append(f"state must be one of {STATES}")
    if entry.get("state_reason") not in STATE_REASONS:
        errors.append(f"state_reason must be one of {STATE_REASONS}")
    labels = entry.get("labels")
    if not isinstance(labels, list) or any(not isinstance(n, str) or not _LABEL_RE.fullmatch(n) for n in labels) \
            or labels != sorted(set(labels)):
        errors.append("labels must be a sorted list of distinct label names")
    if entry.get("os") not in ("",) + OS_FAMILIES:
        errors.append(f"os must be '' or one of {OS_FAMILIES}")
    if entry.get("crash_log") not in (True, False, None):
        errors.append("crash_log must be true, false or null")
    version = entry.get("form_version")
    if not isinstance(version, str) or (version and not _VERSION_RE.fullmatch(version)):
        errors.append("form_version must be '' or a version")
    closed_by = entry.get("closed_by_reporter")
    if not (closed_by is True or closed_by is False or closed_by == REPORTER_UNKNOWN):
        errors.append("closed_by_reporter must be true, false or 'unknown' (never an account)")
    elif entry.get("state") == "open" and closed_by != REPORTER_UNKNOWN:
        errors.append("closed_by_reporter of an open report must be 'unknown'")
    if not isinstance(entry.get("checked_at"), str) or _day(entry["checked_at"]) is None:
        errors.append("checked_at must be a date, YYYY-MM-DD")
    if not isinstance(entry.get("rule"), str) or not entry["rule"].strip():
        errors.append("rule must name the rule that wrote the entry")
    return errors


def schema_errors(doc: Any) -> list[str]:
    """Structural problems of the whole file. Any problem refuses the whole file: a store that is partly wrong
    is not partly trusted."""
    if not isinstance(doc, Mapping) or doc.get("schema_version") != SCHEMA_VERSION \
            or not isinstance(doc.get("facts"), list):
        return [f"expected schema_version {SCHEMA_VERSION} and a 'facts' list"]
    errors: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(doc["facts"]):
        label = entry.get("key") if isinstance(entry, Mapping) and isinstance(entry.get("key"), str) \
            else f"facts[{index}]"
        errors += [f"{label}: {problem}" for problem in entry_errors(entry)]
        if label in seen:
            errors.append(f"{label}: duplicate key")
        seen.add(label)
    return errors


def index(doc: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """key -> entry, for the entries written under the CURRENT rule. Call only after `schema_errors` is empty."""
    return {entry["key"]: dict(entry) for entry in doc.get("facts") or [] if entry.get("rule") == RULE_VERSION}


def load(path: Path) -> dict[str, dict[str, Any]]:
    """The facts a file supports: {} when there is no file, FactsFileError when it is present but wrong."""
    import yaml  # noqa: PLC0415

    path = Path(path)
    if not path.is_file():
        return {}
    try:
        doc = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.SafeLoader)
    except Exception as exc:  # noqa: BLE001 - any parse failure is malformed, never "absent"
        raise FactsFileError(f"{path.name}: unreadable YAML: {exc}") from exc
    errors = schema_errors(doc)
    if errors:
        raise FactsFileError(f"{path.name}: {len(errors)} schema error(s), first: {errors[0]}")
    return index(doc)


_CAPTURED_RE = re.compile(r"^\s*captured_at:\s*['\"]?([0-9]{4}-[0-9]{2}-[0-9]{2})", re.M | re.ASCII)


def _day(value: Any) -> int | None:
    """The ordinal of a YYYY-MM-DD date, or None when it is not one."""
    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value).toordinal()
    except ValueError:
        return None


def newest_capture(path: Path) -> str:
    """The day of the newest report the evidence store at `path` collected (its newest `captured_at`), or "".
    THE ONE DATE staleness is measured against: part of the tree, so every caller reaches the same answer for the
    same commit. The authority takes no clock."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""
    days = [d for d in set(_CAPTURED_RE.findall(text)) if _day(d) is not None]
    return max(days) if days else ""


def is_stale(checked_at: Any, as_of: Any) -> bool:
    """Was this record read too long before `as_of` to be used? No readable reference date means the age is not
    established, and that is stale too."""
    checked, reference = _day(checked_at), _day(as_of)
    return checked is None or reference is None or reference - checked > STALE_AFTER_DAYS


class DatedFacts(dict):
    """Explicit facts (key -> entry) together with the reference date they are aged against."""

    __slots__ = ("as_of",)

    def __init__(self, entries: Mapping[str, Mapping[str, Any]] | None = None, as_of: str = "") -> None:
        super().__init__(entries or {})
        self.as_of = as_of


_STORED: dict[str, Any] = {}


def stored() -> dict[str, dict[str, Any]]:
    """The tracked facts file, read once per process. A malformed file supports nothing (`stored_problem` names
    it) and so does a missing one (`stored_missing`); QA reports either as an error."""
    if "facts" not in _STORED:
        _STORED["missing"] = not FACTS_PATH.is_file()
        try:
            _STORED["facts"], _STORED["problem"] = load(FACTS_PATH), ""
        except FactsFileError as exc:
            _STORED["facts"], _STORED["problem"] = {}, str(exc)
    return _STORED["facts"]


def stored_problem() -> str:
    stored()
    return _STORED.get("problem", "")


def stored_missing() -> bool:
    stored()
    return bool(_STORED.get("missing", False))


def stored_as_of() -> str:
    """The reference date the tracked file's records are aged against: `newest_capture` of the tracked evidence
    store, read once per process."""
    if "as_of" not in _STORED:
        _STORED["as_of"] = newest_capture(EVIDENCE_PATH)
    return _STORED["as_of"]


def reset_stored() -> None:
    """Forget the cached file (a writer that has just rewritten it, and the tests)."""
    _STORED.clear()


def render(entries: Iterable[Mapping[str, Any]]) -> str:
    """The file text for these entries, sorted by key, one stable layout."""
    import yaml  # noqa: PLC0415

    rows = sorted(({k: entry[k] for k in ENTRY_KEYS} for entry in entries), key=lambda e: e["key"])
    head = ("# Source-supplied facts about reports that are stored as counted evidence rows (lib/assessment_facts).\n"
            "# Written ONLY by scripts/backfill_report_source_facts.py from each tracker's own record of the issue:\n"
            "# its state, its close reason, its label names, the operating-system family and the version chosen in\n"
            "# the issue form, whether the form's crash-log field holds a link, whether the report was closed by its\n"
            "# own reporter (true, false or unknown: the accounts are compared in memory and never stored), and the\n"
            "# day it was read. No report text and no account data. Never edited by hand.\n")
    return head + yaml.safe_dump({"schema_version": SCHEMA_VERSION, "facts": rows}, sort_keys=False,
                                 allow_unicode=True, width=1000)


# ---------------------------------------------------------------------------------------------- one report

def version_tuple(value: Any) -> tuple[int, ...] | None:
    """A dotted numeric version as a tuple, or None when it is not one ("33.0.1" -> (33, 0, 1); a pre-release
    suffix is not compared)."""
    text = str(value or "").strip().lower()
    text = text[1:] if text.startswith("v") else text
    match = re.match(r"^([0-9]+(?:\.[0-9]+)*)(?:-[0-9a-z]+)?$", text, re.ASCII)
    return tuple(int(p) for p in match.group(1).split(".")) if match else None


def version_relation(form_version: Any, page_version: Any) -> str:
    """How the version the reporter's own form names stands to the page's: "same", "earlier", "later", or ""
    when either is not established or they cannot be ordered."""
    form, page = version_tuple(form_version), version_tuple(page_version)
    if form is None or page is None:
        return ""
    width = max(len(form), len(page))
    form, page = form + (0,) * (width - len(form)), page + (0,) * (width - len(page))
    return "same" if form == page else "earlier" if form < page else "later"


class ReportFacts:
    """What the stored entry of one report establishes, under its source's vocabulary, for a page of `version`
    read against the reference date `as_of`."""

    __slots__ = ("key", "source", "authority", "confirmable", "checked_at", "stale", "open", "closed", "declined",
                 "duplicate", "completed", "version", "form_version", "labelled_confirmed", "confirmed",
                 "regression_label", "regression", "crash_label", "typed", "decided", "closed_by_reporter",
                 "dismissal", "confirmed_fix", "workaround", "crash", "platform_label", "os")

    def __init__(self, entry: Mapping[str, Any], version: str = "", as_of: str = "") -> None:
        vocab = sources()[entry["source"]]
        labels = set(entry["labels"])
        reason = entry["state_reason"]
        self.key = entry["key"]
        self.source = entry["source"]
        self.authority = vocab.authority
        self.confirmable = vocab.confirmable
        self.checked_at = entry["checked_at"]
        self.stale = is_stale(entry["checked_at"], as_of)
        self.open = entry["state"] == "open"
        self.closed = entry["state"] == "closed"
        self.declined = self.closed and reason == "not_planned"
        self.duplicate = self.closed and reason == "duplicate"
        self.completed = self.closed and reason == "completed"
        self.form_version = str(entry.get("form_version") or "")
        self.version = version_relation(self.form_version, version)
        # Confirmed by the tracker's own label, whatever version the form names; the version relation travels with
        # it and the weighing step weighs it (residual path 1: a form version never erases it).
        self.labelled_confirmed = bool(labels & vocab.confirmed) and not self.declined
        self.confirmed = self.labelled_confirmed
        self.regression_label = bool(labels & vocab.regression)
        self.regression = self.confirmed and self.regression_label
        self.crash_label = bool(labels & vocab.crash)
        self.typed = bool(labels & vocab.typed)
        # ONLY a label from the vocabulary is a maintainer decision. A closure never is by itself.
        self.decided = vocab.confirmable and bool(labels & vocab.marks)
        self.closed_by_reporter = entry.get("closed_by_reporter", REPORTER_UNKNOWN)
        self.workaround = bool(labels & vocab.workaround)
        self.confirmed_fix = (self.confirmed and self.completed and self.closed_by_reporter is False)
        self.dismissal = classify_closure(self, labels, vocab) if self.closed and not self.confirmed_fix else ""
        self.crash = entry["crash_log"] is True or self.crash_label
        families = {vocab.platform[name] for name in labels if name in vocab.platform}
        self.platform_label = next(iter(families)) if len(families) == 1 else ""
        self.os = self.platform_label or entry["os"]


def classify_closure(fact: ReportFacts, labels: set, vocab: Vocabulary) -> str:
    """The ONE place a closed report's dismissal class is decided (residual path 2). Most specific first: the
    reporter's own closure, a maintainer dismissal label, the duplicate close reason, then what the record shows
    about the closer. None of these classes is positive evidence."""
    if fact.closed_by_reporter is True:
        return "reporter"
    classes = sorted({vocab.dismissal[name] for name in labels if name in vocab.dismissal})
    if len(classes) == 1:
        return classes[0]
    if fact.duplicate:
        return "duplicate"
    if fact.closed_by_reporter != False:  # noqa: E712 - "unknown" is not False
        return "unknown_closer"
    if fact.declined:
        return "administrative"
    return "unexplained"


def facts_for(row: Mapping[str, Any], facts: Mapping[str, Mapping[str, Any]], *, version: str = "",
              as_of: str = "") -> ReportFacts | None:
    """The stored facts of one counted row's report, or None: no entry under the current rule, or an entry of a
    source this module has no vocabulary for."""
    entry = facts.get(report_url_key(str(row.get("source_url") or "")))
    if not isinstance(entry, Mapping) or entry.get("rule") != RULE_VERSION or entry.get("source") not in sources():
        return None
    return ReportFacts(entry, version, as_of)


# -------------------------------------------------------------------------------------------- the counting

class Weighing:
    """What the stored records of one page's reports establish, COUNTED (no verdict: the weighing step
    weighs). `reports` are the page's separate report links; `records` those with an entry under the current rule;
    `stale` the records too old to use and `fresh` the others, which every other count is taken over; `by_key` the
    fresh ReportFacts by report link. Every fresh record is in exactly one group of `groups()`."""

    __slots__ = ("reports", "records", "stale", "fresh", "unread", "decided", "unconfirmable", "confirmed",
                 "regressions", "confirmed_earlier", "confirmed_later", "confirmed_open", "confirmed_fix",
                 "confirmed_closed_other", "workaround", "regression_unconfirmed", "crash_unconfirmed", "dismissals",
                 "open_marked", "open_undecided", "crash", "os", "os_unknown", "authority", "read_from", "read_to",
                 "marked", "by_key", "unvocabulary")

    def __init__(self) -> None:
        self.reports = self.records = self.stale = self.fresh = self.unread = self.unvocabulary = 0
        self.decided = self.unconfirmable = 0
        self.confirmed = self.regressions = self.confirmed_earlier = self.confirmed_later = 0
        self.confirmed_open = self.confirmed_fix = self.confirmed_closed_other = self.workaround = 0
        self.regression_unconfirmed = self.crash_unconfirmed = 0
        self.dismissals: Counter = Counter()
        self.open_marked = self.open_undecided = self.crash = 0
        self.os: dict[str, int] = {}
        self.os_unknown = 0
        self.authority = GENERIC_AUTHORITY
        self.read_from = self.read_to = ""
        # Which listed reports are the confirmed ones ({"url", "text", "note"}), so a scope can be acted on.
        self.marked: list[dict[str, str]] = []
        self.by_key: dict[str, ReportFacts] = {}

    def cap(self) -> str:
        return self.authority[:1].upper() + self.authority[1:]

    def dated(self) -> str:
        """The day (or days) the records a statement rests on were read. "" when no record is used."""
        if not self.read_from:
            return ""
        return f"Tracker records read on {self.read_from}." if self.read_from == self.read_to \
            else f"Tracker records read between {self.read_from} and {self.read_to}."

    def response(self) -> str:
        """The Maintainer response line: what the tracker shows for every report with a current record, each in
        exactly one group, the dismissals by class. Says plainly that a dismissal is not positive evidence."""
        if not self.records:
            return ("Not established for this page. AUXSAYS holds no maintainer record for these reports: their "
                    "sources publish none, or AUXSAYS does not read one yet.")
        parts = [f"confirmed as a defect: {self.confirmed} (labelled a regression: {self.regressions}; still open: "
                 f"{self.confirmed_open}; closed as completed by another account: {self.confirmed_fix}; closed "
                 f"another way: {self.confirmed_closed_other})"]
        parts += [f"{DISMISSALS[name]}: {self.dismissals[name]}" for name in DISMISSALS if self.dismissals[name]]
        parts += [f"open with a maintainer label but not confirmed: {self.open_marked}",
                  f"open without a maintainer label: {self.open_undecided}"]
        text = (f"What the tracker shows for the {self.fresh} accepted reports with a current record: "
                + "; ".join(parts) + ". A closure is not a resolution and no dismissal counts as positive evidence; "
                "a closure by another account does not show that a maintainer was involved.")
        if self.unconfirmable:
            text += (f" {self.unconfirmable} of them are on a tracker with no confirmation label that AUXSAYS can "
                     f"read, so whether they were confirmed is not established.")
        if self.stale:
            text += (f" {self.stale} stored records were read more than {STALE_AFTER_DAYS} days before the newest "
                     f"collected report and are not used.")
        if self.reports > self.fresh:
            text += f" Accepted reports without a current record: {self.reports - self.fresh} of {self.reports}."
        return f"{text} {self.dated()}".strip()


def _mark(fact: ReportFacts) -> dict[str, str]:
    source, number = fact.key[len("https://"):].rsplit("/issues/", 1)
    note = (MARK_EARLIER if fact.version == "earlier" else MARK_LATER if fact.version == "later"
            else MARK_REGRESSION if fact.regression else MARK_CONFIRMED)
    return {"url": fact.key, "text": f"{source.rsplit('/', 1)[1]} issue {number}", "note": note}


def weigh(counted_rows: Any, facts: Mapping[str, Mapping[str, Any]] | None = None, *, version: str = "",
          as_of: str | None = None) -> Weighing:
    """Count one page's counted rows by the stored source facts of their reports. `facts` None means the tracked
    file (`stored`), aged against the tracked evidence store's newest collection day; explicit `facts` are aged
    against `as_of`, else against the date they carry (`DatedFacts`). Each report link is read once."""
    if facts is None:
        facts, as_of = stored(), (stored_as_of() if as_of is None else as_of)
    elif as_of is None:
        as_of = getattr(facts, "as_of", "")
    as_of = as_of or ""
    out = Weighing()
    seen: set[str] = set()
    found: list[ReportFacts] = []
    for row in counted_rows or ():
        if not isinstance(row, Mapping):
            continue
        key = report_url_key(str(row.get("source_url") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.reports += 1
        fact = facts_for(row, facts, version=version, as_of=as_of)
        if fact is not None:
            found.append(fact)
        elif source_of(key):
            out.unread += 1
        elif _ISSUE_KEY_RE.match(str(key or "")) and sources_problem():
            # Review of 2026-11-24, N2: with no readable vocabulary file NO tracker is read, so an issue link's record
            # is NOT CURRENT (it holds the page), never silently "no tracker".
            out.unread += 1
            out.unvocabulary += 1
    out.records = len(found)
    fresh = [f for f in found if not f.stale]
    out.stale, out.fresh = len(found) - len(fresh), len(fresh)
    authorities = {f.authority for f in fresh}
    out.authority = next(iter(authorities)) if len(authorities) == 1 else GENERIC_AUTHORITY
    days = sorted(f.checked_at for f in fresh)
    out.read_from, out.read_to = (days[0], days[-1]) if days else ("", "")
    os_count: Counter = Counter()
    for f in fresh:
        out.by_key[f.key] = f
        out.decided += f.decided
        out.unconfirmable += not f.confirmable
        out.crash += f.crash
        out.workaround += f.workaround
        if f.os:
            os_count[f.os] += 1
        else:
            out.os_unknown += 1
        out.regression_unconfirmed += f.regression_label and not f.confirmed and not f.declined
        out.crash_unconfirmed += f.crash_label and not f.confirmed and not f.declined
        if f.confirmed:
            out.confirmed += 1
            out.regressions += f.regression
            out.confirmed_earlier += f.version == "earlier"
            out.confirmed_later += f.version == "later"
            out.confirmed_open += f.open
            out.confirmed_fix += f.confirmed_fix
            out.marked.append(_mark(f))
            out.confirmed_closed_other += f.closed and not f.confirmed_fix
        elif f.closed:
            out.dismissals[f.dismissal] += 1
        elif f.decided:
            out.open_marked += 1
        else:
            out.open_undecided += 1
    out.os = dict(os_count)
    out.marked.sort(key=lambda m: m["url"])
    return out
