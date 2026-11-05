#!/usr/bin/env python3
"""Every owned method is emitted by its product's production path, in the state that path runs it.

`collector_ownership.ALLOWED_METHODS` has two jobs. As the write allow-list an over-wide set is
harmless: a collector simply never writes the extra method. Since AUX-054 it is ALSO the monitoring
authority's list of EXPECTED methods (`monitoring_health.certify_monitoring`, H7): an owned method
with no telemetry row puts `missing_method_telemetry:<method>` on every identity of the product, and
any one reason refuses live certification. Five owned pairs had never been implemented or emitted
(Acrobat Pro and Reader `adobe_community_bug_tab_index` and `adobe_community_known_url_recheck`,
Premiere `known_watchlist`): copy errors from the day the manifest was written, which blocked all 398
identities of those three products (AUX-074). Every earlier ownership check asserted only
emitted <= owned. Nothing asserted owned <= emitted, and nothing tied an emitted status to whether
the method actually ran -- which is how the five survived.

This suite calls each promotion product's PRODUCTION path offline, with transports stubbed and
counted at the per-method entry points, and pins:

  A    PowerPoint and Premiere: every planned method is owned; Premiere owns exactly its plan.
  REG  under the workflow's own environment each product is reached by exactly one production path
       (one runner step or one graph step), and the driver here is that path.
  ENV  every AUXSAYS_* name a workflow or a production module uses is classified (registration,
       mode or tuning), and no mode flag that governs an UNOWNED method is set by a workflow.
  B    per (product, mode, scenario): the emitted method set equals owned minus manual-only, one
       row per method. A DEPENDENT method (PowerPoint's context resolver, which runs only on the
       other methods' resolvable rejections) is expected exactly when its input exists.
  T    transport accounting: a `disabled` row made 0 calls, an executing row made >= 1, and no
       socket was opened outside the stubbed entry points.
  R    every owned method has an expected state (plan role, or the pinned table below), and the
       emitted status class matches it. Expected states come from the MODE's declared flags, never
       from the collector's own flag reader.
  C    C1 a method `disabled` under refusal is `disabled` when the source answers too (no failure
       relabelled as disabled); C2 every method expected to execute reports a degraded status when
       every transport refuses; C3 a `disabled` row's last_run is empty or stamped by this call.
  D    answered rows (executing ones made fresh `success`) give certify_monitoring no H7
       `missing_method_telemetry:` and no H0 `unowned_method:` reason.
  E    mutation self-tests: each named check fails on the defect it exists for.

Environment modes. Each clears every AUXSAYS_*, BRAVE_SEARCH_API_KEY, REDDIT_BEARER_TOKEN,
GITHUB_TOKEN and GH_TOKEN key first:
  workflow      the env of the job and step that actually run the product, read from
                obs-evidence-collection.yml with yaml.safe_load (`${{ ... }}` modelled as set).
  flags_on      workflow plus every MODE flag whose governed methods are all owned, at its on value.
                No workflow sets one today, so this is the only mode that sees those methods on.
  code_default  every gate absent: the code's own default, kept as a regression mode only.

Offline and dry-run: CollectorContext(write=False); sockets and DNS refused and counted; no
repository file is written (the graph's checkpoints go to a temporary directory).
Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_owned_method_lifecycle.py
"""
from __future__ import annotations

import ast
import contextlib
import copy
import os
import re
import shutil
import socket
import sys
import tempfile
import traceback
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # auxsays/
SCRIPTS = ROOT / "scripts"
REPO = ROOT.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# ---- network refusal, installed before any collector module is imported --------------------------
UNATTRIBUTED = [0]


class _NoNetSocket(socket.socket):
    def connect(self, *args, **kwargs):          # noqa: D102
        UNATTRIBUTED[0] += 1
        raise OSError("network refused by test_owned_method_lifecycle")

    def connect_ex(self, *args, **kwargs):       # noqa: D102
        UNATTRIBUTED[0] += 1
        raise OSError("network refused by test_owned_method_lifecycle")


def _no_dns(*args, **kwargs):
    UNATTRIBUTED[0] += 1
    raise OSError("DNS refused by test_owned_method_lifecycle")


socket.socket = _NoNetSocket                     # type: ignore[misc]
socket.getaddrinfo = _no_dns                     # type: ignore[assignment]

import yaml                                                              # noqa: E402

import collect_obs_reports as legacy_obs                                 # noqa: E402
import orchestrate_evidence_run as orch                                  # noqa: E402
import run_patch_evidence_collection as runner                           # noqa: E402
from lib import collector_ownership as co                                # noqa: E402
from lib import method_routing as mr                                     # noqa: E402
from lib import monitoring_health as mh                                  # noqa: E402
from lib import report_counts                                            # noqa: E402
from patch_collectors import adobe_acrobat_community as ac              # noqa: E402
from patch_collectors import adobe_premiere as ap                       # noqa: E402
from patch_collectors import base                                       # noqa: E402
from patch_collectors import microsoft_powerpoint as ppt                # noqa: E402
from patch_collectors import microsoft_teams as teams                   # noqa: E402
from patch_collectors import microsoft_windows as mw                    # noqa: E402
from patch_collectors import obs as obs_adapter                         # noqa: E402
from patch_collectors import obs_forum_source as forum                  # noqa: E402

WORKFLOWS = REPO / ".github" / "workflows"
COLLECTION_YML = WORKFLOWS / "obs-evidence-collection.yml"
SINCE = "2026-01-01"
REFUSAL = "http_403 blocked"         # the production total-failure shape: a refused request
SCENARIOS = ("answer_empty", "refuse")
MODES = ("workflow", "flags_on", "code_default")

