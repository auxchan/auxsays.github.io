#!/usr/bin/env python3
"""PowerPoint R3: shared build token + explicit build-ROLE attribution.

Two corrections, one primitive. ``lib.build_claims`` is the single place a Click-to-Run build is
recognised and the single place a build's ROLE is decided, so the collector's acceptance gate and
the orchestration graph's context-resolution stage can no longer read builds differently.

The role classifier exists because "several builds named" is not the same as "we cannot tell which
build this is about". An author who writes "on 2607 (Build A) it crashes, I rolled back to Build B
and it works" has answered the question explicitly. Only their OWN language may answer it: there is
no first/last-build rule, no proximity to the tracked YYMM, no release chronology, and no AI.

Every acceptance decision below runs through the REAL authority (``ppt.row_from_candidate`` /
``ppt.build_check``). Offline and deterministic.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_powerpoint_build_roles.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from lib import build_claims as bc  # noqa: E402
from lib import context_resolution as cr  # noqa: E402
from lib import source_segments as ss  # noqa: E402
from patch_collectors import microsoft_powerpoint as ppt  # noqa: E402
from patch_collectors.base import PatchRecord  # noqa: E402

PRODUCT = "microsoft-powerpoint"
VERSION = "2607"
BUILD = "20228.20110"          # the tracked target
ROLLBACK = "20131.20154"       # a genuinely older build
OTHER = "20028.20190"
THIRD = "20228.20300"
RELEASE = "2026-07-23T00:00:00Z"
CAPTURED = "2026-08-01T00:00:00Z"
QID = "5975138"
URL = f"https://learn.microsoft.com/en-us/answers/questions/{QID}/ppt-crash"
OP = ("Real Reporter", "5eee431a-ba0c-439a-961f-fe3092adbd65")
REPLIER = ("Someone Else", "7bf13722-2ad4-4e15-a104-eca51777522d")
AI = ("AI answer", "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1")

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


def target(build: str = BUILD) -> dict:
    return {"update_version": VERSION, "target_build": build,
            "target_release_date": RELEASE, "version_ambiguous": False}


def record(build: str = BUILD) -> PatchRecord:
    return PatchRecord(product_id=PRODUCT, update_version=VERSION, path=Path("x.md"),
                       update_published_at=RELEASE, update_status="current",
                       update_product="Microsoft PowerPoint", target_build=build)


def candidate(text: str, url: str = URL) -> dict:
    return {"source_url": url, "parent_title": f"PowerPoint Version {VERSION} crash",
            "report_title": "", "report_text": text, "source_date": "2026-08-14",
            "source_type": "microsoft_learn_qna", "source_name": "Microsoft Learn Q&A"}


def row(text: str, build: str = BUILD) -> dict:
    return ppt.row_from_candidate(record(build), target(build), candidate(text), CAPTURED)


def qapage(question_text: str, answers=(), qid: str = QID) -> str:
    payload = {
        "@context": "https://schema.org", "@type": "QAPage",
        "mainEntity": {
            "@type": "Question", "id": qid, "name": f"PowerPoint Version {VERSION} crash",
            "text": f"<p>{question_text}</p>", "answerCount": len(answers),
            "author": OP[0], "authorId": OP[1], "acceptedAnswer": [],
            "suggestedAnswer": [
                {"@type": "Answer", "id": str(9000 + i), "text": f"<p>{t}</p>", "author": who[0],
                 "authorId": who[1], "authorRole": "Independent Advisor",
                 "updatedAt": "2026-08-14T07:47:43Z",
                 "url": f"https://learn.microsoft.com/en-us/answers/a/{9000 + i}"}
                for i, (t, who) in enumerate(answers)],
            "moderatorRecommendedAnswers": [],
        },
    }
    return '<script type="application/ld+json">' + json.dumps(payload) + "</script>"


def resolve(page: str, cand: dict | None = None, budget=None):
    cand = cand if cand is not None else candidate(f"PowerPoint {VERSION} crashes on save.")
    budget = budget or cr.ResolutionBudget()
    out = cr.resolve_candidate(cand, cr.RESOLVABLE_REASON,
                               fetch_thread=lambda _u: (page, "ok"), budget=budget)
    return out, budget, cand


CRASH_BLOCK = (
    '<Event><System><Provider Name="Application Error"/><EventID>1000</EventID></System>'
    '<EventData><Data Name="AppName">POWERPNT.EXE</Data>'
    '<Data Name="AppVersion">16.0.{build}</Data>'
    '<Data Name="ModuleName">unknown</Data></EventData></Event>')

OTHER_APP_CRASH = (
    '<Event><EventData><Data Name="AppName">EXCEL.EXE</Data>'
    '<Data Name="AppVersion">16.0.{build}</Data></EventData></Event>')


def run() -> int:  # noqa: PLR0915
    print("=" * 74)
    print("PowerPoint R3 -- shared build token + explicit build-role attribution")
    print("=" * 74)

    # ================= DECISION 1: the shared token =================
    print("\n[token] one primitive, sentence-safe boundaries")
    check("the collector and the resolver share ONE token pattern",
          ppt.BUILD_RE is bc.BUILD_TOKEN_RE and cr.BUILD_RE is bc.BUILD_TOKEN_RE)
    for text, expect, why in [
        (f"Build {BUILD}.", [BUILD], "sentence-final"),
        (f"Build {BUILD},", [BUILD], "comma"),
        (f"({BUILD})", [BUILD], "parenthesised"),
        (f"Build {BUILD}", [BUILD], "bare"),
        (f"Build {BUILD}; and more", [BUILD], "semicolon"),
        (f"16.0.{BUILD}", [], "Office full version is not a bare build token"),
        (f"{BUILD}.123", [], "never truncated into a shorter valid build"),
        ("1.2.3", [], "too short to be a build"),
    ]:
        check(f"token: {why}", bc.build_tokens(text) == expect,
              f"{text!r} -> {bc.build_tokens(text)}")

    # A: the ACCEPTANCE AUTHORITY itself must see a sentence-final build.
    print("\n[A] sentence-final exact build is detected by the acceptance authority")
    a = row(f"PowerPoint Version {VERSION} crashes on save. I'm on Build {BUILD}.")
    check("A the authority accepts it", a.get("counted") is True, str(a))
    check("A the row carries the exact build", a.get("target_build") == BUILD)
    check("A build_check agrees", ppt.build_check(f"I'm on Build {BUILD}.", BUILD) == (None, True))

    # B: a longer dotted version must not be truncated into a build.
    print("\n[B] a 16.0.X.Y string is not truncated into a valid build")
    check("B build_check finds no bare build in an Office full version",
          ppt.build_check(f"Version is 16.0.{BUILD} here", BUILD) == (None, False))
    b = row(f"PowerPoint Version {VERSION} crashes on save; version string 16.0.{BUILD}.")
    check("B the authority refuses it as missing_exact_build",
          b.get("counted") is False and b.get("exclusion_reason") == "missing_exact_build", str(b))
    check("B and 19822.20182.123 yields nothing", bc.build_tokens("19822.20182.123") == [])

    # ================= DECISION 2: role attribution =================
    print("\n[C] one CURRENT + one ROLLBACK -> the current build is selected")
    text_c = (f"PowerPoint Version {VERSION} (Build {BUILD}) crashes on save every time. "
              f"I rolled back to Build {ROLLBACK} and it works again.")
    claims = bc.extract_build_claims(text_c)
    roles = {c.build: c.role for c in claims}
    check("C the current build is classified current_failing",
          roles.get(BUILD) == bc.ROLE_CURRENT_FAILING, str(roles))
    check("C the rollback build is classified rollback_previous",
          roles.get(ROLLBACK) == bc.ROLE_ROLLBACK_PREVIOUS, str(roles))
    sel, basis, refusal = bc.select_current_failing_build(claims)
    check("C exactly the current build is selected", sel == BUILD and not refusal, f"{sel} {refusal}")
    c_row = row(text_c)
    check("C the authority ACCEPTS for the current build", c_row.get("counted") is True, str(c_row))
    check("C the accepted row carries the current build", c_row.get("target_build") == BUILD)

    print("\n[D] one CURRENT + two ROLLBACK -> the current build is selected")
    text_d = (f"PowerPoint Version {VERSION} (Build {BUILD}) is not working. "
              f"I went back to Build {ROLLBACK} and it works again; "
              f"previous build {OTHER} was fine too.")
    claims = bc.extract_build_claims(text_d)
    roles = {c.build: c.role for c in claims}
    check("D both older builds are rollback_previous",
          roles.get(ROLLBACK) == bc.ROLE_ROLLBACK_PREVIOUS
          and roles.get(OTHER) == bc.ROLE_ROLLBACK_PREVIOUS, str(roles))
    sel, _b, refusal = bc.select_current_failing_build(claims)
    check("D the current build is still selected", sel == BUILD and not refusal, f"{sel} {refusal}")
    check("D the authority ACCEPTS", row(text_d).get("counted") is True)

    print("\n[E] two CURRENT builds -> conflict, nothing selected")
    text_e = (f"Build {BUILD} crashes on save and Build {THIRD} crashes on save too, "
              f"both on Current Channel.")
    claims = bc.extract_build_claims(text_e)
    check("E both are current_failing",
          all(c.role == bc.ROLE_CURRENT_FAILING for c in claims), str(bc.role_counts(claims)))
    sel, _b, refusal = bc.select_current_failing_build(claims)
    check("E nothing is selected", sel == "" and refusal == "multiple_current_failing_claims",
          f"{sel} {refusal}")
    e_row = row(text_e)
    check("E the authority refuses", e_row.get("counted") is False, str(e_row))
    check("E refused as missing_exact_build (eligible for resolution, not mis-matched)",
          e_row.get("exclusion_reason") == "missing_exact_build",
          str(e_row.get("exclusion_reason")))

    print("\n[F] three unlabeled builds -> conflict")
    text_f = (f"PowerPoint keeps crashing on save. Builds {BUILD}, {THIRD} and {OTHER} "
              f"are in our estate.")
    claims = bc.extract_build_claims(text_f)
    check("F all three are ambiguous",
          all(c.role == bc.ROLE_AMBIGUOUS for c in claims), str({c.build: c.role for c in claims}))
    check("F every one reports why", all(c.match_basis == bc.BASIS_NO_ROLE_STATED for c in claims))
    sel, _b, refusal = bc.select_current_failing_build(claims)
    check("F nothing is selected", sel == "" and refusal == "no_current_failing_claim",
          f"{sel} {refusal}")
    check("F the authority refuses", row(text_f).get("counted") is False)

    print("\n[F2] one CURRENT alongside an UNCLASSIFIED build -> still refused")
    text_f2 = (f"PowerPoint Version {VERSION} (Build {BUILD}) crashes on save. "
               f"Build {THIRD} is also around.")
    claims = bc.extract_build_claims(text_f2)
    sel, _b, refusal = bc.select_current_failing_build(claims)
    check("F2 an unclassified build BLOCKS selection",
          sel == "" and refusal == "unclassified_build_present",
          f"{sel} {refusal} {[(c.build, c.role) for c in claims]}")
    check("F2 the authority refuses", row(text_f2).get("counted") is False)

    # ================= G: cross-author attribution =================
    print("\n[G] a build only in another author's segment is ignored")
    page = qapage(f"PowerPoint {VERSION} crashes when I save.",
                  [(f"I'm on Build {BUILD} and see the same crash on save.", REPLIER)])
    out, budget, cand = resolve(page)
    check("G the OP resolves nothing", out.resolved_build == "", out.detail)
    check("G result is cross_segment_build_ignored",
          out.resolution_result == cr.CROSS_SEGMENT_BUILD_IGNORED, out.resolution_result)
    check("G the other author's build is reported, not borrowed",
          out.cross_segment_builds == [BUILD], str(out.cross_segment_builds))
    check("G the OP stays uncounted",
          row_from(cr.augmented_candidate(cand, out)).get("counted") is False)

    # ================= H: rollback build == target =================
    print("\n[H] the ROLLBACK build matches the target, the current build does not")
    text_h = (f"PowerPoint Version {VERSION} (Build {THIRD}) crashes on save. "
              f"I rolled back to Build {BUILD} and it works again.")
    claims = bc.extract_build_claims(text_h)
    roles = {c.build: c.role for c in claims}
    check("H the target build is classified rollback_previous",
          roles.get(BUILD) == bc.ROLE_ROLLBACK_PREVIOUS, str(roles))
    h_row = row(text_h)
    check("H the target is NOT accepted", h_row.get("counted") is False, str(h_row))
    check("H it is refused as build_mismatch",
          h_row.get("exclusion_reason") == "build_mismatch", str(h_row.get("exclusion_reason")))
    check("H no build is stamped on the row", not h_row.get("target_build"))
    check("H build_check refuses the target directly",
          ppt.build_check(text_h, BUILD) == ("build_mismatch", False), str(ppt.build_check(text_h, BUILD)))

    # ================= I / J: crash records =================
    print("\n[I] a PowerPoint crash record's AppVersion is a current/failing claim")
    text_i = (f"PowerPoint Version {VERSION} crashes on save. " + CRASH_BLOCK.format(build=BUILD))
    records = bc.crash_record_builds(text_i)
    check("I the crash record is parsed with its application identity",
          records == [(BUILD, "powerpnt.exe")], str(records))
    claims = bc.extract_build_claims(text_i)
    check("I the build is current_failing on the crash-record basis",
          any(c.build == BUILD and c.role == bc.ROLE_CURRENT_FAILING
              and c.match_basis == bc.BASIS_CRASH_RECORD for c in claims),
          str([(c.build, c.role, c.match_basis) for c in claims]))
    check("I the authority ACCEPTS it", row(text_i).get("counted") is True, str(row(text_i)))

    print("\n[J] another application's AppVersion is never a PowerPoint build claim")
    text_j = (f"PowerPoint Version {VERSION} crashes on save. "
              + OTHER_APP_CRASH.format(build=BUILD))
    records = bc.crash_record_builds(text_j)
    check("J the record is parsed but attributed to EXCEL",
          records == [(BUILD, "excel.exe")], str(records))
    claims = bc.extract_build_claims(text_j)
    check("J it is NOT a current_failing claim",
          all(c.role != bc.ROLE_CURRENT_FAILING for c in claims),
          str([(c.build, c.role, c.match_basis) for c in claims]))
    sel, _b, refusal = bc.select_current_failing_build(claims)
    check("J nothing is selected from it", sel == "", f"{sel} {refusal}")
    check("J the authority refuses", row(text_j).get("counted") is False, str(row(text_j)))
    check("J an AppVersion with no governing AppName is not credited",
          bc.crash_record_builds(f'<Data Name="AppVersion">16.0.{BUILD}</Data>')
          == [(BUILD, "")], str(bc.crash_record_builds(f'AppVersion 16.0.{BUILD}')))

    # ================= K: machine-generated segments =================
    print("\n[K] a machine-generated answer is never evidence, whatever roles it states")
    page = qapage(f"PowerPoint {VERSION} crashes when I save.",
                  [(f"Build {BUILD} crashes on save for many users; roll back to {ROLLBACK}.", AI)])
    out, budget, cand = resolve(page)
    reports = cr.independent_reports(cand, budget=budget, exclude_segment_key=out.segment_key,
                                     issue_predicate=ppt.concrete_issue)
    check("K the AI answer is not offered as a candidate", reports == [], str(reports))
    check("K its build is not transferred to the OP", out.resolved_build == "")
    check("K the segment is flagged machine-generated",
          all(s.machine_generated for s in ss.parse_learn_qna_thread(URL, page).answers()))

    # ================= L: existing single-build reports =================
    print("\n[L] existing exact single-build reports behave identically")
    for text, expect, why in [
        (f"PowerPoint Version {VERSION} (Build {BUILD}) crashes on save.", True, "target build"),
        (f"PowerPoint Version {VERSION} (Build {THIRD}) crashes on save.", False, "other build"),
        (f"PowerPoint Version {VERSION} crashes on save.", False, "no build"),
    ]:
        r = row(text)
        check(f"L single-build report, {why}: counted={expect}",
              (r.get("counted") is True) == expect, str(r.get("exclusion_reason")))
    check("L a lone build with NO role language still counts (nothing to disambiguate)",
          row(f"PowerPoint {VERSION} crashes on save. Build {BUILD}.").get("counted") is True)
    check("L the shortcut still returns a lone build with no role stated",
          bc.single_named_build(bc.extract_build_claims(f"Build {BUILD}.")) == BUILD)
    check("L but NOT a lone build the author placed elsewhere (see O/P/Q)",
          bc.single_named_build(bc.extract_build_claims(f"rolled back to {BUILD}")) == "")

    # ================= M: other products =================
    print("\n[M] non-PowerPoint products are untouched")
    # CONSUMPTION means importing the primitive, not mentioning its name. A text scan also fired on
    # a comment explaining why a module deliberately does NOT duplicate the build regex -- which is
    # the opposite of the violation this guards against. Parsed, so only a real import counts.
    import ast as _ast
    other_src = (_REPO / "auxsays" / "scripts" / "patch_collectors").glob("*.py")
    users = []
    for _p in other_src:
        if _p.name == "__init__.py":
            continue
        try:
            _tree = _ast.parse(_p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for _node in _ast.walk(_tree):
            if isinstance(_node, _ast.ImportFrom) and "build_claims" in (_node.module or ""):
                users.append(_p.name)
                break
            if isinstance(_node, _ast.Import) and any("build_claims" in a.name for a in _node.names):
                users.append(_p.name)
                break
    check("M only the PowerPoint collector consumes the build-role primitive",
          users == ["microsoft_powerpoint.py"], str(users))
    for product in ("obs-studio", "blackmagic-davinci", "adobe-premiere-pro",
                    "adobe-acrobat-reader", "microsoft-windows-11"):
        from lib.patch_identity import is_build_aware  # noqa: PLC0415
        check(f"M {product} remains non-build-aware", not is_build_aware(product))

    # ================= N: zero AI =================
    print("\n[N] zero-AI environment")
    probe = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, sys.argv[1]); from lib import build_claims as b; "
         "c=b.extract_build_claims('Version 2607 (Build 20228.20110) crashes; rolled back to "
         "Build 20131.20154 and it works again.'); "
         "print(b.select_current_failing_build(c)[0]); "
         "print([m for m in sys.modules if m.split('.')[0] in "
         "{'openai','anthropic','langchain','langgraph','transformers','litellm'}])",
         str(_REPO / "auxsays" / "scripts")],
        capture_output=True, text=True, cwd=str(_REPO),
        env={k: v for k, v in os.environ.items()
             if "OPENAI" not in k and "ANTHROPIC" not in k and not k.endswith("_API_KEY")})
    lines = probe.stdout.strip().splitlines()
    check("N role attribution works with no AI credentials",
          probe.returncode == 0 and lines and lines[0] == BUILD,
          f"rc={probe.returncode} {probe.stdout.strip()[:200]} {probe.stderr.strip()[-200:]}")
    check("N no AI provider package is imported",
          len(lines) > 1 and lines[1] == "[]", str(lines))
    src = (_REPO / "auxsays" / "scripts" / "lib" / "build_claims.py").read_text(encoding="utf-8")
    check("N the primitive imports only the standard library",
          "import openai" not in src and "langgraph" not in src.lower()
          and "anthropic" not in src.lower())

    # ============ O-S: the single-build shortcut respects roles ============
    # "Only one build is named" means nothing is NUMERICALLY ambiguous. It does not overrule the
    # author having positively placed that build somewhere other than the current/failing role.
    print("\n[O] a single ROLLBACK build must not satisfy the exact-build gate")
    text_o = (f"PowerPoint Version {VERSION} keeps crashing on save. "
              f"I rolled back to Build {BUILD} and everything works.")
    claims = bc.extract_build_claims(text_o)
    check("O the build is classified rollback_previous",
          [c.role for c in claims] == [bc.ROLE_ROLLBACK_PREVIOUS],
          str([(c.build, c.role) for c in claims]))
    check("O single_named_build refuses it", bc.single_named_build(claims) == "")
    check("O build_check reports no usable build",
          ppt.build_check(text_o, BUILD) == (None, False), str(ppt.build_check(text_o, BUILD)))
    o_row = row(text_o)
    check("O the authority does NOT count it", o_row.get("counted") is False, str(o_row))
    check("O refused as missing_exact_build",
          o_row.get("exclusion_reason") == "missing_exact_build", str(o_row.get("exclusion_reason")))
    check("O no build is stamped on the row", not o_row.get("target_build"))

    print("\n[P] a single REFERENCE-OTHER build must not satisfy the exact-build gate")
    text_p = (f"PowerPoint Version {VERSION} crashes on save for me. "
              f"A different PC on Build {BUILD} works fine.")
    claims = bc.extract_build_claims(text_p)
    check("P the build is classified reference_other",
          [c.role for c in claims] == [bc.ROLE_REFERENCE_OTHER],
          str([(c.build, c.role) for c in claims]))
    check("P single_named_build refuses it", bc.single_named_build(claims) == "")
    p_row = row(text_p)
    check("P the authority does NOT count it", p_row.get("counted") is False, str(p_row))
    check("P refused as missing_exact_build",
          p_row.get("exclusion_reason") == "missing_exact_build", str(p_row.get("exclusion_reason")))

    print("\n[Q] a single build with CONTRADICTORY claims must not satisfy the gate")
    text_q = (f"PowerPoint Version {VERSION}: Build {BUILD} crashes on save, "
              f"but I rolled back to Build {BUILD} and it works again.")
    claims = bc.extract_build_claims(text_q)
    check("Q the build is ambiguous on the contradictory basis",
          [(c.role, c.match_basis) for c in claims]
          == [(bc.ROLE_AMBIGUOUS, bc.BASIS_CONTRADICTORY)],
          str([(c.build, c.role, c.match_basis) for c in claims]))
    check("Q single_named_build refuses it", bc.single_named_build(claims) == "")
    q_row = row(text_q)
    check("Q the authority does NOT count it", q_row.get("counted") is False, str(q_row))

    print("\n[R] a single CURRENT/FAILING build is accepted when the other gates pass")
    text_r = (f"PowerPoint Version {VERSION} (Build {BUILD}) crashes on save every time "
              f"since the update.")
    claims = bc.extract_build_claims(text_r)
    check("R the build is classified current_failing",
          [c.role for c in claims] == [bc.ROLE_CURRENT_FAILING],
          str([(c.build, c.role) for c in claims]))
    check("R single_named_build returns it", bc.single_named_build(claims) == BUILD)
    r_row = row(text_r)
    check("R the authority COUNTS it", r_row.get("counted") is True, str(r_row))
    check("R the row carries the exact build", r_row.get("target_build") == BUILD)

    print("\n[S] an ordinary legacy single-build report is unchanged")
    text_s = (f"PowerPoint {VERSION} crashes on save after the update. Build {BUILD}.")
    claims = bc.extract_build_claims(text_s)
    check("S no role is stated, so the build stays ambiguous/no_role_stated",
          [(c.role, c.match_basis) for c in claims]
          == [(bc.ROLE_AMBIGUOUS, bc.BASIS_NO_ROLE_STATED)],
          str([(c.build, c.role, c.match_basis) for c in claims]))
    check("S the legacy shortcut still returns it", bc.single_named_build(claims) == BUILD)
    s_row = row(text_s)
    check("S the authority still COUNTS it", s_row.get("counted") is True, str(s_row))
    check("S the row carries the exact build", s_row.get("target_build") == BUILD)
    check("S a legacy single build that is NOT the target still mismatches",
          ppt.build_check(f"PowerPoint {VERSION} crashes. Build {THIRD}.", BUILD)
          == ("build_mismatch", False))

    print("\n[O/P/Q via context resolution] resolution cannot revive them either")
    for label, body in (("O rollback", text_o), ("P reference", text_p), ("Q contradictory", text_q)):
        out, budget, cand = resolve(qapage(body))
        check(f"{label}: the stage does not report a resolved build",
              out.resolution_result != cr.RESOLVED_EXACT_BUILD and out.resolved_build == "",
              f"{out.resolution_result} {out.resolved_build} :: {out.detail}")
        after = row_from(cr.augmented_candidate(cand, out))
        check(f"{label}: still not counted after resolution", after.get("counted") is False,
              str(after.get("exclusion_reason")))
        check(f"{label}: no build reaches the row", not after.get("target_build"))

    print("\n[R via context resolution] a single current build still resolves and counts")
    out, budget, cand = resolve(qapage(text_r))
    check("R resolves through the stage",
          out.resolution_result == cr.RESOLVED_EXACT_BUILD and out.resolved_build == BUILD,
          f"{out.resolution_result} {out.detail}")
    check("R counts after re-evaluation",
          row_from(cr.augmented_candidate(cand, out)).get("counted") is True)

    # ================= fail-closed doctrine =================
    print("\n[doctrine] what role attribution must never do")
    check("doctrine: no first-build rule",
          bc.select_current_failing_build(
              bc.extract_build_claims(f"Builds {BUILD} and {THIRD} exist."))[0] == "")
    check("doctrine: no last-build rule",
          bc.select_current_failing_build(
              bc.extract_build_claims(f"Builds {THIRD} and {BUILD} exist."))[0] == "")
    check("doctrine: proximity to the tracked YYMM decides nothing",
          bc.select_current_failing_build(
              bc.extract_build_claims(f"Version {VERSION}: builds {BUILD} and {THIRD}."))[0] == "")
    contradictory = bc.extract_build_claims(
        f"Build {BUILD} crashes on save but I rolled back to Build {BUILD} and it works again.")
    check("doctrine: contradictory claims about one build -> ambiguous, not a pick",
          all(c.role == bc.ROLE_AMBIGUOUS and c.match_basis == bc.BASIS_CONTRADICTORY
              for c in contradictory), str([(c.build, c.role, c.match_basis) for c in contradictory]))
    check("doctrine: the role vocabulary is exactly the four declared concepts",
          bc.ROLES == {bc.ROLE_CURRENT_FAILING, bc.ROLE_ROLLBACK_PREVIOUS,
                       bc.ROLE_REFERENCE_OTHER, bc.ROLE_AMBIGUOUS})
    check("doctrine: every claim carries a deterministic match basis and an excerpt",
          all(c.match_basis and c.excerpt for c in bc.extract_build_claims(text_c)))
    check("doctrine: an empty text names no builds",
          bc.extract_build_claims("") == [] and bc.select_current_failing_build([])[2] == "no_build_named")

    print()
    print("=" * 74)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 74)
    return 0 if _FAIL == 0 else 1


def row_from(cand: dict) -> dict:
    return ppt.row_from_candidate(record(), target(), cand, CAPTURED)


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
