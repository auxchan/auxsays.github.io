#!/usr/bin/env python3
"""A stored evidence row may not disappear, and may stop being accepted only by an audited withdrawal.

THE DEFECT. Delete 241 of the 246 DaVinci evidence rows, keep the five a test happened to name, run
the lane's own `apply_consensus_to_records.py --write-all --confirm-write`, and every automatic gate
passed: qa_patch_records 0 errors, audit_consensus_evidence exit 0, the full governed suite green --
and the real automation_writeback pushed it. Each of those gates compares the generated records
against the SAME store the purge rewrote, so each confirms consistency by construction. Nothing in
the repository compared the store with what it replaced.

Two historical count floors (`len(dv) >= 234`, `count_of(resolve-20) >= 26`) used to catch the crude
version of this for one product, by accident: they were pinned to the day #82 landed, so they also
failed on legitimate withdrawal. This suite asserts the property they were standing in for, for
every product, with no count of the live corpus anywhere:

    a row in the base store is still accounted for in the candidate -- accepted, or withdrawn in
    place with `counted: false` and a non-empty `exclusion_reason`.

Sections
  [P] the predicate, on immutable fixtures      (counts are asserted ONLY here, on fixtures)
  [W] the real automation_writeback, end to end  (a throwaway bare origin; nothing leaves the temp dir)
  [K] the pull-request check, check_evidence_loss.py
  [Y] the ci-integrity step, EXECUTED against a stubbed git and python -- not grepped
  [C] ci-integrity concurrency, EVALUATED per event: a push's window is never cancelled away
  [L] the live store, read-only: the predicate parses it and live purges are refused, with no count
      of the store pinned and no product assumed

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_evidence_loss_guard.py
REQUIRES: git, and bash for [Y]. If bash is missing the suite fails loudly, never vacuously.
"""
from __future__ import annotations

import ast
import contextlib
import copy
import io
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import yaml  # noqa: E402

import check_evidence_loss as cli  # noqa: E402
from lib import automation_writeback as aw  # noqa: E402
from lib import evidence_loss as el  # noqa: E402

NEWLINE = chr(10)
_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []

WORKFLOW = _REPO / ".github" / "workflows" / "ci-integrity.yml"
STEP_NAME = "Refuse unexplained evidence loss"
FIXTURE_EVIDENCE = "data/consensus_evidence.yml"


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        _ERRORS.append(label)
        print(f"  FAIL  {label}" + (f"{NEWLINE}        {detail}" if detail else ""))


# --------------------------------------------------------------------------------------------------
# Immutable fixtures. Every count this suite asserts is a count of THESE rows, defined here, never
# of _data/consensus_evidence.yml.
# --------------------------------------------------------------------------------------------------
def row(pid: str, ver: str, n: int, *, counted: bool = True, pvm: bool = True,
        reason: str | None = None, build: str | None = None, url: str | None = None,
        rid: str | None = None, **extra) -> dict:
    r = {
        "id": rid or f"{pid}-{ver}-fixture-report-{n}",
        "product_id": pid,
        "update_version": ver,
        "source_url": url or f"https://forum.example.test/{pid}/{ver}/thread-{n}/",
        "report_title": f"Resolve {ver} crashes on export ({n})",
        "counted": counted,
        "patch_version_matched": pvm,
        "exclusion_reason": reason,
        "severity": "high",
    }
    if build is not None:
        r["target_build"] = build
    r.update(extra)
    return r


def fixture_base() -> list[dict]:
    rows = [row("blackmagic-davinci", ("19", "20", "21")[n % 3], n) for n in range(50)]
    rows += [row("obs-studio", "32.2.1", n) for n in range(5)]
    # Windows sibling-build rows: identical (product, version, id, url), distinguished ONLY by build.
    sib_url = "https://answers.example.test/windows/25h2/thread-7/"
    rows += [row("microsoft-windows-11", "25H2", 7, url=sib_url, build=b,
                 rid="microsoft-windows-11-25h2-sibling-7")
             for b in ("26200.9168", "26200.9278", "26200.9445")]
    # Two rows already withdrawn the audited way -- tombstones.
    rows += [row("blackmagic-davinci", "16", 900, counted=False, reason="cross_patch_duplicate"),
             row("obs-studio", "32.2.0", 901, counted=False, reason="version_named_but_working")]
    return rows


def dump(rows: list[dict]) -> str:
    return yaml.safe_dump({"schema_version": 1, "evidence": rows}, sort_keys=False,
                          allow_unicode=True, width=10**6)


def codes(losses) -> set[str]:
    return {l.code for l in losses}


def rows_of(losses, code: str | None = None) -> int:
    return sum(l.rows for l in losses if code is None or l.code == code)


def dv(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["product_id"] == "blackmagic-davinci" and el.is_accepted(r)]


