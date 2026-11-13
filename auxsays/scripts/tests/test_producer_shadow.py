#!/usr/bin/env python3
"""AUX-099: shadow operation of the verdict-reason producer, with its activation switch OFF.

lib/producer_shadow keeps a bounded, public-safe ledger across deploys that tells a candidate (or review-queue
item) seen for the FIRST time apart from a REPEAT appearance, by the producer's stable identity. Only an item
first seen under an unchanged producer version, against a continuing ledger, is PROSPECTIVE; a first deploy,
a lost ledger and a rules change are baselines that never inflate the prospective count.

SECTIONS. [L] the ledger over consecutive simulated deploys (PS-L1..L7): baseline, a repeat deploy counts 0
new, one added evidence row is exactly the expected new candidate, one more report of it is a repeat, a rules
change and a lost ledger are not prospective, a re-run is not double counted, the ledger stays bounded. [P]
public safety (PS-P1, P2). [N] never public, never a tracked writer (PS-N1..N3). [S] the bare script pages.yml
runs (PS-S1). [X] mutants, one per fix, each caught by a named check.

Offline; writes only in a temp dir.
Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_producer_shadow.py
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import re
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
sys.path.insert(0, str(_AUX / "scripts"))

import yaml  # noqa: E402

from lib import producer_shadow as ps  # noqa: E402
from lib import verdict_reason_producer as vrp  # noqa: E402
from lib import verdict_reasons as vr  # noqa: E402

SHADOW_LIB = _AUX / "scripts" / "lib" / "producer_shadow.py"
SCRIPT = _AUX / "scripts" / "producer_shadow.py"
PAGES = _REPO / ".github" / "workflows" / "pages.yml"

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
        print(f"  FAIL  {label}" + (f"  --  {detail}" if detail else ""))
        _ERRORS.append(label)


@contextlib.contextmanager
def captured():
    global _PASS, _FAIL, _ERRORS
    saved = (_PASS, _FAIL, _ERRORS)
    _PASS, _FAIL, _ERRORS = 0, 0, []
    failures: list[str] = []
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            yield failures
    finally:
        failures.extend(_ERRORS)
        _PASS, _FAIL, _ERRORS = saved


# ------------------------------------------------------------------------ fixtures
PRO = {"update_entry": True, "product_id": "adobe-acrobat-pro", "update_version": "15.099.20001",
       "permalink": "/updates/adobe/adobe-acrobat-pro/15-099-20001/", "update_report_count": 1}
OBS_NOTES = "\r\n".join(["## OBS Studio 31.1.2 Hotfix Changes",
                         "* Fixed an issue in OBS Studio 31.1.0 and 31.1.1 where Decklink Output did not work [dev]"])
RECORDS = [
    PRO,
    {"update_entry": True, "product_id": "obs-studio", "update_version": "31.1.0", "update_published_at": "2025-07-07",
     "permalink": "/updates/obs-project/obs-studio/31-1-0/"},
    {"update_entry": True, "product_id": "obs-studio", "update_version": "31.1.1", "update_published_at": "2025-07-12",
     "permalink": "/updates/obs-project/obs-studio/31-1-1/"},
    {"update_entry": True, "product_id": "obs-studio", "update_version": "31.1.2", "update_published_at": "2025-07-28",
     "permalink": "/updates/obs-project/obs-studio/31-1-2/", "official_patch_notes_body": OBS_NOTES,
     "official_patch_notes_source_url": "https://github.com/obsproject/obs-studio/releases/tag/31.1.2"},
]
SECRET = "SECRET-REPORT-TEXT-7f3a"


def row(i: int, title: str, excerpt: str, date: str) -> dict:
    return {"id": f"acro-{i}", "source_url": f"https://community.test/{SECRET}/{i}", "report_title": title,
            "report_text_excerpt": excerpt + f" {SECRET}", "source_date": date,
            "source_reporter_id": f"{SECRET}-author-{i}"}


MAC = row(1, "Acrobat DC install fails on my Mac",
          "Exit Code: 7 on El Capitan 10.11.3 from Creative Cloud. ERROR: DW003", "2026-05-01")
WIN10 = row(2, "Cannot install Acrobat Pro DC on Windows 10",
            "Installer stops with Exit Code: 7 on Windows 10. ERROR: DW003", "2026-05-02")
# A third reporter (its own source reporter id), worded apart from the other two so no copy cue joins it.
WIN7 = row(3, "Acrobat Pro DC on my old Windows 7 machine", "Setup ends with exit code 7 after the extraction step, "
           "DW003 listed under specific errors.", "2026-05-03")
WIN7_SAME_AUTHOR_AS_10 = dict(WIN7, source_reporter_id=WIN10["source_reporter_id"])


def artifact(rows: list, *, records=RECORDS) -> dict:
    """What build_verdict_projection.py writes at deploy (the producer's artifact), over these rows."""
    result = vrp.produce(records, {vr.record_identity(PRO): rows})
    return json.loads(json.dumps(vrp.artifact(result)))


def deploy(ledger, art, n: int, version_override: str | None = None):
    if version_override is not None:
        art = dict(art, producer_version=version_override)
    return ps.update(ledger, art, deploy=f"run{n}.1", commit=f"{n:040x}", observed_at=f"2026-11-{12 + n:02d}T05:41:00Z")


EXPECTED_KEY = "c:" + vrp.candidate_key(vrp.INSTALL_CLASS, vr.record_identity(PRO), "TEST FIRST", vrp.INSTALL_SCOPE,
                                        vrp.ACROBAT_GROUP_PREFIX + "DW003")


# ------------------------------------------------------------------------ [L] the ledger
def check_ledger() -> None:
    a1 = artifact([MAC])
    l1, s1 = deploy(None, a1, 1)
    origins = {e["origin"] for e in l1["entries"].values()}
    check("PS-L1 the first deploy is a BASELINE: every candidate and queue item it sees is recorded, none as "
          "prospective (they existed before shadow operation began)",
          s1["mode"] == "baseline" and s1["candidates"] >= 1 and origins == {"baseline"}
          and l1["totals"]["prospective_candidate"] == 0 and not s1["new_prospective_candidates"],
          f"{s1} {origins}")
    l2, s2 = deploy(l1, a1, 2)
    check("PS-L2 a second deploy over UNCHANGED evidence counts 0 new unique candidates: every item is a repeat "
          "appearance (appearances 2), nothing prospective",
          s2["mode"] == "continuing" and s2["first_seen_candidates"] == 0 and s2["first_seen_queue"] == 0
          and s2["repeat_candidates"] == s1["candidates"] and s2["repeat_queue"] == s1["queue"]
          and all(e["appearances"] == 2 for e in l2["entries"].values())
          and l2["totals"]["prospective_candidate"] == 0, str(s2))
    a3 = artifact([MAC, WIN10])
    l3, s3 = deploy(l2, a3, 3)
    entry = l3["entries"].get(EXPECTED_KEY) or {}
    check("PS-L3 one added evidence row (a second report of the same installer error, from Windows 10: another "
          "machine) gives EXACTLY the expected new candidate -- the Acrobat install TEST FIRST, by its stable key "
          "-- as the one unique prospective candidate, and nothing else is new",
          s3["new_prospective_candidates"] == [EXPECTED_KEY] and s3["first_seen_queue"] == 0
          and entry.get("origin") == "prospective" and entry.get("verdict") == "TEST FIRST"
          and entry.get("reports") == 2 and l3["totals"]["prospective_candidate"] == 1,
          f"{s3} {entry}")
    a4 = artifact([MAC, WIN10, WIN7])
    l4, s4 = deploy(l3, a4, 4)
    check("PS-L4 one more report of the SAME problem is a repeat appearance, not a new candidate: the reason now "
          "says three reports, the stable identity is unchanged",
          s4["first_seen_candidates"] == 0 and l4["entries"].get(EXPECTED_KEY, {}).get("reports") == 3
          and l4["entries"].get(EXPECTED_KEY, {}).get("appearances") == 2 and l4["totals"]["prospective_candidate"] == 1, str(s4))
    l5, s5 = deploy(l4, artifact([MAC, WIN10, WIN7, row(4, "Acrobat DC fails on Windows 11", "Exit Code: 7 on "
                                                        "Windows 11 too.", "2026-05-04")]), 5, version_override="99")
    rules = deploy(l5, artifact([MAC, WIN10]), 6, version_override="99")[1]
    l6b, s6b = deploy(l2, a3, 6, version_override="99")
    check("PS-L5 a deploy that runs a DIFFERENT producer version records what it sees for the first time as a rules "
          "change, never as prospective (new rules re-reading old evidence are not new cases); the next deploy on "
          "that version continues normally",
          s5["mode"] == "rules_change" and s6b["mode"] == "rules_change" and not s6b["new_prospective_candidates"]
          and l6b["entries"].get(EXPECTED_KEY, {}).get("origin") == "rules_change" and rules["mode"] == "continuing",
          f"{s5['mode']} {s6b} {rules['mode']}")
    lost, s_lost = deploy(None, a3, 7)
    corrupt, s_corrupt = deploy({"schema_version": 0}, a3, 7)
    again, s_again = deploy(l3, a3, 3)
    check("PS-L6 a ledger that cannot be continued (absent, or unreadable) is a new BASELINE that says why and counts "
          "the reset -- prospective cases are under-counted, never inflated; the same deploy recorded twice is not "
          "counted twice",
          s_lost["mode"] == "baseline" and lost["totals"]["prospective_candidate"] == 0
          and s_corrupt["mode"] == "baseline" and corrupt["resets"] == 1 and corrupt["baseline"]["reason"]
          and s_again["mode"] == "already_recorded" and again == l3, f"{s_lost} {s_corrupt} {s_again['mode']}")
    saved = (ps.MAX_ENTRIES, ps.MAX_DEPLOYS)
    try:
        ps.MAX_ENTRIES, ps.MAX_DEPLOYS = 3, 4
        led = None
        for n in range(1, 9):
            art = {"producer_version": "4", "candidates": [
                {"candidate_key": f"k{n}-{j}", "producer": {"class": vrp.VENDOR_CLASS}, "product_id": "p",
                 "update_version": f"{n}.{j}", "verdict": "WAIT", "scope": "if you use x", "evidence": []}
                for j in range(2)], "review_queue": []}
            led, _s = deploy(led, art, n)
    finally:
        ps.MAX_ENTRIES, ps.MAX_DEPLOYS = saved
    kept = sorted(led["entries"])
    check("PS-L7 bounded: at most MAX_ENTRIES items (inactive ones evicted, oldest and non-prospective first) and the "
          "last MAX_DEPLOYS deploy summaries; the running totals keep counting what was evicted",
          len(led["entries"]) <= 3 and len(led["deploys"]) == 4 and {"c:k8-0", "c:k8-1"} <= set(kept)
          and led["totals"]["evicted"] == 16 - len(led["entries"])
          and led["totals"]["prospective_candidate"] + led["totals"]["baseline_candidate"] == 16,
          f"{kept} {led['totals']} {len(led['deploys'])}")


# ------------------------------------------------------------------------ [P] public safety
FORBIDDEN_KEYS = {"reason", "failure", "evidence", "citation", "source", "statement", "report_title",
                  "report_text_excerpt", "source_url", "id", "source_reporter_id", "rows", "dropped_by_independence_gate",
                  "producer", "why"}


def check_public_safety() -> None:
    art = artifact([MAC, WIN10, WIN7_SAME_AUTHOR_AS_10])
    led, summary = deploy(None, art, 1)
    led, summary = deploy(led, artifact([MAC, WIN10, WIN7]), 2)
    text = json.dumps(led) + ps.render_summary(led, summary)
    keys = {k for e in led["entries"].values() for k in e}
    check("PS-P1 the ledger and the step summary carry no report text, title, source URL, row id or reporter id "
          "(a marker planted in every one of them never appears), and no reason, statement or citation text",
          SECRET not in text and not (keys & FORBIDDEN_KEYS) and "acro-" not in text
          and "Decklink Output did not work" not in text, f"{sorted(keys & FORBIDDEN_KEYS)} {SECRET in text}")
    allowed = set(ps._CANDIDATE_FIELDS) | set(ps._QUEUE_FIELDS) | {"kind", "origin", "first_seen", "last_seen",
                                                                    "appearances", "active"}
    labels = {e.get("problem") for e in led["entries"].values() if e.get("problem")}
    odd = ps._problem("error 0x800f0991; the user wrote this")
    check("PS-P2 every stored field is from a closed list, and a problem label must match the producer's closed "
          "vocabulary (an error code, a named stage, a specific installer error) or it is dropped",
          keys <= allowed and labels <= {vrp.ACROBAT_GROUP_PREFIX + "DW003"} and odd == ""
          and ps._problem("error 0x800f0991") != "" and ps._problem("installer error DW003") != "",
          f"{sorted(keys - allowed)} {labels} {odd!r}")


# ------------------------------------------------------------------------ [N] never public, never a writer
def check_never_public() -> None:
    hits = []
    for path in sorted(_AUX.rglob("*")):
        if not path.is_file() or path.suffix not in (".html", ".md", ".liquid", ".xml", ".json", ".js") \
                or any(part in ("_site", "node_modules", "updates", "scripts", "_data") for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"verdict_reason_candidates|producer_shadow|producer-shadow", text):
            hits.append(str(path.relative_to(_AUX)))
    readers = []
    for path in sorted((_AUX / "scripts" / "lib").glob("*.py")):
        if path.name in ("verdict_reason_producer.py", "producer_shadow.py", "verdict_projection.py"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = ([a.name for a in node.names] if isinstance(node, (ast.Import, ast.ImportFrom)) else [])
            mod = node.module if isinstance(node, ast.ImportFrom) and node.module else ""
            if any(n.split(".")[-1] in ("verdict_reason_producer", "producer_shadow") for n in names + [mod]):
                readers.append(path.name)
    check("PS-N1 no template, include, layout or page reads the producer's artifact or the shadow ledger, and no "
          "library behind evidence, counts, maturity or live certification imports the producer or the shadow "
          "module: shadow candidates reach nothing public",
          not hits and not readers, f"{hits[:5]} {readers}")
    workflow = yaml.safe_load(PAGES.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["build"]["steps"]
    names = [s.get("name", "") for s in steps]
    shadow = [s for s in steps if "shadow" in s.get("name", "").lower()]
    idx = {n: i for i, n in enumerate(names)}
    projection, qa = idx.get("Build the verdict projection"), idx.get("Run generated record QA (publication-strict)")
    record = idx.get("Record the reason producer's shadow diagnostics")
    save = idx.get("Save the reason producer's shadow ledger")
    upload = idx.get("Upload artifact")
    check("PS-N2 pages.yml runs the shadow steps on main only, each continue-on-error (diagnostics never stop a "
          "deploy), after the projection wrote the artifact and before QA, and saves the ledger only after the Pages "
          "artifact is uploaded; the ledger lives outside the site source under a per-run cache key and is never "
          "part of the Pages artifact",
          len(shadow) == 4 and all(s.get("continue-on-error") is True and "refs/heads/main" in str(s.get("if"))
                                   for s in shadow)
          and None not in (projection, qa, record, save, upload) and projection < record < qa and upload < save
          and all(".producer-shadow" in json.dumps(s) for s in shadow)
          and all("github.run_id" in str((s.get("with") or {}).get("key", "github.run_id")) for s in shadow)
          and "auxsays" not in str((steps[save].get("with") or {}).get("path"))
          and (steps[upload].get("with") or {}).get("path") == "./auxsays/_site", str(names))
    ignored = (_REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    imports = set()
    for node in ast.walk(ast.parse(SHADOW_LIB.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imports |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    calls = {n.func.id for n in ast.walk(ast.parse(SHADOW_LIB.read_text(encoding="utf-8")))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    check("PS-N3 never a tracked writer: the ledger path is git-ignored and outside auxsays/, no writeback lane "
          "touches it, and lib/producer_shadow is pure (standard library only; no file, clock or network)",
          ".producer-shadow/" in ignored and imports <= {"__future__", "re", "typing"} and "open" not in calls
          and not any("producer-shadow" in p.read_text(encoding="utf-8", errors="replace")
                      for p in (_REPO / ".github" / "workflows").glob("*.yml") if p.name != "pages.yml"),
          f"{sorted(imports)} {sorted(calls & {'open'})}")


# ------------------------------------------------------------------------ [S] the script pages.yml runs
def check_script(tmp: Path) -> None:
    tmp.mkdir(parents=True, exist_ok=True)
    cand = tmp / "verdict_reason_candidates.yml"
    ledger = tmp / ".producer-shadow" / "ledger.json"
    summary = tmp / "summary.md"
    env = {k: v for k, v in __import__("os").environ.items() if k not in ("GITHUB_STEP_SUMMARY", "GITHUB_OUTPUT")}

    def run(art: dict | None, n: int):
        if art is None:
            cand.unlink(missing_ok=True)
        else:
            cand.write_text(vrp.ARTIFACT_HEADER + yaml.safe_dump(art, sort_keys=False, allow_unicode=True),
                            encoding="utf-8")
        return subprocess.run([sys.executable, str(SCRIPT), "--candidates", str(cand), "--ledger", str(ledger),
                               "--deploy-id", f"run{n}.1", "--commit", f"{n:040x}", "--observed-at",
                               f"2026-11-{12 + n:02d}T05:41:00Z", "--summary", str(summary)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env)
    p1, p2, p3 = run(artifact([MAC]), 1), run(artifact([MAC]), 2), run(artifact([MAC, WIN10]), 3)
    data = json.loads(ledger.read_text(encoding="utf-8"))
    p4 = run(None, 4)
    data4 = json.loads(ledger.read_text(encoding="utf-8"))
    text = summary.read_text(encoding="utf-8") if summary.exists() else ""
    check("PS-S1 the bare script pages.yml runs: three consecutive deploys give baseline, then 0 new over unchanged "
          "evidence, then exactly one new prospective candidate after one added row; a missing artifact is recorded as "
          "a producer error and still exits 0; the step summary is appended each time",
          all(p.returncode == 0 for p in (p1, p2, p3, p4)) and "mode baseline" in p1.stdout
          and "first seen 0 / 0 (prospective)" in p2.stdout and "first seen 1 / 0 (prospective)" in p3.stdout
          and data["totals"]["prospective_candidate"] == 1 and EXPECTED_KEY in data["entries"]
          and data4["deploys"][-1].get("producer_error") is True and text.count("## Verdict-reason producer") == 4,
          f"{[p.returncode for p in (p1, p2, p3, p4)]} {p2.stdout[-200:]} {p3.stdout[-200:]} {p4.stdout[-200:]}")


# ------------------------------------------------------------------------ [X] mutants
def run_mutant(label: str, body, mutants: list, *, mutate, restore) -> None:
    try:
        with captured() as baseline:
            body()
    except Exception as exc:  # noqa: BLE001
        mutants.append((label, [], f"baseline raised {type(exc).__name__}: {exc}"))
        return
    mutate()
    try:
        with captured() as failures:
            body()
    except Exception as exc:  # noqa: BLE001
        mutants.append((label, [], f"{type(exc).__name__}: {exc}"))
        return
    finally:
        restore()
    mutants.append((label, [f for f in failures if f not in set(baseline)], ""))


def swap(owner, name, replacement):
    original = getattr(owner, name)
    return (lambda: setattr(owner, name, replacement)), (lambda: setattr(owner, name, original))


def check_mutations(tmp: Path) -> None:
    real_update, real_obs = ps.update, ps.observation

    def every_first_seen_prospective(ledger, art, *, deploy, commit, observed_at):
        led, summ = real_update(ledger, art, deploy=deploy, commit=commit, observed_at=observed_at)
        for e in led["entries"].values():
            if e.get("appearances") == 1:
                e["origin"] = "prospective"
        return led, dict(summ, new_prospective_candidates=[k for k, e in led["entries"].items()
                                                           if e.get("appearances") == 1 and e["kind"] == "candidate"])

    def unstable_key(art):
        out = {}
        for key, item in real_obs(art).items():
            out[f"{key}:{item.get('reports', 0)}"] = item
        return out

    def copies_text(art):
        out = real_obs(art)
        for c in art.get("candidates") or []:
            k = "c:" + str(c.get("candidate_key"))
            if k in out:
                out[k]["reason"] = c.get("reason")
        return out

    def rules_ignored(ledger, art, *, deploy, commit, observed_at):
        if isinstance(ledger, dict) and ledger.get("producer_version"):
            ledger = dict(ledger, producer_version=str(art.get("producer_version")))
        return real_update(ledger, art, deploy=deploy, commit=commit, observed_at=observed_at)

    cases = [
        ("PX1 every first-seen item is prospective (a baseline or a lost ledger inflates the count)", check_ledger,
         swap(ps, "update", every_first_seen_prospective)),
        ("PX2 an appearance with one more report is a new candidate (unstable identity)", check_ledger,
         swap(ps, "observation", unstable_key)),
        ("PX3 a producer-version change is not detected (new rules count as prospective cases)", check_ledger,
         swap(ps, "update", rules_ignored)),
        ("PX4 the ledger is not bounded", check_ledger, swap(ps, "_bounded", lambda entries, totals: entries)),
        ("PX5 the ledger copies the candidate's reason text", check_public_safety, swap(ps, "observation", copies_text)),
        ("PX6 any problem label is stored (no closed vocabulary)", check_public_safety,
         swap(ps, "_PROBLEM_LABEL_RE", re.compile(r".+", re.S))),
    ]
    mutants: list = []
    for label, body, (mutate, restore) in cases:
        run_mutant(label, body, mutants, mutate=mutate, restore=restore)
    for label, failures, crash in mutants:
        check(f"{label} -> caught", bool(failures),
              f"mutant crashed instead of being caught: {crash}" if crash else "no NAMED check failed")
        if failures:
            print(f"        caught by: {', '.join(sorted(failures)[:3])}")


def run() -> int:
    print("=" * 78)
    print("AUX-099 VERDICT-REASON PRODUCER: SHADOW OPERATION")
    print("=" * 78)
    if vrp.PUBLIC_AUTO_ACTIVATION is not False:
        print("  the activation switch is not OFF")
        return 1
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        print("\n[L] the ledger over consecutive simulated deploys")
        check_ledger()
        print("\n[P] public safety")
        check_public_safety()
        print("\n[N] never public, never a tracked writer")
        check_never_public()
        print("\n[S] the script pages.yml runs")
        check_script(tmp / "s")
        print("\n[X] mutants, each caught by a named check")
        check_mutations(tmp)
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
