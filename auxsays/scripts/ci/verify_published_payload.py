#!/usr/bin/env python3
"""Refuse to publish internal implementation in the built site.

WHY A DENY-LIST AND NOT AN ALLOW-LIST. The first design of this check allow-listed file
extensions gathered from the working tree. Measured against two real `jekyll build` runs, that
list was missing `.map`, `.xml`, `.ico` and `.webmanifest`, which exist only in the BUILT site --
so as a deploy gate it would have refused every correct build. An allow-list fails toward
"block everything new"; a deny-list fails toward "let something new through". For a gate wired
into the deploy path, the second failure is recoverable and the first is an outage.

So this names the classes that are internal BY CONSTRUCTION, and says nothing about the rest.
A new legitimate asset type ships without touching this file. A new Python script, test,
operator tool, validation note or fixture does not.

WHAT WAS PUBLISHED BEFORE THIS EXISTED, measured on a real build of the tree at aeadfa21:
1,850 files, of which 190 .py, the operator browser-capture tooling (PowerShell, C#, cmd) with
a sample of captured data, three raw PASS/FAIL validation notes at the DOMAIN ROOT, a published
test fixture, the CI manifest with its per-suite check counts, and a CSS source map. All were
reachable at HTTP 200.

This is a PATH-AND-NAME gate only. It deliberately does not read file contents: the rendered
text of a page is a different question with a different failure mode, and it is covered by the
public-projection suite instead. Keeping the two apart is what lets this one be cheap enough to
run on every deploy.

Run:  python auxsays/scripts/ci/verify_published_payload.py --site auxsays/_site
Exit: 0 clean, 1 internal payload found, 2 the site directory is unusable.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Directories that exist to implement AUXSAYS, never to be read by a visitor.
DENIED_PREFIXES: tuple[str, ...] = (
    "scripts/",
    "tools/",
    # A browser editor that asked visitors for a repository-write token and wrote through the
    # GitHub contents API. Removed; it may not be published again under its old path.
    "vault/",
)

# Extensions that are implementation or build residue wherever they appear. Deliberately NOT
# here: .xml (sitemap, feeds), .json (.webmanifest siblings, page data), .ico, .webmanifest,
# .txt (robots.txt is a real public file), .yml (a public data file is conceivable).
# Those are judged by name or prefix instead, so a legitimate one is never blocked.
DENIED_SUFFIXES: tuple[str, ...] = (
    ".py",      # collectors, adapters, scoring, CI
    ".ps1",     # operator capture tooling
    ".cmd",     # operator capture launcher
    ".cs",      # operator capture launcher
    ".sh",      # build scripts
    ".jsonl",   # captured-sample data
    ".map",     # source maps reconstruct authored stylesheets/scripts
    ".test.mjs",  # Node test files, which live beside genuinely shipped modules
    # In a BUILT site every legitimate page is .html. A surviving .md is a file Jekyll copied
    # verbatim because it carried no front matter -- which is how nine internal engineering
    # notes came to be served at the domain root, and which a path prefix would never catch.
    ".md",
)

# Exact basenames and suffix patterns that are internal regardless of directory.
DENIED_BASENAME_SUFFIXES: tuple[str, ...] = (
    "_VALIDATION.txt",   # raw PASS/FAIL notes; three were served at the domain root
)
DENIED_BASENAMES: tuple[str, ...] = (
    "integrity_suites.txt",     # the CI manifest, with per-suite check counts
    "requirements-ingest.txt",  # the ingestion dependency set
    "package.json",             # names the dependency set and the build scripts
    "vault.js",                 # the removed token editor's GitHub contents-API client
)

# Licence and credit notices are published ON PURPOSE beside the assets they cover, and removing
# one would strip a required attribution. The Systems Monitor build copies its media folder with
# an ATTRIBUTION.md recording each image's licence; the blanket .md rule above refused it and
# halted the first deploy after this gate shipped. Compared case-insensitively on the full
# basename, so NOTES.md or ATTRIBUTION_DRAFT.md is still refused.
PERMITTED_NOTICE_BASENAMES: frozenset[str] = frozenset({
    "attribution.md", "license.md", "licence.md", "notice.md", "credits.md", "copying.md",
})


def findings_for(site: Path) -> list[tuple[str, str]]:
    """Return (relative_path, reason) for every published file that is internal by construction."""
    found: list[tuple[str, str]] = []
    for path in sorted(site.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(site).as_posix()
        base = path.name
        if any(rel.startswith(prefix) for prefix in DENIED_PREFIXES):
            found.append((rel, "internal directory"))
            continue
        if (any(base.endswith(suffix) for suffix in DENIED_SUFFIXES)
                and base.lower() not in PERMITTED_NOTICE_BASENAMES):
            found.append((rel, "implementation or build-residue file type"))
            continue
        if any(base.endswith(suffix) for suffix in DENIED_BASENAME_SUFFIXES):
            found.append((rel, "internal validation note"))
            continue
        if base in DENIED_BASENAMES:
            found.append((rel, "internal manifest or dependency set"))
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="auxsays/_site",
                    help="the built site directory to inspect")
    args = ap.parse_args(argv)

    site = Path(args.site)
    if not site.is_dir():
        print(f"verify_published_payload: not a directory: {site}", file=sys.stderr)
        return 2

    total = sum(1 for p in site.rglob("*") if p.is_file())
    if total == 0:
        print(f"verify_published_payload: no files under {site}", file=sys.stderr)
        return 2

    found = findings_for(site)
    if not found:
        print(f"verify_published_payload: clean ({total} published files)")
        return 0

    print(f"verify_published_payload: {len(found)} internal file(s) in the built site "
          f"({total} published files)", file=sys.stderr)
    shown = found[:40]
    for rel, reason in shown:
        print(f"  {rel}  [{reason}]", file=sys.stderr)
    if len(found) > len(shown):
        print(f"  ... and {len(found) - len(shown)} more", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
