#!/usr/bin/env python3
"""AUX-065: DaVinci Resolve records archive themselves when their major falls two behind stable.

THE RULE. The newest STABLE major minus two, or older, is archived. With stable 21 that is every
10.x-19.x record (100 of 122); 20.x, 21.x and "21 Public Beta 1" stay active. It is a one-way
ratchet, DaVinci-scoped, and it REFUSES, with a named reason, when its baseline is implausible.

WHAT THIS SUITE PINS.
[P] parsing: stable, beta, rejected. [T] the threshold: a beta never sets it, a stable 22 moves it.
[G] major gaps and refusals: a bare "2026", a jump of more than one, no stable record, an
unreadable record, an archived record at the baseline. [E] the single-line byte-preserving edit.
[I] idempotence. [R] the ratchet: nothing is ever un-archived. [S] scope: no other product, no
non-entry record. [Q] the generated-record loader skips archived records. [C] the CLI: dry run by
default, a refusal exits 3 and writes nothing, a write needs both flags.
[X] persistence: consensus writeback (including version 21, the old hard-coded reactivation),
official-ingestion refresh and repeated cycles all keep an archived record archived; a stable 23
makes 21 qualify; no status event is ever written; feed_hidden / status_change_type cannot bring an
archived record back into a current surface.
[W] the workflow step: position, gate, and the shell executed rather than grepped.
[N] the notice: shipped Liquid rendered through the liquid gem, exact wording, scoped, wired.
[K] the real corpus: the measured 100 / 7 / 22 and a scratch-copy apply that converges to zero.

Deterministic and offline: no network, no git, writes only inside temp dirs.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_davinci_archive_policy.py
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from collections import Counter
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
_SCRIPTS = _AUX / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import yaml  # noqa: E402

import apply_consensus_to_records as acr  # noqa: E402
import apply_davinci_archive_policy as cli  # noqa: E402
from lib import davinci_archive_policy as pol  # noqa: E402
from lib import write_update_record as wur  # noqa: E402
from lib.report_counts import counted_evidence_counts, load_evidence_store  # noqa: E402
from patch_collectors import base  # noqa: E402

DAV = "blackmagic-davinci"
OBS = "obs-studio"
NL = "\n"
WORKFLOW = _REPO / ".github" / "workflows" / "patch-ingest.yml"
LAYOUT = _AUX / "_layouts" / "aux-update.html"
INCLUDE = _AUX / "_includes" / "archived-notice.html"
STEP_NAME = "Converge DaVinci archive status"
NOTICE = ("Archived release. This DaVinci Resolve version is no longer included in routine patch "
          "monitoring. Historical report counts and recorded decisions are retained for reference; "
          "they are not a current assessment of whether to install this version.")

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
        print(f"  FAIL  {label}" + (f"  --  {detail}" if detail else ""))


# ----------------------------------------------------------------------------- fixtures

def rec_text(version: str, *, status: str | None = "current", product: str = DAV, entry: bool = True,
             eol: str = NL, extra: list[str] | None = None, body: str = "body") -> str:
    lines = ["layout: aux-update", f"product_id: {product}", f"update_entry: {'true' if entry else 'false'}",
             f"update_version: '{version}'"]
    if status is not None:
        lines.append(f"update_status: {status}")
    lines += ["update_report_count: 3", "quick_verdict: 'WAIT: x'"]
    lines += list(extra or [])
    return "---" + eol + eol.join(lines) + eol + "---" + eol + body + eol


def make_tree(td: str, versions: list[str], **kw) -> Path:
    gen = Path(td) / "auxsays" / "updates" / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    for i, v in enumerate(versions):
        (gen / f"2026-01-{(i % 28) + 1:02d}-davinci-resolve-{i:03d}.md").write_text(
            rec_text(v, **kw), encoding="utf-8", newline="")
    return gen


def fm(path: Path) -> dict:
    front, _ = base.split_front_matter(path.read_text(encoding="utf-8"))
    return yaml.safe_load(front)


def digest(directory: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.glob("*.md"))}


def majors_of(plan: pol.Plan) -> list[int]:
    return sorted({r.major for r in plan.to_archive})


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*a, **k)


STABLE = ["10.1.5", "11", "11.1", "12.0", "12.5.6", "14", "14.3.1", "15", "16.2.8", "17.4.6", "18.6.6",
          "19", "19.1.4", "20", "20.3.3", "21", "21.0.4", "21.1.2"]

# ----------------------------------------------------------------------------- workflow helpers

def eval_if(expr: str, source, dry_run) -> bool:
    """Evaluate a workflow `if:` for the two inputs this step reads."""
    py = expr.strip()
    py = re.sub(r"^\$\{\{|\}\}$", "", py).strip()
    py = py.replace("&&", " and ").replace("||", " or ")
    py = py.replace("github.event.inputs.source", "SRC").replace("github.event.inputs.dry_run", "DRY")
    py = re.sub(r"\bnull\b", "None", py)
    return bool(eval(py, {"__builtins__": {}}, {"SRC": source, "DRY": dry_run}))  # noqa: S307


def bash_exe() -> str | None:
    for cand in ("C:/Program Files/Git/bin/bash.exe", "C:/Program Files/Git/usr/bin/bash.exe"):
        if os.path.exists(cand):
            return cand
    return shutil.which("bash")


# ----------------------------------------------------------------------------- ruby bridge

RUBY = r"""
require 'liquid'
require 'json'
payload = JSON.parse(File.read(ARGV[0]))
out = {}
payload.each do |name, job|
  begin
    out[name] = Liquid::Template.parse(job['template']).render!(job['vars'])
  rescue => e
    out[name] = "<<ERR: #{e.class}: #{e.message}>>"
  end
