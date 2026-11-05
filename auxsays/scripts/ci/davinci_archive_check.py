#!/usr/bin/env python3
"""DaVinci archive build check: the convergence is a pure ratchet, and the build agrees with it.

WHY THIS EXISTS. davinci-archive-build-check.yml first asserted the ONE-TIME migration baseline
(AUX-065): exactly 100 records changed by the convergence, exactly 100 pages carrying the notice,
and 21.0.4 as the active page. Once the migration ran in production the convergence on a pull
request changes nothing, so the check failed on every pull request that triggered it. Nothing here
counts a migration. Every rule holds for N = 0 (already converged) and for any later legitimate
N > 0 (when a stable 22 ships, every 20.x record archives on the next convergence).

THREE SUBCOMMANDS, in the order the workflow runs them:

  preplan      BEFORE convergence. The policy plan must not be refused, the tracked tree must
               equal HEAD, and no untracked file may sit in the generated-record directory (so
               every later change is attributable to the convergence, and every pending record is
               one HEAD holds). Writes the plan (pending paths, HEAD, untracked files already
               present) to --out, which must be OUTSIDE the checkout.

  convergence  AFTER `apply_davinci_archive_policy.py --write --confirm-write`. Judged per FILE
               against HEAD (`git diff --no-renames`, plus files that were not there before):
               every changed file is an EXISTING DaVinci record (product_id and update_entry read
               from HEAD's own front matter, because other products share the directory), planned
               by preplan, and its only change is exactly one front-matter line going from
               `update_status: current` to `update_status: archived`. An added, deleted or renamed
               record, an unarchive, any other edit, and any file outside the generated-record
               directory are refused. Every transition pending before convergence must be among
               the accepted edits (N equals the pending count). The plan is then taken again: it
               must not be refused and must have ZERO pending transitions.

  render       AFTER the site build. Every DaVinci record (the policy module's own selection,
               archived ones included) has its page, resolved from its permalink; an archived
               record's page carries the notice exactly once and an active record's page not at
               all; no other page carries it; at least ARCHIVED_FLOOR records are archived and at
               least MIN_ACTIVE are active; 19.1.4 is an archived spot page and a dynamically
               chosen active record is an active one.

Every failure is reported under a NAMED check id (the constants below) and exits 1. Exit 2 means
the check could not run at all (bad arguments, git unavailable, a malformed plan file, any
unexpected error): never a pass, and never mistaken for a named failure.

Read-only: it writes nothing except the preplan file it is told to write, outside the checkout.

Run: python auxsays/scripts/ci/davinci_archive_check.py {preplan --out F | convergence --plan F |
     render [--site DIR]} [--root REPO]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import yaml  # noqa: E402

from lib import davinci_archive_policy as policy  # noqa: E402
from lib.normalize import split_front_matter  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
GENERATED_REL = "auxsays/updates/generated"
SITE_REL = "auxsays/_site"

# The visible text of the shipped notice (_includes/archived-notice.html).
NOTICE_MARKER = "Archived release."
# The ratchet floor measured when the migration ran (D3). The ratchet never un-archives, so the
# archived population can only grow from here.
ARCHIVED_FLOOR = 100
MIN_ACTIVE = 1
# Archived under every future baseline: the ratchet keeps it archived for good.
FIXED_ARCHIVED_SPOT = "19.1.4"

ARCHIVED_LINE = "update_status: archived"
# The only prior forms apply_davinci_archive_policy.archive_edit accepts (a plain `current`, bare or
# quoted). Anything else is not a line the CLI can have rewritten.
_CURRENT_LINE = re.compile(r"""update_status:[ \t]*(?:current|'current'|"current")[ \t]*""")

# ---- named checks ------------------------------------------------------------------------------
PLAN_REFUSED = "PLAN_REFUSED"                    # the policy refused the plan before convergence
TREE_NOT_CLEAN = "TREE_NOT_CLEAN"                # tracked files already differed from HEAD
UNTRACKED_IN_SCOPE = "UNTRACKED_IN_SCOPE"        # an untracked file among the generated records before convergence
HEAD_MOVED = "HEAD_MOVED"                        # HEAD changed between preplan and convergence
OUT_OF_SCOPE = "OUT_OF_SCOPE"                    # a changed path outside the generated records
RECORD_ADDED = "RECORD_ADDED"                    # a new file in the generated-record directory
RECORD_DELETED = "RECORD_DELETED"                # a generated record disappeared
NOT_DAVINCI_RECORD = "NOT_DAVINCI_RECORD"        # a changed file that is not an existing DaVinci record
UNARCHIVE = "UNARCHIVE"                          # an archived record became anything else
UNAUTHORIZED_CHANGE = "UNAUTHORIZED_CHANGE"      # not exactly one current -> archived status line
FRONT_MATTER_DRIFT = "FRONT_MATTER_DRIFT"        # parsed front matter moved beyond that one status
UNPLANNED_CHANGE = "UNPLANNED_CHANGE"            # a status edit the pre-convergence plan did not hold
PENDING_NOT_ACCEPTED = "PENDING_NOT_ACCEPTED"    # a pending transition that is not among the accepted edits
POSTPLAN_REFUSED = "POSTPLAN_REFUSED"            # the policy refused the converged tree
POSTPLAN_PENDING = "POSTPLAN_PENDING"            # the converged tree still has pending transitions
UNREADABLE_RECORD = "UNREADABLE_RECORD"          # a DaVinci record the policy could not read
UNRESOLVABLE_PERMALINK = "UNRESOLVABLE_PERMALINK"  # no literal permalink to resolve a page from
DUPLICATE_PAGE = "DUPLICATE_PAGE"                # two records resolve to one page
MISSING_PAGE = "MISSING_PAGE"                    # a record's page was not built
MISSING_NOTICE = "MISSING_NOTICE"                # an archived record's page lacks the notice
DUPLICATE_NOTICE = "DUPLICATE_NOTICE"            # an archived record's page carries it twice
NOTICE_ON_ACTIVE = "NOTICE_ON_ACTIVE"            # an active record's page carries the notice
UNEXPECTED_NOTICE_PAGE = "UNEXPECTED_NOTICE_PAGE"  # a page no archived record owns carries it
ARCHIVED_BELOW_FLOOR = "ARCHIVED_BELOW_FLOOR"    # fewer archived records than the ratchet floor
NO_ACTIVE_RECORD = "NO_ACTIVE_RECORD"            # no DaVinci record is active
SPOT_ARCHIVED = "SPOT_ARCHIVED"                  # the fixed archived spot page is not archived
SPOT_ACTIVE = "SPOT_ACTIVE"                      # the chosen active spot page is not active

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERROR = 2


class CheckError(Exception):
    """The check could not run. Never a pass."""


@dataclass(frozen=True)
class Failure:
    check: str
    detail: str


# ---- git ---------------------------------------------------------------------------------------

def _git(root: Path, *args: str) -> bytes:
    try:
        proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    except OSError as exc:
        raise CheckError(f"git unavailable: {exc}") from exc
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        raise CheckError(f"git {' '.join(args)} failed ({proc.returncode}): {err[:300]}")
    return proc.stdout


def head_commit(root: Path) -> str:
    return _git(root, "rev-parse", "HEAD").decode("ascii").strip()


def tracked_changes(root: Path) -> list[tuple[str, str]]:
    """(status, path) for every tracked path that differs from HEAD, renames split into D + A."""
    out = _git(root, "diff", "--no-renames", "--name-status", "-z", "HEAD", "--").decode("utf-8")
    parts = out.split("\0")
    items: list[tuple[str, str]] = []
    i = 0
    while i + 1 < len(parts):
        status = parts[i]
        if status[:1] in ("R", "C"):  # cannot happen with --no-renames; never trusted if it does
            items.append(("D", parts[i + 1]))
            items.append(("A", parts[i + 2]))
            i += 3
            continue
        items.append((status, parts[i + 1]))
        i += 2
    return items


def untracked_files(root: Path) -> list[str]:
    out = _git(root, "ls-files", "--others", "--exclude-standard", "-z").decode("utf-8")
    return sorted(p for p in out.split("\0") if p)


def head_bytes(root: Path, path: str) -> bytes:
    """HEAD's copy as it would be checked out (eol and filters applied), so bytes compare."""
    return _git(root, "cat-file", "--filters", f"HEAD:{path}")


