#!/usr/bin/env python3
"""The audited withdrawal of five reports counted against a version they are not about (AUX-108).

`withdraw_live_citation_rows.py` (the AUX-088 mechanism, unchanged) withdraws, with a fourth pinned manifest
(audit/live_citation_withdrawal_v4.json), five stored rows that TWO independent blind adjudications labelled
INCORRECT for the credited version: the build a Windows device rolled back to, the DaVinci version an author
upgraded from, and three DaVinci rows from posts that report no problem with the credited version (a question
from someone who never installed it, the same post's hearsay about another version, a post that says everything
works). Its contract, pinned here:

  A  the committed manifest names exactly those five rows by their full five-field identity, each with two blind
     INCORRECT labels from two different named reviewers (second_blind, third_blind) that both support the row's
     reason, the first audit recorded as provenance only; the scope is Windows, OBS and DaVinci; no retain entry;
     the held-out row (DaVinci 20.2.1) and the two rows that must stay counted are not entries, and the control
     both reviews also labelled INCORRECT is reported as a finding, never an entry; it shares no row with AUX-072's,
     AUX-079's, AUX-088's, AUX-090's or AUX-098's manifest; the committed run audit is this manifest's run
  B  a dry run (the default) plans the five and writes nothing
  C  --write --confirm-write changes exactly 11 lines (three for the Windows row, two per DaVinci row), keeps every
     row, leaves the held-out row, the two must-stay rows, the finding and every other row byte-identical and
     counted, starts no row counting, and the evidence-loss guard reads it as an audited withdrawal; the fixture's
     per-page counts fall by exactly the withdrawn rows (fixture-based, never the live corpus)
  D  a second run changes nothing
  R  re-admission: the append guard every Windows and DaVinci lane writes through (base.append_evidence_rows)
     refuses a withdrawn report seen again (same id and URL, a new Learn title slug, another URL spelling), so the
     five stay withdrawn; a report the store does not hold is still appended
  E  the two-blind rule is not vacuous (a CORRECT, missing, same-reviewer or unsupported label fails it), and the
     tool refuses the whole run on a drifted block, a moved Windows record identity, or a held-out row without
     two INCORRECT labels
  F  --regenerate for this manifest runs the reconcile and one scoped promotion per declared product, never unscoped
  G  the committed store holds the five as withdrawn at their pinned after-hash, the held-out row and the two
     must-stay rows still count, and this suite changed nothing real

The tool runs as a BARE script, so B-D run it as a subprocess exactly as an operator would. Offline: frozen
fixtures (tests/fixtures/live_citation/g51_role_store.yml holds the 18 stored rows involved, serialised as the
store serialises them, with the free-text fields replaced by synthetic marker text; g51_role_targets.json holds
the four records' identity front matter). Because the text differs from the store, the suite re-pins the
committed manifest's block hashes on the fixture with its OWN line edit, never the tool's. No live-corpus count
is asserted anywhere: scheduled collection legitimately moves those.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_withdraw_g51_role_rows.py
"""
from __future__ import annotations

import collections
import copy
import hashlib
import json
import os
import re
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
from patch_collectors import base as wd_base  # noqa: E402

TOOL = SCRIPTS / "withdraw_live_citation_rows.py"
AUDIT = SCRIPTS / "audit"
MANIFEST = AUDIT / "live_citation_withdrawal_v4.json"
RUN_AUDIT = AUDIT / "live_citation_withdrawal_v4_2026-11-19.json"
FIX = SCRIPTS / "tests" / "fixtures" / "live_citation"
STORE_FIXTURE = FIX / "g51_role_store.yml"
TARGETS = FIX / "g51_role_targets.json"
NL = chr(10)
SEL = ("product_id", "update_version", "target_build", "id", "source_url")
WIN, OBS, DAV = "microsoft-windows-11", "obs-studio", "blackmagic-davinci"
INCORRECT = "INCORRECT"
PARENT = "f5bd8e66b7504467f92eef6adde051295dd571d5"

