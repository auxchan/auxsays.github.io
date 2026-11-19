#!/usr/bin/env python3
"""ComfyUI community evidence from its own GitHub issues: identity, the shared authority, the wiring.

WHAT THIS PROVES, IN ORDER.
  F  Fixture replay. Twenty issues captured from Comfy-Org/ComfyUI on 2026-11-18 (bodies trimmed,
     author accounts replaced by opaque numbers) are replayed through the shipped decision path, and
     each lands on the decision recorded when it was captured: accepted reports; a version that is
     only a Python package's, the Desktop app's or a third-party build's; builds past the release tag
     (ComfyUI-Manager describe, `master @ <sha>`); a mixed install whose frontend package is older than
     the release requires; failures that run through a custom-node pack; a maintainer-labelled feature
     request; a "latest version" complaint that names no release; a same-author repost; an issue
     created before the release and edited later; a version the reporter names as working; two
     sessions' logs where the older version is the one rolled back to.
  I  Identity unit checks on the exact shapes those decisions rest on.
  A  The acceptance authority is the shared one: base.apply_acceptance_gates decides, its own reasons
     are what a refused row carries, counted rows carry the sentiment the promotion requires, and the
     date is the issue's creation day -- never its last activity.
  D  Discovery and health: one paginated walk by creation date; PRs, foreign URLs and repeats dropped;
     a refused, broken, truncated or budget-stopped walk is never reported as "nothing found".
  W  The five gates a dry run never reaches: ownership (driven through the real validators),
     registration, the scoped promotion step and its position, the writeback allow-list, and the
     runtime budget. Plus the write path itself, against a temporary evidence store.

Offline and deterministic: every socket is refused for the whole run. Run:
    PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_comfyui_github_issues.py
"""
from __future__ import annotations

import contextlib
import fnmatch
import json
import socket
import sys
import tempfile
import traceback
import urllib.error
import urllib.parse
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

_REFUSED = [0]


class _NoNet(socket.socket):
    def connect(self, *args, **kwargs):  # noqa: D102
        _REFUSED[0] += 1
        raise OSError("network refused by test_comfyui_github_issues")


socket.socket = _NoNet  # type: ignore[misc]
socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(OSError("network refused"))  # type: ignore[assignment]

import run_patch_evidence_collection as runner  # noqa: E402
from lib import collector_ownership as ownership  # noqa: E402
from lib import report_counts  # noqa: E402
from lib.method_routing import HEALTH_STATUSES  # noqa: E402
from patch_collectors import base  # noqa: E402
from patch_collectors import comfyui as comfy  # noqa: E402
from patch_collectors import runtime_budget as rb  # noqa: E402

FIXTURE = _SCRIPTS / "tests" / "fixtures" / "comfyui_github_issues" / "issues.json"
WORKFLOW = _REPO / ".github" / "workflows" / "obs-evidence-collection.yml"
CAPTURED = "2026-11-19T00:00:00Z"

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print("  PASS  " + label)
    else:
        _FAIL += 1
        print("  FAIL  " + label + ("  --  " + detail if detail else ""))
        _ERRORS.append(label)


def record(version: str, published: str) -> base.PatchRecord:
    return base.PatchRecord(product_id="comfyui", update_version=version,
                            path=Path(f"comfyui-{version}.md"), update_published_at=published,
                            update_status="current", update_product="ComfyUI")


def issue(number: int, title: str, body: str, created: str = "2026-11-06T10:00:00Z",
          labels: tuple[str, ...] = (), author: int = 1, updated: str = "") -> dict:
    return {"number": number, "html_url": f"https://github.com/Comfy-Org/ComfyUI/issues/{number}",
            "title": title, "body": body, "created_at": created, "updated_at": updated or created,
            "state": "open", "state_reason": None, "labels": [{"name": n} for n in labels],
            "user": {"id": author}}


R044 = record("0.44.0", "2026-11-04T01:12:27Z")


@contextlib.contextmanager
def patched(pairs):
    saved = [(obj, name, getattr(obj, name)) for obj, name, _value in pairs]
    try:
        for obj, name, value in pairs:
            setattr(obj, name, value)
        yield
    finally:
        for obj, name, value in reversed(saved):
            setattr(obj, name, value)


