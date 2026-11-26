#!/usr/bin/env python3
"""The PowerPoint open-web lane asks each question once a run and fetches each page once a run.

THE DEFECT. open_web_source.build_queries gives every record four questions of its own (its build,
its version) and then the SAME product-level questions ("PowerPoint after update site:...", "PowerPoint
crash after Office update", ...). The run cache was keyed on a record's WHOLE query list, which never
repeats, so all of it -- every search on both providers (a Stack Exchange search costs two calls, one
per site) and up to 120 page fetches -- was sent again for each of the 38 tracked records. On the
2026-11-25 10:26Z run that was roughly 38 x (8 searches + 16 Stack Exchange calls + 120 page fetches),
against a keyless Stack Exchange quota of about 300 a day, and 22 of 38 records -- the newest builds,
walked last -- stored `blocked: rate_limited`: the current releases were the ones never searched.

WHAT THIS SUITE PINS. Driving the REAL run_open_web_method and the REAL discover_urls across records of
one run, with the two providers and the page fetch stubbed (no network):
  D1  a (provider, query) pair is sent once a run, however many records ask it
  D2  a URL is fetched once a run, however many records' candidate lists hold it
  D3  every record's outcome -- discovered URLs in order, candidates, accepted, rejected, status,
      blocked_reason, counters -- equals the outcome of the same record run with an EMPTY cache (the
      behaviour before), in a clean scenario and in one with refusals
  D4  a refused search is not re-sent in the run, and its refusal is replayed into every record that
      asks it (so each record's health still says it was refused)
  D5  a refused page fetch is not retried in the run and is replayed the same way
  D6  reset_symptom_cache empties both caches: the next run asks again
  D7  the per-record request budget and the hydration cap are unchanged (16 provider slots, 120 pages)
  D8  the notes state what this record sent and what it reused; the counts add up to what was sent
  D9  on a run shaped like production (38 records, 22 versions; every record's own build and version
      questions return pages of their own) the sent requests fall by more than 60 percent, with the
      same outcome per record; the numbers are printed

Deterministic and offline. No file is written.
Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_powerpoint_open_web_request_dedup.py
"""
from __future__ import annotations

import hashlib
import socket
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

NET = [0]


class _NoNetSocket(socket.socket):
    def connect(self, *args, **kwargs):          # noqa: D102
        NET[0] += 1
        raise OSError("network refused by test_powerpoint_open_web_request_dedup")


def _no_dns(*args, **kwargs):
    NET[0] += 1
    raise OSError("DNS refused by test_powerpoint_open_web_request_dedup")


socket.socket = _NoNetSocket                     # type: ignore[misc]
socket.getaddrinfo = _no_dns                     # type: ignore[assignment]

from patch_collectors import microsoft_powerpoint as ppt                 # noqa: E402
from patch_collectors import open_web_source as ows                      # noqa: E402
from patch_collectors.base import CollectorContext, PatchRecord          # noqa: E402

CAPTURED = "2026-11-25T10:26:33Z"
CTX = CollectorContext(write=False, since="2026-09-01", max_pages=1, target_versions=None)
LEARN = "https://learn.microsoft.com/en-us/answers/questions/"
SU = "https://superuser.com/questions/"

PASS = FAIL = 0
FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


def _n(text: str, mod: int) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16) % mod


