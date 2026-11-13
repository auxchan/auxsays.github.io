"""Shadow operation of the verdict-reason producer: durable, bounded, public-safe diagnostics (AUX-099).

WHAT IT IS FOR. The producer (lib/verdict_reason_producer) runs at every deploy with its activation switch
OFF: its candidates and review-queue items are computed from stored structured evidence, written to the
git-ignored `_data/verdict_reason_candidates.yml`, and never reach a page, search metadata, accepted
evidence, maturity or live certification. Activation needs a class-level review of PROSPECTIVE, unseen
cases (AUTH_V2_38, activation criteria: at least 30 distinct positive candidates per class), and "repeated
shadow observations never count as independent validation". So the deploys must tell a candidate seen for
the FIRST time apart from the same candidate seen again: this module keeps that ledger.

STABLE IDENTITY. A candidate is keyed by `candidate_key` (class, exact page, verdict, scope, problem); a queue
item by `queue_key` (class, kind, exact page, problem). Neither changes when one more report arrives or the
wording moves, so the same candidate at the next deploy is a REPEAT appearance, never a new one.

ORIGINS, failing closed. The first deploy after this module ships records every current item as `baseline`:
those existed before shadow operation began, so none is prospective. A deploy that runs a different producer
version records the items it sees for the first time as `rules_change`: new rules re-reading old evidence
are not new cases. A ledger that cannot be restored (first run, cache evicted, unreadable) is re-established
as a new baseline and the deploy says so. Only an item first seen under an unchanged producer version
against a continuing ledger is `prospective`. Every way of losing track UNDER-counts prospective cases;
none can inflate them.

BOUNDED. At most MAX_ENTRIES items (inactive ones evicted oldest-first, baseline before prospective; the
running totals keep counting what was evicted) and the last MAX_DEPLOYS deploy summaries.

PUBLIC-SAFE (the repository is public; the ledger is an Actions cache entry and a run artifact, readable by
anyone who can read the repository). Stored per item: class, product id, version, build, verdict, scope,
severity basis, whether new, the number of reports, the KINDS of incident detail that separated them (never
their values), a closed-vocabulary problem label for install items (an error code, a named stage), the
public page path and, for a vendor item, the public record path and line of the vendor statement. Never a
report's title or text, a source URL, a row id, a reporter id or any analytics.

Pure: reads its arguments only (no file, network or clock); the deploy script supplies time and paths.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

SCHEMA_VERSION = 1
MAX_ENTRIES = 3000
MAX_DEPLOYS = 90
ORIGINS = ("baseline", "rules_change", "prospective")
# The only problem labels an item may carry: install characteristics from the producer's closed vocabulary.
_PROBLEM_LABEL_RE = re.compile(r"^(?:error 0x[0-9a-f]{3,8}|rolls back|stops at [0-9]{1,3}%|installer error D[WF][0-9]{3}|"
                               r"no shared characteristic|any install failure)$")
_CANDIDATE_FIELDS = ("class", "product_id", "update_version", "target_build", "verdict", "scope", "severity_basis",
                     "new_in_this_version", "reports", "independence_basis", "problem", "page", "source_record",
                     "source_line")
_QUEUE_FIELDS = ("class", "queue_kind", "product_id", "update_version", "target_build", "problem", "page")


def _s(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _problem(value: Any) -> str:
    text = _s(value)
    return text if _PROBLEM_LABEL_RE.match(text) else ""


def observation(artifact: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """The public-safe items one deploy's producer artifact holds, by stable key."""
    items: dict[str, dict[str, Any]] = {}
    for c in artifact.get("candidates") or []:
        key = _s(c.get("candidate_key"))
        if not key:
            continue
        producer = c.get("producer") or {}
        citation = c.get("citation") or {}
        item = {"kind": "candidate", "class": _s(producer.get("class")), "product_id": _s(c.get("product_id")),
                "update_version": _s(c.get("update_version")), "target_build": _s(c.get("target_build")),
                "verdict": _s(c.get("verdict")), "scope": _s(c.get("scope")),
                "severity_basis": _s(c.get("severity_basis")),
                "new_in_this_version": bool(c.get("new_in_this_version")),
                "reports": len(c.get("evidence") or []),
                "independence_basis": sorted(_s(k) for k in c.get("independence_basis") or []),
                "problem": _problem(c.get("problem_key")), "page": _s(c.get("page")),
                "source_record": _s(citation.get("record")), "source_line": citation.get("line") or 0}
        items["c:" + key] = {k: item[k] for k in ("kind",) + _CANDIDATE_FIELDS
                             if item[k] not in ("", None, [], 0) or k in ("new_in_this_version", "reports")}
    for q in artifact.get("review_queue") or []:
        key = _s(q.get("queue_key"))
        if not key:
            continue
        item = {"kind": "queue", "class": _s(q.get("class")), "queue_kind": _s(q.get("kind")),
                "product_id": _s(q.get("product_id")), "update_version": _s(q.get("update_version")),
                "target_build": _s(q.get("target_build")), "problem": _problem(q.get("problem_key")),
                "page": _s(q.get("page"))}
        items["q:" + key] = {k: item[k] for k in ("kind",) + _QUEUE_FIELDS if item[k] not in ("", None)}
    return dict(sorted(items.items()))


