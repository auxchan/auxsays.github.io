"""NVIDIA desktop driver identity: which driver FAMILY a listing or a report belongs to.

TWO PRODUCTS, NEVER ONE. GeForce Game Ready and NVIDIA Studio drivers are separate products with
separate records. They share version strings: 621.14 and 621.24 each shipped as BOTH families on the
same day, under different NVIDIA download ids (Game Ready 283968 / 285320, Studio 283966 / 285317).
A version number therefore never identifies a family on its own, and the patch identity is always
``(product_id, update_version)`` with the family carried by the product id.

NVIDIA App has its own version line and is not one of these products. Nothing here may attribute an
App release or report to a driver family.

TWO RULES LIVE HERE, and both fail closed:

* ``listing_matches`` -- an official listing row belongs to a family only when NVIDIA's own NAME for
  the row is that family's exact name AND the row's own Studio flag agrees with it AND it is a stable
  desktop DCH package (and, for Game Ready, WHQL-certified). Any other name -- a hotfix, a beta, a
  name this module has never seen -- matches nothing. Nothing is inferred from a version, a URL or
  a file name.

* ``report_family`` -- the contract for any future NVIDIA user-report path. A report naming only
  "621.14" belongs to neither family unless the family is named in the report, or the parent thread
  is that family's own release-feedback thread. An explicit mention of the OTHER family vetoes: a
  Studio-named report inside a Game Ready feedback thread is attributed to nothing, never silently to
  the thread. A report naming both families is attributed to nothing. Nothing collects NVIDIA user
  reports today; this rule exists so the first path that does inherits it instead of re-deriving it
  (the Acrobat shared-build lesson: widening WHO a report can belong to widens WHAT gets counted).
"""
from __future__ import annotations

import re
from typing import Any, Mapping

GAME_READY = "nvidia-geforce-game-ready"
STUDIO = "nvidia-studio-driver"

# NVIDIA's own wording, compared EXACTLY after URL-decoding. `up_crd` is the value of the lookup's
# family query parameter; `is_crd` is the row's own Studio flag, which must agree with the query.
FAMILIES: dict[str, dict[str, Any]] = {
    GAME_READY: {
        "listing_name": "GeForce Game Ready Driver",
        "label": "GeForce Game Ready",
        "up_crd": "0",
        "is_crd": "0",
        # Every Game Ready row the lookup returns carries IsWHQL "1"; a row that does not is a beta
        # or preview build and is skipped.
        "require_whql": True,
    },
    STUDIO: {
        "listing_name": "NVIDIA Studio Driver",
        "label": "NVIDIA Studio",
        "up_crd": "1",
        "is_crd": "1",
        # Measured 2026-11-19: every Studio row returns IsWHQL "0", although its installer file name
        # says whql. Requiring the flag would skip every Studio driver, so it is reported as returned
        # and never used to accept or reject a Studio row.
        "require_whql": False,
    },
}

DRIVER_PRODUCTS = frozenset(FAMILIES)


def family(product_id: Any) -> dict[str, Any] | None:
    return FAMILIES.get(str(product_id or "").strip())


def listing_matches(product_id: Any, info: Mapping[str, Any]) -> tuple[bool, str]:
    """Does this decoded listing row belong to ``product_id``? Returns ``(ok, reason)``.

    ``info`` is one ``downloadInfo`` object with its text fields already URL-decoded. The reason is
    a short code, so a skipped row is counted by why it was skipped and never silently dropped.
    """
    spec = family(product_id)
    if spec is None:
        return False, "unknown_product"
    if str(info.get("Name") or "").strip() != spec["listing_name"]:
        return False, "name_not_this_family"
    if str(info.get("IsCRD") or "").strip() != spec["is_crd"]:
        return False, "studio_flag_disagrees_with_name"
    if str(info.get("IsBeta") or "").strip() != "0":
        return False, "beta"
    if str(info.get("IsDC") or "").strip() != "1":
        return False, "not_dch_package"
    if spec["require_whql"] and str(info.get("IsWHQL") or "").strip() != "1":
        return False, "not_whql"
    return True, ""


# A family is NAMED only by words that name it. "Studio" alone is not enough -- "OBS Studio 33" is a
# different product -- so Studio needs "Studio Driver", "NVIDIA Studio", "NSD" or a driver version
# right after it. "GeForce" alone names neither family: both are GeForce drivers.
_FAMILY_MENTIONS = {
    GAME_READY: re.compile(r"\bgame[\s-]*ready\b|\bgrd\b", re.I),
    STUDIO: re.compile(r"\bstudio[\s-]*drivers?\b|\bnvidia\s+studio\b|\bnsd\b"
                       r"|\bstudio\s+\d{3,4}\.\d{2}\b", re.I),
}


def families_named(text: Any) -> set[str]:
    value = str(text or "")
    return {pid for pid, pattern in _FAMILY_MENTIONS.items() if pattern.search(value)}


def report_family(text: Any, thread_family: Any = None) -> str | None:
    """The driver family a user report may be attributed to, or None. Never a guess.

    ``thread_family`` is the product id whose OWN release-feedback thread the report was posted in,
    or None for any other thread. See the module docstring for the rule.
    """
    thread = str(thread_family or "").strip() or None
    if thread is not None and thread not in FAMILIES:
        thread = None
    named = families_named(text)
    if len(named) > 1:
        return None
    if named:
        (only,) = named
        if thread is not None and only != thread:
            return None   # an explicit other-family mention vetoes the thread
        return only
    return thread
