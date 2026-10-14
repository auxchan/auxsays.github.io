#!/usr/bin/env python3
"""Content AUXSAYS holds must actually reach the reader.

Two independent mechanisms were discarding it. Presence guards that never gated (S/K/I/H/F/C
below), and an entrance animation that left content at opacity 0 (V below).

AUXSAYS wrote 91 presence tests as `x != blank` / `x == blank` across eight layouts and
includes. None of them worked. Liquid 4 resolves the `blank` literal through a
`MethodLiteral` that sends `:blank?` to the value; `blank?` is an ActiveSupport method and
Jekyll does not load ActiveSupport, so the send never happens and the comparison degrades
to one against nil. `x != blank` was therefore ALWAYS true and `x == blank` ALWAYS false:
every guard written that way passed unconditionally, and every `== blank` branch was dead.

What that cost, measured over all 1,274 shipped patch records plus the live site:

  * 1,218 empty `<dd></dd>` values -- "File size", "Product", release-channel pills and
    technical rows printing their label with nothing after it.
  * 1,095 `<a href="">Download page</a>` self-links on the patch feed. An empty href
    resolves to the current page, so a reader clicking "Download page" reloaded the feed.
  * 1,258 records rendering the checksum block, with its "Use these hashes to verify
    downloaded installers" instruction, over zero hashes. Only 16 records have any.
  * 1,262 records rendering "<Product> in these notes:" with no attribution. Only 12 have one.
  * The homepage's article thumbnails NEVER resolved, for any post, under any front-matter
    shape. The first guard assigned `post.image` even when absent, which killed the
    thumbnail/cover/hero fallbacks; then three unwrap guards ran unconditionally and a
    String has no `.path`, reducing the value to nil. nil is not '', so the render guard
    still passed and the card emitted an img with an empty src. Both Recent Articles cards
    on production auxsays.com were broken images, not the designed gradient placeholder.

The repair normalises each tested value with `| default: '' | strip` and compares against
''. That is the idiom this codebase already adopted for `decision_label` when the same bug
was found there (86 records rendered no verdict at all), so this suite pins the pattern
rather than inventing one. Comparing a normalised string against '' also treats
whitespace-only as absent, which is what `blank` was reaching for in the first place.

Two things this suite deliberately does NOT do. It does not assert the absence of the word
"blank" from comment prose -- the comments explaining this bug necessarily contain it, so
the ban is enforced over EMITTING markup only. And it does not assert any verdict text: the
repair was proven byte-identical on the published verdict across all 1,274 records, and
patch-decision authority is owned by `lib/patch_decision.py`, not by a presence guard.

K1-K3 are the keystone. They prove `blank` really is inert HERE rather than taking it on
faith, so S1's ban is grounded in measurement. If a future dependency change makes `blank`
work, K1-K3 fail loudly and the ban can be revisited on evidence.

Needs ruby + the liquid gem for the render half, like the hierarchy suite. Without them L1
fails and every render check fails with it, rather than skipping silently.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_template_presence_guards.py
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
_LAYOUTS = _AUX / "_layouts"
_INCLUDES = _AUX / "_includes"
CSS_PATH = _AUX / "assets" / "css" / "auxsays-custom.css"
JS_PATH = _AUX / "assets" / "js" / "auxsays.js"
BASE_LAYOUT_PATH = _AUX / "_layouts" / "aux-base.html"

COMMENT_RE = re.compile(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", re.S)
FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.S)
INCLUDE_RE = re.compile(r"\{%-?\s*include\s.*?-?%\}", re.S)
TAG_IN_COMMENT_RE = re.compile(r"\{%|\{\{")

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
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))


def template_files() -> list[Path]:
    return sorted(_LAYOUTS.glob("*.html")) + sorted(_INCLUDES.glob("*.html"))


def emitted(src: str) -> str:
    """The markup Jekyll actually renders: front matter and comment blocks removed."""
    return COMMENT_RE.sub("", FRONT_MATTER_RE.sub("", src))


# --------------------------------------------------------------------------- ruby bridge

_RUBY_DRIVER = r"""
require 'liquid'
require 'json'