# ---- front matter ------------------------------------------------------------------------------

def front_matter(raw: bytes) -> dict[str, Any]:
    """Exactly as lib.davinci_archive_policy.read_front_matter reads a file, from bytes."""
    front, _body = split_front_matter(raw.decode("utf-8"))
    if front is None:
        return {}
    data = yaml.load(front, Loader=yaml.SafeLoader)
    return data if isinstance(data, dict) else {}


def is_davinci_record(fm: dict[str, Any]) -> bool:
    """The policy's own selection: lib.davinci_archive_policy._record_from_front_matter."""
    return fm.get("update_entry") is True and str(fm.get("product_id") or "").strip() == policy.PRODUCT_ID


def _status(fm: dict[str, Any]) -> str:
    return str(fm.get("update_status") or "").strip()


def _front_matter_close(lines: list[bytes]) -> int | None:
    if not lines or lines[0].rstrip(b"\r") != b"---":
        return None
    for idx in range(1, len(lines)):
        if lines[idx].rstrip(b"\r") == b"---":
            return idx
    return None


def in_generated_scope(path: str) -> bool:
    """A record is a direct `*.md` child of the generated directory, as policy.load_records globs."""
    prefix = GENERATED_REL + "/"
    if not path.startswith(prefix):
        return False
    name = path[len(prefix):]
    return bool(name) and "/" not in name and name.endswith(".md")