WINDOWS, OBS, TEAMS, PPT = "microsoft-windows-11", "obs-studio", "microsoft-teams", "microsoft-powerpoint"
PREMIERE, PRO, READER = "adobe-premiere-pro", "adobe-acrobat-pro", "adobe-acrobat-reader"
PRODUCTS = (WINDOWS, OBS, TEAMS, PPT, PREMIERE, PRO, READER)

PASS = FAIL = 0
FAILURES: list[str] = []
WARNINGS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


def warn(label: str, ok: bool, detail: str = "") -> None:
    """A corpus observation, not a gate: a newly owned method has no rows until its first run."""
    if ok:
        print(f"  ok    {label}")
    else:
        WARNINGS.append(label)
        print(f"  WARN  {label}" + (f"  [{detail}]" if detail else ""))


# ---- environment classification ------------------------------------------------------------------
# Every AUXSAYS_* name a workflow sets or a production module reads. An unclassified name fails ENV1
# or ENV2, so a new flag cannot reach production without someone deciding what it gates.
REGISTRATION_FLAGS = frozenset({
    "AUXSAYS_ENABLE_WINDOWS_LEARN_QNA_WRITEBACK", "AUXSAYS_ENABLE_ACROBAT_CONSENSUS",
    "AUXSAYS_ENABLE_POWERPOINT_CONSENSUS", "AUXSAYS_ENABLE_TEAMS_CONSENSUS",
    "AUXSAYS_ORCHESTRATED_PRODUCTS",
})
# MODE flags choose an owned method's state inside a production path. Each names the
# (product, method) pairs it governs and its canonical on value.
_REDDIT_READERS = (PRO, READER, PREMIERE, PPT, "blackmagic-davinci")
MODE_FLAGS: dict[str, tuple[str, frozenset]] = {
    "AUXSAYS_ACROBAT_RETIRED_METHODS": ("1", frozenset(
        {(p, m) for p in (PRO, READER) for m in ("adobe_community_search", "reddit_search")})),
    "AUXSAYS_REDDIT_ACCESS_AUTHORIZATION_REF": ("test-authorisation-ref", frozenset(
        {(p, "reddit_search") for p in _REDDIT_READERS})),
    "AUXSAYS_POWERPOINT_REDDIT_FALLBACK": ("true", frozenset({(PPT, "reddit_search")})),
    "AUXSAYS_ENABLE_WINDOWS_ELEVENFORUM_DISCOVERY": ("true", frozenset(
        {(WINDOWS, "elevenforum_windows_listing")})),
}
TUNING = frozenset({
    "AUXSAYS_CHECKPOINT_DIR", "AUXSAYS_COLLECTOR_DEADLINE_SECONDS",
    "AUXSAYS_COLLECTOR_FINALIZE_RESERVE_SECONDS", "AUXSAYS_LEARN_QNA_REQUEST_DELAY_SECONDS",
    "AUXSAYS_LEARN_QNA_USER_AGENT", "AUXSAYS_MAX_REQUESTS_PER_METHOD",
    "AUXSAYS_METHOD_DEADLINE_SECONDS", "AUXSAYS_OBS_FORUM_REQUEST_DELAY_SECONDS",
    "AUXSAYS_REDDIT_BACKOFF_CAP_SECONDS", "AUXSAYS_REDDIT_BACKOFF_SECONDS",
    "AUXSAYS_REDDIT_DIAGNOSTICS", "AUXSAYS_REDDIT_MAX_RETRIES",
    "AUXSAYS_REDDIT_REQUEST_DELAY_SECONDS", "AUXSAYS_REDDIT_USER_AGENT",
    "AUXSAYS_REQ_BACKOFF_CAP_SECONDS", "AUXSAYS_REQ_BACKOFF_SECONDS", "AUXSAYS_REQ_MAX_BYTES",
    "AUXSAYS_REQ_MAX_CUMULATIVE_BACKOFF_SECONDS", "AUXSAYS_REQ_MAX_RETRIES",
    "AUXSAYS_REQ_READ_SLICE_SECONDS", "AUXSAYS_REQ_TOTAL_DEADLINE_SECONDS",
    "AUXSAYS_RUN_COLLECTION_DEADLINE_SECONDS",
})
CLASSIFIED = REGISTRATION_FLAGS | frozenset(MODE_FLAGS) | TUNING
GATE_PREFIXES = ("AUXSAYS_", "BRAVE_SEARCH_API_KEY", "REDDIT_BEARER_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")
NAME_RE = re.compile(r"AUXSAYS_[A-Z0-9_]+")


def _comment_free(text: str) -> str:
    """Shell text without whole-line comments (a name in a comment sets nothing)."""
    return "\n".join(line for line in str(text or "").splitlines() if not line.lstrip().startswith("#"))


def load_workflows() -> dict[str, dict]:
    return {p.name: yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            for p in sorted(WORKFLOWS.glob("*.yml"))}


def iter_steps(docs: dict[str, dict]):
    """(workflow, job_id, job, step, merged env) for every step of every workflow."""
    for wf_name, wf in docs.items():
        wf_env = {k: str(v) for k, v in (wf.get("env") or {}).items()}
        for job_id, job in (wf.get("jobs") or {}).items():
            job_env = {k: str(v) for k, v in (job.get("env") or {}).items()}
            for step in job.get("steps") or []:
                env = dict(wf_env)
                env.update(job_env)
                env.update({k: str(v) for k, v in (step.get("env") or {}).items()})
                yield wf_name, job_id, job, step, env


def workflow_names(docs: dict[str, dict]) -> set[str]:
    """Every AUXSAYS_* key of every env block, and every AUXSAYS_* name a run script uses."""
    names: set[str] = set()
    for wf in docs.values():
        blocks = [wf.get("env") or {}]
        for job in (wf.get("jobs") or {}).values():
            blocks.append(job.get("env") or {})
            for step in job.get("steps") or []:
                blocks.append(step.get("env") or {})
                names |= set(NAME_RE.findall(_comment_free(step.get("run") or "")))
        for block in blocks:
            names |= {k for k in block if str(k).startswith("AUXSAYS_")}
    return names


