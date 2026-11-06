#!/usr/bin/env python3
"""READ-ONLY diagnostic for the Windows link rule `identity_not_linked_to_issue` (AUX-076).

Not a governed check, and never one: the evidence store grows every six hours, so anything that
pins a live total breaks CI on ordinary growth (the D3 lesson). The governed suite,
tests/test_windows_identity_link_roles.py, runs only on frozen synthetic fixtures. This script is
the companion that looks at the LIVE corpus, prints what it sees, and warns; it exits 0 whatever
the corpus says, unless it cannot read its inputs.

    python auxsays/scripts/diagnose_windows_link_roles.py
        Replays every counted Windows row (the shipped count population) through the CURRENT
        authority on its retained text (parent_title + report_title + stored excerpt), prints the
        rows the link rule refuses and the per-occurrence role tallies, and diffs the refusal set
        against the pinned manifest (scripts/audit/r1_link_roles_refusals_2026-11-05.json). A row
        missing from, or added to, the pinned set is a WARN line, not a failure. `residual_impact`
        measures the declared residual classes R1N-01..R1N-03 (ledger AUX-076) on the same rows: the
        in-scope rows the narrow rule keeps because a mention is not a stated state (R1N-01), because
        a stated state is continued, taken up or follows a blocking word (R1N-02), or because the body
        has a link word (R1N-03), listing every such row outside the reviewed keep fixture.

    python auxsays/scripts/diagnose_windows_link_roles.py --fixture-equivalence
        The fixture builder's check. Every case in the frozen synthetic fixture names its stored
        original by (update_version, target_build, question id); the synthetic text must reach the
        same decision, the same per-occurrence roles AND the same link words as the stored
        original, and both must be accepted by the authority with the link rule switched off. Exits
        1 on any mismatch, because a paraphrase that changes the decision does not test the rule it
        claims to test.

Zero writes: it reads the store and the records through `live_eligibility.load_inputs`, prints JSON
and returns.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from lib import live_eligibility  # noqa: E402
from lib.patch_identity import patch_key  # noqa: E402
from patch_collectors import microsoft_windows as mw  # noqa: E402

AUX_ROOT = _HERE.parent
REASON = "identity_not_linked_to_issue"
MANIFEST = _HERE / "audit" / "r1_link_roles_refusals_2026-11-05.json"
FIXTURE = _HERE / "tests" / "fixtures" / "windows_link_roles" / "corpus_shapes.json"
SELECTOR = ("product_id", "update_version", "target_build", "id", "source_url")
TARGET_FIELDS = ("target_feature_version", "target_kb", "target_os_build", "target_release_date", "update_version")


def retained_text(parent_title: str, report_title: str, excerpt: str) -> str:
    """The text a stored row still carries, joined exactly as `row_from_candidate` joins it. A capped
    excerpt ends in "..."; the marker is not the reporter's text and is removed."""
    excerpt = excerpt or ""
    if excerpt.endswith("..."):
        excerpt = excerpt[:-3]
    return " ".join([parent_title or "", report_title or "", excerpt]).strip()


@contextmanager
def link_rule_disabled():
    """The authority exactly as shipped, minus the link rule: proves the rule is the deciding gate."""
    original = mw.identity_not_linked_to_issue
    mw.identity_not_linked_to_issue = lambda *_a, **_k: False
    try:
        yield
    finally:
        mw.identity_not_linked_to_issue = original


def decide(target: dict[str, Any], url: str, date: str, parent: str, title: str, excerpt: str,
           kb: str, build: str, feature: str) -> dict[str, Any]:
    text = retained_text(parent, title, excerpt)
    reason = mw.windows_learn_qna_reason(target, url, date, text, title, kb, build, feature)
    with link_rule_disabled():
        without = mw.windows_learn_qna_reason(target, url, date, text, title, kb, build, feature)
    target_kb = str(target.get("target_kb") or "")
    in_scope = bool(build and not kb and not mw._has_exact(title, build)
                    and not (target_kb and mw._has_exact(title, target_kb)))
    details = (mw.identity_link_details(text, title, build, str(target.get("target_release_date") or ""))
               if in_scope else [])
    words = sorted({name for name, _w in mw.identity_link_words(text, title)}) if in_scope else []
    return {"reason": reason, "reason_without_link_rule": without, "in_scope": in_scope,
            "roles": [[role, rule] for role, rule, _sentence in details], "link_words": words}


