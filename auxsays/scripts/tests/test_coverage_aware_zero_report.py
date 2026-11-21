#!/usr/bin/env python3
"""Not monitored is not too few reports: the patch page's zero-report wording reads coverage (AUX-120, G80).

WHY. The GPT G77 ruling ("Public wording exception") defines two different statements:
"Not monitored: AUXSAYS is not collecting community evidence." and "Insufficient evidence: Collection
exists, but there is not enough verified evidence to support a conclusion." -- "Conflating them is a
credibility defect." The patch page never read the coverage authority (build_coverage_projection.py,
AUX-102), so every zero-report page said "Too few reports for a verdict yet." and "Community signal: Not
enough reports", including 847 pages of products with no community collection at all (GitHub 468, Figma
233, the four Elgato apps 140, Microsoft 365 Apps 6; measured on e2cfca68).

WHAT THIS PINS.
  [A] real Liquid renders of the shipped patch page (its own includes inlined, as Jekyll includes them)
      over every (coverage state, community state) pair the authority can derive, both zero-report paths
      and the security line. A product whose community collection is absent reads "not monitored"; an
      operating or impaired one keeps the insufficient-evidence words; with no projection (a local
      render, the offline harnesses) or no row for the product, nothing changes. The verdict word stays
      INSUFFICIENT DATA in every case.
  [B] byte comparisons inside one harness: the projection changes nothing on a page whose product is
      collected, nothing on a report-bearing page, and on an absent zero-report page exactly the verdict
      line and the community-signal word.
  [C] the deploy check (ci/verify_coverage_claims.py, PATCH) on rendered pages: it refuses an absent page
      that says reports are too few, a collected product's page that says not monitored, a page it cannot
      read and a product with no projection row; it passes a clean page and vendor text on the page.
  [D] the deploy check against the REAL templates with each half of the absent wording reverted (one
      mutant per half, so neither half is left unpinned).

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_coverage_aware_zero_report.py
"""
from __future__ import annotations

import difflib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
sys.path.insert(0, str(_AUX / "scripts"))
sys.path.insert(0, str(_AUX / "scripts" / "ci"))

import yaml  # noqa: E402

import build_coverage_projection as cov  # noqa: E402
import verify_coverage_claims as gate  # noqa: E402

LAYOUT = _AUX / "_layouts" / "aux-update.html"
INCLUDES = _AUX / "_includes"
DECISION = INCLUDES / "patch-decision.html"

# The exact public words (written verbatim into the PR so they can be disclosed as they ship).
NOT_MONITORED_LINE = "AUXSAYS is not monitoring community reports for this product."
NOT_MONITORED_WORD = "Not monitored"
TOO_FEW_LINE = "Too few reports for a verdict yet."
TOO_FEW_WORD = "Not enough reports"
SECURITY_LINE = ("Security-sensitive update. Test first if your workflow is fragile, but do not ignore "
                 "security exposure.")

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        _ERRORS.append(label)
        print(f"  FAIL  {label}" + (f"  [{str(detail)[:600]}]" if detail != "" else ""))


# ------------------------------------------------------------------------------------------------
# The shipped patch page, rendered with the Liquid gem
# ------------------------------------------------------------------------------------------------

PAGE_INCLUDE_TAG = re.compile(r"\{%-?\s*include\s+(patch-evidence-state|patch-decision)\.html\s+record=([\w.]+)\s*-?%\}")
GATE_INCLUDE_TAG = re.compile(r"\{%-?\s*include\s+patch-verdict-gate\.html\s+record=([\w.]+)\s+count=([\w.]+)\s*-?%\}")
MATURITY_TAG = re.compile(r"\{%-?\s*include\s+maturity-state\.html\s+record=([\w.]+)\s*-?%\}")
OTHER_INCLUDE = re.compile(r"\{%-?\s*include\s.*?-?%\}", re.S)


def _include(name: str) -> str:
    return (INCLUDES / f"{name}.html").read_text(encoding="utf-8")