def workflow_assignments(docs: dict[str, dict]) -> set[str]:
    """AUXSAYS_* names a workflow SETS: env-block keys, and `NAME=` assignments in run scripts."""
    names: set[str] = set()
    for _wf, _job_id, _job, step, env in iter_steps(docs):
        names |= {k for k in env if k.startswith("AUXSAYS_")}
        names |= set(re.findall(r"\b(AUXSAYS_[A-Z0-9_]+)=", _comment_free(step.get("run") or "")))
    return names


def module_names() -> dict[str, list[str]]:
    """Every AUXSAYS_* string constant in the modules a collection run imports (AST, not grep)."""
    files = sorted(list((SCRIPTS / "patch_collectors").glob("*.py")) + list((SCRIPTS / "lib").glob("*.py"))
                   + [SCRIPTS / "run_patch_evidence_collection.py", SCRIPTS / "orchestrate_evidence_run.py"])
    found: dict[str, list[str]] = {}
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and re.fullmatch(r"AUXSAYS_[A-Z0-9_]+", node.value):
                found.setdefault(node.value, []).append(f"{path.name}:{node.lineno}")
    return found


def _modelled(env: dict[str, str]) -> dict[str, str]:
    # `${{ ... }}` is resolved by Actions and unknowable offline: modelled as SET (non-empty).
    return {k: ("<actions-expression>" if "${{" in v else v) for k, v in env.items()}


def production_step(docs: dict[str, dict], script: str) -> tuple[str, dict, dict[str, str]]:
    hits = [(job_id, step, env) for _wf, job_id, _job, step, env in iter_steps(docs)
            if script in _comment_free(step.get("run") or "") and _wf == COLLECTION_YML.name]
    assert len(hits) == 1, f"expected one {script} step in {COLLECTION_YML.name}, found {len(hits)}"
    job_id, step, env = hits[0]
    return job_id, step, _modelled(env)


DOCS = load_workflows()
_RUNNER_JOB, RUNNER_STEP, RUNNER_ENV = production_step(DOCS, "run_patch_evidence_collection.py")
_GRAPH_JOB, GRAPH_STEP, GRAPH_ENV = production_step(DOCS, "orchestrate_evidence_run.py")


def flags_on_values() -> dict[str, str]:
    """Every mode flag whose governed (product, method) pairs are ALL owned, at its on value."""
    return {flag: on for flag, (on, governs) in MODE_FLAGS.items()
            if all(m in co.ALLOWED_METHODS.get(p, set()) for p, m in governs)}


def mode_env(mode: str, product_id: str) -> dict[str, str]:
    if mode == "code_default":
        return {}
    env = dict(GRAPH_ENV if product_id == PPT else RUNNER_ENV)
    if mode == "flags_on":
        env.update(flags_on_values())
    return env


def apply_env(env: dict[str, str]) -> None:
    for key in list(os.environ):
        if key.startswith(GATE_PREFIXES):
            del os.environ[key]
    for key, value in env.items():
        if key.startswith(GATE_PREFIXES):
            os.environ[key] = value


def flag_on(flag: str) -> bool:
    """Read from the environment the MODE set, not through any collector's flag reader."""
    return os.environ.get(flag, "") == MODE_FLAGS[flag][0]


# ---- record selection: one real record per product, chosen by the production newest-first order ---
_FM_CACHE: dict[str, tuple[dict, str]] = {}
_OBS_FM_CACHE: dict[str, tuple[dict, str]] = {}
_real_load = base.load_front_matter_and_body
_real_obs_fm = legacy_obs.front_matter_parts


def _memo_load(path):
    key = str(path)
    if key not in _FM_CACHE:
        _FM_CACHE[key] = _real_load(path)
    data, body = _FM_CACHE[key]
    return dict(data), body


def _memo_obs_fm(path):
    key = str(path)
    if key not in _OBS_FM_CACHE:
        _OBS_FM_CACHE[key] = _real_obs_fm(path)
    data, body = _OBS_FM_CACHE[key]
    return dict(data), body


# Parsing ~1500 front matters costs ~10 s a scan, and the production paths rescan per call. The
# memo changes only the cost: the production filters run unchanged over the same files every time.
base.load_front_matter_and_body = _memo_load
legacy_obs.front_matter_parts = _memo_obs_fm
_CLAIMS = mw.claimed_urls()               # read once; the Windows run reuses a copy each call
_real_claimed_urls = mw.claimed_urls

RECORDS = {pid: base.newest_first(base.generated_records(pid))[0] for pid in PRODUCTS}
TMP = Path(tempfile.mkdtemp(prefix="aux-owned-lifecycle-"))
PPT_GENERATED = TMP / "generated"
PPT_GENERATED.mkdir()
shutil.copy2(RECORDS[PPT].path, PPT_GENERATED / RECORDS[PPT].path.name)


# ---- transport stubs ----------------------------------------------------------------------------
CALLS: dict[str, int] = {}


def _hit(method_id: str) -> None:
    CALLS[method_id] = CALLS.get(method_id, 0) + 1


def _errors_arg(args, kwargs):
    if isinstance(kwargs.get("errors"), list):
        return kwargs["errors"]
    for arg in reversed(args):
        if isinstance(arg, list):
            return arg
    return None


def stub(method_id: str, scenario: str, empty=list, answer=None):
    """A per-method transport entry point: counts its calls; refuses or answers `empty()`."""
    def fn(*args, **kwargs):
        _hit(method_id)
        if scenario == "refuse":
            errors = _errors_arg(args, kwargs)
            if errors is None:
                raise urllib.error.HTTPError("https://example.invalid/", 403, "Forbidden", None, None)
            errors.append({"source_url": "https://example.invalid/", "reason": REFUSAL})
            return empty()
        return answer() if answer is not None else empty()
    return fn


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