# --------------------------------------------------------------------------------------------------
# [P] the predicate
# --------------------------------------------------------------------------------------------------
def section_predicate() -> None:
    print(NEWLINE + "[P] the predicate, on immutable fixtures")
    base = fixture_base()
    n_dv = len(dv(base))
    check("P fixture sanity: 50 accepted DaVinci rows, 60 rows in all",
          n_dv == 50 and len(base) == 60, f"{n_dv} / {len(base)}")
    check("P an unchanged store loses nothing", el.find_unexplained_losses(base, base) == [])

    # A -- growth
    grown = base + [row("blackmagic-davinci", "21", 100 + n) for n in range(5)]
    check("P [A] legitimate growth is never a loss", el.find_unexplained_losses(base, grown) == [])

    # B -- the audited withdrawal the repository actually uses
    cand = copy.deepcopy(base)
    cand[3]["counted"] = False
    cand[3]["exclusion_reason"] = "version_named_but_working"
    check("P [B] withdrawing a row in place with counted:false + exclusion_reason passes",
          el.find_unexplained_losses(base, cand) == [])
    many = copy.deepcopy(base)
    for r in dv(many)[:20]:
        r["counted"] = False
        r["exclusion_reason"] = "vendor_release_announcement"
    check("P [B] a LARGE audited withdrawal still passes -- no percentage threshold exists",
          el.find_unexplained_losses(base, many) == [])

    # D -- silent deletion of a substantial set
    gone = {id(r) for r in dv(base)[:20]}
    cand = [r for r in base if id(r) not in gone]
    losses = el.find_unexplained_losses(base, cand)
    check("P [D] silently deleting 20 accepted DaVinci rows is refused as removal",
          codes(losses) == {el.REMOVED} and rows_of(losses) == 20,
          f"{codes(losses)} rows={rows_of(losses)}")

    # E -- the reviewer's purge: 98% of DaVinci, keeping a handful
    keep = {id(r) for r in dv(base)[:1]}
    cand = [r for r in base if r["product_id"] != "blackmagic-davinci" or id(r) in keep
            or not el.is_accepted(r)]
    losses = el.find_unexplained_losses(base, cand)
    check("P [E] deleting 49 of 50 DaVinci rows is refused, every row named",
          codes(losses) == {el.REMOVED} and rows_of(losses) == 49,
          f"{codes(losses)} rows={rows_of(losses)}")
    check("P [E] and only DaVinci is blamed -- the untouched products report nothing",
          {l.product_id for l in losses} == {"blackmagic-davinci"})

    # The shapes that must still be refused even though no row was deleted.
    cand = copy.deepcopy(base)
    cand[5]["counted"] = False
    losses = el.find_unexplained_losses(base, cand)
    check("P an accepted row flipped to counted:false with NO reason is unaudited",
          codes(losses) == {el.UNAUDITED} and rows_of(losses) == 1, str(codes(losses)))
    cand = copy.deepcopy(base)
    cand[5]["counted"] = False
    cand[5]["exclusion_reason"] = "   "
    check("P a whitespace-only exclusion_reason is not a reason",
          codes(el.find_unexplained_losses(base, cand)) == {el.UNAUDITED})
    cand = copy.deepcopy(base)
    cand[5]["patch_version_matched"] = False
    check("P losing patch_version_matched without a reason is unaudited",
          codes(el.find_unexplained_losses(base, cand)) == {el.UNAUDITED})
    cand = copy.deepcopy(base)
    tomb = next(r for r in cand if r.get("exclusion_reason") == "cross_patch_duplicate")
    tomb["exclusion_reason"] = None
    check("P blanking an existing withdrawal's reason is unaudited -- the audit trail is protected",
          codes(el.find_unexplained_losses(base, cand)) == {el.UNAUDITED})

    # Flip-then-delete: each step judged against the one before it.
    step1 = copy.deepcopy(base)
    step1[8]["counted"] = False
    step1[8]["exclusion_reason"] = "version_named_but_working"
    step2 = [r for r in step1 if r is not step1[8]]
    check("P flip-then-delete: step 1 (the audited flip) passes",
          el.find_unexplained_losses(base, step1) == [])
    check("P flip-then-delete: step 2 (deleting the tombstone) is refused",
          codes(el.find_unexplained_losses(step1, step2)) == {el.REMOVED})

    # Identity: target_build restamps (#110/#112/#113) are not losses; sibling deletions are.
    cand = copy.deepcopy(base)
    for r in cand:
        if r["product_id"] == "microsoft-windows-11":
            r["target_build"] = ""
    check("P restamping target_build in place (the #110 shape) is not a loss",
          el.find_unexplained_losses(base, cand) == [])
    sibs = [r for r in base if r["product_id"] == "microsoft-windows-11"]
    cand = [r for r in base if r is not sibs[1]]
    losses = el.find_unexplained_losses(base, cand)
    check("P deleting ONE of three sibling-build rows is caught -- a multiset, not a dict",
          codes(losses) == {el.REMOVED} and rows_of(losses) == 1, f"rows={rows_of(losses)}")
    cand = copy.deepcopy(base)
    cand[10]["update_version"] = "22"
    check("P re-attributing a row to another version is a removal from the version it left",
          el.REMOVED in codes(el.find_unexplained_losses(base, cand)))

    # Deliberate non-goals -- asserted, so they cannot quietly become goals.
    cand = copy.deepcopy(base)
    cand[12]["severity"] = "low"
    cand[12]["report_title"] = "retitled by a classification pass"
    check("P a classification edit is not a loss (no immutability rule)",
          el.find_unexplained_losses(base, cand) == [])
    cand = copy.deepcopy(base)
    tomb = next(r for r in cand if r.get("exclusion_reason") == "version_named_but_working")
    tomb["counted"] = True
    tomb["exclusion_reason"] = None
    check("P re-accepting a withdrawn row is not a LOSS (precision owns that, not this rule)",
          el.find_unexplained_losses(base, cand) == [])

    # Raw parsing, fail-closed reading.
    check("P a missing `counted` key reads as accepted, not as False (no normalizer)",
          el.is_accepted({"patch_version_matched": True}))
    check("P an empty base has nothing to lose",
          el.losses_between("", dump(base)) == [] and el.losses_between(None, dump(base)) == [])
    losses = el.losses_between(dump(base), None)
    check("P a DELETED store reports every base row as removed",
          rows_of(losses, el.REMOVED) == len(base), f"{rows_of(losses)} of {len(base)}")
    check("P a store with no `evidence` key and non-mapping entries is tolerated",
          el.parse_store("evidence_count: 1\n") == [] and
          el.parse_store("evidence:\n  - x\n  - {id: a}\n") == [{"id": "a"}])
    for label, text in (("invalid YAML", "evidence: [unterminated\n"),
                        ("a top-level list", "- a\n- b\n"),
                        ("`evidence` that is not a list", "evidence: 3\n"),
                        # The constructor, not the parser, rejects these -- as a plain ValueError.
                        ("an unbuildable timestamp", "evidence:\n- id: a\n  captured_at: 2026-13-45\n"),
                        ("an unbuildable explicit tag", "evidence:\n- id: a\n  n: !!int x\n")):
        try:
            el.parse_store(text)
            outcome = "read as a store"
        except el.EvidenceStoreUnreadable:
            outcome = "unreadable"
        except Exception as exc:  # noqa: BLE001 - an escaping exception IS the defect checked for
            outcome = f"escaped as {type(exc).__name__}"
        check(f"P {label} raises EvidenceStoreUnreadable rather than reading as empty",
              outcome == "unreadable", outcome)
    with tempfile.TemporaryDirectory() as td:
        script = Path(td, "deep_parse.py")
        script.write_text(_DEEP_PARSE, encoding="utf-8")
        p = subprocess.run([sys.executable, str(script), str(_REPO / "auxsays" / "scripts"), "100000"],
                           capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        check("P a store nested 100k levels deep is unreadable -- not a hard crash of the interpreter",
              p.returncode == 0 and p.stdout.strip() == "UNREADABLE",
              f"rc={p.returncode} stdout={p.stdout.strip()!r} (0xC00000FD / 0x80000001 = C stack overflow)")
    check("P public_reason is bounded and names the rule",
          el.EvidenceLoss(el.REMOVED, "p" * 500, "v", "i" * 900, "u", 1, "d").public_reason()
          .startswith("code=evidence_row_removed")
          and len(el.EvidenceLoss(el.REMOVED, "p" * 500, "v", "i" * 900, "u", 1, "d")
                  .public_reason()) < 320)


# --------------------------------------------------------------------------------------------------
# [W] the real automation_writeback
# --------------------------------------------------------------------------------------------------
def g(repo: Path, *args: str, check_rc: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if check_rc and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} -> {p.returncode}: {p.stderr}")
    return p


def write(repo: Path, rel: str, content: str) -> None:
    fp = repo / rel
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content, encoding="utf-8", newline="\n")


