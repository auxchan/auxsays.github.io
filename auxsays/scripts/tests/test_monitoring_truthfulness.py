#!/usr/bin/env python3
"""A monitoring claim must describe what collection actually did.

WHAT WAS WRONG. `coverage_status_label` is a static editorial string in
`_data/patch_companies.yml` and `_data/patch_products.yml`. Three render sites published it as a
monitoring claim: the product page pill, the product card on a company page, and the
company-level pill. It tracks nothing.

Measured before the fix, across 47 products and 35 companies:
  * 29 products publicly claimed "Monitoring active" with NO enabled ingestion source;
  * 27 companies claimed it with ZERO healthy products, `netlify` among them while its only
    product's recorded state was `broken`;
  * two products claimed "Source map staged" while enabled, healthy and producing records that
    same day -- so the field was not even conservative, it was decoupled;
  * four ENABLED products sat at 226, 226, 146 and 102 consecutive failures with last successes
    between 2026-08-18 and 2026-09-21, and said nothing about it.

WHY FAIL-CLOSED IS THE PROPERTY UNDER TEST. Two earlier attempts at this repair each produced a
DIFFERENT false claim: one derived the state from `coverage_state` (an editorial enum) and one
from the source's `enabled` flag. Neither tracks whether collection WORKS -- `enabled` only says
a source is switched on, and five enabled sources have produced nothing. So `healthy` is the only
affirmative state, it is checked last, and it must be earned: enabled, recorded healthy, AND a
success recent enough for the source's own cadence. Everything else resolves to a non-affirmative
state, and anything unestablished resolves to `unverified`.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_monitoring_truthfulness.py
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
_SCRIPTS = _AUX / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import build_monitoring_projection as proj  # noqa: E402

# Where the DEPLOY writes the projection. Never committed (see section G), so a clean checkout --
# CI included -- does not have these files. Nothing here may depend on their presence.
REPO_PRODUCT_PROJECTION = _AUX / "_data" / "monitoring_state.yml"
REPO_COMPANY_PROJECTION = _AUX / "_data" / "monitoring_company_state.yml"

_GENERATED: dict = {}


def repo_snapshot() -> dict:
    """(mtime, size) of the repository's own projection paths, or None where absent.

    mtime, not a content hash: a generator that rewrites the repo copy with identical bytes still
    wrote into the repository, and a hash cannot see that.
    """
    out = {}
    for p in (REPO_PRODUCT_PROJECTION, REPO_COMPANY_PROJECTION):
        st = p.stat() if p.exists() else None
        out[p] = (st.st_mtime_ns, st.st_size) if st else None
    return out


def generated() -> tuple:
    """Generate both projections ONCE into a private temp dir -> (product_path, company_path).

    The suite validates freshly generated output, exactly what the deploy publishes, instead of a
    committed copy that was stale whenever a scheduled lane moved the ingest state.
    """
    if not _GENERATED:
        # Taken before the FIRST generator run in this process, so G4 can see a write into the
        # repository made by any run, including this one.
        _GENERATED["repo_before"] = repo_snapshot()
        td = tempfile.mkdtemp(prefix="monitoring-projection-")
        with io.StringIO() as sink:
            saved, sys.stdout = sys.stdout, sink
            try:
                rc = proj.main(["--output-dir", td])
            except Exception as exc:  # noqa: BLE001 -- G4 must FAIL by name, not crash the suite
                rc = f"raised {exc!r}"
            finally:
                sys.stdout = saved
        _GENERATED.update(rc=rc, dir=Path(td))
    d = _GENERATED["dir"]
    return d / REPO_PRODUCT_PROJECTION.name, d / REPO_COMPANY_PROJECTION.name
TEMPLATES = (_AUX / "_layouts" / "aux-patch-product.html",
             _AUX / "_layouts" / "aux-patch-company.html")

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)

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


def src(enabled=True, cadence="12h", **extra) -> dict:
    s = {"enabled": enabled, "ingestion": {"polling_frequency": cadence}}
    s["ingestion"].update(extra)
    return s


def state(status="healthy", success_hours_ago=1, error_type=None) -> dict:
    st = {"status": status}
    if success_hours_ago is not None:
        st["last_success_at"] = (NOW - timedelta(hours=success_hours_ago)).isoformat()
    if error_type:
        st["last_error_type"] = error_type
    return st


def section_a_fail_closed() -> None:
    print("\n[A] healthy is EARNED; everything unestablished is not affirmative")
    d = lambda s, st: proj.derive_state(s, st, now=NOW)

    check("A1 no ingestion source at all -> unconfigured", d(None, None) == "unconfigured")
    check("A2 a source switched off -> disabled", d(src(enabled=False), state()) == "disabled")
    check("A3 enabled with NO recorded run -> unverified", d(src(), None) == "unverified",
          "this is the case `enabled` alone would have called active")
    check("A4 enabled with an EMPTY state -> unverified", d(src(), {}) == "unverified")
    check("A5 a status this code does not recognise -> unverified",
          d(src(), {"status": "something_new", "last_success_at": NOW.isoformat()}) == "unverified",
          "an unrecognised status must never render as working")
    check("A6 recorded healthy but NO success timestamp -> unverified",
          d(src(), {"status": "healthy"}) == "unverified")
    check("A7 recorded healthy with a RECENT success -> healthy",
          d(src(), state(success_hours_ago=2)) == "healthy")
    check("A8 recorded healthy with a STALE success -> stale, not healthy",
          d(src(cadence="12h"), state(success_hours_ago=200)) == "stale",
          "enabled + healthy status is not enough; the success has to be recent")
    check("A9 a manual source is not active monitoring",
          d(src(cadence="manual"), state(success_hours_ago=1)) == "disabled")


def section_b_distinct_failures() -> None:
    print("\n[B] refused, unanswered and unreadable are DIFFERENT facts")
    d = lambda s, st: proj.derive_state(s, st, now=NOW)
    check("B1 a refusal is blocked",
          d(src(), state("failing", 500, "blocked")) == "blocked")
    check("B2 no answer is unreachable, not blocked",
          d(src(), state("failing", 500, "timeout")) == "unreachable",
          "a timeout is not a refusal; collapsing them tells the reader something untrue")
    check("B3 an unreadable response is broken, not blocked or stale",
          d(src(), state("broken", 1)) == "broken",
          "a source we reached but could not parse is a third, separate condition")
    check("B4 failing for an unrecognised reason -> unverified",
          d(src(), state("failing", 500, "something_else")) == "unverified")
    # The ingest state records a bot challenge as its own error type. Left unmapped, four sources
    # being refused by a challenge page read "status unknown" instead of saying so.
    check("B6 a bot challenge is a refusal -> blocked",
          d(src(), state("failing", 500, "challenged")) == "blocked",
          "a challenge page is the source refusing automated checks")
    states = {d(src(), state("failing", 500, "blocked")),
              d(src(), state("failing", 500, "timeout")),
              d(src(), state("broken", 1))}
    check("B5 those three do not collapse into one label", len(states) == 3, f"got {states}")


def section_c_cadence_recency() -> None:
    print("\n[C] the recency window follows the source's own cadence")
    w = proj.recency_window
    six = w(timedelta(hours=6))
    check("C1 the fastest lane gets the 48-hour floor, not 24",
          six == timedelta(hours=48), f"got {six}")
    check("C2 a slower cadence gets a proportionally wider window",
          w(timedelta(hours=24)) == timedelta(hours=96), f"got {w(timedelta(hours=24))}")
    check("C3 the window is capped so nothing is 'healthy' indefinitely",
          w(timedelta(days=30)) == proj.RECENCY_CEILING)
    check("C4 no schedule means recency cannot be judged", w(None) is None)
    check("C5 a per-source override is honoured",
          w(timedelta(hours=6), override_hours=10) == timedelta(hours=10))
    check("C6 an UNPARSEABLE override falls back rather than widening the window",
          w(timedelta(hours=6), override_hours="soon") == timedelta(hours=48),
          "a typo must not silently make a stale source look healthy")
    # An override may TIGHTEN, never widen. Each of these used to be honoured verbatim.
    check("C7 an override LARGER than the window does not widen it",
          w(timedelta(hours=6), override_hours=500) == timedelta(hours=48),
          f"got {w(timedelta(hours=6), override_hours=500)}")
    check("C8 an enormous override neither widens nor overflows",
          w(timedelta(hours=6), override_hours=1e9) == timedelta(hours=48))
    check("C9 an infinite override is ignored instead of raising",
          w(timedelta(hours=6), override_hours=float("inf")) == timedelta(hours=48))
    check("C10 a zero or negative override cannot call every source stale",
          w(timedelta(hours=6), override_hours=0) == timedelta(hours=48)
          and w(timedelta(hours=6), override_hours=-5) == timedelta(hours=48))
    check("C11 nan is ignored", w(timedelta(hours=6), override_hours=float("nan")) == timedelta(hours=48))
    check("C12 an override does not invent a schedule for a manual source",
          w(None, override_hours=10) is None)

    d = lambda s, st: proj.derive_state(s, st, now=NOW)
    future = {"status": "healthy", "last_success_at": (NOW + timedelta(days=3)).isoformat()}
    check("C13 a success dated in the FUTURE is not a recent success",
          d(src(), future) == "unverified", d(src(), future))

    labels = proj.STATE_LABELS
    check("C14 every reader-facing label names the official activity it describes",
          all("official" in v.lower() for v in labels.values()), str(labels))
    check("C15 no label is the bare phrase that let readers confuse the two monitors",
          "Monitoring active" not in labels.values())
    # The label TABLE is not the only source: company_state builds its own aggregate wording, and a
    # first version of this fix reworded the table while six companies kept publishing "Monitoring
    # active". Assert against every state each builder can produce, not against the table.
    company_labels = {proj.company_state(states)[1] for states in (
        ["healthy"], ["healthy", "disabled"], ["blocked"], ["disabled"], ["stale"], [], ["weird"])}
    check("C16 every COMPANY label also names the official activity",
          all("official" in lab.lower() for lab in company_labels), str(sorted(company_labels)))


def section_d_vocabulary_is_closed() -> None:
    print("\n[D] the published vocabulary is closed, and the live projection obeys it")
    import yaml
    product_path, company_path = generated()
    try:
        rows = yaml.safe_load(product_path.read_text(encoding="utf-8")) or []
        crows = yaml.safe_load(company_path.read_text(encoding="utf-8")) or []
    except Exception as exc:  # noqa: BLE001 -- a failed generation FAILS D1 by name, never crashes
        rows, crows = [], []
        print(f"        generation failed: rc={_GENERATED.get('rc')} {exc!r}"[:200])
    check("D1 the product projection is non-empty", len(rows) >= 40, f"{len(rows)} rows")
    outside = sorted({r["state"] for r in rows} - set(proj.PUBLIC_STATES))
    check("D2 every product state is an approved member", not outside, f"outside: {outside}")
    coutside = sorted({r["state"] for r in crows} - set(proj.COMPANY_STATES))
    check("D3 every company state is an approved member", not coutside, f"outside: {coutside}")
    labels_ok = all(r.get("label") for r in rows + crows)
    check("D4 every row carries reader-facing text", labels_ok)
    # The projection must carry NOTHING operational. The richer source_health.yml holds 24 fields
    # including last_error, adapter_type and consecutive_failures; none of that belongs here.
    allowed_product = {"product_id", "state", "label", "last_success", "last_checked"}
    extra = sorted({k for r in rows for k in r} - allowed_product)
    check("D5 the product projection carries no operational field", not extra, f"extra: {extra}")
    allowed_company = {"company_id", "state", "label", "monitored", "total"}
    cextra = sorted({k for r in crows for k in r} - allowed_company)
    check("D6 the company projection carries no operational field", not cextra, f"extra: {cextra}")


def section_e_company_aggregate() -> None:
    print("\n[E] a company summarises its products honestly")
    cs = proj.company_state
    check("E1 all products healthy -> active", cs(["healthy", "healthy"])[0] == "healthy")
    check("E2 some healthy -> a COUNT, not an adjective",
          cs(["healthy", "disabled", "disabled"]) == ("partial", "Official updates monitored for 1 of 3 products"),
          "27 companies claimed 'Monitoring active' with zero healthy products")
    check("E3 none healthy but something failing -> says checks are failing",
          cs(["blocked", "blocked"])[0] == "failing")
    check("E4 none healthy and nothing configured -> not monitored",
          cs(["disabled", "disabled"])[0] == "disabled")
    check("E5 a company with no products -> unconfigured", cs([])[0] == "unconfigured")
    check("E6 'not monitored' and 'checks failing' are different labels",
          cs(["disabled"])[1] != cs(["broken"])[1])
    check("E7 one broken product does not read as monitored",
          cs(["broken"])[0] == "failing",
          "netlify claimed active while its only product was broken")


def section_f_raw_state_not_in_templates() -> None:
    print("\n[F] no template reads the raw ingest state")
    # INTERIM CONTAINMENT. patch_ingest_state.json sits in _data, so Jekyll loads it into
    # site.data for every template whether or not one references it, and it carries raw error
    # bodies, adapter names and failure counters. Relocating it is 27 files across all four
    # committing workflows and is tracked separately; until then, nothing may read it.
    offenders = []
    for path in list((_AUX / "_layouts").glob("*.html")) + \
                list((_AUX / "_includes").glob("*.html")) + \
                list((_AUX / "updates").glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        stripped = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "",
                          text, flags=re.S)
        if "patch_ingest_state" in stripped:
            offenders.append(path.name)
    check("F1 no layout, include or page reads site.data.patch_ingest_state", not offenders,
          f"offenders: {offenders}")
    for path in TEMPLATES:
        text = path.read_text(encoding="utf-8", errors="replace")
        stripped = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "",
                          text, flags=re.S)
        rendered_label = [ln for ln in stripped.splitlines()
                          if "coverage_status_label" in ln and "{{" in ln]
        check(f"F2 {path.name} no longer renders the editorial label as a claim",
              not rendered_label, f"{rendered_label[:1]}")
        check(f"F3 {path.name} uses '' rather than the inert `blank`",
              not re.search(r"[!=]=\s*blank", stripped))


_RENDER_RB = r"""
require 'liquid'
require 'json'