def _context(pid: str) -> base.CollectorContext:
    return base.CollectorContext(write=False, since=SINCE, max_pages=5,
                                 target_versions={RECORDS[pid].update_version})


def _one_result(results: list, pid: str) -> list[dict]:
    assert len(results) == 1, f"{pid}: expected one result for one record, got {len(results)}"
    return list(results[0]["method_health"])


# ---- drivers: each calls the product's production path; returns (health rows, dependent input) --
def drive_windows(scenario: str):
    def pool(context, errors):
        _hit("techcommunity_windows_sitemap")
        if scenario == "refuse":
            errors.append({"source_url": "https://techcommunity.microsoft.com/", "reason": REFUSAL})
            return [], {"attempted": 1, "hydration_errors": 1}
        return [], {}
    record = RECORDS[WINDOWS]
    with patched([(mw.learn_qna, "collect_learn_qna_candidates", stub("learn_qna_search_rss", scenario)),
                  (mw, "collect_techcommunity_candidates", pool),
                  (mw, "claimed_urls", lambda: dict(_CLAIMS)),
                  (mw, "generated_records", lambda pid, tv=None, **kw: [record])]):
        return _one_result(mw.WindowsLearnQnaCollector().collect(_context(WINDOWS)), WINDOWS), {}


def drive_obs(scenario: str):
    def search(version, since, max_pages):
        _hit("github_issues")
        if scenario == "refuse":
            raise urllib.error.HTTPError("https://api.github.com/search/issues", 403, "Forbidden", None, None)
        return []

    def pool(*args, **kwargs):
        _hit("obs_forum")
        return [], {"threads_requested": 0, "threads_in_pool": 0}, (REFUSAL if scenario == "refuse" else None)
    with patched([(legacy_obs, "search_issues", search), (forum, "get_pool", pool)]):
        return _one_result(obs_adapter.ObsCollector().collect(_context(OBS)), OBS), {}


def drive_teams(scenario: str):
    with patched([(teams.qna_source, "collect_learn_qna_candidates", stub("learn_qna_search_rss", scenario)),
                  (teams.techcommunity_source, "enumerate_sitemaps",
                   stub("tech_community_discussions", scenario))]):
        return _one_result(teams.TeamsCommunityCollector().collect(_context(TEAMS)), TEAMS), {}


def drive_premiere(scenario: str):
    saved = dict(ap.PREMIERE_METHODS)
    try:
        for method_id in list(ap.PREMIERE_METHODS):
            ap.PREMIERE_METHODS[method_id] = stub(method_id, scenario)
        return _one_result(ap.AdobePremiereCollector().collect(_context(PREMIERE)), PREMIERE), {}
    finally:
        ap.PREMIERE_METHODS.clear()
        ap.PREMIERE_METHODS.update(saved)


def drive_acrobat(pid: str, scenario: str):
    with patched([(ac, "adobe_community_algolia_search_candidates",
                   stub("adobe_community_algolia_search", scenario)),
                  (ac, "adobe_community_search_candidates", stub("adobe_community_search", scenario)),
                  (ac, "reddit_search_candidates", stub("reddit_search", scenario))]):
        _accepted, _rejected, health = ac.AdobeAcrobatCollector(pid).collect_for_record(
            RECORDS[pid], base.CollectorContext(write=False, since=SINCE, max_pages=5), base.utc_now())
        return list(health), {}


def _ppt_resolvable_candidate() -> dict:
    """One Learn Q&A report naming PowerPoint and the Version YYMM but no build: the authority
    rejects it `missing_exact_build`, which is exactly what the context resolver exists for."""
    record = RECORDS[PPT]
    return {
        "source_type": ppt.LEARN_QNA_SOURCE_TYPE, "source_name": ppt.LEARN_QNA_SOURCE_NAME,
        "source_url": "https://learn.microsoft.com/en-us/answers/questions/9990001/powerpoint-crashes",
        "source_date": str(record.update_published_at or "")[:10],
        "parent_title": "PowerPoint crashes when opening a presentation after the update",
        "report_title": "PowerPoint crashes when opening a presentation after the update",
        "report_text": (f"Since updating to PowerPoint Version {record.update_version} on Current Channel, "
                        "PowerPoint crashes every time I open a presentation. Repaired Office, same crash."),
    }


# The thread answers, parses, and states no build anywhere: the resolver reads it and finds nothing.
_NO_BUILD_PAGE = (
    "<html><head><title>PowerPoint crashes - Microsoft Q&amp;A</title>"
    '<script type="application/ld+json">{"@context": "https://schema.org", "@type": "QAPage", '
    '"mainEntity": {"@type": "Question", "id": "9990001", "name": "PowerPoint crashes", '
    '"text": "PowerPoint crashes every time I open a presentation.", "author": "reporter", '
    '"authorId": "reporter-1", "answerCount": 0}}</script></head><body></body></html>')


