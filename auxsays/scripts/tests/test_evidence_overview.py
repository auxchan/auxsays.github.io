#!/usr/bin/env python3
"""The patch page's evidence overview and newer-release note (G82-A, AUX-123).

WHAT IS PINNED, and the mechanism each section protects:

  [R] the reviewed file (_data/evidence_presentation.yml): exactly which products' labels are withheld
      and which page carries a reviewed finding; a malformed entry counts for nothing.
  [C] the count line: "<n> accepted patch-specific reports." plus the universal clause on a page that
      prints no verdict, no clause on a page that prints one, and the reviewed finding
      ONLY while the counted population is exactly the assessed one (self-invalidating).
  [N] the newer release: a port of My Installed Versions' installedState (UPDATE AVAILABLE only),
      run against the SHIPPED JavaScript over every record of the corpus so the two cannot part; the
      newer release's verdict is its page's own, or "not established"; changelog headlines get none,
      and so does Windows 11 (patch_lifecycle.yml's recorded KB applicability hold). Newer is never
      presented as safer (amendment A1): the vendor's known-issue caution when the NEWER record
      declares one (G85's contract: official_notes_known_issue: declared, or Release Health's
      official_known_issues_present: true), else "Newer is not necessarily safer"; never
      "available", "addresses", "fixes" or "resolves".
  [V] vendor fix lines: a complete mechanism, switched OFF because no source's publication permission
      is on record; forced on in memory it extracts and attributes, and the guard refuses unpermitted text.
  [G] the public-text guard: no stored report title or excerpt, no author field, no acceptance or
      threshold wording in any AUXSAYS string the projection writes.
  [F] fail closed: the builder writes an empty projection carrying the error; QA errors on a missing,
      failed, malformed or stale projection and on a malformed reviewed file.
  [T] the templates, rendered with the liquid gem: the include prints the row and nothing without it;
      the layout no longer prints a strength word, withholds labels only for listed products, and keeps
      the include tags where the standalone render harnesses cut; the search description stops tying the
      missing verdict to quantity; pages.yml builds the projection before QA and Jekyll.

The governed count is fixed: corpus-wide properties are ONE check each, so natural runs cannot drift it.
Needs ruby + the liquid gem and node (both run in CI); without them their checks FAIL rather than skip.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_evidence_overview.py
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
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
_SCRIPTS = _AUX / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from lib import evidence_overview as eo  # noqa: E402
from lib import verdict_projection  # noqa: E402

LAYOUT = _AUX / "_layouts" / "aux-update.html"
INCLUDE = _AUX / "_includes" / "patch-evidence-overview.html"
SEARCH_META = _AUX / "_includes" / "patch-search-meta.html"
JS = _AUX / "assets" / "js" / "auxsays.js"
REVIEWED = _AUX / "_data" / "evidence_presentation.yml"
BUILDER = _SCRIPTS / "build_evidence_overview_projection.py"

FINDING = "No individual problem was independently corroborated in the available evidence."
OBS_SHA = "873413edf42dab6a4f93623768bbc1c7dff893cd4f5b6ae901286a245a21b966"

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
        print(f"  FAIL  {label}" + (f"\n        {str(detail)[:600]}" if detail else ""))


def section(title: str) -> None:
    print(f"\n{title}")


# --------------------------------------------------------------------------- fixtures

def rec(version, *, pid="tool", product="Tool", date="2026-10-01T00:00:00Z", build="", status="current",
        platform=None, channel=None, notes="https://vendor.test/notes", body="", n_reports=0):
    r = {"update_entry": True, "product_id": pid, "update_product": product, "update_version": version,
         "update_published_at": date, "update_status": status,
         "permalink": f"/updates/v/{pid}/{str(version).replace(' ', '-').lower()}/{build}".rstrip("/") + "/",
         "official_patch_notes_source_url": notes, "update_source_name": "Vendor",
         "official_patch_notes_body": body, "update_report_count": n_reports}
    if build:
        r["target_build"] = build
    if platform is not None:
        r["official_notes_platform"] = platform
    if channel is not None:
        r["release_channel_label"] = channel
    return r


def row(i, *, pid="tool", version="1.0", source_type="github_issue", title=None, excerpt=None):
    return {"id": f"{pid}-{version}-row-{i}", "product_id": pid, "update_version": version,
            "source_type": source_type, "source_url": f"https://reports.test/{pid}/{version}/{i}",
            "report_title": title or f"synthetic report number {i}",
            "report_text_excerpt": excerpt or f"synthetic excerpt for report number {i}",
            "counted": True, "patch_version_matched": True}


def ident(r):
    return (str(r["product_id"]), str(r["update_version"]), str(r.get("target_build") or ""))


def reviewed_with(assessments=(), withheld=("tool-labels",)):
    return {"schema_version": 1,
            "label_withheld_products": [{"product_id": p, "measured": "m", "basis": "b", "reopen": "r"}
                                        for p in withheld],
            "assessments": list(assessments)}


def assessment_for(r, rows, finding=FINDING):
    return {"id": f"{r['product_id']}:{r['update_version']}:a", "product_id": r["product_id"],
            "update_version": r["update_version"], "target_build": r.get("target_build", ""),
            "finding": finding, "basis": "a reviewed reading", "assessed_reports": len(rows),
            "assessed_population_sha256": eo.population_digest(rows), "reviewed_at": "2026-11-21"}


def project_one(records, groups, verdict_rows=None, reasons=(), reviewed=None, split=()):
    return eo.project(records, groups, verdict_rows or {}, reasons, reviewed or reviewed_with(), split)["pages"]


# --------------------------------------------------------------------------- ruby bridge (shipped templates)

_DRIVER = r"""
require 'liquid'
require 'json'
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
    return "" unless File.exist?(path)
    vals = {}
    @params.each { |k, v| vals[k] = (v =~ /\A"(.*)"\z/m || v =~ /\A'(.*)'\z/m) ? $1 : context[v] }
    partial = (context.registers[:cache] ||= {})[path] ||=
      Liquid::Template.parse(File.read(path, encoding: "utf-8"))
    context.stack { context["include"] = vals; partial.render!(context) }
  end
end
Liquid::Template.register_tag("include", JekyllInclude)
payload = JSON.parse(File.read(ARGV[0], encoding: "utf-8"))
out = {}
payload["cases"].each do |name, c|
  begin
    tpl = Liquid::Template.parse(c["template"])
    out[name] = tpl.render!({ "site" => c["site"], "page" => c["page"], "content" => c["content"] || "" },
                            registers: { include_root: payload["includes"] })
  rescue => e
    out[name] = "<<ERR #{e.class}: #{e.message}>>"
  end
