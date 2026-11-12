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
import unicodedata
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
# ASCII ONLY (PR-A2 review, LOW-2 / LOW-3). `\d` matches any Unicode digit and `int()` reads them,
# so a KB number written with a full-width digit passed, and an invisible character after a lifecycle
# build passed because it is not whitespace. Every pattern here is ASCII, and each is matched against
# the WHOLE value (fullmatch: a bare `$` also accepts a final newline).
KB_RE = re.compile(r"^KB[0-9]{7}$", re.ASCII)
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", re.ASCII)
LIFECYCLE_BUILD_RE = re.compile(r"^[0-9]{5}\.[0-9]{1,5}$", re.ASCII)
MAX_LIFECYCLE_ENTRIES = 1
# Exactly what Liquid's `| strip` removes (Ruby String#strip): ASCII whitespace and NUL, nothing else.
# Python's str.strip() also removes Unicode spaces (U+00A0, U+2009, U+3000, U+0085, U+001C..U+001F),
# which is how QA once modelled a page key the gate never builds (PR-A2 review, LOW-1).
LIQUID_STRIP_CHARS = " \t\n\v\f\r\x00"
IDENTITY_FIELDS = ("product_id", "update_version", "target_build")

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


def liquid_strip(value: Any) -> str:
    """`value | append: '' | strip` as the Liquid gate computes it: str() of the raw field, then only
    ASCII whitespace and NUL removed from both ends."""
    return str(value if value is not None else "").strip(LIQUID_STRIP_CHARS)


def reason_identity(entry: Mapping[str, Any]) -> tuple[str, str, str]:
    return (liquid_strip(entry.get("product_id")), liquid_strip(entry.get("update_version")),
            liquid_strip(entry.get("target_build")))


def record_identity(record: Mapping[str, Any]) -> tuple[str, str, str]:
    """The identity a Liquid template sees: the RAW fields, stripped exactly as Liquid's `| strip`
    strips them and no further. Only build-aware products carry `target_build`, so for every record
    without Unicode padding this equals lib.patch_identity.key_from.

    ASCII-STRICT ON PURPOSE (PR-A2 review, LOW-1, probe P5). This used Python's str.strip(), which
    also removes a no-break space: a target_build of "26200.7623" plus U+00A0 made QA and the
    projection key the page "...|26200.7623" while the gate, whose `| strip` keeps U+00A0, looked up
    the padded key, found no row and printed INSUFFICIENT DATA where decide gave SECURITY UPDATE, with
    QA silent. Now both sides compute the same key. A value whose Unicode and ASCII stripping differ
    matches no reason entry and no counted group (fail closed), and `identity_padding_problems` makes
    it a publication error."""
    return (liquid_strip(record.get("product_id")), liquid_strip(record.get("update_version")),
            liquid_strip(record.get("target_build")))


def identity_padding_problems(record: Mapping[str, Any]) -> list[str]:
    """Identity fields whose Python (Unicode) stripping differs from Liquid's (ASCII) stripping, or [].

    Such padding is invisible: the gate keeps it and every Python reader used to drop it. The page
    and `decide` agree on it now (both keep it), but the page silently stops matching its reasons and
    its counted evidence, so QA --publish-strict reports it (record_identity_unicode_padding)."""
    problems = []
    for field in IDENTITY_FIELDS:
        raw = record.get(field)
        if raw is None:
            continue
        text = str(raw)
        if text.strip() != text.strip(LIQUID_STRIP_CHARS):
            problems.append(f"{field} {text!r} carries leading or trailing Unicode whitespace that "
                            "Liquid's strip keeps and Python's strip removes")
    return problems


# Characters that print as nothing, or as a blank that is not a plain space: format characters (Cf:
# U+200B zero-width space, U+FEFF, U+00AD soft hyphen, U+2060 ...), control characters (Cc), the line
# and paragraph separators (Zl, Zp), and every space separator except U+0020 (Zs: U+00A0, U+2009,
# U+3000 ...). G35-04 review 2, LOW-7 (probe P6): "15.010.20056" + U+200B is neither whitespace nor
# padding, so the page key kept it, the page matched none of its reasons or counted rows, the reviewed
# TEST FIRST vanished and QA said nothing. A narrower rule than "ASCII only": 673 live versions are
# changelog TITLES (GitHub, Figma) with spaces, dashes, curly quotes and other printable Unicode, and
# they stay valid (VERIFY_3; AUTH_V2_38 WS2).
INVISIBLE_IDENTITY_CATEGORIES = frozenset({"Cf", "Cc", "Zl", "Zp"})


def _invisible(ch: str) -> bool:
    category = unicodedata.category(ch)
    return category in INVISIBLE_IDENTITY_CATEGORIES or (category == "Zs" and ch != " ")


def identity_invisible_problems(record: Mapping[str, Any]) -> list[str]:
    """Identity fields that carry an invisible or control character, or [].

    Read on the value the page key is built from (`liquid_strip`), with leading and trailing Unicode
    whitespace also set aside: that is padding, which `identity_padding_problems` reports. What is left
    must contain no character of INVISIBLE_IDENTITY_CATEGORIES and no space separator other than a plain
    space. A legitimate Unicode title (a curly apostrophe, an em dash, a trade-mark sign) passes: those
    are printable. QA --publish-strict reports a finding as `record_identity_invisible_character`."""
    problems = []
    for field in IDENTITY_FIELDS:
        raw = record.get(field)
        if raw is None:
            continue
        text = liquid_strip(raw).strip()
        found = sorted({ch for ch in text if _invisible(ch)})
        if found:
            names = ", ".join(f"U+{ord(ch):04X} {unicodedata.name(ch, unicodedata.category(ch))}" for ch in found)
            problems.append(f"{field} {text!r} contains an invisible or control character ({names})")
    return problems


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
        if not DATE_RE.fullmatch(_s(entry.get("reviewed_at"))):
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
        for key in ("builds", "replacement_builds"):
            for position, build in enumerate(entry.get(key) if isinstance(entry.get(key), list) else []):
                problem = _strict_string_problem(build)
                if not problem and not LIFECYCLE_BUILD_RE.fullmatch(str(build)):
                    # PR-A2 review, LOW-3, probe P4: a build followed by a zero-width space is a plain,
                    # unpadded string, so it passed, matched no page, and the 24H2 AVOID vanished.
                    problem = "is not an ASCII OS build of the form 12345.6789"
                if problem:
                    errors.append(f"{label}: {key}[{position}] {problem}")
        if _s(entry.get("relationship")) not in LIFECYCLE_RELATIONSHIPS:
            errors.append(f"{label}: relationship must be one of {LIFECYCLE_RELATIONSHIPS}")
        for field in ("kb", "replacement_kb"):
            if not KB_RE.fullmatch(_s(entry.get(field))):
                errors.append(f"{label}: {field} must be an ASCII KB number like KB1234567")
        for field in ("released", "replacement_released", "verified_at"):
            if not DATE_RE.fullmatch(_s(entry.get(field))):
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