def drive_powerpoint(scenario: str):
    served = [False]

    def rss_answer():
        if served[0]:
            return []
        served[0] = True
        return [_ppt_resolvable_candidate()]

    def context_fetch(url):
        _hit("learn_qna_segment_context")
        return ("", "blocked") if scenario == "refuse" else (_NO_BUILD_PAGE, "ok")

    pairs = [
        (ppt.learn_qna, "collect_learn_qna_candidates",
         stub("learn_qna_search_rss", scenario, answer=rss_answer)),
        (ppt.reddit_source, "collect_reddit_candidates", stub("reddit_search", scenario)),
        (ppt.stack_exchange_source, "collect_stack_exchange_candidates",
         stub("stack_exchange_search", scenario)),
        (ppt.github_officedev_source, "collect_officedev_candidates",
         stub("github_officedev_issues", scenario, empty=lambda: ([], {}))),
        (ppt.qna_tags, "enumerate_tag", stub("learn_qna_powerpoint_tags", scenario, empty=lambda: ([], 0))),
        (ppt.techcommunity_source, "enumerate_boards", stub("tech_community_discussions", scenario)),
        (ppt.open_web_source, "discover_urls", stub("open_web_discovery", scenario, empty=lambda: ([], {}))),
    ]
    checkpoints = Path(tempfile.mkdtemp(prefix="ckpt-", dir=TMP))
    with patched(pairs):
        # The graph exactly as main() binds it for a dry run -- production method adapters and
        # production capability -- except the transports above, the context fetch, and the three
        # authorities after FINALIZE_EVIDENCE (promote/QA/audit subprocesses emit no method health).
        pipeline = orch.Pipeline(
            REPO, [PPT], write=False, checkpoint_dir=checkpoints, generated_dir=PPT_GENERATED,
            authorities={"promote": lambda: {"rc": 0}, "qa": lambda: {"rc": 0}, "audit": lambda: {"rc": 0}},
            context=base.CollectorContext(write=False, since=SINCE, max_pages=5),
            context_fetch=context_fetch)
        state = pipeline.run()
    assert state.terminal == orch.DONE, f"graph terminated {state.terminal}: {state.failures}"
    rows = [res["health_row"] for res in state.method_results]
    offered = sum(len(res.get("resolvable_rows") or []) for res in state.method_results
                  if res.get("role") != "context_resolution")
    return rows, {"learn_qna_segment_context": offered}


DRIVERS = {
    WINDOWS: drive_windows, OBS: drive_obs, TEAMS: drive_teams, PPT: drive_powerpoint,
    PREMIERE: drive_premiere,
    PRO: lambda s: drive_acrobat(PRO, s), READER: lambda s: drive_acrobat(READER, s),
}
# The production path each driver calls, as the runner registers it (PowerPoint: the graph).
DRIVER_PATH = {WINDOWS: "WindowsLearnQnaCollector", OBS: "ObsCollector", TEAMS: "TeamsCommunityCollector",
               PREMIERE: "AdobePremiereCollector", PRO: "AdobeAcrobatCollector",
               READER: "AdobeAcrobatCollector", PPT: "graph"}
# A DEPENDENT method runs only on what the product's other methods hand it; with no input the
# production path emits no row for it (the router skips RESOLVE_CONTEXT). Exactly one exists.
DEPENDENT = {(PPT, "learn_qna_segment_context")}

# ---- expected states ----------------------------------------------------------------------------
# Products without a METHOD_PLANS entry. "exec" runs its transport and reports the outcome;
# "disabled" emits `disabled` and makes no transport call.
PINNED = {
    WINDOWS: {"learn_qna_search_rss": "exec", "techcommunity_windows_sitemap": "exec"},
    OBS: {"github_issues": "exec", "obs_forum": "exec", "known_watchlist": "disabled"},
    TEAMS: {"learn_qna_search_rss": "exec", "tech_community_discussions": "exec"},
    PRO: {
        "adobe_community_algolia_search": lambda: "exec",
        "adobe_community_search": lambda: "exec" if flag_on("AUXSAYS_ACROBAT_RETIRED_METHODS") else "disabled",
        "reddit_search": lambda: ("exec" if flag_on("AUXSAYS_ACROBAT_RETIRED_METHODS")
                                  and flag_on("AUXSAYS_REDDIT_ACCESS_AUTHORIZATION_REF") else "disabled"),
    },
}
PINNED[READER] = PINNED[PRO]
GRAPH_NODE_METHODS = {PPT: {"learn_qna_segment_context": "exec"}}


def expected_states(pid: str, rows: list[dict]) -> dict[str, str]:
    if pid in mr.METHOD_PLANS:
        plan = mr.plan_methods(pid)
        primary = [r for r in rows if r.get("method_id") in plan["primary"]]
        accepted = sum(int(r.get("accepted_reports") or 0) for r in primary)
        justified, _reason = mr.fallback_justified(primary, accepted, plan["fallback_when"])
        out = {m: "exec" for m in plan["primary"]}
        out.update({m: ("exec" if justified else "disabled") for m in plan["fallback"]})
        out.update({m: "disabled" for m in plan["probe_only"] + plan["disabled"]})
        if "reddit_search" in out and out["reddit_search"] == "exec":
            authorised = flag_on("AUXSAYS_REDDIT_ACCESS_AUTHORIZATION_REF")
            if not authorised or (pid == PPT and not flag_on("AUXSAYS_POWERPOINT_REDDIT_FALLBACK")):
                out["reddit_search"] = "disabled"
        out.update(GRAPH_NODE_METHODS.get(pid, {}))
        return out
    return {m: (s() if callable(s) else s) for m, s in PINNED.get(pid, {}).items()}


# ---- the matrix ---------------------------------------------------------------------------------
def _stamp(value) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def observe(pid: str, mode: str, scenario: str) -> dict:
    apply_env(mode_env(mode, pid))
    CALLS.clear()
    before = UNATTRIBUTED[0]
    t0 = datetime.now(timezone.utc).replace(microsecond=0)
    rows, dependent_input = DRIVERS[pid](scenario)
    t1 = datetime.now(timezone.utc)
    return {"rows": [dict(r) for r in rows], "calls": dict(CALLS), "unattributed": UNATTRIBUTED[0] - before,
            "t0": t0, "t1": t1, "dependent_input": dependent_input,
            "expected": expected_states(pid, rows)}


def run_matrix(products=PRODUCTS, modes=MODES) -> dict:
    return {(pid, mode, scen): observe(pid, mode, scen)
            for mode in modes for pid in products for scen in SCENARIOS}


