#!/usr/bin/env python3
"""What the PUBLIC site is allowed to say about how evidence was gathered.

WHY THIS SUITE EXISTS. The public methodology page rendered the whole method-health store:
measured on the deployed page, 1,554,238 bytes carrying `reddit_search` 1,064 times, `http_403`
558 times, `http_202_aws_waf` 329 times, and every adapter name beside it. The per-patch
monitoring card leaked the same class a different way -- its family label DEFAULTED to
`method_id | replace: '_',' '` and let seven mappings override it, so the 16 unmapped ids of 23
printed their internal token on hundreds of pages: "adobe community algolia search" on 216,
"adobe community search" on 184, "known watchlist" on 137, "vendor forum search" on 121,
"techcommunity windows sitemap" on 89, "brave search api" and "wayback snapshot recheck" on 2.

Two suites used to guard that table's presentation and they were retired with it
(test_methodology_notes_rendering, test_public_method_health_presentation). A removed check in
this repository has previously turned out to have had a second job, so the guarantees that
OUTLIVE the table were moved here FIRST, in the same change that retired them:

  * the Liquid `blank` literal is INERT, so a guard must compare against '' -- measured live
    three times in this repo (a verdict blanked on 86 pages, a dangling "Build " on 119 rows,
    and both notes-cell guards unconditionally true);
  * a raw block reason is never rendered publicly;
  * the public family label is a CLOSED set, and an unmapped id costs specificity, never truth.

THE LINE THIS SUITE DRAWS. `method_id` describes HOW a source was reached -- a route, an API, a
search strategy -- and is proprietary. `source_type` describes WHAT was cited, and is citation
metadata the contract requires us to keep. So this suite forbids the first and deliberately does
not touch the second.

Assertions run against a REAL Liquid render of the verbatim shipped include wherever Ruby and
the liquid gem are present; the structural assertions run either way. Nothing here greps a
template for a string it hopes is present: a grep over source would pass with the defect
restored, which is exactly how the notes-cell defect survived review.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_public_evidence_projection.py
"""
from __future__ import annotations

import html
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
_SCRIPTS = _AUX / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

MONITORING_INCLUDE = _AUX / "_includes" / "monitoring-status.html"
METHODOLOGY_PAGE = _AUX / "updates" / "methodology" / "index.md"
HOME_LAYOUT = _AUX / "_layouts" / "aux-home.html"
SHIPPED_JS = (_AUX / "assets" / "js" / "auxsays.js",
              _AUX / "assets" / "js" / "patch-table-sort.mjs")

NEWLINE = "\n"
_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print("  PASS  " + label)
    else:
        _FAIL += 1
        print("  FAIL  " + label)
        if detail:
            print("        " + detail)
        _ERRORS.append(label)


_RENDER_SCRIPT = """
require 'liquid'
require 'json'
payload = JSON.parse(File.read(ARGV[0]))
tpl = Liquid::Template.parse(payload['template'])
# render! (not render): a Liquid error must RAISE rather than be embedded in the output as text
# where an assertion could read straight past it.
print tpl.render!(payload['vars'])
"""


def liquid_render(template: str, variables: dict) -> str | None:
    """Render `template` with the real liquid gem. None when Ruby/liquid is unavailable."""
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "render.rb"
        script.write_text(_RENDER_SCRIPT, encoding="utf-8")
        payload = Path(td) / "payload.json"
        payload.write_text(json.dumps({"template": template, "vars": variables}),
                           encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload)],
                              capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            return None
        return proc.stdout


def family_block() -> str:
    """The verbatim family-label block from the shipped include, as a renderable template.

    Extracted from the real file rather than restated, so this cannot drift away from what
    ships. Emits the resolved label so an assertion reads the rendered text.
    """
    src = MONITORING_INCLUDE.read_text(encoding="utf-8")
    start = src.index("{%- assign m_mid =")
    end = src.index("{%- endif -%}", start) + len("{%- endif -%}")
    return src[start:end] + "{{ m_family | escape }}"


def resolved_family(method_id) -> str | None:
    """The public label the shipped template produces for `method_id`, HTML-unescaped.

    Unescaped on purpose: the template pipes through `escape`, so a label containing an
    ampersand renders as `Microsoft Q&amp;A`. Comparing the escaped form against a plain
    allow-list is how a previous draft of this check reported a false failure.
    """
    out = liquid_render(family_block(), {"m": {"method_id": method_id}})
    return None if out is None else html.unescape(out.strip())


