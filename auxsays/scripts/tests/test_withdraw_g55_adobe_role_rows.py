#!/usr/bin/env python3
"""The audited withdrawal of two Adobe reports counted against a version they are not about (AUX-111).

`withdraw_live_citation_rows.py` (the AUX-088 mechanism) gains a third product scope, exactly (Acrobat Reader,
Premiere Pro), and withdraws with a fifth pinned manifest (audit/live_citation_withdrawal_v5.json) the two rows
that TWO independent blind adjudications labelled INCORRECT for the credited version: a Premiere Pro 27 error on
projects that were CREATED in 26.2.2, and a failure to patch FROM Acrobat Reader 15.020.20039 to a later build.
Its contract, pinned here:

  A  the committed manifest names exactly those two rows by their full five-field identity, each with two blind
     INCORRECT labels from two different named reviewers that both support its reason, the first audit as
     provenance only; the scope is exactly (Acrobat Reader, Premiere Pro); the manifest's identities are exactly
     the tool's grant; the two must-stay controls and the control finding are not entries; it shares no row with
     an earlier withdrawal or re-admission manifest; it records the blind packet's hashes; the committed run
     audit is this manifest's run
  B  a dry run plans the two and writes nothing
  C  --write --confirm-write changes exactly 4 lines, keeps every row, leaves every other row (the must-stay rows,
     the controls, the finding, the same report re-stated on Acrobat Pro, an Acrobat Pro, a Photoshop and a
     DaVinci row) byte-identical and counted, starts no row counting, and the evidence-loss guard reads it as an
     audited withdrawal; fixture counts fall by exactly the two
  D  a second run changes nothing
  R  re-admission: the append guard both Adobe collectors write through (base.append_evidence_rows) refuses a
     withdrawn report seen again (same id and URL, another URL spelling), so both stay withdrawn; a report the
     store does not hold is still appended
  S  THE SCOPE GUARD (GPT's G55 requirement): the extension cannot authorize a withdrawal of an unrelated Adobe
     product (Acrobat Pro -- even the same report on the same version -- or Photoshop), under a scope that adds,
     drops or reorders a product, of an unlisted identity of a granted product (the must-stay row on the target's
     own page, another page's row, the control finding), or of a granted identity with any one field changed;
     the grant is enforced by the manifest reader AND by the planner, under every scope; a granted row needs two
     blind INCORRECT labels in the tool itself; the older scopes, their writers and their manifests are unchanged
  F  --regenerate for this manifest runs the reconcile scoped to the two products and each product's own scoped
     promotion -- the same two steps the scheduled lane runs for them -- never unscoped
  G  the committed store holds the two as withdrawn at their pinned after-hash, the must-stay rows and the finding
     still count, and this suite changed nothing real

The tool runs as a BARE script, so B-D and the S end-to-end checks run it as a subprocess, exactly as an operator
would; S also calls the manifest reader and the planner in process, so each half of the guard is pinned on its
own. Offline: frozen fixtures (tests/fixtures/live_citation/g55_adobe_store.yml holds 12 rows serialised as the
store serialises them, with free text replaced by synthetic marker text; two rows exist only in the fixture: the
Reader report re-stated on Acrobat Pro, and a Photoshop row; g55_adobe_targets.json holds the pages' identity
front matter). The suite re-pins the manifest's block hashes on the fixture with its OWN line edit. No live-corpus
count is asserted anywhere.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_withdraw_g55_adobe_role_rows.py
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
MANIFEST = AUDIT / "live_citation_withdrawal_v5.json"
RUN_AUDIT = AUDIT / "live_citation_withdrawal_v5_2026-11-19.json"
FIX = SCRIPTS / "tests" / "fixtures" / "live_citation"
STORE_FIXTURE = FIX / "g55_adobe_store.yml"
TARGETS = FIX / "g55_adobe_targets.json"
WORKFLOW = ROOT.parent / ".github" / "workflows" / "obs-evidence-collection.yml"
NL = chr(10)
SEL = ("product_id", "update_version", "target_build", "id", "source_url")
READER, PREMIERE = "adobe-acrobat-reader", "adobe-premiere-pro"
PRO, PHOTOSHOP = "adobe-acrobat-pro", "adobe-photoshop"
WIN, OBS, DAV = "microsoft-windows-11", "obs-studio", "blackmagic-davinci"
INCORRECT = "INCORRECT"
PARENT = "cfd2c36af236d9c4c59f9a32f8548b116856d525"
REASON = "version_named_but_working"

# The two rows both blind reviews labelled INCORRECT, written out here so neither the manifest nor the tool's grant
# can redefine them: (product, version, build, report number) -> the closed reason both reviews support.
WITHDRAW = {(PREMIERE, "26.2.2", "", "1656474"): REASON, (READER, "15.020.20039", "", "1510656"): REASON}
MUST_STAY = {(READER, "15.020.20039", "", "673695"), (PREMIERE, "26.2.2", "", "1627000")}  # each target page's S1
FINDING = {(READER, "15.010.20056", "", "594365")}  # a control both reviews labelled INCORRECT: reported, not withdrawn
CONTROLS = {(PREMIERE, "26.2", "", "1635805"), (READER, "19.010.20064", "", "1516326"), (PREMIERE, "26.2", "", "1630083")}
# The blind adjudication's own files, by hash (the packet, its brief, the control rule fixed before the draw, A, B).
PACKET_HASHES = {
    "packet_sha256": "f944c74e129010b6a0a8b56384e60f191c9a73294ebd5b59ea2b6ad86467b86b",
    "brief_sha256": "5b66aebd11fb71ec03d20ab9e2df08bc335b7f99bb65f6db6c695e34a4d8aefd",
    "control_rule_sha256": "050683bedf6a81b579e2618d1b0d8c138059b7eebea2f495349c0c0500fd5910",
    "labels_a_sha256": "c1b60ce9e5312bf6da6895822b4bce30638892ec9db9ed753a65455146b7f6d8",
    "labels_b_sha256": "6da65703d9331aa49577ab2bba48dd2e35e65b0631ceb6e03456ca1e498f2a19",
}
PRIOR = {  # the earlier audited manifests this one must not overlap
    "AUX-072": "windows_identity_not_the_subject_withdrawal.json",
    "AUX-079": "windows_confirmed_and_duplicate_withdrawal.json",
    "AUX-088": "live_citation_withdrawal.json",
    "AUX-090": "live_citation_withdrawal_v2.json",
    "AUX-098": "live_citation_withdrawal_v3.json",
    "AUX-108": "live_citation_withdrawal_v4.json",
    "AUX-110": "acrobat_reader_readmission.json",
}
# Fixture-based count deltas (12 fixture rows; never the live corpus).
PER_PAGE = {(READER, "15.020.20039", ""): (2, 1), (PREMIERE, "26.2.2", ""): (2, 1)}
POPULATION = {READER: [4, 3], PREMIERE: [4, 3]}
RECORDS = ("2016-10-11-adobe-acrobat-reader-15-020-20039.md", "2026-05-01-premiere-pro-26-2-2.md")

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
    """The thread number an Adobe Community URL ends with (the last hyphen-separated token)."""
    return str(url or "").rstrip("/").rsplit("-", 1)[-1]


def short(row: dict) -> tuple[str, str, str, str]:
    return (str(row.get("product_id") or ""), str(row.get("update_version") or ""),
            str(row.get("target_build") or ""), report_id(str(row.get("source_url") or "")))


def ident(row: dict) -> tuple[str, ...]:
    """The suite's own five-field identity, so a broken selector in the tool fails a check, not the suite."""
    return tuple(str(row.get(key) or "") for key in SEL)


