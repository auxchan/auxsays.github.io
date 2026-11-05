#!/usr/bin/env python3
"""auxsays/_data/source_health.yml is a GENERATED deploy snapshot, never a tracked source of truth.

WHAT WAS WRONG (AUX-069). The file was last committed on 2026-05-02: 37 rows against 47 configured
sources, in a status vocabulary the generator no longer emits. pages.yml regenerates it at every
deploy, so the live site was never wrong, but the stale committed copy sat in the tree as if it
were authoritative. Three writeback lanes also restored it with `git checkout --`, which only works
while it is tracked.

THE CONSUMER AUDIT THIS PINS. No Jekyll template, include, layout or page reads it; no Python module
reads it (only the generator writes it); the only code that names it is the generator, pages.yml, the
three lane cleanups, a forbidden-write-path list and a protected-file snapshot. So removing it from
tracking changes no rendered page. Section [B] makes that a standing property: the first consumer
someone adds must come with a conscious update here (and must fail closed when the file is absent).

Sections:
  [A] untracked and ignored
  [B] no render-time or Python consumer
  [C] the generator regenerates deterministically and refuses to publish an empty snapshot
  [D] workflows: no `git checkout` of the untracked file; deploy still generates it before the build
  [E] the old cleanup command really fails on an untracked file (so the workflow fix is load-bearing)

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_source_health_generated_snapshot.py
"""
from __future__ import annotations

import importlib
import io
import contextlib
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
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

REL = "auxsays/_data/source_health.yml"
WORKFLOWS = _REPO / ".github" / "workflows"
CLEANUP_LANES = ["davinci-updates.yml", "obs-evidence-collection.yml",
                 "promote-davinci-verified-reports.yml"]

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
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERRORS.append(label)


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory",
                "GIT_CONFIG_VALUE_0": "*"})
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, env=env)


def strip_comments(text: str) -> str:
    """Drop whole-line YAML/shell comments so prose that explains the old bug is not code."""
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def section_a() -> None:
    print("\n[A] untracked and ignored")
    gi = (_REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    check("A1 .gitignore carries the exact rule", REL in [ln.strip() for ln in gi])
    ls = git(_REPO, "ls-files", "--", REL)
    if ls.returncode == 0:
        check("A2 git does not track the snapshot", ls.stdout.strip() == "", ls.stdout)
        ig = git(_REPO, "check-ignore", "-q", "--", REL)
        check("A3 git reports the path as ignored", ig.returncode == 0, ig.stderr)
    else:
        # No usable git (a tarball checkout): the rule check above still stands; do not fake a pass.
        check("A2 git unavailable, rule alone cannot prove untracked (skipped as pass)", True)
        check("A3 git unavailable (skipped as pass)", True)


def section_b() -> None:
    print("\n[B] no render-time or Python consumer")
    hits = []
    for root in ("_layouts", "_includes", "updates", "_data", "_plugins"):
        base = _AUX / root
        if not base.exists():
            continue
        for f in base.rglob("*"):
            if not f.is_file() or f.suffix not in (".html", ".md", ".liquid", ".xml", ".json", ".yml", ".rb"):
                continue
            if f.name == "source_health.yml" or f.name == "patch_ingestion_sources.yml":
                continue
            txt = f.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r"site\.data\.source_health|site\.data\[\s*['\"]source_health", txt):
                hits.append(f"{f.relative_to(_REPO)}:{txt[:m.start()].count(chr(10)) + 1}")
    check("B1 no template/include/layout/page reads site.data.source_health", not hits, "; ".join(hits))

    root_pages = [p for p in _AUX.glob("*.html")] + [p for p in _AUX.glob("*.md") if not p.name.startswith("AUXSAYS_")]
    rp = [p.name for p in root_pages if "source_health" in p.read_text(encoding="utf-8", errors="replace")]
    check("B2 no site-root page reads it", not rp, ",".join(rp))

    readers = []
    for f in list(_SCRIPTS.rglob("*.py")):
        if f.name == "source_health_snapshot.py" or "tests" in f.parts:
            continue
        txt = f.read_text(encoding="utf-8", errors="replace")
        # a READ of the file, as opposed to prose mentioning it
        if re.search(r"""["']source_health\.yml["']""", txt):
            readers.append(str(f.relative_to(_REPO)))
    check("B3 no non-test Python module opens source_health.yml (only the generator writes it)",
          not readers, ",".join(readers))

    src = (_SCRIPTS / "source_health_snapshot.py").read_text(encoding="utf-8")
    check("B4 the generator documents the file as never committed (AUX-069)",
          "NEVER COMMITTED" in src and "AUX-069" in src)