def judge(matrix: dict) -> list[tuple[str, bool, str]]:
    """B, T, R per (product, mode, scenario); C1, C2, C3, D per (product, mode)."""
    out: list[tuple[str, bool, str]] = []
    pairs = sorted({(pid, mode) for pid, mode, _s in matrix}, key=lambda x: (MODES.index(x[1]), x[0]))
    for pid, mode in pairs:
        owned = set(co.ALLOWED_METHODS.get(pid, set())) - set(co.MANUAL_ONLY_METHODS)
        obs = {s: matrix[(pid, mode, s)] for s in SCENARIOS}
        for scen in SCENARIOS:
            o = obs[scen]
            ids = [str(r.get("method_id")) for r in o["rows"]]
            want = {m for m in owned
                    if (pid, m) not in DEPENDENT or o["dependent_input"].get(m, 0) > 0}
            out.append((f"B1 {mode} {pid} {scen}: emitted methods == owned (minus manual, minus "
                        f"dependent-without-input)", set(ids) == want,
                        f"missing={sorted(want - set(ids))} extra={sorted(set(ids) - want)}"))
            out.append((f"B2 {mode} {pid} {scen}: one row per method", len(ids) == len(set(ids)), str(ids)))
            bad_t = []
            for r in o["rows"]:
                n = o["calls"].get(r["method_id"], 0)
                if (r.get("status") == "disabled" and n != 0) or (r.get("status") != "disabled" and n < 1):
                    bad_t.append(f"{r['method_id']}={r.get('status')}/calls={n}")
            out.append((f"T {mode} {pid} {scen}: disabled rows made 0 transport calls, executing rows >= 1, "
                        f"no unattributed socket", not bad_t and o["unattributed"] == 0,
                        f"{bad_t} unattributed={o['unattributed']}"))
            bad_r = [f"{r['method_id']}: expected={o['expected'].get(r['method_id'])} got={r.get('status')}"
                     for r in o["rows"]
                     if o["expected"].get(r["method_id"]) != ("disabled" if r.get("status") == "disabled"
                                                             else "exec")]
            out.append((f"R {mode} {pid} {scen}: emitted status class == expected state", not bad_r, str(bad_r)))
        st = {s: {str(r["method_id"]): str(r.get("status")) for r in obs[s]["rows"]} for s in SCENARIOS}
        laundered = [m for m, s in st["refuse"].items()
                     if s == "disabled" and st["answer_empty"].get(m) != "disabled"]
        out.append((f"C1 {mode} {pid}: a method disabled under refusal is disabled when answered too",
                    not laundered, str(laundered)))
        expected_exec = [m for m, e in obs["refuse"]["expected"].items()
                         if e == "exec" and m in owned and m in st["refuse"]]
        undegraded = {m: st["refuse"][m] for m in expected_exec if st["refuse"][m] not in mh.DEGRADED_STATUSES}
        out.append((f"C2 {mode} {pid}: every method expected to execute is degraded when every transport "
                    f"refuses", not undegraded, str(undegraded)))
        bad_stamp = []
        for scen in SCENARIOS:
            o = obs[scen]
            for r in o["rows"]:
                if r.get("status") != "disabled" or not str(r.get("last_run") or ""):
                    continue
                at = _stamp(r.get("last_run"))
                if at is None or not (o["t0"] <= at <= o["t1"]):
                    bad_stamp.append(f"{scen}:{r['method_id']}={r.get('last_run')}")
        out.append((f"C3 {mode} {pid}: a disabled row's last_run is empty or stamped by this call",
                    not bad_stamp, str(bad_stamp)))
        now = datetime.now(timezone.utc)
        fresh = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        rows = [dict(r, status=("disabled" if r.get("status") == "disabled" else "success"),
                     last_run=(r.get("last_run") if r.get("status") == "disabled" else fresh))
                for r in obs["answer_empty"]["rows"]]
        decision = mh.certify_monitoring(pid, rows, published_at="2026-01-01T00:00:00Z",
                                         contributing_families=set(), now=now,
                                         thresholds=mh.Thresholds(14, 2),
                                         owned_methods=co.ALLOWED_METHODS,
                                         manual_only_methods=co.MANUAL_ONLY_METHODS)
        h07 = [r for r in decision.reasons if r.startswith(("missing_method_telemetry:", "unowned_method:"))]
        out.append((f"D {mode} {pid}: answered rows give no H7 missing_method_telemetry / H0 unowned_method",
                    not h07, str(h07)))
    return out


def failing(results, prefix: str) -> list[str]:
    return [label for label, ok, _d in results if not ok and label.startswith(prefix)]


# ---- E: mutation self-tests -------------------------------------------------------------------
REMOVED_PAIRS = {PRO: {"adobe_community_bug_tab_index", "adobe_community_known_url_recheck"},
                 READER: {"adobe_community_bug_tab_index", "adobe_community_known_url_recheck"},
                 PREMIERE: {"known_watchlist"}}


@contextlib.contextmanager
def ownership_with(extra: dict[str, set[str]]):
    saved = copy.deepcopy(co.ALLOWED_METHODS)
    try:
        for pid, methods in extra.items():
            co.ALLOWED_METHODS[pid] = set(co.ALLOWED_METHODS.get(pid, set())) | set(methods)
        yield
    finally:
        co.ALLOWED_METHODS.clear()
        co.ALLOWED_METHODS.update(saved)


