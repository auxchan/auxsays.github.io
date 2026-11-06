#!/usr/bin/env python3
"""A collection problem reads as CURRENT on a patch page only while the monitoring card says so.

THE DEFECT (AUX-084). A patch page makes two statements about community collection for one release:
the monitoring card (`_includes/monitoring-status.html`) and the freshness notice in
`_layouts/aux-update.html`. The card judges every method-health row against the configured
`monitoring_max_age_days` and says COLLECTION STALE once nothing has run recently. The notice read
the SAME rows by status alone, with no freshness check, so one failed visit kept saying "Collection
blocked. Some collection methods are currently blocked or returning errors." for as long as the row
stayed in the file. Rendering every record on main 47720db4 at a pinned 2026-11-12T00:00:00Z: 10
Acrobat Pro 25.001 pages said "Collection blocked." beside a card that said COLLECTION STALE, all
from one failed Adobe community search on 2026-10-28 that the newest-first schedule never revisits.

THE CONTRACT, pinned by rendering the SHIPPED layout through the Liquid gem with EVERY include it
uses resolved from `_includes` (the monitoring card included, nothing stubbed), at FIXED clocks over
frozen synthetic fixtures -- never the wall clock:
  [N] named cases: the exact notice text and the exact card status. They include the Acrobat Pro
      shape at the instants before, at and after its failed run ages out, both boundary seconds,
      rows that ran before release, in the future, or with no or an unparseable time, a fresh and
      an old row together, live pages, and a site whose limit is not the default (which proves the
      notice reads the card's input rather than a number of its own).
  [G] every degraded status x {1 day, exactly the limit, the limit + 1 s, 20 days}: the notice
      speaks in the present tense exactly when the card counts that run as fresh.
  [A] on EVERY rendered case: a notice that says "Collection blocked." or "Collection degraded."
      sits beside a card that says COLLECTION BLOCKED or MONITORING DEGRADED.
  [S] statics the harness relies on.
  [W] the public wording separates report age from collection freshness.

The boundary instants are computed from the shipped `_config.yml`, so the suite tests the limit the
site actually uses. The My Patch Stack label is pinned in test_patch_stack_dashboard.py [CL].

Offline and deterministic. Writes only inside a temp dir.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_freshness_notice_currency.py
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
LAYOUT_PATH = _AUX / "_layouts" / "aux-update.html"
INCLUDES = _AUX / "_includes"
CARD_PATH = INCLUDES / "monitoring-status.html"
CONFIG_PATH = _AUX / "_config.yml"
METHODOLOGY_PATH = _AUX / "updates" / "methodology" / "index.md"
STACK_PAGE_PATH = _AUX / "updates" / "my-stack.md"
JS_PATH = _AUX / "assets" / "js" / "auxsays.js"

LAYOUT = LAYOUT_PATH.read_text(encoding="utf-8")
COMMENT_RE = re.compile(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", re.S)
LAYOUT_EMITTED = COMMENT_RE.sub("", LAYOUT)
CARD = CARD_PATH.read_text(encoding="utf-8")
CARD_EMITTED = COMMENT_RE.sub("", CARD)
CONFIG = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}

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
        _ERRORS.append(label)
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))


# ------------------------------------------------------------------------------ the renderer

# Jekyll's include tag, not Liquid's (the filename carries a dot, params arrive as key=value), and
# the Jekyll filters the layout and its includes use. render! so a Liquid error RAISES and is
# reported per case instead of being embedded where an "is absent" assertion would read past it.
_DRIVER = r"""
require 'liquid'
require 'json'