PUBLIC_FAMILIES = {
    "Microsoft Q&A",
    "Microsoft Tech Community",
    "Stack Exchange",
    "GitHub issues",
    "Reddit",
    "Adobe Support Community",
    "Creative COW forum",
    "OBS Project forum",
    "Vendor community forum",
    "Other monitored sources",
}

INTERNAL_TOKENS = (
    "method_id", "blocked_reason", "accepted_candidates", "candidates_found",
    "http_403", "http_429", "http_202", "aws_waf", "algolia", "brave_search",
    "wayback", "integrity_suites", "learn_qna", "techcommunity", "reddit_search",
    "obs_forum", "known_watchlist", "open_web_discovery", "vendor_forum_search",
    "adobe_community_", "creative_cow", "stack_exchange_search",
    "github_officedev_issues", "evidence_rows_added",
)


def load_health_ids() -> list[str]:
    import yaml
    data = yaml.safe_load((_AUX / "_data" / "evidence_method_health.yml").read_text(encoding="utf-8"))
    rows = data.get("methods") or []
    return sorted({str(r.get("method_id") or "") for r in rows if isinstance(r, dict)})


def section_a_family_is_closed() -> None:
    print(NEWLINE + "[A] the public source-family label is a closed set, and it fails closed")
    ids = load_health_ids()
    check("A1 the live store still has method ids to classify", len(ids) >= 10,
          f"{len(ids)} distinct ids")

    rendered = {i: resolved_family(i) for i in ids}
    if any(v is None for v in rendered.values()):
        check("A2 SKIPPED - ruby/liquid unavailable", True)
        check("A3 SKIPPED - ruby/liquid unavailable", True)
        check("A4 SKIPPED - ruby/liquid unavailable", True)
    else:
        outside = {i: v for i, v in rendered.items() if v not in PUBLIC_FAMILIES}
        check("A2 every live method id resolves to an approved public family", not outside,
              f"outside the allow-list: {sorted(outside.items())[:4]}")
        # A label MAY coincide with the de-underscored id when that string is itself an
        # approved public name -- `github_issues` renders "GitHub issues", which is exactly
        # what a reader should see. The defect shape is a label that is the de-underscored id
        # AND is not an approved name, which is what the old raw-id default produced.
        leaks = {i: v for i, v in rendered.items()
                 if v and v.lower() == i.replace("_", " ").lower()
                 and v not in PUBLIC_FAMILIES}
        check("A3 no label is an unapproved de-underscored internal id", not leaks,
              f"raw-id labels: {sorted(leaks.items())[:4]}")
        unknown = resolved_family("some_method_nobody_has_mapped_yet")
        check("A4 an UNMAPPED id renders the generic family, never its own token",
              unknown == "Other monitored sources",
              f"rendered {unknown!r}; an unmapped id must cost specificity, not truth")

    # Carried over from test_monitoring_status, which asserted this by COUNTING a literal
    # route-naming string in the template source. Several methods deliberately read the SAME
    # community by different routes; if each renders its own label, one community reads as
    # several independent sources. The old code gave them three different parenthetical
    # labels, which is the conflation it was trying to prevent. Asserted here on the rendered
    # label instead, so it holds however the mapping is written.
    qna = [resolved_family(i) for i in ids if "learn_qna" in i]
    if not qna or any(v is None for v in qna):
        check("A6 SKIPPED - no Q&A routes live, or ruby/liquid unavailable", True)
    else:
        check("A6 several routes over ONE community render ONE label",
              len(set(qna)) == 1,
              f"{len(qna)} routes rendered {sorted(set(qna))}; they would read as "
              "separate independent sources")

    absent = resolved_family("")
    if absent is None:
        check("A5 SKIPPED - ruby/liquid unavailable", True)
    else:
        check("A5 an EMPTY method id renders the generic family",
              absent == "Other monitored sources", f"rendered {absent!r}")