def page_template(layout_text: str | None = None, decision_text: str | None = None) -> str:
    """The patch layout with the includes that decide its words inlined, bound to their arguments the
    way Jekyll's include binds them. The other includes (archived notice, monitoring card, vendor known
    issues) say nothing this test reads and cannot render standalone, so they are dropped."""
    text = (layout_text if layout_text is not None else LAYOUT.read_text(encoding="utf-8")).split("---", 2)[-1]
    decision = decision_text if decision_text is not None else DECISION.read_text(encoding="utf-8")
    text = PAGE_INCLUDE_TAG.sub(
        lambda m: (decision if m.group(1) == "patch-decision" else _include(m.group(1)))
        .replace("include.record", m.group(2)), text)
    text = GATE_INCLUDE_TAG.sub(
        lambda m: _include("patch-verdict-gate").replace("include.record", m.group(1))
        .replace("include.count", m.group(2)), text)
    text = MATURITY_TAG.sub(lambda m: _include("maturity-state").replace("include.record", m.group(1)), text)
    return OTHER_INCLUDE.sub("", text)


# render! so a Liquid error RAISES instead of landing in the output, where a wording assertion could
# read straight past it.
_RENDER_RB = r"""
require 'liquid'
require 'json'
module Shims
  def relative_url(i) = "/" + i.to_s.sub(%r{\A/}, "")
  def absolute_url(i) = "https://auxsays.test/" + i.to_s.sub(%r{\A/}, "")
  def markdownify(i) = i.to_s
  def jsonify(i) = JSON.generate(i)
  def where(input, property, value)
    input = input.values if input.is_a?(Hash)
    return input unless input.respond_to?(:select)
    input.select { |item| item.is_a?(Hash) && item[property].to_s == value.to_s }
  end
end
Liquid::Template.register_filter(Shims)
payload = JSON.parse(File.read(ARGV[0]))
parsed = {}
out = {}
payload['cases'].each do |name, c|
  parsed[c['template']] ||= Liquid::Template.parse(payload['templates'][c['template']])
  out[name] = parsed[c['template']].render!('site' => c['site'], 'page' => c['page'], 'content' => '')
end
print JSON.generate(out)
"""


def render_all(templates: dict[str, str], cases: dict[str, dict]) -> dict[str, str] | None:
    """{case name: html}, or None when ruby or the liquid gem is unavailable. A render error raises."""
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "render.rb"
        script.write_text(_RENDER_RB, encoding="utf-8")
        payload = Path(td) / "p.json"
        payload.write_text(json.dumps({"templates": templates, "cases": cases}), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300)
    if proc.returncode != 0:
        if "cannot load such file -- liquid" in (proc.stderr or ""):
            return None
        raise RuntimeError((proc.stderr or "")[-600:])
    return json.loads(proc.stdout)


_VERDICT = re.compile(r'update-decision-eyebrow">AUXSAYS verdict</span>\s*<strong>(.*?)</strong>', re.S)


def verdict_word(html_text: str) -> str:
    m = _VERDICT.search(html_text)
    return " ".join(m.group(1).split()) if m else ""


def verdict_line(html_text: str) -> str:
    found = gate._PATCH_LINE.findall(html_text)
    return gate._visible(found[0]) if len(found) == 1 else f"<{len(found)} lines>"


def signal_word(html_text: str) -> str:
    found = gate._PATCH_SIGNAL.findall(html_text)
    return gate._visible(found[0]) if len(found) == 1 else f"<{len(found)} words>"


def as_patch_page(html_text: str) -> str:
    """A rendered layout as the built site serves it: aux-base wraps it in the patch page's body."""
    return f'<html><body class="aux-page aux-update">{html_text}</body></html>'


PID = "acme-tool"


def record(path: str, *, count: int = 0, label: str = "Insufficient data") -> dict:
    """A patch page. `path` picks the zero-report branch: 'official' has a captured official source, so
    the decision include's official-only rule words the line; 'plain' has none, so the layout's own
    fallback words it; 'security' is official and security-sensitive."""
    page = {"product_id": PID, "company_id": "acme", "update_product": "Acme Tool", "update_version": "4.2.0",
            "target_build": "", "update_published_at": "2026-11-02T00:00:00Z", "url": "/updates/acme/acme-tool/4-2-0/",
            "update_report_count": count, "confirmed_patch_specific_report_count": count,
            "update_consensus_label": label}
    if path in ("official", "security"):
        page["update_source_url"] = "https://vendor.test/notes/4.2.0"
    if path == "security":
        page["security_sensitive"] = True
    if count:
        page.update({"evidence_state": "pilot_sample", "consensus_collection_status": "pilot_initial_sample",
                     "evidence_last_checked": "2026-11-10T00:00:00Z",
                     "accepted_report_sources": [{"source_type": "forum_thread"}]})
    return page


