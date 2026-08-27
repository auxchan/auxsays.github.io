#!/usr/bin/env python3
"""Public method-health presentation must preserve EXACT patch identity.

Method-health rows are stored per exact patch: patch_collectors.base.method_health_key is the
canonical identity triple (product_id, update_version, target_build) plus method_id. The public
methodology table rendered only product + version + method, so for a build-aware product the four
sibling builds under one version rendered as four rows whose identity columns read identically --
one apparent patch simultaneously reported blocked AND success, with no way to attribute any row to
a build. This locks the fix and the two constraints that bound it:

  - a build-aware row states its own build, so siblings are distinguishable to sighted AND
    screen-reader users (the identity is real text, never styling);
  - a version-only product renders byte-identically to before -- no column, no placeholder, no
    "None", no empty element.

It also locks the guard IDIOM. Liquid resolves the `blank` literal as MethodLiteral(:blank?)
(liquid-4.0.4 expression.rb), and neither liquid-4.0.4 nor jekyll-4.4.1 defines String#blank?, so
`x != blank` evaluates to nil and inverts to ALWAYS TRUE. That is not theoretical: before this
change every one of the 119 rows on the live /updates/blackmagic-design/blackmagic-davinci/ page
rendered a dangling "Build " with no value, and a data-version with a trailing dot. Any guard on
target_build must therefore compare against the empty string, never `blank`.

Where Ruby + the liquid gem are available the assertions run against a REAL Liquid render of the
verbatim shipped template block; otherwise those cases SKIP and the structural assertions still run.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_public_method_health_presentation.py
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

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"

PAGE_PATH = _AUX / "updates" / "methodology" / "index.md"
CSS_PATH = _AUX / "assets" / "css" / "auxsays-custom.css"
ROW_PATH = _AUX / "_includes" / "patch-table-row.html"
MON_PATH = _AUX / "_includes" / "monitoring-status.html"

PAGE = PAGE_PATH.read_text(encoding="utf-8")
CSS = CSS_PATH.read_text(encoding="utf-8")
ROW = ROW_PATH.read_text(encoding="utf-8")

PPT = "microsoft-powerpoint"
B110, B124, B158, B190 = "20228.20110", "20228.20124", "20228.20158", "20228.20190"

_PASS = 0
_FAIL = 0
_SKIP = 0
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


def skip(label: str, why: str) -> None:
    global _SKIP
    _SKIP += 1
    print(f"  SKIP  {label}\n        {why}")


# ---------------------------------------------------------------- template slicing


def method_health_block(page_text: str) -> str:
    """The verbatim shipped method-health table block, sliced out of the page."""
    start = page_text.index('<div class="source-health-table method-health-table"')
    end = page_text.index("{% endfor %}", start) + len("{% endfor %}")
    return page_text[start:end] + "\n    </div>"


def version_cell_fragment(row_include_text: str) -> str:
    """The patch-history row's build-bearing expressions, verbatim."""
    lines = row_include_text.splitlines()
    pre = [ln for ln in lines if "assign row_build" in ln]
    tr = next(ln for ln in lines if ln.startswith('<tr class="patch-row"'))
    td = next(ln for ln in lines if ln.startswith('<td data-label="Version"'))
    return "\n".join(pre + [re.search(r'data-version="[^"]*"', tr).group(0), td])


# ---------------------------------------------------------------- real Liquid render


_RENDER_SCRIPT = """
require 'liquid'
require 'json'
payload = JSON.parse(File.read(ARGV[0]))
tpl = Liquid::Template.parse(payload['template'])
# render! (not render): a Liquid error must RAISE, not be embedded in the output as text where an
# assertion could read straight past it.
print tpl.render!(payload['vars'])
"""


def _ruby() -> str | None:
    return shutil.which("ruby")


def liquid_render(template: str, variables: dict) -> str | None:
    """Render `template` with the real liquid gem. None if Ruby/liquid is unavailable."""
    ruby = _ruby()
    if not ruby:
        return None
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "render.rb"
        script.write_text(_RENDER_SCRIPT, encoding="utf-8")
        payload = Path(td) / "payload.json"
        payload.write_text(json.dumps({"template": template, "vars": variables}), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload)],
                              capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            return None
        return proc.stdout


