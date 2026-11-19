#!/usr/bin/env python3
"""The audited re-admission of two Acrobat Reader rows the role veto withdrew wrongly (AUX-110).

`readmit_adjudicated_rows.py` re-admits the two stored Reader rows (18.009.20044 / thread 1511973 and
19.021.20047 / thread 1518668) that the shipped veto stored as `version_named_but_working` and that two fresh
blind adjudicators BOTH labelled CORRECT, and `recompute_evidence_classification.py --correction-manifest`
corrects the theme one of them carries. Their contract, pinned here:

  A  the committed manifests: exactly those two rows by their full five-field identity, Reader only, the
     closed from-vocabulary (`version_named_but_working`), two CORRECT labels from two different named
     adjudicators per row, the packet and brief pinned, the held third row held, no row shared with any
     withdrawal manifest, and one recorded successor (the label correction) on 1511973 only
  B  a dry run (the default) plans the two and writes nothing
  C  --write needs --confirm-write; the write changes exactly 4 lines, keeps every row, moves only counted and
     exclusion_reason, starts exactly the two counting, leaves the sibling and the held row byte-identical, and
     the evidence-loss guard reads nothing as lost
  D  idempotence: a second run, the label correction, and a run after it change nothing more; the successor is
     what lets the corrected block read as already re-admitted
  E  duplicate prevention and every unsafe input refuse the WHOLE run and write nothing
  F  the writers are the two scoped Reader commands, never anything unscoped
  G  auditability: the run audit names the manifest, the store before and after, the labels and the deltas, and
     the committed audits agree with the committed manifests
  H  the committed store holds the two re-admitted and corrected, and on stored text the shipped veto refuses
     exactly the manifest's rows among all counted Acrobat rows (the manifest is the exemption list)
  I  writeback stability: a rediscovery is never appended, and a collector may not modify a re-admitted row
  J  the pinned label correction refuses anything but the shipped classifier's own answer

The tools run as BARE scripts, so B-E and J run them as subprocesses exactly as an operator would. Offline:
tests/fixtures/acrobat_readmit/store.yml holds the six stored Reader rows involved, serialised as the store
serialises them, with the free-text fields replaced by synthetic marker text. Because that text differs from
the store, the suite re-pins the committed manifest's block hashes on the fixture with its OWN line edits.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_readmit_adjudicated_rows.py
"""
from __future__ import annotations

import copy
import glob
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

import readmit_adjudicated_rows as ra  # noqa: E402
import withdraw_windows_identity_not_the_subject_rows as aux072  # noqa: E402
from lib import collector_ownership, evidence_loss  # noqa: E402
from lib.target_outcome import target_is_contradicted  # noqa: E402
from patch_collectors import base  # noqa: E402

TOOL = SCRIPTS / "readmit_adjudicated_rows.py"
RECOMPUTE = SCRIPTS / "recompute_evidence_classification.py"
MANIFEST = SCRIPTS / "audit" / "acrobat_reader_readmission.json"
CORRECTION = SCRIPTS / "audit" / "acrobat_reader_label_correction.json"
RUN_AUDIT = SCRIPTS / "audit" / "acrobat_reader_readmission_2026-11-19.json"
CORRECTION_AUDIT = SCRIPTS / "audit" / "acrobat_reader_label_correction_2026-11-19.json"
STORE = ROOT / "_data" / "consensus_evidence.yml"
STORE_FIXTURE = SCRIPTS / "tests" / "fixtures" / "acrobat_readmit" / "store.yml"
NL = chr(10)
SEL = ("product_id", "update_version", "target_build", "id", "source_url")
READER, PRO = "adobe-acrobat-reader", "adobe-acrobat-pro"
WORK, ROLL, MULTI = ("version_named_but_working", "version_named_but_rollback_target",
                     "multiple_builds_named_target_not_blamed")

# The two rows both fresh adjudicators labelled CORRECT, written out so the manifest cannot redefine them:
# (update_version, thread) -> (stored reason, record file).
READMIT = {
    ("18.009.20044", "1511973"): (WORK, "2017-11-14-adobe-acrobat-reader-18-009-20044.md"),
    ("19.021.20047", "1518668"): (WORK, "2019-10-15-adobe-acrobat-reader-19-021-20047.md"),
}
HELD = ("25.001.21111", "1548715")            # 2/2 CORRECT but its gate's trigger is past the stored cut
SIBLING = ("19.012.20040", "1518668")          # same thread, the build users went FROM: the veto was right
PACKET_SHA = "2c0af039f8bda9bf1a972cbcdb13c780200381257eaf8fa9866f251a41aab02c"
BRIEF_SHA = "907c9024939701e5162ddae1d34d69b2ce6e6c608233c4d507366f3f9e57f359"
FROM_LABELS = {"issue_theme": "install/update failure", "workflow_area": "deployment", "severity": "high"}
TO_LABELS = {"issue_theme": "unspecified Acrobat issue", "workflow_area": "Acrobat workflow", "severity": "medium"}
RECORD_VERSIONS = {"18.009.20044": "2017-11-14-adobe-acrobat-reader-18-009-20044.md",
                   "19.012.20040": "2019-07-02-adobe-acrobat-reader-19-012-20040.md",
                   "19.021.20047": "2019-10-15-adobe-acrobat-reader-19-021-20047.md",
                   "25.001.21111": "2026-01-20-adobe-acrobat-reader-25-001-21111.md"}

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