def site(coverage: dict | None) -> dict:
    data = {"evidence_method_health": {},
            "patch_verdicts": yaml.safe_load((_AUX / "_data" / "patch_verdicts.yml").read_text(encoding="utf-8"))}
    if coverage is not None:
        data["coverage_state"] = coverage
    return {"time": "2026-11-21T00:00:00Z", "data": data}


def coverage_row(state: str, official: str, community: str, pid: str = PID) -> dict:
    return {"product_id": pid, "state": state, "label": cov.COVERAGE_LABELS[state], "official": official,
            "community": community}


def reachable_pairs() -> dict[tuple[str, str], str]:
    """Every (coverage state, community state) the authority can derive -> an official state that gives it.
    Taken from derive_coverage itself, so a new state or rule is rendered here without editing this list."""
    pairs: dict[tuple[str, str], str] = {}
    for official in ("healthy", "disabled", "unconfigured", "stale", "blocked", "broken", "unverified"):
        for community in cov.COMMUNITY_STATES:
            for planned in (False, True):
                pairs.setdefault((cov.derive_coverage(official, community, planned=planned), community), official)
    return pairs


PATHS = ("official", "plain", "security")


def build_cases() -> tuple[dict, dict]:
    pairs = reachable_pairs()
    cases: dict[str, dict] = {}
    for (state, community), official in sorted(pairs.items()):
        cov_payload = {"products": [coverage_row("full", "healthy", "operating", pid="other-product"),
                                    coverage_row(state, official, community)], "companies": []}
        for path in PATHS:
            cases[f"{state}/{community}/{path}"] = {"template": "shipped", "site": site(cov_payload),
                                                    "page": record(path)}
        cases[f"{state}/{community}/reports"] = {"template": "shipped", "site": site(cov_payload),
                                                 "page": record("official", count=3, label="Negative")}
    no_row = {"products": [coverage_row("official_only", "healthy", "absent", pid="other-product")], "companies": []}
    for path in PATHS:
        cases[f"none/{path}"] = {"template": "shipped", "site": site(None), "page": record(path)}
        cases[f"norow/{path}"] = {"template": "shipped", "site": site(no_row), "page": record(path)}
    cases["none/reports"] = {"template": "shipped", "site": site(None),
                             "page": record("official", count=3, label="Negative")}
    return pairs, cases


# ------------------------------------------------------------------------------------------------
# [A] the words, in every state
# ------------------------------------------------------------------------------------------------

