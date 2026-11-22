#!/usr/bin/env python3
"""Where a reviewed problem's "fixed in" line is printed, and when it credits the vendor (G95, AUX-132).

G87 (AUX-127) added one line for a supported reviewed reason that names `fixed_in`: "The reviewed problem that
applies <its scope> was fixed in <product> <fixed_in>." Its own rule says it must never read as a recommendation of
that version. It was printed in the way forward, straight after the newer-release note, which names a different,
newer release (OBS 32.1.2 and 32.2.2: "Newer release: OBS Studio 33.0.2", a vendor-documented known issue, "AUXSAYS has
not matched its changes to the reports on this page."). There it read as a recommendation of that release and as a
contradiction of the note, and it did not say where the fact came from. Pinned here:

  [P] placement, rendered with the shipped Liquid through the real patch page (the layout from its top to the compact
      monitoring line, every include resolved): the line prints once, in the verdict box, DIRECTLY AFTER the clause
      of the verdict line that states its own reviewed finding (the verdict line joins every reviewed reason into one
      paragraph; on 32.2.2 a line printed after the whole paragraph sat after the menu-bar crash, another finding),
      and the rest of the verdict line continues beneath it word for word; never in or after the newer-release note
      or the way forward; nothing where there is no fixed_in; byte for byte nothing without a projection row, or
      where the finding cannot be found; only under WAIT; the producer places a line only where its finding ends a
      clause exactly once
  [C] the vendor credit ("<vendor>'s release notes for <fixed_in> record a fix for this problem.") appears ONLY where
      the stored reason carries an official confirmation that names this product and exactly the fixed_in version;
      otherwise the plain G87 sentence; the guard refuses a credit for another version
  [N] no implication: the line never names the newer release, the newer-release note is exactly G87's, nothing calls
      a version safer or recommends one, no fixed string reaches the note's four checked fields, no third caution
  [W] the way forward keeps exactly its G87 variants, and every WAIT page still has one

Offline: synthetic trees, and the shipped corpus read once. The liquid gem renders the real templates.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_fixed_in_placement_g95.py
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from html import unescape
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
SCRIPTS = _AUX / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import yaml  # noqa: E402

from lib import evidence_facts as ef  # noqa: E402
from lib import evidence_overview as eo  # noqa: E402
from lib import patch_decision as pd  # noqa: E402
from lib import verdict_projection as vp  # noqa: E402
from lib import verdict_reasons as vr  # noqa: E402

OBS = "obs-studio"
P3212, P3222, P3301, P3211 = "obs-studio|32.1.2|", "obs-studio|32.2.2|", "obs-studio|33.0.1|", "obs-studio|32.1.1|"
FIX_3212 = ("The reviewed problem that applies if you use connected accounts or service docks on macOS was fixed in "
            "OBS Studio 32.2.0.")
FIX_3222 = "The reviewed problem that applies if you use macOS 27.2 was fixed in OBS Studio 33.0.0."
CREDIT_3212 = "OBS Project's release notes for 32.2.0 record a fix for this problem."
CREDIT_3222 = "OBS Project's release notes for 33.0.0 record a fix for this problem."
FINDING_3212 = "Also TEST FIRST if you use connected accounts or service docks on macOS: "
FINDING_3222 = "Also WAIT if you use macOS 27.2: "
NEWER_NOTE = ("Newer release: OBS Studio 33.0.2 (released Nov 20, 2026). OBS Project has documented a known issue "
              "affecting this version. Review the official release notes before upgrading. AUXSAYS has not established "
              "an installation verdict for this release. AUXSAYS has not matched its changes to the reports on this "
              "page. See its AUXSAYS page and its official release notes.")
G95_BLOCK = re.compile(r"\n[ \t]*\{%- comment -%\}\n[ \t]*THE REVIEWED FIX \(G95.*?\{%- endif -%\}(?=\n[ \t]*<div id=\"verdict\")",
                       re.S)
G95_TAIL = '<p class="update-decision-recommendation">{{ decision_body }}</p>{{ dfx_tail }}'
CUT = "{% include monitoring-status.html mode='compact'"
REASON_3212 = "obs-studio:32.1.2:macos-accounts-and-docks-lost"
REASON_3222 = "obs-studio:32.2.2:macos-27-2-launch-crash"
REASON_MENU = "obs-studio:32.2.2:macos-27-menu-bar-icon-crash"
VERDICT_LINE = "update-decision-recommendation"

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


# ------------------------------------------------------------------------------------------------ rendering

_RENDER_RB = r"""
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
    out[name] = tpl.render!({ "site" => payload["sites"][c["site"]], "page" => c["page"], "item" => c["page"] },
                            registers: { include_root: payload["includes"] })
  rescue => e
    out[name] = "<<ERR #{e.class}: #{e.message}>>"
  end
