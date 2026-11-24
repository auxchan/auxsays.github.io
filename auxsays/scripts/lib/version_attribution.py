#!/usr/bin/env python3
"""Corpus guard: does a COUNTED row's own stored text agree with the version it is counted for?

THE GAP THIS CLOSES. Every wrong-version count found so far (#79, #82, AUX-108, AUX-111, AUX-118)
was found by a person reading reports. Acceptance decides on the FULL source text, once, and nothing
re-reads what was stored. This module re-reads it: for each counted row it asks three structural
questions of the text the row itself carries, and reports the rows whose answer is "no".

WHAT IT IS NOT. It is not an acceptance gate and it withdraws nothing. A stored excerpt is cut at
about 280 characters (1,166 of 1,620 counted rows end in an ellipsis), so a flag can mean "the wrong
version was counted" or "the right version sits past the cut". A flag is therefore a named, bounded
review item; a row stops counting only through the audited withdrawal path (PR #134).

THE THREE CHECKS. None adds vocabulary. Each reuses a primitive acceptance already runs.

  own_version_contradicted
      The row's own identity is in the stored text and the SHARED role authority
      (`lib.target_outcome.classify_target_outcome`) reads it as the version rolled back TO or the
      version that FIXED the problem. Same authority the OBS, Acrobat, Premiere, ComfyUI, Teams and
      NVIDIA lanes consult at acceptance, here consulted on stored text for every product.
      MEASURED AND NARROWED (12d207ba, 1,620 counted rows): with the `working` and `reference`
      outcomes included this check raised 5 flags and all 5 were wrong ("won't work", "I work in
      IT", "how do I get this to work", "working laptop", and a clause that bound to the previous
      line's version). A cue on a 280-character excerpt has no declared-version field to overrule it
      (R1), so those two outcomes are not reported. Rolled-back-to and fixed-in are.
  other_version_only
      The stored text names another TRACKED version of the same product (by the shared
      `exact_version_match`, the matcher acceptance itself uses) and names none of the row's own
      identities. Only self-identifying tokens are vocabulary: a version with a dot, or a KB number.
      A bare integer ("20", "2607") is never vocabulary, because it is also an ordinary number.
  point_release_on_line_row
      The row is counted for a bare release line ("21") and its stored text names an exact point
      release of that line ("21.1", "21.0.0.1"). The row says which release it is about; the count
      does not.

Deterministic, offline, no model. A row can carry more than one flag.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .davinci_release_line import stated_point_releases
from .target_outcome import FIXED, ROLLBACK, classify_target_outcome

FLAG_CONTRADICTED = "own_version_contradicted"
FLAG_OTHER_ONLY = "other_version_only"
FLAG_POINT_RELEASE = "point_release_on_line_row"
FLAG_ORDER = (FLAG_CONTRADICTED, FLAG_OTHER_ONLY, FLAG_POINT_RELEASE)
# The two roles the stored text can establish without a declared-version field. See the docstring.
REPORTED_ROLES = frozenset({ROLLBACK, FIXED})

# Fields a row stores about what its source said. `matched_text` / `matched_context` are the
# occurrence the matcher accepted, retained since AUX-108 precisely so a match can be audited.
TEXT_FIELDS = ("parent_title", "report_title", "report_text_excerpt", "matched_context")
# Every identity a row may have been accepted on. `matched_version` can be a product-local spelling
# ("DaVinci Resolve 21"), so it is an identity for presence but never a vocabulary token.
IDENTITY_FIELDS = ("update_version", "target_build", "matched_version", "matched_os_build",
                   "matched_kb", "matched_feature_version", "matched_text")

_BARE_LINE = re.compile(r"^\d{1,3}$")
_SELF_IDENTIFYING = re.compile(r"^(?:\d+(?:\.\d+)+|KB\d{6,8})$", re.I)
_TRUNCATED = re.compile(r"(?:\.\.\.|…)\s*$")

_VERSION_PREFIX_RE = re.compile(r"(?:^|[^A-Za-z0-9.])(?:v|ver|version|build)\.?$", re.I)


def names_version(text: str, version: str) -> bool:
    """`patch_collectors.base.exact_version_match` (same boundaries), without importing a collector.

    A copy would drift, so `test_version_attribution_guard` pins this against the shared matcher on
    every counted row's own identity and stored text.
    """
    body = text or ""
    candidate = str(version or "").strip()
    if not candidate:
        return False
    pattern = re.compile(rf"{re.escape(candidate)}(?![A-Za-z0-9])(?!\.\d)", flags=re.I)
    for hit in pattern.finditer(body):
        before = body[:hit.start()]
        if not before or _VERSION_PREFIX_RE.search(before):
            return True
        if before[-1].isdigit() or before[-1] == "." or before[-1].isalpha():
            continue
        return True
    return False


def stored_text(row: Mapping[str, Any]) -> str:
    """Everything the row itself stores about what its source said, one field per line.

    A newline is a clause boundary for the role authority, so a cue in the title cannot bind to an
    identity in the excerpt. A field repeated verbatim (title and parent title usually are) is
    read once.
    """
    seen: list[str] = []
    for name in TEXT_FIELDS:
        value = " ".join(str(row.get(name) or "").split())
        if value and value not in seen:
            seen.append(value)
    return "\n".join(seen)


def own_identities(row: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for name in IDENTITY_FIELDS:
        value = str(row.get(name) or "").strip()
        if value and value not in out:
            out.append(value)
    return out


def is_self_identifying(token: str) -> bool:
    return bool(_SELF_IDENTIFYING.match(str(token or "").strip()))


def is_release_line(version: Any) -> bool:
    return bool(_BARE_LINE.match(str(version or "").strip()))


def is_truncated(row: Mapping[str, Any]) -> bool:
    return bool(_TRUNCATED.search(str(row.get("report_text_excerpt") or "")))


@dataclass(frozen=True)
class Flag:
    code: str
    row_id: str
    product_id: str
    update_version: str
    target_build: str
    detail: str
    named: tuple[str, ...] = ()
    truncated: bool = False
    extra: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "code": self.code, "id": self.row_id, "product_id": self.product_id,
            "update_version": self.update_version, "detail": self.detail,
            "named": list(self.named), "stored_text_truncated": self.truncated,
        }
        if self.target_build:
            data["target_build"] = self.target_build
        data.update(self.extra)
        return data


def tracked_vocabulary(rows: Iterable[Mapping[str, Any]],
                       records: Iterable[Mapping[str, Any]] = ()) -> dict[str, frozenset[str]]:
    """product -> the self-identifying versions, builds and KBs this corpus tracks for it."""
    out: dict[str, set[str]] = {}
    for source in (rows, records):
        for item in source:
            product = str(item.get("product_id") or "")
            if not product:
                continue
            for name in ("update_version", "target_build", "matched_kb"):
                token = str(item.get(name) or "").strip()
                if is_self_identifying(token):
                    out.setdefault(product, set()).add(token)
    return {product: frozenset(tokens) for product, tokens in out.items()}


def counted_identities_by_url(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], frozenset[str]]:
    """(product, source URL) -> every version and build that URL is COUNTED for."""
    out: dict[tuple[str, str], set[str]] = {}
    for row in rows:
        if row.get("counted") is not True:
            continue
        key = (str(row.get("product_id") or ""), str(row.get("source_url") or "").strip())
        if not key[1]:
            continue
        for name in ("update_version", "target_build"):
            token = str(row.get(name) or "").strip()
            if token:
                out.setdefault(key, set()).add(token)
    return {key: frozenset(tokens) for key, tokens in out.items()}


def assess_row(row: Mapping[str, Any], vocabulary: frozenset[str] = frozenset(),
               counted_for: frozenset[str] = frozenset()) -> list[Flag]:
    """The flags for one row. Callers pass counted rows; the function does not look at `counted`.

    ``counted_for`` is every identity this row's source URL is counted for. When the version the
    text names already counts the same report, the flagged row is a second count of one report.
    """
    text = stored_text(row)
    product = str(row.get("product_id") or "")
    version = str(row.get("update_version") or "").strip()
    build = str(row.get("target_build") or "").strip()
    truncated = is_truncated(row)
    flags: list[Flag] = []

    def flag(code: str, detail: str, named: Iterable[str] = (), **extra: Any) -> None:
        flags.append(Flag(code, str(row.get("id") or ""), product, version, build, detail,
                          tuple(named), truncated, extra))

    # 1. The most specific identity the row is counted for, read by the shared role authority.
    specific = build or version
    if specific and not is_release_line(specific) and specific in text:
        outcome = classify_target_outcome(text, specific)
        if outcome.outcome in REPORTED_ROLES:
            flag(FLAG_CONTRADICTED,
                 f"stored text names {specific} as {outcome.outcome} ({outcome.basis})",
                 [specific], outcome=outcome.outcome, basis=outcome.basis,
                 evidence=str(outcome.excerpt)[:160])

    # 2. Another tracked version is named and none of the row's own identities is.
    identities = own_identities(row)
    own_named = any(names_version(text, identity) for identity in identities)
    if not own_named:
        own = {identity.lower() for identity in identities}
        others = sorted(token for token in vocabulary
                        if token.lower() not in own and names_version(text, token))
        # A point release of the row's own line is the third check's finding, not a foreign version.
        if is_release_line(version):
            others = [token for token in others if not token.startswith(version + ".")]
        if others:
            flag(FLAG_OTHER_ONLY,
                 "stored text names " + ", ".join(others) + " and none of the row's own identities",
                 others, also_counted_for=sorted(set(others) & counted_for))

    # 3. A release-line row whose stored text names an exact point release of that line.
    if is_release_line(version):
        points = stated_point_releases(text, version, vocabulary)
        if points:
            tracked = [p for p in points if p in vocabulary]
            flag(FLAG_POINT_RELEASE,
                 f"counted for the {version} release line; stored text names " + ", ".join(points),
                 points, tracked_point_releases=tracked,
                 also_counted_for=sorted(set(points) & counted_for))
    return flags


def assess_corpus(rows: Iterable[Mapping[str, Any]],
                  records: Iterable[Mapping[str, Any]] = ()) -> list[Flag]:
    """Flags for every counted row, in store order. ``records`` widens the tracked vocabulary."""
    rows = [row for row in rows if isinstance(row, Mapping)]
    vocabulary = tracked_vocabulary(rows, records)
    by_url = counted_identities_by_url(rows)
    flags: list[Flag] = []
    for row in rows:
        if row.get("counted") is not True:
            continue
        product = str(row.get("product_id") or "")
        key = (product, str(row.get("source_url") or "").strip())
        flags.extend(assess_row(row, vocabulary.get(product, frozenset()),
                                by_url.get(key, frozenset())))
    return flags


def summarise(flags: Iterable[Flag]) -> dict[str, Any]:
    flags = list(flags)
    by_code = {code: sum(1 for f in flags if f.code == code) for code in FLAG_ORDER}
    by_product: dict[str, dict[str, int]] = {}
    for f in flags:
        by_product.setdefault(f.product_id, {}).setdefault(f.code, 0)
        by_product[f.product_id][f.code] += 1
    return {"flags": len(flags), "rows": len({f.row_id for f in flags}), "by_code": by_code,
            "by_product": {p: dict(sorted(c.items())) for p, c in sorted(by_product.items())}}
