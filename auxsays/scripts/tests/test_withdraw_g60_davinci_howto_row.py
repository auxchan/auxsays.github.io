#!/usr/bin/env python3
"""The audited withdrawal of one DaVinci Resolve 21.0.4 report that is a how-to question (AUX-114).

`withdraw_live_citation_rows.py` (the AUX-088 mechanism, unchanged) withdraws, with a sixth pinned manifest
(audit/live_citation_withdrawal_v6.json), the one stored row that TWO independent blind adjudications labelled
INCORRECT for the credited version: a question asking whether HDR can be enabled in the previews on Linux, in which
21.0.4 is the version the author runs, not a version reported as having a problem. An earlier pair of blind labels
on the same row (AUX-108's control finding) is recorded as provenance only. Its contract, pinned here:

  A  the committed manifest names exactly that row by its full five-field identity, with the reason both blind
     reviews support and two blind INCORRECT labels from two different named reviewers, the earlier labels as
     provenance only; the scope is Windows, OBS and DaVinci and no product grant is involved; the row's two
     controls, the three held candidates and the control finding are listed and are not entries; it shares no row
     with an earlier withdrawal or re-admission manifest; it records the blind packet's hashes; the tool's own
     manifest reader accepts it
  V  the five earlier manifests (v1-v5) are byte-identical to their pins and still accepted, and AUX-108's manifest
     still records this row as its control finding and the 20.2.1 row as held out
  B  a dry run plans the one row and writes nothing
  C  --write --confirm-write changes exactly 2 lines, keeps every row, leaves every other row (the same-page
     must-stay control, the other-version control, the held 20.2.1 row and every Windows, OBS and DaVinci row)
     byte-identical and counted, starts no row counting, and the evidence-loss guard reads it as an audited
     withdrawal; the fixture's counts fall by exactly the one row
  D  a second run changes nothing
  R  re-admission: the append guard the DaVinci lanes write through (base.append_evidence_rows) refuses the
     withdrawn report seen again (same id and URL, another URL spelling), so it stays withdrawn; a report the store
     does not hold is still appended
  E  the two-blind rule is not vacuous, and the tool fails closed on a drifted block or on a held row with no two
     INCORRECT labels
  F  --regenerate for this manifest runs the reconcile and one scoped promotion per declared product, never
     unscoped
  G  the committed store holds the row as withdrawn at its pinned after-hash; its two controls and the three held
     rows (DaVinci 20.2.1, Acrobat Reader 15.010.20056, Premiere Pro 26.2) still count; this suite changed nothing
     real

The tool runs as a BARE script, so B-E run it as a subprocess, exactly as an operator would. Offline: the frozen
AUX-108 fixture (tests/fixtures/live_citation/g51_role_store.yml, 18 rows whose free text is synthetic, among them
this row and the held 20.2.1 row) plus two synthetic blocks this suite derives from it for the row's two controls,
and the AUX-108 records' identity front matter plus the 21.0.4 record's. The suite re-pins the manifest's block
hashes on the fixture with its OWN line edit. No live-corpus count is asserted anywhere.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_withdraw_g60_davinci_howto_row.py
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
MANIFEST = AUDIT / "live_citation_withdrawal_v6.json"
FIX = SCRIPTS / "tests" / "fixtures" / "live_citation"
STORE_FIXTURE = FIX / "g51_role_store.yml"
TARGETS = FIX / "g51_role_targets.json"
NL = chr(10)
SEL = ("product_id", "update_version", "target_build", "id", "source_url")
WIN, OBS, DAV = "microsoft-windows-11", "obs-studio", "blackmagic-davinci"
READER, PREMIERE = "adobe-acrobat-reader", "adobe-premiere-pro"
INCORRECT = "INCORRECT"
REASON = "not_a_real_issue_report"
PARENT = "0e84d3942f009211c40043fdf69cbfe3c0ba6f58"
RECORD = "2026-08-05-davinci-resolve-21-0-4.md"

# The row both blind reviews labelled INCORRECT, written out in full here so neither the manifest nor the fixture can
# redefine it.
D2 = (DAV, "21.0.4", "",
      "blackmagic-davinci-21-0-4-reddit-community-report-https-www-reddit-com-r-davinciresolve-comments-1w23ivu-linux-is-"
      "there-a-way-to-enable-hdr-in-the",
      "https://www.reddit.com/r/davinciresolve/comments/1w23ivu/linux_is_there_a_way_to_enable_hdr_in_the/")
# Its two controls, which stay counted: the must-stay row on its own page, and a row of another version.
P08 = (DAV, "21.0.4", "",
       "blackmagic-davinci-21-0-4-reddit-community-report-https-www-reddit-com-r-davinciresolve-comments-1vkctcb-i-cant-"
       "get-davinci-to-export",
       "https://www.reddit.com/r/davinciresolve/comments/1vkctcb/i_cant_get_davinci_to_export/")
P05 = (DAV, "21", "",
       "blackmagic-davinci-21-reddit-community-report-https-www-reddit-com-r-davinciresolve-comments-1w927vk-why-isnt-my-"
       "gpu-being-recognized-resolve",
       "https://www.reddit.com/r/davinciresolve/comments/1w927vk/why_isnt_my_gpu_being_recognized_resolve_21/")
# The three other candidates both reviews labelled INCORRECT, held by the ruling: they stay counted.
HELD = {(DAV, "20.2.1", "", "1noccl9"), (READER, "15.010.20056", "", "594365"), (PREMIERE, "26.2", "", "1653348")}
FINDING = {(READER, "15.010.20056", "", "604847")}  # A1's must-stay control, labelled INCORRECT by both: recorded
# The blind adjudication's own files, by hash (the packet, its brief, the control rule fixed before the draw, A, B).
PACKET_HASHES = {
    "packet_sha256": "ab9e1c6cea79fc011144d9a3981619a43a1e84a081bea014a6435f571749573b",
    "brief_sha256": "e7f69f4115191c3ae9061d5956a10ee2cb7422880e603237ae3badae4876ee34",
    "control_rule_sha256": "83ee18570be71b57039b6bf014ad0ec9219e471449890aba9d22d4392ca47bfb",
    "labels_a_sha256": "65d08886f58c045e26e9d8b1da047fd4666e733bbf8c1e1cfbc0038eebac9111",
    "labels_b_sha256": "a7fc9f8d4f6f92068434b0dec3f42020352ea3bfb5dafb2531f616876d8b1ee9",
}
# The five earlier manifests of this tool, which this one must leave byte-identical.
EARLIER = {
    "live_citation_withdrawal.json": "e7fda1cf2cdf42a1dc88a8ab962c2ef3fbaec9599bff26077a6880f0247d9d24",
    "live_citation_withdrawal_v2.json": "51adfe324fed5eaea98a46e3857b9a737847d7f91a8777e332a793ad161d1490",
    "live_citation_withdrawal_v3.json": "eae1abf5d5f9f2c5be3c09fa1ea59b37438457a2ff01cb0309bc1ee62b9b588d",
    "live_citation_withdrawal_v4.json": "6394217b309b02fddf0b89ee1fe0773e01e26552c2b00a4ae3d8c48b0a705bc3",
    "live_citation_withdrawal_v5.json": "4cba0edcdea03d3406999891e8b6960c1fb9f23da72badda252208813935826d",
}
PRIOR = {  # the earlier audited manifests this one must not overlap
    "AUX-072": "windows_identity_not_the_subject_withdrawal.json",
    "AUX-079": "windows_confirmed_and_duplicate_withdrawal.json",
    "AUX-088": "live_citation_withdrawal.json",
    "AUX-090": "live_citation_withdrawal_v2.json",
    "AUX-098": "live_citation_withdrawal_v3.json",
    "AUX-108": "live_citation_withdrawal_v4.json",
    "AUX-110": "acrobat_reader_readmission.json",
    "AUX-111": "live_citation_withdrawal_v5.json",
}
# Fixture-based count deltas (20 fixture rows; never the live corpus).
PER_PAGE = {(DAV, "21.0.4", ""): (2, 1)}
POPULATION = {WIN: [4, 4], OBS: [1, 1], DAV: [15, 14]}

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
    """The post or thread number a URL names: a Reddit post id, a Learn question number, or the number an Adobe
    Community URL ends with."""
    tail = str(url or "").rstrip("/")
    if "/comments/" in tail:
        return tail.split("/comments/", 1)[1].split("/", 1)[0]
    if "/answers/questions/" in tail:
        return tail.split("/answers/questions/", 1)[1].split("/", 1)[0]
    return tail.rsplit("-", 1)[-1]


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


def blocks_by_identity(text: str) -> dict[tuple[str, ...], list[str]]:
    out: dict[tuple[str, ...], list[str]] = {}
    for lo, hi, row in aux072.store_blocks(text):
        out.setdefault(ident(row), []).append(text[lo:hi])
    return out


def synthetic_control(d2_block: str, control: tuple[str, ...], version_line: str) -> str:
    """A control row for the fixture, derived from the fixture's own D2 block: another report's id and URL, synthetic
    marker text, and the control's version."""
    block = d2_block.replace("- id: " + D2[3] + NL, "- id: " + control[3] + NL, 1)
    block = block.replace("  source_url: " + D2[4] + NL, "  source_url: " + control[4] + NL, 1)
    block = block.replace("(AUX-108)", "(AUX-114)")
    if control[1] != D2[1]:
        block = block.replace("  update_version: 21.0.4" + NL, "  update_version: " + version_line + NL, 1)
        block = block.replace("  matched_version: 21.0.4" + NL, "  matched_version: " + version_line + NL, 1)
        block = block.replace("  target_release_date: '2026-08-05'" + NL, "  target_release_date: '2026-04-14'" + NL, 1)
    assert block != d2_block and control[3] in block and control[4] in block, control[3]
    return block


