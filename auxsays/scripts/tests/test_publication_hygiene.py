"""The publication-hygiene deploy gate refuses contradictory indexing signals, and the G39 repairs stay put.

WHY IT EXISTS. 17 patch pages published HTML entities inside their JSON-LD, a page whose source asked
for noindex was published indexable and in the sitemap, a stored title carried mojibake and every feed
card overflowed a phone screen. verify_publication_hygiene.py reads the built site at deploy; this suite
proves it catches each class and stays quiet on a correct site.

WHAT IS PINNED HERE.
  [V]   the gate over synthetic built sites: a correct site (with an honoured explicit noindex page and a
        page that has no structured data) is clean; each defect fails a NAMED check -- JSON-LD entity,
        unparseable block, patch values that are not the page's, a source robots policy not rendered, a
        noindex page in the sitemap, a rendered robots tag no source asked for, conflicting directives,
        two canonicals, a canonical to nothing, a non-absolute canonical, a sitemap URL with no page, a
        sitemap URL whose page canonicalises elsewhere, one robots.txt disallows, a duplicate sitemap
        URL, a live page missing from its product hub. A live page missing from its company hub, a
        mojibake title and an entity in the site-wide SEO tag's JSON-LD only WARN (exit 0). A title with a
        no-break or doubled space whose JSON-LD states the same text is clean: both sides are folded alike.
        A page the deploy-time live projection certifies but whose verdict box the gate cannot read as
        live, or that no built page serves, fails HUBS (the hub check cannot go vacuous).
  [JL]  the bytes of _includes/patch-search-meta.html: each JSON-LD value is decoded from its HTML form
        and written with the backslash-u escapes for <, > and & (the replaces were once no-ops because
        an editor decoded the escapes). The rendered result is pinned by test_patch_decision_authority
        S19/S20.
  [RB]  the robots block of _layouts/aux-base.html, rendered with the Liquid gem: an explicit policy is
        rendered exactly, and a page without one gets no robots tag. Needs ruby + liquid.
  [CSS] the phone-width card rules sit inside the max-width 860px block, and (G43) so do the product-page
        rules that kept the Windows 11 page at 441 px on a 375 px phone; neither exists outside it.
  [TT]  (G43) _includes/patch-display-title.html, rendered with the Liquid gem: a stored title that repeats
        its product label ("GitHub / Copilot Copilot Student ...") shows the label once, every other title
        comes back byte-identical, and the include prints nothing. aux-update.html carries a written-out
        copy (the top of that layout holds no include tag), rendered over the same titles (TT5). The
        heading, search title and JSON-LD headline of a rendered patch page are pinned by
        test_patch_decision_authority S27/S28.
  [SM]  auxsays/sitemap.xml, rendered with the Liquid gem over a site that holds every kind of URL and every
        kind of stored value: the URL set is jekyll-sitemap's, a record / tracker / post carries its stored
        date, a stored value that is not a date (a word, an impossible month, 'now', a bare number, a future
        date) leaves its URL listed with no lastmod instead of failing the build, and nothing carries the
        build time or a file time. Needs ruby + liquid.
  [W]   wiring: pages.yml runs the gate on auxsays/_site after the build and before the upload, and it
        is not continue-on-error; the DaVinci 20.2.2 notice keeps its noindex policy out of the sitemap;
        the gate's live marker is the class aux-update.html renders for a live page.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_publication_hygiene.py
"""
from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from contextlib import redirect_stdout
from pathlib import Path
from xml.etree import ElementTree

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import yaml  # noqa: E402

from ci import verify_publication_hygiene as gate  # noqa: E402

AUX = _REPO / "auxsays"
SEARCH_META = AUX / "_includes" / "patch-search-meta.html"
BASE_LAYOUT = AUX / "_layouts" / "aux-base.html"
CSS = AUX / "assets" / "css" / "auxsays-custom.css"
PAGES_YML = _REPO / ".github" / "workflows" / "pages.yml"
NOTICE = AUX / "updates" / "blackmagic-design" / "davinci-resolve" / "20-2-2" / "index.md"
UPDATE_LAYOUT = AUX / "_layouts" / "aux-update.html"
STATE_INCLUDE = AUX / "_includes" / "patch-evidence-state.html"
ORIGIN = "https://auxsays.com"

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


# --------------------------------------------------------------------------------------------------
# [V] synthetic built sites
# --------------------------------------------------------------------------------------------------

def page_html(url: str, *, layout: str = "aux-base", title: str = "A page", canonical: str | None = "self",
              canonicals: int = 1, robots: list[str] = (), jsonld: list[str] | None = None, live: bool = False,
              links: list[str] = (), patch: bool = False, description: str = "A description.",
              body_html: str = "") -> str:
    canon = ORIGIN + url if canonical == "self" else canonical
    head = [f"<title>{title} | AUXSAYS</title>", f'<meta name="description" content="{description}" />']
    if patch:
        head.insert(0, "<!-- Patch page search metadata: title and description from the page's own verdict -->")
    if canon is not None:
        head += [f'<link rel="canonical" href="{canon}" />'] * canonicals
    head += [f'<meta name="robots" content="{r}">' for r in robots]
    if jsonld is None:
        jsonld = [json.dumps({"@context": "https://schema.org", "@type": "WebPage", "headline": title,
                              "description": description, "url": canon})]
    head += [f'<script type="application/ld+json">\n{b}</script>' for b in jsonld]
    body = [f'<a href="{h}">link</a>' for h in links] + ([body_html] if body_html else [])
    if live:
        body.append('<div id="verdict" class="update-decision-box update-decision-box--live"></div>')
    return ("<!doctype html><html><head>" + "\n".join(head) + f'</head><body class="aux-page {layout}">'
            + "<main>" + "".join(body) + f"<h1>{title}</h1></main></body></html>")