def check_record_edit(path: str, old: bytes, new: bytes) -> Failure | None:
    """None when ``new`` is ``old`` with exactly one current -> archived front-matter status line."""
    try:
        fm_old = front_matter(old)
    except Exception as exc:  # noqa: BLE001 -- unreadable at HEAD is not a DaVinci record
        return Failure(NOT_DAVINCI_RECORD, f"{path}: HEAD front matter unreadable ({exc.__class__.__name__})")
    if not is_davinci_record(fm_old):
        return Failure(NOT_DAVINCI_RECORD, f"{path}: at HEAD product_id={fm_old.get('product_id')!r} "
                                           f"update_entry={fm_old.get('update_entry')!r}")
    try:
        fm_new = front_matter(new)
    except Exception as exc:  # noqa: BLE001
        return Failure(UNAUTHORIZED_CHANGE, f"{path}: front matter no longer parses ({exc.__class__.__name__})")
    if _status(fm_old).lower() == policy.ARCHIVED and _status(fm_new).lower() != policy.ARCHIVED:
        return Failure(UNARCHIVE, f"{path}: update_status {_status(fm_old)!r} -> {_status(fm_new)!r}")

    old_lines, new_lines = old.split(b"\n"), new.split(b"\n")
    if len(old_lines) != len(new_lines):
        return Failure(UNAUTHORIZED_CHANGE, f"{path}: line count {len(old_lines)} -> {len(new_lines)}")
    changed = [i for i, (a, b) in enumerate(zip(old_lines, new_lines)) if a != b]
    if len(changed) != 1:
        return Failure(UNAUTHORIZED_CHANGE, f"{path}: {len(changed)} lines changed, expected exactly one")
    idx = changed[0]
    close = _front_matter_close(old_lines)
    if close is None or not 0 < idx < close:
        return Failure(UNAUTHORIZED_CHANGE, f"{path}: the changed line {idx + 1} is outside the front matter")
    a = old_lines[idx].decode("utf-8", "replace")
    b = new_lines[idx].decode("utf-8", "replace")
    a_cr, b_cr = a.endswith("\r"), b.endswith("\r")
    a_text, b_text = a.rstrip("\r"), b.rstrip("\r")
    if not _CURRENT_LINE.fullmatch(a_text):
        return Failure(UNAUTHORIZED_CHANGE, f"{path}: changed line was {a_text!r}, not a plain current status")
    if b_text != ARCHIVED_LINE:
        return Failure(UNAUTHORIZED_CHANGE, f"{path}: changed line became {b_text!r}, not {ARCHIVED_LINE!r}")
    if a_cr != b_cr:
        return Failure(UNAUTHORIZED_CHANGE, f"{path}: the status line's line ending changed")

    rest_old = {k: v for k, v in fm_old.items() if k != "update_status"}
    rest_new = {k: v for k, v in fm_new.items() if k != "update_status"}
    if _status(fm_old) != "current" or _status(fm_new) != policy.ARCHIVED or rest_old != rest_new:
        return Failure(FRONT_MATTER_DRIFT, f"{path}: parsed front matter is not one current -> archived move "
                                           f"(status {_status(fm_old)!r} -> {_status(fm_new)!r})")
    return None


