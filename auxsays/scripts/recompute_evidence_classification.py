#!/usr/bin/env python3
"""Re-derive stored evidence classification through the shipped classifiers, from retained text.

AUX-041 and AUX-058 repaired the collectors; the rows they had already written still carry the old
chains' guesses ("hang" inside "change" published as "freeze / hang", a Fusion "Spline window" as
Windows). Rows are append-only inside a collector run, so nothing else will ever correct them.

A STORED LABEL IS RE-JUDGED ONLY WHEN ITS EVIDENCE IS IN HAND. The excerpt is truncated, so a label
may have come from text no longer stored. A row is re-judged only when the classifier that PRODUCED
it -- a frozen copy of the replaced chain for rows captured before that collector's repair, the
shipped one after -- reproduces the stored label from the retained text. Then:

  platform  stored == new                   -> confirmed
            stored unknown                  -> upgrade_withheld (never upgraded)
            new unknown, or a different OS  -> written `unknown` (downgrade only; a swap is refused)
  theme     the stored theme's own word-boundary rule has no hit in the retained text
                                            -> written: the shipped classifier's answer (unsupported)
            the reporter's title names the new theme and never the stored one
                                            -> written (outranked_by_title)
            anything else                   -> kept
  severity and workflow_area travel with a rewritten theme.

NEVER WRITTEN: sentiment (verdict-bearing), counted, exclusion_reason, identity, URLs, dates,
version-match fields and the text itself. The single write site refuses any other key. The one
addition is DERIVED: on a row that carries the structured evidence facts (G68), the facts that a
rewritten label changes (the issue bucket) are recomputed by lib.evidence_facts and written with it.

Zero network. Stored text only: refetching would re-theme rows this defect never touched (the stored
excerpt disagrees with the full thread on 44 of 105 rows measured).

A PINNED CORRECTION (AUX-110). Acrobat themes are outside the re-judging above (no frozen chain), so a
theme a person found wrong on a row is corrected only through a manifest (`--correction-manifest`): the
row by its five-field identity, its stored labels (`from`) and the new ones (`to`), a basis and who
authorised it. `to` must be EXACTLY the shipped classifier's answer on the retained text, so the label is
derived, never typed by hand; only theme, workflow_area and severity move (never platform, sentiment or
counted); a stored label that is neither `from` nor `to` refuses the whole run; a row already at `to` is
left alone. The write goes through the same single write site and the same field-by-field proof.

Run:  python auxsays/scripts/recompute_evidence_classification.py            # dry run, JSON on stdout
      python auxsays/scripts/recompute_evidence_classification.py --write    # in-place, block-scoped
      python auxsays/scripts/recompute_evidence_classification.py --product-id P --only-id ID ... [--write]
                                                                              # a NAMED handful only
      python auxsays/scripts/recompute_evidence_classification.py --correction-manifest PATH [--write]
                                                                              # a PINNED correction only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

import collect_obs_reports as obs  # noqa: E402
from lib import evidence_classification as ec  # noqa: E402
from lib import evidence_facts as ef  # noqa: E402
from patch_collectors import adobe_acrobat_community as acrobat  # noqa: E402
from patch_collectors import adobe_premiere as premiere  # noqa: E402
from patch_collectors import davinci  # noqa: E402
from patch_collectors import microsoft_powerpoint as powerpoint  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "_data" / "consensus_evidence.yml"

WRITABLE = frozenset({"platform", "issue_theme", "workflow_area", "severity"})
# The structured evidence facts (G68) a row must carry once its labels move: the issue bucket reads the
# theme and the area. They are DERIVED by lib.evidence_facts from the row as written, never decided
# here, and only on a row that already carries facts (`ef.derived_fact_updates`).
DERIVED_WRITABLE = frozenset(ef.STORED_FIELDS)

# An id-scoped run (`--only-id`) is for correcting a NAMED handful of rows after a classifier fix
# (AUX-062). It never writes `platform`, and it considers no row that was not named.
ONLY_ID_WRITABLE = frozenset({"issue_theme", "workflow_area", "severity"})

# When each collector's repaired classifier merged. A row captured earlier was produced by the
# replaced chain; a later one by the shipped classifier.
REPAIRED_AT = {
    "adobe-premiere-pro": "2026-10-22T09:48:05Z",     # AUX-041, #184
    "adobe-acrobat-pro": "2026-10-22T09:48:05Z",
    "adobe-acrobat-reader": "2026-10-22T09:48:05Z",
    "blackmagic-davinci": "2026-11-04T03:26:42Z",     # AUX-058, #202
    "obs-studio": "2026-11-04T03:26:42Z",
    "microsoft-powerpoint": "2026-11-04T03:26:42Z",
}

Result = tuple[str, str, str, str, str]


# --- the replaced chains, frozen verbatim --------------------------------------------------------
# Only to decide whether a stored label is reproducible from the retained text. Never written.

def _legacy_davinci(row: dict[str, Any]) -> Result:
    lowered = " ".join([_s(row, "parent_title"), _s(row, "report_title"), _s(row, "report_text_excerpt")]).lower()
    platform = "unknown"
    for name in ("windows", "macos", "mac", "linux"):
        if name in lowered:
            platform = "macos" if name == "mac" else name
            break
    if "magic mask" in lowered and "crash" in lowered:
        return "magic mask crash", "color grading / Magic Mask", platform, "high", "negative"
    if "crash" in lowered or "won't open" in lowered or "does not open" in lowered:
        return "startup or application crash", "application stability", platform, "high", "negative"
    if "decode" in lowered or "render" in lowered or "export" in lowered:
        return "render/export failure", "render/export", platform, "medium", "negative"
    if "gpu" in lowered or "performance" in lowered or "lag" in lowered or "slow" in lowered:
        return "performance regression", "timeline / GPU performance", platform, "medium", "negative"
    if "plugin" in lowered or "codec" in lowered:
        return "compatibility issue", "plugins / codecs", platform, "medium", "negative"
    if "install" in lowered:
        return "install issue", "installation", platform, "medium", "negative"
    return "unspecified issue", "general DaVinci Resolve workflow", platform, "medium", "moderate"


def _legacy_obs(row: dict[str, Any]) -> Result:
    title, _body, labels, scrubbed_body = obs.issue_text(_obs_issue(row))
    combined = f"{title} {scrubbed_body} {labels}"
    platform = "unknown"
    for name in ("windows", "macos", "linux"):
        if name in combined:
            platform = name
            break
    chain = (
        (("crashes on quit", "crash if"), ("crash / stability", "application stability", "high")),
        (("screen capture", "xcomposite", "black screen"), ("screen capture regression", "screen/window capture", "high")),
        (("black square", "mouse cursor"), ("visual capture artifact", "display capture / HDR workflow", "medium")),
        (("audio mixer", "audio"), ("audio mixer regression", "audio mixer UI", "medium")),
        (("hotkey",), ("hotkey regression", "keyboard shortcuts", "medium")),
        (("web camera", "camera"), ("camera/source regression", "camera source workflow", "medium")),
        (("rescale output",), ("output configuration regression", "output settings", "medium")),
        (("freeze", "hang"), ("freeze / hang", "application stability", "high")),
        (("plugin",), ("plugin compatibility", "plugins", "medium")),
    )
    for tokens, (theme, area, severity) in chain:
        if any(token in combined for token in tokens):
            return theme, area, platform, severity, "negative"
    return "unspecified issue", "general OBS workflow", platform, "medium", "moderate"


def _legacy_powerpoint(row: dict[str, Any]) -> Result:
    lowered = f"{_s(row, 'parent_title')} {_s(row, 'report_title')}\n{_s(row, 'report_text_excerpt')}".strip().lower()
    chain = (
        (("corrupt", "damaged", "data loss", "lost my work", "lost slides", "lost changes"), ("file corruption / data loss", "file integrity", "critical")),
        (("can't save", "cannot save", "save fail", "unable to save"), ("save failure", "save / storage", "high")),
        (("won't open", "wont open", "cannot open", "can't open", "fails to open", "won't launch", "won't start", "fails to launch"), ("launch / open failure", "startup", "high")),
        (("slideshow", "slide show", "presenter view"), ("slideshow failure", "presenting", "high")),
        (("export",), ("export failure", "export", "high")),
        (("animation", "transition"), ("animation / transition regression", "animation", "medium")),
        (("add-in", "add in", "addin"), ("add-in incompatibility", "add-ins", "medium")),
        (("render", "display", "blank slide"), ("rendering regression", "rendering", "medium")),
        (("slow", "lag", "performance", "high cpu", "memory leak"), ("performance regression", "performance", "medium")),
        (("install", "update fail"), ("install/update failure", "update", "high")),
        (("crash", "freeze", "hang", "not responding"), ("crash or hang", "system stability", "high")),
    )
    for tokens, (theme, area, severity) in chain:
        if any(token in lowered for token in tokens):
            return theme, area, "windows", severity, "negative"
    return "unspecified PowerPoint issue", "PowerPoint workflow", "windows", "medium", "negative"


def _legacy_premiere(row: dict[str, Any]) -> Result:
    lowered = " ".join([_s(row, "parent_title"), _s(row, "report_title"), _s(row, "report_text_excerpt")]).lower()
    platform = "unknown"
    for token, label in (("windows", "windows"), ("macos", "macos"), ("mac os", "macos"), ("mac", "macos")):
        if token in lowered:
            platform = label
            break
    if "export" in lowered or "render" in lowered:
        return "export/render failure", "export/render", platform, "high", "negative"
    if "project" in lowered and any(token in lowered for token in ("open", "load", "hang", "delay")):
        return "project open/load failure", "project opening", platform, "high", "negative"
    if "timeline" in lowered and any(token in lowered for token in ("crash", "freeze", "hang", "lag")):
        return "timeline crash or hang", "timeline editing", platform, "high", "negative"
    if "ui" in lowered or "interface" in lowered or "lag" in lowered or "slow" in lowered:
        return "interface lag or freezing", "editing interface", platform, "high", "negative"
    if "plugin" in lowered or "compatib" in lowered:
        return "plugin or compatibility issue", "plugins / compatibility", platform, "medium", "negative"
    if "media" in lowered or "decode" in lowered or "audio" in lowered or "video" in lowered:
        return "media decode or audio/video issue", "media playback", platform, "medium", "negative"
    if "install" in lowered:
        return "install issue", "installation", platform, "medium", "negative"
    if "crash" in lowered or "hang" in lowered or "freeze" in lowered:
        return "application crash or hang", "application stability", platform, "high", "negative"
    return "unspecified issue", "Premiere Pro workflow", platform, "medium", "moderate"


def _legacy_acrobat_platform(row: dict[str, Any]) -> str:
    lowered = _s(row, "report_text_excerpt").lower()
    for token, label in (("windows", "windows"), ("macos", "macos"), ("mac os", "macos"), ("mac ", "macos")):
        if token in lowered:
            return label
    return "unknown"


# --- the shipped classifiers, on retained text ----------------------------------------------------

def _s(row: dict[str, Any], key: str) -> str:
    return str(row.get(key) or "")


def _heading(row: dict[str, Any]) -> str:
    titles = [_s(row, "report_title").strip(), _s(row, "parent_title").strip()]
    return " ".join(dict.fromkeys(title for title in titles if title))


def _obs_issue(row: dict[str, Any]) -> dict[str, Any]:
    return {"title": _s(row, "report_title"), "body": _s(row, "report_text_excerpt"), "labels": []}


def _shipped(row: dict[str, Any]) -> Result:
    pid, body = _s(row, "product_id"), _s(row, "report_text_excerpt")
    if pid == "blackmagic-davinci":
        return davinci.classify(_heading(row), body)
    if pid == "obs-studio":
        return obs.classify(_obs_issue(row))
    if pid == "microsoft-powerpoint":
        return powerpoint.classify(_heading(row), body)
    if pid == "adobe-premiere-pro":
        return premiere.classify(_s(row, "report_title") or _s(row, "parent_title"), body)
    return acrobat.acrobat_classify(body, title=_s(row, "report_title") or _s(row, "parent_title"))


THEME_RULES: dict[str, tuple[ec.ThemeRule, ...]] = {
    "blackmagic-davinci": davinci._DAVINCI_THEME_RULES,
    "obs-studio": obs._OBS_THEME_RULES,
    "microsoft-powerpoint": powerpoint._POWERPOINT_THEME_RULES,
    "adobe-premiere-pro": premiere._PREMIERE_THEME_RULES,
}
LEGACY: dict[str, Callable[[dict[str, Any]], Result]] = {
    "blackmagic-davinci": _legacy_davinci,
    "obs-studio": _legacy_obs,
    "microsoft-powerpoint": _legacy_powerpoint,
    "adobe-premiere-pro": _legacy_premiere,
}


def _producer(row: dict[str, Any]) -> Callable[[dict[str, Any]], Result] | None:
    """The classifier that wrote this row, or None for Acrobat themes (unchanged by AUX-041)."""
    pid = _s(row, "product_id")
    if _s(row, "captured_at") >= REPAIRED_AT[pid]:
        return _shipped
    return LEGACY.get(pid)


def _producer_platform(row: dict[str, Any]) -> str:
    pid = _s(row, "product_id")
    if _s(row, "captured_at") >= REPAIRED_AT[pid]:
        return _shipped(row)[2]
    if pid in LEGACY:
        return LEGACY[pid](row)[2]
    return _legacy_acrobat_platform(row)


def _rule_hits(rule: ec.ThemeRule, heading: str, body: str) -> tuple[int, int]:
    return ec.count_hits(heading, rule.pattern, negatable=rule.negatable)[0], \
        ec.count_hits(body, rule.pattern, negatable=rule.negatable)[0]


def decide(row: dict[str, Any]) -> dict[str, Any]:
    """The decision for one row: the fields to write (possibly none) and why."""
    pid = _s(row, "product_id")
    new = _shipped(row)
    out: dict[str, Any] = {"id": row.get("id"), "product_id": pid, "counted": bool(row.get("counted")),
                           "write": {}, "platform": "", "theme": ""}

    stored_platform = _s(row, "platform")
    if stored_platform == new[2]:
        out["platform"] = "confirmed"
    elif stored_platform in ("", "unknown"):
        out["platform"] = "upgrade_withheld"
    elif _producer_platform(row) != stored_platform:
        out["platform"] = "not_reproducible_from_retained_text"
    else:
        out["platform"] = "downgraded_unsupported" if new[2] == "unknown" else "downgraded_swap_refused"
        out["write"]["platform"] = "unknown"

    stored_theme, producer = _s(row, "issue_theme"), _producer(row)
    rules = THEME_RULES.get(pid)
    if stored_theme == new[0]:
        out["theme"] = "confirmed"
    elif producer is None or rules is None:
        out["theme"] = "not_in_scope"
    elif producer(row)[0] != stored_theme:
        out["theme"] = "not_reproducible_from_retained_text"
    else:
        own = next((rule for rule in rules if rule.theme == stored_theme), None)
        heading, body = (_s(row, "report_title") or _s(row, "parent_title")), _s(row, "report_text_excerpt")
        if pid in ("blackmagic-davinci", "microsoft-powerpoint"):
            heading = _heading(row)
        if own is None:
            out["theme"] = "kept_not_a_table_theme"
        else:
            own_heading, own_body = _rule_hits(own, heading, body)
            verdict = ec.score_themes(heading, body, rules)
            if own_heading + own_body == 0:
                out["theme"] = "rewritten_unsupported"
            elif own_heading == 0 and verdict is not None and verdict.heading_hits > 0:
                out["theme"] = "rewritten_outranked_by_title"
            else:
                out["theme"] = "kept_supported"
            if out["theme"].startswith("rewritten"):
                out["write"].update({"issue_theme": new[0], "workflow_area": new[1], "severity": new[3]})
    if "severity" in out["write"] and out["write"]["severity"] not in ec.VALID_SEVERITIES:
        raise SystemExit(f"refusing {row.get('id')}: severity {out['write']['severity']!r} would un-count it")
    return out


# --- the single write site -----------------------------------------------------------------------

def _write_store(store: Path, text: str) -> None:
    """The one place this module writes: the whole store, already proven field by field."""
    store.write_bytes(text.encode("utf-8"))


_ID_LINE = re.compile(r"^- id: (.+)$", re.M)


def _scalar(value: str) -> str:
    dumped = yaml.safe_dump(value, default_flow_style=True, allow_unicode=True, width=10_000)
    return dumped.split("\n", 1)[0]


def apply_writes(text: str, row_ids: list[Any], writes: dict[int, dict[str, str]]) -> str:
    """Rewrite only the named field lines inside each written row's block. Rows are addressed by
    POSITION, cross-checked id for id against the parsed list: an id alone is not an identity here
    (Acrobat Pro and Reader rows share ids for one shared build). Refuses any other key, or a field
    that is not exactly one line in its block."""
    starts = [(m.start(), yaml.safe_load(m.group(1))) for m in _ID_LINE.finditer(text)]
    if [rid for _start, rid in starts] != list(row_ids):
        raise SystemExit("refusing: the store's row blocks do not line up with its parsed rows")
    pieces, cursor = [], 0
    for index in sorted(writes):
        fields = writes[index]
        if set(fields) - WRITABLE - DERIVED_WRITABLE:
            raise SystemExit(f"refusing row {index}: not writable: {sorted(set(fields) - WRITABLE - DERIVED_WRITABLE)}")
        start = starts[index][0]
        end = starts[index + 1][0] if index + 1 < len(starts) else len(text)
        block = text[start:end]
        for key, value in fields.items():
            pattern = re.compile(rf"^(  {key}: ).*$", re.M)
            if len(pattern.findall(block)) != 1:
                raise SystemExit(f"refusing row {index}: {key} is not exactly one line in its block")
            block = pattern.sub(lambda m: m.group(1) + _scalar(value), block)
        pieces.append(text[cursor:start])
        pieces.append(block)
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def run(store: Path, write: bool, only_ids: tuple[str, ...] = (), product_id: str = "") -> dict[str, Any]:
    raw = store.read_bytes().decode("utf-8")
    rows = yaml.load(raw, Loader=yaml.SafeLoader)["evidence"]
    named: dict[str, list[int]] = {}
    if only_ids:
        if product_id not in REPAIRED_AT:
            raise SystemExit("refusing: --only-id needs --product-id naming one repaired product")
        for rid in only_ids:
            hits = [i for i, row in enumerate(rows) if _s(row, "product_id") == product_id and row.get("id") == rid]
            if len(hits) != 1:
                raise SystemExit(f"refusing: --only-id {rid!r} matches {len(hits)} {product_id} rows, not exactly one")
            named[rid] = hits
        if len(set(only_ids)) != len(only_ids):
            raise SystemExit("refusing: --only-id repeats an id")
    selected = {i for hits in named.values() for i in hits}
    decisions = [(index, decide(row)) for index, row in enumerate(rows)
                 if _s(row, "product_id") in REPAIRED_AT and (not only_ids or index in selected)]
    if only_ids:
        for _index, d in decisions:
            d["write"] = {k: v for k, v in d["write"].items() if k in ONLY_ID_WRITABLE}
    writes = {index: d["write"] for index, d in decisions if d["write"]}
    writes = {index: {**fields, **ef.derived_fact_updates(rows[index], fields)} for index, fields in writes.items()}
    summary: dict[str, dict[str, int]] = {}
    for _index, d in decisions:
        for axis in ("platform", "theme"):
            key = f"{d['product_id']}:{axis}"
            summary.setdefault(key, {})
            summary[key][d[axis]] = summary[key].get(d[axis], 0) + 1
    basis = {index: {axis: d[axis] for axis in ("platform", "theme")} for index, d in decisions}
    changes = [{"id": rows[index].get("id"), "product_id": rows[index].get("product_id"),
                "update_version": rows[index].get("update_version"),
                "counted": bool(rows[index].get("counted")),
                "title": _s(rows[index], "report_title")[:120],
                **{f: [rows[index].get(f), v] for f, v in fields.items()}, "basis": basis[index]}
               for index, fields in sorted(writes.items())]
    new_text = apply_writes(raw, [row.get("id") for row in rows], writes)
    after_rows = yaml.load(new_text, Loader=yaml.SafeLoader)["evidence"]
    # Prove the edit is exactly the decided one: every other field of every row is unchanged.
    if len(after_rows) != len(rows):
        raise SystemExit("refusing: the row count changed")
    for index, (old, new) in enumerate(zip(rows, after_rows)):
        if new != dict(old, **writes.get(index, {})):
            raise SystemExit(f"refusing row {index} ({old.get('id')}): the edit changed more than decided")
    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "store_sha256_before": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "store_sha256_after": hashlib.sha256(new_text.encode("utf-8")).hexdigest(),
        "rows_in_scope": len(decisions), "rows_changed": len(writes),
        "platform_labels_written": sum("platform" in w for w in writes.values()),
        "themes_written": sum("issue_theme" in w for w in writes.values()),
        "summary": summary, "changes": changes, "written": False,
    }
    if only_ids:
        report["only_ids"] = {rows[i].get("id"): {"theme": basis[i]["theme"], "written": i in writes}
                              for i in sorted(selected)}
    if write and writes:
        _write_store(store, new_text)
        report["written"] = True
    return report


# --- a pinned, human-authorised correction (AUX-110) ----------------------------------------------

CORRECTION_SELECTOR = ("product_id", "update_version", "target_build", "id", "source_url")


def _shipped_labels(row: dict[str, Any]) -> dict[str, str]:
    theme, area, _platform, severity, _sentiment = _shipped(row)
    return {"issue_theme": theme, "workflow_area": area, "severity": severity}


def correction_entries(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """The pinned corrections, refusing a manifest that could select ambiguously or widen the fields."""
    if list(doc.get("selector") or []) != list(CORRECTION_SELECTOR):
        raise SystemExit("refusing: the correction manifest's selector is not the five-field identity")
    if sorted(doc.get("fields") or []) != sorted(ONLY_ID_WRITABLE):
        raise SystemExit("refusing: the correction manifest's fields are not theme, workflow_area and severity")
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        raise SystemExit("refusing: the correction manifest has no entries")
    seen: set[tuple[str, ...]] = set()
    for entry in entries:
        ident = tuple(str(entry.get(key) or "") for key in CORRECTION_SELECTOR)
        if not all(ident[i] for i in (0, 1, 3, 4)) or ident[0] not in REPAIRED_AT:
            raise SystemExit(f"refusing: a correction lacks part of its identity or names no repaired product: {ident}")
        if ident in seen:
            raise SystemExit(f"refusing: a correction names one row twice: {ident[3]}")
        seen.add(ident)
        frm, to = entry.get("from"), entry.get("to")
        if not (isinstance(frm, dict) and isinstance(to, dict)
                and set(frm) == set(ONLY_ID_WRITABLE) and set(to) == set(ONLY_ID_WRITABLE)) or frm == to:
            raise SystemExit(f"refusing: a correction must state from and to for exactly theme, workflow_area "
                             f"and severity, and change one of them: {ident[3]}")
        if not str(entry.get("basis") or "").strip() or not str(entry.get("authorized_by") or "").strip():
            raise SystemExit(f"refusing: a correction must state its basis and who authorised it: {ident[3]}")
    return entries


def run_corrections(store: Path, manifest: Path, write: bool) -> dict[str, Any]:
    """Apply a pinned correction manifest, all or nothing. Refusals raise SystemExit before any write."""
    raw = store.read_bytes().decode("utf-8")
    rows = yaml.load(raw, Loader=yaml.SafeLoader)["evidence"]
    doc = json.loads(Path(manifest).read_text(encoding="utf-8"))
    entries = correction_entries(doc)
    writes: dict[int, dict[str, str]] = {}
    decided: list[dict[str, Any]] = []
    for entry in entries:
        ident = tuple(str(entry.get(key) or "") for key in CORRECTION_SELECTOR)
        hits = [i for i, row in enumerate(rows)
                if tuple(_s(row, key) for key in CORRECTION_SELECTOR) == ident]
        if len(hits) != 1:
            raise SystemExit(f"refusing: correction {ident[3]!r} matches {len(hits)} rows, not exactly one")
        index = hits[0]
        row = rows[index]
        derived = _shipped_labels(row)
        if entry["to"] != derived:
            raise SystemExit(f"refusing: correction {ident[3]!r} is not the shipped classifier's answer on the "
                             f"retained text ({derived})")
        if derived["severity"] not in ec.VALID_SEVERITIES:
            raise SystemExit(f"refusing {ident[3]!r}: severity {derived['severity']!r} would un-count it")
        current = {key: _s(row, key) for key in ONLY_ID_WRITABLE}
        if current == entry["to"]:
            action = "already_corrected"
        elif current == entry["from"]:
            action = "correct"
            writes[index] = dict(entry["to"])
            writes[index].update(ef.derived_fact_updates(row, writes[index]))
        else:
            raise SystemExit(f"refusing: correction {ident[3]!r}: the stored labels {current} are neither the "
                             f"pinned from nor to")
        decided.append({**dict(zip(CORRECTION_SELECTOR, ident)), "action": action,
                        "from": entry["from"], "to": entry["to"], "counted": row.get("counted")})
    new_text = apply_writes(raw, [row.get("id") for row in rows], writes)
    after_rows = yaml.load(new_text, Loader=yaml.SafeLoader)["evidence"]
    if len(after_rows) != len(rows):
        raise SystemExit("refusing: the row count changed")
    for index, (old, new) in enumerate(zip(rows, after_rows)):
        if new != dict(old, **writes.get(index, {})):
            raise SystemExit(f"refusing row {index} ({old.get('id')}): the edit changed more than decided")
    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": "correction_manifest",
        "manifest_sha256": hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
        "store_sha256_before": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "store_sha256_after": hashlib.sha256(new_text.encode("utf-8")).hexdigest(),
        "rows_changed": len(writes), "corrections": decided, "written": False,
    }
    if write and writes:
        _write_store(store, new_text)
        report["written"] = True
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--store", type=Path, default=STORE)
    parser.add_argument("--write", action="store_true", help="apply the decided edits in place")
    parser.add_argument("--product-id", default="", help="required with --only-id")
    parser.add_argument("--only-id", action="append", default=[], metavar="ID",
                        help="consider ONLY this row id (repeatable); writes theme, workflow_area and "
                             "severity only, never platform")
    parser.add_argument("--correction-manifest", type=Path, default=None,
                        help="apply ONLY this pinned correction manifest (AUX-110); excludes --only-id")
    args = parser.parse_args(argv)
    if args.product_id and not args.only_id:
        parser.error("--product-id is only meaningful with --only-id")
    if args.correction_manifest is not None:
        if args.only_id:
            parser.error("--correction-manifest cannot be combined with --only-id")
        print(json.dumps(run_corrections(args.store, args.correction_manifest, args.write),
                         indent=2, ensure_ascii=False))
        return 0
    print(json.dumps(run(args.store, args.write, tuple(args.only_id), args.product_id),
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