def section_a(pairs: dict, out: dict) -> None:
    print("\n[A] the zero-report words follow the authority's community state, and nothing else")
    states = {s for s, _c in pairs}
    communities = {c for _s, c in pairs}
    check("A1 the render covers every coverage state and every community state the authority defines",
          states == set(cov.COVERAGE_STATES) and communities == set(cov.COMMUNITY_STATES)
          and tuple(cov.COMMUNITY_STATES) == ("operating", "impaired", "absent"), (sorted(pairs), cov.COMMUNITY_STATES))
    decision_src = DECISION.read_text(encoding="utf-8")
    layout_src = LAYOUT.read_text(encoding="utf-8")
    check("A2 the shipped words are exactly the disclosed sentences, each written once, in the include and the layout",
          decision_src.count(f"'{NOT_MONITORED_LINE}'") == 1 and layout_src.count(f"'{NOT_MONITORED_WORD}'") == 1
          and not re.search(r"\d", NOT_MONITORED_LINE + NOT_MONITORED_WORD))

    absent_bad, kept_bad, verdict_bad = [], [], []
    for (state, community), _o in pairs.items():
        for path in ("official", "plain"):
            html_text = out[f"{state}/{community}/{path}"]
            got = (verdict_line(html_text), signal_word(html_text))
            if verdict_word(html_text) != "INSUFFICIENT DATA":
                verdict_bad.append((state, community, path, verdict_word(html_text)))
            if community == "absent":
                if got != (NOT_MONITORED_LINE, NOT_MONITORED_WORD):
                    absent_bad.append((state, path, got))
            elif got != (TOO_FEW_LINE, TOO_FEW_WORD):
                kept_bad.append((state, community, path, got))
    check("A3 every product without community collection (community absent: official_only, planned, "
          "not_monitored, impaired), on both zero-report paths, says it is not monitored, never too few",
          not absent_bad and sum(c == "absent" for _s, c in pairs) >= 4, absent_bad)
    check("A4 every product whose collection exists (operating or impaired, in every coverage state) keeps "
          "the insufficient-evidence words on both paths", not kept_bad, kept_bad)
    unchanged = [(k, verdict_line(out[k]), signal_word(out[k])) for k in
                 ("none/official", "none/plain", "norow/official", "norow/plain")
                 if (verdict_line(out[k]), signal_word(out[k])) != (TOO_FEW_LINE, TOO_FEW_WORD)]
    check("A5 with no projection (a local render, the offline harnesses) or no row for the product, the "
          "words are unchanged: the dependency fails to the existing wording, deliberately", not unchanged, unchanged)
    check("A6 the verdict word is INSUFFICIENT DATA in every zero-report case: presentation only",
          not verdict_bad and all(verdict_word(out[f"{p}/official"]) == "INSUFFICIENT DATA" for p in ("none", "norow")),
          verdict_bad)
    sec_bad = []
    for (state, community), _o in pairs.items():
        html_text = out[f"{state}/{community}/security"]
        want_word = NOT_MONITORED_WORD if community == "absent" else TOO_FEW_WORD
        if (verdict_line(html_text), signal_word(html_text)) != (SECURITY_LINE, want_word):
            sec_bad.append((state, community, verdict_line(html_text), signal_word(html_text)))
    check("A7 a security-sensitive zero-report page keeps its security line in every state (it never said too "
          "few); only its community-signal word follows the community state", not sec_bad, sec_bad)
    rep_bad = [(s, c, verdict_line(out[f"{s}/{c}/reports"]), signal_word(out[f"{s}/{c}/reports"]))
               for (s, c) in pairs
               if signal_word(out[f"{s}/{c}/reports"]) != "Negative"
               or "not monitoring" in verdict_line(out[f"{s}/{c}/reports"]).lower()]
    check("A8 a page WITH reports is untouched in every state: its sentiment word and its gate line stay",
          not rep_bad and verdict_line(out["none/reports"]).startswith("No verdict yet: 3 user reports"), rep_bad)


# ------------------------------------------------------------------------------------------------
# [B] byte comparisons: only the two intended lines, only on absent pages
# ------------------------------------------------------------------------------------------------

def changed_lines(a: str, b: str) -> list[tuple[str, str]]:
    old = [ln for ln in difflib.ndiff(a.split("\n"), b.split("\n")) if ln.startswith("- ")]
    new = [ln for ln in difflib.ndiff(a.split("\n"), b.split("\n")) if ln.startswith("+ ")]
    return list(zip([o[2:] for o in old], [n[2:] for n in new])) if len(old) == len(new) else [("<count>", f"{len(old)}/{len(new)}")]


def section_b(pairs: dict, out: dict) -> None:
    print("\n[B] the projection changes only the two intended lines, and only where collection is absent")
    collected_diff = [(s, c, p) for (s, c) in pairs if c != "absent" for p in PATHS
                      if out[f"{s}/{c}/{p}"] != out[f"none/{p}"]]
    check("B1 a collected product's zero-report page (operating or impaired, every state, every path) is "
          "byte-identical to the render with no projection at all", not collected_diff, collected_diff)
    check("B2 so is a page whose product has no projection row", all(out[f"norow/{p}"] == out[f"none/{p}"] for p in PATHS))
    reports_diff = [(s, c) for (s, c) in pairs if out[f"{s}/{c}/reports"] != out["none/reports"]]
    check("B3 a page with reports is byte-identical with and without the projection, in every state",
          not reports_diff, reports_diff)
    bad = []
    for (s, c) in pairs:
        if c != "absent":
            continue
        for p in ("official", "plain"):
            lines = changed_lines(out[f"none/{p}"], out[f"{s}/{c}/{p}"])
            want = [(f'          <p class="update-decision-recommendation">{TOO_FEW_LINE}</p>',
                     f'          <p class="update-decision-recommendation">{NOT_MONITORED_LINE}</p>')]
            signal_old = [ln for ln in out[f"none/{p}"].split("\n") if "Community signal:" in ln]
            signal_new = [ln for ln in out[f"{s}/{c}/{p}"].split("\n") if "Community signal:" in ln]
            want.append((signal_old[0] if signal_old else "?", signal_new[0] if signal_new else "?"))
            if lines != want or TOO_FEW_WORD not in want[1][0] or NOT_MONITORED_WORD not in want[1][1]:
                bad.append((s, p, lines))
    check("B4 on an absent zero-report page exactly two lines change: the verdict line and the "
          "community-signal word, old words to new", not bad, bad[:2])
    sec = [(s, changed_lines(out["none/security"], out[f"{s}/{c}/security"])) for (s, c) in pairs if c == "absent"]
    check("B5 on an absent security-sensitive page exactly one line changes, the community-signal word",
          all(len(lines) == 1 and "Community signal:" in lines[0][1] for _s, lines in sec), sec[:2])