def section_b_no_internal_tokens_rendered() -> None:
    print(NEWLINE + "[B] the monitoring card never emits an internal token")
    src = MONITORING_INCLUDE.read_text(encoding="utf-8")
    # The template may READ m.notes and m.blocked_reason as discriminators; what matters is
    # that it never EMITS them. Assert on the emitting constructs, not on a mere mention.
    emitted = re.findall(r"\{\{-?\s*([^}]+?)\s*-?\}\}", src)
    bad = [e for e in emitted
           if "blocked_reason" in e or "m.notes" in e or "method_id" in e]
    check("B1 no output expression emits blocked_reason, notes or method_id", not bad,
          f"emitting expressions: {bad[:4]}")

    out = liquid_render(family_block(), {"m": {"method_id": "adobe_community_algolia_search"}})
    if out is None:
        check("B2 SKIPPED - ruby/liquid unavailable", True)
    else:
        label = html.unescape(out.strip())
        check("B2 the worst real offender renders a family, not its route",
              label == "Adobe Support Community",
              f"rendered {label!r} for adobe_community_algolia_search")


def section_c_blank_idiom() -> None:
    print(NEWLINE + "[C] the inert Liquid `blank` literal is not used as a guard")
    # Carried forward from the retired suites. `x != blank` is ALWAYS TRUE and `x == blank`
    # ALWAYS FALSE in this Liquid, because neither liquid-4.0.4 nor jekyll-4.4.1 defines
    # String#blank?. Measured live three times in this repository.
    for path in (MONITORING_INCLUDE, METHODOLOGY_PAGE, HOME_LAYOUT):
        src = path.read_text(encoding="utf-8")
        stripped = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "",
                          src, flags=re.S)
        hits = re.findall(r"[!=]=\s*blank", stripped)
        check(f"C {path.name} uses no `blank` comparison", not hits,
              f"{len(hits)} occurrence(s); compare against '' instead")


def section_d_page_is_contained_and_truthful() -> None:
    print(NEWLINE + "[D] the public evidence page discloses no method, and still tells the truth")
    page = METHODOLOGY_PAGE.read_text(encoding="utf-8")
    low = page.lower()

    present = [t for t in INTERNAL_TOKENS if t.lower() in low]
    check("D1 the page names no internal method, route or telemetry field", not present,
          f"found: {present[:6]}")

    # Identity is load-bearing: the URL carries inbound links, and the publish-strict deploy
    # gate pins the literal "Methodology" in the PATCH layout, not here.
    check("D2 the page keeps its permalink", "permalink: /updates/methodology/" in page)
    check("D3 the page keeps a title", re.search(r"^title:\s*\S", page, re.M) is not None)

    required = {
        "absence of reports is not safety": "does not establish that an update is safe",
        "a stopped source is disclosed as stopped": "stopped calling it",
        "repeated refusal is named": "refused request after request",
        "a failed check is not evidence either way": "does not know",
        "zero is reported as zero": "including when that number is zero",
        "recommendations can change": "may change",
    }
    for label, needle in required.items():
        check(f"D4 {label}", needle in low, f"missing: {needle!r}")

    check("D5 the page contains no Liquid tags", "{%" not in page and "{{" not in page,
          "a page with no Liquid cannot be silently blanked by an inert guard")


def section_e_shipped_js() -> None:
    print(NEWLINE + "[E] shipped front-end code names no internal module or threshold")
    # .js/.mjs are served VERBATIM, comments included, so these are scanned raw.
    banned = ("lib/patch_decision", "apply_consensus_to_records",
              "test_patch_decision_authority", "test_evidence_strength_thresholds",
              "_data/patch_verdicts", "RISK_ORDER", "integrity_suites")
    for path in SHIPPED_JS:
        src = path.read_text(encoding="utf-8")
        hits = [b for b in banned if b in src]
        check(f"E {path.name} names no internal module, data file or suite", not hits,
              f"found: {hits}")
    sort_src = SHIPPED_JS[1].read_text(encoding="utf-8")
    check("E the dead exported tier function is gone",
          "export function evidenceRank" not in sort_src,
          "it had no runtime caller and published the exact tier thresholds")
    # The ledger id STAYS: another suite asserts it against the raw module text, and an
    # opaque id is not an endpoint, a module or a selector.
    check("E the ledger id explaining the removal is retained", "AUX-008" in sort_src)


