"""Structured evidence facts: public, derived facts every Tier 1 evidence row carries, computed when
the row is written, so a reader that compares or groups reports does not have to re-read the stored
third-party text (G68, GPT ruling P3; G1_SPEC step S0, PR A).

WHY. Five scheduled modules re-read stored report text. Two of them fail OPEN when that text is
absent. `lib.verdict_reasons.support_problems` treats two cited rows with the same excerpt as one
reporter, so with no excerpts every URL would become a reporter. The Level-3 cross-post merge treats
an empty title as "nothing to merge", so it would show one report twice. The text may not stay in
the public store (G1), so the facts those readers need are computed while the text is still in hand
and stored beside it.

THE FACTS. All are public and derived; none is a copy of the text.
  excerpt_norm_sha256  sha256 of the row's `report_text_excerpt` under rule `excerpt-norm-1`: str(),
                       strip, every whitespace run to one space, lower case (the exact normalisation
                       `verdict_reasons` compared before G68). Rows with the same value carried the
                       same stored excerpt: the "identical excerpts are one reporter" group.
  title_dedup_sha256   sha256 of the row's `report_title` under rule `title-dedup-1`: lower case,
                       whitespace runs to one space, the first 80 characters (the Level-3 cross-post
                       key in `lib.recent_reports.merge_recent_reports`).
  issue_bucket         the public issue bucket under rule `issue-bucket-1` (`compute_issue_bucket`).
                       This is now the ONE copy of the function that apply_consensus_to_records and
                       build_consensus_from_evidence used to carry as two mirrored copies.
  facts_rule_version   the rule set that computed the three. RULE_SETS names the exact rule of each
                       fact for each version.

An empty input still has a fact: the sha256 of the empty string (EMPTY_SHA256). Readers treat it as
"this row carries no excerpt / no title", exactly as the text comparisons skipped an empty string.

RELATIONSHIPS (P3: source identities, report identities, duplicate groups). The store already holds
the two identities, as public fields that sealing the text would not touch. The SOURCE identity is
the row's `source_url`, canonicalised by `lib.source_segments.report_url_key`. The REPORT identity is
`patch_collectors.base.evidence_key`: (product_id, update_version, target_build, report url). The
DUPLICATE group of the distinct-reporter rule is the excerpt fact itself (`duplicate_group_key`). So
no new identity field is needed, and none is added.

VERSIONED, NEVER SILENTLY MIXED. Each rule has a name (`excerpt-norm-1` ...). A version is never
edited after it ships. A rule change (G73 will change the capture-source bucket cues next) adds a new
version naming the new rule, and the zero-network migration (`migrate_evidence_facts.py --write`)
rewrites the facts that changed. A reader accepts a fact only when the row's version names the
CURRENT rule for that fact (`require_fact`). A missing, malformed or unknown-version value, or a value
computed under a different rule, raises FactUnavailable. Frozen vectors in
tests/test_structured_evidence_facts.py pin every rule's output, so changing a rule's behaviour
without a new version fails CI.

A HASH IS NOT A JUDGEMENT (P3 critical safeguard). Equal excerpt hashes mean equal stored excerpts.
That is exactly what the distinct-reporter rule compared before, and no more: they do not show that
two reports describe one problem, or that a version plays the same role in both. The facts replace
text EQUALITY and BUCKETING only. Version matching, attribution and full-text adjudication still read
the text, at collection time or in a replay.

FAIL CLOSED. `require_fact` and the accessors never rebuild a fact from the row's text, which may be
absent. A reader that cannot get a fact must refuse the conclusion it was about to draw (for
verdict_reasons, the entry is unsupported). It must not fall back to the text, and it must never read
a missing fact as "no duplicate".

Pure: stdlib only, plus PyYAML imported lazily by the store-text helpers used by the migration. No
network, no repository writes.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable, Mapping

EXCERPT_FACT = "excerpt_norm_sha256"
TITLE_FACT = "title_dedup_sha256"
BUCKET_FACT = "issue_bucket"
VERSION_FIELD = "facts_rule_version"
FACT_FIELDS = (EXCERPT_FACT, TITLE_FACT, BUCKET_FACT)
# The order a row carries them in: they are the last four keys of a stored row.
STORED_FIELDS = FACT_FIELDS + (VERSION_FIELD,)

# Per version, the exact rule each fact was computed under. Add a version; never edit one.
RULE_SETS: dict[str, dict[str, str]] = {
    "v1": {EXCERPT_FACT: "excerpt-norm-1", TITLE_FACT: "title-dedup-1", BUCKET_FACT: "issue-bucket-1"},
}
CURRENT_VERSION = "v1"

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
_SHA256_RE = re.compile(r"[0-9a-f]{64}", re.ASCII)

# Problem codes (`fact_problems`). Every one but `stale` means a reader cannot use the row's facts.
MISSING = "missing"
PARTIAL = "partial"
UNKNOWN_VERSION = "unknown_version"
MALFORMED = "malformed"
OUTDATED = "outdated"
STALE = "stale"


class FactUnavailable(ValueError):
    """A required structured fact is missing, malformed, of an unknown version, or computed under a
    rule other than the current one. The message names the field and the reason, never any text."""

    def __init__(self, field: str, reason: str):
        self.field = field
        self.reason = reason
        super().__init__(f"structured fact {field} unavailable ({reason})")


class FactStoreError(ValueError):
    """The store text cannot be edited safely (block layout, partial fact set, failed proof)."""


# --- the rules ------------------------------------------------------------------------------------

def normalise_excerpt(value: Any) -> str:
    """Rule `excerpt-norm-1`. Byte-identical to `verdict_reasons._norm_excerpt` before G68."""
    return re.sub(r"\s+", " ", str(value if value is not None else "").strip()).lower()


def title_dedup_key(value: Any) -> str:
    """Rule `title-dedup-1`. Byte-identical to the `merge_recent_reports` cross-post key."""
    return " ".join(str(value or "").lower().split())[:80]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_public_phrase(value: Any, *, fallback: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    text = re.sub(r"[_-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def compute_issue_bucket(product_id: str, row: Mapping[str, Any]) -> str:
    """Rule `issue-bucket-1`: the public issue bucket of one row, from its theme, workflow area and
    title. Moved here unchanged from the two mirrored copies (apply_consensus_to_records and
    build_consensus_from_evidence); both names now point at this function."""
    raw_theme = clean_public_phrase(row.get("issue_theme"))
    raw_workflow = clean_public_phrase(row.get("workflow_area"))
    raw_title = clean_public_phrase(row.get("report_title") or row.get("source_title") or row.get("parent_title"))
    text = " ".join([raw_theme, raw_workflow, raw_title]).lower()

    if product_id == "blackmagic-davinci":
        if "magic mask" in text:
            return "Magic Mask crashes"
        if "decode" in text and ("render" in text or "export" in text):
            return "render/decode failures"
        if "render" in text or "export" in text or "delivery" in text:
            return "render/export failures"
        if "crash" in text or "startup" in text or "launch" in text:
            return "startup or application crashes"
        if "performance" in text or "slow" in text:
            return "performance slowdowns"
        if "install" in text:
            return "installation problems"

    if product_id == "obs-studio":
        if "scene list" in text or ("scene" in text and "selection" in text):
            return "scene list workflow regressions"
        if "audio" in text or "mixer" in text or "monitoring" in text:
            return "audio mixer or routing issues"
        # "window" and "hang" are word-bounded: as substrings they matched "Windows" (the OS) and
        # "change"/"changing" (AUX-060).
        if "capture" in text or "camera" in text or "xcomposite" in text or "screen" in text or re.search(r"\bwindow\b", text):
            return "capture-source issues"
        if "plugin" in text or "setup" in text or "profile" in text:
            return "plugin or setup compatibility"
        if "crash" in text or "freeze" in text or re.search(r"\bhang(?:s|ing|ed)?\b", text) or "stability" in text:
            return "crash or stability problems"
        if "hotkey" in text or "shortcut" in text:
            return "keyboard shortcut regressions"
        if "output" in text or "recording" in text or "stream" in text:
            return "output or recording regressions"

    if raw_theme and raw_theme.lower() != "unspecified issue":
        return raw_theme.lower()
    if raw_workflow and not raw_workflow.lower().startswith("general "):
        return raw_workflow.lower()
    return "general workflow reports"


def compute_facts(row: Mapping[str, Any]) -> dict[str, str]:
    """The four stored fields for this row under the CURRENT rule set, from the text the row holds.

    Called only where the text is in hand: at the persistence boundary, in a replay tool that has
    just rewritten a label, and in the migration. Never by a reader."""
    return {
        EXCERPT_FACT: sha256_text(normalise_excerpt(row.get("report_text_excerpt"))),
        TITLE_FACT: sha256_text(title_dedup_key(row.get("report_title"))),
        BUCKET_FACT: compute_issue_bucket(str(row.get("product_id") or "").strip(), row),
        VERSION_FIELD: CURRENT_VERSION,
    }


def with_facts(row: Mapping[str, Any]) -> dict[str, Any]:
    """A copy of `row` with its facts computed now, as its last four keys in STORED_FIELDS order. Any
    fact the row already carried is dropped first: a writer never trusts a supplied fact."""
    out = {key: value for key, value in row.items() if key not in STORED_FIELDS}
    out.update(compute_facts(row))
    return out


def carries_facts(row: Mapping[str, Any]) -> bool:
    """Whether the row holds any of the four stored fields (a partial set included)."""
    return any(row.get(field) not in (None, "") for field in STORED_FIELDS)


def derived_fact_updates(row: Mapping[str, Any], writes: Mapping[str, Any] | None = None) -> dict[str, str]:
    """For a tool that rewrites a row's labels in place: the fact values the row must carry once
    `writes` is applied, for each one that changes. {} when the row carries no facts (adding them is
    the migration's job) or when nothing changes. A row with a PARTIAL set gets every field, so the
    tool's one-line-per-key edit refuses it rather than leaving it half-written."""
    if not carries_facts(row):
        return {}
    expected = compute_facts(dict(row, **dict(writes or {})))
    return {field: value for field, value in expected.items() if row.get(field) != value}


# --- fail-closed readers ----------------------------------------------------------------------------

def _well_formed(field: str, value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if field in (EXCERPT_FACT, TITLE_FACT):
        return bool(_SHA256_RE.fullmatch(value))
    if field == BUCKET_FACT:
        return bool(value) and value == " ".join(value.split())
    return False


def require_fact(row: Mapping[str, Any], field: str) -> str:
    """The stored value of one fact, or FactUnavailable. NEVER computed from the row's text."""
    if field not in FACT_FIELDS:
        raise KeyError(field)
    value = row.get(field)
    version = row.get(VERSION_FIELD)
    if value in (None, "") or version in (None, ""):
        raise FactUnavailable(field, MISSING)
    if not isinstance(version, str) or version not in RULE_SETS:
        raise FactUnavailable(field, UNKNOWN_VERSION)
    if RULE_SETS[version].get(field) != RULE_SETS[CURRENT_VERSION][field]:
        raise FactUnavailable(field, OUTDATED)
    if not _well_formed(field, value):
        raise FactUnavailable(field, MALFORMED)
    return value


def excerpt_key(row: Mapping[str, Any]) -> str | None:
    """The row's excerpt fact, or None when its stored excerpt was empty. Raises FactUnavailable."""
    value = require_fact(row, EXCERPT_FACT)
    return None if value == EMPTY_SHA256 else value


# The distinct-reporter rule's duplicate group: rows sharing it carried the same stored excerpt.
duplicate_group_key = excerpt_key


def title_key(row: Mapping[str, Any]) -> str | None:
    """The row's title fact, or None when its stored report_title was empty. Raises FactUnavailable."""
    value = require_fact(row, TITLE_FACT)
    return None if value == EMPTY_SHA256 else value


def stored_issue_bucket(row: Mapping[str, Any]) -> str:
    """The row's stored issue bucket. Raises FactUnavailable; never re-buckets from text."""
    return require_fact(row, BUCKET_FACT)


# --- coherence --------------------------------------------------------------------------------------

def fact_problems(row: Mapping[str, Any], *, verify: bool = True) -> list[str]:
    """Why this row's facts cannot be used, or [] when they can. Codes: `missing`, `partial`,
    `unknown_version`, `malformed:<field>`, `outdated:<field>` and, with `verify`, `stale:<field>`
    (the stored value differs from the value the row's own text gives under the current rule).

    `verify` re-reads the row's text, so it is for QA, the migration and the tests while the text is
    still stored. It is never a reader's fallback."""
    present = [field for field in STORED_FIELDS if row.get(field) not in (None, "")]
    if not present:
        return [MISSING]
    if len(present) != len(STORED_FIELDS):
        return [PARTIAL]
    version = row.get(VERSION_FIELD)
    if not isinstance(version, str) or version not in RULE_SETS:
        return [UNKNOWN_VERSION]
    problems = [f"{MALFORMED}:{field}" for field in FACT_FIELDS if not _well_formed(field, row.get(field))]
    if problems:
        return problems
    current = RULE_SETS[CURRENT_VERSION]
    problems = [f"{OUTDATED}:{field}" for field in FACT_FIELDS if RULE_SETS[version][field] != current[field]]
    if verify:
        expected = compute_facts(row)
        problems += [f"{STALE}:{field}" for field in FACT_FIELDS
                     if RULE_SETS[version][field] == current[field] and row.get(field) != expected[field]]
    return problems


def store_fact_problems(rows: Iterable[Mapping[str, Any]], *, verify: bool = True) -> dict[str, list[int]]:
    """problem code (the part before ':') -> row positions, over a whole store."""
    found: dict[str, list[int]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            found.setdefault(MALFORMED, []).append(index)
            continue
        for problem in fact_problems(row, verify=verify):
            found.setdefault(problem.split(":", 1)[0], []).append(index)
    return {code: sorted(set(indices)) for code, indices in found.items()}


# --- store text (used by migrate_evidence_facts.py) ---------------------------------------------------

_BLOCK_START = re.compile(r"^- ", re.M)


def fact_line(field: str, value: str) -> str:
    """One stored fact as the line PyYAML writes inside a row (`yaml.safe_dump(..., width=1000)`)."""
    import yaml  # noqa: PLC0415

    dumped = yaml.safe_dump({field: value}, sort_keys=False, allow_unicode=True, width=1000)
    if dumped.count("\n") != 1:
        raise FactStoreError(f"{field} does not serialise to one line")
    return "  " + dumped


def _split_blocks(text: str) -> tuple[str, list[str]]:
    starts = [m.start() for m in _BLOCK_START.finditer(text)]
    if not starts:
        return text, []
    head = text[:starts[0]]
    bounds = starts + [len(text)]
    return head, [text[bounds[i]:bounds[i + 1]] for i in range(len(starts))]


def backfill_store_text(text: str) -> tuple[str, dict[str, Any]]:
    """The store text with every row carrying current facts, and what changed.

    A row with no facts gains the four lines at the END of its own block. A row whose facts are
    complete but outdated, malformed or stale has exactly those lines rewritten in place. A row whose
    facts are current and correct keeps every byte. A partial set, or a block layout that does not
    line up with the parsed rows, raises FactStoreError and changes nothing."""
    import yaml  # noqa: PLC0415

    payload = yaml.load(text, Loader=yaml.SafeLoader)
    if not isinstance(payload, dict) or not isinstance(payload.get("evidence"), list):
        raise FactStoreError("the store is not a mapping with an evidence list")
    rows = payload["evidence"]
    head, blocks = _split_blocks(text)
    if len(blocks) != len(rows) or not head.endswith("evidence:\n"):
        raise FactStoreError(f"{len(blocks)} row blocks for {len(rows)} parsed rows")
    stats = {"rows": len(rows), "backfilled": 0, "refreshed": 0, "unchanged": 0, "refreshed_fields": {}}
    out = [head]
    for index, (block, row) in enumerate(zip(blocks, rows)):
        if not isinstance(row, dict):
            raise FactStoreError(f"row {index} is not a mapping")
        expected = compute_facts(row)
        if not carries_facts(row):
            if not block.endswith("\n"):
                block += "\n"
            block += "".join(fact_line(field, expected[field]) for field in STORED_FIELDS)
            stats["backfilled"] += 1
        elif fact_problems(row):
            if PARTIAL in fact_problems(row):
                raise FactStoreError(f"row {index} ({row.get('id')}) carries a partial fact set")
            for field in STORED_FIELDS:
                if row.get(field) == expected[field]:
                    continue
                pattern = re.compile(rf"^  {re.escape(field)}: .*\n", re.M)
                if len(pattern.findall(block)) != 1:
                    raise FactStoreError(f"row {index}: {field} is not exactly one line in its block")
                block = pattern.sub(lambda _m, f=field: fact_line(f, expected[f]), block)
                stats["refreshed_fields"][field] = stats["refreshed_fields"].get(field, 0) + 1
            stats["refreshed"] += 1
        else:
            stats["unchanged"] += 1
        out.append(block)
    return "".join(out), stats


_FACT_LINE = re.compile(r"  (?:%s): [^\n]*\n" % "|".join(re.escape(f) for f in STORED_FIELDS))


def audited_block_end(text: str, lo: int, hi: int) -> int:
    """Where the row block text[lo:hi] stops being audited content: the start of its TRAILING
    structured-fact lines, or `hi` when it has none.

    The facts are derived from the row's own text and recomputed by whoever writes it, so the audited
    withdrawal tools hash and edit the block without them, and every block hash pinned before G68 still
    holds. Only trailing lines are set aside: a fact line anywhere else stays inside the block, so the
    block no longer matches its pin and the tool refuses."""
    lines = text[lo:hi].splitlines(keepends=True)
    end = hi
    while lines and _FACT_LINE.fullmatch(lines[-1]):
        end -= len(lines.pop())
    return end


def strip_fact_lines(text: str) -> str:
    """The store text with every stored-fact line removed: equal to the pre-migration bytes when the
    migration only backfilled. The hash proof of the migration's scope."""
    pattern = re.compile(r"^  (?:%s): .*\n" % "|".join(re.escape(f) for f in STORED_FIELDS), re.M)
    return pattern.sub("", text)