def pages_from(issues: list[dict], per_page: int = comfy.PER_PAGE, *, total: int | None = None,
               incomplete: bool = False, fail_at: int | None = None, reason: str = "rate_limited"):
    """A fake shared GitHub transport serving `issues` newest first, paged like the search API."""
    ordered = sorted(issues, key=lambda i: i["created_at"], reverse=True)
    calls: list[str] = []

    def fetch(url: str):
        calls.append(url)
        page = int(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["page"][0])
        if fail_at is not None and page >= fail_at:
            raise comfy.github.GitHubError(reason)
        chunk = ordered[(page - 1) * per_page: page * per_page]
        return ({"total_count": len(ordered) if total is None else total,
                 "incomplete_results": incomplete, "items": chunk}, {})
    return fetch, calls


# ------------------------------------------------------------------------------------------------
def section_fixture() -> list[dict]:
    print("\n[F] fixture replay: captured ComfyUI issues -> the recorded decision")
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = data["cases"]
    check("F0 the fixture loaded and is not trivially small", len(cases) >= 15, str(len(cases)))
    reasons_seen = set()
    for case in cases:
        rec = record(case["record_version"], case["record_published_at"])
        iss = case["issue"]
        exp = case["expected"]
        cand = bool(comfy.candidates_for(rec.update_version, [iss]))
        row = comfy.evaluate_issue(rec, iss, CAPTURED)
        got = {"candidate": cand, "counted": bool(row.get("counted")),
               "exclusion_reason": row.get("exclusion_reason"),
               "match_basis": row.get("match_basis") or "", "source_date": row.get("source_date") or ""}
        # The repost decision belongs to the run (it compares candidates), so the pair is replayed
        # through collect() in section W; here the row-level decision is pinned.
        ok = all(got[k] == exp[k] for k in ("candidate", "counted", "exclusion_reason", "match_basis",
                                             "source_date"))
        check(f"F #{iss['number']} {case['record_version']}: {case['label']}", ok,
              f"expected={exp} got={got}")
        reasons_seen.add(exp["exclusion_reason"] or "counted")
    # Non-vacuity: every category the hand-off names is actually represented.
    wanted = {"counted", "version_not_core_identity", "core_version_untagged_build",
              "release_packages_not_as_shipped", "custom_node_in_failure_path",
              "feature_request_not_a_problem_report", "missing_exact_patch_version_match",
              "source_date_before_or_unverified_against_release", "version_role_working",
              "not_a_real_issue_report"}
    check("F1 every decision class is represented in the fixture", wanted <= reasons_seen,
          str(sorted(wanted - reasons_seen)))
    repost_pair = [c for c in cases if c["issue"]["number"] in (17415, 17416)]
    check("F2 the fixture keeps the repost pair under one opaque author with one title",
          len(repost_pair) == 2
          and len({c["issue"]["user"]["id"] for c in repost_pair}) == 1
          and len({c["issue"]["title"] for c in repost_pair}) == 1)
    check("F3 the fixture carries no reporter login", '"login"' not in FIXTURE.read_text(encoding="utf-8"))
    return cases


# ------------------------------------------------------------------------------------------------
def ident(text: str, version: str = "0.44.0") -> dict:
    return comfy.resolve_identity(text, version)