def new_ledger() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "producer_version": "", "baseline": {}, "resets": 0,
            "totals": {f"{origin}_{kind}": 0 for origin in ORIGINS for kind in ("candidate", "queue")}
            | {"evicted": 0}, "deploys": [], "entries": {}}


def ledger_problem(ledger: Any) -> str:
    """Why `ledger` cannot be continued, or ""."""
    if not isinstance(ledger, Mapping):
        return "no ledger"
    if ledger.get("schema_version") != SCHEMA_VERSION:
        return f"schema_version {ledger.get('schema_version')!r} is not {SCHEMA_VERSION}"
    if not isinstance(ledger.get("entries"), Mapping) or not isinstance(ledger.get("deploys"), list) \
            or not isinstance(ledger.get("totals"), Mapping):
        return "malformed ledger"
    return ""


def update(ledger: Any, artifact: Mapping[str, Any], *, deploy: str, commit: str, observed_at: str,
           ) -> tuple[dict[str, Any], dict[str, Any]]:
    """(the ledger after this deploy, this deploy's summary). Never raises on a bad ledger: it re-baselines."""
    seen = {"deploy": _s(deploy), "commit": _s(commit)[:40], "at": _s(observed_at)}
    version = _s(artifact.get("producer_version"))
    problem = ledger_problem(ledger)
    if problem:
        prior_resets = int((ledger or {}).get("resets") or 0) if isinstance(ledger, Mapping) else 0
        ledger, mode = new_ledger(), "baseline"
        ledger["resets"] = prior_resets + (0 if problem == "no ledger" else 1)
        ledger["baseline"] = dict(seen, producer_version=version, reason=problem)
    else:
        ledger = {k: (dict(v) if isinstance(v, Mapping) else list(v) if isinstance(v, list) else v)
                  for k, v in ledger.items()}
        ledger["entries"] = {k: dict(v) for k, v in ledger["entries"].items()}
        if ledger["deploys"] and ledger["deploys"][-1].get("deploy") == seen["deploy"]:
            return ledger, dict(ledger["deploys"][-1], mode="already_recorded")
        mode = "continuing" if _s(ledger.get("producer_version")) == version else "rules_change"
    summary: dict[str, Any] = dict(seen, producer_version=version, mode=mode)
    if artifact.get("error"):
        summary.update(producer_error=True, candidates=0, queue=0)
        ledger["deploys"] = (ledger["deploys"] + [summary])[-MAX_DEPLOYS:]
        return ledger, summary
    origin = {"baseline": "baseline", "rules_change": "rules_change", "continuing": "prospective"}[mode]
    current = observation(artifact)
    entries = ledger["entries"]
    first_seen: dict[str, list[str]] = {"candidate": [], "queue": []}
    repeats = {"candidate": 0, "queue": 0}
    for key, item in current.items():
        kind = item["kind"]
        if key in entries:
            entry = entries[key]
            entry.update({k: v for k, v in item.items() if k not in ("kind",)})
            entry["last_seen"] = dict(seen, producer_version=version)
            entry["appearances"] = int(entry.get("appearances") or 0) + 1
            entry["active"] = True
            repeats[kind] += 1
        else:
            entries[key] = dict(item, origin=origin, first_seen=dict(seen, producer_version=version),
                                last_seen=dict(seen, producer_version=version), appearances=1, active=True)
            ledger["totals"][f"{origin}_{kind}"] = int(ledger["totals"].get(f"{origin}_{kind}") or 0) + 1
            first_seen[kind].append(key)
    gone = 0
    for key, entry in entries.items():
        if key not in current and entry.get("active"):
            entry["active"] = False
            gone += 1
    ledger["entries"] = dict(sorted(_bounded(entries, ledger["totals"]).items()))
    ledger["producer_version"] = version
    summary.update(candidates=sum(1 for i in current.values() if i["kind"] == "candidate"),
                   queue=sum(1 for i in current.values() if i["kind"] == "queue"),
                   first_seen_candidates=len(first_seen["candidate"]), first_seen_queue=len(first_seen["queue"]),
                   first_seen_origin=origin, repeat_candidates=repeats["candidate"], repeat_queue=repeats["queue"],
                   no_longer_present=gone,
                   new_prospective_candidates=first_seen["candidate"] if origin == "prospective" else [],
                   new_prospective_queue=first_seen["queue"] if origin == "prospective" else [])
    ledger["deploys"] = (ledger["deploys"] + [{k: v for k, v in summary.items()
                                               if not k.startswith("new_prospective_")}])[-MAX_DEPLOYS:]
    return ledger, summary


