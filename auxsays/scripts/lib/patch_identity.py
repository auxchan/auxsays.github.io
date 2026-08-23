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
BUILD_AWARE_PRODUCTS: frozenset[str] = frozenset({"microsoft-powerpoint"})

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


def version_landing_path(company_id: Any, product_id: Any, update_version: Any) -> str:
    """The YYMM landing URL that a build-aware product's old version-only URL becomes.

    This is deliberately the SAME string a version-only product would use as its record permalink;
    for a build-aware product no record is ever published there, so the two can never collide."""
    return f"/updates/{str(company_id or '').strip()}/{str(product_id or '').strip()}/{slugify(update_version)}/"
