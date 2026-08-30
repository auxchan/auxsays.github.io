#!/usr/bin/env python3
"""A Liquid `blank` comparison is a silent no-op, so it must never gate a value that can be empty.

liquid-4.0.4 maps the `blank` literal to MethodLiteral(:blank?) (expression.rb:20) and resolves it
through `other.respond_to?(:blank?)`. Neither liquid-4.0.4 nor jekyll-4.4.1 defines String#blank?,
and there is no ActiveSupport in the Gemfile, so:

    {% if x != blank %}   is ALWAYS TRUE   -- for every value, including '' and nil
    {% if x == blank %}   is ALWAYS FALSE

Every else-branch behind such a guard is dead code. On the live site that produced, among others:
309 methodology Notes cells that demoted their note into <small> and left the primary slot empty,
two home-page article cards rendering <img src="">, 35 blank Verdict cells on one product page,
733 <a href=""> download links, and an empty "Checksum" section on 889 records.

The fix idiom is `{% assign b = x | default: '' %}{% if b != '' %}` -- `default` replaces nil, false
AND the empty string, which is why `x != ''` alone is NOT sufficient (nil != '' is also true).

WHAT THIS LOCKS
  [C] Census: every surviving `blank` guard is resolved back to the data field it reads, and the
      REAL corpus is measured. A guard over a field that is empty on even one row fails. This is
      not a spelling ban -- guards over fields that are never empty are left in place deliberately,
      and this test starts failing the moment the data makes one of them matter.
  [S] Sentinels: a local initialised to '' (or built by {% capture %}) exists precisely so it can
      be empty, so a `blank` comparison on it can never fire and is banned outright.
  [R] Renders: the repaired branches are exercised through the REAL liquid gem, so "the else branch
      is reachable now" is proven rather than asserted. Those cases SKIP without Ruby/liquid.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_blank_guard_emptiness.py
"""
from __future__ import annotations

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
sys.path.insert(0, str(_AUX / "scripts"))
from lib.normalize import split_front_matter  # noqa: E402

_PASS = _FAIL = _SKIP = 0
_ERRORS: list[str] = []

NL = chr(10)


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        _ERRORS.append(label)
        print(f"  FAIL  {label}" + (f"{NL}        {detail}" if detail else ""))


def skip(label: str, why: str) -> None:
    global _SKIP
    _SKIP += 1
    print(f"  SKIP  {label}{NL}        {why}")


# ---------------------------------------------------------------- real Liquid render

_RENDER = """
require 'liquid'
require 'json'
p_ = JSON.parse(File.read(ARGV[0]))
# render! (not render): a Liquid error must RAISE rather than be embedded in the output as text
# where an assertion could read straight past it.
print Liquid::Template.parse(p_['template']).render!(p_['vars'])
"""


def liquid_render(template: str, variables: dict) -> str | None:
    """Render with the real liquid gem. None if Ruby/liquid is unavailable."""
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "r.rb"
        script.write_text(_RENDER, encoding="utf-8")
        payload = Path(td) / "p.json"
        payload.write_text(json.dumps({"template": template, "vars": variables}), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload)],
                              capture_output=True, text=True, timeout=120)
        return proc.stdout if proc.returncode == 0 else None


def liquid_parses(template: str) -> bool | None:
    """True if the real gem parses `template`. None if Ruby/liquid is unavailable."""
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "t.liquid"
        f.write_text(template, encoding="utf-8")
        proc = subprocess.run(
            [ruby, "-e", "require 'liquid'; Liquid::Template.parse(File.read(ARGV[0])); print 'OK'",
             str(f)], capture_output=True, text=True, timeout=120)
        return proc.returncode == 0 and proc.stdout.strip() == "OK"


# ---------------------------------------------------------------- the real corpus