# The two Jekyll filters these layouts use that plain Liquid 4 lacks. `where` keeps Jekyll's
# semantics: a nil or non-enumerable input comes back unchanged, which is exactly the
# "projection absent" case the fallback has to survive.
module JekyllShims
  def relative_url(i) = "/" + i.to_s.sub(%r{\A/}, "")
  def where(input, property, value)
    input = input.values if input.is_a?(Hash)
    return input unless input.respond_to?(:select)
    input.select { |item| item.is_a?(Hash) && item[property].to_s == value.to_s }
  end
end
Liquid::Template.register_filter(JekyllShims)

payload = JSON.parse(File.read(ARGV[0]))
print Liquid::Template.parse(payload['layout']).render!('site' => payload['site'], 'page' => payload['page'])
"""


def _layout_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[-1]
    # Includes need a file system; none of them renders the monitoring pill.
    return re.sub(r"\{%-?\s*include\s.*?-?%\}", "", text, flags=re.S)


def render_layout(path: Path, site_data: dict, page: dict):
    """Render a REAL layout through the liquid gem -> html, or None when ruby/liquid is absent."""
    import shutil
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "render.rb"
        script.write_text(_RENDER_RB, encoding="utf-8")
        payload = Path(td) / "p.json"
        payload.write_text(json.dumps({"layout": _layout_body(path), "page": page,
                                       "site": {"data": site_data, "pages": []}}, default=str),
                           encoding="utf-8")
        out = subprocess.run([ruby, str(script), str(payload)], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=180)
    if out.returncode != 0:
        if "cannot load such file -- liquid" in (out.stderr or ""):
            return None
        raise RuntimeError(out.stderr[-400:])
    return out.stdout


def pills(html: str) -> list:
    """-> [(state, label)] for every monitoring pill in rendered html."""
    return re.findall(r'patch-coverage-pill--monitor-([a-z]+)">([^<]*)</span>', html)


def _steps_by_job(workflow: dict):
    for name, job in (workflow.get("jobs") or {}).items():
        yield name, job.get("steps") or []


def _run_lines(step: dict) -> list:
    """The executable lines of a step's run: scalar, shell comments stripped."""
    run = step.get("run") or ""
    return [ln.strip() for ln in run.splitlines() if ln.strip() and not ln.strip().startswith("#")]


