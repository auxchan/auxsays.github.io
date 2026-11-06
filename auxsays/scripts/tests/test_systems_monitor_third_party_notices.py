#!/usr/bin/env python3
"""The published Systems Monitor ships its third-party licence notices beside the bundle (AUX-082).

The deployed bundle (/systems-monitor/assets/main-*.js) contains React, react-dom, react-is, Recharts and
their dependencies, and the minifier strips every licence comment. Nothing served beside it carried the
copyright and permission notices those licences require. systems-monitor/app/THIRD_PARTY_NOTICES.txt is
now generated from the lockfile's production set and the licence files the installed packages ship
(scripts/generate-third-party-notices.mjs), copied by the build to /systems-monitor/THIRD_PARTY_NOTICES.txt
and linked from the app.

This suite runs the REAL Node scripts. Node is required: its absence is a failure, never a skip (the
same contract as test_patch_stack_dashboard.py). Nothing outside a temp directory is written; the real
tree is only read.

  A  the committed file, judged with no node_modules: what a pull request can be judged on
  B  hermetic regeneration over a fixture lockfile and node_modules: deterministic bytes
  C  mutants: each must fail a NAMED check (drop a package, a dependency added without a notice, stale
     versions, a licence edit, a package with no licence file, a stale supplement)
  D  the build wiring, executed: compose copies the file, the deploy's built-site check refuses a site
     without it, clean removes it, and the published-payload verifier lets it through
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
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]          # auxsays/
REPO = ROOT.parent
APP = REPO / "systems-monitor" / "app"
SCRIPTS = APP / "scripts"
CLI = "scripts/generate-third-party-notices.mjs"
NOTICES = APP / "THIRD_PARTY_NOTICES.txt"
NOTICES_URL = "/systems-monitor/THIRD_PARTY_NOTICES.txt"
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

NODE = shutil.which("node")
PASS = FAIL = 0
FAILURES: list[str] = []
RULE = "=" * 80


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f" -- {detail}" if detail else ""))


def node(cwd: Path, *args: str) -> SimpleNamespace:
    """Run a real script under node. Without node every caller's check fails rather than vanishing."""
    if not NODE:
        return SimpleNamespace(returncode=127, stdout="", stderr="node not on PATH")
    res = subprocess.run([NODE, *args], cwd=str(cwd), capture_output=True, text=True,
                         encoding="utf-8", timeout=180)
    return SimpleNamespace(returncode=res.returncode, stdout=res.stdout or "", stderr=res.stderr or "")


def named(res: SimpleNamespace, code: str, needle: str = "") -> bool:
    """Exit 1 and a `CODE: ...` line that names `needle`."""
    lines = [line for line in res.stderr.splitlines() if line.startswith(f"{code}: ")]
    return res.returncode == 1 and any(needle in line for line in lines)


def show(res: SimpleNamespace) -> str:
    return f"exit {res.returncode}; stderr: {res.stderr.strip()[-400:]}; stdout: {res.stdout.strip()[-200:]}"


# ---------------------------------------------------------------- independent oracles (test-side)
def locked_production(lock: dict) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for path, meta in (lock.get("packages") or {}).items():
        if not path or meta.get("dev") is True or not meta.get("version"):
            continue
        name = meta.get("name") or path.split("node_modules/")[-1]
        out[(name, meta["version"])] = meta.get("license") or "UNKNOWN"
    return out


def notice_entries(text: str) -> list[tuple[str, str, str | None]]:
    lines = text.split("\n")
    start = next(i for i, line in enumerate(lines) if line == "PACKAGES" and lines[i - 1] == RULE)
    end = next(i for i, line in enumerate(lines) if line == "LICENCE TEXTS" and lines[i - 1] == RULE)
    entries: list[list] = []
    for line in lines[start + 2:end - 1]:
        if line and not line.startswith(" "):
            name, version = line.rsplit(" ", 1)
            entries.append([name, version, None])
        elif line.startswith("  Licence: ") and entries:
            entries[-1][2] = line[len("  Licence: "):]
    return [tuple(e) for e in entries]