end
File.write(ARGV[1], JSON.generate(out), encoding: "utf-8")
"""


def render(cases: dict, sites: dict) -> dict:
    """Each case {template, page, site-name} through the liquid gem, includes resolved from the shipped _includes."""
    ruby = shutil.which("ruby")
    if not ruby:
        return {"__error__": "ruby is not on PATH"}
    with tempfile.TemporaryDirectory() as td:
        script, payload, out = Path(td) / "r.rb", Path(td) / "p.json", Path(td) / "o.json"
        script.write_text(_RENDER_RB, encoding="utf-8")
        payload.write_text(json.dumps({"cases": cases, "sites": sites, "includes": str(_AUX / "_includes")},
                                      default=str), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload), str(out)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=900)
        if proc.returncode != 0 or not out.exists():
            return {"__error__": (proc.stderr or "")[-400:]}
        return json.loads(out.read_text(encoding="utf-8"))


def page_head(layout: str) -> str:
    """The patch page from the top of the layout to the compact monitoring line: the verdict box, the evidence card,
    the newer-release note and the way forward, with every include they use."""
    body = layout.split("---", 2)[2]
    return body[:body.index(CUT)]


def text_of(html: str) -> str:
    """The reader's text: tags dropped, entities decoded, whitespace collapsed (no space left before a full stop
    that followed a closing tag)."""
    text = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html or ""))).strip()
    return re.sub(r" ([.,;:])", r"\1", text)


def box_of(html: str) -> str:
    """The verdict box's header: from id="verdict" to its reasoning block."""
    start = html.find('id="verdict"')
    end = html.find('class="update-decision-reasoning"', start)
    return html[start:end] if start >= 0 and end > start else ""


def after_newer(html: str) -> str:
    """Everything from the newer-release note to the end of the rendered head (the note, the way forward)."""
    i = html.find('class="update-evidence-freshness-notice update-newer-release"')
    return html[i:] if i >= 0 else ""


def aside(html: str, cls: str) -> str:
    m = re.search(r'<aside class="update-evidence-freshness-notice ' + re.escape(cls) + r'".*?</aside>', html, re.S)
    return m.group(0) if m else ""


def paragraphs(html: str) -> list[tuple[str, str]]:
    """(class, text) of each <p> in order."""
    return [(m.group(1) or "", text_of(m.group(2)))
            for m in re.finditer(r'<p(?: class="([^"]*)")?[^>]*>(.*?)</p>', html, re.S)]


def without_g95(head: str) -> str:
    """The page head with the G95 block and its output removed: what the layout printed before G95."""
    out = G95_BLOCK.sub("", head, count=1)
    return out.replace(G95_TAIL, '<p class="update-decision-recommendation">{{ decision_body }}</p>', 1)


def clause(entry: dict) -> str:
    """The clause of a volume-based verdict line that states a reviewed finding (patch_decision.public_body)."""
    return text_of(f"Also {entry.get('verdict')} {entry.get('scope')}: {entry.get('reason')}")


def verdict_paras(box: str) -> list[tuple[str, str]]:
    """The verdict line's paragraphs and the fixed lines between them, in order (the provenance, panel and actions
    that follow are not part of it)."""
    return [(c, s) for c, s in paragraphs(box) if c.startswith(VERDICT_LINE) or c == "update-decision-fixed"]


def own_finding_problems(box: str, findings: dict[str, str]) -> list[str]:
    """Every fixed paragraph must come directly after a verdict-line paragraph that ENDS with its own finding
    (`findings`: fixed line -> the text that states its finding), with nothing between them."""
    problems, paras = [], verdict_paras(box)
    for i, (cls, text) in enumerate(paras):
        if cls != "update-decision-fixed":
            continue
        before = paras[i - 1] if i else ("", "")
        want = findings.get(text)
        if not want or not before[0].startswith(VERDICT_LINE) or not before[1].endswith(want):
            problems.append(f"{text[:70]!r} follows {before[1][-90:]!r}")
    return problems


# ------------------------------------------------------------------------------------------------ fixtures

def vrow(i: int, *, version: str, pid: str = OBS) -> dict:
    r = {"id": f"{pid}-{version}-g95-{i}", "product_id": pid, "update_version": version,
         "source_type": "github_issue", "source_url": f"https://reports.test/{pid}/{version}/{i}",
         "report_title": f"Synthetic report {i} (G95)", "report_text_excerpt": f"Synthetic report number {i}.",
         "captured_at": "2026-11-01T00:00:00Z", "source_date": "2026-10-30", "sentiment": "negative",
         "severity": "medium", "issue_theme": "unspecified issue", "counted": True, "patch_version_matched": True,
         "source_weight": 1}
    return ef.with_facts(r)


def rec(version: str, *, pid: str = OBS, **over) -> dict:
    r = {"product_id": pid, "update_version": version, "update_product": "OBS Studio" if pid == OBS else pid,
         "update_entry": True, "update_status": "current", "update_report_count": 2,
         "update_published_at": "2026-10-01T00:00:00Z", "evidence_state": "pilot_sample",
         "update_source_name": "OBS Project", "permalink": f"/updates/t/{pid}/{version.replace('.', '-')}/"}
    r.update(over)
    return r