def thread(url: str) -> str:
    return str(url or "").rstrip("/").rsplit("-", 1)[-1]


def short(row: dict) -> tuple[str, str]:
    return str(row.get("update_version") or ""), thread(str(row.get("source_url") or ""))


def ident(row: dict) -> tuple[str, ...]:
    """The suite's own five-field identity, so a broken selector in the tool fails a check, not the suite."""
    return tuple(str(row.get(key) or "") for key in SEL)


def own_readmit(block: str, reason: str) -> str:
    """The suite's own re-admission edit, independent of the tool's."""
    for old, new in (("  counted: false", "  counted: true"), ("  exclusion_reason: " + reason, "  exclusion_reason: null")):
        assert block.count(NL + old + NL) == 1, (old, block[:120])
        block = block.replace(NL + old + NL, NL + new + NL, 1)
    return block


def own_relabel(block: str, frm: dict, to: dict) -> str:
    """The suite's own label edit, independent of the tool's single write site."""
    for key in ("issue_theme", "workflow_area", "severity"):
        old, new = f"  {key}: {frm[key]}", f"  {key}: {to[key]}"
        assert block.count(NL + old + NL) == 1, (old, block[:120])
        block = block.replace(NL + old + NL, NL + new + NL, 1)
    return block


def fixture_text() -> str:
    return STORE_FIXTURE.read_bytes().decode("utf-8")


def manifest_doc() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def correction_doc() -> dict:
    return json.loads(CORRECTION.read_text(encoding="utf-8"))


def blocks_by_identity(text: str) -> dict[tuple[str, ...], list[str]]:
    out: dict[tuple[str, ...], list[str]] = {}
    for lo, hi, row in aux072.store_blocks(text):
        out.setdefault(ident(row), []).append(text[lo:hi])
    return out


def block_of(text: str, key: tuple[str, str]) -> str:
    hits = [text[lo:hi] for lo, hi, row in aux072.store_blocks(text)
            if row.get("product_id") == READER and short(row) == key]
    assert len(hits) == 1, (key, len(hits))
    return hits[0]


def fixture_manifest(text: str | None = None) -> dict:
    """The committed manifest with its block hashes (and the successor) re-pinned on the fixture by the
    suite's own edits."""
    doc = manifest_doc()
    blocks = blocks_by_identity(text if text is not None else fixture_text())
    for entry in doc["entries"]:
        hits = blocks.get(ident(entry), [])
        if len(hits) != 1:
            continue
        after = own_readmit(hits[0], entry["exclusion_reason_before"])
        entry["block_sha256_before"], entry["block_sha256_after"] = sha(hits[0]), sha(after)
        for step in entry.get("successors") or []:
            step["block_sha256_from"] = sha(after)
            step["block_sha256_to"] = sha(own_relabel(after, FROM_LABELS, TO_LABELS))
    return doc


def make_tree(tmp: Path, store_text: str | None = None, manifest: dict | None = None,
              versions: dict | None = None) -> tuple[Path, Path, Path]:
    store = tmp / "consensus_evidence.yml"
    store.write_bytes((store_text if store_text is not None else fixture_text()).encode("utf-8"))
    generated = tmp / "generated"
    generated.mkdir()
    for version, name in (versions if versions is not None else RECORD_VERSIONS).items():
        front = yaml.safe_dump({"product_id": READER, "update_version": version, "update_entry": True}, sort_keys=False)
        (generated / name).write_bytes(("---" + NL + front + "---" + NL).encode("utf-8"))
    man = tmp / "manifest.json"
    man.write_text(json.dumps(manifest if manifest is not None else fixture_manifest(store_text)), encoding="utf-8")
    return store, generated, man


def _env() -> dict:
    return dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def run_tool(store: Path, generated: Path, manifest: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), "--store", str(store), "--generated-dir", str(generated),
                           "--manifest", str(manifest), *args],
                          capture_output=True, text=True, encoding="utf-8", env=_env(), cwd=str(SCRIPTS))


def run_correction(store: Path, manifest: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(RECOMPUTE), "--store", str(store), "--correction-manifest",
                           str(manifest), *args],
                          capture_output=True, text=True, encoding="utf-8", env=_env(), cwd=str(SCRIPTS))


def changed_lines(a: str, b: str) -> list[int]:
    la, lb = a.split(NL), b.split(NL)
    return [i for i, (x, y) in enumerate(zip(la, lb)) if x != y] + ([-1] if len(la) != len(lb) else [])


def joined_text(row: dict) -> str:
    """The collector's own join of the stored text fields (one copy of each distinct part)."""
    seen, parts = set(), []
    for field in ("parent_title", "report_title", "report_text_excerpt"):
        value = str(row.get(field) or "").strip()
        key = " ".join(value.lower().split())
        if value and key not in seen:
            seen.add(key)
            parts.append(value)
    return " ".join(parts)


