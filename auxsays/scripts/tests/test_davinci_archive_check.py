#!/usr/bin/env python3
"""The DaVinci archive build check holds after the migration: any N >= 0, never a frozen count.

davinci-archive-build-check.yml asserted the ONE-TIME migration baseline (exactly 100 records changed,
exactly 100 notice pages, 21.0.4 active). Once the migration ran in production the convergence on a
pull request changed nothing, so the check failed on every pull request that triggered it. The check
now lives in auxsays/scripts/ci/davinci_archive_check.py. This suite drives it the way CI does: the
real script in child processes, against a scratch git repository holding a copy of EVERY real DaVinci
record (plus one record of another product), with the real archive CLI doing the convergence. Each
refusal must arrive under its NAMED check id with exit 1; a crash (exit 2) is not a catch.

  [C01-C14] the fourteen governed cases of the P-H authorization, in its order
  [F] further per-file refusals: line endings, body edits, duplicate keys, renames, staged adds
  [P] the plan before and after convergence, and the paths that must never read as a pass
  [R] render parity details: duplicate notice, stray notice pages, spot pages, permalinks
  [W] the workflow: trigger paths, read-only, step order, no frozen numbers -- run: scalars EXECUTED

Offline and deterministic; writes only inside temp directories. Needs git and bash.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_davinci_archive_check.py
"""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
_SCRIPTS = _AUX / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import yaml  # noqa: E402

from lib import davinci_archive_policy as pol  # noqa: E402

CHECK = _SCRIPTS / "ci" / "davinci_archive_check.py"
APPLY = _SCRIPTS / "apply_davinci_archive_policy.py"
WORKFLOW = _REPO / ".github" / "workflows" / "davinci-archive-build-check.yml"
INCLUDE = _AUX / "_includes" / "archived-notice.html"
REAL_GEN = _AUX / "updates" / "generated"
GEN_REL = "auxsays/updates/generated"
DAV = "blackmagic-davinci"

_spec = importlib.util.spec_from_file_location("davinci_archive_check", CHECK)
chk = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = chk  # dataclasses resolve their module through sys.modules
_spec.loader.exec_module(chk)

PASS = FAIL = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  [{one_line(detail)}]" if detail else ""))


def one_line(text: str) -> str:
    # Never echo a child's lines verbatim: a line of ours starting with FAIL is read by the runner.
    return " | ".join(x.strip() for x in str(text).strip().splitlines()[-8:])[:500]


def section(title: str) -> None:
    print()
    print(title)


# ----------------------------------------------------------------------------- fixture

def git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def child_env() -> dict:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("GITHUB_ACTIONS", None)
    return env


def run_check(root: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(CHECK), *args, "--root", str(root)], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", env=child_env(), timeout=300)
    return proc.returncode, proc.stdout + proc.stderr


def run_apply(root: Path) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(APPLY), "--write", "--confirm-write", "--root", str(root / "auxsays")],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=child_env(), timeout=300)
    return proc.returncode, proc.stdout + proc.stderr


def passed(res: tuple[int, str]) -> bool:
    return res[0] == 0 and "DAVINCI ARCHIVE CHECK PASSED" in res[1]


def failed_with(res: tuple[int, str], check_id: str) -> bool:
    """Exit 1 AND the named check reported. A crash or a different reason is not a catch."""
    return res[0] == 1 and re.search(rf"^\s*FAIL\s+{re.escape(check_id)}:", res[1], re.M) is not None


def other_product_record() -> Path:
    """A real record of another product, sharing the directory, with one plain current status."""
    for path in sorted(REAL_GEN.glob("*.md")):
        raw = path.read_bytes()
        if DAV.encode() in raw:
            continue
        fm = pol.read_front_matter(path)
        if fm.get("update_entry") is True and fm.get("update_status") == "current" \
                and raw.count(b"\nupdate_status: current\n") == 1:
            return path
    raise RuntimeError("no other-product record with a plain current status")


def replace_once(path: Path, old: bytes, new: bytes, last: bool = False) -> None:
    raw = path.read_bytes()
    at = raw.rfind(old) if last else raw.find(old)
    if at < 0:
        raise RuntimeError(f"{path.name}: {old!r} not found")
    path.write_bytes(raw[:at] + new + raw[at + len(old):])


def set_field(text: str, key: str, value: str) -> str:
    out, done = [], False
    for line in text.split("\n"):
        if not done and line.startswith(key + ":"):
            out.append(f"{key}: {value}")
            done = True
        else:
            out.append(line)
    if not done:
        raise RuntimeError(f"no {key} line")
    return "\n".join(out)


def edit_line_after_status(path: Path) -> None:
    """Change the front-matter line right AFTER the status line, in place (same line count), so the
    first changed line is still the legitimate status edit."""
    lines = path.read_bytes().split(b"\n")
    close = next(i for i in range(1, len(lines)) if lines[i].rstrip(b"\r") == b"---")
    at = next(i for i in range(1, close) if lines[i].startswith(b"update_status:"))
    if at + 1 >= close:
        raise RuntimeError(f"{path.name}: the status line is the last front-matter line")
    lines[at + 1] = lines[at + 1] + b" (edited)"
    path.write_bytes(b"\n".join(lines))


