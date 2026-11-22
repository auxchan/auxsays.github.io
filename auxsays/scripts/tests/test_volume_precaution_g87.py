#!/usr/bin/env python3
"""The volume-based WAIT precaution and the mandatory way forward (G87, AUX-127).

Owner amendment of 2026-11-21 to the 2026-11-06 verdict policy: a volume-based WAIT precaution at 30 accepted /
30 unique URLs, with a mandatory way forward; owner-approved 2026-11-21; provisional policy constant, not a
statistical claim. `lib/patch_decision.decide` gives a page WAIT, reason code high_report_volume, label
"Volume-based precaution", when its CANONICAL counted population (lib.report_counts.counted_evidence_rows) holds at
least 30 accepted patch-specific reports with at least 30 unique report URLs, on one of the ten products whose
projections the lanes maintain, every row publishable, and no higher-precedence outcome applies. Pinned here:

  [D] the decision: the 29/30 report and URL boundaries (30 reports on 29 URLs fails), duplicate citations, an
      unpublishable row, the ten products (and not DaVinci or any other), maturity, sentiment values and the
      stored count are never inputs; SECURITY UPDATE, an official withdrawal and an official security
      identification outside Windows always win; a reviewed TEST FIRST is superseded but stays visible beneath,
      and a scoped reviewed WAIT stays visible with its own scope and wording; the exact public copy
  [H] collection health is not an input: MONITORING ACTIVE, DEGRADED, BLOCKED and STALE give the same verdict
  [W] an audited withdrawal that drops the page to 29 removes the verdict
  [F] the way forward on every page that prints WAIT (any reason): archived, excluded product, newer release (the
      G83 note, its vendor caution before the links), proven newest (a tie is not proof), not established, and the
      reviewed fixed_in line; newer is never called safer; a TEST FIRST page gets none; where no better-supported
      alternative is established the keep-it advice follows unless the verdict box already gives it (A3 item 3);
      a newer-release note pointing at a volume-WAIT page prints its label, never a bare WAIT (review 1)
  [Q] QA: a page that prints WAIT without a next action is a publication error, and so is one whose rendered way
      forward is not the variant a recompute from the source facts gives or whose newer-release note names a
      stale release (A3 item 2); an empty scope is printed only for the volume-based WAIT, in Python and in the
      Liquid gate alike
  [S] the six decide() call sites over ONE fixture whose stored count is stale: the projection, QA's two, both
      record writers and decision_label all read the canonical counted rows and agree
  [A] a still-valid reviewed finding (OBS 33.0.1's investigated line) keeps its place under a volume WAIT, only
      there, and the universal clause never stands beside a printed verdict
  [C] corpus guard: among the pages measured at G87, exactly OBS Studio 33.0.1, 32.1.1, 32.1.2 and 32.2.2 change
      (to the volume WAIT) and every other verdict is identical; a page that crosses the minimum later may change
      only to an eligible volume WAIT; the four pages' scoped findings, ways forward and regenerated records
  [R] surfaces, rendered with the shipped Liquid: patch page, homepage row, feed card, table row and My Patch Stack
      print the same verdict, label and count; the way forward renders

Offline: synthetic rows, and the shipped corpus read once. The liquid gem renders the real includes.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_volume_precaution_g87.py
"""
from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
SCRIPTS = _AUX / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import yaml  # noqa: E402

import apply_consensus_to_records as acr  # noqa: E402
import build_consensus_from_evidence as bce  # noqa: E402
import qa_patch_records as qa  # noqa: E402
from lib import evidence_facts as ef  # noqa: E402
from lib import evidence_overview as eo  # noqa: E402
from lib import monitoring_health as mh  # noqa: E402
from lib import patch_decision as pd  # noqa: E402
from lib import report_counts  # noqa: E402
from lib import verdict_projection as vp  # noqa: E402
from lib import verdict_reasons as vr  # noqa: E402

OBS, WIN, DAV = "obs-studio", "microsoft-windows-11", "blackmagic-davinci"
LABEL = "Volume-based precaution"
COPY = ("{n} accepted patch-specific problem reports. AUXSAYS recommends delaying this version unless you need its "
        "changes. AUXSAYS recommends waiting because of the volume of accepted problem reports, not because one "
        "widespread defect has been confirmed. These reports do not establish how likely the update is to cause "
        "problems on your system. Next step: If your current version works, consider keeping it while you review "
        "known issues and available alternatives. A newer version is not necessarily safer.")
FOUR = {"obs-studio|33.0.1|", "obs-studio|32.1.1|", "obs-studio|32.1.2|", "obs-studio|32.2.2|"}
# Every page with 30 or more counted rows when G87 was measured (main 4a559ed9 plus the AUX-127 withdrawal).
MEASURED = FOUR | {"blackmagic-davinci|20.3.2|", "blackmagic-davinci|20|", "blackmagic-davinci|21|",
                   "microsoft-windows-11|25H2|26200.7462", "microsoft-windows-11|25H2|26200.7623",
                   "microsoft-windows-11|25H2|26200.7840", "microsoft-windows-11|26H2|26300.9974"}
OBS_ASSESSED_SHA = "873413edf42dab6a4f93623768bbc1c7dff893cd4f5b6ae901286a245a21b966"
FINDING = "No individual problem was independently corroborated in the available evidence."

PASS = FAIL = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  -- {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n{title}")


# ------------------------------------------------------------------------------------------------ fixtures

def vrow(i: int, *, pid: str = OBS, version: str = "99.0.0", url: str | None = None, **over) -> dict:
    """One counted, publishable row as the store holds it (facts computed at the persistence boundary)."""
    r = {"id": f"{pid}-{version}-vol-{i}", "product_id": pid, "update_version": version,
         "source_type": "github_issue", "source_url": url or f"https://reports.test/{pid}/{version}/{i}",
         "report_title": f"Synthetic report {i} (G87)", "report_text_excerpt": f"Synthetic report number {i}.",
         "captured_at": "2026-11-01T00:00:00Z", "source_date": "2026-10-30", "sentiment": "negative",
         "severity": "medium", "issue_theme": "unspecified issue", "counted": True, "patch_version_matched": True,
         "source_weight": 1}
    r.update(over)
    return ef.with_facts(r)


def rows(n: int, **kw) -> list[dict]:
    return [vrow(i, **kw) for i in range(1, n + 1)]


def rec(version: str = "99.0.0", *, pid: str = OBS, **over) -> dict:
    r = {"product_id": pid, "update_version": version, "update_product": "OBS Studio" if pid == OBS else pid,
         "update_entry": True, "update_status": "current", "update_report_count": 3,
         "update_published_at": "2026-10-01T00:00:00Z", "evidence_state": "pilot_sample",
         "permalink": f"/updates/t/{pid}/{version.replace('.', '-')}/"}
    r.update(over)
    return r


def entry(eid: str, verdict: str, rclass: str, version: str, cite=(1, 2), **extra) -> dict:
    e = {"id": eid, "product_id": OBS, "update_version": version, "verdict": verdict, "reason_class": rclass,
         "scope": "if you use the test setup" if verdict == "TEST FIRST" else "if you use the other test setup",
         "reason": f"Two users independently report that the {eid} setup fails.",
         "evidence": [{"id": f"{OBS}-{version}-vol-{i}", "source_url": f"https://reports.test/{OBS}/{version}/{i}"}
                      for i in cite],
         "new_in_this_version": rclass == "regression", "reviewed_at": "2026-11-21", "basis": "G87 test"}
    if verdict == "WAIT":
        e.update(transition={"working": "98.0.0", "failing": version}, material="it does not start")
    e.update(extra)
    return e


def decide(record: dict, counted=(), reasons=(), life=()) -> pd.Decision:
    return pd.decide(record, valid_reasons=list(reasons), lifecycle=list(life), counted_rows=list(counted))


def supported(records: list[dict], groups: dict, entries: list[dict]) -> dict:
    by_ident = {vr.record_identity(r): r for r in records}
    return vr.valid_reasons_by_identity(entries, groups, by_ident)[0]


# ------------------------------------------------------------------------------------------------ rendering

_INCLUDE_RB = r"""
require 'liquid'
require 'json'
module Shims
  def relative_url(i) = "/" + i.to_s.sub(%r{\A/}, "")
  def jsonify(i) = JSON.generate(i)
  def where(input, prop, val) = Array(input).select { |x| x.is_a?(Hash) && x[prop].to_s == val.to_s }
end
Liquid::Template.register_filter(Shims)
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
    @params.each { |k, v| vals[k] = (v =~ /\A"(.*)"\z/m || v =~ /\A'(.*)'\z/m) ? $1 : context[v] }
    partial = (context.registers[:cache] ||= {})[path] ||= Liquid::Template.parse(File.read(path, encoding: "utf-8"))
    context.stack { context["include"] = vals; partial.render!(context) }
  end
end
Liquid::Template.register_tag("include", JekyllInclude)
payload = JSON.parse(File.read(ARGV[0], encoding: "utf-8"))
out = {}
payload["cases"].each do |name, c|
  begin
    tpl = Liquid::Template.parse(c["template"])
    out[name] = tpl.render!({ "site" => payload["site"], "item" => c["item"], "summary" => c["summary"] },
                            registers: { include_root: payload["includes"] })
  rescue => e
    out[name] = "<<ERR #{e.class}: #{e.message}>>"
  end
end
File.write(ARGV[1], JSON.generate(out), encoding: "utf-8")
"""
_PAGE_RB = r"""
require 'liquid'
require 'json'
module Shims
  def relative_url(i) = "/" + i.to_s.sub(%r{\A/}, "")
  def jsonify(i) = JSON.generate(i)
end
Liquid::Template.register_filter(Shims)
payload = JSON.parse(File.read(ARGV[0], encoding: "utf-8"))
print Liquid::Template.parse(payload['template']).render!('site' => payload['site'])
"""


def render_includes(cases: dict, site: dict, overrides: dict | None = None) -> dict:
    ruby = shutil.which("ruby")
    if not ruby:
        return {"__error__": "ruby is not on PATH"}
    with tempfile.TemporaryDirectory() as td:
        inc = Path(td) / "_includes"
        shutil.copytree(_AUX / "_includes", inc)
        for name, text in (overrides or {}).items():
            (inc / name).write_text(text, encoding="utf-8")
        script, payload, out = Path(td) / "i.rb", Path(td) / "p.json", Path(td) / "o.json"
        script.write_text(_INCLUDE_RB, encoding="utf-8")
        payload.write_text(json.dumps({"cases": cases, "site": site, "includes": str(inc)}, default=str),
                           encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload), str(out)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=600)
        if proc.returncode != 0 or not out.exists():
            return {"__error__": (proc.stderr or "")[-400:]}
        return json.loads(out.read_text(encoding="utf-8"))