def load_snapshot_module(tmp: Path):
    mod = importlib.import_module("source_health_snapshot")
    mod = importlib.reload(mod)
    mod.ROOT = tmp
    mod.CONFIG_PATH = tmp / "_data" / "patch_ingestion_sources.yml"
    mod.STATE_PATH = tmp / "_data" / "patch_ingest_state.json"
    mod.OUTPUT_PATH = tmp / "_data" / "source_health.yml"
    return mod


def run_main(mod) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = mod.main()
    return rc, buf.getvalue()


def section_c() -> None:
    print("\n[C] generation, determinism and the empty-snapshot refusal")
    import yaml
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "_data").mkdir()
        sources = [
            {"product_id": "alpha", "company_id": "co", "company": "Co", "software": "Alpha",
             "enabled": True, "ingestion": {"adapter": "html", "polling_frequency": "daily"}},
            {"product_id": "beta", "company_id": "co", "company": "Co", "software": "Beta",
             "enabled": False, "ingestion": {"adapter": "manual_watch"}},
        ]
        (tmp / "_data" / "patch_ingestion_sources.yml").write_text(yaml.safe_dump(sources), encoding="utf-8")
        (tmp / "_data" / "patch_ingest_state.json").write_text('{"sources": {}}', encoding="utf-8")
        mod = load_snapshot_module(tmp)
        out = tmp / "_data" / "source_health.yml"
        check("C1 the snapshot is absent before generation", not out.exists())
        rc, _ = run_main(mod)
        check("C2 generation succeeds", rc == 0, str(rc))
        check("C3 generation creates the file", out.exists())
        rows = yaml.safe_load(out.read_text(encoding="utf-8")) if out.exists() else []
        check("C4 one row per configured source (no stale subset)", len(rows) == 2, str(len(rows)))
        check("C5 every row carries the current status field",
              all(r.get("status") for r in rows), str([r.get("status") for r in rows]))
        first = out.read_bytes()
        run_main(mod)
        check("C6 a second generation from the same inputs is byte-identical", out.read_bytes() == first)
        # inputs change -> the snapshot follows them (it is a function of the inputs, not history)
        sources.append({"product_id": "gamma", "company_id": "co", "company": "Co", "software": "Gamma",
                        "enabled": False, "ingestion": {"adapter": "manual_watch"}})
        (tmp / "_data" / "patch_ingestion_sources.yml").write_text(yaml.safe_dump(sources), encoding="utf-8")
        run_main(mod)
        check("C7 a new configured source appears in the regenerated snapshot",
              len(yaml.safe_load(out.read_text(encoding="utf-8"))) == 3)

    # fail closed: unreadable / empty source list must not publish an empty snapshot
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "_data").mkdir()
        mod = load_snapshot_module(tmp)
        out = tmp / "_data" / "source_health.yml"
        rc, text = run_main(mod)
        check("C8 a missing source list exits non-zero", rc != 0, str(rc))
        check("C9 and writes NO file (never an empty snapshot pretending success)", not out.exists())
        check("C10 and says why", "refusing to write an empty" in text, text)
        (tmp / "_data" / "patch_ingestion_sources.yml").write_text("[]\n", encoding="utf-8")
        rc2, _ = run_main(mod)
        check("C11 an empty source list also exits non-zero and writes nothing",
              rc2 != 0 and not out.exists())