# The five rows both blind reviews labelled INCORRECT, written out here so the manifest cannot redefine them:
# (product, version, build, report number) -> the closed reason both reviews support.
WITHDRAW = {
    (WIN, "25H2", "26200.9168", "5976649"): "version_is_rollback_target",
    (DAV, "21", "", "1wazcmw"): "identity_not_the_subject",
    (DAV, "21.1", "", "1wbshk6"): "not_a_real_issue_report",
    (DAV, "20", "", "1utwlro"): "not_a_real_issue_report",
    (DAV, "21", "", "1wbshk6"): "not_a_real_issue_report",
}
HELD = {(DAV, "20.2.1", "", "1noccl9")}  # held out before adjudication; stays counted
# Must stay counted and untouched: the post's real report (on 21.1), and the 9168 update failing to install.
MUST_STAY = {(DAV, "21.1", "", "1wazcmw"), (WIN, "25H2", "26200.9168", "5987544")}
FINDING = {(DAV, "21.0.4", "", "1w23ivu")}  # a control both reviews labelled INCORRECT: reported, not withdrawn
PRIOR = {  # the earlier audited manifests this one must not overlap
    "AUX-072": "windows_identity_not_the_subject_withdrawal.json",
    "AUX-079": "windows_confirmed_and_duplicate_withdrawal.json",
    "AUX-088": "live_citation_withdrawal.json",
    "AUX-090": "live_citation_withdrawal_v2.json",
    "AUX-098": "live_citation_withdrawal_v3.json",
}
# Fixture-based count deltas (18 fixture rows; never the live corpus): page -> (before, after).
PER_PAGE = {(WIN, "25H2", "26200.9168"): (4, 3), (DAV, "20", ""): (3, 2), (DAV, "21", ""): (4, 2),
            (DAV, "21.1", ""): (4, 3)}
POPULATION = {WIN: [4, 3], OBS: [1, 1], DAV: [13, 9]}
RECORDS = ("2026-08-11-windows-11-25h2-26200-9168.md", "2025-05-28-davinci-resolve-20.md",
           "2026-04-14-davinci-resolve-21.md", "2026-09-08-davinci-resolve-21-1.md")

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
    """The question or post number a URL names."""
    tail = url.rstrip("/")
    if "/answers/questions/" in tail:
        return tail.split("/answers/questions/", 1)[1].split("/", 1)[0]
    if "/comments/" in tail:
        return tail.split("/comments/", 1)[1].split("/", 1)[0]
    return tail.rsplit("/", 1)[-1]


def short(row: dict) -> tuple[str, str, str, str]:
    return (str(row.get("product_id") or ""), str(row.get("update_version") or ""),
            str(row.get("target_build") or ""), report_id(str(row.get("source_url") or "")))


def ident(row: dict) -> tuple[str, ...]:
    """The suite's own five-field identity, so a broken selector in the tool fails a check, not the suite."""
    return tuple(str(row.get(key) or "") for key in SEL)


def own_edit(block: str, product: str, reason: str) -> str:
    """The suite's own withdrawal edit, independent of the tool's: three lines for Windows, two otherwise."""
    pairs = [("  counted: true", "  counted: false"), ("  exclusion_reason: null", "  exclusion_reason: " + reason)]
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
        entry["block_sha256_after"] = sha(own_edit(hits[0], entry["product_id"], entry["exclusion_reason"]))
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


def entry_of(doc: dict, key: tuple[str, str, str, str]) -> dict:
    hits = [e for e in doc["entries"] if short(e) == key]
    assert len(hits) == 1, (key, len(hits))
    return hits[0]


def row_of(text: str, key: tuple[str, str, str, str]) -> tuple[str, dict]:
    hits = [(text[lo:hi], row) for lo, hi, row in aux072.store_blocks(text) if short(row) == key]
    assert len(hits) == 1, (key, len(hits))
    return hits[0]


def supported(label: dict) -> set[str]:
    return {str(label.get("reason_class") or ""), str(label.get("alternative_reason_class") or "")} - {""}


