#!/usr/bin/env python3
"""The audited withdrawal of live-page citations credited to the wrong update, Windows and OBS (AUX-088).

`withdraw_live_citation_rows.py` withdraws the twenty stored rows that BOTH the citation audit of the
six live pages and an independent blind second review judged INCORRECT for the credited update (two
Windows, eighteen OBS), and keeps the two earlier reports that two of them cross-post. Its contract,
pinned here:

  A  the committed manifest names exactly those twenty rows, each by its full five-field identity
     (target_build set for Windows, empty for OBS), each with its own reason from a closed set the store
     already uses, two INCORRECT labels and a stated basis; the two duplicates name their kept rows; no
     reason can be promoted back into view; no row is one the reviews disagree on; it shares no row with
     AUX-072 or AUX-079
  B  a dry run (the default) plans the twenty, keeps the two and writes nothing
  C  --write needs --confirm-write; the write changes exactly 42 lines (three per Windows row, two per OBS
     row, each with its own reason), keeps every row, adds no field, leaves the kept rows and every other
     row byte-identical, starts no row counting, and the evidence-loss guard reads it as an audited
     withdrawal (deleting the same rows, or uncounting them without a reason, is a loss)
  D  a second run changes nothing
  E  every unsafe input refuses the WHOLE run and writes nothing
  F  a row of the same report stored on another identity is never re-homed: byte-identical, still counted,
     and reported
  G  the committed store holds the twenty as withdrawn with their reasons, the two kept rows and every row the
     reviews disagree on still count, and this suite changed nothing real
  H  a later audited change to a pinned row (AUX-090's posting dates) is accepted only through the versioned
     supplemental baseline: the pin is never rewritten, a successor counts only against the exact pinned hash
     it was recorded for, never for a row still to withdraw, and the original manifest and run audit stay
     byte-identical

The tool runs as a BARE script, so B-D run it as a subprocess exactly as an operator would. Offline: frozen
fixtures (tests/fixtures/live_citation/withdrawal_store.yml holds the 32 stored rows involved, serialised as
the store serialises them, with the free-text fields replaced by synthetic marker text; withdrawal_targets.json
holds the nine records' identity front matter). Because the text differs from the store, the suite re-pins the
committed manifest's block hashes on the fixture with its OWN line edit, never the tool's.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_withdraw_live_citation_rows.py
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
import withdraw_windows_confirmed_and_duplicate_rows as aux079  # noqa: E402
import withdraw_windows_identity_not_the_subject_rows as aux072  # noqa: E402
from lib import acrobat_tiering, context_resolution, evidence_loss as el, tier2_evidence  # noqa: E402
from lib.patch_identity import key_from  # noqa: E402

TOOL = SCRIPTS / "withdraw_live_citation_rows.py"
MANIFEST = SCRIPTS / "audit" / "live_citation_withdrawal.json"
FIX = SCRIPTS / "tests" / "fixtures" / "live_citation"
STORE_FIXTURE = FIX / "withdrawal_store.yml"
TARGETS = FIX / "withdrawal_targets.json"
NL = chr(10)
SEL = ("product_id", "update_version", "target_build", "id", "source_url")
WIN, OBS = "microsoft-windows-11", "obs-studio"
INTS, DUP = "identity_not_the_subject", "duplicate_existing_evidence"
WORK, ROLL, NOTR = "version_named_but_working", "version_is_rollback_target", "not_a_real_issue_report"
GH, FORUM = "https://github.com/obsproject/obs-studio/issues/", "https://obsproject.com/forum/threads/"

# The twenty rows both reviews labelled INCORRECT, written out here so the manifest cannot redefine them:
# (update_version, target_build, report id: the Learn/Tech Community thread, GitHub issue or forum thread) -> reason.
WITHDRAW = {
    ("25H2", "26200.7623", "6039416"): INTS, ("25H2", "26200.7840", "4494943"): INTS,
    ("32.1.1", "", "13291"): INTS, ("32.1.1", "", "13332"): INTS,
    ("32.1.2", "", "13370"): NOTR, ("32.1.2", "", "13373"): WORK, ("32.1.2", "", "13437"): INTS,
    ("32.1.2", "", "13466"): INTS, ("32.1.2", "", "13995"): INTS, ("32.1.2", "", "14088"): WORK,
    ("32.1.2", "", "14152"): ROLL, ("32.1.2", "", "195299"): INTS, ("32.1.2", "", "195407"): DUP,
    ("32.1.2", "", "196824"): ROLL,
    ("32.2.2", "", "14023"): INTS, ("32.2.2", "", "14040"): INTS, ("32.2.2", "", "14088"): INTS,
    ("32.2.2", "", "14117"): WORK, ("32.2.2", "", "196184"): NOTR, ("32.2.2", "", "196545"): DUP,
}
KEPT = {("32.1.2", "", "13506"), ("32.2.2", "", "13997")}
# The rows the two reviews disagree on, all seven onset rows among them: they stay counted.
STAY_COUNTED = {
    ("32.2.2", "", "196683"), ("32.1.1", "", "13337"), ("32.1.1", "", "13286"), ("25H2", "26200.7840", "4494548"),
    ("32.2.2", "", "14071"), ("32.1.2", "", "13547"), ("32.1.1", "", "13289"), ("32.2.2", "", "14032"),
    ("32.1.2", "", "196761"), ("25H2", "26200.7840", "5824421"), ("32.1.1", "", "13338"), ("32.1.1", "", "13348"),
    ("32.1.1", "", "13278"), ("32.1.1", "", "13304"), ("32.1.2", "", "13529"), ("32.1.2", "", "13491"),
    ("32.1.2", "", "13429"), ("32.1.1", "", "13298"), ("32.1.2", "", "13997"), ("32.2.2", "", "13878"),
    ("32.1.1", "", "194821"), ("32.1.1", "", "13360"),
}
RECORDS = ("2026-01-13-windows-11-25h2-26200-7623.md", "2026-02-10-windows-11-25h2-26200-7840.md",
           "2026-04-02-obs-studio-32-1-1.md", "2026-04-21-obs-studio-32-1-2.md", "2026-08-14-obs-studio-32-2-2.md")

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
    """The thread/issue/question number a URL names (Learn: the question id; others: the last number)."""
    tail = url.rstrip("/")
    if "/answers/questions/" in tail:
        return tail.split("/answers/questions/", 1)[1].split("/", 1)[0]
    last = tail.rsplit("/", 1)[-1]
    return last.rsplit(".", 1)[-1] if "." in last else last


def short(row: dict) -> tuple[str, str, str]:
    return (str(row.get("update_version") or ""), str(row.get("target_build") or ""),
            report_id(str(row.get("source_url") or "")))


def ident(row: dict) -> tuple[str, ...]:
    """The suite's own five-field identity, so a broken selector in the tool fails a check, not the suite."""
    return tuple(str(row.get(key) or "") for key in SEL)


