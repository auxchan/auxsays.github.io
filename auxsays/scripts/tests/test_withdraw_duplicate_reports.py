#!/usr/bin/env python3
"""The audited withdrawal of reports one person posted twice, Windows, OBS and DaVinci (AUX-098).

`withdraw_live_citation_rows.py` (the AUX-088 mechanism) withdraws, with a third pinned manifest
(audit/live_citation_withdrawal_v3.json), the fourteen stored rows that two independent adjudications BOTH
labelled `same_report_duplicate` of the SAME kept row, and keeps the eight originals. Its contract, pinned here:

  A  the committed manifest names exactly those fourteen rows by their full five-field identity, each with two
     labels from two named reviewers that name the kept row the entry names; the scope is Windows, OBS and
     DaVinci; a same-time capture is flagged exactly where the two captures are equal; the pairs the reviews did
     not agree on (the 26200.7922 pair, the Acrobat Reader pair, the cross-identity 9550 row) are held out; it
     shares no row with AUX-072's, AUX-079's, AUX-088's or AUX-090's manifest
  B  a dry run (the default) plans the fourteen, keeps the eight and writes nothing
  C  --write --confirm-write changes exactly 36 lines (three per Windows row, two per OBS and DaVinci row), keeps
     every row, leaves the kept rows, the held-out rows and every other row byte-identical, starts no row
     counting, and the evidence-loss guard reads it as an audited withdrawal
  D  a second run changes nothing
  E  each new acceptance clause refuses the WHOLE run and writes nothing: two labels that name different kept
     rows (the 26200.7922 pair as recorded), a blind label naming another row, one duplicate label, one reviewer
     twice or unnamed, a missing reason; a same-time capture without the flag, the flag without a same-time
     capture, the kept row the later post, two source families, a family with no post number, two INCORRECT
     labels, no capture time; a DaVinci row outside a DaVinci scope, an undeclared scope, a DaVinci build, a
     DaVinci validity line, a drifted DaVinci pin, a missing DaVinci record; a kept row on another patch
  F  --regenerate runs the reconcile and one scoped promotion per product of the DECLARED scope, never unscoped;
     AUX-088's writer list is unchanged; the source post numbers are derived only for the two families
  G  the committed store holds the fourteen as withdrawn and the eight kept rows counted, the held-out rows still
     count, and this suite changed nothing real

The tool runs as a BARE script, so B-D run it as a subprocess exactly as an operator would. Offline: frozen
fixtures (tests/fixtures/live_citation/duplicate_store.yml holds the 29 stored rows involved, serialised as the
store serialises them, with the free-text fields replaced by synthetic marker text; duplicate_targets.json holds
the eleven records' identity front matter). Because the text differs from the store, the suite re-pins the
committed manifest's block hashes on the fixture with its OWN line edit, never the tool's.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_withdraw_duplicate_reports.py
"""
from __future__ import annotations

import collections
import copy
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

import withdraw_live_citation_rows as wd  # noqa: E402
import withdraw_windows_identity_not_the_subject_rows as aux072  # noqa: E402
from lib import evidence_loss as el  # noqa: E402

TOOL = SCRIPTS / "withdraw_live_citation_rows.py"
MANIFEST = SCRIPTS / "audit" / "live_citation_withdrawal_v3.json"
FIX = SCRIPTS / "tests" / "fixtures" / "live_citation"
STORE_FIXTURE = FIX / "duplicate_store.yml"
TARGETS = FIX / "duplicate_targets.json"
NL = chr(10)
SEL = ("product_id", "update_version", "target_build", "id", "source_url")
WIN, OBS, DAV = "microsoft-windows-11", "obs-studio", "blackmagic-davinci"
DUP, LABEL = "duplicate_existing_evidence", "same_report_duplicate"

# The fourteen rows both adjudications labelled a duplicate of the SAME kept row, written out here so the manifest
# cannot redefine them: (product, version, build, report number) -> the kept report's number on the same page.
WITHDRAW = {
    (WIN, "25H2", "26200.7623", "5769728"): "5708079",
    (DAV, "20.2", "", "1rvhlmx"): "1rnhcy6",
    (WIN, "25H2", "26200.8894", "5956430"): "5956328",
    (WIN, "25H2", "26200.8973", "5982769"): "5978256", (WIN, "25H2", "26200.8973", "5983062"): "5978256",
    (WIN, "25H2", "26200.8973", "4547615"): "5978256", (WIN, "25H2", "26200.8973", "4550372"): "5978256",
    (WIN, "25H2", "26200.8973", "4551560"): "5978256", (WIN, "25H2", "26200.8973", "4552324"): "5978256",
    (OBS, "31.1.2", "", "196230"): "13711",
    (OBS, "32.2.0", "", "13689"): "13685", (OBS, "32.2.0", "", "13690"): "13685",
    (OBS, "32.2.1", "", "195984"): "13729", (OBS, "32.2.1", "", "196230"): "13711",
}
# Captured in the same collection run as their kept row: the kept row is the earlier POST.
TIES = {"5769728", "1rvhlmx", "5956430", "5982769", "5983062"}
# Held out: the reviews keep opposite rows (7922), only one labels a duplicate (Reader), no second label for the
# right reason and the kept row is on another patch (26300.9550). They stay counted.
HELD = {(WIN, "25H2", "26200.7922", "5791250"), (WIN, "25H2", "26200.7922", "5794016"),
        (WIN, "26H2", "26300.9550", "6019205"), (WIN, "25H2", "26200.9550", "6014283")}