def fixture_text() -> str:
    """The AUX-108 fixture plus this row's two controls, appended as synthetic rows."""
    text = STORE_FIXTURE.read_bytes().decode("utf-8")
    d2_block = blocks_by_identity(text)[D2][0]
    if not text.endswith(NL):
        text += NL
    return text + synthetic_control(d2_block, P08, "21.0.4") + synthetic_control(d2_block, P05, "'21'")


def targets_fixture() -> list[dict]:
    targets = json.loads(TARGETS.read_text(encoding="utf-8"))
    return targets + [{"file": RECORD, "front_matter": {"update_entry": True, "product_id": DAV,
                                                       "update_version": "21.0.4"}}]


def manifest_doc() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


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


def refused(prefix: str, store_text: str | None = None, targets: list[dict] | None = None,
            manifest: dict | None = None) -> tuple[subprocess.CompletedProcess, bool]:
    """Run --write --confirm-write on a fixture tree and report whether the store came back byte-identical."""
    with tempfile.TemporaryDirectory(prefix=prefix) as tmp:
        store, generated, man = make_tree(Path(tmp), store_text, targets, manifest)
        before = store.read_bytes()
        proc = run_tool(store, generated, man, "--write", "--confirm-write")
        return proc, store.read_bytes() == before


def reader_refusal(doc: dict) -> str:
    """The manifest reader's own verdict, in process: '' when it accepts, else its refusal text. Any other exception
    comes back as its type and text, so a crash is never mistaken for an acceptance or a refusal."""
    try:
        wd.manifest_entries(doc)
    except wd.Refusal as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001
        return f"CRASH {type(exc).__name__}: {exc}"
    return ""