class JekyllInclude < Liquid::Tag
  SYNTAX = /([\w.\/-]+)((\s+\w+\s*=\s*(?:"[^"]*"|'[^']*'|[\w.\[\]\/-]+))*)/
  def initialize(name, markup, tokens)
    super
    m = markup.strip.match(SYNTAX) or raise Liquid::SyntaxError, "bad include: #{markup}"
    @file = m[1]
    @params = {}
    (m[2] || "").scan(/(\w+)\s*=\s*("[^"]*"|'[^']*'|[\w.\[\]\/-]+)/) { |k, v| @params[k] = v }
  end
  def render(context)
    path = File.join(context.registers[:include_root], @file)
    raise Liquid::FileSystemError, "missing include #{@file}" unless File.exist?(path)
    vals = {}
    @params.each do |k, v|
      vals[k] = (v =~ /\A"(.*)"\z/m || v =~ /\A'(.*)'\z/m) ? $1 : context[v]
    end
    partial = (context.registers[:cache] ||= {})[path] ||=
      Liquid::Template.parse(File.read(path, encoding: "utf-8"))
    context.stack { context["include"] = vals; partial.render!(context) }
  end
end
Liquid::Template.register_tag("include", JekyllInclude)

module Shims
  def relative_url(i) = "/" + i.to_s.sub(%r{\A/}, "")
  def absolute_url(i) = "https://auxsays.test/" + i.to_s.sub(%r{\A/}, "")
  def jsonify(i) = JSON.generate(i)
  def markdownify(i) = i.to_s
  def where(input, property, value)
    input = input.values if input.is_a?(Hash)
    return input unless input.respond_to?(:select)
    input.select { |item| item.is_a?(Hash) && item[property].to_s == value.to_s }
  end
end
Liquid::Template.register_filter(Shims)

payload = JSON.parse(File.read(ARGV[0], encoding: "utf-8"))
tpl = Liquid::Template.parse(payload["template"])
out = {}
payload["cases"].each do |name, c|
  begin
    out[name] = tpl.render!({ "site" => c["site"], "page" => c["page"], "content" => "" },
                            registers: { include_root: payload["includes"] })
  rescue => e
    out[name] = "<<RENDER FAILED: #{e.class}: #{e.message}>>"
  end
end
print JSON.generate(out)
"""


def render_all(cases: dict) -> dict:
    """{name: html} for {name: {"site": ..., "page": ...}}, one Ruby process for every case. A missing
    ruby or gem yields a failure string per case, so every check still runs -- and fails."""
    ruby = shutil.which("ruby")
    if not ruby:
        return {name: "<<RENDER FAILED: ruby is not on PATH>>" for name in cases}
    template = LAYOUT.split("---", 2)[-1]          # drop the `layout: aux-base` front matter
    with tempfile.TemporaryDirectory(prefix="auxsays-notice-currency-") as td:
        script, payload = Path(td) / "d.rb", Path(td) / "p.json"
        script.write_text(_DRIVER, encoding="utf-8")
        payload.write_text(json.dumps({"template": template, "cases": cases,
                                       "includes": str(INCLUDES)}), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=600)
    if proc.returncode != 0:
        reason = f"<<RENDER FAILED: ruby exited {proc.returncode}: {(proc.stderr or '')[-300:]}>>"
        return {name: reason for name in cases}
    return json.loads(proc.stdout)


def aside_of(html: str):
    m = re.search(r'<aside class="update-evidence-freshness-notice".*?</aside>', html, re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(0))).strip() if m else None


def card_statuses(html: str) -> tuple:
    """(compact hero status, full card status) as the shipped monitoring include rendered them."""
    def first(pattern):
        m = re.search(pattern, html, re.S)
        return re.sub(r"\s+", " ", m.group(1)).strip() if m else None
    compact = first(r'<div class="update-monitoring-compact[^"]*">.*?'
                    r'<span class="patch-monitoring[^"]*">(.*?)</span>')
    full = first(r'<div class="update-monitoring-card[^"]*"[^>]*>.*?'
                 r'<span class="patch-monitoring[^"]*">(.*?)</span>')
    return compact, full


# ------------------------------------------------------------------------------ the fixtures

LIMIT_DAYS = int(CONFIG.get("monitoring_max_age_days") or 14)
MIN_HEALTHY = int(CONFIG.get("monitoring_min_healthy_methods") or 2)
CLOCK = datetime(2026, 9, 9, tzinfo=timezone.utc)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


DAY_OLD = iso(CLOCK - timedelta(days=1))
AT_LIMIT = iso(CLOCK - timedelta(days=LIMIT_DAYS))
PAST_LIMIT = iso(CLOCK - timedelta(days=LIMIT_DAYS, seconds=1))
OLD_RUN = iso(CLOCK - timedelta(days=LIMIT_DAYS + 6))

PAGE_URL = "/updates/obs-project/obs-studio/31-0-4/"


def site(clock: str = iso(CLOCK), rows=(), **over) -> dict:
    s = {"time": clock,
         "monitoring_max_age_days": LIMIT_DAYS,
         "monitoring_min_healthy_methods": MIN_HEALTHY,
         "data": {"evidence_method_health": {"methods": list(rows)},
                  "live_eligibility": {"urls": [PAGE_URL]}}}
    s.update(over)
    return s


def page(**over) -> dict:
    """A synthetic pilot page with one accepted report, captured long before CLOCK."""
    base = {
        "url": PAGE_URL,
        "product_id": "obs-studio", "update_version": "31.0.4", "target_build": "",
        "update_product": "OBS Studio", "update_consensus_label": "Negative",
        "update_published_at": "2025-06-27T00:00:00Z",
        "update_source_url": "https://example.test/notes",
        "update_status": "current",
        "consensus_collection_status": "pilot_initial_sample",
        "evidence_state": "pilot_sample",
        "update_report_count": 1,
        "confirmed_patch_specific_report_count": 1,
        "accepted_report_sources": [{"source_type": "forum_thread"}],
        "evidence_last_checked": "2026-01-01T00:00:00Z",
    }
    base.update(over)
    return base


def live_page(**over) -> dict:
    return page(update_report_count=5, confirmed_patch_specific_report_count=5,
                consensus_collection_status="live_consensus", evidence_state="live", **over)


def row(status: str, last_run, *, method_id: str = "obs_forum_search",
        source_type: str = "forum_thread") -> dict:
    r = {"product_id": "obs-studio", "update_version": "31.0.4", "target_build": "",
         "method_id": method_id, "source_type": source_type, "status": status}
    if last_run is not None:
        r["last_run"] = last_run
    return r


RECENT_CAPTURE = iso(CLOCK - timedelta(days=4))   # inside the seven-day capture rule

_D = "Jan 1, 2026"
_OLD = f"No recently captured accepted reports. The newest accepted report was captured on {_D}."
_BLOCKED = "Collection blocked. Some collection methods are currently blocked or returning errors."
_DEGRADED = "Collection degraded. Some collection methods reported partial or low-confidence results."
_OLD_HEALTHY = f"{_OLD} Collection status is reported separately."
_CLAUSE = " Report counts are preserved from structured evidence and are not live telemetry."

BLOCKED_CARD, DEGRADED_CARD, STALE_CARD = "COLLECTION BLOCKED", "MONITORING DEGRADED", "COLLECTION STALE"
NOT_YET_CARD = "NOT YET MONITORED"

# The real record's shape: Acrobat Pro 25.001.20630 (build-aware product, empty build), one accepted
# report captured 2026-09-01, and three method rows from one pass on 2026-10-28 -- the Adobe
# community search returned an error and the two retired methods report disabled. Synthetic values
# only; the instants are the real ones because the defect is about exactly those instants.
ACRO_RUN = datetime(2026, 10, 28, 12, 49, 3, tzinfo=timezone.utc)
ACRO_URL = "/updates/adobe/adobe-acrobat-pro/25-001-20630/"


def acro_page() -> dict:
    return {
        "url": ACRO_URL,
        "product_id": "adobe-acrobat-pro", "update_version": "25.001.20630", "target_build": "",
        "update_product": "Adobe Acrobat Pro", "update_consensus_label": "Negative",
        "update_published_at": "2025-08-18T00:00:00Z",
        "update_source_url": "https://example.test/acrobat-notes",
        "update_status": "current",
        "consensus_collection_status": "pilot_initial_sample",
        "evidence_state": "pilot_sample",
        "update_report_count": 1,
        "confirmed_patch_specific_report_count": 1,
        "accepted_report_sources": [{"source_type": "adobe community bug report"}],
        "evidence_last_checked": "2026-09-01T17:40:03Z",
    }


def acro_rows() -> list:
    def r(method_id, source_type, status):
        return {"product_id": "adobe-acrobat-pro", "update_version": "25.001.20630",
                "target_build": "", "method_id": method_id, "source_type": source_type,
                "status": status, "last_run": iso(ACRO_RUN)}
    return [r("adobe_community_algolia_search", "adobe_community_bug_report", "broken"),
            r("adobe_community_search", "adobe_community_bug_report", "disabled"),
            r("reddit_search", "reddit_community_report", "disabled")]


def acro_site(clock: datetime) -> dict:
    return site(iso(clock), acro_rows(),
                data={"evidence_method_health": {"methods": acro_rows()},
                      "live_eligibility": {"urls": []}})


_ACRO_D = "Sep 1, 2026"
_ACRO_BLOCKED = (f"{_BLOCKED} No recently captured accepted reports. The newest accepted report was "
                 f"captured on {_ACRO_D}.")
_ACRO_STALE = (f"No recently captured accepted reports. The newest accepted report was captured on "
               f"{_ACRO_D}. Collection status is reported separately.")

TEN_DAY_LIMIT = 10 if LIMIT_DAYS != 10 else 9   # any limit other than the shipped one

# name -> (site, page, expected aside text or None, expected card status)
NAMED = {
    "fresh blocked row, old capture":
        (site(rows=[row("blocked", DAY_OLD)]), page(), f"{_BLOCKED} {_OLD}", BLOCKED_CARD),
    "fresh blocked row, recent capture":
        (site(rows=[row("blocked", DAY_OLD)]), page(evidence_last_checked=RECENT_CAPTURE),
         _BLOCKED, BLOCKED_CARD),
    "old blocked row, old capture":
        (site(rows=[row("blocked", OLD_RUN)]), page(), _OLD_HEALTHY, STALE_CARD),
    "old blocked row, recent capture":
        (site(rows=[row("blocked", OLD_RUN)]), page(evidence_last_checked=RECENT_CAPTURE),
         None, STALE_CARD),
    "blocked row exactly at the limit":
        (site(rows=[row("blocked", AT_LIMIT)]), page(), f"{_BLOCKED} {_OLD}", BLOCKED_CARD),
    "blocked row one second past the limit":
        (site(rows=[row("blocked", PAST_LIMIT)]), page(), _OLD_HEALTHY, STALE_CARD),
    "fresh degraded row":
        (site(rows=[row("partial", DAY_OLD)]), page(), f"{_DEGRADED} {_OLD}", DEGRADED_CARD),
    "old degraded row":
        (site(rows=[row("partial", OLD_RUN)]), page(), _OLD_HEALTHY, STALE_CARD),
    "degraded row exactly at the limit":
        (site(rows=[row("partial", AT_LIMIT)]), page(), f"{_DEGRADED} {_OLD}", DEGRADED_CARD),
    "degraded row one second past the limit":
        (site(rows=[row("partial", PAST_LIMIT)]), page(), _OLD_HEALTHY, STALE_CARD),
    # The card still reads the old row's status (its rule 7), so it says degraded; the notice makes
    # no present-tense claim from that row and defers to the card.
    "fresh success beside an old blocked row":
        (site(rows=[row("success", DAY_OLD, method_id="a"), row("blocked", OLD_RUN, method_id="b")]),
         page(), _OLD_HEALTHY, DEGRADED_CARD),
    "fresh blocked beside an old success":
        (site(rows=[row("blocked", DAY_OLD, method_id="b"), row("success", OLD_RUN, method_id="a")]),
         page(), f"{_BLOCKED} {_OLD}", BLOCKED_CARD),
    "blocked row that ran before release":
        (site(rows=[row("blocked", iso(CLOCK - timedelta(days=6)))]),
         page(update_published_at=iso(CLOCK - timedelta(days=4))), _OLD_HEALTHY, NOT_YET_CARD),
    "blocked row stamped in the future":
        (site(rows=[row("blocked", iso(CLOCK + timedelta(days=1)))]), page(), _OLD_HEALTHY,
         STALE_CARD),
    "blocked row with no run time":
        (site(rows=[row("blocked", None)]), page(), _OLD_HEALTHY, STALE_CARD),
    "blocked row with an unparseable run time":
        (site(rows=[row("blocked", "not-a-time")]), page(), _OLD_HEALTHY, NOT_YET_CARD),
    "live page, old blocked row":
        (site(rows=[row("blocked", OLD_RUN)]), live_page(), _OLD_HEALTHY + _CLAUSE, STALE_CARD),
    "live page, fresh blocked row":
        (site(rows=[row("blocked", DAY_OLD)]), live_page(), f"{_BLOCKED} {_OLD}" + _CLAUSE,
         BLOCKED_CARD),
    # Same row, same clock, a different configured limit: only a notice that reads the card's input
    # moves with it. Under the shipped limit this run would be fresh.
    "another configured limit, run just past it":
        (site(rows=[row("blocked", iso(CLOCK - timedelta(days=TEN_DAY_LIMIT, seconds=1)))],
              monitoring_max_age_days=TEN_DAY_LIMIT), page(), _OLD_HEALTHY, STALE_CARD),
    "another configured limit, run inside it":
        (site(rows=[row("blocked", iso(CLOCK - timedelta(days=TEN_DAY_LIMIT - 1)))],
              monitoring_max_age_days=TEN_DAY_LIMIT), page(), f"{_BLOCKED} {_OLD}", BLOCKED_CARD),
    "Acrobat Pro 25.001 shape, 2026-11-06":
        (acro_site(datetime(2026, 11, 6, 5, tzinfo=timezone.utc)), acro_page(), _ACRO_BLOCKED,
         BLOCKED_CARD),
    "Acrobat Pro 25.001 shape, exactly at the limit":
        (acro_site(ACRO_RUN + timedelta(days=LIMIT_DAYS)), acro_page(), _ACRO_BLOCKED, BLOCKED_CARD),
    "Acrobat Pro 25.001 shape, one second past the limit":
        (acro_site(ACRO_RUN + timedelta(days=LIMIT_DAYS, seconds=1)), acro_page(), _ACRO_STALE,
         STALE_CARD),
    "Acrobat Pro 25.001 shape, 2026-11-12":
        (acro_site(datetime(2026, 11, 12, tzinfo=timezone.utc)), acro_page(), _ACRO_STALE,
         STALE_CARD),
}
assert ACRO_RUN + timedelta(days=LIMIT_DAYS) < datetime(2026, 11, 12, tzinfo=timezone.utc), \
    "the 2026-11-12 Acrobat case must lie past the limit for the shipped config"

DEGRADED_STATUSES = ("blocked", "broken", "partial", "low_confidence", "manual_review_needed", "stale")
AGES = (("1 day", DAY_OLD, True), ("exactly the limit", AT_LIMIT, True),
        ("the limit + 1 s", PAST_LIMIT, False), ("20 days", OLD_RUN, False))
GRID = {}
for _status in DEGRADED_STATUSES:
    for _age, _run, _fresh in AGES:
        GRID[f"{_status} at {_age}"] = (_status, _run, _fresh)

PRESENT_TENSE = ("Collection blocked.", "Collection degraded.")
AGREEING_CARD = (BLOCKED_CARD, DEGRADED_CARD)


def agrees(aside, card_full) -> bool:
    """The notice claims a CURRENT collection problem only where the card shows a current one."""
    if aside is None or not aside.startswith(PRESENT_TENSE):
        return True
    return card_full in AGREEING_CARD


def run() -> int:
    print("=" * 78)
    print("Freshness notice: an old collection problem never reads as a current one")
    print("=" * 78)

    # ---------- S: what the harness relies on ----------
    print("\n[S] the notice reads the card's input; the harness renders the real card")
    check("S1 the notice reads the card's freshness limit, with the card's own default",
          "site.monitoring_max_age_days | default: 14" in LAYOUT_EMITTED
          and "site.monitoring_max_age_days | default: 14" in CARD_EMITTED)
    check("S2 the notice and the card read the same build clock",
          "site.time | date: '%s' | plus: 0" in LAYOUT_EMITTED
          and "site.time | date: '%s' | plus: 0" in CARD_EMITTED)
    emitters = sorted(p.name for p in INCLUDES.glob("*.html")
                      if 'class="patch-monitoring' in COMMENT_RE.sub("", p.read_text(encoding="utf-8")))
    check("S3 only the monitoring card emits the card status the cases read",
          emitters == ["monitoring-status.html"] and 'class="patch-monitoring' not in LAYOUT_EMITTED,
          str(emitters))
    used = sorted(set(re.findall(r"\{%-?\s*include\s+([\w.-]+)", LAYOUT_EMITTED)))
    check("S4 every include the layout uses exists, so nothing is stubbed out of the render",
          bool(used) and all((INCLUDES / name).is_file() for name in used), str(used))

    # ---------- render everything once ----------
    cases = {f"N {name}": {"site": s, "page": p} for name, (s, p, _a, _c) in NAMED.items()}
    for name, (status, run_at, _fresh) in GRID.items():
        cases[f"G {name}"] = {"site": site(rows=[row(status, run_at)]), "page": page()}
    rendered = render_all(cases)
    liquid_ok = all("RENDER FAILED" not in h for h in rendered.values())
    check("S5 every case rendered through the liquid gem (install liquid 4.0.4; never skipped)",
          liquid_ok, next((h[:300] for h in rendered.values() if "RENDER FAILED" in h), ""))

    # ---------- N: named cases ----------
    print("\n[N] named cases: exact notice text and exact card status")
    for name, (_s, _p, want_aside, want_card) in NAMED.items():
        html = rendered.get(f"N {name}", "<<RENDER FAILED: missing>>")
        aside = aside_of(html)
        compact, full = card_statuses(html)
        check(f"N {name}: the card says {want_card}",
              compact == want_card and full == want_card, f"compact={compact!r} full={full!r}")
        check(f"N {name}: the notice says exactly what is current",
              aside == want_aside, f"got {aside!r}\n        wanted {want_aside!r}")
        check(f"A {name}: the notice claims no current problem the card does not show",
              agrees(aside, full), f"notice={aside!r} card={full!r}")

    # ---------- G: the grid ----------
    print("\n[G] every degraded status at every age: present tense exactly when the card says fresh")
    for name, (status, _run, fresh) in GRID.items():
        html = rendered.get(f"G {name}", "<<RENDER FAILED: missing>>")
        aside = aside_of(html)
        compact, full = card_statuses(html)
        blocked = status in ("blocked", "broken")
        want_head = (("Collection blocked." if blocked else "Collection degraded.") if fresh
                     else "No recently captured accepted reports.")
        want_card = (BLOCKED_CARD if blocked else DEGRADED_CARD) if fresh else STALE_CARD
        check(f"G {name}: the card says {want_card}",
              compact == want_card and full == want_card, f"compact={compact!r} full={full!r}")
        check(f"G {name}: the notice headline is {want_head!r}",
              aside is not None and aside.startswith(want_head), f"got {aside!r}")
        check(f"A {name}: the notice claims no current problem the card does not show",
              agrees(aside, full), f"notice={aside!r} card={full!r}")

    # ---------- W: public wording ----------
    print("\n[W] the public wording separates report age from collection freshness")
    methodology = METHODOLOGY_PATH.read_text(encoding="utf-8")
    live_def = re.search(r"<dt>Live consensus</dt><dd>(.*?)</dd>", methodology, re.S)
    live_text = live_def.group(1) if live_def else ""
    check("W1 the live-consensus definition no longer says the collection 'goes stale'",
          bool(live_text) and "goes stale" not in live_text, live_text[:200])
    limit_said = re.search(r"has not run for (\d+) days", live_text)
    check("W2 it says when collection counts as stopped, using the configured limit",
          bool(limit_said) and int(limit_said.group(1)) == LIMIT_DAYS,
          f"said={limit_said.group(1) if limit_said else None} config={LIMIT_DAYS}")
    check("W3 it names the newest accepted report's capture date as a separate fact",
          "newest accepted report was captured" in live_text, live_text[:300])
    public_text = (COMMENT_RE.sub("", methodology) + COMMENT_RE.sub("", STACK_PAGE_PATH.read_text(
        encoding="utf-8")) + JS_PATH.read_text(encoding="utf-8"))
    retired = [phrase for phrase in ("Evidence checked", "user-report evidence were last checked",
                                     "user-report evidence was last checked",
                                     "when it was last checked", "Check the evidence date")
               if phrase in public_text]
    check("W4 no public text calls the capture date an evidence check", not retired, str(retired))

    print()
    print("=" * 78)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed checks:")
        for e in _ERRORS:
            print(f"  - {e}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2) from None
