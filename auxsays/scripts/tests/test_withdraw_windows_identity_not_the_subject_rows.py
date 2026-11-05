#!/usr/bin/env python3
"""The audited withdrawal of the AUX-067 rows (AUX-072): five-field selection, a three-line edit,
fail closed, idempotent.

`withdraw_windows_identity_not_the_subject_rows.py` withdraws the eight Windows rows the AUX-067
authority (`identity_not_the_subject`) refuses, and keeps row 51. Its contract, pinned here:

  A  the committed manifest names exactly the eight Part A false acceptances and row 51, each by its
     full five-field identity, and the shared authority refuses the eight and keeps row 51
  B  a dry run (the default) plans the eight, keeps row 51 and writes nothing
  C  --write needs --confirm-write; the write changes exactly 24 lines (counted, exclusion_reason,
     evidence_valid_for_current_patch on each of the eight), keeps every row, leaves row 51 and every
     sibling build of the same thread byte-identical, and the evidence-loss guard reads it as an
     audited withdrawal (deleting the same rows, or uncounting them without a reason, is a loss)
  D  a second run changes nothing
  E  every unsafe input refuses the WHOLE run and writes nothing: a drifted, duplicated or missing
     row, an incomplete or duplicated selector, a changed row 51, a moved record identity, a counted
     refusal the manifest does not name, a pinned row the authority no longer refuses, a row withdrawn
     for another reason, an edit whose bytes or fields differ from the pinned after-block
  F  why all five fields: the product/version/URL selector the Acrobat and OBS tools use is ambiguous
     on exactly these rows
  G  the live store and records are untouched by this suite

The tool runs as a BARE script, so B-D run it as a subprocess exactly as an operator would. Offline:
frozen fixtures copied verbatim from the store (tests/fixtures/windows_c1b/withdrawal_store.yml,
withdrawal_targets.json) and temporary trees only.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_withdraw_windows_identity_not_the_subject_rows.py
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import yaml  # noqa: E402

import withdraw_windows_identity_not_the_subject_rows as wd  # noqa: E402
from lib import evidence_loss as el  # noqa: E402
from withdraw_acrobat_wrong_edition_rows import withdraw as product_version_url_withdraw  # noqa: E402

TOOL = SCRIPTS / "withdraw_windows_identity_not_the_subject_rows.py"
MANIFEST = SCRIPTS / "audit" / "windows_identity_not_the_subject_withdrawal.json"
FIX = SCRIPTS / "tests" / "fixtures" / "windows_c1b"
STORE_FIXTURE = FIX / "withdrawal_store.yml"
TARGETS = FIX / "withdrawal_targets.json"
C1B_ROWS = FIX / "c1b_rows.json"
REASON = "identity_not_the_subject"
NL = chr(10)
SEL = ("product_id", "update_version", "target_build", "id", "source_url")

PASS = FAIL = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  -- {detail}" if detail else ""))


def sha(data: bytes | str) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def fixture_text() -> str:
    return STORE_FIXTURE.read_bytes().decode("utf-8")


def targets_fixture() -> list[dict]:
    return json.loads(TARGETS.read_text(encoding="utf-8"))


def make_tree(tmp: Path, store_text: str | None = None, targets: list[dict] | None = None) -> tuple[Path, Path]:
    store = tmp / "consensus_evidence.yml"
    store.write_bytes((store_text if store_text is not None else fixture_text()).encode("utf-8"))
    generated = tmp / "generated"
    generated.mkdir()
    for target in targets if targets is not None else targets_fixture():
        front = yaml.safe_dump(target["front_matter"], sort_keys=False)
        (generated / target["file"]).write_bytes(("---" + NL + front + "---" + NL).encode("utf-8"))
    return store, generated


def run_tool(store: Path, generated: Path, *args: str, manifest: Path = MANIFEST) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, str(TOOL), "--store", str(store), "--generated-dir", str(generated),
                           "--manifest", str(manifest), *args],
                          capture_output=True, text=True, encoding="utf-8", env=env, timeout=600)


def ident(row: dict) -> tuple[str, ...]:
    """The suite's own five-field identity, so a broken selector in the tool fails a check, not the suite."""
    return tuple(str(row.get(key) or "") for key in SEL)