def setup_origin(tmp: Path, base_rows: list[dict]) -> tuple[Path, Path]:
    origin = tmp / "origin.git"
    g(tmp, "init", "--bare", "-b", "main", str(origin))
    seed = tmp / "seed"
    g(tmp, "clone", str(origin), str(seed))
    g(seed, "config", "user.name", "seed")
    g(seed, "config", "user.email", "seed@x")
    write(seed, FIXTURE_EVIDENCE, dump(base_rows))
    write(seed, "records/davinci-resolve-20.md", f"update_report_count: {len(dv(base_rows))}\n")
    write(seed, "records/obs.md", "obs\n")
    g(seed, "add", "-A")
    g(seed, "commit", "-m", "seed")
    g(seed, "push", "origin", "main")
    work = tmp / "work"
    g(tmp, "clone", str(origin), str(work))
    return origin, work


def wb_cfg(work: Path, **kw) -> aw.WritebackConfig:
    base = dict(repo=work, message="Update automated patch evidence",
                allow=[FIXTURE_EVIDENCE, "records/*.md"], validate=[], max_retries=2,
                branch="main", remote="origin", pages_cmd=None, sleep_fn=lambda s: None,
                evidence_path=FIXTURE_EVIDENCE)
    base.update(kw)
    return aw.WritebackConfig(**base)


def quiet_writeback(cfg: aw.WritebackConfig) -> aw.WritebackResult:
    with contextlib.redirect_stdout(io.StringIO()):
        return aw.run_writeback(cfg)


# A concurrent human push that moves the store elsewhere, fired just before the lane's own push.
_UPSTREAM_RENAME = r'''
import subprocess, sys
other = sys.argv[1]
def g(*a):
    subprocess.run(["git", "-C", other, *a], check=True, capture_output=True)
g("fetch", "-q", "origin", "main")
g("reset", "-q", "--hard", "origin/main")
g("mv", "data/consensus_evidence.yml", "records/zz-evidence-archive.md")
g("-c", "user.name=up", "-c", "user.email=up@x", "commit", "-q", "-m", "upstream moves the store")
g("push", "-q", "origin", "main")
'''

# A concurrent human push that EDITS a file the lane is about to rename.
_UPSTREAM_EDIT = r'''
import subprocess, sys
from pathlib import Path
other = sys.argv[1]
def g(*a):
    subprocess.run(["git", "-C", other, *a], check=True, capture_output=True)
g("fetch", "-q", "origin", "main")
g("reset", "-q", "--hard", "origin/main")
p = Path(other, "records", "long.md")
lines = p.read_text(encoding="utf-8").splitlines()
lines[0] = "HUMAN EDIT upstream"
p.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
g("-c", "user.name=up", "-c", "user.email=up@x", "commit", "-q", "-am", "upstream edits long.md")
g("push", "-q", "origin", "main")
'''

# parse_store on a pathologically nested store, in its OWN process: a loader that overflows the C
# stack kills the interpreter with no Python exception, and must not take this suite down with it.
_DEEP_PARSE = r'''
import sys
sys.path.insert(0, sys.argv[1])
from lib import evidence_loss as el
depth = int(sys.argv[2])
text = "evidence:\n- id: a\n  x: " + "[" * depth + "]" * depth + "\n"
try:
    el.parse_store(text)
    print("PARSED")
except el.EvidenceStoreUnreadable:
    print("UNREADABLE")
'''


def run_writeback_script(work: Path, allow: list[str]) -> tuple[int, list[str], str]:
    """automation_writeback.py executed as a BARE SCRIPT, exactly as every writer workflow runs it.
    In-process tests import it as `lib.automation_writeback`, where `__package__` is set, so they
    can never see an import that only resolves in package mode."""
    cmd = [sys.executable, str(_REPO / "auxsays" / "scripts" / "lib" / "automation_writeback.py"),
           "--repo", str(work), "--message", "Update automated patch evidence"]
    for a in allow:
        cmd += ["--allow", a]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    # The CLI's main() appends its outcome to $GITHUB_OUTPUT whenever that is set -- and the Actions
    # runner sets it for the step running this suite. That file is outside the checkout, so the
    # runner's tree guard cannot see a write to it. A test must leave Actions state alone.
    for var in ("GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY", "GITHUB_ENV"):
        env.pop(var, None)
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
    outcomes = [ln.split(": ", 1)[1].strip() for ln in p.stdout.splitlines()
                if ln.startswith("WRITEBACK_OUTCOME: ")]
    return p.returncode, outcomes, p.stdout + p.stderr