PATCH = "/updates/acme/tool/1-0/"
PRODUCT = "/updates/acme/tool/"
COMPANY = "/updates/acme/"
NOTICE_URL = "/updates/acme/tool/old/"
BARE = "/plain/"


def base_pages() -> dict[str, dict]:
    """A correct site: a live patch page linked from both hubs, an explicit noindex notice outside the
    sitemap, and a plain page with no structured data and no canonical outside the sitemap."""
    return {
        "/": {"links": [COMPANY, PRODUCT, PATCH]},
        COMPANY: {"layout": "aux-patch-company", "links": [PRODUCT, PATCH]},
        PRODUCT: {"layout": "aux-patch-product", "links": [COMPANY, PATCH]},
        PATCH: {"layout": "aux-update", "patch": True, "live": True, "title": "Tool 1.0: no verdict yet",
                "links": [COMPANY, PRODUCT]},
        NOTICE_URL: {"robots": ["noindex"]},
        BARE: {"canonical": None, "jsonld": []},
    }


def make_site(root: Path, pages: dict[str, dict], *, sitemap: list[str] | None = None,
              lastmods: dict[str, str] | None = None,
              robots_txt: str = "User-agent: *\nDisallow: /norobots/\n",
              policies: dict[str, str] | None = None,
              certified: list[str] | None = (PATCH,)) -> tuple[Path, Path]:
    site = root / "_site"
    for url, spec in pages.items():
        f = site / url.lstrip("/") / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(page_html(url, **spec), encoding="utf-8")
    if sitemap is None:
        sitemap = [u for u in pages if u not in (NOTICE_URL, BARE)]
    (site / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{ORIGIN}{u}</loc>"
                  + (f"<lastmod>{(lastmods or {})[u]}</lastmod>" if u in (lastmods or {}) else "") + "</url>"
                  for u in sitemap) + "</urlset>", encoding="utf-8")
    (site / "robots.txt").write_text(robots_txt, encoding="utf-8")
    source = root / "src"
    source.mkdir()
    (source / "_config.yml").write_text("title: AUXSAYS\n", encoding="utf-8")
    if certified is not None:  # the deploy-time live projection, as build_live_eligibility_projection.py writes it
        (source / "_data").mkdir()
        (source / "_data" / "live_eligibility.yml").write_text(
            yaml.safe_dump({"generated_at": "2026-11-18T00:00:00Z", "urls": list(certified)}), encoding="utf-8")
    for i, (url, policy) in enumerate((policies if policies is not None else {NOTICE_URL: "noindex"}).items()):
        d = source / "updates" / f"p{i}"
        d.mkdir(parents=True)
        (d / "index.md").write_text(f"---\nlayout: aux-base\npermalink: {url}\nrobots: {policy}\n---\nx\n",
                                    encoding="utf-8")
    return site, source


def run_gate(site: Path, source: Path) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = gate.main(["--site", str(site), "--source", str(source)])
    return code, buf.getvalue()


def variant(label: str, expect_rc: int, expect: str, mutate=None, **site_kwargs) -> None:  # noqa: ANN001
    with tempfile.TemporaryDirectory() as td:
        pages = base_pages()
        if mutate:
            mutate(pages)
        site, source = make_site(Path(td), pages, **site_kwargs)
        rc, out = run_gate(site, source)
    check(label, rc == expect_rc and expect in out, f"rc={rc} want {expect_rc}; {out[-600:]}")


