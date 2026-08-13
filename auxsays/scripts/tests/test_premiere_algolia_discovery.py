#!/usr/bin/env python3
"""Deterministic OFFLINE tests for Premiere's Adobe Community (Algolia + getTopics) discovery.

No network: both public JSON transports are stubbed, so every assertion is reproducible and the
suite can never depend on live corpus state. Covers index pinning, board scoping, bounded
discovery accounting, truncation semantics, health precedence, the candidate contract and the
runtime/transport invariants.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_premiere_algolia_discovery.py
"""
from __future__ import annotations

import json
import sys
import traceback
import urllib.parse
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from patch_collectors import adobe_premiere as pp  # noqa: E402
from patch_collectors.base import CollectorContext, PatchRecord  # noqa: E402

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


def record(version: str = "26.2") -> PatchRecord:
    return PatchRecord(product_id=pp.PRODUCT_ID, update_version=version, path=Path("x.md"),
                       update_published_at="2026-04-16T00:00:00Z", update_status="released",
                       update_product="Adobe Premiere Pro")


def topic(topic_id: int, *, title="Premiere Pro 26.2 export crash on render",
          body="Premiere Pro 26.2 crashes every time I export a timeline.",
          date="2026-07-20T10:00:00+0000", board="bug-reports-728") -> dict:
    return {"id": topic_id, "title": title,
            "url": f"https://community.adobe.com/{board}/slug-{topic_id}",
            "firstPost": {"content": body, "creationDate": date}}


class Stub:
    """Records every HTTP call the collector makes."""

    def __init__(self, *, indexes=("adobedme-en-unified",), hits_pages=None, topics_by_id=None,
                 token_payload=None, topics_payload=None):
        self.indexes = indexes
        self.hits_pages = hits_pages if hits_pages is not None else [[]]
        self.topics_by_id = topics_by_id or {}
        self.token_payload = token_payload
        self.topics_payload = topics_payload
        self.token_calls = 0
        self.post_calls: list[dict] = []
        self.get_topics_calls: list[list[str]] = []

    def get(self, url, *a, **k):
        if url.startswith(pp.ALGOLIA_TOKEN_URL):
            self.token_calls += 1
            if self.token_payload is not None:
                return self.token_payload
            return {"client_id": "APPID", "token": "SECRET", "availableIndexes": list(self.indexes)}
        if url.startswith(pp.COMMUNITY_GET_TOPICS_URL):
            ids = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("topicIds[]", [])
            self.get_topics_calls.append(ids)
            if self.topics_payload is not None:
                return self.topics_payload
            return [self.topics_by_id[int(i)] for i in ids if int(i) in self.topics_by_id]
        raise AssertionError(f"unexpected GET {url}")

    def post(self, url, payload, *, headers, **k):
        params = urllib.parse.parse_qs(urllib.parse.parse_qs(payload.decode())["params"][0]) \
            if False else urllib.parse.parse_qs(json.loads(payload.decode())["params"])
        self.post_calls.append({"url": url, "params": params, "headers": headers})
        page = int(params.get("page", ["0"])[0])
        hits = self.hits_pages[page] if page < len(self.hits_pages) else []
        return {"hits": hits}

    def install(self):
        pp.request_public_json = self.get
        pp.request_public_json_post = self.post
        return self


def hit(topic_id: int, added: int) -> dict:
    return {"id": topic_id, "date_added": added}