def setup_production_layout(tmp: Path, base_rows: list[dict]) -> tuple[Path, Path]:
    """Like setup_origin, but the store sits at its PRODUCTION path: the writeback CLI deliberately
    offers no way to re-aim the gate, so a bare-script run can only protect the real location."""
    origin = tmp / "origin.git"
    g(tmp, "init", "--bare", "-b", "main", str(origin))
    seed = tmp / "seed"
    g(tmp, "clone", str(origin), str(seed))
    g(seed, "config", "user.name", "seed")
    g(seed, "config", "user.email", "seed@x")
    write(seed, el.EVIDENCE_PATH, dump(base_rows))
    g(seed, "add", "-A")
    g(seed, "commit", "-m", "seed")
    g(seed, "push", "origin", "main")
    work = tmp / "work"
    g(tmp, "clone", str(origin), str(work))
    return origin, work


def section_writeback() -> None:
    print(NEWLINE + "[W] the real automation_writeback, against a throwaway bare origin")
    check("W the writeback protects the same store the predicate is written for",
          aw.EVIDENCE_PATH == el.EVIDENCE_PATH, f"{aw.EVIDENCE_PATH!r} != {el.EVIDENCE_PATH!r}")
    check("W production writeback configs are never built with the gate aimed elsewhere",
          aw.WritebackConfig(repo=Path("."), message="m", allow=[]).evidence_path == el.EVIDENCE_PATH)
    # No production WritebackConfig(...) may pass evidence_path= -- that would re-aim or disable the
    # gate. An AST walk of the calls themselves, not a grep: `evidence_path` is also an ordinary
    # keyword across the collectors (write_evidence(evidence_path=...)), and a comment or string
    # naming it must not satisfy or trip this either.
    offenders, sites = [], 0
    for py in sorted((_REPO / "auxsays" / "scripts").rglob("*.py")):
        if "tests" in py.parts:
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else ""
            if name != "WritebackConfig":
                continue
            sites += 1
            if any(k.arg == "evidence_path" or k.arg is None for k in node.keywords):
                offenders.append(f"{py.relative_to(_REPO).as_posix()}:{node.lineno}")
    # sites >= 1 keeps this from passing vacuously if the constructor were ever renamed; it does not
    # pin how many call sites there are.
    check("W no production WritebackConfig(...) overrides evidence_path (or splats **kwargs)",
          sites >= 1 and not offenders, f"sites={sites} offenders={offenders}")

    base = fixture_base()

    # [E] through the real pipeline -- with the davinci-updates.yml flags: NO --validate, NO
    # --validate-before-commit. This is the lane that ran zero validators on the purge.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup_origin(tmp, base)
        before = g(origin, "rev-parse", "main").stdout.strip()
        keep = {id(r) for r in dv(base)[:1]}
        purged = [r for r in base if r["product_id"] != "blackmagic-davinci" or id(r) in keep
                  or not el.is_accepted(r)]
        write(work, FIXTURE_EVIDENCE, dump(purged))
        # ...and the records regenerated to match, so everything downstream is self-consistent.
        write(work, "records/davinci-resolve-20.md", f"update_report_count: {len(dv(purged))}\n")
        head_before = g(work, "rev-parse", "HEAD").stdout.strip()
        r = quiet_writeback(wb_cfg(work, validate=[], validate_before_commit=False))
        check("W [E] a coherent 98% purge is REFUSED by the real writeback, with no validators "
              "configured (the davinci-updates.yml shape)",
              r.outcome == aw.EVIDENCE_LOSS_REFUSED, f"outcome={r.outcome}")
        check("W [E] nothing was committed", g(work, "rev-parse", "HEAD").stdout.strip() == head_before)
        check("W [E] nothing was pushed -- origin is byte-for-byte where it was",
              g(origin, "rev-parse", "main").stdout.strip() == before and not r.pushed)
        check("W [E] the index is reset, so no half-staged purge is left behind",
              g(work, "diff", "--cached", "--name-only").stdout.strip() == "")
        check("W [E] the refusal names the losses in the run summary",
              r.evidence_losses and all(x.startswith("code=evidence_row_removed")
                                        for x in r.evidence_losses[:-1])
              and "evidence_losses" in r.as_dict(), str(r.evidence_losses[:2]))
        check("W [E] a long refusal is capped and states how much it elided",
              len(r.evidence_losses) <= aw.MAX_REPORTED_LOSSES + 1
              and "more identities" in r.evidence_losses[-1], r.evidence_losses[-1])

    # The gate runs BEFORE the validators, so a lane that does validate first cannot be reached by
    # a purge either -- and a validator that happens to pass cannot wave one through.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup_origin(tmp, base)
        write(work, FIXTURE_EVIDENCE, dump([r for r in base if id(r) not in {id(x) for x in dv(base)[:20]}]))
        ok = f'"{sys.executable}" -c "import sys; sys.exit(0)"'
        r = quiet_writeback(wb_cfg(work, validate=[ok], validate_before_commit=True))
        check("W [D] a silent 20-row deletion is refused even when every validator would pass",
              r.outcome == aw.EVIDENCE_LOSS_REFUSED and r.validation == [],
              f"outcome={r.outcome} validation={r.validation}")

    # [A] and [B] go through, so the gate costs a legitimate lane nothing.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup_origin(tmp, base)
        write(work, FIXTURE_EVIDENCE, dump(base + [row("blackmagic-davinci", "21", 200)]))
        r = quiet_writeback(wb_cfg(work))
        check("W [A] ordinary growth is committed and pushed",
              r.pushed and r.outcome != aw.EVIDENCE_LOSS_REFUSED, f"outcome={r.outcome}")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup_origin(tmp, base)
        cand = copy.deepcopy(base)
        cand[4]["counted"] = False
        cand[4]["exclusion_reason"] = "multiple_builds_named_target_not_blamed"
        write(work, FIXTURE_EVIDENCE, dump(cand))
        r = quiet_writeback(wb_cfg(work))
        check("W [B] an audited in-place withdrawal is committed and pushed",
              r.pushed and r.outcome != aw.EVIDENCE_LOSS_REFUSED, f"outcome={r.outcome}")

        # ...and the tombstone it created is itself protected on the NEXT run.
        cand2 = [x for i, x in enumerate(cand) if i != 4]
        write(work, FIXTURE_EVIDENCE, dump(cand2))
        r2 = quiet_writeback(wb_cfg(work))
        check("W flip-then-delete across two runs: deleting the tombstone is refused",
              r2.outcome == aw.EVIDENCE_LOSS_REFUSED, f"outcome={r2.outcome}")

    # Deleting the store outright, and a store that no longer parses, are both refusals.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup_origin(tmp, base)
        (work / FIXTURE_EVIDENCE).unlink()
        r = quiet_writeback(wb_cfg(work))
        check("W deleting the evidence store itself is refused",
              r.outcome == aw.EVIDENCE_LOSS_REFUSED, f"outcome={r.outcome}")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup_origin(tmp, base)
        write(work, FIXTURE_EVIDENCE, "evidence: [this is not yaml\n")
        r = quiet_writeback(wb_cfg(work))
        check("W an unreadable candidate store fails CLOSED, never read as empty",
              r.outcome == aw.EVIDENCE_LOSS_REFUSED
              and r.evidence_losses and r.evidence_losses[0].startswith(f"code={el.UNREADABLE}"),
              f"outcome={r.outcome} {r.evidence_losses}")

    # Git's rename detection must not hide the store's deletion. With it on, deleting the store while
    # adding a >=50%-similar file under an allowed glob listed only the DESTINATION, the gate never saw
    # the store path, and a main with no store at all was pushed.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup_origin(tmp, base)
        before = g(origin, "rev-parse", "main").stdout.strip()
        text = (work / FIXTURE_EVIDENCE).read_text(encoding="utf-8")
        (work / FIXTURE_EVIDENCE).unlink()
        write(work, "records/zz-evidence-archive.md", text[: int(len(text) * 0.8)])
        g(work, "add", "-A")
        renamed = "R" in g(work, "diff", "--cached", "--name-status").stdout.split()[0][:1]
        g(work, "reset", "-q")
        r = quiet_writeback(wb_cfg(work))
        check("W a store 'renamed' into an allowed path (git sees a rename) is still refused as a loss",
              renamed and r.outcome == aw.EVIDENCE_LOSS_REFUSED
              and g(origin, "rev-parse", "main").stdout.strip() == before,
              f"git saw a rename: {renamed}; outcome={r.outcome}")
    # The same one-line fix closes the same blind spot in the allow gate: a tracked file OUTSIDE the
    # allow list, renamed INTO an allowed glob by an earlier step (`git mv` pre-stages both sides),
    # used to show only its allowed destination. The writeback's own `git add -- <allow>` would never
    # stage that deletion, so the rename has to arrive pre-staged for the hole to exist at all.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup_origin(tmp, base)
        seed_extra = tmp / "seed"
        write(seed_extra, "docs/handbook.md", "handbook\n" * 200)
        g(seed_extra, "add", "-A"); g(seed_extra, "commit", "-m", "add a tracked, non-allowed file")
        g(seed_extra, "push", "origin", "main")
        g(work, "pull", "--quiet", "origin", "main")
        g(work, "mv", "docs/handbook.md", "records/handbook.md")
        r = quiet_writeback(wb_cfg(work))
        check("W a non-allowed tracked file renamed INTO an allowed glob is refused by the allow gate",
              r.outcome == aw.UNEXPECTED_CHANGED_PATH and "docs/handbook.md" in r.conflicting_paths,
              f"outcome={r.outcome} conflicting={r.conflicting_paths}")

    # The rebase must see both sides of an upstream rename too, or its "upstream touched the store,
    # refuse" rule never fires: merge-ort follows the rename, this lane's rows are replayed into the
    # moved file, and the store leaves main under a success outcome.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup_origin(tmp, base)
        other = tmp / "other"
        g(tmp, "clone", "-q", str(origin), str(other))
        hook_py = tmp / "upstream_rename.py"
        hook_py.write_text(_UPSTREAM_RENAME, encoding="utf-8")
        hook = f'"{sys.executable}" "{hook_py.as_posix()}" "{other.as_posix()}"'
        write(work, FIXTURE_EVIDENCE, dump(base + [row("blackmagic-davinci", "21", 400)]))
        r = quiet_writeback(wb_cfg(work, test_hook_before_push=hook, test_hook_fires=1))
        archive = g(origin, "show", "main:records/zz-evidence-archive.md", check_rc=False).stdout
        check("W an upstream that renames the store mid-run makes the lane REFUSE its rebase",
              r.outcome == aw.REBASE_CONFLICT and "fixture-report-400" not in archive,
              f"outcome={r.outcome} outcomes={r.outcomes} "
              f"lane row in the renamed file: {'fixture-report-400' in archive}")

    # ...and the LANE's own rename must count on its side of that comparison. The check above puts the
    # rename upstream, so it only pins the upstream diff; this one pins the lane's commit paths. With
    # rename detection, the lane renaming records/long.md listed only the new name, upstream's edit to
    # long.md found no overlap, and merge-ort silently folded the human edit into the renamed file.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup_origin(tmp, base)
        seed = tmp / "seed"
        write(seed, "records/long.md", "".join(f"record line {i}\n" for i in range(60)))
        g(seed, "add", "-A"); g(seed, "commit", "-m", "add a long record")
        g(seed, "push", "origin", "main")
        g(work, "pull", "--quiet", "origin", "main")
        other = tmp / "other"
        g(tmp, "clone", "-q", str(origin), str(other))
        hook_py = tmp / "upstream_edit.py"
        hook_py.write_text(_UPSTREAM_EDIT, encoding="utf-8")
        hook = f'"{sys.executable}" "{hook_py.as_posix()}" "{other.as_posix()}"'
        (work / "records/long.md").rename(work / "records/long-renamed.md")
        r = quiet_writeback(wb_cfg(work, test_hook_before_push=hook, test_hook_fires=1))
        renamed_on_main = g(origin, "show", "main:records/long-renamed.md", check_rc=False).stdout
        check("W a lane that renames a file upstream just edited REFUSES its rebase, naming the source",
              r.outcome == aw.REBASE_CONFLICT and "records/long.md" in r.conflicting_paths
              and "HUMAN EDIT" not in renamed_on_main,
              f"outcome={r.outcome} conflicting={r.conflicting_paths} "
              f"edit silently merged into the rename: {'HUMAN EDIT' in renamed_on_main}")

    # BARE-SCRIPT mode -- how every writer workflow actually runs the writeback. Every other [W]
    # check imports it in-process as a package, where the deferred import takes its package branch;
    # the script branch is the one production depends on, and nothing else in the manifest runs it.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup_production_layout(tmp, base)
        write(work, el.EVIDENCE_PATH, dump(base + [row("blackmagic-davinci", "21", 500)]))
        rc, outcomes, out = run_writeback_script(work, [el.EVIDENCE_PATH])
        check("W [bare script] the writeback, run as the lanes run it, commits ordinary growth",
              rc == 0 and aw.PUSH_SUCCESS_FIRST_ATTEMPT in outcomes
              and "Traceback" not in out and "ModuleNotFoundError" not in out,
              f"rc={rc} outcomes={outcomes} tail={out[-240:]!r}")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup_production_layout(tmp, base)
        before = g(origin, "rev-parse", "main").stdout.strip()
        write(work, el.EVIDENCE_PATH, dump([r for r in base if id(r) not in {id(x) for x in dv(base)}]))
        rc, outcomes, out = run_writeback_script(work, [el.EVIDENCE_PATH])
        check("W [bare script] and refuses a purge in that mode too",
              rc != 0 and outcomes and outcomes[-1] == aw.EVIDENCE_LOSS_REFUSED
              and g(origin, "rev-parse", "main").stdout.strip() == before,
              f"rc={rc} outcomes={outcomes} tail={out[-240:]!r}")

    # A lane that does not stage the store is untouched by the gate.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        origin, work = setup_origin(tmp, base)
        write(work, "records/obs.md", "obs, refreshed\n")
        r = quiet_writeback(wb_cfg(work))
        check("W a records-only writeback never consults the evidence gate",
              r.pushed and not r.evidence_losses, f"outcome={r.outcome}")