def section_v() -> None:
    print("\n[V] the deploy gate over synthetic built sites")
    variant("V1 a correct site is clean: honoured noindex, a page with no structured data, live page on its hubs",
            0, "verify_publication_hygiene: clean (0 warning(s))")

    def entity(p):  # noqa: ANN001
        p[PATCH]["title"] = "Tool &amp; Co 1.0"
        p[PATCH]["jsonld"] = [json.dumps({"@type": "WebPage", "headline": "Tool &amp; Co 1.0",
                                          "description": "A description.", "url": ORIGIN + PATCH})]
    variant("V2 an HTML entity inside JSON-LD fails JSONLD", 1, "carries HTML entities ['&amp;']", entity)
    variant("V3 a JSON-LD block that does not parse fails JSONLD", 1, "has a block that does not parse",
            lambda p: p[BARE].update(jsonld=['{"@type": "WebPage",}']))
    variant("V4 a patch page whose JSON-LD headline is not its title fails JSONLD", 1,
            "states values its page does not: headline",
            lambda p: p[PATCH].update(jsonld=[json.dumps({"@type": "WebPage", "headline": "Other",
                                                          "description": "A description.", "url": ORIGIN + PATCH})]))
    variant("V5 a source robots policy the page does not render fails ROBOTS (the DaVinci defect)", 1,
            f"ROBOTS {NOTICE_URL}: its source sets robots 'noindex', the page renders 'none'",
            lambda p: p[NOTICE_URL].update(robots=[]))
    variant("V6 a noindex page listed in the sitemap fails ROBOTS", 1, "renders noindex but the sitemap lists it",
            sitemap=["/", COMPANY, PRODUCT, PATCH, NOTICE_URL])
    variant("V7 a rendered robots tag no source asked for fails ROBOTS (an accidental noindex)", 1,
            f"ROBOTS {BARE} renders robots 'noindex' but its source sets no robots policy",
            lambda p: p[BARE].update(robots=["noindex"]))
    variant("V8 conflicting robots directives on one page fail ROBOTS", 1, "carries conflicting robots directives",
            lambda p: p[NOTICE_URL].update(robots=["noindex", "index, follow"]))
    variant("V9 two canonical links on one page fail CANONICAL", 1, f"CANONICAL {PATCH} carries 2 canonical links",
            lambda p: p[PATCH].update(canonicals=2))
    variant("V10 a canonical naming no built page fails CANONICAL", 1, "which no built file serves",
            lambda p: p[NOTICE_URL].update(canonical=ORIGIN + "/nowhere/"))
    variant("V11 a canonical that is not an absolute auxsays.com URL fails CANONICAL", 1,
            "not an absolute https://auxsays.com URL", lambda p: p[NOTICE_URL].update(canonical="/updates/acme/"))
    variant("V12 a sitemap URL no built file serves fails SITEMAP", 1, "is listed but no built file serves it",
            sitemap=["/", COMPANY, PRODUCT, PATCH, "/gone/"])
    variant("V13 a sitemap URL whose page canonicalises elsewhere fails SITEMAP", 1,
            "is listed but its page's canonical is",
            lambda p: p[PRODUCT].update(canonical=ORIGIN + COMPANY))
    variant("V14 a sitemap URL robots.txt disallows fails SITEMAP", 1, "is listed but robots.txt disallows it",
            robots_txt="User-agent: *\nDisallow: /updates/acme/tool/\n")
    variant("V15 a sitemap URL listed twice fails SITEMAP", 1, "is listed more than once",
            sitemap=["/", COMPANY, PRODUCT, PATCH, PATCH])
    variant("V16 a live page its product hub does not link fails HUBS", 1,
            f"HUBS live page {PATCH} is not linked from its product hub {PRODUCT}",
            lambda p: p[PRODUCT].update(links=[COMPANY]))
    variant("V17 a live page its company hub does not link only WARNS", 0,
            f"WARN HUBS live page {PATCH} is not linked from its company hub {COMPANY}",
            lambda p: p[COMPANY].update(links=[PRODUCT]))
    damaged = "Tool agent" + "’s".encode("utf-8").decode("cp1252")
    variant("V18 a mojibake title only WARNS", 0, "WARN MOJIBAKE",
            lambda p: p[BARE].update(title=damaged))

    def seo_entity(p):  # noqa: ANN001
        p[COMPANY]["title"] = "Acme &amp; Co"
        p[COMPANY]["jsonld"] = [json.dumps({"@type": "WebPage", "headline": "Acme &amp; Co", "url": ORIGIN + COMPANY})]
    variant("V19 an HTML entity in the site-wide SEO tag's JSON-LD (not a patch page) only WARNS: an editorial title "
            "must not stop every deploy", 0, f"WARN JSONLD {COMPANY} carries HTML entities ['&amp;'] in the SEO tag's",
            seo_entity)

    # The ingest lane writes U+00A0 from vendor text, and a doubled space survives a template. The include
    # writes the same text into <title> and into the JSON-LD; the gate must compare them like for like.
    spaced = "Tool" + chr(0xA0) + "1.0:  no verdict yet"
    variant("V20 a patch page whose title holds a no-break space and a doubled space, with JSON-LD stating the same "
            "text, is clean (whitespace is folded on both sides of the value comparison)", 0,
            "verify_publication_hygiene: clean (0 warning(s))",
            lambda p: p[PATCH].update(title=spaced, description="Two  spaces and a no" + chr(0xA0) + "break."))

    def unreadable_live(p):  # noqa: ANN001 -- the layout renamed the box's class, and a hub dropped the page
        p[PATCH]["live"] = False
        p[PRODUCT]["links"] = [COMPANY]
    variant("V21 a page the deploy-time projection certifies live whose verdict box the gate cannot read as live "
            "fails HUBS (the hub check would otherwise find 0 live pages and pass)", 1,
            f"HUBS the deploy-time projection certifies {PATCH} live, but its page does not render the live verdict box",
            unreadable_live)
    variant("V22 a page the projection certifies live that no built page serves fails HUBS", 1,
            "HUBS the deploy-time projection certifies /updates/acme/tool/2-0/ live, but no built page serves it",
            certified=[PATCH, "/updates/acme/tool/2-0/"])


# --------------------------------------------------------------------------------------------------
# [R3] R3-SEO: stored dates, breadcrumbs, no ratings, and homepage findings that match their pages
# --------------------------------------------------------------------------------------------------

STAMP = "2026-11-15T07:50:17+00:00"
PATCH_TITLE = "Tool 1.0: no verdict yet"


def crumb(*items) -> dict:  # noqa: ANN002
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": n, "item": u} for i, (n, u) in enumerate(items, 1)]}


def patch_ld(**extra) -> list[str]:  # noqa: ANN003
    return [json.dumps({"@context": "https://schema.org", "@type": "WebPage", "headline": PATCH_TITLE,
                        "description": "A description.", "url": ORIGIN + PATCH, **extra})]


GOOD_CRUMB = crumb(("Acme", ORIGIN + COMPANY), ("Tool", ORIGIN + PRODUCT), ("Tool 1.0", ORIGIN + PATCH))
VERDICT_BOX = ('<div class="update-decision-box__header"><span class="update-decision-eyebrow">AUXSAYS verdict</span>'
               '\n<strong>TEST FIRST</strong> <span class="update-decision-scope">when installing it</span>'
               '\n<p class="update-decision-recommendation">Two users report that installing it fails. Install it '
               'on one machine first.</p></div>')