def wait_entry(eid: str, version: str, *, fixed_in: str, conf: dict | None = None, cite=(1, 2)) -> dict:
    e = {"id": eid, "product_id": OBS, "update_version": version, "verdict": "WAIT", "reason_class": "regression",
         "scope": f"if you use the {eid} setup", "reason": f"Two users report that the {eid} setup fails.",
         "evidence": [{"id": f"{OBS}-{version}-g95-{i}", "source_url": f"https://reports.test/{OBS}/{version}/{i}"}
                      for i in cite],
         "transition": {"working": "79.0.0", "failing": version}, "material": "it does not start",
         "new_in_this_version": True, "fixed_in": fixed_in, "reviewed_at": "2026-11-22", "basis": "G95 test"}
    if conf is not None:
        e["official_confirmation"] = conf
    return e


def credit_tree():
    """Five pages that each print a reviewed WAIT naming fixed_in, differing only in the official confirmation."""
    notes = "- Fixed the synthetic setup failure [dev]\n"
    records = [rec("80.0.0"), rec("81.0.0"), rec("82.0.0"), rec("83.0.0"), rec("84.0.0"),
               rec("80.0.5", official_patch_notes_body=notes, update_published_at="2026-10-05T00:00:00Z"),
               rec("80.0.6", official_patch_notes_body=notes, update_published_at="2026-10-06T00:00:00Z"),
               rec("84.0.5", official_patch_notes_body=notes, update_published_at="2026-10-07T00:00:00Z",
                   update_source_name=""),
               rec("1.0.0", pid="other-tool", official_patch_notes_body=notes, update_source_name="Other Vendor")]
    statement = "Fixed the synthetic setup failure"
    entries = [
        wait_entry("equal", "80.0.0", fixed_in="80.0.5",
                   conf={"product_id": OBS, "update_version": "80.0.5", "statement": statement}),
        wait_entry("otherver", "81.0.0", fixed_in="80.0.5",
                   conf={"product_id": OBS, "update_version": "80.0.6", "statement": statement}),
        wait_entry("noconf", "82.0.0", fixed_in="80.0.5"),
        wait_entry("otherprod", "83.0.0", fixed_in="1.0.0",
                   conf={"product_id": "other-tool", "update_version": "1.0.0", "statement": statement}),
        wait_entry("noname", "84.0.0", fixed_in="84.0.5",
                   conf={"product_id": OBS, "update_version": "84.0.5", "statement": statement}),
    ]
    groups = {(OBS, v, ""): [vrow(i, version=v) for i in (1, 2)]
              for v in ("80.0.0", "81.0.0", "82.0.0", "83.0.0", "84.0.0")}
    verdict, unsupported = vp.project(records, groups, entries, [])
    overview = eo.project(records, groups, verdict["pages"], entries, {}, [])
    return records, entries, verdict, overview, unsupported


def fixed_of(overview: dict, key: str) -> list[str]:
    return list((((overview.get("pages") or {}).get(key) or {}).get("next_action") or {}).get("fixed") or [])


# ------------------------------------------------------------------------------------------------ the corpus

def corpus():
    records, groups = vp.load_inputs(_AUX)
    reasons, lifecycle, problems = vp.load_fact_files(_AUX)
    verdict, _unsupported = vp.project(records, groups, reasons, lifecycle)
    reviewed = eo.load_reviewed(_AUX / "_data" / eo.REVIEWED_NAME)
    overview = eo.project(records, groups, verdict["pages"], reasons, reviewed, eo.split_products_from(_AUX))
    return records, groups, reasons, verdict, overview, problems


def site_for(verdict: dict, overview: dict | None) -> dict:
    data = {name: yaml.safe_load((_AUX / "_data" / f"{name}.yml").read_text(encoding="utf-8"))
            for name in ("patch_verdicts", "patch_products", "patch_companies", "evidence_presentation")}
    data["verdict_projection"] = verdict
    if overview is not None:
        data["evidence_overview_projection"] = overview
    return {"data": data}


# ------------------------------------------------------------------------------------------------ checks

