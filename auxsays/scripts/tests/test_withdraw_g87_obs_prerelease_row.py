#!/usr/bin/env python3
"""The derived withdrawal of one OBS Studio 32.1.1 report posted before 32.1.1 was released (G87, AUX-127).

`withdraw_live_citation_rows.py` withdraws, with an eighth pinned manifest (audit/live_citation_withdrawal_v8.json),
the one stored row of GitHub issue #13278 counted against OBS Studio 32.1.1. The issue was opened on 2026-04-01
(UTC); 32.1.1 was released on 2026-04-02. The OBS acceptance gate refuses such a report
(collect_obs_reports.release_date_gate returns `before_release_date`); this row was accepted before the gate read the
post date. No label decides it: the tool decides it again on every run by CALLING that gate with the post time pinned
in audit/obs_report_dates.json and the record's update_published_at. It is the first label-free withdrawal reason, so
its contract is pinned here:

  A  the committed manifest names exactly that row by its full five-field identity, version 8, with the derived
     reason and NO adjudication labels; the reason is granted for exactly that identity in the tool's code; the
     must-stay rows and the out-of-scope 32.1.2 row are listed and are not entries; it shares no row with an earlier
     manifest; the tool's reader accepts it; the committed run audit is this manifest's run and states the derived
     basis (the gate, the pinned post time, the release date)
  V  the vocabulary is VERSIONED: the seven earlier manifests (v1-v7) are byte-identical and still accepted under
     exactly the legacy five reasons; a v1-v7 manifest that lists the derived reason, and a version-8 manifest that
     does not, both refuse
  B  a dry run plans the one row and writes nothing
  C  --write --confirm-write changes exactly 2 lines, keeps every row, leaves every other row byte-identical (the
     must-stay rows included), starts no row counting, leaves source_date_pass as stored, and the evidence-loss guard
     reads it as an audited withdrawal; the fixture's counts fall by exactly the one row
  D  a second run changes nothing
  P  every refusal the derivation carries fails closed and writes nothing: no pinned post time, no release date, an
     unreadable release date, a gate result other than before_release_date, a stored source_date that is not the
     pinned day, adjudication labels on the entry or on the stored row, a named kept row, a non-OBS product, and an
     OBS row the grant does not name
  R  re-admission: the OBS collector's dedupe refuses the report seen again, and no resolver, tier or re-admission
     lane lists the reason in the positive set it promotes from
  F  --regenerate for this manifest runs exactly the reconcile scoped to Windows and OBS and each product's own
     scoped promotion
  G  the committed store holds the row once, withdrawn, at its pinned after-hash; the must-stay rows still count at
     their pinned hashes (or a recorded successor); no counted 32.1.1 row was posted before the release; this suite
     changed nothing real

The tool runs as a BARE script, so B-P run it as a subprocess, exactly as an operator would. Offline: the frozen AUX-088
fixture (tests/fixtures/live_citation/withdrawal_store.yml, synthetic text) with two synthetic 32.1.1 blocks derived
from its own 32.1.1 block (the target, dated the day before the release, and a must-stay row dated after it), its
records' identity front matter with the 32.1.1 release time added, and a synthetic pinned-date file. The manifest's
block hashes are re-pinned on the fixture with the suite's own edit. No live-corpus count is asserted.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_withdraw_g87_obs_prerelease_row.py
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

import collect_obs_reports as obs_collector  # noqa: E402
import readmit_adjudicated_rows as readmit  # noqa: E402
import withdraw_live_citation_rows as wd  # noqa: E402
import withdraw_windows_identity_not_the_subject_rows as aux072  # noqa: E402
from lib import acrobat_tiering, context_resolution, evidence_loss as el, tier2_evidence  # noqa: E402
from patch_collectors import base as wd_base  # noqa: E402

TOOL = SCRIPTS / "withdraw_live_citation_rows.py"
AUDIT = SCRIPTS / "audit"
MANIFEST = AUDIT / "live_citation_withdrawal_v8.json"
RUN_AUDIT = AUDIT / "live_citation_withdrawal_v8_2026-11-22.json"
BASELINE = AUDIT / "live_citation_withdrawal_baseline_v2.json"
REPORT_DATES = AUDIT / "obs_report_dates.json"
FIX = SCRIPTS / "tests" / "fixtures" / "live_citation"
STORE_FIXTURE = FIX / "withdrawal_store.yml"
TARGETS = FIX / "withdrawal_targets.json"
NL = chr(10)
SEL = ("product_id", "update_version", "target_build", "id", "source_url")
WIN, OBS = "microsoft-windows-11", "obs-studio"
REASON = "before_release_date"
LEGACY = {"identity_not_the_subject", "duplicate_existing_evidence", "version_named_but_working",
          "version_is_rollback_target", "not_a_real_issue_report"}
PARENT = "4a559ed9f59cc5bb37e1003a001bdf9ba6529ec2"
# The committed run audit is the run at the branch's base (origin/main b3a8193a), whose store is byte-identical to
# the one the manifest pinned at PARENT (both hash to STORE_PIN); the run re-checks every pin against it.
RUN_PARENT = "b3a8193a12140087f5dcc83f71f0ae55f334cbf8"
STORE_PIN = "f92914e16ab1c1bbe035a6dd625868e93223236161e2c282db2e3de84a1a2674"
RECORD = "2026-04-02-obs-studio-32-1-1.md"
RELEASED = "2026-04-02T19:54:40Z"
POSTED = "2026-04-01T12:05:03Z"
URL_13278 = "https://github.com/obsproject/obs-studio/issues/13278"
RELEASE_32_1_1 = "https://github.com/obsproject/obs-studio/releases/tag/32.1.1"

# The row the gate refuses, written out in full here so neither the manifest nor the fixture can redefine it, and its
# pinned before/after block hashes on the live store.
TARGET = (OBS, "32.1.1", "", "obs-studio-32-1-1-github-issue-13278", URL_13278)
TARGET_BEFORE = "14e0b6ce062ad24616c9d5d2eed8fa93a537ad79b81eca06b2b267b091488490"
TARGET_AFTER = "9420d28e66d843734411c388a01e30aa1e859ac7f65fbcf57376e4ff9ea90ee7"
# The first two counted 32.1.1 reports posted after the release (the same gate accepts them).
FORUM = (OBS, "32.1.1", "", "obs-studio-32-1-1-obs-forum-thread-194821",
         "https://obsproject.com/forum/threads/nvenc-video-encoder-has-disappeared.194821/")
GH13286 = (OBS, "32.1.1", "", "obs-studio-32-1-1-github-issue-13286", "https://github.com/obsproject/obs-studio/issues/13286")
STAY_HASHES = {FORUM: "96335041770fc283eaa75fdde28245ed3ab71d7af694a3c3b8fa10060f60e066",
               GH13286: "e672383238be42c93ef5d77feae8f4e7ea70e7f63a7928a7099c037ea9d5fb62"}
OUT_OF_SCOPE = (OBS, "32.1.2", "", "obs-studio-32-1-2-github-issue-13518")
REPORT_DATES_SHA = "c39ed71349bc26c7f3c5ff65255362cf641d76d99ee1c77e03449e42ee4efccd"
# The seven earlier manifests of this tool, which this one must leave byte-identical.
EARLIER = {
    "live_citation_withdrawal.json": "e7fda1cf2cdf42a1dc88a8ab962c2ef3fbaec9599bff26077a6880f0247d9d24",
    "live_citation_withdrawal_v2.json": "51adfe324fed5eaea98a46e3857b9a737847d7f91a8777e332a793ad161d1490",
    "live_citation_withdrawal_v3.json": "eae1abf5d5f9f2c5be3c09fa1ea59b37438457a2ff01cb0309bc1ee62b9b588d",
    "live_citation_withdrawal_v4.json": "6394217b309b02fddf0b89ee1fe0773e01e26552c2b00a4ae3d8c48b0a705bc3",
    "live_citation_withdrawal_v5.json": "4cba0edcdea03d3406999891e8b6960c1fb9f23da72badda252208813935826d",
    "live_citation_withdrawal_v6.json": "e852e6bdba1826881a053612cca5c441b77fce08eb419c73eb26d177d74362a0",
    "live_citation_withdrawal_v7.json": "f75cefb8fcb1d5b2c3186da5c95ae6897e0847dc78422508e8f36731ebf16ba5",
}
PRIOR = ("windows_identity_not_the_subject_withdrawal.json", "windows_confirmed_and_duplicate_withdrawal.json",
         "live_citation_withdrawal.json", "live_citation_withdrawal_v2.json", "live_citation_withdrawal_baseline_v2.json",
         "live_citation_withdrawal_v3.json", "live_citation_withdrawal_v4.json", "acrobat_reader_readmission.json",
         "acrobat_reader_label_correction.json", "live_citation_withdrawal_v5.json", "live_citation_withdrawal_v6.json",
         "live_citation_withdrawal_v7.json")
# Fixture-based count deltas (the AUX-088 fixture plus two synthetic 32.1.1 rows; never the live corpus).
PER_PAGE = {(OBS, "32.1.1", ""): (4, 3)}

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


def own_edit(block: str, reason: str = REASON) -> str:
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


def derived_block(template: str, key: tuple[str, ...], source_date: str, extra: str = "") -> str:
    """A synthetic 32.1.1 block from the fixture's own 32.1.1 block: another report's id, URL and post day."""
    block = template.replace("- id: obs-studio-32-1-1-github-issue-13332" + NL, "- id: " + key[3] + NL, 1)
    block = block.replace("  source_url: https://github.com/obsproject/obs-studio/issues/13332" + NL,
                          "  source_url: " + key[4] + NL, 1)
    block = block.replace("  source_date: null" + NL, f"  source_date: '{source_date}'" + NL + extra, 1)
    block = block.replace("(AUX-088)", "(AUX-127)")
    assert block != template and key[3] in block and key[4] in block and source_date in block
    return block


def fixture_text(target_date: str = "2026-04-01", target_extra: str = "") -> str:
    """The AUX-088 fixture plus the synthetic target (posted the day before the release) and one synthetic must-stay
    row (posted the day after it)."""
    text = STORE_FIXTURE.read_bytes().decode("utf-8")
    template = blocks_by_identity(text)[(OBS, "32.1.1", "", "obs-studio-32-1-1-github-issue-13332",
                                         "https://github.com/obsproject/obs-studio/issues/13332")][0]
    if not text.endswith(NL):
        text += NL
    return (text + derived_block(template, TARGET, target_date, target_extra)
            + derived_block(template, GH13286, "2026-04-03"))


def targets_fixture(published: object = RELEASED) -> list[dict]:
    """The fixture's records, with the 32.1.1 release time set (or removed, when `published` is None)."""
    targets = json.loads(TARGETS.read_text(encoding="utf-8"))
    for target in targets:
        if target["file"] == RECORD:
            target["front_matter"].pop("update_published_at", None)
            if published is not None:
                target["front_matter"]["update_published_at"] = published
    return targets


