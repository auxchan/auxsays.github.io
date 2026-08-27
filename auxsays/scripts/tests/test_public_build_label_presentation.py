#!/usr/bin/env python3
"""The PUBLIC LABEL of a patch must state the build that patch actually is.

A build-aware product ships several builds under one marketing version, and the whole point of
`patch_identity` is that those are DIFFERENT patches. The public label did not know that. It is
baked once, at record CREATE time, by `write_update_record._public_version_label`, and
`refresh_existing_record` never rewrites it -- so the 20 PowerPoint records written before the
writer learned about builds carried a bare "2607" forever, in `title`, `description`,
`update_feed_title` and `update_detail_title`. Every one of those strings is rendered immediately
beside a per-BUILD monitoring status: the reader saw a health state for one exact build next to a
headline that would not say which build it was, and the moment a sibling ingests it would arrive
carrying "(Build ...)" while its older sibling kept a bare label under the same version.

This locks the fix and the constraints that bound it:

  - a build-aware record states its build on every public surface -- the detail H1, both patch-feed
    card titles, the home signal card, the detail-page citation, and the two front-matter fields
    jekyll-seo-tag reads for <title> / og:title / the meta description;
  - a version-only product renders BYTE-IDENTICALLY to before -- no "(Build )", no empty parens, no
    placeholder, no inherited sibling build;
  - the repair never manufactures attribution: no stored build, no label, no guess;
  - consensus still cannot rewrite a title.

The rendering assertions run the VERBATIM shipped Liquid -- the real `_includes/patch-public-label.html`
and real slices of the three shipped layouts -- through the liquid gem, with a minimal shim for
Jekyll's `{% include file.html k=v %}` tag syntax (stock Liquid uses a different one). Where Ruby or
the liquid gem is unavailable those cases SKIP and the structural, corpus and repair-script
assertions still run.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_public_build_label_presentation.py
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
_SCRIPTS = _AUX / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import normalize_public_build_labels as repair  # noqa: E402
import qa_patch_records as qa  # noqa: E402
from lib import write_update_record as wur  # noqa: E402
from lib.patch_identity import is_build_aware  # noqa: E402

INCLUDES_DIR = _AUX / "_includes"
LABEL_INCLUDE_PATH = INCLUDES_DIR / "patch-public-label.html"
DETAIL_PATH = _AUX / "_layouts" / "aux-update.html"
FEED_PATH = _AUX / "_layouts" / "aux-updates.html"
HOME_PATH = _AUX / "_layouts" / "aux-home.html"
GENERATED_DIR = _AUX / "updates" / "generated"

LABEL_INCLUDE = LABEL_INCLUDE_PATH.read_text(encoding="utf-8")
DETAIL = DETAIL_PATH.read_text(encoding="utf-8")
FEED = FEED_PATH.read_text(encoding="utf-8")
HOME = HOME_PATH.read_text(encoding="utf-8")

PPT = "microsoft-powerpoint"
PRODUCT_NAME = "Microsoft PowerPoint"
V = "2608"
B100, B112 = "20326.20100", "20326.20112"
DAV = "blackmagic-davinci"

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


# ---------------------------------------------------------------- real Liquid render

# Stock Liquid's include tag is `{% include 'name', k: v %}`; Jekyll's is `{% include name.html k=v %}`
# and it renders the included file in a PUSHED scope with an `include` hash. The shim below is that
# and nothing more, so what is rendered is the shipped include file itself, not a paraphrase of it.
_RENDER_SCRIPT = r"""
require 'liquid'
require 'json'

payload = JSON.parse(File.read(ARGV[0]))
$includes_dir = payload['includes_dir']

