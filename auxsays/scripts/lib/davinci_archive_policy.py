"""DaVinci Resolve archive policy: the newest STABLE major minus two, or older, is archived.

THE RULE (AUX-065). A DaVinci Resolve generated record whose major version is at least
``GAP`` (2) behind the newest STABLE major is archived: ``update_status: archived``. With 21 the
newest stable major the threshold is 19, so every 10.x-19.x record archives and 20.x / 21.x /
"21 Public Beta 1" stay active. When a stable 22 ships the threshold becomes 20, and so on.

THREE PROPERTIES THIS MODULE EXISTS TO HOLD.

1. A public beta never sets the baseline. ``21 Public Beta 1`` is major 21 but not stable; only a
   stable record raises the newest stable major. A 22 beta alone therefore changes nothing.

2. It fails CLOSED, and says why. A jump of more than one between the two newest stable majors, a
   stable major outside 1..99 (a bare "2026" parses as major 2026), no stable record at all, or an
   archived record at or above the baseline each REFUSE the whole plan with a named reason. The
   plan is never partially applied: a baseline that cannot be trusted would otherwise archive
   every record in the product.

3. It is a ONE-WAY RATCHET. The plan only ever proposes ``<anything but archived> -> archived``.
   There is no un-archive path in this module; a record already archived is left exactly as it is
   even if a later baseline would no longer select it. Restoring one is a separate, explicitly
   authorised act.

SCOPE. DaVinci only: a record is considered when ``product_id == blackmagic-davinci`` and
``update_entry`` is true. Nothing here reads another product, evidence, counts or verdicts.

PURE. ``plan_archive`` reads record front matter and returns a plan; it writes nothing. The CLI
``scripts/apply_davinci_archive_policy.py`` performs the single-line edit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from .normalize import split_front_matter
from .normalize_davinci_version import normalize_davinci_version

PRODUCT_ID = "blackmagic-davinci"
GAP = 2
ARCHIVED = "archived"
MAJOR_MIN = 1
MAJOR_MAX = 99

REFUSAL_NO_STABLE = "no_stable_record"
REFUSAL_JUMP = "implausible_major_jump"
REFUSAL_RANGE = "implausible_major_value"
REFUSAL_BASELINE_BELOW_ARCHIVED = "baseline_not_above_archived_record"
REFUSAL_UNREADABLE = "unreadable_record"

# The most a newest stable major may exceed the next stable major below it. Releases are annual;
# one is the only legitimate step. (Gaps BELOW the top, such as there being no Resolve 13, are
# history and are not examined.)
MAX_MAJOR_JUMP = 1


@dataclass(frozen=True)
class Record:
    path: Path
    version: str
    status: str
    major: int | None
    is_beta: bool
    rejected: bool
    rejection_reason: str | None


@dataclass
class Plan:
    gap: int = GAP
    records: int = 0
    newest_stable_major: int | None = None
    threshold_major: int | None = None
    refused: bool = False
    refusal_reason: str | None = None
    refusal_detail: str | None = None
    to_archive: list[Record] = field(default_factory=list)
    already_archived: int = 0
    ratchet_held: list[Record] = field(default_factory=list)
    unparsed: list[Record] = field(default_factory=list)

    def as_dict(self, root: Path | None = None) -> dict[str, Any]:
        def rel(p: Path) -> str:
            if root is not None:
                try:
                    return p.relative_to(root).as_posix()
                except ValueError:
                    pass
            return p.as_posix()

        return {
            "product_id": PRODUCT_ID,
            "gap": self.gap,
            "records": self.records,
            "newest_stable_major": self.newest_stable_major,
            "threshold_major": self.threshold_major,
            "refused": self.refused,
            "refusal_reason": self.refusal_reason,
            "refusal_detail": self.refusal_detail,
            "to_archive_count": len(self.to_archive),
            "to_archive": [
                {"path": rel(r.path), "version": r.version, "major": r.major,
                 "from": r.status, "to": ARCHIVED}
                for r in self.to_archive
            ],
            "already_archived": self.already_archived,
            "ratchet_held": [
                {"path": rel(r.path), "version": r.version, "major": r.major}
                for r in self.ratchet_held
            ],
            "unparsed": [
                {"path": rel(r.path), "version": r.version, "reason": r.rejection_reason}
                for r in self.unparsed
            ],
        }


def read_front_matter(path: Path) -> dict[str, Any]:
    text = path.read_bytes().decode("utf-8")
    front, _body = split_front_matter(text)
    if front is None:
        return {}
    # SafeLoader on purpose: CSafeLoader dies silently on deep nesting (libyaml C-stack overflow).
    data = yaml.load(front, Loader=yaml.SafeLoader)
    return data if isinstance(data, dict) else {}


def _record_from_front_matter(path: Path, fm: dict[str, Any]) -> Record | None:
    if fm.get("update_entry") is not True:
        return None
    if str(fm.get("product_id") or "").strip() != PRODUCT_ID:
        return None
    version = str(fm.get("update_version") if fm.get("update_version") is not None else "").strip()
    status = str(fm.get("update_status") or "").strip()
    n = normalize_davinci_version(version)
    return Record(
        path=path,
        version=version,
        status=status,
        major=None if n["rejected"] else n["major_version"],
        is_beta=bool(n["is_beta"]),
        rejected=bool(n["rejected"]),
        rejection_reason=n["rejection_reason"],
    )


def load_records(generated_dir: Path) -> tuple[list[Record], list[str]]:
    """Every DaVinci record under ``generated_dir``, plus the names of unreadable DaVinci files.

    A cheap byte test skips files that cannot be DaVinci before any YAML is parsed, so the scan of
    the whole generated directory stays fast. A file that mentions the product id but cannot be
    read is returned in the second list and makes the plan REFUSE rather than guess.
    """
    records: list[Record] = []
    unreadable: list[str] = []
    needle = PRODUCT_ID.encode("ascii")
    for path in sorted(generated_dir.glob("*.md")):
        try:
            raw = path.read_bytes()
        except OSError:
            unreadable.append(path.name)
            continue
        if needle not in raw:
            continue
        try:
            fm = read_front_matter(path)
        except Exception:  # noqa: BLE001 -- ANY parse failure must be a refusal, never a skip
            unreadable.append(path.name)
            continue
        rec = _record_from_front_matter(path, fm)
        if rec is not None:
            records.append(rec)
    return records, unreadable


def plan_records(records: Iterable[Record], *, unreadable: Iterable[str] = (), gap: int = GAP) -> Plan:
    """The pure decision, over already-loaded records. No filesystem access."""
    recs = list(records)
    plan = Plan(gap=gap, records=len(recs))

    def refuse(reason: str, detail: str) -> Plan:
        plan.refused = True
        plan.refusal_reason = reason
        plan.refusal_detail = detail
        plan.to_archive = []
        return plan

    bad = sorted(unreadable)
    if bad:
        return refuse(REFUSAL_UNREADABLE,
                      f"{len(bad)} DaVinci record(s) could not be read: {', '.join(bad[:5])}")

    stable_majors = sorted({r.major for r in recs if not r.rejected and not r.is_beta
                            and r.major is not None})
    if not stable_majors:
        return refuse(REFUSAL_NO_STABLE, "no stable DaVinci record parses to a major version")

    out_of_range = [m for m in stable_majors if not (MAJOR_MIN <= m <= MAJOR_MAX)]
    if out_of_range:
        return refuse(REFUSAL_RANGE,
                      f"stable major(s) {out_of_range} fall outside {MAJOR_MIN}..{MAJOR_MAX}")

    newest = stable_majors[-1]
    plan.newest_stable_major = newest
    plan.threshold_major = newest - gap
    if len(stable_majors) >= 2 and newest - stable_majors[-2] > MAX_MAJOR_JUMP:
        return refuse(REFUSAL_JUMP,
                      f"newest stable major {newest} is {newest - stable_majors[-2]} above the next "
                      f"stable major {stable_majors[-2]}; the limit is {MAX_MAJOR_JUMP}")

    suspect = [r for r in recs if r.status == ARCHIVED and r.major is not None and r.major >= newest]
    if suspect:
        return refuse(REFUSAL_BASELINE_BELOW_ARCHIVED,
                      f"{len(suspect)} archived record(s) have major >= the newest stable major "
                      f"{newest} (e.g. {suspect[0].version}); the baseline cannot be trusted")

    for r in recs:
        if r.rejected or r.major is None:
            plan.unparsed.append(r)
            continue
        qualifies = r.major <= plan.threshold_major
        if r.status == ARCHIVED:
            plan.already_archived += 1
            if not qualifies:
                plan.ratchet_held.append(r)
            continue
        if qualifies:
            plan.to_archive.append(r)
    return plan


def plan_archive(generated_dir: Path, *, gap: int = GAP) -> Plan:
    records, unreadable = load_records(generated_dir)
    return plan_records(records, unreadable=unreadable, gap=gap)