def render_stack(records: list[dict], products: list, site_data: dict) -> str:
    """updates/my-stack.md rendered as test_patch_stack_dashboard renders it: the verdict gate and the maturity
    contract inlined against their arguments, every other include stripped."""
    src = (_AUX / "updates" / "my-stack.md").read_text(encoding="utf-8").split("---", 2)[-1]
    maturity = (_AUX / "_includes" / "maturity-state.html").read_text(encoding="utf-8")
    src = re.sub(r"\{%-?\s*include\s+maturity-state\.html\s+record=([\w.]+)\s*-?%\}",
                 lambda m: maturity.replace("include.record", m.group(1)), src)
    gate = (_AUX / "_includes" / "patch-verdict-gate.html").read_text(encoding="utf-8")
    src = re.sub(r"\{%-?\s*include\s+patch-verdict-gate\.html\s+record=([\w.]+)\s+count=([\w.]+)\s*-?%\}",
                 lambda m: gate.replace("include.record", m.group(1)).replace("include.count", m.group(2)), src)
    src = re.sub(r"\{%-?\s*include\s.*?-?%\}", "", src, flags=re.S)
    ruby = shutil.which("ruby")
    if not ruby:
        return "<<RENDER FAILED: ruby is not on PATH>>"
    with tempfile.TemporaryDirectory() as td:
        script, payload = Path(td) / "r.rb", Path(td) / "p.json"
        script.write_text(_PAGE_RB, encoding="utf-8")
        payload.write_text(json.dumps({"template": src, "site": {"data": {"patch_products": products, **site_data},
                                                                  "pages": records}}, default=str), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload)], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=300)
    return proc.stdout if proc.returncode == 0 else f"<<RENDER FAILED: {(proc.stderr or '')[-400:]}>>"


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


# ------------------------------------------------------------------------------------------------ [D]

def check_decision() -> None:
    section("[D] the decision")
    r = rec()
    d30 = decide(r, rows(30))
    check("D1 30 accepted reports on 30 unique URLs: WAIT, rule R3V, reason high_report_volume, the label, no scope, "
          "and the canonical count",
          (d30.verdict, d30.rule, d30.reason_code, d30.label, d30.scope, d30.reports, d30.volume)
          == ("WAIT", "R3V", "high_report_volume", LABEL, "", 30, True), repr((d30.verdict, d30.rule, d30.reports)))
    d29 = decide(r, rows(29))
    check("D2 29 reports: INSUFFICIENT DATA (R5), and the problem names the count",
          (d29.verdict, d29.rule) == ("INSUFFICIENT DATA", "R5")
          and "below_volume_reports:29" in pd.volume_problems(r, rows(29)), repr(d29))
    dup = rows(29) + [vrow(30, url="https://reports.test/obs-studio/99.0.0/1")]
    d_dup = decide(r, dup)
    probs = pd.volume_problems(r, dup)
    check("D3 30 reports on 29 unique URLs fails: below the URL minimum and a duplicate citation",
          d_dup.verdict == "INSUFFICIENT DATA" and "below_volume_unique_urls:29" in probs
          and "duplicate_citation_urls" in probs, str(probs))
    dup31 = rows(30) + [vrow(31, url="https://reports.test/obs-studio/99.0.0/2/")]
    check("D3b 31 reports on 30 unique URLs still fails: one report cited twice (the URL identity is "
          "report_url_key: a trailing slash is the same report)",
          decide(r, dup31).verdict == "INSUFFICIENT DATA"
          and pd.volume_problems(r, dup31) == ["duplicate_citation_urls"], str(pd.volume_problems(r, dup31)))
    bad_date = rows(29) + [vrow(30, source_date_pass=False)]
    bad_sent = rows(29) + [vrow(30, sentiment="furious")]
    check("D4 an unpublishable row (a failed source date, a sentiment outside the vocabulary) refuses it: the "
          "population must pass the live gate's condition (e)",
          decide(r, bad_date).verdict == decide(r, bad_sent).verdict == "INSUFFICIENT DATA"
          and pd.volume_problems(r, bad_date) == ["unpublishable_rows:1"])
    products = sorted(report_counts.CONSENSUS_PROMOTION_PRODUCTS)
    eligible = {p: decide(rec(pid=p), rows(30, pid=p)).verdict for p in products}
    others = {p: decide(rec(pid=p), rows(40, pid=p)).verdict for p in (DAV, "adobe-photoshop", "openai-chatgpt")}
    check("D5 every one of the ten promotion products is eligible, the set is report_counts'; DaVinci and a "
          "non-promotion product are never eligible at any count",
          pd.VOLUME_PRODUCTS == report_counts.CONSENSUS_PROMOTION_PRODUCTS and len(products) == 10
          and set(eligible.values()) == {"WAIT"} and set(others.values()) == {"INSUFFICIENT DATA"}
          and "not_promotion_product" in pd.volume_problems(rec(pid=DAV), rows(40, pid=DAV)),
          f"{eligible} {others}")
    live = dict(evidence_state="consensus_live", consensus_collection_status="consensus_live",
                evidence_state_label="Live consensus", intelligence_stage="consensus_live")
    pilot = dict(evidence_state="pilot_sample", consensus_collection_status="pilot_initial_sample",
                 evidence_state_label="Verified reports", intelligence_stage="pilot")
    check("D6 maturity is not an input: a live and a pilot record decide the same (a record on a promotion product "
          "at pilot maturity is eligible; DaVinci-style pilot-only products are excluded by product, not maturity)",
          decide(rec(**live), rows(30)).verdict == decide(rec(**pilot), rows(30)).verdict == "WAIT")
    sentiments = {s: decide(r, rows(30, sentiment=s)).verdict for s in ("negative", "moderate", "positive")}
    check("D7 a sentiment value never selects: all-negative, all-moderate and all-positive rows decide the same",
          set(sentiments.values()) == {"WAIT"}, str(sentiments))
    stale = {n: decide(rec(update_report_count=n, confirmed_patch_specific_report_count=n), rows(30)) for n in (0, 3, 900)}
    check("D8 the stored count is never read: 0, 3 and 900 stored decide the same, and the line states the canonical 30",
          {d.verdict for d in stale.values()} == {"WAIT"}
          and all(pd.public_body(d, rec(update_report_count=n), n).startswith("30 accepted") for n, d in stale.items())
          and decide(rec(update_report_count=900)).verdict == "INSUFFICIENT DATA")
    win_b = rec("25H2", pid=WIN, target_build="26200.1000", target_kb="KB5000001", update_type="2026-02 B")
    d_sec = decide(win_b, rows(40, pid=WIN, version="25H2"))
    check("D9 SECURITY UPDATE always wins: a monthly security update with 40 accepted reports stays SECURITY UPDATE",
          (d_sec.verdict, d_sec.rule) == ("SECURITY UPDATE", "R2"), repr(d_sec))
    life = [{"id": "life", "product_id": WIN, "kb": "KB5000002", "builds": ["26200.2000"],
             "relationship": "withdrawn_for_new_installs", "replacement_kb": "KB5000003"}]
    win_w = rec("25H2", pid=WIN, target_build="26200.2000", target_kb="KB5000002", update_type="2026-03 D")
    check("D10 an official withdrawal always wins: AVOID for new installations",
          decide(win_w, rows(40, pid=WIN, version="25H2"), life=life).verdict == "AVOID")
    flagged = {k: decide(rec(**{k: v}), rows(40)).verdict
               for k, v in (("security_sensitive", True), ("update_security_sensitive", True),
                            ("official_patch_notes_source_type", "security_advisory"),
                            ("official_source_type", "security_advisory"))}
    check("D11 an official security identification outside Windows always wins: the volume WAIT does not apply "
          "(each of the four stored flags), and the problem says why",
          set(flagged.values()) == {"INSUFFICIENT DATA"}
          and "officially_identified_security_update" in pd.volume_problems(rec(security_sensitive=True), rows(40)),
          str(flagged))
    tf = entry("tf", "TEST FIRST", "corroborated_issue", "99.0.0")
    d_tf = decide(r, rows(30), [tf])
    check("D12 a reviewed TEST FIRST is superseded but stays visible beneath, with its own scope and wording",
          d_tf.volume and [e["id"] for e in d_tf.reasons] == ["tf"]
          and pd.public_body(d_tf, r, 30) == COPY.format(n=30) + f" Also TEST FIRST {tf['scope']}: {tf['reason']}",
          pd.public_body(d_tf, r, 30)[-160:])
    wt = entry("wt", "WAIT", "regression", "99.0.0")
    d_wt = decide(r, rows(30), [tf, wt])
    body = pd.public_body(d_wt, r, 30)
    check("D13 a scoped reviewed WAIT stays visible and unrewritten: printed beneath with its scope and reason "
          "verbatim, most cautionary first; the volume WAIT itself carries no scope",
          d_wt.volume and d_wt.scope == "" and [e["id"] for e in d_wt.reasons] == ["wt", "tf"]
          and body == (COPY.format(n=30) + f" Also WAIT {wt['scope']}: {wt['reason']}"
                       f" Also TEST FIRST {tf['scope']}: {tf['reason']}")
          and pd.OTHER_SETUPS not in body, body[-220:])
    check("D14 below the minimum the reviewed entries decide exactly as before (R3 WAIT, R4 TEST FIRST)",
          (decide(r, rows(29), [tf, wt]).rule, decide(r, rows(29), [tf]).rule) == ("R3", "R4"))
    check("D15 no rows handed in: never a volume WAIT (a caller that passes no population fails closed)",
          decide(r).verdict == "INSUFFICIENT DATA" and pd.decide(r, valid_reasons=[]).verdict == "INSUFFICIENT DATA")
    summary = pd.summary_line(d30, r, 3, identity="OBS Studio 99.0.0")
    check("D16 the exact public copy: the line, the label beside the verdict on every surface (verdict_phrase), and "
          "the stored summary whose lead the shared reader parses as WAIT",
          pd.public_body(d30, r, 3) == COPY.format(n=30) and pd.verdict_phrase(d30) == f"WAIT {LABEL}"
          and summary == f"WAIT {LABEL}: OBS Studio 99.0.0. " + COPY.format(n=30)
          and pd.leading_decision(summary) == "WAIT" and pd.leading_decision("WAIT Volume precaution: x") == "",
          summary[:120])