# ---------------------------------------------------------------- the hermetic fixture
MIT_ALPHA = ("MIT License\n\nCopyright (c) 2020 Alpha Author\n\nPermission is hereby granted, free of charge, to any "
             "person obtaining a copy of this software.\n\nThe above copyright notice and this permission notice "
             "shall be included in all copies or substantial portions of the Software.\n\n"
             # A disclaimer wrapped so a line STARTS with "COPYRIGHT HOLDERS": it is not a notice.
             "IN NO EVENT SHALL THE AUTHORS OR\nCOPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM.\n")
MIT_ALPHA_OLD = MIT_ALPHA.replace("2020", "2019")
ISC_BETA = ("ISC License\n\nCopyright 2021 Beta Author\n\nPermission to use, copy, modify, and/or distribute this "
            "software for any purpose is hereby granted, provided that the above copyright notice appear in all copies.\n")
BSD_DELTA = ("Copyright (c) 2019, Delta Org\nAll rights reserved.\n\nRedistribution and use in source and binary "
             "forms are permitted provided that the above copyright notice is retained.\n")
NOTICE_DELTA = "Delta\n\nPortions of this software are derived from Example.\nCopyright 2018 Example Corp\n"
ISC_D3 = ("Copyright 2010-2021 Mike Bostock\n\nPermission to use, copy, modify, and/or distribute this software for "
          "any purpose with or without fee is hereby granted.\n")

# install path -> (name, version, license, dev, {relative file: text})
FIXTURE = {
    "node_modules/@scope/delta": ("@scope/delta", "1.2.3", "BSD-3-Clause", False, {"LICENSE": BSD_DELTA, "NOTICE": NOTICE_DELTA}),
    "node_modules/alpha": ("alpha", "1.0.0", "MIT", False, {"LICENSE": MIT_ALPHA}),
    "node_modules/beta": ("beta", "2.0.0", "ISC", False, {"LICENSE.md": ISC_BETA}),
    # A second production version of alpha, nested under beta: one name, two notices.
    "node_modules/beta/node_modules/alpha": ("alpha", "0.9.0", "MIT", False, {"license": MIT_ALPHA_OLD}),
    "node_modules/devonly": ("devonly", "9.9.9", "MIT", True, {"LICENSE": MIT_ALPHA}),
    # The same text as alpha's, written with a BOM, CRLF endings and trailing spaces: it must
    # normalise to the same bytes and so be printed ONCE.
    "node_modules/gamma": ("gamma", "3.0.0", "MIT", False,
                           {"LICENSE": "﻿" + MIT_ALPHA.replace("\n", "  \r\n")}),
    # The one reviewed supplement: no root licence file, vendored ISC texts only.
    "node_modules/victory-vendor": ("victory-vendor", "37.3.6", "MIT AND ISC", False,
                                    {"lib-vendor/d3-x/LICENSE": ISC_D3}),
}


def write_lock(app: Path, packages: dict, reverse: bool = False) -> None:
    entries = {"": {"name": "fixture", "version": "1.0.0"}}
    items = sorted(packages.items(), reverse=reverse)
    for path, (name, version, licence, dev, _files) in items:
        meta = {"version": version, "resolved": f"https://registry.npmjs.org/{name}/-/x-{version}.tgz", "license": licence}
        if dev:
            meta["dev"] = True
        if path.split("node_modules/")[-1] != name:
            meta["name"] = name
        entries[path] = meta
    lock = {"name": "fixture", "version": "1.0.0", "lockfileVersion": 3, "requires": True, "packages": entries}
    (app / "package-lock.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8", newline="\n")


def install(app: Path, packages: dict) -> None:
    for path, (name, version, licence, _dev, files) in packages.items():
        pkg = app.joinpath(*path.split("/"))
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "package.json").write_text(json.dumps({"name": name, "version": version, "license": licence}),
                                          encoding="utf-8", newline="\n")
        for rel, text in files.items():
            target = pkg.joinpath(*rel.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode("utf-8"))