# --------------------------------------------------------------------------------------------------
# [K] the pull-request check
# --------------------------------------------------------------------------------------------------
def run_cli(repo: Path, base: str) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli.main(["--base", base, "--repo", str(repo), "--evidence-path", FIXTURE_EVIDENCE])
    return rc, buf.getvalue()


def section_cli() -> None:
    print(NEWLINE + "[K] check_evidence_loss.py -- the pull-request half")
    base_rows = fixture_base()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _origin, work = setup_origin(tmp, base_rows)
        base = g(work, "rev-parse", "HEAD").stdout.strip()

        rc, _ = run_cli(work, base)
        check("K an unchanged tree exits 0", rc == cli.EXIT_OK, f"rc={rc}")
        write(work, FIXTURE_EVIDENCE, dump(base_rows + [row("blackmagic-davinci", "21", 300)]))
        rc, _ = run_cli(work, base)
        check("K [A] growth exits 0", rc == cli.EXIT_OK, f"rc={rc}")
        cand = copy.deepcopy(base_rows)
        cand[2]["counted"] = False
        cand[2]["exclusion_reason"] = "vendor_release_announcement"
        write(work, FIXTURE_EVIDENCE, dump(cand))
        rc, _ = run_cli(work, base)
        check("K [B] an audited withdrawal exits 0", rc == cli.EXIT_OK, f"rc={rc}")

        keep = {id(r) for r in dv(base_rows)[:1]}
        write(work, FIXTURE_EVIDENCE, dump([r for r in base_rows if r["product_id"] != "blackmagic-davinci"
                                            or id(r) in keep or not el.is_accepted(r)]))
        rc, out = run_cli(work, base)
        check("K [E] a 98% purge exits 1 and says how to withdraw instead",
              rc == cli.EXIT_LOSS and "counted: false" in out and "::error::" in out, f"rc={rc}")

        for label, bad in (("an empty base", ""), ("an all-zero base (a new ref)", "0" * 40),
                           ("a base not present in the checkout", "1" * 40)):
            rc, _ = run_cli(work, bad)
            check(f"K {label} exits 2 -- never a pass", rc == cli.EXIT_NO_BASE, f"rc={rc}")

        write(work, FIXTURE_EVIDENCE, dump(base_rows) + "- id: hand-edit\n  captured_at: 2026-13-45\n")
        try:
            rc, out = run_cli(work, base)
        except Exception as exc:  # noqa: BLE001 - the defect this asserts against IS an escape
            rc, out = -1, f"escaped: {type(exc).__name__}"
        check("K a store the YAML constructor rejects exits 2 (unreadable), not 1 or a traceback",
              rc == cli.EXIT_NO_BASE and "::error::" in out, f"rc={rc} {out[-120:]}")