def blocks_by_identity(text: str) -> dict[tuple[str, ...], list[str]]:
    out: dict[tuple[str, ...], list[str]] = {}
    for lo, hi, row in wd.store_blocks(text):
        out.setdefault(ident(row), []).append(text[lo:hi])
    return out


def block_of(text: str, needle: str, build: str) -> str:
    hits = [text[lo:hi] for lo, hi, row in wd.store_blocks(text)
            if needle in str(row.get("source_url")) and str(row.get("target_build")) == build]
    assert len(hits) == 1, (needle, build, len(hits))
    return hits[0]


def refused(tmp_name: str, store_text: str | None = None, targets: list[dict] | None = None,
            manifest: Path = MANIFEST) -> tuple[subprocess.CompletedProcess, bool]:
    """Run --write --confirm-write on a tree and report whether the store came back byte-identical."""
    with tempfile.TemporaryDirectory(prefix=tmp_name) as tmp:
        store, generated = make_tree(Path(tmp), store_text, targets)
        before = store.read_bytes()
        proc = run_tool(store, generated, "--write", "--confirm-write", manifest=manifest)
        return proc, store.read_bytes() == before


def in_process_plan(store_text: str, entries: list[dict] | None = None) -> tuple[str, dict | None]:
    """plan() in-process on a temp tree: ('', result) or (refusal message, None)."""
    with tempfile.TemporaryDirectory(prefix="wd-plan-") as tmp:
        _store, generated = make_tree(Path(tmp), store_text)
        targets = wd.windows_targets(generated)
    try:
        return "", wd.plan(store_text, entries if entries is not None else wd.load_manifest(MANIFEST), targets)
    except wd.Refusal as exc:
        return str(exc), None


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Audited withdrawal of the AUX-067 Windows rows (AUX-072)")
    print("=" * 78)
    live_store = ROOT / "_data" / "consensus_evidence.yml"
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live_files = [live_store] + [ROOT.parent / e["record_file"] for e in manifest["entries"]]
    live_before = {str(p): sha(p.read_bytes()) for p in live_files if p.exists()}
    text = fixture_text()

    print("A  the pinned manifest")
    withdraw = [e for e in manifest["entries"] if e["role"] == "withdraw"]
    retain = [e for e in manifest["entries"] if e["role"] == "retain"]
    check("A1 the manifest withdraws exactly eight rows and keeps exactly one",
          len(withdraw) == 8 and len(retain) == 1 and len(manifest["entries"]) == 9,
          f"{len(withdraw)} withdraw, {len(retain)} retain")
    check("A2 every entry carries all five identity fields, target_build included",
          all(all(str(e.get(k) or "") for k in SEL) for e in manifest["entries"]))
    c1b = json.loads(C1B_ROWS.read_text(encoding="utf-8"))
    part_a = {(r["id"], r["update_version"], r["target_build"]) for r in c1b if r["target_build"] != "26200.8894"}
    part_a_kept = {(r["id"], r["update_version"], r["target_build"]) for r in c1b if r["target_build"] == "26200.8894"}
    check("A3 the eight are exactly AUX-067's eight false acceptances, and the kept row is its row 51",
          {(e["id"], e["update_version"], e["target_build"]) for e in withdraw} == part_a and len(part_a) == 8
          and {(e["id"], e["update_version"], e["target_build"]) for e in retain} == part_a_kept)
    per_record = collections.Counter((e["update_version"], e["target_build"]) for e in withdraw)
    check("A4 two rows each on 25H2 9168 and 9457, one each on 9278, 8328, 8246 and 26H2 9711",
          per_record == collections.Counter({("25H2", "26200.9168"): 2, ("25H2", "26200.9457"): 2,
                                             ("25H2", "26200.9278"): 1, ("25H2", "26200.8328"): 1,
                                             ("25H2", "26200.8246"): 1, ("26H2", "26300.9711"): 1}),
          str(per_record))
    fronts = {(t["front_matter"]["update_version"], t["front_matter"]["target_build"]): t["front_matter"]
              for t in targets_fixture()}
    rows = {ident(row): row for _lo, _hi, row in wd.store_blocks(text)}
    verdicts = {e["role"] + " " + e["id"][-24:]: wd._refused(fronts[(e["update_version"], e["target_build"])],
                                                             rows[tuple(e[k] for k in SEL)])
                for e in manifest["entries"]}
    check("A5 the shared authority refuses the eight and keeps row 51 (the verdict is derived, not listed)",
          all(v for k, v in verdicts.items() if k.startswith("withdraw")) and
          not any(v for k, v in verdicts.items() if k.startswith("retain")), str(verdicts))
    check("A6 the selector is the five fields, in order", wd.SELECTOR == SEL, str(wd.SELECTOR))

    print("B  dry run, as the bare script")
    with tempfile.TemporaryDirectory(prefix="wd-dry-") as tmp:
        store, generated = make_tree(Path(tmp))
        before = store.read_bytes()
        proc = run_tool(store, generated)
        out = proc.stdout
        check("B1 a dry run exits 0", proc.returncode == 0, proc.stdout[-400:] + proc.stderr[-400:])
        check("B2 a dry run writes nothing", store.read_bytes() == before)
        check("B3 it plans the eight and keeps row 51",
              out.count("[withdraw ") == 8 and out.count("[kept ") == 1, out[-600:])
        check("B4 it reports the counted population each record would lose",
              "Windows counted population: 12 -> 4" in out and "25H2 26200.9168: 2 -> 0" in out
              and "25H2 26200.9457: 3 -> 1" in out and "26H2 26300.9711: 2 -> 1" in out
              and "25H2 26200.8894" not in out.split("Windows counted population")[1], out[-600:])
        check("B5 it says how to apply", "pass --write --confirm-write to apply" in out)

    print("C  the write")
    with tempfile.TemporaryDirectory(prefix="wd-write-") as tmp:
        store, generated = make_tree(Path(tmp))
        before_bytes = store.read_bytes()
        p1 = run_tool(store, generated, "--write")
        check("C1 --write without --confirm-write is a usage error and writes nothing",
              p1.returncode == 2 and store.read_bytes() == before_bytes, f"rc={p1.returncode}")
        p2 = run_tool(store, generated, "--confirm-write")
        check("C2 --confirm-write without --write is a usage error and writes nothing",
              p2.returncode == 2 and store.read_bytes() == before_bytes, f"rc={p2.returncode}")
        audit_path = Path(tmp) / "audit.json"
        p3 = run_tool(store, generated, "--write", "--confirm-write", "--audit", str(audit_path),
                      "--parent-commit", "f" * 40)
        check("C3 --write --confirm-write withdraws and says so",
              p3.returncode == 0 and "WROTE" in p3.stdout and "rows withdrawn by this run: 8" in p3.stdout,
              p3.stdout[-500:] + p3.stderr[-500:])
        before_text, after_text = before_bytes.decode("utf-8"), store.read_bytes().decode("utf-8")
        a_lines, b_lines = before_text.split(NL), after_text.split(NL)
        changed = [(a, b) for a, b in zip(a_lines, b_lines) if a != b]
        expected = collections.Counter({("  counted: true", "  counted: false"): 8,
                                        ("  exclusion_reason: null", "  exclusion_reason: " + REASON): 8,
                                        ("  evidence_valid_for_current_patch: true",
                                         "  evidence_valid_for_current_patch: false"): 8})
        check("C4 exactly 24 lines change: three per row, and only the three expected transitions",
              len(a_lines) == len(b_lines) and collections.Counter(changed) == expected,
              f"{len(changed)} changed: {collections.Counter(changed)}")
        after_blocks = blocks_by_identity(after_text)
        before_blocks = blocks_by_identity(before_text)
        check("C5 every withdrawn block now hashes to its pinned after-value",
              all([sha(b) for b in after_blocks.get(tuple(e[k] for k in SEL), [])] == [e["block_sha256_after"]]
                  for e in withdraw))
        rows_b = [r for _lo, _hi, r in wd.store_blocks(before_text)]
        rows_a = [r for _lo, _hi, r in wd.store_blocks(after_text)]
        pinned = {tuple(e[k] for k in SEL) for e in withdraw}
        moved = [(o, n) for o, n in zip(rows_b, rows_a) if ident(o) in pinned]
        check("C6 the eight parse as withdrawn, and every other field of them is unchanged",
              len(moved) == 8 and all(n == dict(o, counted=False, exclusion_reason=REASON,
                                                evidence_valid_for_current_patch=False) for o, n in moved))
        r51 = tuple(retain[0][k] for k in SEL)
        check("C7 row 51 is byte-identical and still counted",
              after_blocks[r51] == before_blocks[r51]
              and {ident(r): r for r in rows_a}[r51].get("counted") is True
              and sha(after_blocks[r51][0]) == retain[0]["block_sha256_before"])
        siblings = [k for k in before_blocks if k not in pinned and k != r51
                    and any(f"/questions/{t}/" in k[4] for t in ("5989625", "5957946"))]
        check("C8 every sibling build of the same threads is byte-identical (six rows)",
              len(siblings) == 6 and all(after_blocks.get(k) == before_blocks[k] for k in siblings),
              f"{len(siblings)} siblings")
        others = [k for k in before_blocks if k not in pinned]
        check("C9 no row is added or removed, and every non-target row is byte-identical",
              len(rows_a) == len(rows_b) == 19 and all(after_blocks.get(k) == before_blocks[k] for k in others))
        check("C10 the evidence-loss guard reads it as an audited withdrawal, not a loss",
              el.losses_between(before_text, after_text) == [])
        deleted = before_text
        for e in withdraw:
            deleted = deleted.replace(before_blocks[tuple(e[k] for k in SEL)][0], "", 1)
        unreasoned = after_text.replace(NL + "  exclusion_reason: " + REASON + NL, NL + "  exclusion_reason: null" + NL)
        losses_del = el.losses_between(before_text, deleted)
        losses_unr = el.losses_between(before_text, unreasoned)
        check("C11 control: the same rows deleted, or uncounted without a reason, ARE evidence loss",
              len(losses_del) == 8 and all(x.code == el.REMOVED for x in losses_del)
              and len(losses_unr) == 8 and all(x.code == el.UNAUDITED for x in losses_unr),
              f"{[x.code for x in losses_del]} / {[x.code for x in losses_unr]}")
        audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
        check("C12 the audit records the run: hashes, parent, the eight, and each record's delta",
              audit.get("written") is True and audit.get("withdrawn_now") == 8
              and audit.get("store_sha256_before") == sha(before_bytes)
              and audit.get("store_sha256_after") == sha(after_text) and audit.get("parent_commit") == "f" * 40
              and audit.get("windows_counted_population") == [12, 4]
              and len(audit.get("per_patch") or []) == 6
              and sorted(i["action"] for i in audit.get("entries") or []) == ["kept"] + ["withdraw"] * 8,
              json.dumps({k: audit.get(k) for k in ("written", "withdrawn_now", "windows_counted_population")}))

        print("D  idempotence")
        p4 = run_tool(store, generated, "--write", "--confirm-write")
        check("D1 a second run exits 0, writes nothing and says so",
              p4.returncode == 0 and "nothing to write" in p4.stdout and store.read_bytes().decode("utf-8") == after_text,
              p4.stdout[-400:] + p4.stderr[-300:])
        check("D2 it reports the eight as already withdrawn and still keeps row 51",
              p4.stdout.count("[already_withdrawn") == 8 and p4.stdout.count("[kept ") == 1)
        check("D3 the population it reports no longer moves", "Windows counted population: 4 -> 4" in p4.stdout)

    print("E  fail closed: each unsafe input refuses the whole run and writes nothing")
    t5885634 = block_of(text, "/5885634/", "26200.8328")
    drifted = text.replace(t5885634, t5885634.replace("thinkpad x1", "ThinkPad x1"), 1)
    assert drifted != text
    proc, same = refused("wd-e1-", drifted)
    check("E1 one drifted pinned row refuses the run, naming the drift",
          proc.returncode == 1 and "block changed since the manifest was pinned" in proc.stdout, proc.stdout[-300:])
    check("E1b all or nothing: the seven intact rows are not withdrawn either", same)

    t6055182 = block_of(text, "/6055182/", "26300.9711")
    proc, same = refused("wd-e2-", text + t6055182)
    check("E2 two blocks with one five-field identity refuse the run",
          proc.returncode == 1 and "2 blocks match the five-field identity" in proc.stdout and same, proc.stdout[-300:])

    proc, same = refused("wd-e3-", text.replace(block_of(text, "/5897669/", "26200.8246"), "", 1))
    check("E3 a pinned row that is missing refuses the run",
          proc.returncode == 1 and "0 blocks match the five-field identity" in proc.stdout and same, proc.stdout[-300:])

    with tempfile.TemporaryDirectory(prefix="wd-e4-") as tmp:
        bad = json.loads(MANIFEST.read_text(encoding="utf-8"))
        bad["entries"][0]["target_build"] = ""
        bad_path = Path(tmp) / "manifest.json"
        bad_path.write_text(json.dumps(bad), encoding="utf-8")
        proc, same = refused("wd-e4b-", manifest=bad_path)
        check("E4 a selector without target_build is refused (never by id or URL alone)",
              proc.returncode == 1 and "lacks part of the five-field identity" in proc.stdout and same, proc.stdout[-300:])
        dup = json.loads(MANIFEST.read_text(encoding="utf-8"))
        dup["entries"].append(dict(dup["entries"][0]))
        dup_path = Path(tmp) / "dup.json"
        dup_path.write_text(json.dumps(dup), encoding="utf-8")
        proc, same = refused("wd-e4c-", manifest=dup_path)
        check("E5 an identity listed twice in the manifest is refused",
              proc.returncode == 1 and "listed twice" in proc.stdout and same, proc.stdout[-300:])

    r51_block = block_of(text, "/5957946/", "26200.8894")
    changed51 = text.replace(r51_block, r51_block.replace("  sentiment: negative", "  sentiment: neutral"), 1)
    assert changed51 != text
    proc, same = refused("wd-e6-", changed51)
    check("E6 a changed row 51 refuses the run",
          proc.returncode == 1 and "retained row changed" in proc.stdout and same, proc.stdout[-300:])

    moved = targets_fixture()
    for t in moved:
        if t["front_matter"]["target_build"] == "26300.9711":
            t["front_matter"]["target_kb"] = "KB5999999"
    proc, same = refused("wd-e7-", None, moved)
    check("E7 a record whose target identity moved refuses the run",
          proc.returncode == 1 and "record target identity moved" in proc.stdout and same, proc.stdout[-300:])

    # The same refused shape under a thread id the manifest does not pin: a new candidate, not a widening.
    extra = t5885634.replace("5885634", "5999998")
    assert extra != t5885634
    proc, same = refused("wd-e8-", text + extra)
    check("E8 a counted row the authority refuses but the manifest does not name refuses the run",
          proc.returncode == 1 and "the manifest does not name" in proc.stdout and same, proc.stdout[-300:])

    original = wd.mw.identity_not_the_subject
    try:
        wd.mw.identity_not_the_subject = lambda *_a, **_k: False
        message, _ = in_process_plan(text)
    finally:
        wd.mw.identity_not_the_subject = original
    check("E9 a pinned row the authority no longer refuses is not withdrawn", "no longer refuses" in message, message[:300])
    try:
        wd.mw.identity_not_the_subject = lambda *_a, **_k: True
        message, _ = in_process_plan(text)
    finally:
        wd.mw.identity_not_the_subject = original
    check("E10 a retained row the authority would refuse refuses the run",
          "retained row is not counted or the authority refuses it" in message, message[:300])

    other = text.replace(t5885634, t5885634.replace("  counted: true" + NL + "  exclusion_reason: null",
                                                    "  counted: false" + NL + "  exclusion_reason: cross_patch_duplicate"), 1)
    assert other != text
    proc, same = refused("wd-e11-", other)
    check("E11 a row already withdrawn for ANOTHER reason is never rewritten",
          proc.returncode == 1 and "block changed since the manifest was pinned" in proc.stdout and same, proc.stdout[-300:])

    shapeless = t5885634.replace("  evidence_valid_for_current_patch: true" + NL, "", 1)
    try:
        wd.withdraw_block(shapeless)
        shape_refused = False
    except wd.Refusal:
        shape_refused = True
    check("E12 the three-line edit refuses a block of unexpected shape", shape_refused)

    edit = wd.EDIT
    try:
        wd.EDIT = tuple((old, new.replace(": " + REASON, ": '" + REASON + "'")) for old, new in edit)
        message, _ = in_process_plan(text)
    finally:
        wd.EDIT = edit
    check("E13 an edit whose BYTES differ from the pinned after-block is refused even if it parses the same",
          "does not produce the pinned block" in message, message[:300])

    stale_old = NL + "  stale_due_to_patch_rollover: false" + NL
    stale_new = NL + "  stale_due_to_patch_rollover: true" + NL
    widened = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for e in widened["entries"]:
        if e["role"] == "withdraw":
            block = blocks_by_identity(text)[tuple(e[k] for k in SEL)][0]
            e["block_sha256_after"] = sha(wd.withdraw_block(block).replace(stale_old, stale_new, 1))
    try:
        wd.EDIT = edit + ((stale_old, stale_new),)
        message, _ = in_process_plan(text, wd.manifest_entries(widened))
    finally:
        wd.EDIT = edit
    check("E14 a pinned after-hash cannot authorise a fourth field: the edit is proved field by field",
          "changed more than decided" in message, message[:300])

    print("F  why the selector needs all five fields")
    r9278 = rows[next(tuple(e[k] for k in SEL) for e in withdraw if "/5989625/" in e["source_url"])]
    try:
        product_version_url_withdraw(text, r9278, REASON)
        ambiguous = False
    except SystemExit as exc:
        ambiguous = "2 blocks match" in str(exc)
    check("F1 the product/version/URL selector cannot tell 25H2 9278's row from its 8973 sibling", ambiguous)
    same_url = [k for k in rows if k[:2] == r51[:2] and k[4] == r51[4]]
    check("F2 four 25H2 rows share row 51's URL; the five-field identity names exactly one",
          len(same_url) == 4 and len(blocks_by_identity(text)[r51]) == 1, str(len(same_url)))

    print("G  this suite changed nothing real")
    live_after = {str(p): sha(p.read_bytes()) for p in live_files if p.exists()}
    check("G1 the live store and the pinned records are byte-identical after the suite",
          live_after == live_before and len(live_before) == 8, f"{len(live_before)} files")

    print()
    for label in FAILURES:
        print(f"  failed: {label}")
    print("=" * 78)
    # The governed count line comes LAST: the runner and the manifest read it.
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