PER_PAGE = {(WIN, "25H2", "26200.7623"): 1, (DAV, "20.2", ""): 1, (WIN, "25H2", "26200.8894"): 1,
            (WIN, "25H2", "26200.8973"): 6, (OBS, "31.1.2", ""): 1, (OBS, "32.2.0", ""): 2, (OBS, "32.2.1", ""): 2}
RECORDS = ("2026-01-13-windows-11-25h2-26200-7623.md", "2025-09-10-davinci-resolve-20-2.md",
           "2026-07-18-windows-11-25h2-26200-8894.md", "2026-07-28-windows-11-25h2-26200-8973.md",
           "2025-07-28-obs-studio-31-1-2.md", "2026-07-21-obs-studio-32-2-0.md", "2026-07-24-obs-studio-32-2-1.md")
AUX088_WRITERS = (
    ("build_consensus_from_evidence.py", "--product-id", WIN, "--product-id", OBS, "--reconcile-only"),
    ("apply_consensus_to_records.py", "--product-id", WIN, "--write-all", "--confirm-write"),
    ("apply_consensus_to_records.py", "--product-id", OBS, "--write-all", "--confirm-write"),
)

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


def report_id(url: str) -> str:
    """The question, post, issue or thread number a URL names."""
    tail = url.rstrip("/")
    if "/answers/questions/" in tail:
        return tail.split("/answers/questions/", 1)[1].split("/", 1)[0]
    if "/comments/" in tail:
        return tail.split("/comments/", 1)[1].split("/", 1)[0]
    last = tail.rsplit("/", 1)[-1]
    return last.rsplit(".", 1)[-1] if "." in last else last


def short(row: dict) -> tuple[str, str, str, str]:
    return (str(row.get("product_id") or ""), str(row.get("update_version") or ""),
            str(row.get("target_build") or ""), report_id(str(row.get("source_url") or "")))


def ident(row: dict) -> tuple[str, ...]:
    """The suite's own five-field identity, so a broken selector in the tool fails a check, not the suite."""
    return tuple(str(row.get(key) or "") for key in SEL)


def own_edit(block: str, product: str) -> str:
    """The suite's own withdrawal edit, independent of the tool's: three lines for Windows, two otherwise."""
    pairs = [("  counted: true", "  counted: false"), ("  exclusion_reason: null", "  exclusion_reason: " + DUP)]
    if product == WIN:
        pairs.append(("  evidence_valid_for_current_patch: true", "  evidence_valid_for_current_patch: false"))
    for old, new in pairs:
        assert block.count(NL + old + NL) == 1, (old, block[:120])
        block = block.replace(NL + old + NL, NL + new + NL, 1)
    return block


def fixture_text() -> str:
    return STORE_FIXTURE.read_bytes().decode("utf-8")


def targets_fixture() -> list[dict]:
    return json.loads(TARGETS.read_text(encoding="utf-8"))


def manifest_doc() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def blocks_by_identity(text: str) -> dict[tuple[str, ...], list[str]]:
    out: dict[tuple[str, ...], list[str]] = {}
    for lo, hi, row in aux072.store_blocks(text):
        out.setdefault(ident(row), []).append(text[lo:hi])
    return out


def repin(doc: dict, text: str) -> dict:
    """Re-pin a manifest's block hashes on `text` with the suite's own edit."""
    blocks = blocks_by_identity(text)
    for entry in doc["entries"]:
        hits = blocks.get(ident(entry), [])
        if len(hits) != 1:
            continue
        entry["block_sha256_before"] = sha(hits[0])
        if entry["role"] == "withdraw":
            entry["block_sha256_after"] = sha(own_edit(hits[0], entry["product_id"]))
    return doc


def fixture_manifest(text: str | None = None) -> dict:
    return repin(manifest_doc(), text if text is not None else fixture_text())


def make_tree(tmp: Path, store_text: str | None = None, targets: list[dict] | None = None,
              manifest: dict | None = None) -> tuple[Path, Path, Path]:
    store = tmp / "consensus_evidence.yml"
    store.write_bytes((store_text if store_text is not None else fixture_text()).encode("utf-8"))
    generated = tmp / "generated"
    generated.mkdir()
    for target in targets if targets is not None else targets_fixture():
        front = yaml.safe_dump(target["front_matter"], sort_keys=False)
        (generated / target["file"]).write_bytes(("---" + NL + front + "---" + NL).encode("utf-8"))
    man = tmp / "manifest.json"
    man.write_text(json.dumps(manifest if manifest is not None else fixture_manifest()), encoding="utf-8")
    return store, generated, man