class Fixture:
    def __init__(self, td: Path):
        self.td = td
        self.root = td / "repo"
        self.gen = self.root / GEN_REL
        self.gen.mkdir(parents=True)
        recs, unreadable = pol.load_records(REAL_GEN)
        if unreadable or not recs:
            raise RuntimeError(f"real corpus unreadable: {unreadable[:3]}")
        for r in recs:
            shutil.copy2(r.path, self.gen / r.path.name)
        self.real_count = len(recs)
        self.other = self.gen / other_product_record().name
        shutil.copy2(REAL_GEN / self.other.name, self.other)
        (self.root / "auxsays" / "_data").mkdir(parents=True)
        (self.root / "auxsays" / "_data" / "fixture.yml").write_text("a: 1\n", encoding="utf-8")
        (self.root / ".gitignore").write_text("auxsays/_site/\n__pycache__/\n", encoding="utf-8")
        # Converge the copy first, so the committed tree is converged by construction (N = 0), whatever
        # state the real corpus is in when this runs.
        code, out = run_apply(self.root)
        if code != 0:
            raise RuntimeError(f"fixture convergence failed: {out[-300:]}")
        git(self.root, "init", "-q")
        for key, value in (("user.email", "t@example.invalid"), ("user.name", "t"), ("core.autocrlf", "false"),
                           ("commit.gpgsign", "false")):
            git(self.root, "config", key, value)
        self.commit("base")
        self.base = self.head()

    def head(self) -> str:
        return git(self.root, "rev-parse", "HEAD").strip()

    def commit(self, msg: str) -> None:
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "--allow-empty", "-m", msg)

    def reset(self, rev: str | None = None) -> None:
        git(self.root, "reset", "-q", "--hard", rev or self.base)
        git(self.root, "clean", "-q", "-fdx")

    def records(self) -> list:
        return pol.load_records(self.gen)[0]

    def rec(self, name: str):
        return next(r for r in self.records() if r.path.name == name)


NOTICE_HTML = re.search(r"<aside\b.*?</aside>", INCLUDE.read_text(encoding="utf-8"), re.S).group(0)
PAGE = ("<!DOCTYPE html>\n<html lang=\"en\"><head><title>{title}</title></head>\n"
        "<body class=\"aux-page\"><main class=\"aux-update\">\n{notice}\n"
        "<section id=\"verdict\"><h2>Verdict</h2></section>\n</main></body></html>\n")


def build_site(fx: Fixture, site: Path) -> dict[str, Path]:
    """What a correct build yields from the working tree: one page per DaVinci record at its
    permalink, carrying the shipped notice markup iff the record is archived, plus pages no record
    owns (the product hub, the home page)."""
    if site.exists():
        shutil.rmtree(site)
    pages: dict[str, Path] = {}
    for rec in fx.records():
        fm = pol.read_front_matter(rec.path)
        page = chk.resolve_page(site, fm.get("permalink"))
        if page is None:
            continue
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(PAGE.format(title=fm.get("title", ""),
                                    notice=NOTICE_HTML if rec.status == "archived" else ""), encoding="utf-8")
        pages[rec.path.name] = page
    for extra in ("updates/blackmagic-design/blackmagic-davinci/index.html", "index.html"):
        (site / extra).parent.mkdir(parents=True, exist_ok=True)
        (site / extra).write_text(PAGE.format(title="hub", notice=""), encoding="utf-8")
    return pages


def strip_notice(page: Path) -> None:
    page.write_text(page.read_text(encoding="utf-8").replace(NOTICE_HTML, ""), encoding="utf-8")


def add_notice(page: Path, times: int = 1) -> None:
    page.write_text(page.read_text(encoding="utf-8").replace("<section id=\"verdict\">",
                                                               NOTICE_HTML * times + "<section id=\"verdict\">"),
                    encoding="utf-8")


def bash_exe() -> str | None:
    for cand in ("C:/Program Files/Git/bin/bash.exe", "C:/Program Files/Git/usr/bin/bash.exe"):
        if os.path.exists(cand):
            return cand
    return shutil.which("bash")


# ----------------------------------------------------------------------------- cases

def run() -> int:
    if shutil.which("git") is None:
        check("git is required to build the scratch repository", False, "git not on PATH")
        return 1
    td = Path(tempfile.mkdtemp(prefix="auxsays-dvcheck-"))
    try:
        return _run(td)
    finally:
        shutil.rmtree(td, ignore_errors=True)