class JekyllInclude < Liquid::Tag
  def initialize(tag_name, markup, options)
    super
    m = markup.strip.match(%r{\A([\w\-./]+)(.*)\z}m)
    @file = m[1]
    @params = {}
    m[2].scan(/(\w+)\s*=\s*("[^"]*"|'[^']*'|[^\s]+)/) { |k, v| @params[k] = v }
  end

  def render(context)
    tpl = Liquid::Template.parse(File.read(File.join($includes_dir, @file)))
    vars = {}
    @params.each { |k, v| vars[k] = context[v] }
    context.stack do
      context['include'] = vars
      tpl.render!(context)
    end
  end
end
Liquid::Template.register_tag('include', JekyllInclude)

tpl = Liquid::Template.parse(payload['template'])
# render! (not render): a Liquid error must RAISE, not land in the output as text an assertion
# could read straight past.
print tpl.render!(payload['vars'])
"""


def liquid_render(template: str, variables: dict) -> str | None:
    """Render `template` with the real liquid gem. None if Ruby/liquid is unavailable."""
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "render.rb"
        script.write_text(_RENDER_SCRIPT, encoding="utf-8")
        payload = Path(td) / "payload.json"
        payload.write_text(json.dumps({"template": template, "vars": variables,
                                       "includes_dir": str(INCLUDES_DIR)}), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload)],
                              capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            return None
        return proc.stdout


def text_of(rendered: str | None) -> str:
    """Rendered output as collapsed visible text, so assertions read the label not the layout."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", rendered or "")).strip()


# ---------------------------------------------------------------- shipped template slicing


def lines_matching(source: str, *patterns: str) -> str:
    """The shipped lines matching these patterns, verbatim and in file order.

    Same idiom the method-health suite uses: assemble a renderable fragment out of REAL lines
    rather than retyping them, so the test cannot drift from what ships."""
    keep = [ln for ln in source.splitlines()
            if any(re.search(p, ln) for p in patterns)]
    return "\n".join(keep)


def _slice(source: str, start: str, end: str, count: int = 1) -> list[str]:
    """Verbatim shipped slices, each running from the `start` line through the `end` line."""
    lines = source.splitlines(keepends=True)
    starts = [i for i, ln in enumerate(lines) if re.search(start, ln)]
    out = []
    for index in starts:
        stop = next(j for j in range(index, len(lines)) if re.search(end, lines[j]))
        out.append("".join(lines[index:stop + 1]))
    assert len(out) == count, f"expected {count} shipped slice(s), found {len(out)}"
    return out


def detail_title_block() -> str:
    """Just the shipped title-resolution assigns on the patch-detail page."""
    return lines_matching(DETAIL, r"assign stored_title", r"capture display_title",
                          r"capture citation_title", r"if citation_title == ''")


def detail_fragment() -> str:
    """The detail title resolution plus the H1 and the citation link that render it, verbatim."""
    h1 = lines_matching(DETAIL, r'<h1 class="update-title">')
    citation = lines_matching(DETAIL, r'<a href="\{\{ page\.update_source_url \}\}">')
    return "\n".join([detail_title_block(), h1, citation])


def feed_title_blocks() -> list[str]:
    """Both shipped patch-feed card-title blocks, each through its own <h2>, verbatim."""
    return _slice(FEED, r"assign card_title = item\.update_feed_title",
                  r'<h2 class="patch-card-title">', count=2)


def home_fragment() -> str:
    return lines_matching(HOME, r"assign home_stored_title", r"capture home_patch_title",
                          r"<strong>\{\{ home_patch_title \}\}</strong>")


def as_prefix_template(fragment: str) -> str:
    """The PRE-FIX fragment: the label include replaced by the stored label used as-is.

    Derived from the shipped template rather than fetched from git, so the non-vacuity proof stays
    true after this merges instead of silently comparing the fix against itself."""
    return re.sub(r"\{%\s*include patch-public-label\.html\s+label=([\w.]+)[^%]*%\}",
                  r"{{ \1 }}", fragment)


def page_vars(build: str | None, *, version: str = V, product: str = PPT,
              name: str = PRODUCT_NAME, stored: str | None = None) -> dict:
    """One record's front matter as the layouts see it.

    build=None omits the target_build KEY entirely (a record predating the field), which is a
    different case from build='' (the key present and empty, what a version-only product stores)."""
    label = stored if stored is not None else f"{name} {version}"
    data = {
        "product_id": product, "update_version": version, "update_product": name,
        "update_source_name": "Microsoft", "update_feed_title": label,
        "update_detail_title": label, "title": f"{label} official update breakdown",
        "update_source_url": "https://learn.microsoft.com/en-us/officeupdates/current-channel",
        "update_published_at": "2026-08-18T00:00:00Z",
        "url": f"/updates/microsoft/{product}/{version}/",
    }
    if build is not None:
        data["target_build"] = build
    return data


