#!/usr/bin/env python3
"""Canonical AUXSAYS patch identity, with an OPTIONAL exact-build component.

Most tracked products identify a patch by ``(product_id, update_version)``: one vendor version is
one patch. Microsoft 365 Apps does not work that way -- several Current Channel builds can ship
under a single YYMM version (the live Current Channel page lists three distinct builds for
PowerPoint 2603), so a YYMM alone is not a patch identity for those products. Keying anything by
version alone there silently merges two different patches: the second generated record overwrites
the first in a ``dict[(product_id, version)]``, both share one public URL, and evidence for one
build lands on the other.

This module is the single authority for that distinction. The identity is ALWAYS the triple

    (product_id, update_version, target_build)

but ``target_build`` is the empty string for every product that has no build contract. That keeps
one shared key shape across the repo while leaving existing products semantically untouched: a
constant empty third slot cannot merge two previously distinct keys, nor split one previously
shared key, so every existing grouping, count and dedup decision is preserved exactly.

Adding a product to ``BUILD_AWARE_PRODUCTS`` is therefore the ONLY switch that turns exact-build
identity on, and it is deliberately explicit -- never inferred from whether a record happens to
carry a ``target_build`` field. Several non-Microsoft records carry build-ish metadata without a
build-identity contract, and inferring from field presence would silently re-key them.

FAIL-CLOSED. For a build-aware product, an operation that needs exact patch identity must refuse
when the build is missing rather than fall back to version-only. ``require_build`` raises
``MissingBuildIdentity`` for exactly that; there is no version-only fallback path for a
build-aware product anywhere in this module.
"""
from __future__ import annotations

from typing import Any, Mapping

try:  # normal package import
    from .normalize import slugify
except ImportError:  # pragma: no cover - direct-script import path used by some callers
    from normalize import slugify  # type: ignore

# Products whose patch identity REQUIRES an exact vendor build. Explicit allowlist, never inferred.
BUILD_AWARE_PRODUCTS: frozenset[str] = frozenset({
    "microsoft-powerpoint",
    # Windows 11: one record is one CUMULATIVE UPDATE inside a servicing train, and several
    # cumulative updates ship under one feature version (25H2 alone shipped 26200.8737,
    # .8973, .9168 and .9278 in three months). Keyed by version alone they collide exactly as
    # this module warns -- and they did: a single mutating 25H2 record rolled its target KB
    # forward monthly, so 34 of 38 counted community reports described superseded updates
    # that had no page, and the live page asserted two different "latest OS build" values.
    "microsoft-windows-11",
})

# Field names that carry the exact build on a record's front matter / an evidence row.
BUILD_FIELD = "target_build"


class MissingBuildIdentity(Exception):
    """A build-aware product reached an exact-identity operation without an exact build.

    Carries the product and version so a production run can report WHICH patch could not be
    identified without guessing a build for it."""

    def __init__(self, product_id: str, update_version: str, detail: str = "") -> None:
        self.product_id = str(product_id or "")
        self.update_version = str(update_version or "")
        self.detail = detail
        msg = f"build-aware product '{self.product_id}' has no exact {BUILD_FIELD} for version '{self.update_version}'"
        super().__init__(f"{msg}: {detail}" if detail else msg)


def is_build_aware(product_id: Any) -> bool:
    """True when this product's patch identity requires an exact build."""
    return str(product_id or "").strip() in BUILD_AWARE_PRODUCTS


def normalize_build(value: Any) -> str:
    return str(value or "").strip()


def identity_build(source: Mapping[str, Any], product_id: Any = None) -> str:
    """The build component for ``source`` -- '' for any product without a build contract.

    ``source`` is a generated record's front matter or a structured evidence row. A non-build-aware
    product returns '' even when the mapping carries a ``target_build`` value, so unrelated build
    metadata can never re-key an existing product."""
    pid = product_id if product_id is not None else source.get("product_id")
    if not is_build_aware(pid):
        return ""
    return normalize_build(source.get(BUILD_FIELD))