def finding(verdict="TEST FIRST", scope="when installing it", line="Two users report that installing it fails.",
            group=None, href=PATCH) -> str:  # noqa: ANN001
    return (f'<div class="home-findings-group" data-home-findings-group="{group or verdict}"><ul>'
            f'<li><a class="home-finding" href="{href}" data-home-finding data-finding-verdict="{verdict}" '
            f'data-finding-scope="{scope}"><strong>Tool 1.0</strong>'
            f'<span class="home-finding__line" data-finding-line>{line}</span></a></li></ul></div>')


def with_finding(**kw):  # noqa: ANN003, ANN201
    def mutate(p):  # noqa: ANN001
        p[PATCH]["body_html"] = VERDICT_BOX
        p["/"]["body_html"] = finding(**kw)
    return mutate


def section_r3() -> None:
    print("\n[R3] R3-SEO: stored dates, breadcrumbs, no ratings, homepage findings")
    good = {PATCH: STAMP}
    variant("R3-1 a patch page whose dateModified is its sitemap lastmod, with a breadcrumb of built pages ending at "
            "itself, is clean", 0, "patch pages with a breadcrumb 1",
            lambda p: p[PATCH].update(jsonld=patch_ld(dateModified=STAMP, breadcrumb=GOOD_CRUMB)), lastmods=good)
    variant("R3-2 a dateModified that is not the sitemap lastmod of the same URL fails JSONLD", 1,
            "states dateModified '2026-11-16T00:00:00+00:00', its sitemap lastmod is",
            lambda p: p[PATCH].update(jsonld=patch_ld(dateModified="2026-11-16T00:00:00+00:00")), lastmods=good)
    variant("R3-3 a sitemap lastmod the patch block does not state fails JSONLD (both read the same stored date)", 1,
            "states dateModified None", lastmods=good)
    variant("R3-4 a breadcrumb naming a page no built file serves fails JSONLD", 1,
            "breadcrumb item 2 names https://auxsays.com/updates/acme/gone/, which no built file serves",
            lambda p: p[PATCH].update(jsonld=patch_ld(breadcrumb=crumb(
                ("Acme", ORIGIN + COMPANY), ("Gone", ORIGIN + "/updates/acme/gone/"), ("Tool 1.0", ORIGIN + PATCH)))))
    variant("R3-5 a breadcrumb that does not end at the page's own canonical fails JSONLD", 1,
            "breadcrumb ends at 'https://auxsays.com/updates/acme/tool/'",
            lambda p: p[PATCH].update(jsonld=patch_ld(breadcrumb=crumb(("Acme", ORIGIN + COMPANY),
                                                                       ("Tool", ORIGIN + PRODUCT)))))
    variant("R3-6 a rating anywhere in any page's structured data fails JSONLD", 1,
            "states ['AggregateRating']: AUXSAYS publishes verdicts, not ratings",
            lambda p: p[BARE].update(jsonld=[json.dumps({"@type": "WebPage", "aggregateRating": {
                "@type": "AggregateRating", "ratingValue": 4}})]))
    variant("R3-7 a homepage finding that states its page's verdict, scope and first sentence is clean", 0,
            "homepage findings rows checked against their pages 1", with_finding())
    variant("R3-8 a finding whose verdict is not its page's fails FINDINGS", 1,
            "the homepage says 'WAIT' 'when installing it', its page says 'TEST FIRST'", with_finding(verdict="WAIT"))
    variant("R3-9 a finding whose scope is not its page's fails FINDINGS", 1,
            "its page says 'TEST FIRST' 'when installing it'", with_finding(scope="if you use macOS"))
    variant("R3-10 a finding whose line is not how its page's verdict line begins fails FINDINGS", 1,
            "is not how its page's verdict line begins", with_finding(line="Many users report problems."))
    variant("R3-11 a finding listed under another verdict's group fails FINDINGS", 1,
            "is listed under 'AVOID' but its row says 'TEST FIRST'", with_finding(group="AVOID"))
    variant("R3-12 a finding linking a page no built file serves fails FINDINGS", 1,
            "is listed on the homepage but no built page serves it", with_finding(href="/updates/acme/tool/9-9/"))


# --------------------------------------------------------------------------------------------------
# [JL] the include's bytes
# --------------------------------------------------------------------------------------------------

def section_jl() -> None:
    print("\n[JL] patch-search-meta.html writes JSON from the plain text, with real escapes")
    text = SEARCH_META.read_text(encoding="utf-8")
    bs = chr(92)
    chain = (f"| jsonify | replace: '<', '{bs}u003c' | replace: '>', '{bs}u003e' | replace: '&', '{bs}u0026' -%}}")
    lines = {name: next((ln for ln in text.splitlines() if f"assign psm_json_{name} =" in ln), "")
             for name in ("description", "headline", "url")}
    bad = [n for n, ln in lines.items() if not ln.rstrip().endswith(chain)
           or f"psm_text_{'headline' if n == 'headline' else n}" not in ln]
    noop = re.findall(r"replace: '([<>&])', '\1'", text)
    check("JL1 every JSON-LD value is jsonified from its plain text and <, > and & become backslash-u escapes "
          "(no replace is a no-op)", not bad and not noop, f"{bad} noop={noop}")
    decode = ("| replace: '&quot;', '\"' | replace: '&#39;', \"'\" | replace: '&lt;', '<' | replace: '&gt;', '>' "
              "| replace: '&amp;', '&' -%}")
    sources = {"description": "psm_description", "headline": "psm_title", "url": "psm_canonical"}
    missing = [n for n, src in sources.items() if f"assign psm_text_{n} = {src} {decode}" not in text]
    check("JL2 each value is decoded from its HTML form first, with &amp; last", not missing, str(missing))


