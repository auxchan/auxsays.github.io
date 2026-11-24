#!/usr/bin/env python3
"""Bounded automatic re-probe of switched-off acquisition methods.

WHAT IT DOES. A method that was switched off because its source refused automated requests used to
stay off until a person noticed the source had recovered. This step re-tests such a method on a
bounded cadence and records the answer. It runs before collection in the scheduled workflow; the
collector then reads the record through `lib.method_routing.effective_plan`.

WHAT IT MAY TOUCH. Only a method that a plan lists `disabled` or `probe_only`, that the registry's
policy allows to be re-probed (`lib.acquisition_methods.reprobe_refusal` == ''), that is not already
back in service, and whose cooldown has expired. Reddit, Microsoft Learn Q&A, Adobe and the paid
search API are refused by the policy floor before any declaration is read; nothing here can send
them a request.

BOUNDS, all hard:
  * per method: at most 2 requests (robots.txt, then one content request);
  * per run: at most `--max-requests` requests (default and ceiling:
    lib.method_routing.MAX_REPROBE_REQUESTS_PER_RUN) across at most MAX_REPROBE_METHODS_PER_RUN methods;
  * between probes of one method: the declared cooldown (a week at least), doubling after each
    refusal up to 30 days;
  * between requests: at least 1 second.

WHAT A PROBE IS NOT. It is not collection: no page content is stored, no evidence row is written, no
method row is changed. It reads robots.txt FIRST and stops if the source disallows the path. A
refusal is a property of the response, not of the status code: a challenge page or a page without
the expected marker is `still_refused` / `inconclusive`, even at HTTP 200. It never retries, never
changes headers to get past a refusal, and never follows a redirect to another host.

HOW A METHOD RETURNS. A `recovered` record lets the collector run the method again as a bounded
fallback. From then on the method's OWN fresh health rows decide: if they answer, it stays; if they
are all blocked, it is off again and the next probe waits out a longer cooldown.

Exit status is 0 unless the arguments are invalid: a probe that cannot run must never fail the
collection that follows it.

    python auxsays/scripts/reprobe_methods.py --dry-run     # say what is due; no request, no write
    python auxsays/scripts/reprobe_methods.py --write       # probe what is due and record it
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import acquisition_methods as registry  # noqa: E402
from lib import method_routing as routing  # noqa: E402
from lib.http import USER_AGENT, looks_like_challenge  # noqa: E402
from patch_collectors import base  # noqa: E402

# The token robots.txt rules are matched against. It is the product token of USER_AGENT.
ROBOTS_AGENT = "AUXSAYS-Patch-Ingest"
REQUEST_SPACING_SECONDS = 1.0
MAX_BODY_BYTES = 200_000
TIMEOUT_SECONDS = 20

# (status, headers, text). status 0 means no HTTP response at all.
Fetch = Callable[[str], tuple[int, dict[str, str], str]]


class _SameHostRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only within the host that was asked. Anything else is a refusal to answer
    the question that was put, and is reported as one."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        origin = urllib.parse.urlsplit(req.full_url)
        target = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        if target.scheme != "https" or target.netloc.lower() != origin.netloc.lower():
            raise urllib.error.HTTPError(req.full_url, code, "redirect_to_other_host", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def default_fetch(url: str) -> tuple[int, dict[str, str], str]:
    opener = urllib.request.build_opener(_SameHostRedirects())
    request = urllib.request.Request(url, method="GET", headers={
        "User-Agent": USER_AGENT, "Accept": "text/html,text/plain;q=0.9,*/*;q=0.5"})
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
    `spec['max_requests']` requests, robots.txt first."""
    budget = int(spec.get("max_requests") or 1)
    markers = [str(m) for m in (spec.get("refusal_markers") or [])]
    requests = 0
    outcome: dict[str, Any] = {"result": "inconclusive", "reason": "", "requests": 0, "http_status": 0}

    def finish(result: str, reason: str, status: int) -> dict[str, Any]:
        outcome.update(result=result, reason=reason, requests=requests, http_status=status)
        return outcome

    # 1. robots.txt: the source's own crawl rules are read before anything else is asked of it.
    requests += 1
    status, headers, text = fetch(str(spec["robots_url"]))
    if status in (404, 410):
        rules_text = ""                       # no robots.txt: nothing is disallowed
    else:
        refusal = _refused(status, headers, text, markers)
        if refusal:
            return finish("still_refused" if refusal != "network_error" else "inconclusive", refusal, status)
        if status != 200:
            return finish("inconclusive", f"robots_http_{status}", status)
        rules_text = text
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(rules_text.splitlines())
    if not parser.can_fetch(ROBOTS_AGENT, str(spec["url"])):
        return finish("still_refused", "robots_disallow", status)
    if requests >= budget:
        return finish("inconclusive", "request_cap_before_content", status)

    # 2. One content request: the page the method itself would read.
    sleep(REQUEST_SPACING_SECONDS)
    requests += 1
    status, headers, text = fetch(str(spec["url"]))
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
    spec = item["spec"]
    recovered = outcome["result"] == "recovered"
    refusals = 0 if recovered else int(item.get("consecutive_refusals") or 0) + 1
    cooldown = routing.probe_cooldown_hours(int(spec["cooldown_hours"]), max(1, refusals),
                                            registry.REPROBE_COOLDOWN_HOURS_MAX)
    return {
        "product_id": item["product_id"], "method_id": item["method_id"],
        "result": outcome["result"], "probed_at": routing.format_time(now),
        "next_probe_after": routing.format_time(now + timedelta(hours=cooldown)),
        "consecutive_refusals": refusals,
        "requests": int(outcome["requests"]),
        "total_requests": int(item.get("total_requests") or 0) + int(outcome["requests"]),
        "http_status": int(outcome.get("http_status") or 0),
        "reason": str(outcome.get("reason") or ""),
    }