def dates_doc(created: str | None = POSTED) -> dict:
    """A pinned-date file in AUX-090's shape: the target's post time (unless None) and the must-stay row's."""
    entries = [{**dict(zip(SEL, GH13286)), "source_date": "2026-04-03",
                "source": {"kind": "github_issue", "created_at": "2026-04-03T07:38:07Z"}}]
    if created is not None:
        entries.append({**dict(zip(SEL, TARGET)), "source_date": created[:10],
                        "source": {"kind": "github_issue", "created_at": created}})
    return {"schema": 1, "selector": list(SEL), "product_id": OBS, "entries": entries}


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
              manifest: dict | None = None, dates: dict | None = None) -> tuple[Path, Path, Path, Path]:
    store = tmp / "consensus_evidence.yml"
    store.write_bytes((store_text if store_text is not None else fixture_text()).encode("utf-8"))
    generated = tmp / "generated"
    generated.mkdir()
    for target in targets if targets is not None else targets_fixture():
        front = yaml.safe_dump(target["front_matter"], sort_keys=False)
        (generated / target["file"]).write_bytes(("---" + NL + front + "---" + NL).encode("utf-8"))
    man = tmp / "manifest.json"
    man.write_text(json.dumps(manifest if manifest is not None else fixture_manifest(store_text)), encoding="utf-8")
    dates_path = tmp / "report_dates.json"
    dates_path.write_text(json.dumps(dates if dates is not None else dates_doc()), encoding="utf-8")
    return store, generated, man, dates_path