def section_identity() -> None:
    print("\n[I] identity: only the CORE release, and only the release itself")
    log = "\x1b[32m[INFO]\x1b[0m ComfyUI version: 0.44.0\n[INFO] comfyui-frontend-package version: 1.57.6\n"
    r = ident(log)
    check("I1 the startup log line (with terminal colour codes) declares the core version",
          r["established"] and r["basis"] == "core_version_declaration", str(r))
    r = ident("## System Information\n- **ComfyUI Version:** v0.44.0\n- **Arguments:** main.py\n")
    check("I2 the error-report system information block declares it", r["established"], str(r))
    r = ident("[INFO] ### ComfyUI Version: v0.44.0 | Released on '2026-11-04'\n")
    check("I3 ComfyUI-Manager on the tag itself declares it", r["established"], str(r))
    r = ident("[INFO] ComfyUI version: 0.44.0\n[INFO] ### ComfyUI Version: v0.44.0-27-g1332fab | Released on\n")
    check("I4 Manager's describe N commits past the tag refuses it as an untagged build",
          r["reason"] == "core_version_untagged_build", str(r))
    for text in ("Environment: ComfyUI 0.44.0-6-ge087d8f6c on Linux",
                 "ComfyUI: master `46493d8` (v0.44.0-29)",
                 "Running ComfyUI 0.44.0 + 6 commits on Windows",
                 "master @ c5751c81 (v0.44.0), macOS arm64",
                 "Environment: ComfyUI v0.44.0, master `5cc4b87` (2026-11-05)",
                 "ComfyUI version: 0.44.0 (master fd7639f47)"):
        check(f"I5 untagged: {text[:48]!r}", ident(text)["reason"] == "core_version_untagged_build",
              str(ident(text)))
    for text in ("Environment: ComfyUI v0.44.0 (the class is unchanged on master `b2f6707`). It crashes.",
                 "Seen on ComfyUI 0.44.0. The same lines are on master.",
                 "Code checked on master `dc9ffe6add`; reproduced on ComfyUI 0.44.0 (`c5751c81`)."):
        check(f"I6 a master code reference beside the release is not a dev build: {text[:40]!r}",
              ident(text)["established"], str(ident(text)))
    for text, why in (("- llvmlite 0.44.0\n- lmdb 1.7.3", "a Python package"),
                      ("custom_nodes\\comfyui-mixlab-nodes-0.44.0\\__init__.py", "a custom-node pack"),
                      ("[INFO] comfyui-frontend-package version: 0.44.0", "the frontend package"),
                      ("| ComfyUI Desktop 0.44.0 | standalone", "the Desktop app"),
                      ("Using cached wheel-0.44.0-py3-none-any.whl", "a wheel"),
                      ("installed comfyui-workflow-templates 0.44.0", "the templates package")):
        check(f"I7 a number that belongs to {why} is not the core version",
              ident(text)["reason"] == "version_not_core_identity", str(ident(text)))
    for text in ("Updated to ComfyUI v0.44.0: images now come out black",
                 "**ComfyUI:** v0.44.0 (portable)", "| ComfyUI | v0.44.0 |", "ComfyUI portable 0.44.0 crashes",
                 "Environment: ComfyUI **v0.44.0** (Python 3.13)"):
        r = ident(text)
        check(f"I8 the reporter naming ComfyUI beside the number: {text[:36]!r}",
              r["established"] and r["basis"] == "core_version_text", str(r))
    r = ident("[INFO] ComfyUI version: 0.43.0\nI think ComfyUI v0.44.0 changed this.")
    check("I9 the reporter's own declaration naming ANOTHER core version wins over prose",
          r["reason"] == "declared_core_version_differs", str(r))
    check("I10 a longer version is a different release",
          ident("ComfyUI version: 0.44.2")["reason"] == "missing_exact_patch_version_match"
          and ident("ComfyUI 0.44.0.1 here")["reason"] == "missing_exact_patch_version_match"
          and ident("ComfyUI v0.44.01")["reason"] == "missing_exact_patch_version_match")
    r = ident("[INFO] ComfyUI version: 0.44.0\nInstalled comfyui-frontend-package version 1.39.19 is "
              "lower than the recommended version 1.57.6.")
    check("I11 ComfyUI's own 'lower than the recommended version' warning is a mixed install",
          r["reason"] == "release_packages_not_as_shipped", str(r))
    check("I12 a sentence-final version still matches (shared matcher)",
          ident("I updated to ComfyUI 0.44.0.")["established"])
    check("I13 'latest' is not a version", not comfy.candidates_for("0.44.0", [issue(
        1, "Broken after I updated comfyui to the latest version", "everything crashes now")]))
    check("I14 a custom-node traceback frame is an ecosystem failure",
          comfy.issue_kind_exclusion([], 'File "C:\\ComfyUI\\custom_nodes\\comfyui-kjnodes\\nodes.py", line 12')
          == "custom_node_in_failure_path")
    check("I15 a custom-node import line that is not a traceback frame is not",
          comfy.issue_kind_exclusion([], "Import times for custom nodes:\n 0.1 seconds: custom_nodes/ComfyUI-Manager")
          == "")
    check("I16 the maintainers' labels: custom node and feature",
          comfy.issue_kind_exclusion(["Custom Nodes Bug"]) == "custom_node_issue"
          and comfy.issue_kind_exclusion(["Feature"]) == "feature_request_not_a_problem_report"
          and comfy.issue_kind_exclusion(["Potential Bug", "User Support"]) == "")