# ------------------------------------------------------------------------------------------------ [H]

def check_health() -> None:
    section("[H] collection health is not an input")
    import inspect  # noqa: PLC0415
    params = set(inspect.signature(pd.decide).parameters)
    src = inspect.getsource(pd.decide) + inspect.getsource(pd.volume_problems)
    names = [w for w in ("monitoring", "method_health", "evidence_state", "maturity", "consensus_live", "now(")
             if w in src.split('"""')[-1]]
    check("H1 decide takes no health, maturity or clock input, and its code and the volume rule's read none",
          params == {"record", "valid_reasons", "lifecycle", "counted_rows"} and not names, f"{params} {names}")
    now = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
    th = mh.Thresholds(max_age_days=14, min_healthy_families=2)
    base = {"product_id": OBS, "update_version": "99.0.0", "target_build": ""}
    states = {
        mh.MONITORING_ACTIVE: [dict(base, method_id="a", source_type="github_issue", status="success",
                                    last_run="2026-11-20T00:00:00Z"),
                               dict(base, method_id="b", source_type="obs_forum_thread", status="success",
                                    last_run="2026-11-20T00:00:00Z")],
        mh.MONITORING_DEGRADED: [dict(base, method_id="a", source_type="github_issue", status="success",
                                      last_run="2026-11-20T00:00:00Z"),
                                 dict(base, method_id="b", source_type="obs_forum_thread", status="partial",
                                      last_run="2026-11-20T00:00:00Z")],
        mh.COLLECTION_BLOCKED: [dict(base, method_id="a", source_type="github_issue", status="blocked",
                                     last_run="2026-11-20T00:00:00Z")],
        mh.COLLECTION_STALE: [dict(base, method_id="a", source_type="github_issue", status="success",
                                   last_run="2026-10-02T00:00:00Z")],
    }
    reached = {k: mh.ladder(v, published_at="2026-10-01T00:00:00Z", report_count=30, now=now, thresholds=th)
               for k, v in states.items()}
    population = rows(30)
    projections = {}
    for state in states:
        # The maturity a writer would store under that health: live only while monitoring certifies.
        stored = rec(evidence_state="consensus_live" if state == mh.MONITORING_ACTIVE else "pilot_sample")
        projections[state] = vp.project([stored], {("obs-studio", "99.0.0", ""): population}, [], [])[0]["pages"]
    rows_seen = {json.dumps(p, sort_keys=True) for p in projections.values()}
    check("H2 MONITORING ACTIVE, MONITORING DEGRADED, COLLECTION BLOCKED and COLLECTION STALE (each reached by the "
          "shipped ladder) give the same projected row: the volume WAIT",
          reached == {k: k for k in states} and len(rows_seen) == 1
          and (next(iter(projections.values())).get("obs-studio|99.0.0|") or {}).get("verdict") == "WAIT",
          str(reached))


# ------------------------------------------------------------------------------------------------ [W]

def check_withdrawal() -> None:
    section("[W] an audited withdrawal can remove the verdict")
    store = rows(30)
    targets = report_counts.windows_targets_from_front_matter([])
    before = report_counts.counted_evidence_rows(store, windows_targets=targets)
    withdrawn = [dict(store[0], counted=False, exclusion_reason="identity_not_the_subject")] + store[1:]
    after = report_counts.counted_evidence_rows(withdrawn, windows_targets=targets)
    key = ("obs-studio", "99.0.0", "")
    p_before = vp.project([rec()], before, [], [])[0]["pages"]
    p_after = vp.project([rec()], after, [], [])[0]["pages"]
    check("W1 30 counted rows through the count authority: WAIT; one row withdrawn (counted false, a reason): 29, and "
          "the page falls back to INSUFFICIENT DATA with no row in the projection",
          len(before[key]) == 30 and len(after[key]) == 29
          and (p_before.get("obs-studio|99.0.0|") or {}).get("verdict") == "WAIT" and "obs-studio|99.0.0|" not in p_after)


# ------------------------------------------------------------------------------------------------ [F]

