#!/usr/bin/env python3
"""DaVinci Resolve release-line identity: what a bare-version page ("21", "20") actually is.

THE DEFECT. Blackmagic names the first release of a line with a bare number ("DaVinci Resolve 20",
2025-05-28) and users name the WHOLE line the same way ("Resolve 20 keeps crashing"). The record for
the first release therefore collects every report that names the line and no point release. Measured
at 12d207ba: the "20" page counted 32 reports and all 32 were posted after 20.0.1 had replaced the
first release (earliest 2025-09-22, when 20.2 was current); the "21" page counted 73, posted between
2026-04-14 and 2026-10-30, a span covering 21.0 through 21.1.2. Each page said its reports were
"matched to this exact update" and "21" called itself "the stable DaVinci Resolve 21 release".

THE IDENTITY. A bare-version record that has point-release siblings is a RELEASE LINE page as soon
as it counts reports: the reports name the line, so the page says so, and names the range. A report
whose text names an exact point release of the line belongs on that release's page and is never
counted on the line page. Nothing is inferred from a date: a line report is not moved to the
release that was current when it was written.

One module, three callers: the collector (the forward rule), the record writer (the page identity),
the one-off migration (the stored rows). Deterministic, offline.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

PRODUCT_ID = "blackmagic-davinci"
SCOPE_FIELD = "update_identity_scope"
SCOPE_RELEASE_LINE = "release_line"
# Stored on a row the collector refuses for this reason, and on a row the migration withdraws.
REASON_POINT_RELEASE_NAMED = "point_release_named_not_release_line"

_BARE = re.compile(r"^\d{1,3}$")
_STABLE_MEMBER = re.compile(r"^\d{1,3}(?:\.\d+)*$")
_FM_FIELD = re.compile(r"^(product_id|update_version):\s*(.*)$", re.M)


def is_bare_line(version: Any) -> bool:
    """A version written as a bare integer: the only shape that names a line as well as a release."""
    return bool(_BARE.match(str(version or "").strip()))


def stated_point_releases(text: str, line: Any, tracked: Iterable[Any] = ()) -> list[str]:
    """Every point release of ``line`` written in ``text``, in order: "21" -> ["21.1", "21.0.0.1"].

    A point release is the line number followed by one or more dotted numeric components, standing
    alone: not inside a longer number or a word, and not a price. "Resolve 21." (a sentence end) and
    "21:9" are not point releases; "v21.1" and "(21.0.3 Free)" are.

    "N.0" IS THE LINE'S FIRST RELEASE WRITTEN IN FULL. Blackmagic's first release of the 20 line is
    named "20", so a report that says "20.0" names that same record and is not a point release.
    It becomes one only when ``tracked`` holds a separate record under that spelling: "21.0" has
    its own record (2026-06-03) beside "21", so a report naming 21.0 belongs there.
    """
    tracked_set = {str(v or "").strip() for v in tracked}
    line = str(line or "").strip()
    if not is_bare_line(line):
        return []
    body = str(text or "")
    pattern = re.compile(rf"(?<![0-9.]){re.escape(line)}(?:\.\d+)+(?![A-Za-z0-9])")
    found: list[str] = []
    for hit in pattern.finditer(body):
        before = body[:hit.start()]
        if before.endswith(("$", "€", "£")):
            continue
        if before and before[-1].isalpha() and not re.search(r"(?:^|[^A-Za-z])v$", before, re.I):
            continue                                   # inside a word; "v21.1" is a version prefix
        token = hit.group(0)
        if not token[len(line):].strip(".0") and token not in tracked_set:
            continue                                   # "20.0": the first release, written in full
        if token not in found:
            found.append(token)
    return found


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def line_members(line: Any, versions: Iterable[Any]) -> list[str]:
    """The stable releases of ``line`` among ``versions``, oldest first: the line itself and every
    dotted release under it. Betas and other lines are not members."""
    line = str(line or "").strip()
    if not is_bare_line(line):
        return []
    members = set()
    for version in versions:
        version = str(version or "").strip()
        if _STABLE_MEMBER.match(version) and (version == line or version.startswith(line + ".")):
            members.add(version)
    return sorted(members, key=_version_key)


@lru_cache(maxsize=8)
def _versions_on_disk(generated_dir: str) -> tuple[str, ...]:
    out: list[str] = []
    for path in sorted(Path(generated_dir).glob("*.md")):
        head = path.read_text(encoding="utf-8", errors="replace").split("\n---", 1)[0]
        fields = {name: value.strip().strip("'\"") for name, value in _FM_FIELD.findall(head)}
        if fields.get("product_id") == PRODUCT_ID and fields.get("update_version"):
            out.append(fields["update_version"])
    return tuple(out)


def versions_on_disk(generated_dir: Path | str) -> tuple[str, ...]:
    """Every DaVinci `update_version` that has a generated record under ``generated_dir``."""
    return _versions_on_disk(str(generated_dir))


def is_release_line(line: Any, versions: Iterable[Any]) -> bool:
    """A bare version with at least one tracked point release under it."""
    return len(line_members(line, versions)) > 1


def identity_fields(product_label: str, line: Any, versions: Iterable[Any]) -> dict[str, Any]:
    """The record fields that state a release-line page's identity, or {} when it is not one.

    Written only by the record writer's DaVinci branch, which runs only while the page counts
    reports: with none, the record is simply the vendor's first release of the line.
    """
    line = str(line or "").strip()
    members = line_members(line, versions)
    if len(members) < 2:
        return {}
    last = members[-1]
    name = f"{product_label} {line}"
    return {
        SCOPE_FIELD: SCOPE_RELEASE_LINE,
        "update_channel_label": f"Release line: {line} to {last}",
        "description": (
            f"User reports that name {name} without a point release. They can be about any release "
            f"from {line} to {last}; each exact release has its own page."),
        "record_note": (
            f"The user reports on this page say \"{name}\" and name no point release, so they can be "
            f"about any release from {line} to {last}. This page is the {line} release line, not one "
            f"exact update. A report that names an exact release is counted on that release's page. "
            f"Beta reports are excluded."),
    }