# ------------------------------------------------------------------------------------------------
def section_authority() -> None:
    print("\n[A] the shared authority decides; dates are creation, never last activity")
    good = issue(901, "KSampler crashes with CUDA error after updating",
                 "[INFO] ComfyUI version: 0.44.0\nThe sampler crashes every run.",
                 created="2026-11-06T09:00:00Z", updated="2026-11-18T09:00:00Z")
    row = comfy.evaluate_issue(R044, good, CAPTURED)
    check("A1 a declared exact release with a concrete failure counts", row.get("counted") is True,
          str(row.get("exclusion_reason")))
    check("A2 the row is the shared schema with a weight of one",
          set(row) <= set(base.EVIDENCE_FIELDS) and row.get("source_weight") == 1, str(sorted(row)))
    check("A3 source_date is the CREATION day, not the last activity",
          row.get("source_date") == "2026-11-06", str(row.get("source_date")))
    from apply_consensus_to_records import VALID_SENTIMENTS  # noqa: PLC0415
    check("A4 a counted row carries a sentiment the promotion authority accepts",
          str(row.get("sentiment")) in VALID_SENTIMENTS, str(row.get("sentiment")))
    check("A5 the row's URL is a specific issue the shared gate accepts",
          base.source_url_is_specific(str(row.get("source_url"))), str(row.get("source_url")))
    stale = issue(902, "KSampler crashes", "[INFO] ComfyUI version: 0.44.0\nThe sampler crashes.",
                  created="2026-11-03T22:00:00Z", updated="2026-11-10T00:00:00Z")
    row = comfy.evaluate_issue(R044, stale, CAPTURED)
    check("A6 an issue created before the release is refused by the shared date gate even when it "
          "was active after it", row.get("exclusion_reason") == "source_date_before_or_unverified_against_release",
          str(row.get("exclusion_reason")))
    vague = issue(903, "Question about 0.44.0", "[INFO] ComfyUI version: 0.44.0\nIs this one good?")
    row = comfy.evaluate_issue(R044, vague, CAPTURED)
    check("A7 no concrete problem -> the shared gate's own reason", row.get("exclusion_reason")
          == "not_a_real_issue_report", str(row.get("exclusion_reason")))
    check("A8 an excluded row is never counted and carries no sentiment",
          row.get("counted") is False and not row.get("sentiment"))
    fixed = issue(904, "Crash in VAE decode", "Updated to ComfyUI v0.45.0 and VAE decode crashes. "
                  "It was fine before; this is fixed in ComfyUI v0.44.0 for me after I went back.")
    row = comfy.evaluate_issue(R044, fixed, CAPTURED)
    check("A9 the shared role veto refuses a version the report names as not affected",
          str(row.get("exclusion_reason") or "").startswith("version_role_"), str(row.get("exclusion_reason")))
    two_logs = ("Session 1:\n[INFO] ComfyUI version: 0.43.0\nSession 2:\n[INFO] ComfyUI version: 0.44.0\n"
                "Loading the workflow takes three minutes and then the server crashes.")
    row = comfy.evaluate_issue(R044, issue(905, "Workflow load crashes the server", two_logs), CAPTURED)
    check("A11 two sessions' logs with no statement of which failed: no declaration is immune, refused",
          row.get("exclusion_reason") == "multiple_core_versions_declared", str(row.get("exclusion_reason")))
    stated = two_logs + "\nIt fails on 0.44.0 every time."
    row = comfy.evaluate_issue(R044, issue(906, "Workflow load crashes the server", stated), CAPTURED)
    check("A12 ...and counted when the shared role reading says the version is the affected one",
          row.get("counted") is True, str(row.get("exclusion_reason")))
    check("A10 the module declares no acceptance vocabulary of its own",
          not any(hasattr(comfy, n) for n in ("ISSUE_TERMS", "CONCRETE_ISSUE_TERMS", "ISSUE_EXTRA_TERMS")))