# --------------------------------------------------------------------------------------------------
# [Y] the ci-integrity step, executed
# --------------------------------------------------------------------------------------------------
FAKE_GIT = r"""#!/usr/bin/env bash
echo "GIT $*" >> "$SIM_LOG"
if [ "$1" = "fetch" ]; then exit "${SIM_FETCH_RC:-0}"; fi
if [ "$1" = "rev-parse" ] && [ "$2" = "HEAD^1" ]; then echo "parentsha0000000000000000000000000000000"; exit 0; fi
exit 0
"""

FAKE_PYTHON = r"""#!/usr/bin/env bash
echo "PY $*" >> "$SIM_LOG"
exit "${SIM_PY_RC:-0}"
"""


def eval_gh_expr(template: str, ctx: dict) -> str:
    """Evaluate the `${{ ... }}` interpolations of `template` against `ctx`, the way GitHub does for
    the ONE shape used here: dotted context lookups joined by `||`, which yields the first truthy
    operand, else the last. Any other syntax raises, so a later edit to the expression fails this
    suite loudly instead of being silently mis-evaluated."""
    import re

    def one(expr: str) -> str:
        last = None
        for operand in (o.strip() for o in expr.split("||")):
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*", operand):
                raise ValueError(f"unsupported expression operand: {operand!r}")
            cur = ctx
            for part in operand.split("."):
                cur = cur.get(part) if isinstance(cur, dict) else None
            last = cur
            if cur:
                return str(cur)
        return "" if last is None else str(last)

    return re.sub(r"\$\{\{(.*?)\}\}", lambda m: one(m.group(1)), template)