def _run(td: Path) -> int:
    fx = Fixture(td)
    plan_file = td / "runner-temp" / "davinci-archive-preplan.json"
    site = td / "site"

    recs = fx.records()
    plan0 = pol.plan_archive(fx.gen)
    newest = plan0.newest_stable_major
    archived = sorted((r for r in recs if r.status == pol.ARCHIVED), key=lambda r: r.path.name)
    active = sorted((r for r in recs if r.status != pol.ARCHIVED), key=lambda r: r.path.name)
    spot19 = next((r for r in recs if r.version == chk.FIXED_ARCHIVED_SPOT), None)
    victims = [r for r in archived if r is not spot19]
    held = [r for r in active if r.major is not None and not r.is_beta and r.major < (newest or 0)]
    top = [r for r in active if r.major == newest and not r.is_beta]
    spot_active = chk.pick_active_spot(recs)
    plain_active = [r for r in active if r is not spot_active]

    section("[fixture] a scratch repository holding every real DaVinci record")
    check("fixture holds every real DaVinci record, converged, with each role this suite needs",
          len(recs) == fx.real_count and not plan0.refused and not plan0.to_archive and spot19 is not None
          and len(victims) >= 3 and held and top and spot_active is not None and plain_active,
          f"records={len(recs)} refused={plan0.refused} pending={len(plan0.to_archive)} victims={len(victims)} "
          f"held={len(held)} top={len(top)}")
    check("the check's constants are the measured ones, not parameters: floor 100, at least one active, 19.1.4",
          chk.ARCHIVED_FLOOR == 100 and chk.MIN_ACTIVE == 1 and chk.FIXED_ARCHIVED_SPOT == "19.1.4"
          and chk.NOTICE_MARKER in NOTICE_HTML)

    def preplan() -> tuple[int, str]:
        return run_check(fx.root, "preplan", "--out", str(plan_file))

    def conv() -> tuple[int, str]:
        return run_check(fx.root, "convergence", "--plan", str(plan_file))

    def render() -> tuple[int, str]:
        return run_check(fx.root, "render", "--site", str(site))

    # ================================================================ the fourteen governed cases
    section("[C] the fourteen governed cases")

    # C01 -- already converged, N = 0 (what every pull request sees today)
    fx.reset()
    pre = preplan()
    check("C01a already-converged tree: preplan passes with 0 pending", passed(pre) and ", 0 pending" in pre[1], pre[1])
    code, out = run_apply(fx.root)
    check("C01b the real CLI converges it as a no-op", code == 0 and not git(fx.root, "status", "--porcelain"), out[-200:])
    res = conv()
    check("C01c already-converged tree: convergence passes with N = 0", passed(res) and "N = 0 record(s)" in res[1], res[1])
    build_site(fx, site)
    res = render()
    check("C01d already-converged tree: render passes over every record, archived >= floor, active >= 1",
          passed(res) and f"DaVinci records: {len(recs)}; archived: {len(archived)} " in res[1]
          and f"active: {len(active)};" in res[1], res[1])
    check("C01e the active spot page is chosen from the converged tree (the newest stable active record)",
          f"active spot page (chosen from the converged tree): {spot_active.version} ->" in res[1]
          and spot_active.status != pol.ARCHIVED and spot_active.major == newest, res[1])
    check("C01f the archived spot page is 19.1.4, carrying the notice once",
          f"archived spot page: {chk.FIXED_ARCHIVED_SPOT} ->" in res[1] and "(notice x1)" in res[1], res[1])

    # C02 -- a future legitimate convergence, N > 0: three qualifying records are current at HEAD
    fx.reset()
    three = victims[:3]
    for r in three:
        replace_once(fx.gen / r.path.name, b"\nupdate_status: archived", b"\nupdate_status: current")
    fx.commit("three qualifying records back to current")
    n3_head = fx.head()
    pre = preplan()
    check("C02a N = 3: preplan passes with exactly those 3 pending", passed(pre) and ", 3 pending" in pre[1], pre[1])
    code, out = run_apply(fx.root)
    status = git(fx.root, "status", "--porcelain")
    check("C02b the real CLI archives the 3", code == 0 and len(status.splitlines()) == 3, f"rc={code} {status} {out[-200:]}")
    res = conv()
    check("C02c N = 3 pure ratchet edits: convergence passes with N = 3", passed(res) and "N = 3 record(s)" in res[1], res[1])
    build_site(fx, site)
    check("C02d N = 3: render passes", passed(render()))

    # C02 -- the real future: a stable 22 ships, so every major-20 record archives
    fx.reset()
    src = max(top, key=lambda r: r.path.name)
    text = src.path.read_text(encoding="utf-8")
    text = set_field(text, "update_version", "'22'")
    text = set_field(text, "permalink", "/updates/blackmagic-design/blackmagic-davinci/22/")
    (fx.gen / "2099-01-01-davinci-resolve-22.md").write_text(text, encoding="utf-8", newline="")
    fx.commit("stable 22")
    expect = len(pol.plan_archive(fx.gen).to_archive)
    pre = preplan()
    check("C02e stable 22 at HEAD: preplan passes with every major-20 record pending (N > 0)",
          expect > 0 and passed(pre) and f", {expect} pending" in pre[1], f"expect={expect} {pre[1]}")
    run_apply(fx.root)
    res = conv()
    check("C02f stable 22: convergence passes with that N", passed(res) and f"N = {expect} record(s)" in res[1], res[1])
    build_site(fx, site)
    res = render()
    check("C02g stable 22: render passes and the active spot page moves to 22 by itself (no hard-coded page)",
          passed(res) and "active spot page (chosen from the converged tree): 22 ->" in res[1], res[1])

    # C03..C07 run against the converged base: one preplan, then one edit per case.
    fx.reset()
    preplan()
    run_apply(fx.root)

    def after_base(edit) -> tuple[int, str]:
        fx.reset()
        edit()
        return conv()

    res = after_base(lambda: replace_once(fx.other, b"\nupdate_status: current\n", b"\nupdate_status: archived\n"))
    check("C03 wrong-product file: a pure current -> archived edit on another product's record -> NOT_DAVINCI_RECORD",
          failed_with(res, chk.NOT_DAVINCI_RECORD), res[1])

    res = after_base(lambda: replace_once(fx.gen / victims[0].path.name, b"\ntitle: ", b"\ntitle: Edited "))
    check("C04a unauthorized front-matter edit (title) -> UNAUTHORIZED_CHANGE",
          failed_with(res, chk.UNAUTHORIZED_CHANGE), res[1])
    res = after_base(lambda: replace_once(fx.gen / held[0].path.name, b"\nupdate_status: current", b"\nupdate_status: retired"))
    check("C04b a status edit to anything but archived -> UNAUTHORIZED_CHANGE",
          failed_with(res, chk.UNAUTHORIZED_CHANGE), res[1])

    res = after_base(lambda: (fx.gen / victims[0].path.name).unlink())
    check("C05a record deletion -> RECORD_DELETED", failed_with(res, chk.RECORD_DELETED), res[1])
    res = after_base(lambda: shutil.copy2(fx.gen / held[0].path.name, fx.gen / "2099-02-02-davinci-resolve-copy.md"))
    check("C05b record addition (a new untracked record) -> RECORD_ADDED", failed_with(res, chk.RECORD_ADDED), res[1])

    res = after_base(lambda: (fx.root / "auxsays" / "_data" / "fixture.yml").write_text("a: 2\n", encoding="utf-8"))
    check("C06a a tracked file outside the generated records changed -> OUT_OF_SCOPE",
          failed_with(res, chk.OUT_OF_SCOPE), res[1])
    res = after_base(lambda: (fx.root / "auxsays" / "stray.txt").write_text("x\n", encoding="utf-8"))
    check("C06b a new file outside the generated records -> OUT_OF_SCOPE", failed_with(res, chk.OUT_OF_SCOPE), res[1])

    res = after_base(lambda: replace_once(fx.gen / victims[0].path.name, b"\nupdate_status: archived", b"\nupdate_status: current"))
    check("C07a unarchive transition (archived -> current) -> UNARCHIVE", failed_with(res, chk.UNARCHIVE), res[1])
    res = after_base(lambda: replace_once(fx.gen / victims[0].path.name, b"\nupdate_status: archived", b""))
    check("C07b unarchive by deleting the status line -> UNARCHIVE", failed_with(res, chk.UNARCHIVE), res[1])

    # C08..C12: render, on the converged base and a correct build of it
    fx.reset()
    pages = build_site(fx, site)
    strip_notice(pages[victims[0].path.name])
    res = render()
    check("C08 an archived record whose page lacks the notice -> MISSING_NOTICE", failed_with(res, chk.MISSING_NOTICE), res[1])

    pages = build_site(fx, site)
    add_notice(pages[plain_active[0].path.name])
    res = render()
    check("C09 an active record whose page carries the notice -> NOTICE_ON_ACTIVE",
          failed_with(res, chk.NOTICE_ON_ACTIVE), res[1])

    pages = build_site(fx, site)
    pages[plain_active[0].path.name].unlink()
    res = render()
    check("C10a an active record with no built page -> MISSING_PAGE", failed_with(res, chk.MISSING_PAGE), res[1])
    pages = build_site(fx, site)
    pages[victims[0].path.name].unlink()
    res = render()
    check("C10b an archived record with no built page -> MISSING_PAGE", failed_with(res, chk.MISSING_PAGE), res[1])

    surplus = len(archived) - chk.ARCHIVED_FLOOR
    fx.reset()
    for r in victims[:surplus + 1]:
        (fx.gen / r.path.name).unlink()
    build_site(fx, site)
    res = render()
    check("C11a one archived record below the ratchet floor -> ARCHIVED_BELOW_FLOOR",
          surplus >= 0 and failed_with(res, chk.ARCHIVED_BELOW_FLOOR)
          and f"archived: {chk.ARCHIVED_FLOOR - 1} " in res[1], res[1])
    fx.reset()
    for r in victims[:surplus]:
        (fx.gen / r.path.name).unlink()
    build_site(fx, site)
    res = render()
    check("C11b exactly at the floor passes (the floor is inclusive)",
          passed(res) and f"archived: {chk.ARCHIVED_FLOOR} " in res[1], res[1])

    fx.reset()
    for r in active:
        (fx.gen / r.path.name).unlink()
    build_site(fx, site)
    res = render()
    check("C12 no active record -> NO_ACTIVE_RECORD", failed_with(res, chk.NO_ACTIVE_RECORD), res[1])

    # C13 -- convergence refusal: an implausible stable major at HEAD
    fx.reset()
    text = set_field(held[0].path.read_text(encoding="utf-8"), "update_version", "'2026'")
    text = set_field(text, "permalink", "/updates/blackmagic-design/blackmagic-davinci/2026/")
    (fx.gen / "2099-03-03-davinci-resolve-2026.md").write_text(text, encoding="utf-8", newline="")
    fx.commit("implausible major")
    res = preplan()
    check("C13a convergence refusal (implausible major) -> PLAN_REFUSED before convergence",
          failed_with(res, chk.PLAN_REFUSED) and pol.REFUSAL_RANGE in res[1], res[1])
    code, out = run_apply(fx.root)
    check("C13b ... and the CLI refuses too (exit 3), writing nothing",
          code == 3 and not git(fx.root, "status", "--porcelain"), f"rc={code}")
    fx.reset()
    preplan()
    res = after_base(lambda: replace_once(fx.gen / top[0].path.name, b"\nupdate_status: current", b"\nupdate_status: archived"))
    check("C13c a converged tree the policy refuses (newest stable archived) -> POSTPLAN_REFUSED",
          failed_with(res, chk.POSTPLAN_REFUSED) and pol.REFUSAL_BASELINE_BELOW_ARCHIVED in res[1], res[1])

    # C14 -- post-convergence pending work: the convergence skipped one of three
    fx.reset(n3_head)
    preplan()
    run_apply(fx.root)
    git(fx.root, "checkout", "--", f"{GEN_REL}/{three[0].path.name}")
    res = conv()
    check("C14 a pending transition left after convergence -> POSTPLAN_PENDING",
          failed_with(res, chk.POSTPLAN_PENDING), res[1])

    # ================================================================ further per-file refusals
    section("[F] further per-file refusals")
    fx.reset(n3_head)
    preplan()

    def after_n3(edit) -> tuple[int, str]:
        fx.reset(n3_head)
        run_apply(fx.root)
        edit()
        return conv()

    res = after_n3(lambda: edit_line_after_status(fx.gen / three[0].path.name))
    check("F1 a planned record whose status edit comes with a second front-matter edit -> UNAUTHORIZED_CHANGE",
          failed_with(res, chk.UNAUTHORIZED_CHANGE), res[1])
    res = after_n3(lambda: (fx.gen / three[0].path.name).write_bytes((fx.gen / three[0].path.name).read_bytes() + b"tail\n"))
    check("F2 a planned record with an appended line (line count moved) -> UNAUTHORIZED_CHANGE",
          failed_with(res, chk.UNAUTHORIZED_CHANGE), res[1])
    res = after_n3(lambda: replace_once(fx.gen / three[0].path.name, b"\nupdate_status: archived", b"\nupdate_status: \"archived\""))
    check("F3 a planned record archived with a value the CLI never writes (quoted) -> UNAUTHORIZED_CHANGE",
          failed_with(res, chk.UNAUTHORIZED_CHANGE), res[1])

    # special records committed at HEAD: CRLF, a body status line, a duplicate key, a non-current
    # status, a non-entry DaVinci file. None is pending, so the CLI leaves them alone.
    fx.reset()
    h = held[0].path.read_text(encoding="utf-8")

    def variant(name: str, text: str, version: str) -> Path:
        t = set_field(text, "permalink", f"/updates/blackmagic-design/blackmagic-davinci/{version}/")
        p = fx.gen / name
        p.write_text(t, encoding="utf-8", newline="")
        return p

    crlf = variant("2099-04-01-davinci-resolve-crlf.md", h, "crlf-1")
    crlf.write_bytes(crlf.read_bytes().replace(b"\n", b"\r\n"))
    body = variant("2099-04-02-davinci-resolve-body.md", h + "\nupdate_status: current\n", "body-1")
    dup = variant("2099-04-03-davinci-resolve-dup.md",
                  h.replace("\nupdate_status: current\n", "\nupdate_status: current\nupdate_status: current\n", 1), "dup-1")
    beta = variant("2099-04-04-davinci-resolve-beta.md", set_field(h, "update_status", "beta"), "beta-1")
    nonentry = variant("2099-04-05-davinci-resolve-nonentry.md", set_field(h, "update_entry", "false"), "nonentry-1")
    # a qualifying record, current at HEAD, with CRLF line endings: the CLI must archive it in kind
    pend = variant("2099-04-06-davinci-resolve-crlf-pending.md",
                   set_field(victims[3].path.read_text(encoding="utf-8"), "update_status", "current"), "crlf-pending-1")
    pend.write_bytes(pend.read_bytes().replace(b"\n", b"\r\n"))
    fx.commit("special records")
    sp_head = fx.head()
    pre = preplan()
    code, out = run_apply(fx.root)
    res = conv()
    check("F4 a CRLF record archived by the CLI keeps its line ending and is accepted (N = 1)",
          passed(pre) and ", 1 pending" in pre[1] and code == 0 and passed(res) and "N = 1 record(s)" in res[1]
          and b"\r\nupdate_status: archived\r\n" in pend.read_bytes(), res[1])

    def after_sp(edit) -> tuple[int, str]:
        fx.reset(sp_head)
        run_apply(fx.root)
        edit()
        return conv()

    res = after_sp(lambda: replace_once(crlf, b"update_status: current\r\n", b"update_status: archived\n"))
    check("F5 a status edit that drops the line's CR -> UNAUTHORIZED_CHANGE", failed_with(res, chk.UNAUTHORIZED_CHANGE), res[1])
    res = after_sp(lambda: replace_once(body, b"update_status: current", b"update_status: archived", last=True))
    check("F6 a status-shaped line edited in the BODY, outside the front matter -> UNAUTHORIZED_CHANGE",
          failed_with(res, chk.UNAUTHORIZED_CHANGE), res[1])
    res = after_sp(lambda: replace_once(dup, b"\nupdate_status: current\n", b"\nupdate_status: archived\n"))
    check("F7 one of two duplicate status keys archived (YAML keeps the other) -> FRONT_MATTER_DRIFT",
          failed_with(res, chk.FRONT_MATTER_DRIFT), res[1])
    res = after_sp(lambda: replace_once(beta, b"\nupdate_status: beta", b"\nupdate_status: archived"))
    check("F8 a status other than current moved to archived -> UNAUTHORIZED_CHANGE",
          failed_with(res, chk.UNAUTHORIZED_CHANGE), res[1])
    res = after_sp(lambda: replace_once(nonentry, b"\nupdate_status: current", b"\nupdate_status: archived"))
    check("F9 a DaVinci file that is not an update entry -> NOT_DAVINCI_RECORD",
          failed_with(res, chk.NOT_DAVINCI_RECORD), res[1])

    fx.reset()
    preplan()
    res = after_base(lambda: replace_once(fx.gen / held[0].path.name, b"\nupdate_status: current", b"\nupdate_status: archived"))
    check("F10 a correct one-line archive the plan did not hold (a ratchet-held major) -> UNPLANNED_CHANGE",
          failed_with(res, chk.UNPLANNED_CHANGE) and chk.POSTPLAN_REFUSED not in res[1], res[1])
    res = after_base(lambda: git(fx.root, "mv", f"{GEN_REL}/{victims[0].path.name}", f"{GEN_REL}/2099-05-05-renamed.md"))
    check("F11 a renamed record reads as a deletion AND an addition (no rename detection)",
          failed_with(res, chk.RECORD_DELETED) and failed_with(res, chk.RECORD_ADDED), res[1])

    def staged_add() -> None:
        shutil.copy2(fx.gen / held[0].path.name, fx.gen / "2099-06-06-staged.md")
        git(fx.root, "add", "--", f"{GEN_REL}/2099-06-06-staged.md")
    res = after_base(staged_add)
    check("F12 a staged new record -> RECORD_ADDED", failed_with(res, chk.RECORD_ADDED), res[1])

    def nested() -> None:
        (fx.gen / "nested").mkdir()
        shutil.copy2(fx.gen / held[0].path.name, fx.gen / "nested" / "x.md")
    res = after_base(nested)
    check("F13 a file in a subdirectory of the records is not a record -> OUT_OF_SCOPE",
          failed_with(res, chk.OUT_OF_SCOPE), res[1])
    res = after_base(lambda: git(fx.root, "commit", "-q", "--allow-empty", "-m", "moved"))
    check("F14 HEAD moved between preplan and convergence -> HEAD_MOVED", failed_with(res, chk.HEAD_MOVED), res[1])

    # ================================================================ the plan before and after
    section("[P] the plan before and after convergence")
    fx.reset()
    (fx.root / "auxsays" / "_data" / "fixture.yml").write_text("a: 3\n", encoding="utf-8")
    res = preplan()
    check("P1 a tracked file already differing before convergence -> TREE_NOT_CLEAN",
          failed_with(res, chk.TREE_NOT_CLEAN), res[1])
    fx.reset()
    (fx.root / "auxsays" / "notes.txt").write_text("already here\n", encoding="utf-8")
    pre = preplan()
    run_apply(fx.root)
    res = conv()
    check("P2 an untracked file present BEFORE convergence is not attributed to it (N = 0 passes)",
          passed(pre) and passed(res), res[1])
    fx.reset()
    res = run_check(fx.root, "preplan", "--out", str(fx.root / "plan.json"))
    check("P3 a plan file inside the checkout is refused as an error (exit 2), never a pass",
          res[0] == 2 and "DAVINCI ARCHIVE CHECK ERROR" in res[1], res[1])
    res = run_check(fx.root, "convergence", "--plan", str(td / "no-such-plan.json"))
    check("P4 convergence without a plan is an error (exit 2), never a pass", res[0] == 2, res[1])

    # ================================================================ render details
    section("[R] render parity details")
    fx.reset()
    pages = build_site(fx, site)
    add_notice(pages[victims[0].path.name])
    res = render()
    check("R1 an archived page carrying the notice twice -> DUPLICATE_NOTICE", failed_with(res, chk.DUPLICATE_NOTICE), res[1])

    pages = build_site(fx, site)
    stray = site / "updates" / "blackmagic-design" / "blackmagic-davinci" / "stray" / "index.html"
    stray.parent.mkdir(parents=True)
    stray.write_text(PAGE.format(title="stray", notice=NOTICE_HTML), encoding="utf-8")
    res = render()
    check("R2 a page no DaVinci record owns carrying the notice -> UNEXPECTED_NOTICE_PAGE",
          failed_with(res, chk.UNEXPECTED_NOTICE_PAGE), res[1])

    fx.reset()
    (fx.gen / spot19.path.name).unlink()
    build_site(fx, site)
    res = render()
    check("R3 no 19.1.4 record -> SPOT_ARCHIVED", failed_with(res, chk.SPOT_ARCHIVED), res[1])

    fx.reset()
    pages = build_site(fx, site)
    add_notice(pages[spot_active.path.name])
    res = render()
    check("R4 the chosen active page carrying the notice -> SPOT_ACTIVE", failed_with(res, chk.SPOT_ACTIVE), res[1])

    pages = build_site(fx, site)
    strip_notice(pages[victims[0].path.name])
    real_pick = chk.pick_active_spot
    try:
        chk.pick_active_spot = lambda recs_: next(r for r in recs_ if r.path.name == victims[0].path.name)
        fails, _lines = chk.render(fx.root, site)
    finally:
        chk.pick_active_spot = real_pick
    check("R5 a spot pick that is in fact archived is refused even when its page lacks the notice -> SPOT_ACTIVE",
          chk.SPOT_ACTIVE in {f.check for f in fails}, str([f.check for f in fails]))
    check("R6 the picker returns no record when none is active, and the newest stable active one otherwise",
          chk.pick_active_spot(archived) is None and spot_active.status != pol.ARCHIVED
          and spot_active.major == max(r.major for r in active if r.major is not None and not r.is_beta))

    fx.reset()
    replace_once(fx.gen / plain_active[0].path.name, b"\npermalink: ", b"\nold_permalink: ")
    build_site(fx, site)
    res = render()
    check("R7 a record with no literal permalink -> UNRESOLVABLE_PERMALINK",
          failed_with(res, chk.UNRESOLVABLE_PERMALINK), res[1])
    fx.reset()
    target = pol.read_front_matter(fx.gen / plain_active[1].path.name)["permalink"]
    t = set_field((fx.gen / plain_active[0].path.name).read_text(encoding="utf-8"), "permalink", target)
    (fx.gen / plain_active[0].path.name).write_text(t, encoding="utf-8", newline="")
    build_site(fx, site)
    res = render()
    check("R8 two records resolving to one page -> DUPLICATE_PAGE", failed_with(res, chk.DUPLICATE_PAGE), res[1])
    fx.reset()
    (fx.gen / "2099-07-07-broken.md").write_text("---\nproduct_id: blackmagic-davinci\nupdate_entry: [\n---\n",
                                                 encoding="utf-8")
    build_site(fx, site)
    res = render()
    check("R9 an unreadable DaVinci record -> UNREADABLE_RECORD", failed_with(res, chk.UNREADABLE_RECORD), res[1])
    res = run_check(fx.root, "render", "--site", str(td / "no-site"))
    check("R10 no built site is an error (exit 2), never a pass", res[0] == 2, res[1])

    # ================================================================ the workflow
    section("[W] the workflow")
    wf_text = WORKFLOW.read_text(encoding="utf-8")
    wf = yaml.safe_load(wf_text)
    on = wf.get(True) or wf.get("on") or {}
    paths = set((on.get("pull_request") or {}).get("paths") or [])
    check("W1 pull_request only, triggered by the check script, the policy, the CLI, the notice, the layout and itself",
          list(on) == ["pull_request"] and {
              "auxsays/scripts/ci/davinci_archive_check.py", "auxsays/scripts/lib/davinci_archive_policy.py",
              "auxsays/scripts/apply_davinci_archive_policy.py", "auxsays/_includes/archived-notice.html",
              "auxsays/_layouts/aux-update.html", ".github/workflows/patch-ingest.yml",
              ".github/workflows/davinci-archive-build-check.yml"} <= paths, str(sorted(paths)))
    steps = wf["jobs"]["build-check"]["steps"]
    runs = [str(s.get("run") or "") for s in steps]
    all_run = "\n".join(runs)
    check("W2 read-only: contents: read, no write permission, nothing committed, pushed, dispatched or deployed",
          wf.get("permissions") == {"contents": "read"} and "permissions" not in wf["jobs"]["build-check"]
          and not re.search(r"contents:\s*write|write-all|git\s+(commit|push)|automation_writeback|gh workflow|deploy-pages",
                            all_run + "\n" + yaml.safe_dump(wf.get("permissions"))), str(wf.get("permissions")))

    def idx(pred) -> int:
        return next((i for i, r in enumerate(runs) if pred(r)), -1)
    i_pre = idx(lambda r: "davinci_archive_check.py preplan" in r)
    i_apply = idx(lambda r: "apply_davinci_archive_policy.py --write --confirm-write" in r)
    i_conv = idx(lambda r: "davinci_archive_check.py convergence" in r)
    i_build = idx(lambda r: "bundle exec jekyll build" in r)
    i_render = idx(lambda r: "davinci_archive_check.py render" in r)
    check("W3 preplan -> apply -> convergence -> site build -> render, in that order",
          -1 < i_pre < i_apply < i_conv < i_build < i_render, f"{i_pre} {i_apply} {i_conv} {i_build} {i_render}")
    plan_args = re.findall(r"--(?:out|plan) \"(\$RUNNER_TEMP/[^\"]+)\"", all_run)
    check("W4 the plan lives in runner temp, outside the checkout, and convergence reads the file preplan wrote",
          len(plan_args) == 2 and plan_args[0] == plan_args[1], str(plan_args))
    check("W5 the frozen migration numbers are gone: no count of 100, no 21.0.4 page, no grep-count of notices",
          not re.search(r"-ne 100|\b100\b|21-0-4|with_notice|grep -rl", all_run), "")
    check("W6 every check step runs under errexit, nounset and pipefail",
          all("set -euo pipefail" in runs[i] for i in (i_pre, i_apply, i_conv, i_render)))

    bash = bash_exe()
    check("W7 a bash is available to execute the steps (not a grep)", bash is not None)
    if bash and min(i_pre, i_apply, i_conv, i_render) >= 0:
        shim = ('python() {\n'
                '  case "$1" in\n'
                '    auxsays/scripts/ci/davinci_archive_check.py) shift; "$REAL_PY" "$CHECK_PY" "$@" --root "$FX_ROOT" ;;\n'
                '    auxsays/scripts/apply_davinci_archive_policy.py) shift; "$REAL_PY" "$APPLY_PY" "$@" --root "$FX_ROOT/auxsays" ;;\n'
                '    *) echo "unexpected python call: $*" >&2; return 97 ;;\n'
                '  esac\n'
                '}\n')
        runner_temp = td / "rt"
        runner_temp.mkdir(exist_ok=True)

        def step(i: int) -> tuple[int, str]:
            script = td / "step.sh"
            script.write_text(shim + runs[i], encoding="utf-8", newline="\n")
            env = child_env()
            env.update({"REAL_PY": sys.executable.replace("\\", "/"), "CHECK_PY": str(CHECK).replace("\\", "/"),
                        "APPLY_PY": str(APPLY).replace("\\", "/"), "FX_ROOT": str(fx.root).replace("\\", "/"),
                        "RUNNER_TEMP": str(runner_temp).replace("\\", "/")})
            proc = subprocess.run([bash, "--noprofile", "--norc", "-eo", "pipefail", str(script)], cwd=str(fx.root),
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                                  timeout=300)
            return proc.returncode, proc.stdout + proc.stderr

        fx.reset(n3_head)
        outs = [step(i) for i in (i_pre, i_apply, i_conv)]
        check("W8 EXECUTED on N = 3: the preplan, apply and convergence steps all succeed, and N = 3",
              all(c == 0 for c, _ in outs) and "N = 3 record(s)" in outs[2][1], " / ".join(o for _, o in outs))
        site_in_tree = fx.root / "auxsays" / "_site"
        pages = build_site(fx, site_in_tree)
        rc_ok, out_ok = step(i_render)
        strip_notice(pages[three[0].path.name])
        rc_bad, out_bad = step(i_render)
        check("W9 EXECUTED: the render step passes on a correct build and fails, by name, on a missing notice",
              rc_ok == 0 and rc_bad != 0 and "FAIL  MISSING_NOTICE:" in out_bad, out_ok + " / " + out_bad)
        fx.reset()
        text = set_field(held[0].path.read_text(encoding="utf-8"), "update_version", "'2026'")
        (fx.gen / "2099-03-03-davinci-resolve-2026.md").write_text(text, encoding="utf-8", newline="")
        fx.commit("implausible major")
        rc, out = step(i_pre)
        check("W10 EXECUTED on a refused plan: the preplan step fails, by name", rc != 0 and "FAIL  PLAN_REFUSED:" in out, out)

    print()
    print("=" * 78)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    for e in FAILURES:
        print(f"  - {e}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        print(f"Results: {PASS}/{PASS + FAIL + 1} passed, {FAIL + 1} failed")
        sys.exit(1)