def own_edit(block: str, reason: str) -> str:
    """The suite's own withdrawal edit, independent of the tool's: two lines, no validity line."""
    for old, new in (("  counted: true", "  counted: false"), ("  exclusion_reason: null", "  exclusion_reason: " + reason)):
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
        entry["block_sha256_after"] = sha(own_edit(hits[0], entry["exclusion_reason"]))
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


def refused(prefix: str, manifest: dict, store_text: str | None = None) -> tuple[subprocess.CompletedProcess, bool]:
    """Run --write --confirm-write on a fixture tree and report whether the store came back byte-identical."""
    with tempfile.TemporaryDirectory(prefix=prefix) as tmp:
        store, generated, man = make_tree(Path(tmp), store_text, None, manifest)
        before = store.read_bytes()
        proc = run_tool(store, generated, man, "--write", "--confirm-write")
        return proc, store.read_bytes() == before


def reader_refusal(doc: dict) -> str:
    """The manifest reader's own verdict, in process: '' when it accepts, else its refusal text. Any other
    exception comes back as its type and text, so a crash is never mistaken for the refusal a check expects."""
    try:
        wd.manifest_entries(doc)
    except wd.Refusal as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001
        return f"CRASH {type(exc).__name__}: {exc}"
    return ""


def planner_refusal(text: str, entries: list[dict], scope: tuple[str, ...] | None) -> str:
    """The planner's own verdict, in process and without the manifest reader in front of it."""
    with tempfile.TemporaryDirectory(prefix="aux111-plan-") as tmp:
        _store, generated, _man = make_tree(Path(tmp), text, None, {})
        try:
            wd.plan(text, entries, wd.patch_records(generated), {}, scope)
        except wd.Refusal as exc:
            return str(exc)
        except Exception as exc:  # noqa: BLE001
            return f"CRASH {type(exc).__name__}: {exc}"
    return ""


