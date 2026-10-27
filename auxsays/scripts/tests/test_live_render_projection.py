#!/usr/bin/env python3
"""A stored live-consensus claim renders as live only while it certifies at deploy time (AUX-055).

WHY IT EXISTS. Five Liquid copies -- the patch page, two feed lists, the homepage and My Patch
Stack -- each turned a record's stored maturity words into "Live consensus" for themselves. The
stored words are a writer's statement from when it last ran; the page is rendered later, and the
collection behind a claim can stop in between without the words changing. So a live claim is now
re-judged when the site is built, and every surface renders through one contract.

WHAT IS PINNED HERE.
  [E] `live_eligibility.evaluate`: each condition (promotion product, High rung, exclusive URLs,
      monitoring health) refuses on its own; a synthetic identity passing all four certifies;
      exclusivity is over normalized URLs and over every other identity, another product's included.
  [M] `maturity.certify_live` is still NOT enabled: this change decides what RENDERS, never what
      a writer STORES.
  [P] `build_live_eligibility_projection.py`, run as the bare script pages.yml runs, on a temp tree:
      a healthy claim is listed, a stale one is not, a non-claim never is, a missing or malformed
      store writes an empty projection and exits 0, and no generated record is touched. pages.yml
      runs it before the Jekyll build on a daily schedule; the output is git-ignored.
  [R] `_includes/maturity-state.html` through the liquid gem with a Jekyll-style include tag: a
      certified claim reads "Live consensus" / "Established reports"; the same claim uncertified,
      or with the projection absent, reads "Verified reports" / "Early reports"; every non-live
      state maps as before; the include emits nothing.
  [W] every consumer takes its maturity words from the contract and keeps no private live ladder;
      the patch page's own derivation renders certified and uncertified claims correctly.

Needs ruby + the liquid gem for [R] and [W]; without them those checks FAIL rather than skip.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_live_render_projection.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
_SCRIPTS = _AUX / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import yaml  # noqa: E402

from lib import collector_ownership as ownership  # noqa: E402
from lib import live_eligibility as le  # noqa: E402
from lib import maturity  # noqa: E402
from lib import monitoring_health as mh  # noqa: E402
from lib import report_counts as rc  # noqa: E402
from patch_collectors.base import write_front_matter_and_body  # noqa: E402

SCRIPT = _SCRIPTS / "build_live_eligibility_projection.py"
INCLUDES = _AUX / "_includes"
REPO_PROJECTION = _AUX / "_data" / "live_eligibility.yml"
COMMENT_RE = re.compile(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", re.S)

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


# ------------------------------------------------------------------------------- synthetic world
NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
NOW_ISO = "2026-10-27T12:00:00Z"
RELEASED = "2026-10-01T00:00:00Z"
FRESH = "2026-10-27T06:00:00Z"
STALE = "2026-10-05T00:00:00Z"          # after the release, 22 days before NOW: past the 14-day limit
T = mh.Thresholds(max_age_days=14, min_healthy_families=2)
HIGH = maturity.LIVE_MIN_ACCEPTED_REPORTS


def methods(product: str) -> list[str]:
    return sorted(ownership.ALLOWED_METHODS[product] - ownership.MANUAL_ONLY_METHODS)


def family(method: str) -> str:
    return f"fam-{method}"


def record(product: str = "obs-studio", version: str = "99.0.0", *, live: bool = True) -> dict:
    tuple_ = maturity.CONSENSUS_LIVE if live else maturity.PILOT_SAMPLE
    return {"layout": "aux-update", "update_entry": True, "product_id": product,
            "update_version": version, "target_build": "", "update_published_at": RELEASED,
            "permalink": f"/updates/test/{product}/{version.replace('.', '-')}/",
            "update_report_count": HIGH, "confirmed_patch_specific_report_count": HIGH,
            **tuple_.axes()}


def health(product: str, version: str, *, status: str = "success", last_run: str = FRESH,
           overrides: dict | None = None) -> list[dict]:
    """One method-health row per owned method -- H7 refuses a patch missing any of them."""
    rows = []
    for method in methods(product):
        rows.append({"product_id": product, "update_version": version, "target_build": "",
                     "method_id": method, "source_type": family(method),
                     "status": (overrides or {}).get(method, status), "last_run": last_run})
    return rows


def reports(product: str, version: str, n: int, *, start: int = 0, via: str | None = None) -> list[dict]:
    """`n` counted rows with distinct URLs, attributed to the family of `via` (default: the first
    owned method)."""
    method = via or methods(product)[0]
    return [{"product_id": product, "update_version": version, "target_build": "",
             "id": f"{product}-{version}-{i}", "source_url": f"https://forum.test/{product}/t/{i}",
             "source_type": family(method), "counted": True, "patch_version_matched": True}
            for i in range(start, start + n)]


def groups(*row_lists: list[dict]) -> dict:
    """The population exactly as the authority groups it."""
    return rc.counted_evidence_rows([row for rows in row_lists for row in rows], windows_targets={})


def decide(rec: dict, population: dict, emh: list[dict], **kw) -> maturity.LiveDecision:
    return le.evaluate(rec, population, emh_rows=emh, now=NOW, thresholds=T, **kw)


# ------------------------------------------------------------------------------- [E] evaluate
def section_e() -> None:
    print("\n[E] live_eligibility.evaluate: every condition refuses on its own")
    rec = record()
    own = reports("obs-studio", "99.0.0", HIGH)
    emh = health("obs-studio", "99.0.0")
    base = decide(rec, groups(own), emh)
    check("E0 a promotion product with 33 exclusive reports and healthy monitoring certifies",
          base.live and base.reasons == (), str(base.reasons))

    dv = record("blackmagic-davinci", "99.0")
    dv_dec = decide(dv, groups(reports("blackmagic-davinci", "99.0", HIGH)),
                    health("blackmagic-davinci", "99.0"))
    check("E1 (a) a product outside CONSENSUS_PROMOTION_PRODUCTS refuses, and for nothing else",
          not dv_dec.live and dv_dec.reasons == ("not_promotion_product",), str(dv_dec.reasons))
    check("E1b ...and that product really is outside the set while OBS is inside it",
          "blackmagic-davinci" not in rc.CONSENSUS_PROMOTION_PRODUCTS
          and "obs-studio" in rc.CONSENSUS_PROMOTION_PRODUCTS)

    thin = decide(rec, groups(reports("obs-studio", "99.0.0", HIGH - 1)), emh)
    # Exclusive URLs are a subset of the identity's reports, so below the rung (b) always brings
    # (c) with it; nothing else may fire.
    check("E2 (b) 32 counted reports refuse on the High rung, with only the implied exclusivity reason",
          not thin.live and thin.reasons == (f"below_high_rung:{HIGH - 1}",
                                             f"exclusive_below_high_rung:{HIGH - 1}"),
          str(thin.reasons))

    shared = reports("obs-studio", "98.0.0", 1, start=0)       # the same URL as 99.0.0's report 0
    excl = decide(rec, groups(own, shared), emh)
    check("E3 (c) one report URL also counted on another version refuses on exclusivity alone",
          not excl.live and excl.reasons == (f"exclusive_below_high_rung:{HIGH - 1}",),
          str(excl.reasons))
    variant = [dict(shared[0], source_url="  HTTPS://FORUM.TEST/obs-studio/t/0/  ")]
    norm = decide(rec, groups(own, variant), emh)
    check("E4 (c) the comparison is over normalize_url: case and a trailing slash do not make it new",
          norm.reasons == (f"exclusive_below_high_rung:{HIGH - 1}",), str(norm.reasons))
    other_product = [dict(shared[0], product_id="adobe-acrobat-pro", update_version="26.001.1",
                          id="acrobat-0")]
    cross = decide(rec, groups(own, other_product), emh)
    check("E5 (c) a URL counted on ANOTHER PRODUCT's identity is not exclusive either",
          cross.reasons == (f"exclusive_below_high_rung:{HIGH - 1}",), str(cross.reasons))
    uncounted = [dict(shared[0], counted=False)]
    check("E6 (c) a URL another identity holds but does NOT count does not cost exclusivity",
          decide(rec, groups(own, uncounted), emh).live)
    dup_ok = own + [dict(own[0], id="dup")]
    dup_short = own[:-1] + [dict(own[0], id="dup")]
    ok_dec, short_dec = decide(rec, groups(dup_ok), emh), decide(rec, groups(dup_short), emh)
    check("E7 (c) counts DISTINCT URLs: 34 rows over 33 URLs certify, 33 rows over 32 URLs do not",
          ok_dec.live and not short_dec.live
          and short_dec.reasons == (f"exclusive_below_high_rung:{HIGH - 1}",),
          f"{ok_dec.reasons} / {short_dec.reasons}")

    stale = decide(rec, groups(own), health("obs-studio", "99.0.0", last_run=STALE))
    check("E8 (d) stale monitoring refuses, every reason prefixed monitoring:, one per method",
          not stale.live and all(r.startswith("monitoring:") for r in stale.reasons)
          and {r for r in stale.reasons} == {f"monitoring:stale:{m}" for m in methods("obs-studio")}
          | {"monitoring:no_healthy_method",
             f"monitoring:contributing_family_unhealthy:{family(methods('obs-studio')[0])}"},
          str(stale.reasons))
    silent = decide(rec, groups(own), [])
    check("E9 (d) no telemetry for the patch refuses: every owned method is missing",
          not silent.live and {f"monitoring:missing_method_telemetry:{m}" for m in methods("obs-studio")}
          <= set(silent.reasons), str(silent.reasons))
    via = methods("obs-studio")[1]
    laundered = decide(rec, groups(reports("obs-studio", "99.0.0", HIGH, via=via)),
                       health("obs-studio", "99.0.0", overrides={via: "disabled"}))
    check("E10 (d) the families come from the counted rows: a disabled method behind the reports refuses",
          laundered.reasons == (f"monitoring:contributing_family_unhealthy:{family(via)}",),
          str(laundered.reasons))
    other_patch = [dict(r, update_version="98.0.0") for r in emh]
    check("E11 (d) another patch's healthy telemetry never answers for this one",
          not decide(rec, groups(own), other_patch).live)

    everything = decide(record("blackmagic-davinci", "1.0"), groups(), [])
    classes = {r.split(":")[0] for r in everything.reasons}
    check("E12 nothing short-circuits: a record failing all four names all four",
          {"not_promotion_product", "below_high_rung", "exclusive_below_high_rung",
           "monitoring"} <= classes, str(everything.reasons))

    population = groups(own, shared, reports("obs-studio", "97.0.0", 5, start=100))
    counts = le.exclusive_url_counts(population)
    check("E13 exclusive_url_counts covers every identity and subtracts the shared URL from both sides",
          counts == {("obs-studio", "99.0.0", ""): HIGH - 1, ("obs-studio", "98.0.0", ""): 0,
                     ("obs-studio", "97.0.0", ""): 5}, str(counts))
    check("E14 a precomputed map gives the same decision as computing it in place",
          decide(rec, population, emh, exclusive=counts) == decide(rec, population, emh))


# ------------------------------------------------------------------------------- [M] certify_live
def section_m() -> None:
    print("\n[M] the stored maturity is untouched: certify_live is still not enabled")
    rec, own = record(), reports("obs-studio", "99.0.0", HIGH)
    check("M1 certify_live declines an identity evaluate certifies",
          maturity.certify_live(rec, own) == maturity.NOT_ENABLED
          and decide(rec, groups(own), health("obs-studio", "99.0.0")).live)
    check("M2 so every writer still stores the non-live tuple at the High rung",
          maturity.record_maturity(rec, own) == maturity.PILOT_SAMPLE)


# ------------------------------------------------------------------------------- [P] projection
def _tree_hashes(root: Path, skip: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and p != skip}


def _run_script(root: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GITHUB_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # The bare-script invocation pages.yml uses, from the repository root.
    return subprocess.run([sys.executable, "auxsays/scripts/build_live_eligibility_projection.py",
                           "--root", str(root), "--now", NOW_ISO],
                          cwd=_REPO, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300, env=env)


def _projection(root: Path) -> dict:
    path = root / "_data" / "live_eligibility.yml"
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}


def _stat(path: Path):
    return (path.stat().st_mtime_ns, path.stat().st_size) if path.exists() else None


def section_p() -> None:
    print("\n[P] the deploy-time projection, run as pages.yml runs it")
    repo_before = _stat(REPO_PROJECTION)
    healthy, stale, pilot = record(version="99.0.0"), record(version="98.0.0"), \
        record(version="97.0.0", live=False)
    with tempfile.TemporaryDirectory(prefix="auxsays-live-") as td:
        root = Path(td) / "auxsays"
        gen = root / "updates" / "generated"
        gen.mkdir(parents=True)
        for name, rec in (("a-healthy.md", healthy), ("b-stale.md", stale), ("c-pilot.md", pilot)):
            write_front_matter_and_body(gen / name, rec, "\nbody\n")
        rows = (reports("obs-studio", "99.0.0", HIGH) + reports("obs-studio", "98.0.0", HIGH, start=200)
                + reports("obs-studio", "97.0.0", HIGH, start=400))
        emh = (health("obs-studio", "99.0.0") + health("obs-studio", "98.0.0", last_run=STALE)
               + health("obs-studio", "97.0.0"))
        data = root / "_data"
        data.mkdir()
        store = data / "consensus_evidence.yml"
        store.write_bytes(yaml.safe_dump({"evidence": rows}, sort_keys=False).encode("utf-8"))
        (data / "evidence_method_health.yml").write_bytes(
            yaml.safe_dump({"methods": emh}, sort_keys=False).encode("utf-8"))
        (root / "_config.yml").write_bytes(
            b"monitoring_min_healthy_methods: 2\nmonitoring_max_age_days: 14\n")
        out_path = data / "live_eligibility.yml"
        before = _tree_hashes(root, out_path)

        proc = _run_script(root)
        payload = _projection(root)
        check("P1 the bare script exits 0 from the repository root", proc.returncode == 0,
              (proc.stderr or proc.stdout)[-400:])
        check("P2 a healthy live claim is listed, and only it",
              payload.get("urls") == [healthy["permalink"]], str(payload))
        check("P3 a live claim whose monitoring went stale is NOT listed",
              stale["permalink"] not in (payload.get("urls") or [])
              and "b-stale.md: not live" in proc.stdout and "monitoring:stale:" in proc.stdout,
              proc.stdout[-400:])
        check("P4 a record that does not claim live is never listed, even with certifying evidence",
              pilot["permalink"] not in (payload.get("urls") or [])
              and "c-pilot.md" not in proc.stdout)
        check("P5 the projection carries exactly generated_at (the judged instant) and urls",
              set(payload) == {"generated_at", "urls"} and payload.get("generated_at") == NOW_ISO,
              str(payload))
        check("P6 nothing but the projection was written: every generated record hashes the same",
              _tree_hashes(root, out_path) == before)

        good_store = store.read_bytes()
        store.unlink()
        missing = _run_script(root)
        check("P7 a MISSING evidence store writes an empty projection, warns, and exits 0",
              missing.returncode == 0 and _projection(root).get("urls") == []
              and "::warning::" in missing.stdout and "EvidenceStoreError" in missing.stdout,
              (missing.stdout + missing.stderr)[-400:])
        store.write_bytes(b"evidence: not-a-list\n")
        malformed = _run_script(root)
        check("P8 a MALFORMED evidence store fails closed the same way",
              malformed.returncode == 0 and _projection(root).get("urls") == []
              and "::warning::" in malformed.stdout, (malformed.stdout + malformed.stderr)[-400:])
        # Not only the store: ANY failure fails closed. A raise here would fail the deploy and
        # freeze the site's HTML -- a worse outcome than a live label withheld.
        store.write_bytes(good_store)  # a VALID store, so only the config can fail
        config = root / "_config.yml"
        config_before = config.read_bytes()
        config.write_bytes(config_before + b"\nmonitoring_max_age_days: fourteen\n")
        bad_config = _run_script(root)
        config.write_bytes(config_before)
        check("P8b a malformed threshold in the config fails closed too, never failing the deploy",
              bad_config.returncode == 0 and _projection(root).get("urls") == []
              and "::warning::" in bad_config.stdout, (bad_config.stdout + bad_config.stderr)[-400:])
        check("P9 neither refusal touched a generated record",
              {k: v for k, v in _tree_hashes(root, out_path).items() if k.startswith("updates")}
              == {k: v for k, v in before.items() if k.startswith("updates")})
    check("P10 no run wrote the repository's own projection", _stat(REPO_PROJECTION) == repo_before)

    ignored = (_REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    check("P11 the projection is git-ignored, so a local run cannot commit a stale answer",
          "auxsays/_data/live_eligibility.yml" in ignored)
    wf = yaml.safe_load((_REPO / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8"))
    on = wf.get(True) or wf.get("on") or {}
    crons = [str(e.get("cron")) for e in (on.get("schedule") or []) if isinstance(e, dict)]
    check("P12 pages.yml also builds on a daily schedule, so freshness advances with no commit",
          len(crons) == 1 and re.fullmatch(r"\d+ \d+ \* \* \*", crons[0] or "") is not None, str(crons))
    steps = (wf.get("jobs") or {}).get("build", {}).get("steps") or []
    runs = [str(s.get("run") or "") for s in steps]
    at = lambda needle: next((i for i, r in enumerate(runs) if needle in r), -1)  # noqa: E731
    gen_at, pip_at, build_at = (at("build_live_eligibility_projection.py"), at("pip install"),
                                at("jekyll build"))
    check("P13 the projection step runs after pip install and BEFORE the Jekyll build",
          -1 < pip_at < gen_at < build_at, f"pip={pip_at} gen={gen_at} build={build_at}")
    check("P14 the Pages build stays read-only and outside the writer lane",
          (wf.get("permissions") or {}).get("contents") == "read"
          and (wf.get("concurrency") or {}).get("group") == "pages", str(wf.get("concurrency")))


# ------------------------------------------------------------------------------- liquid bridge
_DRIVER = r"""
require 'liquid'
require 'json'