def run_tool(store: Path, generated: Path, manifest: Path, dates: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, str(TOOL), "--store", str(store), "--generated-dir", str(generated),
                           "--manifest", str(manifest), "--baseline", str(store.parent / "no-baseline.json"),
                           "--report-dates", str(dates), *args],
                          capture_output=True, text=True, encoding="utf-8", env=env, timeout=600)


def refused(prefix: str, store_text: str | None = None, targets: list[dict] | None = None,
            manifest: dict | None = None, dates: dict | None = None) -> tuple[subprocess.CompletedProcess, bool]:
    """Run --write --confirm-write on a fixture tree and report whether the store came back byte-identical."""
    with tempfile.TemporaryDirectory(prefix=prefix) as tmp:
        store, generated, man, dates_path = make_tree(Path(tmp), store_text, targets, manifest, dates)
        before = store.read_bytes()
        proc = run_tool(store, generated, man, dates_path, "--write", "--confirm-write")
        return proc, store.read_bytes() == before


def reader_refusal(doc: dict) -> str:
    """The manifest reader's own verdict, in process: '' when it accepts, else its refusal text."""
    try:
        wd.manifest_entries(doc)
    except wd.Refusal as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001
        return f"CRASH {type(exc).__name__}: {exc}"
    return ""


def pinned_or_successor(key: tuple[str, ...], pinned: str, digest: str) -> bool:
    return digest == pinned or wd.load_baseline(BASELINE).get(key, {}).get(pinned) == digest