def run_tool(store: Path, generated: Path, manifest: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, str(TOOL), "--store", str(store), "--generated-dir", str(generated),
                           "--manifest", str(manifest), "--baseline", str(store.parent / "no-baseline.json"), *args],
                          capture_output=True, text=True, encoding="utf-8", env=env, timeout=600)


def refused(prefix: str, store_text: str | None = None, targets: list[dict] | None = None,
            manifest: dict | None = None) -> tuple[subprocess.CompletedProcess, bool]:
    """Run --write --confirm-write on a tree and report whether the store came back byte-identical."""
    with tempfile.TemporaryDirectory(prefix=prefix) as tmp:
        store, generated, man = make_tree(Path(tmp), store_text, targets, manifest)
        before = store.read_bytes()
        proc = run_tool(store, generated, man, "--write", "--confirm-write")
        return proc, store.read_bytes() == before


def plan_of(store_text: str, doc: dict) -> str:
    """plan() in-process on a temp tree: '' when it plans, else the refusal message."""
    with tempfile.TemporaryDirectory(prefix="aux098-plan-") as tmp:
        _store, generated, _man = make_tree(Path(tmp), store_text)
        records = wd.patch_records(generated)
    try:
        wd.plan(store_text, wd.manifest_entries(doc), records, {}, wd.manifest_scope(doc))
        return ""
    except wd.Refusal as exc:
        return str(exc)


def entry_of(doc: dict, product: str, version: str, rid: str, role: str = "withdraw") -> dict:
    hits = [e for e in doc["entries"] if e["role"] == role and short(e)[0] == product and short(e)[1] == version
            and short(e)[3] == rid]
    assert len(hits) == 1, (product, version, rid, role)
    return hits[0]


def row_of(text: str, product: str, version: str, rid: str) -> tuple[str, dict]:
    hits = [(text[lo:hi], row) for lo, hi, row in aux072.store_blocks(text)
            if short(row)[0] == product and short(row)[1] == version and short(row)[3] == rid]
    assert len(hits) == 1, (product, version, rid, len(hits))
    return hits[0]


def labels(entry: dict) -> tuple[dict, dict]:
    adj = entry["adjudication"]
    return adj["first_audit"], adj["second_blind"]