class Index:
    """Stubs both providers and the page fetch. A query's hits depend only on the query, so the same
    question gets the same answer, as one index does within a run; product-level questions share
    most of their pages."""

    def __init__(self, *, refuse_queries=(), refuse_pages=(), hits_per_query=24):
        self.refuse_queries = set(refuse_queries)
        self.refuse_pages = set(refuse_pages)
        self.hits = hits_per_query
        self.searches: dict[tuple[str, str], int] = {}
        self.pages: dict[str, int] = {}

    def _hits(self, provider: str, query: str) -> list[str]:
        base = LEARN if provider == "learn" else SU
        if '"' in query:                      # an identity question: a few pages of its own
            return [f"{base}{900000 + _n(query + str(i), 50000)}" for i in range(3)]
        return [f"{base}{100000 + _n(query[:18] + str(i), 400)}" for i in range(self.hits)]

    def learn(self, query: str) -> list[str]:
        ows._pace()
        self.searches[("learn_qna_search", query)] = self.searches.get(("learn_qna_search", query), 0) + 1
        if ("learn_qna_search", query) in self.refuse_queries:
            raise ows.OpenWebError("rate_limited", status=429)
        return self._hits("learn", query)

    def stack(self, query: str) -> list[str]:
        ows._pace()
        ows._pace()                           # two sites, two calls, as the real provider
        self.searches[("stack_exchange_search", query)] = self.searches.get(("stack_exchange_search", query), 0) + 1
        if ("stack_exchange_search", query) in self.refuse_queries:
            raise ows.OpenWebError("rate_limited", status=429)
        return self._hits("stack", query)

    def hydrate(self, row: dict) -> dict | None:
        url = row["source_url"]
        self.pages[url] = self.pages.get(url, 0) + 1
        if url in self.refuse_pages:
            raise ows.OpenWebError("rate_limited", status=429)
        if _n(url, 5) == 0:
            return None                        # a page that yields no candidate
        build = "19328.20000" if _n(url, 7) == 0 else ""
        return {"source_type": row["source_type"], "source_name": "stub", "source_url": url,
                "report_title": f"t {url[-6:]}", "report_text": f"PowerPoint crashes {build}".strip(),
                "source_date": "2026-10-20", "nested": {"tokens": [url[-6:]]}}

    def __enter__(self):
        self.saved = (ows.PROVIDERS, ows._MIN_REQUEST_INTERVAL, ppt.hydrate_discovered_url,
                      ppt.evaluate_candidates)
        ows.PROVIDERS = (("learn_qna_search", self.learn), ("stack_exchange_search", self.stack))
        ows._MIN_REQUEST_INTERVAL = 0.0

        def evaluate(record, target, candidates, captured_at, seen=None, run_accepted_urls=None):
            # Pure and record-dependent; it also MUTATES what it is given, as real gates may, so a
            # shared cached candidate would leak from one record into the next.
            acc, rej = [], []
            for c in candidates:
                c["nested"]["tokens"].append(record.target_build)
                (acc if record.target_build in c["report_text"] else rej).append(
                    dict(c, exclusion_reason=None if record.target_build in c["report_text"]
                         else "missing_exact_build"))
            return acc, rej
        ppt.hydrate_discovered_url = self.hydrate
        ppt.evaluate_candidates = evaluate
        ppt.reset_symptom_cache()
        return self

    def __exit__(self, *exc):
        ows.PROVIDERS, ows._MIN_REQUEST_INTERVAL, ppt.hydrate_discovered_url, ppt.evaluate_candidates = self.saved
        ppt.reset_symptom_cache()
        return False