def _bounded(entries: dict[str, dict[str, Any]], totals: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """At most MAX_ENTRIES: inactive entries go first, oldest last-seen first, baseline and rules-change ones
    before prospective ones. The totals keep counting them."""
    if len(entries) <= MAX_ENTRIES:
        return entries
    order = {"baseline": 0, "rules_change": 1, "prospective": 2}
    inactive = sorted((k for k, e in entries.items() if not e.get("active")),
                      key=lambda k: (order.get(entries[k].get("origin"), 0), _s((entries[k].get("last_seen") or {})
                                                                                 .get("at")), k))
    excess = len(entries) - MAX_ENTRIES
    for key in inactive[:excess]:
        del entries[key]
        totals["evicted"] = int(totals.get("evicted") or 0) + 1
    return entries


def unique_prospective(ledger: Mapping[str, Any], kind: str = "candidate", product_class: str = "") -> list[str]:
    """The keys of prospective items of `kind` (optionally one producer class) the ledger still holds."""
    return sorted(k for k, e in (ledger.get("entries") or {}).items()
                  if e.get("origin") == "prospective" and e.get("kind") == kind
                  and (not product_class or e.get("class") == product_class))


def render_summary(ledger: Mapping[str, Any], summary: Mapping[str, Any]) -> str:
    """The deploy's Markdown summary (the Actions step summary): counts and the identities of new
    prospective items -- page paths, verdicts and classes only."""
    totals = ledger.get("totals") or {}
    lines = ["## Verdict-reason producer: shadow diagnostics (activation OFF)", "",
             f"Deploy `{summary.get('deploy')}` at `{_s(summary.get('commit'))[:12]}`, producer version "
             f"{summary.get('producer_version')}, ledger mode **{summary.get('mode')}**.", ""]
    if summary.get("producer_error"):
        lines.append("The producer reported an error this deploy, so nothing was observed.")
        return "\n".join(lines) + "\n"
    if summary.get("mode") == "baseline":
        reason = (ledger.get("baseline") or {}).get("reason") or ""
        lines.append(f"No ledger was continued ({reason}): every item seen now is recorded as a baseline, so none of "
                     "them counts as prospective.")
    elif summary.get("mode") == "rules_change":
        lines.append("The producer's rules changed since the last deploy: items seen for the first time now are "
                     "recorded as a rules change, not as prospective cases.")
    lines += ["", "| | Candidates | Review queue |", "|---|---|---|",
              f"| Seen this deploy | {summary.get('candidates', 0)} | {summary.get('queue', 0)} |",
              f"| First seen this deploy ({summary.get('first_seen_origin', '')}) | "
              f"{summary.get('first_seen_candidates', 0)} | {summary.get('first_seen_queue', 0)} |",
              f"| Repeat appearances | {summary.get('repeat_candidates', 0)} | {summary.get('repeat_queue', 0)} |",
              f"| Unique prospective since shadow operation began | {totals.get('prospective_candidate', 0)} | "
              f"{totals.get('prospective_queue', 0)} |",
              f"| Distinct pages with a prospective candidate (still held) | {len(prospective_pages(ledger))} | |",
              ""]
    entries = ledger.get("entries") or {}
    new = list(summary.get("new_prospective_candidates") or []) + list(summary.get("new_prospective_queue") or [])
    if new:
        lines += ["New prospective items:", ""]
        for key in new:
            e = entries.get(key) or {}
            what = (f"{e.get('verdict', '')} {e.get('scope', '')}".strip() if e.get("kind") == "candidate"
                    else f"review queue: {e.get('queue_kind', '')}")
            lines.append(f"- `{e.get('class', '')}` {e.get('page', '')}: {what}")
    return "\n".join(lines) + "\n"


def prospective_pages(ledger: Mapping[str, Any], product_class: str = "") -> list[str]:
    """The DISTINCT pages with a prospective candidate the ledger still holds (optionally one producer class).
    An activation review counts these beside the keys: one page can carry two keys over time -- its install
    candidate is the problem with the most separate reports, so when another problem overtakes, the page's
    candidate changes problem and identity -- and two keys on one page are not two cases."""
    return sorted({_s(e.get("page")) for e in (ledger.get("entries") or {}).values()
                   if e.get("origin") == "prospective" and e.get("kind") == "candidate"
                   and (not product_class or e.get("class") == product_class)})


def class_counts(ledger: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    """Unique items per producer class and origin, and the distinct pages with a prospective one: what an
    activation review starts from."""
    out: dict[str, dict[str, int]] = {}
    for e in (ledger.get("entries") or {}).values():
        if e.get("kind") != "candidate":
            continue
        row = out.setdefault(_s(e.get("class")), {o: 0 for o in ORIGINS})
        row[_s(e.get("origin"))] = row.get(_s(e.get("origin")), 0) + 1
    for cls, row in out.items():
        row["prospective_pages"] = len(prospective_pages(ledger, cls))
    return dict(sorted(out.items()))