# --------------------------------------------------------------------------------------------------
# [RB] the robots block, rendered
# --------------------------------------------------------------------------------------------------

_RB_RUBY = r"""
require 'liquid'
require 'json'
tpl = Liquid::Template.parse(File.read(ARGV[0], encoding: 'utf-8'))
out = {}
JSON.parse(File.read(ARGV[1], encoding: 'utf-8')).each do |name, page|
  out[name] = tpl.render!({ 'page' => page })
end
print JSON.generate(out)
"""


def section_rb() -> None:
    print("\n[RB] aux-base renders an explicit robots policy, and only an explicit one")
    text = BASE_LAYOUT.read_text(encoding="utf-8")
    start = text.find("{%- assign aux_robots")
    end = text.find("{%- endif %}", start)
    ruby = shutil.which("ruby")
    if start < 0 or end < 0 or not ruby:
        check("RB1 the robots block renders under the Liquid gem", False,
              "block not found" if ruby else "ruby missing")
        return
    block = text[start:end + len("{%- endif %}")]
    cases = {"noindex": {"robots": "noindex"}, "pair": {"robots": "noindex, follow"}, "none": {},
             "empty": {"robots": ""}}
    with tempfile.TemporaryDirectory() as td:
        tpl, payload, script = Path(td) / "b.liquid", Path(td) / "p.json", Path(td) / "r.rb"
        tpl.write_text(block, encoding="utf-8")
        payload.write_text(json.dumps(cases), encoding="utf-8")
        script.write_text(_RB_RUBY, encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(tpl), str(payload)], capture_output=True, text=True,
                              encoding="utf-8", timeout=120)
    try:
        out = json.loads(proc.stdout)
    except ValueError:
        check("RB1 the robots block renders under the Liquid gem", False, (proc.stderr or proc.stdout)[:300])
        return
    metas = {k: re.findall(r'<meta name="robots"[^>]*>', v) for k, v in out.items()}
    check("RB1 an explicit policy is rendered exactly", metas["noindex"] == ['<meta name="robots" content="noindex">']
          and metas["pair"] == ['<meta name="robots" content="noindex, follow">'], str(metas))
    check("RB2 a page without a policy, or with an empty one, gets no robots tag and no output",
          metas["none"] == [] and metas["empty"] == [] and out["none"].strip() == "" and out["empty"].strip() == "",
          json.dumps(out)[:300])
    check("RB3 the block sits in the head, after the SEO tag", text.find("{% seo %}") < start < text.find("</head>"),
          str((text.find("{% seo %}"), start, text.find("</head>"))))


# --------------------------------------------------------------------------------------------------
# [CSS] and [W]
# --------------------------------------------------------------------------------------------------

def media_blocks(css: str, query: str) -> list[str]:
    """The bodies of every @media block whose query is exactly `query` (brace-matched)."""
    out = []
    for m in re.finditer(r"@media\s*\(" + re.escape(query) + r"\)\s*\{", css):
        depth, i = 1, m.end()
        while depth and i < len(css):
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        out.append(css[m.end():i - 1])
    return out


def section_css() -> None:
    print("\n[CSS] the phone-width card rules")
    blocks = " ".join(media_blocks(CSS.read_text(encoding="utf-8"), "max-width: 860px"))
    flat = re.sub(r"\s+", " ", blocks)
    want = [".patch-card { grid-template-columns: minmax(0, 1fr); }", ".patch-card-headline { flex-wrap: wrap; }",
            ".patch-status-stack { max-width: 100%; }", ".patch-card-monitoring { flex-wrap: wrap; }"]
    missing = [w for w in want if w not in flat]
    check("CSS1 a phone-width card lets its track shrink and wraps its headline, status stack and monitoring pill",
          not missing, str(missing))
    # G43: the Windows 11 product page (441 px on a 375 px phone). Phone-only, so desktop cannot change.
    css = CSS.read_text(encoding="utf-8")
    g43 = [".patch-intel-shell { grid-template-columns: minmax(0, 1fr); }",
           ".patch-cell-monitoring .patch-monitoring { white-space: normal; }"]
    outside = css
    for block in media_blocks(css, "max-width: 860px"):
        outside = outside.replace(block, "")
    outside = re.sub(r"\s+", " ", outside)
    check("CSS2 a phone-width product page lets its grid track shrink and its monitoring pill wrap, inside the "
          "max-width 860px block and nowhere else (G43)",
          all(w in flat for w in g43) and not any(w in outside for w in g43),
          str([w for w in g43 if w not in flat]))


# --------------------------------------------------------------------------------------------------
# [TT] a patch title names its product once (G43)
# --------------------------------------------------------------------------------------------------

TITLE_INCLUDE = AUX / "_includes" / "patch-display-title.html"
TITLE_LAYOUTS = {AUX / "_layouts" / "aux-update.html": 0, AUX / "_layouts" / "aux-updates.html": 2,
                 AUX / "_layouts" / "aux-home.html": 1}