def relapsed(product_id: str, method_id: str, rows: list[dict[str, Any]], probes: list[dict[str, Any]]) -> bool:
    """A method a probe returned to service whose own rows since have all failed."""
    probe = next((p for p in probes if p.get("product_id") == product_id and p.get("method_id") == method_id), None)
    return bool(probe and probe.get("result") == "recovered"
                and not routing.recovered_in_service(product_id, method_id, rows, probes))


def run(*, health_path: Path, now: datetime, write: bool, max_requests: int,
        fetch: Fetch | None = None, sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    # Resolved at CALL time, so a test that replaces `default_fetch` can never reach the network.
    fetch = fetch or default_fetch
    rows = base.load_method_health(health_path)
    probes = base.load_method_probes(health_path)
    cap = max(0, min(int(max_requests), routing.MAX_REPROBE_REQUESTS_PER_RUN))
    plan = routing.due_reprobes(rows, probes, now, reprobe_refusal=registry.reprobe_refusal,
                                reprobe_spec=registry.reprobe_spec, max_requests=cap)
    summary: dict[str, Any] = {"at": routing.format_time(now), "mode": "write" if write else "dry-run",
                               "request_cap": cap, "requests_made": 0, "probed": [], "skipped": []}
    records: list[dict[str, Any]] = []
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
        if relapsed(item["product_id"], item["method_id"], rows, probes):
            # It was returned to service and then refused real work: that counts as a refusal for
            # the back-off, so a flapping source is asked less often, not more.
            item["consecutive_refusals"] = max(1, int(item.get("consecutive_refusals") or 0))
        outcome = run_probe(item["spec"], fetch, sleep=sleep)
        summary["requests_made"] += int(outcome["requests"])
        record = probe_record(item, outcome, now)
        records.append(record)
        summary["probed"].append({**label, "result": record["result"], "reason": record["reason"],
                                  "requests": record["requests"],
                                  "next_probe_after": record["next_probe_after"]})
    if write and records:
        changed, _all = base.upsert_method_probes(records, health_path)
        summary["records_written"] = changed
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded re-probe of switched-off acquisition methods.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="List what is due. No request, no write.")
    mode.add_argument("--write", action="store_true", help="Probe what is due and record the result.")
    parser.add_argument("--health-path", type=Path, default=base.METHOD_HEALTH_PATH)
    parser.add_argument("--max-requests", type=int, default=routing.MAX_REPROBE_REQUESTS_PER_RUN)
    parser.add_argument("--now", help="ISO time to evaluate cooldowns at (default: the current time).")
    args = parser.parse_args(argv)
    now = routing.parse_time(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        parser.error("--now is not a timestamp")
    try:
        summary = run(health_path=args.health_path, now=now, write=bool(args.write),
                      max_requests=args.max_requests)
    except Exception as exc:  # noqa: BLE001 -- a probe step must never fail the collection after it
        print(json.dumps({"error": type(exc).__name__, "note": "re-probe skipped; collection continues"}))
        return 0
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