def way_forward_tree():
    """Records of three products, their counted rows and reasons, and the two projections over them."""
    obs = [rec("89.0.0", update_status="archived", update_published_at="2025-12-01T00:00:00Z"),
           rec("90.0.0", update_published_at="2026-01-01T00:00:00Z"),
           rec("90.1.0", update_published_at="2026-02-01T00:00:00Z", official_notes_known_issue="declared",
               update_source_name="OBS Project", official_patch_notes_source_url="https://notes.test/90.1.0"),
           rec("88.0.0", update_published_at="2025-11-01T00:00:00Z"),
           rec("87.0.0", update_published_at="2025-10-01T00:00:00Z"),
           rec("86.0.0", update_status="archived", update_published_at="2025-09-01T00:00:00Z")]
    tie = [rec("5.0.0", pid="comfyui", update_published_at="2026-03-01T00:00:00Z"),
           rec("5.0.1", pid="comfyui", update_published_at="2026-03-01T00:00:00Z")]
    win = [rec("25H2", pid=WIN, target_build="26200.4000", target_kb="KB5000009", update_type="2026-03 D",
               update_published_at="2026-03-20T00:00:00Z")]
    records = obs + tie + win
    groups = {("obs-studio", "89.0.0", ""): rows(30, version="89.0.0"),
              ("obs-studio", "90.0.0", ""): rows(30, version="90.0.0"),
              ("obs-studio", "90.1.0", ""): rows(31, version="90.1.0"),
              ("obs-studio", "88.0.0", ""): rows(2, version="88.0.0"),
              ("obs-studio", "87.0.0", ""): rows(2, version="87.0.0"),
              ("obs-studio", "86.0.0", ""): rows(2, version="86.0.0"),
              ("comfyui", "5.0.0", ""): rows(30, pid="comfyui", version="5.0.0"),
              ("microsoft-windows-11", "25H2", "26200.4000"): rows(30, pid=WIN, version="25H2")}
    entries = [entry("fx", "TEST FIRST", "corroborated_issue", "90.0.0", fixed_in="90.0.5"),
               entry("rw", "WAIT", "regression", "88.0.0", fixed_in="88.0.1"),
               entry("tf87", "TEST FIRST", "corroborated_issue", "87.0.0"),
               entry("rw86", "WAIT", "regression", "86.0.0")]
    verdict, _u = vp.project(records, groups, entries, [])
    overview = eo.project(records, groups, verdict["pages"], entries, {}, [])
    return records, groups, entries, verdict, overview


def check_way_forward() -> None:
    section("[F] the way forward on every WAIT")
    records, groups, entries, verdict, overview = way_forward_tree()
    pages, vrows = overview["pages"], verdict["pages"]
    nxt = Missing({k: Missing(v.get("next_action") or {}) for k, v in pages.items()})
    raw = dict(pages)  # the projection rows as written: what production functions are handed
    pages = Missing({k: Missing(v) for k, v in pages.items()})
    vrows = Missing({k: Missing(v) for k, v in vrows.items()})
    check("F1 archived: 'This release is archived.' then no better-supported alternative -- never 'no newer release'",
          nxt["obs-studio|89.0.0|"] == {"kind": "archived", "lines": [eo.ARCHIVED_LINE, eo.NO_BETTER_ALTERNATIVE],
                                        "fixed": []}, str(nxt.get("obs-studio|89.0.0|")))
    check("F2 a product with no newer-release note (Windows 11): no better-supported alternative established",
          vrows["microsoft-windows-11|25H2|26200.4000"]["verdict"] == "WAIT"
          and nxt["microsoft-windows-11|25H2|26200.4000"]["kind"] == "excluded_product"
          and nxt["microsoft-windows-11|25H2|26200.4000"]["lines"] == [eo.NO_BETTER_ALTERNATIVE])
    p90 = pages["obs-studio|90.0.0|"]
    check("F3 a newer release: the G83 note is the next action, unchanged (identity, release date, the vendor's "
          "known-issue caution, its verdict, links), with the reviewed fixed_in line in the reviewed scope",
          nxt["obs-studio|90.0.0|"]["kind"] == "newer_release" and nxt["obs-studio|90.0.0|"]["lines"] == []
          and p90["newer"]["identity"] == "OBS Studio 90.1.0"
          and p90["newer"]["caution"] == "OBS Project" + eo.KNOWN_ISSUE_CAUTION
          and nxt["obs-studio|90.0.0|"]["fixed"]
          == ["The reviewed problem that applies if you use the test setup was fixed in OBS Studio 90.0.5."]
          and eo.has_next_action(raw.get("obs-studio|90.0.0|")), json.dumps(nxt.get("obs-studio|90.0.0|")))
    check("F4 proven newest (the first stable entry of the product's list, nothing released at or after it): no "
          "record of a newer release",
          nxt["obs-studio|90.1.0|"] == {"kind": "newest", "lines": [eo.NEWEST_LINE], "fixed": []})
    check("F5 a tie on the release time is not proof: two same-time releases give 'not established', never newest",
          nxt["comfyui|5.0.0|"]["kind"] == "not_established" and nxt["comfyui|5.0.0|"]["lines"] == [eo.NO_BETTER_ALTERNATIVE]
          and not eo.proven_newest(records[6], eo.product_payload(records[6:8])))
    check("F6 keyed on the printed verdict WAIT of ANY reason: a reviewed scoped WAIT below the volume minimum gets "
          "its way forward and its fixed_in line; a TEST FIRST page gets none",
          vrows["obs-studio|88.0.0|"]["rule"] == "R3" and nxt["obs-studio|88.0.0|"]["kind"] == "newer_release"
          and nxt["obs-studio|88.0.0|"]["fixed"]
          == ["The reviewed problem that applies if you use the other test setup was fixed in OBS Studio 88.0.1."]
          and vrows["obs-studio|87.0.0|"]["verdict"] == "TEST FIRST" and "next_action" not in pages["obs-studio|87.0.0|"])
    strings = []
    for row in raw.values():
        n = row.get("next_action") or {}
        strings += list(n.get("lines") or []) + list(n.get("fixed") or [])
        newer = row.get("newer") or {}
        strings += [str(newer.get(k) or "") for k in ("caution", "verdict_line", "match_note", "fix_source")]
    safer = [s for s in strings if re.search(r"\bsafer\b", s) and "not necessarily safer" not in s]
    guarded = [k for k, row in raw.items() if eo.public_text_problems(row, groups.get(tuple(k.split("|")), []))]
    in_note = [k for k, row in raw.items() for f in ("caution", "match_note", "fix_source", "verdict_line")
               if any(s in str((row.get("newer") or {}).get(f) or "") for s in
                      (eo.ARCHIVED_LINE, eo.NO_BETTER_ALTERNATIVE, eo.NEWEST_LINE, "was fixed in"))]
    check("F7 'safer' is never asserted for a newer release; every row passes the public-text guard; no way-forward "
          "string is written into the newer-release note's four checked fields",
          not safer and not guarded and not in_note and len(strings) > 5, f"{safer} {guarded} {in_note}")
    forged = {"kind": "newest", "lines": [eo.NEWEST_LINE], "fixed": ["Upgrade to OBS Studio 9.0.0, which is safer."]}
    check("F8 the guard refuses a next action this module does not write: an unknown kind, other lines, or a fixed "
          "line that reads as a recommendation",
          bool(eo.next_action_problems(forged)) and bool(eo.next_action_problems({"kind": "upgrade", "lines": []}))
          and bool(eo.next_action_problems({"kind": "newest", "lines": ["Install the newest one."], "fixed": []}))
          and not eo.next_action_problems((raw.get("obs-studio|90.0.0|") or {}).get("next_action") or {"kind": "none"}))
    volume_lines = [nxt[k]["lines"] for k in ("obs-studio|89.0.0|", "microsoft-windows-11|25H2|26200.4000",
                                              "comfyui|5.0.0|")]
    check("F9 where no better-supported alternative is established the way forward ends with 'If your current version "
          "works, consider keeping it.' -- on a reviewed WAIT (archived 86.0.0); never on a volume WAIT, whose verdict "
          "box already says it; the guard accepts it only on those three variants",
          vrows["obs-studio|86.0.0|"]["rule"] == "R3"
          and nxt["obs-studio|86.0.0|"] == {"kind": "archived", "lines": [eo.ARCHIVED_LINE, eo.NO_BETTER_ALTERNATIVE,
                                                                         eo.KEEP_LINE], "fixed": []}
          and eo.KEEP_LINE == "If your current version works, consider keeping it."
          and all(lines and eo.KEEP_LINE not in lines for lines in volume_lines)
          and all(eo.KEEP_ADVICE in vrows[k]["body"] for k in ("obs-studio|89.0.0|", "comfyui|5.0.0|"))
          and not eo.next_action_problems(raw.get("obs-studio|86.0.0|", {}).get("next_action") or {"kind": "none"})
          and bool(eo.next_action_problems({"kind": "newest", "lines": [eo.NEWEST_LINE, eo.KEEP_LINE], "fixed": []})),
          json.dumps({"86": nxt.get("obs-studio|86.0.0|"), "volume": volume_lines})[:400])
    scoped_note = eo.newer_row(records[3], records[4], verdict["pages"], 0) if len(records) > 4 else {}
    site = {"data": {"verdict_projection": verdict, "evidence_overview_projection": overview}}
    item = dict(records[1], url=records[1].get("permalink"))
    note_html = render_includes({"n": {"template": "{% include patch-evidence-overview.html part='newer' record=item %}",
                                       "item": item, "summary": ""}}, site).get("n", "")
    check("F10 a newer-release note pointing at a volume-WAIT page prints its verdict as that page's gate does, with the "
          "label ('AUXSAYS verdict for this release: WAIT Volume-based precaution.'), and the shipped include prints it; "
          "a note pointing at a scoped page keeps the scope",
          vrows["obs-studio|90.1.0|"]["reason_code"] == "high_report_volume"
          and p90["newer"]["verdict_line"] == "AUXSAYS verdict for this release: WAIT Volume-based precaution."
          and pages["obs-studio|88.0.0|"]["newer"]["verdict_line"] == p90["newer"]["verdict_line"]
          and "AUXSAYS verdict for this release: WAIT Volume-based precaution." in text_of(note_html)
          and scoped_note.get("verdict_line") == "AUXSAYS verdict for this release: TEST FIRST if you use the test setup.",
          f"{p90['newer'].get('verdict_line')!r} {scoped_note.get('verdict_line')!r} {text_of(note_html)[:200]!r}")