def counted_windows_rows(aux_root: Path) -> list[dict[str, Any]]:
    inputs = live_eligibility.load_inputs(aux_root)
    pid = mw.PRODUCT_ID
    targets = {}
    for _path, data in inputs.records:
        if str(data.get("product_id")) == pid:
            targets[patch_key(pid, data.get("update_version"), data.get("target_build"))] = {
                k: str(data.get(k) or "").strip() for k in TARGET_FIELDS}
    out = []
    for key, rows in sorted(inputs.counted_groups.items()):
        if key[0] != pid:
            continue
        for row in rows:
            out.append({"row": row, "target": targets[key],
                        "five": [str(row.get(f) or "") for f in SELECTOR]})
    return out


def decide_row(item: dict[str, Any]) -> dict[str, Any]:
    row = item["row"]
    return decide(item["target"], str(row.get("source_url") or ""), str(row.get("source_date") or ""),
                  str(row.get("parent_title") or ""), str(row.get("report_title") or ""),
                  str(row.get("report_text_excerpt") or ""), str(row.get("matched_kb") or ""),
                  str(row.get("matched_os_build") or ""), str(row.get("matched_feature_version") or ""))


def question_id(url: str) -> str:
    part = url.split("/questions/", 1)[1] if "/questions/" in url else ""
    return part.split("/", 1)[0]


def residual_class(got: dict[str, Any]) -> str:
    """The declared residual class (ledger AUX-076) of an in-scope row the narrow rule keeps."""
    found = [role for role, _rule in got["roles"]]
    if "unlinked" in found:
        return "R1N-01"
    if "linked" in found:
        return "R1N-02"
    return "R1N-03"


def residual_impact(items: list[dict[str, Any]], decided: list[dict[str, Any]]) -> dict[str, Any]:
    """How many stored, counted, in-scope rows each declared residual class (ledger AUX-076) keeps, and
    which of them lie outside the reviewed keep fixture (each of those needs a look)."""
    keep_originals = {tuple(c["original"]) for c in json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
                      if c["kind"] == "keep"}

    def row_key(it: dict[str, Any]) -> tuple[str, str, str]:
        r = it["row"]
        return (str(r.get("update_version") or ""), str(r.get("target_build") or ""),
                question_id(str(r.get("source_url") or "")))
    by_class: dict[str, list[dict[str, Any]]] = {"R1N-01": [], "R1N-02": [], "R1N-03": []}
    by_rule = Counter()
    for item, got in zip(items, decided):
        if not got["roles"] or got["reason"] is not None:
            continue
        by_class[residual_class(got)].append(item)
        for role, rule in got["roles"]:
            if role == "linked":
                by_rule[rule] += 1
        for name in got["link_words"]:
            by_rule["link_word:" + name] += 1
    return {
        **{f"{cls}_rows": len(rows) for cls, rows in by_class.items()},
        "kept_by_rule": dict(sorted(by_rule.items())),
        "rows_outside_the_reviewed_keep_fixture": {cls: sorted(list(it["five"]) for it in rows
                                                               if row_key(it) not in keep_originals)
                                                   for cls, rows in by_class.items()},
    }


def replay(aux_root: Path) -> dict[str, Any]:
    items = counted_windows_rows(aux_root)
    refused, roles = [], Counter()
    reasons, scope = Counter(), Counter()
    decided = []
    for item in items:
        got = decide_row(item)
        decided.append(got)
        reasons[str(got["reason"])] += 1
        scope["in_scope_build_visible" if got["roles"] else ("in_scope_build_not_retained" if got["in_scope"]
                                                              else "out_of_scope")] += 1
        for role, rule in got["roles"]:
            roles[rule or role] += 1
        if got["reason"] == REASON:
            refused.append(item["five"])
    pinned = [[e[f] for f in SELECTOR] for e in json.loads(MANIFEST.read_text(encoding="utf-8"))["entries"]]
    got_set = {tuple(f) for f in refused}
    pin_set = {tuple(f) for f in pinned}
    counted_set = {tuple(item["five"]) for item in items}
    store = aux_root / "_data" / "consensus_evidence.yml"
    report = {
        "mode": "replay", "write": False,
        "store_sha256": hashlib.sha256(store.read_bytes()).hexdigest(),
        "authority_sha256": hashlib.sha256((_HERE / "patch_collectors" / "microsoft_windows.py").read_bytes()).hexdigest(),
        "counted_windows_rows": len(items),
        "reasons_on_retained_text": dict(sorted(reasons.items())),
        "rule_scope": dict(sorted(scope.items())),
        "refused_by_link_rule": len(refused),
        # In-scope rows only (build-only identity, title silent on build and KB), one entry per occurrence.
        "occurrence_roles": dict(sorted(roles.items())),
        "pinned_manifest_rows": len(pin_set),
        # Withdrawn by an audited correction (or rolled over): expected once that correction lands.
        "pinned_no_longer_counted": sorted(list(f) for f in pin_set - counted_set),
        # Still counted, but the current authority no longer refuses it: the rule or the row changed.
        "missing_from_replay": sorted(list(f) for f in (pin_set & counted_set) - got_set),
        "not_in_pinned_manifest": sorted(list(f) for f in got_set - pin_set),
        # The declared residual classes R1N-01..R1N-03 (ledger AUX-076), measured on this corpus.
        "residual_impact": residual_impact(items, decided),
    }
    return report