# ---------------------------------------------------------------- the suite


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Public patch label -- exact-build identity")
    print("=" * 78)

    liquid_ok = liquid_render("{{ x }}", {"x": "ok"}) == "ok"
    include_ok = liquid_ok and liquid_render(
        "{% include patch-public-label.html label='A 1' target_build='9.9' %}", {}) == "A 1 (Build 9.9)"
    if not liquid_ok:
        print("\n  (Ruby + liquid gem unavailable: render cases SKIP, structure still checked)")
    elif not include_ok:
        print("\n  (the Jekyll include shim did not resolve: render cases SKIP)")

    # ---------- L1: the include contract ----------
    print("\n[L1] the shared label include states a build only when the record has one")
    if not include_ok:
        skip("L1 (render)", "no Ruby/liquid include render")
    else:
        def label(stored, build):
            return liquid_render(
                "{% include patch-public-label.html label=l target_build=b %}",
                {"l": stored, "b": build})

        check("L1 a build-aware label gains exactly its own build",
              label("Microsoft PowerPoint 2608", B100) == "Microsoft PowerPoint 2608 (Build 20326.20100)",
              repr(label("Microsoft PowerPoint 2608", B100)))
        # The corpus is PERMANENTLY mixed: the write path bakes "(Build X)" into every new record
        # while the 20 older ones were written bare. A renderer that is not idempotent would double
        # the marker on every record created from now on.
        already = "Microsoft PowerPoint 2608 (Build 20326.20100)"
        check("L1 a label that already states this build is passed through untouched",
              label(already, B100) == already, repr(label(already, B100)))
        check("L1 the marker is never doubled", label(already, B100).count("(Build") == 1)
        # The whole reason this include exists rather than a template-level string append.
        for build in ("", None):
            out = label("DaVinci Resolve 20.3.3", build)
            check(f"L1 target_build={build!r}: renders the stored label verbatim",
                  out == "DaVinci Resolve 20.3.3", repr(out))
            for junk in ("Build", "(", ")", "None", "null"):
                check(f"L1 target_build={build!r}: no {junk!r} anywhere in the output",
                      junk not in out, repr(out))
        check("L1 an empty label with a build stays empty (no orphan marker)",
              label("", B100) == "", repr(label("", B100)))
        # Not the same test as the idempotence one above: the marker is matched EXACTLY, so a build
        # merely mentioned in prose does not suppress the identity marker.
        check("L1 a build mentioned in prose does not count as the marker",
              label("PowerPoint 2608 build 20326.20100 notes", B100).endswith("(Build 20326.20100)"))

    # ---------- L2: the patch-detail page ----------
    print("\n[L2] the detail H1 and citation state the build")
    frag = detail_fragment()
    check("L2 the fragment really is the shipped one (H1 + citation + all three assigns)",
          frag.count("patch-public-label.html") == 2 and "update-title" in frag
          and "update_source_url" in frag, frag[:160])
    if not include_ok:
        skip("L2 (render)", "no Ruby/liquid include render")
    else:
        out = liquid_render(frag, {"page": page_vars(B100)})
        check("L2 the H1 names the exact build",
              f"{PRODUCT_NAME} {V} (Build {B100})" in text_of(out), text_of(out))
        check("L2 the citation link names it too",
              text_of(out).count(f"(Build {B100})") == 2, text_of(out))
        # The defect, stated as the reader saw it.
        old = liquid_render(as_prefix_template(frag), {"page": page_vars(B100)})
        check("L2 this is a real fix: the pre-fix H1 named only the version",
              f"(Build {B100})" not in text_of(old) and f"{PRODUCT_NAME} {V}" in text_of(old),
              text_of(old))
        # A record that never had the field at all must not crash or invent one.
        bare = liquid_render(frag, {"page": page_vars(None, product=DAV, name="DaVinci Resolve",
                                                      version="20.3.3")})
        check("L2 a version-only record renders exactly as the pre-fix template does",
              bare == liquid_render(as_prefix_template(frag),
                                    {"page": page_vars(None, product=DAV, name="DaVinci Resolve",
                                                       version="20.3.3")}), text_of(bare))
        check("L2 a version-only record emits no build vocabulary at all",
              "Build" not in (bare or ""), text_of(bare))

    # ---------- L3: both patch-feed grids ----------
    print("\n[L3] both patch-feed card titles state the build")
    frags = feed_title_blocks()
    check("L3 both shipped card-title blocks were found", len(frags) == 2, str(len(frags)))
    check("L3 both go through the shared include",
          all("patch-public-label.html" in f for f in frags))
    if not include_ok or len(frags) != 2:
        skip("L3 (render)", "no Ruby/liquid include render, or blocks not found")
    else:
        for index, fragment in enumerate(frags):
            out = text_of(liquid_render(fragment, {"item": page_vars(B100)}))
            check(f"L3 grid {index}: the card title names the exact build",
                  out == f"{PRODUCT_NAME} {V} (Build {B100})", out)
            dav = page_vars("", product=DAV, name="DaVinci Resolve", version="20.3.3")
            new_out = liquid_render(fragment, {"item": dav})
            old_out = liquid_render(as_prefix_template(fragment), {"item": dav})
            check(f"L3 grid {index}: a version-only card is byte-identical to pre-fix",
                  new_out == old_out, repr(text_of(new_out)))
            # The fallback chain the `!= blank` no-op had made unreachable. Every shipped record
            # carries update_feed_title, so this is a latent path -- pinned so the corrected guards
            # are proven to actually branch rather than merely look correct.
            no_feed = {k: v for k, v in page_vars(B100).items() if k != "update_feed_title"}
            check(f"L3 grid {index}: with no stored feed title it falls back to product+version",
                  text_of(liquid_render(fragment, {"item": no_feed}))
                  == f"{PRODUCT_NAME} {V} (Build {B100})",
                  text_of(liquid_render(fragment, {"item": no_feed})))
            only_title = {k: v for k, v in no_feed.items()
                          if k not in ("update_product", "update_version")}
            only_title["title"] = "Fallback headline"
            check(f"L3 grid {index}: with neither, it falls back to the record title",
                  text_of(liquid_render(fragment, {"item": only_title}))
                  == f"Fallback headline (Build {B100})",
                  text_of(liquid_render(fragment, {"item": only_title})))

    # ---------- L4: the home signal card ----------
    print("\n[L4] the home signal card states the build")
    home = home_fragment()
    check("L4 the shipped home card goes through the shared include",
          "patch-public-label.html" in home, home[:160])
    if not include_ok:
        skip("L4 (render)", "no Ruby/liquid include render")
    else:
        check("L4 the home card names the exact build",
              text_of(liquid_render(home, {"item": page_vars(B100)}))
              == f"{PRODUCT_NAME} {V} (Build {B100})",
              text_of(liquid_render(home, {"item": page_vars(B100)})))
        dav = page_vars("", product=DAV, name="DaVinci Resolve", version="20.3.3")
        check("L4 a version-only card is byte-identical to pre-fix",
              liquid_render(home, {"item": dav})
              == liquid_render(as_prefix_template(home), {"item": dav}))

    # ---------- L5: siblings under one version are distinguishable ----------
    print("\n[L5] two builds of one version are two distinguishable patches")
    if not include_ok or len(frags) != 2:
        skip("L5 (render)", "no Ruby/liquid include render")
    else:
        surfaces = [("detail", detail_fragment(), "page"), ("home", home_fragment(), "item")]
        surfaces += [(f"feed{i}", f, "item") for i, f in enumerate(frags)]
        for name, fragment, var in surfaces:
            a = text_of(liquid_render(fragment, {var: page_vars(B100)}))
            b = text_of(liquid_render(fragment, {var: page_vars(B112)}))
            check(f"L5 {name}: the two siblings render DIFFERENT labels", a != b, f"{a!r} == {b!r}")
            check(f"L5 {name}: each names its own build and never the sibling's",
                  B100 in a and B112 not in a and B112 in b and B100 not in b, f"{a} / {b}")
            # Non-vacuity, proven by rendering: strip the include and they collapse to one label.
            old_a = text_of(liquid_render(as_prefix_template(fragment), {var: page_vars(B100)}))
            old_b = text_of(liquid_render(as_prefix_template(fragment), {var: page_vars(B112)}))
            check(f"L5 {name}: pre-fix, the two siblings were indistinguishable",
                  old_a == old_b, f"{old_a!r} vs {old_b!r}")

    # ---------- guard idiom ----------
    print("\n[guard] no always-true guard may gate a build")
    # `!= blank` is one spelling of an always-true comparison in this stack; `!= nil` and `!= false`
    # are others. Ban the family in the include, and assert POSITIVELY that its guards test
    # emptiness. The semantics are pinned, not the local names.
    # Comments are stripped first: the include DOCUMENTS the always-true family in prose, and a
    # regex that cannot tell prose from code would either fail on the documentation or force the
    # documentation out.
    include_code = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "",
                          LABEL_INCLUDE, flags=re.S)
    check("guard: the include's CODE contains no always-true comparison",
          not re.search(r"!=\s*(blank|nil|null|false)\b", include_code), include_code)
    guarded = set(re.findall(r"([\w.]+)\s*!=\s*(?:''|\"\")", include_code))
    normalised = set(re.findall(r"assign\s+([\w.]+)\s*=\s*include\.\w+\s*\|\s*default:\s*''",
                                LABEL_INCLUDE))
    check("guard: both inputs are normalised through `default` and tested for emptiness",
          len(normalised) == 2 and normalised == guarded, f"normalised={normalised} guarded={guarded}")
    # Liquid PARSES tags inside a comment block, so a literal example tag written INSIDE one is a
    # build-breaking syntax error, not documentation -- an unbalanced `endcomment` aborts the whole
    # render. Found the hard way while writing this suite. Checked across every file this change
    # added comments to, since the failure is total rather than local.
    smuggled = [f"{path.name}: {body.strip()[:60]}"
                for path in (LABEL_INCLUDE_PATH, DETAIL_PATH, FEED_PATH, HOME_PATH)
                for body in re.findall(r"(?s)\{%-?\s*comment\s*-?%\}(.*?)\{%-?\s*endcomment\s*-?%\}",
                                       path.read_text(encoding="utf-8"))
                if "{%" in body or "{{" in body]
    check("guard: no comment block smuggles a parseable tag into a shipped template",
          not smuggled, str(smuggled))
    # The title-resolution blocks this change rewrote must not reintroduce the no-op. Scoped to the
    # resolution assigns: the surrounding shipped markup carries its own pre-existing `!= blank`
    # usages, which are real backlog but are not what this change touched or claims to have fixed.
    for name, fragment in (("detail", detail_title_block()), ("home", home_fragment()),
                           *[(f"feed{i}", f) for i, f in enumerate(frags)]):
        check(f"guard: the {name} title block uses no always-true comparison",
              not re.search(r"!=\s*(blank|nil|null|false)\b", fragment), fragment[:200])
    if liquid_ok:
        # Prove the no-op rather than asserting it, so this explains itself if it ever fails.
        check("guard: `!= blank` really does fire on an empty string (the bug)",
              liquid_render("[{% if v != blank %}Build {{ v }}{% endif %}]", {"v": ""}) == "[Build ]")
        check("guard: the empty-string guard really does suppress it (the fix)",
              liquid_render("[{% assign b = v | default: '' %}{% if b != '' %}Build {{ b }}{% endif %}]",
                            {"v": ""}) == "[]")

    # ---------- wiring: every public headline goes through one authority ----------
    print("\n[wiring] every rendered patch headline resolves its build the same way")
    calls = {p.name: len(re.findall(r"\{%\s*include patch-public-label\.html[^%]*%\}",
                                    p.read_text(encoding="utf-8")))
             for p in (DETAIL_PATH, FEED_PATH, HOME_PATH)}
    check("wiring: detail (H1 + citation), feed (both grids), home (card) all call the include",
          calls == {"aux-update.html": 2, "aux-updates.html": 2, "aux-home.html": 1}, str(calls))
    missing = [c for p in (DETAIL_PATH, FEED_PATH, HOME_PATH)
               for c in re.findall(r"\{%\s*include patch-public-label\.html[^%]*%\}",
                                   p.read_text(encoding="utf-8"))
               if "target_build=" not in c]
    check("wiring: every individual call passes a target_build", not missing, str(missing))
    # #66's build-aware monitoring join is what makes a bare headline a contradiction; if it ever
    # stopped joining on the build this fix would be solving a problem that no longer exists.
    mon_missing = [c for p in (DETAIL_PATH, FEED_PATH)
                   for c in re.findall(r"\{%\s*include monitoring-status\.html[^%]*%\}",
                                       p.read_text(encoding="utf-8"))
                   if "target_build=" not in c]
    check("wiring: the per-build monitoring join beside these headlines is untouched",
          not mon_missing, str(mon_missing))

    # ---------- R1: the repair never manufactures attribution ----------
    print("\n[R1] the stored-label repair refuses to guess")
    def record_text(**over) -> str:
        front = {"layout": "aux-update", "title": f"{PRODUCT_NAME} {V} official update breakdown",
                 "description": f"Official {PRODUCT_NAME} update record captured from Microsoft.",
                 "product_id": PPT, "update_product": PRODUCT_NAME,
                 "update_source_name": "Microsoft", "update_version": f"'{V}'",
                 "target_build": f"'{B100}'"}
        front.update(over)
        body = "\n".join(f"{k}: {v}" for k, v in front.items() if v is not None)
        return f"---\n{body}\n---\n\nRecord body, untouched.\n"

    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        (out / "no-build.md").write_text(record_text(target_build="''"), encoding="utf-8")
        (out / "absent-build.md").write_text(record_text(target_build=None), encoding="utf-8")
        (out / "authored.md").write_text(
            record_text(title="Everything you need to know about PowerPoint 2608"), encoding="utf-8")
        (out / "version-only.md").write_text(
            record_text(product_id=DAV, update_product="DaVinci Resolve",
                        update_source_name="Blackmagic Design", update_version="'20.3.3'",
                        target_build="''"), encoding="utf-8")
        (out / "stale.md").write_text(record_text(), encoding="utf-8")
        before = {p.name: p.read_text(encoding="utf-8") for p in out.glob("*.md")}
        plans = {p["path"].name: p for p in (repair.plan_record(q) for q in sorted(out.glob("*.md")))}

        check("R1 a build-aware record with an EMPTY build is reported, not relabelled",
              plans["no-build.md"]["status"] == "no_build" and not plans["no-build.md"]["changes"],
              str(plans["no-build.md"]))
        check("R1 a build-aware record with NO target_build key is reported, not relabelled",
              plans["absent-build.md"]["status"] == "no_build",
              str(plans["absent-build.md"]))
        check("R1 a version-only product is not considered at all",
              plans["version-only.md"]["status"] == "skipped", str(plans["version-only.md"]))
        check("R1 a hand-authored title is left untouched",
              "title" not in plans["authored.md"]["changes"], str(plans["authored.md"]))
        check("R1 ...but its engine-written description is still repaired",
              B100 in plans["authored.md"]["changes"].get("description", ""),
              str(plans["authored.md"]["changes"]))
        check("R1 the untouched title is reported rather than silently skipped",
              any("not an engine-written label" in n for n in plans["authored.md"]["notes"]),
              str(plans["authored.md"]["notes"]))
        check("R1 the ordinary stale record is the one that gets repaired",
              set(plans["stale.md"]["changes"]) == {"title", "description"},
              str(plans["stale.md"]["changes"]))

        repair.run(apply=True, generated_dir=out)
        after = {p.name: p.read_text(encoding="utf-8") for p in out.glob("*.md")}
        for name in ("no-build.md", "absent-build.md", "version-only.md"):
            check(f"R1 {name} is byte-identical after --apply", before[name] == after[name])
        check("R1 no record anywhere gained an empty build marker",
              not any("(Build )" in t or "Build ''" in t for t in after.values()))

    # ---------- R2: the repair is surgical, exact and idempotent ----------
    print("\n[R2] the repair changes two fields and nothing else")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        path = out / "stale.md"
        path.write_text(record_text(), encoding="utf-8")
        original = path.read_text(encoding="utf-8")
        repair.run(apply=True, generated_dir=out)
        updated = path.read_text(encoding="utf-8")

        before_front, before_body = repair.split_front_matter(original)
        after_front, after_body = repair.split_front_matter(updated)
        check("R2 the record body is untouched", before_body == after_body)
        b, a = repair._parse(original), repair._parse(updated)
        check("R2 no front-matter key is added or removed", set(a) == set(b), str(set(a) ^ set(b)))
        check("R2 exactly title and description changed",
              {k for k in b if b[k] != a[k]} == {"title", "description"},
              str({k for k in b if b[k] != a[k]}))
        untouched_lines = [ln for ln in before_front.splitlines()
                           if not ln.startswith(("title:", "description:"))]
        check("R2 every other front-matter line is byte-identical",
              untouched_lines == [ln for ln in after_front.splitlines()
                                  if not ln.startswith(("title:", "description:"))])
        # ONE authority for the string: the repaired value is what the writer itself produces.
        written = wur.build_front_matter({
            "company_id": "microsoft", "product_id": PPT, "version": V, "target_build": B100,
            "software": PRODUCT_NAME, "company": "Microsoft",
            "published_at": "2026-08-18T00:00:00Z"})
        check("R2 the repaired title is exactly what the writer would have written",
              a["title"] == written["title"], f"{a['title']!r} vs {written['title']!r}")
        check("R2 the repaired description is exactly what the writer would have written",
              a["description"] == written["description"],
              f"{a['description']!r} vs {written['description']!r}")
        check("R2 the repair is idempotent",
              repair.run(apply=False, generated_dir=out) == 0
              and path.read_text(encoding="utf-8") == updated)
        check("R2 the repaired record passes the QA gate", not [
            e for e in qa.scan_record(path)[0] if e["code"] == "public_label_missing_build"])

    # ---------- R3: the QA gate is the invariant, not the script ----------
    print("\n[R3] the gate catches a build-free public label on its own")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        stale = out / "stale.md"
        stale.write_text(record_text(), encoding="utf-8")
        codes = {e["code"] for e in qa.scan_record(stale)[0]}
        check("R3 a bare build-aware label is an ERROR, not a warning",
              "public_label_missing_build" in codes, str(codes))
        nob = out / "nob.md"
        nob.write_text(record_text(target_build="''"), encoding="utf-8")
        check("R3 a record with no build is NOT reported as a label fault (nothing to state)",
              "public_label_missing_build" not in {e["code"] for e in qa.scan_record(nob)[0]})
        vonly = out / "vonly.md"
        vonly.write_text(record_text(product_id=DAV, update_product="DaVinci Resolve",
                                     update_source_name="Blackmagic Design",
                                     update_version="'20.3.3'", target_build="''"),
                         encoding="utf-8")
        check("R3 a version-only product is never flagged",
              "public_label_missing_build" not in {e["code"] for e in qa.scan_record(vonly)[0]})

    # ---------- corpus ----------
    print("\n[corpus] the shipped records agree with their own identity")
    build_aware, version_only, faults, contaminated = 0, 0, [], []
    for path in sorted(GENERATED_DIR.glob("*.md")):
        data = qa.front_matter(path)
        product_id = str(data.get("product_id") or "").strip()
        build = str(data.get("target_build") or "").strip()
        label_fields = ("title", "description", "update_feed_title", "update_detail_title")
        if is_build_aware(product_id) and build:
            build_aware += 1
            for field in ("title", "description"):
                if build not in str(data.get(field) or ""):
                    faults.append(f"{path.name}:{field}")
        else:
            version_only += 1
            for field in label_fields:
                if "(Build" in str(data.get(field) or ""):
                    contaminated.append(f"{path.name}:{field}")
    check(f"corpus: all {build_aware} build-aware records state their build in title+description",
          not faults, str(faults[:5]))
    check(f"corpus: none of the {version_only} version-only records gained a build label",
          not contaminated, str(contaminated[:5]))
    check("corpus: the repair reports nothing left to do", repair.run(False, GENERATED_DIR) == 0)

    # ---------- write authority ----------
    print("\n[authority] consensus still cannot rewrite a title")
    import apply_consensus_to_records as acr  # noqa: PLC0415
    check("authority: `title` is still a PROTECTED field on the consensus path",
          "title" in acr.PROTECTED_FIELDS)
    # PROTECTED ∩ COHERENCE is the set consensus MAY write (apply_consensus_to_records ~L1292).
    # `title` must never join it, whatever this change did to the stored value.
    check("authority: `title` is not in the consensus-writable coherence set",
          "title" not in acr.CONSENSUS_COHERENCE_FIELDS)
    check("authority: the repair writes only the two seo-tag fields",
          repair.REPAIRED_FIELDS == ("title", "description"), str(repair.REPAIRED_FIELDS))
    # The two AUXSAYS presentation fields stay OUT of the repair: they are rendered, not stored.
    check("authority: the repair never touches update_feed_title / update_detail_title",
          not ({"update_feed_title", "update_detail_title"} & set(repair.REPAIRED_FIELDS)))

    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed"
          + (f", {_SKIP} skipped" if _SKIP else ""))
    for err in _ERRORS:
        print(f"  - {err}")
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
