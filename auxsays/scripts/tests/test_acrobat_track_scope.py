#!/usr/bin/env python3
"""Acrobat's parallel release tracks: a newer release is named only on the reader's own track (G93).

THE DEFECT. Adobe services Acrobat Pro and Acrobat Reader on two tracks at once: Continuous
(26.003.22110) and Classic (20.005.30838). Every Acrobat record stores which one in `target_track`, but
neither newer-release selector read it. The patch page's newer-release note
(lib/evidence_overview.update_available, G83) and My Patch Stack's UPDATE AVAILABLE
(installedState in assets/js/auxsays.js) both pointed every Classic page that had a newer target --
62 of them, 31 Pro and 31 Reader -- at a CONTINUOUS release: Acrobat Pro 20.005.30838 was told about
26.003.22110.

WHAT IS PINNED, with one fixture set driving BOTH implementations (the Python port, and the shipped
JavaScript executed in node):

  [L] the product list is the same in both languages, is exactly Acrobat Pro and Acrobat Reader, and
      no listed product is platform-split (that branch would never reach the track rule).
  [F] Classic -> the newest newer Classic release; the newest Classic -> nothing (My Patch Stack:
      NEWER TRACKED VERSION EXISTS, never CURRENT and never a Continuous target); Continuous -> the
      newest Continuous; a track missing on the reader's side -> nothing; a newer release with no track
      is never a target. Pro and Reader both. A same-day release on the other track is still never a
      step. The upgrade path holds only the reader's track and ends at the target.
  [C] control: the same records under a product that is not listed keep the old rule, whatever they
      carry -- no other product's behaviour changes.
  [E] end to end: the SHIPPED my-stack.md, rendered with the liquid gem, carries each record's track in
      rec[13], and the shipped installedState run on that rendered payload keeps a Classic reader on
      Classic.
  [K] this tree: no Acrobat page's newer release (Python, full record list) and no My Patch Stack
      target (JavaScript, same list) is on another track or has no track, and the two agree on every
      Acrobat record. One check each, so corpus growth cannot drift the count.

Needs node, and ruby + the liquid gem for [E] (both run in CI); without them the checks FAIL, never skip.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_acrobat_track_scope.py
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
sys.path.insert(0, str(_AUX / "scripts"))

from lib import evidence_overview as eo  # noqa: E402
from lib import verdict_projection  # noqa: E402

JS = _AUX / "assets" / "js" / "auxsays.js"
PAGE = _AUX / "updates" / "my-stack.md"
PRO, READER = "adobe-acrobat-pro", "adobe-acrobat-reader"

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        _ERRORS.append(label)
        print(f"  FAIL  {label}" + (f"\n        {str(detail)[:600]}" if detail != "" else ""))


# --------------------------------------------------------------------------- fixtures

# (version, release date, track). Dates are distinct except one deliberate same-day pair across the two
# tracks, which is what Adobe's Patch Tuesday releases look like.
BASE = [
    ("20.005.30700", "2024-06-11", "Classic"),
    ("24.002.20857", "2024-07-09", "Continuous"),
    ("20.005.30750", "2024-12-10", "Classic"),
    ("24.005.20320", "2024-12-10", "Continuous"),
    ("25.001.20100", "2025-03-11", "Continuous"),
    ("20.005.30800", "2025-09-09", "Classic"),       # the newest Classic
    ("26.001.21000", "2026-01-13", "Continuous"),
    ("26.003.22110", "2026-11-10", "Continuous"),    # the newest release, Continuous
]
# The same product with two records that carry no track: one in the middle, one the newest of all.
MISSING = BASE + [
    ("24.003.20180", "2025-06-10", None),
    ("26.004.20001", "2026-11-17", None),
]


def record(pid: str, version: str, date: str, track: str | None) -> dict:
    r = {"update_entry": True, "product_id": pid, "update_product": "Adobe Acrobat", "update_version": version,
         "update_published_at": f"{date}T00:00:00Z", "update_status": "current",
         "permalink": f"/updates/adobe/{pid}/{version.replace('.', '-')}/", "update_source_name": "Adobe"}
    if track is not None:
        r["target_track"] = track
    return r


def records(pid: str, rows: list[tuple]) -> list[dict]:
    return [record(pid, v, d, t) for v, d, t in rows]


def payload_tuple(r: dict) -> list:
    """My Patch Stack's 14-slot record tuple, built from a record as updates/my-stack.md builds it."""
    return [eo._ver(r), eo._build(r), eo._date(r), str(r.get("permalink") or ""), 1 if eo._beta(r) else 0,
            "", 0, 0, "", 0, 0, eo._platform(r), "", eo._track(r)]