def build_mirror(base: Path) -> Path:
    """A repo-shaped mirror: the real scripts, a fixture lockfile and node_modules. Returns its app dir."""
    app = base / "systems-monitor" / "app"
    shutil.copytree(SCRIPTS, app / "scripts", ignore=shutil.ignore_patterns("*.test.*"))
    (base / "auxsays" / "systems-monitor").mkdir(parents=True)
    write_lock(app, FIXTURE)
    install(app, FIXTURE)
    return app


def fresh(pristine: Path, scratch: Path, label: str) -> Path:
    target = scratch / label
    shutil.copytree(pristine, target)
    return target / "systems-monitor" / "app"


def drop_entry(text: str, header: str) -> str:
    """Remove one package's block from the PACKAGES section (header line through its blank line)."""
    lines = text.split("\n")
    i = lines.index(header)
    j = i
    while lines[j]:
        j += 1
    return "\n".join(lines[:i] + lines[j + 1:])


# ---------------------------------------------------------------- sections
def section_a_committed_file() -> None:
    print("\n[A] the committed notices, judged without node_modules")
    res = node(APP, CLI, "--check-committed")
    check("A1 --check-committed passes on the real tree", res.returncode == 0, show(res))

    lock = json.loads((APP / "package-lock.json").read_text(encoding="utf-8"))
    inventory = json.loads((APP / "DEPENDENCY_LICENSE_INVENTORY.json").read_text(encoding="utf-8"))
    raw = NOTICES.read_bytes() if NOTICES.exists() else b""
    text = raw.decode("utf-8", errors="replace")
    expected = locked_production(lock)
    try:
        entries = notice_entries(text)
    except StopIteration:
        entries = []
    noticed = {(n, v) for n, v, _ in entries}
    check("A2 the notices name exactly the lockfile's production set (test-side oracle)",
          bool(expected) and noticed == set(expected) and len(entries) == len(expected),
          f"missing {sorted(set(expected) - noticed)[:5]}, extra {sorted(noticed - set(expected))[:5]}")
    listed = {(p["name"], p["version"]) for p in inventory.get("packages", [])}
    check("A3 ... and exactly the licence inventory's set", listed == noticed and inventory.get("packageCount") == len(noticed),
          f"inventory {len(listed)}, notices {len(noticed)}")
    wrong = [(n, v, lic, expected.get((n, v))) for n, v, lic in entries if expected.get((n, v)) != lic]
    check("A4 every entry carries the lockfile's licence identifier", not wrong and bool(entries), str(wrong[:3]))
    check("A5 the bytes are canonical: UTF-8, LF only, no trailing spaces, one final newline",
          bool(raw) and b"\r" not in raw and raw.endswith(b"\n") and not raw.endswith(b"\n\n")
          and not any(line != line.rstrip() for line in text.split("\n")),
          "CR, trailing whitespace or a missing/duplicated final newline")
    keys = [f"{n}@{v}" for n, v, _ in entries]
    check("A6 entries are in code-point order (locale-independent)", keys == sorted(keys) and bool(keys))

    package = json.loads((APP / "package.json").read_text(encoding="utf-8"))
    build = package.get("scripts", {}).get("build", "")
    steps = [s.strip() for s in build.split("&&")]
    check_at = steps.index("node scripts/generate-third-party-notices.mjs --check") if "node scripts/generate-third-party-notices.mjs --check" in steps else -1
    compose_at = steps.index("node scripts/compose-jekyll.mjs") if "node scripts/compose-jekyll.mjs" in steps else -1
    check("A7 the deploy build regenerates and compares BEFORE it publishes (check precedes compose)",
          0 <= check_at < compose_at, build)
    check("A8 `npm run notices` regenerates the file",
          package.get("scripts", {}).get("notices") == "node scripts/generate-third-party-notices.mjs --write")

    ignored = subprocess.run(["git", "check-ignore", "-q", "auxsays/systems-monitor/THIRD_PARTY_NOTICES.txt"],
                             cwd=str(REPO), capture_output=True)
    check("A9 the build's published copy is git-ignored (the committed source is the app's file)", ignored.returncode == 0)

    link_src = (APP / "src" / "shared" / "ThirdPartyNoticesLink.tsx").read_text(encoding="utf-8")
    lib_src = (SCRIPTS / "third-party-notices.mjs").read_text(encoding="utf-8")
    paths_src = (SCRIPTS / "paths.mjs").read_text(encoding="utf-8")
    shell_src = (APP / "src" / "shell" / "AppShell.tsx").read_text(encoding="utf-8")
    check("A10 the app's link, the checker and the published path name the same URL (source pin)",
          f'THIRD_PARTY_NOTICES_URL = "{NOTICES_URL}"' in link_src and f'NOTICES_URL = "{NOTICES_URL}"' in lib_src
          and '"auxsays", "systems-monitor", "THIRD_PARTY_NOTICES.txt"' in paths_src)
    check("A11 both production shells render the link (persistent world and classic)",
          shell_src.count("<ThirdPartyNoticesLink />") == 2, f"found {shell_src.count('<ThirdPartyNoticesLink />')}")