end
print JSON.generate(out)
"""


def render_all(jobs: dict) -> tuple[bool, dict]:
    ruby = shutil.which("ruby")
    if not ruby:
        return False, {}
    tmp = Path(tempfile.mkdtemp(prefix="auxsays-archnotice-"))
    try:
        (tmp / "driver.rb").write_text(RUBY, encoding="utf-8")
        (tmp / "payload.json").write_text(json.dumps(jobs), encoding="utf-8")
        proc = subprocess.run([ruby, str(tmp / "driver.rb"), str(tmp / "payload.json")],
                              capture_output=True, text=True, encoding="utf-8")
        if proc.returncode != 0 or not proc.stdout.strip():
            return False, {"_stderr": proc.stderr[:400]}
        return True, json.loads(proc.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def visible_text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def layout_include_line() -> str:
    for line in LAYOUT.read_text(encoding="utf-8").splitlines():
        if re.search(r"\{%-?\s*include\s+archived-notice\.html", line):
            return line
    return ""


def expand_include(args_line: str, include_src: str) -> str:
    """Inline the shipped include with the arguments the shipped layout passes (as the other
    render suites do): `include.KEY` becomes the layout's value expression for KEY."""
    args = dict(re.findall(r"(\w+)=([\w.]+)", args_line))
    return re.sub(r"\binclude\.(\w+)", lambda m: args.get(m.group(1), "nil"), include_src)


# ----------------------------------------------------------------------------- promotion harness

def write_evidence(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"schema_version": 1, "evidence": rows}, sort_keys=False), encoding="utf-8")


def evidence_row(version: str, n: int) -> dict:
    return {
        "id": f"{DAV}-{version}-row-{n}", "product_id": DAV, "update_version": version,
        "source_type": "blackmagic_forum", "source_name": "Blackmagic Design Community Forum",
        "source_url": f"https://forum.example.invalid/t/{version}/{n}",
        "report_title": f"{version} issue {n}",
        "report_text_excerpt": f"User-verified report describing an issue on {version}.",
        "captured_at": "2026-09-01T00:00:00Z", "patch_version_matched": True, "matched_version": version,
        "counted": True, "issue_theme": "playback_stutter", "severity": "high", "sentiment": "negative",
        "source_weight": 1,
    }


def promote(tree: Path, evidence: Path) -> int:
    saved = (acr.ROOT, acr.GENERATED_DIR, acr.DEFAULT_EVIDENCE_PATH, acr.METHOD_HEALTH_PATH)
    acr.ROOT = tree.parents[1]
    acr.GENERATED_DIR = tree
    acr.DEFAULT_EVIDENCE_PATH = evidence
    acr.METHOD_HEALTH_PATH = tree / "no-method-health.yml"
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return acr.main(["--product-id", DAV, "--write-all", "--confirm-write"])
    finally:
        acr.ROOT, acr.GENERATED_DIR, acr.DEFAULT_EVIDENCE_PATH, acr.METHOD_HEALTH_PATH = saved


def dav21_record(status: str, **extra) -> str:
    data = {
        "layout": "aux-update", "update_entry": True, "product_id": DAV, "update_version": "21",
        "update_product": "DaVinci Resolve", "update_status": status,
        "feed_hidden": True, "status_change_type": "",
        "update_report_count": 5, "confirmed_patch_specific_report_count": 5,
        "accepted_report_sources": [{"source": f"s{i}", "source_url": f"https://x.invalid/{i}"} for i in range(5)],
        "evidence_samples": [{"source": "s0"}],
        "update_consensus_summary": "WAIT: DaVinci Resolve 21 has 5 user reports found.",
        "consensus_report": "5 user reports found for DaVinci Resolve 21.",
        "quick_verdict": "WAIT: DaVinci Resolve 21 has 5 user reports found.",
    }
    data.update(extra)
    return "---" + NL + yaml.safe_dump(data, sort_keys=False) + "---" + NL + "body" + NL


# ----------------------------------------------------------------------------- the suite