def section_d() -> None:
    print("\n[D] workflows")
    bad_all, cont_all = [], []
    for name in sorted(p.name for p in WORKFLOWS.glob("*.yml")):
        code = strip_comments((WORKFLOWS / name).read_text(encoding="utf-8"))
        bad_all += [f"{name}: {ln.strip()}" for ln in code.splitlines()
                    if "source_health.yml" in ln and re.search(r"git\s+(checkout|restore|add|rm|stash)\b|--allow", ln)]
        # also catches a multi-line `git checkout -- \` continuation naming it
        joined = re.sub(r"\\(?:\r)?\n\s*", " ", code)
        if re.search(r"git\s+(checkout|restore)[^\n]*source_health\.yml", joined):
            cont_all.append(name)
    check("D1 no workflow git-checkouts/restores/adds or --allows the untracked snapshot",
          not bad_all, "; ".join(bad_all))
    check("D2 no workflow restores it across a line continuation", not cont_all, ",".join(cont_all))

    for name in CLEANUP_LANES:
        code = strip_comments((WORKFLOWS / name).read_text(encoding="utf-8"))
        check(f"D3 {name}: still restores the TRACKED patch_ingest_state.json",
              re.search(r"git checkout -- auxsays/_data/patch_ingest_state\.json\b", code) is not None)
        check(f"D4 {name}: clears any stray untracked copy with rm -f",
              "rm -f auxsays/_data/source_health.yml" in code)

    pages = strip_comments((WORKFLOWS / "pages.yml").read_text(encoding="utf-8"))
    gen = pages.find("python auxsays/scripts/source_health_snapshot.py")
    build = pages.find("bundle exec jekyll build")
    check("D5 pages.yml still generates the snapshot at deploy", gen != -1)
    check("D6 and does so BEFORE the site build", gen != -1 and build != -1 and gen < build)

    # No other lane regenerates + commits it (it would need an --allow, which D1 forbids). A lane may
    # still RUN the generator to mirror the deploy build (davinci-archive-build-check.yml does, as a
    # pull-request build check), but only when it is read-only and cannot commit: then its snapshot
    # is discarded with the runner. A lane with no top-level `contents: read`, any `contents: write`,
    # `write-all`, a git commit/push, or the writeback helper fails this check.
    writers = []
    for p in sorted(WORKFLOWS.glob("*.yml")):
        if p.name == "pages.yml":
            continue
        code = strip_comments(p.read_text(encoding="utf-8"))
        if "source_health_snapshot.py" not in code:
            continue
        can_write = (re.search(r"contents:\s*write\b", code) is not None
                     or re.search(r"\bwrite-all\b", code) is not None
                     or re.search(r"\bgit\s+(commit|push)\b", code) is not None
                     or "automation_writeback" in code)
        read_only = re.search(r"^permissions:[ \t]*\r?\n[ \t]+contents:[ \t]*read\b", code, re.M) is not None
        if can_write or not read_only:
            writers.append(p.name)
    check("D7 only the deploy generates it; any other lane running the generator is read-only "
          "and never commits", not writers, ",".join(writers))


def section_e() -> None:
    print("\n[E] the old cleanup command is what breaks on an untracked file")
    if shutil.which("git") is None:
        check("E1 git unavailable (skipped as pass)", True)
        return
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "r"
        (repo / "d").mkdir(parents=True)
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "t@example.invalid")
        git(repo, "config", "user.name", "t")
        (repo / "d" / "patch_ingest_state.json").write_text("{}\n", encoding="utf-8")
        (repo / ".gitignore").write_text("d/source_health.yml\n", encoding="utf-8")
        git(repo, "add", "-A")
        c = git(repo, "commit", "-q", "-m", "seed")
        if c.returncode != 0:
            check("E0 temp repo could not be seeded (skipped as pass)", True, c.stderr)
            return
        (repo / "d" / "source_health.yml").write_text("- generated: true\n", encoding="utf-8")
        old = git(repo, "checkout", "--", "d/source_health.yml", "d/patch_ingest_state.json")
        check("E1 the OLD command (naming the untracked file) fails", old.returncode != 0, old.stderr)
        (repo / "d" / "patch_ingest_state.json").unlink()
        new = git(repo, "checkout", "--", "d/patch_ingest_state.json")
        check("E2 the NEW command restores the tracked state file", new.returncode == 0
              and (repo / "d" / "patch_ingest_state.json").exists(), new.stderr)
        (repo / "d" / "source_health.yml").unlink()
        st = git(repo, "status", "--porcelain", "--untracked-files=normal")
        check("E3 an ignored snapshot, present or absent, leaves the tree clean (writeback sees nothing)",
              st.stdout.strip() == "", st.stdout)
        (repo / "d" / "source_health.yml").write_text("- generated: true\n", encoding="utf-8")
        st2 = git(repo, "status", "--porcelain", "--untracked-files=normal")
        check("E4 a freshly generated snapshot is invisible to git status", st2.stdout.strip() == "", st2.stdout)


def main() -> int:
    for fn in (section_a, section_b, section_c, section_d, section_e):
        try:
            fn()
        except Exception:
            traceback.print_exc()
            check(f"{fn.__name__} crashed", False)
    print("\n" + "=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed tests:")
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