def e1_phantom_reintroduced() -> tuple[bool, str]:
    with ownership_with(REMOVED_PAIRS):
        res = judge(run_matrix((PRO, READER, PREMIERE), ("workflow",)))
    b1 = failing(res, "B1")
    want = {f"B1 workflow {pid} {s}" for pid in REMOVED_PAIRS for s in SCENARIOS}
    names_phantoms = all(any(m in d for m in REMOVED_PAIRS[label.split()[2]])
                         for label, ok, d in res if not ok and label.startswith("B1"))
    ok = {" ".join(l.split()[:4]).rstrip(":") for l in b1} == want and names_phantoms \
        and len(failing(res, "D ")) == 3
    return ok, f"B1 failing={b1} D failing={failing(res, 'D ')}"


def e2_conditional_relabel() -> tuple[bool, str]:
    real = ac._method_status
    with patched([(ac, "_method_status", lambda c, a, r, e: "disabled" if e else real(c, a, r, e))]):
        res = judge(run_matrix((PRO,), ("workflow",)))
    ok = bool(failing(res, "C1")) and bool(failing(res, "T ")) and bool(failing(res, "R "))
    return ok, f"C1={failing(res, 'C1')} T={failing(res, 'T ')} R={failing(res, 'R ')}"


def e3_unconditional_relabel() -> tuple[bool, str]:
    with patched([(mw, "techcommunity_method_status", lambda pool, accepted, rejected: "disabled")]):
        res = judge(run_matrix((WINDOWS,), ("workflow",)))
    ok = len(failing(res, "T ")) == 2 and len(failing(res, "R ")) == 2 \
        and not failing(res, "B") and not failing(res, "D ")
    return ok, f"T={failing(res, 'T ')} R={failing(res, 'R ')} B={failing(res, 'B')} D={failing(res, 'D ')}"


def e4_flag_on_only_defect() -> tuple[bool, str]:
    real = ac.AdobeAcrobatCollector.collect_for_record

    def hides_failure(self, record, context, captured_at):
        accepted, rejected, health = real(self, record, context, captured_at)
        for row in health:
            if row["method_id"] == "adobe_community_search" and row["status"] in mh.DEGRADED_STATUSES:
                row["status"] = "no_results"
        return accepted, rejected, health
    with patched([(ac.AdobeAcrobatCollector, "collect_for_record", hides_failure)]):
        res = judge(run_matrix((PRO,), MODES))
    c2 = failing(res, "C2")
    return c2 == [f"C2 flags_on {PRO}: every method expected to execute is degraded when every transport "
                  f"refuses"], f"C2 failing={c2}"


def e5_backfilled_stamp() -> tuple[bool, str]:
    real = ac.AdobeAcrobatCollector.collect_for_record

    def backfills(self, record, context, captured_at):
        accepted, rejected, health = real(self, record, context, captured_at)
        for row in health:
            if row["status"] == "disabled" and row.get("last_run"):
                row["last_run"] = "2026-08-07T00:14:09Z"
        return accepted, rejected, health
    with patched([(ac.AdobeAcrobatCollector, "collect_for_record", backfills)]):
        res = judge(run_matrix((PRO,), ("workflow",)))
    return failing(res, "C3") == [f"C3 workflow {PRO}: a disabled row's last_run is empty or stamped by "
                                  f"this call"], f"C3 failing={failing(res, 'C3')}"


def env1_unclassified(docs: dict[str, dict]) -> list[str]:
    return sorted(workflow_names(docs) - CLASSIFIED)


def e6_unclassified_key() -> tuple[bool, str]:
    docs = copy.deepcopy(DOCS)
    job = docs[COLLECTION_YML.name]["jobs"][_RUNNER_JOB]
    job.setdefault("env", {})["AUXSAYS_UNCLASSIFIED_PROBE"] = "true"
    return env1_unclassified(docs) == ["AUXSAYS_UNCLASSIFIED_PROBE"], str(env1_unclassified(docs))


