#!/usr/bin/env python3
"""Tests for the dedicated Adobe Photoshop (desktop) official release-notes adapter.

Offline only: canned Photoshop desktop release-notes HTML is fed directly to the pure
parser (no network). Proves the fail-closed contract:

- explicit desktop-Photoshop attribution (other Adobe products, Camera-Raw-only notes,
  and non-desktop Photoshop variants never produce a record);
- exact stable-version extraction (2X.Y / 2X.Y.Z), rejecting year-only, bare-major, and
  beta/prerelease builds;
- deterministic release date (full/ISO -> day precision, month+year -> month precision),
  with a body's exact day upgrading a heading's month;
- ambiguity fails closed (multi-version heading, undated release);
- deduplication by version; limit is honoured;
- records stay official_only with 0 reports and carry no consensus/community language.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_adobe_photoshop_adapter.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from adapters import adobe_photoshop as ap
from lib.write_update_record import build_front_matter

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []

_URL = "https://helpx.adobe.com/photoshop/desktop/whats-new/photoshop-on-desktop-release-notes.html"


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        msg = f"  FAIL  {label}"
        if detail:
            msg += f"\n        {detail}"
        print(msg)
        _ERRORS.append(label)


def _src() -> dict:
    return {
        "company_id": "adobe",
        "product_id": ap.PRODUCT_ID,
        "company": "Adobe",
        "software": "Photoshop",
        "public_category": "Design Workflow",
        "ingestion": {
            "official_url": _URL,
            "secondary_official_url": None,
        },
    }


def _parse(html: str, limit: int = 20):
    return ap._records_from_photoshop_release_notes(_src(), _URL, html, limit)


# A representative multi-release page. Release identity (version + date) lives in the
# HEADING; a full date in a heading yields day precision, a month+year yields month
# precision. Body prose (bundled Camera Raw / Premiere mentions, fixed-issues) is never
# parsed for identity, so it can never leak a foreign version or date.
PAGE = """
<h1>Photoshop desktop release notes</h1>
<p>Learn what's new in the latest releases of Photoshop on desktop.</p>

<h2>Photoshop 27.0 (October 14, 2025)</h2>
<h3>What's new</h3>
<ul><li>New Firefly-powered features. Camera Raw 17.0 is included. Premiere Pro 25.0 integration.</li></ul>

<h2>Photoshop 26.11 (September 2025 release)</h2>
<p>Monthly feature update.</p>

<h2>Photoshop 26.10.1 (August 2025 release)</h2>
<ul><li>Maintenance build.</li></ul>