def patch_key(product_id: Any, update_version: Any, target_build: Any = "") -> tuple[str, str, str]:
    """The canonical identity triple. The build slot is '' unless the product is build-aware."""
    pid = str(product_id or "").strip()
    version = str(update_version or "").strip()
    build = normalize_build(target_build) if is_build_aware(pid) else ""
    return (pid, version, build)


def key_from(source: Mapping[str, Any]) -> tuple[str, str, str]:
    """``patch_key`` read straight off a record's front matter or an evidence row."""
    pid = str(source.get("product_id") or "").strip()
    return patch_key(pid, source.get("update_version"), source.get(BUILD_FIELD))


def require_build(product_id: Any, update_version: Any, target_build: Any = "",
                  detail: str = "") -> str:
    """Return the exact build, or raise for a build-aware product that has none.

    Non-build-aware products return '' and never raise -- their identity is complete without a
    build. This is the fail-closed gate: callers that need exact identity call this instead of
    silently degrading to a version-only key."""
    pid = str(product_id or "").strip()
    if not is_build_aware(pid):
        return ""
    build = normalize_build(target_build)
    if not build:
        raise MissingBuildIdentity(pid, update_version, detail)
    return build


def patch_display_label(update_version: Any, target_build: Any = "", product_id: Any = "") -> str:
    """How a patch NAMES ITSELF in public prose: '2607' normally, '25H2 (Build 26200.9168)' when
    build-aware.

    A build-aware product's records share a version by design, so prose keyed on the version alone
    cannot distinguish them. Measured live: four Windows 25H2 pages each said "Windows 11 25H2 has
    N user reports found" with N of 14, 10, 10 and 4, and two PowerPoint 2607 pages said 1 and 3.
    Every one of those sentences is true of its own patch and reads as a contradiction next to its
    siblings -- the reader has no way to tell that four different cumulative updates are speaking.

    Unlike ``permalink_path`` and ``record_version_slug`` this is DISPLAY, not identity, so a
    missing build degrades to the version rather than raising: prose that omits the build is
    imprecise, while refusing to render a verdict at all would withhold real decision intelligence
    over a formatting concern. The write paths that must not degrade already fail closed on their
    own."""
    version = str(update_version or "").strip()
    if not is_build_aware(product_id):
        return version
    build = normalize_build(target_build)
    return f"{version} (Build {build})" if build else version


def record_version_slug(update_version: Any, target_build: Any = "", product_id: Any = "") -> str:
    """Filename version component: '2607' normally, '2607-20228-20110' when build-aware.

    Uses the repo's shared ``slugify`` for both halves, so the dotted build follows the same
    convention every other dotted version already does (26.001.21529 -> 26-001-21529)."""
    version_slug = slugify(update_version)
    if not is_build_aware(product_id):
        return version_slug
    # WRITE PATH: a build-aware product must not be given a version-only filename. Falling back
    # here would silently produce the exact collision this identity exists to prevent -- two
    # builds under one YYMM landing on one file -- so refuse instead.
    build = require_build(product_id, update_version, target_build,
                          "record filename requires the exact build")
    return f"{version_slug}-{slugify(build)}"


def permalink_path(company_id: Any, product_id: Any, update_version: Any,
                   target_build: Any = "") -> str:
    """Canonical public URL.

    Version-only products keep the established four-segment shape
    ``/updates/<company>/<product>/<version>/``. A build-aware product gains ONE further segment
    carrying the exact build verbatim (dots preserved, matching how Microsoft writes it):
    ``/updates/microsoft/microsoft-powerpoint/2607/20228.20110/``."""
    company = str(company_id or "").strip()
    pid = str(product_id or "").strip()
    version_slug = slugify(update_version)
    if not is_build_aware(pid):
        return f"/updates/{company}/{pid}/{version_slug}/"
    # WRITE PATH: the version-only URL belongs to the version LANDING page for a build-aware
    # product. Falling back to it here would make a record claim a URL that is not its own, so
    # refuse instead.
    build = require_build(pid, update_version, target_build,
                          "record permalink requires the exact build")
    return f"/updates/{company}/{pid}/{version_slug}/{build}/"