# ------------------------------------------------------------------------------------------------
def section_discovery() -> None:
    print("\n[D] discovery: one walk by creation date; health never reads a failure as empty")
    fetch, calls = pages_from([])
    url = comfy.search_page_url("2026-10-05", 2)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    check("D1 the walk asks for issues CREATED in the window, newest first",
          q["q"] == ["repo:Comfy-Org/ComfyUI is:issue created:>=2026-10-05"]
          and q["sort"] == ["created"] and q["order"] == ["desc"] and q["page"] == ["2"], str(q))
    check("D2 it never filters by last activity", "updated" not in url)
    check("D3 a page holds 50 issues (payload bound measured against the transport's read cap)",
          q["per_page"] == ["50"] and comfy.PER_PAGE == 50)
    many = [issue(2000 + i, f"t{i}", "b", created=f"2026-11-{1 + i % 15:02d}T00:{i % 60:02d}:00Z") for i in range(120)]
    many.append(dict(issue(5000, "a pull request", "b"), pull_request={"url": "x"}))
    many.append(dict(issue(5001, "foreign", "b"), html_url="https://github.com/someone/else/issues/5001"))
    many.append(dict(many[0]))
    fetch, calls = pages_from(many)
    errors: list = []
    got, tele = comfy.enumerate_issues("2026-10-01", errors, fetch=fetch)
    check("D4 the walk pages until a short page and keeps every issue once",
          len(got) == 120 and len(calls) == 3 and not errors, f"{len(got)} issues, {len(calls)} calls")
    check("D5 pull requests and other repositories' issues are dropped",
          all(i["number"] < 5000 for i in got))
    fetch, _ = pages_from(many[:10], total=1500)
    errors = []
    _got, tele = comfy.enumerate_issues("2026-10-01", errors, fetch=fetch)
    check("D6 a window beyond the 1000-result cap is truncated, and health says partial",
          tele["truncated"] and comfy.method_status(errors, tele, 3) == "partial", str(tele))
    fetch, _ = pages_from(many[:10], incomplete=True)
    errors = []
    _got, tele = comfy.enumerate_issues("2026-10-01", errors, fetch=fetch)
    check("D7 incomplete_results reads partial, never success",
          comfy.method_status(errors, tele, 5) == "partial", str(tele))
    for reason, want in (("rate_limited", "blocked"), ("http_500_error", "broken"),
                         ("network_unreachable", "broken"), ("payload_parse_failed", "broken")):
        fetch, _ = pages_from(many, fail_at=1, reason=reason)
        errors = []
        _got, tele = comfy.enumerate_issues("2026-10-01", errors, fetch=fetch)
        check(f"D8 a walk refused on page one with {reason} reports {want}",
              comfy.method_status(errors, tele, 0) == want, comfy.method_status(errors, tele, 0))
    fetch, _ = pages_from(many, fail_at=2)
    errors = []
    _got, tele = comfy.enumerate_issues("2026-10-01", errors, fetch=fetch)
    check("D9 a walk that fails after reading a page is partial, not success",
          comfy.method_status(errors, tele, 2) == "partial")

    def raw_403(_url):
        raise urllib.error.HTTPError("https://api.github.com/search/issues", 403, "Forbidden", None, None)
    errors = []
    _got, tele = comfy.enumerate_issues("2026-10-01", errors, fetch=raw_403)
    check("D10 a raw 403 (GitHub's secondary rate limit) is blocked",
          comfy.method_status(errors, tele, 0) == "blocked", str(errors))
    fetch, _ = pages_from([])
    errors = []
    _got, tele = comfy.enumerate_issues("2026-10-01", errors, fetch=fetch)
    check("D11 an answered empty window is no_results", comfy.method_status(errors, tele, 0) == "no_results")
    check("D12 every status this module can return is canonical",
          {"blocked", "broken", "partial", "success", "no_results"} <= HEALTH_STATUSES)
    check("D13 the routine window is 45 days and an explicit since passes through",
          comfy.window_start(None).count("-") == 2 and comfy.window_start("2026-09-01") == "2026-09-01"
          and comfy.window_start("garbage") != "garbage")

    class Expired:
        def collector_finalize_expired(self):
            return True
    rb.set_run_budget(Expired())
    try:
        fetch, calls = pages_from(many)
        errors = []
        _got, tele = comfy.enumerate_issues("2026-10-01", errors, fetch=fetch)
        check("D14 an expired budget stops the walk before a request and reads partial",
              not calls and comfy.method_status(errors, tele, 0) == "partial", str(errors))
    finally:
        rb.set_run_budget(None)