# ---- plan --------------------------------------------------------------------------------------

def plan_tree(root: Path) -> policy.Plan:
    return policy.plan_archive(root / GENERATED_REL)


def _rel_record(rec: policy.Record) -> str:
    return f"{GENERATED_REL}/{rec.path.name}"


def preplan(root: Path) -> tuple[list[Failure], dict[str, Any], list[str]]:
    failures: list[Failure] = []
    plan = plan_tree(root)
    if plan.refused:
        failures.append(Failure(PLAN_REFUSED, f"{plan.refusal_reason}: {plan.refusal_detail}"))
    tracked = tracked_changes(root)
    if tracked:
        failures.append(Failure(TREE_NOT_CLEAN, f"{len(tracked)} tracked path(s) already differ from HEAD "
                                                f"before convergence, e.g. {tracked[0][0]} {tracked[0][1]}"))
    untracked = untracked_files(root)
    # The plan reads the directory, not HEAD: an untracked record there could be pending, and its
    # convergence would never be judged (untracked files present now are not attributed to it).
    stray = [p for p in untracked if p.startswith(GENERATED_REL + "/")]
    if stray:
        failures.append(Failure(UNTRACKED_IN_SCOPE, f"{len(stray)} untracked file(s) among the generated records "
                                                    f"before convergence, e.g. {stray[0]}"))
    pending = sorted(_rel_record(r) for r in plan.to_archive)
    data = {
        "head": head_commit(root),
        "refused": plan.refused,
        "pending": pending,
        "untracked_before": untracked,
    }
    lines = [f"pre-convergence plan: {plan.records} DaVinci records, newest stable major "
             f"{plan.newest_stable_major}, threshold {plan.threshold_major}, {plan.already_archived} already "
             f"archived, {len(pending)} pending"]
    return failures, data, lines


def convergence(root: Path, pre: dict[str, Any]) -> tuple[list[Failure], list[str]]:
    failures: list[Failure] = []
    head = head_commit(root)
    if head != pre.get("head"):
        failures.append(Failure(HEAD_MOVED, f"HEAD {pre.get('head')} at preplan, {head} now"))
    pending = set(pre.get("pending") or [])
    before = set(pre.get("untracked_before") or [])
    changes = tracked_changes(root)
    changes += [("?", p) for p in untracked_files(root) if p not in before]
    accepted: list[str] = []
    for status, path in changes:
        if not in_generated_scope(path):
            failures.append(Failure(OUT_OF_SCOPE, f"{status} {path}"))
            continue
        if status in ("A", "?"):
            failures.append(Failure(RECORD_ADDED, path))
            continue
        if status == "D":
            failures.append(Failure(RECORD_DELETED, path))
            continue
        if status != "M":
            failures.append(Failure(UNAUTHORIZED_CHANGE, f"{path}: git status {status}"))
            continue
        failure = check_record_edit(path, head_bytes(root, path), (root / path).read_bytes())
        if failure is not None:
            failures.append(failure)
            continue
        if path not in pending:
            failures.append(Failure(UNPLANNED_CHANGE, f"{path}: archived, but not pending before convergence"))
            continue
        accepted.append(path)
    # N must equal the pending count: a planned transition that no judged edit accounts for was made
    # where this check cannot see it, or not made at all.
    unaccounted = sorted(pending - set(accepted))
    if unaccounted:
        failures.append(Failure(PENDING_NOT_ACCEPTED, f"{len(unaccounted)} of {len(pending)} pending transition(s) "
                                                      f"not among the accepted edits, e.g. {unaccounted[0]}"))
    post = plan_tree(root)
    if post.refused:
        failures.append(Failure(POSTPLAN_REFUSED, f"{post.refusal_reason}: {post.refusal_detail}"))
    elif post.to_archive:
        failures.append(Failure(POSTPLAN_PENDING, f"{len(post.to_archive)} transition(s) still pending, e.g. "
                                                  f"{_rel_record(post.to_archive[0])}"))
    lines = [f"convergence: N = {len(accepted)} record(s) archived by exactly one current -> archived line "
             f"({len(pending)} were pending); post-convergence plan: {post.already_archived} archived, "
             f"{len(post.to_archive)} pending, refused={post.refused}"]
    return failures, lines