module Shims
  def relative_url(i) = "/" + i.to_s.sub(%r{\A/}, "")
  def absolute_url(i) = "https://auxsays.test/" + i.to_s.sub(%r{\A/}, "")
  def jsonify(i) = JSON.generate(i)
  def markdownify(i) = i.to_s
  def date_to_string(i) = i.to_s
  def date_to_long_string(i) = i.to_s
  def number_with_delimiter(i) = i.to_s
end
Liquid::Template.register_filter(Shims)

# jekyll-seo-tag is a plugin, not core Liquid. Stub it so aux-base parses.
class SeoStub < Liquid::Tag
  def render(_ctx) = ""
end
Liquid::Template.register_tag("seo", SeoStub)

payload = JSON.parse(File.read(ARGV[0]))
out = { "string_responds_to_blank" => "".respond_to?(:blank?),
        "liquid_version" => Liquid::VERSION, "parse" => {}, "render" => {} }

payload["parse"].each do |name, src|
  begin
    Liquid::Template.parse(src)
    out["parse"][name] = "OK"
  rescue => e
    out["parse"][name] = "#{e.class}: #{e.message}"
  end
end

payload["render"].each do |name, job|
  begin
    tpl = Liquid::Template.parse(job["template"])
    out["render"][name] = tpl.render!(job["assigns"])
  rescue => e
    out["render"][name] = "<<ERR: #{e.class}: #{e.message}>>"
  end
end