def section_b_regeneration(pristine: Path, scratch: Path) -> None:
    print("\n[B] hermetic regeneration is deterministic")
    app = fresh(pristine, scratch, "b")
    inv = node(app, "scripts/generate-license-inventory.mjs")
    check("B1 the real inventory script runs over the fixture (shared production predicate)", inv.returncode == 0, show(inv))
    res = node(app, CLI, "--write")
    out = app / "THIRD_PARTY_NOTICES.txt"
    check("B2 --write succeeds", res.returncode == 0 and out.exists(), show(res))
    first = out.read_bytes() if out.exists() else b""
    text = first.decode("utf-8", errors="replace")
    res = node(app, CLI, "--check")
    check("B3 --check: the committed bytes equal a fresh regeneration", res.returncode == 0, show(res))
    res = node(app, CLI, "--check-committed")
    check("B4 --check-committed passes on what --write produced", res.returncode == 0, show(res))
    node(app, CLI, "--write")
    check("B5 writing twice gives the same bytes", out.read_bytes() == first)
    write_lock(app, FIXTURE, reverse=True)
    node(app, CLI, "--write")
    check("B6 lockfile entry order does not change a byte", out.read_bytes() == first)

    entries = notice_entries(text) if text else []
    keys = [f"{n}@{v}" for n, v, _ in entries]
    check("B7 exactly the production set, sorted: the dev-only package is absent, the nested alpha 0.9.0 present",
          keys == ["@scope/delta@1.2.3", "alpha@0.9.0", "alpha@1.0.0", "beta@2.0.0", "gamma@3.0.0", "victory-vendor@37.3.6"],
          str(keys))
    check("B8 a text written with BOM, CRLF and trailing spaces normalises to its LF twin and is printed ONCE",
          text.count("Copyright (c) 2020 Alpha Author\n\nPermission") == 1
          and "\n  alpha 1.0.0\n  gamma 3.0.0\n" in text and "Distinct licence texts: 7" in text, "dedup or normalisation broke")
    check("B9 NOTICE files are reproduced beside the licence", "Portions of this software are derived from Example." in text
          and "[T2] NOTICE" in text)
    check("B10 copyright lines are extracted; a wrapped 'COPYRIGHT HOLDERS BE LIABLE' line is not one",
          "  Copyright: Copyright (c) 2019, Delta Org\n             Copyright 2018 Example Corp\n" in text
          and "\nCOPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM." in text
          and "  Copyright: Copyright (c) 2020 Alpha Author\n  Licence text:" in text
          and "             COPYRIGHT HOLDERS" not in text, "copyright extraction drifted")
    check("B11 the reviewed supplement adds the MIT text for victory-vendor's own code, after its vendored texts",
          "lib-vendor/d3-x/LICENSE\n                [T7] MIT License (standard text; the package ships none)" in text
          and "Permission is hereby granted, free of charge, to any person obtaining a copy\nof this software" in text, text[-600:])