def run() -> int:
    print("=" * 78)
    print("DaVinci archive policy: newest stable major minus two, or older, is archived")
    print("=" * 78)

    # ============================================================ P: parsing
    print(NL + "[P] parsing: stable, beta, rejected")
    from lib.normalize_davinci_version import normalize_davinci_version as norm
    s = norm("19.1.4")
    check("P1 a stable version parses to its major and is not a beta",
          (s["major_version"], s["is_beta"], s["rejected"]) == (19, False, False), str(s))
    b = norm("21 Public Beta 1")
    check("P2 a public beta parses to its major and IS a beta",
          (b["major_version"], b["is_beta"], b["rejected"]) == (21, True, False), str(b))
    for bad in ("DR21", "21.x", "", "Resolve Studio"):
        check(f"P3 {bad!r} is rejected, so it can never archive or set a baseline",
              norm(bad)["rejected"] is True)
    with tempfile.TemporaryDirectory() as td:
        gen = make_tree(td, STABLE + ["DR21", "21.x"])
        plan = pol.plan_archive(gen)
        check("P4 rejected versions are listed as unparsed, not archived, and do not refuse the plan",
              [r.version for r in plan.unparsed] == ["DR21", "21.x"] and not plan.refused
              and all(r.rejected is False for r in plan.to_archive), str(plan.as_dict(gen)["unparsed"]))

    # ============================================================ T: threshold
    print(NL + "[T] the threshold")
    with tempfile.TemporaryDirectory() as td:
        gen = make_tree(td, STABLE)
        plan = pol.plan_archive(gen)
        check("T1 newest stable major is 21 and the threshold is 19",
              (plan.newest_stable_major, plan.threshold_major) == (21, 19))
        check("T2 exactly the majors <= 19 are planned, and 20.x / 21.x are not",
              majors_of(plan) == [10, 11, 12, 14, 15, 16, 17, 18, 19]
              and len(plan.to_archive) == 13, str(majors_of(plan)))
        check("T3 GAP is 2", pol.GAP == 2 and plan.gap == 2)
    with tempfile.TemporaryDirectory() as td:
        gen_a = make_tree(td, STABLE)
        base_plan = sorted(r.version for r in pol.plan_archive(gen_a).to_archive)
    with tempfile.TemporaryDirectory() as td:
        gen_b = make_tree(td, STABLE + ["22 Public Beta 1", "22 Public Beta 2"])
        plan_b = pol.plan_archive(gen_b)
        check("T4 a 22 BETA alone changes nothing: the baseline stays 21",
              plan_b.newest_stable_major == 21 and plan_b.threshold_major == 19
              and sorted(r.version for r in plan_b.to_archive) == base_plan and not plan_b.refused,
              str(plan_b.newest_stable_major))
    with tempfile.TemporaryDirectory() as td:
        gen_c = make_tree(td, STABLE + ["22 Public Beta 1", "22", "22.0.1"])
        plan_c = pol.plan_archive(gen_c)
        check("T5 a 22 STABLE moves the baseline to 22 and archives 20",
              plan_c.newest_stable_major == 22 and plan_c.threshold_major == 20
              and 20 in majors_of(plan_c) and 21 not in majors_of(plan_c), str(majors_of(plan_c)))
    with tempfile.TemporaryDirectory() as td:
        gen_d = make_tree(td, STABLE + ["21 Public Beta 2", "20 Public Beta 3", "19 Public Beta 1"])
        plan_d = pol.plan_archive(gen_d)
        beta_versions = {r.version for r in plan_d.to_archive}
        check("T6 an old BETA archives by its major; a current-major beta does not",
              "19 Public Beta 1" in beta_versions and "20 Public Beta 3" not in beta_versions
              and "21 Public Beta 2" not in beta_versions, str(sorted(beta_versions)))
    with tempfile.TemporaryDirectory() as td:
        gen_e = make_tree(td, ["20", "21", "22", "23"])
        plan_e = pol.plan_archive(gen_e)
        check("T7 a new stable 23 makes 21 qualify (and 20)",
              plan_e.threshold_major == 21 and majors_of(plan_e) == [20, 21], str(majors_of(plan_e)))

    # ============================================================ G: gaps and refusals
    print(NL + "[G] major gaps and fail-closed refusals")
    with tempfile.TemporaryDirectory() as td:
        gen = make_tree(td, ["10.1.5", "11", "12.0", "14", "15", "20", "21"])
        plan = pol.plan_archive(gen)
        check("G1 a hole BELOW the top (no 13, no 16-19) is history, not a refusal",
              not plan.refused and majors_of(plan) == [10, 11, 12, 14, 15], str(plan.refusal_reason))
    with tempfile.TemporaryDirectory() as td:
        gen = make_tree(td, STABLE + ["2026"])
        plan = pol.plan_archive(gen)
        check("G2 a bare \"2026\" REFUSES by name and plans nothing",
              plan.refused and plan.refusal_reason == pol.REFUSAL_RANGE and not plan.to_archive,
              str(plan.refusal_reason))
        check("G2b ...and the refusal states the offending major",
              "2026" in (plan.refusal_detail or ""))
    with tempfile.TemporaryDirectory() as td:
        gen = make_tree(td, ["19", "20", "21", "23"])
        plan = pol.plan_archive(gen)
        check("G3 a jump of two (21 -> 23, no 22) REFUSES with implausible_major_jump",
              plan.refused and plan.refusal_reason == pol.REFUSAL_JUMP and not plan.to_archive,
              str(plan.refusal_reason))
    with tempfile.TemporaryDirectory() as td:
        gen = make_tree(td, ["20", "21", "22"])
        check("G4 a jump of exactly one is plausible", not pol.plan_archive(gen).refused)
    with tempfile.TemporaryDirectory() as td:
        gen = make_tree(td, ["21 Public Beta 1", "20 Public Beta 2"])
        try:
            plan = pol.plan_archive(gen)
            ok, why = plan.refused and plan.refusal_reason == pol.REFUSAL_NO_STABLE, str(plan.refusal_reason)
        except Exception as exc:  # noqa: BLE001 -- a crash is not a refusal
            ok, why = False, f"raised {exc!r}"
        check("G5 betas only: no stable record REFUSES with no_stable_record", ok, why)
    with tempfile.TemporaryDirectory() as td:
        gen = make_tree(td, [])
        try:
            plan = pol.plan_archive(gen)
            ok, why = plan.refused and plan.refusal_reason == pol.REFUSAL_NO_STABLE, str(plan.refusal_reason)
        except Exception as exc:  # noqa: BLE001 -- a crash is not a refusal
            ok, why = False, f"raised {exc!r}"
        check("G6 no DaVinci record at all REFUSES rather than succeeding vacuously", ok, why)
    with tempfile.TemporaryDirectory() as td:
        gen = make_tree(td, STABLE)
        (gen / "2026-05-05-davinci-resolve-broken.md").write_text(
            "---\nproduct_id: blackmagic-davinci\nupdate_entry: true\nupdate_version: [unclosed\n---\nx\n",
            encoding="utf-8")
        plan = pol.plan_archive(gen)
        check("G7 an unreadable DaVinci record REFUSES with unreadable_record (never silently skipped)",
              plan.refused and plan.refusal_reason == pol.REFUSAL_UNREADABLE and not plan.to_archive,
              str(plan.refusal_reason))
    with tempfile.TemporaryDirectory() as td:
        gen = make_tree(td, ["19", "20"])
        make_tree(td, ["21"], status="archived")
        plan = pol.plan_archive(gen)
        check("G8 an ARCHIVED record at the newest stable major means the baseline is untrusted",
              plan.refused and plan.refusal_reason == pol.REFUSAL_BASELINE_BELOW_ARCHIVED,
              str(plan.refusal_reason))
    with tempfile.TemporaryDirectory() as td:
        gen = make_tree(td, STABLE + ["2026"])
        before = digest(gen)
        code, report = quiet(cli.run, Path(td) / "auxsays", write=True, confirm=True)
        check("G9 a refused plan through the CLI exits 3 and writes NOTHING",
              code == cli.EXIT_REFUSED and digest(gen) == before and report["refused"] is True
              and report["refusal_reason"] == pol.REFUSAL_RANGE, f"code={code}")
        proc = subprocess.run([sys.executable, str(_SCRIPTS / "apply_davinci_archive_policy.py"),
                               "--root", str(Path(td) / "auxsays"), "--write", "--confirm-write"],
                              capture_output=True, text=True)
        check("G10 the subprocess exit status is 3 and stderr NAMES the reason",
              proc.returncode == 3 and pol.REFUSAL_RANGE in proc.stderr, f"rc={proc.returncode}")

    # ============================================================ E: the edit
    print(NL + "[E] the single-line, byte-preserving edit")
    original = rec_text("19.1.4", extra=["note: 'update_status: current is mentioned here'"],
                        body="Body keeps update_status: current untouched.")
    edited = cli.archive_edit(original.encode()).decode()
    diff = [(a, b) for a, b in zip(original.splitlines(), edited.splitlines()) if a != b]
    check("E1 exactly one line changes, and it is the update_status line",
          diff == [("update_status: current", "update_status: archived")] and
          len(original.splitlines()) == len(edited.splitlines()), str(diff))
    check("E2 the body and a quoted mention elsewhere are untouched",
          "Body keeps update_status: current untouched." in edited
          and "update_status: current is mentioned here" in edited)
    crlf = rec_text("19.1.4", eol="\r\n")
    crlf_out = cli.archive_edit(crlf.encode())
    check("E3 CRLF line endings survive byte for byte",
          crlf_out == crlf.replace("update_status: current", "update_status: archived").encode())
    for quoted in ("'current'", '"current"'):
        out = cli.archive_edit(rec_text("19", status=quoted).encode())
        check(f"E4 a quoted {quoted} value is replaced by a plain archived", b"update_status: archived\n" in out)
    for label, text in (
        ("a duplicate key", rec_text("19", extra=["update_status: current"])),
        ("a missing key", rec_text("19", status=None)),
        ("an already-archived value (the ratchet has no un-archive and no re-archive)", rec_text("19", status="archived")),
        ("a foreign status", rec_text("19", status="superseded")),
        ("no front matter", "update_status: current\n"),
        ("an unclosed front matter", "---\nupdate_status: current\n"),
    ):
        try:
            cli.archive_edit(text.encode())
            check(f"E5 {label} is REFUSED by the edit", False)
        except cli.EditError:
            check(f"E5 {label} is REFUSED by the edit", True)

    # ============================================================ I / R / S / Q / C
    print(NL + "[I] idempotence   [R] ratchet   [S] scope   [Q] loader   [C] CLI")
    with tempfile.TemporaryDirectory() as td:
        gen = make_tree(td, STABLE)
        root = Path(td) / "auxsays"
        before = digest(gen)
        dry_code, dry = quiet(cli.run, root, write=False, confirm=False)
        check("C1 the default is a DRY RUN: it plans 13 and writes nothing",
              dry_code == 0 and dry["mode"] == "dry-run" and dry["to_archive_count"] == 13
              and digest(gen) == before)
        half_code, half = quiet(cli.run, root, write=True, confirm=False)
        check("C2 --write without --confirm-write is refused and writes nothing",
              half_code == cli.EXIT_FAILED and digest(gen) == before and "confirm" in half.get("error", ""))
        code1, rep1 = quiet(cli.run, root, write=True, confirm=True)
        after1 = digest(gen)
        check("C3 --write --confirm-write archives exactly the planned records and re-plans to ZERO",
              code1 == 0 and rep1["written"] == 13 and rep1["remaining_after"] == 0
              and sum(1 for p in gen.glob("*.md") if fm(p)["update_status"] == "archived") == 13)
        changed = [n for n in before if before[n] != after1[n]]
        check("C4 only the planned files changed", len(changed) == 13)
        code2, rep2 = quiet(cli.run, root, write=True, confirm=True)
        check("I1 a SECOND apply is a byte no-op", code2 == 0 and digest(gen) == after1
              and rep2.get("written", 0) == 0 and rep2["to_archive_count"] == 0)
        plan3 = pol.plan_archive(gen)
        check("I2 an archived record is counted, not re-planned",
              plan3.already_archived == 13 and not plan3.to_archive)
        for p in gen.glob("*.md"):
            d = fm(p)
            if d["update_status"] == "archived":
                continue
            check(f"R0 active record {d['update_version']} kept status current",
                  d["update_status"] == "current")

    with tempfile.TemporaryDirectory() as td:
        gen = make_tree(td, ["19", "20", "21"])
        # a hand-archived record ABOVE the threshold (20 under stable 21) is held, never reversed
        (gen / "2026-02-02-davinci-resolve-hand.md").write_text(rec_text("20.1", status="archived"),
                                                                encoding="utf-8", newline="")
        before = digest(gen)
        plan = pol.plan_archive(gen)
        check("R1 an archived record the rule would not select is HELD, listed, and never edited",
              [r.version for r in plan.ratchet_held] == ["20.1"] and not plan.refused
              and "20.1" not in [r.version for r in plan.to_archive])
        quiet(cli.run, Path(td) / "auxsays", write=True, confirm=True)
        check("R2 applying leaves the held record byte-identical",
              digest(gen)["2026-02-02-davinci-resolve-hand.md"] == before["2026-02-02-davinci-resolve-hand.md"])
        # the baseline retreats (the 21 stable record disappears): nothing is un-archived
        for p in list(gen.glob("*.md")):
            if fm(p)["update_version"] == "21":
                p.unlink()
        snap = digest(gen)
        quiet(cli.run, Path(td) / "auxsays", write=True, confirm=True)
        check("R3 a lower baseline later NEVER un-archives anything", digest(gen) == snap)
    src = (_SCRIPTS / "lib" / "davinci_archive_policy.py").read_text(encoding="utf-8")
    cli_src = (_SCRIPTS / "apply_davinci_archive_policy.py").read_text(encoding="utf-8")
    writes_new = re.findall(r"new_line = (.*)", cli_src)
    check("R4 the only status value the writer can emit is 'archived' (there is no code path that writes anything else)",
          writes_new == ['b"update_status: archived" + m.group("eol")'], str(writes_new))

    with tempfile.TemporaryDirectory() as td:
        gen = make_tree(td, STABLE)
        make_tree(td, ["10", "11", "12"], product=OBS)
        gen2 = gen
        (gen2 / "2026-03-03-davinci-resolve-notentry.md").write_text(
            rec_text("12", entry=False), encoding="utf-8", newline="")
        (gen2 / "2026-03-04-obs-mention.md").write_text(
            rec_text("12", product=OBS, extra=["related: blackmagic-davinci"]), encoding="utf-8", newline="")
        before = digest(gen)
        quiet(cli.run, Path(td) / "auxsays", write=True, confirm=True)
        after = digest(gen)
        moved = {n for n in before if before[n] != after[n]}
        statuses = {p.name: (fm(p)["product_id"], fm(p)["update_status"]) for p in gen.glob("*.md")}
        check("S1 no OBS record changes, even one that mentions the DaVinci product id",
              all(statuses[n][0] == DAV for n in moved) and
              all(v[1] == "current" for k, v in statuses.items() if v[0] == OBS))
        check("S2 a DaVinci file with update_entry false is not touched",
              statuses["2026-03-03-davinci-resolve-notentry.md"] == (DAV, "current"))
        check("S3 the policy names exactly one product", pol.PRODUCT_ID == DAV)

    with tempfile.TemporaryDirectory() as td:
        gen = make_tree(td, ["19", "20", "21"])
        saved = base.GENERATED_DIR
        base.GENERATED_DIR = gen
        try:
            quiet(cli.run, Path(td) / "auxsays", write=True, confirm=True)
            active = [r.update_version for r in base.generated_records(DAV)]
            everything = [r.update_version for r in base.generated_records(DAV, include_archived=True)]
        finally:
            base.GENERATED_DIR = saved
        check("Q1 generated_records skips archived records by default (so routine collection stops)",
              active == ["20", "21"], str(active))
        check("Q2 ...and a targeted call can still reach them", sorted(everything) == ["19", "20", "21"])

    # ============================================================ X: persistence
    print(NL + "[X] persistence: nothing reactivates an archived record")
    with tempfile.TemporaryDirectory() as td:
        tree = Path(td) / "auxsays" / "updates" / "generated"
        tree.mkdir(parents=True)
        ev = Path(td) / "auxsays" / "_data" / "consensus_evidence.yml"
        write_evidence(ev, [evidence_row("21", i) for i in range(5)])
        arch = tree / "2026-04-14-davinci-resolve-21.md"
        arch.write_text(dav21_record("archived"), encoding="utf-8", newline="")
        before_fm = fm(arch)
        rc = promote(tree, ev)
        after_fm = fm(arch)
        check("X1 consensus writeback keeps version 21 ARCHIVED even with counted evidence (the old hard-coded reactivation)",
              rc == 0 and after_fm["update_status"] == "archived", f"rc={rc} status={after_fm.get('update_status')}")
        check("X2 ...and does not set feed_hidden=False or status_change_type=new on it",
              after_fm["feed_hidden"] is True and after_fm["status_change_type"] == "",
              f"feed_hidden={after_fm.get('feed_hidden')} sct={after_fm.get('status_change_type')!r}")
        check("X3 ...while still rebuilding its count-derived prose (the promotion really ran)",
              after_fm["description"] != before_fm.get("description")
              and "5 user reports" in after_fm["quick_verdict"], str(after_fm.get("description")))
        events_after_first = list(after_fm.get("status_events") or [])
        promote(tree, ev)
        events_after_second = list(fm(arch).get("status_events") or [])
        check("X4 no ARCHIVAL status event: a converged repeat writes none, and none mentions archiving",
              events_after_second == events_after_first
              and not [e for e in events_after_second if "archiv" in json.dumps(e).lower()],
              str(events_after_second))

        ctl = tree / "2026-04-14-davinci-resolve-21.md"
        ctl.write_text(dav21_record("current", feed_hidden=True), encoding="utf-8", newline="")
        promote(tree, ev)
        ctl_fm = fm(ctl)
        check("X5 CONTROL: a CURRENT 21 still gets its stable-release projection (feed_hidden False, status new)",
              ctl_fm["feed_hidden"] is False and ctl_fm["status_change_type"] == "new"
              and ctl_fm["update_status"] == "current", str(ctl_fm.get("status_change_type")))

    # the projection function itself, both directions, and update_status is never a proposed field
    for status, expect_keys in (("archived", False), ("current", True), ("", True)):
        fields = acr._record_coherence_fields(DAV, "21", 5, {"update_product": "DaVinci Resolve", "update_status": status},
                                              Counter(), decision="WAIT")
        check(f"X6 projection for 21 with status {status!r}: never proposes update_status",
              "update_status" not in fields)
        check(f"X7 projection for 21 with status {status!r}: feed_hidden/status_change_type proposed={expect_keys}",
              ("feed_hidden" in fields) == expect_keys and ("status_change_type" in fields) == expect_keys)
    f20 = acr._record_coherence_fields(DAV, "20.3.3", 5, {"update_product": "DaVinci Resolve"}, Counter(), decision="WAIT")
    check("X8 no other version ever had these fields and still does not", not {"update_status", "feed_hidden", "status_change_type"} & set(f20))

    # a layout that hides archived records is what stops feed_hidden/status_change_type resurrecting one
    home = (_AUX / "_layouts" / "aux-home.html").read_text(encoding="utf-8")
    feed = (_AUX / "_layouts" / "aux-updates.html").read_text(encoding="utf-8")
    check("X9 the Home signal list and the Patch Feed 'current' list both gate on update_status != archived BEFORE feed_hidden",
          "item.update_status != 'archived' and item.feed_hidden != true" in home
          and "item.update_status != 'archived' and item.feed_hidden != true" in feed)
    check("X10 no layout, include or script outside the projection reads status_change_type",
          not [str(p.relative_to(_AUX)) for p in list((_AUX / "_layouts").glob("*.html")) + list((_AUX / "_includes").glob("*.html"))
               + list((_AUX / "assets").rglob("*.js")) if "status_change_type" in p.read_text(encoding="utf-8")])

    # official ingestion refresh
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "2026-04-14-davinci-resolve-19.md"
        p.write_text(rec_text("19", status="archived", extra=["update_product: DaVinci Resolve",
                                                              "update_source_name: Blackmagic Design"],
                              body="old"), encoding="utf-8", newline="")
        try:
            outcome = wur.refresh_existing_record(p, {
                "source_last_checked": "2026-11-04T00:00:00Z", "product_id": DAV, "version": "19",
                "body": "New official release notes for this version, long enough to count as a body.",
                "source_url": "https://www.blackmagicdesign.com/support/family/davinci-resolve-and-fusion",
            })
        except Exception as exc:  # noqa: BLE001
            outcome = ("exception", repr(exc))
        d = fm(p)
        check("X11 official-ingestion refresh keeps the record ARCHIVED while refreshing its notes",
              d.get("update_status") == "archived" and "New official release notes" in str(d.get("official_patch_notes_body")),
              f"outcome={outcome} status={d.get('update_status')}")
        check("X12 ...and adds no status_events", "status_events" not in d)

    # record creation writes current; convergence is what archives it again, and cycles are stable
    with tempfile.TemporaryDirectory() as td:
        gen = make_tree(td, ["10", "14", "17", "19", "20", "21", "22", "23"])
        root = Path(td) / "auxsays"
        ev = root / "_data" / "consensus_evidence.yml"
        write_evidence(ev, [evidence_row("21", i) for i in range(4)])
        pre = pol.plan_archive(gen)
        check("X13 a stable 23 makes 21 (and 20) qualify, and nothing refused", majors_of(pre) == [10, 14, 17, 19, 20, 21] and not pre.refused,
              str(majors_of(pre)))
        quiet(cli.run, root, write=True, confirm=True)
        statuses0 = {fm(p)["update_version"]: fm(p)["update_status"] for p in gen.glob("*.md")}
        check("X14 after convergence 21 is archived and 22 / 23 stay current",
              statuses0["21"] == "archived" and statuses0["22"] == "current" and statuses0["23"] == "current")
        snap = None
        stable_cycles = True
        for cycle in range(3):
            # one scheduled cycle: ingestion refresh of the archived 21, consensus writeback, convergence
            f21 = next(p for p in gen.glob("*.md") if fm(p)["update_version"] == "21")
            try:
                wur.refresh_existing_record(f21, {"source_last_checked": f"2026-11-0{cycle + 1}T00:00:00Z",
                                                  "product_id": DAV, "version": "21"})
            except Exception:  # noqa: BLE001 -- a minimal fixture may be refused; the status is what matters
                pass
            promote(gen, ev)
            quiet(cli.run, root, write=True, confirm=True)
            now = {fm(p)["update_version"]: fm(p)["update_status"] for p in gen.glob("*.md")}
            stable_cycles = stable_cycles and now == statuses0
        check("X15 THREE repeated cycles (refresh, writeback, convergence) never reactivate anything", stable_cycles)
        check("X16 and the converged tree plans zero", not pol.plan_archive(gen).to_archive)

    # no status events and a single-line diff for every archived file (real shape)
    with tempfile.TemporaryDirectory() as td:
        gen = make_tree(td, STABLE, extra=["status_events: []", "notification_message: ''"])
        before_text = {p.name: p.read_text(encoding="utf-8") for p in gen.glob("*.md")}
        quiet(cli.run, Path(td) / "auxsays", write=True, confirm=True)
        bad = []
        for p in gen.glob("*.md"):
            a, b = before_text[p.name].splitlines(), p.read_text(encoding="utf-8").splitlines()
            d = [(x, y) for x, y in zip(a, b) if x != y]
            if len(a) != len(b) or (d and d != [("update_status: current", "update_status: archived")]):
                bad.append(p.name)
        check("X17 every edited file differs by exactly the one update_status line; status_events/notification untouched",
              not bad, str(bad[:3]))
        check("X18 the CLI and policy modules never mention a status event or notification writer",
              not re.search(r"status_events|notification_message|status_change_type", src + cli_src.split('"""', 2)[2]))

    # ============================================================ W: the workflow step
    print(NL + "[W] the patch-ingest converge step")
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = wf["jobs"]["ingest"]["steps"]
    names = [st.get("name") for st in steps]
    idx = names.index(STEP_NAME) if STEP_NAME in names else -1
    check("W1 the converge step exists exactly once", names.count(STEP_NAME) == 1)
    ingest_idx = [i for i, n in enumerate(names) if n in ("Run enabled patch ingestion", "Run selected patch ingestion")]
    qa_idx = names.index("Run generated record QA before commit")
    commit_idx = names.index("Commit generated patch records (conflict-safe writeback)")
    check("W2 it runs AFTER both ingestion steps, BEFORE QA and BEFORE the writeback",
          idx >= 0 and all(i < idx for i in ingest_idx) and idx < qa_idx < commit_idx,
          f"ingest={ingest_idx} step={idx} qa={qa_idx} commit={commit_idx}")
    win = names.index("Converge records whose patch identity this run advanced")
    check("W3 it sits with the other converge steps, after the Windows ones", idx > win)
    cond = str(steps[idx].get("if") or "") if idx >= 0 else ""
    cases = {
        ("", "false"): True, (None, "false"): True, (None, ""): True, (None, None): True,
        ("blackmagic-davinci", "false"): True, ("blackmagic-design", "false"): True,
        ("obs-studio", "false"): False, ("microsoft-windows-11", "false"): False,
        ("adobe-premiere-pro", "false"): False, ("microsoft", "false"): False,
        ("", "true"): False, (None, "true"): False, ("blackmagic-davinci", "true"): False,
    }
    wrong = [(k, v) for k, v in cases.items() if idx < 0 or eval_if(cond, k[0], k[1]) != v]
    check("W4 the gate is: routine or DaVinci/Blackmagic dispatch, never an unrelated product, never a dry run",
          not wrong, str(wrong))
    win_cond = str(steps[win].get("if") or "")
    check("W5 it is gated exactly like the Windows converge step apart from the product list",
          "github.event.inputs.dry_run != 'true'" in cond and "github.event.inputs.dry_run != 'true'" in win_cond
          and "github.event.inputs.source == ''" in cond and "github.event.inputs.source == null" in cond)
    run_text = str(steps[idx].get("run") or "") if idx >= 0 else ""
    check("W6 it runs the CLI with BOTH write flags and nothing else",
          "apply_davinci_archive_policy.py --write --confirm-write" in run_text
          and "--root" not in run_text)
    writes = [st for st in steps if "automation_writeback" in str(st.get("run") or "")]
    allow_ok = writes and "--allow auxsays/updates/generated" in str(writes[0].get("run"))
    check("W7 the existing writeback already allows the generated directory, so no new writer or workflow is needed",
          bool(allow_ok))
    wf_dir = _REPO / ".github" / "workflows"
    check("W8 no workflow other than patch-ingest runs the archive CLI",
          [p.name for p in wf_dir.glob("*.yml") if "apply_davinci_archive_policy" in p.read_text(encoding="utf-8")]
          == ["patch-ingest.yml"])

    # execute the shell: refusal is annotated but does not wedge; any other failure fails the step
    bash = bash_exe()
    check("W9 a bash is available to execute the step (not a grep)", bash is not None)
    if bash and run_text:
        def run_step(td: str) -> subprocess.CompletedProcess:
            env = dict(os.environ)
            env["ARCH_ROOT"] = str(Path(td) / "auxsays")
            env["REAL_PY"] = sys.executable.replace("\\", "/")
            script = ('python() { "$REAL_PY" "$@" --root "$ARCH_ROOT"; }; export -f python; set -e; '
                      + run_text)
            return subprocess.run([bash, "-c", script], cwd=str(_REPO), env=env, capture_output=True, text=True)

        with tempfile.TemporaryDirectory() as td:
            gen = make_tree(td, STABLE)
            proc = run_step(td)
            n_arch = sum(1 for p in gen.glob("*.md") if fm(p)["update_status"] == "archived")
            check("W10 EXECUTED on a scratch tree: the step succeeds and archives 13", proc.returncode == 0 and n_arch == 13,
                  f"rc={proc.returncode} archived={n_arch} err={proc.stderr[-200:]}")
            snap = digest(gen)
            proc2 = run_step(td)
            check("W11 EXECUTED again: still success, and a byte no-op", proc2.returncode == 0 and digest(gen) == snap)
        with tempfile.TemporaryDirectory() as td:
            gen = make_tree(td, STABLE + ["2026"])
            snap = digest(gen)
            proc = run_step(td)
            check("W12 EXECUTED with a refusal: the step exits 0 (ingestion's results still land), says why, writes nothing",
                  proc.returncode == 0 and digest(gen) == snap and pol.REFUSAL_RANGE in proc.stderr
                  and "refused" in proc.stdout.lower(), f"rc={proc.returncode} out={proc.stdout[-200:]}")
        with tempfile.TemporaryDirectory() as td:
            gen = make_tree(td, STABLE)
            victim = sorted(gen.glob("*.md"))[0]
            victim.write_text(rec_text("10", extra=["update_status: current"]), encoding="utf-8", newline="")
            snap = digest(gen)
            proc = run_step(td)
            check("W13 EXECUTED with an edit failure (duplicate key): the step FAILS and nothing is written",
                  proc.returncode == 1 and digest(gen) == snap, f"rc={proc.returncode}")

    # ============================================================ N: the notice
    print(NL + "[N] the archived notice")
    inc_src = INCLUDE.read_text(encoding="utf-8")
    line = layout_include_line()
    layout_src = LAYOUT.read_text(encoding="utf-8")
    check("N1 aux-update.html contains exactly ONE archived-notice include line",
          len(re.findall(r"include\s+archived-notice\.html", layout_src)) == 1 and bool(line))
    verdict_at = layout_src.find('id="verdict"')
    check("N2 the include sits prominently ABOVE the decision content", 0 <= layout_src.find(line) < verdict_at,
          f"include@{layout_src.find(line)} verdict@{verdict_at}")
    check("N3 it passes the record's product_id and update_status",
          re.search(r"product_id=page\.product_id", line) and re.search(r"update_status=page\.update_status", line))
    check("N4 the include never uses the Liquid `blank` keyword and has no tag inside its comment",
          not re.search(r"[!=]=\s*blank\b", inc_src)
          and not re.search(r"\{%|\{\{", re.search(r"\{%-?\s*comment\s*-?%\}(.*?)\{%-?\s*endcomment", inc_src, re.S).group(1)))
    tpl = expand_include(line, inc_src)
    jobs = {
        "arch": {"template": tpl, "vars": {"page": {"product_id": DAV, "update_status": "archived"}}},
        "arch_ws": {"template": tpl, "vars": {"page": {"product_id": DAV, "update_status": " Archived "}}},
        "cur": {"template": tpl, "vars": {"page": {"product_id": DAV, "update_status": "current"}}},
        "none": {"template": tpl, "vars": {"page": {"product_id": DAV}}},
        "obs": {"template": tpl, "vars": {"page": {"product_id": OBS, "update_status": "archived"}}},
        "nopid": {"template": tpl, "vars": {"page": {"update_status": "archived"}}},
        "wiring_probe": {"template": tpl, "vars": {"page": {"product_id": DAV, "update_status": "archived",
                                                            "status": "current"}}},
    }
    ok, out = render_all(jobs)
    check("N5 the liquid gem is available, so the render assertions run for real", ok, str(out.get("_stderr", "")))
    if ok:
        check("N6 an archived DaVinci page renders the notice with GPT's exact wording",
              visible_text(out["arch"]) == NOTICE, visible_text(out["arch"]))
        check("N7 the status comparison is whitespace- and case-insensitive", visible_text(out["arch_ws"]) == NOTICE)
        check("N8 a CURRENT DaVinci page renders nothing", out["cur"].strip() == "", repr(out["cur"][:80]))
        check("N9 a DaVinci page with no status renders nothing", out["none"].strip() == "")
        check("N10 an archived OBS page renders nothing (DaVinci-scoped)", out["obs"].strip() == "")
        check("N11 a page with no product renders nothing", out["nopid"].strip() == "")
        check("N12 the output is a labelled note region", 'role="note"' in out["arch"] and "<aside" in out["arch"])
        check("N13 no Liquid error text leaks into any render", not any("<<ERR" in v or "Liquid error" in v for v in out.values()),
              str({k: v[:60] for k, v in out.items() if "ERR" in v}))

    # ============================================================ K: the real corpus
    print(NL + "[K] the real corpus")
    real_gen = _AUX / "updates" / "generated"
    recs, unreadable = pol.load_records(real_gen)
    ev_rows = load_evidence_store(_AUX / "_data" / "consensus_evidence.yml")
    counts = counted_evidence_counts(ev_rows, windows_targets={})
    plan = pol.plan_records(recs, unreadable=unreadable)
    check("K1 all DaVinci records on disk parse and none is unreadable",
          len(recs) >= 122 and not unreadable and not plan.unparsed, f"{len(recs)} {unreadable[:2]}")
    check("K2 the real corpus is not refused", not plan.refused, str(plan.refusal_reason))
    qualifying = [r for r in recs if r.major is not None and plan.threshold_major is not None and r.major <= plan.threshold_major]
    check("K3 against stable 21, EXACTLY 100 records qualify (planned now, or already archived by the writer)",
          plan.newest_stable_major != 21 or len(qualifying) == 100, f"{len(qualifying)} at newest={plan.newest_stable_major}")
    check("K4 every qualifying record is either planned or already archived",
          len(plan.to_archive) + sum(1 for r in qualifying if r.status == "archived") == len(qualifying))
    with_ev = [r for r in qualifying if counts.get((DAV, r.version, ""), 0) > 0]
    reports = sum(counts.get((DAV, r.version, ""), 0) for r in qualifying)
    check("K5 against stable 21, 7 qualifying records carry counted evidence (22 reports) -- the measured basis; later evidence may only add",
          plan.newest_stable_major != 21 or (len(with_ev) >= 7 and reports >= 22), f"{len(with_ev)} records {reports} reports")
    check("K6 20.x, 21.x and the 21 beta are NOT qualifying while stable 21 is newest",
          plan.newest_stable_major != 21 or not [r for r in qualifying if r.major >= 20])
    with tempfile.TemporaryDirectory() as td:
        scratch = Path(td) / "auxsays" / "updates" / "generated"
        scratch.mkdir(parents=True)
        for r in recs:
            shutil.copy2(r.path, scratch / r.path.name)
        # normalise to the pre-writer state so this guard stays meaningful after the real writer
        # has archived the 100: put every qualifying record back to 'current' in the COPY only.
        for r in qualifying:
            f = scratch / r.path.name
            raw = f.read_bytes()
            if b"\nupdate_status: archived" in raw:
                f.write_bytes(raw.replace(b"\nupdate_status: archived", b"\nupdate_status: current", 1))
        pre = digest(scratch)
        scratch_plan = pol.plan_archive(scratch)
        check("K7 on a scratch copy of the corpus the plan selects every qualifying record",
              len(scratch_plan.to_archive) == len(qualifying), f"{len(scratch_plan.to_archive)} vs {len(qualifying)}")
        code, rep = quiet(cli.run, Path(td) / "auxsays", write=True, confirm=True)
        check("K8 applying to the scratch copy leaves ZERO remaining and exits 0",
              code == 0 and rep["remaining_after"] == 0 and rep["written"] == len(qualifying), str(rep.get("error")))
        post = digest(scratch)
        # compare line-by-line against the pre-state we reconstructed
        diffs_ok = True
        for r in qualifying:
            now = (scratch / r.path.name).read_text(encoding="utf-8").splitlines()
            orig = r.path.read_text(encoding="utf-8").splitlines()
            orig = ["update_status: current" if x == "update_status: archived" else x for x in orig]
            delta = [(x, y) for x, y in zip(orig, now) if x != y]
            if len(orig) != len(now) or delta != [("update_status: current", "update_status: archived")]:
                diffs_ok = False
        check("K9 each applied file differs from its pre-state by exactly the one update_status line", diffs_ok)
        check("K10 non-qualifying DaVinci records are byte-identical", all(
            pre[r.path.name] == post[r.path.name] for r in recs if r not in qualifying))
        code2, rep2 = quiet(cli.run, Path(td) / "auxsays", write=True, confirm=True)
        check("K11 a second apply to the scratch copy is a byte no-op", code2 == 0 and digest(scratch) == post)
        # counts, verdict, evidence, URLs, citations are untouched on every applied file
        untouched = True
        for r in qualifying:
            a, b = fm(r.path), fm(scratch / r.path.name)
            a["update_status"] = b["update_status"] = None
            if a != b:
                untouched = False
        check("K12 every other front-matter field of every applied file (counts, verdict, evidence, URLs, citations) is identical",
              untouched)

    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        print(f"Results: {_PASS}/{_PASS + _FAIL + 1} passed, {_FAIL + 1} failed")
        sys.exit(1)