def section_g_generated_never_committed() -> None:
    print("\n[G] the projection is generated at deploy, never committed, and fails closed when absent")
    import yaml
    # WHY THIS REPLACED "the committed projection is current". The projection is a function of NOW
    # and of patch_ingest_state.json, which every scheduled lane rewrites, so a committed copy went
    # stale between a push and its own CI run and turned CI red with nothing wrong. The deploy
    # regenerates it before building; the repository simply must not carry a copy.
    tracked = subprocess.run(["git", "ls-files", "--", str(REPO_PRODUCT_PROJECTION),
                              str(REPO_COMPANY_PROJECTION)], capture_output=True, text=True,
                             cwd=_REPO)
    check("G1 neither projection is tracked by git",
          tracked.returncode == 0 and tracked.stdout.strip() == "",
          f"rc={tracked.returncode} tracked={tracked.stdout.strip()!r} {tracked.stderr.strip()[:120]}")
    ignored = [subprocess.run(["git", "check-ignore", "-q", "--no-index", str(p)], cwd=_REPO)
               .returncode == 0 for p in (REPO_PRODUCT_PROJECTION, REPO_COMPANY_PROJECTION)]
    check("G2 both projections are git-ignored, so a local run cannot re-commit them",
          all(ignored), f"ignored={ignored}")

    # Parsed, not grepped: a grep for the script name passes with the step commented out or moved
    # after the build. The executable run lines decide.
    wf = yaml.safe_load((_REPO / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8"))
    order_ok, where = False, "no job carries all three steps"
    for job, steps in _steps_by_job(wf):
        idx = {"checkout": None, "generate": None, "build": None}
        for i, st in enumerate(steps):
            uses = str(st.get("uses") or "")
            lines = _run_lines(st)
            if idx["checkout"] is None and uses.startswith("actions/checkout"):
                idx["checkout"] = i
            if idx["generate"] is None and any("build_monitoring_projection.py" in ln for ln in lines):
                idx["generate"] = i
            if idx["build"] is None and any("jekyll build" in ln for ln in lines):
                idx["build"] = i
        if all(v is not None for v in idx.values()):
            order_ok = idx["checkout"] < idx["generate"] < idx["build"]
            where = f"job {job}: {idx}"
            break
    check("G3 pages.yml generates the projection after checkout and BEFORE jekyll build",
          order_ok, where)

    # The CLI writes both files where it is told, exits 0, and leaves the repository alone. The
    # baseline is the snapshot taken before the FIRST generator run in this process (section D's,
    # via generated()); G4 then makes its own fresh run. A snapshot taken here, after D, would
    # bracket nothing D did, and was measured to pass a generator that also wrote the repo copy.
    generated()
    before = _GENERATED["repo_before"]
    with tempfile.TemporaryDirectory() as g4_dir, io.StringIO() as sink:
        saved, sys.stdout = sys.stdout, sink
        try:
            g4_rc = proj.main(["--output-dir", g4_dir])
        except Exception as exc:  # noqa: BLE001 -- fail G4 by name, never crash the suite
            g4_rc = f"raised {exc!r}"
        finally:
            sys.stdout = saved
        written = all((Path(g4_dir) / p.name).is_file() and (Path(g4_dir) / p.name).stat().st_size > 0
                      for p in (REPO_PRODUCT_PROJECTION, REPO_COMPANY_PROJECTION))
    after = repo_snapshot()
    check("G4 --output-dir writes both projections outside the repository and exits 0",
          g4_rc == 0 and written and before == after,
          f"rc={g4_rc} written={written} repo files touched={before != after}")

    # Determinism on the real inputs, and that the injected clock is honoured -- the second half on
    # a SYNTHETIC ingest state, so it depends on no real date and cannot age into a failure. One
    # enabled, scheduled source recorded healthy an hour before the clock: healthy at that clock,
    # stale 400 days later. A generator reading the wall clock fails the first.
    fixed = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    a_rows, b_rows = proj.build_rows(now=fixed), proj.build_rows(now=fixed)
    deterministic = (proj.render(a_rows) == proj.render(b_rows)
                     and proj.render_companies(proj.build_company_rows(a_rows))
                     == proj.render_companies(proj.build_company_rows(b_rows)))
    pid = next((s["product_id"] for s in proj.load_yaml(proj.SOURCES_PATH) or []
                if isinstance(s, dict) and s.get("product_id") and s.get("enabled")
                and proj.parse_cadence((s.get("ingestion") or {}).get("polling_frequency"))), None)
    at_fixed = at_later = None
    if pid:
        with tempfile.TemporaryDirectory() as sd:
            synthetic = Path(sd) / "patch_ingest_state.json"
            synthetic.write_text(json.dumps({"sources": {pid: {
                "status": "healthy",
                "last_success_at": (fixed - timedelta(hours=1)).isoformat()}}}), encoding="utf-8")
            real_state, proj.STATE_PATH = proj.STATE_PATH, synthetic
            try:
                at_fixed = {r["product_id"]: r["state"] for r in proj.build_rows(now=fixed)}.get(pid)
                at_later = {r["product_id"]: r["state"]
                            for r in proj.build_rows(now=fixed + timedelta(days=400))}.get(pid)
            finally:
                proj.STATE_PATH = real_state
    check("G5 at a fixed clock the projection is byte-identical, and the clock is honoured",
          deterministic and at_fixed == "healthy" and at_later == "stale",
          f"deterministic={deterministic} {pid}: at clock={at_fixed} 400 days later={at_later}")

    # REAL RENDERS of both layouts, with the projection absent and present. Checking the assign
    # statements would pass a template that kept them and rendered the wrong value elsewhere.
    data = {name: yaml.safe_load((_AUX / "_data" / f"{name}.yml").read_text(encoding="utf-8"))
            for name in ("patch_companies", "patch_products")}
    product_path, company_path = generated()
    try:
        rows = yaml.safe_load(product_path.read_text(encoding="utf-8")) or []
        crows = yaml.safe_load(company_path.read_text(encoding="utf-8")) or []
    except Exception as exc:  # noqa: BLE001 -- a failed generation FAILS G6-G9 by name
        for n in ("G6", "G7", "G8", "G9"):
            check(f"{n} the generated projection could not be read", False,
                  f"rc={_GENERATED.get('rc')} {exc!r}"[:200])
        return
    products = {p.get("id"): p for p in data["patch_products"] or []}
    # A product whose derived state is NOT the fallback, so "present" is distinguishable from
    # "absent". Prefer an affirmative one: that is the claim the fallback must never fabricate.
    pick = next((r for r in rows if r["state"] == "healthy" and r["product_id"] in products), None) \
        or next((r for r in rows if r["state"] != "unverified" and r["product_id"] in products), None)
    unknown = proj.STATE_LABELS["unverified"]
    affirmative = proj.STATE_LABELS["healthy"]
    if pick is None:
        for n in ("G6", "G7", "G8", "G9"):
            check(f"{n} SKIPPED - no non-fallback product to render", False,
                  "the generated projection has no product to distinguish present from absent")
        return
    company_id = products[pick["product_id"]].get("company_id")
    crow = next((c for c in crows if c["company_id"] == company_id), None)
    page = {"company_id": company_id, "product_id": pick["product_id"]}
    product_layout = _AUX / "_layouts" / "aux-patch-product.html"
    company_layout = _AUX / "_layouts" / "aux-patch-company.html"

    absent = render_layout(product_layout, data, page)
    if absent is None:
        for n in ("G6", "G7", "G8", "G9"):
            check(f"{n} SKIPPED - ruby/liquid unavailable", True)
        return
    got = pills(absent)
    check("G6 with NO projection the product page reads unknown, never monitored",
          bool(got) and all(s == "unverified" and lbl == unknown for s, lbl in got)
          and affirmative not in absent, f"pills={got}")
    present = render_layout(product_layout, dict(data, monitoring_state=rows), page)
    got = pills(present)
    check("G7 with the generated projection the product page shows its derived state",
          (pick["state"], pick["label"]) in got, f"want {(pick['state'], pick['label'])}, pills={got}")

    absent_c = render_layout(company_layout, data, {"company_id": company_id})
    got = pills(absent_c)
    check("G8 with NO projection the company pill and every product card read unknown",
          bool(got) and all(s == "unverified" and lbl == unknown for s, lbl in got)
          and affirmative not in absent_c, f"pills={got}")
    present_c = render_layout(company_layout, dict(data, monitoring_state=rows,
                                                   monitoring_company_state=crows),
                              {"company_id": company_id})
    got = pills(present_c)
    # The company pill renders BEFORE every product card, so it is got[0]. Matching anywhere on
    # the page would let a product card with the same state stand in for a broken company pill.
    check("G9 with the generated projection the company page shows its derived states",
          crow is not None and bool(got) and got[0] == (crow["state"], crow["label"])
          and (pick["state"], pick["label"]) in got[1:],
          f"want company {crow and (crow['state'], crow['label'])} + product, pills={got}")


def run() -> int:
    section_a_fail_closed()
    section_b_distinct_failures()
    section_c_cadence_recency()
    section_d_vocabulary_is_closed()
    section_e_company_aggregate()
    section_f_raw_state_not_in_templates()
    section_g_generated_never_committed()
    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2) from None