def row_of(text: str, key: tuple[str, ...]) -> tuple[str, dict]:
    hits = [(text[lo:hi], row) for lo, hi, row in aux072.store_blocks(text) if ident(row) == key]
    assert len(hits) == 1, (key[3], len(hits))
    return hits[0]


def supported(label: dict) -> set[str]:
    return {str(label.get("reason_class") or ""), str(label.get("alternative_reason_class") or "")} - {""}


def two_blind(entry: dict) -> bool:
    """The suite's own reading of the rule: two independently established INCORRECT determinations, the blind
    reviews (second_blind, third_blind): both INCORRECT, two different named reviewers, neither the first audit,
    the same packet case, each with a reason, and the row's reason one BOTH support. The first audit (here an earlier
    pair of blind labels) is provenance (INCORRECT, as the tool's two-label check requires) and never one of the
    two."""
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
    print("Audited withdrawal of one DaVinci Resolve 21.0.4 report that is a how-to question (AUX-114)")
    print("=" * 78)
    live_store = ROOT / "_data" / "consensus_evidence.yml"
    live_files = [live_store, ROOT / "updates" / "generated" / RECORD]
    live_before = {str(p): sha(p.read_bytes()) for p in live_files if p.exists()}
    manifest = manifest_doc()
    text = fixture_text()
    withdraw = [e for e in manifest["entries"] if e.get("role") == "withdraw"]

    print("A  the pinned manifest")
    check("A1 one DaVinci row is withdrawn and none is kept, under ledger AUX-114, version 6",
          len(withdraw) == 1 and len(manifest["entries"]) == 1 and manifest.get("ledger") == "AUX-114"
          and manifest.get("version") == 6 and withdraw[0].get("product_id") == DAV,
          f"{len(withdraw)} withdraw of {len(manifest['entries'])}")
    check("A2 the withdrawn row is exactly the 21.0.4 how-to question, by its full five-field identity, with the "
          "reason both blind reviews support",
          [ident(e) for e in withdraw] == [D2] and [e.get("exclusion_reason") for e in withdraw] == [REASON],
          str([ident(e)[3][-40:] for e in withdraw]))
    check("A3 the selector, the closed reasons and the Windows, OBS and DaVinci scope are the tool's own; DaVinci has "
          "no product grant, so no grant is involved",
          tuple(manifest["selector"]) == SEL and sorted(manifest["exclusion_reasons"]) == sorted(wd.REASONS)
          and tuple(manifest["products"]) == wd.EXTENDED_PRODUCTS == (WIN, OBS, DAV)
          and DAV not in wd.PRODUCT_GRANTS and all(wd._grant_refusal(ident(e)) == "" for e in withdraw))
    check("A4 the row carries two blind INCORRECT labels from two different named reviewers on one packet case that "
          "both support its reason (the suite's reading and the tool's two-label check agree); the earlier labels "
          "are provenance only",
          all(two_blind(e) and wd._two_labels(e) and str(e.get("basis") or "").strip() for e in withdraw)
          and [e["adjudication"]["second_blind"]["case"] for e in withdraw] == ["P11"],
          str([e["id"][-30:] for e in withdraw if not two_blind(e)]))
    stay = {ident(r) for r in manifest.get("must_stay_counted", [])}
    held = {short(r) for h in manifest.get("held_out", []) for r in h["rows"]}
    found = {short(r) for h in manifest.get("findings_not_withdrawn", []) for r in h["rows"]}
    entries = {ident(e) for e in manifest["entries"]}
    check("A5 the row's two controls, the three held candidates and the control finding are listed (each held row "
          "and the finding with a reason) and none is an entry",
          stay == {P08, P05} and held == HELD and found == FINDING
          and all(str(h.get("why") or "").strip() for h in manifest["held_out"] + manifest["findings_not_withdrawn"])
          and not ({short(dict(zip(SEL, k))) for k in entries} & (HELD | FINDING)) and not (entries & stay))
    prior_ids, prior_reports = set(), set()
    for name in PRIOR.values():
        doc = json.loads((AUDIT / name).read_text(encoding="utf-8"))
        prior_ids |= {ident(e) for e in doc["entries"]}
        prior_reports |= {short(e) for e in doc["entries"]}
    check("A6 no row (by five-field identity, or by page and report) is shared with AUX-072's, AUX-079's, AUX-088's, "
          "AUX-090's, AUX-098's, AUX-108's, AUX-110's or AUX-111's manifest",
          not (prior_ids & entries) and not (prior_reports & {short(e) for e in withdraw}))
    packet = manifest.get("adjudication_packet") or {}
    check("A7 the row pins its record; the manifest records the blind packet, its brief, the control rule and both "
          "label files by hash, with 12 items, 4 candidates and 8 controls",
          [e.get("record_file") for e in withdraw] == ["auxsays/updates/generated/" + RECORD]
          and {k: packet.get(k) for k in PACKET_HASHES} == PACKET_HASHES
          and (packet.get("items"), packet.get("targets"), packet.get("controls")) == (12, 4, 8)
          and manifest.get("parent_commit") == PARENT, json.dumps(packet)[:300])
    accepted = reader_refusal(manifest)
    check("A8 the tool's own manifest checks accept it (scope, selector, closed reasons, two labels, basis)",
          accepted == "" and wd.manifest_scope(manifest) == wd.EXTENDED_PRODUCTS, accepted)

    print("V  the earlier manifests")
    hashes = {name: sha((AUDIT / name).read_bytes()) for name in EARLIER}
    check("V1 the five earlier manifests (v1-v5) are byte-identical to their pins",
          hashes == EARLIER, str({k: v[:12] for k, v in hashes.items() if v != EARLIER[k]}))
    earlier_ok = {name: reader_refusal(json.loads((AUDIT / name).read_text(encoding="utf-8"))) for name in EARLIER}
    check("V2 and the tool still accepts each of them", all(v == "" for v in earlier_ok.values()), str(earlier_ok))
    v4 = json.loads((AUDIT / "live_citation_withdrawal_v4.json").read_text(encoding="utf-8"))
    check("V3 AUX-108's manifest still records this row as its control finding and the 20.2.1 row as held out; this "
          "manifest takes up only the finding",
          [ident(r) for h in v4.get("findings_not_withdrawn", []) for r in h["rows"]] == [D2]
          and {short(r) for h in v4.get("held_out", []) for r in h["rows"]} == {(DAV, "20.2.1", "", "1noccl9")}
          and entries == {D2})

    print("B  dry run, as the bare script")
    with tempfile.TemporaryDirectory(prefix="aux114-dry-") as tmp:
        store, generated, man = make_tree(Path(tmp))
        before = store.read_bytes()
        proc = run_tool(store, generated, man)
        out = proc.stdout
        check("B1 a dry run exits 0 and writes nothing", proc.returncode == 0 and store.read_bytes() == before,
              proc.stdout[-400:] + proc.stderr[-400:])
        check("B2 it plans exactly the one row", out.count("[withdraw ") == 1 and "rows withdrawn by this run: 1" in out
              and "[kept " not in out and "21.0.4" in out, out[-600:])

    print("C  the write")
    with tempfile.TemporaryDirectory(prefix="aux114-write-") as tmp:
        store, generated, man = make_tree(Path(tmp))
        before_bytes = store.read_bytes()
        audit_path = Path(tmp) / "audit.json"
        p3 = run_tool(store, generated, man, "--write", "--confirm-write", "--audit", str(audit_path),
                      "--parent-commit", "e" * 40)
        check("C1 --write --confirm-write withdraws the one row and says so",
              p3.returncode == 0 and "WROTE" in p3.stdout and "rows withdrawn by this run: 1" in p3.stdout,
              p3.stdout[-500:] + p3.stderr[-500:])
        before_text, after_text = before_bytes.decode("utf-8"), store.read_bytes().decode("utf-8")
        a_lines, b_lines = before_text.split(NL), after_text.split(NL)
        changed = [(a, b) for a, b in zip(a_lines, b_lines) if a != b]
        expected = collections.Counter({("  counted: true", "  counted: false"): 1,
                                        ("  exclusion_reason: null", "  exclusion_reason: " + REASON): 1})
        check("C2 exactly 2 lines change, and no validity line is added",
              len(a_lines) == len(b_lines) and collections.Counter(changed) == expected and len(changed) == 2,
              f"{len(changed)} changed: {collections.Counter(changed)}")
        after_blocks, before_blocks = blocks_by_identity(after_text), blocks_by_identity(before_text)
        fman = json.loads(man.read_text(encoding="utf-8"))
        check("C3 the withdrawn block now hashes to its pinned after-value",
              all([sha(b) for b in after_blocks.get(ident(e), [])] == [e["block_sha256_after"]] for e in fman["entries"]))
        rows_b = [r for _lo, _hi, r in aux072.store_blocks(before_text)]
        rows_a = [r for _lo, _hi, r in aux072.store_blocks(after_text)]
        moved = [(o, n) for o, n in zip(rows_b, rows_a) if ident(o) == D2]
        check("C4 the row parses as withdrawn, every other field unchanged, no field added",
              len(moved) == 1 and all(n == dict(o, counted=False, exclusion_reason=REASON) and set(n) == set(o)
                                      for o, n in moved))
        others = [k for k in before_blocks if k != D2]
        parsed_after = {ident(r): r for r in rows_a}
        kinds = collections.Counter(k[0] for k in others)
        named = {short(dict(zip(SEL, k))) for k in others if k in (P08, P05) or short(dict(zip(SEL, k))) in HELD}
        check("C5 no row is added or removed; the two controls, the held 20.2.1 row and every Windows, OBS and DaVinci "
              "row are byte-identical and still count",
              len(rows_a) == len(rows_b) == 20 and len(others) == 19 and kinds == {WIN: 4, OBS: 1, DAV: 14}
              and named == {(DAV, "21.0.4", "", "1vkctcb"), (DAV, "21", "", "1w927vk"), (DAV, "20.2.1", "", "1noccl9")}
              and all(after_blocks.get(k) == before_blocks[k] for k in others)
              and all(parsed_after[k].get("counted") is True for k in others), str(kinds))
        check("C6 no row starts counting",
              {ident(r) for r in rows_a if r.get("counted") is True} <= {ident(r) for r in rows_b if r.get("counted") is True})
        check("C7 the evidence-loss guard reads it as an audited withdrawal, not a loss",
              el.losses_between(before_text, after_text) == [])
        losses = el.losses_between(before_text, before_text.replace(before_blocks[D2][0], "", 1))
        check("C8 control: the same row deleted IS evidence loss",
              len(losses) == 1 and all(x.code == el.REMOVED for x in losses), str([x.code for x in losses]))
        audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
        per_page = {(p["product_id"], p["update_version"], p["target_build"]): (p["before"], p["after"])
                    for p in audit.get("per_patch") or []}
        check("C9 fixture counts: the 21.0.4 page loses exactly the one row, the DaVinci population falls by one and "
              "Windows and OBS do not move; no same-report row sits on another identity",
              audit.get("written") is True and audit.get("withdrawn_now") == 1 and per_page == PER_PAGE
              and audit.get("counted_population") == POPULATION and audit.get("newly_counted_rows") == []
              and audit.get("store_sha256_before") == sha(before_bytes) and audit.get("store_sha256_after") == sha(after_text)
              and audit.get("product_scope") == [WIN, OBS, DAV] and audit.get("parent_commit") == "e" * 40
              and audit.get("same_report_rows_on_other_identities") == [],
              json.dumps({k: audit.get(k) for k in ("withdrawn_now", "counted_population", "per_patch")})[:600])

        print("D  idempotence")
        p4 = run_tool(store, generated, man, "--write", "--confirm-write")
        check("D1 a second run exits 0, writes nothing and reports the row as already withdrawn",
              p4.returncode == 0 and "nothing to write" in p4.stdout and store.read_bytes().decode("utf-8") == after_text
              and p4.stdout.count("[already_withdrawn") == 1, p4.stdout[-400:] + p4.stderr[-300:])

        print("R  re-admission: a scheduled collector that sees the withdrawn report again")
        # The DaVinci lanes persist through base.append_evidence_rows (patch_collectors/davinci.py and
        # promote_davinci_verified_reports.py). Its guard keys are built from EVERY stored row, counted or not, and a
        # withdrawal keeps the row, so the report's id and URL keys stay held.
        original = next(o for o in rows_b if ident(o) == D2)
        again = dict(original, counted=True, exclusion_reason=None, captured_at="2026-12-01T00:00:00Z")
        variant = dict(again, id=original["id"] + "-recaptured",
                       source_url=original["source_url"].rstrip("/").replace("/r/davinciresolve/", "/r/DavinciResolve/"))
        pre = store.read_bytes()
        held_back: list[dict] = []
        added, _total, _all = wd_base.append_evidence_rows([again, variant], store, out_already_held=held_back)
        check("R1 re-seeing the withdrawn report (the same id and URL, or the same post under another URL spelling) "
              "adds nothing: both are refused as already held and the store is byte-identical",
              added == 0 and store.read_bytes() == pre and len(held_back) == 2, f"added={added} held={len(held_back)}")
        stored = {ident(r): r for _lo, _hi, r in aux072.store_blocks(store.read_bytes().decode("utf-8"))}
        check("R2 so it is still withdrawn, with its reason, and nothing re-counts it",
              stored[D2].get("counted") is False and stored[D2].get("exclusion_reason") == REASON)
        control_store = Path(tmp) / "control.yml"
        control_store.write_bytes(pre)
        fresh = dict(again, id=again["id"] + "-a-different-report",
                     source_url="https://www.reddit.com/r/davinciresolve/comments/1zzzzzz/a_different_report/")
        added_new, _t, _a = wd_base.append_evidence_rows([fresh], control_store)
        check("R3 control: a report the store does not hold IS appended (the guard is not refusing everything)",
              added_new == 1 and control_store.read_bytes() != pre)

    print("E  the two-blind rule is not vacuous, and the tool fails closed")
    base = fixture_manifest()
    cases = {}
    m = copy.deepcopy(base)
    m["entries"][0]["adjudication"]["third_blind"]["label"] = "CORRECT"
    cases["a blind review saying CORRECT"] = m
    m = copy.deepcopy(base)
    m["entries"][0]["adjudication"].pop("third_blind")
    cases["a missing second blind review"] = m
    m = copy.deepcopy(base)
    adj = m["entries"][0]["adjudication"]
    adj["third_blind"]["by"] = adj["second_blind"]["by"]
    cases["one reviewer named twice"] = m
    m = copy.deepcopy(base)
    adj = m["entries"][0]["adjudication"]
    adj["third_blind"]["by"] = adj["first_audit"]["by"]
    cases["the earlier labels standing in for a blind review"] = m
    m = copy.deepcopy(base)
    m["entries"][0]["exclusion_reason"] = "version_named_but_working"
    cases["a reason neither blind review supports"] = m
    m = copy.deepcopy(base)
    m["entries"][0]["adjudication"]["first_audit"]["counts_toward_the_two"] = True
    cases["the earlier labels counted as one of the two"] = m
    m = copy.deepcopy(base)
    m["entries"][0]["adjudication"]["third_blind"]["case"] = "P99"
    cases["two different packet cases"] = m
    verdicts = {name: all(two_blind(e) for e in doc["entries"]) for name, doc in cases.items()}
    check("E1 the two-blind rule rejects: " + "; ".join(cases),
          all(two_blind(e) for e in base["entries"]) and not any(verdicts.values()), str(verdicts))

    d2_block, _d2 = row_of(text, D2)
    drifted = text.replace(d2_block, d2_block.replace("  severity: ", "  severity: x", 1), 1)
    assert drifted != text
    proc, same = refused("aux114-e2-", drifted, manifest=fixture_manifest())
    check("E2 the row moved since it was pinned: the whole run refuses and writes nothing",
          proc.returncode == 1 and "block changed since the manifest was pinned" in proc.stdout and same,
          proc.stdout[-300:])

    d1_key = next(ident(r) for _lo, _hi, r in aux072.store_blocks(text) if short(r) == (DAV, "20.2.1", "", "1noccl9"))
    d1_block, _d1_row = row_of(text, d1_key)
    d1_entry = dict(copy.deepcopy(base["entries"][0]), **dict(zip(SEL, d1_key)),
                    record_file="auxsays/updates/generated/2025-09-23-davinci-resolve-20-2-1.md",
                    block_sha256_before=sha(d1_block), block_sha256_after=sha(own_edit(d1_block, REASON)))
    d1_entry["adjudication"]["second_blind"]["label"] = "UNSURE"
    d1_doc = copy.deepcopy(base)
    d1_doc["entries"].append(d1_entry)
    d1_targets = targets_fixture() + [{"file": "2025-09-23-davinci-resolve-20-2-1.md", "front_matter": {
        "update_entry": True, "product_id": DAV, "update_version": "20.2.1"}}]
    proc, same = refused("aux114-e3-", None, d1_targets, d1_doc)
    check("E3 the held 20.2.1 row added without two INCORRECT labels refuses the whole run and writes nothing",
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
        with tempfile.TemporaryDirectory(prefix="aux114-f1-") as tmp:
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
    controls = [live_parsed.get(k, {}) for k in (P08, P05)]
    check("G2 the row's two controls (the 21.0.4 must-stay row and the 21 row) are each stored once and still count",
          all(r.get("counted") is True for r in controls) and all(len(live_rows.get(k, [])) == 1 for k in (P08, P05)),
          str([(k[3][-30:], live_parsed.get(k, {}).get("counted")) for k in (P08, P05)]))
    held_rows = [r for r in live_parsed.values() if short(r) in HELD]
    check("G3 the three held candidates (DaVinci 20.2.1, Acrobat Reader 15.010.20056, Premiere Pro 26.2) are each "
          "stored once and still count",
          len(held_rows) == 3 and {short(r) for r in held_rows} == HELD
          and all(r.get("counted") is True for r in held_rows)
          and all(len(live_rows[ident(r)]) == 1 for r in held_rows),
          str([(short(r), r.get("counted")) for r in held_rows]))
    live_after = {str(p): sha(p.read_bytes()) for p in live_files if p.exists()}
    check("G4 the live store and the 21.0.4 record are byte-identical after the suite",
          live_after == live_before and len(live_before) == 2, f"{len(live_before)} files")

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
