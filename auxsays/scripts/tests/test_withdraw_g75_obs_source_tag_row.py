#!/usr/bin/env python3
"""The audited withdrawal of one OBS Studio 31.1.2 report that names 31.1.2 only as a diffed source tag (AUX-118).

`withdraw_live_citation_rows.py` (the AUX-088 mechanism, unchanged) withdraws, with a seventh pinned manifest
(audit/live_citation_withdrawal_v7.json), the one stored row of GitHub issue #13995 counted against OBS Studio 31.1.2.
Two independent blind adjudications of the stored text both found that the report does not establish 31.1.2 is
affected: the version appears only as a release tag the reporter compared by diffing build files, not as a version
they ran or saw the failure on. The same report's 32.1.2 row was withdrawn under AUX-088 for the same clause, and its
32.2.2 row (the version the reporter ran) stays counted. An earlier full-source audit of the row is recorded as
provenance only. Its contract, pinned here:

  A  the committed manifest names exactly that row by its full five-field identity, with the reason both blind
     reviews support and two blind INCORRECT labels from two different named readers on one packet case (the
     earlier audit is provenance only); the scope is exactly AUX-088's (Windows, OBS) and no product grant is
     involved; the two rows that must stay counted and the control finding are listed and are not entries; it shares
     no row with an earlier withdrawal, label or re-admission manifest; it records the blind packet's file hashes;
     the tool's own manifest reader accepts it; the committed run audit is this manifest's run
  V  the six earlier manifests (v1-v6) are byte-identical to their pins and still accepted, and AUX-088's manifest
     still withdraws the same report's 32.1.2 row
  B  a dry run plans the one row and writes nothing
  C  --write --confirm-write changes exactly 2 lines, keeps every row, leaves every other row (the must-stay control
     on the same page, the report's two other rows and every Windows and OBS row) byte-identical, starts no row
     counting, and the evidence-loss guard reads it as an audited withdrawal; the fixture's counts fall by exactly
     the one row
  D  a second run changes nothing
  R  re-admission: the next scheduled OBS collection cannot count the report on 31.1.2 again. The collector's own row
     builder gives #13995 re-seen on 31.1.2 exactly the stored id and URL; the OBS dedupe authority it writes
     through (collect_obs_reports.write_evidence, keyed on version + id and version + URL over EVERY stored row,
     counted or not) and the shared append guard (patch_collectors.base.append_evidence_rows) both refuse it, under
     the same URL and under another URL spelling, so the row stays withdrawn; a report the store does not hold is
     still appended by both
  E  the two-blind rule is not vacuous, and the tool fails closed on a drifted block or on an extra row with no two
     INCORRECT labels
  F  --regenerate for this manifest runs exactly the reconcile scoped to Windows and OBS and each product's own
     scoped promotion; nothing unscoped, and no DaVinci step
  G  the committed store holds the row once, withdrawn, at its pinned after-hash; the must-stay control (#13989 on
     31.1.2) and the report's 32.2.2 row still count, its 32.1.2 row stays withdrawn, and the control finding (an
     AUX-088 withdrawal) is not re-admitted; this suite changed nothing real

The tool runs as a BARE script, so B-E run it as a subprocess, exactly as an operator would. Offline: the frozen
AUX-088 fixture (tests/fixtures/live_citation/withdrawal_store.yml, 32 rows whose free text is synthetic, among them
all three rows of #13995 and the control finding) and its records' identity front matter (31.1.2 included). In
memory, the suite puts the two AUX-088 rows this manifest names into their withdrawn state with its OWN line edit, as
the live store holds them, and derives one synthetic 31.1.2 block for the must-stay control from the fixture's own
31.1.2 block. It re-pins the manifest's block hashes on the fixture with that same edit. No live-corpus count is
asserted anywhere.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_withdraw_g75_obs_source_tag_row.py
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

import collect_obs_reports as obs_collector  # noqa: E402
import withdraw_live_citation_rows as wd  # noqa: E402
import withdraw_windows_identity_not_the_subject_rows as aux072  # noqa: E402
from lib import evidence_loss as el  # noqa: E402
from patch_collectors import base as wd_base  # noqa: E402

TOOL = SCRIPTS / "withdraw_live_citation_rows.py"
AUDIT = SCRIPTS / "audit"
MANIFEST = AUDIT / "live_citation_withdrawal_v7.json"
RUN_AUDIT = AUDIT / "live_citation_withdrawal_v7_2026-11-21.json"
BASELINE = AUDIT / "live_citation_withdrawal_baseline_v2.json"
FIX = SCRIPTS / "tests" / "fixtures" / "live_citation"
STORE_FIXTURE = FIX / "withdrawal_store.yml"
TARGETS = FIX / "withdrawal_targets.json"
NL = chr(10)
SEL = ("product_id", "update_version", "target_build", "id", "source_url")
WIN, OBS, DAV = "microsoft-windows-11", "obs-studio", "blackmagic-davinci"
INCORRECT = "INCORRECT"
REASON = "identity_not_the_subject"
PARENT = "e2cfca68c09ad5035b5e8dad0999147b128a5028"
STORE_PIN = "715c13b237a0d96ee39e94afce7ee0af794c4a6478ebea3ce89b9541bd21026a"
RECORD = "2025-07-28-obs-studio-31-1-2.md"
URL_13995 = "https://github.com/obsproject/obs-studio/issues/13995"

# The row both blind reviews found does not establish 31.1.2, written out in full here so neither the manifest nor
# the fixture can redefine it, and its pinned before/after block hashes on the live store.
TARGET = (OBS, "31.1.2", "", "obs-studio-31-1-2-github-issue-13995", URL_13995)
TARGET_BEFORE = "00c0992c44ef55d4554bfa32c1add83d2be3999561b9c08c2d58e599499342f9"
TARGET_AFTER = "45cddacf83866d9e991b7517cd755585fffcfdb209f8605c1b05183206317e57"
# Rows that must stay as they are: the must-stay control on the same page (several versions tested, a failure on
# each; both readers counted it), the same report's row on the version the reporter ran, and its 32.1.2 row, which
# AUX-088 already withdrew for the same clause.
WYT4 = (OBS, "31.1.2", "", "obs-studio-31-1-2-github-issue-13989", "https://github.com/obsproject/obs-studio/issues/13989")
SIB_322 = (OBS, "32.2.2", "", "obs-studio-32-2-2-github-issue-13995", URL_13995)
SIB_312 = (OBS, "32.1.2", "", "obs-studio-32-1-2-github-issue-13995", URL_13995)
STAY_HASHES = {WYT4: "57e0d921276d5130c9909913930108acc91fe6773d019fd5460b2377b4a77d55",
               SIB_322: "79ee83557f059a88230e44ea36d9dd87e149c41a235e4c78a3468801b724baca"}
SIB_312_AFTER = "4fe6ce7daea55d17dfc6355c68e4ca61a55fc3479ae35bab3c964013334e6fa0"  # AUX-088's after-hash
# The control finding: a row AUX-088 withdrew that both new readers would count. Recorded only, never re-admitted.
WAYA = (OBS, "32.2.2", "", "obs-studio-32-2-2-obs-forum-thread-196184",
        "https://obsproject.com/forum/threads/zoominator-wayland-mouse-follow-broken-requesting-xdg-desktop-portal-support.196184/")
WAYA_REASON = "not_a_real_issue_report"
WAYA_AFTER = "aef75bff49f52afc1e774b5ac5ed7a4e4013a49ab15ed201490bc02f05b54907"  # AUX-088's after-hash
# The blind adjudication's own files, by hash (the packet, the control rule with the amendments it recorded during
# the draw, the draw, the sealed key and both readers' answer sheets), and the earlier full-source audit.
PACKET_HASHES = {
    "packet_sha256": "ef02985663e778674dab45b3195cab30265b34cd22daa3432d3e17f1b6b13262",
    "control_rule_sha256": "72dc9790283ad49cfcc70bf18b176647ee68004c3f7e07b42958f2c0aa80d3aa",
    "draw_sha256": "ada61b6cb692de01dfa1fb38d1f7be1502f88059976642fe712cff3d005b6104",
    "key_sha256": "65ea8412fbf34f297cec942cb22eb538bbff64d9bb13e92d33086c063caca2bc",
    "reader_1_sha256": "268db420d84a7aa1b96333f8bdb69b95ae66f974030dc30045069a63b6de3244",
    "reader_2_sha256": "c1417d0dbd22fc6297cdfe3350e776a0f4f7bacd1bcc7a20aa1e41afde8fa98e",
}
FIRST_AUDIT_SHA = "11951d76df6ae15cb4841fde37753a08c36943cfca1691f7cd1a75ef42c56195"
# The six earlier manifests of this tool, which this one must leave byte-identical.
EARLIER = {
    "live_citation_withdrawal.json": "e7fda1cf2cdf42a1dc88a8ab962c2ef3fbaec9599bff26077a6880f0247d9d24",
    "live_citation_withdrawal_v2.json": "51adfe324fed5eaea98a46e3857b9a737847d7f91a8777e332a793ad161d1490",
    "live_citation_withdrawal_v3.json": "eae1abf5d5f9f2c5be3c09fa1ea59b37438457a2ff01cb0309bc1ee62b9b588d",
    "live_citation_withdrawal_v4.json": "6394217b309b02fddf0b89ee1fe0773e01e26552c2b00a4ae3d8c48b0a705bc3",
    "live_citation_withdrawal_v5.json": "4cba0edcdea03d3406999891e8b6960c1fb9f23da72badda252208813935826d",
    "live_citation_withdrawal_v6.json": "e852e6bdba1826881a053612cca5c441b77fce08eb419c73eb26d177d74362a0",
}
PRIOR = {  # the earlier audited manifests this one must not overlap
    "AUX-072": ("windows_identity_not_the_subject_withdrawal.json",),
    "AUX-079": ("windows_confirmed_and_duplicate_withdrawal.json",),
    "AUX-088": ("live_citation_withdrawal.json",),
    "AUX-090": ("live_citation_withdrawal_v2.json", "live_citation_withdrawal_baseline_v2.json"),
    "AUX-098": ("live_citation_withdrawal_v3.json",),
    "AUX-108": ("live_citation_withdrawal_v4.json",),
    "AUX-110": ("acrobat_reader_readmission.json", "acrobat_reader_label_correction.json"),
    "AUX-111": ("live_citation_withdrawal_v5.json",),
    "AUX-114": ("live_citation_withdrawal_v6.json",),
}
# Fixture-based count deltas (33 fixture rows; never the live corpus).
PER_PAGE = {(OBS, "31.1.2", ""): (2, 1)}
POPULATION = {WIN: [3, 3], OBS: [28, 27]}

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


def ident(row: dict) -> tuple[str, ...]:
    """The suite's own five-field identity, so a broken selector in the tool fails a check, not the suite."""
    return tuple(str(row.get(key) or "") for key in SEL)