# --------------------------------------------------------------------------- the two implementations

def py_targets(recs: list[dict]) -> dict[str, str | None]:
    """{version: the Python port's newer-release version, or None} for every record."""
    pay = eo.product_payload(recs)
    out = {}
    for r in pay:
        t = eo.update_available(r, pay, split=False)
        out[eo._ver(r)] = eo._ver(t) if t else None
    return out


def js_run(cases: list[dict]) -> list[dict] | None:
    """The shipped installedState, executed in node, over [{product, entry}] cases."""
    node = shutil.which("node")
    if not node:
        return None
    src = JS.read_text(encoding="utf-8")
    start, end = src.index("const PATH_LIMIT"), src.index("const paintInstalledControls")
    probe = (src[start:end] + "\nconst CASES = " + json.dumps(cases) + ";\n"
             + "console.log(JSON.stringify(CASES.map((c) => {\n"
             + "  const info = installedState(c.entry, c.product);\n"
             + "  return { state: info.state || '', latest: info.latest ? info.latest[0] : null,\n"
             + "           url: info.latest ? info.latest[3] : null, latestScope: info.latestScope || '',\n"
             + "           pathKind: info.pathKind || '',\n"
             + "           path: (info.path || []).map((s) => s.rec[0]) };\n"
             + "})));\n")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "probe.js"
        path.write_text(probe, encoding="utf-8")
        proc = subprocess.run([node, str(path)], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=600)
    if proc.returncode != 0:
        raise AssertionError("node probe failed: " + (proc.stderr or "")[-400:])
    return json.loads(proc.stdout.strip().splitlines()[-1])


def js_product(pid: str, recs: list[dict]) -> dict:
    return {"id": pid, "recs": [payload_tuple(r) for r in eo.product_payload(recs)], "split": False}


def js_states(product: dict) -> dict[str, dict]:
    """{version: installedState's result} for a reader on every record of a payload product."""
    cases = [{"product": product, "entry": {"v": t[0], "b": t[1], "d": t[2], "u": t[3]}} for t in product["recs"]]
    res = js_run(cases)
    if res is None:
        return {}
    return {c["entry"]["v"]: r for c, r in zip(cases, res)}


def js_target(state: dict | None) -> str | None:
    """The UPDATE AVAILABLE target only: every other state names no newer release."""
    if not state or state.get("state") != "UPDATE AVAILABLE":
        return None
    return state.get("latest")


# --------------------------------------------------------------------------- the shipped page (liquid)

_RENDER_RB = """
require 'liquid'
require 'json'
module Shims
  def relative_url(i) = "/" + i.to_s.sub(%r{\\A/}, "")
  def jsonify(i) = JSON.generate(i)
end
Liquid::Template.register_filter(Shims)
payload = JSON.parse(File.read(ARGV[0]))
tpl = Liquid::Template.parse(payload['template'])
print tpl.render!('site' => payload['site'])
"""


