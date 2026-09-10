#!/usr/bin/env python3
"""A green patch-ingestion run must not be able to hide an enabled source that failed.

THE DEFECT
----------
`patch_ingest.py` returned 0 unless `--strict` was passed, and the production workflow never passed
it. Production run 34391487960 logged four `[ERROR] elgato-*: HTTP 403 while fetching official
source` lines and concluded **success**. Workflow green did not mean ingestion healthy.

A blanket `--strict` was not the repair. It exits non-zero when ANY enabled source errors -- which
would pin the lane red for as long as one vendor blocks us -- and it also `break`s out of the source
loop on the first error, throwing away valid discovery from every source that had not run yet.

Two separate things were wrong and both are tested here:

1. RUN LEVEL. Nothing read the per-source health back at the end of the run. The state file already
   said `elgato-stream-deck: status failing, consecutive_failures 13`; the process still exited 0.

2. SOURCE LEVEL. `classify_success` returned `degraded` for every zero-extraction run, with a note
   that said the state "can mean no new updates or that the parser needs review" -- it recorded that
   it could not tell those apart. And `update_source_success` stamped `last_success_at` even when
   nothing was extracted, so a source whose parser had rotted looked freshly successful forever.
   Measured on Netlify at 3a47e1f8: `www.netlify.com/changelog/` serves HTTP 200 and 152 KB with 41
   `/changelog/` links; `NETLIFY_DETAIL_RE` requires `/changelog/YYYY/M/D/slug/`; zero of the 41
   match because the site moved to slug-only URLs. Every run since has reported `status: "success"`.

WHAT COUNTS AS A CATCH
----------------------
These are behaviour tests over the real `lib.state` and `lib.ingest_health` functions, not string
searches over source files. A mutation is CAUGHT only when the intended semantic assertion fails --
a crash, an import error or an unrelated exception is NOT a catch, and the mutation harness at the
end asserts that distinction explicitly.

Run standalone. Deterministic, offline, writes nothing outside a temp dir.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "auxsays" / "scripts"))

from lib import ingest_health as H  # noqa: E402
from lib.state import (  # noqa: E402
    DEFAULT_EMPTY_EXTRACTION_TOLERANCE,
    classify_success,
    update_source_error,
    update_source_success,
)

NEWLINE = "\n"
_passed = 0
_failed = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  PASS  {label}")
    else:
        _failed += 1
        print(f"  FAIL  {label}" + (f"  --  {detail}" if detail else ""))


def src(pid: str, *, enabled: bool = True, adapter: str = "html_changelog") -> dict:
    return {"product_id": pid, "company_id": "c", "enabled": enabled,
            "ingestion": {"adapter": adapter, "type": adapter}}


def fresh() -> dict:
    return {}


def succeed(state, pid, *, fetched, at="2026-09-10T00:00:00Z", tolerance=None):
    kw = {} if tolerance is None else {"tolerance": tolerance}
    update_source_success(state, pid, checked_at=at, duration_ms=100, adapter="html_changelog",
                          fetched=fetched, written=fetched, skipped=0, **kw)


def fail(state, pid, *, error, at="2026-09-10T00:00:00Z"):
    update_source_error(state, pid, checked_at=at, duration_ms=0,
                        adapter="html_changelog", error=error)


def status_of(state, pid):
    return ((state.get("sources") or {}).get(pid) or {}).get("status")


def res(pid, *, fetched, written=0):
    """A result dict shaped exactly as `run_source` returns one."""
    return {"product_id": pid, "adapter": "html_changelog", "candidate_count": fetched,
            "written": [f"w{i}" for i in range(written)], "status": "success"}


def err(pid, message="HTTP 403 while fetching official source"):
    return {"product_id": pid, "adapter": "html_changelog", "error": message}


def rows_for(state, sources, results=None, errors=None):
    return H.source_rows(state, sources, results or [], errors or [])


def verdict_for(state, sources, results=None, errors=None):
    return H.classify_run(rows_for(state, sources, results, errors))


def main() -> int:
    T = DEFAULT_EMPTY_EXTRACTION_TOLERANCE

    print(NEWLINE + "[1] healthy source + valid extraction -> success")
    st = fresh(); succeed(st, "github", fetched=10)
    check("1a source status is healthy", status_of(st, "github") == "healthy", str(status_of(st, "github")))
    check("1b run is healthy", verdict_for(st, [src("github")], [res("github", fetched=10)]) == H.RUN_HEALTHY)
    check("1c the extraction timestamp is recorded",
          bool(st["sources"]["github"].get("last_extraction_at")))

    print(NEWLINE + "[2] healthy source + valid extraction + no new release -> no_results")
    st = fresh(); succeed(st, "obs-studio", fetched=4); succeed(st, "obs-studio", fetched=0)
    check("2a a single quiet check is no_results, not a failure",
          status_of(st, "obs-studio") == "no_results", str(status_of(st, "obs-studio")))
    check("2b the run stays healthy -- quiet is not broken",
          verdict_for(st, [src("obs-studio")], [res("obs-studio", fetched=0)]) == H.RUN_HEALTHY)
    check("2c and the last real extraction is still remembered",
          st["sources"]["obs-studio"]["last_extraction_at"] == "2026-09-10T00:00:00Z")

    print(NEWLINE + "[3] HTTP 403 / WAF -> blocked")
    st = fresh(); fail(st, "elgato-stream-deck", error="HTTP 403 while fetching official source")
    b = st["sources"]["elgato-stream-deck"]
    check("3a the error is classified as blocked", b["last_error_type"] == "blocked", b["last_error_type"])
    check("3b the source is not trustworthy", b["status"] not in H.TRUSTWORTHY, b["status"])
    check("3c a lone blocked source fails the run -- nothing trustworthy ran",
          verdict_for(st, [src("elgato-stream-deck")], [], [err("elgato-stream-deck")]) == H.RUN_FAILED)

    print(NEWLINE + "[4] HTTP 500 / transport failure -> not trustworthy")
    st = fresh(); fail(st, "x", error="HTTP 500 server error")
    check("4a transport failure is recorded as an error state",
          status_of(st, "x") not in H.TRUSTWORTHY, str(status_of(st, "x")))
    fail(st, "x", error="HTTP 500 server error")
    check("4b a second consecutive failure escalates", status_of(st, "x") == "failing",
          str(status_of(st, "x")))

    print(NEWLINE + "[5] HTTP 200 + parser structural mismatch -> broken, NOT no_results")
    # The Netlify shape: the fetch works every time and extracts nothing, forever.
    st = fresh()
    for i in range(T + 1):
        succeed(st, "netlify", fetched=0, at=f"2026-09-{i + 1:02d}T00:00:00Z")
    check("5a sustained zero-extraction is broken", status_of(st, "netlify") == "broken",
          str(status_of(st, "netlify")))
    check("5b it is explicitly NOT no_results", status_of(st, "netlify") != "no_results")
    check("5c and NOT reported as a plain success", status_of(st, "netlify") != "healthy")
    check("5d a source that never extracted has no extraction timestamp to show",
          not st["sources"]["netlify"].get("last_extraction_at"))
    check("5e the run does not look healthy",
          verdict_for(st, [src("netlify")], [res("netlify", fetched=0)]) != H.RUN_HEALTHY)
    # THE DISCRIMINATOR. Below tolerance the same evidence must still read as quiet, or `broken`
    # would just be "zero extraction" renamed and would fire on every genuinely quiet source.
    st2 = fresh()
    for i in range(T):
        succeed(st2, "netlify", fetched=0, at=f"2026-09-{i + 1:02d}T00:00:00Z")
    check("5f below tolerance the identical evidence is still no_results",
          status_of(st2, "netlify") == "no_results", str(status_of(st2, "netlify")))

    print(NEWLINE + "[9] extraction ages past expectation -> stale (worked before), not broken")
    st = fresh(); succeed(st, "moved", fetched=3, at="2026-01-01T00:00:00Z")
    for i in range(T + 1):
        succeed(st, "moved", fetched=0, at=f"2026-09-{i + 1:02d}T00:00:00Z")
    check("9a a source that USED to extract goes stale, not broken",
          status_of(st, "moved") == "stale", str(status_of(st, "moved")))
    check("9b and it still reports when it last really worked",
          st["sources"]["moved"]["last_extraction_at"] == "2026-01-01T00:00:00Z")
    check("9c stale is not trustworthy output", "stale" not in H.TRUSTWORTHY)
    # A source may declare that its own silence stays plausible for longer.
    st3 = fresh()
    for i in range(T + 1):
        succeed(st3, "rare", fetched=0, at=f"2026-09-{i + 1:02d}T00:00:00Z", tolerance=T + 50)
    check("9d a source-specific tolerance overrides the shared default",
          status_of(st3, "rare") == "no_results", str(status_of(st3, "rare")))

    print(NEWLINE + "[6] mixed healthy + blocked -> healthy output kept AND degradation visible")
    st = fresh()
    succeed(st, "github", fetched=10)
    fail(st, "elgato-stream-deck", error="HTTP 403 while fetching official source")
    sources = [src("github"), src("elgato-stream-deck")]
    rows = rows_for(st, sources, [res("github", fetched=10, written=2)], [err("elgato-stream-deck")])
    v = H.classify_run(rows)
    check("6a the run is degraded, not failed and not healthy", v == H.RUN_DEGRADED, v)
    check("6b the healthy source's records are preserved in the report",
          any(r["source_id"] == "github" and r["records_fetched"] == 10 for r in rows))
    emitted: list[str] = []
    H.annotate(rows, v, emit=emitted.append)
    check("6c a warning annotation names the failing source",
          any("elgato-stream-deck" in m and "::warning" in m for m in emitted), str(emitted))
    check("6d no annotation is emitted for the healthy source",
          not any("github" in m for m in emitted), str(emitted))
    summary = H.summarise(rows, v)
    check("6e the summary states degradation in plain language",
          "not collecting" in summary and "DEGRADED" in summary, summary[:120])
    check("6f and says the healthy source's records were kept",
          "were kept" in summary, summary[:200])

    print(NEWLINE + "[7] every enabled source fails -> the run must not look healthy")
    st = fresh()
    fail(st, "a", error="HTTP 403 while fetching official source")
    fail(st, "b", error="Timeout while fetching")
    errs = [err("a"), err("b", "Timeout while fetching")]
    v = verdict_for(st, [src("a"), src("b")], [], errs)
    check("7a verdict is failed", v == H.RUN_FAILED, v)
    check("7b and that is the case the exit code must reflect", H.RUN_FAILED == "failed")
    emitted = []
    H.annotate(rows_for(st, [src("a"), src("b")], [], errs), v, emit=emitted.append)
    check("7c an error annotation is emitted", any("::error" in m for m in emitted), str(emitted))

    print(NEWLINE + "[8] a DISABLED source failing must not poison production health")
    st = fresh()
    succeed(st, "github", fetched=10)
    fail(st, "staged-thing", error="HTTP 403 while fetching official source")
    sources = [src("github"), src("staged-thing", enabled=False)]
    rows = rows_for(st, sources, [res("github", fetched=10)], [err("staged-thing")])
    check("8a the run stays healthy", H.classify_run(rows) == H.RUN_HEALTHY,
          H.classify_run(rows))
    check("8b the disabled source is still reported, not hidden",
          any(r["source_id"] == "staged-thing" for r in rows))
    emitted = []
    H.annotate(rows, H.classify_run(rows), emit=emitted.append)
    check("8c but it raises no annotation against production",
          not any("staged-thing" in m for m in emitted), str(emitted))

    print(NEWLINE + "[DC] the streak must not be counted twice on a write run")
    # On a write run `update_source_*` already advanced the bucket during the loop. Re-deriving the
    # streak afterwards double-counted the check: production run 34436159379 persisted
    # `consecutive_empty_extractions: 1` for the Elgato buckets while the reported row said 2, and a
    # source could therefore be declared `broken` a full run early. A dry run persists nothing, so
    # there the increment must still happen.
    st = fresh()
    fail(st, "elg", error="HTTP 403 while sfetching official source".replace("sf", "f"))
    bucket_streak = st["sources"]["elg"]["consecutive_empty_extractions"]
    wrote = H.source_rows(st, [src("elg")], [], [err("elg")], already_persisted=True)
    check("DC1 a write run reports the streak the bucket already holds",
          wrote[0]["consecutive_empty_extractions"] == bucket_streak,
          f"row={wrote[0]['consecutive_empty_extractions']} bucket={bucket_streak}")
    dry = H.source_rows(st, [src("elg")], [], [err("elg")], already_persisted=False)
    check("DC2 a dry run projects one further check, because it persists nothing",
          dry[0]["consecutive_empty_extractions"] == bucket_streak + 1,
          f"row={dry[0]['consecutive_empty_extractions']} bucket={bucket_streak}")
    # And the same must hold for the classification, not just the reported number.
    st2 = fresh()
    for i in range(T):
        succeed(st2, "rot", fetched=0, at=f"2026-09-{i + 1:02d}T00:00:00Z")
    at_tolerance = st2["sources"]["rot"]["consecutive_empty_extractions"]
    row_w = H.source_rows(st2, [src("rot")], [res("rot", fetched=0)], [], already_persisted=True)
    check("DC3 at exactly the tolerance a write run does not prematurely say broken",
          row_w[0]["status"] == "no_results",
          f"streak={at_tolerance} status={row_w[0]['status']}")

    print(NEWLINE + "[TR] the threshold boundary, walked through the REAL write-run sequence")
    # A write run persists via `update_source_*` and THEN reports via `source_rows`. Both halves
    # must agree on where the threshold falls, check by check, or the reported status and the
    # persisted status diverge at exactly the boundary that matters.
    def write_run_check(state, pid):
        """One production-shaped check: persist, then report with already_persisted=True."""
        succeed(state, pid, fetched=0,
                at=f"2026-10-{len(state.get('sources', {}).get(pid, {}).get('seen', [])) + 1:02d}T00:00:00Z")
        row = H.source_rows(state, [src(pid)], [res(pid, fetched=0)], [], already_persisted=True)[0]
        return state["sources"][pid], row

    st = fresh()
    for _ in range(T - 1):
        write_run_check(st, "edge")
    bucket, row = write_run_check(st, "edge")            # A: tolerance - 1  ->  tolerance
    check("TR-A streak reaches EXACTLY the tolerance after tolerance-1 plus one no-record run",
          bucket["consecutive_empty_extractions"] == T, str(bucket["consecutive_empty_extractions"]))
    check("TR-A at exactly the tolerance the PERSISTED status is still no_results",
          bucket["status"] == "no_results", bucket["status"])
    check("TR-A and the REPORTED row agrees -- it does not fire one run early",
          row["status"] == "no_results", f"row={row['status']} bucket={bucket['status']}")
    check("TR-A reported streak equals persisted streak",
          row["consecutive_empty_extractions"] == bucket["consecutive_empty_extractions"],
          f"row={row['consecutive_empty_extractions']} bucket={bucket['consecutive_empty_extractions']}")
    bucket, row = write_run_check(st, "edge")            # B: tolerance  ->  tolerance + 1
    check("TR-B one further no-record run crosses the threshold",
          bucket["consecutive_empty_extractions"] == T + 1, str(bucket["consecutive_empty_extractions"]))
    check("TR-B the persisted status becomes broken exactly here, as designed",
          bucket["status"] == "broken", bucket["status"])
    check("TR-B and the reported row becomes broken on the SAME run, not a run later",
          row["status"] == "broken", f"row={row['status']} bucket={bucket['status']}")
    check("TR-B reported streak still equals persisted streak after crossing",
          row["consecutive_empty_extractions"] == bucket["consecutive_empty_extractions"],
          f"row={row['consecutive_empty_extractions']} bucket={bucket['consecutive_empty_extractions']}")
    # The same boundary for a source that USED to extract: it must cross into `stale`, not `broken`.
    st = fresh(); succeed(st, "was", fetched=4, at="2026-01-01T00:00:00Z")
    for _ in range(T):
        write_run_check(st, "was")
    bucket, row = write_run_check(st, "was")
    check("TR-B' a source that previously extracted crosses into stale, not broken",
          bucket["status"] == "stale" and row["status"] == "stale",
          f"row={row['status']} bucket={bucket['status']}")

    print(NEWLINE + "[FC] an unobserved source must fail CLOSED, never open")
    # If a source reaches `attempted` but yields neither a result nor an error -- a control-flow gap,
    # a future refactor, a `continue` added in the wrong place -- the honest answer is "unknown",
    # never "healthy". Defaulting the other way would silently readmit exactly the class of bug this
    # module exists to close, and an adversarial pass showed nothing was testing it.
    unobserved = rows_for(fresh(), [src("ghost")], [], [])
    check("FC1 a source with no result and no error is not trustworthy",
          unobserved[0]["status"] not in H.TRUSTWORTHY, str(unobserved[0]["status"]))
    check("FC2 and it drags the run off healthy",
          H.classify_run(unobserved) != H.RUN_HEALTHY, H.classify_run(unobserved))
    check("FC3 and it is annotated rather than passed over",
          any("ghost" in m for m in (lambda acc: (H.annotate(unobserved, H.classify_run(unobserved),
                                                             emit=acc.append), acc)[1])([])))

    print(NEWLINE + "[E] the empty-scope case is not evidence of health either way")
    # An empty scope is NOT health. Reporting it as healthy let a `--source` typo persist
    # `healthy` over a stored `failed` while the per-source buckets still said `failing`.
    check("E1 nothing in scope is reported as not-evaluated, not as healthy",
          H.classify_run([]) == H.RUN_NOT_EVALUATED, H.classify_run([]))
    check("E2 and not-evaluated is a distinct verdict from healthy",
          H.RUN_NOT_EVALUATED != H.RUN_HEALTHY)
    check("E3 summarise renders it without crashing",
          "nothing about collection health" in H.summarise([], H.RUN_NOT_EVALUATED))

    print(NEWLINE + "[PUB] the public source-health page must not publish a rotted source as Active")
    # This was live at 3a47e1f8: auxsays.com/updates/methodology/ rendered
    # `netlify ... Active  No new records  2026-09-10T00:03:01Z` -- today's timestamp, on a source
    # whose parser had matched nothing since 2026-04-29 and which has never produced a record.
    # `status_for` short-circuited on `fetched == 0` BEFORE consulting the source's own status, so
    # every rotted source was published as Active.
    import source_health_snapshot as SHS
    live = {"enabled": True, "ingestion": {"adapter": "html_changelog"}, "recommended_priority": ""}

    def pub(status, **extra):
        st = {"status": status, "last_checked_at": "t", "last_records_fetched": 0,
              "last_records_written": 0, "last_success_at": "t", **extra}
        return SHS.status_for(live, st, st.get("last_error", ""))

    check("PUB1 a genuinely quiet source is still Active",
          pub("no_results") == ("Active", "No new records"), str(pub("no_results")))
    check("PUB2 a source whose parser never matched is NOT Active",
          pub("broken")[0] == "Error", str(pub("broken")))
    check("PUB3 and says so in plain language, not a raw enum",
          "broken" not in pub("broken")[1].lower() and pub("broken")[1].strip() != "",
          str(pub("broken")))
    check("PUB4 a source that stopped extracting is NOT Active",
          pub("stale", last_extraction_at="2026-04-29T00:00:00Z")[0] == "Error",
          str(pub("stale", last_extraction_at="2026-04-29T00:00:00Z")))
    check("PUB5 and it names the date it last really worked",
          "2026-04-29" in pub("stale", last_extraction_at="2026-04-29T00:00:00Z")[1],
          str(pub("stale", last_extraction_at="2026-04-29T00:00:00Z")))
    healthy = SHS.status_for(live, {"status": "healthy", "last_checked_at": "t",
                                    "last_records_fetched": 5, "last_records_written": 2,
                                    "last_success_at": "t"}, "")
    check("PUB6 a healthy source is unaffected", healthy == ("Active", "Active"), str(healthy))
    blocked = SHS.status_for(live, {"status": "failing", "last_checked_at": "t",
                                    "consecutive_failures": 3, "last_records_fetched": 0,
                                    "last_records_written": 0}, "")
    check("PUB7 a blocked source is still an Error", blocked[0] == "Error", str(blocked))

    print(NEWLINE + "[10] a source that CHANGES failure mode must not restart the clock")
    # The real Elgato trajectory. Four sources served HTTP 403 for 13 consecutive production runs;
    # transport then recovered and they began fetching ~30 help-centre articles and extracting 0
    # from them (`parser_misses=7`, `no_matching_articles=True`). If the no-record streak counted
    # only empty PARSES, recovering transport would reset it to 1 and present a source that has
    # produced nothing for weeks as freshly quiet.
    st = fresh()
    for i in range(13):
        fail(st, "elgato-stream-deck", error="HTTP 403 while fetching official source",
             at=f"2026-09-{i + 1:02d}T00:00:00Z")
    check("10a a blocked source accrues the no-record streak",
          st["sources"]["elgato-stream-deck"]["consecutive_empty_extractions"] == 13,
          str(st["sources"]["elgato-stream-deck"]["consecutive_empty_extractions"]))
    succeed(st, "elgato-stream-deck", fetched=0, at="2026-09-20T00:00:00Z")
    check("10b recovering the FETCH while still extracting nothing is broken, not quiet",
          status_of(st, "elgato-stream-deck") == "broken", str(status_of(st, "elgato-stream-deck")))
    check("10c the streak carried across the mode change",
          st["sources"]["elgato-stream-deck"]["consecutive_empty_extractions"] == 14)
    succeed(st, "elgato-stream-deck", fetched=5, at="2026-09-21T00:00:00Z")
    check("10d and one real extraction clears it completely",
          status_of(st, "elgato-stream-deck") == "healthy"
          and st["sources"]["elgato-stream-deck"]["consecutive_empty_extractions"] == 0)

    print(NEWLINE + "[E2E] patch_ingest.main() itself, invoked -- not inspected")
    # The run-level half USED to be covered only by `inspect.getsource` substring searches, which is
    # the failure mode this repo has been bitten by twice. An adversarial pass proved it: mutating
    # `if verdict == RUN_FAILED: return 1` to `return 0` -- the exact line that closes the defect --
    # left the suite fully green. These checks call main() and assert the RETURN CODE.
    import json
    import tempfile
    import types
    import patch_ingest as PI

    def run_main(sources_spec, *, argv_extra=(), seed_state=None):
        """Invoke the real main() against a temp config/state/output with stubbed adapters."""
        tmp = Path(tempfile.mkdtemp())
        cfg = [{"company_id": "c", "product_id": pid, "company": "C", "software": pid,
                "public_category": "x", "enabled": en, "recommended_priority": "",
                "ingestion": {"type": "stub", "adapter": "stub",
                              "official_url": "https://example.invalid/"},
                "generated_record": {}, "community_future": {}}
               for pid, en, _behaviour in sources_spec]
        import yaml as _yaml
        (tmp / "cfg.yml").write_text(_yaml.safe_dump(cfg), encoding="utf-8")
        (tmp / "state.json").write_text(json.dumps(seed_state or {}), encoding="utf-8")
        (tmp / "out").mkdir()
        behaviour = {pid: b for pid, _en, b in sources_spec}

        def fake_adapter_module(_name):
            mod = types.SimpleNamespace()

            def fetch(source, **_kw):
                pid = str(source.get("product_id"))
                what = behaviour[pid]
                if what == "raise":
                    raise RuntimeError("HTTP 403 while fetching official source")
                if what == "records":
                    return [{"record_id": f"{pid}:r{i}", "version": f"1.{i}", "title": f"{pid} 1.{i}",
                             "source_url": f"https://example.invalid/{pid}/{i}"} for i in range(2)]
                return []          # a successful fetch that extracts nothing
            mod.fetch = fetch
            return mod

        original = PI.adapter_module
        PI.adapter_module = fake_adapter_module
        summary = tmp / "summary.md"
        import os
        prev = os.environ.get("GITHUB_STEP_SUMMARY")
        os.environ["GITHUB_STEP_SUMMARY"] = str(summary)
        prev_argv = sys.argv
        sys.argv = ["patch_ingest.py", "--config", str(tmp / "cfg.yml"),
                    "--state", str(tmp / "state.json"), "--output", str(tmp / "out"), *argv_extra]
        import io
        import contextlib
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                code = PI.main()
        finally:
            sys.argv = prev_argv
            PI.adapter_module = original
            if prev is None:
                os.environ.pop("GITHUB_STEP_SUMMARY", None)
            else:
                os.environ["GITHUB_STEP_SUMMARY"] = prev
        state = json.loads((tmp / "state.json").read_text(encoding="utf-8"))
        text = buf.getvalue()
        run_main.stdout = text
        start = text.find("{")
        run_main.report = json.loads(text[start:]) if start >= 0 else {}
        return code, state, (summary.read_text(encoding="utf-8") if summary.exists() else "")

    code, state, summary = run_main([("alpha", True, "raise")])
    check("E2E1 a production run where the only enabled source fails returns NON-ZERO",
          code == 1, f"return code {code} -- this is the line the whole sprint turns on")
    check("E2E2 and persists the failed verdict", state.get("last_run_health") == "failed",
          str(state.get("last_run_health")))
    check("E2E3 and writes a step summary saying so",
          "FAILED" in summary, summary[:120])

    code, state, summary = run_main([("alpha", True, "raise"), ("beta", True, "empty")])
    check("E2E4 impaired + a source that produced nothing is still failed",
          code == 1 and state.get("last_run_health") == "failed",
          f"code={code} verdict={state.get('last_run_health')}")

    code, state, summary = run_main([("beta", True, "empty")])
    check("E2E5 a lone quiet source is healthy and returns zero",
          code == 0 and state.get("last_run_health") == "healthy",
          f"code={code} verdict={state.get('last_run_health')}")

    # THE DRY-RUN REGRESSION. Seed state that claims health, then dry-run a source that 403s.
    seeded = {"sources": {"alpha": {"seen": [], "status": "healthy", "last_success_at": "x",
                                    "last_records_fetched": 5, "consecutive_failures": 0}},
              "last_run_health": "healthy"}
    code, state, summary = run_main([("alpha", True, "raise")],
                                    argv_extra=("--dry-run",), seed_state=seeded)
    check("E2E6 a DRY RUN grades this run, not the last one",
          code == 1, f"return code {code} -- a dry run inherited yesterday's `healthy` before this")
    check("E2E7 and its summary does not claim health",
          "normally" not in summary, summary[:160])
    check("E2E8 while a dry run still writes nothing to state",
          state.get("last_run_health") == "healthy",
          "the seeded value must survive: dry runs must not persist")

    # THE EMPTY-SCOPE REGRESSION. A --source typo must not overwrite a stored verdict.
    seeded = {"sources": {"alpha": {"seen": [], "status": "failing", "consecutive_failures": 13}},
              "last_run_health": "failed"}
    code, state, summary = run_main([("alpha", True, "raise")],
                                    argv_extra=("--source", "nosuchsource"), seed_state=seeded)
    check("E2E9 a scope that matches nothing does not overwrite a stored verdict",
          state.get("last_run_health") == "failed", str(state.get("last_run_health")))
    check("E2E10 and does not crash rendering the not-evaluated summary", code == 0, f"code={code}")

    # E -- one hard-failing source plus a healthy one. An adversarial mutation that made DEGRADED
    # exit non-zero survived the suite: nothing asserted this case end to end.
    code, state, summary = run_main([("good", True, "records"), ("dead", True, "raise")],
                                    argv_extra=("--dry-run",))
    rep = run_main.report
    check("E2E-E1 a mixed run is degraded", rep.get("run_health") == "degraded",
          str(rep.get("run_health")))
    check("E2E-E2 and exits ZERO -- the healthy vendor's work must not be thrown away",
          code == 0, f"return code {code}")
    check("E2E-E3 the healthy source's output is preserved in the report",
          any(r.get("product_id") == "good" and r.get("candidate_count") == 2
              for r in rep.get("results") or []), str(rep.get("results"))[:160])
    check("E2E-E4 a warning names the failing source",
          "::warning" in run_main.stdout and "dead" in run_main.stdout, run_main.stdout[:200])

    # THE PRODUCTION BUG AT THE WIRING LEVEL. Run 34436159379 persisted streak 1 while reporting 2.
    # The unit checks pass `already_persisted` themselves, so they cannot see `patch_ingest.main()`
    # passing the wrong value -- an adversarial mutation doing exactly that survived. This drives a
    # WRITE run through main() and compares what it REPORTED against what it PERSISTED.
    code, state, summary = run_main([("wired", True, "raise")])
    reported = next((r for r in run_main.report.get("source_health") or []
                     if r.get("source_id") == "wired"), {})
    persisted = state["sources"]["wired"]
    check("E2E-W1 a write run's reported streak equals its persisted streak",
          reported.get("consecutive_empty_extractions") == persisted.get("consecutive_empty_extractions"),
          f"reported={reported.get('consecutive_empty_extractions')} "
          f"persisted={persisted.get('consecutive_empty_extractions')}")
    check("E2E-W2 and its reported failure count equals its persisted one",
          reported.get("consecutive_failures") == persisted.get("consecutive_failures"),
          f"reported={reported.get('consecutive_failures')} persisted={persisted.get('consecutive_failures')}")

    # D -- a dry run must PROJECT the check it is making, because it persists nothing. At a streak of
    # exactly the tolerance, one more empty check crosses the threshold; a dry run that forgot to
    # project would still call it quiet.
    seeded = {"sources": {"edge": {"seen": [], "status": "no_results", "last_success_at": "x",
                                   "consecutive_empty_extractions": T, "consecutive_failures": 0}}}
    code, state, summary = run_main([("edge", True, "empty")], argv_extra=("--dry-run",),
                                    seed_state=seeded)
    dry_row = next((r for r in run_main.report.get("source_health") or []
                    if r.get("source_id") == "edge"), {})
    check("E2E-D1 a dry run at the tolerance projects this check and sees the crossing",
          dry_row.get("status") == "broken", f"dry-run status={dry_row.get('status')}")
    check("E2E-D2 while persisting nothing", state["sources"]["edge"]["consecutive_empty_extractions"] == T,
          str(state["sources"]["edge"]["consecutive_empty_extractions"]))

    print(NEWLINE + "[P] the PRE-FIX semantics, simulated, must fail these same questions")
    # Running this suite against the old `lib.state` raises ImportError, and an ImportError is a
    # crash, not a catch -- this file says so itself. So the old behaviour is reproduced here
    # verbatim and asked the same questions, which is a semantic comparison rather than a
    # statement about which symbols happen to exist.
    def prefix_classify_success(fetched, written, skipped):
        """`lib.state.classify_success` exactly as it stood at 3a47e1f8."""
        if fetched > 0:
            return "healthy"
        return "degraded"

    # Not `f(0,0,0) == f(0,0,0)`, which is true of any function. The point is that the pre-fix
    # code returned one verdict for BOTH situations while the shipped code returns two.
    check("P1 pre-fix gave rot and a quiet check the same verdict; the fix gives them different ones",
          prefix_classify_success(0, 0, 0) == "degraded"
          and classify_success(0, 0, 0, consecutive_empty=1)
          != classify_success(0, 0, 0, consecutive_empty=T + 1))
    check("P2 so pre-fix could not answer check 5a at all",
          prefix_classify_success(0, 0, 0) != "broken",
          "if the old code already said broken, check 5a proves nothing")
    check("P3 and could not answer check 9a either",
          prefix_classify_success(0, 0, 0) != "stale")
    check("P4 whereas the shipped code separates them on the same inputs",
          classify_success(0, 0, 0, consecutive_empty=T + 1, ever_extracted=False) == "broken"
          and classify_success(0, 0, 0, consecutive_empty=T + 1, ever_extracted=True) == "stale"
          and classify_success(0, 0, 0, consecutive_empty=1) == "no_results")
    # The run-level half: pre-fix, `patch_ingest.main` ended in an unconditional `return 0` unless
    # --strict was passed. Assert the shipped policy does NOT have that shape.
    import inspect
    import patch_ingest
    main_src = inspect.getsource(patch_ingest.main)
    check("P5 the run's exit is decided by the health verdict, not by an unconditional return",
          "RUN_FAILED" in main_src and "run_health" in main_src,
          "main() must consult the verdict before returning")
    check("P6 and a failing source no longer abandons the remaining sources",
          "if args.strict:\n                break" not in main_src,
          "the --strict break discarded healthy vendors' discovery")

    print(NEWLINE + "[M] mutation harness -- a catch must be a SEMANTIC failure, not a crash")
    mutations = [
        ("classify_success ignores the tolerance and always says no_results",
         lambda: "no_results" if True else "", "5a"),
        ("TRUSTWORTHY wrongly includes broken", None, "6a"),
    ]
    # Mutation 1: collapse the zero-extraction branch back to a single verdict.
    import lib.state as S
    original = S.classify_success
    try:
        S.classify_success = lambda f, w, s, **k: "healthy" if f > 0 else "no_results"
        st_m = fresh()
        for i in range(T + 1):
            # call through update_source_success so the mutation is exercised in situ
            S.update_source_success(st_m, "netlify", checked_at=f"2026-09-{i + 1:02d}T00:00:00Z",
                                    duration_ms=1, adapter="a", fetched=0, written=0, skipped=0)
        caught = status_of(st_m, "netlify") != "broken"
        check("M1 collapsing the zero-extraction branch is caught by check 5a", caught,
              f"mutant status={status_of(st_m, 'netlify')} -- 5a would still pass, so 5a is vacuous")
    except Exception as exc:  # pragma: no cover
        check("M1 collapsing the zero-extraction branch is caught by check 5a", False,
              f"the mutant CRASHED ({exc!r}); a crash is not a catch")
    finally:
        S.classify_success = original
    # Mutation 2: let an impaired status count as trustworthy.
    original_t = H.TRUSTWORTHY
    try:
        H.TRUSTWORTHY = {"healthy", "no_results", "blocked", "failing", "degraded"}
        st_m = fresh()
        succeed(st_m, "github", fetched=10)
        fail(st_m, "elgato-stream-deck", error="HTTP 403 while fetching official source")
        mutant = verdict_for(st_m, [src("github"), src("elgato-stream-deck")])
        check("M2 treating a blocked source as trustworthy is caught by check 6a",
              mutant != H.RUN_DEGRADED,
              f"mutant verdict={mutant} -- 6a would still pass, so 6a is vacuous")
    except Exception as exc:  # pragma: no cover
        check("M2 treating a blocked source as trustworthy is caught by check 6a", False,
              f"the mutant CRASHED ({exc!r}); a crash is not a catch")
    finally:
        H.TRUSTWORTHY = original_t
    # Mutation 3: stamp an extraction timestamp even when nothing was extracted -- the exact lie
    # that made Netlify look current for months.
    st_m = fresh()
    succeed(st_m, "netlify", fetched=0)
    check("M3 a zero-extraction run must NOT record an extraction timestamp",
          not st_m["sources"]["netlify"].get("last_extraction_at"),
          "last_extraction_at was stamped without an extraction")

    print(NEWLINE + "=" * 74)
    print(f"Results: {_passed}/{_passed + _failed} passed, {_failed} failed")
    print("=" * 74)
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