# aux-update.html's written-out copy of the include (the top of that layout holds no include tag).
COPY_START = "{%- assign pdt_raw = display_title -%}"
COPY_END = "{%- assign cite_title = page.update_feed_title"
_TT_COPY_RUBY = r"""
require 'liquid'
require 'json'
tpl = Liquid::Template.parse('[' + File.read(ARGV[0], encoding: 'utf-8') + ']{{ display_title }}')
out = JSON.parse(File.read(ARGV[1], encoding: 'utf-8')).map do |t, p|
  tpl.render!({ 'display_title' => t, 'page' => { 'update_product' => p } })
end
print JSON.generate(out)
"""
_TT_RUBY = r"""
require 'liquid'
require 'json'
tpl = Liquid::Template.parse('[' + File.read(ARGV[0], encoding: 'utf-8') + ']{{ patch_display_title }}')
out = JSON.parse(File.read(ARGV[1], encoding: 'utf-8')).map do |t, p|
  tpl.render!({ 'include' => { 'title' => t, 'product' => p } })
end
print JSON.generate(out)
"""
GH = "GitHub / Copilot"
TT_AFFECTED = [
    ("GitHub / Copilot Copilot Student GPT-5.3-Codex removal from model picker", GH,
     "GitHub / Copilot Student GPT-5.3-Codex removal from model picker"),
    ("GitHub / Copilot Copilot Student GPT-5.3-Codex removal from model picker official update breakdown", GH,
     "GitHub / Copilot Student GPT-5.3-Codex removal from model picker official update breakdown"),
    ("Figma Figma for Zoom GA", "Figma", "Figma for Zoom GA"),
    ("OBS Studio OBS Studio 32.0.1", "OBS Studio", "OBS Studio 32.0.1"),
]
TT_UNAFFECTED = [
    ("OBS Studio 32.0.1", "OBS Studio"),
    ("Figma Figmaverse launch", "Figma"),
    ("Windows 11 25H2 (Build 26200.7840)", "Windows 11"),
    ('Copilot "agent" & tools 1.0', "OBS Studio"),
    ("GitHub / Copilot Copilot Student", GH),
    ("GitHub / Copilot Copilot Student", ""),
    ("", GH),
]


def section_tt() -> None:
    print("\n[TT] a patch title names its product once")
    ruby = shutil.which("ruby")
    cases = [[t, p] for t, p, _ in TT_AFFECTED] + [[t, p] for t, p in TT_UNAFFECTED]
    if not ruby:
        check("TT1 the title include renders under the Liquid gem", False, "ruby missing")
        return
    with tempfile.TemporaryDirectory() as td:
        payload, script = Path(td) / "p.json", Path(td) / "t.rb"
        payload.write_text(json.dumps(cases), encoding="utf-8")
        script.write_text(_TT_RUBY, encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(TITLE_INCLUDE), str(payload)], capture_output=True,
                              text=True, encoding="utf-8", timeout=120)
    try:
        out = json.loads(proc.stdout)
    except ValueError:
        check("TT1 the title include renders under the Liquid gem", False, (proc.stderr or proc.stdout)[:300])
        return
    printed = [o.split("]", 1)[0] for o in out]
    shown = [o.split("]", 1)[1] if "]" in o else o for o in out]
    got_affected = shown[:len(TT_AFFECTED)]
    want_affected = [w for _, _, w in TT_AFFECTED]
    check("TT1 a title that repeats its product label (GitHub Copilot, Figma, a whole label) shows it once",
          got_affected == want_affected, str(list(zip(got_affected, want_affected))))
    got_unaffected = shown[len(TT_AFFECTED):]
    check("TT2 every other title comes back byte-identical: a word that only begins with the label, a "
          "label that is not repeated, a no-break space, no label, no title",
          got_unaffected == [t for t, _ in TT_UNAFFECTED], str(got_unaffected))
    check("TT3 the include prints nothing of its own", printed == ["["] * len(cases), str(printed[:3]))
    wired = {p.name: p.read_text(encoding="utf-8").count("{% include patch-display-title.html ")
             for p in TITLE_LAYOUTS}
    layout = (AUX / "_layouts" / "aux-update.html").read_text(encoding="utf-8")
    start, end = layout.find(COPY_START), layout.find(COPY_END)
    heading_after = 0 <= start < end < layout.find('<h1 class="update-title">{{ display_title }}</h1>')
    check("TT4 both Patch Feed card branches and the homepage list use the include; the patch page applies "
          "its written-out copy before the heading and holds no include tag for it",
          wired == {p.name: n for p, n in TITLE_LAYOUTS.items()} and heading_after
          and "{{ cite_title }}</a>" in layout, f"{wired} copy@{start}..{end}")
    if not heading_after:
        check("TT5 the patch page's copy renders exactly as the include", False, "copy not found")
        return
    with tempfile.TemporaryDirectory() as td:
        block, payload, script = Path(td) / "b.liquid", Path(td) / "p.json", Path(td) / "c.rb"
        block.write_text(layout[start:end], encoding="utf-8")
        payload.write_text(json.dumps(cases), encoding="utf-8")
        script.write_text(_TT_COPY_RUBY, encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(block), str(payload)], capture_output=True, text=True,
                              encoding="utf-8", timeout=120)
    try:
        copy_out = json.loads(proc.stdout)
    except ValueError:
        check("TT5 the patch page's copy renders exactly as the include", False, (proc.stderr or proc.stdout)[:300])
        return
    check("TT5 the patch page's copy renders exactly as the include over every case, and prints nothing",
          copy_out == ["[]" + s for s in shown], str([(a, b) for a, b in zip(copy_out, shown) if a != "[]" + b][:3]))