def render_payload(pages: list[dict], products: list[dict]) -> list | str:
    """The SHIPPED my-stack.md rendered with the liquid gem; its payload, or an error string. Includes
    are stripped: they produce the verdict, maturity and monitoring words, which this suite does not
    read, and none of them touches rec[13]."""
    ruby = shutil.which("ruby")
    if not ruby:
        return "ruby is not on PATH"
    src = PAGE.read_text(encoding="utf-8").split("---", 2)[-1]
    src = re.sub(r"\{%-?\s*include\s.*?-?%\}", "", src, flags=re.S)
    site = {"data": {"patch_products": products}, "pages": pages}
    with tempfile.TemporaryDirectory() as td:
        script, payload = Path(td) / "render.rb", Path(td) / "p.json"
        script.write_text(_RENDER_RB, encoding="utf-8")
        payload.write_text(json.dumps({"template": src, "site": site}), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300)
    if proc.returncode != 0:
        return "render failed: " + (proc.stderr or "")[-400:]
    m = re.search(r'<script type="application/json" id="patch-stack-data">(.*?)</script>', proc.stdout, re.S)
    if not m:
        return "no payload script in the rendered page"
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        return f"payload is not JSON: {exc}"


# =========================================================================== run

def run() -> int:  # noqa: PLR0915
    print("=" * 96)
    print("Acrobat release tracks: a newer release only on the reader's own track (G93)")
    print("=" * 96)

    # ------------------------------------------------------------------ [L]
    print("\n[L] one product list, in both languages")
    js_src = JS.read_text(encoding="utf-8")
    m = re.search(r"const TRACK_SCOPED_PRODUCTS = new Set\(\[([^\]]*)\]\);", js_src)
    js_list = set(re.findall(r"'([^']+)'", m.group(1))) if m else None
    check("L1 Python and JavaScript list the same track-scoped products, exactly Acrobat Pro and Acrobat Reader",
          js_list == set(eo.TRACK_SCOPED_PRODUCTS) == {PRO, READER}, (js_list, sorted(eo.TRACK_SCOPED_PRODUCTS)))
    split = set(eo.split_products_from(_AUX))
    check("L2 no track-scoped product is platform-split in the catalogue (that branch never reaches the track "
          "rule)", not (split & set(eo.TRACK_SCOPED_PRODUCTS)), sorted(split & set(eo.TRACK_SCOPED_PRODUCTS)))

    # ------------------------------------------------------------------ [F]
    print("\n[F] one fixture set, both implementations")
    node_ok = shutil.which("node") is not None
    check("F0 node is on PATH (the shipped installedState is executed, never just read)", node_ok)
    want_base = {
        "20.005.30700": "20.005.30800", "24.002.20857": "26.003.22110", "20.005.30750": "20.005.30800",
        "24.005.20320": "26.003.22110", "25.001.20100": "26.003.22110", "20.005.30800": None,
        "26.001.21000": "26.003.22110", "26.003.22110": None,
    }
    want_missing = dict(want_base, **{"24.003.20180": None, "26.003.22110": None, "26.004.20001": None})
    for pid, short in ((PRO, "Pro"), (READER, "Reader")):
        base, miss = records(pid, BASE), records(pid, MISSING)
        py_b, py_m = py_targets(base), py_targets(miss)
        st_b = js_states(js_product(pid, base)) if node_ok else {}
        st_m = js_states(js_product(pid, miss)) if node_ok else {}
        js_b = {v: js_target(s) for v, s in st_b.items()}
        js_m = {v: js_target(s) for v, s in st_m.items()}

        def both(versions, want, py, js):
            got = {v: (py.get(v, "absent"), js.get(v, "absent")) for v in versions}
            return all(got[v] == (want[v], want[v]) for v in versions), got

        ok, got = both(("20.005.30700", "20.005.30750"), want_base, py_b, js_b)
        check(f"F1 {short}: a Classic reader is pointed at the newest newer CLASSIC release, never the newer "
              f"Continuous one (Python, JavaScript)", ok, got)
        ok, got = both(("20.005.30800",), want_base, py_b, js_b)
        check(f"F2 {short}: the newest Classic release gets no target, though Continuous releases are newer",
              ok, got)
        s = st_b.get("20.005.30800") or {}
        check(f"F2b {short}: My Patch Stack says NEWER TRACKED VERSION EXISTS for it (never CURRENT, never "
              f"UPDATE AVAILABLE)", s.get("state") == "NEWER TRACKED VERSION EXISTS", s)
        ok, got = both(("24.002.20857", "24.005.20320", "25.001.20100", "26.001.21000"), want_base, py_b, js_b)
        s = st_b.get("25.001.20100") or {}
        check(f"F3 {short}: a Continuous reader is pointed at the newest Continuous release, and a target that "
              f"nothing is dated after keeps the plain 'Latest tracked' label (as before this change)",
              ok and s.get("latestScope") == "", (got, s))
        s = st_b.get("26.003.22110") or {}
        check(f"F3b {short}: the newest Continuous release has no target (My Patch Stack: CURRENT)",
              py_b.get("26.003.22110", "absent") is None and s.get("state") == "CURRENT", (py_b.get("26.003.22110"), s))
        ok, got = both(("24.003.20180",), want_missing, py_m, js_m)
        s = st_m.get("24.003.20180") or {}
        check(f"F4 {short}: a reader whose release stores no track gets no target (fail closed)",
              ok and s.get("state") == "NEWER TRACKED VERSION EXISTS", (got, s))
        ok, got = both(("25.001.20100", "20.005.30700", "26.003.22110"), want_missing, py_m, js_m)
        check(f"F5 {short}: a newer release that stores no track is never a target, even as the newest of all",
              ok, got)
        s = st_b.get("20.005.30700") or {}
        check(f"F6 {short}: the Classic reader's upgrade path holds only Classic releases, ends at the target, "
              f"and the target is labelled as the newest on the reader's own line (a Continuous release is "
              f"dated after it)",
              s.get("pathKind") == "upgrade" and s.get("path") == ["20.005.30750", "20.005.30800"]
              and s.get("latestScope") == "line", s)
        s = st_b.get("20.005.30750") or {}
        s2 = st_b.get("24.005.20320") or {}
        check(f"F7 {short}: a same-day release on the other track is never a step, in either direction",
              js_b.get("20.005.30750") == "20.005.30800" and "24.005.20320" not in (s.get("path") or [])
              and js_b.get("24.005.20320") == "26.003.22110" and "20.005.30750" not in (s2.get("path") or []),
              (s, s2))

    # ------------------------------------------------------------------ [C]
    print("\n[C] control: a product that is not listed keeps the old rule")
    tool = records("tool", BASE)
    py_t = py_targets(tool)
    js_t = {v: js_target(s) for v, s in (js_states(js_product("tool", tool)) if node_ok else {}).items()}
    check("C1 the same records under an unlisted product, track field and all, still name the newest stable "
          "release (Python, JavaScript): no other product's behaviour changes",
          py_t.get("20.005.30700") == js_t.get("20.005.30700") == "26.003.22110"
          and py_t.get("20.005.30800") == js_t.get("20.005.30800") == "26.003.22110",
          (py_t, js_t))
    no_id = js_run([{"product": {"recs": js_product(PRO, records(PRO, BASE))["recs"]},
                     "entry": {"v": "20.005.30700", "b": "", "d": "2024-06-11",
                               "u": "/updates/adobe/adobe-acrobat-pro/20-005-30700/"}}]) if node_ok else None
    check("C2 the JavaScript scopes by the payload's product id: a product entry without one is not scoped",
          bool(no_id) and no_id[0].get("latest") == "26.003.22110", no_id)

    # ------------------------------------------------------------------ [E]
    print("\n[E] end to end: the shipped page's payload, read by the shipped function")
    pages = []
    for r in records(PRO, BASE):
        pages.append(dict(r, url=r["permalink"]))
    products = [{"id": PRO, "product_name": "Acrobat Pro", "product_url": "/updates/adobe/adobe-acrobat-pro/"}]
    rendered = render_payload(pages, products)
    entry = rendered[0] if isinstance(rendered, list) and rendered else {}
    tracks = {rec[0]: rec[13] for rec in entry.get("recs") or [] if isinstance(rec, list) and len(rec) == 14}
    check("E1 the liquid gem renders my-stack.md, and every record carries its stored track in rec[13]",
          tracks == {v: t for v, _d, t in BASE}, rendered if isinstance(rendered, str) else tracks)
    res = js_run([{"product": entry, "entry": {"v": v, "b": "", "d": d, "u": f"/updates/adobe/{PRO}/{v.replace('.', '-')}/"}}
                  for v, d in (("20.005.30700", "2024-06-11"), ("20.005.30800", "2025-09-09"))]) \
        if node_ok and entry else None
    check("E2 on the rendered payload, a Classic reader is pointed at the newest Classic release and the newest "
          "Classic release at none",
          bool(res) and res[0].get("state") == "UPDATE AVAILABLE" and res[0].get("latest") == "20.005.30800"
          and res[1].get("state") == "NEWER TRACKED VERSION EXISTS", res)

    # ------------------------------------------------------------------ [K]
    print("\n[K] this tree")
    real_records, _groups = verdict_projection.load_inputs(_AUX)
    by_pid: dict[str, list[dict]] = {}
    for r in real_records:
        by_pid.setdefault(eo._text(r.get("product_id")), []).append(r)
    py_bad, py_pairs, classic = [], {}, {"with": 0, "without": 0}
    for pid in sorted(eo.TRACK_SCOPED_PRODUCTS):
        pay = eo.product_payload(by_pid.get(pid, []))
        for r in pay:
            t = eo.update_available(r, pay, split=False)
            py_pairs[str(r.get("permalink") or "")] = str(t.get("permalink")) if t else None
            if t is not None and not (eo._track(r) and eo._track(t) == eo._track(r)):
                py_bad.append(f"{pid} {eo._ver(r)} ({eo._track(r) or 'no track'}) -> {eo._ver(t)} "
                              f"({eo._track(t) or 'no track'})")
            if eo._track(r) == "Classic":
                classic["with" if t is not None else "without"] += 1
    print(f"        Classic records in this tree: {classic['with']} with a Classic target, "
          f"{classic['without']} with none")
    check(f"K1 no Acrobat page's newer release is on another track or has no track ({len(py_pairs)} records)",
          not py_bad and len(py_pairs) > 0, py_bad[:5])
    js_bad, diff = [], []
    if node_ok:
        for pid in sorted(eo.TRACK_SCOPED_PRODUCTS):
            pay = eo.product_payload(by_pid.get(pid, []))
            product = {"id": pid, "recs": [payload_tuple(r) for r in pay], "split": False}
            track_of = {str(r.get("permalink") or ""): eo._track(r) for r in pay}
            cases = [{"product": product, "entry": {"v": t[0], "b": t[1], "d": t[2], "u": t[3]}} for t in product["recs"]]
            for c, s in zip(cases, js_run(cases) or []):
                url = c["entry"]["u"]
                got = s.get("url") if s.get("state") == "UPDATE AVAILABLE" else None
                if got is not None and not (track_of.get(url) and track_of.get(got) == track_of.get(url)):
                    js_bad.append(f"{url} -> {got}")
                if got != py_pairs.get(url, "absent"):
                    diff.append(f"{url}: python {py_pairs.get(url, 'absent')} js {got}")
    check("K2 no My Patch Stack target for an Acrobat record is on another track or has no track, and the "
          "shipped JavaScript gives the Python port's answer for every Acrobat record",
          node_ok and not js_bad and not diff, (js_bad[:3], diff[:3]))

    print()
    print("=" * 96)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 96)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
