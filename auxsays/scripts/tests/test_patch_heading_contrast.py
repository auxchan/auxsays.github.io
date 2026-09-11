#!/usr/bin/env python3
"""Patch-page headings stay readable whichever colour scheme the reader's OS prefers.

THE DEFECT. The site paints a fixed dark ground in every colour scheme
(`html, body { background: var(--bg-0) }`), but the theme colours headings with
`h1, h2, h3, h4, h5 { color: var(--heading-color) }` and flips that token on
prefers-color-scheme: #cccccc for dark, #2a2a2a for light. With the OS set to light, the patch-page
title and the Level-2 / Level-3 card titles rendered #2a2a2a on #0a0d10 -- measured in Chromium at
1.36:1 and 1.30:1 -- while the same page with the OS set to dark read at about 12:1. Nothing in the
stylesheet was "wrong" in isolation: the page owned its ground but not its heading colour.

WHAT THIS SUITE DOES. It evaluates the cascade rather than searching the stylesheet for a token. A
grep for `--heading-color` cannot tell a declaration that reaches the heading from one inside a
comment, behind a media query that only matches in dark mode, or scoped to an element the heading
is not inside -- and those are exactly the ways this repair can silently stop working.

  * The REAL layout is rendered through the liquid gem (the harness test_patch_page_hierarchy.py
    uses), wrapped in aux-base.html, so every heading is evaluated inside the ancestor chain the
    page really emits.
  * Stylesheets are applied in the order the rendered <head> links them: the theme first, then
    auxsays-custom.css. The theme is not vendored in this repo (it comes from the gem at build
    time), so its heading contract is pinned below from the stylesheet production serves.
  * For each heading, under prefers-color-scheme light AND dark, at a desktop and a mobile width,
    it resolves the computed colour (specificity, !important, media, inheritance, var()) and the
    worst-case backdrop: every background layer from the canvas down, alpha-composited, with each
    gradient stop and the fixed decorative underlays counted as candidates. The threshold is 4.5:1
    for every heading, large or not -- one readable treatment, not the large-text allowance.

[E] first proves the evaluator discriminates, against synthetic fixtures, so a broken evaluator
cannot report everything as passing. [M] then removes the repair in memory and requires the
original defect to come back, which is what makes the rest of the suite non-vacuous.

MODEL LIMITS, stated so nobody over-reads a green run: element `opacity` and `mask-image` are not
modelled (underlay layers count at full alpha, which only lightens the backdrop -- stricter for
light text), url() images fail the check rather than being guessed at, and the `.reveal-up` entrance
animation is evaluated at its settled state.

Static and offline apart from one `ruby` call; writes nothing. No Jekyll, no browser.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_patch_heading_contrast.py
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
CSS_PATH = _AUX / "assets" / "css" / "auxsays-custom.css"
UPDATE_LAYOUT = _AUX / "_layouts" / "aux-update.html"
BASE_LAYOUT = _AUX / "_layouts" / "aux-base.html"

THRESHOLD = 4.5
ENVS = [("light", 1280), ("dark", 1280), ("light", 390), ("dark", 390)]

# The theme's heading contract, as served by https://auxsays.com/assets/css/jekyll-theme-chirpy.css
# on 2026-09-11 (sha256 f2561ba16fe9f56b2301390174fac8b60438d17ea8511fd94759c7200339da60; lines
# 54-55, 206-215, 514, 812-830, 1082-1100, 1352-1355). Only the rules that reach a patch heading or
# one of its ancestors -- found by matching every theme rule against the live DOM -- and only the
# declarations this evaluator reads. There is no Gemfile.lock, so the theme version is whatever the
# Pages build resolves; if the theme changes this contract, re-capture it from production.
THEME_CONTRACT = """
header .post-desc, #toc-bar .label, #search-results a, h1, h2, h3, h4, h5 {
  color: var(--heading-color);
}
:root[data-bs-theme=light] { --main-bg: white; --text-color: #34343c; --heading-color: #2a2a2a; }
:root[data-bs-theme=dark] { color-scheme: dark; --main-bg: rgb(27 27 30);
  --text-color: rgb(175 176 177); --heading-color: #cccccc; }
@media (prefers-color-scheme: light) {
  :root:not([data-bs-theme]) { --main-bg: white; --text-color: #34343c; --heading-color: #2a2a2a; }
}
@media (prefers-color-scheme: dark) {
  :root:not([data-bs-theme]) { color-scheme: dark; --main-bg: rgb(27 27 30);
    --text-color: rgb(175 176 177); --heading-color: #cccccc; }
}
body { background: var(--main-bg); color: var(--text-color); }
"""

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
        msg = f"  FAIL  {label}"
        if detail:
            msg += f"\n        {detail}"
        print(msg)
        _ERRORS.append(label)


class Unsupported(Exception):
    """CSS the evaluator cannot model faithfully. Raised, never guessed past."""


# =============================================================================================
# CSS parsing -- comment- and string-aware, and faithful to how a declaration value swallows
# balanced {} blocks (the `--radius-xl: 28px@font-face {` class of defect).
# =============================================================================================

def strip_comments(css: str) -> str:
    out: list[str] = []
    i, n, quote = 0, len(css), ""
    while i < n:
        c = css[i]
        if quote:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(css[i + 1])
                i += 2
                continue
            if c == quote:
                quote = ""
            i += 1
        elif c == "/" and i + 1 < n and css[i + 1] == "*":
            end = css.find("*/", i + 2)
            end = n if end == -1 else end + 2
            out.append(re.sub(r"[^\n]", " ", css[i:end]))
            i = end
        else:
            if c in "\"'":
                quote = c
            out.append(c)
            i += 1
    return "".join(out)


def _scan(text: str, i: int, stops: str) -> int:
    """Index of the first char in `stops` at bracket depth 0 outside strings (len(text) if none).

    `{` is a stop when asked for; otherwise braces nest like the other brackets."""
    depth, quote, n = 0, "", len(text)
    while i < n:
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = ""
        elif c in "\"'":
            quote = c
        elif depth == 0 and c in stops:
            return i
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        i += 1
    return n


def _match_brace(text: str, open_i: int) -> int:
    depth, quote, i, n = 0, "", open_i, len(text)
    while i < n:
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = ""
        elif c in "\"'":
            quote = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n


@dataclass
class Rule:
    media: tuple
    selectors: list
    decls: list          # [(property, value, important)]
    order: int
    parsed: list = field(default_factory=list)   # [(parts, specificity)] or Unsupported
    error: str = ""


def parse_decls(body: str) -> list:
    decls = []
    i, n = 0, len(body)
    while i < n:
        j = _scan(body, i, ";")
        part = body[i:j].strip()
        i = j + 1
        if not part or ":" not in part:
            continue
        name, value = part.split(":", 1)
        name = name.strip()
        if not name.startswith("--"):
            name = name.lower()
            if "{" in value:
                raise Unsupported(f"nested rule inside a declaration block near {part[:60]!r}")
        value = value.strip()
        important = False
        m = re.search(r"!\s*important\s*$", value, re.I)
        if m:
            important = True
            value = value[:m.start()].strip()
        decls.append((name, value, important))
    return decls


def parse_stylesheet(css: str, start_order: int = 0) -> list:
    rules: list = []
    order = [start_order]

    def walk(text: str, media: tuple) -> None:
        i, n = 0, len(text)
        while i < n:
            while i < n and (text[i].isspace() or text[i] == ";"):
                i += 1
            if i >= n:
                return
            if text[i] == "}":
                i += 1
                continue
            j = _scan(text, i, "{;")
            prelude = text[i:j].strip()
            if j >= n:
                return
            if text[j] == ";":
                if prelude.lower().startswith("@import"):
                    raise Unsupported("@import pulls in a stylesheet this evaluator does not see")
                i = j + 1
                continue
            k = _match_brace(text, j)
            body = text[j + 1:k]
            if prelude.startswith("@"):
                name = re.match(r"@([\w-]+)", prelude).group(1).lower()
                cond = prelude[len(name) + 1:].strip()
                if name == "media":
                    walk(body, media + (cond,))
                elif name == "supports":
                    walk(body, media)          # modern Chromium: assume the feature is supported
                elif name in ("font-face", "keyframes", "-webkit-keyframes", "page", "counter-style"):
                    pass
                else:
                    # @layer reorders the cascade, @property can make a custom property
                    # non-inheriting, @container gates on geometry: none can be ignored safely.
                    raise Unsupported(f"@{name} is not modelled")
            else:
                sels = [s.strip() for s in _split_top(prelude, ",") if s.strip()]
                rules.append(Rule(media, sels, parse_decls(body), order[0]))
                order[0] += 1
            i = k + 1

    walk(strip_comments(css), ())
    return rules


def _split_top(text: str, sep: str) -> list:
    parts, i = [], 0
    while True:
        j = _scan(text, i, sep)
        parts.append(text[i:j])
        if j >= len(text):
            return parts
        i = j + 1


# =============================================================================================
# Media queries
# =============================================================================================

def _length_px(v: str) -> float:
    m = re.fullmatch(r"\s*([\d.]+)\s*(px|rem|em)?\s*", v)
    if not m:
        raise Unsupported(f"media length {v!r}")
    return float(m.group(1)) * (16.0 if m.group(2) in ("rem", "em") else 1.0)


def media_matches(query: str, env: dict) -> bool:
    for alt in _split_top(query, ","):
        alt = alt.strip().lower()
        negate = alt.startswith("not ")
        if negate:
            alt = alt[4:]
        alt = re.sub(r"^only\s+", "", alt)
        ok = True
        for term in re.split(r"\s+and\s+", alt):
            term = term.strip()
            if term in ("all", "screen"):
                continue
            if term in ("print", "speech"):
                ok = False
                continue
            m = re.fullmatch(r"\(\s*([a-z-]+)\s*(?::\s*([^)]+?))?\s*\)", term)
            if not m:
                raise Unsupported(f"media term {term!r}")
            feat, val = m.group(1), (m.group(2) or "").strip()
            if feat == "max-width":
                ok &= env["width"] <= _length_px(val)
            elif feat == "min-width":
                ok &= env["width"] >= _length_px(val)
            elif feat == "prefers-color-scheme":
                ok &= val == env["scheme"]
            elif feat == "prefers-reduced-motion":
                ok &= val == "no-preference"
            elif feat in ("hover", "any-hover"):
                ok &= (val or "hover") == ("hover" if env["width"] > 600 else "none")
            elif feat in ("pointer", "any-pointer"):
                ok &= (val or "fine") == ("fine" if env["width"] > 600 else "coarse")
            else:
                raise Unsupported(f"media feature {feat!r}")
        if ok != negate:
            return True
    return False


# =============================================================================================
# A small DOM from the rendered HTML
# =============================================================================================

class Node:
    __slots__ = ("tag", "attrs", "parent", "children", "text")

    def __init__(self, tag: str, attrs: dict | None = None, parent: "Node | None" = None):
        self.tag, self.attrs, self.parent = tag, attrs or {}, parent
        self.children: list[Node] = []
        self.text = ""

    @property
    def classes(self) -> set:
        return set(self.attrs.get("class", "").split())

    def element_parent(self) -> "Node | None":
        p = self.parent
        return p if p is not None and p.tag != "#document" else None

    def prev_element(self) -> "Node | None":
        if self.parent is None:
            return None
        sibs = self.parent.children
        i = sibs.index(self)
        return sibs[i - 1] if i > 0 else None

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def label(self) -> str:
        cls = self.attrs.get("class", "").split()
        return self.tag + ("." + cls[0] if cls else "")


_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param",
         "source", "track", "wbr"}


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#document")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v or "") for k, v in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, {k: (v or "") for k, v in attrs}, self.stack[-1]))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].text += data


def parse_html(html: str) -> Node:
    b = _Builder()
    b.feed(html)
    b.close()
    return b.root


def select(root: Node, selector: str) -> list:
    parts, _ = parse_selector(selector)
    return [n for n in root.walk() if n.tag != "#document" and matches(n, parts)]


# =============================================================================================
# Selectors
# =============================================================================================

_IDENT = re.compile(r"-?[_a-zA-Z][\w-]*")
_STATEFUL = {"hover", "focus", "focus-visible", "focus-within", "active", "target", "visited",
             "checked", "disabled", "indeterminate", "placeholder-shown", "autofill", "invalid",
             "user-invalid", "valid", "user-valid"}
_LEGACY_PSEUDO_ELEMENTS = {"before", "after", "first-line", "first-letter"}


def _ident(sel: str, i: int) -> tuple:
    m = _IDENT.match(sel, i)
    if not m:
        raise Unsupported(f"expected an identifier at {sel[i:i + 20]!r} in {sel!r}")
    return m.group(0), m.end()


def parse_selector(sel: str) -> tuple:
    """-> ([(combinator, [simple...]), ...], specificity). Combinator of the first part is None."""
    if "\\" in sel:
        raise Unsupported(f"escaped selector {sel!r}")
    parts, compound, comb = [], [], None
    i, n = 0, len(sel)
    while i < n:
        c = sel[i]
        if c.isspace() or c in ">+~":
            j, saw = i, " "
            while j < n and (sel[j].isspace() or sel[j] in ">+~"):
                if sel[j] in ">+~":
                    saw = sel[j]
                j += 1
            if compound:
                parts.append((comb, compound))
                compound, comb = [], saw
            elif saw != " ":
                raise Unsupported(f"relative selector {sel!r}")
            i = j
            continue
        if c == "*":
            compound.append(("univ",))
            i += 1
        elif c == "#":
            name, i = _ident(sel, i + 1)
            compound.append(("id", name))
        elif c == ".":
            name, i = _ident(sel, i + 1)
            compound.append(("class", name))
        elif c == "[":
            j = sel.index("]", i)
            m = re.fullmatch(r"\s*([\w-]+)\s*(?:([~|^$*]?=)\s*(\"[^\"]*\"|'[^']*'|[^\s\]]+)\s*(i|s)?)?\s*",
                             sel[i + 1:j])
            if not m:
                raise Unsupported(f"attribute selector {sel[i:j + 1]!r}")
            val = m.group(3)
            if val and val[0] in "\"'":
                val = val[1:-1]
            compound.append(("attr", m.group(1).lower(), m.group(2), val, m.group(4)))
            i = j + 1
        elif c == ":":
            element = sel.startswith("::", i)
            name, i = _ident(sel, i + (2 if element else 1))
            name = name.lower()
            arg = None
            if i < n and sel[i] == "(":
                k = _scan(sel, i + 1, ")")
                arg, i = sel[i + 1:k], k + 1
            if element or name in _LEGACY_PSEUDO_ELEMENTS:
                compound.append(("pe", name))
            else:
                compound.append(("pc", name, arg))
        else:
            name, i = _ident(sel, i)
            compound.append(("type", name.lower()))
    if compound:
        parts.append((comb, compound))
    if not parts:
        raise Unsupported(f"empty selector {sel!r}")
    return parts, _specificity(parts)


def _specificity(parts) -> tuple:
    a = b = c = 0
    for _comb, compound in parts:
        for s in compound:
            kind = s[0]
            if kind == "id":
                a += 1
            elif kind in ("class", "attr"):
                b += 1
            elif kind in ("type", "pe"):
                c += 1
            elif kind == "pc":
                name, arg = s[1], s[2]
                if name == "where":
                    continue
                if name in ("is", "not", "matches", "-webkit-any", "has"):
                    best = max((parse_selector(x.strip())[1] for x in _split_top(arg or "", ",")
                                if x.strip()), default=(0, 0, 0))
                    a, b, c = a + best[0], b + best[1], c + best[2]
                else:
                    b += 1
    return (a, b, c)


def _nth(expr: str, index: int) -> bool:
    expr = expr.replace(" ", "").lower()
    if expr == "odd":
        expr = "2n+1"
    elif expr == "even":
        expr = "2n"
    m = re.fullmatch(r"([+-]?\d*)n([+-]\d+)?", expr)
    if not m:
        return index == int(expr)
    a = int(m.group(1)) if m.group(1) not in ("", "+", "-") else (-1 if m.group(1) == "-" else 1)
    b = int(m.group(2) or 0)
    if a == 0:
        return index == b
    return (index - b) % a == 0 and (index - b) / a >= 0


def _siblings(node: Node) -> list:
    return [c for c in node.parent.children] if node.parent else [node]


def _match_simple(node: Node, s) -> bool:
    kind = s[0]
    if kind == "univ":
        return True
    if kind == "type":
        return node.tag == s[1]
    if kind == "id":
        return node.attrs.get("id") == s[1]
    if kind == "class":
        return s[1] in node.classes
    if kind == "attr":
        _, name, op, val, flag = s
        if name not in node.attrs:
            return False
        if op is None:
            return True
        have = node.attrs[name]
        if flag == "i":
            have, val = have.lower(), val.lower()
        return {"=": have == val, "~=": val in have.split(), "|=": have == val or have.startswith(val + "-"),
                "^=": have.startswith(val), "$=": have.endswith(val), "*=": val in have}[op]
    if kind == "pe":
        return False                      # styles a pseudo-element, never the element itself
    name, arg = s[1], s[2]
    if name == "root":
        return node.element_parent() is None and node.tag == "html"
    if name in ("is", "where", "matches", "-webkit-any"):
        return any(matches(node, parse_selector(x.strip())[0]) for x in _split_top(arg, ",") if x.strip())
    if name == "not":
        return not any(matches(node, parse_selector(x.strip())[0]) for x in _split_top(arg, ",") if x.strip())
    if name in _STATEFUL:
        return False                      # the static page: nothing hovered, focused or checked
    if name in ("link", "any-link"):
        return node.tag in ("a", "area") and "href" in node.attrs
    if name == "open":
        return "open" in node.attrs
    if name == "empty":
        return not node.children and not node.text.strip()
    sibs = _siblings(node)
    same = [x for x in sibs if x.tag == node.tag]
    if name == "first-child":
        return sibs[0] is node
    if name == "last-child":
        return sibs[-1] is node
    if name == "only-child":
        return len(sibs) == 1
    if name == "first-of-type":
        return same[0] is node
    if name == "last-of-type":
        return same[-1] is node
    if name == "nth-child":
        return _nth(arg, sibs.index(node) + 1)
    if name == "nth-last-child":
        return _nth(arg, len(sibs) - sibs.index(node))
    if name == "nth-of-type":
        return _nth(arg, same.index(node) + 1)
    raise Unsupported(f"pseudo-class :{name}")


def matches(node: Node, parts) -> bool:
    def at(idx: int, el: Node) -> bool:
        comb, compound = parts[idx]
        if not all(_match_simple(el, s) for s in compound):
            return False
        if idx == 0:
            return True
        link = parts[idx][0]
        if link == ">":
            p = el.element_parent()
            return p is not None and at(idx - 1, p)
        if link == " ":
            p = el.element_parent()
            while p is not None:
                if at(idx - 1, p):
                    return True
                p = p.element_parent()
            return False
        if link == "+":
            s = el.prev_element()
            return s is not None and at(idx - 1, s)
        if link == "~":
            s = el.prev_element()
            while s is not None:
                if at(idx - 1, s):
                    return True
                s = s.prev_element()
            return False
        raise Unsupported(f"combinator {link!r}")
    return at(len(parts) - 1, node)


# =============================================================================================
# Colour
# =============================================================================================

_NAMED = {"white": (255, 255, 255, 1.0), "black": (0, 0, 0, 1.0), "transparent": (0, 0, 0, 0.0),
          "dimgray": (105, 105, 105, 1.0), "gray": (128, 128, 128, 1.0), "grey": (128, 128, 128, 1.0),
          "silver": (192, 192, 192, 1.0), "lightgray": (211, 211, 211, 1.0),
          "lightcyan": (224, 255, 255, 1.0), "red": (255, 0, 0, 1.0)}


def parse_color(v: str):
    """-> (r, g, b, a) or None when `v` is not a colour."""
    v = v.strip().lower()
    if v in _NAMED:
        return _NAMED[v]
    m = re.fullmatch(r"#([0-9a-f]{3,8})", v)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h)
        if len(h) not in (6, 8):
            return None
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)
    m = re.fullmatch(r"rgba?\((.*)\)", v)
    if m:
        body = m.group(1).strip()
        alpha = "1"
        if "/" in body:
            body, alpha = body.split("/", 1)
        comps = [x for x in re.split(r"[\s,]+", body.strip()) if x]
        if len(comps) == 4:
            comps, alpha = comps[:3], comps[3]
        if len(comps) != 3:
            return None

        def chan(x):
            return float(x[:-1]) * 2.55 if x.endswith("%") else float(x)
        alpha = alpha.strip()
        a = float(alpha[:-1]) / 100 if alpha.endswith("%") else float(alpha)
        return (chan(comps[0]), chan(comps[1]), chan(comps[2]), max(0.0, min(1.0, a)))
    return None


def over(top, bottom):
    a = top[3]
    return (top[0] * a + bottom[0] * (1 - a), top[1] * a + bottom[1] * (1 - a),
            top[2] * a + bottom[2] * (1 - a), 1.0)


def _lin(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(c) -> float:
    return 0.2126 * _lin(c[0]) + 0.7152 * _lin(c[1]) + 0.0722 * _lin(c[2])


def contrast(fg, bg) -> float:
    fg = over(fg, bg) if fg[3] < 1 else fg
    hi, lo = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def hexc(c) -> str:
    return "#" + "".join(f"{round(x):02x}" for x in c[:3])


# =============================================================================================
# The cascade
# =============================================================================================

INVALID = object()


def _functions(value: str, names: tuple) -> list:
    """Top-level occurrences of name(...) in `value`, as (name, inner)."""
    out, i = [], 0
    rx = re.compile(r"(" + "|".join(re.escape(n) for n in names) + r")\(", re.I)
    while True:
        m = rx.search(value, i)
        if not m:
            return out
        k = _scan(value, m.end(), ")")
        out.append((m.group(1).lower(), value[m.end():k]))
        i = k + 1


class Styler:
    def __init__(self, sheets: list, env: dict):
        self.env = env
        self.rules = []
        for sheet in sheets:
            for r in sheet:
                try:
                    if all(media_matches(q, env) for q in r.media):
                        self.rules.append(r)
                except Unsupported as exc:
                    r.error = str(exc)       # reported by R4; never silently treated as matching
        self._matched: dict = {}
        self._custom: dict = {}
        self._color: dict = {}

    # -- which declarations reach a node ------------------------------------------------------
    def matched(self, node: Node) -> list:
        key = id(node)
        if key not in self._matched:
            hits = []
            for r in self.rules:
                if not r.parsed:
                    try:
                        r.parsed = [parse_selector(s) for s in r.selectors]
                    except Unsupported as exc:
                        r.parsed, r.error = [], str(exc)
                if r.error:
                    continue
                specs = [spec for parts, spec in r.parsed if matches(node, parts)]
                if specs:
                    hits.append((max(specs), r))
            self._matched[key] = hits
        return self._matched[key]

    def declared(self, node: Node, props: tuple):
        """The cascade winner among `props` on `node` -> (property, value) or None."""
        best, best_key = None, None
        for spec, r in self.matched(node):
            for di, (p, v, imp) in enumerate(r.decls):
                if p in props:
                    key = (imp, 0, spec, r.order, di)
                    if best_key is None or key > best_key:
                        best, best_key = (p, v), key
        style = node.attrs.get("style")
        if style:
            for di, (p, v, imp) in enumerate(parse_decls(style)):
                if p in props:
                    key = (imp, 1, (0, 0, 0), 10 ** 9, di)
                    if best_key is None or key > best_key:
                        best, best_key = (p, v), key
        return best

    # -- custom properties and var() ----------------------------------------------------------
    def custom(self, node: Node | None, name: str, stack: frozenset = frozenset()):
        if node is None:
            return None
        key = (id(node), name)
        if key in self._custom:
            return self._custom[key]
        d = self.declared(node, (name,))
        parent = node.element_parent()
        if d is None or d[1].strip().lower() in ("inherit", "unset", "revert"):
            val = self.custom(parent, name, stack)
        elif d[1].strip().lower() == "initial" or name in stack:
            val = None
        else:
            sub = self.substitute(node, d[1], stack | {name})
            val = None if sub is INVALID else sub
        self._custom[key] = val
        return val

    def substitute(self, node: Node, value: str, stack: frozenset = frozenset()):
        out, i = [], 0
        while True:
            m = re.compile(r"var\(", re.I).search(value, i)
            if not m:
                out.append(value[i:])
                return "".join(out)
            out.append(value[i:m.start()])
            k = _scan(value, m.end(), ")")
            inner = value[m.end():k]
            name, sep, fallback = inner.partition(",")
            name = name.strip()
            got = None if name in stack else self.custom(node, name, stack)
            if got is None:
                if not sep:
                    return INVALID
                got = self.substitute(node, fallback.strip(), stack)
                if got is INVALID:
                    return INVALID
            out.append(got)
            i = k + 1

    # -- color ----------------------------------------------------------------------------------
    def canvastext(self):
        return (255, 255, 255, 1.0) if self.env["scheme"] == "dark" else (0, 0, 0, 1.0)

    def color(self, node: Node | None):
        if node is None:
            return self.canvastext()
        key = id(node)
        if key in self._color:
            return self._color[key]
        parent = node.element_parent()
        d = self.declared(node, ("color",))
        value = None if d is None else self.substitute(node, d[1])
        if value is None or value is INVALID or value.strip().lower() in ("inherit", "unset", "currentcolor"):
            c = self.color(parent) if parent is not None else self.canvastext()
        elif value.strip().lower() == "initial":
            c = self.canvastext()
        else:
            c = parse_color(value)
            if c is None:
                raise Unsupported(f"color value {value!r} on {node.label()}")
        self._color[key] = c
        return c

    def keyword(self, node: Node, prop: str, default: str) -> str:
        d = self.declared(node, (prop,))
        if d is None:
            return default
        v = self.substitute(node, d[1])
        return default if v is INVALID else v.strip().lower()

    # -- backgrounds ----------------------------------------------------------------------------
    def layers(self, node: Node) -> tuple:
        """(background colour, [image layers bottom-to-top as colour-stop lists])."""
        colour = (0, 0, 0, 0.0)
        images: list = []
        dc = self.declared(node, ("background", "background-color"))
        di = self.declared(node, ("background", "background-image"))
        for which, d in (("color", dc), ("image", di)):
            if d is None:
                continue
            prop, raw = d
            value = self.substitute(node, raw)
            if value is INVALID:
                continue
            value = value.strip()
            layer_texts = [x.strip() for x in _split_top(value, ",")]
            if which == "color":
                if prop == "background-color":
                    c = parse_color(value)
                else:
                    c = None
                    for tok in _split_top(layer_texts[-1], " "):
                        c = parse_color(tok) or c
                if c is not None:
                    colour = c
            else:
                for text in reversed(layer_texts):       # the first listed layer paints on top
                    if prop == "background-image" and text.lower() == "none":
                        continue
                    if _functions(text, ("url", "image-set", "-webkit-image-set")):
                        raise Unsupported(f"raster background on {node.label()}: {text[:60]}")
                    for _fname, inner in _functions(text, ("linear-gradient", "radial-gradient",
                                                           "conic-gradient", "repeating-linear-gradient",
                                                           "repeating-radial-gradient")):
                        stops = []
                        for arg in _split_top(inner, ","):
                            toks = [t for t in _split_top(arg.strip(), " ") if t]
                            c = parse_color(toks[0]) if toks else None
                            if c is not None:
                                stops.append(c)
                        if stops:
                            images.append(stops)
        return colour, images

    def composite(self, node: Node, cands: set) -> set:
        colour, images = self.layers(node)
        if colour[3] > 0:
            cands = {over(colour, c) for c in cands}
        for stops in images:
            cands = {over(s, c) for s in stops for c in cands}
        return {tuple(round(x, 3) for x in c) for c in cands}

    def composite_tree(self, node: Node, cands: set) -> set:
        cands = self.composite(node, cands)
        for child in node.children:
            cands = self.composite_tree(child, cands)
        return cands

    def backdrop(self, target: Node) -> set:
        chain = []
        n = target
        while n is not None:
            chain.append(n)
            n = n.element_parent()
        chain.reverse()
        canvas = (18, 18, 18, 1.0) if self.env["scheme"] == "dark" else (255, 255, 255, 1.0)
        cands = {canvas}
        for idx, el in enumerate(chain):
            cands = self.composite(el, cands)
            if el.tag == "body":
                nxt = chain[idx + 1] if idx + 1 < len(chain) else None
                for child in el.children:
                    if child is nxt:
                        break
                    z = self.keyword(child, "z-index", "auto")
                    if self.keyword(child, "position", "static") == "fixed" and (
                            z == "auto" or (re.fullmatch(r"-?\d+", z) and int(z) <= 0)):
                        cands = self.composite_tree(child, cands)
            if len(cands) > 20000:
                raise Unsupported("backdrop candidate explosion")
        return cands

    def worst_contrast(self, target: Node) -> tuple:
        fg = self.color(target)
        worst = None
        for bg in self.backdrop(target):
            r = contrast(fg, bg)
            if worst is None or r < worst[0]:
                worst = (r, bg)
        return worst[0], fg, worst[1]


# =============================================================================================
# Rendering the real layout
# =============================================================================================

_RENDER_RB = """
require 'liquid'
require 'json'

module Shims
  def relative_url(i) = "/" + i.to_s.sub(%r{\\A/}, "")
  def absolute_url(i) = "https://auxsays.test/" + i.to_s.sub(%r{\\A/}, "")
  def jsonify(i) = JSON.generate(i)
  def markdownify(i) = i.to_s
end
Liquid::Template.register_filter(Shims)

payload = JSON.parse(File.read(ARGV[0]))
ctx = { 'site' => payload['site'], 'page' => payload['page'] }
inner = Liquid::Template.parse(payload['update']).render!(ctx.merge('content' => ''))
print Liquid::Template.parse(payload['base']).render!(ctx.merge('content' => inner))
"""

KEY = "microsoft-powerpoint|2608|20326.20100"
PAGE = {
    "layout": "aux-update",
    "title": "Microsoft PowerPoint 2608 (Build 20326.20100)",
    "product_id": "microsoft-powerpoint", "update_product": "Microsoft PowerPoint",
    "update_version": "2608", "target_build": "20326.20100",
    "update_published_at": "2026-08-18T00:00:00Z",
    "update_source_url": "https://example.test/release-notes",
    "consensus_collection_status": "deferred_official_only",
    "update_report_count": 0, "confirmed_patch_specific_report_count": 0,
    # markdownify is an identity shim here, so these are the HTML the real filter would emit
    "official_patch_notes_body": "<h2>What changed</h2>\n<p>Fixes.</p>\n<h3>Details</h3>\n<p>More.</p>",
    "official_checksums_body": "<h2>Checksums</h2>\n<p>sha256 0000</p>",
}
SITE = {
    "title": "AUXSAYS", "tagline": "t", "time": "2026-09-11T00:00:00Z",
    "data": {
        "evidence_method_health": {"methods": []},
        "update_linked_evidence": {"reports": [{
            "associated_patch_key": KEY, "report_title": "Embed iframes stopped loading",
            "source_url": "https://example.test/q/1", "source_family": "Microsoft Q&A",
            "report_date": "2026-08-22", "update_link_reason": "began after an Office update",
            "exact_build_known": False}]},
        "recent_powerpoint_reports": {"reports": [{
            "release_window_key": KEY, "report_title": "Slides freeze on open",
            "source_url": "https://example.test/q/2", "source_family": "Microsoft Q&A",
            "report_date": "2026-08-25", "window_version": "2608", "window_build": "20326.20100"}]},
    },
}


def _template(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[-1]
    # Includes need a file system and {% seo %} is a plugin tag; neither emits a heading colour.
    text = re.sub(r"\{%-?\s*include\s.*?-?%\}", "", text, flags=re.S)
    return re.sub(r"\{%-?\s*seo\s*-?%\}", "", text)


def render_page(page: dict = PAGE) -> tuple:
    """-> (html or None, reason)."""
    ruby = shutil.which("ruby")
    if not ruby:
        return None, "ruby is not on PATH"
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "render.rb"
        script.write_text(_RENDER_RB, encoding="utf-8")
        payload = Path(td) / "p.json"
        payload.write_text(json.dumps({"update": _template(UPDATE_LAYOUT), "base": _template(BASE_LAYOUT),
                                       "site": SITE, "page": page}), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
    if proc.returncode != 0:
        return None, (proc.stderr or "")[-400:]
    return proc.stdout, ""


# =============================================================================================
# The suite
# =============================================================================================

# (label, selector) -- the headings a patch page emits. The last is a CONTROL: it sets its own
# colour, so it must be unaffected by whatever the theme's token does.
TARGETS = [
    ("H1 patch title", "h1.update-title"),
    ("L2 update-linked card title", "h2.update-linked-card__title"),
    ("L3 recent-reports card title", "h2.recent-reports-card__title"),
    ("release-note heading", ".official-patch-notes.node-bullet-scope h2"),
    ("checksum heading", ".official-patch-notes.checksum-body h2"),
    ("control: official-sources subhead", "h3.update-source-subhead"),
]


def sheets_for(dom: Node, site_rules: list, theme_rules: list) -> tuple:
    """Stylesheets in the order the rendered <head> links them -> (sheets, names, unknown)."""
    sheets, names, unknown = [], [], []
    for link in select(dom, "link"):
        if "stylesheet" not in link.attrs.get("rel", "").split():
            continue
        href = link.attrs.get("href", "")
        if href.endswith("/jekyll-theme-chirpy.css"):
            sheets.append(theme_rules)
            names.append("theme")
        elif href.endswith("/auxsays-custom.css"):
            sheets.append(site_rules)
            names.append("site")
        else:
            unknown.append(href)
    return sheets, names, unknown


_STYLERS: dict = {}


def styler(sheets: list, scheme: str, width: int) -> Styler:
    """One Styler per (stylesheet set, environment): its caches are keyed on the DOM's nodes."""
    key = (tuple(id(s) for s in sheets), scheme, width)
    if key not in _STYLERS:
        _STYLERS[key] = Styler(sheets, {"scheme": scheme, "width": width})
    return _STYLERS[key]


def evaluate(dom: Node, sheets: list, selector: str, scheme: str, width: int):
    nodes = select(dom, selector)
    if not nodes:
        return None
    return styler(sheets, scheme, width).worst_contrast(nodes[0])


def _mini(css: str, html: str, scheme: str = "light", width: int = 1280):
    dom = parse_html(html)
    return dom, Styler([parse_stylesheet(css)], {"scheme": scheme, "width": width})


def engine_checks() -> None:
    print("\n[E] the evaluator discriminates -- synthetic fixtures")
    page = '<html><body class="s"><main><h1 id="t">x</h1></main><p id="sib">y</p></body></html>'

    dom, st = _mini("h1 { color: #111; } /* h1 { color: #eee; } */", page)
    check("E1 a declaration inside a comment is not live",
          hexc(st.color(select(dom, "#t")[0])) == "#111111", hexc(st.color(select(dom, "#t")[0])))

    css = "h1 { color: #111; } @media (prefers-color-scheme: dark) { h1 { color: #eee; } }"
    dom, lt = _mini(css, page, "light")
    _, dk = _mini(css, page, "dark")
    check("E2 a scheme-gated rule applies only under its scheme",
          hexc(lt.color(select(dom, "#t")[0])) == "#111111" and hexc(dk.color(select(dom, "#t")[0])) == "#eeeeee",
          f"light {hexc(lt.color(select(dom, '#t')[0]))} dark {hexc(dk.color(select(dom, '#t')[0]))}")

    dom, st = _mini("main h1 { color: #222; } h1 { color: #333; } .s h1 { color: #444; } h1 { color: #555 !important; } h1 { color: #666; }", page)
    check("E3 !important, then specificity, then order decide the winner",
          hexc(st.color(select(dom, "#t")[0])) == "#555555", hexc(st.color(select(dom, "#t")[0])))
    dom, st = _mini(".s h1 { color: #444; } main h1 { color: #222; }", page)
    check("E3b a class outranks a later, less specific rule",
          hexc(st.color(select(dom, "#t")[0])) == "#444444", hexc(st.color(select(dom, "#t")[0])))

    css = ":root { --h: #101010; } body.s main { --h: #fafafa; } h1, p { color: var(--h); }"
    dom, st = _mini(css, page)
    check("E4 a custom property set on an ancestor overrides :root for that subtree only",
          hexc(st.color(select(dom, "#t")[0])) == "#fafafa" and hexc(st.color(select(dom, "#sib")[0])) == "#101010",
          f"h1 {hexc(st.color(select(dom, '#t')[0]))} sibling {hexc(st.color(select(dom, '#sib')[0]))}")

    dom, st = _mini("h1 { color: var(--missing, #0e0e0e); }", page)
    check("E5 var() falls back when the property is undefined",
          hexc(st.color(select(dom, "#t")[0])) == "#0e0e0e", hexc(st.color(select(dom, "#t")[0])))

    css = "html, body { background: #000; } main { background: linear-gradient(180deg, #000, rgba(255,255,255,.9)); } h1 { color: #fff; }"
    dom, st = _mini(css, page)
    r, _fg, bg = st.worst_contrast(select(dom, "#t")[0])
    check("E6 a light gradient stop is a backdrop candidate (worst case, not the flat colour)",
          r < 2.0, f"worst {r:.2f} against {hexc(bg)}")

    css = "html { background: #000; } main { background-color: rgba(255,255,255,.5); } h1 { color: #fff; }"
    dom, st = _mini(css, page)
    r, _fg, bg = st.worst_contrast(select(dom, "#t")[0])
    check("E7 translucent backgrounds composite over what is beneath them",
          hexc(bg) in ("#7f7f7f", "#808080"), hexc(bg))

    check("E8 contrast anchors: #000 on #fff is 21:1, and #2a2a2a on #0a0d10 is the measured 1.36:1",
          abs(contrast((0, 0, 0, 1), (255, 255, 255, 1)) - 21.0) < 1e-9
          and round(contrast(parse_color("#2a2a2a"), parse_color("#0a0d10")), 2) == 1.36,
          f"{contrast(parse_color('#2a2a2a'), parse_color('#0a0d10')):.4f}")

    try:
        dom, st = _mini("h1:has(> span) { color: #fff; }", page)
        st.color(select(dom, "#t")[0])
        unsupported = [r.error for r in st.rules if r.error]
    except Unsupported as exc:
        unsupported = [str(exc)]
    check("E9 a selector the evaluator cannot model is reported, not silently skipped",
          bool(unsupported), "an unmodelled :has() rule vanished without a trace")

    dom, st = _mini("h1 { color: #121212; } h1::before { color: #fefefe; }", page)
    check("E10 a pseudo-element rule does not colour the element itself",
          hexc(st.color(select(dom, "#t")[0])) == "#121212", hexc(st.color(select(dom, "#t")[0])))

    dom, st = _mini("#t { color: #121212 !important; } h1 { color: #343434; }",
                    '<html><body><h1 id="t" style="color: #565656">x</h1><h1 id="u" style="color: #787878">y</h1></body></html>')
    check("E11 inline style beats selectors, and an !important rule beats inline style",
          hexc(st.color(select(dom, "#t")[0])) == "#121212" and hexc(st.color(select(dom, "#u")[0])) == "#787878",
          f"{hexc(st.color(select(dom, '#t')[0]))} {hexc(st.color(select(dom, '#u')[0]))}")

    dom, st = _mini(":root { --h: #0c0c0c; } main { --h: inherit; } h1 { color: var(--h); }", page)
    check("E12 `inherit` on a custom property takes the parent's value",
          hexc(st.color(select(dom, "#t")[0])) == "#0c0c0c", hexc(st.color(select(dom, "#t")[0])))


def run() -> int:
    print("=" * 78)
    print("Patch-page headings: readable in BOTH colour schemes on the fixed-dark ground")
    print("=" * 78)

    engine_checks()

    site_rules = parse_stylesheet(CSS_PATH.read_text(encoding="utf-8"), start_order=100000)
    theme_rules = parse_stylesheet(THEME_CONTRACT, start_order=0)

    # ---------- R: the real page ----------
    print("\n[R] the real layout renders, and is styled in the order its <head> links")
    html, reason = render_page()
    check("R1 aux-base + aux-update render through the liquid gem", html is not None,
          f"{reason} -- install liquid 4.0.4; CI does this explicitly")
    dom = parse_html(html or "<html><body></body></html>")
    body = select(dom, "body")
    check("R2 the rendered body carries the layout-derived class aux-update",
          bool(body) and {"aux-page", "aux-update"} <= body[0].classes,
          body[0].attrs.get("class") if body else "no <body>")
    sheets, names, unknown = sheets_for(dom, site_rules, theme_rules)
    check("R3 the theme stylesheet is linked before auxsays-custom.css, and nothing else is",
          names == ["theme", "site"] and not unknown, f"order={names} unknown={unknown}")
    if names != ["theme", "site"]:
        sheets = [theme_rules, site_rules]
    # Every rule that could colour or paint something must be one the evaluator understands.
    relevant = ("color", "background", "background-color", "background-image", "position", "z-index")
    blind = []
    for r in site_rules + theme_rules:
        if any(p in relevant or p.startswith("--") for p, _v, _i in r.decls):
            try:
                [parse_selector(s) for s in r.selectors]
                [media_matches(q, {"scheme": "light", "width": 1280}) for q in r.media]
            except Unsupported as exc:
                blind.append(f"{', '.join(r.selectors)[:60]} -> {exc}")
    check("R4 every colour / background / custom-property rule is one the evaluator can model",
          not blind, "; ".join(blind[:4]))
    # The render strips {% include %}. That is only safe while no stripped include emits a heading
    # -- otherwise [W] below would be blind to it.
    included = sorted({m for layout in (UPDATE_LAYOUT, BASE_LAYOUT)
                       for m in re.findall(r"\{%-?\s*include\s+([\w.-]+)", layout.read_text(encoding="utf-8"))})
    hidden = []
    for name in included:
        inc = _AUX / "_includes" / name
        tags = [n.tag for n in parse_html(inc.read_text(encoding="utf-8")).walk()] if inc.exists() else ["<missing>"]
        hidden += [f"{name}: <{t}>" for t in tags if re.fullmatch(r"h[1-6]|<missing>", t)]
    check(f"R5 none of the {len(included)} include(s) the render strips emits a heading",
          bool(included) and not hidden, "; ".join(hidden) or "no includes found")

    # ---------- C: each patch heading, both schemes, both widths ----------
    print(f"\n[C] each heading clears {THRESHOLD}:1 against its worst-case backdrop in every scheme")
    results: dict = {}
    for label, selector in TARGETS:
        present = bool(select(dom, selector)) if html else False
        check(f"C {label} is emitted by the layout ({selector})", present,
              "the render did not produce it" if html else "no render")
        for scheme, width in ENVS:
            got = None
            err = ""
            if present:
                try:
                    got = evaluate(dom, sheets, selector, scheme, width)
                except Unsupported as exc:
                    err = str(exc)
            results[(label, scheme, width)] = got
            ok = got is not None and got[0] >= THRESHOLD
            detail = err or ("not evaluated" if got is None else
                             f"{hexc(got[1])} on {hexc(got[2])} = {got[0]:.2f}:1")
            check(f"C {label} -- {scheme} scheme, {width}px -- >= {THRESHOLD}:1", ok, detail)
        colours = {hexc(results[(label, s, w)][1]) for s, w in ENVS if results[(label, s, w)]}
        check(f"S {label} is the same colour whatever the OS prefers",
              len(colours) == 1 and all(results[(label, s, w)] for s, w in ENVS), str(sorted(colours)))

    # ---------- W: every heading on the page, not just the named ones ----------
    print("\n[W] every h1-h6 the page emits, including ones nobody listed above")
    headings = [n for n in dom.walk() if re.fullmatch(r"h[1-6]", n.tag)]
    for scheme, width in ENVS:
        st = styler(sheets, scheme, width)
        bad = []
        for h in headings:
            try:
                r, fg, bg = st.worst_contrast(h)
            except Unsupported as exc:
                bad.append(f"{h.label()}: {exc}")
                continue
            if r < THRESHOLD:
                bad.append(f"{h.label()} {hexc(fg)} on {hexc(bg)} = {r:.2f}")
        check(f"W every heading ({len(headings)}) clears {THRESHOLD}:1 -- {scheme}, {width}px",
              bool(headings) and not bad, "; ".join(bad[:4]) or "no headings rendered")

    # ---------- O: the page owns the colour; the theme's token value is irrelevant ----------
    print("\n[O] the patch surface owns its heading colour -- perturbing the theme moves nothing")
    perturbed = parse_stylesheet(THEME_CONTRACT.replace("#2a2a2a", "#000000").replace("#cccccc", "#ffffff"))
    alt = [perturbed if s is theme_rules else s for s in sheets]
    for scheme in ("light", "dark"):
        moved = []
        for label, selector in TARGETS:
            try:
                a = evaluate(dom, sheets, selector, scheme, 1280)
                b = evaluate(dom, alt, selector, scheme, 1280)
            except Unsupported as exc:
                moved.append(f"{label}: {exc}")
                continue
            if a is None or b is None or hexc(a[1]) != hexc(b[1]):
                moved.append(f"{label}: {a and hexc(a[1])} -> {b and hexc(b[1])}")
        check(f"O no patch heading changes colour when the theme's {scheme} token changes",
              not moved, "; ".join(moved[:4]))

    # ---------- M: without the repair, the original defect comes back ----------
    print("\n[M] counterfactual: remove every site rule that sets the heading token")
    stripped = [Rule(r.media, r.selectors, [d for d in r.decls if d[0] != "--heading-color"], r.order)
                for r in site_rules]
    removed = sum(len(r.decls) for r in site_rules) - sum(len(r.decls) for r in stripped)
    cf = [stripped if s is site_rules else s for s in sheets]
    light = evaluate(dom, cf, "h1.update-title", "light", 1280) if html else None
    dark = evaluate(dom, cf, "h1.update-title", "dark", 1280) if html else None
    check("M1 without it the H1 falls back to the theme and fails in the light scheme (the bug)",
          removed >= 1 and light is not None and light[0] < THRESHOLD,
          f"removed {removed} declaration(s); light = "
          f"{'n/a' if light is None else f'{hexc(light[1])} {light[0]:.2f}:1'}")
    check("M2 ...while the dark scheme stays readable, so the defect is scheme-specific",
          dark is not None and dark[0] >= THRESHOLD,
          "n/a" if dark is None else f"{hexc(dark[1])} {dark[0]:.2f}:1")

    # ---------- K: the repair is scoped to the patch layout ----------
    print("\n[K] scope: the repair reaches the aux-update layout and nothing else")
    other, other_reason = render_page(dict(PAGE, layout="aux-patch-product")) if html else (None, "no render")
    odom = parse_html(other or "<html><body></body></html>")
    obody = select(odom, "body")
    for scheme in ("light", "dark"):
        ok = False
        detail = other_reason or "no body"
        if obody:
            st = Styler(sheets, {"scheme": scheme, "width": 1280})
            theme_only = Styler([theme_rules], {"scheme": scheme, "width": 1280})
            got = st.custom(obody[0], "--heading-color")
            want = theme_only.custom(obody[0], "--heading-color")
            ok = got is not None and got == want and "aux-update" not in obody[0].classes
            detail = f"body.{'.'.join(sorted(obody[0].classes))}: {got!r} vs theme {want!r} -- a " \
                     f"site-wide fix is a separate, deliberate decision; update [K] with it"
        check(f"K on a non-patch layout the heading token is still the theme's ({scheme})", ok, detail)

    print()
    print("=" * 78)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed tests:")
        for error in _ERRORS:
            print(f"  - {error}")
    print("=" * 78)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