def _empty(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (
        isinstance(v, (list, dict)) and not v)


def _load_records() -> list[dict]:
    out = []
    for p in sorted(_AUX.joinpath("updates").rglob("*.md")):
        fm_text, _ = split_front_matter(p.read_text(encoding="utf-8"))
        if not fm_text:
            continue
        try:
            fm = yaml.safe_load(fm_text) or {}
        except yaml.YAMLError:
            continue
        if isinstance(fm, dict) and fm.get("layout") == "aux-update":
            out.append(fm)
    return out


def _rows(path: Path, key: str | None = None) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if key and isinstance(data, dict):
        data = data.get(key) or []
    if isinstance(data, dict):
        data = next((v for v in data.values() if isinstance(v, list)), [])
    return [r for r in (data or []) if isinstance(r, dict)]


RECORDS = _load_records()
METHOD_ROWS = _rows(_AUX / "_data" / "evidence_method_health.yml", "methods")
SOURCE_HEALTH = _rows(_AUX / "_data" / "source_health.yml")
PRODUCTS = _rows(_AUX / "_data" / "patch_products.yml")
COMPANIES = _rows(_AUX / "_data" / "patch_companies.yml")
REPORT_ROWS = [r for rec in RECORDS for r in (rec.get("accepted_report_sources") or [])
               if isinstance(r, dict)]
BUILD_RECORDS = [r for r in RECORDS if r.get("target_build")]
# aux-update.html's `item` is the issue-cluster loop variable, which walks evidence_samples and
# then complaint_themes; both feed the same `issue | issue_theme | theme` chain, so they are one
# population for census purposes.
ISSUE_ROWS = [r for rec in RECORDS
              for r in (rec.get("evidence_samples") or []) + (rec.get("complaint_themes") or [])
              if isinstance(r, dict)]

# Which population each loop/page variable reads, per template. Explicit rather than inferred:
# `item` means four different things across these files, and guessing would make the census lie.
SCOPES: dict[str, dict[str, list[dict]]] = {
    "_layouts/aux-update.html": {"page": RECORDS, "source": REPORT_ROWS, "product": PRODUCTS,
                                "company": COMPANIES, "item": ISSUE_ROWS},
    "_layouts/aux-updates.html": {"item": RECORDS, "page": RECORDS},
    "_layouts/aux-home.html": {"page": RECORDS},
    "_layouts/aux-patch-company.html": {"product": PRODUCTS, "page": RECORDS},
    "_layouts/aux-patch-product.html": {"product": PRODUCTS, "page": RECORDS},
    # The version-landing page lists BUILD records only, so that is the population it must be
    # measured against -- not all 905.
    "_layouts/aux-patch-version.html": {"item": BUILD_RECORDS, "product": PRODUCTS},
    "_includes/patch-table-row.html": {"item": RECORDS},
    "_includes/monitoring-status.html": {"m": METHOD_ROWS, "include": RECORDS},
    "_includes/patch-latest-signals.html": {"product": PRODUCTS},
    # methodology has TWO `item` loops over different data; split below by section offset.
    "updates/methodology/index.md": {"item": METHOD_ROWS},
}
# `{% include monitoring-status.html published_at=item.update_published_at %}` -- the include
# parameter is a record field under a different name.
INCLUDE_PARAM_FIELD = {"published_at": "update_published_at"}

TEMPLATES = {rel: (_AUX / rel).read_text(encoding="utf-8") for rel in SCOPES}

GUARD = re.compile(r"\{%-?\s*(?:if|elsif|unless)\s+([^%]*?)\s*-?%\}")
# ONLY `blank`. `nil`, `null` and `false` are real Liquid literals whose comparisons work, and
# `empty` maps to MethodLiteral(:empty?) which String DOES respond to -- banning those would flag
# correct code. `blank` is the single literal with no backing method here, so it is the whole bug.
COMPARISON = re.compile(r"([A-Za-z_][\w.]*)\s*(==|!=)\s*blank\b")


def scope_for(rel: str, offset: int, var: str) -> list[dict] | None:
    """The population `var` iterates at `offset` in template `rel`."""
    if rel == "updates/methodology/index.md" and var == "item":
        # Everything from the source-audit section on is a source_health row.
        split = TEMPLATES[rel].index("{% for item in site.data.source_health %}")
        return SOURCE_HEALTH if offset > split else METHOD_ROWS
    return SCOPES[rel].get(var)


def assign_rhs(text: str, local: str) -> str | None:
    """The right-hand side of the first `{% assign local = ... %}` in the template."""
    hits = re.findall(r"\{%-?\s*assign\s+" + re.escape(local) + r"\s*=\s*(.+?)\s*-?%\}", text)
    return hits[0] if hits else None


def resolve(rel: str, offset: int, expr: str) -> tuple[str, object]:
    """Classify a guarded expression.

    -> ("scoped", [(population, [field, ...])])  a data read, possibly a `default:` chain
    -> ("sentinel", why)                         a local that exists in order to be empty
    -> ("unresolved", why)                       not attributable to data; reported, not failed
    """
    if "." in expr:
        var, field = expr.split(".", 1)
        pop = scope_for(rel, offset, var)
        if pop is not None and "." not in field:
            name = INCLUDE_PARAM_FIELD.get(field, field) if var == "include" else field
            return "scoped", [(pop, [name])]
        return "unresolved", f"{expr} (nested or unmapped scope)"

    text = TEMPLATES[rel]
    if re.search(r"\{%-?\s*capture\s+" + re.escape(expr) + r"\s*-?%\}", text):
        return "sentinel", "built by {% capture %}; empty when it emits nothing"
    rhs = assign_rhs(text, expr)
    if rhs is None:
        return "unresolved", f"{expr} (no assignment found)"
    if re.fullmatch(r"''|\"\"", rhs.strip()):
        return "sentinel", "initialised to the empty string"
    # `a | default: b | default: ''` is empty only when EVERY source field is empty.
    fields, pops = [], []
    for m in re.finditer(r"\b([A-Za-z_]\w*)\.(\w+)\b", rhs):
        pop = scope_for(rel, offset, m.group(1))
        if pop is None:
            return "unresolved", f"{expr} = {rhs} (unmapped scope {m.group(1)})"
        fields.append(m.group(2))
        pops.append(pop)
    if not fields:
        return "unresolved", f"{expr} = {rhs} (no field reads)"
    if any(p is not pops[0] for p in pops):
        # A `default:` chain spanning two populations (e.g. product.logo_path | default:
        # company.logo_path) cannot be joined row-by-row here. It is still provably inert if ANY
        # single link is never empty in its own population, because that link always supplies a
        # value. Otherwise say so rather than guessing.
        return "scoped", [(p, [f]) for p, f in zip(pops, fields)]
    return "scoped", [(pops[0], fields)]


def empty_rows(pop: list[dict], fields: list[str]) -> int:
    """Rows where EVERY field in the `default:` chain is empty -- i.e. the guard sees ''/nil."""
    return sum(1 for row in pop if all(_empty(row.get(f)) for f in fields))


def survey() -> tuple[list, list, list]:
    """(offending, inert, unresolved) for every `blank` comparison in every template."""
    offending, inert, unresolved = [], [], []
    for rel, text in TEMPLATES.items():
        for gm in GUARD.finditer(text):
            for cm in COMPARISON.finditer(gm.group(1)):
                expr = cm.group(1)
                site = f"{rel}:{text[:gm.start()].count(NL) + 1}"
                kind, payload = resolve(rel, gm.start(), expr)
                if kind == "sentinel":
                    offending.append((site, expr, f"'' sentinel -- {payload}"))
                elif kind == "unresolved":
                    unresolved.append((site, expr, str(payload)))
                else:
                    # payload is one (population, default-chain) pair, or several when the chain
                    # spans populations -- in which case a single never-empty link makes it inert.
                    counts = [(empty_rows(pop, fields), len(pop), fields)
                              for pop, fields in payload]
                    n = min(c for c, _, _ in counts)
                    detail = " / ".join(f"{c}/{tot} rows empty ({'|'.join(f)})"
                                        for c, tot, f in counts) if len(counts) > 1 \
                        else f"{counts[0][0]}/{counts[0][1]} rows empty"
                    (offending if n else inert).append((site, expr, detail))
    return offending, inert, unresolved


# ---------------------------------------------------------------- the suite

def run() -> int:
    print("=" * 78)
    print("Liquid `blank` guards -- banned wherever emptiness is reachable")
    print("=" * 78)
    print(f"corpus: {len(RECORDS)} update records, {len(METHOD_ROWS)} method-health rows, "
          f"{len(SOURCE_HEALTH)} source-health rows, {len(PRODUCTS)} products, "
          f"{len(REPORT_ROWS)} accepted report rows, {len(ISSUE_ROWS)} issue rows, "
          f"{len(BUILD_RECORDS)} build records")

    liquid_ok = liquid_render("{{ x }}", {"x": "ok"}) == "ok"
    if not liquid_ok:
        print(NL + "  (Ruby + liquid gem unavailable: render cases SKIP, census still runs)")

    # ---------- [0] the no-op itself, proven rather than asserted ----------
    print(NL + "[0] the defect this test exists for")
    if not liquid_ok:
        skip("0 (render)", "no Ruby/liquid")
    else:
        check("0 `!= blank` fires on the empty string (always true)",
              liquid_render("[{% if v != blank %}X{% endif %}]", {"v": ""}) == "[X]")
        check("0 `== blank` never fires on the empty string (always false)",
              liquid_render("[{% if v == blank %}X{% endif %}]", {"v": ""}) == "[]")
        check("0 `!= ''` alone is NOT the fix -- nil still passes it",
              liquid_render("[{% if v != '' %}X{% endif %}]", {"v": None}) == "[X]")
        check("0 `| default: ''` then `!= ''` suppresses BOTH nil and ''",
              liquid_render("{% assign b = v | default: '' %}[{% if b != '' %}X{% endif %}]",
                            {"v": None}) == "[]"
              and liquid_render("{% assign b = v | default: '' %}[{% if b != '' %}X{% endif %}]",
                                {"v": ""}) == "[]")

    # ---------- [C] census ----------
    print(NL + "[C] every surviving `blank` guard reads a field that is never empty")
    offending, inert, unresolved = survey()
    check("C no `blank` guard gates a value that is empty anywhere in the corpus",
          not offending,
          (NL + "        ").join(f"{s}  {e}  ({d})" for s, e, d in offending))
    check("C the census actually resolved guards (it is not passing vacuously)",
          len(inert) >= 20, f"{len(inert)} resolved-inert, {len(unresolved)} unresolved")
    print(f"        {len(inert)} guard(s) left in place, each provably inert:")
    for site, expr, detail in sorted(inert):
        print(f"          - {site:48} {expr:40} {detail}")
    if unresolved:
        print(f"        {len(unresolved)} not attributable to data (reported, not failed):")
        for site, expr, detail in sorted(unresolved):
            print(f"          - {site:48} {detail}")

    # Non-vacuity: a guard put back onto a field that IS empty must be caught.
    print(NL + "[C2] the census is non-vacuous")
    saved = TEMPLATES["_layouts/aux-update.html"]
    TEMPLATES["_layouts/aux-update.html"] = saved.replace(
        "{% if download_url_clean != '' %}<li><cite>",
        "{% if page.update_download_url != blank %}<li><cite>")
    caught = [o for o in survey()[0] if "update_download_url" in o[1]]
    TEMPLATES["_layouts/aux-update.html"] = saved
    check("C2 re-introducing the download-url guard is caught, with a real empty count",
          bool(caught) and caught[0][2].startswith("733/"), str(caught))

    # ---------- [S] sentinels ----------
    print(NL + "[S] locals that exist in order to be empty are never `blank`-guarded")
    for rel, local in (("_includes/monitoring-status.html", "mon_latest_raw"),
                       ("_includes/monitoring-status.html", "m_checked"),
                       ("_layouts/aux-update.html", "issue_cluster_text"),
                       ("_layouts/aux-update.html", "file_size_pill_value")):
        text = TEMPLATES[rel]
        guards = [c.group(0) for g in GUARD.finditer(text)
                  for c in COMPARISON.finditer(g.group(1)) if c.group(1) == local]
        check(f"S {local} is compared against '' only", not guards, str(guards))

    # ---------- [R] the repaired branches actually render ----------
    print(NL + "[R] the repaired else-branches are reachable through real Liquid")
    page = TEMPLATES["updates/methodology/index.md"]
    start = page.index('<div class="source-health-table method-health-table"')
    notes_block = page[start:page.index("{% endfor %}", start) + len("{% endfor %}")] + NL + "</div>"

    def notes_cell(blocked: str, notes: str) -> str | None:
        out = liquid_render(notes_block, {"method_health_rows": [{
            "product_id": "blackmagic-davinci", "update_version": "20.3", "method_id": "reddit",
            "source_type": "reddit_community_report", "status": "no_results",
            "last_run": "2026-08-26T20:55:50Z", "blocked_reason": blocked, "notes": notes}]})
        if out is None:
            return None
        return re.findall(r"<span>(?:(?!<span>).)*?<small>.*?</small></span>", out, re.S)[-1]

    if not liquid_ok:
        skip("R (render)", "no Ruby/liquid")
    else:
        NOTE = "Reddit community search across r/davinciresolve"
        BLOCK = "HTTP 403 from source"
        # THE acceptance case: 309 of 1116 rows carry a note and no block reason. Before the fix
        # the always-true guard put blocked_reason (empty) in the primary slot and demoted the note
        # into <small>; the live page showed `<span><small>Reddit community search...`.
        cell = notes_cell("", NOTE)
        check("R1 notes-only row puts the note in the PRIMARY slot (the else branch runs)",
              cell == f"<span>{NOTE}<small></small></span>", str(cell))
        check("R1 it is no longer demoted into <small>",
              not (cell or "").startswith("<span><small>"), str(cell))
        check("R2 a block reason still wins the primary slot",
              notes_cell(BLOCK, "") == f"<span>{BLOCK}<small></small></span>",
              str(notes_cell(BLOCK, "")))
        check("R3 with BOTH, the block reason leads and the note rides in <small>",
              notes_cell(BLOCK, NOTE) == f"<span>{BLOCK}<small>{NOTE}</small></span>",
              str(notes_cell(BLOCK, NOTE)))
        check("R4 with neither, nothing is invented",
              notes_cell("", "") == "<span><small></small></span>", str(notes_cell("", "")))
        # Non-vacuity: restore the old guard in THIS template and the note collapses back into
        # <small>. Derived from the shipped text, so it stays true after this lands on main.
        old_block = notes_block.replace("mh_blocked != ''", "mh_blocked != blank")
        old_out = liquid_render(old_block, {"method_health_rows": [{
            "blocked_reason": "", "notes": NOTE, "status": "no_results"}]})
        check("R5 this is a real fix: the old guard still demotes the note into <small>",
              old_out is not None and f"<span><small>{NOTE}</small></span>" in old_out,
              (old_out or "")[-140:])

        # Verdict fallback -- 868 records store no update_decision_label; 35 Verdict cells on one
        # live product page rendered EMPTY because all three fallback branches were unreachable.
        row = TEMPLATES["_includes/patch-table-row.html"]
        block = row[row.index("{% assign verdict_text"):row.index("{% assign report_count_num")]

        def verdict(item: dict) -> str:
            return (liquid_render("{% assign item = i %}" + block + "[{{ decision_label }}]",
                                  {"i": item}) or "").strip()

        check("R6 verdict falls back to the consensus summary's leading category",
              verdict({"update_consensus_summary": "AVOID: driver crashes."}) == "[AVOID]",
              verdict({"update_consensus_summary": "AVOID: driver crashes."}))
        check("R7 then to the quick verdict's leading category",
              verdict({"quick_verdict": "TEST FIRST: some regressions."}) == "[TEST FIRST]",
              verdict({"quick_verdict": "TEST FIRST: some regressions."}))
        check("R8 then to INSUFFICIENT DATA rather than an empty cell",
              verdict({}) == "[INSUFFICIENT DATA]", verdict({}))
        check("R9 an explicit decision label still wins",
              verdict({"update_decision_label": "WAIT",
                       "update_consensus_summary": "AVOID: x."}) == "[WAIT]")

        # Home page: all three posts carry no image key, and the placeholder branch never ran --
        # the live home page served two <img src=""> and zero placeholders.
        home = TEMPLATES["_layouts/aux-home.html"]
        chain = home[home.index("{% assign article_image_src = post.image"):
                     home.index('<article class="featured-card featured-card--wide">')]
        tail = ("[{% if article_image_src != '' %}IMG:{{ article_image_src }}"
                "{% else %}PLACEHOLDER{% endif %}]")

        def img(post: dict) -> str:
            return (liquid_render(chain + tail, {"post": post}) or "").strip()

        check("R10 a post with no image key reaches the placeholder branch",
              img({}) == "[PLACEHOLDER]", img({}))
        check("R11 an empty-string image is treated as absent too",
              img({"image": ""}) == "[PLACEHOLDER]", img({"image": ""}))
        for key in ("image", "thumbnail", "thumb", "cover", "hero_image", "featured_image"):
            check(f"R12 the {key} fallback still resolves",
                  img({key: "/a/x.png"}) == "[IMG:/a/x.png]", img({key: "/a/x.png"}))
        for shape in ("path", "url", "src"):
            check(f"R13 a mapping image with .{shape} still resolves",
                  img({"image": {shape: "/a/y.png"}}) == "[IMG:/a/y.png]",
                  img({"image": {shape: "/a/y.png"}}))

        # Empty-href download links: 733 records store update_download_url: ''.
        upd = TEMPLATES["_layouts/aux-update.html"]
        dl = upd[upd.index("{% assign download_url_clean"):].split("%}")[0] + "%}"
        probe = (dl + "[{% if download_url_clean != '' %}"
                 '<a href="{{ download_url_clean }}">D</a>{% endif %}]')
        check("R14 an empty download url emits no anchor at all",
              liquid_render(probe, {"page": {"update_download_url": ""}}) == "[]",
              str(liquid_render(probe, {"page": {"update_download_url": ""}})))
        check("R15 a real download url still emits its anchor",
              liquid_render(probe, {"page": {"update_download_url": "https://x/y"}})
              == '[<a href="https://x/y">D</a>]')

    # ---------- [P] the shipped templates still parse ----------
    print(NL + "[P] every template this change touches still parses under the real gem")
    if liquid_parses("{{ x }}") is None:
        skip("P (parse)", "no Ruby/liquid")
    else:
        for rel in TEMPLATES:
            check(f"P {rel} parses", liquid_parses(TEMPLATES[rel]) is True)

    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed"
          + (f", {_SKIP} skipped" if _SKIP else ""))
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