# ------------------------------------------------------------------------------------------------
# [C] the deploy check on rendered pages
# ------------------------------------------------------------------------------------------------

def products(community: str | None) -> dict:
    if community is None:
        return {}
    state = {"operating": "full", "impaired": "impaired", "absent": "official_only"}[community]
    return {PID: coverage_row(state, "healthy", community)}


def section_c(out: dict) -> None:
    print("\n[C] the deploy check reads the two template-written elements against the projection")
    absent_page = as_patch_page(out["official_only/absent/official"])
    collected_page = as_patch_page(out["full/operating/official"])
    errs, info = gate.patch_page_problems("p.html", absent_page, products("absent"))
    check("C1 a clean absent page passes, and is counted as absent, zero-report and saying not monitored",
          not errs and info == {"community": "absent", "zero": True, "not_monitored": True}, (errs, info))
    errs, info = gate.patch_page_problems("p.html", collected_page, products("operating"))
    check("C2 a collected product's page saying too few reports passes: that is the right statement there",
          not errs and info["community"] == "operating" and not info["not_monitored"], (errs, info))
    reverted_line = absent_page.replace(NOT_MONITORED_LINE, TOO_FEW_LINE)
    errs, _ = gate.patch_page_problems("p.html", reverted_line, products("absent"))
    check("C3 an absent page whose verdict line says 'Too few reports' is refused",
          reverted_line != absent_page and any("'too few reports'" in e for e in errs), errs)
    reverted_word = absent_page.replace(f">{NOT_MONITORED_WORD}</em>", f">{TOO_FEW_WORD}</em>")
    errs, _ = gate.patch_page_problems("p.html", reverted_word, products("absent"))
    check("C4 an absent page whose community-signal word says 'Not enough reports' is refused",
          reverted_word != absent_page and any("'not enough reports'" in e for e in errs), errs)
    inverse = [gate.patch_page_problems("p.html", absent_page, products(c))[0] for c in ("operating", "impaired")]
    check("C5 the inverse is refused: a page saying not monitored for a product whose collection is "
          "operating or impaired", all(any("not monitored" in e for e in errs) for errs in inverse), inverse)
    vendor = absent_page.replace(
        "</body>", '<div class="official-patch-notes">Too few reports were filed; not enough reports to tell.</div></body>')
    errs, _ = gate.patch_page_problems("p.html", vendor, products("absent"))
    check("C6 vendor notes on the page that happen to say 'too few reports' never fail a deploy", not errs, errs)
    unreadable = re.sub(r'<p class="update-decision-recommendation">.*?</p>', "", absent_page, flags=re.S)
    no_signal = re.sub(r"<strong>Community signal:</strong>", "<strong>Signal:</strong>", absent_page)
    no_pid = absent_page.replace('data-watch-product="', 'data-watch-thing="')
    refused = [gate.patch_page_problems("p.html", t, products("absent"))[0] for t in (unreadable, no_signal, no_pid)]
    check("C7 a patch page whose verdict line, community-signal word or product identity cannot be read is "
          "refused, never read as clean", all(len(e) == 1 and "cannot be read" in e[0] for e in refused), refused)
    errs, _ = gate.patch_page_problems("p.html", absent_page, products(None))
    check("C8 a patch page whose product has no projection row is refused", any("no community state" in e for e in errs), errs)

    # Through the whole deploy entry point, over a one-page built site.
    def run_verify(page_text: str) -> tuple[list[str], dict]:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            built, source = root / "_site", root / "src"
            (built / "updates" / "acme" / "acme-tool" / "4-2-0").mkdir(parents=True)
            (built / "index.html").write_text("<html><body>home</body></html>", encoding="utf-8")
            (built / "updates" / "acme" / "acme-tool" / "4-2-0" / "index.html").write_text(page_text, encoding="utf-8")
            (source / "_data").mkdir(parents=True)
            (source / "updates").mkdir(parents=True)
            (source / "updates" / "2026-11-02-acme-tool-4-2-0.md").write_text(
                "---\nlayout: aux-update\nproduct_id: acme-tool\n---\n", encoding="utf-8")
            (source / "_data" / "patch_products.yml").write_text("[]\n", encoding="utf-8")
            (source / "_data" / "patch_companies.yml").write_text("[]\n", encoding="utf-8")
            projection = source / "_data" / "coverage_state.yml"
            projection.write_text(yaml.safe_dump({"products": [products("absent")[PID]], "companies": []}),
                                  encoding="utf-8")
            errors, _w, stats = gate.verify(built, source, projection)
            return errors, stats
    errors, stats = run_verify(absent_page)
    check("C9 the deploy entry point passes a clean absent patch page and counts it",
          not errors and stats.get("patch_pages") == 1 and stats.get("patch_pages_absent") == 1
          and stats.get("patch_pages_not_monitored") == 1, (errors, stats))
    errors, _stats = run_verify(reverted_line)
    check("C10 ... and refuses the same page saying too few reports",
          any(e.startswith("PATCH updates/acme/acme-tool/4-2-0/index.html") for e in errors), errors)
    errors, stats = run_verify(absent_page.replace('class="aux-page aux-update"', 'class="aux-page"'))
    check("C11 a build in which no patch page is recognised, while the source holds patch records, is refused",
          stats.get("patch_pages") == 0 and any("no built patch page was read" in e for e in errors), (errors, stats))