def health_row(build: str | None, *, version: str = "2607", product: str = PPT,
               method: str = "reddit_search", status: str = "no_results",
               last_run: str = "2026-08-26T20:55:50Z") -> dict:
    """One method-health row shaped exactly as the collector writes it.

    build=None omits the target_build KEY entirely (the absent-key case), which is different from
    build='' (the key present and empty, what every version-only product actually stores)."""
    row = {
        "product_id": product, "update_version": version, "method_id": method,
        "source_type": "reddit_community_report", "status": status, "last_run": last_run,
        "candidates_found": 0, "accepted_candidates": 0, "evidence_rows_added": 0,
        "public_counted_reports": 0, "blocked_reason": "", "notes": "",
    }
    if build is not None:
        row["target_build"] = build
    return row


def rendered_rows(rows: list[dict], *, page_text: str | None = None) -> list[str] | None:
    """Rendered method-health row bodies, in render order. None if Liquid is unavailable."""
    block = method_health_block(page_text if page_text is not None else PAGE)
    out = liquid_render(block, {"method_health_rows": rows})
    if out is None:
        return None
    # Capture the status CLASS along with the body: which build a status belongs to is exactly what
    # is under test, and the status is carried on the row element itself.
    return re.findall(
        r'(<div class="source-health-row method-health-row method-health-row--[^"]*" role="row">'
        r".*?\n      </div>)", out, re.S)


def without_build_label(page_text: str) -> str:
    """The page with the build sub-label removed -- a synthetic PRE-FIX template.

    Non-vacuity used to be proven by rendering `git show main:...`. That is self-invalidating: once
    the fix merges, `main` IS the fixed template and the comparison silently inverts (it failed on
    main immediately after PR #67 landed). Deriving the pre-fix template from the current one keeps
    the proof true forever and needs no git at all."""
    stripped = re.sub(r"\{%-?\s*if\s+[a-z_]+\s*!=\s*(?:''|\"\")\s*-?%\}.*?"
                      r"\{%-?\s*endif\s*-?%\}", "", page_text, flags=re.S)
    stripped = re.sub(r"\{%-?\s*unless\s+[a-z_]+\s*==\s*(?:''|\"\")\s*-?%\}.*?"
                      r"\{%-?\s*endunless\s*-?%\}", "", stripped, flags=re.S)
    return stripped


def identity_of(row_html: str) -> str:
    """The first three rendered cells -- product, version(+build), method -- as visible text."""
    cells = re.findall(r"<span\b[^>]*>(.*?)</span>", row_html, re.S)[:3]
    return " | ".join(re.sub(r"<[^>]+>", " ", c).strip() for c in cells)


# ---------------------------------------------------------------- the suite


