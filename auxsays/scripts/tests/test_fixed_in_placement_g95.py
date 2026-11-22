#!/usr/bin/env python3
"""Where a reviewed problem's "fixed in" line is printed, and when it credits the vendor (G95, AUX-132).

G87 (AUX-127) added one line for a supported reviewed reason that names `fixed_in`: "The reviewed problem that
applies <its scope> was fixed in <product> <fixed_in>." Its own rule says it must never read as a recommendation of
that version. It was printed in the way forward, straight after the newer-release note, which names a different,
newer release (OBS 32.1.2 and 32.2.2: "Newer release: OBS Studio 33.0.2", a vendor-documented known issue, "AUXSAYS has
not matched its changes to the reports on this page."). There it read as a recommendation of that release and as a
contradiction of the note, and it did not say where the fact came from. Pinned here:

  [P] placement, rendered with the shipped Liquid through the real patch page (the layout from its top to the compact
      monitoring line, every include resolved): the line prints once, in the verdict box, directly beneath the line
      that states the reviewed finding in the same scope words; never in or after the newer-release note or the way
      forward; nothing where there is no fixed_in; byte for byte nothing without a projection row; only under WAIT
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
G95_BLOCK = re.compile(r"\n[ \t]*\{%- comment -%\}\n[ \t]*THE REVIEWED FIX \(G95.*?\{%- endfor %\}\{% endif %\}", re.S)
CUT = "{% include monitoring-status.html mode='compact'"

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
    layout = (_AUX / "_layouts" / "aux-update.html").read_text(encoding="utf-8")
    head = page_head(layout)
    head_without = G95_BLOCK.sub("", head, count=1)
    sites = {"full": site_for(verdict, overview), "none": site_for(verdict, None)}
    forged = json.loads(json.dumps(overview))
    # A row that prints TEST FIRST (32.2.2's menu-bar page is not one; use a reviewed TEST FIRST page) given a fixed
    # line by hand: the box must not print it, because no WAIT is printed above it.
    tf_key = next((k for k, row in verdict["pages"].items()
                   if row.get("verdict") == "TEST FIRST" and k in by_key), "")
    forged["pages"].setdefault(tf_key, {"url": ""})["next_action"] = {"kind": "newest", "lines": [eo.NEWEST_LINE],
                                                                        "fixed": [FIX_3212]}
    only_fixed = json.loads(json.dumps(overview))
    only_fixed["pages"][P3211]["next_action"] = {"kind": "newer_release", "lines": [], "fixed": [FIX_3212]}
    sites["forged"] = site_for(verdict, forged)
    sites["only_fixed"] = site_for(verdict, only_fixed)

    def page(key: str) -> dict:
        return dict(by_key.get(key) or {}, url=(by_key.get(key) or {}).get("permalink"))

    cases = {}
    for key in (P3212, P3222, P3301, P3211):
        cases[f"head:{key}"] = {"template": head, "page": page(key), "site": "full"}
        cases[f"without:{key}"] = {"template": head_without, "page": page(key), "site": "full"}
        cases[f"next:{key}"] = {"template": "{% include patch-evidence-overview.html part='next' record=page %}",
                                "page": page(key), "site": "full"}
    cases["norow:with"] = {"template": head, "page": page(P3212), "site": "none"}
    cases["norow:without"] = {"template": head_without, "page": page(P3212), "site": "none"}
    cases["forged:tf"] = {"template": head, "page": page(tf_key), "site": "forged"}
    cases["only_fixed:next"] = {"template": "{% include patch-evidence-overview.html part='next' record=page %}",
                                "page": page(P3211), "site": "only_fixed"}
    out = render(cases, sites)

    section("[P] placement, rendered through the real patch page")
    errs = [k for k, v in out.items() if str(v).startswith("<<ERR")]
    check("P0 the liquid gem renders every case through the shipped layout and includes, and the corpus loads",
          "__error__" not in out and not errs and not problems and len(out) == len(cases)
          and G95_BLOCK.search(head) is not None,
          str(out.get("__error__") or [out[k][:160] for k in errs[:2]] or problems))
    heads = {k: out.get(f"head:{k}", "") for k in (P3212, P3222, P3301, P3211)}
    want = {P3212: (FIX_3212, CREDIT_3212, FINDING_3212), P3222: (FIX_3222, CREDIT_3222, FINDING_3222)}
    once = {k: (text_of(heads[k]).count(fix), text_of(box_of(heads[k])).count(fix)) for k, (fix, _c, _f) in want.items()}
    check("P1 32.1.2 and 32.2.2: the fixed-in sentence prints exactly once on the page, and that once is in the "
          "verdict box", all(v == (1, 1) for v in once.values()), str(once))
    attached = {}
    for k, (fix, credit, finding) in want.items():
        paras = paragraphs(box_of(heads[k]))
        i = next((n for n, (cls, _t) in enumerate(paras) if cls == "update-decision-recommendation"), -1)
        nxt = paras[i + 1] if 0 <= i < len(paras) - 1 else ("", "")
        scope = finding[len("Also WAIT "):] if finding.startswith("Also WAIT ") else finding[len("Also TEST FIRST "):]
        scope = scope.rstrip(": ")
        attached[k] = (i >= 0 and finding in paras[i][1], nxt[0], nxt[1].startswith(fix),
                       f"applies {scope} was fixed in" in nxt[1])
    check("P2 it is the paragraph directly beneath the verdict line, and that line states the reviewed finding it "
          "belongs to in the same scope words ('Also TEST FIRST if you use connected accounts or service docks on "
          "macOS: ...', 'Also WAIT if you use macOS 27.2: ...')",
          all(v == (True, "update-decision-fixed", True, True) for v in attached.values()), str(attached))
    away = {k: ("was fixed in" in text_of(after_newer(heads[k])), "update-way-forward" in heads[k],
                bool(after_newer(heads[k]))) for k in want}
    check("P3 never in or after the newer-release note: nothing from the note to the compact monitoring line says "
          "'was fixed in', and no way-forward block prints (the note is the way forward and has no lines)",
          all(v == (False, False, True) for v in away.values()), str(away))
    none_311 = heads[P3301]
    archived = aside(heads[P3211], "update-way-forward")
    check("P4 a page with no fixed_in prints no fixed line: 33.0.1 (volume WAIT, newer note) has none anywhere; 32.1.1 "
          "(archived) keeps its G87 way forward 'Other versions: This release is archived. AUXSAYS has not established "
          "a better-supported alternative.' and no fixed line",
          "was fixed in" not in none_311 and "update-decision-fixed" not in none_311 and bool(after_newer(none_311))
          and text_of(archived) == ("Other versions: This release is archived. AUXSAYS has not established a "
                                    "better-supported alternative.")
          and "was fixed in" not in heads[P3211], text_of(archived)[:200])
    same = {k: out.get(f"head:{k}") == out.get(f"without:{k}") for k in (P3301, P3211)}
    check("P5 fail closed, byte for byte: with no projection the page renders identically with and without the G95 "
          "block, and so does every page with no fixed line (33.0.1, 32.1.1)",
          out.get("norow:with") == out.get("norow:without") and "update-decision-fixed" not in out.get("norow:with", "x")
          and all(same.values()) and out.get("norow:with", "") != "", str(same))
    tf_html = out.get("forged:tf", "")
    check("P6 only under a printed WAIT: a forged overview row that carries a fixed line on a TEST FIRST page prints "
          "nothing in its verdict box",
          bool(tf_key) and "TEST FIRST" in text_of(box_of(tf_html)) and "update-decision-fixed" not in tf_html
          and FIX_3212 not in text_of(tf_html), tf_key)

    section("[C] the vendor credit, only where the official confirmation names fixed_in")
    lines = {k: fixed_of(overview, k) for k in (P3212, P3222)}
    by_id = {str(e.get("id")): e for e in reasons}
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
    c_records, entries, c_verdict, c_overview, unsupported = credit_tree()
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
    other = {"kind": "newer_release", "lines": [],
             "fixed": [f"{FIX_3212} OBS Project's release notes for 33.0.2 record a fix for this problem."]}
    clean = [eo.next_action_problems({"kind": "newer_release", "lines": [], "fixed": [line]})
             for line in (FIX_3212, f"{FIX_3212} {CREDIT_3212}", f"{FIX_3222} {CREDIT_3222}")]
    check("C6 the guard refuses a credit that names another version than the line's fixed_in (here the newer "
          "release, 33.0.2), and accepts the plain and the credited shapes this module writes",
          bool(eo.next_action_problems(other)) and not any(clean)
          and not any(eo.public_text_problems(overview["pages"][k], groups.get(tuple(k.split("|")), []))
                      for k in (P3212, P3222)), str(clean))

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