def run() -> int:  # noqa: PLR0915
    print("=" * 62)
    print("Premiere Adobe Community (Algolia + getTopics) discovery -- offline")
    print("=" * 62)

    real_get, real_post = pp.request_public_json, pp.request_public_json_post
    ctx = CollectorContext(write=False, since=None, max_pages=1)
    try:
        # --- 1-5 index pinning -------------------------------------------------
        Stub(indexes=("adobedme-en-unified", "other-index")).install()
        check("1 verified index selected when first", pp.algolia_credentials()["index"] == "adobedme-en-unified")
        Stub(indexes=("other-index", "another", "adobedme-en-unified")).install()
        check("2 verified index selected when NOT first", pp.algolia_credentials()["index"] == "adobedme-en-unified")
        for label, kwargs in (
            ("3 missing verified index fails closed", {"indexes": ("other-index",)}),
            ("4 empty indexes fails closed", {"indexes": ()}),
            ("5 malformed indexes fails closed", {"token_payload": {"client_id": "A", "token": "T", "availableIndexes": "not-a-list"}}),
        ):
            Stub(**kwargs).install()
            try:
                pp.algolia_credentials()
                check(label, False, "no exception raised")
            except pp.AdobeCommunityAccessError as exc:
                check(label, "searchtoken_index_unavailable" in str(exc), str(exc))
        check("5b positional selection is impossible (no availableIndexes[0])",
              "availableIndexes\")[0]" not in (_SCRIPTS / "patch_collectors" / "adobe_premiere.py").read_text(encoding="utf-8"))

        # --- 6-13 board scoping + pagination + request accounting --------------
        s = Stub(hits_pages=[[hit(900 + i, 1_700_000_000 + i) for i in range(pp.MAX_ALGOLIA_HITS_PER_QUERY)],
                            [hit(800, 1_600_000_000)]],
                 topics_by_id={i: topic(i) for i in list(range(900, 900 + pp.MAX_ALGOLIA_HITS_PER_QUERY)) + [800]}).install()
        cands = pp.adobe_community_algolia_search_candidates(record(), ctx, [])
        tel = dict(pp._ALGOLIA_TELEMETRY)
        facets = [json.loads(c["params"]["facetFilters"][0]) for c in s.post_calls]
        flat = [f for group in facets for pair in group for f in pair]
        check("6 category:726 present in the Algolia POST", all("category:726" in [f for pair in g for f in pair] for g in facets))
        check("7 forum:728 present in the Algolia POST", all("forum:728" in [f for pair in g for f in pair] for g in facets))
        check("8 a category-only payload would fail this scope test", "category:726" in flat and len(flat) > len(facets))
        check("9 forum scoping is never absent", all(any(x.startswith("forum:") for x in [f for pair in g for f in pair]) for g in facets))
        check("10 forum:727 (Announcements) never substituted", "forum:727" not in flat)
        pages_seen = {int(c["params"]["page"][0]) for c in s.post_calls}
        check("11 two-page Algolia pagination exercised", pages_seen == {0, 1}, str(pages_seen))
        check("12 logical query count recorded", tel["algolia_query_count"] == min(pp.MAX_QUERIES_PER_RECORD, tel["algolia_query_count"]) and tel["algolia_query_count"] >= 1)
        check("13 actual page-request count equals POSTs made", tel["algolia_page_request_count"] == len(s.post_calls),
              f"tel={tel['algolia_page_request_count']} posts={len(s.post_calls)}")
        check("12b logical queries are NOT reported as HTTP requests",
              tel["algolia_query_count"] != tel["algolia_page_request_count"] or len(s.post_calls) == tel["algolia_query_count"])

        # --- 14-15 malformed / duplicate ids -----------------------------------
        s = Stub(hits_pages=[[{"id": "not-an-int", "date_added": 1}, hit(500, 10), {"id": 500, "date_added": 10}, {"no_id": 1}]],
                 topics_by_id={500: topic(500)}).install()
        pp.adobe_community_algolia_search_candidates(record(), ctx, [])
        tel = dict(pp._ALGOLIA_TELEMETRY)
        # Discovery issues one pass per logical query term, so the raw discovered count scales
        # with algolia_query_count; only the malformed entries must be dropped from each pass.
        check("14 malformed hit ids ignored",
              tel["discovered_topic_ids"] == 2 * tel["algolia_query_count"],
              f"discovered={tel['discovered_topic_ids']} queries={tel['algolia_query_count']}")
        check("15 duplicate ids deduped", tel["unique_topic_ids"] == 1, str(tel["unique_topic_ids"]))

        # --- 16-21 chunking + truncation + health ------------------------------
        many = {i: topic(i) for i in range(1000, 1000 + 200)}
        s = Stub(hits_pages=[[hit(i, 1_700_000_000 + i) for i in range(1000, 1000 + 200)]], topics_by_id=many).install()
        pp.adobe_community_algolia_search_candidates(record(), ctx, [])
        tel_trunc = dict(pp._ALGOLIA_TELEMETRY)
        sizes = [len(c) for c in s.get_topics_calls]
        check("16 getTopics chunks are <= 20", all(n <= pp.GET_TOPICS_CHUNK for n in sizes), str(sizes))
        check("17 no getTopics request can exceed 25 ids", all(n <= 25 for n in sizes))
        check("19 >120 unique ids reports the correct truncation",
              tel_trunc["unique_topic_ids"] == 200 and tel_trunc["selected_topic_ids"] == 120 and tel_trunc["truncated_topic_ids"] == 80,
              str({k: tel_trunc[k] for k in ("unique_topic_ids", "selected_topic_ids", "truncated_topic_ids")}))
        check("16b gettopics_request_count equals chunks issued", tel_trunc["gettopics_request_count"] == len(sizes))

        exact = {i: topic(i) for i in range(2000, 2120)}
        Stub(hits_pages=[[hit(i, 1_700_000_000 + i) for i in range(2000, 2120)]], topics_by_id=exact).install()
        pp.adobe_community_algolia_search_candidates(record(), ctx, [])
        tel_exact = dict(pp._ALGOLIA_TELEMETRY)
        check("18 exactly 120 ids => no truncation",
              tel_exact["unique_topic_ids"] == 120 and tel_exact["truncated_topic_ids"] == 0, str(tel_exact["truncated_topic_ids"]))

        def health(tel_in, *, accepted=1, cands_n=1, errors=None):
            res = {"method_id": "adobe_community_algolia_search",
                   "candidates": [{"source_url": f"u{i}"} for i in range(cands_n)],
                   "accepted": [{"source_url": "u0"}] * accepted, "rejected": [], "errors": errors or [],
                   "telemetry": tel_in}
            return pp.health_for_method(record(), "2026-08-12T00:00:00Z", res)

        check("20 >120 truncation downgrades a clean run to partial", health(tel_trunc)["status"] == "partial",
              health(tel_trunc)["status"])
        check("21 no truncation + successful run stays success", health(tel_exact)["status"] == "success",
              health(tel_exact)["status"])
        no_res = dict(tel_exact, truncated_topic_ids=5)
        check("21b no_results + truncation becomes partial",
              health(no_res, accepted=0, cands_n=0)["status"] == "partial")
        blocked = health(tel_trunc, accepted=0, cands_n=0,
                         errors=[{"source_url": "u", "reason": "adobe_community_algolia_search_query_failed:blocked"}])
        check("40 a blocked diagnosis is NOT overwritten by partial",
              blocked["status"] in {"blocked", "broken"}, blocked["status"])

        # --- 22-23 selection basis --------------------------------------------
        Stub(hits_pages=[[hit(10, 999), hit(11, 5_000), hit(12, 1)]],
             topics_by_id={10: topic(10), 11: topic(11), 12: topic(12)}).install()
        saved_cap = pp.MAX_TOPIC_IDS_PER_RECORD
        pp.MAX_TOPIC_IDS_PER_RECORD = 1
        try:
            s2 = Stub(hits_pages=[[hit(10, 999), hit(11, 5_000), hit(12, 1)]],
                      topics_by_id={10: topic(10), 11: topic(11), 12: topic(12)}).install()
            pp.adobe_community_algolia_search_candidates(record(), ctx, [])
            picked = [int(i) for call in s2.get_topics_calls for i in call]
            check("22 newest-by-date_added selected under the cap (not lowest id)", picked == [11], str(picked))
        finally:
            pp.MAX_TOPIC_IDS_PER_RECORD = saved_cap
        check("23 topic_selection_basis telemetry is explicit",
              tel_exact["topic_selection_basis"] == "algolia_date_added_descending", tel_exact["topic_selection_basis"])

        # --- 24-25 since window ------------------------------------------------
        Stub(hits_pages=[[hit(70, 5), hit(71, 6)]],
             topics_by_id={70: topic(70, date="2026-01-05T00:00:00+0000"),
                           71: topic(71, date="2026-08-01T00:00:00+0000")}).install()
        got = pp.adobe_community_algolia_search_candidates(record(), CollectorContext(write=False, since="2026-06-28", max_pages=1), [])
        urls = [c["source_url"] for c in got]
        check("24 since-window rejects the old report", all("slug-70" not in u for u in urls), str(urls))
        check("25 recent report survives the since-window", any("slug-71" in u for u in urls), str(urls))

        # --- 26-27 getTopics honesty ------------------------------------------
        Stub(hits_pages=[[hit(80, 1)]], topics_payload=[]).install()
        check("26 empty getTopics yields no candidates (never invented)",
              pp.adobe_community_algolia_search_candidates(record(), ctx, []) == [])
        Stub(hits_pages=[[hit(81, 1)]], topics_payload={"unexpected": "shape"}).install()
        check("27 malformed getTopics fails closed",
              pp.adobe_community_algolia_search_candidates(record(), ctx, []) == [])

        # --- 28-32 candidate contract ------------------------------------------
        Stub(hits_pages=[[hit(90, 1)]],
             topics_by_id={90: topic(90, board="announcements-727")}).install()
        check("29 an announcement URL is rejected",
              pp.adobe_community_algolia_search_candidates(record(), ctx, []) == [])
        Stub(hits_pages=[[hit(91, 1)]], topics_by_id={91: topic(91, board="questions-729")}).install()
        check("28 a non-Bug-Report specific URL is rejected",
              pp.adobe_community_algolia_search_candidates(record(), ctx, []) == [])
        Stub(hits_pages=[[hit(92, 1)]], topics_by_id={92: topic(92, title="")}).install()
        check("30 missing title rejected", pp.adobe_community_algolia_search_candidates(record(), ctx, []) == [])
        Stub(hits_pages=[[hit(93, 1)]], topics_by_id={93: topic(93, body="")}).install()
        check("31 missing body rejected", pp.adobe_community_algolia_search_candidates(record(), ctx, []) == [])
        Stub(hits_pages=[[hit(94, 1)]], topics_by_id={94: topic(94)}).install()
        one = pp.adobe_community_algolia_search_candidates(record(), ctx, [])
        check("32 candidate contract preserved",
              len(one) == 1 and set(one[0]) == {"source_type", "source_name", "source_url", "archive_url",
                                                "parent_title", "report_title", "report_text", "source_date"}
              and one[0]["source_type"] == pp.SOURCE_TYPE, str(one[:1]))

        # --- 33-37 request accounting + duration -------------------------------
        s = Stub(hits_pages=[[hit(i, i) for i in range(300, 330)]],
                 topics_by_id={i: topic(i) for i in range(300, 330)}).install()
        pp.adobe_community_algolia_search_candidates(record(), ctx, [])
        tel = dict(pp._ALGOLIA_TELEMETRY)
        check("33 searchToken HTTP count", tel["search_token_request_count"] == s.token_calls == 1)
        check("34 Algolia page-request count", tel["algolia_page_request_count"] == len(s.post_calls))
        check("35 getTopics request count", tel["gettopics_request_count"] == len(s.get_topics_calls))
        check("36 total HTTP arithmetic holds",
              tel["total_http_request_count"] == tel["search_token_request_count"] + tel["algolia_page_request_count"] + tel["gettopics_request_count"]
              == s.token_calls + len(s.post_calls) + len(s.get_topics_calls),
              str(tel))
        check("37 duration telemetry present and non-negative",
              isinstance(tel["method_duration_ms"], int) and tel["method_duration_ms"] >= 0)

        # --- 38-39 transport invariants ----------------------------------------
        src = (_SCRIPTS / "patch_collectors" / "adobe_premiere.py").read_text(encoding="utf-8")
        check("38 runtime budget path still used by both transports",
              src.count("rb.request_timeout(rb.get_run_budget()") >= 4 and "rb.bounded_read" in src)
        import re as _re
        imports = [ln for ln in src.splitlines() if ln.lstrip().startswith(("import ", "from "))]
        check("39 no lib.http dependency introduced (import-level, prose-immune)",
              not any("lib.http" in line or "lib import http" in line for line in imports),
              str([l for l in imports if "http" in l]))


        # ================= PATCH-IDENTITY AUTHORITY (P0 false-positive) =================
        # A 26.3 regression report that says "works in 26.2" is evidence about 26.3, never
        # evidence that 26.2 is defective. Identity comes from the most authoritative statement.
        def ident(target, *, parent="", title="", body=""):
            return pp.premiere_patch_identity(
                {"parent_title": parent, "report_title": title, "report_text": body}, target)

        def counted(target, *, title="", body="", url="https://community.adobe.com/bug-reports-728/x-1"):
            cand = {"source_type": pp.SOURCE_TYPE, "source_name": pp.SOURCE_NAME, "source_url": url,
                    "archive_url": "", "parent_title": title, "report_title": title,
                    "report_text": body, "source_date": "2026-07-20T00:00:00+0000"}
            return pp.row_from_candidate(record(target), cand, "2026-08-13T00:00:00Z")

        T1 = "Premiere Pro 26.3 Export button does nothing; UI tabs become unclickable after clicking Export"
        B1 = "Product/Version: Adobe Premiere Pro 26.3. This is a regression; works in 26.2. Export crashes."
        ok, basis, reason = ident("26.2", title=T1, body=B1)
        check("ID-1 title 26.3 + body 'works in 26.2', target 26.2 => REJECT",
              (not ok) and reason == "conflicting_premiere_title_version", f"{ok=} {basis=} {reason=}")
        row = counted("26.2", title=T1, body=B1)
        check("ID-1b the 26.2 row is not counted and names the identity reason",
              row.get("counted") is not True and row.get("exclusion_reason") == "conflicting_premiere_title_version",
              str({k: row.get(k) for k in ("counted", "exclusion_reason", "patch_version_matched")}))
        ok2, _b2, _r2 = ident("26.3", title=T1, body=B1)
        check("ID-2 same report, target 26.3 => identity PASS", ok2)

        T3 = "Premiere Pro 26.3 Project Errors and Logitech MX Creative Console Compatibility Issue"
        B3 = "Problem version: Premiere Pro 26.3\nWorking version: Premiere Pro 26.2\nReverting to 26.2 resolves it."
        ok3, _b3, r3 = ident("26.2", title=T3, body=B3)
        check("ID-3 explicit problem 26.3 / working 26.2, target 26.2 => REJECT", (not ok3) and r3, f"{ok3=} {r3=}")
        check("ID-4 same, target 26.3 => identity PASS", ident("26.3", title=T3, body=B3)[0])

        check("ID-5 no title version, body says 26.2 crashes => fallback PASS",
              ident("26.2", title="Export fails after update", body="Premiere Pro 26.2 crashes during export.")[0])
        ok6, b6, r6 = ident("26.2", title="Export fails after update",
                            body="Problem version: Premiere Pro 26.3\nWorking version: Premiere Pro 26.2")
        check("ID-6 no title version, declared problem 26.3, target 26.2 => REJECT",
              (not ok6) and r6 == "conflicting_premiere_problem_version", f"{ok6=} {b6=} {r6=}")
        check("ID-7 same body, target 26.3 => identity PASS",
              ident("26.3", title="Export fails after update",
                    body="Problem version: Premiere Pro 26.3\nWorking version: Premiere Pro 26.2")[0])

        T8 = "Premiere Pro 26.2.2 / 26.3.0 Text Style strokes lost on export"
        check("ID-8 multi-version title, target 26.2.2 => may PASS", ident("26.2.2", title=T8)[0])
        check("ID-9 multi-version title, target 26.3.0 => may PASS", ident("26.3.0", title=T8)[0])
        check("ID-9b multi-version title, unrelated target 26.1 => REJECT", not ident("26.1", title=T8)[0])

        check("ID-10 title 26.3 + incidental historical 26.2 mention, target 26.2 => REJECT",
              not ident("26.2", title="Premiere Pro 26.3 timeline corruption",
                        body="I have used Premiere Pro 26.2 for a year without issue. Now it corrupts projects.")[0])

        check("ID-11 26.2 is not satisfied by 26.2.2 (no prefix matching)",
              not pp._version_in("26.2", ["26.2.2"]) and pp._version_in("26.2", ["26.2.0"])
              and pp._version_in("26.2.2", ["26.2.2"]))
        check("ID-11b title-extracted versions are exact tokens",
              pp.premiere_versions_in_title("Premiere Pro 26.2.2 crash") == ["26.2.2"],
              str(pp.premiere_versions_in_title("Premiere Pro 26.2.2 crash")))

        b65 = "Premiere Pro 26.2 Build 65 crashes on launch every time."
        check("ID-12 BUILD 65 handling unchanged",
              pp.premiere_build_65_context(b65, "26.2") and pp.premiere_version_match(b65, "26.2")[0]
              and ident("26.2", title="Crash on launch", body=b65)[0])


        # ===== RESIDUAL FALLBACK CLASS: target used only as a comparison/control version =====
        # No title version, no labelled Problem/Affected declaration -- the defect belongs to the
        # OTHER version and the target is merely named as the one that works.
        ADV = [
            ("ADV-1 '26.3 crashes / 26.2 was stable'",
             "Export regression after update",
             "Premiere Pro 26.3 crashes every time I export.\nPremiere Pro 26.2 was stable."),
            ("ADV-2 '26.3 is broken / 26.2 works fine'",
             "Export regression after update",
             "Premiere Pro 26.3 is broken.\nPremiere Pro 26.2 works fine."),
            ("ADV-3 '26.3 crashes / no issue in 26.2'",
             "Export regression after update",
             "Premiere Pro 26.3 crashes.\nNo issue in Premiere Pro 26.2."),
            ("ADV-4 '26.3 crashes / 26.2 was unaffected'",
             "Export regression after update",
             "Premiere Pro 26.3 crashes.\n26.2 was unaffected."),
        ]
        for label, title, body in ADV:
            ok_t, basis_t, reason_t = ident("26.2", title=title, body=body)
            check(f"{label} => target 26.2 REJECT", not ok_t, f"{basis_t=} {reason_t=}")
            row_t = counted("26.2", title=title, body=body)
            check(f"{label} => 26.2 row not counted", row_t.get("counted") is not True,
                  str({k: row_t.get(k) for k in ("counted", "exclusion_reason", "match_basis")}))
            check(f"ADV-5 {label} => target 26.3 may PASS", ident("26.3", title=title, body=body)[0])

        check("ADV-6 control phrase AND separate affirmative affected phrase => may PASS",
              ident("26.2", title="Export regression",
                    body="Premiere Pro 26.3 crashes. Premiere Pro 26.2 was stable at first, "
                         "but Premiere Pro 26.2 now crashes on export too.")[0])

        # ===== LIVE ROWS THAT MUST STAY VALID =====
        check("LIVE-7 .kys report: '26.2 (same issue)' stays valid",
              ident("26.2", title="Premiere Pro reports Adobe Premiere Pro defaults kys is invalid",
                    body="Premiere Pro 26.3 (latest)\nPremiere Pro 26.2 (same issue)\n"
                         "Beta crashes when opening keyboard shortcuts.")[0])
        check("LIVE-8 New Index: reporter is using 26.2.2 while experiencing the slowdown",
              ident("26.2.2", title="New Index panel slows Premiere a lot",
                    body="I am using Premiere Pro 26.2.2 and the new Index panel slows everything down.")[0])
        ok9, basis9, _r9 = ident("26.2.2", title="CUDA issue in Premiere's console",
                                 body="Premiere Pro version: 26.2.2\nCUDA errors fill the console.")
        check("LIVE-9 CUDA reports premiere_declared_problem_version",
              ok9 and basis9 == "premiere_declared_problem_version", f"{ok9=} {basis9=}")
        ts_title = "Text Style: second and subsequent strokes are lost when saving to My Styles (26.2.2 / 26.3.0)"
        ok10, basis10, _r10 = ident("26.2.2", title=ts_title,
                                    body="Reproduced on Premiere Pro 26.2.2 and 26.3.0.")
        check("LIVE-10 Text Style reports the ACTUAL basis the code used (no Premiere-prefixed title version)",
              ok10 and basis10 in {"premiere_text_fallback", "premiere_title_version_identity",
                                   "premiere_declared_problem_version"},
              f"actual basis={basis10!r}")
        print(f"        [LIVE-10 actual identity basis = {basis10!r}]")

        check("ADV-11 shared exact_version_match untouched",
              "def exact_version_match" not in (_SCRIPTS / "patch_collectors" / "adobe_premiere.py").read_text(encoding="utf-8"))

        check("ID-13 control-only mention cannot establish identity",
              not ident("26.2", title="Crash after update", body="I reverted to 26.2 and it was fine.")[0])
        check("ID-14 no versions anywhere => fallback defers to text matching (no false reject)",
              ident("26.2", title="Export crash", body="Export crashes constantly since the update.")[0])

        # --- notes surface -------------------------------------------------------
        row = health(tel_trunc)
        check("telemetry appears in health notes", "truncated_topic_ids=80" in row["notes"] and "topic_selection_basis=" in row["notes"],
              row["notes"][-160:])
        check("health row keeps the canonical schema (extra keys discarded)",
              "truncated_topic_ids" not in row and row["method_id"] == "adobe_community_algolia_search")
    finally:
        pp.request_public_json, pp.request_public_json_post = real_get, real_post

    print()
    print("=" * 62)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 62)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