def run() -> int:
    print("=" * 74)
    print("Public method-health presentation -- exact-build identity")
    print("=" * 74)

    liquid_ok = liquid_render("{{ x }}", {"x": "ok"}) == "ok"
    if not liquid_ok:
        print("\n  (Ruby + liquid gem unavailable: render cases will SKIP, structure still checked)")

    FOUR = [health_row(b, status=s) for b, s in
            ((B110, "disabled"), (B124, "no_results"), (B158, "blocked"), (B190, "success"))]

    # ---------- M1: four sibling rows -> four distinct public identities ----------
    print("\n[M1] four 2607 siblings are four distinguishable patches")
    if not liquid_ok:
        skip("M1 (render)", "no Ruby/liquid")
    else:
        rows = rendered_rows(FOUR)
        check("M1 all four sibling rows render", len(rows) == 4, str(len(rows)))
        ids = [identity_of(r) for r in rows]
        check("M1 four DISTINCT identity strings", len(set(ids)) == 4, str(ids))
        for b in (B110, B124, B158, B190):
            check(f"M1 build {b} is stated on exactly one row",
                  sum(1 for r in rows if b in r) == 1)
        # Non-vacuity, proven by rendering rather than asserted: strip the build sub-label out of
        # THIS template and the four siblings collapse to a single identity again.
        old_ids = {identity_of(r) for r in rendered_rows(FOUR, page_text=without_build_label(PAGE))}
        check("M1 this is a real fix: without the build label the four collapse to ONE identity",
              len(old_ids) == 1, str(old_ids))

    # ---------- M2: the same method across siblings ----------
    print("\n[M2] the same method on every sibling stays attributable")
    if not liquid_ok:
        skip("M2 (render)", "no Ruby/liquid")
    else:
        same = [health_row(b, status="blocked") for b in (B110, B124, B158, B190)]
        rows = rendered_rows(same)
        check("M2 four rows for one method", len(rows) == 4)
        # Identical method AND identical status: before the fix these were byte-identical.
        check("M2 no two rows are byte-identical", len(set(rows)) == 4,
              f"{len(set(rows))} distinct of {len(rows)}")
        check("M2 every row names its own build",
              all(b in r for b, r in zip((B110, B124, B158, B190), rows)))

    # ---------- M3: differing health across siblings ----------
    print("\n[M3] each status stays attached to the build that earned it")
    if not liquid_ok:
        skip("M3 (render)", "no Ruby/liquid")
    else:
        rows = rendered_rows(FOUR)
        for build, status in ((B110, "disabled"), (B124, "no-results"),
                              (B158, "blocked"), (B190, "success")):
            owning = [r for r in rows if build in r]
            check(f"M3 {build} carries exactly its own status ({status})",
                  len(owning) == 1 and f"method-health-row--{status}" in owning[0],
                  owning[0][:120] if owning else "no row")
            others = [r for r in rows if build not in r]
            check(f"M3 no sibling inherits {build}",
                  all(build not in r for r in others))

    # ---------- M4: a sibling with no telemetry at all ----------
    print("\n[M4] a build with no health row is not implied by its siblings")
    if not liquid_ok:
        skip("M4 (render)", "no Ruby/liquid")
    else:
        # .20190 deliberately absent from the data entirely.
        three = [health_row(b, status=s) for b, s in
                 ((B110, "blocked"), (B124, "success"), (B158, "no_results"))]
        rows = rendered_rows(three)
        check("M4 only the three builds with telemetry render", len(rows) == 3)
        check("M4 the absent build is never named", all(B190 not in r for r in rows))
        # Behavioural: every rendered row's identity text must carry a build, so no row presents a
        # bare "2607" that a reader could take to cover the absent sibling. Pins the visible text,
        # not the element or its adjacency -- a correct fix is free to change either.
        check("M4 no row claims a bare version that could absorb it",
              all(re.search(r"\b2607\b.*\bBuild\s+20228\.\d+", identity_of(r)) for r in rows),
              str([identity_of(r) for r in rows]))

    # ---------- M5: version-only products are untouched ----------
    print("\n[M5] a non-build-aware product renders exactly as before")
    if not liquid_ok:
        skip("M5 (render)", "no Ruby/liquid")
    else:
        version_only = [
            health_row("", product="blackmagic-davinci", version="20.3.3", method="web_search"),
            health_row(None, product="adobe-acrobat-pro", version="26.001.21529",
                       method="adobe_community"),
        ]
        new_rows = rendered_rows(version_only)
        # A version-only product must render exactly as it would with no build label in the template
        # at all -- i.e. the change is provably invisible to the 1075 rows that have no build.
        old_rows = rendered_rows(version_only, page_text=without_build_label(PAGE))
        check("M5 byte-identical to a template with no build label at all", new_rows == old_rows,
              f"new={new_rows[0][:90]!r}")
        for label, rendered in zip(("davinci", "acrobat"), new_rows):
            # The Version cell is the second <span> of the row.
            version_cell = re.findall(r"<span\b[^>]*>.*?</span>", rendered, re.S)[1]
            check(f"M5 {label}: the Version cell emits no <small> element at all",
                  "<small>" not in version_cell, version_cell)
            for junk in ("Build ", "None", "null", "target_build"):
                check(f"M5 {label}: no {junk!r} placeholder in the row", junk not in rendered)
        # The NOTES cell already emits <small></small> on main -- that is the methodology page's own
        # `!= blank` no-op on blocked_reason, reported as backlog and deliberately not touched here.
        # Assert it is unchanged rather than pretending this fix cleaned it up.
        if old_rows is not None:
            check("M5 the Notes-cell <small> behaviour is untouched by this change",
                  [r.count("<small></small>") for r in new_rows]
                  == [r.count("<small></small>") for r in old_rows])

    # ---------- M6: ordering stays deterministic ----------
    print("\n[M6] ordering is unchanged and deterministic")
    loop = re.search(r"\{%\s*for item in ([a-z_]+)\s*%\}", PAGE).group(1)
    check("M6 the row loop still iterates the data array directly",
          loop == "method_health_rows")
    assign = re.search(r"\{%\s*assign method_health_rows = ([^%]+?)\s*%\}", PAGE).group(1)
    check("M6 no sort/group filter was introduced (that would churn every row)",
          "sort" not in assign and "group_by" not in assign, assign)
    if liquid_ok:
        rows_a = rendered_rows(FOUR)
        rows_b = rendered_rows(FOUR)
        check("M6 the render is stable across runs", rows_a == rows_b)
        check("M6 render order follows data order",
              [i for i, r in enumerate(rows_a) if B110 in r] == [0]
              and [i for i, r in enumerate(rows_a) if B190 in r] == [3])

    # ---------- M7: accessibility, not styling ----------
    print("\n[M7] the build identity reaches assistive technology as text")
    # Behavioural: the build must be OUTPUT by the template. Any local, and any filter chain on it
    # (`| escape` is a perfectly good future change), still satisfies this.
    page_build_local = next(iter(re.findall(r"assign\s+([a-z_]+)\s*=\s*item\.target_build\b", PAGE)),
                            "item.target_build")
    check("M7 the build is emitted as template text, not injected by CSS",
          bool(re.search(r"\{\{\s*(" + re.escape(page_build_local)
                         + r"|item\.target_build)\b[^}]*\}\}", PAGE)), page_build_local)
    check("M7 no CSS pseudo-element fabricates the build label",
          not re.search(r"\.method-health-row[^{]*::(before|after)[^}]*content", CSS))
    check("M7 it is a real element, not a bare <br> splitting one text run",
          "<br" not in method_health_block(PAGE))
    if liquid_ok:
        text_only = [re.sub(r"<[^>]+>", " ", r) for r in rendered_rows(FOUR)]
        check("M7 stripping ALL markup still leaves four distinct rows",
              len({re.sub(r"\s+", " ", t).strip() for t in text_only}) == 4)
        check("M7 each build survives markup-stripping",
              all(b in t for b, t in zip((B110, B124, B158, B190), text_only)))

    # ---------- structural invariant: header / cells / CSS grid agree ----------
    print("\n[grid] the column contract is internally consistent")
    head = re.search(r'source-health-row--head" role="row">\s*(.*?)\s*</div>', PAGE, re.S).group(1)
    headers = re.findall(r"<span\b[^>]*>(.*?)</span>", head, re.S)
    body = method_health_block(PAGE)
    body_rows = body[body.index("{% for item"):]
    cells = re.findall(r"<span\b[^>]*>", body_rows)
    grid = re.search(r"\.method-health-row \{[^}]*grid-template-columns:([^;]+);",
                     CSS).group(1).split()
    minw = int(re.search(r"\.method-health-row \{[^}]*min-width:\s*([0-9]+)px", CSS).group(1))
    check(f"grid: headers ({len(headers)}) == row cells ({len(cells)}) == CSS tracks ({len(grid)})",
          len(headers) == len(cells) == len(grid), f"{headers}")
    # The count is what matters -- adding a column would widen an already-scrolling table. The
    # min-width is asserted as "not increased", not pinned to a literal, so a future narrowing is
    # allowed but a widening is caught.
    check("grid: the fix added NO column, so the table did not get wider",
          len(grid) == 10 and minw <= 1480, f"tracks={len(grid)} min-width={minw}")
    check("grid: the header names the build, not just the version",
          "build" in headers[1].lower() and "version" in headers[1].lower(), headers[1])
    # Intent, not spelling: the build is emitted upstream of the Method cell, i.e. inside the
    # existing Version cell rather than as an eleventh column (the count check above covers that).
    before_method = re.split(r"<span\b[^>]*>\{\{ item\.method_id \}\}</span>", PAGE)[0]
    check("grid: the build rides in the Version cell, not a column of its own",
          bool(re.search(r"\{\{\s*(" + re.escape(page_build_local)
                         + r"|item\.target_build)\b", before_method)), page_build_local)

    # ---------- ARIA: a role="row" that owns no cells associates nothing ----------
    print("\n[aria] every table row exposes real cells")
    # Both health tables are div-based, so no cell role is implied by the tag name the way it is
    # for <td>/<th>. An element with role="row" whose children carry no cell role exposes ZERO
    # cells, and a screen reader then cannot say which column a value sits under -- the same
    # header-to-value association this page relies on to keep sibling builds apart.
    aria_rows = re.findall(r'(<div class="source-health-row[^"]*" role="row">)(.*?)\n      </div>', PAGE, re.S)
    check(f"aria: both tables' head and body rows are found ({len(aria_rows)})",
          len(aria_rows) == 4, [o for o, _ in aria_rows])
    for open_tag, blk in aria_rows:
        want = "columnheader" if "--head" in open_tag else "cell"
        spans = re.findall(r"<span\b[^>]*>", blk)
        label = ("head" if "--head" in open_tag else "body") + (
            " method-health" if "method-health-row" in open_tag else " source-health")
        bare = [t for t in spans if f'role="{want}"' not in t]
        check(f'aria: {label} row -- all {len(spans)} cells carry role="{want}"',
              bool(spans) and not bare, bare[:3])
    # ---------- the guard idiom: `!= blank` must never gate a build ----------
    print("\n[guard] the build guard must actually be able to be false")
    # `!= blank` is one spelling of an always-true comparison; `!= nil` and `!= false` are others,
    # and a regex banning only the first spelling leaves the same bug reachable. Assert POSITIVELY
    # that every build guard tests emptiness, and ban the always-true family as a whole. What is
    # pinned is the SEMANTICS -- an emptiness test on a `default`-normalised local -- not a name.
    ALWAYS_TRUE = r"!=\s*(blank|nil|null|false)\b"
    # Discover the build locals from the templates rather than hardcoding their names, so renaming
    # one is not a test failure. A build local is anything assigned from item.target_build.
    def build_locals(src: str) -> set[str]:
        return set(re.findall(r"assign\s+([a-z_]+)\s*=\s*item\.target_build\b", src))

    page_locals, row_locals = build_locals(PAGE), build_locals(ROW)
    check("guard: each template derives a build local from item.target_build",
          len(page_locals) == 1 and len(row_locals) == 1, f"page={page_locals} row={row_locals}")
    names = page_locals | row_locals
    # `if x != ''` and `unless x == ''` are equivalent and both acceptable; what is rejected is a
    # comparison that can never be false.
    build_guards = re.findall(
        r"\{%-?\s*(if|unless)\s+([a-z_]+)\s*(!=|==)\s*([^%]*?)\s*-?%\}", PAGE + "\n" + ROW)
    build_conds = [g for g in build_guards if g[1] in names]

    def is_emptiness_test(tag, _name, op, rhs):
        return rhs in ("''", '""') and ((tag == "if" and op == "!=") or (tag == "unless" and op == "=="))

    check("guard: every build guard is an emptiness test, not an always-true comparison",
          bool(build_conds) and all(is_emptiness_test(*g) for g in build_conds), str(build_conds))
    check("guard: no build guard uses blank/nil/null/false (all always-true here)",
          not re.search(r"(target_build|" + "|".join(sorted(names) or ["_"]) + r")[^%]*" + ALWAYS_TRUE,
                        PAGE + "\n" + ROW))
    check("guard: every build local is normalised through `default` first",
          all(re.search(r"assign\s+" + n + r"\s*=\s*item\.target_build\s*\|\s*default:\s*(''|\"\")", src)
              for src, ns in ((PAGE, page_locals), (ROW, row_locals)) for n in ns))
    row_name = next(iter(row_locals), None)
    check("guard: the patch-history include guards BOTH of its build sites",
          len([g for g in build_conds if g[1] == row_name]) == 2,
          str([g for g in build_conds if g[1] == row_name]))

    # The build sub-label must never break mid-digit -- .source-health-row span sets
    # overflow-wrap:anywhere and the sub-label INHERITS it, which would split "20228.20110" into
    # "20228.2012" / "6" and show an identity that was never stored. The CSS override and the class
    # actually emitted must stay in agreement, or the rule silently stops applying.
    override = re.search(r"\.method-health-row\s+\.([a-z-]+)\s*\{[^}]*overflow-wrap:\s*normal", CSS)
    check("wrap: an overflow-wrap override exists for the build sub-label", bool(override),
          "no `.method-health-row .<class> { overflow-wrap: normal }` rule found")
    if override:
        check("wrap: the class it targets is the one the template emits",
              f'class="{override.group(1)}"' in method_health_block(PAGE), override.group(1))
    check("wrap: the row still sets overflow-wrap:anywhere for ordinary cells (unchanged)",
          "overflow-wrap: anywhere" in CSS)
    if liquid_ok:
        # Prove the no-op rather than asserting it, so this test explains itself if it ever fails.
        blank_out = liquid_render("[{% if v != blank %}Build {{ v }}{% endif %}]", {"v": ""})
        guard_out = liquid_render(
            "[{% assign b = v | default: '' %}{% if b != '' %}Build {{ b }}{% endif %}]", {"v": ""})
        check("guard: `!= blank` really does fire on an empty string (the bug)",
              blank_out == "[Build ]", repr(blank_out))
        check("guard: the empty-string guard really does suppress it (the fix)",
              guard_out == "[]", repr(guard_out))

    # ---------- patch-history row: build-aware unchanged, version-only repaired ----------
    print("\n[history] the patch-history Version cell stops asserting a build it lacks")
    if not liquid_ok:
        skip("history (render)", "no Ruby/liquid")
    else:
        frag_new = version_cell_fragment(ROW)
        # The PRE-FIX fragment, reconstructed rather than fetched from git: put the always-true
        # `!= blank` guard back. Comparing against `main` would be self-invalidating once this
        # merges, and would silently start comparing the fix against itself.
        frag_old = re.sub(r"([a-z_]+)\s*!=\s*(?:''|\"\")", r"\1 != blank", frag_new)
        check("history: the pre-fix fragment really is the buggy one",
              "!= blank" in frag_old and "!= ''" not in frag_old, frag_old[:120])
        ppt_item = {"update_version": "2607", "target_build": B110}
        dav_item = {"update_version": "21.0.4", "target_build": ""}
        acr_item = {"update_version": "26.001.21529"}

        def cells(text, item):
            """The rendered data-version + Version <td>; blank lines dropped so what is compared is
            the emitted HTML rather than incidental template layout."""
            out = liquid_render(text, {"item": item}) or ""
            return "\n".join(ln for ln in out.splitlines() if ln.strip())

        new_ppt = cells(frag_new, ppt_item)
        # A build-aware row is unaffected by the guard change: the old always-true guard and the new
        # emptiness guard both fire when a build is actually present.
        check("history: a build-aware row renders identically under the OLD buggy guard",
              new_ppt == cells(frag_old, ppt_item), new_ppt)
        # ...and the version-only case is exactly where they diverge, which is the whole defect.
        check("history: the OLD guard really did emit a dangling 'Build ' for a version-only row",
              "Build </span>" in cells(frag_old, dav_item), cells(frag_old, dav_item))
        check("history: it still states the build and the sort key still carries it",
              f"Build {B110}" in new_ppt and f'data-version="2607.{B110}"' in new_ppt, new_ppt)

        for label, item, version in (("davinci", dav_item, "21.0.4"),
                                     ("acrobat", acr_item, "26.001.21529")):
            out = cells(frag_new, item)
            check(f"history: {label} no longer renders a dangling 'Build '",
                  "Build " not in out and "patch-cell-version__build" not in out, out)
            check(f"history: {label} sort key loses the stray trailing dot",
                  f'data-version="{version}"' in out, out)
            check(f"history: {label} still shows its version",
                  f">{version}</td>" in out, out)

        # KNOWN, ACCEPTED consequence. The old sort keys carried a spurious trailing dot on every
        # version-only row, and for one live DaVinci pair that dot WAS the tiebreak: ICU compared
        # '.' against ' ' and put the beta ahead of the GA release. Removing the corruption flips
        # that one pair to plain prefix order. Pinned so it stays a deliberate, known effect rather
        # than an accidental one -- and so the claim "ordering cannot change" is never re-asserted.
        node = shutil.which("node")
        if not node:
            skip("history (sort)", "node unavailable")
        else:
            probe = (
                "const {compareVersion} = await import('./auxsays/assets/js/patch-table-sort.mjs');"
                "console.log(JSON.stringify(["
                "compareVersion('21.','21 Public Beta 1.'),"
                "compareVersion('21','21 Public Beta 1'),"
                "compareVersion('21.0.4','21.0.10'),"
                "compareVersion('2607','2605')]));")
            res = subprocess.run([node, "-e", probe, "--input-type=module"],
                                 capture_output=True, text=True, cwd=str(_REPO), timeout=120)
            vals = json.loads(res.stdout.strip().splitlines()[-1]) if res.returncode == 0 else None
            check("history: exactly the known DaVinci beta/GA pair changes order",
                  vals is not None and vals[0] > 0 and vals[1] < 0, str(vals))
            check("history: ordinary numeric version ordering is unaffected",
                  vals is not None and vals[2] < 0 and vals[3] > 0, str(vals))

    # ---------- #66 regressions must still hold ----------
    print("\n[M8/M9] the build-aware joins from #66 are untouched")
    mon = MON_PATH.read_text(encoding="utf-8")
    check("M8 monitoring still joins on the build at all three sites",
          mon.count("== mon_build") == 3, str(mon.count("== mon_build")))
    # Per CALL, not per file: counting target_build= file-wide against monitoring-status.html
    # file-wide passes even if one call site drops it and another gains a duplicate.
    missing = []
    for caller in ("_layouts/aux-update.html", "_layouts/aux-updates.html",
                   "_includes/patch-table-row.html"):
        text = (_AUX / caller).read_text(encoding="utf-8")
        for call in re.findall(r"\{%\s*include monitoring-status\.html[^%]*%\}", text):
            if "target_build=" not in call:
                missing.append(f"{caller}: {call[:70]}")
    check("M8 every individual monitoring include passes target_build", not missing, str(missing))
    acr = (_AUX / "scripts" / "apply_consensus_to_records.py").read_text(encoding="utf-8")
    check("M9 the source-limitation join is still the full identity triple",
          "key_from(row) == target" in acr and "patch_key(pid, ver, build)" in acr)
    # Behavioural: `build` must be keyword-only with NO default, whatever else the signature holds.
    import inspect as _inspect  # noqa: PLC0415
    sys.path.insert(0, str(_AUX / "scripts"))
    import apply_consensus_to_records as _acr  # noqa: PLC0415
    params = _inspect.signature(_acr._public_source_limitations).parameters
    check("M9 build is still a REQUIRED keyword-only argument there",
          "build" in params
          and params["build"].kind is _inspect.Parameter.KEYWORD_ONLY
          and params["build"].default is _inspect.Parameter.empty,
          str(params.get("build")))

    print()
    print("=" * 74)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed"
          + (f", {_SKIP} skipped" if _SKIP else ""))
    if _ERRORS:
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 74)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
