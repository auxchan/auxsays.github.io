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
  [JL]  the bytes of _includes/patch-search-meta.html: each JSON-LD value is decoded from its HTML form
        and written with the backslash-u escapes for <, > and & (the replaces were once no-ops because
        an editor decoded the escapes). The rendered result is pinned by test_patch_decision_authority
        S19/S20.
  [RB]  the robots block of _layouts/aux-base.html, rendered with the Liquid gem: an explicit policy is
        rendered exactly, and a page without one gets no robots tag. Needs ruby + liquid.
  [CSS] the phone-width card rules sit inside the max-width 860px block.
  [W]   wiring: pages.yml runs the gate on auxsays/_site after the build and before the upload, and it
        is not continue-on-error; the DaVinci 20.2.2 notice keeps its noindex policy out of the sitemap.

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
              links: list[str] = (), patch: bool = False, description: str = "A description.") -> str:
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
    body = [f'<a href="{h}">link</a>' for h in links]
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
              robots_txt: str = "User-agent: *\nDisallow: /norobots/\n",
              policies: dict[str, str] | None = None) -> tuple[Path, Path]:
    site = root / "_site"
    for url, spec in pages.items():
        f = site / url.lstrip("/") / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(page_html(url, **spec), encoding="utf-8")
    if sitemap is None:
        sitemap = [u for u in pages if u not in (NOTICE_URL, BARE)]
    (site / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{ORIGIN}{u}</loc></url>" for u in sitemap) + "</urlset>", encoding="utf-8")
    (site / "robots.txt").write_text(robots_txt, encoding="utf-8")
    source = root / "src"
    source.mkdir()
    (source / "_config.yml").write_text("title: AUXSAYS\n", encoding="utf-8")
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


def main() -> int:
    section_v()
    section_jl()
    section_rb()
    section_css()
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