end
File.write(ARGV[1], JSON.generate(out), encoding: "utf-8")
"""


def render_cases(cases: dict, overrides: dict | None = None) -> dict | None:
    """Render {name: {template, site, page}} with the shipped includes (optionally overridden)."""
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    with tempfile.TemporaryDirectory() as td:
        inc = Path(td) / "_includes"
        shutil.copytree(_AUX / "_includes", inc)
        for name, text in (overrides or {}).items():
            (inc / name).write_text(text, encoding="utf-8")
        script, payload, out = Path(td) / "d.rb", Path(td) / "p.json", Path(td) / "o.json"
        script.write_text(_DRIVER, encoding="utf-8")
        payload.write_text(json.dumps({"cases": cases, "includes": str(inc)}, default=str), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload), str(out)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=600)
        if proc.returncode != 0 or not out.exists():
            return {"__error__": (proc.stderr or "")[-400:]}
        return json.loads(out.read_text(encoding="utf-8"))


def layout_body(text: str | None = None) -> str:
    text = LAYOUT.read_text(encoding="utf-8") if text is None else text
    return text.split("---", 2)[-1] if text.startswith("---") else text


def visible(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html or "").split())


# --------------------------------------------------------------------------- JS parity

def js_states(products: dict) -> dict | None:
    """installedState over every record of every product, run in node from the shipped auxsays.js."""
    node = shutil.which("node")
    if not node:
        return None
    src = JS.read_text(encoding="utf-8")
    start, end = src.index("const PATH_LIMIT"), src.index("const paintInstalledControls")
    probe = (src[start:end] + "\nconst PRODUCTS = " + json.dumps(products) + ";\n"
             + "const out = {};\n"
             + "for (const [pid, p] of Object.entries(PRODUCTS)) {\n"
             + "  for (const r of p.recs) {\n"
             + "    const info = installedState({ v: r[0], b: r[1], d: r[2], u: r[3] }, p);\n"
             + "    out[r[3]] = info.state === 'UPDATE AVAILABLE' && info.latest ? info.latest[3] : null;\n"
             + "  }\n"
             + "}\n"
             + "console.log(JSON.stringify(out));\n")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "probe.js"
        path.write_text(probe, encoding="utf-8")
        proc = subprocess.run([node, str(path)], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=600)
    if proc.returncode != 0:
        return {"__error__": proc.stderr[-400:]}
    return json.loads(proc.stdout)


def payload_tuple(r: dict) -> list:
    """My Patch Stack's 14-slot record tuple; installedState reads slots 0-4, 11 and 13 (the release track)."""
    return [eo._ver(r), eo._build(r), eo._date(r), str(r.get("permalink") or ""), 1 if eo._beta(r) else 0,
            "", 0, 0, "", 0, 0, eo._platform(r), "", eo._track(r)]


# =========================================================================== run

