#!/usr/bin/env python3
"""The audited withdrawal of confirmed off-topic and duplicate Windows rows (AUX-079).

`withdraw_windows_confirmed_and_duplicate_rows.py` withdraws ten Track B rows (both adjudicators said
the report is about something other than the credited patch) and four Track C rows (a later capture
of a Microsoft Q&A question the same patch already counts under an earlier title slug), and keeps the
four earlier captures. Its contract, pinned here:

  A  the committed manifest names exactly those fourteen rows and the four kept rows, each by its full
     five-field identity; every Track B row carries two agreeing B labels and its reason; every
     Track C row names its kept row and the pair derives; both reasons come from the existing
     vocabulary and neither can be laundered back into visibility; it shares no row with AUX-072
  B  a dry run (the default) plans the fourteen, keeps the four and writes nothing
  C  --write needs --confirm-write; the write changes exactly 42 lines (three per row, the track's own
     reason), keeps every row, leaves the kept rows and every other row byte-identical, starts no row
     counting, leaves no patch counting one Learn report twice, and the evidence-loss guard reads it
     as an audited withdrawal (deleting the same rows, or uncounting them without a reason, is a loss)
  D  a second run changes nothing
  E  every unsafe input refuses the WHOLE run and writes nothing
  F  a same-question row stored on another patch is never re-homed: byte-identical, still uncounted,
     and reported as stranded when its question now counts nowhere
  G  the committed store holds the fourteen as withdrawn, each with its track's reason (pinned
     identities only; no live total is read), and this suite changed nothing real

The tool runs as a BARE script, so B-D run it as a subprocess exactly as an operator would. Offline:
frozen fixtures copied verbatim from the store (tests/fixtures/windows_pk1/withdrawal_store.yml: the
eighteen manifest rows and two unrelated counted 26200.7840 rows; withdrawal_targets.json: the eight
records' identity front matter) and temporary trees only.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_withdraw_windows_confirmed_and_duplicate_rows.py
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

import withdraw_windows_confirmed_and_duplicate_rows as wd  # noqa: E402
import withdraw_windows_identity_not_the_subject_rows as aux072  # noqa: E402
from lib import context_resolution, evidence_loss as el, tier2_evidence  # noqa: E402
from patch_collectors import base  # noqa: E402

TOOL = SCRIPTS / "withdraw_windows_confirmed_and_duplicate_rows.py"
MANIFEST = SCRIPTS / "audit" / "windows_confirmed_and_duplicate_withdrawal.json"
FIX = SCRIPTS / "tests" / "fixtures" / "windows_pk1"
STORE_FIXTURE = FIX / "withdrawal_store.yml"
TARGETS = FIX / "withdrawal_targets.json"
NL = chr(10)
SEL = ("product_id", "update_version", "target_build", "id", "source_url")
REASON_B, REASON_C = "identity_not_the_subject", "duplicate_existing_evidence"

# The audited rows, written out here so the manifest cannot redefine them: (question id, patch build).
TRACK_B = {("5671947", "26200.7462"), ("5698431", "26200.7462"), ("5674430", "26200.7462"),
           ("6034766", "26200.7462"), ("5870615", "26200.7623"), ("5809263", "26200.7623"),
           ("5737538", "26200.7623"), ("5993083", "26200.7840"), ("5779394", "26200.7840"),
           ("6040671", "26200.9711")}
TRACK_C = {("5945620", "26200.8737"), ("5998917", "26200.9445"), ("6043315", "26300.9711"),
           ("6053821", "26300.9818")}

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


def manifest_doc() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


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
    for lo, hi, row in aux072.store_blocks(text):
        out.setdefault(ident(row), []).append(text[lo:hi])
    return out


def block_of(text: str, qid: str, build: str, kept: bool | None = None) -> str:
    """The one block of question `qid` on `build`; for a Track C pair, `kept` picks the earlier capture."""
    hits = [(str(row.get("captured_at")), text[lo:hi]) for lo, hi, row in aux072.store_blocks(text)
            if f"/questions/{qid}/" in str(row.get("source_url")) and str(row.get("target_build")) == build]
    hits.sort()
    if kept is None:
        assert len(hits) == 1, (qid, build, len(hits))
        return hits[0][1]
    assert len(hits) == 2, (qid, build, len(hits))
    return hits[0][1] if kept else hits[1][1]


def write_manifest(tmp: Path, doc: dict, name: str = "manifest.json") -> Path:
    path = tmp / name
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


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
    with tempfile.TemporaryDirectory(prefix="pk1-plan-") as tmp:
        _store, generated = make_tree(Path(tmp), store_text)
        targets = wd.windows_targets(generated)
    try:
        return "", wd.plan(store_text, entries if entries is not None else wd.load_manifest(MANIFEST), targets)
    except wd.Refusal as exc:
        return str(exc), None


def qid_of(entry: dict) -> str:
    return wd.learn_report(entry["source_url"])[0]


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Audited withdrawal of confirmed off-topic and duplicate Windows rows (AUX-079)")
    print("=" * 78)
    live_store = ROOT / "_data" / "consensus_evidence.yml"
    manifest = manifest_doc()
    live_files = [live_store] + sorted({ROOT.parent / e["record_file"] for e in manifest["entries"]})
    live_before = {str(p): sha(p.read_bytes()) for p in live_files if p.exists()}
    text = fixture_text()
    withdraw = [e for e in manifest["entries"] if e["role"] == "withdraw"]
    retain = [e for e in manifest["entries"] if e["role"] == "retain"]
    track_b = [e for e in withdraw if e["track"] == "B"]
    track_c = [e for e in withdraw if e["track"] == "C"]

    print("A  the pinned manifest")
    check("A1 fourteen rows are withdrawn (ten Track B, four Track C) and four kept rows are pinned",
          len(withdraw) == 14 and len(track_b) == 10 and len(track_c) == 4 and len(retain) == 4
          and all(e["track"] == "C" for e in retain) and len(manifest["entries"]) == 18,
          f"{len(track_b)} B, {len(track_c)} C, {len(retain)} kept")
    check("A2 every entry carries all five identity fields, target_build included, and no identity repeats",
          all(all(str(e.get(k) or "") for k in SEL) for e in manifest["entries"])
          and len({ident(e) for e in manifest["entries"]}) == 18)
    check("A3 Track B is exactly the ten audited rows and Track C exactly the four duplicate captures",
          {(qid_of(e), e["target_build"]) for e in track_b} == TRACK_B
          and {(qid_of(e), e["target_build"]) for e in track_c} == TRACK_C
          and {(qid_of(e), e["target_build"]) for e in retain} == TRACK_C)
    per_record = collections.Counter((e["update_version"], e["target_build"]) for e in withdraw)
    check("A4 four rows on 25H2 7462, three on 7623, two on 7840, one each on 25H2 9711, 8737, 9445 and 26H2 9711, 9818",
          per_record == collections.Counter({("25H2", "26200.7462"): 4, ("25H2", "26200.7623"): 3,
                                             ("25H2", "26200.7840"): 2, ("25H2", "26200.9711"): 1,
                                             ("25H2", "26200.8737"): 1, ("25H2", "26200.9445"): 1,
                                             ("26H2", "26300.9711"): 1, ("26H2", "26300.9818"): 1}),
          str(per_record))
    adj = [e.get("adjudication") or {} for e in track_b]
    check("A5 every Track B row has two agreeing B labels, a sub-label and a written reason",
          all((a.get("auditor_label_final"), a.get("verifier_label"), a.get("final_label")) == ("B", "B", "B")
              and a.get("sub_label") in ("B-source", "B-onset", "B-cause") and str(a.get("rationale") or "").strip()
              for a in adj),
          str([(a.get("auditor_label_final"), a.get("verifier_label")) for a in adj]))
    kept_ids = {ident(e) for e in retain}
    check("A6 every Track C row names a pinned kept row of the same patch and question",
          all(tuple(e["duplicate_of"][k] for k in SEL) in kept_ids
              and tuple(e["duplicate_of"][k] for k in SEL)[:3] == ident(e)[:3]
              and wd.learn_report(e["duplicate_of"]["source_url"])[0] == qid_of(e) for e in track_c))
    rows = {ident(row): row for _lo, _hi, row in aux072.store_blocks(text)}
    derived = {e["id"][-30:]: wd._duplicate_refusal(rows[ident(e)], rows[tuple(e["duplicate_of"][k] for k in SEL)])
               for e in track_c}
    check("A7 each Track C pair derives on the stored rows (the verdict is derived, not listed)",
          all(v == "" for v in derived.values()), str(derived))
    check("A8 the reasons come from the existing vocabulary: Track B is AUX-072's, Track C the append guard's name",
          manifest["exclusion_reasons"] == wd.TRACK_REASONS == {"B": REASON_B, "C": REASON_C}
          and wd.TRACK_REASONS["B"] == aux072.REASON and REASON_C in base.METHOD_HEALTH_FIELDS,
          str(manifest["exclusion_reasons"]))
    never_visible = set(tier2_evidence.PROMOTABLE_REJECTIONS) | set(context_resolution.RESOLVABLE_REASONS)
    check("A9 neither reason is one a resolver or tier can promote back, and neither is the unshipped link rule's",
          not ({REASON_B, REASON_C} & never_visible) and "identity_not_linked_to_issue" not in (REASON_B, REASON_C))
    aux072_ids = {ident(e) for e in json.loads((SCRIPTS / "audit" / "windows_identity_not_the_subject_withdrawal.json")
                                               .read_text(encoding="utf-8"))["entries"]}
    check("A10 no row is shared with AUX-072's manifest", not (aux072_ids & {ident(e) for e in manifest["entries"]}))
    check("A11 the selector is the five fields, in order", wd.SELECTOR == SEL == tuple(manifest["selector"]))

    print("B  dry run, as the bare script")
    with tempfile.TemporaryDirectory(prefix="pk1-dry-") as tmp:
        store, generated = make_tree(Path(tmp))
        before = store.read_bytes()
        proc = run_tool(store, generated)
        out = proc.stdout
        check("B1 a dry run exits 0", proc.returncode == 0, proc.stdout[-400:] + proc.stderr[-400:])
        check("B2 a dry run writes nothing", store.read_bytes() == before)
        check("B3 it plans the fourteen and keeps the four",
              out.count("[withdraw ") == 14 and out.count("[kept ") == 4, out[-600:])
        check("B4 it reports the counted population each record would lose",
              "Windows counted population: 20 -> 6" in out and "25H2 26200.7462: 4 -> 0" in out
              and "25H2 26200.7840: 4 -> 2" in out and "26H2 26300.9818: 2 -> 1" in out, out[-700:])
        check("B5 it says how to apply", "pass --write --confirm-write to apply" in out)

    print("C  the write")
    with tempfile.TemporaryDirectory(prefix="pk1-write-") as tmp:
        store, generated = make_tree(Path(tmp))
        before_bytes = store.read_bytes()
        p1 = run_tool(store, generated, "--write")
        check("C1 --write without --confirm-write is a usage error and writes nothing",
              p1.returncode == 2 and store.read_bytes() == before_bytes, f"rc={p1.returncode}")
        p2 = run_tool(store, generated, "--confirm-write")
        check("C2 --confirm-write without --write is a usage error and writes nothing",
              p2.returncode == 2 and store.read_bytes() == before_bytes, f"rc={p2.returncode}")
        p2b = run_tool(store, generated, "--write", "--confirm-write", "--regenerate")
        p2c = run_tool(store, generated, "--regenerate")
        check("C3 --regenerate refuses a non-default tree and a run without --write, writing nothing",
              p2b.returncode == 2 and p2c.returncode == 2 and store.read_bytes() == before_bytes
              and "must be the defaults" in p2b.stdout, f"rc={p2b.returncode}/{p2c.returncode}")
        audit_path = Path(tmp) / "audit.json"
        p3 = run_tool(store, generated, "--write", "--confirm-write", "--audit", str(audit_path),
                      "--parent-commit", "f" * 40)
        check("C4 --write --confirm-write withdraws and says so",
              p3.returncode == 0 and "WROTE" in p3.stdout and "rows withdrawn by this run: 14" in p3.stdout,
              p3.stdout[-500:] + p3.stderr[-500:])
        before_text, after_text = before_bytes.decode("utf-8"), store.read_bytes().decode("utf-8")
        a_lines, b_lines = before_text.split(NL), after_text.split(NL)
        changed = [(a, b) for a, b in zip(a_lines, b_lines) if a != b]
        expected = collections.Counter({("  counted: true", "  counted: false"): 14,
                                        ("  exclusion_reason: null", "  exclusion_reason: " + REASON_B): 10,
                                        ("  exclusion_reason: null", "  exclusion_reason: " + REASON_C): 4,
                                        ("  evidence_valid_for_current_patch: true",
                                         "  evidence_valid_for_current_patch: false"): 14})
        check("C5 exactly 42 lines change: three per row, each row with its own track's reason",
              len(a_lines) == len(b_lines) and collections.Counter(changed) == expected,
              f"{len(changed)} changed: {collections.Counter(changed)}")
        after_blocks, before_blocks = blocks_by_identity(after_text), blocks_by_identity(before_text)
        check("C6 every withdrawn block now hashes to its pinned after-value",
              all([sha(b) for b in after_blocks.get(ident(e), [])] == [e["block_sha256_after"]] for e in withdraw))
        rows_b = [r for _lo, _hi, r in aux072.store_blocks(before_text)]
        rows_a = [r for _lo, _hi, r in aux072.store_blocks(after_text)]
        reason_of = {ident(e): (REASON_B if e["track"] == "B" else REASON_C) for e in withdraw}
        moved = [(o, n) for o, n in zip(rows_b, rows_a) if ident(o) in reason_of]
        check("C7 the fourteen parse as withdrawn with their track's reason, every other field unchanged",
              len(moved) == 14 and all(n == dict(o, counted=False, exclusion_reason=reason_of[ident(o)],
                                                 evidence_valid_for_current_patch=False) for o, n in moved))
        check("C8 the four kept rows are byte-identical, hash to their pins and still count",
              all(after_blocks[ident(e)] == before_blocks[ident(e)] and sha(after_blocks[ident(e)][0]) == e["block_sha256_before"]
                  and {ident(r): r for r in rows_a}[ident(e)].get("counted") is True for e in retain))
        others = [k for k in before_blocks if k not in reason_of]
        check("C9 no row is added or removed, and every row not withdrawn is byte-identical",
              len(rows_a) == len(rows_b) == 20 and len(others) == 6
              and all(after_blocks.get(k) == before_blocks[k] for k in others))
        check("C10 no row starts counting and no patch counts one Learn report twice afterwards",
              {ident(r) for r in rows_a if r.get("counted") is True} <= {ident(r) for r in rows_b if r.get("counted") is True}
              and wd._counted_learn_duplicates(rows_a, wd.windows_targets(generated)) == []
              and len(wd._counted_learn_duplicates(rows_b, wd.windows_targets(generated))) == 4)
        check("C11 the evidence-loss guard reads it as an audited withdrawal, not a loss",
              el.losses_between(before_text, after_text) == [])
        deleted = before_text
        for e in withdraw:
            deleted = deleted.replace(before_blocks[ident(e)][0], "", 1)
        unreasoned = after_text
        for reason in (REASON_B, REASON_C):
            unreasoned = unreasoned.replace(NL + "  exclusion_reason: " + reason + NL, NL + "  exclusion_reason: null" + NL)
        losses_del, losses_unr = el.losses_between(before_text, deleted), el.losses_between(before_text, unreasoned)
        check("C12 control: the same rows deleted, or uncounted without a reason, ARE evidence loss",
              len(losses_del) == 14 and all(x.code == el.REMOVED for x in losses_del)
              and len(losses_unr) == 14 and all(x.code == el.UNAUDITED for x in losses_unr),
              f"{[x.code for x in losses_del]} / {[x.code for x in losses_unr]}")
        audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
        check("C13 the audit records the run: hashes, parent, reasons, the fourteen and each record's delta",
              audit.get("written") is True and audit.get("withdrawn_now") == 14
              and audit.get("store_sha256_before") == sha(before_bytes)
              and audit.get("store_sha256_after") == sha(after_text) and audit.get("parent_commit") == "f" * 40
              and audit.get("windows_counted_population") == [20, 6] and len(audit.get("per_patch") or []) == 8
              and audit.get("exclusion_reasons") == {"B": REASON_B, "C": REASON_C}
              and sorted(i["action"] for i in audit.get("entries") or []) == ["kept"] * 4 + ["withdraw"] * 14,
              json.dumps({k: audit.get(k) for k in ("written", "withdrawn_now", "windows_counted_population")}))

        print("D  idempotence")
        p4 = run_tool(store, generated, "--write", "--confirm-write")
        check("D1 a second run exits 0, writes nothing and says so",
              p4.returncode == 0 and "nothing to write" in p4.stdout and store.read_bytes().decode("utf-8") == after_text,
              p4.stdout[-400:] + p4.stderr[-300:])
        check("D2 it reports the fourteen as already withdrawn and still keeps the four",
              p4.stdout.count("[already_withdrawn") == 14 and p4.stdout.count("[kept ") == 4)
        check("D3 the population it reports no longer moves", "Windows counted population: 6 -> 6" in p4.stdout)

    print("E  fail closed: each unsafe input refuses the whole run and writes nothing")
    b6034766 = block_of(text, "6034766", "26200.7462")
    drifted = text.replace(b6034766, b6034766.replace("  sentiment: negative", "  sentiment: neutral"), 1)
    assert drifted != text
    proc, same = refused("pk1-e1-", drifted)
    check("E1 one drifted pinned row refuses the run, naming the drift",
          proc.returncode == 1 and "block changed since the manifest was pinned" in proc.stdout, proc.stdout[-300:])
    check("E1b all or nothing: the thirteen intact rows are not withdrawn either", same)

    b5993083 = block_of(text, "5993083", "26200.7840")
    proc, same = refused("pk1-e2-", text + b5993083)
    check("E2 two blocks with one five-field identity refuse the run",
          proc.returncode == 1 and "2 blocks match the five-field identity" in proc.stdout and same, proc.stdout[-300:])

    proc, same = refused("pk1-e3-", text.replace(block_of(text, "6040671", "26200.9711"), "", 1))
    check("E3 a pinned row that is missing refuses the run",
          proc.returncode == 1 and "0 blocks match the five-field identity" in proc.stdout and same, proc.stdout[-300:])

    with tempfile.TemporaryDirectory(prefix="pk1-e4-") as tmp:
        bad = manifest_doc()
        bad["entries"][0]["target_build"] = ""
        proc, same = refused("pk1-e4b-", manifest=write_manifest(Path(tmp), bad, "a.json"))
        check("E4 a selector without target_build is refused (never by id or URL alone)",
              proc.returncode == 1 and "lacks part of the five-field identity" in proc.stdout and same, proc.stdout[-300:])
        dup = manifest_doc()
        dup["entries"].append(dict(dup["entries"][0]))
        proc, same = refused("pk1-e5b-", manifest=write_manifest(Path(tmp), dup, "b.json"))
        check("E5 an identity listed twice in the manifest is refused",
              proc.returncode == 1 and "listed twice" in proc.stdout and same, proc.stdout[-300:])
        relabel = manifest_doc()
        relabel["exclusion_reasons"] = {"B": "identity_not_linked_to_issue", "C": REASON_C}
        proc, same = refused("pk1-e6b-", manifest=write_manifest(Path(tmp), relabel, "c.json"))
        check("E6 a manifest cannot relabel a track's reason",
              proc.returncode == 1 and "per-track exclusion reasons differ" in proc.stdout and same, proc.stdout[-300:])
        split = manifest_doc()
        next(e for e in split["entries"] if e.get("track") == "B")["adjudication"]["verifier_label"] = "U"
        proc, same = refused("pk1-e7b-", manifest=write_manifest(Path(tmp), split, "d.json"))
        check("E7 a Track B row without two agreeing B labels is refused",
              proc.returncode == 1 and "lacks two agreeing B labels" in proc.stdout and same, proc.stdout[-300:])
        orphan = manifest_doc()
        orphan["entries"] = [e for e in orphan["entries"]
                             if not (e["role"] == "retain" and "/5945620/" in e["source_url"])]
        proc, same = refused("pk1-e8b-", manifest=write_manifest(Path(tmp), orphan, "e.json"))
        check("E8 a Track C row whose kept row is not pinned is refused",
              proc.returncode == 1 and "names no pinned kept row" in proc.stdout and same, proc.stdout[-300:])

    kept9445 = block_of(text, "5998917", "26200.9445", kept=True)
    changed_kept = text.replace(kept9445, kept9445.replace("  sentiment: negative", "  sentiment: neutral"), 1)
    assert changed_kept != text
    proc, same = refused("pk1-e9-", changed_kept)
    check("E9 a changed kept row refuses the run",
          proc.returncode == 1 and "kept row changed" in proc.stdout and same, proc.stdout[-300:])

    uncounted_kept = kept9445.replace("  counted: true" + NL, "  counted: false" + NL, 1)
    entries = manifest_doc()
    for e in entries["entries"]:
        if e["role"] == "retain" and "/5998917/" in e["source_url"]:
            e["block_sha256_before"] = sha(uncounted_kept)
    message, _ = in_process_plan(text.replace(kept9445, uncounted_kept, 1), wd.manifest_entries(entries))
    check("E10 a kept row that no longer counts refuses the run", "kept row no longer counts" in message, message[:300])

    moved = targets_fixture()
    for t in moved:
        if t["front_matter"]["target_build"] == "26200.7840":
            t["front_matter"]["target_kb"] = "KB5999999"
    proc, same = refused("pk1-e11-", None, moved)
    check("E11 a record whose target identity moved refuses the run",
          proc.returncode == 1 and "record target identity moved" in proc.stdout and same, proc.stdout[-300:])

    # A third counted capture of a Track C question on the same patch, under yet another slug: a new
    # duplicate the manifest does not name.
    extra = kept9445.replace("/5998917/kb5124008-26200-9445-breaks-machine-secure-channel",
                             "/5998917/kb5124008-breaks-machine-secure-channel-trust", 1)
    extra = extra.replace("questions-5998917-kb5124008-26200-9445-breaks-machine-se",
                          "questions-5998917-kb5124008-breaks-machine-secure-chan", 1)
    assert extra.count("/5998917/kb5124008-breaks-machine-secure-channel-trust") == 1
    assert extra.count("questions-5998917-kb5124008-breaks-machine-secure-chan") == 1
    proc, same = refused("pk1-e12-", text + extra)
    check("E12 a counted duplicate the manifest does not name refuses the run",
          proc.returncode == 1 and "still counts one Learn report more than once" in proc.stdout and same,
          proc.stdout[-400:])

    w9818 = block_of(text, "6053821", "26300.9818", kept=False)
    k9818 = block_of(text, "6053821", "26300.9818", kept=True)
    late_kept = k9818.replace("  captured_at: '2026-10-29T", "  captured_at: '2026-10-31T", 1)
    assert late_kept != k9818
    entries = manifest_doc()
    for e in entries["entries"]:
        if e["role"] == "retain" and "/6053821/" in e["source_url"]:
            e["block_sha256_before"] = sha(late_kept)
    message, _ = in_process_plan(text.replace(k9818, late_kept, 1), wd.manifest_entries(entries))
    check("E13 keep-first: a pair whose kept row is the LATER capture is refused",
          "the kept row is not the earlier capture" in message, message[:300])
    entries = manifest_doc()
    swap = {ident(e): e for e in entries["entries"] if e["role"] == "retain"}
    k8737 = next(k for k in swap if "/5945620/" in k[4])
    for e in entries["entries"]:
        if e["role"] == "withdraw" and "/6053821/" in e["source_url"]:
            e["duplicate_of"] = dict(zip(SEL, k8737))
    message, _ = in_process_plan(text, wd.manifest_entries(entries))
    check("E14 a pair whose kept row is another patch's or another question's is refused",
          "the kept row is on another patch" in message, message[:300])
    # Keep-first compares opening reports only: an answer anchored under the question is another segment.
    anchored = w9818.replace("/6053821/boot-and-login-animation-regression-to-old-dots-ri" + NL,
                             "/6053821/boot-and-login-animation-regression-to-old-dots-ri#answer-6053999" + NL, 1)
    assert anchored != w9818
    entries = manifest_doc()
    for e in entries["entries"]:
        if e["role"] == "withdraw" and "/6053821/" in e["source_url"]:
            e["source_url"] += "#answer-6053999"
            e["block_sha256_before"] = sha(anchored)
            e["block_sha256_after"] = sha(wd.withdraw_block(anchored, REASON_C))
    message, _ = in_process_plan(text.replace(w9818, anchored, 1), wd.manifest_entries(entries))
    check("E19 a pair in which one row is an answer segment, not the question, is refused",
          "an answer segment is not the question's opening report" in message, message[:300])

    other = text.replace(b6034766, b6034766.replace("  counted: true" + NL + "  exclusion_reason: null",
                                                    "  counted: false" + NL + "  exclusion_reason: cross_patch_duplicate"), 1)
    assert other != text
    proc, same = refused("pk1-e15-", other)
    check("E15 a row already withdrawn for ANOTHER reason is never rewritten",
          proc.returncode == 1 and "block changed since the manifest was pinned" in proc.stdout and same, proc.stdout[-300:])

    shapeless = b6034766.replace("  evidence_valid_for_current_patch: true" + NL, "", 1)
    try:
        wd.withdraw_block(shapeless, REASON_B)
        shape_refused = False
    except wd.Refusal:
        shape_refused = True
    check("E16 the three-line edit refuses a block of unexpected shape", shape_refused)
    doubled = b6034766 + "  counted: true" + NL
    try:
        wd.withdraw_block(doubled, REASON_B)
        doubled_refused = False
    except wd.Refusal:
        doubled_refused = True
    check("E16b it refuses a block in which a line to edit occurs twice", doubled_refused)

    edit_for = wd.edit_for
    try:
        wd.edit_for = lambda reason: tuple((old, new.replace(": " + reason, ": '" + reason + "'"))
                                           for old, new in edit_for(reason))
        message, _ = in_process_plan(text)
    finally:
        wd.edit_for = edit_for
    check("E17 an edit whose BYTES differ from the pinned after-block is refused even if it parses the same",
          "does not produce the pinned block" in message, message[:300])

    stale_old = NL + "  stale_due_to_patch_rollover: false" + NL
    stale_new = NL + "  stale_due_to_patch_rollover: true" + NL
    widened = manifest_doc()
    for e in widened["entries"]:
        if e["role"] == "withdraw":
            block = blocks_by_identity(text)[ident(e)][0]
            e["block_sha256_after"] = sha(wd.withdraw_block(block, wd.TRACK_REASONS[e["track"]]).replace(stale_old, stale_new, 1))
    try:
        wd.edit_for = lambda reason: edit_for(reason) + ((stale_old, stale_new),)
        message, _ = in_process_plan(text, wd.manifest_entries(widened))
    finally:
        wd.edit_for = edit_for
    check("E18 a pinned after-hash cannot authorise a fourth field: the edit is proved field by field",
          "changed more than decided" in message, message[:300])

    print("F  no re-homing")
    # A same-question row stored on ANOTHER patch, refused there as a cross-patch duplicate (the shape
    # one-report-one-patch leaves behind). Built from a pinned block by moving it to 26H2 26300.9711.
    sibling = (b6034766.replace("- id: microsoft-windows-11-25h2-", "- id: microsoft-windows-11-26h2-", 1)
               .replace("  update_version: 25H2" + NL, "  update_version: 26H2" + NL, 1)
               .replace("  target_build: '26200.7462'" + NL, "  target_build: '26300.9711'" + NL, 1)
               .replace("  counted: true" + NL + "  exclusion_reason: null",
                        "  counted: false" + NL + "  exclusion_reason: cross_patch_duplicate", 1)
               .replace("  evidence_valid_for_current_patch: true", "  evidence_valid_for_current_patch: false", 1))
    assert sibling.count("26H2") >= 1 and "cross_patch_duplicate" in sibling and "'26300.9711'" in sibling, sibling[:400]
    with tempfile.TemporaryDirectory(prefix="pk1-f-") as tmp:
        store, generated = make_tree(Path(tmp), text + sibling)
        audit_path = Path(tmp) / "audit.json"
        proc = run_tool(store, generated, "--write", "--confirm-write", "--audit", str(audit_path))
        after = store.read_bytes().decode("utf-8")
        audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
        sib = [s for s in audit.get("same_question_siblings") or [] if s.get("question_id") == "6034766"]
        check("F1 the run succeeds and leaves the other patch's same-question row byte-identical and uncounted",
              proc.returncode == 0 and after.endswith(sibling) and after.count(sibling) == 1
              and len(sib) == 1 and sib[0]["unchanged"] is True and sib[0]["counted"] is False,
              proc.stdout[-300:] + json.dumps(sib))
        check("F2 it is reported as stranded (its question now counts on no patch), never re-attributed",
              len(audit.get("stranded_cross_patch_duplicates") or []) == 1
              and sib and sib[0]["question_counted_on_any_patch_after"] is False
              and audit.get("newly_counted_rows") == [], json.dumps(audit.get("stranded_cross_patch_duplicates")))

    print("G  the committed store, and this suite changed nothing real")
    live_text = live_store.read_bytes().decode("utf-8")
    live_rows = blocks_by_identity(live_text)
    live_parsed = {ident(r): r for _lo, _hi, r in aux072.store_blocks(live_text)}
    check("G1 the committed store holds each of the fourteen exactly once, withdrawn with its track's reason",
          all(len(live_rows.get(ident(e), [])) == 1 and live_parsed[ident(e)].get("counted") is False
              and live_parsed[ident(e)].get("exclusion_reason") == reason_of[ident(e)]
              and sha(live_rows[ident(e)][0]) == e["block_sha256_after"] for e in withdraw),
          str([e["id"][-20:] for e in withdraw if live_parsed.get(ident(e), {}).get("counted") is not False]))
    live_after = {str(p): sha(p.read_bytes()) for p in live_files if p.exists()}
    check("G2 the live store and the eight records are byte-identical after the suite",
          live_after == live_before and len(live_before) == 9, f"{len(live_before)} files")

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