def single(doc: dict, keep: dict, withdraw: dict) -> dict:
    """A manifest of one kept row and one withdrawal, otherwise the committed manifest's header."""
    return dict(doc, entries=[keep, withdraw])


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Audited withdrawal of reports posted twice (AUX-098)")
    print("=" * 78)
    live_store = ROOT / "_data" / "consensus_evidence.yml"
    live_files = [live_store] + [ROOT / "updates" / "generated" / name for name in RECORDS]
    live_before = {str(p): sha(p.read_bytes()) for p in live_files if p.exists()}
    manifest = manifest_doc()
    text = fixture_text()
    withdraw = [e for e in manifest["entries"] if e["role"] == "withdraw"]
    retain = [e for e in manifest["entries"] if e["role"] == "retain"]

    print("A  the pinned manifest")
    check("A1 fourteen rows are withdrawn (eight Windows, five OBS, one DaVinci) and eight originals are kept, "
          "under ledger AUX-098, version 3",
          len(withdraw) == 14 and len(retain) == 8 and manifest.get("ledger") == "AUX-098"
          and manifest.get("version") == 3
          and collections.Counter(e["product_id"] for e in withdraw) == {WIN: 8, OBS: 5, DAV: 1},
          f"{len(withdraw)} withdraw, {len(retain)} kept")
    kept_by_page = {short(e)[:3] + (short(e)[3],) for e in retain}
    check("A2 the withdrawn rows are exactly the fourteen, each naming the original the reviews agreed on, "
          "and the kept rows are exactly those originals",
          {short(e) for e in withdraw} == set(WITHDRAW)
          and all(short(e["duplicate_of"]) == short(e)[:3] + (WITHDRAW[short(e)],) for e in withdraw)
          and kept_by_page == {k[:3] + (v,) for k, v in WITHDRAW.items()},
          str(sorted({short(e) for e in withdraw} ^ set(WITHDRAW))))
    check("A3 five-field identity: every field set, target_build exactly for Windows, no identity repeated; the "
          "scope is Windows, OBS and DaVinci",
          all(all(str(e.get(k) or "") for k in SEL if k != "target_build") for e in manifest["entries"])
          and all(bool(e["target_build"]) == (e["product_id"] == WIN) for e in manifest["entries"])
          and len({ident(e) for e in manifest["entries"]}) == 22 and tuple(manifest["selector"]) == SEL
          and tuple(manifest["products"]) == wd.EXTENDED_PRODUCTS == (WIN, OBS, DAV))

    def agreed(e: dict) -> bool:
        first, blind = labels(e)
        return (first.get("label") == blind.get("label") == LABEL
                and first.get("duplicate_of_id") == blind.get("duplicate_of_id") == e["duplicate_of"]["id"]
                and str(first.get("by") or "").strip() and str(blind.get("by") or "").strip()
                and first["by"] != blind["by"] and str(first.get("reason") or "").strip()
                and str(blind.get("reason_class") or "").strip() and str(e.get("basis") or "").strip())
    check("A4 every row: reason duplicate_existing_evidence, two same_report_duplicate labels from two named "
          "reviewers, both naming its kept row, with reasons and a basis",
          all(e["exclusion_reason"] == DUP and agreed(e) for e in withdraw),
          str([e["id"][-30:] for e in withdraw if not agreed(e)]))
    check("A5 a same-time capture is flagged on exactly the five rows captured in the same run as their kept row",
          {short(e)[3] for e in withdraw if e.get("capture_tie") is True} == TIES
          and all((e["captured_at"] == e["kept_captured_at"]) == (e.get("capture_tie") is True) for e in withdraw)
          and all(e.get("capture_tie") in (True, False) for e in withdraw))
    per_page = collections.Counter(short(e)[:3] for e in withdraw)
    check("A6 per page: 7623 1, DaVinci 20.2 1, 8894 1, 8973 6, OBS 31.1.2 1, 32.2.0 2, 32.2.1 2",
          per_page == PER_PAGE, str(per_page))
    held = {short(r) for h in manifest.get("held_out", []) for r in h["rows"] if r["product_id"] != "adobe-acrobat-reader"}
    check("A7 the pairs the reviews did not agree on are held out with a reason, and none of their rows is an entry",
          held == HELD and len(manifest["held_out"]) == 3
          and all(str(h.get("why") or "").strip() for h in manifest["held_out"])
          and not ({short(e) for e in manifest["entries"]} & HELD))
    prior = set()
    for name in ("windows_identity_not_the_subject_withdrawal.json", "windows_confirmed_and_duplicate_withdrawal.json",
                 "live_citation_withdrawal.json", "live_citation_withdrawal_v2.json"):
        prior |= {ident(e) for e in json.loads((SCRIPTS / "audit" / name).read_text(encoding="utf-8"))["entries"]}
    check("A8 no row is shared with AUX-072's, AUX-079's, AUX-088's or AUX-090's manifest",
          not (prior & {ident(e) for e in manifest["entries"]}))
    check("A9 each row pins its record, and each Windows row its record's target KB and OS build",
          all(str(e.get("record_file") or "").endswith(".md") for e in manifest["entries"])
          and all(e.get("target_kb") and e.get("target_os_build") == e["target_build"]
                  for e in manifest["entries"] if e["product_id"] == WIN))

    print("B  dry run, as the bare script")
    with tempfile.TemporaryDirectory(prefix="aux098-dry-") as tmp:
        store, generated, man = make_tree(Path(tmp))
        before = store.read_bytes()
        proc = run_tool(store, generated, man)
        out = proc.stdout
        check("B1 a dry run exits 0 and writes nothing", proc.returncode == 0 and store.read_bytes() == before,
              proc.stdout[-400:] + proc.stderr[-400:])
        check("B2 it plans the fourteen and keeps the eight", out.count("[withdraw ") == 14 and out.count("[kept ") == 8,
              out[-600:])
        check("B3 it reports each product's counted population and each page's loss, DaVinci included",
              "blackmagic-davinci counted population: 3 -> 2" in out and "blackmagic-davinci 20.2: 3 -> 2" in out
              and "microsoft-windows-11 25H2 26200.8973: 8 -> 2" in out and "obs-studio 32.2.1: 4 -> 2" in out
              and "microsoft-windows-11 25H2 26200.7623: 2 -> 1" in out, out[-900:])

    print("C  the write")
    with tempfile.TemporaryDirectory(prefix="aux098-write-") as tmp:
        store, generated, man = make_tree(Path(tmp))
        before_bytes = store.read_bytes()
        audit_path = Path(tmp) / "audit.json"
        p3 = run_tool(store, generated, man, "--write", "--confirm-write", "--audit", str(audit_path),
                      "--parent-commit", "e" * 40)
        check("C1 --write --confirm-write withdraws the fourteen and says so",
              p3.returncode == 0 and "WROTE" in p3.stdout and "rows withdrawn by this run: 14" in p3.stdout,
              p3.stdout[-500:] + p3.stderr[-500:])
        before_text, after_text = before_bytes.decode("utf-8"), store.read_bytes().decode("utf-8")
        a_lines, b_lines = before_text.split(NL), after_text.split(NL)
        changed = [(a, b) for a, b in zip(a_lines, b_lines) if a != b]
        expected = collections.Counter({("  counted: true", "  counted: false"): 14,
                                        ("  exclusion_reason: null", "  exclusion_reason: " + DUP): 14,
                                        ("  evidence_valid_for_current_patch: true",
                                         "  evidence_valid_for_current_patch: false"): 8})
        check("C2 exactly 36 lines change: three per Windows row, two per OBS and DaVinci row",
              len(a_lines) == len(b_lines) and collections.Counter(changed) == expected and len(changed) == 36,
              f"{len(changed)} changed: {collections.Counter(changed)}")
        after_blocks, before_blocks = blocks_by_identity(after_text), blocks_by_identity(before_text)
        fman = json.loads(man.read_text(encoding="utf-8"))
        check("C3 every withdrawn block now hashes to its pinned after-value",
              all([sha(b) for b in after_blocks.get(ident(e), [])] == [e["block_sha256_after"]]
                  for e in fman["entries"] if e["role"] == "withdraw"))
        rows_b = [r for _lo, _hi, r in aux072.store_blocks(before_text)]
        rows_a = [r for _lo, _hi, r in aux072.store_blocks(after_text)]
        out_ids = {ident(e) for e in withdraw}
        moved = [(o, n) for o, n in zip(rows_b, rows_a) if ident(o) in out_ids]

        def expected_row(o: dict) -> dict:
            extra = {"evidence_valid_for_current_patch": False} if o["product_id"] == WIN else {}
            return dict(o, counted=False, exclusion_reason=DUP, **extra)
        check("C4 the fourteen parse as withdrawn, every other field unchanged, no field added to an OBS or "
              "DaVinci row",
              len(moved) == 14 and all(n == expected_row(o) for o, n in moved)
              and all("evidence_valid_for_current_patch" not in n for o, n in moved if o["product_id"] != WIN))
        others = [k for k in before_blocks if k not in out_ids]
        held_rows = [k for k in others if short(dict(zip(SEL, k))) in HELD]
        check("C5 no row is added or removed; the eight kept, the four held-out and every other row are "
              "byte-identical and still in their counted state",
              len(rows_a) == len(rows_b) == 29 and len(others) == 15 and len(held_rows) == 4
              and all(after_blocks.get(k) == before_blocks[k] for k in others))
        check("C6 no row starts counting",
              {ident(r) for r in rows_a if r.get("counted") is True} <= {ident(r) for r in rows_b if r.get("counted") is True})
        check("C7 the evidence-loss guard reads it as an audited withdrawal, not a loss",
              el.losses_between(before_text, after_text) == [])
        deleted = before_text
        for e in withdraw:
            deleted = deleted.replace(before_blocks[ident(e)][0], "", 1)
        losses = el.losses_between(before_text, deleted)
        check("C8 control: the same rows deleted ARE evidence loss",
              len(losses) == 14 and all(x.code == el.REMOVED for x in losses), str([x.code for x in losses]))
        audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
        deltas = {(p["product_id"], p["update_version"], p["target_build"]): p["before"] - p["after"]
                  for p in audit.get("per_patch") or []}
        check("C9 the audit records the run: hashes, parent, the declared scope, all three populations, each "
              "page losing exactly its withdrawn rows",
              audit.get("written") is True and audit.get("withdrawn_now") == 14
              and audit.get("store_sha256_before") == sha(before_bytes) and audit.get("store_sha256_after") == sha(after_text)
              and audit.get("parent_commit") == "e" * 40 and audit.get("product_scope") == [WIN, OBS, DAV]
              and audit.get("counted_population") == {WIN: [16, 8], OBS: [9, 4], DAV: [3, 2]}
              and deltas == PER_PAGE and audit.get("newly_counted_rows") == [],
              json.dumps({k: audit.get(k) for k in ("withdrawn_now", "product_scope", "counted_population")}))

        print("D  idempotence")
        p4 = run_tool(store, generated, man, "--write", "--confirm-write")
        check("D1 a second run exits 0, writes nothing and reports the fourteen as already withdrawn",
              p4.returncode == 0 and "nothing to write" in p4.stdout and store.read_bytes().decode("utf-8") == after_text
              and p4.stdout.count("[already_withdrawn") == 14 and p4.stdout.count("[kept ") == 8,
              p4.stdout[-400:] + p4.stderr[-300:])

    print("E  each new acceptance clause fails closed: the whole run refuses and nothing is written")
    base = fixture_manifest()
    l1 = entry_of(base, WIN, "25H2", "5769728")
    l1_keep = entry_of(base, WIN, "25H2", "5708079", "retain")

    # E1: the 26200.7922 pair exactly as the two reviews recorded it: one report, opposite kept rows.
    n2_block_w, n2_w = row_of(text, WIN, "25H2", "5794016")
    n2_block_k, n2_k = row_of(text, WIN, "25H2", "5791250")
    n2_keep = {"role": "retain", **{k: str(n2_k.get(k) or "") for k in SEL}, "block_sha256_before": sha(n2_block_k),
               "record_file": "auxsays/updates/generated/2026-02-24-windows-11-25h2-26200-7922.md",
               "target_kb": "KB5077241", "target_os_build": "26200.7922"}
    n2_withdraw = dict(copy.deepcopy(l1), **{k: str(n2_w.get(k) or "") for k in SEL},
                       block_sha256_before=sha(n2_block_w), block_sha256_after=sha(own_edit(n2_block_w, WIN)),
                       record_file=n2_keep["record_file"], target_kb="KB5077241", target_os_build="26200.7922",
                       duplicate_of={k: n2_keep[k] for k in SEL})
    first, blind = labels(n2_withdraw)
    first["duplicate_of_id"], blind["duplicate_of_id"] = n2_w["id"], n2_k["id"]
    n2 = copy.deepcopy(base)
    n2["entries"] += [n2_keep, n2_withdraw]
    proc, same = refused("aux098-e1-", manifest=n2)
    check("E1 the 26200.7922 pair as recorded (the reviews keep opposite rows) refuses the whole run",
          proc.returncode == 1 and "lacks two INCORRECT labels (or two same_report_duplicate" in proc.stdout and same,
          proc.stdout[-300:])

    other = copy.deepcopy(base)
    labels(entry_of(other, WIN, "25H2", "4551560"))[1]["duplicate_of_id"] = entry_of(other, WIN, "25H2", "5982769")["id"]
    proc, same = refused("aux098-e2-", manifest=other)
    check("E2 a blind label that names another row as the original refuses",
          proc.returncode == 1 and "same_report_duplicate labels from two reviewers naming its kept row" in proc.stdout
          and same, proc.stdout[-300:])

    one = copy.deepcopy(base)
    labels(entry_of(one, OBS, "32.2.0", "13690"))[1]["label"] = "uncertain"
    proc, same = refused("aux098-e3-", manifest=one)
    check("E3 one duplicate label beside an uncertain one refuses", proc.returncode == 1 and "lacks two" in proc.stdout
          and same, proc.stdout[-300:])

    twice = copy.deepcopy(base)
    f3, b3 = labels(entry_of(twice, OBS, "32.2.1", "195984"))
    b3["by"] = f3["by"]
    proc, same = refused("aux098-e4-", manifest=twice)
    check("E4 the same reviewer named twice is one adjudication, and refuses",
          proc.returncode == 1 and "lacks two" in proc.stdout and same, proc.stdout[-300:])

    unnamed = copy.deepcopy(base)
    labels(entry_of(unnamed, DAV, "20.2", "1rvhlmx"))[0]["by"] = " "
    proc, same = refused("aux098-e5-", manifest=unnamed)
    check("E5 a label from an unnamed reviewer refuses", proc.returncode == 1 and "lacks two" in proc.stdout and same,
          proc.stdout[-300:])

    noreason = copy.deepcopy(base)
    labels(entry_of(noreason, WIN, "25H2", "4552324"))[1]["reason_class"] = ""
    proc, same = refused("aux098-e6-", manifest=noreason)
    check("E6 a duplicate label without its reason refuses", proc.returncode == 1 and "lacks two" in proc.stdout and same,
          proc.stdout[-300:])

    unflagged = copy.deepcopy(base)
    entry_of(unflagged, WIN, "25H2", "5769728")["capture_tie"] = False
    message = plan_of(text, unflagged)
    check("E7 a same-time capture whose entry does not state it refuses (the kept row is not the earlier capture)",
          "5769728" in message and "the kept row is not the earlier capture" in message, message[:300])

    flagged = copy.deepcopy(base)
    entry_of(flagged, WIN, "25H2", "4551560")["capture_tie"] = True
    message = plan_of(text, flagged)
    check("E8 the flag on a row whose kept original is the earlier capture refuses",
          "capture_tie is stated but the kept row is the earlier capture" in message, message[:300])

    # E9: the same pair with the roles swapped: the kept row would be the LATER post.
    later_keep = dict(copy.deepcopy(l1_keep), **{k: l1[k] for k in SEL}, block_sha256_before=l1["block_sha256_before"])
    later_w = dict(copy.deepcopy(l1), **{k: l1_keep[k] for k in SEL},
                   block_sha256_before=l1_keep["block_sha256_before"],
                   block_sha256_after=sha(own_edit(row_of(text, WIN, "25H2", "5708079")[0], WIN)),
                   duplicate_of={k: l1[k] for k in SEL})
    for lab in labels(later_w):
        lab["duplicate_of_id"] = l1["id"]
    message = plan_of(text, single(base, later_keep, later_w))
    check("E9 at the same capture time the kept row must be the earlier post (the lower question number)",
          "the kept row is not the earlier post" in message, message[:300])

    # E10: two families at one instant -- the kept DaVinci row restated as a Learn question (lower number).
    keep_block, keep_row = row_of(text, DAV, "20.2", "1rnhcy6")
    learn_url = "https://learn.microsoft.com/en-us/answers/questions/1/synthetic-cross-family-fixture"
    cross_text = text.replace(keep_block, keep_block.replace("  source_url: " + keep_row["source_url"] + NL,
                                                             "  source_url: " + learn_url + NL, 1), 1)
    assert cross_text != text
    cross = repin(copy.deepcopy(manifest_doc()), cross_text)
    entry_of(cross, DAV, "20.2", "1rnhcy6", "retain")["source_url"] = learn_url
    cross = repin(cross, cross_text)
    entry_of(cross, DAV, "20.2", "1rvhlmx")["duplicate_of"]["source_url"] = learn_url
    message = plan_of(cross_text, cross)
    check("E10 a same-time capture across two source families refuses",
          "a same-time capture across two source families" in message, message[:300])

    # E11: two Tech Community threads captured at one instant: that family gives no post number here.
    tc_keep_block, tc_keep = row_of(text, WIN, "25H2", "4547615")
    tc_w = copy.deepcopy(entry_of(base, WIN, "25H2", "4550372"))
    tc_w["capture_tie"] = True
    tc_w["duplicate_of"] = {k: str(tc_keep.get(k) or "") for k in SEL}
    for lab in labels(tc_w):
        lab["duplicate_of_id"] = tc_keep["id"]
    tc_keep_entry = dict(copy.deepcopy(entry_of(base, WIN, "25H2", "5978256", "retain")),
                         **{k: str(tc_keep.get(k) or "") for k in SEL}, block_sha256_before=sha(tc_keep_block))
    message = plan_of(text, single(base, tc_keep_entry, tc_w))
    check("E11 a same-time capture in a family without a source post number refuses",
          "a same-time capture whose source gives no post number" in message, message[:300])

    incorrect = copy.deepcopy(base)
    for lab in labels(entry_of(incorrect, WIN, "25H2", "5956430")):
        lab["label"] = "INCORRECT"
    message = plan_of(text, incorrect)
    check("E12 a same-time capture under two INCORRECT labels (no agreed original) refuses",
          "a same-time capture needs two same_report_duplicate labels" in message, message[:300])

    blank_text = text
    for rid in ("5769728", "5708079"):
        block, row = row_of(blank_text, WIN, "25H2", rid)
        blank_text = blank_text.replace(block, block.replace("  captured_at: '" + row["captured_at"] + "'" + NL,
                                                             "  captured_at: ''" + NL, 1), 1)
    assert blank_text.count("  captured_at: ''" + NL) == 2
    message = plan_of(blank_text, repin(copy.deepcopy(manifest_doc()), blank_text))
    check("E13 two rows without a capture time are never a same-time capture",
          "5769728" in message and "the kept row is not the earlier capture" in message, message[:300])

    legacy = copy.deepcopy(base)
    legacy["products"] = [WIN, OBS]
    proc, same = refused("aux098-e14-", manifest=legacy)
    undeclared = copy.deepcopy(base)
    undeclared["products"] = [WIN, DAV]
    proc2, same2 = refused("aux098-e14b-", manifest=undeclared)
    check("E14 a DaVinci row under AUX-088's scope, or a scope the tool does not declare, refuses",
          proc.returncode == 1 and "not a Windows or OBS row" in proc.stdout and same
          and proc2.returncode == 1 and "product scope differs" in proc2.stdout and same2,
          proc.stdout[-200:] + proc2.stdout[-200:])

    built = copy.deepcopy(base)
    entry_of(built, DAV, "20.2", "1rvhlmx")["target_build"] = "20.2"
    proc, same = refused("aux098-e15-", manifest=built)
    check("E15 a DaVinci selector with a target_build refuses (DaVinci has no build contract)",
          proc.returncode == 1 and "target_build must be set exactly" in proc.stdout and same, proc.stdout[-300:])

    dav_block, _dav = row_of(text, DAV, "20.2", "1rvhlmx")
    shaped = dav_block.replace("  counted: true" + NL, "  counted: true" + NL
                               + "  evidence_valid_for_current_patch: true" + NL, 1)
    try:
        wd.withdraw_block(shaped, DAV, DUP)
        dav_shape = False
    except wd.Refusal:
        dav_shape = True
    check("E16 a DaVinci block carrying a validity line is an unexpected shape", dav_shape)

    drifted = text.replace(dav_block, dav_block.replace("  severity: ", "  severity: x", 1), 1)
    assert drifted != text
    proc, same = refused("aux098-e17-", drifted, manifest=fixture_manifest())
    check("E17 a DaVinci row that moved since it was pinned refuses the whole run",
          proc.returncode == 1 and "block changed since the manifest was pinned" in proc.stdout and same,
          proc.stdout[-300:])

    no_dav = [t for t in targets_fixture() if t["front_matter"].get("product_id") != DAV]
    proc, same = refused("aux098-e18-", None, no_dav)
    check("E18 a DaVinci page whose record is missing refuses",
          proc.returncode == 1 and "0 records carry the identity blackmagic-davinci 20.2" in proc.stdout and same,
          proc.stdout[-300:])

    x1_block_w, x1_w = row_of(text, WIN, "26H2", "6019205")
    x1_block_k, x1_k = row_of(text, WIN, "25H2", "6014283")
    x1_keep = {"role": "retain", **{k: str(x1_k.get(k) or "") for k in SEL}, "block_sha256_before": sha(x1_block_k),
               "record_file": "auxsays/updates/generated/2026-09-22-windows-11-25h2-26200-9550.md",
               "target_kb": "KB5124010", "target_os_build": "26200.9550"}
    x1_withdraw = dict(copy.deepcopy(l1), **{k: str(x1_w.get(k) or "") for k in SEL},
                       block_sha256_before=sha(x1_block_w), block_sha256_after=sha(own_edit(x1_block_w, WIN)),
                       record_file="auxsays/updates/generated/2026-09-29-windows-11-26h2-26300-9550.md",
                       target_kb="KB5124010", target_os_build="26300.9550", capture_tie=False,
                       duplicate_of={k: x1_keep[k] for k in SEL})
    for lab in labels(x1_withdraw):
        lab["duplicate_of_id"] = x1_k["id"]
    message = plan_of(text, single(base, x1_keep, x1_withdraw))
    check("E19 the cross-identity 9550 copy, even with two agreeing labels, refuses: its kept row is on another patch",
          "the kept row is on another patch" in message, message[:300])

    print("F  writers and source post numbers")
    expected_writers = (
        ("build_consensus_from_evidence.py", "--product-id", WIN, "--product-id", OBS, "--product-id", DAV,
         "--reconcile-only"),
        ("apply_consensus_to_records.py", "--product-id", WIN, "--write-all", "--confirm-write"),
        ("apply_consensus_to_records.py", "--product-id", OBS, "--write-all", "--confirm-write"),
        ("apply_consensus_to_records.py", "--product-id", DAV, "--write-all", "--confirm-write"),
    )
    writers = wd.writers_for(wd.EXTENDED_PRODUCTS)
    check("F1 the DaVinci scope adds the reconcile's DaVinci scope and davinci-updates.yml's own scoped promotion; "
          "every writer is scoped",
          writers == expected_writers and all(w.count("--product-id") >= 1 for w in writers), str(writers))
    check("F2 AUX-088's writer list is unchanged", wd.WRITERS == AUX088_WRITERS == wd.writers_for(wd.PRODUCTS))
    seen: list[tuple] = []
    saved = (wd.STORE, wd.GENERATED, wd.regenerate)
    try:
        legacy_doc = copy.deepcopy(base)
        legacy_doc["products"] = [WIN, OBS]
        legacy_doc["entries"] = [e for e in legacy_doc["entries"] if e["product_id"] != DAV]
        for doc in (base, legacy_doc):
            with tempfile.TemporaryDirectory(prefix="aux098-f3-") as tmp:
                store, generated, man = make_tree(Path(tmp), manifest=doc)
                wd.STORE, wd.GENERATED = store, generated
                wd.regenerate = lambda w=None: (seen.append(tuple(w)) or [])
                rc = wd.main(["--manifest", str(man), "--baseline", str(Path(tmp) / "none.json"),
                              "--write", "--confirm-write", "--regenerate"])
                seen.append(("rc", rc))
    finally:
        wd.STORE, wd.GENERATED, wd.regenerate = saved
    check("F3 --regenerate runs the writers of the manifest's DECLARED scope (DaVinci only when declared)",
          seen == [expected_writers, ("rc", 0), AUX088_WRITERS, ("rc", 0)], str(seen)[:400])
    ordinals = {url: wd.source_ordinal(url) for url in (
        "https://learn.microsoft.com/en-us/answers/questions/5708079/security-updates-are-not-installing",
        "https://www.reddit.com/r/davinciresolve/comments/1rnhcy6/problem_audio_after_exporting/",
        "https://github.com/obsproject/obs-studio/issues/13685",
        "https://techcommunity.microsoft.com/discussions/windows11/file-history-broken-after-kb5101684--kb5120249/4551560",
        "https://learn.microsoft.com.example.net/en-us/answers/questions/5708079/x")}
    check("F4 a post number is derived only for a Microsoft Learn question or a Reddit post (base 36)",
          list(ordinals.values()) == [("microsoft_learn_question", 5708079), ("reddit_post", int("1rnhcy6", 36)),
                                      None, None, None], str(ordinals))

    print("G  the committed store, and this suite changed nothing real")
    live_text = live_store.read_bytes().decode("utf-8")
    live_rows = blocks_by_identity(live_text)
    live_parsed = {ident(r): r for _lo, _hi, r in aux072.store_blocks(live_text)}
    check("G1 the committed store holds each of the fourteen once, withdrawn, at its pinned after-hash",
          all(len(live_rows.get(ident(e), [])) == 1 and live_parsed[ident(e)].get("counted") is False
              and live_parsed[ident(e)].get("exclusion_reason") == DUP
              and sha(live_rows[ident(e)][0]) == e["block_sha256_after"] for e in withdraw),
          str([e["id"][-24:] for e in withdraw if live_parsed.get(ident(e), {}).get("counted") is not False]))
    check("G2 the eight originals are stored once, counted and byte-identical to their pins",
          all(len(live_rows.get(ident(e), [])) == 1 and live_parsed[ident(e)].get("counted") is True
              and sha(live_rows[ident(e)][0]) == e["block_sha256_before"] for e in retain))
    held_live = [r for r in live_parsed.values() if short(r) in HELD]
    check("G3 every held-out row is still stored once and still counts",
          len(held_live) == 4 and all(r.get("counted") is True for r in held_live)
          and all(len(live_rows[ident(r)]) == 1 for r in held_live))
    live_after = {str(p): sha(p.read_bytes()) for p in live_files if p.exists()}
    check("G4 the live store and the seven records are byte-identical after the suite",
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