def issue_13278(html_url: str = URL_13278) -> dict:
    """GitHub issue #13278 as the collector's GitHub search would hand it over again (synthetic text)."""
    return {"number": 13278, "title": "Synthetic re-seen issue (AUX-127), not recorded source text",
            "body": "Synthetic body (AUX-127) naming 32.1.1 once.", "html_url": html_url, "created_at": POSTED}


def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Derived withdrawal of one OBS Studio 32.1.1 report posted before the release (AUX-127)")
    print("=" * 78)
    live_store = ROOT / "_data" / "consensus_evidence.yml"
    live_files = [live_store, ROOT / "updates" / "generated" / RECORD]
    live_before = {str(p): sha(p.read_bytes()) for p in live_files if p.exists()}
    manifest = manifest_doc()
    withdraw = [e for e in manifest["entries"] if e.get("role") == "withdraw"]

    print("A  the pinned manifest")
    check("A1 one OBS row is withdrawn and none is kept, under ledger AUX-127, version 8",
          len(withdraw) == 1 and len(manifest["entries"]) == 1 and manifest.get("ledger") == "AUX-127"
          and manifest.get("version") == 8 and withdraw[0].get("product_id") == OBS,
          f"{len(withdraw)} withdraw of {len(manifest['entries'])}")
    check("A2 the withdrawn row is exactly the 32.1.1 row of #13278, by its full five-field identity, with the derived "
          "reason, the collector's own rejection string",
          [ident(e) for e in withdraw] == [TARGET] and [e.get("exclusion_reason") for e in withdraw] == [REASON]
          and wd.DERIVED_REASON == REASON and obs_collector.release_date_gate({"created_at": POSTED},
                                                                              obs_collector.parse_date(RELEASED)) == REASON,
          str([ident(e)[1:4] for e in withdraw]))
    check("A3 the manifest declares the versioned vocabulary (the five plus the derived reason) and AUX-088's scope; the "
          "tool's legacy vocabulary is still exactly the five",
          tuple(manifest["selector"]) == SEL and sorted(manifest["exclusion_reasons"]) == sorted(LEGACY | {REASON})
          and set(wd.REASONS) == LEGACY and wd.DERIVED_VOCABULARY == frozenset(LEGACY | {REASON})
          and tuple(manifest["products"]) == wd.PRODUCTS == (WIN, OBS), str(manifest.get("exclusion_reasons")))
    check("A4 no label decides it: the entry carries no adjudication block and names no kept row, and the reason is "
          "granted in the tool's code for exactly this one identity",
          all(not e.get("adjudication") and not e.get("duplicate_of") and str(e.get("basis") or "").strip()
              for e in withdraw)
          and wd.DERIVED_GRANTS == {REASON: frozenset({TARGET})}, str(wd.DERIVED_GRANTS))
    stay = {ident(r): r.get("block_sha256") for r in manifest.get("must_stay_counted", [])}
    entries = {ident(e) for e in manifest["entries"]}
    oos = [tuple(str(r.get(k) or "") for k in SEL[:4]) for r in manifest.get("out_of_scope", [])]
    check("A5 the must-stay rows are the first two 32.1.1 reports posted after the release, at their pinned hashes; the "
          "32.1.2 row #13518 is recorded out of scope; none of them is an entry",
          stay == STAY_HASHES and oos == [OUT_OF_SCOPE] and not (entries & set(stay))
          and not any(k[:4] == OUT_OF_SCOPE for k in entries) and manifest.get("held_out") == [],
          str({k[3][-5:]: v for k, v in stay.items()}))
    prior_ids = set()
    for name in PRIOR:
        doc = json.loads((AUDIT / name).read_text(encoding="utf-8"))
        prior_ids |= {ident(e) for e in doc["entries"]}
    check("A6 no row is shared with any earlier withdrawal, label or re-admission manifest",
          not (prior_ids & entries), str(prior_ids & entries))
    derivation = manifest.get("derivation") or {}
    dates_entry = [e for e in json.loads(REPORT_DATES.read_text(encoding="utf-8"))["entries"] if ident(e) == TARGET]
    check("A7 the manifest pins the parent commit, the store and the pinned-date file by hash, and the row's derived "
          "basis is the pinned post time, the stored day and the record's release time",
          manifest.get("parent_commit") == PARENT and manifest.get("store_sha256_at_pin") == STORE_PIN
          and derivation.get("post_time_source_sha256") == REPORT_DATES_SHA == sha(REPORT_DATES.read_bytes())
          and [e.get("record_file") for e in withdraw] == ["auxsays/updates/generated/" + RECORD]
          and [(e.get("block_sha256_before"), e.get("block_sha256_after")) for e in withdraw] == [(TARGET_BEFORE, TARGET_AFTER)]
          and [e.get("derived_basis") for e in withdraw] == [{"pinned_created_at": POSTED, "stored_source_date": POSTED[:10],
                                                             "record_update_published_at": RELEASED,
                                                             "gate_result": REASON}]
          and [(e.get("source") or {}).get("created_at") for e in dates_entry] == [POSTED],
          json.dumps(derivation)[:300])
    accepted = reader_refusal(manifest)
    check("A8 the tool's own manifest checks accept it", accepted == "" and wd.manifest_scope(manifest) == wd.PRODUCTS, accepted)
    run_audit = json.loads(RUN_AUDIT.read_text(encoding="utf-8")) if RUN_AUDIT.exists() else {}
    deltas = {(p["product_id"], p["update_version"], p["target_build"]): p["before"] - p["after"]
              for p in run_audit.get("per_patch") or []}
    population = {k: v[0] - v[1] for k, v in (run_audit.get("counted_population") or {}).items()}
    basis = [(e.get("derived_basis") or {}) for e in run_audit.get("entries") or []]
    check("A9 the committed run audit is this manifest's run: written, one row withdrawn at the base whose store is the "
          "pinned one, the manifest's hash, only the 32.1.1 page and the OBS population losing exactly one, no row newly "
          "counted, the derived basis stated (the gate, both timestamps with their sources, the result), the three "
          "scoped writers ok",
          run_audit.get("written") is True and run_audit.get("withdrawn_now") == 1
          and run_audit.get("parent_commit") == RUN_PARENT and run_audit.get("store_sha256_before") == STORE_PIN
          and run_audit.get("manifest_sha256") == sha(MANIFEST.read_bytes())
          and deltas == {(OBS, "32.1.1", ""): 1} and population == {WIN: 0, OBS: 1}
          and run_audit.get("newly_counted_rows") == [] and run_audit.get("product_scope") == [WIN, OBS]
          and sorted(run_audit.get("exclusion_reasons") or []) == sorted(LEGACY | {REASON})
          and basis == [{"gate": "collect_obs_reports.release_date_gate", "pinned_created_at": POSTED,
                         "pinned_created_at_source": {
                             "file": "auxsays/scripts/audit/obs_report_dates.json", "file_sha256": REPORT_DATES_SHA,
                             "ledger": "AUX-090", "field": "entries[].source.created_at", "kind": "github_issue",
                             "read": "GET https://api.github.com/repos/obsproject/obs-studio/issues/13278 (created_at)",
                             "url": URL_13278},
                         "release_date": RELEASED,
                         "release_date_source": {"file": "auxsays/updates/generated/" + RECORD,
                                                 "field": "update_published_at",
                                                 "official_source_url": RELEASE_32_1_1},
                         "gate_result": REASON}]
          and [w["command"] for w in run_audit.get("writers") or []] == [" ".join(w) for w in wd.writers_for(wd.PRODUCTS)]
          and all(w["returncode"] == 0 for w in run_audit.get("writers") or []),
          json.dumps({k: run_audit.get(k) for k in ("written", "withdrawn_now", "per_patch", "entries")})[:500])

    print("V  the versioned vocabulary")
    hashes = {name: sha((AUDIT / name).read_bytes()) for name in EARLIER}
    check("V1 the seven earlier manifests (v1-v7) are byte-identical to their pins",
          hashes == EARLIER, str({k: v[:12] for k, v in hashes.items() if v != EARLIER[k]}))
    earlier = {name: json.loads((AUDIT / name).read_text(encoding="utf-8")) for name in EARLIER}
    earlier_ok = {name: (reader_refusal(doc), sorted(wd.manifest_vocabulary(doc))) for name, doc in earlier.items()}
    check("V2 the tool still accepts each of them, each under exactly the legacy five reasons",
          all(v == ("", sorted(LEGACY)) for v in earlier_ok.values()), str(earlier_ok)[:400])
    widened = copy.deepcopy(earlier["live_citation_withdrawal_v7.json"])
    widened["exclusion_reasons"] = sorted(LEGACY | {REASON})
    narrow = copy.deepcopy(manifest)
    narrow["exclusion_reasons"] = sorted(LEGACY)
    unversioned = copy.deepcopy(manifest)
    unversioned["version"] = 7
    w_ref, n_ref, u_ref = reader_refusal(widened), reader_refusal(narrow), reader_refusal(unversioned)
    check("V3 a v7 manifest that lists the derived reason refuses, a version-8 manifest without it refuses, and this "
          "manifest relabelled version 7 refuses",
          "closed vocabulary" in w_ref and "version-8 manifest must list" in n_ref and "closed vocabulary" in u_ref,
          f"{w_ref!r} / {n_ref!r} / {u_ref!r}")

    print("B  dry run, as the bare script")
    with tempfile.TemporaryDirectory(prefix="aux127-dry-") as tmp:
        store, generated, man, dates_path = make_tree(Path(tmp))
        before = store.read_bytes()
        proc = run_tool(store, generated, man, dates_path)
        out = proc.stdout
        check("B1 a dry run exits 0 and writes nothing", proc.returncode == 0 and store.read_bytes() == before,
              proc.stdout[-400:] + proc.stderr[-400:])
        check("B2 it plans exactly the one row, with the derived reason",
              out.count("[withdraw ") == 1 and "rows withdrawn by this run: 1" in out and "[kept " not in out
              and "obs-studio 32.1.1  before_release_date" in out, out[-600:])

    print("C  the write")
    with tempfile.TemporaryDirectory(prefix="aux127-write-") as tmp:
        store, generated, man, dates_path = make_tree(Path(tmp))
        before_bytes = store.read_bytes()
        audit_path = Path(tmp) / "audit.json"
        p3 = run_tool(store, generated, man, dates_path, "--write", "--confirm-write", "--audit", str(audit_path),
                      "--parent-commit", "e" * 40)
        check("C1 --write --confirm-write withdraws the one row and says so",
              p3.returncode == 0 and "WROTE" in p3.stdout and "rows withdrawn by this run: 1" in p3.stdout,
              p3.stdout[-500:] + p3.stderr[-500:])
        before_text, after_text = before_bytes.decode("utf-8"), store.read_bytes().decode("utf-8")
        a_lines, b_lines = before_text.split(NL), after_text.split(NL)
        changed = [(a, b) for a, b in zip(a_lines, b_lines) if a != b]
        expected = collections.Counter({("  counted: true", "  counted: false"): 1,
                                        ("  exclusion_reason: null", "  exclusion_reason: " + REASON): 1})
        check("C2 exactly 2 lines change, no validity line is added and source_date_pass is untouched",
              len(a_lines) == len(b_lines) and collections.Counter(changed) == expected and len(changed) == 2
              and after_text.count("evidence_valid_for_current_patch") == before_text.count("evidence_valid_for_current_patch")
              and after_text.count("source_date_pass: null") == before_text.count("source_date_pass: null"),
              f"{len(changed)} changed: {collections.Counter(changed)}")
        after_blocks, before_blocks = blocks_by_identity(after_text), blocks_by_identity(before_text)
        fman = json.loads(man.read_text(encoding="utf-8"))
        check("C3 the withdrawn block now hashes to its after-value, re-pinned on the fixture with the suite's own edit",
              all([sha(b) for b in after_blocks.get(ident(e), [])] == [e["block_sha256_after"]]
                  == [sha(own_edit(before_blocks[ident(e)][0]))] for e in fman["entries"]))
        rows_b = [r for _lo, _hi, r in aux072.store_blocks(before_text)]
        rows_a = [r for _lo, _hi, r in aux072.store_blocks(after_text)]
        moved = [(o, n) for o, n in zip(rows_b, rows_a) if ident(o) == TARGET]
        check("C4 the row parses as withdrawn, every other field unchanged (source_date_pass still null), no field added",
              len(moved) == 1 and all(n == dict(o, counted=False, exclusion_reason=REASON) and set(n) == set(o)
                                      and n.get("source_date_pass") is None for o, n in moved))
        others = [k for k in before_blocks if k != TARGET]
        parsed_a, parsed_b = {ident(r): r for r in rows_a}, {ident(r): r for r in rows_b}
        check("C5 no row is added or removed; every other row is byte-identical, and the must-stay row still counts",
              len(rows_a) == len(rows_b) and len(others) == len(rows_b) - 1
              and all(after_blocks.get(k) == before_blocks[k] for k in others)
              and parsed_a[GH13286].get("counted") is True, f"{len(rows_a)} rows")
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
        fbasis = [(e.get("derived_basis") or {}) for e in audit.get("entries") or []]
        fdates = sha(dates_path.read_bytes())
        check("C9 fixture counts: the 32.1.1 page loses exactly the one row and Windows does not move; the audit states "
              "the derived basis: the gate's result, the pinned post time with its source (the pinned file by name and "
              "hash, the field, the source kind) and the release time with its source (the record file, "
              "update_published_at)",
              audit.get("written") is True and audit.get("withdrawn_now") == 1 and per_page == PER_PAGE
              and len(set((audit.get("counted_population") or {}).get(WIN) or [None, "moved"])) == 1
              and [(b.get("gate_result"), b.get("pinned_created_at"), b.get("release_date")) for b in fbasis]
              == [(REASON, POSTED, RELEASED)]
              and [((b.get("pinned_created_at_source") or {}).get("file"),
                    (b.get("pinned_created_at_source") or {}).get("file_sha256"),
                    (b.get("pinned_created_at_source") or {}).get("field"),
                    (b.get("pinned_created_at_source") or {}).get("kind")) for b in fbasis]
              == [("report_dates.json", fdates, "entries[].source.created_at", "github_issue")]
              and [((b.get("release_date_source") or {}).get("file"), (b.get("release_date_source") or {}).get("field"))
                   for b in fbasis] == [(RECORD, "update_published_at")]
              and audit.get("parent_commit") == "e" * 40,
              json.dumps({k: audit.get(k) for k in ("withdrawn_now", "counted_population", "per_patch")})[:600])

        print("D  idempotence")
        p4 = run_tool(store, generated, man, dates_path, "--write", "--confirm-write")
        check("D1 a second run exits 0, writes nothing and reports the row as already withdrawn",
              p4.returncode == 0 and "nothing to write" in p4.stdout and store.read_bytes().decode("utf-8") == after_text
              and p4.stdout.count("[already_withdrawn") == 1, p4.stdout[-400:] + p4.stderr[-300:])

        print("R  re-admission: the next scheduled OBS collection sees #13278 again")
        again = obs_collector.evidence_row(issue_13278(), "32.1.1", "body", "2026-12-01T00:00:00Z")
        pre = store.read_bytes()
        saved_path = obs_collector.EVIDENCE_PATH
        try:
            obs_collector.EVIDENCE_PATH = store
            added_obs, _total_obs, _rows_obs = obs_collector.write_evidence([again])
        finally:
            obs_collector.EVIDENCE_PATH = saved_path
        check("R1 the collector's row builder gives #13278 the stored id and URL, and its dedupe authority "
              "(write_evidence) refuses it: nothing is added and the store is byte-identical",
              ident(again) == TARGET and added_obs == 0 and store.read_bytes() == pre
              and obs_collector.EVIDENCE_PATH == saved_path, f"added={added_obs} ident={ident(again)}")
        check("R2 and the collector's acceptance gate itself refuses the report on 32.1.1 for the same reason",
              obs_collector.release_date_gate(issue_13278(), obs_collector.parse_date(RELEASED)) == REASON)
    lanes = {"context_resolution.RESOLVABLE_REASONS": context_resolution.RESOLVABLE_REASONS,
             "tier2_evidence.PROMOTABLE_REJECTIONS": tier2_evidence.PROMOTABLE_REJECTIONS,
             "acrobat_tiering.ACROBAT_TIERABLE_REJECTIONS": acrobat_tiering.ACROBAT_TIERABLE_REJECTIONS,
             "readmit_adjudicated_rows.FROM_REASONS": readmit.FROM_REASONS}
    check("R3 no resolver, tier or re-admission lane lists before_release_date in the positive set it promotes from "
          "(each set is non-empty, so the check is not vacuous)",
          all(sets and REASON not in sets for sets in lanes.values()), str({k: sorted(v) for k, v in lanes.items()}))

    print("P  every refusal of the derivation fails closed")
    text = fixture_text()
    base_doc = fixture_manifest(text)
    cases: dict[str, tuple] = {}
    cases["P1 no pinned post time"] = (None, None, None, dates_doc(created=None), "no pinned post time")
    cases["P2 no release date on the record"] = (None, targets_fixture(None), None, None, "no readable update_published_at")
    cases["P3 an unreadable release date"] = (None, targets_fixture("soon"), None, None, "no readable update_published_at")
    cases["P4 the gate accepts it (released before the post)"] = (None, targets_fixture("2026-03-30T10:00:00Z"), None, None,
                                                                  "the OBS release-date gate gives None")
    drifted_day = fixture_text(target_date="2026-03-31")
    cases["P5 the stored source_date is not the pinned post day"] = (drifted_day, None, fixture_manifest(drifted_day), None,
                                                                     "is not the pinned post day")
    labelled = copy.deepcopy(base_doc)
    labelled["entries"][0]["adjudication"] = {"first_audit": {"by": "x", "label": "INCORRECT", "reason": "x"}}
    cases["P6 adjudication labels on the entry"] = (None, None, labelled, None, "carries adjudication labels")
    row_labelled = fixture_text(target_extra="  adjudication: INCORRECT" + NL)
    cases["P7 adjudication labels on the stored row"] = (row_labelled, None, fixture_manifest(row_labelled), None,
                                                         "the stored row carries adjudication labels")
    dup = copy.deepcopy(base_doc)
    dup["entries"][0]["duplicate_of"] = dict(zip(SEL, GH13286))
    cases["P8 a named kept row"] = (None, None, dup, None, "names a kept row")
    blocks = blocks_by_identity(text)
    win_key = next(k for k in blocks if k[0] == WIN)
    windows = copy.deepcopy(base_doc)
    windows["entries"][0].update(dict(zip(SEL, win_key)), target_kb="KB0", target_os_build=win_key[2])
    cases["P9 a non-OBS product"] = (None, None, windows, None, "applies to OBS Studio rows only")
    other = copy.deepcopy(base_doc)
    other["entries"][0].update(dict(zip(SEL, GH13286)), block_sha256_before=sha(blocks[GH13286][0]),
                               block_sha256_after=sha(own_edit(blocks[GH13286][0])))
    cases["P10 an OBS row the grant does not name"] = (None, None, other, None, "not an identity this tool grants")
    for label, (store_text, targets, doc, dates, needle) in cases.items():
        proc, same = refused("aux127-p-", store_text, targets, doc, dates)
        check(f"{label}: the whole run refuses and writes nothing",
              proc.returncode == 1 and needle in proc.stdout and same, proc.stdout[-300:] + proc.stderr[-200:])
    control, control_same = refused("aux127-p0-")
    check("P0 control: the unmodified fixture is withdrawn by the same --write run (the refusals are not vacuous)",
          control.returncode == 0 and "WROTE" in control.stdout and not control_same, control.stdout[-300:])

    print("F  writers")
    expected_writers = (
        ("build_consensus_from_evidence.py", "--product-id", WIN, "--product-id", OBS, "--reconcile-only"),
        ("apply_consensus_to_records.py", "--product-id", WIN, "--write-all", "--confirm-write"),
        ("apply_consensus_to_records.py", "--product-id", OBS, "--write-all", "--confirm-write"),
    )
    seen: list[tuple] = []
    saved = (wd.STORE, wd.GENERATED, wd.regenerate)
    try:
        with tempfile.TemporaryDirectory(prefix="aux127-f1-") as tmp:
            store, generated, man, dates_path = make_tree(Path(tmp))
            wd.STORE, wd.GENERATED = store, generated
            wd.regenerate = lambda w=None: (seen.append(tuple(w)) or [])
            rc = wd.main(["--manifest", str(man), "--baseline", str(Path(tmp) / "none.json"),
                          "--report-dates", str(dates_path), "--write", "--confirm-write", "--regenerate"])
            seen.append(("rc", rc))
    finally:
        wd.STORE, wd.GENERATED, wd.regenerate = saved
    check("F1 --regenerate runs exactly the reconcile scoped to Windows and OBS and each product's own scoped "
          "promotion; nothing unscoped", seen == [expected_writers, ("rc", 0)], str(seen)[:400])

    print("G  the committed store, and this suite changed nothing real")
    live_text = live_store.read_bytes().decode("utf-8")
    live_rows = blocks_by_identity(live_text)
    live_parsed = {ident(r): r for _lo, _hi, r in aux072.store_blocks(live_text)}
    row = live_parsed.get(TARGET, {})
    check("G1 32.1.1 #13278 is stored once, withdrawn as before_release_date, at its pinned after-hash",
          len(live_rows.get(TARGET, [])) == 1 and row.get("counted") is False and row.get("exclusion_reason") == REASON
          and sha(live_rows[TARGET][0]) == TARGET_AFTER, str((row.get("counted"), row.get("exclusion_reason"))))
    stay_ok = {k: (len(live_rows.get(k, [])) == 1 and live_parsed.get(k, {}).get("counted") is True
                   and pinned_or_successor(k, pinned, sha(live_rows[k][0])))
               for k, pinned in STAY_HASHES.items()}
    check("G2 the two must-stay rows are each stored once and still count, at their pinned hashes or a recorded successor",
          all(stay_ok.values()), str({k[3][-6:]: v for k, v in stay_ok.items()}))
    from lib import verdict_projection  # noqa: PLC0415 - the canonical counted population
    _records, groups = verdict_projection.load_inputs(ROOT)
    dates = wd.load_report_dates(REPORT_DATES)
    early = []
    for counted_row in groups.get((OBS, "32.1.1", ""), []):
        created = dates.get(ident(counted_row), "") or str(counted_row.get("source_date") or "")
        if obs_collector.release_date_gate({"created_at": created}, obs_collector.parse_date(RELEASED)) == REASON:
            early.append(counted_row.get("id"))
    check("G3 no counted 32.1.1 row was posted before the release (the gate accepts every one), and #13278 is not among them",
          not early and TARGET[3] not in {r.get("id") for r in groups.get((OBS, "32.1.1", ""), [])}, str(early))
    live_after = {str(p): sha(p.read_bytes()) for p in live_files if p.exists()}
    check("G4 the live store and the 32.1.1 record are byte-identical after the suite",
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