def own_edit(block: str, product: str, reason: str) -> str:
    """The suite's own withdrawal edit, independent of the tool's: three lines for Windows, two for OBS."""
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


def fixture_manifest(text: str | None = None) -> dict:
    """The committed manifest with its block hashes re-pinned on the fixture by the suite's own edit."""
    doc = manifest_doc()
    blocks = blocks_by_identity(text if text is not None else fixture_text())
    for entry in doc["entries"]:
        hits = blocks.get(ident(entry), [])
        if len(hits) != 1:
            continue
        entry["block_sha256_before"] = sha(hits[0])
        if entry["role"] == "withdraw":
            entry["block_sha256_after"] = sha(own_edit(hits[0], entry["product_id"], entry["exclusion_reason"]))
    return doc


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
                           "--manifest", str(manifest), *args],
                          capture_output=True, text=True, encoding="utf-8", env=env, timeout=600)


def refused(prefix: str, store_text: str | None = None, targets: list[dict] | None = None,
            manifest: dict | None = None) -> tuple[subprocess.CompletedProcess, bool]:
    """Run --write --confirm-write on a tree and report whether the store came back byte-identical."""
    with tempfile.TemporaryDirectory(prefix=prefix) as tmp:
        store, generated, man = make_tree(Path(tmp), store_text, targets, manifest)
        before = store.read_bytes()
        proc = run_tool(store, generated, man, "--write", "--confirm-write")
        return proc, store.read_bytes() == before


def in_process_plan(store_text: str, doc: dict | None = None) -> tuple[str, dict | None]:
    """plan() in-process on a temp tree: ('', result) or (refusal message, None)."""
    with tempfile.TemporaryDirectory(prefix="aux088-plan-") as tmp:
        _store, generated, _man = make_tree(Path(tmp), store_text)
        records = wd.patch_records(generated)
    try:
        entries = wd.manifest_entries(doc if doc is not None else fixture_manifest(store_text))
        return "", wd.plan(store_text, entries, records)
    except wd.Refusal as exc:
        return str(exc), None


def block_of(text: str, version: str, rid: str) -> str:
    hits = [text[lo:hi] for lo, hi, row in aux072.store_blocks(text) if short(row)[0] == version and short(row)[2] == rid]
    assert len(hits) == 1, (version, rid, len(hits))
    return hits[0]


def entry_of(doc: dict, version: str, rid: str) -> dict:
    hits = [e for e in doc["entries"] if short(e)[0] == version and short(e)[2] == rid]
    assert len(hits) == 1, (version, rid)
    return hits[0]


def own_date_edit(block: str, day: str) -> str:
    """The suite's own AUX-090 date edit: a null source_date becomes the day, else the day goes after captured_at."""
    lines = block.split(NL)
    new = "  source_date: '" + day + "'"
    present = [i for i, line in enumerate(lines) if line.startswith("  source_date:")]
    if present:
        assert len(present) == 1 and lines[present[0]] == "  source_date: null"
        lines[present[0]] = new
    else:
        at = [i for i, line in enumerate(lines) if line.startswith("  captured_at: ")]
        assert len(at) == 1
        lines.insert(at[0] + 1, new)
    return NL.join(lines)


def plan_with(store_text: str, doc: dict, baseline: dict) -> tuple[str, dict | None]:
    """plan() in-process with a supplemental baseline: ('', result) or (refusal message, None)."""
    with tempfile.TemporaryDirectory(prefix="aux088-h-") as tmp:
        _store, generated, _man = make_tree(Path(tmp), store_text)
        records = wd.patch_records(generated)
    try:
        return "", wd.plan(store_text, wd.manifest_entries(doc), records, baseline)
    except wd.Refusal as exc:
        return str(exc), None