# ---- render ------------------------------------------------------------------------------------

def resolve_page(site: Path, permalink: Any) -> Path | None:
    """The built file for a literal permalink, as Jekyll writes it; None if it is not literal."""
    if not isinstance(permalink, str):
        return None
    link = permalink.strip()
    if not link.startswith("/") or ":" in link or "\\" in link:
        return None
    parts = [p for p in link.split("/") if p]
    if any(p in (".", "..") for p in parts):
        return None
    if link.endswith("/"):
        return site.joinpath(*parts, "index.html")
    if link.endswith(".html") and parts:
        return site.joinpath(*parts)
    return None


def pick_active_spot(records: list[policy.Record]) -> policy.Record | None:
    """The newest stable active record (by major, then file name); any active one if none is stable."""
    active = [r for r in records if r.status != policy.ARCHIVED]
    if not active:
        return None
    stable = [r for r in active if not r.is_beta and r.major is not None]
    pool = stable or active
    return max(pool, key=lambda r: (r.major if r.major is not None else -1, r.path.name))


def _page_key(site: Path, page: Path) -> str:
    return page.relative_to(site).as_posix()


def render(root: Path, site: Path) -> tuple[list[Failure], list[str]]:
    failures: list[Failure] = []
    if not site.is_dir():
        raise CheckError(f"no built site at {site}")
    records, unreadable = policy.load_records(root / GENERATED_REL)
    for name in sorted(unreadable):
        failures.append(Failure(UNREADABLE_RECORD, name))

    pages: dict[str, policy.Record] = {}
    notices: dict[str, int] = {}
    for rec in records:
        page = resolve_page(site, policy.read_front_matter(rec.path).get("permalink"))
        if page is None:
            failures.append(Failure(UNRESOLVABLE_PERMALINK, rec.path.name))
            continue
        key = _page_key(site, page)
        if key in pages:
            failures.append(Failure(DUPLICATE_PAGE, f"{rec.path.name} and {pages[key].path.name} -> {key}"))
            continue
        pages[key] = rec
        if not page.is_file():
            failures.append(Failure(MISSING_PAGE, f"{rec.path.name} -> {key}"))
            continue
        count = page.read_text(encoding="utf-8", errors="replace").count(NOTICE_MARKER)
        notices[key] = count
        archived = rec.status == policy.ARCHIVED
        if archived and count == 0:
            failures.append(Failure(MISSING_NOTICE, f"{rec.version} ({rec.path.name}) -> {key}"))
        elif archived and count > 1:
            failures.append(Failure(DUPLICATE_NOTICE, f"{rec.version} -> {key} carries it {count} times"))
        elif not archived and count > 0:
            failures.append(Failure(NOTICE_ON_ACTIVE, f"{rec.version} ({rec.status or 'no status'}) -> {key}"))

    owners = {k for k, r in pages.items() if r.status == policy.ARCHIVED}
    for page in sorted(site.rglob("*.html")):
        key = _page_key(site, page)
        if key in owners:
            continue
        if NOTICE_MARKER in page.read_text(encoding="utf-8", errors="replace"):
            owner = pages.get(key)
            failures.append(Failure(UNEXPECTED_NOTICE_PAGE,
                                    f"{key} ({'active record ' + owner.version if owner else 'no DaVinci record'})"))

    archived_n = sum(1 for r in records if r.status == policy.ARCHIVED)
    active_n = len(records) - archived_n
    if archived_n < ARCHIVED_FLOOR:
        failures.append(Failure(ARCHIVED_BELOW_FLOOR, f"{archived_n} archived, the ratchet floor is {ARCHIVED_FLOOR}"))
    if active_n < MIN_ACTIVE:
        failures.append(Failure(NO_ACTIVE_RECORD, f"{active_n} active DaVinci records"))

    lines = [f"DaVinci records: {len(records)}; archived: {archived_n} (floor {ARCHIVED_FLOOR}); "
             f"active: {active_n}; pages checked: {len(notices)}"]

    spot = next((r for r in records if r.version == FIXED_ARCHIVED_SPOT), None)
    spot_key = next((k for k, r in pages.items() if r is spot), None)
    if spot is None or spot.status != policy.ARCHIVED or notices.get(spot_key) != 1:
        failures.append(Failure(SPOT_ARCHIVED, f"{FIXED_ARCHIVED_SPOT}: "
                                               + ("no record" if spot is None else
                                                  f"status {spot.status!r}, notice x{notices.get(spot_key)}")))
    else:
        lines.append(f"archived spot page: {FIXED_ARCHIVED_SPOT} -> {spot_key} (notice x1)")

    active = pick_active_spot(records)
    active_key = next((k for k, r in pages.items() if r is active), None)
    if active is None or active.status == policy.ARCHIVED or notices.get(active_key) != 0:
        failures.append(Failure(SPOT_ACTIVE, "no active record" if active is None else
                                f"{active.version}: status {active.status!r}, notice x{notices.get(active_key)}"))
    else:
        lines.append(f"active spot page (chosen from the converged tree): {active.version} -> {active_key} "
                     f"(status {active.status!r}, notice x0)")
    return failures, lines