def two_blind(entry: dict) -> bool:
    """GPT's rule for this withdrawal: two independently established INCORRECT determinations. The two are the
    blind reviews (second_blind, third_blind): both INCORRECT, two different named reviewers, neither the first
    audit, the same packet case, each with a closed reason and a one-line reason, and the row's reason one that
    BOTH support. The first audit is provenance (INCORRECT, as the tool requires) and never one of the two."""
    adj = entry.get("adjudication") or {}
    first, a, b = adj.get("first_audit") or {}, adj.get("second_blind") or {}, adj.get("third_blind") or {}
    names = [str(x.get("by") or "").strip() for x in (first, a, b)]
    return (a.get("label") == b.get("label") == INCORRECT and all(names) and len(set(names)) == 3
            and bool(re.fullmatch(r"P[0-9]{2}", str(a.get("case") or ""))) and a.get("case") == b.get("case")
            and str(a.get("reason") or "").strip() != "" and str(b.get("reason") or "").strip() != ""
            and supported(a) <= wd.REASONS and supported(b) <= wd.REASONS
            and entry.get("exclusion_reason") in (supported(a) & supported(b))
            and first.get("label") == INCORRECT and first.get("counts_toward_the_two") is False)


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Audited withdrawal of five reports counted against a version they are not about (AUX-108)")
    print("=" * 78)
    live_store = ROOT / "_data" / "consensus_evidence.yml"
    live_files = [live_store] + [ROOT / "updates" / "generated" / name for name in RECORDS]
    live_before = {str(p): sha(p.read_bytes()) for p in live_files if p.exists()}
    manifest = manifest_doc()
    text = fixture_text()
    withdraw = [e for e in manifest["entries"] if e.get("role") == "withdraw"]

    print("A  the pinned manifest")
    check("A1 five rows are withdrawn (one Windows, four DaVinci) and none is kept, under ledger AUX-108, version 4",
          len(withdraw) == 5 and len(manifest["entries"]) == 5 and manifest.get("ledger") == "AUX-108"
          and manifest.get("version") == 4
          and collections.Counter(e["product_id"] for e in withdraw) == {WIN: 1, DAV: 4},
          f"{len(withdraw)} withdraw of {len(manifest['entries'])}")
    check("A2 the withdrawn rows are exactly the five, each with the reason both blind reviews support",
          {short(e): e["exclusion_reason"] for e in withdraw} == WITHDRAW,
          str(sorted({short(e) for e in withdraw} ^ set(WITHDRAW))))
    check("A3 five-field identity: every field set, target_build exactly for Windows, no identity repeated; the "
          "selector, the closed reasons and the Windows, OBS and DaVinci scope are the tool's own",
          all(all(str(e.get(k) or "") for k in SEL if k != "target_build") for e in withdraw)
          and all(bool(e["target_build"]) == (e["product_id"] == WIN) for e in withdraw)
          and len({ident(e) for e in withdraw}) == 5 and tuple(manifest["selector"]) == SEL
          and sorted(manifest["exclusion_reasons"]) == sorted(wd.REASONS)
          and tuple(manifest["products"]) == wd.EXTENDED_PRODUCTS == (WIN, OBS, DAV))
    check("A4 every row carries two blind INCORRECT labels from two different named reviewers that both support its "
          "reason; the first audit is provenance only; each row its own packet case",
          all(two_blind(e) and str(e.get("basis") or "").strip() for e in withdraw)
          and len({e["adjudication"]["second_blind"]["case"] for e in withdraw}) == 5,
          str([e["id"][-30:] for e in withdraw if not two_blind(e)]))
    held = {short(r) for h in manifest.get("held_out", []) for r in h["rows"]}
    found = {short(r) for h in manifest.get("findings_not_withdrawn", []) for r in h["rows"]}
    entries = {short(e) for e in manifest["entries"]}
    check("A5 the held-out row and the control finding are listed with a reason and are not entries; the two "
          "must-stay rows are not entries",
          held == HELD and found == FINDING
          and all(str(h.get("why") or "").strip() for h in manifest["held_out"] + manifest["findings_not_withdrawn"])
          and not (entries & (HELD | FINDING | MUST_STAY)))
    prior_ids, prior_reports = set(), set()
    for name in PRIOR.values():
        doc = json.loads((AUDIT / name).read_text(encoding="utf-8"))
        prior_ids |= {ident(e) for e in doc["entries"]}
        prior_reports |= {short(e) for e in doc["entries"]}
    check("A6 no row (by five-field identity, or by page and report) is shared with AUX-072's, AUX-079's, "
          "AUX-088's, AUX-090's or AUX-098's manifest",
          not (prior_ids & {ident(e) for e in withdraw}) and not (prior_reports & entries))
    check("A7 each row pins its record, and the Windows row its record's target KB and OS build",
          all(str(e.get("record_file") or "").endswith(".md") for e in withdraw)
          and all(e.get("target_kb") == "KB5121003" and e.get("target_os_build") == e["target_build"] == "26200.9168"
                  for e in withdraw if e["product_id"] == WIN))
    try:
        accepted = wd.manifest_entries(manifest) == manifest["entries"] and wd.manifest_scope(manifest) == wd.EXTENDED_PRODUCTS
    except wd.Refusal as exc:
        accepted = False
        print(f"        refusal: {exc}")
    check("A8 the tool's own manifest checks accept it (scope, selector, closed reasons, two labels, basis)", accepted)
    run_audit = json.loads(RUN_AUDIT.read_text(encoding="utf-8"))
    deltas = {(p["product_id"], p["update_version"], p["target_build"]): p["before"] - p["after"]
              for p in run_audit.get("per_patch") or []}
    check("A9 the committed run audit is this manifest's run: written, five withdrawn at the pinned parent, the "
          "manifest's hash, each page losing exactly its withdrawn rows, no row newly counted, the four scoped writers ok",
          run_audit.get("written") is True and run_audit.get("withdrawn_now") == 5
          and run_audit.get("parent_commit") == manifest.get("parent_commit") == PARENT
          and run_audit.get("manifest_sha256") == sha(MANIFEST.read_bytes())
          and run_audit.get("store_sha256_before") == manifest.get("store_sha256_at_pin")
          and deltas == {k: b - a for k, (b, a) in PER_PAGE.items()} and run_audit.get("newly_counted_rows") == []
          and [w["command"] for w in run_audit.get("writers") or []] == [" ".join(w) for w in wd.writers_for(wd.EXTENDED_PRODUCTS)]
          and all(w["returncode"] == 0 for w in run_audit.get("writers") or []),
          json.dumps({k: run_audit.get(k) for k in ("written", "withdrawn_now", "parent_commit")}))

    print("B  dry run, as the bare script")
    with tempfile.TemporaryDirectory(prefix="aux108-dry-") as tmp:
        store, generated, man = make_tree(Path(tmp))
        before = store.read_bytes()
        proc = run_tool(store, generated, man)
        out = proc.stdout
        check("B1 a dry run exits 0 and writes nothing", proc.returncode == 0 and store.read_bytes() == before,
              proc.stdout[-400:] + proc.stderr[-400:])
        check("B2 it plans exactly the five", out.count("[withdraw ") == 5 and "rows withdrawn by this run: 5" in out
              and "[kept " not in out, out[-600:])

    print("C  the write")
    with tempfile.TemporaryDirectory(prefix="aux108-write-") as tmp:
        store, generated, man = make_tree(Path(tmp))
        before_bytes = store.read_bytes()
        audit_path = Path(tmp) / "audit.json"
        p3 = run_tool(store, generated, man, "--write", "--confirm-write", "--audit", str(audit_path),
                      "--parent-commit", "e" * 40)
        check("C1 --write --confirm-write withdraws the five and says so",
              p3.returncode == 0 and "WROTE" in p3.stdout and "rows withdrawn by this run: 5" in p3.stdout,
              p3.stdout[-500:] + p3.stderr[-500:])
        before_text, after_text = before_bytes.decode("utf-8"), store.read_bytes().decode("utf-8")
        a_lines, b_lines = before_text.split(NL), after_text.split(NL)
        changed = [(a, b) for a, b in zip(a_lines, b_lines) if a != b]
        expected = collections.Counter({("  counted: true", "  counted: false"): 5,
                                        ("  exclusion_reason: null", "  exclusion_reason: version_is_rollback_target"): 1,
                                        ("  exclusion_reason: null", "  exclusion_reason: identity_not_the_subject"): 1,
                                        ("  exclusion_reason: null", "  exclusion_reason: not_a_real_issue_report"): 3,
                                        ("  evidence_valid_for_current_patch: true",
                                         "  evidence_valid_for_current_patch: false"): 1})
        check("C2 exactly 11 lines change: three for the Windows row, two per DaVinci row, each with its own reason",
              len(a_lines) == len(b_lines) and collections.Counter(changed) == expected and len(changed) == 11,
              f"{len(changed)} changed: {collections.Counter(changed)}")
        after_blocks, before_blocks = blocks_by_identity(after_text), blocks_by_identity(before_text)
        fman = json.loads(man.read_text(encoding="utf-8"))
        check("C3 every withdrawn block now hashes to its pinned after-value",
              all([sha(b) for b in after_blocks.get(ident(e), [])] == [e["block_sha256_after"]] for e in fman["entries"]))
        rows_b = [r for _lo, _hi, r in aux072.store_blocks(before_text)]
        rows_a = [r for _lo, _hi, r in aux072.store_blocks(after_text)]
        out_ids = {ident(e): e["exclusion_reason"] for e in withdraw}
        moved = [(o, n) for o, n in zip(rows_b, rows_a) if ident(o) in out_ids]

        def expected_row(o: dict) -> dict:
            extra = {"evidence_valid_for_current_patch": False} if o["product_id"] == WIN else {}
            return dict(o, counted=False, exclusion_reason=out_ids[ident(o)], **extra)
        check("C4 the five parse as withdrawn, every other field unchanged, no field added to a DaVinci row",
              len(moved) == 5 and all(n == expected_row(o) for o, n in moved)
              and all("evidence_valid_for_current_patch" not in n for o, n in moved if o["product_id"] != WIN))
        others = [k for k in before_blocks if k not in out_ids]
        kept = [k for k in others if short(dict(zip(SEL, k))) in HELD | MUST_STAY | FINDING]
        parsed_after = {ident(r): r for r in rows_a}
        check("C5 no row is added or removed; the held-out row, the two must-stay rows, the finding and every other "
              "row are byte-identical and still count",
              len(rows_a) == len(rows_b) == 18 and len(others) == 13 and len(kept) == 4
              and all(after_blocks.get(k) == before_blocks[k] for k in others)
              and all(parsed_after[k].get("counted") is True for k in others))
        check("C6 no row starts counting",
              {ident(r) for r in rows_a if r.get("counted") is True} <= {ident(r) for r in rows_b if r.get("counted") is True})
        check("C7 the evidence-loss guard reads it as an audited withdrawal, not a loss",
              el.losses_between(before_text, after_text) == [])
        deleted = before_text
        for e in withdraw:
            deleted = deleted.replace(before_blocks[ident(e)][0], "", 1)
        losses = el.losses_between(before_text, deleted)
        check("C8 control: the same rows deleted ARE evidence loss",
              len(losses) == 5 and all(x.code == el.REMOVED for x in losses), str([x.code for x in losses]))
        audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
        per_page = {(p["product_id"], p["update_version"], p["target_build"]): (p["before"], p["after"])
                    for p in audit.get("per_patch") or []}
        siblings = audit.get("same_report_rows_on_other_identities") or []
        check("C9 fixture counts: each page loses exactly its withdrawn rows, the populations fall by one Windows and "
              "four DaVinci rows and no OBS row, and the one same-report row on another identity (the post's 21.1 "
              "report) is left untouched and counted",
              audit.get("written") is True and audit.get("withdrawn_now") == 5 and per_page == PER_PAGE
              and audit.get("counted_population") == POPULATION and audit.get("newly_counted_rows") == []
              and audit.get("store_sha256_before") == sha(before_bytes) and audit.get("store_sha256_after") == sha(after_text)
              and audit.get("product_scope") == [WIN, OBS, DAV] and audit.get("parent_commit") == "e" * 40
              and [short(s) for s in siblings] == [(DAV, "21.1", "", "1wazcmw")]
              and all(s["counted"] is True and s["unchanged"] is True for s in siblings),
              json.dumps({k: audit.get(k) for k in ("withdrawn_now", "counted_population", "per_patch")})[:600])

        print("D  idempotence")
        p4 = run_tool(store, generated, man, "--write", "--confirm-write")
        check("D1 a second run exits 0, writes nothing and reports the five as already withdrawn",
              p4.returncode == 0 and "nothing to write" in p4.stdout and store.read_bytes().decode("utf-8") == after_text
              and p4.stdout.count("[already_withdrawn") == 5, p4.stdout[-400:] + p4.stderr[-300:])

        print("R  re-admission: a scheduled collector that sees a withdrawn report again")
        # Every lane that can write these rows persists through base.append_evidence_rows (Windows:
        # patch_collectors/microsoft_windows.py; DaVinci: patch_collectors/davinci.py and
        # promote_davinci_verified_reports.py). Its guard keys are built from EVERY stored row, counted or not, and a
        # withdrawal keeps the row, so the report's id and URL keys stay held.
        reseen, variants = [], []
        for o in rows_b:
            if ident(o) not in out_ids:
                continue
            again = dict(o, counted=True, exclusion_reason=None, captured_at="2026-12-01T00:00:00Z")
            if o["product_id"] == WIN:
                again["evidence_valid_for_current_patch"] = True
            reseen.append(again)
            url = o["source_url"]
            if "/answers/questions/" in url:  # Learn: the same question under a new title slug (AUX-078)
                alt = url.split("/answers/questions/", 1)[0] + f"/answers/questions/{report_id(url)}/a-new-title-slug"
            else:  # Reddit: the same post spelled another way
                alt = url.rstrip("/").replace("https://www.reddit.com/r/davinciresolve/", "https://www.reddit.com/r/DavinciResolve/")
            variants.append(dict(again, id=o["id"] + "-recaptured", source_url=alt))
        pre = store.read_bytes()
        held_back: list[dict] = []
        added, _total, _all = wd_base.append_evidence_rows(reseen + variants, store, out_already_held=held_back)
        check("R1 re-seeing each withdrawn report (the same id and URL, or the same report under another title slug "
              "or URL spelling) adds nothing: all ten are refused as already held and the store is byte-identical",
              added == 0 and store.read_bytes() == pre and len(held_back) == 10 and len(reseen) == len(variants) == 5,
              f"added={added} held={len(held_back)}")
        stored = {ident(r): r for _lo, _hi, r in aux072.store_blocks(store.read_bytes().decode("utf-8"))}
        check("R2 so each of the five is still withdrawn, with its reason, and nothing re-counts it",
              all(stored[k].get("counted") is False and stored[k].get("exclusion_reason") == reason
                  for k, reason in out_ids.items()))
        control_store = Path(tmp) / "control.yml"
        control_store.write_bytes(pre)
        fresh = dict(reseen[0], id=reseen[0]["id"] + "-a-different-report",
                     source_url=reseen[0]["source_url"].rstrip("/") + "-a-different-report")
        if "/answers/questions/" in fresh["source_url"]:
            fresh["source_url"] = "https://learn.microsoft.com/en-us/answers/questions/1/a-different-question"
        added_new, _t, _a = wd_base.append_evidence_rows([fresh], control_store)
        check("R3 control: a report the store does not hold IS appended (the guard is not refusing everything)",
              added_new == 1 and control_store.read_bytes() != pre)

    print("E  the two-blind rule is not vacuous, and the tool fails closed")
    base = fixture_manifest()
    h1, t3 = (WIN, "25H2", "26200.9168", "5976649"), (DAV, "21", "", "1wazcmw")
    cases = {}
    m = copy.deepcopy(base)
    entry_of(m, h1)["adjudication"]["third_blind"]["label"] = "CORRECT"
    cases["a blind review saying CORRECT"] = m
    m = copy.deepcopy(base)
    entry_of(m, h1)["adjudication"].pop("third_blind")
    cases["a missing second blind review"] = m
    m = copy.deepcopy(base)
    adj = entry_of(m, h1)["adjudication"]
    adj["third_blind"]["by"] = adj["second_blind"]["by"]
    cases["one reviewer named twice"] = m
    m = copy.deepcopy(base)
    adj = entry_of(m, h1)["adjudication"]
    adj["third_blind"]["by"] = adj["first_audit"]["by"]
    cases["the first audit standing in for a blind review"] = m
    m = copy.deepcopy(base)
    entry_of(m, t3)["exclusion_reason"] = "version_named_but_working"
    cases["a reason only one blind review supports"] = m
    m = copy.deepcopy(base)
    entry_of(m, h1)["adjudication"]["first_audit"]["counts_toward_the_two"] = True
    cases["the first audit counted as one of the two"] = m
    verdicts = {name: all(two_blind(e) for e in doc["entries"]) for name, doc in cases.items()}
    check("E1 the two-blind rule rejects: " + "; ".join(cases),
          all(two_blind(e) for e in base["entries"]) and not any(verdicts.values()), str(verdicts))

    t5 = (DAV, "20", "", "1utwlro")
    t5_block, _t5 = row_of(text, t5)
    drifted = text.replace(t5_block, t5_block.replace("  severity: ", "  severity: x", 1), 1)
    assert drifted != text
    proc, same = refused("aux108-e2-", drifted, manifest=fixture_manifest())
    check("E2 a row that moved since it was pinned refuses the whole run and writes nothing",
          proc.returncode == 1 and "block changed since the manifest was pinned" in proc.stdout and same,
          proc.stdout[-300:])

    moved_kb = copy.deepcopy(targets_fixture())
    for target in moved_kb:
        if target["front_matter"]["product_id"] == WIN:
            target["front_matter"]["target_kb"] = "KB0000000"
    proc, same = refused("aux108-e3-", None, moved_kb)
    check("E3 a Windows record whose target KB moved refuses the whole run (the record pin)",
          proc.returncode == 1 and "record target identity moved" in proc.stdout and same, proc.stdout[-300:])

    t2_block, t2_row = row_of(text, (DAV, "20.2.1", "", "1noccl9"))
    t2_entry = dict(copy.deepcopy(entry_of(base, t5)), **{k: str(t2_row.get(k) or "") for k in SEL},
                    record_file="auxsays/updates/generated/2025-09-23-davinci-resolve-20-2-1.md",
                    block_sha256_before=sha(t2_block),
                    block_sha256_after=sha(own_edit(t2_block, DAV, "not_a_real_issue_report")))
    t2_entry["adjudication"]["second_blind"]["label"] = "UNSURE"
    t2_doc = copy.deepcopy(base)
    t2_doc["entries"].append(t2_entry)
    t2_targets = targets_fixture() + [{"file": "2025-09-23-davinci-resolve-20-2-1.md", "front_matter": {
        "update_entry": True, "product_id": DAV, "update_version": "20.2.1"}}]
    proc, same = refused("aux108-e4-", None, t2_targets, t2_doc)
    check("E4 the held-out row without two INCORRECT labels refuses the whole run",
          proc.returncode == 1 and "lacks two INCORRECT labels" in proc.stdout and same, proc.stdout[-300:])

    print("F  writers")
    expected_writers = (
        ("build_consensus_from_evidence.py", "--product-id", WIN, "--product-id", OBS, "--product-id", DAV,
         "--reconcile-only"),
        ("apply_consensus_to_records.py", "--product-id", WIN, "--write-all", "--confirm-write"),
        ("apply_consensus_to_records.py", "--product-id", OBS, "--write-all", "--confirm-write"),
        ("apply_consensus_to_records.py", "--product-id", DAV, "--write-all", "--confirm-write"),
    )
    seen: list[tuple] = []
    saved = (wd.STORE, wd.GENERATED, wd.regenerate)
    try:
        with tempfile.TemporaryDirectory(prefix="aux108-f1-") as tmp:
            store, generated, man = make_tree(Path(tmp))
            wd.STORE, wd.GENERATED = store, generated
            wd.regenerate = lambda w=None: (seen.append(tuple(w)) or [])
            rc = wd.main(["--manifest", str(man), "--baseline", str(Path(tmp) / "none.json"),
                          "--write", "--confirm-write", "--regenerate"])
            seen.append(("rc", rc))
    finally:
        wd.STORE, wd.GENERATED, wd.regenerate = saved
    check("F1 --regenerate runs the reconcile and one scoped promotion per declared product; nothing unscoped",
          seen == [expected_writers, ("rc", 0)] and all(w.count("--product-id") >= 1 for w in expected_writers),
          str(seen)[:400])

    print("G  the committed store, and this suite changed nothing real")
    live_text = live_store.read_bytes().decode("utf-8")
    live_rows = blocks_by_identity(live_text)
    live_parsed = {ident(r): r for _lo, _hi, r in aux072.store_blocks(live_text)}
    for e in withdraw:
        row = live_parsed.get(ident(e), {})
        check(f"G1 {e['product_id']} {e['update_version']} {report_id(e['source_url'])} is stored once, withdrawn "
              f"as {e['exclusion_reason']}, at its pinned after-hash",
              len(live_rows.get(ident(e), [])) == 1 and row.get("counted") is False
              and row.get("exclusion_reason") == e["exclusion_reason"]
              and sha(live_rows[ident(e)][0]) == e["block_sha256_after"],
              str((row.get("counted"), row.get("exclusion_reason"))))
    stay = [r for r in live_parsed.values() if short(r) in HELD | MUST_STAY]
    check("G2 the held-out row and the two must-stay rows are each stored once and still count",
          len(stay) == 3 and all(r.get("counted") is True for r in stay)
          and all(len(live_rows[ident(r)]) == 1 for r in stay),
          str([(short(r), r.get("counted")) for r in stay]))
    live_after = {str(p): sha(p.read_bytes()) for p in live_files if p.exists()}
    check("G3 the live store and the four records are byte-identical after the suite",
          live_after == live_before and len(live_before) == 5, f"{len(live_before)} files")

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
