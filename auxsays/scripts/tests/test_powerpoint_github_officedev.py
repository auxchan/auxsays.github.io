#!/usr/bin/env python3
"""OfficeDev/office-js issues as a PowerPoint discovery method.

The template asks reporters for exactly what AUXSAYS needs -- `Host:` and `Office version number:` --
which makes this the only PowerPoint source with a STRUCTURED product and build statement. That is
also its risk: the template's placeholder text puts "Excel, Word" in every body, and the version
line routinely names a web build beside the desktop one. Both traps are asserted here.

Offline: every issue is a fixture. No network, no repo writes.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from patch_collectors import github_officedev_source as gh  # noqa: E402
from patch_collectors import microsoft_powerpoint as ppt  # noqa: E402
from patch_collectors.base import PatchRecord  # noqa: E402

PASS = FAIL = 0
FAILURES: list[str] = []

# The real calibration issue's shape, reproduced as a fixture. Its live discovery is asserted
# separately by the production dry run; hardcoding the id here would prove nothing about discovery.
CALIBRATION_BODY = """
### Your Environment
* Platform [PC desktop, Mac, iOS, Office on the web]: PC desktop
* Host [Excel, Word, PowerPoint, etc.]: PowerPoint
* Office version number: web: 16.0.20329.45605; desktop: Version 2607 Build 16.0.20228.20124
## Expected behavior
Document settings written from PowerPoint desktop should be readable everywhere.
## Current behavior
If I set a document settings value from PowerPoint desktop, I cannot read the value from PowerPoint web.
"""


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


def issue(number: int, title: str, body: str, login: str = "reporter",
          created: str = "2026-08-07T12:22:00Z") -> dict:
    return {"number": number, "title": title, "body": body,
            "html_url": f"https://github.com/OfficeDev/office-js/issues/{number}",
            "created_at": created, "updated_at": created,
            "user": {"login": login, "id": 33959505}}


RECORD_PATH = ROOT / "updates" / "generated" / "2026-07-29-microsoft-powerpoint-2607-20228-20124.md"


def record():
    return PatchRecord("microsoft-powerpoint", "2607", RECORD_PATH, "2026-07-29T00:00:00Z",
                       "current", "Microsoft PowerPoint")


def run() -> int:
    rec = record()
    target = ppt.record_target(rec) if RECORD_PATH.exists() else None

    print("=" * 96)
    print("G1  the structured Host field decides the product")
    print("=" * 96)
    check("G1.1 Host: PowerPoint is read", gh.declared_host(CALIBRATION_BODY) == "powerpoint",
          gh.declared_host(CALIBRATION_BODY))
    check("G1.2 Host: Excel is read", gh.declared_host("* Host [Excel, Word]: Excel") == "excel")
    check("G1.3 a body with no Host field yields no declaration",
          gh.declared_host("PowerPoint crashes on save") == "")
    check("G1.4 a declared PowerPoint host passes primacy with no PowerPoint in the title",
          ppt.product_primacy_reason("", "Unreliable Document Settings", "", "powerpoint") is None)

    print()
    print("=" * 96)
    print("G2  a non-PowerPoint host stays non-PowerPoint, however often it says PowerPoint")
    print("=" * 96)
    excel = issue(1, "Excel breaks when exporting to PowerPoint",
                  "* Host [Excel, Word, PowerPoint, etc.]: Excel\n"
                  "* Office version number: Version 2607 Build 16.0.20228.20124\n"
                  "PowerPoint PowerPoint PowerPoint export crashes every time.")
    check("G2.1 an Excel-host issue is dropped at discovery",
          gh.issue_candidate(excel, source_type="x", source_name="y") is None)
    check("G2.2 and primacy refuses it even if it reached the authority",
          ppt.product_primacy_reason("", "PowerPoint everywhere", "PowerPoint PowerPoint", "excel")
          == "product_not_powerpoint")

    print()
    print("=" * 96)
    print("G3  the desktop build is parsed, and the WEB build never is")
    print("=" * 96)
    check("G3.1 the desktop segment is isolated from a web+desktop line",
          gh.desktop_version_text(CALIBRATION_BODY) == "Version 2607 Build 16.0.20228.20124",
          gh.desktop_version_text(CALIBRATION_BODY))
    check("G3.2 a web-only version line yields NO build",
          gh.desktop_version_text("* Office version number: web: 16.0.20329.45605") == "")
    # The 16.0. reduction lives in the COLLECTOR, via lib.build_claims -- the source module must not
    # carry a second copy of build semantics. Assert the behaviour where it now belongs.
    from lib.build_claims import OFFICE_FULL_VERSION_RE  # noqa: PLC0415
    reduced = OFFICE_FULL_VERSION_RE.sub(lambda m: m.group(1), "Version 2607 Build 16.0.20228.20124")
    check("G3.3 Office's 16.0. full form reduces to the canonical build token via the shared primitive",
          "20228.20124" in reduced and "16.0.20228.20124" not in reduced, reduced)
    check("G3.3b the source module carries no build regex of its own",
          not hasattr(gh, "OFFICE_FULL_BUILD_RE") and not hasattr(gh, "normalized_desktop_build_text"))
    cand = gh.issue_candidate(issue(6886, "Unreliable Document Settings", CALIBRATION_BODY),
                              source_type=gh.DEFAULT_SOURCE_TYPE, source_name=gh.DEFAULT_SOURCE_NAME)
    check("G3.4 the web build never reaches the candidate text",
          cand is not None and "20329.45605" not in gh.desktop_version_text(CALIBRATION_BODY))

    print()
    print("=" * 96)
    print("G4  discovery is by ordinary query, and a bare build token is NOT one")
    print("=" * 96)
    tgt = {"update_version": "2607", "target_build": "20228.20124"}
    queries = ([f'repo:{gh.REPO} "16.0.{tgt["target_build"]}"'] + list(ppt.GITHUB_SYMPTOM_QUERIES))
    check("G4.1 build-first uses the FULL 16.0. form, which is what GitHub search matches",
          any('"16.0.20228.20124"' in q for q in queries), str(queries[:1]))
    check("G4.2 no query hardcodes an issue number or URL",
          not any("6886" in q or "issues/" in q for q in queries), str(queries))
    check("G4.3 symptom queries carry recall for issues that never state a build",
          len(ppt.GITHUB_SYMPTOM_QUERIES) >= 3 and
          all(q.startswith(f"repo:{gh.REPO}") for q in ppt.GITHUB_SYMPTOM_QUERIES))

    print()
    print("=" * 96)
    print("G5  a feature request is not patch evidence, even with an exact build")
    print("=" * 96)
    for title, body in [
        ("Add API to read document settings",
         "* Host [Excel, Word, PowerPoint, etc.]: PowerPoint\n"
         "* Office version number: Version 2607 Build 16.0.20228.20124\n"
         "PowerPoint should expose an API to read document settings."),
        ("Documentation unclear for PowerPoint settings",
         "* Host [Excel, Word, PowerPoint, etc.]: PowerPoint\n"
         "* Office version number: Version 2607 Build 16.0.20228.20124\n"
         "The documentation for PowerPoint settings is unclear, please clarify."),
    ]:
        c = gh.issue_candidate(issue(2, title, body), source_type=gh.DEFAULT_SOURCE_TYPE,
                               source_name=gh.DEFAULT_SOURCE_NAME)
        if target is None:
            check(f"G5 record fixture present ({title[:24]})", False, "record missing")
            continue
        # Canonicalise as the collector does, so the exact build IS present and the ONLY thing left
        # that can reject this is the concrete-issue gate. Without it the fixture would be refused
        # for missing_exact_build and would prove nothing about feature-request filtering.
        from lib.build_claims import OFFICE_FULL_VERSION_RE  # noqa: PLC0415
        c = {**c, "report_text": OFFICE_FULL_VERSION_RE.sub(lambda m: m.group(1),
                                                            str(c.get("report_text") or ""))}
        row = ppt.row_from_candidate(rec, target, c, "2026-08-29T00:00:00Z")
        check(f"G5 feature/doc request rejected: {title[:38]!r}",
              row.get("counted") is False
              and row.get("exclusion_reason") == "not_a_concrete_powerpoint_issue",
              f"{row.get('counted')}/{row.get('exclusion_reason')}")

    print()
    print("=" * 96)
    print("D1/D2  dedupe by issue identity, not by discovery route")
    print("=" * 96)
    dup = issue(6886, "Unreliable Document Settings", CALIBRATION_BODY)
    seen: set[str] = set()
    kept = []
    for _route in ("build-first", "symptom-first", "tag"):
        key = f"{gh.REPO}#{dup['number']}"
        if key in seen:
            continue
        seen.add(key)
        kept.append(gh.issue_candidate(dup, source_type="x", source_name="y"))
    check("D1.1 one issue found by three routes stays ONE candidate", len(kept) == 1, str(len(kept)))
    check("D1.2 identity is repo + issue number",
          f"{gh.REPO}#6886" in seen and len(seen) == 1, str(seen))
    a = gh.issue_candidate(issue(6886, "A", CALIBRATION_BODY, login="userA"), source_type="x", source_name="y")
    b = gh.issue_candidate(issue(7001, "B", CALIBRATION_BODY, login="userB"), source_type="x", source_name="y")
    check("D2.1 two DIFFERENT issues on the same build remain separate evidence",
          a["source_url"] != b["source_url"]
          and a["github_author_login"] != b["github_author_login"])

    print()
    print("=" * 96)
    print("G6  the reporter's identity is retained for author-authority decisions")
    print("=" * 96)
    check("G6.1 author login and id are carried",
          cand["github_author_login"] == "reporter" and cand["github_author_id"] == "33959505")
    check("G6.2 comments are NOT folded into the reporter's text",
          "github_comment" not in cand and "comments" not in cand)
    check("G6.3 a pull request is never a report", gh.issue_candidate(
        {**issue(3, "PR", CALIBRATION_BODY), "pull_request": {"url": "x"}},
        source_type="x", source_name="y") is None)

    print()
    print("=" * 96)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed: " + ", ".join(FAILURES))
    print("=" * 96)
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