# Jekyll's include tag, not Liquid's: the filename carries a dot and params arrive as key=value.
class JekyllInclude < Liquid::Tag
  SYNTAX = /([\w.\/-]+)((\s+\w+\s*=\s*(?:"[^"]*"|'[^']*'|[\w.\[\]\/-]+))*)/
  def initialize(name, markup, tokens)
    super
    m = markup.strip.match(SYNTAX) or raise Liquid::SyntaxError, "bad include: #{markup}"
    @file = m[1]
    @params = {}
    (m[2] || "").scan(/(\w+)\s*=\s*("[^"]*"|'[^']*'|[\w.\[\]\/-]+)/) { |k, v| @params[k] = v }
  end
  def render(context)
    path = File.join(context.registers[:include_root], @file)
    raise Liquid::FileSystemError, "missing include #{@file}" unless File.exist?(path)
    vals = {}
    @params.each do |k, v|
      vals[k] = (v =~ /\A"(.*)"\z/m || v =~ /\A'(.*)'\z/m) ? $1 : context[v]
    end
    partial = (context.registers[:cache] ||= {})[path] ||=
      Liquid::Template.parse(File.read(path, encoding: "utf-8"))
    context.stack { context["include"] = vals; partial.render!(context) }
  end
end
Liquid::Template.register_tag("include", JekyllInclude)

payload = JSON.parse(File.read(ARGV[0]))
tpl = Liquid::Template.parse(payload["template"])
out = {}
payload["cases"].each do |name, c|
  begin
    out[name] = tpl.render!({ "site" => c["site"], "page" => c["page"] },
                            registers: { include_root: payload["includes"] })
  rescue => e
    out[name] = "<<ERR: #{e.class}: #{e.message}>>"
  end
end
print JSON.generate(out)
"""


def render(template: str, cases: dict) -> dict:
    """{name: rendered} for {name: {"page": ..., "site": ...}}. A missing ruby/gem yields an error
    string per case, so every check still runs -- and fails -- rather than silently skipping."""
    ruby = shutil.which("ruby")
    if not ruby:
        return {name: "<<ERR: ruby is not on PATH>>" for name in cases}
    with tempfile.TemporaryDirectory(prefix="auxsays-maturity-") as td:
        script, payload = Path(td) / "d.rb", Path(td) / "p.json"
        script.write_text(_DRIVER, encoding="utf-8")
        payload.write_text(json.dumps({"template": template, "cases": cases,
                                       "includes": str(INCLUDES)}, default=str), encoding="utf-8")
        proc = subprocess.run([ruby, str(script), str(payload)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300)
    if proc.returncode != 0 or not proc.stdout.strip():
        return {name: f"<<ERR: {(proc.stderr or '')[-300:]}>>" for name in cases}
    return json.loads(proc.stdout)


URL = "/updates/test/obs-studio/99-0-0/"
LISTED = {"data": {"live_eligibility": {"urls": [URL]}}}
UNLISTED = {"data": {"live_eligibility": {"urls": []}}}
ABSENT = {"data": {}}
PROBE = ("{% include maturity-state.html record=page %}"
         "[{{ maturity_class }}|{{ maturity_label }}|{{ maturity_stage_label }}|{{ maturity_live }}]")


def page(**axes) -> dict:
    return {"url": URL, **axes}


LIVE_AXES = maturity.CONSENSUS_LIVE.axes()
RENDER_CASES = {
    # name: (page, site, expected probe)
    "R1 certified live claim":
        (page(**LIVE_AXES), LISTED, "[live|Live consensus|Established reports|true]"),
    "R2 the same claim, projection present but not listing it":
        (page(**LIVE_AXES), UNLISTED, "[pilot|Verified reports|Early reports|false]"),
    "R3 the same claim, projection missing entirely":
        (page(**LIVE_AXES), ABSENT, "[pilot|Verified reports|Early reports|false]"),
    "R3b the same claim, no site data at all":
        (page(**LIVE_AXES), {}, "[pilot|Verified reports|Early reports|false]"),
    "R4 a claim on the collection status alone (legacy word) is a claim":
        (page(evidence_state="pilot_sample", consensus_collection_status="live_consensus",
              intelligence_stage="pilot"), LISTED, "[live|Live consensus|Established reports|true]"),
    "R5 a listed page that does NOT claim live stays verified reports":
        (page(**maturity.PILOT_SAMPLE.axes()), LISTED, "[pilot|Verified reports|Early reports|false]"),
    "R6 pilot_sample":
        (page(**maturity.PILOT_SAMPLE.axes()), ABSENT, "[pilot|Verified reports|Early reports|false]"),
    "R7 static_sample":
        (page(evidence_state="static_sample"), ABSENT, "[pilot|Verified reports||false]"),
    "R8 a pilot collection status with no evidence state":
        (page(consensus_collection_status="pilot_initial_sample"), ABSENT,
         "[pilot|Verified reports||false]"),
    "R9 official_only":
        (page(**maturity.OFFICIAL_ONLY.axes()), LISTED,
         "[official|Official source only|Vendor information|false]"),
    "R10 insufficient_data":
        (page(evidence_state="insufficient_data"), ABSENT, "[insufficient|Insufficient data||false]"),
    "R11 no maturity fields at all":
        (page(), ABSENT, "[insufficient|Insufficient data||false]"),
    "R12 an unknown state reads as Insufficient data, never its own words":
        (page(evidence_state="under_review"), ABSENT, "[insufficient|Insufficient data||false]"),
    "R13 an unknown state with a stored live label cannot print it without a certificate":
        (page(evidence_state="established_consensus", evidence_state_label="LIVE CONSENSUS",
              consensus_collection_status="deferred_official_only"), ABSENT,
         "[insufficient|Insufficient data||false]"),
    "R14 a manual_watch stage reads Watching":
        (page(evidence_state="official_only", intelligence_stage="manual_watch"), ABSENT,
         "[official|Official source only|Watching|false]"),
    "R15 a case/hyphen variant of the live word is still a claim (uncertified)":
        (page(evidence_state="Consensus-Live"), ABSENT, "[pilot|Verified reports||false]"),
    "R16 ...and certifies like the canonical spelling":
        (page(evidence_state="Consensus-Live"), LISTED, "[live|Live consensus|Established reports|true]"),
}


def section_r() -> None:
    print("\n[R] the maturity contract, rendered through Liquid with a Jekyll include tag")
    cases = {name: {"page": p, "site": s} for name, (p, s, _e) in RENDER_CASES.items()}
    out = render(PROBE, cases)
    for name, (_p, _s, expected) in RENDER_CASES.items():
        got = out.get(name, "<<missing>>")
        check(f"{name} -> {expected}", got == expected, got[:300])
    silent = render("<{% include maturity-state.html record=page %}>",
                    {"x": {"page": page(**LIVE_AXES), "site": LISTED}})
    check("R17 the include emits nothing, so it is safe inside My Patch Stack's JSON",
          silent.get("x") == "<>", str(silent.get("x"))[:300])


# ------------------------------------------------------------------------------- [W] consumers
CONSUMERS = {
    "_layouts/aux-update.html": {"record=page": 1},
    "_layouts/aux-updates.html": {"record=item": 2},
    "_layouts/aux-home.html": {"record=candidate": 1, "record=item": 1},
    "updates/my-stack.md": {"record=chosen": 1, "record=rec": 1},
}
# The variables the five private ladders compared to the live word. The homepage's "is this
# candidate worth ranking at all" filter still reads `candidate_evidence_state`; it is not a ladder
# (an uncertified claim renders as Verified reports, which is just as worth ranking) and the
# lookbehind leaves it alone.
_LADDER_RE = re.compile(r"(?<![\w.])(evidence_state|feed_evidence_state|ev_state|rec_ev_state|"
                        r"collection_status|item_stage)\s*==\s*'(consensus_live|live_consensus)'")


def private_ladder(emitted: str, *, allowed_live: int = 0) -> bool:
    """Does this markup decide the live words for itself? One literal is allowed on the patch page,
    in its branch keyed on the contract's own class."""
    return (emitted.count("'Live consensus'") != allowed_live
            or "'Established reports'" in emitted
            or _LADDER_RE.search(emitted) is not None)


def section_w() -> None:
    print("\n[W] every consumer renders maturity through the one contract")
    check("W0 the ladder predicate bites on a line of the removed feed ladder",
          private_ladder("{% elsif feed_evidence_state == 'consensus_live' %}")
          and private_ladder("{% elsif item_stage == 'consensus_live' %}{% assign stage_label = "
                             "'Established reports' %}"))
    for rel, expected in CONSUMERS.items():
        text = (_AUX / rel).read_text(encoding="utf-8")
        emitted = COMMENT_RE.sub("", text)
        tags = re.findall(r"\{%-?\s*include\s+maturity-state\.html\s+(record=\w+)\s*-?%\}", emitted)
        found = {arg: tags.count(arg) for arg in set(tags)}
        check(f"W1 {rel} includes the contract as expected {expected}", found == expected, str(found))
        check(f"W2 {rel} keeps no private live ladder",
              not private_ladder(emitted, allowed_live=1 if rel.endswith("aux-update.html") else 0))
    update = (_AUX / "_layouts" / "aux-update.html").read_text(encoding="utf-8")
    check("W3 the patch page derives its class from the contract and keeps the pinned literals",
          "{% if maturity_class == 'live' %}" in update and "{% elsif maturity_class == 'pilot' %}" in update
          and "{% assign evidence_state = 'Verified reports' %}" in update
          and "{% if evidence_state_class == 'live' %}{% assign consensus_established = true %}" in update)
    home = (_AUX / "_layouts" / "aux-home.html").read_text(encoding="utf-8")
    check("W4 the homepage ranks a candidate 2 only for a certified claim, 1 for verified reports",
          re.search(r"\{% if maturity_live %\}\s*\{% assign candidate_state_rank = 2 %\}\s*"
                    r"\{% elsif maturity_class == 'pilot' %\}\s*\{% assign candidate_state_rank = 1 %\}",
                    home) is not None)

    # The patch page's own derivation, rendered from the shipped layout: everything above the
    # strength ladder, through the contract, with a probe of what the rest of the page reads.
    body = update.split("---", 2)[-1]
    head = body[:body.index("{% assign confirmed_report_count")]
    probe = head + "[{{ evidence_state }}|{{ evidence_state_class }}|{{ consensus_established }}]"
    official_src = {"update_source_url": "https://vendor.test/notes"}
    cases = {
        "certified": {"page": page(**LIVE_AXES), "site": LISTED},
        "uncertified": {"page": page(**LIVE_AXES), "site": UNLISTED},
        "official": {"page": page(**maturity.OFFICIAL_ONLY.axes(), **official_src), "site": ABSENT},
        "nothing captured": {"page": page(**maturity.OFFICIAL_ONLY.axes()), "site": ABSENT},
    }
    out = {k: (v[-80:] if v.startswith("<<ERR") else v[v.rfind("["):])
           for k, v in render(probe, cases).items()}
    check("W5 the patch page establishes consensus for a certified claim",
          out.get("certified") == "[Live consensus|live|true]", str(out.get("certified")))
    check("W6 ...and presents the same claim uncertified as Verified reports, not established",
          out.get("uncertified") == "[Verified reports|pilot|false]", str(out.get("uncertified")))
    check("W7 below the pilot rung it keeps its own rule: official only when a source was captured",
          out.get("official") == "[Official source only|official|false]"
          and out.get("nothing captured") == "[Insufficient data|insufficient|false]", str(out))


def main() -> int:
    for section in (section_e, section_m, section_p, section_r, section_w):
        section()
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
