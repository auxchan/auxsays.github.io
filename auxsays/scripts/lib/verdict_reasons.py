"""The two committed fact files the verdict authority reads: reviewed verdict reasons and the one
verified lifecycle exception (GROWTH-3).

WHY A FILE. Owner decision 1 (2026-11-06) allows TEST FIRST and WAIT only with an evidence-backed
reason: the same concrete problem from independent incidents, or "worked before, broke after
updating". Neither is derivable from stored fields -- `issue_theme` is a classifier label (it typed
a virtual-camera report as an audio regression), and two rows sharing it are the same problem only
4 times in 20 when read. So each TEST FIRST / WAIT rests on a short, reviewed, committed record:
`auxsays/_data/verdict_reasons.yml`. A page without a valid entry shows INSUFFICIENT DATA (or its
official verdict). A deterministic corroboration signal is follow-up work; until it exists, a new
TEST FIRST / WAIT needs a new reviewed entry.

WHAT AN ENTRY MUST SATISFY (checked here, named in the tests):
  * schema: identity (product_id, update_version, target_build), verdict WAIT | TEST FIRST, a
    scope qualifier ("if ...", "when ...", "for ..."), a reason class, a one-line public reason,
    and the exact counted evidence rows (id + source_url) it rests on;
  * every cited row exists in the authoritative counted population OF THAT PAGE, by id, with the
    same source_url (F1). A row that stops counting -- an audited withdrawal -- makes the entry
    UNSUPPORTED: the page falls back and QA warns; it is never a writer-blocking error;
  * at least two distinct reporters (distinct URL, and identical excerpts are one reporter), unless
    an official confirmation is cited (F2/F3);
  * an official confirmation names a stored record whose captured official notes contain the
    statement verbatim, so it can be re-checked rather than trusted;
  * WAIT needs reason_class `regression`, the version transition, a written material impact and
    `new_in_this_version: true` (F4/F5). A persistent problem is never a regression.

THE LIFECYCLE FILE holds exactly ONE entry today: KB5079391, which Microsoft withdrew for new
installations, replaced by KB5086672. It is a single verified exception, NOT the lifecycle
mechanism: the general "newer update available" links wait for the Microsoft KB source assessment
and a deterministic source-to-record writer. `lifecycle_errors` refuses a second entry so this
file cannot quietly become a hand-maintained list, and refuses a matching field (product_id, kb,
relationship, a build) that is not a plain unpadded string (GROWTH-3 review 2, LOW-1).

This module reads YAML and nothing else: no collector import, no network.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

ROOT = Path(__file__).resolve().parents[2]
REASONS_PATH = ROOT / "_data" / "verdict_reasons.yml"
LIFECYCLE_PATH = ROOT / "_data" / "patch_lifecycle.yml"

SCHEMA_VERSION = 1
REASON_VERDICTS = ("WAIT", "TEST FIRST")
REASON_CLASSES = ("regression", "corroborated_issue", "corroborated_install_problem")
# No colon: the stored summary and the feed card print "WAIT <scope>: <line>", and a reader (or
# lib.patch_decision.leading_decision) finds the end of the verdict at the first colon.
SCOPE_RE = re.compile(r"^(?:if|when|for) [^\s:][^:\n]*[^.\s:]$")
LIFECYCLE_RELATIONSHIPS = ("withdrawn_for_new_installs",)
KB_RE = re.compile(r"^KB\d{7}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_LIFECYCLE_ENTRIES = 1

REQUIRED_REASON_KEYS = ("id", "product_id", "update_version", "verdict", "reason_class", "scope",
                        "evidence", "reason", "new_in_this_version", "reviewed_at", "basis")
ALLOWED_REASON_KEYS = frozenset(REQUIRED_REASON_KEYS + (
    "target_build", "official_confirmation", "fixed_in", "transition", "material"))
REQUIRED_LIFECYCLE_KEYS = ("id", "product_id", "kb", "builds", "relationship", "replacement_kb",
                           "released", "replacement_released", "official_url", "verified_at")
ALLOWED_LIFECYCLE_KEYS = frozenset(REQUIRED_LIFECYCLE_KEYS + ("replacement_builds",))


class FactFileError(ValueError):
    """A committed fact file is malformed. It changes only by reviewed PR, so this is a hard error."""


def _s(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _load(path: Path, key: str) -> list[dict[str, Any]]:
    """Entries of a fact file. A MISSING file is an empty population (fail closed: no reasons means
    no TEST FIRST / WAIT, no lifecycle means no AVOID); a present but malformed file raises."""
    path = Path(path)
    if not path.is_file():
        return []
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # any parse failure is malformed, never "empty"
        raise FactFileError(f"{path.name}: unreadable YAML: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise FactFileError(f"{path.name}: expected a mapping with schema_version: {SCHEMA_VERSION}")
    entries = payload.get(key)
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise FactFileError(f"{path.name}: '{key}' must be a list of mappings")
    return entries


def load_reasons(path: Path = REASONS_PATH) -> list[dict[str, Any]]:
    return _load(path, "entries")


def load_lifecycle(path: Path = LIFECYCLE_PATH) -> list[dict[str, Any]]:
    return _load(path, "entries")


def reason_identity(entry: Mapping[str, Any]) -> tuple[str, str, str]:
    return (_s(entry.get("product_id")), _s(entry.get("update_version")), _s(entry.get("target_build")))


def record_identity(record: Mapping[str, Any]) -> tuple[str, str, str]:
    """The identity a Liquid template sees: the RAW fields, no normalisation. Only build-aware
    products carry `target_build`, so this equals lib.patch_identity.key_from for every record."""
    return (_s(record.get("product_id")), _s(record.get("update_version")), _s(record.get("target_build")))


def schema_errors(entries: Iterable[Mapping[str, Any]]) -> list[str]:
    """Structural problems in the reasons file. Static: independent of the evidence store."""
    errors: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        label = _s(entry.get("id")) or f"entries[{index}]"
        missing = [k for k in REQUIRED_REASON_KEYS if k not in entry]
        if missing:
            errors.append(f"{label}: missing {missing}")
            continue
        unknown = sorted(set(entry) - ALLOWED_REASON_KEYS)
        if unknown:
            errors.append(f"{label}: unknown keys {unknown}")
        if label in seen:
            errors.append(f"{label}: duplicate id")
        seen.add(label)
        verdict = _s(entry.get("verdict"))
        rclass = _s(entry.get("reason_class"))
        if verdict not in REASON_VERDICTS:
            errors.append(f"{label}: verdict {verdict!r} is not one of {REASON_VERDICTS}")
        if rclass not in REASON_CLASSES:
            errors.append(f"{label}: reason_class {rclass!r} is not one of {REASON_CLASSES}")
        if not SCOPE_RE.match(_s(entry.get("scope"))):
            errors.append(f"{label}: scope must read 'if ...', 'when ...' or 'for ...' without a colon or a final period")
        reason = _s(entry.get("reason"))
        if not reason or "\n" in reason or len(reason) > 320:
            errors.append(f"{label}: reason must be one public line (1-320 characters)")
        if not isinstance(entry.get("new_in_this_version"), bool):
            errors.append(f"{label}: new_in_this_version must be true or false")
        for field in ("product_id", "update_version", "reviewed_at", "basis"):
            if not _s(entry.get(field)):
                errors.append(f"{label}: {field} is empty")
        if not DATE_RE.match(_s(entry.get("reviewed_at"))):
            errors.append(f"{label}: reviewed_at must be YYYY-MM-DD")
        evidence = entry.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{label}: evidence must list the counted rows it rests on")
        else:
            for item in evidence:
                if not isinstance(item, dict) or not _s(item.get("id")) or not _s(item.get("source_url")):
                    errors.append(f"{label}: every evidence item needs id and source_url")
        conf = entry.get("official_confirmation")
        if conf is not None:
            if not isinstance(conf, dict) or not all(_s(conf.get(k)) for k in ("product_id", "update_version", "statement")):
                errors.append(f"{label}: official_confirmation needs product_id, update_version, statement")
        # F4/F5: WAIT is a regression -- transition, materiality, and genuinely new in this version.
        if verdict == "WAIT":
            transition = entry.get("transition")
            if rclass != "regression":
                errors.append(f"{label}: WAIT requires reason_class regression")
            if not isinstance(transition, dict) or not _s(transition.get("working")) or not _s(transition.get("failing")):
                errors.append(f"{label}: WAIT requires transition.working and transition.failing")
            if not _s(entry.get("material")):
                errors.append(f"{label}: WAIT requires a written material impact")
            if entry.get("new_in_this_version") is not True:
                errors.append(f"{label}: WAIT requires new_in_this_version: true (a persistent problem is not a regression)")
        if rclass == "regression" and entry.get("new_in_this_version") is not True:
            errors.append(f"{label}: reason_class regression requires new_in_this_version: true")
    return errors


def _norm_excerpt(row: Mapping[str, Any]) -> str:
    return re.sub(r"\s+", " ", _s(row.get("report_text_excerpt"))).lower()


def _norm_ws(text: Any) -> str:
    return re.sub(r"\s+", " ", _s(text).replace("\\r", " ").replace("\\n", " "))


def support_problems(entry: Mapping[str, Any], counted_rows: Iterable[Mapping[str, Any]],
                     records_by_identity: Mapping[tuple[str, str, str], Mapping[str, Any]]) -> list[str]:
    """Why this entry does NOT support a verdict right now, or [] when it does.

    `counted_rows` is the authoritative counted population of the entry's own page
    (lib.report_counts.counted_evidence_rows for that identity). Dynamic: an audited withdrawal can
    make a valid entry unsupported, which is a fall-back, not an error."""
    problems: list[str] = []
    by_id = {_s(r.get("id")): r for r in counted_rows}
    cited = []
    for item in entry.get("evidence") or []:
        row = by_id.get(_s(item.get("id")))
        if row is None:
            problems.append(f"row {item.get('id')!r} is not counted on this page")
            continue
        if _s(row.get("source_url")) != _s(item.get("source_url")):
            problems.append(f"row {item.get('id')!r} source_url differs from the counted row")
            continue
        cited.append(row)
    # F2/F3: distinct reporters. Distinct URL, and two rows with an identical excerpt are one
    # reporter posting twice (DaVinci 20.2's only same-problem pair was exactly that).
    urls = {_s(r.get("source_url")) for r in cited}
    excerpts = {_norm_excerpt(r) for r in cited if _norm_excerpt(r)}
    reporters = min(len(urls), len(excerpts) if excerpts else len(urls))
    conf = entry.get("official_confirmation")
    if conf:
        rec = records_by_identity.get((_s(conf.get("product_id")), _s(conf.get("update_version")), ""))
        body = _norm_ws((rec or {}).get("official_patch_notes_body"))
        if not rec or _norm_ws(conf.get("statement")) not in body:
            problems.append("official confirmation is not found in the named record's captured official notes")
    needed = 1 if conf else 2
    if reporters < needed:
        problems.append(f"{reporters} distinct counted reporter(s); {needed} required")
    return problems


# The fields that decide WHICH page a withdrawal applies to. Each must be a plain string exactly as
# a record carries it: not a YAML number, not padded. GROWTH-3 review 2 (LOW-1, probe N1) wrote the
# builds as YAML numbers -- `builds: [26100.8116, 26200.8116]` -- and the file still passed: Python
# compared str(26100.8116) and decided AVOID, while the Liquid gate compared a number with the page's
# string build and printed INSUFFICIENT DATA, and QA saw no difference. A float is also lossy
# (26200.8110 reads back as "26200.811"). A value Python would have to coerce or trim is refused, so
# the file supports nothing until it is fixed (fail closed) and QA reports it as an error.
STRICT_LIFECYCLE_STRINGS = ("product_id", "kb", "relationship")


def _strict_string_problem(value: Any) -> str:
    """Why `value` is not a plain, unpadded, non-empty string, or ''."""
    if not isinstance(value, str):
        return f"is a {type(value).__name__}, not a string (quote it)"
    if not value.strip():
        return "is empty"
    if value != value.strip():
        return "has leading or trailing whitespace"
    return ""


def lifecycle_errors(entries: list[Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    if len(entries) > MAX_LIFECYCLE_ENTRIES:
        errors.append(f"{len(entries)} lifecycle entries; this file holds the single verified KB5079391 "
                      "exception only. More need the KB source assessment and a deterministic writer.")
    for index, entry in enumerate(entries):
        label = _s(entry.get("id")) or f"entries[{index}]"
        missing = [k for k in REQUIRED_LIFECYCLE_KEYS if k not in entry]
        if missing:
            errors.append(f"{label}: missing {missing}")
            continue
        unknown = sorted(set(entry) - ALLOWED_LIFECYCLE_KEYS)
        if unknown:
            errors.append(f"{label}: unknown keys {unknown} (store only KB ids, builds, dates, the URL and the relationship)")
        for field in STRICT_LIFECYCLE_STRINGS:
            problem = _strict_string_problem(entry.get(field))
            if problem:
                errors.append(f"{label}: {field} {problem}")
        for position, build in enumerate(entry.get("builds") if isinstance(entry.get("builds"), list) else []):
            problem = _strict_string_problem(build)
            if problem:
                errors.append(f"{label}: builds[{position}] {problem}")
        if _s(entry.get("relationship")) not in LIFECYCLE_RELATIONSHIPS:
            errors.append(f"{label}: relationship must be one of {LIFECYCLE_RELATIONSHIPS}")
        for field in ("kb", "replacement_kb"):
            if not KB_RE.match(_s(entry.get(field))):
                errors.append(f"{label}: {field} must look like KB1234567")
        for field in ("released", "replacement_released", "verified_at"):
            if not DATE_RE.match(_s(entry.get(field))):
                errors.append(f"{label}: {field} must be YYYY-MM-DD")
        if not _s(entry.get("official_url")).startswith("https://support.microsoft.com/"):
            errors.append(f"{label}: official_url must be the support.microsoft.com article")
        builds = entry.get("builds")
        if not isinstance(builds, list) or not builds or not all(_s(b) for b in builds):
            errors.append(f"{label}: builds must list the exact OS builds of the withdrawn update")
    return errors


def valid_reasons_by_identity(entries: Iterable[Mapping[str, Any]],
                              counted_by_identity: Mapping[tuple[str, str, str], list[Mapping[str, Any]]],
                              records_by_identity: Mapping[tuple[str, str, str], Mapping[str, Any]],
                              ) -> tuple[dict[tuple[str, str, str], list[dict[str, Any]]], dict[str, list[str]]]:
    """Supported entries grouped by page identity, and the problems of the unsupported ones.

    Call only after `schema_errors` is empty: a structurally invalid file is refused outright."""
    valid: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    unsupported: dict[str, list[str]] = {}
    for entry in entries:
        ident = reason_identity(entry)
        problems = support_problems(entry, counted_by_identity.get(ident, []), records_by_identity)
        if problems:
            unsupported[_s(entry.get("id"))] = problems
        else:
            valid.setdefault(ident, []).append(dict(entry))
    return valid, unsupported