# ------------------------------------------------------------------------------------------------ [Q]

def write_record(path: Path, data: dict) -> None:
    path.write_text("---\n" + yaml.safe_dump(data, sort_keys=False) + "---\nbody\n", encoding="utf-8")


def qa_tree(tmp: Path, record: dict, population: list[dict], *, verdict_rows=None, overview_rows=None,
            write_overview: bool = True, others=()):
    """A deploy tree QA reads: the record (and `others`, (record, population) pairs), the evidence store, empty fact
    files, and the two projections as the deploy builds them -- `verdict_rows` / `overview_rows` forge a page row."""
    tmp.mkdir(parents=True, exist_ok=True)
    gen = tmp / "gen"
    gen.mkdir(exist_ok=True)
    records = [record] + [r for r, _p in others]
    files = []
    for i, r in enumerate(records):
        write_record(gen / f"r{i}.md", r)
        files.append(gen / f"r{i}.md")
    ev = tmp / "ev.yml"
    store = list(population) + [row for _r, pop in others for row in pop]
    ev.write_text(yaml.safe_dump({"schema_version": 1, "evidence": store}), encoding="utf-8")
    (tmp / "reasons.yml").write_text(yaml.safe_dump({"schema_version": 1, "entries": []}), encoding="utf-8")
    (tmp / "life.yml").write_text(yaml.safe_dump({"schema_version": 1, "entries": []}), encoding="utf-8")
    groups = {vr.record_identity(record): population}
    groups.update({vr.record_identity(r): pop for r, pop in others})
    verdict = vp.project(records, groups, [], [])[0]
    if verdict_rows is not None:
        verdict = dict(verdict, pages=verdict_rows(verdict["pages"]))
    (tmp / "vp.yml").write_text(vp.render(verdict), encoding="utf-8")
    overview = eo.project(records, groups, vp.project(records, groups, [], [])[0]["pages"], [], {}, [])
    if overview_rows is not None:
        overview = dict(overview, pages=overview_rows(overview["pages"]))
    if write_overview:
        (tmp / "eo.yml").write_text(eo.render(overview), encoding="utf-8")
    return files, tmp


QA_PATHS = ("REASONS_PATH", "LIFECYCLE_PATH", "EVIDENCE_PATH", "PROJECTION_PATH", "EVIDENCE_OVERVIEW_PATH",
            "EVIDENCE_PRESENTATION_PATH", "ROOT")


def qa_run(tree, scan: str, **kw):
    files, tmp = tree
    saved = {k: getattr(qa, k) for k in QA_PATHS}
    try:
        qa.REASONS_PATH, qa.LIFECYCLE_PATH, qa.EVIDENCE_PATH = tmp / "reasons.yml", tmp / "life.yml", tmp / "ev.yml"
        qa.PROJECTION_PATH, qa.EVIDENCE_OVERVIEW_PATH = tmp / "vp.yml", tmp / "eo.yml"
        qa.EVIDENCE_PRESENTATION_PATH, qa.ROOT = tmp / "no-presentation.yml", tmp
        errors, warnings = getattr(qa, scan)(files, **kw)
    finally:
        for k, v in saved.items():
            setattr(qa, k, v)
    return {e["code"] for e in errors}, {w["code"] for w in warnings}


def check_qa(tmp: Path) -> None:
    section("[Q] QA and the empty-scope rule")
    population = rows(30, version="77.0.0")
    record = rec("77.0.0", update_report_count=30)
    code = "evidence_overview_wait_without_next_action"
    ok_e, ok_w = qa_run(qa_tree(tmp / "q-ok", record, population), "scan_evidence_overview", publish_strict=True)
    dropped = qa_tree(tmp / "q-drop", record, population,
                      overview_rows=lambda p: {k: {kk: vv for kk, vv in v.items() if kk not in ("next_action", "newer")}
                                               for k, v in p.items()})
    d_e, d_w = qa_run(dropped, "scan_evidence_overview", publish_strict=True)
    gone_e, gone_w = qa_run(qa_tree(tmp / "q-gone", record, population, write_overview=False),
                            "scan_evidence_overview", publish_strict=True)
    promoted, _kept = qa.promote_for_publication([], [{"code": code, "file": "x", "message": "m"}])
    check("Q1 a deploy whose WAIT page carries a next action is clean; the same page with its next action dropped, or "
          "with no overview projection at all, is reported, and --publish-strict makes it an ERROR",
          code not in ok_e | ok_w and code in d_w and code in gone_w and code in qa.PUBLICATION_BLOCKING_CODES
          and [p["code"] for p in promoted] == [code], f"{ok_w} {d_w} {gone_w}")
    vol = vp.project([record], {vr.record_identity(record): population}, [], [])[0]["pages"].get(
        "obs-studio|77.0.0|") or {"verdict": "missing"}
    shapes = {
        "volume, no scope": (dict(vol), True),
        "reviewed WAIT, no scope": (dict(vol, reason_code="", label="", rule="R3"), False),
        "volume code, wrong label": (dict(vol, label="High volume"), False),
        "TEST FIRST, no scope, volume code": (dict(vol, verdict="TEST FIRST"), False),
        "AVOID, no scope, volume code": (dict(vol, verdict="AVOID"), False),
    }
    py = {name: vp.printed_row(record, {"obs-studio|77.0.0|": row}) is not None for name, (row, _ok) in shapes.items()}
    check("Q2 printed_row prints an empty scope only for the volume-based WAIT (reason high_report_volume and its "
          "label); a reviewed WAIT, a TEST FIRST or an AVOID with an empty scope is still refused",
          py == {name: ok for name, (_row, ok) in shapes.items()}, str(py))
    cases = {name: {"template": "{% include patch-verdict-gate.html record=item count=30 %}@@{{ gate_label }}|"
                                "{{ gate_scope }}@@", "item": record, "summary": ""} for name in shapes}
    site_for = {name: {"data": {"verdict_projection": {"schema_version": 1, "pages": {"obs-studio|77.0.0|": row}}}}
                for name, (row, _ok) in shapes.items()}
    got = {}
    for name in shapes:
        out = render_includes({name: cases[name]}, site_for[name])
        m = re.search(r"@@(.*?)\|(.*?)@@", out.get(name, ""), re.S)
        got[name] = (m.group(1).strip(), m.group(2).strip()) if m else (out.get("__error__") or out.get(name, ""))[:120]
    want = {name: (("WAIT", LABEL) if ok else ("INSUFFICIENT DATA", "")) for name, (_row, ok) in shapes.items()}
    check("Q3 the Liquid gate agrees: it prints the volume row with its label in the scope slot and refuses every "
          "other empty-scope row", got == want, str(got))
    mismatch = "evidence_overview_wait_next_action_mismatch"
    alone_key = "obs-studio|77.0.0|"

    def wrong_variant(pages):
        out = copy.deepcopy(pages)
        out[alone_key]["next_action"] = {"kind": "not_established",
                                         "lines": [eo.NO_BETTER_ALTERNATIVE], "fixed": []}
        return out
    truth = (eo.project([record], {vr.record_identity(record): population},
                        vp.project([record], {vr.record_identity(record): population}, [], [])[0]["pages"], [], {}, [])
             ["pages"].get(alone_key) or {}).get("next_action") or {}
    wv_e, wv_w = qa_run(qa_tree(tmp / "q-variant", record, population, overview_rows=wrong_variant),
                        "scan_evidence_overview", publish_strict=True)
    check("Q4 QA recomputes the way forward from the source facts: a lone release is proven newest; a deploy rendering "
          "another variant (not established) still HAS a next action, yet is evidence_overview_wait_next_action_mismatch, "
          "publication-blocking; the true variant is clean",
          truth.get("kind") == "newest" and mismatch not in ok_e | ok_w and mismatch in wv_w
          and code not in wv_w and mismatch in qa.PUBLICATION_BLOCKING_CODES, f"{truth} {wv_w} {ok_w}")
    older = rec("76.0.0", update_report_count=30, update_published_at="2026-09-01T00:00:00Z")
    newer = rec("76.1.0", update_report_count=1, update_published_at="2026-10-01T00:00:00Z")
    older_rows, newer_rows = rows(30, version="76.0.0"), rows(1, version="76.1.0")
    older_key = "obs-studio|76.0.0|"

    def stale_release(pages):
        out = copy.deepcopy(pages)
        out[older_key]["newer"] = dict(out[older_key]["newer"], identity="OBS Studio 76.0.5",
                                       published_at="2026-09-15T00:00:00Z")
        return out
    pair = {"others": [(newer, newer_rows)]}
    good_e, good_w = qa_run(qa_tree(tmp / "q-pair", older, older_rows, **pair), "scan_evidence_overview",
                            publish_strict=True)
    st_e, st_w = qa_run(qa_tree(tmp / "q-stale", older, older_rows, overview_rows=stale_release, **pair),
                        "scan_evidence_overview", publish_strict=True)
    check("Q5 a newer-release note naming a stale release and date (76.0.5, Sep 15) where the source facts name 76.1.0 "
          "is evidence_overview_wait_next_action_mismatch, though the page still prints a note; the true note is clean",
          mismatch not in good_e | good_w and mismatch in st_w and code not in st_w, f"{good_w} {st_w}")


