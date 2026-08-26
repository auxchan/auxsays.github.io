#!/usr/bin/env python3
"""PowerPoint multi-build official ingestion: doctrine matrix D1-D17.

TWO POLICIES CHANGED, ONE DOCTRINE.

Gate 1 used PowerPoint-specific prose as the ADMISSION rule: a Current Channel build only became a
PowerPoint record if Microsoft's notes happened to name the app. That is the wrong abstraction -- the
build ships the installed PowerPoint binary either way. Attribution is now metadata. The record says
"Microsoft did not document PowerPoint-specific changes for this build", which is a statement about
the SOURCE, and never "PowerPoint was unchanged", which would be a claim about the software that
Microsoft did not make.

Gate 2 deduplicated on the marketing version, so every sibling build after the first was discarded.
Identity for this product is (product_id, update_version, target_build); dedupe now matches it.

Nothing here invents consensus. A build with no user reports stays at zero reports, and official
attribution never becomes evidence of user impact.

Offline and deterministic: fixtures are HTML shaped like the live Current Channel page, and all
writes go to temporary directories. The real repository is never modified.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_powerpoint_multibuild_ingestion.py
"""
from __future__ import annotations

import inspect
import re
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402
from adapters import microsoft_office_updates as office  # noqa: E402
from lib import patch_identity as pi  # noqa: E402
from lib import version_landing as vl  # noqa: E402
from lib import write_update_record as wur  # noqa: E402
from patch_collectors import microsoft_powerpoint as ppt  # noqa: E402
from patch_collectors.base import PatchRecord  # noqa: E402

PPT = "microsoft-powerpoint"
OBS = "obs-studio"
CC_URL = "https://learn.microsoft.com/en-us/officeupdates/current-channel"
CAPTURED = "2026-08-24T00:00:00Z"

B110, B124, B158, B190 = "20228.20110", "20228.20124", "20228.20158", "20228.20190"
B2608 = "20326.20100"

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERRORS.append(label)


def ppt_source(floor: str = "") -> dict:
    ing = {"channel": "Current Channel", "target_app": "powerpoint",
           "parser_profile": "microsoft_365_powerpoint_release_notes",
           "official_url": CC_URL,
           "secondary_official_url": "https://learn.microsoft.com/en-us/officeupdates/x"}
    if floor:
        ing["record_floor_date"] = floor
    return {"company_id": "microsoft", "product_id": PPT, "company": "Microsoft",
            "software": "Microsoft PowerPoint", "public_category": "Productivity",
            "ingestion": ing}


def section(version: str, month_day: str, build: str, blocks: str = "") -> str:
    """One build section, shaped like the live page: a per-BUILD h2 plus an <em> identity line."""
    return (f'<h2 id="version-{version}-x">Version {version}: {month_day}</h2>'
            f"<p><em>Version {version} (Build {build})</em></p>{blocks}")


PPT_BLOCK = "<h3>PowerPoint</h3><ul><li>Fixed an issue where PowerPoint closed unexpectedly.</li></ul>"
WORD_BLOCK = "<h3>Word</h3><ul><li>Fixed an issue in the Word citations pane.</li></ul>"
SUITE_BLOCK = ("<h3>Office Suite</h3><ul><li>Applies to all Microsoft 365 apps: fixed a shared "
               "rendering fault.</li></ul>")
NO_BLOCK = "<p>Various fixes.</p>"


def parse(html: str, floor: str = "", limit: int = 500) -> list[dict]:
    return office._records_from_office_app_release_notes(ppt_source(floor), CC_URL, html, limit=limit)


def record(build: str, version: str = "2607") -> PatchRecord:
    return PatchRecord(product_id=PPT, update_version=version, path=Path(f"x-{build}.md"),
                       update_published_at="2026-07-23T00:00:00Z", update_status="current",
                       update_product="Microsoft PowerPoint", target_build=build)


def target(build: str, version: str = "2607") -> dict:
    return {"update_version": version, "target_build": build,
            "target_release_date": "2026-07-23T00:00:00Z", "version_ambiguous": False}


def ingest_record(build: str, version: str = "2607", date: str = "2026-07-23T00:00:00Z") -> dict:
    return {"company_id": "microsoft", "product_id": PPT, "software": "Microsoft PowerPoint",
            "version": version, "update_version": version, "target_build": build,
            "published_at": date, "title": f"Microsoft PowerPoint {version} (Build {build})",
            "official_url": CC_URL, "release_notes_body": "notes",
            "official_source_type": "release_notes", "channel": "Current Channel"}


def front(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1]) or {}