# ---- reporting ---------------------------------------------------------------------------------

def report(stage: str, failures: list[Failure], lines: list[str]) -> int:
    for line in lines:
        print(line)
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    for f in failures:
        print(f"  FAIL  {f.check}: {f.detail}")
        if in_actions:
            print(f"::error title=DaVinci archive check {f.check}::{f.detail}")
    if failures:
        names = sorted({f.check for f in failures})
        print(f"DAVINCI ARCHIVE CHECK FAILED ({stage}): {len(failures)} failure(s): {', '.join(names)}")
        return EXIT_FAIL
    print(f"DAVINCI ARCHIVE CHECK PASSED ({stage})")
    return EXIT_PASS


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(REPO_ROOT), help="repository root (default: this checkout)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_pre = sub.add_parser("preplan", help="validate the plan before convergence")
    p_pre.add_argument("--out", required=True, help="where to keep the plan; must be outside the checkout")
    p_pre.add_argument("--root", default=argparse.SUPPRESS)
    p_conv = sub.add_parser("convergence", help="judge the convergence diff and the converged plan")
    p_conv.add_argument("--plan", required=True, help="the file preplan wrote")
    p_conv.add_argument("--root", default=argparse.SUPPRESS)
    p_ren = sub.add_parser("render", help="judge the built site against every DaVinci record")
    p_ren.add_argument("--site", default=None, help=f"built site (default: <root>/{SITE_REL})")
    p_ren.add_argument("--root", default=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    root = Path(args.root)
    try:
        if args.cmd == "preplan":
            out = Path(args.out)
            if _inside(out, root):
                raise CheckError(f"--out {out} is inside the checkout; it would read as a changed file")
            failures, data, lines = preplan(root)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return report("preplan", failures, lines)
        if args.cmd == "convergence":
            pre = json.loads(Path(args.plan).read_text(encoding="utf-8"))
            failures, lines = convergence(root, pre)
            return report("convergence", failures, lines)
        site = Path(args.site) if args.site else root / SITE_REL
        failures, lines = render(root, site)
        return report("render", failures, lines)
    except Exception as exc:  # noqa: BLE001 -- ANY error means "could not run" (exit 2), never a named failure
        if not isinstance(exc, (CheckError, OSError, ValueError)):
            traceback.print_exc()
        print(f"DAVINCI ARCHIVE CHECK ERROR ({args.cmd}): {exc.__class__.__name__}: {exc}")
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::error title=DaVinci archive check could not run::{exc.__class__.__name__}: {exc}")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