def run() -> int:
    print("=" * 78)
    print("Where a reviewed problem's fixed-in line is printed, and its vendor credit (G95, AUX-132)")
    print("=" * 78)
    records, groups, reasons, verdict, overview, problems = corpus()
    by_key = {vp.page_key(r): r for r in records}
    by_id = {str(e.get("id")): e for e in reasons}
    layout = (_AUX / "_layouts" / "aux-update.html").read_text(encoding="utf-8")
    head = page_head(layout)
    head_without = without_g95(head)
    sites = {"full": site_for(verdict, overview), "none": site_for(verdict, None)}

    def forge(edits: dict) -> dict:
        doc = json.loads(json.dumps(overview))
        for key, nxt in edits.items():
            doc["pages"].setdefault(key, {"url": ""})["next_action"] = nxt
        return doc

    # A row that prints TEST FIRST (32.2.2's menu-bar page is not one; use a reviewed TEST FIRST page) given a fixed
    # line by hand, placed after that page's own finding: only the WAIT gate keeps it out of the verdict box.
    tf_key = next((k for k, row in verdict["pages"].items()
                   if row.get("verdict") == "TEST FIRST" and k in by_key), "")
    tf_reason = str((by_id.get(str(((verdict["pages"].get(tf_key) or {}).get("reasons") or [""])[0])) or {})
                    .get("reason") or "")
    sites["forged"] = site_for(verdict, forge({tf_key: {"kind": "newest", "lines": [eo.NEWEST_LINE],
                                                        "fixed": [FIX_3212], "fixed_after": [tf_reason]}}))
    sites["only_fixed"] = site_for(verdict, forge({P3211: {"kind": "newer_release", "lines": [], "fixed": [FIX_3212],
                                                           "fixed_after": [tf_reason]}}))
    # 32.2.2 with a fixed line for EACH of its two findings (the menu-bar one invented here), in verdict-line order and
    # reversed; and a line whose finding the verdict line does not state, or that names no finding at all.
    reason_a, reason_b = str(by_id[REASON_3222]["reason"]), str(by_id[REASON_MENU]["reason"])
    line_a = f"{FIX_3222} {CREDIT_3222}"
    line_b = "The reviewed problem that applies if you use the menu-bar icon on macOS 27 was fixed in OBS Studio 99.0.0."
    base = {"kind": "newer_release", "lines": []}
    sites["two"] = site_for(verdict, forge({P3222: dict(base, fixed=[line_a, line_b], fixed_after=[reason_a, reason_b])}))
    sites["reversed"] = site_for(verdict, forge({P3222: dict(base, fixed=[line_b, line_a],
                                                             fixed_after=[reason_b, reason_a])}))
    sites["lost"] = site_for(verdict, forge({P3222: dict(base, fixed=[line_a],
                                                         fixed_after=["A finding this verdict line does not state."])}))
    sites["unnamed"] = site_for(verdict, forge({P3222: dict(base, fixed=[line_a])}))
    # A reviewed (not volume-based) WAIT whose HEAD reason names fixed_in: the synthetic credit tree's 80.0.0.
    c_records, entries, c_verdict, c_overview, unsupported = credit_tree()
    sites["credit"] = site_for(c_verdict, c_overview)

    def page(key: str, recs: dict | None = None) -> dict:
        src = (recs if recs is not None else by_key).get(key) or {}
        return dict(src, url=src.get("permalink"))

    cases = {}
    for key in (P3212, P3222, P3301, P3211):
        cases[f"head:{key}"] = {"template": head, "page": page(key), "site": "full"}
        cases[f"without:{key}"] = {"template": head_without, "page": page(key), "site": "full"}
        cases[f"next:{key}"] = {"template": "{% include patch-evidence-overview.html part='next' record=page %}",
                                "page": page(key), "site": "full"}
    cases["norow:with"] = {"template": head, "page": page(P3212), "site": "none"}
    cases["norow:without"] = {"template": head_without, "page": page(P3212), "site": "none"}
    cases["forged:tf"] = {"template": head, "page": page(tf_key), "site": "forged"}
    cases["forged:tf:without"] = {"template": head_without, "page": page(tf_key), "site": "forged"}
    cases["only_fixed:next"] = {"template": "{% include patch-evidence-overview.html part='next' record=page %}",
                                "page": page(P3211), "site": "only_fixed"}
    for name in ("two", "reversed", "lost", "unnamed"):
        cases[f"{name}:{P3222}"] = {"template": head, "page": page(P3222), "site": name}
    c_by_key = {vp.page_key(r): r for r in c_records}
    cases["credit:80"] = {"template": head, "page": page(f"{OBS}|80.0.0|", c_by_key), "site": "credit"}
    out = render(cases, sites)

    section("[P] placement, rendered through the real patch page")
    errs = [k for k, v in out.items() if str(v).startswith("<<ERR")]
    check("P0 the liquid gem renders every case through the shipped layout and includes, and the corpus loads",
          "__error__" not in out and not errs and not problems and len(out) == len(cases)
          and G95_BLOCK.search(head) is not None and head.count(G95_TAIL) == 1,
          str(out.get("__error__") or [out[k][:160] for k in errs[:2]] or problems))
    heads = {k: out.get(f"head:{k}", "") for k in (P3212, P3222, P3301, P3211)}
    want = {P3212: (FIX_3212, CREDIT_3212, FINDING_3212), P3222: (FIX_3222, CREDIT_3222, FINDING_3222)}
    once = {k: (text_of(heads[k]).count(fix), text_of(box_of(heads[k])).count(fix)) for k, (fix, _c, _f) in want.items()}
    check("P1 32.1.2 and 32.2.2: the fixed-in sentence prints exactly once on the page, and that once is in the "
          "verdict box", all(v == (1, 1) for v in once.values()), str(once))
    own = {P3212: clause(by_id[REASON_3212]), P3222: clause(by_id[REASON_3222])}
    placed = {}
    for k, (fix, credit, finding) in want.items():
        paras = verdict_paras(box_of(heads[k]))
        i = next((n for n, (cls, _t) in enumerate(paras) if cls == "update-decision-fixed"), -1)
        before = paras[i - 1] if i > 0 else ("", "")
        after = paras[i + 1] if 0 <= i < len(paras) - 1 else ("", "")
        scope = finding.split(" if ", 1)[-1].rstrip(": ")
        placed[k] = (before[0] == VERDICT_LINE and before[1].endswith(own[k]) and own[k].startswith(finding.strip()),
                     paras[i][1] if i >= 0 else "", f"applies if {scope} was fixed in" in (paras[i][1] if i >= 0 else ""),
                     after)
    check("P2 the text directly before the fixed line is its OWN finding, the whole clause ('Also TEST FIRST if you use "
          "connected accounts or service docks on macOS: ...', 'Also WAIT if you use macOS 27.2: ...'), with nothing "
          "between them and the same scope words; on 32.2.2 the rest of the verdict line, the menu-bar crash ('Also "
          "TEST FIRST if you use the menu-bar icon on macOS 27: ...'), continues BENEATH the line, never before it; "
          "on 32.1.2 the finding ends the verdict line and nothing follows the fixed line",
          placed[P3212][:3] == (True, f"{FIX_3212} {CREDIT_3212}", True) and placed[P3212][3] == ("", "")
          and placed[P3222][:3] == (True, f"{FIX_3222} {CREDIT_3222}", True)
          and placed[P3222][3] == (f"{VERDICT_LINE} update-decision-continued", clause(by_id[REASON_MENU]))
          and not own_finding_problems(box_of(heads[P3222]), {f"{FIX_3222} {CREDIT_3222}": own[P3222]}),
          json.dumps(placed)[:900])
    words = {}
    for k in want:
        line_paras = [t for c, t in paragraphs(box_of(heads[k])) if c.startswith(VERDICT_LINE)]
        exact = [c for c, _t in paragraphs(heads[k]) if c == VERDICT_LINE]
        old = [t for c, t in paragraphs(box_of(out.get(f"without:{k}", ""))) if c.startswith(VERDICT_LINE)]
        words[k] = (" ".join(line_paras) == text_of(verdict["pages"][k]["body"]), len(exact), old == [" ".join(line_paras)])
    check("P3 word for word: the verdict line's paragraphs, read in order, are exactly the verdict projection's line, "
          "the same words the page printed in one paragraph before G95; exactly one paragraph carries the class "
          "attribute 'update-decision-recommendation' alone (the search metadata and the deploy checks read it)",
          all(v == (True, 1, True) for v in words.values()), str(words))
    away = {k: ("was fixed in" in text_of(after_newer(heads[k])), "update-way-forward" in heads[k],
                bool(after_newer(heads[k]))) for k in want}
    check("P4 never in or after the newer-release note: nothing from the note to the compact monitoring line says "
          "'was fixed in', and no way-forward block prints (the note is the way forward and has no lines)",
          all(v == (False, False, True) for v in away.values()), str(away))
    none_311 = heads[P3301]
    archived = aside(heads[P3211], "update-way-forward")
    check("P5 a page with no fixed_in prints no fixed line: 33.0.1 (volume WAIT, newer note) has none anywhere; 32.1.1 "
          "(archived) keeps its G87 way forward 'Other versions: This release is archived. AUXSAYS has not established "
          "a better-supported alternative.' and no fixed line",
          "was fixed in" not in none_311 and "update-decision-fixed" not in none_311 and bool(after_newer(none_311))
          and text_of(archived) == ("Other versions: This release is archived. AUXSAYS has not established a "
                                    "better-supported alternative.")
          and "was fixed in" not in heads[P3211], text_of(archived)[:200])
    same = {k: out.get(f"head:{k}") == out.get(f"without:{k}") for k in (P3301, P3211)}
    check("P6 fail closed, byte for byte: with no projection the page renders identically with and without the G95 "
          "block, and so does every page with no fixed line (33.0.1, 32.1.1)",
          out.get("norow:with") == out.get("norow:without") and "update-decision-fixed" not in out.get("norow:with", "x")
          and all(same.values()) and out.get("norow:with", "") != "", str(same))
    tf_html = out.get("forged:tf", "")
    check("P7 only under a printed WAIT: a forged overview row on a TEST FIRST page whose fixed line names that page's "
          "own finding prints nothing, byte for byte the page without the G95 block",
          bool(tf_key) and bool(tf_reason) and tf_reason in str(verdict["pages"][tf_key].get("body"))
          and "TEST FIRST" in text_of(box_of(tf_html)) and "update-decision-fixed" not in tf_html
          and FIX_3212 not in text_of(tf_html) and tf_html == out.get("forged:tf:without"), tf_key)
    two, rev = box_of(out.get(f"two:{P3222}", "")), box_of(out.get(f"reversed:{P3222}", ""))
    findings = {line_a: clause(by_id[REASON_3222]), line_b: clause(by_id[REASON_MENU])}
    two_fixed = [t for c, t in verdict_paras(two) if c == "update-decision-fixed"]
    rev_fixed = [t for c, t in verdict_paras(rev) if c == "update-decision-fixed"]
    check("P8 two fixed lines on one page each print directly after their OWN finding (32.2.2 with a line invented for "
          "the menu-bar finding), the verdict line still word for word; given in the wrong order, the line whose "
          "finding is already behind it is not printed at all rather than after another finding",
          two_fixed == [line_a, line_b] and not own_finding_problems(two, findings)
          and verdict_paras(two)[-1] == ("update-decision-fixed", line_b)
          and " ".join(t for c, t in verdict_paras(two) if c.startswith(VERDICT_LINE))
          == text_of(verdict["pages"][P3222]["body"])
          and rev_fixed == [line_b] and not own_finding_problems(rev, findings),
          json.dumps({"two": verdict_paras(two), "reversed": verdict_paras(rev)})[:900])
    check("P9 a fixed line whose finding the verdict line does not state, or that names no finding (a projection from "
          "before this rule), prints nothing: the page is byte for byte the page without the G95 block",
          out.get(f"lost:{P3222}") == out.get(f"without:{P3222}") == out.get(f"unnamed:{P3222}")
          and "update-decision-fixed" not in out.get(f"lost:{P3222}", "x"), "")
    c80 = verdict_paras(box_of(out.get("credit:80", "")))
    c80_line = (fixed_of(c_overview, f"{OBS}|80.0.0|") or [""])[0]
    c80_reason = str(entries[0]["reason"])
    check("P10 a reviewed WAIT whose HEAD reason names fixed_in (not volume-based; synthetic, rendered through the real "
          "page): the line prints directly after that reason and before 'Other setups: ...', which continues beneath it",
          c80 == [(VERDICT_LINE, c80_reason), ("update-decision-fixed", c80_line),
                  (f"{VERDICT_LINE} update-decision-continued", text_of(pd.OTHER_SETUPS))]
          and c80_line.startswith("The reviewed problem that applies if you use the equal setup was fixed in"),
          json.dumps(c80)[:600])
    by_identity = {vr.record_identity(r): r for r in c_records}
    e_equal, e_noconf = entries[0], entries[2]
    rec80 = c_by_key[f"{OBS}|80.0.0|"]
    reasons_two = {str(e["id"]): e for e in (e_equal, e_noconf)}
    ra, rb = str(e_equal["reason"]), str(e_noconf["reason"])

    def places(body: str, order=(e_equal, e_noconf)) -> list:
        producer = getattr(eo, "fixed_placements", None)  # absent before G95 round 2: the check fails, not the run
        return producer(rec80, {"reasons": [str(e["id"]) for e in order], "body": body}, reasons_two,
                        by_identity) if producer else [("", "(no fixed_placements)")]
    expected_pairs = {(k, str(by_id[r]["reason"])) for k, row in verdict["pages"].items() if k in by_key
                      if (vp.printed_row(by_key[k], verdict["pages"]) or {}).get("verdict") == "WAIT"
                      for r in row.get("reasons") or [] if (by_id.get(r) or {}).get("fixed_in")}
    got_pairs = {(k, a) for k, row in overview["pages"].items()
                 for a in ((row.get("next_action") or {}).get("fixed_after") or [])}
    check("P11 the producer places a line only where its finding ends a clause exactly once in the verdict line the "
          "gate prints: none when the wording is absent, appears twice, or runs on into other words; in verdict-line "
          "order whatever the reason order; and corpus-wide every supported reviewed fixed_in on a printed WAIT page is "
          "placed after its own finding, none lost",
          [a for _l, a in places(f"{ra} Also WAIT x: {rb}")] == [ra, rb]
          and [a for _l, a in places(f"{ra} Also WAIT x: {rb}", order=(e_noconf, e_equal))] == [ra, rb]
          and [a for _l, a in places(f"Lead. {rb}")] == [rb]
          and [a for _l, a in places(f"{ra} {ra} {rb}")] == [rb]
          and [a for _l, a in places(f"{ra}Also {rb}")] == [rb]
          and eo.fixed_lines(rec80, {"reasons": [str(e_equal["id"])], "body": ra}, reasons_two, by_identity)
          == fixed_of(c_overview, f"{OBS}|80.0.0|")
          and expected_pairs == got_pairs and len(got_pairs) >= 2,
          json.dumps({"want": sorted(expected_pairs), "got": sorted(got_pairs)})[:600])

    section("[C] the vendor credit, only where the official confirmation names fixed_in")
    lines = {k: fixed_of(overview, k) for k in (P3212, P3222)}
    confs = {eid: ((by_id.get(eid) or {}).get("official_confirmation") or {}).get("update_version") ==
             (by_id.get(eid) or {}).get("fixed_in")
             for eid in ("obs-studio:32.1.2:macos-accounts-and-docks-lost", "obs-studio:32.2.2:macos-27-2-launch-crash")}
    rendered = {k: [t for c, t in paragraphs(box_of(heads[k])) if c == "update-decision-fixed"] for k in want}
    check("C1 32.1.2 and 32.2.2: each stored reason carries an official confirmation whose version equals fixed_in, "
          "so the line credits the vendor, and the page prints it",
          all(confs.values()) and len(confs) == 2
          and lines == {P3212: [f"{FIX_3212} {CREDIT_3212}"], P3222: [f"{FIX_3222} {CREDIT_3222}"]}
          and rendered == {P3212: [f"{FIX_3212} {CREDIT_3212}"], P3222: [f"{FIX_3222} {CREDIT_3222}"]},
          json.dumps({"confs": confs, "lines": lines, "rendered": rendered})[:600])
    plain = {v: eo.FIXED_LINE.format(scope=f"if you use the {eid} setup", product="OBS Studio", fixed_in=f)
             for v, eid, f in (("80.0.0", "equal", "80.0.5"), ("81.0.0", "otherver", "80.0.5"),
                               ("82.0.0", "noconf", "80.0.5"), ("83.0.0", "otherprod", "1.0.0"),
                               ("84.0.0", "noname", "84.0.5"))}
    printed = {v: (c_verdict["pages"].get(f"{OBS}|{v}|") or {}).get("verdict") for v in plain}
    check("C2 a confirmation for ANOTHER version than fixed_in: the plain G87 sentence, no credit (the entry is "
          "supported and its page prints WAIT)",
          printed["81.0.0"] == "WAIT" and fixed_of(c_overview, f"{OBS}|81.0.0|") == [plain["81.0.0"]],
          json.dumps({"printed": printed, "fixed": fixed_of(c_overview, f"{OBS}|81.0.0|"), "u": unsupported})[:500])
    check("C3 no official confirmation (two reporters): the plain G87 sentence, no credit",
          printed["82.0.0"] == "WAIT" and fixed_of(c_overview, f"{OBS}|82.0.0|") == [plain["82.0.0"]],
          str(fixed_of(c_overview, f"{OBS}|82.0.0|")))
    check("C4 a confirmation that names another product: the plain G87 sentence, no credit",
          printed["83.0.0"] == "WAIT" and fixed_of(c_overview, f"{OBS}|83.0.0|") == [plain["83.0.0"]],
          str(fixed_of(c_overview, f"{OBS}|83.0.0|")))
    check("C5 a confirmation for exactly fixed_in: credited to the confirming record's own vendor name, or 'The "
          "vendor' where that record names none",
          fixed_of(c_overview, f"{OBS}|80.0.0|")
          == [f"{plain['80.0.0']} OBS Project's release notes for 80.0.5 record a fix for this problem."]
          and fixed_of(c_overview, f"{OBS}|84.0.0|")
          == [f"{plain['84.0.0']} The vendor's release notes for 84.0.5 record a fix for this problem."],
          str([fixed_of(c_overview, f"{OBS}|{v}|") for v in ("80.0.0", "84.0.0")]))
    other = {"kind": "newer_release", "lines": [], "fixed_after": ["Its finding."],
             "fixed": [f"{FIX_3212} OBS Project's release notes for 33.0.2 record a fix for this problem."]}
    clean = [eo.next_action_problems({"kind": "newer_release", "lines": [], "fixed": [line],
                                      "fixed_after": ["Its finding."]})
             for line in (FIX_3212, f"{FIX_3212} {CREDIT_3212}", f"{FIX_3222} {CREDIT_3222}")]
    check("C6 the guard refuses a credit that names another version than the line's fixed_in (here the newer "
          "release, 33.0.2), and accepts the plain and the credited shapes this module writes",
          bool(eo.next_action_problems(other)) and not any(clean)
          and not any(eo.public_text_problems(overview["pages"][k], groups.get(tuple(k.split("|")), []))
                      for k in (P3212, P3222)), str(clean))

    def refused(fixed: list, after) -> bool:
        nxt = {"kind": "newer_release", "lines": [], "fixed": fixed}
        if after is not None:
            nxt["fixed_after"] = after
        return bool(eo.next_action_problems(nxt))
    spaced = f"{FIX_3212} OBS Project's release notes for 27.0 Update 2 record a fix for this problem."
    malformed = f"{FIX_3212} OBS Project release notes for 32.2.0 record a fix for this problem."
    good = f"{FIX_3212} {CREDIT_3212}"
    check("C7 the guard also refuses a credit for another version that has spaces in it ('27.0 Update 2'), a credit "
          "in a shape this module does not write, and a fixed line that names no finding to print it after (none, "
          "an empty one, or a count that differs); the same line with its finding passes",
          refused([spaced], ["Its finding."]) and refused([malformed], ["Its finding."]) and refused([good], None)
          and refused([good], [""]) and refused([good], ["One.", "Two."]) and refused([], ["Stray."])
          and not refused([good], ["Its finding."]) and not refused([], []) and not refused([], None),
          "")

    section("[N] no implication about the newer release; nothing recommended")
    notes = {k: text_of(aside(heads[k], "update-newer-release")) for k in want}
    fixed_paras = {k: " ".join(rendered[k]) for k in want}
    check("N1 the newer-release note is exactly G87's (33.0.2, its date, the vendor's caution, no verdict, not matched, "
          "links), carries no fixed text, and the fixed line names neither OBS Studio 33.0.2 nor 33.0.2",
          all(n == NEWER_NOTE for n in notes.values())
          and all("33.0.2" not in t and "fix" not in notes[k].lower() for k, t in fixed_paras.items()),
          json.dumps({"notes": notes, "fixed": fixed_paras})[:700])
    all_fixed = [s for row in overview["pages"].values() for s in ((row.get("next_action") or {}).get("fixed") or [])]
    recommending = [s for s in all_fixed if eo._RECOMMENDING_RE.search(s)]
    safer = {k: [m.start() for m in re.finditer(r"\bsafer\b", text_of(heads[k]))
                 if "not necessarily safer" not in text_of(heads[k])[max(0, m.start() - 20):m.end()]] for k in want}
    check("N2 no fixed line in the corpus upgrades, installs, recommends or calls anything safer or available, and "
          "neither page calls any version safer",
          all_fixed and not recommending and not any(safer.values()), f"{recommending} {safer}")
    leaked = [(k, f) for k, row in overview["pages"].items() for f in ("caution", "match_note", "fix_source",
                                                                       "verdict_line")
              if any(s in str((row.get("newer") or {}).get(f) or "") for s in ("was fixed in", "record a fix"))]
    cautions = {str((row.get("newer") or {}).get("caution") or "") for row in overview["pages"].values()} - {""}
    third = [c for c in cautions if c != eo.NEWER_NOT_SAFER
             and not (c.endswith(eo.KNOWN_ISSUE_CAUTION) and len(c) > len(eo.KNOWN_ISSUE_CAUTION))]
    check("N3 no fixed or credit string reaches the newer-release note's four checked fields (caution, match_note, "
          "fix_source, verdict_line) on any page, and no third caution string exists",
          not leaked and not third and cautions, f"{leaked[:3]} {third[:3]}")
    crossed = []
    for k, row in overview["pages"].items():
        newer_version = str((row.get("newer") or {}).get("identity") or "").rsplit(" ", 1)[-1]
        for s in (row.get("next_action") or {}).get("fixed") or []:
            m = re.search(r" was fixed in (.+?)\.(?: |$)", s)
            fixed_v = (m.group(1).rsplit(" ", 1)[-1] if m else "")
            if newer_version and newer_version != fixed_v and newer_version in s:
                crossed.append((k, s[:120]))
    check("N4 corpus-wide, a fixed line never names the version its page's newer-release note names (unless that is "
          "the very version the problem was fixed in)", not crossed and all_fixed, str(crossed[:3]))

    section("[W] the way forward keeps its G87 variants")
    kinds = {k: (((overview["pages"].get(k) or {}).get("next_action") or {}).get("kind"),
                 ((overview["pages"].get(k) or {}).get("next_action") or {}).get("lines"))
             for k in (P3212, P3222, P3301, P3211)}
    printed_wait = [k for k, r in by_key.items() if (vp.printed_row(r, verdict["pages"]) or {}).get("verdict") == "WAIT"]
    no_exit = [k for k in printed_wait if not eo.has_next_action(overview["pages"].get(k))]
    bad_guard = [k for k, row in overview["pages"].items()
                 if row.get("next_action") and eo.next_action_problems(row["next_action"])]
    check("W1 32.1.2, 32.2.2 and 33.0.1 keep the newer-release way forward with no lines, 32.1.1 archived with its two; "
          "every page that prints WAIT still has a next action and every next action passes the guard",
          kinds == {P3212: ("newer_release", []), P3222: ("newer_release", []), P3301: ("newer_release", []),
                    P3211: ("archived", [eo.ARCHIVED_LINE, eo.NO_BETTER_ALTERNATIVE])}
          and printed_wait and not no_exit and not bad_guard, json.dumps({"kinds": kinds, "no_exit": no_exit[:3],
                                                                          "guard": bad_guard[:3]})[:500])
    check("W2 the way-forward include prints its lines and never a fixed line: nothing for 32.1.2 and 32.2.2, the "
          "archived lines for 32.1.1, nothing for a row that carries only a fixed line",
          out.get(f"next:{P3212}", "x").strip() == "" and out.get(f"next:{P3222}", "x").strip() == ""
          and text_of(out.get(f"next:{P3211}", "")).startswith("Other versions: This release is archived.")
          and "was fixed in" not in out.get(f"next:{P3211}", "x")
          and out.get("only_fixed:next", "x").strip() == "",
          json.dumps({k: out.get(k, "")[:160] for k in (f"next:{P3212}", "only_fixed:next")}))

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