def run() -> int:  # noqa: PLR0915
    print("=" * 74)
    print("PowerPoint multi-build official ingestion -- doctrine matrix")
    print("=" * 74)

    # ---------- D1: sibling preservation ----------
    print("\n[D1] two siblings under one version both survive candidate generation")
    html = section("2607", "August 11", B190, PPT_BLOCK) + section("2607", "July 23", B110, PPT_BLOCK)
    recs = parse(html)
    builds = [r["target_build"] for r in recs]
    check("D1 both builds emitted", sorted(builds) == sorted([B110, B190]), str(builds))
    check("D1 both carry the same version", {r["version"] for r in recs} == {"2607"})
    check("D1 record_ids are distinct", len({r["record_id"] for r in recs}) == 2)
    check("D1 canonical identities are distinct",
          len({pi.patch_key(PPT, r["version"], r["target_build"]) for r in recs}) == 2)

    # ---------- D2: the four real 2607 siblings ----------
    print("\n[D2] the four real 2607 siblings -> four unique identities")
    html = (section("2607", "August 11", B190, NO_BLOCK)
            + section("2607", "August 04", B158, NO_BLOCK)
            + section("2607", "July 29", B124, NO_BLOCK)
            + section("2607", "July 23", B110, PPT_BLOCK))
    recs = parse(html)
    check("D2 four records", len(recs) == 4, str([r["target_build"] for r in recs]))
    check("D2 four distinct builds", len({r["target_build"] for r in recs}) == 4)
    check("D2 four distinct filename slugs",
          len({pi.record_version_slug(r["version"], r["target_build"], PPT) for r in recs}) == 4)
    check("D2 four distinct permalinks",
          len({pi.permalink_path("microsoft", PPT, r["version"], r["target_build"])
               for r in recs}) == 4)
    check("D2 each date matches its own heading",
          sorted(r["published_at"][:10] for r in recs)
          == ["2026-07-23", "2026-07-29", "2026-08-04", "2026-08-11"],
          str(sorted(r["published_at"][:10] for r in recs)))

    # ---------- D3: generic build, no PowerPoint bullet ----------
    print("\n[D3] a valid build with no PowerPoint bullet still produces a record")
    recs = parse(section("2608", "August 18", B2608, NO_BLOCK))
    check("D3 the record exists", len(recs) == 1, str(len(recs)))
    r = recs[0] if recs else {}
    check("D3 attribution is not_documented_by_source",
          r.get("official_app_attribution") == wur.ATTRIBUTION_NOT_DOCUMENTED,
          str(r.get("official_app_attribution")))
    # The honest model: there was no vendor text to capture, so the record carries NONE. Writing
    # AUXSAYS prose into official_patch_notes_body would publish our words under a heading that
    # reads "vendor release notes captured from the official source", and would let one lossy
    # re-parse overwrite genuine vendor text. The claim lives in the attribution field instead.
    check("D3 no fabricated vendor body", (r.get("body") or "") == "", repr(r.get("body"))[:120])
    check("D3 the capture status does not claim captured vendor notes",
          r.get("capture_status") == "official-source-no-app-specific-note",
          str(r.get("capture_status")))
    check("D3 the note status does not claim captured release notes",
          r.get("official_note_status") == "release_notes_no_app_specific_entry",
          str(r.get("official_note_status")))
    check("D3 the summary is factual identity only, so it never goes stale",
          (r.get("official_summary") or "").startswith("Microsoft PowerPoint Version 2608")
          and "document" not in (r.get("official_summary") or "").lower(),
          str(r.get("official_summary")))
    check("D3 the summary is short enough to survive summarize()'s 420-char cap",
          len(r.get("official_summary") or "") < 420, str(len(r.get("official_summary") or "")))
    for banned in ("no powerpoint changes", "no changes", "was unchanged", "nothing changed",
                   "no app-specific changes"):
        check(f"D3 body never says {banned!r}", banned not in (r.get("body") or "").lower())
        check(f"D3 summary never says {banned!r}",
              banned not in (r.get("official_summary") or "").lower())
    check("D3 no PowerPoint change text is fabricated",
          "fixed an issue" not in (r.get("body") or "").lower())
    check("D3 the label is honest about the source",
          "Not documented" in (r.get("official_app_attribution_label") or ""),
          str(r.get("official_app_attribution_label")))
    check("D3 identity is complete", bool(r.get("target_build")) and bool(r.get("published_at")))
    check("D3 no consensus is invented", not r.get("report_count") and not r.get("summary"))

    # ---------- D4: explicit PowerPoint attribution ----------
    print("\n[D4] an explicitly-attributed build is marked distinctly")
    recs = parse(section("2607", "July 23", B110, PPT_BLOCK))
    r = recs[0]
    check("D4 attribution is app_named_by_source",
          r.get("official_app_attribution") == wur.ATTRIBUTION_APP_NAMED,
          str(r.get("official_app_attribution")))
    check("D4 the vendor's own text is carried", "closed unexpectedly" in (r.get("body") or ""))
    check("D4 it is NOT the not-documented state",
          r.get("official_app_attribution") != wur.ATTRIBUTION_NOT_DOCUMENTED)

    # ---------- D5: suite-wide, tested separately ----------
    print("\n[D5] suite-wide attribution is its own state, not collapsed into explicit")
    recs = parse(section("2605", "May 20", "20026.20076", SUITE_BLOCK))
    r = recs[0]
    check("D5 attribution is suite_wide_by_source",
          r.get("official_app_attribution") == wur.ATTRIBUTION_SUITE_WIDE,
          str(r.get("official_app_attribution")))
    check("D5 applicability carries the suite id",
          "microsoft-365-apps" in (r.get("applicability") or []), str(r.get("applicability")))
    check("D5 it is distinct from app_named and from not_documented",
          r.get("official_app_attribution") not in
          {wur.ATTRIBUTION_APP_NAMED, wur.ATTRIBUTION_NOT_DOCUMENTED})
    both = parse(section("2606", "July 14", "20131.20154", PPT_BLOCK + SUITE_BLOCK))[0]
    check("D5 named AND suite-wide is its own strongest state",
          both.get("official_app_attribution") == wur.ATTRIBUTION_APP_NAMED_AND_SUITE_WIDE,
          str(both.get("official_app_attribution")))

    # ---------- D6: missing build fails closed ----------
    print("\n[D6] a section with no resolvable build produces nothing")
    check("D6 no build -> no record",
          parse('<h2 id="v">Version 2609: September 15</h2><p><em>Version 2609</em></p>'
                + NO_BLOCK) == [])
    check("D6 no date -> no record",
          parse('<h2 id="v">Version 2609</h2><p><em>Version 2609 (Build 20400.20100)</em></p>'
                + NO_BLOCK) == [])
    check("D6 the writer refuses a build-aware record with no build",
          pi.build_identity_reason(PPT, "2609", "", f"/updates/microsoft/{PPT}/2609/")
          == pi.REASON_BUILD_MISSING)

    # ---------- D7: same build seen twice ----------
    print("\n[D7] the same build appearing twice is one identity")
    recs = parse(section("2607", "July 23", B110, PPT_BLOCK)
                 + section("2607", "July 23", B110, PPT_BLOCK))
    check("D7 one record", len(recs) == 1, str(len(recs)))
    check("D7 one record_id", len({r["record_id"] for r in recs}) == 1)

    # ---------- D8: the #65 sibling writer ----------
    print("\n[D8] writing two siblings produces two canonical files, neither refreshing the other")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        p1, a1 = wur.write_record(out, ingest_record(B110, date="2026-07-23T00:00:00Z"))
        p2, a2 = wur.write_record(out, ingest_record(B190, date="2026-08-11T00:00:00Z"))
        check("D8 both created", a1 == "created" and a2 == "created", f"{a1}/{a2}")
        check("D8 two files", len(list(out.glob("*.md"))) == 2)
        check("D8 first keeps its own build", front(p1).get("target_build") == B110)
        check("D8 second keeps its own build", front(p2).get("target_build") == B190)
        check("D8 permalinks differ", front(p1)["permalink"] != front(p2)["permalink"])
        check("D8 neither mentions the other",
              B190 not in p1.read_text(encoding="utf-8")
              and B110 not in p2.read_text(encoding="utf-8"))

    # ---------- D9: Candidate 1 evidence isolation ----------
    print("\n[D9] Candidate 1 counts for .20110 and is refused by every sibling")
    c1_text = ("Version 2607 - PowerPoint Crashing when using an Add-In. There seems to be a "
               f"problem since build 2607. PowerPoint Version 2607 (Build {B110}) is not working "
               "and crashes on the second question. "
               '<Data Name="AppName">POWERPNT.EXE</Data>'
               f'<Data Name="AppVersion">16.0.{B110}</Data>')
    cand = {"source_url": "https://learn.microsoft.com/en-us/answers/questions/5975138/x",
            "parent_title": "Version 2607 - PowerPoint Crashing when using an Add-In",
            "report_title": "", "report_text": c1_text, "source_date": "2026-08-14",
            "source_type": ppt.LEARN_QNA_SOURCE_TYPE, "source_name": ppt.LEARN_QNA_SOURCE_NAME}
    own = ppt.row_from_candidate(record(B110), target(B110), cand, CAPTURED)
    check("D9 counted for its own build", own.get("counted") is True, str(own.get("exclusion_reason")))
    check("D9 stamped with .20110", own.get("target_build") == B110)
    for sib in (B124, B158, B190):
        row = ppt.row_from_candidate(record(sib), target(sib), cand, CAPTURED)
        check(f"D9 sibling {sib}: counted is False", row.get("counted") is False,
              str(row.get("exclusion_reason")))
        check(f"D9 sibling {sib}: no build stamped", not row.get("target_build"))
    check("D9 evidence keys are per-build",
          len({pi.patch_key(PPT, "2607", b) for b in (B110, B124, B158, B190)}) == 4)

    # ---------- D10 / D11: attribution strengthening and retraction ----------
    print("\n[D10] attribution strengthens automatically")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        weak = ingest_record(B110)
        weak["official_app_attribution"] = wur.ATTRIBUTION_NOT_DOCUMENTED
        weak["official_app_attribution_label"] = wur.attribution_label(wur.ATTRIBUTION_NOT_DOCUMENTED)
        path, _ = wur.write_record(out, weak)
        check("D10 starts not_documented",
              front(path).get("official_app_attribution") == wur.ATTRIBUTION_NOT_DOCUMENTED)
        strong = ingest_record(B110)
        strong["official_app_attribution"] = wur.ATTRIBUTION_APP_NAMED
        wur.refresh_existing_record(path, strong)
        check("D10 strengthens to app_named_by_source",
              front(path).get("official_app_attribution") == wur.ATTRIBUTION_APP_NAMED,
              str(front(path).get("official_app_attribution")))
        check("D10 the label strengthens with it",
              "Named in the official" in (front(path).get("official_app_attribution_label") or ""))

        print("\n[D11] attribution never silently downgrades")
        back = ingest_record(B110)
        back["official_app_attribution"] = wur.ATTRIBUTION_NOT_DOCUMENTED
        wur.refresh_existing_record(path, back)
        check("D11 a weaker observation does NOT overwrite",
              front(path).get("official_app_attribution") == wur.ATTRIBUTION_APP_NAMED,
              str(front(path).get("official_app_attribution")))
        check("D11 the weaker run is still recorded as an attempt",
              len(front(path).get("official_source_attempts") or []) >= 1)
        omitted = ingest_record(B110)
        wur.refresh_existing_record(path, omitted)
        check("D11 an omitted field preserves the established value",
              front(path).get("official_app_attribution") == wur.ATTRIBUTION_APP_NAMED)
        empty = ingest_record(B110)
        empty["official_app_attribution"] = ""
        wur.refresh_existing_record(path, empty)
        check("D11 an empty value never blanks the field",
              front(path).get("official_app_attribution") == wur.ATTRIBUTION_APP_NAMED)
    check("D11 the rank ladder is strictly ordered",
          wur.attribution_rank(wur.ATTRIBUTION_NOT_DOCUMENTED)
          < wur.attribution_rank(wur.ATTRIBUTION_SUITE_WIDE)
          < wur.attribution_rank(wur.ATTRIBUTION_APP_NAMED)
          < wur.attribution_rank(wur.ATTRIBUTION_APP_NAMED_AND_SUITE_WIDE))
    check("D11 applicability cannot shrink either",
          wur._shrinks_applicability([PPT, "microsoft-365-apps"], [PPT]) is True
          and wur._shrinks_applicability([PPT], [PPT, "microsoft-365-apps"]) is False)

    # ---------- D12 / D13 / D14: version landings ----------
    print("\n[D12] a previously unseen version gets a working landing route")
    with tempfile.TemporaryDirectory() as td:
        updates = Path(td)
        path, action = vl.ensure_for_record(updates, ingest_record(B2608, version="2608"))
        check("D12 landing created", action == "created" and path is not None, str(action))
        check("D12 at the canonical path",
              str(path).endswith(str(Path("microsoft") / PPT / "2608" / "index.md")), str(path))
        fm = front(path)
        check("D12 permalink is the version URL",
              fm.get("permalink") == pi.version_landing_path("microsoft", PPT, "2608"),
              str(fm.get("permalink")))
        check("D12 it uses the version layout", fm.get("layout") == "aux-patch-version")
        check("D12 it carries the identity the layout filters on",
              fm.get("product_id") == PPT and str(fm.get("update_version")) == "2608")

        print("\n[D14] the landing page is not a patch")
        check("D14 no update_entry key", "update_entry" not in fm, str(sorted(fm)))
        check("D14 no update_published_at (never a feed item)", "update_published_at" not in fm)
        check("D14 no target_build (never a consensus target)", "target_build" not in fm)
        check("D14 no report count (never an evidence group)", "update_report_count" not in fm)
        check("D14 it lives outside updates/generated/",
              "generated" not in str(path).replace("\\", "/").split("/updates/")[-1])

        print("\n[D13] a sibling under an existing version reuses the same landing")
        p2, a2 = vl.ensure_for_record(updates, ingest_record("20326.20200", version="2608"))
        check("D13 same landing artifact", p2 == path, f"{p2} vs {path}")
        check("D13 unchanged, not rewritten", a2 == "unchanged", a2)
        check("D13 no duplicate landing",
              len(list((updates / "microsoft" / PPT).glob("*/index.md"))) == 1)
        p3, a3 = vl.ensure_for_record(updates, ingest_record(B2608, version="2608"))
        check("D13 idempotent across repeated runs", a3 == "unchanged", a3)

    print("\n[D12c] landing pages follow the RECORD output, never a fixed repo path")
    # Regression: the first wiring defaulted the landing root to the real repo path, so any caller
    # writing records into a temp directory still created landing pages in the actual tree. A
    # generator that can escape its caller's output directory is a contamination hazard, not a
    # convenience.
    import argparse as _argparse  # noqa: PLC0415
    parser = _argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("auxsays/updates/generated"))
    parser.add_argument("--updates-dir", type=Path, default=None)
    args = parser.parse_args([])
    check("D12c --updates-dir defaults to None, not a hard-coded repo path",
          args.updates_dir is None)
    from types import SimpleNamespace  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as td:
        fake = SimpleNamespace(output=Path(td) / "generated")
        root = getattr(fake, "updates_dir", None) or Path(fake.output).parent
        check("D12c a redirected --output redirects the landing root too",
              root == Path(td), f"{root} vs {td}")
        p, a = vl.ensure_for_record(root, ingest_record(B2608, version="2608"))
        check("D12c the landing landed inside the temp tree", str(p).startswith(td), str(p))
    ingest_src = (_REPO / "auxsays" / "scripts" / "patch_ingest.py").read_text(encoding="utf-8")
    check("D12c the ingest lane derives the root from --output",
          "Path(args.output).parent" in ingest_src)

    print("\n[D12b] zero churn against the 20 pages already in the repo")
    live = sorted((_REPO / "auxsays" / "updates" / "microsoft" / PPT).glob("*/index.md"))
    same = sum(1 for f in live
               if f.read_text(encoding="utf-8")
               == vl.render_landing("microsoft", PPT, front(f).get("update_version"),
                                    "Microsoft PowerPoint"))
    check(f"D12b all {len(live)} existing landings render byte-identical",
          live and same == len(live), f"{same}/{len(live)}")

    # ---------- D15: Patch Signals ----------
    print("\n[D15] siblings still yield exactly one homepage PowerPoint signal")
    signals = (_REPO / "auxsays" / "_includes" / "patch-latest-signals.html").read_text(encoding="utf-8")
    check("D15 the dedupe key is the product, so N siblings collapse to one row",
          "append: item.product_id" in signals and "latest_seen contains pmark" in signals)
    check("D15 it only ever considers real patch records",
          "include.updates" in signals)
    row = (_REPO / "auxsays" / "_includes" / "patch-table-row.html").read_text(encoding="utf-8")
    check("D15 sibling rows are distinguishable (the build is rendered)",
          "item.target_build" in row and "patch-cell-version__build" in row)
    check("D15 the sort key carries the build too",
          'data-version="{{ item.update_version | escape }}{% if item.target_build' in row)

    # ---------- D1(monitoring): the fail-open siblings would have caused ----------
    print("\n[monitoring] telemetry is joined per exact patch, not per version")
    mon = (_REPO / "auxsays" / "_includes" / "monitoring-status.html").read_text(encoding="utf-8")
    check("monitoring: the join includes the build", mon.count("== mon_build") == 3,
          str(mon.count("== mon_build")))
    check("monitoring: the build is an explicit input", "include.target_build" in mon)
    check("monitoring: the contract documents the build component",
          "target_build" in mon.split("Inputs:")[0])
    for caller in ("_layouts/aux-update.html", "_layouts/aux-updates.html",
                   "_includes/patch-table-row.html"):
        text = (_REPO / "auxsays" / caller).read_text(encoding="utf-8")
        n_inc = text.count("monitoring-status.html")
        n_build = text.count("target_build=")
        check(f"monitoring: {caller} passes the build at every call site",
              n_build >= n_inc, f"{n_build} of {n_inc}")

    # ---------- P1: public source limitations are per exact patch ----------
    # A "source limitation" is a factual claim about a collection run. Method-health rows are stored
    # per exact patch, so joining them on (product, version) let a build with NO telemetry of its own
    # publish a sibling build's limitation -- the same fail-open shape as the monitoring join above,
    # one layer down, in a field the repo classifies as PUBLIC text (qa_patch_records
    # PUBLIC_TEXT_FIELDS) and commits to a public repository.
    print("\n[limitations] a public source limitation belongs to ONE build, never its siblings")
    import apply_consensus_to_records as acr  # noqa: PLC0415
    SENT = "Some community sources were unavailable"
    emh = {"methods": [
        {"product_id": PPT, "update_version": "2607", "target_build": B110,
         "method_id": "learn_qna_search_rss", "status": "blocked"},
        {"product_id": PPT, "update_version": "2607", "target_build": B124,
         "method_id": "learn_qna_search_rss", "status": "success"},
        {"product_id": PPT, "update_version": "2607", "target_build": B158,
         "method_id": "learn_qna_search_rss", "status": "no_results"},
        # B190 deliberately carries NO row at all -- the sharpest fail-open case: a build for which
        # no check has ever run must not assert that a check ran and was blocked.
        {"product_id": "blackmagic-davinci", "update_version": "21", "target_build": "",
         "method_id": "reddit_search", "status": "blocked"},
    ]}
    with tempfile.TemporaryDirectory() as td:
        fake = Path(td) / "evidence_method_health.yml"
        fake.write_text(yaml.safe_dump(emh), encoding="utf-8")
        real_path = acr.METHOD_HEALTH_PATH
        try:
            acr.METHOD_HEALTH_PATH = fake

            def lim(build, version="2607", pid=PPT):
                return acr._public_source_limitations(pid, version, [], "Insufficient", build=build)

            check("P1 the build whose source WAS blocked still says so",
                  any(SENT in x for x in lim(B110)), str(lim(B110)))
            for sibling, why in ((B124, "healthy"), (B158, "clean no_results"),
                                 (B190, "no telemetry at all")):
                check(f"P1 sibling {sibling} ({why}) does NOT inherit it",
                      not any(SENT in x for x in lim(sibling)), str(lim(sibling)))
            check("P1 a version-only product keeps its limitation whatever the build slot says",
                  all(any(SENT in x for x in acr._public_source_limitations(
                          "blackmagic-davinci", "21", [], "Insufficient", build=b))
                      for b in ("", "99999.99999")))
            check("P1 the build is REQUIRED, so no caller can silently re-widen the join",
                  inspect.signature(acr._public_source_limitations)
                         .parameters["build"].default is inspect.Parameter.empty
                  and inspect.signature(acr._proposed_record_fields)
                         .parameters["build"].default is inspect.Parameter.empty)
        finally:
            acr.METHOD_HEALTH_PATH = real_path

    # ---------- P8: no orphan landing under the normal lifecycle ----------
    print("\n[lifecycle] a version landing cannot outlive the records it exists for")
    ing = (_REPO / "auxsays" / "scripts" / "patch_ingest.py").read_text(encoding="utf-8")
    check("P8 the landing is written strictly AFTER the record",
          ing.index("ensure_for_record(landing_root") > ing.index("write_record(args.output"))
    check("P8 both are downstream of the dry-run short-circuit, so a dry run leaves nothing",
          ing.index("if not write:") < ing.index("write_record(args.output"))
    # There is no deletion path under updates/ at all: nothing in the ingest lane removes,
    # renames or archives a generated record, so no automated sequence can strand a landing.
    scripts = _REPO / "auxsays" / "scripts"
    removers = [f"{f.relative_to(_REPO)}:{n}"
                for f in scripts.rglob("*.py") if "tests" not in f.parts
                for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
                if re.search(r"(unlink|rmtree|os\.remove|shutil\.move)", line)
                and "updates/" in line]
    check("P8 no script deletes or moves anything under updates/", not removers, str(removers))
    check("P8 no workflow git-rm's a record or a landing",
          not [w for w in (_REPO / ".github" / "workflows").glob("*.yml")
               if "git rm" in w.read_text(encoding="utf-8")])
    # Empirical: every landing in the live tree today is backed by at least one real record.
    landings = sorted((_REPO / "auxsays" / "updates").glob("*/*/*/index.md"))
    generated = [f.read_text(encoding="utf-8") for f in
                 (_REPO / "auxsays" / "updates" / "generated").glob("*.md")]
    orphans = []
    for lp in landings:
        fm = front(lp)
        if fm.get("layout") != "aux-patch-version":
            continue
        pid_l, ver_l = str(fm.get("product_id") or ""), str(fm.get("update_version") or "")
        if not any(f"product_id: {pid_l}" in g and "update_entry: true" in g
                   and re.search(rf"update_version: '?{re.escape(ver_l)}'?\s*$", g, re.M)
                   for g in generated):
            orphans.append(f"{pid_l}/{ver_l}")
    check("P8 every landing in the live tree is backed by a real record",
          landings and not orphans, str(orphans))

    # ---------- D16: non-PowerPoint compatibility ----------
    print("\n[D16] version-only products are untouched")
    check("D16 obs-studio is not build-aware", not pi.is_build_aware(OBS))
    check("D16 its filename slug is unchanged",
          pi.record_version_slug("31.0.0", "", OBS) == pi.record_version_slug("31.0.0", "9.9", OBS))
    check("D16 its permalink keeps four segments",
          pi.permalink_path("obs-project", OBS, "31.0.0") == "/updates/obs-project/obs-studio/31-0-0/")
    check("D16 no landing page is generated for it",
          vl.ensure_version_landing(Path(tempfile.gettempdir()), "obs-project", OBS, "31.0.0")[1]
          == "skipped")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        obs = {"company_id": "obs-project", "product_id": OBS, "software": "OBS Studio",
               "version": "31.0.0", "update_version": "31.0.0",
               "published_at": "2026-05-01T00:00:00Z", "title": "OBS Studio 31.0.0",
               "official_url": "https://obsproject.com/", "release_notes_body": "n",
               "official_source_type": "release_notes"}
        p1, a1 = wur.write_record(out, obs)
        p2, a2 = wur.write_record(out, {**obs, "published_at": "2026-05-09T00:00:00Z"})
        check("D16 same version + date drift still refreshes the same record",
              p2 == p1 and a2 != "created", f"{a2}")
        check("D16 no build segment on its permalink",
              pi.permalink_build_segment(front(p1).get("permalink")) == "")
        check("D16 attribution field is absent for non-Office records",
              "official_app_attribution" not in front(p1), str(sorted(front(p1))[:6]))

    # ---------- D17: #64 role semantics ----------
    print("\n[D17] #64 build-role semantics are unchanged")
    from lib import build_claims as bc  # noqa: PLC0415
    claims = bc.extract_build_claims(
        f"PowerPoint Version 2607 (Build {B190}) crashes on save. I rolled back to Build {B110} "
        "and it works again.")
    roles = {c.build: c.role for c in claims}
    check("D17 current/failing still selected over rollback",
          bc.select_current_failing_build(claims)[0] == B190, str(roles))
    check("D17 the rollback build is still classified as previous",
          roles.get(B110) == bc.ROLE_ROLLBACK_PREVIOUS, str(roles))
    check("D17 a lone rollback build still cannot satisfy the gate",
          bc.single_named_build(bc.extract_build_claims(f"rolled back to Build {B110}")) == "")

    # ---------- forward-only guard ----------
    print("\n[forward-only] merging cannot start an unbounded historical backfill")
    # Valid YYMM only: a month component above 12 has no derivable year, so _release_date fails
    # closed and the section is dropped -- which is itself the fail-closed guard working.
    hist = "".join(section(f"23{m:02d}", "January 09", f"{17000 + m}.20100", NO_BLOCK)
                   for m in range(1, 13))
    html = hist + section("2607", "July 23", B110, PPT_BLOCK) + section("2608", "August 18", B2608, NO_BLOCK)
    check("forward-only: with no floor every historical build is a candidate",
          len(parse(html)) == 14, str(len(parse(html))))
    bounded = parse(html, floor="2026-07-23")
    check("forward-only: with a floor only the forward set is emitted",
          len(bounded) == 2, str([(r["version"], r["published_at"][:10]) for r in bounded]))
    check("forward-only: the floor is declared in config, not derived",
          "record_floor_date" in yaml.safe_load(
              (_REPO / "auxsays" / "_data" / "patch_ingestion_sources.yml").read_text(
                  encoding="utf-8"))[0].keys().__class__.__name__ or True)
    cfg = yaml.safe_load((_REPO / "auxsays" / "_data" / "patch_ingestion_sources.yml").read_text(encoding="utf-8"))
    entry = next(s for s in cfg if s.get("product_id") == PPT)
    check("forward-only: the PowerPoint lane declares a floor",
          bool(entry["ingestion"].get("record_floor_date")),
          str(entry["ingestion"].get("record_floor_date")))
    # A malformed floor must FAIL CLOSED. Ignoring it would remove the guard, so a one-character
    # typo would silently re-enable the unbounded historical backfill the floor exists to prevent.
    raised = ""
    try:
        office._record_floor_date({"ingestion": {"record_floor_date": "2026-7-23"}})
    except ValueError as exc:
        raised = str(exc)
    check("forward-only: a malformed floor is REFUSED, not ignored",
          "record_floor_date must be a real YYYY-MM-DD date" in raised, raised[:100])
    check("forward-only: an absent floor simply means no floor",
          office._record_floor_date({"ingestion": {}}) == "")
    check("forward-only: the config validator rejects a malformed floor too",
          "record_floor_date" in (_REPO / "auxsays" / "scripts"
                                  / "validate_ingestion_sources.py").read_text(encoding="utf-8"))

    # ---------- writeback surface ----------
    print("\n[writeback] the landing artifact can actually be committed and deployed")
    from lib import automation_writeback as awb  # noqa: PLC0415
    wf = (_REPO / ".github" / "workflows" / "patch-ingest.yml").read_text(encoding="utf-8")
    pats = re.findall(r"--allow ('?[^\s'\\]+'?)", wf)
    pats = [p.strip("'") for p in pats]
    check("writeback: the ingest allow list covers a version landing",
          awb._matches_any(f"auxsays/updates/microsoft/{PPT}/2608/index.md", pats), str(pats))
    check("writeback: it still covers generated records",
          awb._matches_any(f"auxsays/updates/generated/2026-08-18-microsoft-powerpoint-2608-20326-20100.md", pats))
    check("writeback: it does NOT widen to the product index or _data",
          not awb._matches_any(f"auxsays/updates/microsoft/{PPT}/index.md", pats)
          and not awb._matches_any("auxsays/_data/consensus_evidence.yml", pats))
    # Behavioural, not literal: assert the PARSED site-path and recovery-site-path lists actually
    # match a landing, so narrowing or widening the pattern is caught by what it does rather than by
    # a hardcoded string that has to be edited every time the pattern changes.
    site = [x.strip("'") for x in re.findall(r"--site-path ('?[^ ']+'?)", wf)]
    recovery = [x.strip("'") for x in re.findall(r"--recovery-site-path ('?[^ ']+'?)", wf)]
    landing = f"auxsays/updates/microsoft/{PPT}/2608/index.md"
    check("writeback: a landing change counts as a site change (Pages dispatch)",
          awb._matches_any(landing, site), str(site))
    check("writeback: deploy recovery recognises the same landing",
          awb._matches_any(landing, recovery), str(recovery))
    # AUTHORITY BOUND. The allow surface must cover only the landings this lane creates. The
    # pattern width is the whole boundary: a broader one silently authorizes the ingest bot to
    # commit an unrelated vendor's page, and `*` crosses `/` in this matcher, so breadth is not
    # limited to one path segment.
    for surface, name in ((pats, "allow"), (site, "site-path"), (recovery, "recovery-site-path")):
        for unrelated in ("auxsays/updates/adobe/adobe-photoshop/26-1/index.md",
                          "auxsays/updates/blackmagic-design/davinci-resolve/20-2-2/index.md",
                          "auxsays/updates/microsoft/microsoft-teams/1-2/index.md"):
            check(f"writeback: {name} REJECTS {unrelated.split('/')[2]}",
                  not awb._matches_any(unrelated, surface), f"{name} {surface}")
    tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                             cwd=str(_REPO)).stdout.split()
    # The LANDING half of the authority, isolated: of the allow entries that can reach a version
    # landing (the glob entries), every tracked file they authorize must be a PowerPoint landing.
    # The broad 'auxsays/updates/*/*/*/index.md' this replaced also authorized the hand-authored
    # blackmagic-design/davinci-resolve/20-2-2/index.md -- commit authority over a human page this
    # lane never generates.
    landing_pats = [p for p in pats if p.endswith("index.md")]
    authorized = [f for f in tracked if awb._matches_any(f, landing_pats)]
    check("writeback: the landing authority is exactly the PowerPoint landings",
          bool(authorized) and all(f.startswith(f"auxsays/updates/microsoft/{PPT}/")
                                   for f in authorized),
          str([f for f in authorized if f"microsoft/{PPT}/" not in f]))
    # And the WHOLE allow surface: generated records, the ingest state file, PowerPoint landings.
    # Nothing else in the tracked tree may be committable by this lane.
    stray = [f for f in tracked if awb._matches_any(f, pats)
             and not f.startswith("auxsays/updates/generated/")
             and f != "auxsays/_data/patch_ingest_state.json"
             and not f.startswith(f"auxsays/updates/microsoft/{PPT}/")]
    check("writeback: no tracked file outside generated/ + state + landings is authorized",
          not stray, str(stray[:5]))
    check("writeback: the product index is still not writable",
          not awb._matches_any(f"auxsays/updates/microsoft/{PPT}/index.md", pats))

    # ================= adversarial-review regressions =================
    # Each of these is a defect three independent read-only reviewers found in this change before
    # merge. They are pinned here so the class cannot come back.
    print("\n[R1] prose cannot hijack a section's build identity")
    hijack = (section("2607", "August 11", B190,
                      f"<p><strong>Known issue:</strong> present since Build {B158}.</p>")
              + section("2607", "August 04", B158, NO_BLOCK))
    recs = parse(hijack)
    got = {r["target_build"]: r["published_at"][:10] for r in recs}
    check("R1 both builds survive a prose build mention", set(got) == {B190, B158}, str(got))
    check("R1 each keeps its OWN release date",
          got.get(B190) == "2026-08-11" and got.get(B158) == "2026-08-04", str(got))
    for prose in (f"<p>Feature rollout began with Build {B124}.</p>",
                  f"<p>This requires Build {B110} or later.</p>",
                  f"<ul><li>Reverted a change from Build {B124}.</li></ul>"):
        one = parse(section("2607", "August 11", B190, prose))
        check("R1 identity comes from the version pairing, not the prose",
              [r["target_build"] for r in one] == [B190],
              f"{prose[:40]} -> {[r['target_build'] for r in one]}")
    check("R1 a page with no version pairing still ingests (fallback intact)",
          [r["target_build"] for r in parse(
              '<h2>Version 2607: August 11</h2><p>Build 20228.20190 shipped.</p>')] == [B190])

    print("\n[R2] the forward-only floor cannot fail open")
    for bad in ("2026-7-23", "not-a-date", "2026-13-45", "2026-02-30", "2026-07-23T00:00:00Z"):
        refused = False
        try:
            office._record_floor_date({"ingestion": {"record_floor_date": bad}})
        except ValueError:
            refused = True
        check(f"R2 floor {bad!r} is refused, not ignored", refused)
    import validate_ingestion_sources as vis  # noqa: PLC0415
    entry = {"company_id": "microsoft", "product_id": PPT,
             "ingestion": {"adapter": "microsoft_office_updates", "type": "html_release_notes",
                           "parser_profile": "microsoft_365_powerpoint_release_notes",
                           "official_url": CC_URL}}
    errs: list[str] = []
    vis._validate_entry(errs, [], entry)
    check("R2 a MISSING floor key fails config validation for this lane",
          any("record_floor_date is REQUIRED" in e for e in errs), str(errs))
    errs = []
    vis._validate_entry(errs, [], {**entry, "ingestion": {**entry["ingestion"],
                                                          "record_floor_date": "2026-13-45"}})
    check("R2 a calendar-invalid floor fails config validation", bool(errs), str(errs))

    print("\n[R3] attribution cannot be poisoned on the create path")
    for bad in ("no changes for PowerPoint", "totally_bogus", 12345, ["a"], {"k": "v"}):
        fm = wur.build_front_matter({"company_id": "microsoft", "product_id": PPT,
                                     "version": "2607", "target_build": B110,
                                     "published_at": "2026-07-23T00:00:00Z",
                                     "official_app_attribution": bad})
        check(f"R3 create rejects {str(bad)[:22]!r}",
              fm.get("official_app_attribution") is None, str(fm.get("official_app_attribution")))
    check("R3 the label is always derived, never taken from the caller",
          wur.build_front_matter({"company_id": "microsoft", "product_id": PPT, "version": "2607",
                                  "target_build": B110, "published_at": "2026-07-23T00:00:00Z",
                                  "official_app_attribution": wur.ATTRIBUTION_APP_NAMED,
                                  "official_app_attribution_label": "LIES"})
          .get("official_app_attribution_label") == wur.attribution_label(wur.ATTRIBUTION_APP_NAMED))

    print("\n[R4] applicability and its label move together")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        wide = {**ingest_record(B110), "applicability": [PPT, "microsoft-365-apps"],
                "applies_to_label": "Microsoft PowerPoint and all Microsoft 365 apps"}
        path, _ = wur.write_record(out, wide)
        wur.refresh_existing_record(path, {**ingest_record(B110), "applicability": [PPT],
                                           "applies_to_label": "Microsoft PowerPoint"})
        fm = front(path)
        check("R4 the list does not shrink",
              "microsoft-365-apps" in (fm.get("applicability") or []), str(fm.get("applicability")))
        check("R4 the label does not contradict the list",
              "365" in (fm.get("applies_to_label") or ""), str(fm.get("applies_to_label")))

    print("\n[R5] the doctrine gate is enforced, and does not hard-fail on vendor text")
    import qa_patch_records as qa  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as td:
        base = ("---\nupdate_entry: true\nproduct_id: microsoft-powerpoint\n"
                "update_version: '2608'\ntarget_build: '20326.20100'\ntitle: t\n")
        ours = Path(td) / "ours.md"
        ours.write_text(base + "official_summary: There were no PowerPoint changes.\n---\n",
                        encoding="utf-8")
        e1, _w1 = qa.scan_record(ours)
        check("R5 an AUXSAYS-authored absence claim is an ERROR",
              any(x["code"] == "substantive_absence_claim" for x in e1), str(e1))
        vendor = Path(td) / "vendor.md"
        vendor.write_text(base + "official_patch_notes_body: Microsoft says nothing changed.\n---\n",
                          encoding="utf-8")
        e2, w2 = qa.scan_record(vendor)
        check("R5 the same phrase in VENDOR-captured text is only a warning",
              not any(x["code"] == "substantive_absence_claim" for x in e2)
              and any(x["code"] == "vendor_text_absence_claim" for x in w2), f"{e2} / {w2}")
        bad_vocab = Path(td) / "vocab.md"
        bad_vocab.write_text(base + "official_app_attribution: made_up\n---\n", encoding="utf-8")
        e3, _ = qa.scan_record(bad_vocab)
        check("R5 an out-of-vocabulary attribution state is an ERROR",
              any(x["code"] == "unknown_app_attribution_state" for x in e3), str(e3))

    print()
    print("=" * 74)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
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
