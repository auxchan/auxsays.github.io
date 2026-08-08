#!/usr/bin/env python3
"""Semantic-ownership identity fixes for the two false positives on natural run 31015586517.

Run 31015586517 rolled back four collectors on ownership violations that were all FALSE POSITIVES:
  * obs-studio / adobe-acrobat-pro / adobe-acrobat-reader -> evidence_duplicate_url, because
    validate_evidence deduped appended evidence by source_url ALONE while the append/dedup authority
    (patch_collectors.base.evidence_key) keys on the triple (product_id, update_version,
    normalize_url(source_url)); the corpus legitimately reuses one URL across distinct (product,version).
  * blackmagic-davinci -> record_permalink_mismatch, because validate_records assumed the permalink
    product-slug equals product_id, but DaVinci publishes under BOTH /blackmagic-davinci/ and
    /davinci-resolve/.

This suite proves:
  Part E (duplicate-URL identity) -- the fix accepts legitimately-shared URLs across distinct exact
    (product,version) identities while still rejecting a genuine same product+version+canonical-URL
    duplicate, and preserves every other evidence-ownership rule + the embedded_listing_report_card
    exemption unchanged.
  Part F (permalink slug authority) -- an explicit per-product allowed-slug set validated by exact
    parsed path segment: DaVinci accepts both established slugs, every other product accepts only its
    own product_id, and unrelated / deceptive / spoofed / malformed slugs, wrong product, and unresolved
    versions are still rejected.
  Part D (behavioral equivalence) -- ~22 unrelated ownership scenarios still raise their identical code,
    and ONLY the two false positives change behavior.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_ownership_identity_fixes.py
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402

from lib import collector_ownership as o  # noqa: E402
from patch_collectors.base import write_front_matter_and_body  # noqa: E402

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []

# Deterministic version resolution per product (stands in for generated_records()).
VERSIONS = {
    "obs-studio": {"31.0.3", "32.2.0"},
    "adobe-acrobat-pro": {"20.004.30005"},
    "adobe-acrobat-reader": {"19.021.20047"},
    "blackmagic-davinci": {"21", "21 Public Beta 1", "20.3.3"},
    "adobe-premiere-pro": {"26.2"},
}


def check(label: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERRORS.append(label)


def expect_ok(label: str, fn) -> None:
    """Assert fn() does NOT raise OwnershipViolation (a legitimate, accepted case)."""
    try:
        fn()
        check(label, True)
    except o.OwnershipViolation as e:
        check(label, False, f"unexpected OwnershipViolation: {e.public_reason()}")


def expect_code(label: str, fn, code: str) -> None:
    """Assert fn() raises OwnershipViolation with exactly `code`."""
    try:
        fn()
        check(f"{label} -> {code}", False, "no OwnershipViolation raised")
    except o.OwnershipViolation as e:
        check(f"{label} -> {code}", e.code == code, f"got {e.code!r}")


# --- evidence helpers ----------------------------------------------------------
def ev(before_rows, after_rows) -> tuple[str, str]:
    b = yaml.safe_dump({"schema_version": 1, "evidence": before_rows}, sort_keys=False)
    a = yaml.safe_dump({"schema_version": 1, "evidence": after_rows}, sort_keys=False)
    return b, a


def erow(rid, pid, ver, url, st, matched=True, counted=True, match_basis=None):
    r = {"id": rid, "product_id": pid, "update_version": ver, "source_url": url, "source_type": st,
         "patch_version_matched": matched, "counted": counted, "sentiment": "negative"}
    if match_basis is not None:
        r["match_basis"] = match_basis
    return r


# --- record helpers ------------------------------------------------------------
def rec(gen: Path, name: str, pid: str, ver: str, permalink: str) -> Path:
    p = gen / name
    write_front_matter_and_body(p, {"update_entry": True, "product_id": pid,
                                    "update_version": ver, "permalink": permalink}, "body\n")
    return p


def run() -> int:
    o._existing_versions = lambda pid: set(VERSIONS.get(pid, set()))
    gen = Path(tempfile.mkdtemp(prefix="ownfix-")) / "generated"
    gen.mkdir()

    print("=" * 74)
    print("Ownership identity fixes: duplicate-URL (Part E) + permalink slug (Part F)")
    print("=" * 74)

    # ============================ PART E: duplicate-URL identity ============================
    print("\n-- Part E: duplicate-URL identity (validate_evidence) --")
    OBS = "obs-studio"
    U = "https://github.com/obsproject/obs-studio/issues/900"

    # E1 same product + same version + same canonical URL -> STILL rejected.
    expect_code("E1 same product+version+url still duplicate",
                lambda: o.validate_evidence(OBS, *ev(
                    [erow("a", OBS, "32.2.0", U, "github_issue")],
                    [erow("a", OBS, "32.2.0", U, "github_issue"), erow("b", OBS, "32.2.0", U, "github_issue")])),
                "evidence_duplicate_url")

    # E2 same URL across DIFFERENT versions of the same product -> ALLOWED (the false positive fixed).
    expect_ok("E2 same url across different versions of one product passes",
              lambda: o.validate_evidence(OBS, *ev(
                  [], [erow("a", OBS, "31.0.3", U, "github_issue"), erow("b", OBS, "32.2.0", U, "github_issue")])))

    # E3 same URL across DIFFERENT products -> ALLOWED (before holds another product's row w/ same URL).
    expect_ok("E3 same url across different products passes (reader vs pro isolation)",
              lambda: o.validate_evidence("adobe-acrobat-reader", *ev(
                  [erow("p", "adobe-acrobat-pro", "20.004.30005", U, "adobe_community_bug_report")],
                  [erow("p", "adobe-acrobat-pro", "20.004.30005", U, "adobe_community_bug_report"),
                   erow("r", "adobe-acrobat-reader", "19.021.20047", U, "adobe_community_bug_report")])))

    # E4 Reader mislabeled as Pro -> rejected (cross-product), proving isolation is NOT weakened.
    expect_code("E4 reader collector appending pro-labeled row rejected",
                lambda: o.validate_evidence("adobe-acrobat-reader", *ev(
                    [], [erow("x", "adobe-acrobat-pro", "20.004.30005", U, "adobe_community_bug_report")])),
                "evidence_product_mismatch")

    # E5 duplicate id (two NEW rows with the SAME (product, version, id) identity) -> still rejected.
    # (Identity is the append authority's (product_id, version, id) triple; the acrobat id encodes the
    # version, so a real duplicate has the same version too.)
    expect_code("E5 duplicate evidence id (same product+version) still rejected",
                lambda: o.validate_evidence(OBS, *ev(
                    [], [erow("dup", OBS, "32.2.0", U, "github_issue"),
                         erow("dup", OBS, "32.2.0", "https://github.com/obsproject/obs-studio/issues/901", "github_issue")])),
                "evidence_duplicate_id")

    # E6 existing row modified -> still rejected.
    expect_code("E6 existing evidence row modified still rejected",
                lambda: o.validate_evidence(OBS, *ev(
                    [erow("k", OBS, "32.2.0", U, "github_issue")],
                    [dict(erow("k", OBS, "32.2.0", U, "github_issue"), sentiment="TAMPER")])),
                "evidence_existing_row_modified")

    # E7 existing row deleted / rows removed -> still rejected.
    expect_code("E7 existing evidence row deleted still rejected",
                lambda: o.validate_evidence(OBS, *ev([erow("k", OBS, "32.2.0", U, "github_issue")], [])),
                "evidence_existing_row_deleted")

    # E8 missing source identity -> still rejected.
    expect_code("E8 appended evidence with no source_type still rejected",
                lambda: o.validate_evidence(OBS, *ev(
                    [], [erow("n", OBS, "32.2.0", U, "")])),
                "evidence_missing_source")

    # E9 unauthorized source -> still rejected.
    expect_code("E9 appended evidence with unauthorized source still rejected",
                lambda: o.validate_evidence(OBS, *ev(
                    [], [erow("n", OBS, "32.2.0", U, "reddit_community_report")])),
                "evidence_unauthorized_source")

    # E10 canonically-equivalent URLs (case + trailing slash per normalize_url) STILL collide in-identity.
    expect_code("E10 case/trailing-slash-equivalent urls still collide within one product+version",
                lambda: o.validate_evidence(OBS, *ev(
                    [erow("a", OBS, "32.2.0", "https://GitHub.com/obsproject/obs-studio/issues/900/", "github_issue")],
                    [erow("a", OBS, "32.2.0", "https://GitHub.com/obsproject/obs-studio/issues/900/", "github_issue"),
                     erow("b", OBS, "32.2.0", "https://github.com/obsproject/obs-studio/issues/900", "github_issue")])),
                "evidence_duplicate_url")

    # E11 embedded_listing_report_card exemption preserved: an embedded card is NEVER a duplicate-url,
    #     and it never blocks a later non-embedded row with the same url (mirrors append_evidence_rows).
    expect_ok("E11a embedded card with duplicate url is exempt (not rejected)",
              lambda: o.validate_evidence("adobe-premiere-pro", *ev(
                  [erow("a", "adobe-premiere-pro", "26.2", U, "adobe_community_listing_card", match_basis="embedded_listing_report_card")],
                  [erow("a", "adobe-premiere-pro", "26.2", U, "adobe_community_listing_card", match_basis="embedded_listing_report_card"),
                   erow("b", "adobe-premiere-pro", "26.2", U, "adobe_community_listing_card", match_basis="embedded_listing_report_card")])))
    expect_ok("E11b embedded card in `before` does not block a non-embedded row w/ same url",
              lambda: o.validate_evidence("adobe-premiere-pro", *ev(
                  [erow("a", "adobe-premiere-pro", "26.2", U, "adobe_community_listing_card", match_basis="embedded_listing_report_card")],
                  [erow("a", "adobe-premiere-pro", "26.2", U, "adobe_community_listing_card", match_basis="embedded_listing_report_card"),
                   erow("b", "adobe-premiere-pro", "26.2", U, "adobe_community_bug_report")])))

    # E12 the (product,version,url) tuple does NOT create a bypass: an unresolved version is still
    #     rejected regardless of URL (a generic report cannot become reusable merely via a new tuple).
    expect_code("E12 unresolved version still rejected (no tuple bypass)",
                lambda: o.validate_evidence(OBS, *ev(
                    [], [erow("n", OBS, "9.9.9", U, "github_issue")])),
                "evidence_version_unresolved")

    # ============================ PART F: permalink slug authority ============================
    print("\n-- Part F: permalink slug authority (validate_records) --")
    DV = "blackmagic-davinci"

    def check_rec(pid, name, ver, permalink, as_product=None):
        """Write a record for `pid` and return a call that validates it as `as_product` (default pid)."""
        p = rec(gen, name, pid, ver, permalink)
        collector = as_product or pid
        return lambda: o.validate_records(collector, gen, {p}, lambda q: None)

    # F1 DaVinci under /davinci-resolve/ + resolvable version -> PASSES (the fixed false positive).
    expect_ok("F1 davinci /davinci-resolve/ slug accepted",
              check_rec(DV, "f1.md", "21", "/updates/blackmagic-design/davinci-resolve/21/"))
    # F2 DaVinci under /blackmagic-davinci/ + resolvable version -> PASSES (both established slugs).
    expect_ok("F2 davinci /blackmagic-davinci/ slug accepted",
              check_rec(DV, "f2.md", "20.3.3", "/updates/blackmagic-design/blackmagic-davinci/20-3-3/"))
    # F3 DaVinci under an UNRELATED slug -> rejected.
    expect_code("F3 davinci unrelated slug rejected",
                check_rec(DV, "f3.md", "21", "/updates/blackmagic-design/some-other/21/"),
                "record_permalink_mismatch")
    # F4 a NON-davinci product using davinci-resolve -> rejected (even with a resolvable version).
    expect_code("F4 obs-studio using davinci-resolve slug rejected",
                check_rec(OBS, "f4.md", "31.0.3", "/updates/obs-project/davinci-resolve/31-0-3/"),
                "record_permalink_mismatch")
    # F5 product + exact version, own slug -> PASSES (unchanged for every non-mapped product).
    expect_ok("F5 obs-studio own slug accepted",
              check_rec(OBS, "f5.md", "31.0.3", "/updates/obs-project/obs-studio/31-0-3/"))
    # F6 malformed permalink -> rejected.
    expect_code("F6 malformed permalink rejected",
                check_rec(OBS, "f6.md", "31.0.3", "/foo/bar/"),
                "record_permalink_mismatch")
    # F7 deceptive substring look-alike slug -> rejected (exact-segment match, not substring).
    expect_code("F7 deceptive substring slug rejected",
                check_rec(DV, "f7.md", "21", "/updates/blackmagic-design/davinci-resolve-fake/21/"),
                "record_permalink_mismatch")
    # F8 slug spoofed into the wrong path position -> rejected (product slug is the 3rd segment).
    expect_code("F8 position-spoofed slug rejected",
                check_rec(DV, "f8.md", "21", "/updates/davinci-resolve/evil/21/"),
                "record_permalink_mismatch")
    # F9 wrong product (record product_id != collector) -> rejected before permalink is even consulted.
    expect_code("F9 cross-product record rejected",
                check_rec("adobe-premiere-pro", "f9.md", "26.2",
                          "/updates/adobe/adobe-premiere-pro/26-2/", as_product=OBS),
                "record_product_mismatch")
    # F10 valid slug but UNRESOLVED version -> rejected (permalink acceptance never bypasses version).
    expect_code("F10 valid davinci slug but unresolved version rejected",
                check_rec(DV, "f10.md", "99.99", "/updates/blackmagic-design/davinci-resolve/99-99/"),
                "record_version_unresolved")
    # F11 non-update file under generated/ -> rejected.
    def f11():
        p = gen / "f11.md"
        p.write_text("---\nfoo: bar\n---\nbody\n", encoding="utf-8")
        o.validate_records(OBS, gen, {p}, lambda q: None)
    expect_code("F11 non-update record rejected", f11, "record_non_update")
    # F12 undeclared deletion (mutated path does not exist) -> rejected.
    expect_code("F12 undeclared deletion rejected",
                lambda: o.validate_records(OBS, gen, {gen / "never-created.md"}, lambda q: None),
                "undeclared_deletion")

    # --- F13-F21: strict canonical-shape parsing (Part F.7 malformed/deceptive permalink matrix) ---
    # Each of these permalinks must be rejected; the parser must not repair, collapse, or smuggle.
    expect_code("F13 substring suffix slug (blackmagic-davinci-extra) rejected",
                check_rec(DV, "f13.md", "21", "/updates/blackmagic-design/blackmagic-davinci-extra/21/"),
                "record_permalink_mismatch")
    expect_code("F14 extra inserted segment rejected",
                check_rec(DV, "f14.md", "21", "/updates/x/blackmagic-design/davinci-resolve/21/"),
                "record_permalink_mismatch")
    expect_code("F15 missing product segment rejected",
                check_rec(DV, "f15.md", "21", "/updates/blackmagic-design/21/"),
                "record_permalink_mismatch")
    expect_code("F16 path traversal rejected",
                check_rec(DV, "f16.md", "21", "/updates/blackmagic-design/../davinci-resolve/21/"),
                "record_permalink_mismatch")
    expect_code("F17 encoded slash rejected",
                check_rec(DV, "f17.md", "21", "/updates/blackmagic-design/davinci%2Fresolve/21/"),
                "record_permalink_mismatch")
    expect_code("F18 encoded traversal rejected",
                check_rec(DV, "f18.md", "21", "/updates/blackmagic-design/%2E%2E/davinci-resolve/21/"),
                "record_permalink_mismatch")
    expect_code("F19 repeated slash rejected (not collapsed)",
                check_rec(DV, "f19.md", "21", "/updates//blackmagic-design/davinci-resolve/21/"),
                "record_permalink_mismatch")
    expect_code("F20 query-string trick rejected",
                check_rec(DV, "f20.md", "21", "/updates/blackmagic-design/davinci-resolve/21/?x=1"),
                "record_permalink_mismatch")
    expect_code("F21 fragment trick rejected",
                check_rec(DV, "f21.md", "21", "/updates/blackmagic-design/davinci-resolve/21/#f"),
                "record_permalink_mismatch")

    # ============================ PART D: behavioral equivalence ============================
    # ~22 UNRELATED ownership scenarios must still raise their identical code -- only E2/E3 and F1/F2
    # (the two proven false positives) change behavior. If any code here drifts, the fix is too broad.
    print("\n-- Part D: unrelated ownership behavior unchanged --")

    # records
    expect_code("D record product mismatch",
                lambda: (lambda p: o.validate_records(OBS, gen, {p}, lambda q: None))(
                    rec(gen, "d1.md", "adobe-premiere-pro", "26.2", "/updates/adobe/adobe-premiere-pro/26-2/")),
                "record_product_mismatch")
    expect_code("D record permalink mismatch (genuine bad slug)",
                check_rec(OBS, "d2.md", "31.0.3", "/updates/x/not-obs/31-0-3/"),
                "record_permalink_mismatch")
    expect_code("D record version unresolved",
                check_rec(OBS, "d3.md", "0.0.1", "/updates/obs-project/obs-studio/0-0-1/"),
                "record_version_unresolved")

    def d_nonrecord():
        p = gen / "d4.md"
        p.write_text("no front matter here\n", encoding="utf-8")
        o.validate_records(OBS, gen, {p}, lambda q: None)
    expect_code("D record non-record file", d_nonrecord, "record_non_record_file")

    def d_malformed():
        p = gen / "d5.md"
        p.write_text("---\n: : bad: [yaml\n---\nbody\n", encoding="utf-8")
        o.validate_records(OBS, gen, {p}, lambda q: None)
    expect_code("D record malformed front matter", d_malformed, "record_malformed_front_matter")

    # evidence
    expect_code("D evidence rows removed",
                lambda: o.validate_evidence(OBS, *ev(
                    [erow("a", OBS, "32.2.0", U, "github_issue"), erow("b", OBS, "31.0.3", U + "x", "github_issue")],
                    [erow("a", OBS, "32.2.0", U, "github_issue")])),
                "evidence_existing_row_deleted")
    expect_code("D evidence product mismatch",
                lambda: o.validate_evidence(OBS, *ev([], [erow("n", "adobe-premiere-pro", "26.2", U, "github_issue")])),
                "evidence_product_mismatch")
    expect_code("D evidence missing id",
                lambda: o.validate_evidence(OBS, *ev([], [erow("", OBS, "32.2.0", U, "github_issue")])),
                "evidence_missing_id")

    # method-health
    expect_code("D mh product mismatch",
                lambda: o.validate_method_health(OBS, [{"product_id": "x", "method_id": "github_issues", "update_version": "32.2.0", "status": "success"}]),
                "method_health_product_mismatch")
    expect_code("D mh method not allowed",
                lambda: o.validate_method_health(OBS, [{"product_id": OBS, "method_id": "reddit_search", "update_version": "32.2.0", "status": "success"}]),
                "method_not_allowed")
    expect_code("D mh version unresolved",
                lambda: o.validate_method_health(OBS, [{"product_id": OBS, "method_id": "github_issues", "update_version": "9.9", "status": "success"}]),
                "method_health_version_unresolved")
    expect_code("D mh noncanonical status",
                lambda: o.validate_method_health(OBS, [{"product_id": OBS, "method_id": "github_issues", "update_version": "32.2.0", "status": "made_up"}]),
                "method_health_noncanonical_status")
    expect_ok("D mh legit row accepted",
              lambda: o.validate_method_health(OBS, [{"product_id": OBS, "method_id": "github_issues", "update_version": "32.2.0", "status": "success"}]))

    print()
    print("=" * 74)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 74)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