def records(count: int, versions: int) -> list[tuple[PatchRecord, dict]]:
    out = []
    for i in range(count):
        version = str(2501 + (i * versions // count))
        build = "19328.20000" if i == count - 1 else f"{17000 + i}.{20100 + i}"
        record = PatchRecord(product_id="microsoft-powerpoint", update_version=version, path=Path("x.md"),
                             update_published_at="2026-01-01T00:00:00Z", update_status="current",
                             update_product="PowerPoint", target_build=build)
        out.append((record, {"update_version": version, "target_build": build}))
    return out


SENT_NOTE = "Sent this record:"


def comparable(result) -> dict:
    accepted, rejected, row = result
    notes = row.get("notes", "")
    cut = notes.find(SENT_NOTE)
    notes_without = notes[:cut] if cut >= 0 else notes
    return {"row": {k: v for k, v in row.items() if k != "notes"}, "notes": notes_without,
            "accepted": [(c["source_url"], c.get("exclusion_reason")) for c in accepted],
            "rejected": [(c["source_url"], c.get("exclusion_reason")) for c in rejected]}


def run_shared(recs, **kw):
    with Index(**kw) as index:
        results = [ppt.run_open_web_method(r, t, CTX, set(), {}, CAPTURED) for r, t in recs]
    return results, index, calls(index)


def run_fresh(recs, **kw):
    """The behaviour before: every record starts from an empty cache."""
    with Index(**kw) as index:
        results = []
        for r, t in recs:
            ppt.reset_symptom_cache()
            results.append(ppt.run_open_web_method(r, t, CTX, set(), {}, CAPTURED))
    return results, index, calls(index)


def calls(index: "Index") -> int:
    """Network calls the stubs received: a Stack Exchange search is two (one per site)."""
    return sum(v * (2 if p == "stack_exchange_search" else 1) for (p, _q), v in index.searches.items())


def run() -> int:
    net0 = NET[0]
    recs = records(12, 5)

    print("D1/D2  one search per question, one fetch per page, per run")
    shared, idx, _ = run_shared(recs)
    check("D1.1 no (provider, query) pair is sent twice in a run",
          max(idx.searches.values(), default=0) == 1, str(sorted(idx.searches.items(), key=lambda x: -x[1])[:3]))
    product_q = [q for (_p, q) in idx.searches if '"' not in q]
    check("D1.2 the product-level questions were asked (the scenario exercises sharing)", len(product_q) >= 4)
    check("D2.1 no URL is fetched twice in a run", max(idx.pages.values(), default=0) == 1,
          str(sorted(idx.pages.items(), key=lambda x: -x[1])[:3]))
    fresh, fidx, _ = run_fresh(recs)
    check("D2.2 the scenario has pages shared across records (the old path fetched them repeatedly)",
          max(fidx.pages.values(), default=0) >= len(recs) // 2)

    print("D3  each record's outcome is the one an empty cache gives")
    check("D3.1 clean run: every record identical to its fresh-cache run",
          [comparable(a) for a in shared] == [comparable(b) for b in fresh])
    check("D3.2 the scenario accepts something and rejects something",
          any(r[0] for r in shared) and any(r[1] for r in shared))
    check("D3.3 a cached candidate is handed out as a copy: a gate that mutates it cannot reach the next record",
          all(len(c["nested"]["tokens"]) == 2 for res in shared for c in res[0] + res[1]),
          str([c["nested"]["tokens"] for res in shared[:2] for c in res[1][:1]]))

    print("D4/D5  refusals: not re-sent, replayed into each record")
    a_product_query = sorted(product_q)[0]
    first_url = shared[0][2]["candidates_found"] and sorted(idx.pages)[0]
    kw = {"refuse_queries": {("stack_exchange_search", a_product_query)}, "refuse_pages": {first_url}}
    shared_r, idx_r, _ = run_shared(recs, **kw)
    fresh_r, _fidx_r, _ = run_fresh(recs, **kw)
    check("D4.1 the refused search was sent once in the run",
          idx_r.searches.get(("stack_exchange_search", a_product_query)) == 1)
    asked = [res for res in shared_r if "rate_limited" in str(res[2].get("blocked_reason") or "")
             or res[2].get("status") in ("partial", "blocked", "broken")]
    check("D4.2 every record that asked it still reports the refusal (status / reason as with an empty cache)",
          [comparable(a) for a in shared_r] == [comparable(b) for b in fresh_r]
          and len(asked) == len(recs), str([r[2].get("status") for r in shared_r]))
    check("D5.1 the refused page was fetched once in the run", idx_r.pages.get(first_url) == 1)

    print("D6  a new run asks again")
    with Index() as index:
        r, t = recs[0]
        ppt.run_open_web_method(r, t, CTX, set(), {}, CAPTURED)
        first = dict(index.searches)
        ppt.run_open_web_method(r, t, CTX, set(), {}, CAPTURED)
        same_run = dict(index.searches)
        ppt.reset_symptom_cache()
        ppt.run_open_web_method(r, t, CTX, set(), {}, CAPTURED)
        check("D6.1 within a run the second call sends nothing", same_run == first)
        check("D6.2 after reset_symptom_cache every question is asked again",
              all(index.searches[k] == 2 for k in first))
        check("D6.3 and every page is fetched again", all(v == 2 for v in index.pages.values()))

    print("D7  budgets unchanged")
    check("D7.1 OPEN_WEB_MAX_REQUESTS is 16 and OPEN_WEB_MAX_HYDRATIONS 120",
          ppt.OPEN_WEB_MAX_REQUESTS == 16 and ppt.OPEN_WEB_MAX_HYDRATIONS == 120)
    with Index(hits_per_query=60) as index:
        r, t = recs[0]
        _a, _r, row = ppt.run_open_web_method(r, t, CTX, set(), {}, CAPTURED)
        check("D7.2 a record hydrates at most 120 pages", len(index.pages) == 120, str(len(index.pages)))
        check("D7.3 a record uses at most 16 provider slots",
              sum(index.searches.values()) == 16, str(sum(index.searches.values())))

    print("D8  the notes say what was sent and what was reused")
    sent_notes = [res[2]["notes"] for res in shared]
    check("D8.1 every record's notes carry the sent/reused sentence", all(SENT_NOTE in n for n in sent_notes))
    import re
    found = [re.search(
        r"Sent this record: (\d+) searches and (\d+) page fetches; reused from earlier records this run: "
        r"(\d+) searches and (\d+) pages", n) for n in sent_notes]
    nums = [tuple(int(x) for x in m.groups()) if m else (-1, -1, -1, -1) for m in found]
    check("D8.2 the searches the notes say were sent add up to the calls made",
          sum(x[0] for x in nums) == calls(idx),
          str((sum(x[0] for x in nums), idx.searches)))
    check("D8.3 the page fetches the notes say were sent add up to the fetches made",
          sum(x[1] for x in nums) == sum(idx.pages.values()))
    check("D8.4 later records reuse", nums[-1][2] > 0 and nums[-1][3] > 0, str(nums[-1]))

    print("D9  a production-shaped run (38 records, 22 versions)")
    big = records(38, 22)
    _s, sidx, sent_after = run_shared(big)
    _f, fidx2, sent_before = run_fresh(big)
    before = sent_before + sum(fidx2.pages.values())
    after = sent_after + sum(sidx.pages.values())
    print(f"        before: {sent_before} search calls + {sum(fidx2.pages.values())} page fetches = {before}")
    print(f"        after:  {sent_after} search calls + {sum(sidx.pages.values())} page fetches = {after}")
    check("D9.1 sent requests fall by more than 60 percent", after * 5 < before * 2, f"{after} vs {before}")
    check("D9.2 the same outcome per record", [comparable(a) for a in _s] == [comparable(b) for b in _f])

    check("NET no socket was opened", NET[0] == net0, str(NET[0] - net0))
    print(f"\nResults: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("FAILED: " + ", ".join(FAILURES))
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
