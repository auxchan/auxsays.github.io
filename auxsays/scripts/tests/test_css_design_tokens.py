#!/usr/bin/env python3
"""The design tokens `.panel` geometry depends on are LIVE in the cascade, not merely present.

WHY THIS SUITE EXISTS. `auxsays-custom.css` carried `--radius-xl: 28px@font-face {` -- a missing
semicolon. Per CSS Syntax a custom-property value consumes balanced {} blocks and ends only at a
top-level `;` or the rule's `}`, so that one missing character swallowed ~900 lines into the value
AND ate the `;` belonging to the `--radius-lg: 22px` that followed. Both tokens were therefore
UNDEFINED in the live cascade, `.panel` computed `border-radius: 0px` on 7237 elements across 1260
pages, and every structural test in this repo still passed -- because a grep for `--radius-xl`
finds it, a brace-balance check finds the file balanced, and the tokens are "present" in the file.

Presence is the wrong predicate. This suite parses the stylesheet the way the CSS parser does and
asserts REACHABILITY, distinguishing four states that a grep collapses into one:

    A  a real live declaration                          -> detected, with its value
    B  a declaration that exists only inside a comment  -> NOT detected
    C  a declaration swallowed inside a malformed value -> NOT detected
    D  a declaration that is simply absent              -> NOT detected

Section [A] proves the detector actually discriminates, against synthetic fixtures for all four.
A detector asserted only against the good case would pass while silently reporting everything as
live. Section [B] then applies it to the shipped stylesheet.

Static and offline: reads one CSS file, writes nothing, no Jekyll, no browser.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_css_design_tokens.py
"""
from __future__ import annotations

import re
import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
CSS_PATH = _REPO / "auxsays" / "assets" / "css" / "auxsays-custom.css"

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


# ---------------------------------------------------------------------------------------------
# A minimal CSS parser, comment- and string-aware.
#
# Deliberately NOT a regex over the raw source. A regex cannot tell a declaration from the same
# text inside a comment (state B) or inside another declaration's value (state C), and those are
# precisely the two states that shipped a broken cascade while looking correct in the file.
# ---------------------------------------------------------------------------------------------

def strip_comments(css: str) -> str:
    """Blank `/* */` comments, preserving line structure so reported offsets stay meaningful.

    String-aware: a `/*` inside url('...') or a quoted font name is content, not a comment.
    """
    out: list[str] = []
    i, n = 0, len(css)
    state = "code"
    quote = ""
    while i < n:
        c = css[i]
        if state == "code":
            if c == "/" and i + 1 < n and css[i + 1] == "*":
                state = "comment"
                out.append("  ")
                i += 2
                continue
            if c in "\"'":
                state = "string"
                quote = c
            out.append(c)
            i += 1
        elif state == "comment":
            out.append("\n" if c == "\n" else " ")
            if c == "*" and i + 1 < n and css[i + 1] == "/":
                out.append(" ")
                state = "code"
                i += 2
                continue
            i += 1
        else:  # inside a string
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(css[i + 1])
                i += 2
                continue
            if c == quote:
                state = "code"
            i += 1
    return "".join(out)


def live_custom_properties(css: str, selector: str = ":root") -> dict[str, str]:
    """Custom properties the CSS parser really registers for the FIRST `selector` rule.

    Values are consumed per CSS Syntax: a value swallows balanced {} blocks and terminates only
    at a top-level `;` or the rule's closing `}`. A declaration whose text is consumed by an
    earlier declaration's runaway value is therefore never registered -- which is exactly what
    happened to --radius-lg -- and a later declaration of the same name overrides an earlier one.
    """
    body = strip_comments(css)
    at = body.find(selector)
    if at == -1:
        return {}
    open_i = body.find("{", at)
    if open_i == -1:
        return {}

    decls: dict[str, str] = {}
    i, n = open_i + 1, len(body)
    while i < n:
        while i < n and body[i] in " \t\r\n;":
            i += 1
        if i >= n or body[i] == "}":
            break

        # property name, up to the ':' that opens its value
        j = i
        while j < n and body[j] not in ":;{}":
            j += 1
        if j >= n or body[j] != ":":
            break  # not a declaration (a nested rule, or the rule ended)
        name = body[i:j].strip()

        # value: consumes balanced blocks, ends at a top-level ';' or the rule's '}'
        k = j + 1
        vdepth = 0
        while k < n:
            ch = body[k]
            if ch == "{":
                vdepth += 1
            elif ch == "}":
                if vdepth == 0:
                    break
                vdepth -= 1
            elif ch == ";" and vdepth == 0:
                break
            k += 1
        value = body[j + 1:k].strip()
        if name.startswith("--"):
            decls[name] = value          # last declaration wins, as in the cascade
        if k >= n or body[k] == "}":
            break
        i = k + 1
    return decls


# ---------------------------------------------------------------------------------------------