def section_f_artifact_gate_is_non_vacuous() -> None:
    print(NEWLINE + "[F] the published-payload gate catches what it exists to catch")
    from ci import verify_published_payload as vpp

    with tempfile.TemporaryDirectory() as td:
        site = Path(td)
        (site / "assets" / "css").mkdir(parents=True)
        (site / "index.html").write_text("<html></html>", encoding="utf-8")
        (site / "sitemap.xml").write_text("<urlset/>", encoding="utf-8")
        (site / "robots.txt").write_text("User-agent: *", encoding="utf-8")
        (site / "favicon.ico").write_bytes(b"\x00")
        (site / "app.webmanifest").write_text("{}", encoding="utf-8")
        (site / "assets" / "css" / "site.css").write_text("a{}", encoding="utf-8")
        check("F1 a clean artifact passes", vpp.findings_for(site) == [],
              f"false positives: {vpp.findings_for(site)}")

        # Every path below was MEASURED live at HTTP 200 before this gate existed.
        cases = (("scripts/lib/patch_decision.py", "implementation"),
                 ("tools/local-browser-capture/capture-edge.ps1", "operator tooling"),
                 ("tools/local-browser-capture/samples/x.sample.jsonl", "captured data"),
                 ("PATCH_FEED_FIX_VALIDATION.txt", "validation note"),
                 ("assets/js/patch-table-sort.test.mjs", "node test"),
                 ("assets/css/site.css.map", "source map"),
                 ("scripts/ci/integrity_suites.txt", "CI manifest"))
        for rel, why in cases:
            p = site / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x", encoding="utf-8")
            flagged = [r for r, _ in vpp.findings_for(site)]
            check(f"F2 {why} is refused", rel in flagged,
                  f"{rel} not flagged; flagged={flagged}")
            p.unlink()

        # Fails in the SAFE direction. An extension allow-list derived from the working tree
        # was measured to refuse .map/.xml/.ico/.webmanifest on a correct build, which would
        # have halted every deploy; a deny-list must let a new legitimate type through.
        (site / "data.xml").write_text("<x/>", encoding="utf-8")
        (site / "feed.json").write_text("{}", encoding="utf-8")
        check("F3 a new legitimate asset type still passes", vpp.findings_for(site) == [],
              "an allow-list would have refused these; a deny-list must not")



def join_block() -> str:
    """The verbatim sibling-build join from the shipped include, as a renderable template.

    Extracted from the real file rather than restated, so it cannot drift from what ships.
    """
    src = MONITORING_INCLUDE.read_text(encoding="utf-8")
    start = src.index("{%- for m in mon_rows -%}")
    marker = "{%- if m_ver == mon_ver and m_build == mon_build -%}"
    end = src.index(marker, start) + len(marker)
    return (src[start:end]
            + "MATCH:{{ m.method_id }};"
            + "{%- endif -%}{%- endfor -%}")


def section_g_build_identity() -> None:
    print(NEWLINE + "[G] a sibling build's telemetry cannot appear on another build's card")
    # REHOMED. test_public_method_health_presentation covered build identity on the
    # method-health surface and was retired with the table. The surviving card still joins on
    # the CANONICAL TRIPLE (product_id, update_version, target_build), so the guarantee is
    # live -- four sibling builds under one marketing version must not pool their telemetry.
    # Nothing asserted the rendered join: test_monitoring_status never mentions m_build, and
    # the multibuild suite covers INGESTION siblings, not this render. Asserted here on
    # rendered output over two real siblings.
    rows = [{"method_id": "own_build_row", "update_version": "2607",
             "target_build": "20228.20158", "status": "success"},
            {"method_id": "sibling_build_row", "update_version": "2607",
             "target_build": "20228.20110", "status": "blocked"},
            {"method_id": "version_only_row", "update_version": "2607",
             "target_build": "", "status": "success"}]
    tpl = ("{%- assign mon_ver = '2607' -%}{%- assign mon_build = '20228.20158' -%}"
           + join_block())
    out = liquid_render(tpl, {"mon_rows": rows})
    if out is None:
        check("G1 SKIPPED - ruby/liquid unavailable", True)
        check("G2 SKIPPED - ruby/liquid unavailable", True)
    else:
        check("G1 the card counts its OWN build's row", "MATCH:own_build_row;" in out,
              f"rendered {out!r}")
        check("G2 a SIBLING build's row is excluded, and so is a version-only row",
              "sibling_build_row" not in out and "version_only_row" not in out,
              f"rendered {out!r}; sibling telemetry would pool under one marketing version")


def run() -> int:
    section_a_family_is_closed()
    section_b_no_internal_tokens_rendered()
    section_c_blank_idiom()
    section_d_page_is_contained_and_truthful()
    section_e_shipped_js()
    section_f_artifact_gate_is_non_vacuous()
    section_g_build_identity()

    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2) from None