def load_step() -> tuple[str, dict]:
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for step in wf["jobs"]["integrity"]["steps"]:
        if step.get("name") == STEP_NAME:
            return step["run"], (step.get("env") or {})
    raise KeyError(STEP_NAME)


def run_step(script: str, **sim) -> tuple[int, list[str]]:
    tmp = tempfile.mkdtemp()
    try:
        for name, body in (("git", FAKE_GIT), ("python", FAKE_PYTHON)):
            p = Path(tmp, name)
            p.write_text(body, newline="\n")
            p.chmod(p.stat().st_mode | stat.S_IEXEC)
        sh = Path(tmp, "step.sh")
        sh.write_text(script, newline="\n")
        log = Path(tmp, "calls.log")
        log.write_text("", newline="\n")
        env = dict(os.environ)
        env.update({
            "PATH": tmp + os.pathsep + env.get("PATH", ""),
            "SIM_LOG": str(log),
            "GITHUB_SHA": "headsha00000000000000000000000000000000",
            "EVENT_NAME": sim.get("event", ""),
            "PR_BASE_SHA": sim.get("pr_base", ""),
            "PUSH_BEFORE_SHA": sim.get("before", ""),
            "SIM_FETCH_RC": sim.get("fetch_rc", "0"),
            "SIM_PY_RC": sim.get("py_rc", "0"),
        })
        # Exactly how GitHub runs a `run:` step on ubuntu: errexit and pipefail ON. Without -e a
        # failed fetch would fall through to the check, and this suite would test the wrong shell.
        proc = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", str(sh)],
                              capture_output=True, text=True, env=env)
        return proc.returncode, log.read_text().splitlines()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def section_workflow() -> None:
    print(NEWLINE + "[Y] the ci-integrity step, executed against a stubbed git and python")
    try:
        script, env_decl = load_step()
    except KeyError:
        check(f"Y ci-integrity.yml has a step named {STEP_NAME!r}", False, "step not found")
        return
    check("Y the base comes from the event payload, never from `main`",
          env_decl.get("PR_BASE_SHA") == "${{ github.event.pull_request.base.sha }}"
          and env_decl.get("PUSH_BEFORE_SHA") == "${{ github.event.before }}"
          and env_decl.get("EVENT_NAME") == "${{ github.event_name }}", str(env_decl))
    check("Y no `${{ }}` expression is interpolated into the shell itself",
          "${{" not in script)
    run_workflow_shell(script)


def section_concurrency() -> None:
    print(NEWLINE + "[C] ci-integrity concurrency -- a push's window is never cancelled away")
    # The step judges a WINDOW (before..after), so a push run that is cancelled before it gets there
    # leaves that window unjudged forever. The concurrency group is evaluated per event, not grepped.
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    group = str((wf.get("concurrency") or {}).get("group") or "")

    def ctx(name: str, event: dict, sha: str, ref: str) -> dict:
        return {"github": {"event_name": name, "event": event, "sha": sha, "ref": ref}}

    A, B, C, Z = ("a" * 40), ("b" * 40), ("c" * 40), ("f" * 40)
    push1 = ctx("push", {"before": Z}, A, "refs/heads/main")
    push2 = ctx("push", {"before": A}, B, "refs/heads/main")
    # main force-pushed away to C, then the old tip A pushed again: same `after`, different window.
    repush = ctx("push", {"before": C}, A, "refs/heads/main")
    disp1 = ctx("workflow_dispatch", {}, A, "refs/heads/main")          # same commit as push1
    pr_v1 = ctx("pull_request", {"before": Z, "pull_request": {"number": 7}}, C, "refs/pull/7/merge")
    pr_v2 = ctx("pull_request", {"before": A, "pull_request": {"number": 7}}, B, "refs/pull/7/merge")
    try:
        g_p1, g_p2, g_rp, g_d1, g_r1, g_r2 = (eval_gh_expr(group, c)
                                              for c in (push1, push2, repush, disp1, pr_v1, pr_v2))
        old = "ci-integrity-${{ github.event.pull_request.number || github.ref }}"
        o_p1, o_p2 = eval_gh_expr(old, push1), eval_gh_expr(old, push2)
    except ValueError as exc:
        check("Y the concurrency group is an expression this suite can evaluate", False, str(exc))
        return
    check("Y non-vacuity: the old ref-keyed group put two pushes to main in ONE group",
          o_p1 == o_p2, f"{o_p1!r} vs {o_p2!r}")
    check("Y two pushes to main never share a concurrency group, so neither cancels the other's window",
          g_p1 != g_p2 and (wf.get("concurrency") or {}).get("cancel-in-progress") is True,
          f"{g_p1!r} vs {g_p2!r}")
    check("Y re-pushing an old tip after a force-push is a different window, so a different group",
          g_rp != g_p1, f"{g_rp!r} vs {g_p1!r}")
    check("Y a manual dispatch on the same commit cannot cancel that commit's push run",
          g_d1 != g_p1, f"{g_d1!r} vs {g_p1!r}")
    check("Y a superseded run of the same PR still shares a group (its replacement re-judges the PR)",
          g_r1 == g_r2 and g_r1 not in (g_p1, g_p2, g_rp, g_d1), f"{g_r1!r} {g_r2!r}")