def fixture_equivalence(aux_root: Path) -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for item in counted_windows_rows(aux_root):
        row = item["row"]
        key = (str(row.get("update_version") or ""), str(row.get("target_build") or ""),
               question_id(str(row.get("source_url") or "")))
        by_key.setdefault(key, []).append(item)
    results, ok = [], True
    for case in fixture["cases"]:
        key = tuple(case["original"])
        found = by_key.get(key, [])
        entry = {"case": case["case"], "original": list(key), "stored_rows": len(found)}
        if len(found) != 1:
            entry["verdict"] = "ORIGINAL_NOT_UNIQUE"
            ok = False
            results.append(entry)
            continue
        stored = decide_row(found[0])
        t = case["target"]
        synth = decide(t, case["source_url"], case["source_date"], case["parent_title"], case["report_title"],
                       case["report_text_excerpt"], case["matched_kb"], case["matched_os_build"],
                       case["matched_feature_version"])
        same_target = found[0]["target"] == t
        same_ids = all(str(found[0]["row"].get(f) or "") == case[f]
                       for f in ("matched_kb", "matched_os_build", "matched_feature_version"))
        synth_text = retained_text(case["parent_title"], case["report_title"], case["report_text_excerpt"])
        rematched = {
            "matched_kb": t["target_kb"] if t["target_kb"] and mw._has_exact(synth_text, t["target_kb"]) else "",
            "matched_os_build": t["target_os_build"] if mw._has_exact(synth_text, t["target_os_build"]) else "",
        }
        entry.update({
            "stored": stored, "synthetic": synth, "same_target": same_target, "same_stored_identity_fields": same_ids,
            "synthetic_rematches_kb_and_build": rematched == {"matched_kb": case["matched_kb"],
                                                              "matched_os_build": case["matched_os_build"]},
            "expected": {"reason": case["expected_reason"], "roles": case["expected_roles"],
                         "link_words": case["expected_link_words"]},
        })
        good = (same_target and same_ids and entry["synthetic_rematches_kb_and_build"]
                and stored == synth
                and synth["reason"] == case["expected_reason"] and synth["roles"] == case["expected_roles"]
                and synth["link_words"] == case["expected_link_words"]
                and synth["reason_without_link_rule"] is None)
        entry["verdict"] = "EQUIVALENT" if good else "MISMATCH"
        ok = ok and good
        results.append(entry)
    return {"mode": "fixture_equivalence", "write": False, "cases": len(results),
            "equivalent": sum(1 for r in results if r["verdict"] == "EQUIVALENT"), "ok": ok, "results": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--aux-root", default=str(AUX_ROOT))
    parser.add_argument("--fixture-equivalence", action="store_true")
    args = parser.parse_args(argv)
    aux_root = Path(args.aux_root).resolve()
    if args.fixture_equivalence:
        report = fixture_equivalence(aux_root)
        print(json.dumps(report, indent=1, ensure_ascii=False))
        return 0 if report["ok"] else 1
    report = replay(aux_root)
    print(json.dumps(report, indent=1, ensure_ascii=False))
    for five in report["missing_from_replay"]:
        print(f"WARN pinned row no longer refused on retained text: {five}", file=sys.stderr)
    for five in report["not_in_pinned_manifest"]:
        print(f"WARN refused row not in the pinned manifest: {five}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
