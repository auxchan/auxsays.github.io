#!/usr/bin/env python3
"""Run a bookkeeping step so that its own failure cannot discard the lane's work, and is never silent.

THE DEFECT THIS CLOSES. Two bookkeeping steps (the second-tier promotion report, the backfill queue
read-back) stand in front of their lane's only writeback, and every later step needs `success()`.
A crash in either one (an unreadable tier file, a non-numeric value in the ingest state) failed the
step and with it the whole run: the evidence or the official records that run had just collected
were not committed. Neither step produces anything the writeback depends on.

WHAT `--fail-soft` DOES. The step's own result is unchanged when it succeeds. When it raises or
returns non-zero, the failure is

  * printed in the log as a GitHub `::error` annotation, with the traceback under it;
  * appended to the run's job summary (`GITHUB_STEP_SUMMARY`), where the lane's health is read;
  * written to the step's outputs as `status=failed` (`GITHUB_OUTPUT`), beside `status=ok`;

and the process exits 0, so the lane goes on to QA and its writeback. Without the flag nothing
changes: a failure is a non-zero exit, as before. The flag is read from the command line only.
"""
from __future__ import annotations

import os
import sys
import traceback
from typing import Callable, Sequence

FLAG = "--fail-soft"


def _append(env_name: str, text: str) -> None:
    target = os.environ.get(env_name, "")
    if not target:
        return
    try:
        with open(target, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    except OSError as exc:                    # reporting must not become a second failure
        print(f"::warning::could not write {env_name}: {exc}")


def run(name: str, main: Callable[[Sequence[str] | None], int],
        argv: Sequence[str] | None = None) -> int:
    """``main(argv)``'s exit code; with ``--fail-soft`` in ``argv`` a failure is reported and is 0."""
    args = list(sys.argv[1:] if argv is None else argv)
    soft = FLAG in args
    detail = ""
    try:
        code = main(args)
        code = 0 if code is None else code
    except SystemExit as exc:
        if not soft:
            raise
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        detail = "" if isinstance(exc.code, int) or exc.code is None else str(exc.code)
    except Exception as exc:                  # noqa: BLE001 - the point is to catch everything
        if not soft:
            raise
        code = 1
        detail = f"{type(exc).__name__}: {exc}"
        print(traceback.format_exc())
    if not soft:
        return code
    if code == 0:
        _append("GITHUB_OUTPUT", "status=ok\n")
        return 0
    line = " ".join((detail or f"exit code {code}").split())[:500]
    print(f"::error title={name} failed (fail-soft)::{name} failed and was skipped: {line}. "
          "The lane continues; nothing this step would have written was written.")
    _append("GITHUB_STEP_SUMMARY",
            f"\n### {name}: FAILED (fail-soft)\n\n- {line}\n- The lane continued to QA and its "
            "writeback. This step wrote nothing.\n")
    _append("GITHUB_OUTPUT", "status=failed\n")
    return 0
