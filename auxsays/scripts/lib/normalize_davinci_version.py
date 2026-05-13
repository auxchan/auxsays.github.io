"""DaVinci Resolve version string normalizer.

Strips Blackmagic product-name prefixes and normalizes version strings to a
canonical form that matches AUXSAYS generated record update_version values.

This module is importable and has no side-effects on import. It does not
modify any files. It does not interact with OBS, Premiere Pro, or any other
product — all logic is gated behind the blackmagic-davinci product_id.

Public API:
    normalize_davinci_version(raw: str) -> dict
    is_same_version(a: str, b: str) -> bool
    canonical_to_record_key(canonical: str) -> tuple[str, str]
"""
from __future__ import annotations

import re
from typing import Any

PRODUCT_ID = "blackmagic-davinci"

# Product-name prefixes to strip, ordered longest-first to prevent partial match.
_PREFIXES: list[str] = [
    "davinci resolve studio ",
    "davinci resolve ",
    "davinci ",
    "resolve ",
]

# Stable version: optional v-prefix, major, optional .minor, optional .patch
# Anchored — must match the entire string after prefix stripping.
_STABLE_RE = re.compile(
    r"^v?(\d+)(?:\.(\d+)(?:\.(\d+))?)?$",
    re.IGNORECASE,
)

# Beta version variants:
#   "21 Public Beta 1"   → groups: major=21, beta_n=1
#   "21 Beta 1"          → groups: major=21, beta_n=1
#   "21.0 Public Beta 1" → groups: major=21, minor=0, beta_n=1
#   "21b1"               → groups: major=21, beta_n=1
#   "21 Beta1"           → groups: major=21, beta_n=1
_BETA_RE = re.compile(
    r"^v?(\d+)(?:\.(\d+)(?:\.(\d+))?)?"
    r"(?:"
    r"\s+(?:public\s+)?beta\s+(\d+)"   # "Public Beta 1" or "Beta 1"
    r"|[- ]?b(\d+)"                    # "b1" or "-b1"
    r"|\s+(?:public\s+)?beta(\d+)"     # "beta1" (no space before number)
    r")$",
    re.IGNORECASE,
)

# Ambiguous beta — has beta keyword but no number.
_AMBIGUOUS_BETA_RE = re.compile(
    r"^v?(\d+)(?:\.(\d+))?(?:\s+(?:public\s+)?beta|[- ]?b)$",
    re.IGNORECASE,
)

# DR-prefix abbreviation: "DR21", "DR 21"
_DR_PREFIX_RE = re.compile(r"^dr\s*\d", re.IGNORECASE)

# Wildcard component: "21.x", "21.x.x"
_WILDCARD_RE = re.compile(r"\.x\b", re.IGNORECASE)

# Studio-only suffix (version already stripped of product prefix but "Studio" remained)
_STUDIO_SUFFIX_RE = re.compile(r"\bstudio\b", re.IGNORECASE)


def _strip_prefix(raw: str) -> str:
    """Strip Blackmagic product-name prefix from a raw version string."""
    lower = raw.lower()
    for prefix in _PREFIXES:
        if lower.startswith(prefix):
            return raw[len(prefix):]
    return raw


def _beta_aliases(major: int, beta_num: int) -> list[str]:
    """Return known community alias forms for a given beta release."""
    return [
        f"{major} Public Beta {beta_num}",
        f"DaVinci Resolve {major} Public Beta {beta_num}",
        f"DaVinci Resolve Studio {major} Public Beta {beta_num}",
        f"Resolve {major} Public Beta {beta_num}",
        f"{major} Beta {beta_num}",
        f"DaVinci Resolve {major} Beta {beta_num}",
        f"Resolve {major} Beta {beta_num}",
        f"{major}b{beta_num}",
        f"Resolve {major}b{beta_num}",
        f"DaVinci Resolve {major}b{beta_num}",
    ]


def _stable_aliases(major: int, minor: str | None, patch: str | None) -> list[str]:
    """Return known alias forms for a stable release."""
    if minor is None:
        ver = str(major)
    elif patch is None:
        ver = f"{major}.{minor}"
    else:
        ver = f"{major}.{minor}.{patch}"
    return [
        ver,
        f"DaVinci Resolve {ver}",
        f"DaVinci Resolve Studio {ver}",
        f"Resolve {ver}",
        f"Resolve Studio {ver}",
        f"DaVinci {ver}",
        f"v{ver}",
    ]


def _rejected(raw: str, reason: str) -> dict[str, Any]:
    return {
        "product_id": None,
        "canonical_update_version": None,
        "is_beta": None,
        "beta_number": None,
        "major_version": None,
        "minor_version": None,
        "confidence": "rejected",
        "rejected": True,
        "rejection_reason": reason,
        "normalized_aliases": [],
        "_raw_input": raw,
    }