# ---- the suite ----------------------------------------------------------------------------------
def run_suite() -> None:
    print("=" * 92)
    print("A  the plan and the manifest agree")
    print("=" * 92)
    owned_ppt = co.ALLOWED_METHODS[PPT]
    plan_ppt = mr.plan_methods(PPT)
    planned_ppt = set(plan_ppt["primary"] + plan_ppt["fallback"] + plan_ppt["probe_only"] + plan_ppt["disabled"])
    check("A.1 PowerPoint: every planned method is owned", planned_ppt <= owned_ppt,
          str(sorted(planned_ppt - owned_ppt)))
    plan_pr = mr.plan_methods(PREMIERE)
    planned_pr = set(plan_pr["primary"] + plan_pr["fallback"] + plan_pr["probe_only"] + plan_pr["disabled"])
    check("A.2 Premiere: every planned method is owned", planned_pr <= co.ALLOWED_METHODS[PREMIERE],
          str(sorted(planned_pr - co.ALLOWED_METHODS[PREMIERE])))
    check("A.3 Premiere: owned minus manual-only is exactly the plan",
          co.ALLOWED_METHODS[PREMIERE] - co.MANUAL_ONLY_METHODS == planned_pr,
          f"owned-only={sorted(co.ALLOWED_METHODS[PREMIERE] - co.MANUAL_ONLY_METHODS - planned_pr)} "
          f"plan-only={sorted(planned_pr - co.ALLOWED_METHODS[PREMIERE])}")

    print("=" * 92)
    print("REG  each promotion product has exactly one production path, and the driver is that path")
    print("=" * 92)
    assert set(PRODUCTS) == set(report_counts.CONSENSUS_PROMOTION_PRODUCTS), \
        f"promotion products changed: {sorted(report_counts.CONSENSUS_PROMOTION_PRODUCTS)}"
    reach: dict[str, list[str]] = {pid: [] for pid in PRODUCTS}
    for wf_name, job_id, _job, step, env in iter_steps(DOCS):
        run = _comment_free(step.get("run") or "")
        named = re.findall(r"--product-id\s+([a-z0-9][a-z0-9-]*)", run)
        where = f"{wf_name}:{job_id}"
        if "run_patch_evidence_collection.py" in run:
            registry = runner.build_collectors(_modelled(env))
            for pid in PRODUCTS:
                if pid in registry and (not named or pid in named):
                    reach[pid].append(f"runner@{where}")
        if "orchestrate_evidence_run.py" in run:
            for pid in (named or [PPT]):
                if pid in reach:
                    reach[pid].append(f"graph@{where}")
    registry = runner.build_collectors(dict(RUNNER_ENV))
    for pid in PRODUCTS:
        paths = reach[pid]
        if DRIVER_PATH[pid] == "graph":
            ok = len(paths) == 1 and paths[0].startswith("graph@") and pid in runner.orchestrated_products(
                dict(RUNNER_ENV)) and pid not in registry
        else:
            ok = len(paths) == 1 and paths[0].startswith("runner@") and pid in registry
            if ok:
                instance = registry[pid]()
                ok = type(instance).__name__ == DRIVER_PATH[pid] \
                    and str(getattr(instance, "product_id", pid)) == pid
        check(f"REG {pid}: reached by exactly one production path, driven here as {DRIVER_PATH[pid]}",
              ok, str(paths))

    print("=" * 92)
    print("ENV  every AUXSAYS_* name is classified, and no flag of an unowned method is set")
    print("=" * 92)
    check("ENV1 every AUXSAYS_* name a workflow sets or uses is classified", not env1_unclassified(DOCS),
          str(env1_unclassified(DOCS)))
    in_code = module_names()
    check("ENV2 every AUXSAYS_* constant in the production modules is classified",
          not (set(in_code) - CLASSIFIED), str({k: in_code[k] for k in sorted(set(in_code) - CLASSIFIED)}))
    unowned_flags = sorted(flag for flag, (_on, governs) in MODE_FLAGS.items()
                           if not all(m in co.ALLOWED_METHODS.get(p, set()) for p, m in governs))
    set_by_workflow = workflow_assignments(DOCS)
    check("ENV3 no mode flag governing an unowned method is set by any workflow",
          not (set(unowned_flags) & set_by_workflow),
          f"unowned-method flags={unowned_flags} set={sorted(set(unowned_flags) & set_by_workflow)}")

    print("=" * 92)
    print("B T R C D  production paths x modes x scenarios")
    print("=" * 92)
    saved_env = dict(os.environ)
    try:
        matrix = run_matrix()
        results = judge(matrix)
    finally:
        os.environ.clear()
        os.environ.update(saved_env)
    for pid in PRODUCTS:
        owned = set(co.ALLOWED_METHODS.get(pid, set())) - set(co.MANUAL_ONLY_METHODS)
        apply_env(mode_env("workflow", pid))
        expected = expected_states(pid, matrix[(pid, "workflow", "answer_empty")]["rows"])
        check(f"R0 {pid}: every owned non-manual method has an expected state", owned <= set(expected),
              str(sorted(owned - set(expected))))
    os.environ.clear()
    os.environ.update(saved_env)
    order = ("B1", "B2", "T ", "R ", "C1", "C2", "C3", "D ")
    for prefix in order:
        for label, ok, detail in results:
            if label.startswith(prefix):
                check(label, ok, detail)
    for (pid, mode, scen), o in sorted(matrix.items(), key=lambda kv: (MODES.index(kv[0][1]), kv[0][0], kv[0][2])):
        print(f"    {mode:12s} {pid:22s} {scen:12s} "
              + " ".join(f"{r['method_id']}={r.get('status')}/{o['calls'].get(r['method_id'], 0)}"
                         for r in o["rows"]))

    print("=" * 92)
    print("E  each check fails on the defect it exists for")
    print("=" * 92)
    for label, fn in (
            ("E1 reintroducing the five removed pairs fails B1 (and D) on exactly Acrobat Pro, Acrobat "
             "Reader and Premiere", e1_phantom_reintroduced),
            ("E2 a conditional relabel (disabled when errors) fails C1, T and R", e2_conditional_relabel),
            ("E3 an unconditional disabled sitemap status, pool still fetched, fails T and R while B and "
             "D pass", e3_unconditional_relabel),
            ("E4 a failure hidden only when the retired-methods flag is on fails C2 in flags_on only",
             e4_flag_on_only_defect),
            ("E5 a backfilled disabled stamp fails C3", e5_backfilled_stamp),
            ("E6 an unclassified AUXSAYS_* key in a workflow env fails ENV1", e6_unclassified_key)):
        saved_env = dict(os.environ)
        try:
            ok, detail = fn()
        finally:
            os.environ.clear()
            os.environ.update(saved_env)
        check(label, ok, detail)

    print("=" * 92)
    print("corpus guard (WARN, not counted): every owned method has committed telemetry")
    print("=" * 92)
    stored = mh.load_method_health_rows(ROOT / "_data" / "evidence_method_health.yml")
    for pid in PRODUCTS:
        for method in sorted(set(co.ALLOWED_METHODS[pid]) - set(co.MANUAL_ONLY_METHODS)):
            n = sum(1 for r in stored if r.get("product_id") == pid and r.get("method_id") == method)
            warn(f"{pid} {method}: {n} committed rows", n > 0, "owned but never emitted")


def main() -> int:
    try:
        run_suite()
    except Exception:  # noqa: BLE001 - a crash is a failure with its traceback, never a pass
        traceback.print_exc()
        check("suite completed without an exception", False)
    finally:
        base.load_front_matter_and_body = _real_load
        legacy_obs.front_matter_parts = _real_obs_fm
        shutil.rmtree(TMP, ignore_errors=True)
    if WARNINGS:
        print(f"WARNINGS: {len(WARNINGS)}")
    if FAILURES:
        print("FAILED CHECKS:")
        for label in FAILURES:
            print(f"  - {label}")
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
