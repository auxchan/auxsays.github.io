"""The two committed fact files the verdict authority reads: reviewed verdict reasons and the
verified official withdrawals (GROWTH-3; G94).

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
    an official confirmation is cited (F2/F3). Excerpts are compared by the structured fact
    `excerpt_norm_sha256` stored with each row (G68, lib.evidence_facts); a cited row without a
    usable fact leaves the entry unsupported;
  * an official confirmation names a stored record whose captured official notes contain the
    statement verbatim, so it can be re-checked rather than trusted. It names the record by its FULL
    identity: product_id, update_version and, for a build-keyed record (every Windows and PowerPoint
    record), target_build (G84, D-1). Without the build the lookup asked for a blank-build record no
    such product has, so a true confirmation made a supported entry unsupported. A confirmation that
    names no build looks up the blank-build record, exactly as before;
  * WAIT needs reason_class `regression`, the version transition, a written material impact and
    `new_in_this_version: true` (F4/F5). A persistent problem is never a regression.

ONE CONTRACT FOR EVERY REASON (G84, H-1). A reason the producer drafted (lib/verdict_reason_producer;
no person reviewed it) meets these same checks before `decide` may read it: `machine_schema_errors`
is `schema_errors` with one difference -- in place of a person's `reviewed_at` and `basis`, its basis
is `automatic:<rule version>`, the producer version named in its own `producer` block, and it may
carry the producer's provenance keys -- and then `support_problems` against the counted rows of its
own page. lib/verdict_projection refuses a candidate that fails either one and reports it with the
unsupported entries. Until G84 the candidates skipped both, so with the activation switch on a WAIT
citing no counted row reached the page.

THE LIFECYCLE FILE holds one entry today: KB5079391, which Microsoft withdrew for new installations,
replaced by KB5086672. It is NOT the lifecycle mechanism: the general "newer update available" links
wait for the Microsoft KB source assessment and a deterministic source-to-record writer.
`lifecycle_errors` refuses a matching field (product_id, kb, relationship, a build) that is not a plain
unpadded string (GROWTH-3 review 2, LOW-1), and any malformed entry refuses the whole file (fail closed,
a QA error).

EVERY WITHDRAWAL IS KEPT (G94, AUX-131). Until G94 `lifecycle_errors` also refused a SECOND entry
(`MAX_LIFECYCLE_ENTRIES = 1`) -- any second entry, valid or not, on another release or the same one. A
refused file supports nothing, so recording a second official withdrawal took the first one's AVOID off
both KB5079391 pages in the projection and in both record writers, and QA's patch_lifecycle_invalid
blocked every deploy and every writeback lane until it was removed: a later withdrawal could never be
recorded. The cap is gone; every entry still passes every per-entry check, and adding one is still a
reviewed pull request. Which entry a page rests on when two withdraw the same release is
lib/patch_decision.lifecycle_for's (the earliest verified; file order decides nothing).

This module reads YAML and nothing else (plus lib.evidence_facts, which is pure): no collector import, no
network.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from . import evidence_facts

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
# Exactly what Liquid's `| strip` removes (Ruby String#strip): ASCII whitespace and NUL, nothing else.
# Python's str.strip() also removes Unicode spaces (U+00A0, U+2009, U+3000, U+0085, U+001C..U+001F),
# which is how QA once modelled a page key the gate never builds (PR-A2 review, LOW-1).
LIQUID_STRIP_CHARS = " \t\n\v\f\r\x00"
IDENTITY_FIELDS = ("product_id", "update_version", "target_build")

REQUIRED_REASON_KEYS = ("id", "product_id", "update_version", "verdict", "reason_class", "scope",
                        "evidence", "reason", "new_in_this_version", "reviewed_at", "basis")
ALLOWED_REASON_KEYS = frozenset(REQUIRED_REASON_KEYS + (
    "target_build", "official_confirmation", "fixed_in", "transition", "material"))
# THE MACHINE SCHEMA (G84, H-1): what a producer candidate must carry to be read like a reviewed entry. The
# reviewed keys, except that nobody reviewed it: no `reviewed_at` (it may not claim one), and its basis is
# `automatic:<rule version>`, taken from the `producer` block every candidate carries (`machine_basis`). The
# provenance keys below are what lib/verdict_reason_producer._candidate writes beside them; no decision reads
# them, and they are allowed so a candidate is checked exactly as produced, never reshaped first.
MACHINE_BASIS_PREFIX = "automatic:"
MACHINE_BASIS_RE = re.compile(r"^automatic:[0-9A-Za-z][0-9A-Za-z._-]*$", re.ASCII)
MACHINE_PROVENANCE_KEYS = frozenset({"candidate_key", "citation", "failure", "page", "problem_key", "producer",
                                     "severity_basis", "independence_basis"})
MACHINE_REQUIRED_REASON_KEYS = tuple(k for k in REQUIRED_REASON_KEYS if k not in ("reviewed_at", "basis")) + (
    "producer",)
MACHINE_ALLOWED_REASON_KEYS = (ALLOWED_REASON_KEYS - {"reviewed_at"}) | MACHINE_PROVENANCE_KEYS
REQUIRED_LIFECYCLE_KEYS = ("id", "product_id", "kb", "builds", "relationship", "replacement_kb",
                           "released", "replacement_released", "official_url", "verified_at")
# PROVENANCE (G66). Which copy of the official statement the entry was verified from, so a later
# permitted re-read can prove the statement is unchanged without the repository keeping the page:
# the sha256 of the retrieved file, the sha256 of the matched statement (normalisation stated in
# _data/patch_lifecycle.yml) and the UTC retrieval time. Hashes and a timestamp, never vendor text.
# OPTIONAL, so adding them changes no decision; when present they must be well formed, like every
# other value here, and test_growth3_verdict_policy pins that the shipped entry carries all three.
# A hash records WHICH text supported the decision; it does not by itself show the decision is right.
LIFECYCLE_PROVENANCE_KEYS = ("source_sha256", "statement_sha256", "source_retrieved_at")
ALLOWED_LIFECYCLE_KEYS = frozenset(REQUIRED_LIFECYCLE_KEYS + ("replacement_builds",) + LIFECYCLE_PROVENANCE_KEYS)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
UTC_TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$", re.ASCII)


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
# G38 WS2 review 2, LOW-2: characters OUTSIDE those categories print as nothing too -- U+FE0F (a variation
# selector, Mn), U+034F (combining grapheme joiner, Mn), U+3164 / U+115F / U+1160 / U+FFA0 (Hangul fillers,
# Lo) -- and each one reproduced P6 (the reviewed TEST FIRST vanished, QA exit 0). The rule now also covers
# EVERY Unicode Default_Ignorable_Code_Point (DerivedCoreProperties.txt, Unicode 16.0; reserved code points
# in its ranges included), the Hangul fillers by name, and U+2800 BRAILLE PATTERN BLANK (So, prints blank).
DEFAULT_IGNORABLE_RANGES = (
    (0x00AD, 0x00AD), (0x034F, 0x034F), (0x061C, 0x061C), (0x115F, 0x1160), (0x17B4, 0x17B5), (0x180B, 0x180F),
    (0x200B, 0x200F), (0x202A, 0x202E), (0x2060, 0x206F), (0x3164, 0x3164), (0xFE00, 0xFE0F), (0xFEFF, 0xFEFF),
    (0xFFA0, 0xFFA0), (0xFFF0, 0xFFF8), (0x1BCA0, 0x1BCA3), (0x1D173, 0x1D17A), (0xE0000, 0xE0FFF))
HANGUL_FILLERS = frozenset({0x115F, 0x1160, 0x3164, 0xFFA0})
BLANK_SYMBOLS = frozenset({0x2800})
# In update_version only, a changelog title may carry an emoji sequence ("🛠️", "👩‍💻"): U+FE0F (emoji
# presentation) right after an emoji, and U+200D (zero-width joiner) between two emoji, are part of the
# visible glyph there. Anywhere else -- and in product_id and target_build always -- they are invisible.
EMOJI_SEQUENCE_JOINERS = frozenset({0xFE0F, 0x200D})


def _default_ignorable(cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in DEFAULT_IGNORABLE_RANGES) or cp in HANGUL_FILLERS or cp in BLANK_SYMBOLS


def _invisible(ch: str) -> bool:
    category = unicodedata.category(ch)
    return (category in INVISIBLE_IDENTITY_CATEGORIES or (category == "Zs" and ch != " ")
            or _default_ignorable(ord(ch)))


def _emoji_base(ch: str) -> bool:
    """An emoji a variation selector or a joiner may follow: a pictographic symbol (So), a skin-tone modifier
    (Sk, U+1F3FB..U+1F3FF), or a regional-indicator letter."""
    cp = ord(ch)
    return ((unicodedata.category(ch) == "So" and cp not in BLANK_SYMBOLS) or 0x1F3FB <= cp <= 0x1F3FF
            or 0x1F1E6 <= cp <= 0x1F1FF)


def _in_emoji_sequence(text: str, i: int) -> bool:
    """Whether text[i] (U+FE0F or U+200D) belongs to a visible emoji sequence: U+FE0F right after an emoji (or
    after a keycap base 0-9 # * that U+20E3 follows); U+200D after an emoji (or its U+FE0F) AND before one."""
    cp = ord(text[i])
    prev = text[i - 1] if i > 0 else ""
    nxt = text[i + 1] if i + 1 < len(text) else ""
    if cp == 0xFE0F:
        return bool(prev) and (_emoji_base(prev) or (prev in "0123456789#*" and nxt == "⃣"))
    if cp == 0x200D:
        before = text[i - 2] if prev == "️" and i > 1 else prev
        return bool(before) and bool(nxt) and _emoji_base(before) and _emoji_base(nxt)
    return False


def identity_invisible_problems(record: Mapping[str, Any]) -> list[str]:
    """Identity fields that carry an invisible or control character, or [].

    Read on the value the page key is built from (`liquid_strip`), with leading and trailing Unicode
    whitespace also set aside: that is padding, which `identity_padding_problems` reports. What is left
    must contain no character of INVISIBLE_IDENTITY_CATEGORIES, no space separator other than a plain
    space, and no Default_Ignorable_Code_Point, Hangul filler or blank symbol (DEFAULT_IGNORABLE_RANGES) --
    in product_id and target_build without exception; in update_version a U+FE0F or U+200D inside an emoji
    sequence of a changelog title is visible and allowed (`_in_emoji_sequence`). A legitimate Unicode title
    (a curly apostrophe, an em dash, a trade-mark sign, an emoji) passes: those are printable. QA
    --publish-strict reports a finding as `record_identity_invisible_character`."""
    problems = []
    for field in IDENTITY_FIELDS:
        raw = record.get(field)
        if raw is None:
            continue
        text = liquid_strip(raw).strip()
        found = sorted({ch for i, ch in enumerate(text) if _invisible(ch)
                        and not (field == "update_version" and ord(ch) in EMOJI_SEQUENCE_JOINERS
                                 and _in_emoji_sequence(text, i))})
        if found:
            names = ", ".join(f"U+{ord(ch):04X} {unicodedata.name(ch, unicodedata.category(ch))}" for ch in found)
            problems.append(f"{field} {text!r} contains an invisible or control character ({names})")
    return problems


def schema_errors(entries: Iterable[Mapping[str, Any]]) -> list[str]:
    """Structural problems in the reasons file. Static: independent of the evidence store."""
    return _schema_errors(entries, machine=False)


def machine_basis(entry: Mapping[str, Any]) -> str:
    """The basis of a reason no person reviewed: `automatic:<rule version>`, the producer version its own
    `producer` block names, or "" when it names none (then `machine_schema_errors` refuses it)."""
    producer = entry.get("producer")
    version = producer.get("version") if isinstance(producer, Mapping) else None
    return f"{MACHINE_BASIS_PREFIX}{version.strip()}" if isinstance(version, str) and version.strip() else ""


def machine_schema_errors(entries: Iterable[Any]) -> list[str]:
    """Structural problems in automatically drafted reasons (producer candidates), checked as produced.

    THE SAME CHECKS AS `schema_errors` (G84, H-1): the same verdicts, reason classes, scope rule, one-line
    reason, cited evidence rows, official-confirmation shape and every WAIT fact (regression, transition,
    material impact, new in this version). Only the review fields differ: a machine entry carries no
    `reviewed_at`, and its basis is `machine_basis` -- `automatic:<rule version>` -- which must be well formed
    (and equal to `basis` if it states one). A value that is not a mapping is refused, never read."""
    return _schema_errors(entries, machine=True)


def _schema_errors(entries: Iterable[Any], *, machine: bool) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    required = MACHINE_REQUIRED_REASON_KEYS if machine else REQUIRED_REASON_KEYS
    allowed = MACHINE_ALLOWED_REASON_KEYS if machine else ALLOWED_REASON_KEYS
    for index, entry in enumerate(entries):
        if machine and not isinstance(entry, Mapping):
            errors.append(f"entries[{index}]: not a mapping")
            continue
        label = _s(entry.get("id")) or f"entries[{index}]"
        missing = [k for k in required if k not in entry]
        if missing:
            errors.append(f"{label}: missing {missing}")
            continue
        unknown = sorted(set(entry) - allowed)
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
        for field in ("product_id", "update_version") + (() if machine else ("reviewed_at", "basis")):
            if not _s(entry.get(field)):
                errors.append(f"{label}: {field} is empty")
        if machine:
            basis = machine_basis(entry)
            if not MACHINE_BASIS_RE.fullmatch(basis):
                errors.append(f"{label}: an automatic reason must name the rule version that drafted it "
                              "(basis automatic:<rule version>, from its producer block)")
            elif "basis" in entry and _s(entry.get("basis")) != basis:
                errors.append(f"{label}: basis {_s(entry.get('basis'))!r} is not {basis!r}, the rule version "
                              "that drafted it")
        elif not DATE_RE.fullmatch(_s(entry.get("reviewed_at"))):
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
            elif "target_build" in conf and not isinstance(conf.get("target_build"), str):
                # G84 (D-1): the build names the confirming record, so it is compared as text. Unquoted, YAML
                # reads 26200.8110 as the number 26200.811 and the lookup would quietly miss (lifecycle N1).
                errors.append(f"{label}: official_confirmation target_build must be a quoted string, "
                              f"not a {type(conf.get('target_build')).__name__}")
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
    """Rule `excerpt-norm-1` on the row's stored text (lib.evidence_facts.normalise_excerpt). Kept for
    callers that hold the text; `support_problems` no longer reads it (G68)."""
    return evidence_facts.normalise_excerpt(row.get("report_text_excerpt"))


def _norm_ws(text: Any) -> str:
    return re.sub(r"\s+", " ", _s(text).replace("\\r", " ").replace("\\n", " "))


def confirmation_identity(conf: Mapping[str, Any]) -> tuple[str, str, str]:
    """The record an official confirmation names: (product_id, update_version, target_build), the build ""
    when it names none (G84, D-1). ONE copy: `support_problems` and the record writer that fetches the
    confirming records (apply_consensus_to_records._confirmation_records) both key on it."""
    return (_s(conf.get("product_id")), _s(conf.get("update_version")), _s(conf.get("target_build")))


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
    #
    # The excerpt comparison reads the STRUCTURED FACT written with the row (G68,
    # lib.evidence_facts.duplicate_group_key), never the stored text: with the text absent, this used
    # to see no excerpts, stop collapsing duplicates and count every URL as a reporter -- failing OPEN.
    # A cited row whose fact is missing, malformed, of an unknown version or computed under another
    # rule makes the entry unsupported. The reader never rebuilds the fact from the text.
    urls = {_s(r.get("source_url")) for r in cited}
    excerpts: set[str] = set()
    for r in cited:
        try:
            key = evidence_facts.duplicate_group_key(r)
        except evidence_facts.FactUnavailable as exc:
            problems.append(f"row {r.get('id')!r}: {exc}")
            continue
        if key is not None:
            excerpts.add(key)
    reporters = min(len(urls), len(excerpts) if excerpts else len(urls))
    conf = entry.get("official_confirmation")
    if conf:
        # The FULL identity (G84, D-1): keyed on (product, version, "") a build-keyed record was never found,
        # so a true confirmation on a Windows or PowerPoint entry REMOVED its support.
        rec = records_by_identity.get(confirmation_identity(conf))
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
    # No entry count (G94): each official withdrawal is checked on its own, and a later one is never
    # refused for being later -- that refusal emptied the file and took the earlier withdrawal with it.
    errors: list[str] = []
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
        for field in ("source_sha256", "statement_sha256"):
            if field in entry and not (isinstance(entry.get(field), str) and SHA256_RE.fullmatch(entry[field])):
                errors.append(f"{label}: {field} must be a lowercase 64-character hex sha256")
        if "source_retrieved_at" in entry and not (isinstance(entry.get("source_retrieved_at"), str)
                                                   and UTC_TIMESTAMP_RE.fullmatch(entry["source_retrieved_at"])):
            errors.append(f"{label}: source_retrieved_at must be a UTC timestamp like 2026-11-06T16:18:26Z")
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