# ----------------------------------------------------------------------------------------------
# [SM] the sitemap template: a lastmod only from a stored date
# ----------------------------------------------------------------------------------------------
SITEMAP_TEMPLATE = AUX / "sitemap.xml"
SM_NOW = "2026-11-24T08:00:00Z"
_SM_RUBY = r"""
require 'liquid'
require 'json'
module SitemapShims
  def absolute_url(i) = "https://auxsays.com/" + i.to_s.sub(%r{\A/}, "")
  def xml_escape(i) = i.to_s.encode(xml: :text)
end
Liquid::Template.register_filter(SitemapShims)
source = File.read(ARGV[0], encoding: 'utf-8').sub(/\A---\n.*?\n---\n/m, '')
site = JSON.parse(File.read(ARGV[1], encoding: 'utf-8'))
print Liquid::Template.parse(source, error_mode: :strict).render!({ 'site' => site }, strict_filters: true)
"""


def _sm_record(name: str, *, product: str = "tool", version: str = "1.0", **fields) -> dict:
    return {"url": f"/u/{product}/{name}/", "layout": "aux-update", "update_entry": True, "company_id": "acme",
            "product_id": product, "update_version": version, **fields}


#: url -> the lastmod the template must print, or None for "listed, no lastmod". Offsets are written out in
#: every stored value, so the expected text does not depend on the machine's time zone.
SM_EXPECT = {
    "/articles/a/": "2026-04-10T07:45:00-07:00",
    "/about/": None,                                    # an undated document: its date IS the build time
    "/": None,
    "/stamped/": "2026-05-05T00:00:00+00:00",
    "/u/tool/good/": "2026-11-22T21:14:15+00:00",
    "/u/tool/older/": "2026-11-01T00:00:00+00:00",
    "/u/tool/fallback/": "2026-10-01T00:00:00+00:00",   # no record_last_updated: the release date
    "/u/other/x/": "2026-10-05T10:00:00+00:00",
    "/u/tool/bad-word/": None, "/u/tool/bad-month/": None, "/u/tool/bad-now/": None, "/u/tool/bad-int/": None,
    "/u/tool/bad-future/": None, "/u/tool/bad-fallback/": None, "/u/broken/bad-only/": None,
    "/u/tool/": "2026-11-22T21:14:15+00:00",            # product tracker: its newest valid record
    "/u/": "2026-11-22T21:14:15+00:00",                 # company tracker
    "/u/tool/v2/": "2026-11-01T00:00:00+00:00",         # version tracker: that version's records only
    "/u/empty/": None, "/u/broken/": None, "/u/noid/": None,
    "/file.pdf": None, "/doc.html": None,
}
SM_BAD = [u for u in SM_EXPECT if "/bad-" in u] + ["/u/broken/"]
SM_ABSENT = ["/404.html", "/hidden/", "/articles/hidden/", "/no/", "/style.css", "/old/404.html"]


def sm_site() -> dict:
    """A site as Jekyll hands it to the template, with every kind of URL and every kind of stored value."""
    records = [
        _sm_record("good", record_last_updated="2026-11-22T21:14:15.681110Z", update_published_at="2026-10-01T00:00:00Z"),
        _sm_record("older", version="2.0", record_last_updated="2026-11-01T00:00:00Z"),
        _sm_record("fallback", update_published_at="2026-10-01T00:00:00Z"),
        _sm_record("x", product="other", record_last_updated="2026-10-05T10:00:00Z"),
        _sm_record("bad-word", record_last_updated="not-a-date"),
        _sm_record("bad-month", record_last_updated="2026-13-45T00:00:00Z"),
        _sm_record("bad-now", record_last_updated="now"),
        _sm_record("bad-int", record_last_updated=1732000000),
        _sm_record("bad-future", record_last_updated="2099-01-01T00:00:00Z"),
        _sm_record("bad-fallback", update_published_at="soon"),
        _sm_record("bad-only", product="broken", record_last_updated="garbage"),
    ]
    trackers = [
        {"url": "/u/tool/", "layout": "aux-patch-product", "company_id": "acme", "product_id": "tool"},
        {"url": "/u/", "layout": "aux-patch-company", "company_id": "acme"},
        {"url": "/u/tool/v2/", "layout": "aux-patch-version", "product_id": "tool", "update_version": "2.0"},
        {"url": "/u/empty/", "layout": "aux-patch-product", "product_id": "none-here"},
        {"url": "/u/broken/", "layout": "aux-patch-product", "product_id": "broken"},
        {"url": "/u/noid/", "layout": "aux-patch-product"},
    ]
    plain = [{"url": "/", "layout": "aux-home"}, {"url": "/404.html", "layout": "aux-base"},
             {"url": "/hidden/", "layout": "aux-base", "sitemap": False},
             {"url": "/stamped/", "layout": "aux-base", "last_modified_at": "2026-05-05T00:00:00Z"}]
    return {
        "time": SM_NOW,
        "collections": [
            {"label": "posts", "output": True, "docs": [
                {"url": "/articles/a/", "date": "2026-04-10T07:45:00-07:00"},
                {"url": "/articles/hidden/", "date": "2026-04-11T07:45:00-07:00", "sitemap": False}]},
            {"label": "tabs", "output": True, "docs": [{"url": "/about/", "date": SM_NOW}]},
            {"label": "drafts", "output": False, "docs": [{"url": "/no/", "date": "2026-01-01T00:00:00Z"}]}],
        "html_pages": plain + records + trackers,
        "static_files": [
            {"path": "/file.pdf", "name": "file.pdf", "extname": ".pdf", "modified_time": SM_NOW},
            {"path": "/doc.html", "name": "doc.html", "extname": ".html", "modified_time": "2026-11-20T00:00:00Z"},
            {"path": "/old/404.html", "name": "404.html", "extname": ".html", "modified_time": SM_NOW},
            {"path": "/style.css", "name": "style.css", "extname": ".css", "modified_time": SM_NOW}],
    }


