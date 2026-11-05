#!/usr/bin/env python3
"""Converge DaVinci Resolve records onto the archive policy (see lib/davinci_archive_policy.py).

DRY RUN BY DEFAULT: prints the JSON plan and writes nothing. Writing needs BOTH --write and
--confirm-write.

What a write does, and only this: for each record the plan selects, the single front-matter line
``update_status: current`` becomes ``update_status: archived``. The edit is byte-preserving (the
rest of the file, its line endings and its quoting are untouched), requires EXACTLY ONE
``update_status:`` line inside the front matter, is computed for every file before any file is
written, and is verified afterwards by re-planning: the run succeeds only if nothing remains.

It writes no status event, no notification, no count, verdict, evidence, URL or citation. It never
raises a record from archived to anything else.

Exit codes:
  0  converged (or nothing to do) / dry run printed
  1  an edit could not be made safely, or the post-write re-plan was not empty (nothing is claimed)
  3  the plan was REFUSED; the named reason is printed, annotated for CI, and nothing was written
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from lib import davinci_archive_policy as policy

ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT / "updates" / "generated"

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_REFUSED = 3

_STATUS_LINE = re.compile(rb"^update_status:[ \t]*(?P<value>[^\r\n]*?)[ \t]*(?P<eol>\r?\n|\Z)", re.M)
_PLAIN_VALUES = {b"current", b"'current'", b'"current"'}


class EditError(Exception):
    pass


def archive_edit(raw: bytes) -> bytes:
    """Return ``raw`` with its one front-matter ``update_status`` line set to ``archived``.

    Raises EditError unless the front matter holds exactly one such line whose value is a plain
    ``current``. Anything else (a different status, a duplicate key, no front matter) is refused,
    because a byte edit that has to guess is a corruption waiting to happen.
    """
    if not raw.startswith(b"---"):
        raise EditError("no front matter")
    head_end = raw.find(b"\n", 0)
    if head_end < 0 or raw[:head_end].rstrip(b"\r") != b"---":
        raise EditError("no front matter fence")
    pos = head_end + 1
    close = None
    while pos < len(raw):
        nl = raw.find(b"\n", pos)
        line_end = len(raw) if nl < 0 else nl
        if raw[pos:line_end].rstrip(b"\r") == b"---":
            close = pos
            break
        pos = line_end + 1
    if close is None:
        raise EditError("front matter is not closed")
    front = raw[head_end + 1:close]
    matches = list(_STATUS_LINE.finditer(front))
    if len(matches) != 1:
        raise EditError(f"expected exactly one update_status line, found {len(matches)}")
    m = matches[0]
    if m.group("value") not in _PLAIN_VALUES:
        raise EditError(f"update_status is {m.group('value')!r}, not a plain 'current'")
    new_line = b"update_status: archived" + m.group("eol")
    new_front = front[:m.start()] + new_line + front[m.end():]
    return raw[:head_end + 1] + new_front + raw[close:]


def _atomic_write(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _annotate_refusal(plan: policy.Plan) -> None:
    msg = f"DaVinci archive convergence REFUSED: {plan.refusal_reason}: {plan.refusal_detail}"
    print(msg, file=sys.stderr)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::error title=DaVinci archive convergence refused::{plan.refusal_reason}: {plan.refusal_detail}")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as handle:
                handle.write(f"### DaVinci archive convergence refused\n\n"
                             f"- reason: `{plan.refusal_reason}`\n- detail: {plan.refusal_detail}\n"
                             f"- nothing was written\n")


def run(root: Path, *, write: bool, confirm: bool, gap: int = policy.GAP) -> tuple[int, dict]:
    generated = root / "updates" / "generated"
    plan = policy.plan_archive(generated, gap=gap)
    report = plan.as_dict(root)
    report["mode"] = "write" if (write and confirm) else "dry-run"
    if plan.refused:
        _annotate_refusal(plan)
        return EXIT_REFUSED, report
    if write and not confirm:
        report["error"] = "--write requires --confirm-write; nothing was written"
        return EXIT_FAILED, report
    if not (write and confirm) or not plan.to_archive:
        report["remaining_after"] = len(plan.to_archive)
        return EXIT_OK, report

    pending: list[tuple[Path, bytes]] = []
    try:
        for rec in plan.to_archive:
            pending.append((rec.path, archive_edit(rec.path.read_bytes())))
    except EditError as exc:
        report["error"] = f"{rec.path.name}: {exc}; nothing was written"
        return EXIT_FAILED, report
    for path, data in pending:
        _atomic_write(path, data)

    after = policy.plan_archive(generated, gap=gap)
    report["written"] = len(pending)
    report["remaining_after"] = len(after.to_archive)
    if after.refused or after.to_archive:
        report["error"] = "re-plan after write was not empty"
        return EXIT_FAILED, report
    return EXIT_OK, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="apply the plan (also needs --confirm-write)")
    ap.add_argument("--confirm-write", action="store_true", help="second key for --write")
    ap.add_argument("--root", default=str(ROOT), help="site root holding updates/generated (default: this checkout)")
    args = ap.parse_args(argv)
    code, report = run(Path(args.root), write=args.write, confirm=args.confirm_write)
    print(json.dumps(report, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