# ------------------------------------------------------------------------------------------------
# [D] the real templates with each half of the wording reverted
# ------------------------------------------------------------------------------------------------

def section_d() -> None:
    print("\n[D] the deploy check catches either half of the wording reverted in the real templates")
    layout = LAYOUT.read_text(encoding="utf-8")
    decision = DECISION.read_text(encoding="utf-8")
    line_mutant = decision.replace(f"'{NOT_MONITORED_LINE}'", f"'{TOO_FEW_LINE}'")
    word_mutant = layout.replace(f"'{NOT_MONITORED_WORD}'", f"'{TOO_FEW_WORD}'")
    cov_payload = {"products": [coverage_row("official_only", "healthy", "absent")], "companies": []}
    templates = {"line": page_template(decision_text=line_mutant), "word": page_template(layout_text=word_mutant)}
    cases = {f"{m}/{p}": {"template": m, "site": site(cov_payload), "page": record(p)}
             for m in templates for p in ("official", "plain")}
    out = render_all(templates, cases)
    if out is None:
        check("D1 could not render: ruby/liquid unavailable", False)
        check("D2 could not render: ruby/liquid unavailable", False)
        return
    line_errs = [gate.patch_page_problems("p.html", as_patch_page(out[f"line/{p}"]), products("absent"))[0]
                 for p in ("official", "plain")]
    check("D1 the decision include's not-monitored line reverted to 'too few': refused on both zero-report paths",
          line_mutant != decision and all(any("'too few reports'" in e for e in errs) for errs in line_errs), line_errs)
    word_errs = [gate.patch_page_problems("p.html", as_patch_page(out[f"word/{p}"]), products("absent"))[0]
                 for p in ("official", "plain")]
    check("D2 the layout's not-monitored word reverted to 'Not enough reports': refused on both paths",
          word_mutant != layout and all(any("'not enough reports'" in e for e in errs) for errs in word_errs), word_errs)


def run() -> int:
    pairs, cases = build_cases()
    try:
        out = render_all({"shipped": page_template()}, cases)
    except Exception as exc:  # noqa: BLE001 -- a render error FAILS by name
        out = None
        check("the shipped patch page renders", False, f"{exc!r}")
    if out is None:
        for n in range(1, 9):
            check(f"A{n} could not render the patch page", False, "install ruby and the liquid gem")
    else:
        for section in (lambda: section_a(pairs, out), lambda: section_b(pairs, out), lambda: section_c(out)):
            try:
                section()
            except Exception as exc:  # noqa: BLE001 -- a crashing section FAILS by name
                check("a section crashed", False, f"{exc!r}\n{traceback.format_exc()[-800:]}")
    try:
        section_d()
    except Exception as exc:  # noqa: BLE001
        check("section_d crashed", False, f"{exc!r}\n{traceback.format_exc()[-800:]}")
    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