# The AUX-088 audit files as that change committed them. They are immutable: a later change to a pinned row
# goes into the supplemental baseline, never into these.
AUX088_FILES = {
    "live_citation_withdrawal.json": "e7fda1cf2cdf42a1dc88a8ab962c2ef3fbaec9599bff26077a6880f0247d9d24",
    "live_citation_withdrawal_2026-11-06.json": "e0228bcb49390939ee91d044097ad5ec1d31153c3315637aac9947c7bb318693",
}


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Audited withdrawal of live-page citations credited to the wrong update (AUX-088)")
    print("=" * 78)
    live_store = ROOT / "_data" / "consensus_evidence.yml"
    live_files = [live_store] + [ROOT / "updates" / "generated" / name for name in RECORDS]
    live_before = {str(p): sha(p.read_bytes()) for p in live_files if p.exists()}
    manifest = manifest_doc()
    text = fixture_text()
    withdraw = [e for e in manifest["entries"] if e["role"] == "withdraw"]
    retain = [e for e in manifest["entries"] if e["role"] == "retain"]

    print("A  the pinned manifest")
    check("A1 twenty rows are withdrawn (two Windows, eighteen OBS) and two kept rows are pinned",
          len(withdraw) == 20 and len(retain) == 2 and len(manifest["entries"]) == 22
          and collections.Counter(e["product_id"] for e in withdraw) == {WIN: 2, OBS: 18},
          f"{len(withdraw)} withdraw, {len(retain)} kept")
    check("A2 five-field identity: every field set, target_build exactly for Windows, no identity repeated",
          all(all(str(e.get(k) or "") for k in SEL if k != "target_build") for e in manifest["entries"])
          and all(bool(e["target_build"]) == (e["product_id"] == WIN) for e in manifest["entries"])
          and len({ident(e) for e in manifest["entries"]}) == 22)
    check("A3 the withdrawn rows are exactly the twenty both reviews labelled INCORRECT, the kept rows the two originals",
          {short(e) for e in withdraw} == set(WITHDRAW) and {short(e) for e in retain} == KEPT,
          str(sorted({short(e) for e in withdraw} ^ set(WITHDRAW))))
    per_page = collections.Counter((e["update_version"], e["target_build"]) for e in withdraw)
    check("A4 one row each on 25H2 7623 and 7840; OBS 32.1.1: 2, 32.1.2: 10, 32.2.2: 6 (seven blind cases: one row was presented twice to the blind reviewer)",
          per_page == {("25H2", "26200.7623"): 1, ("25H2", "26200.7840"): 1, ("32.1.1", ""): 2,
                       ("32.1.2", ""): 10, ("32.2.2", ""): 6}, str(per_page))
    check("A5 every row carries its own reason, as both reviews support it",
          all(e["exclusion_reason"] == WITHDRAW[short(e)] for e in withdraw),
          str([(short(e), e["exclusion_reason"]) for e in withdraw if e["exclusion_reason"] != WITHDRAW.get(short(e))]))
    adj = [e.get("adjudication") or {} for e in withdraw]
    check("A6 every row has two INCORRECT labels (first audit and blind second review), case keys and a basis",
          all((a.get("first_audit") or {}).get("label") == "INCORRECT" and (a.get("second_blind") or {}).get("label") == "INCORRECT"
              and (a.get("first_audit") or {}).get("case_key") and (a.get("second_blind") or {}).get("case")
              and (a.get("first_audit") or {}).get("reason") == e["exclusion_reason"]
              and (a.get("second_blind") or {}).get("reason_class") for a, e in zip(adj, withdraw))
          and all(str(e.get("basis") or "").strip() for e in withdraw)
          and len({(a.get("second_blind") or {}).get("case") for a in adj}) == 20)
    vocabulary = {aux072.REASON, aux079.TRACK_REASONS["C"]} | set(acrobat_tiering.ACROBAT_NEVER_TIER)
    obs_roles = (SCRIPTS / "collect_obs_reports.py").read_text(encoding="utf-8")
    check("A7 the five reasons are names the store already uses: AUX-072's, AUX-079's, Acrobat's never-tier list, OBS's roles",
          sorted(manifest["exclusion_reasons"]) == sorted(wd.REASONS) == sorted({INTS, DUP, WORK, ROLL, NOTR})
          and {INTS, DUP, WORK, NOTR} <= vocabulary and f'"rollback_target": "{ROLL}"' in obs_roles,
          str(manifest["exclusion_reasons"]))
    never_visible = (set(tier2_evidence.PROMOTABLE_REJECTIONS) | set(context_resolution.RESOLVABLE_REASONS)
                     | set(acrobat_tiering.ACROBAT_TIERABLE_REJECTIONS))
    check("A8 no reason is one a resolver or tier can promote back, and none is the unshipped link rule's",
          not (set(wd.REASONS) & never_visible) and "identity_not_linked_to_issue" not in wd.REASONS)
    kept_ids = {ident(e) for e in retain}
    dups = [e for e in withdraw if e["exclusion_reason"] == DUP]
    check("A9 each of the two duplicates names a pinned kept row on its own page, and only they do",
          len(dups) == 2 and all(tuple(e["duplicate_of"][k] for k in SEL) in kept_ids
                                 and tuple(e["duplicate_of"][k] for k in SEL)[:3] == ident(e)[:3] for e in dups)
          and all("duplicate_of" not in e for e in withdraw if e["exclusion_reason"] != DUP))
    check("A10 no row the reviews disagree on (the seven onset rows among them) is withdrawn",
          not ({short(e) for e in withdraw} & STAY_COUNTED) and len(STAY_COUNTED) == 22)
    prior = set()
    for name in ("windows_identity_not_the_subject_withdrawal.json", "windows_confirmed_and_duplicate_withdrawal.json"):
        prior |= {ident(e) for e in json.loads((SCRIPTS / "audit" / name).read_text(encoding="utf-8"))["entries"]}
    check("A11 no row is shared with AUX-072's or AUX-079's manifest", not (prior & {ident(e) for e in manifest["entries"]}))
    check("A12 the selector is the five fields in order, and the scope is Windows and OBS only",
          wd.SELECTOR == SEL == tuple(manifest["selector"]) and tuple(manifest["products"]) == wd.PRODUCTS == (WIN, OBS))

    print("B  dry run, as the bare script")
    with tempfile.TemporaryDirectory(prefix="aux088-dry-") as tmp:
        store, generated, man = make_tree(Path(tmp))
        before = store.read_bytes()
        proc = run_tool(store, generated, man)
        out = proc.stdout
        check("B1 a dry run exits 0", proc.returncode == 0, proc.stdout[-400:] + proc.stderr[-400:])
        check("B2 a dry run writes nothing", store.read_bytes() == before)
        check("B3 it plans the twenty and keeps the two",
              out.count("[withdraw ") == 20 and out.count("[kept ") == 2, out[-600:])
        check("B4 it reports the counted population each page would lose",
              "microsoft-windows-11 counted population: 3 -> 1" in out and "obs-studio counted population: 29 -> 11" in out
              and "microsoft-windows-11 25H2 26200.7840: 1 -> 0" in out and "obs-studio 32.1.2: 13 -> 3" in out
              and "obs-studio 32.2.2: 8 -> 2" in out and "obs-studio 32.1.1: 2 -> 0" in out, out[-900:])
        check("B5 it says how to apply", "pass --write --confirm-write to apply" in out)

    print("C  the write")
    with tempfile.TemporaryDirectory(prefix="aux088-write-") as tmp:
        store, generated, man = make_tree(Path(tmp))
        before_bytes = store.read_bytes()
        p1 = run_tool(store, generated, man, "--write")
        check("C1 --write without --confirm-write is a usage error and writes nothing",
              p1.returncode == 2 and store.read_bytes() == before_bytes, f"rc={p1.returncode}")
        p2 = run_tool(store, generated, man, "--confirm-write")
        check("C2 --confirm-write without --write is a usage error and writes nothing",
              p2.returncode == 2 and store.read_bytes() == before_bytes, f"rc={p2.returncode}")
        p2b = run_tool(store, generated, man, "--write", "--confirm-write", "--regenerate")
        p2c = run_tool(store, generated, man, "--regenerate")
        check("C3 --regenerate refuses a non-default tree and a run without --write, writing nothing",
              p2b.returncode == 2 and p2c.returncode == 2 and store.read_bytes() == before_bytes
              and "must be the defaults" in p2b.stdout, f"rc={p2b.returncode}/{p2c.returncode}")
        audit_path = Path(tmp) / "audit.json"
        p3 = run_tool(store, generated, man, "--write", "--confirm-write", "--audit", str(audit_path),
                      "--parent-commit", "f" * 40)
        check("C4 --write --confirm-write withdraws and says so",
              p3.returncode == 0 and "WROTE" in p3.stdout and "rows withdrawn by this run: 20" in p3.stdout,
              p3.stdout[-500:] + p3.stderr[-500:])
        before_text, after_text = before_bytes.decode("utf-8"), store.read_bytes().decode("utf-8")
        a_lines, b_lines = before_text.split(NL), after_text.split(NL)
        changed = [(a, b) for a, b in zip(a_lines, b_lines) if a != b]
        reasons = collections.Counter(WITHDRAW.values())
        expected = collections.Counter({("  counted: true", "  counted: false"): 20,
                                        ("  evidence_valid_for_current_patch: true",
                                         "  evidence_valid_for_current_patch: false"): 2})
        for reason, n in reasons.items():
            expected[("  exclusion_reason: null", "  exclusion_reason: " + reason)] = n
        check("C5 exactly 42 lines change: three per Windows row, two per OBS row, each row with its own reason",
              len(a_lines) == len(b_lines) and collections.Counter(changed) == expected and len(changed) == 42,
              f"{len(changed)} changed: {collections.Counter(changed)}")
        after_blocks, before_blocks = blocks_by_identity(after_text), blocks_by_identity(before_text)
        fman = json.loads(man.read_text(encoding="utf-8"))
        fwithdraw = [e for e in fman["entries"] if e["role"] == "withdraw"]
        check("C6 every withdrawn block now hashes to its pinned after-value",
              all([sha(b) for b in after_blocks.get(ident(e), [])] == [e["block_sha256_after"]] for e in fwithdraw))
        rows_b = [r for _lo, _hi, r in aux072.store_blocks(before_text)]
        rows_a = [r for _lo, _hi, r in aux072.store_blocks(after_text)]
        reason_of = {ident(e): e["exclusion_reason"] for e in withdraw}
        moved = [(o, n) for o, n in zip(rows_b, rows_a) if ident(o) in reason_of]

        def expected_row(o: dict) -> dict:
            extra = {"evidence_valid_for_current_patch": False} if o["product_id"] == WIN else {}
            return dict(o, counted=False, exclusion_reason=reason_of[ident(o)], **extra)
        check("C7 the twenty parse as withdrawn with their own reason, every other field unchanged, no field added",
              len(moved) == 20 and all(n == expected_row(o) for o, n in moved)
              and all("evidence_valid_for_current_patch" not in n for o, n in moved if o["product_id"] == OBS))
        parsed_after = {ident(r): r for r in rows_a}
        check("C8 the two kept rows are byte-identical and still count",
              all(after_blocks[ident(e)] == before_blocks[ident(e)] and parsed_after[ident(e)].get("counted") is True
                  for e in retain))
        others = [k for k in before_blocks if k not in reason_of]
        check("C9 no row is added or removed, and every row not withdrawn is byte-identical",
              len(rows_a) == len(rows_b) == 32 and len(others) == 12
              and all(after_blocks.get(k) == before_blocks[k] for k in others))
        check("C10 no row starts counting",
              {ident(r) for r in rows_a if r.get("counted") is True} <= {ident(r) for r in rows_b if r.get("counted") is True})
        check("C11 the evidence-loss guard reads it as an audited withdrawal, not a loss",
              el.losses_between(before_text, after_text) == [])
        deleted = before_text
        for e in withdraw:
            deleted = deleted.replace(before_blocks[ident(e)][0], "", 1)
        unreasoned = after_text
        for reason in reasons:
            unreasoned = unreasoned.replace(NL + "  exclusion_reason: " + reason + NL, NL + "  exclusion_reason: null" + NL)
        losses_del, losses_unr = el.losses_between(before_text, deleted), el.losses_between(before_text, unreasoned)
        check("C12 control: the same rows deleted, or uncounted without a reason, ARE evidence loss",
              len(losses_del) == 20 and all(x.code == el.REMOVED for x in losses_del)
              and len(losses_unr) == 20 and all(x.code == el.UNAUDITED for x in losses_unr),
              f"{[x.code for x in losses_del]} / {[x.code for x in losses_unr]}")
        audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
        check("C13 the audit records the run: hashes, parent, reasons, the twenty and each page's delta",
              audit.get("written") is True and audit.get("withdrawn_now") == 20
              and audit.get("store_sha256_before") == sha(before_bytes)
              and audit.get("store_sha256_after") == sha(after_text) and audit.get("parent_commit") == "f" * 40
              and audit.get("counted_population") == {WIN: [3, 1], OBS: [29, 11]} and len(audit.get("per_patch") or []) == 5
              and audit.get("exclusion_reasons") == sorted(wd.REASONS)
              and sorted(i["action"] for i in audit.get("entries") or []) == ["kept"] * 2 + ["withdraw"] * 20,
              json.dumps({k: audit.get(k) for k in ("written", "withdrawn_now", "counted_population")}))
        deltas = {(p["update_version"], p["target_build"]): p["before"] - p["after"] for p in audit.get("per_patch") or []}
        check("C14 each page loses exactly the rows withdrawn from it under the authoritative count",
              deltas == dict(per_page), str(deltas))

        print("D  idempotence")
        p4 = run_tool(store, generated, man, "--write", "--confirm-write")
        check("D1 a second run exits 0, writes nothing and says so",
              p4.returncode == 0 and "nothing to write" in p4.stdout and store.read_bytes().decode("utf-8") == after_text,
              p4.stdout[-400:] + p4.stderr[-300:])
        check("D2 it reports the twenty as already withdrawn and still keeps the two",
              p4.stdout.count("[already_withdrawn") == 20 and p4.stdout.count("[kept ") == 2)
        check("D3 the population it reports no longer moves",
              "microsoft-windows-11 counted population: 1 -> 1" in p4.stdout and "obs-studio counted population: 11 -> 11" in p4.stdout)

    print("E  fail closed: each unsafe input refuses the whole run and writes nothing")
    b13437 = block_of(text, "32.1.2", "13437")
    drifted = text.replace(b13437, b13437.replace("  severity: ", "  severity: x", 1), 1)
    assert drifted != text
    proc, same = refused("aux088-e1-", drifted, manifest=fixture_manifest())
    check("E1 one drifted pinned row refuses the run, naming the drift",
          proc.returncode == 1 and "block changed since the manifest was pinned" in proc.stdout, proc.stdout[-300:])
    check("E1b all or nothing: the nineteen intact rows are not withdrawn either", same)

    b4494943 = block_of(text, "25H2", "4494943")
    proc, same = refused("aux088-e2-", text + b4494943)
    check("E2 two blocks with one five-field identity refuse the run",
          proc.returncode == 1 and "2 blocks match the five-field identity" in proc.stdout and same, proc.stdout[-300:])

    missing = text.replace(block_of(text, "32.2.2", "14040"), "", 1)
    proc, same = refused("aux088-e3-", missing, manifest=fixture_manifest())
    check("E3 a pinned row that is missing refuses the run",
          proc.returncode == 1 and "0 blocks match the five-field identity" in proc.stdout and same, proc.stdout[-300:])

    bad = fixture_manifest()
    entry_of(bad, "25H2", "6039416")["target_build"] = ""
    proc, same = refused("aux088-e4-", manifest=bad)
    check("E4 a Windows selector without target_build is refused (never by id or URL alone)",
          proc.returncode == 1 and "target_build must be set exactly" in proc.stdout and same, proc.stdout[-300:])
    bad = fixture_manifest()
    entry_of(bad, "32.1.1", "13291")["target_build"] = "32.1.1"
    proc, same = refused("aux088-e4b-", manifest=bad)
    check("E4b an OBS selector WITH a target_build is refused (OBS has no build contract)",
          proc.returncode == 1 and "target_build must be set exactly" in proc.stdout and same, proc.stdout[-300:])
    bad = fixture_manifest()
    entry_of(bad, "32.1.2", "13370")["source_url"] = ""
    proc, same = refused("aux088-e4c-", manifest=bad)
    check("E4c a selector without its source_url is refused",
          proc.returncode == 1 and "lacks part of the five-field identity" in proc.stdout and same, proc.stdout[-300:])
    dup = fixture_manifest()
    dup["entries"].append(copy.deepcopy(dup["entries"][0]))
    proc, same = refused("aux088-e5-", manifest=dup)
    check("E5 an identity listed twice in the manifest is refused",
          proc.returncode == 1 and "listed twice" in proc.stdout and same, proc.stdout[-300:])
    wide = fixture_manifest()
    wide["exclusion_reasons"] = sorted(wd.REASONS | {"identity_not_linked_to_issue"})
    proc, same = refused("aux088-e6-", manifest=wide)
    check("E6 a manifest cannot widen the reason vocabulary",
          proc.returncode == 1 and "differ from the tool's closed vocabulary" in proc.stdout and same, proc.stdout[-300:])
    odd = fixture_manifest()
    entry_of(odd, "32.1.2", "13466")["exclusion_reason"] = "missing_exact_patch_version_match"
    proc, same = refused("aux088-e6b-", manifest=odd)
    check("E6b an entry with a reason outside the closed set is refused",
          proc.returncode == 1 and "outside the closed vocabulary" in proc.stdout and same, proc.stdout[-300:])
    split = fixture_manifest()
    entry_of(split, "32.2.2", "14023")["adjudication"]["second_blind"]["label"] = "UNRESOLVED"
    proc, same = refused("aux088-e7-", manifest=split)
    check("E7 a row without two INCORRECT labels is refused (a disagreement stays counted)",
          proc.returncode == 1 and "lacks two INCORRECT labels" in proc.stdout and same, proc.stdout[-300:])
    nobasis = fixture_manifest()
    entry_of(nobasis, "32.2.2", "14023")["basis"] = " "
    proc, same = refused("aux088-e7b-", manifest=nobasis)
    check("E7b a row without a stated basis is refused",
          proc.returncode == 1 and "stated basis" in proc.stdout and same, proc.stdout[-300:])
    orphan = fixture_manifest()
    orphan["entries"] = [e for e in orphan["entries"] if not (e["role"] == "retain" and short(e)[2] == "13506")]
    proc, same = refused("aux088-e8-", manifest=orphan)
    check("E8 a duplicate whose kept row is not pinned is refused",
          proc.returncode == 1 and "names no pinned kept row" in proc.stdout and same, proc.stdout[-300:])
    unnamed = fixture_manifest()
    del entry_of(unnamed, "32.1.2", "195407")["duplicate_of"]
    proc, same = refused("aux088-e8b-", manifest=unnamed)
    check("E8b a duplicate that names no kept row is refused",
          proc.returncode == 1 and "a duplicate must name its kept row" in proc.stdout and same, proc.stdout[-300:])

    kept13506 = block_of(text, "32.1.2", "13506")
    changed_kept = text.replace(kept13506, kept13506.replace("  severity: ", "  severity: x", 1), 1)
    assert changed_kept != text
    proc, same = refused("aux088-e9-", changed_kept, manifest=fixture_manifest())
    check("E9 a changed kept row refuses the run",
          proc.returncode == 1 and "kept row changed" in proc.stdout and same, proc.stdout[-300:])
    uncounted_kept = kept13506.replace("  counted: true" + NL, "  counted: false" + NL, 1)
    uncounted_text = text.replace(kept13506, uncounted_kept, 1)
    message, _ = in_process_plan(uncounted_text, fixture_manifest(uncounted_text))
    check("E10 a kept row that no longer counts refuses the run", "kept row no longer counts" in message, message[:300])

    moved_target = targets_fixture()
    for t in moved_target:
        if t["front_matter"].get("target_build") == "26200.7840":
            t["front_matter"]["target_kb"] = "KB5999999"
    proc, same = refused("aux088-e11-", None, moved_target)
    check("E11 a Windows record whose target identity moved refuses the run",
          proc.returncode == 1 and "record target identity moved" in proc.stdout and same, proc.stdout[-300:])
    no_obs = [t for t in targets_fixture() if t["front_matter"].get("update_version") != "32.2.2"]
    proc, same = refused("aux088-e12-", None, no_obs)
    check("E12 an OBS page whose record is missing refuses the run",
          proc.returncode == 1 and "0 records carry the identity obs-studio 32.2.2" in proc.stdout and same, proc.stdout[-300:])
    twice = targets_fixture()
    twice.append(dict(next(t for t in twice if t["front_matter"].get("update_version") == "32.1.1"),
                      file="2026-04-02-obs-studio-32-1-1-copy.md"))
    proc, same = refused("aux088-e12b-", None, twice)
    check("E12b an OBS page with two records refuses the run",
          proc.returncode == 1 and "2 records carry the identity obs-studio 32.1.1" in proc.stdout and same, proc.stdout[-300:])
    renamed = fixture_manifest()
    entry_of(renamed, "32.1.2", "13437")["record_file"] = "auxsays/updates/generated/2026-04-21-obs-studio-32-1-2-old.md"
    proc, same = refused("aux088-e12c-", manifest=renamed)
    check("E12c a record that is not the pinned file refuses the run",
          proc.returncode == 1 and "not the pinned" in proc.stdout and same, proc.stdout[-300:])

    w195407 = block_of(text, "32.1.2", "195407")
    late_kept = kept13506.replace("  captured_at: '2026-05-31T", "  captured_at: '2026-12-31T", 1)
    assert late_kept != kept13506
    late_text = text.replace(kept13506, late_kept, 1)
    message, _ = in_process_plan(late_text, fixture_manifest(late_text))
    check("E13 keep-first: a duplicate whose kept row is the LATER capture is refused",
          "the kept row is not the earlier capture" in message, message[:300])
    elsewhere = fixture_manifest()
    other = next(e for e in elsewhere["entries"] if e["role"] == "retain" and short(e)[2] == "13997")
    entry_of(elsewhere, "32.1.2", "195407")["duplicate_of"] = {k: other[k] for k in SEL}
    entry_of(elsewhere, "32.2.2", "196545")["duplicate_of"] = {k: other[k] for k in SEL}
    elsewhere["entries"] = [e for e in elsewhere["entries"] if not (e["role"] == "retain" and short(e)[2] == "13506")]
    message, _ = in_process_plan(text, elsewhere)
    check("E14 a duplicate whose kept row is on another page is refused",
          "the kept row is on another patch" in message, message[:300])

    already_other = text.replace(w195407, w195407.replace("  counted: true" + NL + "  exclusion_reason: null",
                                                          "  counted: false" + NL + "  exclusion_reason: cross_patch_duplicate"), 1)
    assert already_other != text
    proc, same = refused("aux088-e15-", already_other, manifest=fixture_manifest())
    check("E15 a row already withdrawn for ANOTHER reason is never rewritten",
          proc.returncode == 1 and "block changed since the manifest was pinned" in proc.stdout and same, proc.stdout[-300:])

    b13291 = block_of(text, "32.1.1", "13291")
    try:
        wd.withdraw_block(b13291.replace("  counted: true" + NL, "  counted: true" + NL
                                         + "  evidence_valid_for_current_patch: true" + NL, 1), OBS, INTS)
        obs_shape = False
    except wd.Refusal:
        obs_shape = True
    check("E16 an OBS block carrying a validity line is an unexpected shape", obs_shape)
    try:
        wd.withdraw_block(b13291 + "  counted: true" + NL, OBS, INTS)
        doubled = False
    except wd.Refusal:
        doubled = True
    check("E16b the edit refuses a block in which a line to edit occurs twice", doubled)
    try:
        wd.withdraw_block(b4494943.replace("  evidence_valid_for_current_patch: true" + NL, "", 1), WIN, INTS)
        win_shape = False
    except wd.Refusal:
        win_shape = True
    check("E16c a Windows block without its validity line is an unexpected shape", win_shape)

    edit_for = wd.edit_for
    try:
        wd.edit_for = lambda product, reason: tuple((old, new.replace(": " + reason, ": '" + reason + "'"))
                                                    for old, new in edit_for(product, reason))
        message, _ = in_process_plan(text)
    finally:
        wd.edit_for = edit_for
    check("E17 an edit whose BYTES differ from the pinned after-block is refused even if it parses the same",
          "does not produce the pinned block" in message, message[:300])
    widened = fixture_manifest()
    extra_old, extra_new = NL + "  severity: high" + NL, NL + "  severity: low" + NL
    for e in widened["entries"]:
        if e["role"] == "withdraw":
            block = blocks_by_identity(text)[ident(e)][0]
            e["block_sha256_after"] = sha(own_edit(block, e["product_id"], e["exclusion_reason"]).replace(extra_old, extra_new, 1))
    try:
        wd.edit_for = lambda product, reason: edit_for(product, reason) + ((extra_old, extra_new),)
        _bw = wd.withdraw_block

        def lenient(block: str, product: str, reason: str) -> str:
            for old, new in wd.edit_for(product, reason):
                block = block.replace(old, new, 1)
            return block
        wd.withdraw_block = lenient
        message, _ = in_process_plan(text, widened)
    finally:
        wd.edit_for = edit_for
        wd.withdraw_block = _bw
    check("E18 a pinned after-hash cannot authorise another field: the edit is proved field by field",
          "changed more than decided" in message, message[:300])
    foreign = fixture_manifest()
    entry_of(foreign, "32.2.2", "14117")["product_id"] = "blackmagic-davinci"
    proc, same = refused("aux088-e19-", manifest=foreign)
    check("E19 a row of any product but Windows and OBS is refused",
          proc.returncode == 1 and "not a Windows or OBS row" in proc.stdout and same, proc.stdout[-300:])
    scope = fixture_manifest()
    scope["products"] = [WIN, OBS, "blackmagic-davinci"]
    proc, same = refused("aux088-e19b-", manifest=scope)
    check("E19b a manifest cannot widen the product scope",
          proc.returncode == 1 and "product scope differs" in proc.stdout and same, proc.stdout[-300:])

    # A pinned row stored UNCOUNTED, with an edit and a field set that would turn it back on: the field
    # proof agrees with the edit, so only the "no row starts counting" guard can refuse it.
    off = b13437.replace("  counted: true" + NL, "  counted: false" + NL, 1)
    off_text = text.replace(b13437, off, 1)
    turn_on = fixture_manifest()
    on_entry = entry_of(turn_on, "32.1.2", "13437")
    on_entry["block_sha256_before"] = sha(off)
    on_entry["block_sha256_after"] = sha(off.replace(NL + "  exclusion_reason: null" + NL,
                                                     NL + "  exclusion_reason: " + INTS + NL, 1)
                                         .replace(NL + "  counted: false" + NL, NL + "  counted: true" + NL, 1))
    fields = wd.withdrawn_fields
    try:
        wd.edit_for = lambda product, reason: ((NL + "  counted: false" + NL, NL + "  counted: true" + NL),
                                               (NL + "  exclusion_reason: null" + NL, NL + "  exclusion_reason: " + reason + NL))
        wd.withdrawn_fields = lambda product, reason: {"counted": True, "exclusion_reason": reason}
        entries = [e for e in turn_on["entries"] if e is on_entry]
        try:
            with tempfile.TemporaryDirectory(prefix="aux088-e20-") as tmp:
                _s, generated, _m = make_tree(Path(tmp), off_text)
                wd.plan(off_text, wd.manifest_entries(dict(turn_on, entries=entries)), wd.patch_records(generated))
            message = ""
        except wd.Refusal as exc:
            message = str(exc)
    finally:
        wd.edit_for = edit_for
        wd.withdrawn_fields = fields
    check("E20 an edit that would make a row count is refused, even when the field proof agrees with it",
          "a row would start counting" in message, message[:300])

    # A "duplicate" whose kept row is the SAME report under another id: one report, not a cross-post.
    twin = (w195407.replace("- id: obs-studio-32-1-2-obs-forum-thread-195407", "- id: obs-studio-32-1-2-obs-forum-thread-195407-twin", 1)
            .replace("  captured_at: '2026-10-16T", "  captured_at: '2026-01-16T", 1))
    assert twin.count("-195407-twin") == 1 and "2026-01-16T" in twin
    twin_text = text + twin
    same_url = fixture_manifest(twin_text)
    twin_row = next(r for _lo, _hi, r in aux072.store_blocks(twin_text) if r["id"].endswith("-twin"))
    same_url["entries"] = [e for e in same_url["entries"] if not (e["role"] == "retain" and short(e)[2] == "13506")]
    same_url["entries"].append({"role": "retain", **{k: str(twin_row.get(k) or "") for k in SEL},
                                "record_file": "auxsays/updates/generated/2026-04-21-obs-studio-32-1-2.md",
                                "block_sha256_before": sha(twin)})
    dup195407 = next(e for e in same_url["entries"] if e["role"] == "withdraw" and short(e)[2] == "195407")
    dup195407["duplicate_of"] = {k: str(twin_row.get(k) or "") for k in SEL}
    message, _ = in_process_plan(twin_text, same_url)
    check("E21 a duplicate whose kept row is the same report URL is refused",
          "the kept row is the same report URL" in message, message[:300])

    print("F  no re-homing")
    with tempfile.TemporaryDirectory(prefix="aux088-f-") as tmp:
        store, generated, man = make_tree(Path(tmp))
        before = store.read_bytes().decode("utf-8")
        audit_path = Path(tmp) / "audit.json"
        proc = run_tool(store, generated, man, "--write", "--confirm-write", "--audit", str(audit_path))
        after = store.read_bytes().decode("utf-8")
        audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
        sib = audit.get("same_report_rows_on_other_identities") or []
        sib_keys = {short(s) for s in sib}
        expected_sib = {("31.1.2", "", "13995"), ("32.2.2", "", "13995"), ("33.0.0", "", "14088"), ("33.0.1", "", "14152"),
                        ("33.0.0", "", "14117"), ("33.0.1", "", "196824"), ("32.1.2", "", "196545")}
        b_blocks, a_blocks = blocks_by_identity(before), blocks_by_identity(after)
        check("F1 the same report stored on another identity is left byte-identical and still counted",
              proc.returncode == 0 and sib_keys == expected_sib
              and all(s["unchanged"] is True and s["counted"] is True for s in sib)
              and all(a_blocks[ident(s)] == b_blocks[ident(s)] for s in sib), json.dumps(sorted(sib_keys)))
        check("F2 it is reported, never re-attributed: no row starts counting",
              audit.get("newly_counted_rows") == [] and len(sib) == 7)

    print("G  the committed store, and this suite changed nothing real")
    live_text = live_store.read_bytes().decode("utf-8")
    live_rows = blocks_by_identity(live_text)
    live_parsed = {ident(r): r for _lo, _hi, r in aux072.store_blocks(live_text)}
    check("G1 the committed store holds each of the twenty exactly once, withdrawn with its own reason",
          all(len(live_rows.get(ident(e), [])) == 1 and live_parsed[ident(e)].get("counted") is False
              and live_parsed[ident(e)].get("exclusion_reason") == e["exclusion_reason"]
              and sha(live_rows[ident(e)][0]) == e["block_sha256_after"] for e in withdraw),
          str([e["id"][-24:] for e in withdraw if live_parsed.get(ident(e), {}).get("counted") is not False]))
    live_baseline = wd.load_baseline(wd.BASELINE)
    check("G2 the two kept rows are stored once and counted, unchanged but for a recorded later audited change",
          all(len(live_rows.get(ident(e), [])) == 1
              and wd._pin_holds(e, "block_sha256_before", sha(live_rows[ident(e)][0]), live_baseline)  # noqa: SLF001
              and live_parsed[ident(e)].get("counted") is True for e in retain))
    stay = collections.Counter(short(r) for r in live_parsed.values()
                               if short(r) in STAY_COUNTED and r.get("product_id") in (WIN, OBS))
    stay_counted = {short(r) for r in live_parsed.values() if short(r) in STAY_COUNTED and r.get("counted") is True}
    check("G3 every row the reviews disagree on is still stored once and still counts",
          set(stay) == STAY_COUNTED and set(stay.values()) == {1} and stay_counted == STAY_COUNTED,
          str(sorted(STAY_COUNTED - stay_counted)))
    successors_hold = []
    for b in json.loads(wd.BASELINE.read_text(encoding="utf-8"))["entries"]:
        hits = live_rows.get(ident(b), [])
        line = "  source_date: '" + b["change"]["source_date"] + "'" + NL
        undone = {hits[0].replace(line, "", 1), hits[0].replace(line, "  source_date: null" + NL, 1)} if hits else set()
        successors_hold.append(len(hits) == 1 and sha(hits[0]) == b["block_sha256_now"] and hits[0].count(line) == 1
                               and b["block_sha256_pinned"] in {sha(u) for u in undone})
    check("G5 every recorded successor is stored, byte for byte, as its pinned block plus exactly its one date line",
          len(successors_hold) == 3 and all(successors_hold), str(successors_hold))
    live_after = {str(p): sha(p.read_bytes()) for p in live_files if p.exists()}
    check("G4 the live store and the five records are byte-identical after the suite",
          live_after == live_before and len(live_before) == 6, f"{len(live_before)} files")

    print("H  later audited changes to pinned rows: the versioned supplemental baseline (AUX-090)")
    base_doc = json.loads(wd.BASELINE.read_text(encoding="utf-8"))
    dates = {ident(e): e for e in
             json.loads((SCRIPTS / "audit" / "obs_report_dates.json").read_text(encoding="utf-8"))["entries"]}
    v2doc = json.loads((SCRIPTS / "audit" / "live_citation_withdrawal_v2.json").read_text(encoding="utf-8"))
    pins = {}
    for path, d in (("auxsays/scripts/audit/live_citation_withdrawal.json", manifest),
                    ("auxsays/scripts/audit/live_citation_withdrawal_v2.json", v2doc)):
        for e in d["entries"]:
            pins[(path, ident(e))] = e

    def recorded(b: dict) -> bool:
        pin = pins.get((b.get("pinned_by"), ident(b)))
        date = dates.get(ident(b))
        if not pin or not date:
            return False
        key = "block_sha256_before" if pin["role"] == "retain" else "block_sha256_after"
        return (pin[key] == b["block_sha256_pinned"] == date["block_sha256_before"]
                and b["block_sha256_now"] == date["block_sha256_after"]
                and b["change"] == {"source_date": date["source_date"]} and "AUX-090" in b["changed_by"])
    check("H1 the baseline is version 2 of the five-field selector, and each entry is a pin of AUX-088's or v2's "
          "manifest moved by exactly its AUX-090 date",
          base_doc.get("version") == 2 and tuple(base_doc.get("selector") or ()) == SEL and len(base_doc["entries"]) == 3
          and all(recorded(b) for b in base_doc["entries"])
          and {(b["update_version"], report_id(b["source_url"])) for b in base_doc["entries"]}
          == {("32.1.2", "13506"), ("32.2.2", "13997"), ("32.1.2", "13997")})
    check("H2 the AUX-088 manifest and its run audit are byte-identical to the files AUX-088 committed",
          all(sha((SCRIPTS / "audit" / name).read_bytes()) == digest for name, digest in AUX088_FILES.items()))
    kept_entry = entry_of(fixture_manifest(), "32.1.2", "13506")
    dated_kept = own_date_edit(kept13506, "2026-05-20")
    dated_text = text.replace(kept13506, dated_kept, 1)
    ok, result = plan_with(dated_text, fixture_manifest(), {ident(kept_entry): {sha(kept13506): sha(dated_kept)}})
    without, _ = plan_with(dated_text, fixture_manifest(), {})
    check("H3 a kept row moved by exactly a recorded change stays kept; without the baseline the same change refuses",
          ok == "" and result is not None
          and [e["action"] for e in result["entries"] if short(e) == ("32.1.2", "", "13506")] == ["kept"]
          and "kept row changed" in without, ok[:200] + without[:200])
    message, _ = plan_with(dated_text, fixture_manifest(), {ident(kept_entry): {"f" * 64: sha(dated_kept)}})
    check("H4 a successor recorded against another pinned hash does not excuse the change",
          "kept row changed" in message, message[:200])
    w_entry = entry_of(fixture_manifest(), "32.1.2", "195407")
    dated_w = own_date_edit(w195407, "2026-05-21")
    message, _ = plan_with(text.replace(w195407, dated_w, 1), fixture_manifest(),
                           {ident(w_entry): {sha(w195407): sha(dated_w)}})
    check("H5 a recorded successor never excuses a row still to withdraw: its edit must start from the pinned bytes",
          "block changed since the manifest was pinned" in message, message[:200])
    withdrawn_w = own_edit(w195407, OBS, DUP)
    moved_w = own_date_edit(withdrawn_w, "2026-05-21")
    moved_text = text.replace(w195407, moved_w, 1)
    ok, result = plan_with(moved_text, fixture_manifest(), {ident(w_entry): {sha(withdrawn_w): sha(moved_w)}})
    without, _ = plan_with(moved_text, fixture_manifest(), {})
    check("H6 an already withdrawn row moved by a recorded change reads as already withdrawn; unrecorded, it refuses",
          ok == "" and result is not None
          and [e["action"] for e in result["entries"] if short(e) == ("32.1.2", "", "195407")] == ["already_withdrawn"]
          and "block changed since the manifest was pinned" in without, ok[:200] + without[:200])
    good = dict({k: kept_entry[k] for k in SEL}, block_sha256_pinned="a" * 64, block_sha256_now="b" * 64,
                change={"source_date": "2026-05-20"}, changed_by="AUX-090")
    bad_docs = {
        "unversioned": {"selector": list(SEL), "entries": [good]},
        "same hash": {"selector": list(SEL), "version": 2, "entries": [dict(good, block_sha256_now="a" * 64)]},
        "no change": {"selector": list(SEL), "version": 2, "entries": [dict(good, change={})]},
        "unaudited": {"selector": list(SEL), "version": 2, "entries": [dict(good, changed_by=" ")]},
        "twice": {"selector": list(SEL), "version": 2, "entries": [good, dict(good, block_sha256_now="c" * 64)]},
    }
    outcomes = {}
    with tempfile.TemporaryDirectory(prefix="aux088-h7-") as tmp:
        for name, bad in bad_docs.items():
            path = Path(tmp) / (name.replace(" ", "_") + ".json")
            path.write_text(json.dumps(bad), encoding="utf-8")
            try:
                wd.load_baseline(path)
                outcomes[name] = "loaded"
            except wd.Refusal as exc:
                outcomes[name] = str(exc)
        good_path = Path(tmp) / "good.json"
        good_path.write_text(json.dumps({"selector": list(SEL), "version": 2, "entries": [good]}), encoding="utf-8")
        loaded = wd.load_baseline(good_path)
        empty = wd.load_baseline(Path(tmp) / "absent.json")
    check("H7 a malformed baseline refuses (unversioned, unchanged hash, no change, no audit, a pin twice); "
          "a well-formed one loads; an absent one is empty",
          all(v.startswith("baseline:") for v in outcomes.values()) and empty == {}
          and loaded == {ident(good): {"a" * 64: "b" * 64}}, json.dumps(outcomes)[:300])
    with tempfile.TemporaryDirectory(prefix="aux088-h8-") as tmp:
        store, generated, man = make_tree(Path(tmp), dated_text)
        bl_path = Path(tmp) / "baseline.json"
        bl_path.write_text(json.dumps({"selector": list(SEL), "version": 2, "entries": [dict(
            {k: kept_entry[k] for k in SEL}, block_sha256_pinned=sha(kept13506), block_sha256_now=sha(dated_kept),
            change={"source_date": "2026-05-20"}, changed_by="AUX-090")]}), encoding="utf-8")
        with_bl = run_tool(store, generated, man, "--baseline", str(bl_path))
        without_bl = run_tool(store, generated, man, "--baseline", str(Path(tmp) / "absent.json"))
        unchanged = store.read_bytes() == dated_text.encode("utf-8")
    check("H8 the bare script reads --baseline: with the recorded change the dry run plans; without it, it refuses",
          with_bl.returncode == 0 and "[kept             ] obs-studio 32.1.2" in with_bl.stdout
          and without_bl.returncode == 1 and "kept row changed" in without_bl.stdout and unchanged,
          with_bl.stdout[-300:] + without_bl.stdout[-300:])

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