def normalize_davinci_version(raw: str) -> dict[str, Any]:
    """Normalize a raw DaVinci Resolve version string.

    Args:
        raw: Any string that may describe a DaVinci Resolve version, such as
             "DaVinci Resolve 21 Public Beta 1", "21b1", "Resolve 21", "21.0.0".

    Returns:
        A dict with keys:
            product_id               str or None
            canonical_update_version str or None — matches update_version in generated records
            is_beta                  bool or None
            beta_number              int or None
            major_version            int or None
            minor_version            str or None  — e.g. "0" or "0.1"
            confidence               "high" | "medium" | "low" | "rejected"
            rejected                 bool
            rejection_reason         str or None
            normalized_aliases       list[str]
            _raw_input               str
    """
    if not raw or not isinstance(raw, str):
        return _rejected(str(raw) if raw is not None else "", "empty_or_invalid_input")

    stripped = _strip_prefix(raw.strip())

    # Reject DR-prefix abbreviations: "DR21", "DR 21"
    if _DR_PREFIX_RE.match(stripped):
        return _rejected(raw, "abbreviation_dr_ambiguous")

    # Reject wildcard versions: "21.x", "21.x.x"
    if _WILDCARD_RE.search(stripped):
        return _rejected(raw, "wildcard_version")

    # Reject Studio-only suffix that survived prefix stripping (e.g., "21 Studio")
    # — "Studio" is a pricing tier, not a version qualifier, and appears after major only.
    studio_check = _STUDIO_SUFFIX_RE.sub("", stripped).strip()
    if studio_check != stripped and not stripped.lower().replace("studio", "").strip():
        return _rejected(raw, "studio_tier_not_a_version")

    # Reject ambiguous beta (beta keyword present but no number).
    if _AMBIGUOUS_BETA_RE.match(stripped):
        return _rejected(raw, "ambiguous_beta_no_number")

    # Try beta match first (must come before stable to avoid "21.0" matching beta).
    beta_m = _BETA_RE.match(stripped)
    if beta_m:
        major = int(beta_m.group(1))
        minor = beta_m.group(2)
        patch = beta_m.group(3)
        # Beta number may be in group 4, 5, or 6 depending on which branch matched.
        beta_num: int | None = None
        for g in (4, 5, 6):
            if beta_m.group(g) is not None:
                beta_num = int(beta_m.group(g))
                break
        if beta_num is None:
            return _rejected(raw, "ambiguous_beta_no_number")

        # Canonical: "{major} Public Beta {N}"  — matches existing record update_version
        canonical = f"{major} Public Beta {beta_num}"
        minor_version: str | None = None
        if minor is not None:
            minor_version = f"{minor}.{patch}" if patch is not None else minor

        return {
            "product_id": PRODUCT_ID,
            "canonical_update_version": canonical,
            "is_beta": True,
            "beta_number": beta_num,
            "major_version": major,
            "minor_version": minor_version,
            "confidence": "high",
            "rejected": False,
            "rejection_reason": None,
            "normalized_aliases": _beta_aliases(major, beta_num),
            "_raw_input": raw,
        }

    # Try stable match.
    stable_m = _STABLE_RE.match(stripped)
    if stable_m:
        major = int(stable_m.group(1))
        minor = stable_m.group(2)
        patch = stable_m.group(3)

        if minor is None:
            canonical = str(major)
            minor_version = None
        elif patch is None:
            canonical = f"{major}.{minor}"
            minor_version = minor
        else:
            canonical = f"{major}.{minor}.{patch}"
            minor_version = f"{minor}.{patch}"

        return {
            "product_id": PRODUCT_ID,
            "canonical_update_version": canonical,
            "is_beta": False,
            "beta_number": None,
            "major_version": major,
            "minor_version": minor_version,
            "confidence": "high",
            "rejected": False,
            "rejection_reason": None,
            "normalized_aliases": _stable_aliases(major, minor, patch),
            "_raw_input": raw,
        }

    return _rejected(raw, "unrecognized_version_format")


def is_same_version(a: str, b: str) -> bool:
    """Return True if two raw version strings normalize to the same canonical form."""
    result_a = normalize_davinci_version(a)
    result_b = normalize_davinci_version(b)
    if result_a["rejected"] or result_b["rejected"]:
        return False
    return result_a["canonical_update_version"] == result_b["canonical_update_version"]


def canonical_to_record_key(canonical: str) -> tuple[str, str]:
    """Return the (product_id, update_version) key used in generated records.

    This is the key used for matching evidence rows to generated Markdown records.
    The update_version in the key is the canonical form as produced by
    normalize_davinci_version(). It is NOT re-normalized here — the caller must
    ensure canonical is already in canonical form.
    """
    return (PRODUCT_ID, canonical)