def run_workflow_shell(script: str) -> None:
    if shutil.which("bash") is None:
        check("Y bash is required to execute the ci-integrity step", False, "bash not on PATH")
        return

    def py_calls(log):
        return [ln[3:] for ln in log if ln.startswith("PY ")]

    def fetches(log):
        return [ln[4:] for ln in log if ln.startswith("GIT fetch")]

    rc, log = run_step(script, event="pull_request", pr_base="prbase00000000000000000000000000000000")
    check("Y pull_request: fetches the PR base by sha and checks against it",
          rc == 0 and any("prbase" in f for f in fetches(log))
          and py_calls(log) == ["auxsays/scripts/check_evidence_loss.py --base "
                                "prbase00000000000000000000000000000000"], str(log))
    rc, log = run_step(script, event="push", before="before0000000000000000000000000000000000")
    check("Y push: checks against the tip it replaced (`before`), not the first parent",
          rc == 0 and py_calls(log) == ["auxsays/scripts/check_evidence_loss.py --base "
                                        "before0000000000000000000000000000000000"], str(log))
    rc, log = run_step(script, event="workflow_dispatch")
    check("Y workflow_dispatch: deepens to the parent and checks against it",
          rc == 0 and any("--depth=2" in f for f in fetches(log))
          and py_calls(log) == ["auxsays/scripts/check_evidence_loss.py --base "
                                "parentsha0000000000000000000000000000000"], str(log))
    rc, log = run_step(script, event="push", before="0" * 40)
    check("Y an all-zero `before` falls back to the parent rather than passing",
          rc == 0 and py_calls(log) and "parentsha" in py_calls(log)[0], str(log))
    rc, log = run_step(script, event="pull_request", pr_base="prbase00000000000000000000000000000000",
                       fetch_rc="128")
    check("Y a failed base fetch FAILS the step and never reaches the check",
          rc != 0 and py_calls(log) == [], f"rc={rc} {log}")
    rc, _ = run_step(script, event="pull_request", pr_base="prbase00000000000000000000000000000000",
                     py_rc="1")
    check("Y a detected loss (exit 1) fails the step", rc == 1, f"rc={rc}")
    rc, _ = run_step(script, event="pull_request", pr_base="prbase00000000000000000000000000000000",
                     py_rc="2")
    check("Y an unestablishable base (exit 2) fails the step", rc == 2, f"rc={rc}")


# --------------------------------------------------------------------------------------------------
# [L] the live store, read-only
# --------------------------------------------------------------------------------------------------
def section_live() -> None:
    print(NEWLINE + "[L] the live store -- read-only; no count of it is pinned, and no product assumed")
    text = (_REPO / el.EVIDENCE_PATH).read_text(encoding="utf-8")
    try:
        rows = el.parse_store(text)
        parsed = True
    except el.EvidenceStoreUnreadable as exc:
        rows, parsed = [], False
        print(f"        {exc}")
    # Non-empty is not a floor: under the rule this suite asserts, no row can leave the store, so a
    # store that has ever held a row always will. An empty store here means this suite read nothing.
    check("L the live store parses under the guard's own reader, and holds rows",
          parsed and bool(rows))
    blank = [el.row_key(r) for r in rows if not all(el.row_key(r))]
    check("L every live row carries all four identity fields, so none can shadow another",
          not blank, f"{len(blank)} row(s) with a blank identity field, e.g. {blank[:2]}")
    reasonless = [r.get("id") for r in rows if r.get("counted") is False
                  and not el.is_audited_withdrawal(r)]
    check("L every withdrawn live row already carries its exclusion_reason -- the rule matches practice",
          not reasonless, f"{reasonless[:3]}")
    check("L the live store compared with itself loses nothing",
          el.find_unexplained_losses(rows, rows) == [])
    # Purges on the REAL rows, in memory. Each asserts that every removed row is named -- however many
    # there are. No product is assumed and nothing is kept back, so no legitimate withdrawal, of any
    # size, can make these fail: an earlier version kept five DaVinci rows and so turned red on any
    # store with five or fewer accepted DaVinci rows -- a live-corpus floor, in the suite written to
    # remove them.
    losses = el.find_unexplained_losses(rows, [])
    check("L deleting the whole real store names every one of its rows",
          codes(losses) <= {el.REMOVED} and rows_of(losses, el.REMOVED) == len(rows),
          f"named {rows_of(losses)} of {len(rows)}")
    accepted = [r for r in rows if el.is_accepted(r)]
    kept = [r for r in rows if not el.is_accepted(r)]
    losses = el.find_unexplained_losses(rows, kept)
    check("L [E] deleting every accepted row of every product names each one, and blames nothing else",
          codes(losses) <= {el.REMOVED} and rows_of(losses) == len(accepted),
          f"{codes(losses)} named {rows_of(losses)} of {len(accepted)}")


def run() -> int:
    print("=" * 78)
    print("A stored evidence row never disappears; it stops counting only by audited withdrawal")
    print("=" * 78)
    section_predicate()
    section_writeback()
    section_cli()
    section_workflow()
    section_concurrency()
    section_live()
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
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