# ------------------------------------------------------------------------------------------------ [S]

def check_call_sites(tmp: Path) -> None:
    section("[S] the six decide() call sites over one fixture")
    version = "66.0.0"
    population = rows(30, version=version)
    stale = rec(version, update_report_count=3, confirmed_patch_specific_report_count=3)
    key = vr.record_identity(stale)
    proj = vp.project([stale], {key: population}, [], [])[0]["pages"].get("obs-studio|66.0.0|") or {}
    s1 = (proj.get("verdict"), proj.get("rule"), proj.get("body", "")[:28])
    check("S1 verdict_projection.project: WAIT R3V, and the line states the canonical 30, not the stale stored 3",
          s1 == ("WAIT", "R3V", "30 accepted patch-specific prob"[:28]), str(s1))
    saved_mh = acr.METHOD_HEALTH_PATH
    acr.METHOD_HEALTH_PATH = Path(__file__).with_name("no-such-method-health.yml")
    try:
        policy, _facts = acr._policy_decision(OBS, version, "", population, dict(stale))
        fields = acr._proposed_record_fields(OBS, version, population, dict(stale, path="updates/generated/x.md"),
                                             "2026-11-01T00:00:00Z", build="")
    finally:
        acr.METHOD_HEALTH_PATH = saved_mh
    check("S2 apply_consensus_to_records (the record writer): WAIT, and the stored label, line and summary say WAIT "
          "with the canonical count",
          policy.volume and fields.get("update_decision_label") == "WAIT"
          and str(fields.get("update_decision_body") or "").startswith("30 accepted patch-specific problem reports.")
          and str(fields.get("update_consensus_summary") or "").startswith(f"WAIT {LABEL}: "),
          str({k: str(fields.get(k))[:60] for k in ("update_decision_label", "update_consensus_summary")}))
    b_policy, _bf = bce.policy_decision(OBS, version, "", population, dict(stale), {})
    summary = bce.consensus_summary(OBS, version, population, None, None, "", "current", dict(stale), {})
    check("S3 build_consensus_from_evidence (the aggregate writer): WAIT, and its summary is the record writer's",
          b_policy.volume and summary == fields.get("update_consensus_summary"), summary[:100])
    check("S4 decision_label reads counted_rows, never its count argument: 30 rows with a stale count of 3 is WAIT; "
          "29 rows with a count of 500 is INSUFFICIENT DATA",
          pd.decision_label(OBS, version, "negative", 3, record=dict(stale), counted_rows=population) == "WAIT"
          and pd.decision_label(OBS, version, "negative", 500, record=dict(stale),
                                counted_rows=population[:29]) == "INSUFFICIENT DATA")
    agreeing = dict(stale, update_report_count=30, update_decision_label="WAIT",
                    update_consensus_summary=pd.summary_line(policy, stale, 30, identity=f"OBS Studio {version}"))
    a_err, a_warn = qa_run(qa_tree(tmp / "s-agree", agreeing, population), "scan_verdict_policy")
    missing = qa_tree(tmp / "s-missing", agreeing, population, verdict_rows=lambda p: {})
    m_err, _m_warn = qa_run(missing, "scan_verdict_policy")
    lagging = dict(agreeing, update_decision_label="INSUFFICIENT DATA",
                   update_consensus_summary=f"INSUFFICIENT DATA: OBS Studio {version}. An old line.")
    l_err, l_warn = qa_run(qa_tree(tmp / "s-lag", lagging, population), "scan_verdict_policy")
    check("S5 qa_patch_records, call site 1 (the rendered verdict against decide): the deploy's volume row agrees; a "
          "projection without it is verdict_render_disagrees -- QA's decide read the canonical rows",
          "verdict_render_disagrees" not in a_err and "verdict_render_disagrees" in m_err, f"{a_err} {m_err}")
    check("S6 qa_patch_records, call site 2 (stored prose against decide): a record storing the volume WAIT is clean; "
          "one storing the old INSUFFICIENT DATA line is verdict_policy_drift",
          "verdict_policy_drift" not in a_warn and "verdict_policy_drift" in l_warn and not l_err - {"verdict_render_disagrees"},
          f"{a_warn} {l_warn} {l_err}")


# ------------------------------------------------------------------------------------------------ [A]

def check_assessment() -> None:
    section("[A] a still-valid reviewed finding under the volume WAIT")
    version = "55.0.0"
    population = rows(30, version=version)
    record = rec(version)
    groups = {vr.record_identity(record): population}
    assessment = {"id": f"{OBS}:{version}:finding", "product_id": OBS, "update_version": version, "target_build": "",
                  "finding": FINDING, "basis": "G87 test", "assessed_reports": 30,
                  "assessed_population_sha256": eo.population_digest(population), "reviewed_at": "2026-11-21"}
    reviewed = {"schema_version": 1, "label_withheld_products": [], "assessments": [assessment]}
    verdict = vp.project([record], groups, [], [])[0]["pages"]
    kept = Missing(eo.project([record], groups, verdict, [], reviewed, [])["pages"]).get(f"obs-studio|{version}|")
    moved_rows = population[:29] + [vrow(31, version=version)]
    moved_groups = {vr.record_identity(record): moved_rows}
    moved = Missing(eo.project([record], moved_groups, vp.project([record], moved_groups, [], [])[0]["pages"], [],
                               reviewed, [])["pages"]).get(f"obs-studio|{version}|")
    other = rec("55.1.0")
    other_groups = {vr.record_identity(other): rows(30, version="55.1.0")}
    elsewhere = Missing(eo.project([other], other_groups, vp.project([other], other_groups, [], [])[0]["pages"], [],
                                   reviewed, [])["pages"]).get("obs-studio|55.1.0|")
    check("A1 the finding keeps its place under a volume WAIT while the population is the assessed one; one report "
          "changed and no clause follows the count; a page without an assessment never gets it, and the universal "
          "clause never stands beside the printed WAIT",
          kept["count_line"] == f"30 accepted patch-specific reports. {FINDING}" and kept["assessment"] == assessment["id"]
          and moved["count_line"] == "30 accepted patch-specific reports." and not moved["assessment"]
          and elsewhere["count_line"] == "30 accepted patch-specific reports."
          and eo.UNIVERSAL_CLAUSE not in kept["count_line"] + moved["count_line"] + elsewhere["count_line"],
          f"{kept.get('count_line')} | {moved.get('count_line')}")


# ------------------------------------------------------------------------------------------------ [C] + [R]