<h2>Photoshop 26.0 (October 2024 release)</h2>
<p>Annual release.</p>
"""


def run() -> int:
    print("=" * 60)
    print("Adobe Photoshop (desktop) adapter tests")
    print("=" * 60)

    recs = _parse(PAGE)
    versions = [r["target_version"] for r in recs]
    by_ver = {r["target_version"]: r for r in recs}

    # --- 1-4: clean multi-release extraction, order, and count -------------
    check("1. four clean desktop releases extracted", len(recs) == 4, f"versions={versions}")
    check("2. newest-first order preserved (27.0, 26.11, 26.10.1, 26.0)",
          versions == ["27.0", "26.11", "26.10.1", "26.0"], f"versions={versions}")
    check("3. two-component version 27.0 accepted", "27.0" in by_ver)
    check("4. three-component version 26.10.1 accepted", "26.10.1" in by_ver)

    # --- 5-7: date extraction + precision (heading-only) -------------------
    check("5. full date in heading yields exact day (27.0 = 2025-10-14, day)",
          by_ver["27.0"]["published_at"] == "2025-10-14T00:00:00Z"
          and by_ver["27.0"]["date_precision"] == "day",
          str((by_ver["27.0"]["published_at"], by_ver["27.0"]["date_precision"])))
    check("6. month-only heading yields month precision (26.11 = 2025-09-01, month)",
          by_ver["26.11"]["published_at"] == "2025-09-01T00:00:00Z"
          and by_ver["26.11"]["date_precision"] == "month",
          str((by_ver["26.11"]["published_at"], by_ver["26.11"]["date_precision"])))
    check("7. month heading yields month precision (26.10.1 = 2025-08-01, month)",
          by_ver["26.10.1"]["published_at"] == "2025-08-01T00:00:00Z"
          and by_ver["26.10.1"]["date_precision"] == "month",
          str((by_ver["26.10.1"]["published_at"], by_ver["26.10.1"]["date_precision"])))

    # --- 8: no cross-product version contamination -------------------------
    check("8. bundled Camera Raw 17.0 / Premiere 25.0 in body never become records",
          "17.0" not in versions and "25.0" not in versions, f"versions={versions}")
    check("8b. body month phrasing is honest (26.11 summary says 'released September 2025', not a day)",
          "September 2025" in by_ver["26.11"]["official_summary"]
          and "September 1" not in by_ver["26.11"]["official_summary"],
          by_ver["26.11"]["official_summary"])

    # --- 9-13: attribution rejection (other products / non-desktop) --------
    check("9. Premiere Pro heading -> no record",
          len(_parse("<h2>Premiere Pro 25.0 (October 2025 release)</h2><p>October 14, 2025.</p>")) == 0)
    check("10. Camera-Raw-only heading -> no record",
          len(_parse("<h2>Camera Raw 17.0 (October 2025 release)</h2><p>October 14, 2025.</p>")) == 0)
    check("11. Lightroom / Illustrator / Acrobat / Firefly headings -> no records",
          all(len(_parse(f"<h2>{p} 27.0 (October 2025 release)</h2><p>October 14, 2025.</p>")) == 0
              for p in ("Lightroom Classic", "Illustrator", "Acrobat", "Firefly")))
    check("12. 'Photoshop on the web' -> no record",
          len(_parse("<h2>Photoshop on the web 27.0 (October 2025)</h2><p>October 14, 2025.</p>")) == 0)
    check("13. 'Photoshop on iPad' -> no record",
          len(_parse("<h2>Photoshop on iPad 6.0 (October 2025)</h2><p>October 14, 2025.</p>")) == 0)
    check("13b. generic Creative Cloud desktop heading -> no record",
          len(_parse("<h2>Creative Cloud desktop app 6.0 (October 2025)</h2><p>October 14, 2025.</p>")) == 0)

    # --- 14-15: stable-only (reject beta/prerelease) -----------------------
    check("14. beta heading -> no record",
          len(_parse("<h2>Photoshop 27.0 beta (October 2025)</h2><p>October 14, 2025.</p>")) == 0)
    check("15. prerelease / technology preview headings -> no records",
          len(_parse("<h2>Photoshop 27.0 (Prerelease)</h2><p>October 14, 2025.</p>")) == 0
          and len(_parse("<h2>Photoshop 27.0 Technology Preview</h2><p>October 14, 2025.</p>")) == 0)

    # --- 16-18: version validity -------------------------------------------
    check("16. year-only 'Photoshop 2025' -> no record",
          len(_parse("<h2>Photoshop 2025 (October 2025 release)</h2><p>October 14, 2025.</p>")) == 0)
    check("17. bare-major 'Photoshop 26' -> no record",
          len(_parse("<h2>Photoshop 26 (October 2025 release)</h2><p>October 14, 2025.</p>")) == 0)
    check("18. multi-version heading is ambiguous -> no record",
          len(_parse("<h2>Photoshop 27.0 and 26.11 (October 2025)</h2><p>October 14, 2025.</p>")) == 0)

    # --- 19-20: date fail-closed + dedup -----------------------------------
    check("19. undated release fails closed (heading + no date anywhere)",
          len(_parse("<h2>Photoshop 27.0</h2><h3>What's new</h3><ul><li>Features.</li></ul>")) == 0)
    dup = _parse("<h2>Photoshop 27.0 (October 2025 release)</h2><p>October 14, 2025.</p>"
                 "<h2>Photoshop 27.0 (October 2025 release)</h2><p>October 14, 2025.</p>")
    check("20. duplicate version deduped to a single record", len(dup) == 1, f"count={len(dup)}")

    # --- 21: limit honoured ------------------------------------------------
    limited = _parse(PAGE, limit=2)
    check("21. limit honoured (limit=2 -> 2 newest records)",
          [r["target_version"] for r in limited] == ["27.0", "26.11"],
          str([r["target_version"] for r in limited]))

    # --- 22: DOM-miss + inert fetch for wrong product ----------------------
    check("22. empty / non-release DOM -> 0 records",
          _parse("") == [] and _parse("<p>No releases here.</p>") == [])
    check("22b. fetch() returns [] for a non-Photoshop product id",
          ap.fetch({"product_id": "obs-studio", "ingestion": {}}, 3) == [])

    # --- 23-25: official-only write path, structured identity, no consensus -
    rec = by_ver["27.0"]
    front = build_front_matter(rec)
    check("23. front matter is official_only with 0 reports",
          front["evidence_state"] == "official_only" and front["update_report_count"] == 0,
          str({k: front[k] for k in ("evidence_state", "update_report_count")}))
    check("24. structured Photoshop identity: version, applicability, platform",
          front.get("target_version") == "27.0"
          and rec.get("applicability") == ["adobe-photoshop"]
          and rec.get("target_platform") == "Windows, macOS",
          str({"tv": front.get("target_version"), "app": rec.get("applicability")}))
    blob = " ".join(str(rec.get(k, "")) for k in ("body", "official_summary", "title", "capture_status")).lower()
    check("25. record carries no consensus/community/report language",
          not any(term in blob for term in ("consensus", "report", "users say", "community", "complaint", "verified reports")),
          blob)
    check("25b. record emits no report/consensus fields (pipeline derives official_only)",
          rec.get("report_count") is None and rec.get("evidence_state") is None
          and rec.get("update_report_count") is None and rec.get("consensus_label") is None)

    # === Regression: adversarial-verification defects (must stay fail-closed) =========
    # Each case was an EMPIRICALLY REPRODUCED false positive found by an adversarial review
    # pass; the parser must now reject (or correctly attribute) every one.
    print("  --- adversarial-defect regression ---")

    def count(html: str) -> int:
        return len(_parse(html))

    # D01 / D05 / D11: another product's version must never leak as a Photoshop record when
    # "Photoshop" merely co-occurs (no Photoshop-anchored version).
    check("D01. 'Photoshop now opens Illustrator 29.0 files' -> no record",
          count("<h2>Photoshop now opens Illustrator 29.0 files</h2><p>Released October 2025.</p>") == 0)
    check("D05. cross-product co-mention ('Photoshop compatibility with After Effects 25.1') -> no record",
          count("<h3>Photoshop compatibility with After Effects 25.1</h3><p>Released October 14, 2025.</p>") == 0
          and count("<h3>Photoshop tips: see also Illustrator 29.0</h3><p>Published November 2025.</p>") == 0)
    check("D11. 'Premiere Pro 26.5 now imports Photoshop layers' -> no record (other product's version)",
          count("<h2>Premiere Pro 26.5 now imports Photoshop layers (October 2025)</h2>") == 0)
    check("D01b. a genuine Photoshop-anchored version that merely references another product still records",
          [r["target_version"] for r in _parse("<h2>Photoshop 26.5 imports Illustrator files (October 2025)</h2>")] == ["26.5"])

    # D02 / D06 / D07 / D09 / D12: a foreign / dependency / older-version / historical date in
    # surrounding prose must never date an undated release heading (heading-only extraction).
    check("D02. undated heading + other-product body date -> no record",
          count("<h2>Photoshop desktop version 26.10</h2><p>Illustrator 29.3 was released on October 9, 2025.</p>") == 0)
    check("D06. undated heading + system-requirement date -> no record",
          count("<h2>Adobe Photoshop 27.0</h2><h3>System requirements</h3><p>Requires macOS Sonoma, released September 2024.</p>") == 0)
    check("D07. undated heading + older-version's date in body -> no record",
          count("<h2>Adobe Photoshop 26.5</h2><h3>Bug fixes</h3><p>Rolls up fixes first shipped in 26.4 on August 12, 2025.</p>") == 0)
    check("D09. undated heading + 'supersedes ... shipped on <date>' -> no record",
          count("<h2>Photoshop version 27.0</h2><p>This build supersedes the previous milestone shipped on March 3, 2024.</p>") == 0)
    check("D12. undated heading + 'since the <month year> release' -> no record",
          count("<h2>Photoshop desktop version 26.5</h2><p>New desktop features.</p>"
                "<h3>Fixed issues</h3><ul><li>Fixed a crash present since the October 2024 release.</li></ul>") == 0)

    # D13: a dated heading must keep its own month; a bugfix date in the body must not
    # "upgrade" or override it.
    d13 = _parse("<h2>Photoshop desktop version 26.5 (October 2025)</h2>"
                 "<h3>Fixed issues</h3><li>Regression introduced on September 3, 2025 has been resolved.</li>")
    check("D13. dated heading keeps its month; body bugfix date does not override it",
          len(d13) == 1 and d13[0]["published_at"] == "2025-10-01T00:00:00Z" and d13[0]["date_precision"] == "month",
          str([(r["target_version"], r["published_at"], r["date_precision"]) for r in d13]))

    # D03: hyphenated / re-spaced beta terms must still be rejected.
    check("D03. hyphenated/re-spaced prerelease terms are rejected",
          all(count(h) == 0 for h in (
              "<h2>Photoshop 26.6 release-candidate, October 2025</h2>",
              "<h2>Adobe Photoshop 26.5 technology-preview (October 2025)</h2>",
              "<h2>Adobe Photoshop 26.5 pre release build (October 2025)</h2>")))
    # D04: additional prerelease synonyms must be rejected. A *bare* "preview" is NOT a beta
    # marker (it is a common feature word) -- only qualified prerelease forms are.
    check("D04. alpha / nightly / early access / qualified preview builds are rejected",
          all(count(h) == 0 for h in (
              "<h2>Adobe Photoshop 26.5 alpha (October 2025)</h2>",
              "<h2>Photoshop 27.0 nightly build, October 2025</h2>",
              "<h2>Photoshop 26.9 Early Access (October 2025)</h2>",
              "<h2>Adobe Photoshop 26.7 preview build (October 2025)</h2>")))
    # D08: beta declared only in the body is moot now (undated heading fails closed anyway).
    check("D08. beta-declared build with body-only date -> no record",
          count("<h2>Adobe Photoshop 26.8</h2><p>This is a beta prerelease technology preview build. October 2025.</p>") == 0)

    # D10: non-desktop Photoshop variants with intervening words must be rejected.
    check("D10. 'Photoshop for the web version 26.5' and parenthetical (web)/(iPad) -> no record",
          count("<h2>Photoshop for the web version 26.5 (October 2025)</h2>") == 0
          and count("<h2>Photoshop 26.5 (web), October 2025</h2>") == 0
          and count("<h2>Photoshop 26.5 (iPad) October 2025</h2>") == 0)
    check("D10b. a genuine desktop release mentioning a 'web export' feature still records",
          [r["target_version"] for r in _parse("<h2>Photoshop 26.0 adds web export (October 2024 release)</h2>")] == ["26.0"])

    # === Regression: second adversarial pass (structural hardening) ===================
    print("  --- adversarial-defect regression (round 2) ---")

    # R2-01: positive attribution -- an UNLISTED Adobe product's version must not leak just
    # because "Photoshop" co-occurs and no denied name matched (deny-lists are never complete).
    check("R2-01. unlisted Adobe products (InCopy/Aero/Frame.io/Behance) do not leak a version",
          all(count(h) == 0 for h in (
              "<h2>InCopy 26.0 shares assets with Photoshop (October 2024)</h2>",
              "<h2>Adobe Aero 26.0 imports from Photoshop (October 2024)</h2>",
              "<h2>Frame.io 26.0 review with Photoshop (October 2024)</h2>",
              "<h2>Behance 26.5 gallery for Photoshop (October 2024)</h2>")))
    check("R2-01b. only a Photoshop-ANCHORED version is ever accepted (positive attribution)",
          ap._heading_version("InCopy 26.0 with Photoshop (October 2024)") is None
          and ap._heading_version("Photoshop 26.0 (October 2024)") == "26.0")

    # R2-02 / R2-05: a co-located historical/superseded date in the heading must not win;
    # >1 distinct month -> ambiguous -> fail closed.
    check("R2-02. co-located historical date does not override the release month (fail closed)",
          all(count(h) == 0 for h in (
              "<h2>Photoshop 26.5 (fixes issue introduced March 3, 2024) - May 2025 release</h2>",
              "<h2>Photoshop 26.1 supersedes the January 5, 2024 build, released November 2024</h2>",
              "<h2>Photoshop 26.2 rolls back 2023-08-15 regression (December 2024 release)</h2>",
              "<h2>Photoshop 26.0 (October 2024 release) supersedes the July 2, 2024 build</h2>")))
    check("R2-02b. a day + month of the SAME month is consistent -> day precision (not dropped)",
          [(r["published_at"], r["date_precision"]) for r in
           _parse("<h2>Photoshop 27.0 (October 14, 2025) - October 2025 release</h2>")]
          == [("2025-10-14T00:00:00Z", "day")])

    # R2-04 / R2-08 / R2-09: non-desktop editions (mobile/iPad/web app) never record, even when
    # the platform word is not adjacent to "Photoshop" or wrapped as "(web app)".
    check("R2-04/08/09. mobile / 'on the iPad' / '(web app)' editions -> no record",
          all(count(h) == 0 for h in (
              "<h2>Photoshop mobile 27.0 released October 2024</h2>",
              "<h3>Photoshop 26.1 on the iPad (November 2024 release)</h3>",
              "<h2>Photoshop 26.1 (web app), November 2024</h2>",
              "<h2>Photoshop 26.5 for Chromebook (October 2025)</h2>")))
    check("R2-04b. a desktop release with an 'iPad file compatibility' feature still records",
          [r["target_version"] for r in
           _parse("<h2>Photoshop 26.0 improves iPad file compatibility (October 2024 release)</h2>")] == ["26.0"])

    # R2-06: plural prerelease forms ("Technology Previews", "sneak peek") are rejected.
    check("R2-06. plural 'Technology Previews' / 'sneak peek' are rejected",
          count("<h2>Photoshop 26.0 Technology Previews (October 2024)</h2>") == 0
          and count("<h2>Photoshop 27.0 sneak peek (October 2025)</h2>") == 0)

    # R2-10: a Unicode (non-breaking) hyphen must not smuggle a prerelease term past the gate.
    check("R2-10. Unicode-hyphen 'release‑candidate' is rejected",
          count("<h2>Photoshop 26.8 release‑candidate (June 2025)</h2>") == 0)

    # R2-03 / R2-07 / R2-11 / R2-12 / R2-13: a bare 'preview'/'experimental-feature' style
    # feature word must NOT drop a genuine dated desktop release (no over-rejection).
    check("R2-03/13. genuine releases naming an 'AI preview' / 'Generative preview' feature still record",
          all([r["target_version"] for r in _parse(h)] == [v] for h, v in (
              ("<h2>Photoshop 26.4: AI preview feature (February 2025)</h2>", "26.4"),
              ("<h2>Photoshop 26.0 (October 2024 release): Generative preview</h2>", "26.0"),
              ("<h3>Photoshop 26.4 (February 2025) — AI preview improvements</h3>", "26.4"))))

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed tests:")
        for error in _ERRORS:
            print(f"  - {error}")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