def section_c_mutants(pristine: Path, scratch: Path) -> None:
    print("\n[C] mutants fail a NAMED check")
    # Each mutant starts from a clean, regenerated fixture.
    def clean(label: str) -> Path:
        app = fresh(pristine, scratch, label)
        node(app, "scripts/generate-license-inventory.mjs")
        node(app, CLI, "--write")
        return app

    app = clean("c_drop")
    notices = app / "THIRD_PARTY_NOTICES.txt"
    notices.write_text(drop_entry(notices.read_text(encoding="utf-8"), "beta 2.0.0"), encoding="utf-8", newline="\n")
    res = node(app, CLI, "--check-committed")
    check("C1 drop a package from the notices -> NOTICE_PACKAGE_MISSING names it (offline)",
          named(res, "NOTICE_PACKAGE_MISSING", "beta@2.0.0"), show(res))
    res = node(app, CLI, "--check")
    check("C2 ... and the deploy regeneration names it and refuses the bytes",
          named(res, "NOTICE_PACKAGE_MISSING", "beta@2.0.0") and named(res, "NOTICE_NOT_REPRODUCIBLE"), show(res))

    app = clean("c_added")
    added = dict(FIXTURE)
    added["node_modules/epsilon"] = ("epsilon", "1.0.0", "MIT", False, {"LICENSE": MIT_ALPHA.replace("Alpha", "Epsilon")})
    write_lock(app, added)
    install(app, {"node_modules/epsilon": added["node_modules/epsilon"]})
    res = node(app, CLI, "--check-committed")
    check("C3 a dependency added without a notice -> NOTICE_PACKAGE_MISSING (and the stale inventory is named too)",
          named(res, "NOTICE_PACKAGE_MISSING", "epsilon@1.0.0") and named(res, "NOTICE_INVENTORY_MISMATCH", "epsilon@1.0.0"), show(res))
    node(app, "scripts/generate-license-inventory.mjs")
    res = node(app, CLI, "--check-committed")
    check("C4 ... still refused once the inventory is regenerated: the notice itself is missing",
          named(res, "NOTICE_PACKAGE_MISSING", "epsilon@1.0.0") and "NOTICE_INVENTORY_MISMATCH" not in res.stderr, show(res))
    res = node(app, CLI, "--check")
    check("C5 ... and the deploy regeneration refuses it", named(res, "NOTICE_PACKAGE_MISSING", "epsilon@1.0.0")
          and named(res, "NOTICE_NOT_REPRODUCIBLE"), show(res))
    node(app, CLI, "--write")
    res = node(app, CLI, "--check")
    check("C6 regenerating with `npm run notices` clears it", res.returncode == 0, show(res))

    app = clean("c_stale")
    bumped = dict(FIXTURE)
    bumped["node_modules/beta"] = ("beta", "2.1.0", "ISC", False, {"LICENSE.md": ISC_BETA})
    write_lock(app, bumped)
    install(app, {"node_modules/beta": bumped["node_modules/beta"]})
    node(app, "scripts/generate-license-inventory.mjs")
    res = node(app, CLI, "--check-committed")
    check("C7 a stale version -> NOTICE_VERSION_STALE names the noticed and the locked version",
          named(res, "NOTICE_VERSION_STALE", "beta: the notice covers 2.0.0, the lockfile installs 2.1.0"), show(res))

    app = clean("c_installed")
    install(app, {"node_modules/beta": ("beta", "2.1.0", "ISC", False, {"LICENSE.md": ISC_BETA})})
    res = node(app, CLI, "--check")
    check("C8 an installed package that is not the locked version -> NOTICE_INSTALLED_VERSION_MISMATCH",
          named(res, "NOTICE_INSTALLED_VERSION_MISMATCH", "beta@2.0.0"), show(res))

    app = clean("c_licence")
    relicensed = dict(FIXTURE)
    relicensed["node_modules/beta"] = ("beta", "2.0.0", "MIT", False, {"LICENSE.md": ISC_BETA})
    write_lock(app, relicensed)
    node(app, "scripts/generate-license-inventory.mjs")
    res = node(app, CLI, "--check-committed")
    check("C9 a licence identifier that changed in the lockfile -> NOTICE_LICENCE_MISMATCH",
          named(res, "NOTICE_LICENCE_MISMATCH", "beta@2.0.0: the notice says ISC, the lockfile says MIT"), show(res))

    app = clean("c_extra")
    removed = {k: v for k, v in FIXTURE.items() if k != "node_modules/gamma"}
    write_lock(app, removed)
    node(app, "scripts/generate-license-inventory.mjs")
    res = node(app, CLI, "--check-committed")
    check("C10 a notice for a package no longer depended on -> NOTICE_PACKAGE_EXTRA",
          named(res, "NOTICE_PACKAGE_EXTRA", "gamma@3.0.0"), show(res))

    app = clean("c_text")
    notices = app / "THIRD_PARTY_NOTICES.txt"
    notices.write_text(notices.read_text(encoding="utf-8").replace("Beta Author", "Someone Else"), encoding="utf-8", newline="\n")
    res = node(app, CLI, "--check")
    check("C11 a hand-edited licence text -> NOTICE_NOT_REPRODUCIBLE at the deploy regeneration",
          named(res, "NOTICE_NOT_REPRODUCIBLE"), show(res))

    app = clean("c_nolicence")
    for name in ("LICENSE.md",):
        (app / "node_modules" / "beta" / name).unlink()
    before = (app / "THIRD_PARTY_NOTICES.txt").read_bytes()
    res = node(app, CLI, "--write")
    check("C12 a package that ships no licence file -> NOTICE_LICENSE_TEXT_MISSING, and nothing is written",
          named(res, "NOTICE_LICENSE_TEXT_MISSING", "beta@2.0.0") and (app / "THIRD_PARTY_NOTICES.txt").read_bytes() == before, show(res))

    app = clean("c_supplement")
    (app / "node_modules" / "victory-vendor" / "LICENSE").write_text(MIT_ALPHA, encoding="utf-8", newline="\n")
    res = node(app, CLI, "--write")
    check("C13 a supplemented package that starts shipping a root licence -> NOTICE_SUPPLEMENT_STALE",
          named(res, "NOTICE_SUPPLEMENT_STALE", "victory-vendor@37.3.6"), show(res))

    app = clean("c_missing")
    (app / "THIRD_PARTY_NOTICES.txt").unlink()
    res = node(app, CLI, "--check-committed")
    check("C14 no committed notices file -> NOTICE_FILE_MISSING", named(res, "NOTICE_FILE_MISSING"), show(res))


