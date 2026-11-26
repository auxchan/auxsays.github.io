"""IMPORT THE STORED PROVISIONAL ASSESSMENTS: the one public writer of `_data/provisional_assessments.yml`.

WHY THIS EXISTS. The provisional assessments are computed outside this repository and published as ONE file in a
separate output-only repository. No credential held outside this repository can write here: this repository's
own scheduled lane (`.github/workflows/assessment-import.yml`) reads that file anonymously, checks it here with
this repository's own code, and commits it with its own token through lib/automation_writeback.py. Whoever can
write the output repository can therefore change, at most, the content of this one file, and only to a document
that passes every check below; never a workflow, a script, a page or any other data file.

THE CHECKS (all must hold, else nothing is installed and the lane fails):
  * the candidate exists, is at most MAX_BYTES, is UTF-8 text and parses with the safe loader;
  * its header passes `assessment_output.file_errors` and EVERY entry passes `entry_errors` (the reader drops a
    bad entry and keeps the rest; the import refuses the whole file), with no page listed twice and at most
    MAX_PAGES entries;
  * it is byte-for-byte the canonical text `assessment_output.render` gives for its own content, so it carries
    no comment, anchor, alias, tag or layout of its own;
  * `generated_at` is not in the future (CLOCK_SKEW of slack);
  * it names none of the private component's files or folders (the publish gate's own list).
A fingerprint that does not match the current tree is NOT a refusal: the reader already treats such an entry as
stale and the page shows the count-based result, exactly as with no file.

Prints fixed status lines only (`IMPORT_STATUS: ...`), never the file's content. Exit 0 when the candidate is
installed or already identical, 1 when it is refused, 2 on a usage error. No network.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from ci import verify_published_payload as vpp
from lib import assessment_output as ao

MAX_BYTES = 1024 * 1024
MAX_PAGES = 1000
CLOCK_SKEW = timedelta(minutes=15)

# Whole names only, so the public output's own name (`provisional_assessments`) is not a private stem.
_PRIVATE_NAME_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:" + "|".join(sorted(map(re.escape, (*vpp.PRIVATE_COMPONENT_DIRS,
                                                            *vpp.PRIVATE_COMPONENT_STEMS)), key=len, reverse=True))
    + r")(?![A-Za-z0-9_])", re.IGNORECASE)

INSTALLED = "installed"
UNCHANGED = "unchanged"
REFUSED = "refused"


def candidate_errors(raw: bytes, *, now: datetime | None = None) -> list[str]:
    """Why the candidate may not be installed ([] when it may). Reason codes only, never file content."""
    if len(raw) > MAX_BYTES:
        return ["too_large"]
    if not raw:
        return ["empty"]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ["not_utf8"]
    try:
        doc: Any = yaml.load(text, Loader=yaml.SafeLoader)
    except Exception:  # noqa: BLE001 - ANY parser failure (libyaml or pure) is a refusal, never a crash
        return ["does_not_parse"]
    if ao.file_errors(doc):
        return ["header_invalid"]
    pages = doc["pages"]
    if len(pages) > MAX_PAGES:
        return ["too_many_pages"]
    errors = []
    if any(ao.entry_errors(e) for e in pages):
        errors.append("entry_invalid")
    keys = [e.get("page") for e in pages if isinstance(e, dict)]
    if len(keys) != len(set(keys)):
        errors.append("page_listed_twice")
    if errors:
        return errors
    try:
        canonical = ao.render(pages, rule_version=doc["rule_version"], generated_at=doc["generated_at"],
                              source_commit=doc["source_commit"])
    except Exception:  # noqa: BLE001
        return ["not_renderable"]
    if canonical != text:
        errors.append("not_canonical")
    stamp = datetime.strptime(doc["generated_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if stamp > (now or datetime.now(timezone.utc)) + CLOCK_SKEW:
        errors.append("generated_in_future")
    if _PRIVATE_NAME_RE.search(text):
        errors.append("names_private_component")
    return errors


def install(candidate: Path, target: Path, *, now: datetime | None = None) -> tuple[str, list[str]]:
    """(status, reasons). Writes `target` only when the candidate passes and differs from it."""
    try:
        raw = Path(candidate).read_bytes()
    except OSError:
        return REFUSED, ["candidate_unreadable"]
    if len(raw) > MAX_BYTES:  # checked before anything else reads it
        return REFUSED, ["too_large"]
    errors = candidate_errors(raw, now=now)
    if errors:
        return REFUSED, errors
    try:
        current = Path(target).read_bytes()
    except OSError:
        current = None
    if current == raw:
        return UNCHANGED, []
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    Path(target).write_bytes(raw)
    return INSTALLED, []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--candidate", required=True, help="the file read from the output repository")
    parser.add_argument("--target", default=str(ao.OUTPUT_PATH), help="where it is installed (default: the tracked file)")
    parser.add_argument("--check-only", action="store_true", help="validate, never write")
    args = parser.parse_args(argv)
    if args.check_only:
        try:
            raw = Path(args.candidate).read_bytes()
        except OSError:
            print("IMPORT_STATUS: refused reasons=candidate_unreadable")
            return 1
        errors = candidate_errors(raw)
        print(f"IMPORT_STATUS: {'refused reasons=' + ','.join(errors) if errors else 'valid'}")
        return 1 if errors else 0
    status, reasons = install(Path(args.candidate), Path(args.target))
    print(f"IMPORT_STATUS: {status}" + (f" reasons={','.join(reasons)}" if reasons else ""))
    return 1 if status == REFUSED else 0


if __name__ == "__main__":
    sys.exit(main())