FIXTURES = {
    # A: an ordinary live declaration.
    "A_live": ":root {\n  --radius-xl: 28px;\n  --radius-lg: 22px;\n}\n",
    # B: the declaration exists ONLY inside a comment. #115 left exactly this state behind, with
    #    both values recorded in prose while the cascade had neither.
    "B_comment_only": ":root {\n  /* --radius-xl: 28px; --radius-lg: 22px; */\n  --radius-md: 16px;\n}\n",
    # C: the original defect. The missing ';' after 28px makes the value swallow the block AND the
    #    --radius-lg declaration that follows, whose ';' becomes the value's terminator.
    "C_swallowed": (
        ":root {\n  --radius-xl: 28px@font-face {\n  font-family: 'X';\n}\n"
        ".panel { color: red; }\n  --radius-lg: 22px;\n  --radius-md: 16px;\n}\n"
    ),
    # D: simply absent.
    "D_absent": ":root {\n  --radius-md: 16px;\n}\n",
    # A `/*` inside a quoted string must not start a comment.
    "E_string_safe": ":root {\n  --sep: '/*';\n  --radius-xl: 28px;\n}\n",
}


def run() -> int:
    print("=" * 78)
    print("CSS design tokens: --radius-xl / --radius-lg are LIVE, not merely present")
    print("=" * 78)

    # ---------- A: the detector discriminates all four states ----------
    print("\n[A] the detector separates live / comment-only / swallowed / absent")

    a = live_custom_properties(FIXTURES["A_live"])
    check("A1 a real live declaration is detected", "--radius-xl" in a, str(sorted(a)))
    check("A2 ...carrying its actual value", a.get("--radius-xl") == "28px", repr(a.get("--radius-xl")))

    b = live_custom_properties(FIXTURES["B_comment_only"])
    check("A3 a declaration only inside a comment is NOT live", "--radius-xl" not in b, str(sorted(b)))
    check("A4 ...and its value does not leak from the comment either",
          b.get("--radius-lg") is None, repr(b.get("--radius-lg")))
    check("A5 ...while a real declaration in the same rule still is",
          b.get("--radius-md") == "16px", repr(b.get("--radius-md")))

    c = live_custom_properties(FIXTURES["C_swallowed"])
    check("A6 a runaway value is not mistaken for a clean declaration",
          c.get("--radius-xl") != "28px", repr(c.get("--radius-xl")))
    check("A7 ...the swallowed --radius-lg is NOT live", "--radius-lg" not in c, str(sorted(c)))
    check("A8 ...and the swallow is visible as a block inside the value",
          "{" in (c.get("--radius-xl") or ""), repr(c.get("--radius-xl"))[:80])
    # The blast radius is bounded, and that is the subtle part. The runaway value ends at the
    # FIRST top-level ';' it reaches -- the one belonging to --radius-lg -- so parsing resumes
    # immediately after it and --radius-md is live again. That asymmetry is exactly what the
    # production file showed: --radius-xl and --radius-lg dead, --radius-md live at 16px. A
    # detector that reported everything after the splice as dead would also "catch" the bug,
    # while being wrong about which tokens to trust.
    check("A9 ...but parsing RESUMES after the value's terminator, so --radius-md is live",
          c.get("--radius-md") == "16px", repr(c.get("--radius-md")))

    d = live_custom_properties(FIXTURES["D_absent"])
    check("A10 an absent declaration is NOT live", "--radius-xl" not in d, str(sorted(d)))

    e = live_custom_properties(FIXTURES["E_string_safe"])
    check("A11 a '/*' inside a quoted string does not start a comment",
          e.get("--radius-xl") == "28px", str(sorted(e)))

    # ---------- B: the shipped stylesheet ----------
    print("\n[B] the shipped stylesheet defines the panel geometry tokens in the live cascade")

    raw = CSS_PATH.read_text(encoding="utf-8")
    live = live_custom_properties(raw)

    for token, expected in (("--radius-xl", "28px"), ("--radius-lg", "22px"), ("--radius-md", "16px")):
        check(f"B1 {token} is LIVE in :root", token in live,
              "not registered by the parser -- absent, commented out, or swallowed by a "
              "malformed value above it")
        check(f"B2 {token} resolves to {expected}", live.get(token) == expected, repr(live.get(token)))

    # The splice class of defect, stated as an invariant rather than as one token's value: no
    # custom property in :root may have a value that opens a block. That is only ever a runaway.
    runaway = {k: v for k, v in live.items() if "{" in v or "}" in v}
    check("B3 no :root custom property value opens a block (the splice cannot return)",
          not runaway, str(sorted(runaway))[:200])

    # Every radius token the stylesheet CONSUMES must be one it defines. This is what actually
    # binds the tokens to the rendering: an undefined var() drops the whole declaration silently.
    body = strip_comments(raw)
    consumed = sorted(set(re.findall(r"var\(\s*(--radius-[a-z0-9-]+)", body)))
    check("B4 the stylesheet consumes at least one radius token", len(consumed) >= 2, str(consumed))
    for token in consumed:
        check(f"B5 consumer var({token}) resolves to a live declaration", token in live,
              f"{token} is used by the stylesheet but is not live -- every declaration that "
              f"reads it is dropped, so the element falls back to border-radius 0")

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