def page_report(row: dict) -> tuple[str, str, str, str]:
    """(product, version, build, report URL in its dedup spelling): one report on one page."""
    return (str(row.get("product_id") or ""), str(row.get("update_version") or ""),
            str(row.get("target_build") or ""), str(row.get("source_url") or "").strip().rstrip("/").lower())


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


def synthetic_wyt4(target_block: str) -> str:
    """The must-stay control for the fixture, derived from the fixture's own 31.1.2 block of #13995: another report's
    id, URL and capture time, and synthetic marker text."""
    block = target_block.replace("- id: " + TARGET[3] + NL, "- id: " + WYT4[3] + NL, 1)
    block = block.replace("  source_url: " + TARGET[4] + NL, "  source_url: " + WYT4[4] + NL, 1)
    block = block.replace("(AUX-088)", "(AUX-118)")
    block = block.replace("  captured_at: '2026-10-05T16:13:13Z'" + NL, "  captured_at: '2026-10-03T17:55:06Z'" + NL, 1)
    assert block != target_block and WYT4[3] in block and WYT4[4] in block and "2026-10-03T17:55:06Z" in block
    return block


def fixture_text() -> str:
    """The AUX-088 fixture with the two rows AUX-088 withdrew that this manifest names (the report's 32.1.2 row and
    the control finding) in their withdrawn state, by the suite's own edit, plus the synthetic must-stay control."""
    text = STORE_FIXTURE.read_bytes().decode("utf-8")
    blocks = blocks_by_identity(text)
    for key, reason in ((SIB_312, REASON), (WAYA, WAYA_REASON)):
        text = text.replace(blocks[key][0], own_edit(blocks[key][0], reason), 1)
    if not text.endswith(NL):
        text += NL
    return text + synthetic_wyt4(blocks[TARGET][0])