def entry_of(doc: dict, key: tuple[str, str, str, str]) -> dict:
    hits = [e for e in doc["entries"] if short(e) == key]
    assert len(hits) == 1, (key, len(hits))
    return hits[0]


def row_of(text: str, key: tuple[str, str, str, str]) -> tuple[str, dict]:
    hits = [(text[lo:hi], row) for lo, hi, row in aux072.store_blocks(text) if short(row) == key]
    assert len(hits) == 1, (key, len(hits))
    return hits[0]


def as_entry(base_entry: dict, row: dict, block: str) -> dict:
    """A fully pinned withdraw entry for `row`, carrying `base_entry`'s labels (two blind INCORRECTs) and basis:
    everything a valid entry needs, so only the scope guard can stop it."""
    entry = copy.deepcopy(base_entry)
    entry.update({k: str(row.get(k) or "") for k in SEL})
    entry["record_file"] = "auxsays/updates/generated/fixture-page.md"
    entry["block_sha256_before"] = sha(block)
    entry["block_sha256_after"] = sha(own_edit(block, entry["exclusion_reason"]))
    return entry


def supported(label: dict) -> set[str]:
    return {str(label.get("reason_class") or ""), str(label.get("alternative_reason_class") or "")} - {""}


def two_blind(entry: dict) -> bool:
    """The suite's own reading of GPT's rule: two independently established INCORRECT determinations, the blind
    reviews (second_blind, third_blind): both INCORRECT, two different named reviewers, neither the first audit,
    the same packet case, each with a reason, and the row's reason one BOTH support. The first audit is provenance
    (INCORRECT, as the tool's older two-label check requires) and never one of the two."""
    adj = entry.get("adjudication") or {}
    first, a, b = adj.get("first_audit") or {}, adj.get("second_blind") or {}, adj.get("third_blind") or {}
    names = [str(x.get("by") or "").strip() for x in (first, a, b)]
    return (a.get("label") == b.get("label") == INCORRECT and all(names) and len(set(names)) == 3
            and bool(re.fullmatch(r"P[0-9]{2}", str(a.get("case") or ""))) and a.get("case") == b.get("case")
            and str(a.get("reason") or "").strip() != "" and str(b.get("reason") or "").strip() != ""
            and supported(a) <= wd.REASONS and supported(b) <= wd.REASONS
            and entry.get("exclusion_reason") in (supported(a) & supported(b))
            and first.get("label") == INCORRECT and first.get("counts_toward_the_two") is False)


