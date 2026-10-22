#!/usr/bin/env python3
"""Deterministic version-landing pages for build-aware products.

WHY. A build-aware product publishes one record per exact vendor build at
``/updates/<company>/<product>/<version>/<build>/``. The version-only URL one segment up is not a
patch -- it is the page that lists every build tracked under that version, and it is what an
already-published version-only link resolves to. Those pages existed only because somebody wrote
twenty of them by hand; nothing created them. The first genuinely new version therefore shipped its
build records to live URLs while its own version URL 404'd.

WHAT THIS IS NOT. It is not a patch record: it carries no ``update_entry``, so every record scanner
(discovery, QA, consensus grouping, report counts, the patch feed, homepage Patch Signals) ignores
it -- they all filter on ``update_entry`` AND glob only ``updates/generated/``, and these files live
under ``updates/<company>/<product>/``. Two independent layers of isolation, neither of which this
module touches.

IDEMPOTENCE. The rendered bytes are a pure function of the identity, with nothing time-varying in
them -- the build list is derived by the layout at render time, not baked in here. So a landing page
is written only when it is absent or its bytes actually differ, and a steady-state run rewrites
nothing. Run against the twenty hand-authored pages it produces a zero-byte diff, which is the
property that lets this land without churning history.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .normalize import slugify
from .patch_identity import is_build_aware, version_landing_path

LAYOUT = "aux-patch-version"


def landing_file_path(updates_dir: Path, company_id: Any, product_id: Any,
                      update_version: Any) -> Path:
    """Filesystem path of the landing page whose permalink is ``version_landing_path(...)``."""
    return (Path(updates_dir) / str(company_id or "").strip() / str(product_id or "").strip()
            / slugify(update_version) / "index.md")


def render_landing(company_id: Any, product_id: Any, update_version: Any,
                   product_name: Any = "") -> str:
    """The canonical landing-page source. Byte-identical to the established hand-authored shape."""
    company = str(company_id or "").strip()
    product = str(product_id or "").strip()
    version = str(update_version or "").strip()
    name = str(product_name or "").strip() or product
    permalink = version_landing_path(company, product, version)
    return (
        "---\n"
        f"layout: {LAYOUT}\n"
        f"title: {name} {version} builds\n"
        f"company_id: {company}\n"
        f"product_id: {product}\n"
        f"update_version: '{version}'\n"
        f"description: Tracked {name} builds released under version {version}.\n"
        f"permalink: {permalink}\n"
        "---\n"
    )


def ensure_version_landing(updates_dir: Path, company_id: Any, product_id: Any,
                           update_version: Any, product_name: Any = "") -> tuple[Path | None, str]:
    """Create or repair the landing page for one build-aware version.

    Returns ``(path, action)`` where action is "created" | "updated" | "unchanged" | "skipped".
    "skipped" means the product is not build-aware -- a version-only product's record already owns
    the version URL, so generating a landing page there would collide with it."""
    product = str(product_id or "").strip()
    version = str(update_version or "").strip()
    if not is_build_aware(product) or not version or not str(company_id or "").strip():
        return None, "skipped"

    path = landing_file_path(updates_dir, company_id, product, version)
    desired = render_landing(company_id, product, version, product_name)
    if path.exists():
        if path.read_text(encoding="utf-8") == desired:
            return path, "unchanged"
        path.write_text(desired, encoding="utf-8")
        return path, "updated"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(desired, encoding="utf-8")
    return path, "created"


def ensure_for_record(updates_dir: Path, record: dict[str, Any]) -> tuple[Path | None, str]:
    """``ensure_version_landing`` driven by a written record's own fields.

    Called AFTER a record is successfully written, never from adapter candidates: a landing page
    must never exist for a version that has no records."""
    return ensure_version_landing(
        updates_dir,
        record.get("company_id"),
        record.get("product_id"),
        record.get("version") or record.get("update_version"),
        record.get("software") or record.get("product_name"),
    )