print JSON.generate(out)
"""


def run_ruby(parse_jobs: dict, render_jobs: dict) -> tuple[bool, dict]:
    """Returns (liquid_ok, results). Never raises: a missing ruby is a FAIL, not a skip."""
    empty = {"parse": {}, "render": {}, "string_responds_to_blank": None}
    ruby = shutil.which("ruby")
    if not ruby:
        return False, dict(empty, _stderr="ruby is not on PATH")
    tmp = Path(tempfile.mkdtemp(prefix="auxsays-presence-"))
    try:
        script = tmp / "driver.rb"
        script.write_text(_RUBY_DRIVER, encoding="utf-8")
        payload = tmp / "payload.json"
        payload.write_text(json.dumps({"parse": parse_jobs, "render": render_jobs}),
                           encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload)],
                              capture_output=True, text=True, encoding="utf-8")
        if proc.returncode != 0 or not proc.stdout.strip():
            return False, dict(empty, _stderr=(proc.stderr or "")[:600])
        return True, json.loads(proc.stdout)
    except Exception as exc:  # noqa: BLE001
        return False, dict(empty, _stderr=repr(exc))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


_MISSING: list[str] = []


def extract(src: str, pattern: str, label: str) -> str:
    """Lift a fragment of the SHIPPED template so the assertions run on real source.

    A fragment that cannot be found does NOT raise. Raising would abort the run and report
    zero checks, which both hides which behaviours broke and defeats the governed per-suite
    check count. Instead the loss is recorded for S4 and a marker template is substituted,
    so every downstream assertion fails by name with a readable reason.
    """
    m = re.search(pattern, src, re.S)
    if not m:
        _MISSING.append(label)
        return "<<ERR: FRAGMENT NOT FOUND: " + label + ">>"
    return m.group(0)


# --------------------------------------------------------------------------- the suite

def run() -> int:
    files = template_files()

    # ---- S: structural bans over emitting markup -------------------------------------
    offenders: list[str] = []
    for path in files:
        body = emitted(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"[!=]=\s*blank\b", body):
            offenders.append(f"{path.name}:~{body.count(chr(10), 0, m.start()) + 1}")
    check("S1 no `== blank` / `!= blank` presence test survives in emitting markup",
          not offenders,
          f"inert in this stack, so these guards always pass: {offenders[:8]}")

    bad_comments: list[str] = []
    for path in files:
        for m in COMMENT_RE.finditer(path.read_text(encoding="utf-8")):
            inner = re.sub(r"\A\{%-?\s*comment\s*-?%\}|\{%-?\s*endcomment\s*-?%\}\Z",
                           "", m.group(0))
            if TAG_IN_COMMENT_RE.search(inner):
                bad_comments.append(path.name)
    check("S2 no comment block contains a Liquid tag delimiter in its prose",
          not bad_comments,
          "`comment` still PARSES tags, so a literal tag in prose is a SyntaxError that "
          f"kills the whole template: {sorted(set(bad_comments))}")

    update_src = (_LAYOUTS / "aux-update.html").read_text(encoding="utf-8")
    normalised = re.findall(r"\{% assign \w+ = page\.[\w.]+ \| default: '' \| strip %\}",
                            update_src)
    check("S3 aux-update normalises every page field it tests for presence",
          len(normalised) >= 10,
          f"expected the normalised-presence block, found {len(normalised)} assigns")

    # ---- build the ruby jobs ---------------------------------------------------------
    parse_jobs = {p.name: INCLUDE_RE.sub("", FRONT_MATTER_RE.sub("", p.read_text(encoding="utf-8")))
                  for p in files}

    home_src = (_LAYOUTS / "aux-home.html").read_text(encoding="utf-8")
    home_block = extract(
        home_src,
        r"\{% assign image_candidate = post\.image.*?"
        r"\{% assign article_image_src = image_candidate \| default: '' \| strip %\}",
        "the homepage thumbnail resolution block")
    home_probe = (home_block +
                  "[{% if article_image_src != '' %}{{ article_image_src }}"
                  "{% else %}PLACEHOLDER{% endif %}]")

    feed_src = (_LAYOUTS / "aux-updates.html").read_text(encoding="utf-8")
    feed_norm = extract(
        feed_src,
        r"\{% assign it_feed_title = item\.update_feed_title \| default: '' \| strip %\}\s*"
        r"(?:\{% assign it_\w+ = item\.\w+ \| default: '' \| strip %\}\s*){4}",
        "the feed's normalised item block")
    feed_title_ladder = extract(
        feed_src,
        r"\{% if it_feed_title != '' %\}.*?\{% assign card_title = item\.title %\}\s*\{% endif %\}",
        "the feed card-title ladder")
    feed_download = extract(
        feed_src,
        r"\{% if it_download_url != '' %\}<a href=\"\{\{ it_download_url \}\}\">"
        r"Download page[^<]*</a>\{% endif %\}",
        "the feed download link")

    cite = extract(
        update_src,
        r"\{% assign source_title = source\.source_title.*?"
        r"<cite>\{% if source_name_clean != '' %\}.*?</cite>",
        "the accepted-source citation")
    # drive the citation without the surrounding for-loop
    cite_probe = cite.replace("source.", "src_fixture.")

    HOME_SHAPES = {
        "image only": {"image": "/a/hero.png"},
        "thumbnail fallback": {"thumbnail": "/a/t.png"},
        "thumb fallback": {"thumb": "/a/t2.png"},
        "cover fallback": {"cover": "/a/cover.png"},
        "hero_image fallback": {"hero_image": "/a/h.png"},
        "featured_image fallback": {"featured_image": "/a/f.png"},
        "hash with path": {"image": {"path": "/a/p.png"}},
        "hash with url": {"image": {"url": "/a/u.png"}},
        "hash with src": {"image": {"src": "/a/s.png"}},
        "nothing at all": {},
        "empty image then real cover": {"image": "", "cover": "/a/c2.png"},
        "whitespace-only image": {"image": "   "},
    }
    render_jobs: dict[str, dict] = {}
    for name, post in HOME_SHAPES.items():
        render_jobs[f"home::{name}"] = {"template": home_probe, "assigns": {"post": post}}

    # keystone: is `blank` inert here?
    render_jobs["blank::nil"] = {
        "template": "{% if x != blank %}PASSED{% else %}GATED{% endif %}",
        "assigns": {"x": None}}
    render_jobs["blank::empty_eq"] = {
        "template": "{% if x == blank %}ABSENT{% else %}PRESENT{% endif %}",
        "assigns": {"x": ""}}

    # the normalised idiom, over all four input shapes
    idiom = ("{% assign c = x | default: '' | strip %}"
             "{% if c != '' %}PRESENT{% else %}ABSENT{% endif %}")
    for tag, val in [("nil", None), ("empty", ""), ("whitespace", "   "), ("real", "v1.2")]:
        render_jobs[f"idiom::{tag}"] = {"template": idiom, "assigns": {"x": val}}

    for tag, item in [
        ("no download url", {"update_download_url": None}),
        ("empty download url", {"update_download_url": ""}),
        ("real download url", {"update_download_url": "https://example.test/dl"}),
    ]:
        render_jobs[f"feed_dl::{tag}"] = {"template": feed_norm + feed_download,
                                          "assigns": {"item": item}}
    for tag, item in [
        ("feed title wins", {"update_feed_title": "Explicit Feed Title",
                             "update_product": "P", "update_version": "1.0", "title": "fallback"}),
        ("product and version", {"update_product": "OBS Studio", "update_version": "32.1.2",
                                 "title": "fallback"}),
        ("product only", {"update_product": "OBS Studio", "title": "fallback"}),
        ("nothing named", {"title": "Record fallback title"}),
        ("whitespace title falls through", {"update_feed_title": "   ",
                                            "update_product": "OBS Studio",
                                            "update_version": "32.1.2", "title": "fallback"}),
    ]:
        render_jobs[f"feed_title::{tag}"] = {
            "template": feed_norm + feed_title_ladder + "[{{ card_title }}]",
            "assigns": {"item": item}}

    for tag, src_fixture in [
        ("no date", {"source_name": "obsproject/obs-studio", "source_url": "https://e.test/1",
                     "source_title": "Crash on launch"}),
        ("empty date", {"source_name": "obsproject/obs-studio", "source_date": "",
                        "source_url": "https://e.test/1", "source_title": "Crash on launch"}),
        ("real date", {"source_name": "obsproject/obs-studio", "source_date": "2026-03-04",
                       "source_url": "https://e.test/1", "source_title": "Crash on launch"}),
        ("no name", {"source_date": "2026-03-04", "source_url": "https://e.test/1",
                     "source_title": "Crash on launch"}),
        # An accepted report without a URL is the case that produced the feed's 1,095
        # empty-href links. Without this fixture C5 only ever sees a populated URL, so
        # reverting the citation's url guard was caught by S1 alone and by no behaviour.
        ("no url", {"source_name": "obsproject/obs-studio", "source_date": "2026-03-04",
                    "source_title": "Crash on launch"}),
    ]:
        render_jobs[f"cite::{tag}"] = {"template": cite_probe,
                                       "assigns": {"src_fixture": src_fixture}}

    check("S4 every assertion fragment is still locatable in the shipped templates",
          not _MISSING,
          "the markup moved, so the checks below are no longer reading what ships: "
          f"{_MISSING}")

    liquid_ok, res = run_ruby(parse_jobs, render_jobs)
    rendered = res.get("render", {})
    parsed = res.get("parse", {})

    print()
    check("L1 the liquid gem is available, so these assertions run for real", liquid_ok,
          "install liquid 4.0.4; CI does this explicitly and must not skip these silently. "
          f"{res.get('_stderr', '')}")

    bad_parse = {k: v for k, v in parsed.items() if v != "OK"}
    check("L2 every shipped layout and include parses",
          liquid_ok and not bad_parse,
          f"a Liquid SyntaxError takes the whole page down: {bad_parse}")

    # ---- K: the keystone -- `blank` really is inert here -----------------------------
    check("K1 `x != blank` passes even when x is nil, so the guard never gated",
          rendered.get("blank::nil") == "PASSED",
          f"got {rendered.get('blank::nil')!r}; if this now GATES, `blank` works in this "
          "stack and S1's ban should be revisited on the evidence")
    check("K2 `x == blank` is false even when x is '', so those branches were dead",
          rendered.get("blank::empty_eq") == "PRESENT",
          f"got {rendered.get('blank::empty_eq')!r}")
    check("K3 String does not respond to `blank?`, which is the mechanism",
          res.get("string_responds_to_blank") is False,
          "`blank` needs ActiveSupport's blank?; Jekyll does not load it. Got "
          f"{res.get('string_responds_to_blank')!r}")

    # ---- I: the replacement idiom ----------------------------------------------------
    check("I1 the normalised idiom reads nil as absent",
          rendered.get("idiom::nil") == "ABSENT", repr(rendered.get("idiom::nil")))
    check("I2 the normalised idiom reads '' as absent",
          rendered.get("idiom::empty") == "ABSENT", repr(rendered.get("idiom::empty")))
    check("I3 the normalised idiom reads whitespace-only as absent, as `blank` intended",
          rendered.get("idiom::whitespace") == "ABSENT", repr(rendered.get("idiom::whitespace")))
    check("I4 the normalised idiom reads a real value as present",
          rendered.get("idiom::real") == "PRESENT", repr(rendered.get("idiom::real")))

    # ---- H: the homepage thumbnail, which never resolved at all ----------------------
    expected_home = {
        "image only": "/a/hero.png",
        "thumbnail fallback": "/a/t.png",
        "thumb fallback": "/a/t2.png",
        "cover fallback": "/a/cover.png",
        "hero_image fallback": "/a/h.png",
        "featured_image fallback": "/a/f.png",
        "hash with path": "/a/p.png",
        "hash with url": "/a/u.png",
        "hash with src": "/a/s.png",
        "nothing at all": "PLACEHOLDER",
        "empty image then real cover": "/a/c2.png",
        "whitespace-only image": "PLACEHOLDER",
    }
    for name, want in expected_home.items():
        got = rendered.get(f"home::{name}", "")
        check(f"H  homepage thumbnail resolves {name} -> {want}",
              got.strip() == f"[{want}]",
              f"got {got.strip()!r}; on origin/main EVERY shape here resolved to nil and the "
              "card emitted an img with an empty src")

    # ---- F: the feed -----------------------------------------------------------------
    check("F1 a record with no download URL renders no download link",
          rendered.get("feed_dl::no download url", "MISSING").strip() == "",
          repr(rendered.get("feed_dl::no download url")))
    check("F2 a record with an empty download URL renders no empty href",
          'href=""' not in rendered.get("feed_dl::empty download url", 'href=""'),
          "1,095 feed rows shipped an empty-href Download page link, which reloads the feed")
    check("F3 a record with a real download URL still renders the link",
          'href="https://example.test/dl"' in rendered.get("feed_dl::real download url", ""),
          repr(rendered.get("feed_dl::real download url")))

    expected_title = {
        "feed title wins": "Explicit Feed Title",
        "product and version": "OBS Studio 32.1.2",
        "product only": "OBS Studio",
        "nothing named": "Record fallback title",
        "whitespace title falls through": "OBS Studio 32.1.2",
    }
    for name, want in expected_title.items():
        got = rendered.get(f"feed_title::{name}", "")
        check(f"F  feed card title: {name} -> {want!r}",
              got.strip().endswith(f"[{want}]"), f"got {got.strip()[-80:]!r}")

    # ---- C: the citation that printed an empty ( ) 107 times on one live page --------
    no_date = rendered.get("cite::no date", "")
    empty_date = rendered.get("cite::empty date", "")
    real_date = rendered.get("cite::real date", "")
    no_name = rendered.get("cite::no name", "")
    check("C1 a source with no date renders no empty parentheses",
          "()" not in no_date and not no_date.startswith("<<ERR"),
          "the live OBS 32.1.2 page shipped 107 of 109 citations with an empty (): "
          f"{no_date[:160]!r}")
    check("C2 a source with an empty date renders no empty parentheses",
          "()" not in empty_date and not empty_date.startswith("<<ERR"),
          repr(empty_date[:160]))
    check("C3 a source with a real date still renders it",
          "2026" in real_date, repr(real_date[:160]))
    check("C4 a source with no name renders no stray separator before the date",
          not re.search(r"<cite>\s*\.", no_name) and not no_name.startswith("<<ERR"),
          repr(no_name[:160]))
    no_url = rendered.get("cite::no url", "")
    check("C6 a source with no URL renders plain text, never an empty href",
          'href=""' not in no_url and "Crash on launch" in no_url
          and not no_url.startswith("<<ERR"),
          "an empty href resolves to the current page, so the citation would self-link: "
          f"{no_url[:160]!r}")
    check("C5 the citation always keeps its link",
          all('href="https://e.test/1"' in r
              for r in (no_date, empty_date, real_date, no_name)),
          "the source URL is the audit trail and must survive every presence gate")

    # ---- V: the entrance animation must not be able to hide content ----------------
    css = CSS_PATH.read_text(encoding="utf-8")
    js = JS_PATH.read_text(encoding="utf-8")

    default_rule = re.search(r"^\.reveal-up \{([^}]*)\}", css, re.M)
    check("V1 the bare `.reveal-up` default is visible",
          bool(default_rule) and "opacity:1" in (default_rule.group(1).replace(" ", "")),
          "an opacity-0 default means a crawler, a reader with JS off, or a missed observer "
          f"callback sees nothing: {default_rule.group(1) if default_rule else 'rule absent'!r}")

    hidden = re.findall(r"^(html\.js-reveal )?\.reveal-up(?:\.[\w-]+)? \{([^}]*)\}", css, re.M)
    unscoped_hidden = [body for scope, body in hidden
                       if not scope and "opacity:0" in body.replace(" ", "")]
    check("V2 nothing hides `.reveal-up` outside the `html.js-reveal` scope",
          not unscoped_hidden,
          f"only the class the script adds for itself may arm the hidden state: {unscoped_hidden}")

    check("V3 the hidden start state is armed only under `html.js-reveal`",
          "html.js-reveal .reveal-up {" in css and "opacity:0" in css.split(
              "html.js-reveal .reveal-up {")[1].split("}")[0].replace(" ", ""),
          "the opt-in rule is what makes the animation possible at all")

    base = BASE_LAYOUT_PATH.read_text(encoding="utf-8")
    head = base.split("</head>")[0] if "</head>" in base else ""

    # The arming must happen BEFORE first paint, which means a synchronous inline script in <head>.
    # Measured on the live site when it was armed from the deferred script instead: content painted
    # at 123ms, `js-reveal` arrived at 158ms, and because the armed rule carries a .72s opacity
    # transition the page then faded to opacity 0 and did not return until 1679ms -- 200 frames
    # below 0.95. The reader saw the whole body disappear for a second and a half.
    arming = re.search(r"classList\.add\('js-reveal'\)", head)
    check("V4 `js-reveal` is armed by a synchronous script inside <head>",
          arming is not None,
          "arming from the deferred script paints the content visible and then fades it out")
    check("V4a that arming script is not deferred or async",
          arming is not None
          and not re.search(r"<script[^>]*\b(defer|async)\b[^>]*>(?:(?!</script>).)*"
                            r"classList\.add\('js-reveal'\)", head, re.S),
          "a deferred script runs after parsing, which is exactly the regression this replaced")
    check("V4b the head script arms only when it can observe and motion is allowed",
          arming is not None
          and "typeof IntersectionObserver !== 'function'" in head
          and "prefers-reduced-motion: reduce" in head,
          "without both guards the hidden state is armed on browsers that can never un-arm it")
    check("V4c the head script un-arms itself if the main script never claims the reveals",
          "__auxRevealReady" in head and "classList.remove('js-reveal')" in head,
          "if auxsays.js 404s or throws, nothing would ever add `.is-visible` and the armed page "
          "would stay blank -- the failsafe is what makes arming early safe")
    check("V4d the main script claims the reveals rather than re-deciding",
          "window.__auxRevealReady = true;" in js
          and "classList.contains('js-reveal')" in js
          and "classList.add('js-reveal')" not in js,
          "two places deciding whether to arm is two places to get it wrong")

    check("V5 the observer threshold is 0, not a ratio a tall element cannot reach",
          "threshold: 0," in js and "threshold: 0.08" not in js,
          "intersectionRatio for an element taller than the viewport is "
          "viewportHeight/elementHeight, so 0.08 was unsatisfiable above ~12 viewports and the "
          "410-row Adobe history never revealed")

    check("V6 a timed sweep reveals anything the observer missed",
          "'.reveal-up:not(.is-visible)'" in js and "setTimeout" in js,
          "a missed callback must not be able to leave content hidden permanently")

    print()
    print("=" * 78)
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