# --- structural consistency of a written record -------------------------------------------
#
# A build-aware record states its build in three places -- the ``target_build`` field, the canonical
# permalink's build segment, and the canonical filename slug. They are produced from one identity,
# so any disagreement means the record was assembled from two different identities and is corrupt.
#
# The reason vocabulary is shared with the consensus lane's ownership validator, which delegates to
# ``build_identity_reason`` below. ONE definition of "a valid build-aware record", enforced in both
# lanes, so the two can never drift into subtly different notions of validity.
REASON_BUILD_MISSING = "record_build_missing"
REASON_PERMALINK_BUILD_MISMATCH = "record_permalink_build_mismatch"
REASON_PERMALINK_BUILD_UNEXPECTED = "record_permalink_build_unexpected"
REASON_FILENAME_BUILD_MISMATCH = "record_filename_build_mismatch"

BUILD_IDENTITY_REASONS = frozenset({
    REASON_BUILD_MISSING, REASON_PERMALINK_BUILD_MISMATCH,
    REASON_PERMALINK_BUILD_UNEXPECTED, REASON_FILENAME_BUILD_MISMATCH,
})


class InconsistentBuildIdentity(Exception):
    """A record's build, permalink and filename disagree.

    Raised on the WRITE path so an inconsistent record never reaches the canonical generated
    directory, rather than being written and detected afterwards. Carries the structured ``reason``
    so a production run can report which rule failed without guessing."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = str(reason or "")
        self.detail = detail
        super().__init__(f"{self.reason}: {detail}" if detail else self.reason)


def permalink_build_segment(permalink: Any) -> str:
    """The exact-build segment of a build-aware permalink, or '' when the path carries none.

    A canonical record permalink is ``/updates/<company>/<product>/<version>/`` for a version-only
    product and one segment longer for a build-aware one. Anything that is not exactly five clean
    segments carries no build segment as far as this function is concerned; callers that need the
    stricter shape/ownership rules apply them separately."""
    text = str(permalink or "").split("?", 1)[0].split("#", 1)[0]
    segments = [seg for seg in text.split("/") if seg]
    if len(segments) != 5 or segments[0] != "updates":
        return ""
    return segments[4]


def build_identity_reason(product_id: Any, update_version: Any, target_build: Any,
                          permalink: Any, filename: Any = "") -> str:
    """'' when the record's build identity is internally consistent, else the reason it is not.

    ``filename`` is optional: pass it to also verify the canonical filename slug carries this
    record's own build. A non-build-aware product must carry NO build segment -- otherwise it would
    be claiming a URL shape whose extra segment nothing owns."""
    pid = str(product_id or "").strip()
    build = normalize_build(target_build)
    permalink_build = permalink_build_segment(permalink)

    if not is_build_aware(pid):
        return REASON_PERMALINK_BUILD_UNEXPECTED if permalink_build else ""
    if not build:
        return REASON_BUILD_MISSING
    if permalink_build != build:
        return REASON_PERMALINK_BUILD_MISMATCH
    name = str(filename or "").strip()
    if name and record_version_slug(update_version, build, pid) not in name:
        return REASON_FILENAME_BUILD_MISMATCH
    return ""


def assert_build_identity(product_id: Any, update_version: Any, target_build: Any,
                          permalink: Any, filename: Any = "", detail: str = "") -> None:
    """Fail closed when a record's build identity is inconsistent."""
    reason = build_identity_reason(product_id, update_version, target_build, permalink, filename)
    if reason:
        raise InconsistentBuildIdentity(
            reason,
            detail or f"{product_id} {update_version} build={normalize_build(target_build)!r} "
                      f"permalink={str(permalink)!r} filename={str(filename)!r}")


def version_landing_path(company_id: Any, product_id: Any, update_version: Any) -> str:
    """The YYMM landing URL that a build-aware product's old version-only URL becomes.

    This is deliberately the SAME string a version-only product would use as its record permalink;
    for a build-aware product no record is ever published there, so the two can never collide."""
    return f"/updates/{str(company_id or '').strip()}/{str(product_id or '').strip()}/{slugify(update_version)}/"