def workflow_promotions() -> list[str]:
    """The product ids the scheduled lane promotes with `--write-all --confirm-write`, in order."""
    text = WORKFLOW.read_text(encoding="utf-8")
    return re.findall(r"apply_consensus_to_records\.py \\\s*\n\s*--product-id ([a-z0-9-]+) \\\s*\n\s*--write-all "
                      r"--confirm-write", text)


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Audited withdrawal of two Adobe reports counted against a version they are not about (AUX-111)")
    print("=" * 78)
    live_store = ROOT / "_data" / "consensus_evidence.yml"
    live_files = [live_store] + [ROOT / "updates" / "generated" / name for name in RECORDS]
    live_before = {str(p): sha(p.read_bytes()) for p in live_files if p.exists()}
    manifest = manifest_doc()
    text = fixture_text()
    withdraw = [e for e in manifest["entries"] if e.get("role") == "withdraw"]

    print("A  the pinned manifest")
    check("A1 two rows are withdrawn (one Acrobat Reader, one Premiere Pro) and none is kept, under ledger AUX-111, "
          "version 5",
          len(withdraw) == 2 and len(manifest["entries"]) == 2 and manifest.get("ledger") == "AUX-111"
          and manifest.get("version") == 5
          and collections.Counter(e["product_id"] for e in withdraw) == {READER: 1, PREMIERE: 1},
          f"{len(withdraw)} withdraw of {len(manifest['entries'])}")
    check("A2 the withdrawn rows are exactly the two, each with the reason both blind reviews support",
          {short(e): e["exclusion_reason"] for e in withdraw} == WITHDRAW,
          str(sorted({short(e) for e in withdraw} ^ set(WITHDRAW))))
    grant = {g for ids in wd.PRODUCT_GRANTS.values() for g in ids}
    check("A3 five-field identity with no build; the selector, the closed reasons and the scope (exactly Acrobat "
          "Reader, Premiere Pro) are the tool's own; the manifest's identities ARE the tool's grant, nothing more",
          all(all(str(e.get(k) or "") for k in SEL if k != "target_build") and e["target_build"] == "" for e in withdraw)
          and tuple(manifest["selector"]) == SEL and sorted(manifest["exclusion_reasons"]) == sorted(wd.REASONS)
          and tuple(manifest["products"]) == wd.ADOBE_PRODUCTS == (READER, PREMIERE)
          and {ident(e) for e in withdraw} == grant and set(wd.PRODUCT_GRANTS) == {READER, PREMIERE}
          and {short(dict(zip(SEL, g))) for g in grant} == set(WITHDRAW),
          str(sorted(short(dict(zip(SEL, g))) for g in grant)))
    check("A4 every row carries two blind INCORRECT labels from two different named reviewers that both support its "
          "reason (the suite's reading and the tool's agree); the first audit is provenance only; each row its own "
          "packet case",
          all(two_blind(e) and wd._two_blind_labels(e) and str(e.get("basis") or "").strip() for e in withdraw)
          and len({e["adjudication"]["second_blind"]["case"] for e in withdraw}) == 2,
          str([e["id"][-30:] for e in withdraw if not two_blind(e)]))
    stay = {short(r) for r in manifest.get("must_stay_counted", [])}
    found = {short(r) for h in manifest.get("findings_not_withdrawn", []) for r in h["rows"]}
    entries = {short(e) for e in manifest["entries"]}
    check("A5 the two must-stay controls and the control finding are listed (the finding with a reason) and are not "
          "entries; nothing is held out",
          stay == MUST_STAY and found == FINDING and manifest.get("held_out") == []
          and all(str(h.get("why") or "").strip() for h in manifest["findings_not_withdrawn"])
          and not (entries & (MUST_STAY | FINDING | CONTROLS)))
    prior_ids, prior_reports = set(), set()
    for name in PRIOR.values():
        doc = json.loads((AUDIT / name).read_text(encoding="utf-8"))
        prior_ids |= {ident(e) for e in doc["entries"]}
        prior_reports |= {short(e) for e in doc["entries"]}
    check("A6 no row (by five-field identity, or by page and report) is shared with AUX-072's, AUX-079's, AUX-088's, "
          "AUX-090's, AUX-098's, AUX-108's or AUX-110's manifest",
          not (prior_ids & {ident(e) for e in withdraw}) and not (prior_reports & entries))
    packet = manifest.get("adjudication_packet") or {}
    check("A7 each row pins its record; the manifest records the blind packet, its brief, the control rule and both "
          "label files by hash, with 8 items and 6 controls",
          all(str(e.get("record_file") or "").endswith(".md") for e in withdraw)
          and {k: packet.get(k) for k in PACKET_HASHES} == PACKET_HASHES
          and packet.get("items") == 8 and packet.get("controls") == 6, json.dumps(packet)[:300])
    accepted = reader_refusal(manifest)
    check("A8 the tool's own manifest checks accept it (scope, grant, selector, closed reasons, labels, basis)",
          accepted == "" and wd.manifest_scope(manifest) == wd.ADOBE_PRODUCTS, accepted)
    run_audit = json.loads(RUN_AUDIT.read_text(encoding="utf-8"))
    deltas = {(p["product_id"], p["update_version"], p["target_build"]): p["before"] - p["after"]
              for p in run_audit.get("per_patch") or []}
    check("A9 the committed run audit is this manifest's run: written, two withdrawn at the pinned parent, the "
          "manifest's hash, each page losing exactly its withdrawn row, no row newly counted, the three scoped "
          "writers ok",
          run_audit.get("written") is True and run_audit.get("withdrawn_now") == 2
          and run_audit.get("parent_commit") == manifest.get("parent_commit") == PARENT
          and run_audit.get("manifest_sha256") == sha(MANIFEST.read_bytes())
          and run_audit.get("store_sha256_before") == manifest.get("store_sha256_at_pin")
          and deltas == {k: 1 for k in PER_PAGE} and run_audit.get("newly_counted_rows") == []
          and run_audit.get("product_scope") == [READER, PREMIERE]
          and [w["command"] for w in run_audit.get("writers") or []] == [" ".join(w) for w in wd.writers_for(wd.ADOBE_PRODUCTS)]
          and all(w["returncode"] == 0 for w in run_audit.get("writers") or []),
          json.dumps({k: run_audit.get(k) for k in ("written", "withdrawn_now", "parent_commit")}))

    print("B  dry run, as the bare script")
    with tempfile.TemporaryDirectory(prefix="aux111-dry-") as tmp:
        store, generated, man = make_tree(Path(tmp))
        before = store.read_bytes()
        proc = run_tool(store, generated, man)
        out = proc.stdout
        check("B1 a dry run exits 0 and writes nothing", proc.returncode == 0 and store.read_bytes() == before,
              proc.stdout[-400:] + proc.stderr[-400:])
        check("B2 it plans exactly the two", out.count("[withdraw ") == 2 and "rows withdrawn by this run: 2" in out
              and "[kept " not in out, out[-600:])

    print("C  the write")
    with tempfile.TemporaryDirectory(prefix="aux111-write-") as tmp:
        store, generated, man = make_tree(Path(tmp))
        before_bytes = store.read_bytes()
        audit_path = Path(tmp) / "audit.json"
        p3 = run_tool(store, generated, man, "--write", "--confirm-write", "--audit", str(audit_path),
                      "--parent-commit", "e" * 40)
        check("C1 --write --confirm-write withdraws the two and says so",
              p3.returncode == 0 and "WROTE" in p3.stdout and "rows withdrawn by this run: 2" in p3.stdout,
              p3.stdout[-500:] + p3.stderr[-500:])
        before_text, after_text = before_bytes.decode("utf-8"), store.read_bytes().decode("utf-8")
        a_lines, b_lines = before_text.split(NL), after_text.split(NL)
        changed = [(a, b) for a, b in zip(a_lines, b_lines) if a != b]
        expected = collections.Counter({("  counted: true", "  counted: false"): 2,
                                        ("  exclusion_reason: null", "  exclusion_reason: " + REASON): 2})
        check("C2 exactly 4 lines change, two per row, and no validity line is added",
              len(a_lines) == len(b_lines) and collections.Counter(changed) == expected and len(changed) == 4,
              f"{len(changed)} changed: {collections.Counter(changed)}")
        after_blocks, before_blocks = blocks_by_identity(after_text), blocks_by_identity(before_text)
        fman = json.loads(man.read_text(encoding="utf-8"))
        check("C3 every withdrawn block now hashes to its pinned after-value",
              all([sha(b) for b in after_blocks.get(ident(e), [])] == [e["block_sha256_after"]] for e in fman["entries"]))
        rows_b = [r for _lo, _hi, r in aux072.store_blocks(before_text)]
        rows_a = [r for _lo, _hi, r in aux072.store_blocks(after_text)]
        out_ids = {ident(e): e["exclusion_reason"] for e in withdraw}
        moved = [(o, n) for o, n in zip(rows_b, rows_a) if ident(o) in out_ids]
        check("C4 the two parse as withdrawn, every other field unchanged, no field added",
              len(moved) == 2 and all(n == dict(o, counted=False, exclusion_reason=out_ids[ident(o)]) for o, n in moved)
              and all(set(n) == set(o) for o, n in moved))
        others = [k for k in before_blocks if k not in out_ids]
        parsed_after = {ident(r): r for r in rows_a}
        kinds = collections.Counter(k[0] for k in others)
        check("C5 no row is added or removed; the must-stay rows, the controls, the finding, the same report on Acrobat "
              "Pro, an Acrobat Pro, a Photoshop and a DaVinci row are byte-identical and still count",
              len(rows_a) == len(rows_b) == 12 and len(others) == 10
              and kinds == {READER: 3, PREMIERE: 3, PRO: 2, PHOTOSHOP: 1, DAV: 1}
              and all(after_blocks.get(k) == before_blocks[k] for k in others)
              and all(parsed_after[k].get("counted") is True for k in others), str(kinds))
        check("C6 no row starts counting",
              {ident(r) for r in rows_a if r.get("counted") is True} <= {ident(r) for r in rows_b if r.get("counted") is True})
        check("C7 the evidence-loss guard reads it as an audited withdrawal, not a loss",
              el.losses_between(before_text, after_text) == [])
        deleted = before_text
        for e in withdraw:
            deleted = deleted.replace(before_blocks[ident(e)][0], "", 1)
        losses = el.losses_between(before_text, deleted)
        check("C8 control: the same rows deleted ARE evidence loss",
              len(losses) == 2 and all(x.code == el.REMOVED for x in losses), str([x.code for x in losses]))
        audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
        per_page = {(p["product_id"], p["update_version"], p["target_build"]): (p["before"], p["after"])
                    for p in audit.get("per_patch") or []}
        siblings = audit.get("same_report_rows_on_other_identities") or []
        check("C9 fixture counts: each page loses exactly its withdrawn row, each product's population falls by one, "
              "and the one same-report row on another identity (the Reader report re-stated on Acrobat Pro) is left "
              "untouched and counted",
              audit.get("written") is True and audit.get("withdrawn_now") == 2 and per_page == PER_PAGE
              and audit.get("counted_population") == POPULATION and audit.get("newly_counted_rows") == []
              and audit.get("store_sha256_before") == sha(before_bytes) and audit.get("store_sha256_after") == sha(after_text)
              and audit.get("product_scope") == [READER, PREMIERE] and audit.get("parent_commit") == "e" * 40
              and [short(s) for s in siblings] == [(PRO, "15.020.20039", "", "1510656")]
              and all(s["counted"] is True and s["unchanged"] is True for s in siblings),
              json.dumps({k: audit.get(k) for k in ("withdrawn_now", "counted_population", "per_patch")})[:600])

        print("D  idempotence")
        p4 = run_tool(store, generated, man, "--write", "--confirm-write")
        check("D1 a second run exits 0, writes nothing and reports the two as already withdrawn",
              p4.returncode == 0 and "nothing to write" in p4.stdout and store.read_bytes().decode("utf-8") == after_text
              and p4.stdout.count("[already_withdrawn") == 2, p4.stdout[-400:] + p4.stderr[-300:])

        print("R  re-admission: a scheduled collector that sees a withdrawn report again")
        # Both Adobe collectors persist through base.append_evidence_rows (patch_collectors/adobe_premiere.py and
        # adobe_acrobat_community.py). Its guard keys are built from EVERY stored row, counted or not, and a
        # withdrawal keeps the row, so the report's id and URL keys stay held.
        reseen, variants = [], []
        for o in rows_b:
            if ident(o) not in out_ids:
                continue
            again = dict(o, counted=True, exclusion_reason=None, captured_at="2026-12-01T00:00:00Z")
            reseen.append(again)
            variants.append(dict(again, id=o["id"] + "-recaptured", source_url=o["source_url"].upper() + "/"))
        pre = store.read_bytes()
        held_back: list[dict] = []
        added, _total, _all = wd_base.append_evidence_rows(reseen + variants, store, out_already_held=held_back)
        check("R1 re-seeing each withdrawn report (the same id and URL, or the same report under another URL "
              "spelling) adds nothing: all four are refused as already held and the store is byte-identical",
              added == 0 and store.read_bytes() == pre and len(held_back) == 4 and len(reseen) == len(variants) == 2,
              f"added={added} held={len(held_back)}")
        stored = {ident(r): r for _lo, _hi, r in aux072.store_blocks(store.read_bytes().decode("utf-8"))}
        check("R2 so each of the two is still withdrawn, with its reason, and nothing re-counts it",
              all(stored[k].get("counted") is False and stored[k].get("exclusion_reason") == reason
                  for k, reason in out_ids.items()))
        control_store = Path(tmp) / "control.yml"
        control_store.write_bytes(pre)
        fresh = dict(reseen[0], id=reseen[0]["id"] + "-a-different-report",
                     source_url=reseen[0]["source_url"].rstrip("/") + "-a-different-report-9999999")
        added_new, _t, _a = wd_base.append_evidence_rows([fresh], control_store)
        check("R3 control: a report the store does not hold IS appended (the guard is not refusing everything)",
              added_new == 1 and control_store.read_bytes() != pre)

    print("S  the scope guard: no unrelated Adobe product, no unlisted identity")
    base = fixture_manifest()
    t7, t8 = (PREMIERE, "26.2.2", "", "1656474"), (READER, "15.020.20039", "", "1510656")
    template = entry_of(base, t8)

    def with_entry(row_key: tuple[str, str, str, str], products: list[str] | None = None) -> dict:
        doc = copy.deepcopy(base)
        block, row = row_of(text, row_key)
        doc["entries"].append(as_entry(template, row, block))
        if products is not None:
            doc["products"] = products
        return doc

    twin, pro_row, photoshop = (PRO, "15.020.20039", "", "1510656"), next(
        short(r) for _lo, _hi, r in aux072.store_blocks(text) if r["product_id"] == PRO and "1510656" not in r["source_url"]), (
        PHOTOSHOP, "27.1", "", "0000001")
    unrelated = {"the same report re-stated on Acrobat Pro (same version)": twin, "an Acrobat Pro row": pro_row,
                 "a Photoshop row": photoshop}
    verdicts = {name: reader_refusal(with_entry(key)) for name, key in unrelated.items()}
    check("S1 the manifest reader refuses an unrelated Adobe product under the Adobe scope: "
          + "; ".join(unrelated),
          all("not a Acrobat Reader or Premiere Pro row" in v for v in verdicts.values()), str(verdicts))
    proc, same = refused("aux111-s1-", with_entry(twin))
    check("S1 and the bare script refuses the whole run and writes nothing (the Acrobat Pro twin)",
          proc.returncode == 1 and "not a Acrobat Reader or Premiere Pro row" in proc.stdout and same, proc.stdout[-300:])

    scopes = {"Acrobat Pro added": [READER, PREMIERE, PRO], "Photoshop added": [READER, PREMIERE, PHOTOSHOP],
              "Premiere alone": [PREMIERE], "Acrobat Reader alone": [READER], "the two reordered": [PREMIERE, READER],
              "the two plus DaVinci": [WIN, OBS, DAV, READER, PREMIERE]}
    verdicts = {}
    for name, products in scopes.items():
        doc = copy.deepcopy(base)
        doc["products"] = products
        verdicts[name] = reader_refusal(doc)
    check("S2 a scope that adds, drops or reorders a product refuses: " + "; ".join(scopes),
          all("product scope differs" in v for v in verdicts.values()), str(verdicts))
    proc, same = refused("aux111-s2-", dict(copy.deepcopy(base), products=[READER, PREMIERE, PRO]))
    check("S2 and the bare script refuses it and writes nothing",
          proc.returncode == 1 and "product scope differs" in proc.stdout and same, proc.stdout[-300:])

    unlisted = {"the must-stay row on the Premiere target's own page": (PREMIERE, "26.2.2", "", "1627000"),
                "the must-stay row on the Reader target's own page": (READER, "15.020.20039", "", "673695"),
                "a Premiere row on another page": (PREMIERE, "26.2", "", "1635805"),
                "the control finding": (READER, "15.010.20056", "", "594365")}
    verdicts = {name: reader_refusal(with_entry(key)) for name, key in unlisted.items()}
    check("S3 the manifest reader refuses an unlisted identity of a granted product, fully pinned and labelled: "
          + "; ".join(unlisted),
          all("not an identity this tool grants" in v for v in verdicts.values()), str(verdicts))
    proc, same = refused("aux111-s3-", with_entry((PREMIERE, "26.2.2", "", "1627000")))
    check("S3 and the bare script refuses the whole run and writes nothing (the must-stay row)",
          proc.returncode == 1 and "not an identity this tool grants" in proc.stdout and same, proc.stdout[-300:])

    variants = {}
    for field, value in (("product_id", PREMIERE), ("update_version", "15.020.20042"),
                         ("id", template["id"] + "-other"), ("source_url", template["source_url"] + "-other"),
                         ("target_build", "15.020.20039")):
        doc = copy.deepcopy(base)
        entry_of(doc, t8)[field] = value
        variants[field] = doc
    verdicts = {f: reader_refusal(doc) for f, doc in variants.items()}
    check("S4 a granted identity with any one field changed (product, version, id, URL, build) is not granted",
          all("not an identity this tool grants" in v for v in verdicts.values()), str(verdicts))

    block_p08, row_p08 = row_of(text, (PREMIERE, "26.2.2", "", "1627000"))
    p08_entry = as_entry(template, row_p08, block_p08)
    plan_verdicts = {"the Adobe scope": planner_refusal(text, copy.deepcopy(base["entries"]) + [p08_entry], wd.ADOBE_PRODUCTS),
                     "the DaVinci scope": planner_refusal(text, [copy.deepcopy(p08_entry)], wd.EXTENDED_PRODUCTS),
                     "no scope given": planner_refusal(text, [copy.deepcopy(p08_entry)], None)}
    check("S5 the planner refuses the same unlisted row on its own, under the Adobe scope, under another scope and "
          "with none (the grant is per product, not per declared scope)",
          all("not an identity this tool grants" in v for v in plan_verdicts.values()), str(plan_verdicts))
    check("S5 control: the planner plans the two granted rows",
          planner_refusal(text, copy.deepcopy(base["entries"]), wd.ADOBE_PRODUCTS) == "")
    legacy = {}
    for name, products in (("Windows and OBS", list(wd.PRODUCTS)), ("Windows, OBS and DaVinci", list(wd.EXTENDED_PRODUCTS))):
        doc = copy.deepcopy(base)
        doc["products"] = products
        legacy[name] = reader_refusal(doc)
    check("S5 the granted rows themselves are refused under the older scopes",
          "not a Windows or OBS row" in legacy["Windows and OBS"]
          and "not a Windows, OBS or DaVinci row" in legacy["Windows, OBS and DaVinci"], str(legacy))

    blind_cases = {}
    m = copy.deepcopy(base)
    entry_of(m, t7)["adjudication"]["third_blind"]["label"] = "CORRECT"
    blind_cases["a blind review saying CORRECT"] = m
    m = copy.deepcopy(base)
    entry_of(m, t7)["adjudication"].pop("third_blind")
    blind_cases["a missing second blind review"] = m
    m = copy.deepcopy(base)
    adj = entry_of(m, t7)["adjudication"]
    adj["third_blind"]["by"] = adj["second_blind"]["by"]
    blind_cases["one reviewer named twice"] = m
    m = copy.deepcopy(base)
    adj = entry_of(m, t7)["adjudication"]
    adj["third_blind"]["by"] = adj["first_audit"]["by"]
    blind_cases["the first audit standing in for a blind review"] = m
    m = copy.deepcopy(base)
    entry_of(m, t8)["adjudication"]["second_blind"]["reason_class"] = "not_a_real_issue_report"
    blind_cases["a reason only one blind review supports"] = m
    m = copy.deepcopy(base)
    entry_of(m, t7)["adjudication"]["third_blind"]["case"] = "P99"
    blind_cases["two different packet cases"] = m
    m = copy.deepcopy(base)
    entry_of(m, t7)["adjudication"]["third_blind"]["reason"] = " "
    blind_cases["a blind review with no reason"] = m
    verdicts = {name: reader_refusal(doc) for name, doc in blind_cases.items()}
    check("S6 the tool itself refuses a granted row without two blind INCORRECT labels: " + "; ".join(blind_cases),
          all("granted row lacks two blind INCORRECT labels" in v for v in verdicts.values())
          and not any(two_blind(entry_of(doc, t7)) and two_blind(entry_of(doc, t8)) for doc in blind_cases.values()),
          str(verdicts))

    prior_ok = {name: reader_refusal(json.loads((AUDIT / name).read_text(encoding="utf-8")))
                for name in ("live_citation_withdrawal.json", "live_citation_withdrawal_v2.json",
                             "live_citation_withdrawal_v3.json", "live_citation_withdrawal_v4.json")}
    check("S7 the older scopes are unchanged: their products and writers, no grant on any of their products, and the "
          "four earlier manifests still accepted",
          wd.PRODUCTS == (WIN, OBS) and wd.EXTENDED_PRODUCTS == (WIN, OBS, DAV)
          and set(wd.SCOPES) == {wd.PRODUCTS, wd.EXTENDED_PRODUCTS, wd.ADOBE_PRODUCTS}
          and wd.WRITERS == wd.writers_for(wd.PRODUCTS) and not (set(wd.PRODUCT_GRANTS) & set(wd.EXTENDED_PRODUCTS))
          and all(v == "" for v in prior_ok.values()), str(prior_ok))

    print("F  writers")
    expected_writers = (
        ("build_consensus_from_evidence.py", "--product-id", READER, "--product-id", PREMIERE, "--reconcile-only"),
        ("apply_consensus_to_records.py", "--product-id", READER, "--write-all", "--confirm-write"),
        ("apply_consensus_to_records.py", "--product-id", PREMIERE, "--write-all", "--confirm-write"),
    )
    seen: list[tuple] = []
    saved = (wd.STORE, wd.GENERATED, wd.regenerate)
    try:
        with tempfile.TemporaryDirectory(prefix="aux111-f1-") as tmp:
            store, generated, man = make_tree(Path(tmp))
            wd.STORE, wd.GENERATED = store, generated
            wd.regenerate = lambda w=None: (seen.append(tuple(w)) or [])
            rc = wd.main(["--manifest", str(man), "--baseline", str(Path(tmp) / "none.json"),
                          "--write", "--confirm-write", "--regenerate"])
            seen.append(("rc", rc))
    finally:
        wd.STORE, wd.GENERATED, wd.regenerate = saved
    lane = workflow_promotions()
    check("F1 --regenerate runs the reconcile scoped to the two products and each product's own scoped promotion; "
          "nothing unscoped",
          seen == [expected_writers, ("rc", 0)] and all(w.count("--product-id") >= 1 for w in expected_writers),
          str(seen)[:400])
    check("F2 both promotions are the scheduled lane's own steps for these products",
          READER in lane and PREMIERE in lane, str(lane))

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
    stay_rows = [r for r in live_parsed.values() if short(r) in MUST_STAY | FINDING]
    check("G2 the two must-stay rows and the control finding are each stored once and still count",
          len(stay_rows) == 3 and all(r.get("counted") is True for r in stay_rows)
          and all(len(live_rows[ident(r)]) == 1 for r in stay_rows),
          str([(short(r), r.get("counted")) for r in stay_rows]))
    live_after = {str(p): sha(p.read_bytes()) for p in live_files if p.exists()}
    check("G3 the live store and the two records are byte-identical after the suite",
          live_after == live_before and len(live_before) == 3, f"{len(live_before)} files")

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