MEDIA = ("employment-exposure-public-domain.jpg", "industrial-demand-public-domain.jpg",
         "us-capitol-public-domain.jpg", "federal-reserve-eccles-public-domain.jpg")


def section_d_build(pristine: Path, scratch: Path) -> None:
    print("\n[D] the build wiring, executed")
    base = scratch / "d"
    shutil.copytree(pristine, base)
    app = base / "systems-monitor" / "app"
    node(app, "scripts/generate-license-inventory.mjs")
    node(app, CLI, "--write")
    committed = (app / "THIRD_PARTY_NOTICES.txt").read_bytes()
    # A stand-in for `vite build`: a manifest and two hashed entry assets, the JS linking the notices.
    ui = base / "systems-monitor" / ".build" / "ui"
    (ui / ".vite").mkdir(parents=True)
    (ui / "assets").mkdir()
    (ui / ".vite" / "manifest.json").write_text(json.dumps({"src/main.tsx": {"file": "assets/main-AbC123.js", "css": ["assets/main-DeF456.css"], "isEntry": True}}), encoding="utf-8")
    (ui / "assets" / "main-AbC123.js").write_text(f'const n="{NOTICES_URL}";', encoding="utf-8")
    (ui / "assets" / "main-DeF456.css").write_text("a{}", encoding="utf-8")
    media = app / "fixtures" / "media"
    media.mkdir(parents=True)
    for name in MEDIA:
        (media / name).write_bytes(b"\xff\xd8jpeg")

    res = node(app, "scripts/compose-jekyll.mjs")
    published = base / "auxsays" / "systems-monitor" / "THIRD_PARTY_NOTICES.txt"
    check("D1 compose-jekyll.mjs copies the committed notices beside the bundle, byte-identical",
          res.returncode == 0 and published.exists() and published.read_bytes() == committed, show(res))

    # A stand-in for `jekyll build`: a .txt without front matter is copied verbatim.
    site = base / "auxsays" / "_site"
    shutil.copytree(base / "auxsays" / "systems-monitor", site / "systems-monitor")
    (site / "systems-monitor" / "index.html").write_text(
        '<div id="systems-monitor-root"><h1>U.S. Systems Monitor public beta</h1></div>'
        '<script type="module" src="/systems-monitor/assets/main-AbC123.js"></script>'
        '<link rel="stylesheet" href="/systems-monitor/assets/main-DeF456.css">', encoding="utf-8")
    res = node(app, "scripts/verify-static-site.mjs")
    check("D2 the deploy's built-site check (verify-static-site.mjs) passes with the notices served", res.returncode == 0, show(res))
    res = node(app, CLI, "--check-built", str(site))
    check("D3 --check-built passes on the same site", res.returncode == 0, show(res))

    from ci import verify_published_payload as vpp
    flagged = [rel for rel, _ in vpp.findings_for(site)]
    check("D4 the published-payload verifier lets /systems-monitor/THIRD_PARTY_NOTICES.txt through",
          "systems-monitor/THIRD_PARTY_NOTICES.txt" not in flagged and (site / "systems-monitor" / "THIRD_PARTY_NOTICES.txt").exists(),
          str(flagged))

    served = site / "systems-monitor" / "THIRD_PARTY_NOTICES.txt"
    served.write_bytes(committed.replace(b"Beta Author", b"Someone Else"))
    res = node(app, CLI, "--check-built", str(site))
    check("D5 a served copy that is not the committed file -> NOTICE_BUILT_FILE_DIFFERS", named(res, "NOTICE_BUILT_FILE_DIFFERS"), show(res))
    served.unlink()
    res = node(app, CLI, "--check-built", str(site))
    check("D6 the file missing from the output -> NOTICE_BUILT_FILE_MISSING", named(res, "NOTICE_BUILT_FILE_MISSING", NOTICES_URL), show(res))
    res = node(app, "scripts/verify-static-site.mjs")
    check("D7 ... and the deploy step itself refuses the site, naming it",
          res.returncode != 0 and "NOTICE_BUILT_FILE_MISSING" in res.stderr, show(res))
    served.write_bytes(committed)
    script = site / "systems-monitor" / "assets" / "main-AbC123.js"
    script.write_text('const n="/elsewhere.txt";', encoding="utf-8")
    res = node(app, CLI, "--check-built", str(site))
    check("D8 a bundle that no longer links the notices -> NOTICE_LINK_MISSING", named(res, "NOTICE_LINK_MISSING"), show(res))
    shutil.rmtree(site / "systems-monitor" / "assets")
    res = node(app, CLI, "--check-built", str(site))
    check("D9 notices with no bundle beside them -> NOTICE_NOT_BESIDE_BUNDLE", named(res, "NOTICE_NOT_BESIDE_BUNDLE"), show(res))

    res = node(app, "scripts/clean-generated.mjs")
    check("D10 clean-generated.mjs removes the published copy (and only generated outputs)",
          res.returncode == 0 and not published.exists() and (app / "THIRD_PARTY_NOTICES.txt").read_bytes() == committed, show(res))


def run() -> int:
    print("Systems Monitor third-party notices (AUX-082)")
    check("N0 a JavaScript runtime is available to run the real scripts", bool(NODE), "node not on PATH")
    section_a_committed_file()
    with tempfile.TemporaryDirectory(prefix="sm-notices-") as td:
        scratch = Path(td)
        pristine = scratch / "pristine"
        build_mirror(pristine)
        section_b_regeneration(pristine, scratch)
        section_c_mutants(pristine, scratch)
        section_d_build(pristine, scratch)

    print()
    print("=" * 60)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed tests:")
        for label in FAILURES:
            print(f"  - {label}")
    print("=" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
