#!/usr/bin/env python3
"""Refuse a change that loses previously accepted evidence without an audited withdrawal.

    python auxsays/scripts/check_evidence_loss.py --base <commit>

Compares the evidence store at <commit> -- the state this change REPLACES -- against the store in
the working tree, using the same predicate the automation writeback enforces
(lib/evidence_loss.py). Read-only: it never writes, and reads git objects only.

WHY IT NEEDS AN EXPLICIT BASE. The obvious reference, `main`, is self-invalidating: the moment a
change merges, `main` BECOMES that change, and a comparison against it silently degenerates into
comparing the tree with itself. This repository was bitten by exactly that once (#67, fixed in #68),
and #92 designed around it deliberately. So the caller names the commit being replaced -- a pull
request's base, a push's `before` -- and there is no default.

Exit codes:  0 nothing lost   1 evidence lost   2 could not establish a base (never a pass)

The two enforcement points are complementary and neither covers the other. The writeback gate sees
every automated lane but only ever compares against fresh main, so a purge that MERGES through a
pull request becomes its next baseline. This check sees pull requests and human pushes, but a
GITHUB_TOKEN push never triggers it, so it never sees the scheduled lanes. It is also a WINDOW check
(base..head), which is why ci-integrity gives every push to main its own concurrency group: with a
shared group, a second push cancels the first push's run before it gets here, and that first window
would never be judged by anything. And it is advisory until `integrity` is a required status check
-- it turns a loss red and names it; it cannot stop a merge on its own.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from lib import evidence_loss as el  # noqa: E402

EXIT_OK = 0
EXIT_LOSS = 1
EXIT_NO_BASE = 2
MAX_SHOWN = 40


def _git_blob(repo: Path, spec: str) -> str | None:
    """`<sha>:<path>` as UTF-8 text, or None when that path does not exist in that commit. Bytes are
    decoded strictly; an undecodable store is unreadable, not empty."""
    if subprocess.run(["git", "-C", str(repo), "cat-file", "-e", spec],
                      capture_output=True).returncode != 0:
        return None
    proc = subprocess.run(["git", "-C", str(repo), "cat-file", "-p", spec], capture_output=True)
    if proc.returncode != 0:
        raise el.EvidenceStoreUnreadable(f"git could not read {spec}")
    try:
        return proc.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise el.EvidenceStoreUnreadable("base evidence store is not valid UTF-8") from exc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--base", required=True,
                    help="the commit this change replaces (PR base sha, push 'before' sha)")
    ap.add_argument("--repo", default=str(_REPO), help=argparse.SUPPRESS)
    ap.add_argument("--evidence-path", default=el.EVIDENCE_PATH, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    repo = Path(args.repo)
    base = args.base.strip()
    if not base or set(base) == {"0"}:
        print("::error::evidence-loss check: no base commit was supplied, so loss cannot be ruled out")
        return EXIT_NO_BASE
    if subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{base}^{{commit}}"],
                      capture_output=True).returncode != 0:
        print(f"::error::evidence-loss check: base commit {base[:12]} is not present in this "
              f"checkout (fetch it first); loss cannot be ruled out")
        return EXIT_NO_BASE

    try:
        base_text = _git_blob(repo, f"{base}:{args.evidence_path}")
        cand_path = repo / args.evidence_path
        cand_text = cand_path.read_text(encoding="utf-8") if cand_path.exists() else None
        losses = el.losses_between(base_text, cand_text)
    except (el.EvidenceStoreUnreadable, UnicodeDecodeError) as exc:
        print(f"::error::evidence-loss check: {exc}")
        return EXIT_NO_BASE

    base_rows = len(el.parse_store(base_text))
    cand_rows = len(el.parse_store(cand_text))
    print(f"evidence-loss check: base {base[:12]} holds {base_rows} rows; working tree holds "
          f"{cand_rows}")
    if not losses:
        print("evidence-loss check: every base row is still accounted for "
              "(accepted, or withdrawn with an exclusion_reason)")
        return EXIT_OK

    total = sum(l.rows for l in losses)
    print(f"::error::evidence-loss check: {total} row(s) across {len(losses)} identities left the "
          f"store without an audited withdrawal")
    for loss in losses[:MAX_SHOWN]:
        print(f"  {loss.public_reason()}")
        print(f"      {loss.detail}")
    if len(losses) > MAX_SHOWN:
        print(f"  ... and {len(losses) - MAX_SHOWN} more identities")
    print("To withdraw evidence, keep the row and set `counted: false` with a non-empty "
          "`exclusion_reason`. Deleting it leaves no audit trail and frees its key to be "
          "re-collected.")
    return EXIT_LOSS


if __name__ == "__main__":
    raise SystemExit(main())