def targets_fixture() -> list[dict]:
    return json.loads(TARGETS.read_text(encoding="utf-8"))


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
    reviews (second_blind, third_blind): both INCORRECT as mapped from the readers' own NOT_AFFECTED, two different
    named readers, neither the first audit, the same packet case, each with a verbatim reason, and the row's reason
    one BOTH support. The first audit (an earlier full-source audit) is provenance (INCORRECT, as the tool's
    two-label check requires) and never one of the two. For OBS the tool itself checks only first_audit plus
    second_blind, so this reading is what enforces the two."""
    adj = entry.get("adjudication") or {}
    first, a, b = adj.get("first_audit") or {}, adj.get("second_blind") or {}, adj.get("third_blind") or {}
    names = [str(x.get("by") or "").strip() for x in (first, a, b)]
    return (a.get("label") == b.get("label") == INCORRECT
            and a.get("label_as_given") == b.get("label_as_given") == "NOT_AFFECTED"
            and all(names) and len(set(names)) == 3
            and bool(re.fullmatch(r"[A-Z0-9]{4}", str(a.get("case") or ""))) and a.get("case") == b.get("case")
            and str(a.get("reason") or "").strip() != "" and str(b.get("reason") or "").strip() != ""
            and supported(a) <= wd.REASONS and supported(b) <= wd.REASONS
            and entry.get("exclusion_reason") in (supported(a) & supported(b))
            and first.get("label") == INCORRECT and first.get("counts_toward_the_two") is False)


def pinned_or_successor(key: tuple[str, ...], pinned: str, digest: str) -> bool:
    """The block is still what was pinned, or what a later audited change recorded against that exact pin (the tool's
    own supplemental baseline)."""
    return digest == pinned or wd.load_baseline(BASELINE).get(key, {}).get(pinned) == digest


def issue_13995(html_url: str = URL_13995) -> dict:
    """GitHub issue #13995 as the collector's GitHub search would hand it over again (synthetic text naming 31.1.2)."""
    return {"number": 13995, "title": "Synthetic re-seen issue (AUX-118), not recorded source text",
            "body": "Synthetic body (AUX-118) naming 31.1.2 once.", "html_url": html_url,
            "created_at": "2026-10-05T10:00:00Z"}


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Audited withdrawal of one OBS Studio 31.1.2 report that names 31.1.2 only as a diffed tag (AUX-118)")
    print("=" * 78)
    live_store = ROOT / "_data" / "consensus_evidence.yml"
    live_files = [live_store, ROOT / "updates" / "generated" / RECORD]
    live_before = {str(p): sha(p.read_bytes()) for p in live_files if p.exists()}
    manifest = manifest_doc()
    text = fixture_text()
    withdraw = [e for e in manifest["entries"] if e.get("role") == "withdraw"]

    print("A  the pinned manifest")
    check("A1 one OBS row is withdrawn and none is kept, under ledger AUX-118, version 7",
          len(withdraw) == 1 and len(manifest["entries"]) == 1 and manifest.get("ledger") == "AUX-118"
          and manifest.get("version") == 7 and withdraw[0].get("product_id") == OBS,
          f"{len(withdraw)} withdraw of {len(manifest['entries'])}")
    check("A2 the withdrawn row is exactly the 31.1.2 row of #13995, by its full five-field identity, with the reason "
          "both blind reviews support",
          [ident(e) for e in withdraw] == [TARGET] and [e.get("exclusion_reason") for e in withdraw] == [REASON],
          str([ident(e)[1:4] for e in withdraw]))
    check("A3 the selector, the closed reasons and the scope are the tool's own, and the scope is exactly AUX-088's "
          "(Windows, OBS); OBS has no product grant, so no grant is involved",
          tuple(manifest["selector"]) == SEL and sorted(manifest["exclusion_reasons"]) == sorted(wd.REASONS)
          and tuple(manifest["products"]) == wd.PRODUCTS == (WIN, OBS)
          and OBS not in wd.PRODUCT_GRANTS and all(wd._grant_refusal(ident(e)) == "" for e in withdraw),
          str(manifest.get("products")))
    check("A4 the row carries two blind INCORRECT labels (each reader's own NOT_AFFECTED) from two different named "
          "readers on one packet case, each with its verbatim reason, both supporting its reason (the suite's reading "
          "and the tool's two-label check agree); the earlier audit is provenance only",
          all(two_blind(e) and wd._two_labels(e) and str(e.get("basis") or "").strip() for e in withdraw)
          and [e["adjudication"]["second_blind"]["case"] for e in withdraw] == ["WPCV"]
          and [e["adjudication"]["first_audit"].get("obs_audit_sha256") for e in withdraw] == [FIRST_AUDIT_SHA],
          str([e["id"][-30:] for e in withdraw if not two_blind(e)]))
    stay = {ident(r): r.get("block_sha256") for r in manifest.get("must_stay_counted", [])}
    finding = [h for h in manifest.get("control_findings_no_action", [])]
    entries = {ident(e) for e in manifest["entries"]}
    check("A5 the must-stay rows are exactly #13989 on 31.1.2 and the report's 32.2.2 row, at their pinned hashes; the "
          "control finding is exactly the AUX-088 row both readers would count, with a reason; nothing is held out "
          "and none of these is an entry",
          stay == STAY_HASHES and [ident(r) for h in finding for r in h["rows"]] == [WAYA]
          and all(str(h.get("why") or "").strip() for h in finding)
          and manifest.get("held_out") == [] and manifest.get("findings_not_withdrawn") == []
          and not (entries & (set(stay) | {WAYA})), str({k[3][-5:]: v for k, v in stay.items()})[:300])
    prior_ids, prior_pages = set(), set()
    for names in PRIOR.values():
        for name in names:
            doc = json.loads((AUDIT / name).read_text(encoding="utf-8"))
            prior_ids |= {ident(e) for e in doc["entries"]}
            prior_pages |= {page_report(e) for e in doc["entries"]}
    same_report = sorted(p[:3] for p in prior_pages if p[3] == URL_13995)
    check("A6 no row (by five-field identity, or by page and report) is shared with the AUX-072, AUX-079, AUX-088, "
          "AUX-090, AUX-098, AUX-108, AUX-110, AUX-111 or AUX-114 manifests; the only earlier entry for this report "
          "is AUX-088's, on 32.1.2, a different page",
          not (prior_ids & entries) and not (prior_pages & {page_report(e) for e in withdraw})
          and same_report == [(OBS, "32.1.2", "")], str(same_report))
    packet = manifest.get("adjudication_packet") or {}
    check("A7 the row pins its record; the manifest pins the parent commit and the store, and records the packet, the "
          "control rule, the draw, the sealed key and both readers' sheets by hash, with 11 items, 1 target and 10 "
          "controls",
          [e.get("record_file") for e in withdraw] == ["auxsays/updates/generated/" + RECORD]
          and {k: packet.get(k) for k in PACKET_HASHES} == PACKET_HASHES
          and (packet.get("items"), packet.get("targets"), packet.get("controls")) == (11, 1, 10)
          and manifest.get("parent_commit") == PARENT and manifest.get("store_sha256_at_pin") == STORE_PIN
          and [(e.get("block_sha256_before"), e.get("block_sha256_after")) for e in withdraw]
          == [(TARGET_BEFORE, TARGET_AFTER)], json.dumps(packet)[:300])
    accepted = reader_refusal(manifest)
    check("A8 the tool's own manifest checks accept it (scope, selector, closed reasons, two labels, basis)",
          accepted == "" and wd.manifest_scope(manifest) == wd.PRODUCTS, accepted)
    run_audit = json.loads(RUN_AUDIT.read_text(encoding="utf-8")) if RUN_AUDIT.exists() else {}
    deltas = {(p["product_id"], p["update_version"], p["target_build"]): p["before"] - p["after"]
              for p in run_audit.get("per_patch") or []}
    population = {k: v[0] - v[1] for k, v in (run_audit.get("counted_population") or {}).items()}
    siblings = {tuple(s.get(k) or "" for k in SEL): (s.get("counted"), s.get("exclusion_reason"), s.get("unchanged"))
                for s in run_audit.get("same_report_rows_on_other_identities") or []}
    check("A9 the committed run audit is this manifest's run: written, one row withdrawn at the pinned parent and store, "
          "the manifest's hash, only the 31.1.2 page and the OBS population losing exactly one, no row newly counted, "
          "the report's two other rows untouched, the three scoped writers ok",
          run_audit.get("written") is True and run_audit.get("withdrawn_now") == 1
          and run_audit.get("parent_commit") == manifest.get("parent_commit") == PARENT
          and run_audit.get("manifest_sha256") == sha(MANIFEST.read_bytes())
          and run_audit.get("store_sha256_before") == STORE_PIN
          and deltas == {(OBS, "31.1.2", ""): 1} and population == {WIN: 0, OBS: 1}
          and run_audit.get("newly_counted_rows") == [] and run_audit.get("product_scope") == [WIN, OBS]
          and siblings == {SIB_312: (False, REASON, True), SIB_322: (True, None, True)}
          and [w["command"] for w in run_audit.get("writers") or []] == [" ".join(w) for w in wd.writers_for(wd.PRODUCTS)]
          and all(w["returncode"] == 0 for w in run_audit.get("writers") or []),
          json.dumps({k: run_audit.get(k) for k in ("written", "withdrawn_now", "parent_commit", "per_patch")})[:400])

    print("V  the earlier manifests")
    hashes = {name: sha((AUDIT / name).read_bytes()) for name in EARLIER}
    check("V1 the six earlier manifests (v1-v6) are byte-identical to their pins",
          hashes == EARLIER, str({k: v[:12] for k, v in hashes.items() if v != EARLIER[k]}))
    earlier_ok = {name: reader_refusal(json.loads((AUDIT / name).read_text(encoding="utf-8"))) for name in EARLIER}
    check("V2 and the tool still accepts each of them", all(v == "" for v in earlier_ok.values()), str(earlier_ok))
    v1 = json.loads((AUDIT / "live_citation_withdrawal.json").read_text(encoding="utf-8"))
    v1_rows = [(e.get("role"), e.get("exclusion_reason"), e.get("block_sha256_after"))
               for e in v1["entries"] if ident(e) == SIB_312]
    check("V3 AUX-088's manifest still withdraws the same report's 32.1.2 row, for the same reason, to the same block",
          v1_rows == [("withdraw", REASON, SIB_312_AFTER)], str(v1_rows))

    print("B  dry run, as the bare script")
    with tempfile.TemporaryDirectory(prefix="aux118-dry-") as tmp:
        store, generated, man = make_tree(Path(tmp))
        before = store.read_bytes()
        proc = run_tool(store, generated, man)
        out = proc.stdout
        check("B1 a dry run exits 0 and writes nothing", proc.returncode == 0 and store.read_bytes() == before,
              proc.stdout[-400:] + proc.stderr[-400:])
        check("B2 it plans exactly the one row", out.count("[withdraw ") == 1 and "rows withdrawn by this run: 1" in out
              and "[kept " not in out and "obs-studio 31.1.2" in out, out[-600:])

    print("C  the write")
    with tempfile.TemporaryDirectory(prefix="aux118-write-") as tmp:
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
              len(a_lines) == len(b_lines) and collections.Counter(changed) == expected and len(changed) == 2
              and after_text.count("evidence_valid_for_current_patch") == before_text.count("evidence_valid_for_current_patch"),
              f"{len(changed)} changed: {collections.Counter(changed)}")
        after_blocks, before_blocks = blocks_by_identity(after_text), blocks_by_identity(before_text)
        fman = json.loads(man.read_text(encoding="utf-8"))
        check("C3 the withdrawn block now hashes to its after-value, re-pinned on the fixture with the suite's own edit",
              all([sha(b) for b in after_blocks.get(ident(e), [])] == [e["block_sha256_after"]]
                  == [sha(own_edit(before_blocks[ident(e)][0], REASON))] for e in fman["entries"]))
        rows_b = [r for _lo, _hi, r in aux072.store_blocks(before_text)]
        rows_a = [r for _lo, _hi, r in aux072.store_blocks(after_text)]
        moved = [(o, n) for o, n in zip(rows_b, rows_a) if ident(o) == TARGET]
        check("C4 the row parses as withdrawn, every other field unchanged, no field added",
              len(moved) == 1 and all(n == dict(o, counted=False, exclusion_reason=REASON) and set(n) == set(o)
                                      for o, n in moved))
        others = [k for k in before_blocks if k != TARGET]
        parsed_a, parsed_b = {ident(r): r for r in rows_a}, {ident(r): r for r in rows_b}
        kinds = collections.Counter(k[0] for k in others)
        check("C5 no row is added or removed; every other row is byte-identical: the must-stay #13989 row and the "
              "report's 32.2.2 row still count, its 32.1.2 row and the control finding stay withdrawn",
              len(rows_a) == len(rows_b) == 33 and len(others) == 32 and kinds == {WIN: 3, OBS: 29}
              and all(after_blocks.get(k) == before_blocks[k] for k in others)
              and all(parsed_a[k].get("counted") == parsed_b[k].get("counted") for k in others)
              and parsed_a[WYT4].get("counted") is True and parsed_a[SIB_322].get("counted") is True
              and (parsed_a[SIB_312].get("counted"), parsed_a[SIB_312].get("exclusion_reason")) == (False, REASON)
              and (parsed_a[WAYA].get("counted"), parsed_a[WAYA].get("exclusion_reason")) == (False, WAYA_REASON),
              str(kinds))
        check("C6 no row starts counting",
              {ident(r) for r in rows_a if r.get("counted") is True} <= {ident(r) for r in rows_b if r.get("counted") is True})
        check("C7 the evidence-loss guard reads it as an audited withdrawal, not a loss",
              el.losses_between(before_text, after_text) == [])
        losses = el.losses_between(before_text, before_text.replace(before_blocks[TARGET][0], "", 1))
        check("C8 control: the same row deleted IS evidence loss",
              len(losses) == 1 and all(x.code == el.REMOVED for x in losses), str([x.code for x in losses]))
        audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
        per_page = {(p["product_id"], p["update_version"], p["target_build"]): (p["before"], p["after"])
                    for p in audit.get("per_patch") or []}
        fixture_siblings = {tuple(s.get(k) or "" for k in SEL): (s.get("counted"), s.get("exclusion_reason"),
                                                                 s.get("unchanged"))
                            for s in audit.get("same_report_rows_on_other_identities") or []}
        check("C9 fixture counts: the 31.1.2 page loses exactly the one row, the OBS population falls by one and Windows "
              "does not move; the report's two rows on other versions are reported untouched",
              audit.get("written") is True and audit.get("withdrawn_now") == 1 and per_page == PER_PAGE
              and audit.get("counted_population") == POPULATION and audit.get("newly_counted_rows") == []
              and audit.get("store_sha256_before") == sha(before_bytes) and audit.get("store_sha256_after") == sha(after_text)
              and audit.get("product_scope") == [WIN, OBS] and audit.get("parent_commit") == "e" * 40
              and fixture_siblings == {SIB_312: (False, REASON, True), SIB_322: (True, None, True)},
              json.dumps({k: audit.get(k) for k in ("withdrawn_now", "counted_population", "per_patch")})[:600])

        print("D  idempotence")
        p4 = run_tool(store, generated, man, "--write", "--confirm-write")
        check("D1 a second run exits 0, writes nothing and reports the row as already withdrawn",
              p4.returncode == 0 and "nothing to write" in p4.stdout and store.read_bytes().decode("utf-8") == after_text
              and p4.stdout.count("[already_withdrawn") == 1, p4.stdout[-400:] + p4.stderr[-300:])

        print("R  re-admission: the next scheduled OBS collection sees #13995 again")
        # The OBS lane (patch_collectors/obs.py -> collect_obs_reports.collect_one) builds every row with
        # evidence_row and persists only through collect_obs_reports.write_evidence, whose seen-sets are built from
        # EVERY stored row, counted or not. A withdrawal keeps the row, so its id and URL stay held.
        again = obs_collector.evidence_row(issue_13995(), "31.1.2", "body", "2026-12-01T00:00:00Z")
        respelled = obs_collector.evidence_row(issue_13995("https://github.com/obsproject/OBS-Studio/issues/13995/"),
                                               "31.1.2", "body", "2026-12-01T00:00:00Z")
        check("R1 the collector's own row builder gives #13995 re-seen on 31.1.2 exactly the stored id and URL, and the "
              "same id under another URL spelling",
              ident(again) == TARGET and again.get("counted") is True and respelled["id"] == TARGET[3]
              and respelled["source_url"] != TARGET[4], str((ident(again), respelled.get("source_url"))))
        pre = store.read_bytes()
        saved_path = obs_collector.EVIDENCE_PATH
        try:
            obs_collector.EVIDENCE_PATH = store
            added_obs, _total_obs, _rows_obs = obs_collector.write_evidence([again, respelled])
        finally:
            obs_collector.EVIDENCE_PATH = saved_path
        check("R2 the OBS dedupe authority (write_evidence) refuses both: nothing is added and the store is "
              "byte-identical",
              added_obs == 0 and store.read_bytes() == pre and obs_collector.EVIDENCE_PATH == saved_path,
              f"added={added_obs}")
        new_id = dict(respelled, id=TARGET[3] + "-recaptured")
        held_back: list[dict] = []
        added, _total, _all = wd_base.append_evidence_rows([again, new_id], store, out_already_held=held_back)
        check("R3 the shared append guard (base.append_evidence_rows) refuses it too, by id and by the report's URL under "
              "another spelling and another id: both are refused as already held and the store is byte-identical",
              added == 0 and store.read_bytes() == pre and len(held_back) == 2, f"added={added} held={len(held_back)}")
        stored = {ident(r): r for _lo, _hi, r in aux072.store_blocks(store.read_bytes().decode("utf-8"))}
        check("R4 so it is still withdrawn, with its reason, and nothing re-counts it",
              stored[TARGET].get("counted") is False and stored[TARGET].get("exclusion_reason") == REASON
              and sum(1 for k in stored if k[3].startswith(TARGET[3])) == 1)
        fresh = obs_collector.evidence_row(dict(issue_13995(), number=99999,
                                                html_url="https://github.com/obsproject/obs-studio/issues/99999"),
                                           "31.1.2", "body", "2026-12-01T00:00:00Z")
        control_a, control_b = Path(tmp) / "control_a.yml", Path(tmp) / "control_b.yml"
        control_a.write_bytes(pre)
        control_b.write_bytes(pre)
        try:
            obs_collector.EVIDENCE_PATH = control_a
            added_new_obs, _t1, _r1 = obs_collector.write_evidence([fresh])
        finally:
            obs_collector.EVIDENCE_PATH = saved_path
        added_new, _t2, _r2 = wd_base.append_evidence_rows([fresh], control_b)
        check("R5 control: a report the store does not hold IS appended by both (neither guard refuses everything)",
              added_new_obs == 1 and added_new == 1 and control_a.read_bytes() != pre and control_b.read_bytes() != pre
              and obs_collector.EVIDENCE_PATH == saved_path, f"obs={added_new_obs} base={added_new}")

    print("E  the two-blind rule is not vacuous, and the tool fails closed")
    base = fixture_manifest()
    cases = {}
    m = copy.deepcopy(base)
    m["entries"][0]["adjudication"]["second_blind"]["label"] = "CORRECT"
    cases["a reader recorded as CORRECT"] = m
    m = copy.deepcopy(base)
    m["entries"][0]["adjudication"].pop("third_blind")
    cases["a missing second reader"] = m
    m = copy.deepcopy(base)
    adj = m["entries"][0]["adjudication"]
    adj["third_blind"]["by"] = adj["second_blind"]["by"]
    cases["one reader named twice"] = m
    m = copy.deepcopy(base)
    adj = m["entries"][0]["adjudication"]
    adj["third_blind"]["by"] = adj["first_audit"]["by"]
    cases["the first audit standing in for a reader"] = m
    m = copy.deepcopy(base)
    m["entries"][0]["adjudication"]["first_audit"]["counts_toward_the_two"] = True
    cases["the first audit counted as one of the two"] = m
    m = copy.deepcopy(base)
    m["entries"][0]["adjudication"]["third_blind"]["case"] = "HRAN"
    cases["two different packet cases"] = m
    m = copy.deepcopy(base)
    m["entries"][0]["exclusion_reason"] = "version_named_but_working"
    cases["a reason neither reader supports"] = m
    verdicts = {name: all(two_blind(e) for e in doc["entries"]) for name, doc in cases.items()}
    check("E1 the two-blind rule rejects: " + "; ".join(cases),
          all(two_blind(e) for e in base["entries"]) and not any(verdicts.values()), str(verdicts))

    target_block, _target = row_of(text, TARGET)
    drifted = text.replace(target_block, target_block.replace("  severity: ", "  severity: x", 1), 1)
    assert drifted != text
    proc, same = refused("aux118-e2-", drifted, manifest=fixture_manifest())
    check("E2 the row moved since it was pinned: the whole run refuses and writes nothing",
          proc.returncode == 1 and "block changed since the manifest was pinned" in proc.stdout and same,
          proc.stdout[-300:])

    wyt4_block, _wyt4_row = row_of(text, WYT4)
    extra = dict(copy.deepcopy(base["entries"][0]), **dict(zip(SEL, WYT4)),
                 block_sha256_before=sha(wyt4_block), block_sha256_after=sha(own_edit(wyt4_block, REASON)))
    extra["adjudication"]["second_blind"]["label"] = "UNSURE"
    extra_doc = copy.deepcopy(base)
    extra_doc["entries"].append(extra)
    proc, same = refused("aux118-e3-", None, None, extra_doc)
    check("E3 the must-stay #13989 row added without two INCORRECT labels refuses the whole run and writes nothing",
          proc.returncode == 1 and "lacks two INCORRECT labels" in proc.stdout and same, proc.stdout[-300:])

    print("F  writers")
    expected_writers = (
        ("build_consensus_from_evidence.py", "--product-id", WIN, "--product-id", OBS, "--reconcile-only"),
        ("apply_consensus_to_records.py", "--product-id", WIN, "--write-all", "--confirm-write"),
        ("apply_consensus_to_records.py", "--product-id", OBS, "--write-all", "--confirm-write"),
    )
    seen: list[tuple] = []
    saved = (wd.STORE, wd.GENERATED, wd.regenerate)
    try:
        with tempfile.TemporaryDirectory(prefix="aux118-f1-") as tmp:
            store, generated, man = make_tree(Path(tmp))
            wd.STORE, wd.GENERATED = store, generated
            wd.regenerate = lambda w=None: (seen.append(tuple(w)) or [])
            rc = wd.main(["--manifest", str(man), "--baseline", str(Path(tmp) / "none.json"),
                          "--write", "--confirm-write", "--regenerate"])
            seen.append(("rc", rc))
    finally:
        wd.STORE, wd.GENERATED, wd.regenerate = saved
    check("F1 --regenerate runs exactly the reconcile scoped to Windows and OBS and each product's own scoped "
          "promotion; nothing unscoped and no DaVinci step",
          seen == [expected_writers, ("rc", 0)] and all(w.count("--product-id") >= 1 for w in expected_writers)
          and not any(DAV in w for w in seen[0]), str(seen)[:400])

    print("G  the committed store, and this suite changed nothing real")
    live_text = live_store.read_bytes().decode("utf-8")
    live_rows = blocks_by_identity(live_text)
    live_parsed = {ident(r): r for _lo, _hi, r in aux072.store_blocks(live_text)}
    for e in withdraw:
        row = live_parsed.get(ident(e), {})
        check(f"G1 {e['product_id']} {e['update_version']} #13995 is stored once, withdrawn as {e['exclusion_reason']}, "
              f"at its pinned after-hash",
              len(live_rows.get(ident(e), [])) == 1 and row.get("counted") is False
              and row.get("exclusion_reason") == e["exclusion_reason"]
              and sha(live_rows[ident(e)][0]) == e["block_sha256_after"] == TARGET_AFTER,
              str((row.get("counted"), row.get("exclusion_reason"))))
    stay_ok = {k: (len(live_rows.get(k, [])) == 1 and live_parsed.get(k, {}).get("counted") is True
                   and pinned_or_successor(k, pinned, sha(live_rows[k][0])))
               for k, pinned in STAY_HASHES.items()}
    sib = live_parsed.get(SIB_312, {})
    check("G2 the must-stay #13989 row and the report's 32.2.2 row are each stored once and still count, at their pinned "
          "hashes or a recorded successor; the report's 32.1.2 row stays withdrawn under AUX-088",
          all(stay_ok.values()) and len(live_rows.get(SIB_312, [])) == 1
          and (sib.get("counted"), sib.get("exclusion_reason")) == (False, REASON),
          str({k[1] + " " + k[3][-5:]: v for k, v in stay_ok.items()}))
    waya = live_parsed.get(WAYA, {})
    check("G3 the control finding is not re-admitted: stored once, still withdrawn as not_a_real_issue_report, at "
          "AUX-088's after-hash or a recorded successor",
          len(live_rows.get(WAYA, [])) == 1 and (waya.get("counted"), waya.get("exclusion_reason")) == (False, WAYA_REASON)
          and pinned_or_successor(WAYA, WAYA_AFTER, sha(live_rows[WAYA][0])),
          str((waya.get("counted"), waya.get("exclusion_reason"))))
    live_after = {str(p): sha(p.read_bytes()) for p in live_files if p.exists()}
    check("G4 the live store and the 31.1.2 record are byte-identical after the suite",
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
