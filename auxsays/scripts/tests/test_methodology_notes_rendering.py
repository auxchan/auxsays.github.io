#!/usr/bin/env python3
"""The methodology table's "Notes / block reason" cell: a real reason is primary, a note is never demoted.

WHAT WAS WRONG
--------------
The cell shipped as:

    <span>{% if item.blocked_reason != blank %}{{ item.blocked_reason }}{% else %}{{ item.notes }}
    {% endif %}<small>{% if item.blocked_reason != blank and item.notes != blank %}{{ item.notes }}
    {% endif %}</small></span>

`blank` is not a value in this Liquid. Measured against liquid 4.0.4 -- the version
`auxsays/Gemfile`'s `jekyll ~> 4.4` resolves to, and the version `pages.yml` builds the site with --
`blank` resolves to nil, so `'' != blank` is TRUE and `'' == blank` is FALSE. Both guards are
therefore unconditionally true.

Live consequence, measured on the deployed page and on `evidence_method_health.yml`:

    1496 rows total
     636 rows had an EMPTY primary cell with the row's real note demoted into <small>
     860 rows looked correct -- but only because two always-true guards happened to pick the
         intended branch. Correct by accident, not by logic.

This is the third instance of the same family in this repo: see the verdict that `!= blank` silently
blanked on 86 patch pages, and the `<small>` label whose colour rule was inert because a bare class
selector lost to `.update-decision-box__header p`. A test that merely greps for the presence of a
string would have passed in all three cases.

HOW THIS TEST AVOIDS BEING VACUOUS
----------------------------------
It does not grep. It extracts the Notes cell FROM THE SHIPPED PAGE and evaluates it with a small
interpreter for exactly the Liquid subset the cell uses (`assign` with `default`/`strip`, `if`/`else`
with `!=` and `and`, output tags, literal text).

The interpreter is CALIBRATED against the known-wrong template: given the pre-fix markup, it must
reproduce the phantom render exactly. An interpreter that cannot reproduce the bug cannot be trusted
to prove the bug is gone. Both directions are asserted, so the suite fails if either the template
regresses or the interpreter stops modelling `blank`.

Run standalone. Deterministic, offline, writes nothing. No Ruby required -- the Ruby render against
the real gem lives in `test_methodology_notes_liquid_render.py`, classified environment_specific.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PAGE_PATH = REPO / "auxsays" / "updates" / "methodology" / "index.md"
DATA_PATH = REPO / "auxsays" / "_data" / "evidence_method_health.yml"

NEWLINE = "\n"
_passed = 0
_failed = 0

# The pre-fix markup, kept verbatim so the interpreter can be calibrated against the real defect
# rather than against a paraphrase of it.
PRE_FIX = (
    "<span>{% if item.blocked_reason != blank %}{{ item.blocked_reason }}"
    "{% else %}{{ item.notes }}{% endif %}"
    "<small>{% if item.blocked_reason != blank and item.notes != blank %}"
    "{{ item.notes }}{% endif %}</small></span>"
)


def check(label: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  PASS  {label}")
    else:
        _failed += 1
        print(f"  FAIL  {label}" + (f"  --  {detail}" if detail else ""))


# ---------------------------------------------------------------------------------------------
# A Liquid interpreter for the subset this cell uses
# ---------------------------------------------------------------------------------------------

MISSING = object()
BLANK = object()


class Ctx:
    def __init__(self, item: dict) -> None:
        self.item = item
        self.vars: dict[str, str] = {}

    def resolve(self, expr: str):
        expr = expr.strip()
        if expr.startswith(("'", '"')):
            return expr[1:-1]
        if expr == "blank":
            # THE DEFECT, modelled. `blank` is a Liquid LITERAL that parses to the symbol
            # `:blank?`, not to a value, and nothing in a template ever equals that symbol. So
            # `x != blank` is TRUE for every x -- verified against liquid 4.0.4 for the empty
            # string, for nil, for an absent key and for ordinary text, all four returning the
            # `if` branch. Modelling it as nil (the intuitive guess) is WRONG: it would make
            # `nil != blank` false and hide the defect for null-valued fields.
            return BLANK
        if expr.startswith("item."):
            return self.item.get(expr[5:], MISSING)
        if expr in self.vars:
            return self.vars[expr]
        return MISSING


def _liquid_eq(a, b) -> bool:
    """Liquid equality for this subset.

    nil equals nil and equals a missing variable. BLANK equals nothing at all, which is what makes
    every `!= blank` guard unconditionally true.
    """
    if a is BLANK or b is BLANK:
        return False
    a = None if a is MISSING else a
    b = None if b is MISSING else b
    return a == b


def _apply_filters(value, filters: list[str]):
    for f in filters:
        f = f.strip()
        if f.startswith("default:"):
            arg = f.split(":", 1)[1].strip()
            arg = arg[1:-1] if arg.startswith(("'", '"')) else arg
            # Liquid's `default` substitutes when the value is nil, false, or EMPTY. Ruby's notion
            # of empty is `respond_to?(:empty?) && empty?`, which covers "" and [] and {} but NOT
            # 0. Testing `value == ""` instead diverges for a list: the gem yields "" for [] while
            # `[] == ""` is False in Python, so the interpreter would have yielded "[]". Every live
            # value of both fields is a str today (1496/1496 measured), so this was latent -- but an
            # interpreter that only agrees with the gem on the inputs that happen to occur is not a
            # model of the gem.
            empty = hasattr(value, "__len__") and len(value) == 0
            if value is MISSING or value is None or value is False or empty:
                value = arg
        elif f == "strip":
            value = "" if value is MISSING or value is None else str(value).strip()
        else:
            raise AssertionError(f"unmodelled filter {f!r} -- extend the interpreter deliberately")
    return value


def _eval_condition(cond: str, ctx: Ctx) -> bool:
    result = True
    for clause in re.split(r"\band\b", cond):
        clause = clause.strip()
        m = re.match(r"(.+?)\s*(!=|==)\s*(.+)", clause)
        if not m:
            raise AssertionError(f"unmodelled condition {clause!r}")
        left, op, right = m.group(1), m.group(2), m.group(3)
        eq = _liquid_eq(ctx.resolve(left), ctx.resolve(right))
        result = result and ((not eq) if op == "!=" else eq)
    return result


def render(template: str, item: dict) -> str:
    """Render the subset, including Liquid's `{%-` / `-%}` whitespace control.

    The trim markers are not cosmetic here: without them the assign tags leave their surrounding
    indentation in the output, and the 860 rows this change must NOT touch would appear to change.
    """
    ctx = Ctx(item)
    tokens = re.split(r"(\{\{-?.*?-?\}\}|\{%-?.*?-?%\})", template, flags=re.S)
    # Apply the trim markers to the literal text on either side of each tag, exactly as Liquid does.
    for i, tok in enumerate(tokens):
        if not tok or not tok.startswith(("{{", "{%")):
            continue
        if tok[2:3] == "-" and i > 0 and not tokens[i - 1].startswith(("{{", "{%")):
            tokens[i - 1] = tokens[i - 1].rstrip()
        if tok[-3:-2] == "-" and i + 1 < len(tokens) and not tokens[i + 1].startswith(("{{", "{%")):
            tokens[i + 1] = tokens[i + 1].lstrip()
    out: list[str] = []
    # A stack of "are we emitting?" plus whether this branch chain already matched.
    emit = [True]
    matched: list[bool] = []
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("{{"):
            if all(emit):
                v = ctx.resolve(tok[2:-2].strip())
                out.append("" if v is MISSING or v is None else str(v))
            continue
        if tok.startswith("{%"):
            body = tok.strip("{}%-").strip()
            if body.startswith("assign "):
                if all(emit):
                    name, expr = body[len("assign "):].split("=", 1)
                    parts = expr.split("|")
                    ctx.vars[name.strip()] = _apply_filters(
                        ctx.resolve(parts[0]), parts[1:])
            elif body.startswith("if "):
                cond = _eval_condition(body[3:], ctx) if all(emit) else False
                matched.append(cond)
                emit.append(cond)
            elif body.startswith("elsif "):
                already = matched[-1]
                emit.pop()
                cond = (not already) and _eval_condition(body[6:], ctx)
                matched[-1] = already or cond
                emit.append(cond)
            elif body == "else":
                already = matched[-1]
                emit.pop()
                emit.append(not already)
                matched[-1] = True
            elif body == "endif":
                emit.pop()
                matched.pop()
            elif body.startswith("comment") or body.startswith("endcomment"):
                raise AssertionError("comment tags must be stripped before rendering")
            else:
                raise AssertionError(f"unmodelled tag {body!r}")
            continue
        if all(emit):
            out.append(tok)
    return "".join(out)


# ---------------------------------------------------------------------------------------------

def notes_cell(page: str) -> str:
    """The shipped Notes cell: the mh_reason/mh_note assigns plus the <span> that consumes them."""
    m = re.search(
        r"(\{%-\s*assign mh_reason.*?\{%-\s*assign mh_note.*?<span>\{%\s*if mh_reason.*?</span>)",
        page, re.S)
    if m:
        return m.group(1)
    m = re.search(r"(<span>\{%\s*if item\.blocked_reason\s*!=\s*blank.*?</span>)", page, re.S)
    return m.group(1) if m else ""


def body_and_small(rendered: str) -> tuple[str, str | None]:
    small = re.search(r"<small>(.*?)</small>", rendered, re.S)
    body = re.sub(r"<small>.*?</small>", "", rendered, flags=re.S)
    body = body.replace("<span>", "").replace("</span>", "").strip()
    return body, (small.group(1).strip() if small else None)


FIXTURES = [
    ("1 real reason + a secondary note",  {"blocked_reason": "http_403_blocked", "notes": "Fetch failures: 1."}),
    ("2 empty reason + a note",           {"blocked_reason": "", "notes": "Reserved fallback discovery method."}),
    ("3 null reason + a note",            {"blocked_reason": None, "notes": "Reserved fallback discovery method."}),
    ("4 empty reason + empty note",       {"blocked_reason": "", "notes": ""}),
    ("5 real reason + empty note",        {"blocked_reason": "http_403_blocked", "notes": ""}),
    ("6 reason key absent + a note",      {"notes": "Reserved fallback discovery method."}),
    ("7 both keys absent",                {}),
    ("8 note identical to the reason",    {"blocked_reason": "same text", "notes": "same text"}),
    ("9 whitespace-only reason + a note", {"blocked_reason": "   ", "notes": "Real note."}),
]


def main() -> int:
    page = PAGE_PATH.read_text(encoding="utf-8")
    cell = notes_cell(page)
    # Strip Liquid comments -- they carry prose, including the words this test asserts about.
    cell = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "", cell, flags=re.S)

    print(NEWLINE + "[C] the interpreter is calibrated against the KNOWN-WRONG template")
    # If the interpreter cannot reproduce the defect, it cannot prove the defect is gone.
    pre2 = render(PRE_FIX, {"blocked_reason": "", "notes": "Reserved fallback discovery method."})
    b2, s2 = body_and_small(pre2)
    check("C1 pre-fix markup renders an EMPTY primary cell for an empty reason",
          b2 == "", f"body={b2!r}")
    check("C2 pre-fix markup demotes the real note into <small>",
          s2 == "Reserved fallback discovery method.", f"small={s2!r}")
    pre4 = render(PRE_FIX, {"blocked_reason": "", "notes": ""})
    check("C3 pre-fix markup emits a stray empty <small></small>",
          "<small></small>" in pre4, pre4)
    pre1 = render(PRE_FIX, {"blocked_reason": "http_403_blocked", "notes": "Fetch failures: 1."})
    check("C4 pre-fix markup is nonetheless correct when a real reason IS present",
          body_and_small(pre1) == ("http_403_blocked", "Fetch failures: 1."), pre1)
    # `!= blank` is true for EVERY input -- the four cases verified against liquid 4.0.4.
    for label, item in (("empty string", {"blocked_reason": ""}),
                        ("nil", {"blocked_reason": None}),
                        ("absent key", {}),
                        ("ordinary text", {"blocked_reason": "text"})):
        check(f"C5 `!= blank` is unconditionally true for {label}",
              _eval_condition("item.blocked_reason != blank", Ctx(item)) is True)
    check("C6 `== blank` is correspondingly always false",
          _eval_condition("item.blocked_reason == blank", Ctx({"blocked_reason": ""})) is False)
    pre3 = render(PRE_FIX, {"blocked_reason": None, "notes": "Reserved fallback discovery method."})
    check("C7 so a NULL reason was broken too, not just an empty string",
          body_and_small(pre3)[0] == "", pre3)
    # The repaired form compares a NORMALISED value against a literal. Both reachable states are
    # asserted; the variable is never unassigned in the template because `default: ''` guarantees a
    # string, which is precisely why normalising first is what makes the comparison decidable.
    empty_ctx = Ctx({})
    empty_ctx.vars["mh_reason"] = ""
    text_ctx = Ctx({})
    text_ctx.vars["mh_reason"] = "http_403_blocked"
    check("C8 a normalised empty value fails `!= ''` (so the note becomes primary)",
          _eval_condition("mh_reason != ''", empty_ctx) is False)
    check("C9 a normalised real value passes `!= ''` (so the reason stays primary)",
          _eval_condition("mh_reason != ''", text_ctx) is True)

    print(NEWLINE + "[1] the shipped cell was located and uses no `blank` comparison")
    check("1a the Notes cell was extracted from the page", bool(cell), "cell not found")
    check("1b no `blank` comparison survives in the Notes logic",
          "blank" not in cell, cell[:200])
    check("1c both fields are normalised with `default` before being compared",
          cell.count("default:") >= 2, cell[:200])
    check("1d whitespace-only values are normalised too",
          cell.count("strip") >= 2, cell[:200])

    print(NEWLINE + "[2] the five governed fixtures")
    expected = {
        "1 real reason + a secondary note":  ("http_403_blocked", "Fetch failures: 1."),
        "2 empty reason + a note":           ("Reserved fallback discovery method.", None),
        "3 null reason + a note":            ("Reserved fallback discovery method.", None),
        "4 empty reason + empty note":       ("", None),
        "5 real reason + empty note":        ("http_403_blocked", None),
        "6 reason key absent + a note":      ("Reserved fallback discovery method.", None),
        "7 both keys absent":                ("", None),
        "8 note identical to the reason":    ("same text", None),
        "9 whitespace-only reason + a note": ("Real note.", None),
    }
    for label, item in FIXTURES:
        got = body_and_small(render(cell, item))
        check(f"2 {label} -> {expected[label]!r}", got == expected[label], f"got {got!r}")

    print(NEWLINE + "[3] the three forbidden outputs, over every fixture")
    for label, item in FIXTURES:
        out = render(cell, item)
        body, small = body_and_small(out)
        check(f"3a {label}: never an empty primary with a meaningful <small>",
              not (body == "" and small not in (None, "")), out)
        check(f"3b {label}: never a stray empty <small></small>",
              "<small></small>" not in out, out)
        check(f"3c {label}: never the same text twice",
              not (small and small == body), out)

    print(NEWLINE + "[4] over every real row in the shipped data file")
    try:
        import yaml
        rows = (yaml.safe_load(DATA_PATH.read_text(encoding="utf-8")) or {}).get("methods") or []
    except Exception as exc:  # pragma: no cover
        rows = []
        print(f"  (data unavailable: {exc})")
    check("4a the data file yields rows to render", bool(rows), f"{len(rows)} rows")
    phantom = stray = dup = 0
    identical_to_pre = repaired = other = 0
    for row in rows:
        item = {k: row.get(k) for k in ("blocked_reason", "notes") if k in row}
        out = render(cell, item)
        body, small = body_and_small(out)
        if body == "" and small not in (None, ""):
            phantom += 1
        if "<small></small>" in out:
            stray += 1
        if small and small == body:
            dup += 1
        pre = render(PRE_FIX, item)
        pbody, psmall = body_and_small(pre)
        if out == pre:
            identical_to_pre += 1
        elif pbody == "" and psmall and body == psmall and "<small>" not in out:
            repaired += 1
        else:
            other += 1
    check(f"4b zero rows render an empty primary with a meaningful note ({len(rows)} rows)",
          phantom == 0, f"{phantom} phantom rows")
    # 4c AND 4d ARE REGRESSION FENCES, NOT DISCRIMINATING CHECKS, and saying so matters. Every one
    # of the 1496 live rows carries a non-empty `notes`, so the PRE-FIX template never produced a
    # stray `<small></small>` or a doubled note on real data either -- both pass against the broken
    # markup. They earn their place by catching a FUTURE data shape (a row with an empty note), and
    # the discriminating versions of the same properties are the fixture checks 3b and 3c, which do
    # fail pre-fix. The counterfactual below states that relationship instead of leaving these two
    # reading as coverage they do not provide.
    pre_stray = sum(1 for _l, item in FIXTURES if "<small></small>" in render(PRE_FIX, item))
    pre_dup = sum(1 for _l, item in FIXTURES
                  if (lambda b, s: bool(s) and s == b)(*body_and_small(render(PRE_FIX, item))))
    check("4c zero rows emit a stray empty <small></small>", stray == 0, f"{stray}")
    check("4d zero rows print the same text twice", dup == 0, f"{dup}")
    check("4c2 (fence, not a discriminator) the live data cannot exercise these: "
          f"pre-fix markup also scores 0/0 on real rows, and fails only on fixtures "
          f"({pre_stray} stray, {pre_dup} doubled)",
          pre_stray > 0 and pre_dup > 0,
          "if the fixtures stop exercising these shapes, 4c/4d become pure decoration")
    check("4e every changed row changed for exactly the intended reason",
          other == 0, f"{other} rows changed some other way")
    check("4f the change is non-vacuous: it repairs real rows",
          repaired > 0, f"repaired={repaired} -- if this is 0 the fix touches nothing")
    print(f"       regression surface: {identical_to_pre} rows byte-identical, "
          f"{repaired} repaired, {other} other")

    print(NEWLINE + "[5] the fix is SCOPED -- no repo-wide blank rewrite")
    # The other `blank` comparisons in this file are latent (no live row reaches the wrong branch)
    # and are deliberately left alone. Assert they are still there, so a future sweeping rewrite is
    # a deliberate decision rather than a side effect of this change.
    others = re.findall(r"\{%\s*if item\.(\w+)\s*!=\s*blank", page)
    check("5a the untouched latent blank guards are still present",
          set(others) >= {"last_run", "last_checked"}, f"found {sorted(set(others))}")
    check("5b the Notes cell is not among them",
          "blocked_reason" not in others, f"found {sorted(set(others))}")

    print(NEWLINE + "=" * 74)
    print(f"Results: {_passed}/{_passed + _failed} passed, {_failed} failed")
    print("=" * 74)
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