def refuses(text: str, manifest: dict, expect: str, *extra: str, versions: dict | None = None) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="aux110-e-") as tmp:
        store, generated, man = make_tree(Path(tmp), text, manifest, versions)
        proc = run_tool(store, generated, man, "--write", "--confirm-write", *extra)
        unchanged = store.read_bytes() == text.encode("utf-8")
    return (proc.returncode == 1 and expect in proc.stdout and "REFUSED, nothing written" in proc.stdout
            and unchanged), proc.stdout[-300:]


def run() -> int:  # noqa: PLR0915
    text = fixture_text()
    doc = manifest_doc()
    cdoc = correction_doc()

    print("A. the committed manifests")
    entries = doc["entries"]
    check("A1 the manifest selects by the five-field identity, Acrobat Reader only, from version_named_but_working only",
          doc.get("selector") == list(SEL) and doc.get("products") == [READER]
          and doc.get("readmit_from_reasons") == [WORK], json.dumps({k: doc.get(k) for k in ("selector", "products")}))
    got = {short(e): (e["exclusion_reason_before"], e["record_file"]) for e in entries}
    check("A2 exactly the two rows both fresh adjudicators labelled CORRECT, each with its stored reason and record",
          got == READMIT and len(entries) == 2 and all(e["target_build"] == "" for e in entries), json.dumps(sorted(got)))
    labels_ok = all(len(e["labels"]) == 2 and {x["label"] for x in e["labels"]} == {"CORRECT"}
                    and len({x["by"] for x in e["labels"]}) == 2 and len({x["packet_id"] for x in e["labels"]}) == 1
                    and all(str(x["reason"]).strip() for x in e["labels"]) for e in entries)
    check("A3 every row carries two CORRECT labels with reasons from two different named adjudicators on one packet entry",
          labels_ok and all(ra._two_correct_labels(e) for e in entries))
    adj = doc["adjudication"]
    check("A4 the adjudication pins the fresh packet and brief, states the both-CORRECT gate and a stored-text, "
          "no-named-row basis",
          adj.get("packet_sha256") == PACKET_SHA and adj.get("brief_sha256") == BRIEF_SHA
          and "BOTH" in adj.get("gate", "") and "Stored text only" in adj.get("basis", "")
          and "names no row" in adj.get("basis", ""), json.dumps(adj)[:300])
    held = [short(h) for h in doc.get("held") or []]
    check("A5 the third row is held, not an entry",
          held == [HELD] and HELD not in got and all(str(h.get("why") or "").strip() for h in doc["held"]))
    withdrawn: set[tuple[str, ...]] = set()
    for path in glob.glob(str(SCRIPTS / "audit" / "*withdrawal*.json")):
        other = json.loads(Path(path).read_text(encoding="utf-8"))
        for e in other.get("entries") or []:
            withdrawn.add(ident(e))
    check("A6 no re-admitted row is a row of any withdrawal manifest",
          withdrawn and not (withdrawn & {ident(e) for e in entries}), str(len(withdrawn)))
    succ = {short(e): e.get("successors") or [] for e in entries}
    step = (succ.get(("18.009.20044", "1511973")) or [{}])[0]
    check("A7 one recorded successor, on 1511973 only: the label correction, chained from the after-pin",
          len(succ[("18.009.20044", "1511973")]) == 1 and succ[("19.021.20047", "1518668")] == []
          and step.get("block_sha256_from") == entries[0]["block_sha256_after"]
          and "--correction-manifest" in step.get("changed_by", "")
          and "acrobat_reader_label_correction.json" in step.get("changed_by", "")
          and step.get("change") == {k: [FROM_LABELS[k], TO_LABELS[k]] for k in FROM_LABELS}, json.dumps(step)[:300])
    check("A8 the tool's own scope: Reader, one from-reason, two scoped writers",
          ra.PRODUCT == READER and ra.FROM_REASONS == frozenset({WORK}) and ra.WRITERS == (
              ("build_consensus_from_evidence.py", "--product-id", READER, "--reconcile-only"),
              ("apply_consensus_to_records.py", "--product-id", READER, "--write-all", "--confirm-write")))
    centry = cdoc["entries"]
    check("A9 the correction manifest names only 1511973, moves theme, area and severity only, from the stored "
          "labels to the shipped answer",
          len(centry) == 1 and ident(centry[0]) == ident(entries[0]) and sorted(cdoc["fields"]) == sorted(FROM_LABELS)
          and centry[0]["from"] == FROM_LABELS and centry[0]["to"] == TO_LABELS
          and str(centry[0].get("basis") or "").strip() and str(centry[0].get("authorized_by") or "").strip())

    print("B. dry run")
    with tempfile.TemporaryDirectory(prefix="aux110-b-") as tmp:
        store, generated, man = make_tree(Path(tmp))
        proc = run_tool(store, generated, man)
        unchanged = store.read_bytes() == text.encode("utf-8")
    check("B1 the default is a dry run: two planned, nothing written",
          proc.returncode == 0 and proc.stdout.count("[readmit") == 2 and "dry run" in proc.stdout and unchanged,
          proc.stdout[-300:] + proc.stderr[-300:])
    check("B2 the dry run reports one more counted report on each of the two patches",
          "18.009.20044: 1 -> 2" in proc.stdout and "19.021.20047: 1 -> 2" in proc.stdout, proc.stdout[-300:])

    print("C. write")
    with tempfile.TemporaryDirectory(prefix="aux110-c-") as tmp:
        store, generated, man = make_tree(Path(tmp))
        half = run_tool(store, generated, man, "--write")
        half2 = run_tool(store, generated, man, "--confirm-write")
        still = store.read_bytes() == text.encode("utf-8")
        proc = run_tool(store, generated, man, "--write", "--confirm-write")
        after = store.read_bytes().decode("utf-8")
    check("C1 --write and --confirm-write are needed together (usage error, nothing written)",
          half.returncode == 2 and half2.returncode == 2 and still)
    lines = changed_lines(text, after)
    check("C2 the write changes exactly 4 lines and keeps the line count",
          proc.returncode == 0 and "WROTE" in proc.stdout and len(lines) == 4 and -1 not in lines, f"{lines} {proc.stdout[-200:]}")
    rows_b, rows_a = yaml.safe_load(text)["evidence"], yaml.safe_load(after)["evidence"]
    moved = []
    for old, new in zip(rows_b, rows_a):
        diff = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
        if diff:
            moved.append((short(old), diff, new.get("counted"), new.get("exclusion_reason")))
    check("C3 only counted and exclusion_reason move, only on the two rows, and every row is kept",
          len(rows_a) == len(rows_b) and sorted(m[0] for m in moved) == sorted(READMIT)
          and all(m[1] == ["counted", "exclusion_reason"] and m[2] is True and m[3] is None for m in moved), str(moved))
    check("C4 the sibling 19.012.20040 row of thread 1518668 and the held row stay byte-identical and withdrawn",
          block_of(after, SIBLING) == block_of(text, SIBLING) and block_of(after, HELD) == block_of(text, HELD)
          and "  counted: false" in block_of(after, SIBLING) and ROLL in block_of(after, SIBLING)
          and MULTI in block_of(after, HELD))
    removed = after.replace(block_of(after, ("19.021.20047", "1518668")), "")
    check("C5 the evidence-loss guard reads the re-admission as no loss, and still sees a deleted re-admitted row",
          evidence_loss.losses_between(text, after) == [] and len(evidence_loss.losses_between(after, removed)) == 1)
    counted_b = {short(r) for r in rows_b if r.get("counted") is True}
    counted_a = {short(r) for r in rows_a if r.get("counted") is True}
    check("C6 exactly the two named rows start counting, and none stops", counted_a - counted_b == set(READMIT)
          and not counted_b - counted_a)
    fm = fixture_manifest()
    check("C7 each re-admitted block is the pinned after-block",
          all(sha(block_of(after, short(e))) == e["block_sha256_after"] for e in fm["entries"]))

    print("D. idempotence and the later audited change")
    with tempfile.TemporaryDirectory(prefix="aux110-d-") as tmp:
        store, generated, man = make_tree(Path(tmp))
        run_tool(store, generated, man, "--write", "--confirm-write")
        once = store.read_bytes()
        again = run_tool(store, generated, man, "--write", "--confirm-write")
        twice = store.read_bytes()
        cman = Path(tmp) / "correction.json"
        cman.write_text(json.dumps(cdoc), encoding="utf-8")
        cdry = run_correction(store, cman)
        cdry_same = store.read_bytes() == twice
        cwrite = run_correction(store, cman, "--write")
        corrected = store.read_bytes().decode("utf-8")
        after_corr = run_tool(store, generated, man, "--write", "--confirm-write")
        still_corrected = store.read_bytes().decode("utf-8") == corrected
        crerun = run_correction(store, cman, "--write")
        crerun_same = store.read_bytes().decode("utf-8") == corrected
        no_succ = copy.deepcopy(fixture_manifest())
        for e in no_succ["entries"]:
            e.pop("successors", None)
        man2 = Path(tmp) / "nosucc.json"
        man2.write_text(json.dumps(no_succ), encoding="utf-8")
        without = run_tool(store, generated, man2, "--write", "--confirm-write")
    check("D1 a second run changes nothing: both already re-admitted",
          again.returncode == 0 and once == twice and again.stdout.count("[already_readmitted") == 2
          and "nothing to write (idempotent)" in again.stdout, again.stdout[-300:])
    dry = json.loads(cdry.stdout) if cdry.returncode == 0 else {}
    check("D2 the label correction's dry run plans one correction and writes nothing",
          cdry.returncode == 0 and cdry_same and [c["action"] for c in dry.get("corrections", [])] == ["correct"]
          and dry.get("written") is False, cdry.stdout[-300:] + cdry.stderr[-300:])
    corr_lines = changed_lines(twice.decode("utf-8"), corrected)
    rows_c = yaml.safe_load(corrected)["evidence"]
    target_c = [r for r in rows_c if short(r) == ("18.009.20044", "1511973")][0]
    target_t = [r for r in yaml.safe_load(twice.decode("utf-8"))["evidence"] if short(r) == ("18.009.20044", "1511973")][0]
    others_same = all(a == b for a, b in zip(yaml.safe_load(twice.decode("utf-8"))["evidence"], rows_c)
                      if short(a) != ("18.009.20044", "1511973"))
    check("D3 the correction writes exactly 3 lines in 1511973's block: theme, area and severity; counted, "
          "platform, sentiment and every other row unchanged",
          cwrite.returncode == 0 and len(corr_lines) == 3 and others_same
          and {k: target_c[k] for k in TO_LABELS} == TO_LABELS
          and dict(target_c, **FROM_LABELS) == target_t and target_c["counted"] is True, f"{corr_lines} {cwrite.stderr[-200:]}")
    check("D4 after the correction the re-admit tool reads the block as already re-admitted (via the successor)",
          after_corr.returncode == 0 and after_corr.stdout.count("[already_readmitted") == 2 and still_corrected,
          after_corr.stdout[-300:])
    rerun = json.loads(crerun.stdout) if crerun.returncode == 0 else {}
    check("D5 a second correction run is already corrected and writes nothing",
          crerun_same and [c["action"] for c in rerun.get("corrections", [])] == ["already_corrected"]
          and rerun.get("written") is False)
    check("D6 without the recorded successor the corrected block refuses: the successor is load-bearing",
          without.returncode == 1 and "block changed since the manifest was pinned" in without.stdout, without.stdout[-300:])

    print("E. duplicate prevention and refusals (each refuses the whole run, nothing written)")
    base_doc = fixture_manifest()

    def mutate(fn) -> dict:
        d = copy.deepcopy(base_doc)
        fn(d)
        return d

    def set_entry(d: dict, i: int, **kv) -> None:
        d["entries"][i].update(kv)

    target_a = block_of(text, ("18.009.20044", "1511973"))
    pro_block = target_a.replace("  product_id: adobe-acrobat-reader", "  product_id: adobe-acrobat-pro", 1)
    pro_text = text + pro_block
    ok, out = refuses(pro_text, mutate(lambda d: set_entry(d, 0, product_id=PRO, block_sha256_before=sha(pro_block),
                                                       block_sha256_after=sha(own_readmit(pro_block, WORK)))),
                      "not an Acrobat Reader row")
    check("E1 an Acrobat Pro row refuses", ok, out)
    held_block = block_of(text, HELD)
    held_row = [r for r in yaml.safe_load(text)["evidence"] if short(r) == HELD][0]

    def as_held(d: dict, reason: str, drop_held: bool) -> None:
        d["entries"][1].update({k: held_row[k] if k in held_row else "" for k in SEL})
        d["entries"][1].update(exclusion_reason_before=reason, record_file=RECORD_VERSIONS["25.001.21111"],
                               block_sha256_before=sha(held_block), successors=[])
        d["entries"][1]["block_sha256_after"] = sha(own_readmit(held_block, MULTI))
        if drop_held:
            d["held"] = []

    ok, out = refuses(text, mutate(lambda d: as_held(d, MULTI, True)), "outside the closed from-vocabulary")
    check("E2 the held row's own reason (several builds named) is outside the from-vocabulary", ok, out)
    sib_block = block_of(text, SIBLING)
    sib_row = [r for r in yaml.safe_load(text)["evidence"] if short(r) == SIBLING][0]

    def as_sibling(d: dict) -> None:
        d["entries"][1].update({k: sib_row[k] if k in sib_row else "" for k in SEL})
        d["entries"][1].update(exclusion_reason_before=ROLL, record_file=RECORD_VERSIONS["19.012.20040"],
                               block_sha256_before=sha(sib_block), block_sha256_after=sha(own_readmit(sib_block, ROLL)))

    ok, out = refuses(text, mutate(as_sibling), "outside the closed from-vocabulary")
    check("E3 a rollback-target row is outside the from-vocabulary", ok, out)
    ok, out = refuses(text, mutate(lambda d: as_held(d, WORK, False)), "a held row is named as an entry")
    check("E4 the held row named as an entry refuses even with an admissible reason", ok, out)
    swapped = text.replace(target_a, target_a.replace("  exclusion_reason: " + WORK, "  exclusion_reason: " + ROLL, 1))
    swapped_block = block_of(swapped, ("18.009.20044", "1511973"))
    ok, out = refuses(swapped, mutate(lambda d: set_entry(d, 0, block_sha256_before=sha(swapped_block))),
                      "stored state is not the pinned withdrawal")
    check("E5 a stored reason other than the pinned one refuses", ok, out)
    for name, fn, expect in (
            ("E6 one label refuses", lambda d: d["entries"][0]["labels"].pop(), "two CORRECT labels"),
            ("E7 an UNSURE label refuses", lambda d: d["entries"][0]["labels"][1].update(label="UNSURE"), "two CORRECT labels"),
            ("E8 an INCORRECT label refuses", lambda d: d["entries"][1]["labels"][0].update(label="INCORRECT"), "two CORRECT labels"),
            ("E9 two labels from one adjudicator refuse",
             lambda d: d["entries"][0]["labels"][1].update(by=d["entries"][0]["labels"][0]["by"]), "two CORRECT labels"),
            ("E10 labels on two different packet entries refuse",
             lambda d: d["entries"][0]["labels"][1].update(packet_id="R99"), "two CORRECT labels"),
            ("E11 a label without a reason refuses", lambda d: d["entries"][1]["labels"][1].update(reason=" "), "two CORRECT labels"),
            ("E12 an identity listed twice refuses", lambda d: d["entries"].append(copy.deepcopy(d["entries"][0])),
             "identity listed twice"),
            ("E13 a widened from-vocabulary refuses", lambda d: d.update(readmit_from_reasons=[WORK, ROLL]),
             "from-reasons differ"),
            ("E14 a widened product scope refuses", lambda d: d.update(products=[READER, PRO]), "product scope differs"),
            ("E15 a changed selector refuses", lambda d: d.update(selector=["product_id", "update_version", "source_url"]),
             "not the five-field identity"),
            ("E16 an unpinned packet refuses", lambda d: d["adjudication"].update(packet_sha256=""), "does not pin its packet"),
            ("E17 a target_build on a Reader entry refuses", lambda d: set_entry(d, 0, target_build="1"),
             "lacks part of the five-field identity"),
            ("E18 a wrong after-pin refuses", lambda d: set_entry(d, 1, block_sha256_after="0" * 64),
             "does not produce the pinned block"),
            ("E19 a moved before-pin refuses", lambda d: set_entry(d, 1, block_sha256_before="0" * 64),
             "block changed since the manifest was pinned"),
            ("E20 a successor not chained from the after-pin refuses",
             lambda d: d["entries"][0]["successors"][0].update(block_sha256_from="1" * 64), "does not continue the chain"),
            ("E21 a successor that does not name its tool refuses",
             lambda d: d["entries"][0]["successors"][0].update(changed_by=""), "does not name its change"),
            ("E22 a wrong pinned record refuses", lambda d: set_entry(d, 0, record_file="2017-11-14-other.md"),
             "not the pinned"),
    ):
        ok, out = refuses(text, mutate(fn), expect)
        check(name, ok, out)
    edited = text.replace(target_a, target_a.replace("Synthetic marker text", "Synthetic marker texts", 1))
    ok, out = refuses(edited, base_doc, "block changed since the manifest was pinned")
    check("E23 a block whose text moved since the pin refuses", ok, out)
    ok, out = refuses(text + target_a, base_doc, "2 blocks match the five-field identity")
    check("E24 two stored blocks with one identity refuse", ok, out)
    # Another counted row of the SAME report on the same patch (a re-post stored under another id).
    target_url = [r for r in yaml.safe_load(text)["evidence"] if short(r) == ("18.009.20044", "1511973")][0]["source_url"]
    twin_lines = block_of(text, ("18.009.20044", "1512140")).split(NL)
    twin_lines = ["- id: acrobat-18-009-20044-fixture-repost-of-1511973" if i == 0 else
                  ("  source_url: " + target_url if line.startswith("  source_url: ") else line)
                  for i, line in enumerate(twin_lines)]
    twin = NL.join(twin_lines)
    ok, out = refuses(text + twin, base_doc, "the report is already counted on 18.009.20044")
    check("E25 duplicate prevention: a report already counted on the patch under another row refuses", ok, out)
    valid = text.replace(target_a, target_a.replace("  source_weight: 1", "  source_weight: 1" + NL
                                                     + "  evidence_valid_for_current_patch: false", 1))
    vblock = block_of(valid, ("18.009.20044", "1511973"))
    ok, out = refuses(valid, mutate(lambda d: set_entry(d, 0, block_sha256_before=sha(vblock))),
                      "carrying evidence_valid_for_current_patch")
    check("E26 a block carrying evidence_valid_for_current_patch is an unexpected shape", ok, out)
    unmatched = text.replace(target_a, target_a.replace("  patch_version_matched: true", "  patch_version_matched: false", 1))
    ublock = block_of(unmatched, ("18.009.20044", "1511973"))
    ok, out = refuses(unmatched, mutate(lambda d: set_entry(d, 0, block_sha256_before=sha(ublock),
                                                            block_sha256_after=sha(own_readmit(ublock, WORK)),
                                                            successors=[])),
                      "would not enter the counted population")
    check("E27 a row that would not enter the counted population refuses", ok, out)
    ok, out = refuses(text, base_doc, "the store is not the expected one", "--expected-store-sha256", "0" * 64)
    check("E28 a store other than --expected-store-sha256 refuses (re-pin at merge time)", ok, out)
    ok, out = refuses(text, base_doc, "not the pinned", versions={k: v for k, v in RECORD_VERSIONS.items()
                                                                  if k != "19.021.20047"})
    check("E29 a missing record refuses", ok, out)
    with tempfile.TemporaryDirectory(prefix="aux110-e30-") as tmp:
        store, generated, man = make_tree(Path(tmp))
        no_write = run_tool(store, generated, man, "--regenerate")
        other_tree = run_tool(store, generated, man, "--write", "--confirm-write", "--regenerate")
        untouched = store.read_bytes() == text.encode("utf-8")
    check("E30 --regenerate needs --write --confirm-write and the default tree (usage error, nothing written)",
          no_write.returncode == 2 and other_tree.returncode == 2 and "default tree" in other_tree.stdout and untouched,
          no_write.stdout[-200:] + other_tree.stdout[-200:])

    print("F. writers")
    calls: list[tuple] = []

    class Done:
        returncode, stdout, stderr = 0, "", ""

    real = ra.subprocess.run
    ra.subprocess.run = lambda cmd, **kw: (calls.append((tuple(cmd), kw.get("cwd"))), Done())[1]
    try:
        steps = ra.regenerate()
    finally:
        ra.subprocess.run = real
    commands = [tuple(c[0][1:]) for c in calls]
    check("F1 --regenerate runs exactly the two scoped Reader writers, in order, from the scripts directory",
          [c[0] for c in commands] == [str(SCRIPTS / "build_consensus_from_evidence.py"),
                                       str(SCRIPTS / "apply_consensus_to_records.py")]
          and commands[0][1:] == ("--product-id", READER, "--reconcile-only")
          and commands[1][1:6] == ("--product-id", READER, "--write-all", "--confirm-write", "--output")
          and all(c[1] == str(SCRIPTS) and c[0][0] == sys.executable for c in calls)
          and [s["returncode"] for s in steps] == [0, 0], str(commands))
    check("F2 no writer is unscoped: every command names --product-id adobe-acrobat-reader",
          all(list(w).count("--product-id") == 1 and w[w.index("--product-id") + 1] == READER for w in ra.WRITERS))

    print("G. auditability")
    with tempfile.TemporaryDirectory(prefix="aux110-g-") as tmp:
        store, generated, man = make_tree(Path(tmp))
        before_sha = sha(store.read_bytes())
        audit = Path(tmp) / "audit.json"
        proc = run_tool(store, generated, man, "--write", "--confirm-write", "--audit", str(audit),
                        "--parent-commit", "abc123")
        got_audit = json.loads(audit.read_text(encoding="utf-8")) if audit.exists() else {}
        after_sha = sha(store.read_bytes())
        man_sha = sha(man.read_bytes())
    check("G1 the run audit names the manifest, the store before and after, the parent commit, and that it wrote",
          proc.returncode == 0 and got_audit.get("manifest_sha256") == man_sha
          and got_audit.get("store_sha256_before") == before_sha and got_audit.get("store_sha256_after") == after_sha
          and got_audit.get("parent_commit") == "abc123" and got_audit.get("written") is True
          and got_audit.get("readmitted_now") == 2)
    check("G2 the run audit carries each row's labels, its action, and the packet and brief it was judged on",
          [e.get("action") for e in got_audit.get("entries", [])] == ["readmit", "readmit"]
          and all([x["label"] for x in e["labels"]] == ["CORRECT", "CORRECT"] for e in got_audit.get("entries", []))
          and got_audit.get("adjudication", {}).get("packet_sha256") == PACKET_SHA
          and got_audit.get("adjudication", {}).get("brief_sha256") == BRIEF_SHA)
    check("G3 the run audit states the per-patch deltas and exactly the two newly counted rows",
          [(p["update_version"], p["before"], p["after"]) for p in got_audit.get("per_patch", [])]
          == [("18.009.20044", 1, 2), ("19.021.20047", 1, 2)]
          and len(got_audit.get("newly_counted_rows", [])) == 2 and got_audit.get("evidence_losses") == [])
    run_audit = json.loads(RUN_AUDIT.read_text(encoding="utf-8"))
    corr_audit = json.loads(CORRECTION_AUDIT.read_text(encoding="utf-8"))
    check("G4 the committed run audit is this manifest's: two re-admitted from the pinned store, +1 on each patch",
          run_audit.get("manifest_sha256") == sha(MANIFEST.read_bytes())
          and run_audit.get("store_sha256_before") == doc["store_sha256_at_pin"] and run_audit.get("readmitted_now") == 2
          and [(p["update_version"], p["before"], p["after"]) for p in run_audit.get("per_patch", [])]
          == [("18.009.20044", 4, 5), ("19.021.20047", 1, 2)] and run_audit.get("written") is True)
    check("G5 the committed correction audit is this correction's, applied to the store the re-admission produced",
          corr_audit.get("manifest_sha256") == sha(CORRECTION.read_bytes())
          and corr_audit.get("store_sha256_before") == run_audit.get("store_sha256_after")
          and [c["action"] for c in corr_audit.get("corrections", [])] == ["correct"] and corr_audit.get("written") is True)

    print("H. the committed store (read only)")
    live_text = STORE.read_bytes().decode("utf-8")
    live_blocks = blocks_by_identity(live_text)
    live_rows = yaml.safe_load(live_text)["evidence"]
    accepted = {ident(e): {e["block_sha256_after"], *[s["block_sha256_to"] for s in e.get("successors") or []]}
                for e in entries}
    states = {short(e): (live_blocks.get(ident(e)) or [""]) for e in entries}
    check("H1 both rows are stored re-admitted, each block its after-pin or its recorded successor",
          all(len(v) == 1 for v in states.values())
          and all(sha(live_blocks[ident(e)][0]) in accepted[ident(e)] for e in entries)
          and all("  counted: true" + NL + "  exclusion_reason: null" in live_blocks[ident(e)][0] for e in entries))
    live_short = {}
    for r in live_rows:
        if r.get("product_id") == READER and short(r) in (*READMIT, HELD, SIBLING):
            live_short.setdefault(short(r), []).append(r)
    target_live = (live_short.get(("18.009.20044", "1511973")) or [{}])[0]
    check("H2 the sibling and the held row stay withdrawn; 1511973 carries the corrected labels, its platform and tone",
          [(r["counted"], r["exclusion_reason"]) for r in live_short.get(SIBLING, [])] == [(False, ROLL)]
          and [(r["counted"], r["exclusion_reason"]) for r in live_short.get(HELD, [])] == [(False, MULTI)]
          and {k: target_live.get(k) for k in TO_LABELS} == TO_LABELS
          and target_live.get("platform") == "windows" and target_live.get("sentiment") == "negative")
    live_dry = subprocess.run([sys.executable, str(TOOL)], capture_output=True, text=True, encoding="utf-8",
                              env=_env(), cwd=str(SCRIPTS))
    check("H3 the tool over the committed tree is a no-op: both already re-admitted",
          live_dry.returncode == 0 and live_dry.stdout.count("[already_readmitted") == 2
          and "rows re-admitted by this run: 0" in live_dry.stdout, live_dry.stdout[-300:] + live_dry.stderr[-300:])
    vetoed = sorted(short(r) for r in live_rows
                    if r.get("product_id") in (READER, PRO) and r.get("counted") is True
                    and target_is_contradicted(joined_text(r), str(r.get("update_version") or "")) is not None)
    counted_acrobat = sum(1 for r in live_rows if r.get("product_id") in (READER, PRO) and r.get("counted") is True)
    check("H4 on stored text the shipped veto refuses exactly the manifest's rows among every counted Acrobat row "
          "(the manifest is the exemption list; the veto itself is unchanged)",
          vetoed == sorted(READMIT) and counted_acrobat > 100, f"{vetoed} of {counted_acrobat}")

    print("I. writeback stability")
    with tempfile.TemporaryDirectory(prefix="aux110-i-") as tmp:
        store, _generated, _man = make_tree(Path(tmp))
        run_tool(store, _generated, _man, "--write", "--confirm-write")
        settled = store.read_bytes()
        rows_s = yaml.safe_load(settled.decode("utf-8"))["evidence"]
        rediscovered = []
        for r in rows_s:
            if short(r) in READMIT:
                rediscovered.append(dict(r, counted=False, exclusion_reason=WORK))  # what the veto would say again
                rediscovered.append(dict(r, id=str(r["id"]) + "-respelled", counted=False, exclusion_reason=WORK))
        held_out: list[dict] = []
        added, _total, _rows = base.append_evidence_rows(rediscovered, Path(store), out_already_held=held_out)
        same = store.read_bytes() == settled
    check("I1 a rediscovery of a re-admitted report (same id, or the same URL under a new id) is never appended",
          added == 0 and same and len(held_out) == 4)
    flipped = settled.decode("utf-8").replace("  counted: true" + NL + "  exclusion_reason: null",
                                              "  counted: false" + NL + "  exclusion_reason: " + WORK, 1)
    try:
        collector_ownership.validate_evidence(READER, settled.decode("utf-8"), flipped)
        code = ""
    except collector_ownership.OwnershipViolation as exc:
        code = getattr(exc, "code", "")
    check("I2 a collector run that would re-veto a stored row is refused as modifying an existing row",
          code == "evidence_existing_row_modified" and flipped != settled.decode("utf-8"), code)

    print("J. the pinned label correction refuses anything but the shipped classifier's answer")
    with tempfile.TemporaryDirectory(prefix="aux110-j-") as tmp:
        store, _g, _m = make_tree(Path(tmp))
        start = store.read_bytes()

        def corr(fn) -> subprocess.CompletedProcess:
            d = copy.deepcopy(cdoc)
            fn(d)
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps(d), encoding="utf-8")
            return run_correction(store, path, "--write")

        cases = {
            "typed label": corr(lambda d: d["entries"][0]["to"].update(issue_theme="file open failure")),
            "platform": corr(lambda d: d.update(fields=["issue_theme", "platform", "severity", "workflow_area"])),
            "from mismatch": corr(lambda d: d["entries"][0]["from"].update(severity="low")),
            "no row": corr(lambda d: d["entries"][0].update(source_url="https://community.adobe.com/questions-12/x-1")),
            "no basis": corr(lambda d: d["entries"][0].update(basis="")),
            "from == to": corr(lambda d: d["entries"][0].update(**{"from": dict(TO_LABELS)})),
        }
        unchanged = store.read_bytes() == start
        both = subprocess.run([sys.executable, str(RECOMPUTE), "--store", str(store), "--correction-manifest",
                               str(CORRECTION), "--product-id", READER, "--only-id", "x"],
                              capture_output=True, text=True, encoding="utf-8", env=_env(), cwd=str(SCRIPTS))
    check("J1 a label that is not the shipped classifier's answer refuses",
          cases["typed label"].returncode == 1 and "not the shipped classifier's answer" in cases["typed label"].stderr)
    check("J2 a correction that would write platform refuses",
          cases["platform"].returncode == 1 and "fields are not theme" in cases["platform"].stderr)
    check("J3 stored labels that are neither the pinned from nor to refuse",
          cases["from mismatch"].returncode == 1 and "neither the pinned from nor to" in cases["from mismatch"].stderr)
    check("J4 a correction matching no row, without a basis, or changing nothing refuses; nothing was written",
          cases["no row"].returncode == 1 and "matches 0 rows" in cases["no row"].stderr
          and cases["no basis"].returncode == 1 and cases["from == to"].returncode == 1 and unchanged)
    check("J5 --correction-manifest cannot be combined with --only-id", both.returncode == 2, both.stderr[-200:])

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