def run() -> int:  # noqa: PLR0915
    print("=" * 96)
    print("Evidence overview and newer-release note (G82-A, AUX-123)")
    print("=" * 96)

    # ------------------------------------------------------------------ [R]
    section("[R] the reviewed presentation file")
    reviewed = eo.load_reviewed(REVIEWED)
    check("R1 the shipped reviewed file is valid", eo.reviewed_errors(reviewed) == [],
          eo.reviewed_errors(reviewed))
    check("R2 labels are withheld for exactly the measured products: OBS Studio, Windows 11, Premiere Pro, ComfyUI",
          eo.label_withheld_products(reviewed) == ["obs-studio", "microsoft-windows-11", "adobe-premiere-pro",
                                                   "comfyui"],
          eo.label_withheld_products(reviewed))
    assessments = reviewed.get("assessments") or []
    a0 = assessments[0] if assessments else {}
    check("R3 exactly one reviewed finding: OBS Studio 33.0.1, 47 assessed reports, G82's population, the "
          "approved sentence",
          len(assessments) == 1 and eo.assessment_identity(a0) == ("obs-studio", "33.0.1", "")
          and a0.get("assessed_reports") == 47 and a0.get("assessed_population_sha256") == OBS_SHA
          and a0.get("finding") == FINDING, a0)
    good = reviewed_with([assessment_for(rec("1.0"), [row(1)])])
    bad_key = copy.deepcopy(good)
    bad_key["extra"] = 1
    check("R4a an unknown top-level key is refused", bool(eo.reviewed_errors(bad_key)))
    bad_sha = copy.deepcopy(good)
    bad_sha["assessments"][0]["assessed_population_sha256"] = "abc"
    check("R4b an assessed population that is not a sha256 is refused", bool(eo.reviewed_errors(bad_sha)))
    bad_num = copy.deepcopy(good)
    bad_num["assessments"][0]["finding"] = "No problem among the 47 reports was corroborated."
    check("R4c a finding that names a number is refused", bool(eo.reviewed_errors(bad_num)))
    bad_rule = copy.deepcopy(good)
    bad_rule["assessments"][0]["finding"] = "No problem has at least two reporters."
    check("R4d a finding that states an acceptance rule or threshold is refused", bool(eo.reviewed_errors(bad_rule)))
    dup = reviewed_with([assessment_for(rec("1.0"), [row(1)])], withheld=("x", "x"))
    dup_row = project_one([rec("1.0", n_reports=1)], {ident(rec("1.0")): [row(1)]}, reviewed=dup)
    check("R4e a product listed twice is refused, and a refused file withholds nothing and applies no finding",
          bool(eo.reviewed_errors(dup)) and eo.label_withheld_products(dup) == []
          and dup_row[verdict_projection.page_key(rec("1.0"))]["count_line"].endswith(eo.UNIVERSAL_CLAUSE))
    check("R5 no source's publication permission is on record, so vendor fix lines are OFF everywhere",
          eo.PUBLICATION_PERMITTED_HOSTS == frozenset() and not eo.publication_permitted(
              "https://github.com/obsproject/obs-studio/releases/tag/33.0.2"))

    # ------------------------------------------------------------------ [C]
    section("[C] the count line, the clause and the reviewed finding")
    page = rec("1.0", n_reports=3)
    rows3 = [row(1), row(2), row(3, source_type="obs_forum_thread")]
    groups = {ident(page): rows3}
    p = project_one([page], groups)[verdict_projection.page_key(page)]
    # The approved sentences are pinned as literals (GPT G82 clarification 2): a reworded constant fails
    # here instead of passing because the test reads the same constant.
    check("C1 no supported reason: the count, then the universal clause",
          p["count_line"] == "3 accepted patch-specific reports. No problem-specific installation "
                             "recommendation has been established.", p["count_line"])
    check("C1b and the list is described as not grouped by problem",
          p["limitation"] == "Each report is listed separately below; AUXSAYS has not grouped them by problem.")
    reason = {"id": "tool:1.0:r", "evidence": [{"id": rows3[0]["id"]}, {"id": rows3[1]["id"]}]}
    vrows = {verdict_projection.page_key(page): {"verdict": "TEST FIRST", "scope": "if you use X",
                                                 "body": "line", "reasons": ["tool:1.0:r"]}}
    pr = project_one([page], groups, vrows, [reason])[verdict_projection.page_key(page)]
    orow = {verdict_projection.page_key(page): {"verdict": "AVOID", "scope": "for new installations",
                                                "body": "The vendor withdrew this update.", "reasons": []}}
    po = project_one([page], groups, orow, [], reviewed=reviewed_with([assessment_for(page, rows3)]))[
        verdict_projection.page_key(page)]
    check("C2 a supported reason, or an official verdict, prints no clause and no reviewed finding",
          pr["count_line"] == "3 accepted patch-specific reports."
          and po["count_line"] == "3 accepted patch-specific reports." and not po["assessment"]
          and po["limitation"] == eo.LIMITATION, (pr["count_line"], po))
    check("C2b and the limitation says how many reports the reason cites",
          pr["limitation"].startswith("The reason above cites 2 of them;"), pr["limitation"])
    rev = reviewed_with([assessment_for(page, rows3)])
    pa = project_one([page], groups, reviewed=rev)[verdict_projection.page_key(page)]
    check("C3 the assessed population, unchanged: the reviewed finding replaces the universal clause",
          pa["count_line"] == "3 accepted patch-specific reports. " + FINDING and pa["assessment"], pa)
    grown = {ident(page): rows3 + [row(4)]}
    pg = project_one([page], grown, reviewed=rev)[verdict_projection.page_key(page)]
    check("C4 one report added: the finding stops showing and the universal clause returns",
          pg["count_line"] == "4 accepted patch-specific reports. " + eo.UNIVERSAL_CLAUSE and not pg["assessment"],
          pg["count_line"])
    miscounted = reviewed_with([dict(assessment_for(page, rows3), assessed_reports=4)])
    pm = project_one([page], groups, reviewed=miscounted)[verdict_projection.page_key(page)]
    check("C4b an entry whose assessed size disagrees with the population is not shown, even with the "
          "right digest", pm["count_line"].endswith(eo.UNIVERSAL_CLAUSE) and not pm["assessment"], pm["count_line"])
    swapped = {ident(page): [row(1), row(2), row(9)]}
    ps = project_one([page], swapped, reviewed=rev)[verdict_projection.page_key(page)]
    check("C5 same size, a different report: the universal clause returns (the ids are the identity)",
          ps["count_line"].endswith(eo.UNIVERSAL_CLAUSE), ps["count_line"])
    prr = project_one([page], groups, vrows, [reason], reviewed=rev)[verdict_projection.page_key(page)]
    check("C6 a page with a supported reason never shows a reviewed finding",
          prr["count_line"] == "3 accepted patch-specific reports." and not prr["assessment"], prr)
    one = project_one([rec("1.0", n_reports=1)], {ident(page): [row(1)]})[verdict_projection.page_key(page)]
    check("C7 singular: one accepted patch-specific report",
          one["count_line"].startswith("1 accepted patch-specific report. ") and one["sources_line"] == "Sources: 1 GitHub issue.",
          one)
    fams = eo.sources_sentence(eo.families([row(1), row(2, source_type="github_officedev_issue"),
                                            row(3, source_type="reddit_community_report"),
                                            row(4, source_type="mystery_feed")]))
    check("C8 families: same public family merged, most first, joined with commas and 'and', unknown named generically",
          fams == "Sources: 2 GitHub issues, 1 Reddit post and 1 other public report.", fams)
    check("C8b the families sentence for the fixture page", p["sources_line"] == "Sources: 2 GitHub issues and 1 OBS forum thread.",
          p["sources_line"])
    zero = project_one([rec("1.0")], {})
    check("C9 a zero-report page with no newer release gets no row at all", zero == {}, zero)
    check("C10 the limitation when the reason cites every report, for a single report, and for two reasons",
          eo.limitation_sentence(3, 3, True) == "The reason above cites every one of them."
          and eo.limitation_sentence(1, 1, True) == "The reason above cites this report."
          and eo.limitation_sentence(56, 3, True, 2).startswith("The reasons above cite 3 of them;"))

    # ------------------------------------------------------------------ [N]
    section("[N] the newer release (My Installed Versions' rule, UPDATE AVAILABLE only)")
    recs_obs = [rec("1.0.0", date="2026-10-01T00:00:00Z"), rec("1.0.1", date="2026-10-10T00:00:00Z"),
                rec("1.0.2", date="2026-10-20T00:00:00Z")]
    pay = eo.product_payload(recs_obs)
    tgt = eo.update_available(recs_obs[0], pay, split=False)
    check("N1 a reader on 1.0.0 is pointed at the NEWEST stable release, not the next one",
          tgt is not None and tgt["update_version"] == "1.0.2", tgt and tgt["update_version"])
    check("N1b the newest release has no newer release", eo.update_available(recs_obs[2], pay, split=False) is None)
    with_beta = recs_obs + [rec("1.1.0 beta 1", date="2026-10-25T00:00:00Z")]
    tb = eo.update_available(recs_obs[0], eo.product_payload(with_beta), split=False)
    check("N2 a newer beta is never the target; a stable target past it is still offered",
          tb is not None and tb["update_version"] == "1.0.2", tb and tb["update_version"])
    only_beta = [rec("1.0.0"), rec("1.1 beta", date="2026-10-25T00:00:00Z")]
    check("N2b when the only newer release is a beta, there is no newer-release note",
          eo.update_available(only_beta[0], eo.product_payload(only_beta), split=False) is None)
    beta_reader = [rec("2.0 preview", date="2026-10-01T00:00:00Z"), rec("2.0", date="2026-10-09T00:00:00Z")]
    check("N3 a reader on a beta gets no note (installedState: NEWER TRACKED VERSION EXISTS)",
          eo.update_available(beta_reader[0], eo.product_payload(beta_reader), split=False) is None)
    win = [rec("25H2", build="26200.100", date="2026-10-01T00:00:00Z"),
           rec("26H1", build="28000.200", date="2026-10-20T00:00:00Z"),
           rec("25H2", build="26200.150", date="2026-10-15T00:00:00Z"),
           rec("25H2", build="26200.180", date="2026-10-18T00:00:00Z")]
    tw = eo.update_available(win[0], eo.product_payload(win), split=False)
    check("N4 build-aware: the target is the newest build of the SAME servicing line, never another line",
          tw is not None and tw["target_build"] == "26200.180", tw and tw.get("target_build"))
    check("N4b a newer build on another line alone is no update",
          eo.update_available(win[3], eo.product_payload(win), split=False) is None)
    same_day = [rec("3.0", date="2026-10-01T10:00:00Z"), rec("3.1", date="2026-10-01T18:00:00Z")]
    check("N5 a same-day sibling is never a step (no recorded order)",
          eo.update_available(same_day[0], eo.product_payload(same_day), split=False) is None)
    arch = [rec("1.0", status="archived"), rec("1.1", date="2026-10-09T00:00:00Z")]
    arch2 = [rec("1.0"), rec("1.1", date="2026-10-09T00:00:00Z", status="archived")]
    check("N6 an archived reader gets no note, and an archived release is never a target",
          eo.update_available(arch[0], eo.product_payload(arch), split=False) is None
          and eo.update_available(arch2[0], eo.product_payload(arch2), split=False) is None)
    plat = [rec("3.2.10", platform="windows", date="2026-08-05T00:00:00Z"),
            rec("2.0.9", platform="macos", date="2026-08-12T00:00:00Z"),
            rec("3.5", platform="windows_macos", date="2026-11-11T00:00:00Z")]
    tp = eo.update_available(plat[0], eo.product_payload(plat), split=True)
    check("N7 per-platform notes: a later release for another platform is never the target; one covering "
          "both platforms with a greater version is",
          tp is not None and tp["update_version"] == "3.5"
          and eo.update_available(plat[1], eo.product_payload(plat), split=True) is not None
          and eo.update_available(plat[0], eo.product_payload(plat[:2]), split=True) is None,
          tp and tp["update_version"])
    heads = [rec("Preview what's inside folders", pid="figma", date="2026-10-01T00:00:00Z"),
             rec("Reusable kits", pid="figma", date="2026-10-09T00:00:00Z")]
    hp = project_one(heads, {})
    check("N8 a changelog headline is not a version: no newer-release note", hp == {}, hp)
    npg = project_one(recs_obs, {})
    first = npg.get(verdict_projection.page_key(recs_obs[0]), {}).get("newer") or {}
    # The approved sentences are pinned as literals (A1; GPT G85 ruling Q2), never read from the constants.
    check("N9 the newer release with no verdict says AUXSAYS has not established one, and links its page and "
          "official notes",
          first.get("verdict_line") == "AUXSAYS has not established an installation verdict for this release."
          and first.get("url") == recs_obs[2]["permalink"]
          and first.get("notes_url") == "https://vendor.test/notes" and first.get("identity") == "Tool 1.0.2", first)
    vrow = {verdict_projection.page_key(recs_obs[2]): {"verdict": "WAIT", "scope": "if you use the test dock",
                                                         "body": "Users report a crash.", "reasons": ["x"]}}
    wv = project_one(recs_obs, {}, vrow)[verdict_projection.page_key(recs_obs[0])]["newer"]
    svrow = {verdict_projection.page_key(recs_obs[2]): {"verdict": "SECURITY UPDATE", "scope": "",
                                                          "body": "Security update.", "reasons": []}}
    sv = project_one(recs_obs, {}, svrow)[verdict_projection.page_key(recs_obs[0])]["newer"]
    check("N9b the verdict sentence follows the verdict projection: a newer release WITH a printed verdict states "
          "exactly that verdict (never a hard-coded 'no verdict')",
          wv["verdict_line"] == "AUXSAYS verdict for this release: WAIT if you use the test dock."
          and sv["verdict_line"] == "AUXSAYS verdict for this release: SECURITY UPDATE.", (wv["verdict_line"], sv))
    key0 = verdict_projection.page_key(recs_obs[0])
    declared = recs_obs[:2] + [dict(recs_obs[2], official_notes_known_issue="declared")]
    nd = project_one(declared, {})
    unnamed = recs_obs[:2] + [dict(recs_obs[2], official_notes_known_issue="declared", update_source_name="")]
    nu = project_one(unnamed, {})[key0]["newer"]
    check("N13 the NEWER record declares a known issue in its release notes (official_notes_known_issue: declared): "
          "the vendor's caution, on every page that points to it",
          nd[key0]["newer"]["caution"] == "Vendor has documented a known issue affecting this version. Review the "
                                          "official release notes before upgrading."
          and nd[key0]["newer"]["known_issue"] is True
          and nd[verdict_projection.page_key(recs_obs[1])]["newer"]["known_issue"] is True
          and nu["caution"] == "The vendor has documented a known issue affecting this version. Review the official "
                               "release notes before upgrading.", (nd.get(key0), nu))
    not_safer = ("Newer is not necessarily safer. Check its official release notes, including any known issues, "
                 "before upgrading.")
    plain = first
    others = [project_one(recs_obs[:2] + [dict(recs_obs[2], official_notes_known_issue=v)], {})[key0]["newer"]
              for v in ("not_declared", "unknown", "Declared", True, "")]
    reader_only = project_one([dict(recs_obs[0], official_notes_known_issue="declared")] + recs_obs[1:], {})[key0]["newer"]
    check("N14 with the field removed (or any other value, or set only on the reader's own page) the caution is "
          "gone and the note says newer is not necessarily safer",
          plain.get("caution") == not_safer and plain.get("known_issue") is False
          and all(o["caution"] == not_safer and o["known_issue"] is False for o in others)
          and reader_only["caution"] == not_safer, (plain, [o["caution"] for o in others], reader_only["caution"]))
    rh = project_one(recs_obs[:2] + [dict(recs_obs[2], official_known_issues_present=True)], {})[key0]["newer"]
    rh_false = project_one(recs_obs[:2] + [dict(recs_obs[2], official_known_issues_present=False)], {})[key0]["newer"]
    check("N15 Release Health's official_known_issues_present: true on the NEWER record gives the vendor's caution "
          "(a synthetic non-Windows record, since Windows 11 gets no note); false gives none",
          rh["caution"] == "Vendor has documented a known issue affecting this version. Review the official release "
                           "notes before upgrading." and rh["known_issue"] is True
          and rh_false["caution"] == not_safer and rh_false["known_issue"] is False, (rh, rh_false))
    reports_here = project_one([rec("1.0.0", n_reports=2)] + recs_obs[1:], {ident(recs_obs[0]): [row(1), row(2)]})
    check("N10 'not matched to these reports' appears only on a page that has reports",
          (reports_here[verdict_projection.page_key(recs_obs[0])]["newer"]["match_note"]
           == "AUXSAYS has not matched its changes to the reports on this page.")
          and npg[verdict_projection.page_key(recs_obs[0])]["newer"]["match_note"] == "")
    real_records, real_groups = verdict_projection.load_inputs(_AUX)
    split = set(eo.split_products_from(_AUX))
    by_pid: dict = {}
    for r in real_records:
        by_pid.setdefault(str(r.get("product_id") or "").strip(), []).append(r)
    products = {}
    py = {}
    for pid, recs in by_pid.items():
        payload = eo.product_payload(recs)
        products[pid] = {"id": pid, "recs": [payload_tuple(r) for r in payload], "split": pid in split}
        for r in payload:
            t = eo.update_available(r, payload, split=pid in split)
            py[str(r.get("permalink") or "")] = str(t.get("permalink")) if t else None
    js = js_states(products)
    check("N11a node is on PATH (the shipped installedState is executed, never just read)", js is not None)
    diff = [] if not isinstance(js, dict) or "__error__" in js else \
        [k for k in sorted(set(py) | set(js)) if py.get(k) != js.get(k)]
    check(f"N11 PARITY: the port gives the shipped installedState's UPDATE AVAILABLE target for every one of "
          f"the corpus's {len(py)} dated, unarchived records",
          isinstance(js, dict) and "__error__" not in js and not diff and len(py) > 100,
          (js or {}).get("__error__") if isinstance(js, dict) else diff[:5])
    # Windows 11 is excluded from the note: patch_lifecycle.yml records that the general Windows "newer update
    # available" links wait for the Microsoft KB source assessment and exact KB/build applicability checks.
    win11 = [dict(r, product_id="microsoft-windows-11") for r in win]
    win_tool = project_one(win, {})
    win_excl = project_one(win11, {ident(win11[0]): [row(1, pid="microsoft-windows-11", version="25H2")]})
    real_newer = eo.project(real_records, real_groups, {}, [], reviewed, split)["pages"]
    real_win = [k for k, rw in real_newer.items() if k.startswith("microsoft-windows-11|")]
    check("N12 Windows 11 gets no newer-release note (the recorded KB applicability hold): not in this tree, and "
          "not for a build line that gets one under another product; its overview stays, PowerPoint keeps the note",
          eo.NEWER_NOTE_EXCLUDED_PRODUCTS == frozenset({"microsoft-windows-11"})
          and "newer" in win_tool.get(verdict_projection.page_key(win[0]), {})
          and not any("newer" in rw for rw in win_excl.values())
          and "count_line" in win_excl.get(verdict_projection.page_key(win11[0]), {})
          and bool(real_win) and not any("newer" in real_newer[k] for k in real_win)
          and any(k.startswith("microsoft-powerpoint|") and "newer" in rw for k, rw in real_newer.items()),
          (sorted(win_excl), [k for k in real_win if "newer" in real_newer[k]][:3]))
    banned = re.compile(r"\b(available|addresses|fixes|resolves)\b", re.I)
    notes_here = [rw["newer"] for rw in real_newer.values() if "newer" in rw]
    notes_here += [first, wv, sv, nd[key0]["newer"], nu, rh,
                   reports_here[verdict_projection.page_key(recs_obs[0])]["newer"]]
    said = [f"{n.get('identity')}: {m.group(0)}" for n in notes_here
            for k in ("caution", "verdict_line", "match_note", "fix_source") for m in [banned.search(str(n.get(k) or ""))]
            if m]
    check(f"N16 no newer-release note says 'available', 'addresses', 'fixes' or 'resolves' ({len(notes_here)} notes: "
          f"this tree's and the fixtures'), and every one carries a caution",
          not said and len(notes_here) > 100 and all(str(n.get("caution") or "") for n in notes_here), said[:5])

    # ------------------------------------------------------------------ [V]
    section("[V] vendor fix lines: complete, and switched off")
    body = ("33.1 Hotfix Changes\r\n------\r\n\r\n* Fixed a crash when A [dev] ([#1](https://x.test/1))\r\n"
            "* Fixed [B](https://x.test/b) failing on start [dev2] (#2)\r\n* Added a feature [dev]\r\n"
            "  + Fixed a nested sub-point\r\n* Fixed C\r\n* Fixed D\r\n* Fixed E\r\n* Fixed F\r\n")
    lines = eo.fix_lines(body)
    check("V1 the parser keeps up to five top-level 'Fixed' bullets, links reduced to text, credits removed",
          lines == ["Fixed a crash when A.", "Fixed B failing on start.", "Fixed C.", "Fixed D.", "Fixed E."], lines)
    newer_rec = rec("1.0.2", date="2026-10-20T00:00:00Z", body=body, notes="https://permitted.test/notes")
    off = eo.newer_row(recs_obs[0], newer_rec, {}, 0)
    check("V2 with no permission on record, a newer release prints its link only (no vendor text)",
          off["fix_lines"] == [] and off["fix_source"] == "" and off["notes_url"] == "https://permitted.test/notes", off)
    saved = eo.PUBLICATION_PERMITTED_HOSTS
    try:
        eo.PUBLICATION_PERMITTED_HOSTS = frozenset({"permitted.test"})
        on = eo.newer_row(recs_obs[0], newer_rec, {}, 0)
    finally:
        eo.PUBLICATION_PERMITTED_HOSTS = saved
    check("V3 forced on in memory for one host, the lines appear, attributed to the vendor's notes",
          on["fix_lines"] == lines and on["fix_source"] == "Vendor's release notes", on)
    check("V4 the guard refuses fix lines from a source with no permission on record",
          any("publication permission" in x for x in eo.public_text_problems({"newer": on}, [])))

    # ------------------------------------------------------------------ [G]
    section("[G] the public-text guard")
    real_reasons, real_lifecycle, _probs = verdict_projection.load_fact_files(_AUX)
    real_verdict, _u = verdict_projection.project(real_records, real_groups, real_reasons, real_lifecycle)
    real = eo.project(real_records, real_groups, real_verdict["pages"], real_reasons, reviewed, split)
    leaks = []
    for r in real_records:
        k = verdict_projection.page_key(r)
        if k in real["pages"]:
            for prob in eo.public_text_problems(real["pages"][k], real_groups.get(eo.verdict_reasons.record_identity(r), [])):
                leaks.append(f"{k}: {prob}")
    check(f"G1 no row of this tree's projection ({len(real['pages'])} pages) reproduces a stored report title or "
          f"excerpt, carries an author field, states a threshold or prints unpermitted vendor text",
          not leaks and len(real["pages"]) > 100, leaks[:5])
    leak_title = "Each report is listed separately below on my machine"
    leaky = eo.public_text_problems(p, [row(1, title=leak_title)])
    check("G2 a stored title that shares six consecutive words with an AUXSAYS string is caught", bool(leaky), leaky)
    whole = eo.public_text_problems({"count_line": "x OBS forum threads y"}, [row(1, title="OBS forum threads")])
    check("G2b a whole stored title of three or more words is caught", bool(whole), whole)
    check("G3 an author-like field is caught",
          bool(eo.public_text_problems({"count_line": "a", "reporter": "x"}, []))
          and bool(eo.public_text_problems({"newer": {"author": "x", "verdict_line": eo.NO_VERDICT_YET}}, [])))
    check("G4 acceptance or threshold wording is caught",
          bool(eo.public_text_problems({"count_line": "Not enough reports yet."}, [])))
    check("G5 a newer-release verdict line in any other shape is caught",
          bool(eo.public_text_problems({"newer": {"verdict_line": "Safe to install."}}, [])))
    ok_note = {"verdict_line": eo.NO_VERDICT_YET, "known_issue": False, "caution": eo.NEWER_NOT_SAFER, "match_note": ""}
    decl_note = dict(ok_note, known_issue=True, caution="Vendor" + eo.KNOWN_ISSUE_CAUTION)
    check("G5b the guard refuses a newer-release note whose caution is missing, reassuring, or not the one its "
          "known-issue flag names, or that says 'available'/'addresses'/'fixes'/'resolves'",
          not eo.public_text_problems({"newer": ok_note}, []) and not eo.public_text_problems({"newer": decl_note}, [])
          and bool(eo.public_text_problems({"newer": dict(ok_note, caution="")}, []))
          and bool(eo.public_text_problems({"newer": dict(ok_note, caution="Safe to upgrade.")}, []))
          and bool(eo.public_text_problems({"newer": dict(ok_note, known_issue=True)}, []))
          and bool(eo.public_text_problems({"newer": dict(decl_note, known_issue=False)}, []))
          and bool(eo.public_text_problems({"newer": dict(ok_note, match_note="Its changes address the reports; "
                                                                               "it resolves them.")}, []))
          and bool(eo.public_text_problems({"newer": dict(ok_note, fix_source="the fixes available")}, []))
          # each word alone, written out here (not read from the module's list), so dropping one is caught
          and all(bool(eo.public_text_problems({"newer": dict(ok_note, match_note=s)}, []))
                  for s in ("It is available now.", "It addresses these reports.", "It fixes these reports.",
                            "It resolves these reports.")))
    shapes = all(re.fullmatch(r"\d+ accepted patch-specific reports?\.( .+\.)?", rw.get("count_line", "x"))
                 for rw in real["pages"].values() if "count_line" in rw)
    clauses = {rw["count_line"].split(". ", 1)[1] for rw in real["pages"].values()
               if rw.get("count_line", "").count(". ") >= 1}
    check("G6 every count line in this tree has the one shape, and its clause is the universal one or a "
          "reviewed finding", shapes and clauses <= {eo.UNIVERSAL_CLAUSE, FINDING}, sorted(clauses)[:4])
    unreasoned_bad = []
    for r in real_records:
        k = verdict_projection.page_key(r)
        rw = real["pages"].get(k) or {}
        if "count_line" not in rw:
            continue
        printed = verdict_projection.printed_row(r, real_verdict["pages"])
        volume = printed is not None and verdict_projection.is_volume_row(printed)
        line = rw["count_line"]
        if printed is None:
            bad = not line.endswith((eo.UNIVERSAL_CLAUSE, FINDING))
        elif volume:  # G87: a volume-based WAIT may keep a valid reviewed finding, never the universal clause
            bad = line.endswith(eo.UNIVERSAL_CLAUSE)
        else:
            bad = line.endswith((eo.UNIVERSAL_CLAUSE, FINDING))
        if bad:
            unreasoned_bad.append(k)
    check("G7 in this tree a clause appears exactly on the pages that print no verdict (INSUFFICIENT DATA), and "
          "under a volume-based WAIT only a still-valid reviewed finding may stand (G87)",
          not unreasoned_bad, unreasoned_bad[:5])
    obs = real["pages"].get("obs-studio|33.0.1|", {})
    obs_rows = real_groups.get(("obs-studio", "33.0.1", ""), [])
    # G87: 33.0.1 prints the volume-based WAIT, so where its population is no longer G82's no clause follows the
    # count (the universal clause never stands beside a printed verdict); with G82's population the finding does.
    obs_printed = verdict_projection.printed_row({"product_id": "obs-studio", "update_version": "33.0.1",
                                                  "target_build": ""}, real_verdict["pages"])
    obs_volume = obs_printed is not None and verdict_projection.is_volume_row(obs_printed)
    assessed = eo.population_digest(obs_rows) == OBS_SHA and len(obs_rows) == 47
    # AUX-137: 33.0.1 may print a verdict that is not the volume-based WAIT (a current stored assessment decides);
    # beside ANY printed verdict the universal clause never stands, and the finding stands only under a volume WAIT.
    expect = (FINDING if assessed and (obs_printed is None or obs_volume)
              else "" if obs_printed is not None else eo.UNIVERSAL_CLAUSE)
    # The same tree with one counted row's id changed (same size, different population): only the reviewed
    # entry and the population may decide the clause, so a special case keyed on the page cannot pass this.
    moved_groups = dict(real_groups)
    moved_groups[("obs-studio", "33.0.1", "")] = ([dict(obs_rows[0], id=f"{obs_rows[0].get('id')}-moved")]
                                                  + list(obs_rows[1:])) if obs_rows else []
    moved = eo.project(real_records, moved_groups, real_verdict["pages"], real_reasons, reviewed, split)
    moved_row = moved["pages"].get("obs-studio|33.0.1|", {})
    check("G8 OBS Studio 33.0.1 shows the reviewed finding exactly while its population is G82's, else the "
          "universal clause, or under its volume-based WAIT no clause at all (also with one of its counted rows "
          "changed in this tree)",
          (obs.get("count_line", "").endswith(expect) if expect
           else obs.get("count_line", "") == eo.count_sentence(len(obs_rows)))
          and (not obs_rows or (bool(moved_row.get("count_line")) and not moved_row["count_line"].endswith(FINDING)
                                and not moved_row.get("assessment"))),
          (obs.get("count_line"), moved_row.get("count_line")))

    # ------------------------------------------------------------------ [F]
    section("[F] fail closed: the builder and QA")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "proj.yml"
        proc = subprocess.run([sys.executable, "-B", str(BUILDER), "--root", str(Path(td) / "no-tree"),
                               "--output", str(out)], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=300, cwd=str(_REPO))
        written = yaml.safe_load(out.read_text(encoding="utf-8")) if out.exists() else None
        check("F1 a builder that cannot read its tree writes an EMPTY projection carrying the error, warns and exits 0",
              proc.returncode == 0 and isinstance(written, dict) and written.get("pages") == {}
              and bool(written.get("error")) and "::warning::" in proc.stdout, (proc.stdout + proc.stderr)[-300:])
    import qa_patch_records as qa  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        gen = tdp / "generated"
        gen.mkdir()
        fx_records = [rec("1.0.0", n_reports=3, date="2026-10-01T00:00:00Z"),
                      rec("1.0.1", date="2026-10-10T00:00:00Z")]
        files = []
        for i, r in enumerate(fx_records):
            fp = gen / f"2026-10-0{i + 1}-tool-{i}.md"
            fp.write_text("---\n" + yaml.safe_dump(r, sort_keys=False) + "---\n", encoding="utf-8")
            files.append(fp)
        fx_rows = [row(1, version="1.0.0"), row(2, version="1.0.0"), row(3, version="1.0.0")]
        (tdp / "ev.yml").write_text(yaml.safe_dump({"evidence": fx_rows}), encoding="utf-8")
        (tdp / "reasons.yml").write_text("schema_version: 1\nentries: []\n", encoding="utf-8")
        (tdp / "life.yml").write_text("schema_version: 1\nentries: []\n", encoding="utf-8")
        (tdp / "rev.yml").write_text(yaml.safe_dump(reviewed_with()), encoding="utf-8")
        saved_paths = (qa.EVIDENCE_PATH, qa.REASONS_PATH, qa.LIFECYCLE_PATH, qa.EVIDENCE_PRESENTATION_PATH,
                       qa.EVIDENCE_OVERVIEW_PATH, qa.PROJECTION_PATH)
        try:
            qa.EVIDENCE_PATH, qa.REASONS_PATH, qa.LIFECYCLE_PATH = tdp / "ev.yml", tdp / "reasons.yml", tdp / "life.yml"
            qa.EVIDENCE_PRESENTATION_PATH = tdp / "rev.yml"
            qa.EVIDENCE_OVERVIEW_PATH = tdp / "overview.yml"
            qa.PROJECTION_PATH = tdp / "verdict.yml"

            def codes(strict=False):
                e, w = qa.scan_evidence_overview(files, publish_strict=strict)
                return {x["code"] for x in e}, {x["code"] for x in w}
            e0, w0 = codes()
            check("F2 no projection and no verdict projection on disk (a lane, PR CI): nothing to report", not e0, e0)
            qa.PROJECTION_PATH.write_text("schema_version: 1\npages: {}\n", encoding="utf-8")
            e1, _ = codes()
            check("F3 the deploy built the verdict projection but not this one: evidence_overview_projection_missing",
                  "evidence_overview_projection_missing" in e1, e1)
            fx_groups = {ident(fx_records[0]): fx_rows}
            good_proj = eo.project(fx_records, fx_groups, {}, [], reviewed_with(), [])
            qa.EVIDENCE_OVERVIEW_PATH.write_text(eo.render(good_proj), encoding="utf-8")
            e2, _ = codes()
            check("F4 the deploy's projection equals the recompute: no error", not e2, e2)
            stale = copy.deepcopy(good_proj)
            first_key = next(iter(stale["pages"]))
            stale["pages"][first_key]["count_line"] = "3 accepted patch-specific reports."
            qa.EVIDENCE_OVERVIEW_PATH.write_text(eo.render(stale), encoding="utf-8")
            e3, _ = codes()
            check("F5 one row edited: evidence_overview_projection_stale", "evidence_overview_projection_stale" in e3, e3)
            failed = {"schema_version": 1, "rule_version": eo.RULE_VERSION, "pages": {}, "error": "boom"}
            qa.EVIDENCE_OVERVIEW_PATH.write_text(eo.render(failed), encoding="utf-8")
            e4, _ = codes()
            check("F6 a failed build: evidence_overview_projection_failed", "evidence_overview_projection_failed" in e4, e4)
            qa.EVIDENCE_OVERVIEW_PATH.write_text("pages: [unclosed\n", encoding="utf-8")
            e5, _ = codes()
            check("F7 an unreadable projection: evidence_overview_projection_invalid",
                  "evidence_overview_projection_invalid" in e5, e5)
            qa.EVIDENCE_OVERVIEW_PATH.unlink()
            qa.PROJECTION_PATH.unlink()
            bad_rev = reviewed_with()
            bad_rev["surprise"] = True
            qa.EVIDENCE_PRESENTATION_PATH.write_text(yaml.safe_dump(bad_rev), encoding="utf-8")
            e6, _ = codes()
            check("F8 a malformed reviewed file: evidence_presentation_invalid", "evidence_presentation_invalid" in e6, e6)
            qa.EVIDENCE_PRESENTATION_PATH.write_text(yaml.safe_dump(reviewed_with()), encoding="utf-8")
            leak_rows = [row(1, version="1.0.0", title="Each report is listed separately below on my machine"),
                         row(2, version="1.0.0"), row(3, version="1.0.0")]
            (tdp / "ev.yml").write_text(yaml.safe_dump({"evidence": leak_rows}), encoding="utf-8")
            en, wn = codes(strict=True)  # nothing on disk: a lane or PR CI reads only the reviewed file
            leak_proj = eo.project(fx_records, {ident(fx_records[0]): leak_rows}, {}, [], reviewed_with(), [])
            qa.EVIDENCE_OVERVIEW_PATH.write_text(eo.render(leak_proj), encoding="utf-8")
            el, wl = codes(strict=False)
            es, _ws = codes(strict=True)
            check("F9 with a deploy projection on disk a guard finding warns without --publish-strict and is an "
                  "ERROR under it; with none on disk the run reads only the reviewed file",
                  "evidence_overview_public_text" in wl and "evidence_overview_public_text" not in el
                  and "evidence_overview_public_text" in es and not en and not wn, (el, wl, es, en, wn))
        finally:
            (qa.EVIDENCE_PATH, qa.REASONS_PATH, qa.LIFECYCLE_PATH, qa.EVIDENCE_PRESENTATION_PATH,
             qa.EVIDENCE_OVERVIEW_PATH, qa.PROJECTION_PATH) = saved_paths
    check("F10 QA scans the evidence overview in its main run, with the publish-strict flag",
          "scan_evidence_overview(files, publish_strict=args.publish_strict)"
          in (_SCRIPTS / "qa_patch_records.py").read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ [T]
    section("[T] the shipped templates")
    inc_src = INCLUDE.read_text(encoding="utf-8")
    page_rec = {"product_id": "tool", "update_version": "1.0.0", "url": "/updates/v/tool/1.0.0/"}
    row_ok = {"url": "/u/", "reports": 3, "count_line": "3 accepted patch-specific reports. " + eo.UNIVERSAL_CLAUSE,
              "sources_line": "Sources: 2 GitHub issues & 1 forum thread.", "limitation": eo.LIMITATION,
              "assessment": "", "newer": {"identity": "Tool 1.0.2", "url": "/updates/v/tool/1.0.2/",
                                           "published_at": "2026-10-20T00:00:00Z", "notes_url": "https://vendor.test/n",
                                           "known_issue": False, "caution": eo.NEWER_NOT_SAFER,
                                           "verdict_line": eo.NO_VERDICT_YET, "match_note": eo.NOT_MATCHED,
                                           "fix_lines": [], "fix_source": ""}}
    site_with = {"data": {"evidence_overview_projection": {"schema_version": 1, "pages": {"tool|1.0.0|": row_ok}}}}
    with_fix = copy.deepcopy(site_with)
    with_fix["data"]["evidence_overview_projection"]["pages"]["tool|1.0.0|"]["newer"].update(
        {"fix_lines": ["Fixed a crash."], "fix_source": "Vendor's release notes"})
    site_decl = copy.deepcopy(site_with)
    site_decl["data"]["evidence_overview_projection"]["pages"]["tool|1.0.0|"]["newer"].update(
        {"known_issue": True, "caution": "OBS Project" + eo.KNOWN_ISSUE_CAUTION})
    site_nocaution = copy.deepcopy(site_with)
    site_nocaution["data"]["evidence_overview_projection"]["pages"]["tool|1.0.0|"]["newer"]["caution"] = ""
    # A newer release WITH a printed verdict: the include prints the row's verdict sentence, so a template that
    # hard-codes "not established" fails here (the real tree has no such row outside Windows 11).
    site_verdict = copy.deepcopy(site_with)
    site_verdict["data"]["evidence_overview_projection"]["pages"]["tool|1.0.0|"]["newer"]["verdict_line"] = (
        "AUXSAYS verdict for this release: WAIT if you use the test dock.")
    ov = "{% include patch-evidence-overview.html part='overview' record=page %}"
    nw = "{% include patch-evidence-overview.html part='newer' record=page %}"
    # The reviewed page itself, with a row carrying the universal clause: the include must print the row's
    # line there too, so no special case keyed on that page can live in the template.
    obs_page = {"product_id": "obs-studio", "update_version": "33.0.1", "url": "/updates/obs-project/obs-studio/33-0-1/"}
    obs_line = "46 accepted patch-specific reports. " + eo.UNIVERSAL_CLAUSE
    site_obs = {"data": {"evidence_overview_projection": {"schema_version": 1, "pages": {
        "obs-studio|33.0.1|": dict(row_ok, count_line=obs_line)}}}}
    cases = {
        "ov": {"template": ov, "site": site_with, "page": page_rec},
        "ov_obs": {"template": ov, "site": site_obs, "page": obs_page},
        "ov_none": {"template": ov, "site": {}, "page": page_rec},
        "nw": {"template": nw, "site": site_with, "page": page_rec},
        "nw_none": {"template": nw, "site": {"data": {"evidence_overview_projection": {"pages": {}}}}, "page": page_rec},
        "nw_fix": {"template": nw, "site": with_fix, "page": page_rec},
        "nw_decl": {"template": nw, "site": site_decl, "page": page_rec},
        "nw_nocaution": {"template": nw, "site": site_nocaution, "page": page_rec},
        "nw_verdict": {"template": nw, "site": site_verdict, "page": page_rec},
    }
    out = render_cases(cases) or {}
    check("T0 the liquid gem renders the shipped include", bool(out) and "__error__" not in out
          and not any(str(v).startswith("<<ERR") for v in out.values()), str(out)[:300])
    ovt = visible(out.get("ov", ""))
    check("T1 the overview prints the row's count line, families and limitation, escaped, with a jump to the list "
          "(on the reviewed OBS Studio 33.0.1 page too)",
          f"Evidence overview: {row_ok['count_line']}" in ovt and "Sources: 2 GitHub issues &amp; 1 forum thread." in out.get("ov", "")
          and eo.LIMITATION in ovt and 'href="#user-reports-sources"' in out.get("ov", "")
          and f"Evidence overview: {obs_line}" in visible(out.get("ov_obs", "")) and FINDING not in out.get("ov_obs", ""),
          (out.get("ov", "")[:400], out.get("ov_obs", "")[:400]))
    check("T2 FAIL CLOSED: no projection, no row -> the include prints nothing at all, not even whitespace",
          out.get("ov_none", "x") == "" and out.get("nw_none", "x") == "",
          (out.get("ov_none"), out.get("nw_none")))
    nw_html, decl_html = out.get("nw", ""), out.get("nw_decl", "")
    # visible() turns every tag into a space; a full stop right after a link closes up again here
    nwt, declt = re.sub(r"\s+\.", ".", visible(nw_html)), re.sub(r"\s+\.", ".", visible(decl_html))

    def before_links(html, text):
        at, link = html.find(text), html.find("<a ")
        return -1 < at and (link == -1 or at < link)
    check("T3 the newer-release note, in order: the release and its date, the caution BEFORE any link, the verdict "
          "sentence and the not-matched note, then the links to its AUXSAYS page and its official notes; it never "
          "says 'available', 'addresses', 'fixes' or 'resolves'",
          nwt == ("Newer release: Tool 1.0.2 (released Oct 20, 2026). Newer is not necessarily safer. Check its "
                  "official release notes, including any known issues, before upgrading. AUXSAYS has not "
                  "established an installation verdict for this release. AUXSAYS has not matched its changes to "
                  "the reports on this page. See its AUXSAYS page and its official release notes.")
          and before_links(nw_html, "Newer is not necessarily safer.")
          and 'href="/updates/v/tool/1.0.2/"' in nw_html and 'href="https://vendor.test/n"' in nw_html
          and not re.search(r"\b(available|addresses|fixes|resolves)\b", nwt + " " + declt, re.I)
          and "update-newer-release__caution--declared" not in nw_html
          # a printed verdict is printed as the row states it, never as "not established"
          and re.sub(r"\s+\.", ".", visible(out.get("nw_verdict", ""))) == (
              "Newer release: Tool 1.0.2 (released Oct 20, 2026). Newer is not necessarily safer. Check its "
              "official release notes, including any known issues, before upgrading. AUXSAYS verdict for this "
              "release: WAIT if you use the test dock. AUXSAYS has not matched its changes to the reports on this "
              "page. See its AUXSAYS page and its official release notes."),
          (nw_html[:700], out.get("nw_verdict", "")[:700]))
    check("T3b a newer release whose vendor documented a known issue: the vendor's caution, emphasised, BEFORE any "
          "link or verdict sentence",
          declt.startswith("Newer release: Tool 1.0.2 (released Oct 20, 2026). OBS Project has documented a known "
                           "issue affecting this version. Review the official release notes before upgrading. "
                           "AUXSAYS has not established an installation verdict for this release.")
          and before_links(decl_html, "OBS Project has documented a known issue")
          and 'class="update-newer-release__caution update-newer-release__caution--declared"' in decl_html,
          decl_html[:700])
    check("T3c FAIL CLOSED: a row with no caution prints no newer-release note at all",
          out.get("nw_nocaution", "x") == "", out.get("nw_nocaution"))
    check("T4 fix lines, when a row carries them, print attributed under the note (the mechanism exists)",
          "Listed first in Vendor's release notes:" in visible(out.get("nw_fix", "")).replace("&#39;", "'")
          and "<li>Fixed a crash.</li>" in out.get("nw_fix", ""), out.get("nw_fix", "")[:500])
    lay = layout_body()
    emitting = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "", lay, flags=re.S)
    check("T5 the layout prints no evidence-strength word any more (the count is stated instead)",
          "Evidence strength" not in emitting and "evidence strength {{" not in emitting
          and "{{ evidence_strength }}" not in emitting)
    i_ov, i_card_end = emitting.find(ov), emitting.find("{% include monitoring-status.html mode='compact'")
    i_nw = emitting.find(nw)
    i_cap = emitting.find("Newest accepted report captured:")
    inc_lines = [ln.strip() for ln in lay.splitlines() if "patch-evidence-overview.html" in ln and "{%" in ln]
    check("T6 both include tags are plain (the standalone harnesses cut at the first one) and share a line with "
          "an existing closing tag (a page with no row renders byte-identical); the overview is the last thing in "
          "the evidence card and the newer note sits before the compact monitoring line",
          -1 < i_cap < i_ov < i_nw < i_card_end and "{%- include patch-evidence-overview" not in lay
          and len(inc_lines) == 2 and all(ln.startswith("</div>{% include patch-evidence-overview.html")
                                          and ln.endswith("%}") for ln in inc_lines),
          (i_cap, i_ov, i_nw, i_card_end, inc_lines))
    # labels withheld, rendered through the real layout
    lab_page = {"product_id": "obs-studio", "company_id": "obs-project", "update_product": "OBS Studio",
                "update_version": "98.0", "update_detail_title": "OBS Studio 98.0",
                "update_published_at": "2026-10-01T00:00:00Z", "update_report_count": 2,
                "confirmed_patch_specific_report_count": 2,
                "accepted_report_sources": [
                    {"source_name": "obsproject/obs-studio", "source_type": "github_issue", "source_date": "2026-10-11",
                     "source_url": "https://reports.test/a", "issue": "crash or stability problems",
                     "workflow_area": "general OBS workflow"},
                    {"source_name": "OBS Project Support Forum", "source_type": "obs_forum_thread",
                     "source_date": "2026-10-12", "source_url": "https://reports.test/b",
                     "issue": "audio mixer or routing issues in audio mixer UI", "workflow_area": "audio mixer UI"}],
                "evidence_samples": [{"issue": "crash or stability problems"},
                                     {"issue": "audio mixer or routing issues in audio mixer UI"}]}
    dv_page = dict(lab_page, product_id="blackmagic-davinci", company_id="blackmagic-design",
                   update_product="DaVinci Resolve", update_detail_title="DaVinci Resolve 98.0")
    lw_site = {"time": "2026-10-14T00:00:00Z", "data": {"evidence_presentation": reviewed,
                                                        "patch_verdicts": yaml.safe_load(
                                                            (_AUX / "_data" / "patch_verdicts.yml").read_text(encoding="utf-8"))}}
    mutant = lay.replace("and issue_adds_nothing == false and labels_withheld == false %}",
                         "and issue_adds_nothing == false %}", 1)
    lcases = {"obs": {"template": lay, "site": lw_site, "page": lab_page},
              "dv": {"template": lay, "site": lw_site, "page": dv_page},
              "obs_nofile": {"template": lay, "site": {"time": lw_site["time"], "data": {
                  "patch_verdicts": lw_site["data"]["patch_verdicts"]}}, "page": lab_page},
              "obs_mutant": {"template": mutant, "site": lw_site, "page": lab_page}}
    lout = render_cases(lcases) or {}
    obs_html, dv_html = lout.get("obs", ""), lout.get("dv", "")
    check("T7a the layout renders for a withheld and a shown product",
          bool(obs_html) and bool(dv_html) and not obs_html.startswith("<<ERR") and not dv_html.startswith("<<ERR"),
          (obs_html[:200], dv_html[:200], lout.get("__error__")))
    check("T7 a withheld product prints no label sentence, no issue label and no workflow line, and keeps every "
          "source link with its date",
          "Current reports mention" not in visible(obs_html) and "crash or stability problems" not in visible(obs_html)
          and "Workflow:" not in obs_html and "User reports are present" in visible(obs_html)
          and '<a href="https://reports.test/a">obsproject/obs-studio report, October 11, 2026</a>' in obs_html
          and 'href="https://reports.test/b"' in obs_html, visible(obs_html)[-900:])
    check("T8 a product with no demonstrated label defect is unchanged: sentence, labels and workflow lines",
          "Current reports mention crash or stability problems" in visible(dv_html)
          and "obsproject/obs-studio report, October 11, 2026: crash or stability problems" in dv_html
          and "<small>Workflow: general OBS workflow</small>" in dv_html, visible(dv_html)[-900:])
    check("T9 the list comes from the tracked reviewed file: without it, nothing is withheld",
          "Current reports mention" in visible(lout.get("obs_nofile", "")))
    check("T10 MUTANT (the sentence guard removed): the withheld product's label sentence comes back",
          "Current reports mention" in visible(lout.get("obs_mutant", "")) and mutant != lay)
    meta = SEARCH_META.read_text(encoding="utf-8")
    check("T11 the search description no longer ties the missing verdict to the number of reports",
          "not yet enough for an AUXSAYS verdict" not in meta
          and "AUXSAYS has no verdict for this release yet." in meta and "linked to {{ psm_identity }} so far." in meta)
    wf = yaml.safe_load((_REPO / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8"))
    runs = [str(s.get("run") or "") for s in wf["jobs"]["build"]["steps"]]

    def at(needle):
        return next((i for i, r in enumerate(runs) if needle in r), -1)
    dv_wf = yaml.safe_load((_REPO / ".github" / "workflows" / "davinci-archive-build-check.yml").read_text(encoding="utf-8"))
    dv_runs = [str(s.get("run") or "") for s in next(iter(dv_wf["jobs"].values()))["steps"]]

    def dv_at(needle):
        return next((i for i, r in enumerate(dv_runs) if needle in r), -1)
    ignored = (_REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    check("T12 pages.yml and the DaVinci build check build the projection after the verdict projection and BEFORE "
          "QA and Jekyll; the projection is git-ignored",
          -1 < at("build_verdict_projection.py") < at("build_evidence_overview_projection.py")
          < at("qa_patch_records.py") < at("jekyll build")
          and -1 < dv_at("build_verdict_projection.py") < dv_at("build_evidence_overview_projection.py")
          < dv_at("qa_patch_records.py") < dv_at("jekyll build")
          and "auxsays/_data/evidence_overview_projection.yml" in ignored)
    check("T13 the include is in QA's public-copy scan of the patch layout",
          any(p.name == "patch-evidence-overview.html" for p in qa.UPDATE_LAYOUT_INCLUDES))
    check("T14 the include writes no literal heading element (the heading-contrast harness strips includes)",
          not re.search(r"<h[1-6]\b", inc_src))

    print()
    print("=" * 96)
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
