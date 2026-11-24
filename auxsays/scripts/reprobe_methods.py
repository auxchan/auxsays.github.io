#!/usr/bin/env python3
"""Bounded automatic re-probe of switched-off acquisition methods.

WHAT IT DOES. A method that was switched off because its source refused automated requests used to
stay off until a person noticed the source had recovered. This step re-tests such a method on a
bounded cadence and records the answer. It runs before collection in the scheduled workflow; the
collector then reads the record through `lib.method_routing.effective_plan`.

WHAT IT MAY TOUCH. Only a method that a plan lists `disabled` or `probe_only`, that the registry's
policy allows to be re-probed (`lib.acquisition_methods.reprobe_refusal` == ''), that is not already
back in service, and whose cooldown has expired. Reddit, Microsoft Learn Q&A, Adobe and the paid
search API are refused by the policy floor before any declaration is read, and a probe may only be
sent to the one host the registry pins for its method; nothing here can send another host a request.

BOUNDS, all hard:
  * per method: at most 2 requests (robots.txt, then one content request);
  * per run: at most `--max-requests` requests (default and ceiling:
    lib.method_routing.MAX_REPROBE_REQUESTS_PER_RUN) across at most MAX_REPROBE_METHODS_PER_RUN methods;
  * between probes of one method: the declared cooldown (a week at least), doubling after each
    refusal AND each relapse up to 30 days; the cooldown is written BEFORE the first request, so a
    step that dies mid-probe has still paid for it;
  * between requests: at least 1 second, or the source's Crawl-delay when that is longer.

WHAT A PROBE IS. The request the method itself makes, with the user agent the method itself sends.
robots.txt is read FIRST, for that agent and for one URL of every shape the method requests, and
the probe stops there if any is disallowed or the file is not a robots file. A refusal is a
property of the response, not of the status code: a challenge page or a page without the expected
marker is `still_refused` / `inconclusive`, even at HTTP 200. It never retries, never changes
headers to get past a refusal, and never follows a redirect to another host. It is not collection:
no page content is stored, no evidence row is written, no method row is changed.

HOW A METHOD RETURNS, AND LEAVES. This step is the ONLY writer of probe records. A `recovered`
record does not switch the method on for good: every run, this step first SETTLES the run it last
granted (from the method's own health rows) and then GRANTS the coming run a request budget from
the registry's declared ramp (6, 12, 20, then 30 requests for the Blackmagic forum). The collector
serves the method only under a fresh grant and only within that budget.
  * the granted run answered            -> the ramp advances;
  * the granted run was refused         -> RELAPSE: the record becomes `relapsed`, the cooldown
                                           restarts with a longer back-off, and only a NEW probe can
                                           return the method (the old one is spent);
  * the granted run left no row at all  -> unsettled (a lost cycle); tolerated once, then the
                                           recovery is withdrawn.

SURVIVING A LOST CYCLE. The records reach main with the job's ordinary writeback. A cycle whose
writeback does not push would lose them, and the next run would probe again. `--carry-path` names a
small JSON copy of the probe records that the workflow restores before this step and saves after
it (actions/cache); on start the newer copy of each record wins, so a cooldown or a grant survives
a cycle that never reached main. A carried record for a policy-closed method is ignored.

FAILING VISIBLY. If the step itself fails it prints a `::error` annotation, writes a block to the
run summary, records `probe_step: {status: error ...}` in the health file and exits 1. The workflow
step is `continue-on-error`, so collection still runs; the failure is no longer a green step.

    python auxsays/scripts/reprobe_methods.py --dry-run     # say what is due; no request, no write
    python auxsays/scripts/reprobe_methods.py --write       # settle, grant, probe what is due, record
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import acquisition_methods as registry  # noqa: E402
from lib import method_routing as routing  # noqa: E402
from lib.http import USER_AGENT, looks_like_challenge  # noqa: E402
from patch_collectors import base  # noqa: E402

# Fallbacks for a declaration without a service block. No such declaration can be probed
# (registry.reprobe_refusal: service_bounds_missing); they exist so run_probe never reads a missing key.
ROBOTS_AGENT = "AUXSAYS-Patch-Ingest"
REQUEST_SPACING_SECONDS = 1.0
MAX_CRAWL_DELAY_SECONDS = 30.0
MAX_BODY_BYTES = 200_000
TIMEOUT_SECONDS = 20
CARRY_SCHEMA = 1

# (url, user_agent) -> (status, headers, text). status 0 means no HTTP response at all.
Fetch = Callable[[str, str], tuple[int, dict[str, str], str]]


class _SameHostRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only within the host that was asked. Anything else is a refusal to answer
    the question that was put, and is reported as one."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        origin = urllib.parse.urlsplit(req.full_url)
        target = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        if target.scheme != "https" or target.netloc.lower() != origin.netloc.lower():
            raise urllib.error.HTTPError(req.full_url, code, "redirect_to_other_host", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def default_fetch(url: str, user_agent: str = USER_AGENT) -> tuple[int, dict[str, str], str]:
    opener = urllib.request.build_opener(_SameHostRedirects())
    request = urllib.request.Request(url, method="GET", headers={
        "User-Agent": user_agent or USER_AGENT, "Accept": "text/html,text/plain;q=0.9,*/*;q=0.5"})
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_BODY_BYTES)
            return (int(getattr(response, "status", 200)), dict(response.headers.items()),
                    raw.decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(8000).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            body = ""
        return int(exc.code), dict((exc.headers or {}).items()), body
    except Exception:  # noqa: BLE001 -- DNS, TLS, timeout: no HTTP answer
        return 0, {}, ""


def _refused(status: int, headers: dict[str, str], text: str, markers: list[str]) -> str:
    """A bounded machine reason when the response is a refusal, else ''."""
    if status == 0:
        return "network_error"
    lowered = (text or "")[:8192].lower()
    if any(marker.lower() in lowered for marker in markers) or looks_like_challenge(text, headers):
        return "access_challenge"
    if status in (401, 403, 405, 407, 429, 451) or status >= 500:
        return f"http_{status}"
    return ""


def run_probe(spec: dict[str, Any], fetch: Fetch, *, sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """Probe one method. Returns {result, reason, requests, http_status}. At most
    `spec['max_requests']` requests, robots.txt first, every one to the method's pinned host and
    with the user agent the method itself sends."""
    budget = int(spec.get("max_requests") or 1)
    markers = [str(m) for m in (spec.get("refusal_markers") or [])]
    service = spec.get("service") if isinstance(spec.get("service"), dict) else {}
    agent = str(service.get("user_agent") or USER_AGENT)
    token = str(service.get("robots_agent") or ROBOTS_AGENT)
    asked = [str(spec["url"])] + [str(u) for u in (service.get("robots_sample_urls") or [])]
    requests = 0
    outcome: dict[str, Any] = {"result": "inconclusive", "reason": "", "requests": 0, "http_status": 0}

    def finish(result: str, reason: str, status: int) -> dict[str, Any]:
        outcome.update(result=result, reason=reason, requests=requests, http_status=status)
        return outcome

    # 0. The destination is the pinned host or nothing is sent at all.
    pin = str(spec.get("host") or "")
    if not pin or any(registry.probe_host(u) != pin for u in [str(spec["robots_url"]), *asked]):
        return finish("inconclusive", "host_not_pinned", 0)

    # 1. robots.txt: the source's own crawl rules are read before anything else is asked of it,
    #    for the agent the method sends and for every URL shape it requests.
    requests += 1
    status, headers, text = fetch(str(spec["robots_url"]), agent)
    if status in (404, 410):
        robots = routing.parse_robots("", token)          # no robots.txt: nothing is disallowed
    else:
        refusal = _refused(status, headers, text, markers)
        if refusal:
            return finish("still_refused" if refusal != "network_error" else "inconclusive", refusal, status)
        if status != 200:
            return finish("inconclusive", f"robots_http_{status}", status)
        robots = routing.parse_robots(text, token)
        if not robots["readable"]:
            # An HTML page served as robots.txt is not "nothing is disallowed".
            return finish("inconclusive", "robots_not_a_robots_file", status)
    if not all(routing.robots_allows(robots, url) for url in asked):
        return finish("still_refused", "robots_disallow", status)
    delay = max(REQUEST_SPACING_SECONDS, float(robots.get("crawl_delay") or 0.0))
    if delay > MAX_CRAWL_DELAY_SECONDS:
        return finish("inconclusive", "crawl_delay_too_long", status)
    if requests >= budget:
        return finish("inconclusive", "request_cap_before_content", status)

    # 2. One content request: the request the method itself makes.
    sleep(delay)
    requests += 1
    status, headers, text = fetch(str(spec["url"]), agent)
    refusal = _refused(status, headers, text, markers)
    if refusal:
        return finish("still_refused" if refusal != "network_error" else "inconclusive", refusal, status)
    if status != 200:
        return finish("inconclusive", f"http_{status}", status)
    if not any(str(marker) in text for marker in (spec.get("expect_any") or [])):
        # Answered, but not with the page the method needs: a login wall, an empty shell, a
        # redesign. Not a recovery -- the method could not work against this.
        return finish("inconclusive", "expected_marker_missing", status)
    return finish("recovered", "content_answered", status)


def probe_record(item: dict[str, Any], outcome: dict[str, Any], now: datetime) -> dict[str, Any]:
    """The record of one probe, computed from the record that was there BEFORE it (`item['prior']`).

    A refused probe adds to `consecutive_refusals`; an answered one resets that to 0 but KEEPS
    `relapses`, and the cooldown counts both, so a source whose probe answers and whose real run is
    then refused is asked less each time. An answered probe also grants the first service run at
    the bottom of the declared ramp."""
    spec = item["spec"]
    prior = item.get("prior") or {}
    recovered = outcome["result"] == "recovered"
    refusals = 0 if recovered else int(prior.get("consecutive_refusals") or 0) + 1
    relapses = int(prior.get("relapses") or 0)
    cooldown = routing.probe_cooldown_hours(int(spec["cooldown_hours"]), max(1, refusals + relapses),
                                            registry.REPROBE_COOLDOWN_HOURS_MAX)
    stamp = routing.format_time(now)
    record = {
        "product_id": item["product_id"], "method_id": item["method_id"],
        "result": outcome["result"], "probed_at": stamp,
        "next_probe_after": routing.format_time(now + timedelta(hours=cooldown)),
        "consecutive_refusals": refusals, "relapses": relapses,
        "requests": int(outcome["requests"]),
        "total_requests": int(prior.get("total_requests") or 0) + int(outcome["requests"]),
        "http_status": int(outcome.get("http_status") or 0),
        "reason": str(outcome.get("reason") or ""),
        "service_runs": 0, "unsettled_runs": 0, "granted_at": "", "grant_requests": 0,
        "state_at": stamp,
    }
    if recovered:
        record["granted_at"] = stamp
        record["grant_requests"] = routing.service_budget(spec.get("service") or {}, 0)
    return record


# --- the carried copy ----------------------------------------------------------------------------
def read_carry(path: Path | None) -> list[dict[str, Any]]:
    """The probe records an earlier run carried, or [] (no file, unreadable, wrong shape)."""
    if path is None:
        return []
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 -- a missing or damaged carry is simply no carry
        return []
    if not isinstance(payload, dict) or payload.get("schema") != CARRY_SCHEMA:
        return []
    probes = payload.get("probes")
    return [p for p in probes if isinstance(p, dict)] if isinstance(probes, list) else []


def merge_carry(probes: list[dict[str, Any]], carried: list[dict[str, Any]], now: datetime
                ) -> tuple[list[dict[str, Any]], int]:
    """Per (product, method) the NEWER record wins (by `state_at`, else `probed_at`). A carried
    record is ignored when its method may not be re-probed, when it is not about a method a plan
    switched off, or when it is dated in the future: a carry can remember, it cannot open a door."""
    merged = {base.method_probe_key(p): p for p in probes}
    horizon = now + timedelta(minutes=10)
    ceiling = now + timedelta(hours=registry.REPROBE_COOLDOWN_HOURS_MAX, minutes=10)
    switched_off = {(pid, mid) for pid in routing.METHOD_PLANS
                    for mid in routing.plan_methods(pid)["disabled"] + routing.plan_methods(pid)["probe_only"]}
    adopted = 0

    def stamp(record: dict[str, Any]) -> datetime | None:
        return routing.parse_time(record.get("state_at")) or routing.parse_time(record.get("probed_at"))

    for raw in carried:
        record = base.normalize_method_probe_row(raw)
        key = base.method_probe_key(record)
        if not all(key) or key not in switched_off or registry.reprobe_refusal(key[1]):
            continue
        when = stamp(record)
        after = routing.parse_time(record.get("next_probe_after"))
        if when is None or when > horizon or (after is not None and after > ceiling):
            continue
        current = merged.get(key)
        if current is None or (stamp(current) or datetime.min.replace(tzinfo=timezone.utc)) < when:
            merged[key] = record
            adopted += 1
    return list(merged.values()), adopted


def write_carry(path: Path | None, probes: list[dict[str, Any]], now: datetime) -> bool:
    """Write the carried copy. Returns True when its records differ from the file already there."""
    if path is None:
        return False
    records = sorted((base.normalize_method_probe_row(p) for p in probes), key=base.method_probe_key)
    before = sorted((base.normalize_method_probe_row(p) for p in read_carry(path)), key=base.method_probe_key)
    if records == before and Path(path).exists():
        return False
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({"schema": CARRY_SCHEMA, "written_at": routing.format_time(now),
                                      "probes": records}, indent=2) + "\n", encoding="utf-8")
    return True


def run(*, health_path: Path, now: datetime, write: bool, max_requests: int,
        fetch: Fetch | None = None, sleep: Callable[[float], None] = time.sleep,
        carry_path: Path | None = None) -> dict[str, Any]:
    # Resolved at CALL time, so a test that replaces `default_fetch` can never reach the network.
    fetch = fetch or default_fetch
    rows = base.load_method_health(health_path)
    stored = base.load_method_probes(health_path)
    probes, adopted = merge_carry(stored, read_carry(carry_path), now)
    cap = max(0, min(int(max_requests), routing.MAX_REPROBE_REQUESTS_PER_RUN))
    summary: dict[str, Any] = {"at": routing.format_time(now), "mode": "write" if write else "dry-run",
                               "request_cap": cap, "requests_made": 0, "probed": [], "skipped": [],
                               "service": [], "carried_records_adopted": adopted, "records_written": 0}

    def store(records: list[dict[str, Any]]) -> None:
        if write and records:
            changed, _all = base.upsert_method_probes(records, health_path)
            summary["records_written"] += changed

    # A record the carry remembered and main never received is written back first.
    if adopted:
        store(probes)

    # 1. SETTLE the run each `recovered` record last granted, then GRANT this run (or relapse).
    settled: list[dict[str, Any]] = []
    for index, probe in enumerate(probes):
        if probe.get("result") != "recovered":
            continue
        spec = registry.reprobe_spec(str(probe.get("method_id") or ""))
        if spec is None:
            continue                       # policy closed it since: it is never granted again
        record, event = routing.advance_service(
            probe, rows, now, service=spec["service"], cooldown_hours=int(spec["cooldown_hours"]),
            max_cooldown_hours=registry.REPROBE_COOLDOWN_HOURS_MAX)
        summary["service"].append({
            "product_id": record["product_id"], "method_id": record["method_id"], "event": event,
            "result": record["result"], "grant_requests": int(record.get("grant_requests") or 0),
            "service_runs": int(record.get("service_runs") or 0),
            "relapses": int(record.get("relapses") or 0),
            "next_probe_after": record.get("next_probe_after", "")})
        if write:
            probes[index] = record
            settled.append(record)
    store(settled)

    # 2. PROBE what is due.
    plan = routing.due_reprobes(rows, probes, now, reprobe_refusal=registry.reprobe_refusal,
                                reprobe_spec=registry.reprobe_spec, max_requests=cap)
    for item in plan:
        label = {"product_id": item["product_id"], "method_id": item["method_id"]}
        if not item.get("due"):
            summary["skipped"].append({**label, "reason": item.get("skip", "")})
            continue
        if not write:
            summary["probed"].append({**label, "result": "would_probe",
                                      "max_requests": int(item["spec"]["max_requests"])})
            continue
        if item["spec"]["max_requests"] > cap - summary["requests_made"]:
            summary["skipped"].append({**label, "reason": "run_cap"})
            continue
        if summary["requests_made"]:
            sleep(REQUEST_SPACING_SECONDS)
        # PAID BEFORE IT IS SENT. The cooldown is on file before the first request, so a step that
        # dies between the request and the write below cannot probe again next run.
        store([probe_record(item, {"result": "inconclusive", "reason": "probe_started",
                                   "requests": 0}, now)])
        outcome = run_probe(item["spec"], fetch, sleep=sleep)
        summary["requests_made"] += int(outcome["requests"])
        record = probe_record(item, outcome, now)
        store([record])
        summary["probed"].append({**label, "result": record["result"], "reason": record["reason"],
                                  "requests": record["requests"],
                                  "grant_requests": int(record.get("grant_requests") or 0),
                                  "next_probe_after": record["next_probe_after"]})
    if write:
        summary["carry_changed"] = write_carry(carry_path, base.load_method_probes(health_path), now)
    return summary


# --- being seen ----------------------------------------------------------------------------------
def summary_lines(summary: dict[str, Any] | None, error: str = "") -> list[str]:
    lines = ["### Re-probe of switched-off sources", ""]
    if error:
        lines.append(f"- status: **FAILED** (`{error}`). No probe result was recorded by this step; "
                     "collection continued. The failure is also in `probe_step` of evidence_method_health.yml.")
        return lines
    summary = summary or {}
    lines.append(f"- status: **ok** ({summary.get('mode')}); requests made: "
                 f"**{summary.get('requests_made', 0)}** of a cap of {summary.get('request_cap', 0)}")
    for probe in summary.get("probed") or []:
        lines.append(f"- probed `{probe['product_id']}` / `{probe['method_id']}`: **{probe['result']}**"
                     f" ({probe.get('reason', '')}); next probe after {probe.get('next_probe_after', 'n/a')}")
    for service in summary.get("service") or []:
        lines.append(f"- returned method `{service['product_id']}` / `{service['method_id']}`: "
                     f"**{service['event']}**; budget this run: {service['grant_requests']} requests; "
                     f"answered runs: {service['service_runs']}; relapses: {service['relapses']}")
    skipped = summary.get("skipped") or []
    waiting = [s for s in skipped if s.get("reason") in ("cooldown", "in_service", "run_cap")]
    lines.append(f"- not probed: {len(skipped)} switched-off methods "
                 f"({len(skipped) - len(waiting)} closed by policy, {len(waiting)} waiting)")
    if summary.get("carried_records_adopted"):
        lines.append(f"- records restored from the carried copy (an earlier cycle did not reach main): "
                     f"{summary['carried_records_adopted']}")
    return lines


def _emit(summary: dict[str, Any] | None, error: str = "") -> None:
    """Run summary and step outputs. Never raises: reporting must not mask what it reports."""
    try:
        target = os.environ.get("GITHUB_STEP_SUMMARY")
        if target:
            with open(target, "a", encoding="utf-8") as handle:
                handle.write("\n".join(summary_lines(summary, error)) + "\n\n")
        target = os.environ.get("GITHUB_OUTPUT")
        if target:
            with open(target, "a", encoding="utf-8") as handle:
                handle.write(f"status={'error' if error else 'ok'}\n")
                handle.write(f"carry_changed={'true' if (summary or {}).get('carry_changed') else 'false'}\n")
                handle.write(f"requests_made={int((summary or {}).get('requests_made') or 0)}\n")
    except Exception:  # noqa: BLE001
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded re-probe of switched-off acquisition methods.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="List what is due. No request, no write.")
    mode.add_argument("--write", action="store_true", help="Settle, grant, probe what is due and record it.")
    parser.add_argument("--health-path", type=Path, default=base.METHOD_HEALTH_PATH)
    parser.add_argument("--max-requests", type=int, default=routing.MAX_REPROBE_REQUESTS_PER_RUN)
    parser.add_argument("--now", help="ISO time to evaluate cooldowns at (default: the current time).")
    parser.add_argument("--carry-path", type=Path, default=None,
                        help="JSON copy of the probe records that survives a cycle which never reached main.")
    args = parser.parse_args(argv)
    now = routing.parse_time(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        parser.error("--now is not a timestamp")
    try:
        summary = run(health_path=args.health_path, now=now, write=bool(args.write),
                      max_requests=args.max_requests, carry_path=args.carry_path)
        if args.write:
            base.record_probe_step(args.health_path)          # a clean run clears an earlier failure
    except Exception as exc:  # noqa: BLE001 -- reported three ways below; collection continues
        name = type(exc).__name__
        traceback.print_exc()
        detail = " ".join(str(exc).split())[:200]
        print(f"::error title=Re-probe step failed::{name}: {detail}")
        print(json.dumps({"error": name, "note": "re-probe FAILED; the step exits 1 and collection continues"}))
        if args.write:
            try:
                base.record_probe_step(args.health_path, error=name, at=routing.format_time(now))
            except Exception:  # noqa: BLE001 -- the health file may be what failed
                print("::warning title=Re-probe step::the failure could not be recorded in the health file")
            try:
                # What was paid for before the failure (a cooldown, a grant) is still carried.
                summary = {"carry_changed": write_carry(args.carry_path,
                                                        base.load_method_probes(args.health_path), now)}
            except Exception:  # noqa: BLE001
                summary = None
        else:
            summary = None
        _emit(summary, error=name)
        return 1
    print(json.dumps(summary, indent=2))
    _emit(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
