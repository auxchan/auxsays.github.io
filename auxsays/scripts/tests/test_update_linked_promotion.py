#!/usr/bin/env python3
"""Second-tier (update-linked) promotion: a held report is counted only on its own stored facts.

`promote_update_linked_evidence.py` rebuilds a candidate from a held row's stored title, excerpt,
date and link, and puts it to the product's own unchanged `evaluate_candidates`. Accepted for
exactly one tracked patch -> appended through the store's append guard with its origin recorded,
and the held row leaves the second tier. Anything else stays where it is.

Measured at 12d207ba: 207 held rows (201 PowerPoint, 6 Acrobat), 0 qualify. 3 PowerPoint rows name a
full build in their stored text and the strict authority still refuses them (no PowerPoint version
context); no Acrobat row names a version at all. So this suite proves the route on fixtures written
to a temporary store and tier file, and pins the live corpus only by invariants.

Offline. The shipped store and tier files are read, never written.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import traceback
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import yaml  # noqa: E402

import promote_update_linked_evidence as promo  # noqa: E402
from patch_collectors import adobe_acrobat_community as acrobat  # noqa: E402
from patch_collectors import base  # noqa: E402

PASS = 0
FAIL = 0
TOOL = str(SCRIPTS / "promote_update_linked_evidence.py")
PRO = "adobe-acrobat-pro"


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")


def held_row(report_id: str, url: str, title: str, excerpt: str, day: str, **over) -> dict:
    data = {"report_id": report_id, "product_id": PRO, "source_family": "adobe community bug report",
            "source_type": "adobe_community_bug_report", "source_url": url, "report_date": day,
            "report_title": title, "report_excerpt": excerpt, "classification": "update_linked",
            "confirmation_state": "not_confirmed", "promotion_eligible": True,
            "strict_exclusion_reason": "missing_exact_patch_version_match",
            "captured_at": "2026-10-26T04:42:27Z"}
    data.update(over)
    return data


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, TOOL, *args], capture_output=True, text=True)


def run_suite() -> int:
    records = sorted(base.generated_records(PRO, None), key=lambda r: r.update_published_at)
    newest, older = records[-1], records[-2]
    day = (date.fromisoformat(newest.update_published_at[:10]) + timedelta(days=3)).isoformat()
    exact = (f"Acrobat Pro {newest.update_version} crashes every time I open a PDF since the update. "
             f"Reinstalling did not help.")
    vague = "After the new update Acrobat Pro crashes every time I open a PDF. Reinstalling did not help."
    two = (f"Acrobat Pro crashes every time I open a PDF on {newest.update_version} and on "
           f"{older.update_version}. Reinstalling did not help.")
    base_url = "https://community.adobe.com/questions-9/acrobat-pro-crashes-every-time-i-open-a-pdf-"

    print("C. the condition, on stored facts only")
    entries = promo.assess(PRO, [
        held_row("p:1", base_url + "1700001", "Acrobat Pro crashes on open", exact, day),
        held_row("p:2", base_url + "1700002", "Acrobat Pro crashes on open", vague, day),
        held_row("p:3", base_url + "1700003", "Acrobat Pro crashes on open", two, day),
        held_row("p:4", base_url + "1700004", "Acrobat Pro crashes on open", exact, ""),
        held_row("p:5", base_url + "1700005", "Acrobat Pro crashes on open", exact,
                 (date.fromisoformat(newest.update_published_at[:10]) - timedelta(days=30)).isoformat()),
        held_row("r:6", base_url + "1700006", "Acrobat Pro crashes on open", exact, day,
                 product_id="adobe-acrobat-reader"),
    ], records, promo._acrobat_accepts)
    by_id = {e["report_id"]: e for e in entries}
    check("C1 exact version, dated, linked, concrete -> qualifies for that one patch",
          by_id["p:1"]["outcome"] == "qualifies"
          and by_id["p:1"]["row"]["update_version"] == newest.update_version
          and by_id["p:1"]["row"]["counted"] is True, str(by_id["p:1"]["outcome"]))
    check("C2 the promoted row records where it came from",
          by_id["p:1"]["row"]["capture_method"] == "promoted_from_update_linked:p:1")
    check("C3 'after the new update' with no version does not qualify",
          by_id["p:2"]["outcome"] == "not_accepted", by_id["p:2"]["outcome"])
    # The Acrobat authority resolves a two-build report itself (its multi-build rule), so the
    # two-patch refusal is exercised with an authority that accepts both.
    def accepts_both(product_id, recs, candidate, captured_at):
        return [{"product_id": product_id, "update_version": newest.update_version, "counted": True},
                {"product_id": product_id, "update_version": older.update_version, "counted": True}]
    twice = promo.assess(PRO, [held_row("p:3", base_url + "1700003", "t", two, day)], records,
                         accepts_both)[0]
    check("C4 a report accepted for two patches is refused, not resolved",
          twice["outcome"] == "accepted_for_more_than_one_patch" and twice["row"] is None
          and len(twice["identities"]) == 2, twice["outcome"])
    check("C5 a row with no stored date cannot qualify",
          by_id["p:4"]["outcome"] == "missing_stored_fact", by_id["p:4"]["outcome"])
    check("C6 a report dated before the release does not qualify",
          by_id["p:5"]["outcome"] == "not_accepted", by_id["p:5"]["outcome"])
    check("C7 another product's held rows are not assessed", "r:6" not in by_id, str(sorted(by_id)))
    check("C8 the associated release window is never an input",
          "associated_update_version" not in promo.candidate_from_held(
              held_row("p:9", base_url + "9", "t", "e", day, associated_update_version="x")))

    print("X. what a held row carries (review M3)")
    last3 = records[-3:]
    oldest = last3[0]
    off = promo.assess(PRO, [
        held_row("p:20", base_url + "1700020", "Acrobat Pro crashes on open", exact, day,
                 promotion_eligible=False),
        held_row("p:21", base_url + "1700021", "Acrobat Pro crashes on open", exact, day,
                 confirmation_state="withdrawn"),
        {k: v for k, v in held_row("p:22", base_url + "1700022", "Acrobat Pro crashes on open", exact,
                                   day).items() if k != "promotion_eligible"},
        held_row("p:23", base_url + "1700023", "Acrobat Pro crashes on open", exact, day),
    ], last3, promo._acrobat_accepts)
    check("X1 a row that says it is not promotion-eligible is not put to the authority",
          [e["outcome"] for e in off[:3]] == ["not_promotion_eligible"] * 3
          and all(e["row"] is None for e in off[:3]) and off[3]["outcome"] == "qualifies",
          str([e["outcome"] for e in off]))
    # THE REVIEWER'S CASE. The report opens with the newest build and a crash; past the 280th
    # character it asks for another build's installer and cites a third. The authority rejects the
    # full report for every tracked patch; the stored excerpt alone reads as a clean report.
    head = (f"Acrobat Pro {newest.update_version} crashes every time I open a PDF since the update. "
            f"Reinstalling did not help. ")
    pad = ("I have tried repairing the installation, clearing preferences and disabling protected "
           "mode, with no change at all. ") * 3
    tail = (f"Can I get the installer for {older.update_version} to revert in the meantime? "
            f"The release notes for {oldest.update_version} mention this.")
    full = head + pad + tail
    excerpt = base.excerpt(full)
    cut_url = base_url + "1700030"
    on_full = []
    for record in last3:
        ok, _rejected = acrobat.evaluate_candidates(PRO, record, [{
            "source_type": "adobe_community_bug_report", "source_name": "Adobe Community",
            "source_url": cut_url, "parent_title": "Acrobat Pro crashes on open",
            "report_title": "Acrobat Pro crashes on open", "report_text": full, "source_date": day}],
            "2026-10-26T04:42:27Z")
        on_full.extend(ok)
    check("X2 the acceptance authority rejects the full report for every tracked patch",
          not on_full and excerpt.endswith("...") and len(excerpt) <= 280, str(len(on_full)))
    cut_row = held_row("p:30", cut_url, "Acrobat Pro crashes on open", excerpt, day)
    judged = promo.assess(PRO, [cut_row], last3, promo._acrobat_accepts)[0]
    check("X3 its cut excerpt is never promoted, whatever the authority says of the excerpt",
          judged["outcome"] == "qualifies_on_cut_excerpt_only" and judged["row"] is None,
          judged["outcome"])
    check("X4 'cut' fails closed: the placeholder, the storage cap, an empty excerpt",
          promo.stored_text_is_cut({"report_excerpt": "crashes on open..."})
          and promo.stored_text_is_cut({"report_excerpt": "crashes on open…"})
          and promo.stored_text_is_cut({"report_excerpt": "x" * 400})
          and promo.stored_text_is_cut({"report_excerpt": ""})
          and promo.stored_text_is_cut({"report_excerpt": "ok", "report_title": "t" * 300})
          and not promo.stored_text_is_cut({"report_excerpt": exact, "report_title": "Crash on open"}))
    with tempfile.TemporaryDirectory() as tmp:
        store, tier = Path(tmp) / "consensus_evidence.yml", Path(tmp) / "tier2.yml"
        base.write_evidence_file([{
            "id": "seed-1", "product_id": "obs-studio", "update_version": "32.1.2",
            "source_type": "github_issue", "source_name": "GitHub",
            "source_url": "https://github.com/obsproject/obs-studio/issues/1", "parent_title": "seed",
            "report_title": "seed", "report_text_excerpt": "seed", "captured_at": "2026-01-01T00:00:00Z",
            "patch_version_matched": True, "matched_version": "32.1.2",
            "match_basis": "exact_version_text", "counted": True, "exclusion_reason": None,
            "source_weight": 1}], store)
        tier.write_text(promo.dump_tier_file({"schema_version": 1, "note": "fixture"}, [cut_row]),
                        encoding="utf-8", newline="\n")
        s0, t0 = store.read_bytes(), tier.read_bytes()
        wrote = run("--product-id", PRO, "--evidence-path", str(store), "--tier2-path", str(tier), "--write")
        check("X5 --write on the reviewer's row appends nothing and leaves it in the second tier",
              wrote.returncode == 0 and store.read_bytes() == s0 and tier.read_bytes() == t0
              and "0 qualify" in wrote.stdout and "NOT promoted" in wrote.stdout,
              wrote.stdout[-300:] + wrote.stderr[-300:])
        # REVIEW S5: the step stands before the lane's only writeback.
        tier.write_text("- not\n- a mapping\n", encoding="utf-8")
        summary, output = Path(tmp) / "summary.md", Path(tmp) / "output.txt"
        env = {**os.environ, "GITHUB_STEP_SUMMARY": str(summary), "GITHUB_OUTPUT": str(output)}
        args = [sys.executable, TOOL, "--product-id", PRO, "--evidence-path", str(store),
                "--tier2-path", str(tier)]
        hard = subprocess.run(args, capture_output=True, text=True, env=env)
        silent = not summary.exists()
        soft = subprocess.run([*args, "--fail-soft"], capture_output=True, text=True, env=env)
        check("X6 without --fail-soft a broken tier file still fails the command",
              hard.returncode != 0 and silent, str(hard.returncode))
        check("X7 --fail-soft: exit 0, and the failure is in the log, the job summary and the step output",
              soft.returncode == 0 and "::error title=Second-tier promotion failed" in soft.stdout
              and summary.exists() and "FAILED (fail-soft)" in summary.read_text(encoding="utf-8")
              and "status=failed" in output.read_text(encoding="utf-8") and store.read_bytes() == s0,
              str(soft.returncode) + soft.stdout[-300:])
    workflow = yaml.safe_load((ROOT.parent / ".github" / "workflows" / "obs-evidence-collection.yml")
                              .read_text(encoding="utf-8"))
    commands = [line.split("#", 1)[0].strip()
                for job in workflow["jobs"].values() for step in job.get("steps", [])
                for line in str(step.get("run") or "").splitlines()
                if "promote_update_linked_evidence.py" in line.split("#", 1)[0]]
    check("X8 the scheduled lane runs promotion report-only and fail-soft: no --write on any call",
          len(commands) == 2 and all("--write" not in c.split() and "--fail-soft" in c.split()
                                     for c in commands), str(commands))

    print("W. the write, on a temporary store and tier file")
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "consensus_evidence.yml"
        tier = Path(tmp) / "tier2.yml"
        seed = {"id": "seed-1", "product_id": "obs-studio", "update_version": "32.1.2",
                "source_type": "github_issue", "source_name": "GitHub",
                "source_url": "https://github.com/obsproject/obs-studio/issues/1",
                "parent_title": "seed", "report_title": "seed", "report_text_excerpt": "seed",
                "captured_at": "2026-01-01T00:00:00Z", "patch_version_matched": True,
                "matched_version": "32.1.2", "match_basis": "exact_version_text", "counted": True,
                "exclusion_reason": None, "source_weight": 1}
        base.write_evidence_file([seed], store)
        held = [held_row("p:1", base_url + "1700001", "Acrobat Pro crashes on open", exact, day),
                held_row("p:2", base_url + "1700002", "Acrobat Pro crashes on open", vague, day),
                held_row("r:6", base_url + "1700006", "Acrobat Pro crashes on open", exact, day,
                         product_id="adobe-acrobat-reader")]
        tier.write_text(promo.dump_tier_file({"schema_version": 1, "note": "fixture"}, held),
                        encoding="utf-8", newline="\n")
        common = ("--product-id", PRO, "--evidence-path", str(store), "--tier2-path", str(tier))
        s0, t0 = store.read_bytes(), tier.read_bytes()
        dry = run(*common)
        check("W1 without --write nothing is written",
              dry.returncode == 0 and store.read_bytes() == s0 and tier.read_bytes() == t0
              and "1 qualify" in dry.stdout, dry.stdout[-300:] + dry.stderr[-300:])
        receipt = Path(tmp) / "receipt.json"
        done = run(*common, "--write", "--json", str(receipt))
        rows = base.load_evidence(store)
        left = yaml.safe_load(tier.read_text(encoding="utf-8"))["reports"]
        check("W2 --write succeeds", done.returncode == 0, done.stdout[-300:] + done.stderr[-400:])
        check("W3 one counted row is appended and the seed row is untouched",
              len(rows) == 2 and rows[0] == base.load_evidence(store)[0] and rows[0]["id"] == "seed-1"
              and rows[1]["counted"] is True and rows[1]["product_id"] == PRO
              and rows[1]["update_version"] == newest.update_version, str(len(rows)))
        check("W4 the store keeps the audit trail on the row",
              rows[-1].get("capture_method") == "promoted_from_update_linked:p:1",
              str(rows[-1].get("capture_method")))
        check("W5 the store was appended to, byte for byte", store.read_bytes().startswith(s0))
        check("W6 the promoted report left the second tier; the others stayed",
              [r["report_id"] for r in left] == ["p:2", "r:6"], str([r["report_id"] for r in left]))
        data = json.loads(receipt.read_text(encoding="utf-8")) if receipt.exists() else {}
        check("W7 the receipt names what was appended and what left the tier",
              data.get("promoted_out") == ["p:1"] and len(data.get("appended", [])) == 1
              and data.get("examined") == 2, str(data)[:300])
        s1, t1 = store.read_bytes(), tier.read_bytes()
        again = run(*common, "--write")
        check("W8 a second run changes nothing",
              again.returncode == 0 and store.read_bytes() == s1 and tier.read_bytes() == t1,
              again.stdout[-200:])
        # A report the store holds WITHDRAWN for that patch is never re-admitted by promotion.
        withdrawn = dict(rows[-1], counted=False, exclusion_reason="not_a_real_issue_report")
        base.write_evidence_file([seed, withdrawn], store)
        tier.write_bytes(t0)
        s2 = store.read_bytes()
        blocked = run(*common, "--write")
        left = yaml.safe_load(tier.read_text(encoding="utf-8"))["reports"]
        check("W9 a withdrawn report is not re-admitted and stays in the second tier",
              blocked.returncode == 0 and store.read_bytes() == s2
              and "p:1" in [r["report_id"] for r in left], blocked.stdout[-300:])

    print("S. scope")
    none = run()
    check("S1 a product scope is required", none.returncode == 2, str(none.returncode))
    empty = run("--product-id", "")
    check("S2 an empty product scope is refused", empty.returncode == 2, str(empty.returncode))
    other = run("--product-id", "obs-studio")
    check("S3 a product with no second tier is refused", other.returncode == 2, str(other.returncode))

    print("L. the shipped files (read only)")
    for label, path in (("PowerPoint", promo.POWERPOINT_TIER2), ("Acrobat", promo.ACROBAT_TIER2)):
        doc, rows = promo.load_tier_file(path)
        check(f"L {label}: an unchanged tier file is rewritten byte for byte",
              promo.dump_tier_file(doc, rows) == path.read_text(encoding="utf-8"))
    counted_urls = {promo.report_url_key(str(r.get("source_url") or ""))
                    for r in base.load_evidence() if r.get("counted") is True}
    both = [r.get("report_id") for path in (promo.POWERPOINT_TIER2, promo.ACROBAT_TIER2)
            for r in promo.load_tier_file(path)[1]
            if r.get("classification") == "update_linked"
            and promo.report_url_key(str(r.get("source_url") or "")) in counted_urls
            and r.get("product_id") in {x.get("product_id") for x in base.load_evidence()
                                        if x.get("counted") is True
                                        and promo.report_url_key(str(x.get("source_url") or ""))
                                        == promo.report_url_key(str(r.get("source_url") or ""))}]
    check("L3 no update-linked report is also a counted report for the same product", not both,
          str(both[:3]))

    print("=" * 78)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run_suite())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