# ------------------------------------------------------------------------------------------------
def section_wiring(cases: list[dict]) -> None:
    print("\n[W] the gates a dry run never reaches, and the write path")
    check("W1 not registered by default", "comfyui" not in runner.build_collectors({}))
    check("W2 registered for the exact string 'true'",
          "comfyui" in runner.build_collectors({runner.COMFYUI_CONSENSUS_ENABLE_ENV: "true"}))
    traps = {v: "comfyui" in runner.build_collectors({runner.COMFYUI_CONSENSUS_ENABLE_ENV: v})
             for v in ("false", "0", "1", "yes", "on", "")}
    check("W3 no truthy-looking value registers it", not any(traps.values()), str(traps))
    check("W4 ownership authorises exactly the shared GitHub-issues method and source type",
          ownership.allowed_methods("comfyui") == {comfy.METHOD_ID}
          and ownership.allowed_source_types("comfyui") == {comfy.SOURCE_TYPE}
          and comfy.METHOD_ID == "github_issues" and comfy.SOURCE_TYPE == "github_issue")
    check("W5 comfyui is a promotion product, so reconciliation may retract what promotion rebuilds",
          "comfyui" in report_counts.CONSENSUS_PROMOTION_PRODUCTS)

    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = (((wf.get("jobs") or {}).get("collect") or {}).get("steps") or [])
    names = [str(s.get("name") or "") for s in steps]
    collect_step = next((s for s in steps if "run_patch_evidence_collection.py" in str(s.get("run") or "")), {})
    check("W6 the scheduled collection step activates the collector with the exact string 'true'",
          (collect_step.get("env") or {}).get(runner.COMFYUI_CONSENSUS_ENABLE_ENV) == "true",
          str(collect_step.get("env")))
    check("W7 and comfyui is not removed by the orchestration list",
          "comfyui" not in str((collect_step.get("env") or {}).get("AUXSAYS_ORCHESTRATED_PRODUCTS") or ""))

    def body_lines(step):
        return [ln.strip() for ln in str(step.get("run") or "").splitlines() if ln.strip() and not ln.strip().startswith("#")]
    promote = [i for i, s in enumerate(steps)
               if "apply_consensus_to_records.py" in " ".join(body_lines(s))
               and "--product-id comfyui" in " ".join(body_lines(s))]
    consensus_i = next((i for i, s in enumerate(steps) if "build_consensus_from_evidence.py" in str(s.get("run") or "")), -1)
    qa_i = next((i for i, n in enumerate(names) if n == "QA patch records"), -1)
    check("W8 exactly one scoped comfyui promotion step, with --write-all --confirm-write",
          len(promote) == 1 and "--write-all --confirm-write" in " ".join(body_lines(steps[promote[0]])),
          str(promote))
    check("W9 positioned after reconciliation and before the first QA",
          bool(promote) and consensus_i < promote[0] < qa_i, f"consensus={consensus_i} promote={promote} qa={qa_i}")
    check("W10 and skipped on a dry run like every promotion",
          bool(promote) and "dry_run != 'true'" in str(steps[promote[0]].get("if") or ""))
    writeback = next((s for s in steps if "automation_writeback.py" in str(s.get("run") or "")), {})
    globs = [ln.split("--allow", 1)[1].strip().rstrip("\\").strip().strip("'\"")
             for ln in body_lines(writeback) if "--allow" in ln]
    live = base.generated_records("comfyui", None)
    unmatched = [r.path.name for r in live
                 if not any(fnmatch.fnmatch("auxsays/updates/generated/" + r.path.name, g) for g in globs)]
    check("W11 every ComfyUI record is committable by the writeback", bool(live) and not unmatched,
          f"{len(live)} records, unmatched={unmatched[:3]}")
    stray = [p.name for p in (_REPO / "auxsays" / "updates" / "generated").glob("*comfyui*.md")
             if base.load_front_matter_and_body(p)[0].get("product_id") != "comfyui"]
    check("W12 the comfyui glob commits no other product's record", not stray, str(stray))

    # --- the run, end to end, against a temporary store ---------------------------------------
    by_number = {c["issue"]["number"]: c for c in cases}
    pool = [c["issue"] for c in cases]
    fetch, _calls = pages_from(pool)
    recs = [record(v, by_number_v) for v, by_number_v in
            sorted({(c["record_version"], c["record_published_at"]) for c in cases})]
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "consensus_evidence.yml"
        store.write_text(yaml.safe_dump({"schema_version": 1, "evidence": []}), encoding="utf-8")
        real_append = base.append_evidence_rows
        writebacks: list[str] = []

        def append(rows, path=None, **kw):
            return real_append(rows, store, **kw)
        with patched([(comfy.github, "request_json", fetch),
                      (base, "generated_records", lambda pid, tv=None, **kw: [r for r in recs if not tv or r.update_version in tv]),
                      (base, "append_evidence_rows", append),
                      (comfy, "apply_consensus_writebacks",
                       lambda vs: writebacks.extend(vs) or {v: True for v in vs})]):
            ctx = base.CollectorContext(write=True, since="2026-09-01", max_pages=5,
                                        target_versions={"0.43.0", "0.44.0"})
            first = comfy.ComfyUICollector().collect(ctx)
            stored = base.load_evidence(store)
            second = comfy.ComfyUICollector().collect(ctx)
            stored_again = base.load_evidence(store)
        res43 = next(r for r in first if r["version"] == "0.43.0")
        repost = next((r for r in stored if r["source_url"].endswith("/17416")), {})
        check("W13 the repost is stored excluded and names the issue it repeats",
              repost.get("counted") is False
              and repost.get("exclusion_reason") == "same_report_reposted_of_issue_17415", str(repost))
        check("W14 its original is counted", any(r["source_url"].endswith("/17415") and r["counted"] for r in stored))
        check("W15 every excluded row is stored with a reason (auditable from the store)",
              all(r.get("exclusion_reason") for r in stored if not r.get("counted")) and
              any(not r.get("counted") for r in stored))
        check("W16 every stored row is comfyui's, on a tracked version, from the one source family",
              all(r["product_id"] == "comfyui" and r["update_version"] in {"0.43.0", "0.44.0"}
                  and r["source_type"] == "github_issue" for r in stored))
        health43 = res43["method_health"][0]
        counted43 = sum(1 for r in stored if r["update_version"] == "0.43.0" and r["counted"])
        check("W17 health stores exactly the ACCEPTED rows it added, not the excluded ones",
              health43["evidence_rows_added"] == counted43 == health43["accepted_reports"]
              and health43["duplicate_existing_evidence"] == 0, str(health43))
        check("W18 a second run adds nothing: one report is one row",
              len(stored_again) == len(stored)
              and all(r.get("evidence_rows_added") == 0 for r in second), str([r.get("evidence_rows_added") for r in second]))
        h2 = next(r for r in second if r["version"] == "0.43.0")["method_health"][0]
        check("W19 and its health says the store already held them",
              h2["evidence_rows_added"] == 0 and h2["duplicate_existing_evidence"] == h2["accepted_reports"], str(h2))
        check("W20 the collector hands accepted patches to the shared writeback, and only those",
              sorted(set(writebacks)) == ["0.43.0", "0.44.0"], str(writebacks))
        check("W21 every health row is canonical and one per record per run",
              all(len(r["method_health"]) == 1 and r["method_health"][0]["status"] in HEALTH_STATUSES
                  for r in first))
        # The real validators, which a dry run never reaches.
        before = yaml.safe_dump({"schema_version": 1, "evidence": []}, sort_keys=False)
        after = yaml.safe_dump({"schema_version": 1, "evidence": stored}, sort_keys=False, allow_unicode=True)
        try:
            ownership.validate_evidence("comfyui", before, after)
            err = None
        except Exception as exc:  # noqa: BLE001
            err = exc
        check("W22 the stored rows pass the real evidence ownership validator", err is None, repr(err))
        live_versions = {r.update_version for r in live}
        real_rows = [row for r in first for row in r["method_health"] if row["update_version"] in live_versions]
        try:
            ownership.validate_method_health("comfyui", real_rows)
            err = None
        except Exception as exc:  # noqa: BLE001
            err = exc
        check("W23 the health rows pass the real method-health ownership validator", err is None and real_rows, repr(err))
        foreign = dict(stored[0], product_id="obs-studio", id="obs-studio-x")
        try:
            ownership.validate_evidence("comfyui", before,
                                        yaml.safe_dump({"schema_version": 1, "evidence": [foreign]}, sort_keys=False))
            err = None
        except Exception as exc:  # noqa: BLE001
            err = exc
        check("W24 and a row for another product is refused", err is not None)

    # The promotion counts exactly what reconciliation counts (the #70 wedge cannot form).
    from apply_consensus_to_records import _index_generated_records, run_dry_run  # noqa: PLC0415
    from lib.report_counts import counted_evidence_counts  # noqa: PLC0415
    target = next((r for r in live if r.update_version == "0.44.0"), None)
    counted = [r for r in stored if r["update_version"] == "0.44.0" and r["counted"]]
    check("W25 there is a real 0.44.0 record and counted rows for it", target is not None and counted)
    with tempfile.TemporaryDirectory() as tmp:
        ev = Path(tmp) / "consensus_evidence.yml"
        ev.write_text(yaml.safe_dump({"schema_version": 1, "evidence": counted}, sort_keys=False,
                                     allow_unicode=True), encoding="utf-8")
        groups = run_dry_run(evidence_path=ev, product_id_filter="comfyui", is_candidate_mode=False,
                             records_index=_index_generated_records(), write_requested=True)
    group = next((g for g in groups if g.get("update_version") == "0.44.0"), {})
    fields = group.get("proposed_fields_if_written") or {}
    reconciled = sum(counted_evidence_counts(counted, windows_targets={}).values())
    check("W26 promotion and reconciliation count the same population",
          group.get("would_write") and fields.get("update_report_count") == reconciled == len(counted),
          f"promotion={fields.get('update_report_count')} reconcile={reconciled} rows={len(counted)} "
          f"blocked={group.get('write_blocked_reason')}")
    check("W27 so the record gets the summary and samples QA requires at a non-zero count",
          bool(str(fields.get("update_consensus_summary") or "").strip()) and fields.get("evidence_samples"))
    official = [f for f in ("update_version", "update_published_at", "update_source_url", "quick_verdict",
                            "update_decision_label", "official_patch_notes_body") if f in fields]
    check("W28 promotion proposes no official identity or verdict field", not official, str(official))
    check("W29 the pilot maturity comes from the one authority",
          fields.get("evidence_state") == "pilot_sample", str(fields.get("evidence_state")))

    # The batched writeback asks the shared authority ONCE, and still selects per patch.
    import apply_consensus_to_records as acr  # noqa: PLC0415
    dry_calls: list[int] = []
    applied: list[str] = []
    groups = [{"update_version": "0.43.0", "would_write": True, "matched_generated_record_path": "a.md",
               "proposed_fields_if_written": {"evidence_last_checked": "x"}},
              {"update_version": "0.44.0", "would_write": False, "matched_generated_record_path": "b.md",
               "proposed_fields_if_written": {}}]
    with patched([(acr, "run_dry_run", lambda **kw: dry_calls.append(1) or groups),
                  (acr, "_index_generated_records", lambda: {}),
                  (acr, "apply_collector_record_fields",
                   lambda path, fields: applied.append(Path(path).name) or {"write_plan": {"fields": fields}})]):
        out = comfy.apply_consensus_writebacks(["0.43.0", "0.44.0"])
        none = comfy.apply_consensus_writebacks([])
    check("W30 several patches cost one dry run of the shared authority", len(dry_calls) == 1, str(dry_calls))
    check("W31 and each patch is still selected on its own (a blocked group writes nothing)",
          out == {"0.43.0": True, "0.44.0": False} and applied == ["a.md"] and none == {},
          f"{out} {applied} {none}")


def run() -> int:
    print("=" * 78)
    print("ComfyUI GitHub-issues community evidence")
    print("=" * 78)
    cases = section_fixture()
    section_identity()
    section_authority()
    section_discovery()
    section_wiring(cases)
    check("Z no socket was opened by this suite", _REFUSED[0] == 0, str(_REFUSED[0]))
    print()
    print("=" * 78)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed: " + ", ".join(_ERRORS))
    print("=" * 78)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