def check_corpus_and_surfaces() -> None:
    section("[C] the shipped corpus")
    records, groups = vp.load_inputs(_AUX)
    reasons, lifecycle, problems = vp.load_fact_files(_AUX)
    valid = vp.supported_reasons(records, groups, reasons)[0]
    projection = vp.project(records, groups, reasons, lifecycle)[0]
    by_key = {vp.page_key(r): r for r in records}
    pre, post = {}, {}
    for key, r in by_key.items():
        ident = vr.record_identity(r)
        pre[key] = pd.decide(r, valid_reasons=valid.get(ident, []), lifecycle=lifecycle)  # the pre-G87 decision
        post[key] = pd.decide(r, valid_reasons=valid.get(ident, []), lifecycle=lifecycle, counted_rows=groups.get(ident, []))
    changed = {k for k in by_key if (pre[k].verdict, pre[k].qualifier) != (post[k].verdict, post[k].qualifier)}
    later = changed - MEASURED
    later_ok = all(post[k].volume and not pd.volume_problems(by_key[k], groups.get(vr.record_identity(by_key[k]), []))
                   for k in later)
    same = all((pre[k].verdict, pre[k].scope, pre[k].rule, [e.get("id") for e in pre[k].reasons])
               == (post[k].verdict, post[k].scope, post[k].rule, [e.get("id") for e in post[k].reasons])
               for k in by_key if k not in changed)
    check("C1 among the pages measured at G87 exactly OBS Studio 33.0.1, 32.1.1, 32.1.2 and 32.2.2 change, each to the "
          "volume WAIT; every other page's verdict, scope, rule and reasons are identical; a page that crosses the "
          "minimum after G87 may change only to an eligible volume WAIT",
          changed & MEASURED == FOUR and all(post[k].volume for k in changed) and same and later_ok and not problems,
          f"changed={sorted(changed)[:8]} later={sorted(later)[:4]}")
    counts = {k: (len(groups.get(tuple(k.split("|")), [])),
                  len({vrow_key(r) for r in groups.get(tuple(k.split("|")), [])})) for k in FOUR}
    b322 = pd.public_body(post["obs-studio|32.2.2|"], by_key["obs-studio|32.2.2|"], 0)
    b312 = pd.public_body(post["obs-studio|32.1.2|"], by_key["obs-studio|32.1.2|"], 0)
    check("C2 the four pages: 30+ counted and 30+ unique URLs; 32.2.2 keeps its macOS 27.2 WAIT and its menu-bar TEST "
          "FIRST beneath, 32.1.2 its reviewed TEST FIRST; 33.0.1 and 32.1.1 carry no reviewed reason; the four Windows "
          "pages stay SECURITY UPDATE and the three DaVinci pages INSUFFICIENT DATA",
          all(n >= 30 and u >= 30 for n, u in counts.values())
          and "Also WAIT if you use macOS 27.2: " in b322 and "Also TEST FIRST if you use the menu-bar icon on macOS 27: " in b322
          and "Also TEST FIRST if you use connected accounts or service docks on macOS: " in b312
          and not post["obs-studio|33.0.1|"].reasons and not post["obs-studio|32.1.1|"].reasons
          and {post[k].verdict for k in MEASURED if k.startswith("microsoft")} == {"SECURITY UPDATE"}
          and {post[k].verdict for k in MEASURED if k.startswith("blackmagic")} == {"INSUFFICIENT DATA"}, str(counts))
    overview = eo.project(records, groups, projection["pages"], reasons,
                          eo.load_reviewed(_AUX / "_data" / eo.REVIEWED_NAME), eo.split_products_from(_AUX))
    printed_wait = [k for k, r in by_key.items()
                    if (vp.printed_row(r, projection["pages"]) or {}).get("verdict") == "WAIT"]
    no_exit = [k for k in printed_wait if not eo.has_next_action(overview["pages"].get(k))]
    kinds = {k: ((overview["pages"].get(k) or {}).get("next_action") or {}).get("kind") for k in FOUR}
    kinds = {k: (v, (((overview["pages"].get(k) or {}).get("next_action") or {}).get("fixed"))) for k, v in kinds.items()}
    check("C3 every page that prints WAIT in this tree has a next action; the four: 33.0.1 the newer release, 32.1.1 "
          "archived, 32.1.2 the newer release plus its reviewed fix in 32.2.0, 32.2.2 the newer release plus its "
          "reviewed fix in 33.0.0 (each credited to OBS Project's release notes for that version, whose official "
          "confirmation the reason cites: G95, AUX-132)",
          printed_wait and not no_exit and kinds["obs-studio|32.1.1|"] == ("archived", [])
          and kinds["obs-studio|33.0.1|"][0] == "newer_release"
          and kinds["obs-studio|32.1.2|"] == ("newer_release", [
              "The reviewed problem that applies if you use connected accounts or service docks on macOS was fixed in "
              "OBS Studio 32.2.0. OBS Project's release notes for 32.2.0 record a fix for this problem."])
          and kinds["obs-studio|32.2.2|"] == ("newer_release", [
              "The reviewed problem that applies if you use macOS 27.2 was fixed in OBS Studio 33.0.0. OBS Project's "
              "release notes for 33.0.0 record a fix for this problem."]),
          f"{no_exit[:3]} {kinds}")
    safer = [k for k, row in overview["pages"].items()
             for s in ([str((row.get("newer") or {}).get(f) or "") for f in ("caution", "verdict_line", "match_note")]
                       + list((row.get("next_action") or {}).get("lines") or [])
                       + list((row.get("next_action") or {}).get("fixed") or []))
             if re.search(r"\bsafer\b", s) and "not necessarily safer" not in s]
    check("C4 no newer-release note and no way-forward line in this tree calls a release safer", not safer, str(safer[:3]))
    obs_rows = groups.get(("obs-studio", "33.0.1", ""), [])
    assessed = [r for r in obs_rows if str(r.get("captured_at") or "") < "2026-11-21T20:00:00Z"]
    replayable = eo.population_digest(assessed) == OBS_ASSESSED_SHA and len(assessed) == 47
    replay_groups = dict(groups)
    replay_groups[("obs-studio", "33.0.1", "")] = assessed
    replay = eo.project(records, replay_groups, vp.project(records, replay_groups, reasons, lifecycle)[0]["pages"],
                        reasons, eo.load_reviewed(_AUX / "_data" / eo.REVIEWED_NAME), eo.split_products_from(_AUX))
    with_finding = sorted(k for k, row in replay["pages"].items() if FINDING in str(row.get("count_line") or ""))
    today = overview["pages"].get("obs-studio|33.0.1|", {})
    check("C5 OBS Studio 33.0.1's investigated line: replayed on the population G82 assessed (the 47 rows captured "
          "before the 2026-11-21 20:4x run) it stands under the volume WAIT, on that page only; with today's 51 rows "
          "(four added since) the reviewed entry no longer applies and no clause follows the count",
          replayable and with_finding == ["obs-studio|33.0.1|"]
          and ((replay["pages"].get("obs-studio|33.0.1|") or {}).get("count_line")
               == f"47 accepted patch-specific reports. {FINDING}")
          and FINDING not in str(today.get("count_line") or "") and eo.UNIVERSAL_CLAUSE not in str(today.get("count_line") or ""),
          f"replayable={replayable} {with_finding} {today.get('count_line')}")
    stored = {k: (by_key[k].get("update_decision_label"), str(by_key[k].get("update_consensus_summary") or "")[:28],
                  int(by_key[k].get("update_report_count") or 0) == len(groups.get(tuple(k.split("|")), [])))
              for k in FOUR}
    check("C6 the four records were regenerated by the repo's writers: label WAIT, summary led by 'WAIT "
          "Volume-based precaution:', stored count equal to the canonical count",
          all(v == ("WAIT", f"WAIT {LABEL}:"[:28], True) for v in stored.values()), str(stored))
    gen = _AUX / "updates" / "generated"
    # Every OBS record, so the official confirmations the reviewed reasons name (33.0.0, 32.2.0) are in hand.
    obs_files = sorted(gen.glob("*obs-studio*.md"))
    four_names = {p.name for p in obs_files if vp.page_key(qa.front_matter(p)) in FOUR}
    saved_projection = qa.PROJECTION_PATH
    try:
        qa.PROJECTION_PATH = gen / "no-deploy-projection.yml"  # no deploy file: QA compares against this tree's
        q_err, q_warn = qa.scan_verdict_policy(obs_files)
    finally:
        qa.PROJECTION_PATH = saved_projection
    codes = {item["code"] for item in q_err + q_warn if Path(str(item.get("file") or "")).name in four_names}
    check("C7 QA's own verdict scan over the OBS records: the four regenerated records draw zero "
          "verdict_render_disagrees and zero verdict_policy_drift",
          len(four_names) == 4 and not ({"verdict_render_disagrees", "verdict_policy_drift"} & codes),
          f"{sorted(four_names)} {sorted(codes)}")

    section("[R] surfaces, rendered with the shipped Liquid")
    patch_verdicts = yaml.safe_load((_AUX / "_data" / "patch_verdicts.yml").read_text(encoding="utf-8"))
    site = {"data": {"verdict_projection": projection, "evidence_overview_projection": overview,
                     "patch_verdicts": patch_verdicts, "patch_lifecycle": {"schema_version": 1, "entries": lifecycle}}}
    layout = (_AUX / "_layouts" / "aux-update.html").read_text(encoding="utf-8")
    box = layout[layout.index("<strong>{{ decision_label }}</strong>"):
                 layout.index('<p class="update-decision-recommendation">{{ decision_body }}</p>')
                 + len('<p class="update-decision-recommendation">{{ decision_body }}</p>')]
    home = (_AUX / "_layouts" / "aux-home.html").read_text(encoding="utf-8")
    span = re.search(r'<span class="home-patch-verdict" data-home-verdict>.*?</span>', home, re.S).group(0)
    pre_t = ("{% assign report_count = item.update_report_count | default: 0 | plus: 0 %}"
             "{% assign report_bearing_count = report_count %}"
             "{%- capture discard -%}{% include patch-evidence-state.html record=item %}"
             "{% include patch-decision.html record=item %}{%- endcapture -%}")
    cases = {}
    for k in sorted(FOUR):
        item = dict(by_key[k], url=by_key[k].get("permalink"))
        cases[f"page:{k}"] = {"template": pre_t + "@@" + box + "@@", "item": item, "summary": ""}
        cases[f"home:{k}"] = {"template": pre_t + "@@" + span + "@@", "item": item, "summary": ""}
        cases[f"feed:{k}"] = {"template": "{% include patch-feed-summary.html item=item summary=summary %}"
                                          "@@{{ feed_summary_line }}@@", "item": item,
                              "summary": str(by_key[k].get("update_consensus_summary") or "")}
        cases[f"row:{k}"] = {"template": "{% include patch-table-row.html item=item %}", "item": item, "summary": ""}
        cases[f"way:{k}"] = {"template": "@@{% include patch-evidence-overview.html part='overview' record=item %}@@"
                                         "{% include patch-evidence-overview.html part='newer' record=item %}@@"
                                         "{% include patch-evidence-overview.html part='next' record=item %}@@",
                             "item": item, "summary": ""}
    out = render_includes(cases, site)
    check("R0 the liquid gem renders every case", "__error__" not in out
          and not any(str(v).startswith("<<ERR") for v in out.values()), str(out.get("__error__") or
                                                                              [v[:120] for v in out.values() if str(v).startswith("<<ERR")][:2]))
    want = {k: (f"WAIT {LABEL}", len(groups.get(tuple(k.split("|")), [])),
                (projection["pages"].get(k) or {}).get("body") or "(no row)") for k in FOUR}
    page_bad, home_bad, feed_bad, row_bad = [], [], [], []
    for k in sorted(FOUR):
        phrase, n, body = want[k]
        page = text_of((re.search(r"@@(.*?)@@", out.get(f"page:{k}", ""), re.S) or [None, ""])[1])
        if page != f"{phrase} {body}" or not body.startswith(f"{n} accepted"):
            page_bad.append((k, page[:100]))
        homeline = text_of((re.search(r"@@(.*?)@@", out.get(f"home:{k}", ""), re.S) or [None, ""])[1])
        if homeline != f"Verdict: {phrase}":
            home_bad.append((k, homeline))
        feed = (re.search(r"@@(.*?)@@", out.get(f"feed:{k}", ""), re.S) or [None, ""])[1]
        if not feed.startswith(f"{phrase}: OBS Studio {k.split('|')[1]}. {n} accepted patch-specific problem reports."):
            feed_bad.append((k, feed[:100]))
        row_html = out.get(f"row:{k}", "")
        cell = text_of((re.search(r'<td data-label="Verdict">(.*?)</td>', row_html, re.S) or [None, ""])[1])
        reports = (re.search(r'data-reports="(\d+)"', row_html) or [None, "-1"])[1]
        if cell != phrase or int(reports) != n:
            row_bad.append((k, cell, reports))
    check("R1 patch page: the verdict box prints 'WAIT', the label beside it and the projection's line, which states "
          "the canonical count", not page_bad, str(page_bad))
    check("R2 homepage row: 'Verdict: WAIT Volume-based precaution'", not home_bad, str(home_bad))
    check("R3 /updates/ feed card: the verdict and label first, the exact patch, then the count and the line",
          not feed_bad, str(feed_bad))
    check("R4 product/vendor table row: the verdict with its label, and the canonical count in the Reports column",
          not row_bad, str(row_bad))
    products = yaml.safe_load((_AUX / "_data" / "patch_products.yml").read_text(encoding="utf-8")) or []
    obs_records = [dict(r, url=str(r.get("permalink") or "")) for r in records if r.get("product_id") == OBS]
    html = render_stack(obs_records, products, {"verdict_projection": projection,
                                                "patch_lifecycle": {"schema_version": 1, "entries": lifecycle}})
    m = re.search(r'<script type="application/json" id="patch-stack-data">(.*?)</script>', html, re.S)
    payload = next((e for e in (json.loads(m.group(1)) if m else []) if e.get("id") == OBS), {})
    recs = {r[0]: r for r in payload.get("recs") or []}
    stack = {v: (recs[v][5], recs[v][12], recs[v][7]) for v in ("33.0.1", "32.1.2", "32.2.2") if v in recs}
    check("R5 My Patch Stack: each volume release carries WAIT, the label and its count (32.1.1 is archived, so it is "
          "in no stack list, as for every archived release)",
          stack == {v: ("WAIT", LABEL, want[f"obs-studio|{v}|"][1]) for v in ("33.0.1", "32.1.2", "32.2.2")}
          and "32.1.1" not in recs, str(stack)[:300] or html[:200])
    way = {k: [text_of(p) for p in out.get(f"way:{k}", "").split("@@")[1:4]] for k in sorted(FOUR)}
    n311, n312, n322 = way["obs-studio|33.0.1|"], way["obs-studio|32.1.1|"], way["obs-studio|32.2.2|"]
    newer = n311[1] if len(n311) > 1 else ""
    check("R6 the way forward renders: 32.1.1 'Other versions: This release is archived. AUXSAYS has not established a "
          "better-supported alternative.'; 33.0.1 the newer-release note with the vendor caution before its links and "
          "nothing else; 32.2.2 the newer note and nothing after it -- its reviewed fix line is printed in the verdict "
          "box, beneath the finding it belongs to, never after a note that names another release (G95, AUX-132)",
          len(n312) == 3 and n312[2] == ("Other versions: This release is archived. AUXSAYS has not established a "
                                         "better-supported alternative.") and n312[1] == ""
          and newer.startswith("Newer release: OBS Studio 33.0.2") and n311[2] == ""
          and newer.index("has documented a known issue") < newer.index("See its AUXSAYS page")
          and len(n322) == 3 and n322[2] == "" and n322[1].startswith("Newer release:")
          and "was fixed in" not in n322[1],
          json.dumps(way)[:600])


class Missing(dict):
    """A mapping whose missing key reads as an empty mapping, so a dropped row fails a named check instead of
    crashing the suite (a crash would hide every later check from a mutant)."""

    def __missing__(self, key):
        return Missing()

    def get(self, key, default=None):
        value = super().get(key, default)
        return Missing(value) if isinstance(value, dict) and not isinstance(value, Missing) else (
            value if value is not None else Missing())


def vrow_key(r: dict) -> str:
    from lib.source_segments import report_url_key  # noqa: PLC0415
    return report_url_key(str(r.get("source_url") or ""))


def run() -> int:
    print("=" * 78)
    print("The volume-based WAIT precaution and the mandatory way forward (G87, AUX-127)")
    print("=" * 78)
    check_decision()
    check_health()
    check_withdrawal()
    check_way_forward()
    with tempfile.TemporaryDirectory(prefix="g87-") as td:
        check_qa(Path(td) / "q")
        check_call_sites(Path(td) / "s")
    check_assessment()
    check_corpus_and_surfaces()
    print()
    for label in FAILURES:
        print(f"  failed: {label}")
    print("=" * 78)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