def section_sm() -> None:
    print("\n[SM] the sitemap template prints a lastmod only from a stored date")
    ruby = shutil.which("ruby")
    if not ruby:
        check("SM1 the shipped sitemap.xml renders under the Liquid gem", False, "ruby missing")
        return
    with tempfile.TemporaryDirectory() as td:
        payload, script = Path(td) / "site.json", Path(td) / "sm.rb"
        payload.write_text(json.dumps(sm_site()), encoding="utf-8")
        script.write_text(_SM_RUBY, encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(SITEMAP_TEMPLATE), str(payload)], capture_output=True,
                              text=True, encoding="utf-8", timeout=120)
    xml = proc.stdout or ""
    got: dict[str, str | None] = {}
    blocks = re.findall(r"<url>(.*?)</url>", xml, re.S)
    for block in blocks:
        loc = re.search(r"<loc>(.*?)</loc>", block, re.S)
        mod = re.findall(r"<lastmod>(.*?)</lastmod>", block, re.S)
        if loc:
            got[loc.group(1).strip().replace(ORIGIN, "")] = mod[0].strip() if len(mod) == 1 else (None if not mod else "TWO")
    try:
        ElementTree.fromstring(xml)
        parses = True
    except ElementTree.ParseError:
        parses = False
    check("SM1 the shipped sitemap.xml renders under the Liquid gem with malformed stored dates in the site, "
          "as XML that opens with its declaration, and lists exactly the plugin's URL set",
          proc.returncode == 0 and xml.startswith("<?xml") and parses and len(blocks) == len(got)
          and sorted(got) == sorted(SM_EXPECT) and not [u for u in SM_ABSENT if u in got],
          f"rc={proc.returncode} {(proc.stderr or '')[-300:]} extra={sorted(set(got) - set(SM_EXPECT))} "
          f"missing={sorted(set(SM_EXPECT) - set(got))}")
    dated = {u: v for u, v in SM_EXPECT.items() if v}
    wrong = {u: got.get(u) for u, v in dated.items() if got.get(u) != v}
    check(f"SM2 a record, a tracker, a post and a stamped page carry their stored date, to the second "
          f"({len(dated)} URLs)", bool(got) and not wrong, str(wrong))
    leaked = {u: got.get(u, "ABSENT") for u in SM_BAD if got.get(u, "ABSENT") is not None}
    check(f"SM3 a stored value that is not a date (a word, an impossible month, 'now', a bare number, a future "
          f"date, a bad fallback) leaves its URL listed with no lastmod ({len(SM_BAD)} URLs)",
          bool(got) and not leaked, str(leaked))
    undated = {u: got.get(u, "ABSENT") for u, v in SM_EXPECT.items() if v is None and got.get(u, "ABSENT") is not None}
    build_time = [u for u, v in got.items() if v and v[:16] == SM_NOW[:16]]
    check("SM4 no URL carries the build time or a file time: an undated document, a tracker with no record, "
          "a tracker with no id and every static file have no lastmod",
          bool(got) and not undated and not build_time
          and sum(1 for v in got.values() if v) == len(dated), f"undated={undated} build_time={build_time}")


def section_w() -> None:
    print("\n[W] wiring")
    wf = yaml.safe_load(PAGES_YML.read_text(encoding="utf-8"))
    steps = wf["jobs"]["build"]["steps"]
    names = [s.get("name", "") for s in steps]
    idx = next((i for i, s in enumerate(steps)
                if "verify_publication_hygiene.py" in str(s.get("run", ""))), -1)
    build = next((i for i, n in enumerate(names) if n == "Build site"), -1)
    upload = next((i for i, n in enumerate(names) if n == "Upload artifact"), -1)
    step = steps[idx] if idx >= 0 else {}
    check("W1 pages.yml runs the gate on auxsays/_site after the build and before the upload",
          build < idx < upload and step.get("run", "").strip()
          == "python auxsays/scripts/ci/verify_publication_hygiene.py --site auxsays/_site",
          f"build={build} gate={idx} upload={upload} run={step.get('run')!r}")
    check("W2 the gate can stop the deploy: it is not continue-on-error and has no condition",
          idx >= 0 and not step.get("continue-on-error") and "if" not in step, str(step))
    text = NOTICE.read_text(encoding="utf-8")
    front = yaml.safe_load(text.split("---", 2)[1])
    check("W3 the DaVinci 20.2.2 notice keeps its explicit noindex policy and stays out of the sitemap",
          front.get("robots") == "noindex" and front.get("sitemap") is False
          and "/updates/blackmagic-design/blackmagic-davinci/20-2-2/" in text, str(front))
    layout = UPDATE_LAYOUT.read_text(encoding="utf-8")
    box = re.search(r'class="(update-decision-box update-decision-box--)\{\{ evidence_state_class \}\}"', layout)
    rendered = f'class="{box.group(1)}live"' if box else None
    assigns_live = "{% assign evidence_state_class = 'live' %}" in STATE_INCLUDE.read_text(encoding="utf-8")
    check("W4 the gate's live marker is the verdict box a live patch page renders (aux-update.html's class with "
          "patch-evidence-state.html's 'live'), so HUBS reads the real pages",
          rendered == gate.LIVE_BOX and assigns_live, f"layout renders {rendered!r}, gate reads {gate.LIVE_BOX!r}, "
          f"include assigns live: {assigns_live}")


def main() -> int:
    section_v()
    section_r3()
    section_jl()
    section_rb()
    section_css()
    section_tt()
    section_sm()
    section_w()
    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2) from None
