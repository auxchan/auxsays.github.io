#!/usr/bin/env python3
"""Structured evidence facts (G68): written with every row, versioned, backfilled, and read FAIL-CLOSED.

GPT ruling P3 approved recording, per Tier 1 row, a normalized excerpt hash, a title-deduplication hash and
an issue bucket, computed when the row is written, so no scheduled reader has to re-read stored text. The
finding that justified it: `lib.verdict_reasons.support_problems` counts two cited rows with the same
excerpt as ONE reporter, and when the excerpt is absent it stopped collapsing them -- every URL became a
reporter, which fails OPEN. Pinned here:

  A  the three rules, by frozen vectors (a behaviour change without a new rule version fails here); the
     pre-G68 normalisations are the same functions; ONE issue-bucket function;
  B  the persistence boundaries write the facts (base.append_evidence_rows, collect_obs_reports);
  C  ADVERSARIAL: a missing, malformed, unknown-version or other-rule fact can never make a reviewed
     verdict reason supported; on the live corpus the fact-based rule decides exactly what the text rule
     did, and no perturbation of a cited row's facts ever adds support;
  D  the accessors never rebuild a fact from the row's text;
  E  coherence and the zero-network migration (scope proven by hash, idempotent, refuses a partial set);
  F  the replay tools keep the facts equal to the labels they rewrite;
  G  the identities the facts group (source, report, duplicate group) need no text;
  H  three simulated mutants -- fail-open fallback, wrong-version fact accepted, bucket recomputed from
     absent text -- each turns a check above false.

A hash is not a judgement (P3 critical safeguard): equal excerpt facts mean equal stored excerpts, which is
what the distinct-reporter rule compared before, and nothing more.

Offline: frozen rows, temporary stores and read-only reads of the checked-in store and reason file.
"""
from __future__ import annotations

import ast
import contextlib
import copy
import io
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import yaml  # noqa: E402

import apply_consensus_to_records as writer  # noqa: E402
import build_consensus_from_evidence as builder  # noqa: E402
import collect_obs_reports as obs  # noqa: E402
import migrate_evidence_facts as mig  # noqa: E402
import qa_patch_records as qa  # noqa: E402
import recompute_evidence_classification as rec  # noqa: E402
import recompute_teams_classification as rt  # noqa: E402
import withdraw_windows_identity_not_the_subject_rows as aux072  # noqa: E402
from lib import evidence_facts as ef  # noqa: E402
from lib import recent_reports  # noqa: E402
from lib import verdict_projection  # noqa: E402
from lib import verdict_reasons as vr  # noqa: E402
from lib.source_segments import report_url_key  # noqa: E402
from patch_collectors import base  # noqa: E402

STORE = ROOT / "_data" / "consensus_evidence.yml"
TEXT_FIELDS = ("report_title", "parent_title", "report_text_excerpt", "matched_context", "matched_text",
               "listing_card_title", "source_title")

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


@contextlib.contextmanager
def swapped(module, name, value):
    saved = getattr(module, name)
    setattr(module, name, value)
    try:
        yield
    finally:
        setattr(module, name, saved)


# ------------------------------------------------------------------------------- frozen vectors
# Computed under the v1 rules and checked against the PRE-G68 implementations (verdict_reasons._norm_excerpt,
# the merge_recent_reports key, both mirrored bucketers) on origin/main e2cfca68 before they were collapsed.
EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
EXCERPT_VECTORS = [
    (None, "", EMPTY),
    ("   ", "", EMPTY),
    ("Report number 1.", "report number 1.", "bcbd6310164634ac38f3d0a29ba235b93648708bb9b7484d9768d3678f6b728a"),
    ("  Same words\n\tposted   twice. ", "same words posted twice.",
     "40ec133892be849edc8254947a5de4e231105f0e3f072ec0353aadabc4a9c253"),
    ("SAME WORDS POSTED TWICE.", "same words posted twice.",
     "40ec133892be849edc8254947a5de4e231105f0e3f072ec0353aadabc4a9c253"),
    (" Non breaking　spaces ", "non breaking spaces",
     "cd63ed1b00506ceb55a1d82d20fc7c8b68879dc8f07be5547fc142ebb5ed41f9"),
    ("Ünïcödé ÇASE", "ünïcödé çase",
     "b3a55b43dd12effbf225320348a67666450d26dc398280dcb682860b10b85ee4"),
    (12345, "12345", "5994471abb01112afcc18159f6cc74b4f511b99806da59b3caf5a9c173cacfc5"),
    ("line1\r\nline2", "line1 line2", "1f5c080ae39f741cb927bef27d0a79de3eb78187a13f04d17f43963dc3eb7684"),
]
TITLE_VECTORS = [
    (None, "", EMPTY),
    (0, "", EMPTY),
    ("  A  B ", "a b", "c8687a08aa5d6ed2044328fa6a697ab8e96dc34291e8c2034ae8c38e6fcc6d65"),
    ("Foo  Bar", "foo bar", "fbc1a9f858ea9e177916964bd88c3d37b91a1e84412765e29950777f265c4b75"),
    ("x" * 100, "x" * 80, "d929cdeea7e6a0f46b59448d36a6fd491df8647cf292040508162ee5f6435ab8"),
    ("Ünïcödé Title — Ä", "ünïcödé title — ä",
     "b6bce082b28a29a30fff24aad46300eebf737d00329a6503ae99c7d6c28aad0d"),
    ("Tab\tand\nnewline", "tab and newline", "825a91a47c8402c90b0f52f618681f56036f2cafbf81c3a63997de1717c7c744"),
]
BUCKET_VECTORS = [
    ("blackmagic-davinci", "crash", "", "Magic Mask freezes", "Magic Mask crashes"),
    ("blackmagic-davinci", "", "", "decode error on render", "render/decode failures"),
    ("blackmagic-davinci", "", "delivery page", "", "render/export failures"),
    ("blackmagic-davinci", "", "", "Crash on launch", "startup or application crashes"),
    ("blackmagic-davinci", "", "", "Timeline is slow", "performance slowdowns"),
    ("blackmagic-davinci", "", "", "install fails", "installation problems"),
    ("blackmagic-davinci", "compatibility issue", "plugins / codecs", "codec plugin missing", "compatibility issue"),
    ("obs-studio", "", "", "scene list order", "scene list workflow regressions"),
    ("obs-studio", "", "", "scene selection lost", "scene list workflow regressions"),
    ("obs-studio", "", "", "audio mixer muted", "audio mixer or routing issues"),
    ("obs-studio", "", "", "Window capture black", "capture-source issues"),
    ("obs-studio", "", "", "Windows: plugin not loading", "plugin or setup compatibility"),
    ("obs-studio", "", "", "changing image file causes lag", "general workflow reports"),
    ("obs-studio", "", "", "OBS hangs on exit", "crash or stability problems"),
    ("obs-studio", "", "", "hotkey broken", "keyboard shortcut regressions"),
    ("obs-studio", "", "", "recording stops", "output or recording regressions"),
    ("adobe-acrobat-pro", "Install_Update-Failure", "general Acrobat workflow", "x", "install update failure"),
    ("adobe-acrobat-pro", "unspecified issue", "printing__pipeline", "x", "printing pipeline"),
    ("adobe-acrobat-pro", "unspecified issue", "general workflow", "x", "general workflow reports"),
    ("adobe-acrobat-pro", "", "", "", "general workflow reports"),
]
FROZEN_RULE_SETS = {"v1": {"excerpt_norm_sha256": "excerpt-norm-1", "title_dedup_sha256": "title-dedup-1",
                           "issue_bucket": "issue-bucket-1"}}


# ------------------------------------------------------------------------------- fixtures
OBS = "obs-studio"
URLS = [f"https://reports.test/g68/{i}" for i in range(1, 6)]


def row(i: int, excerpt: str) -> dict:
    return ef.with_facts({"id": f"row-{i}", "product_id": OBS, "update_version": "99.0.0",
                          "source_url": URLS[i - 1], "report_title": f"Problem {i}",
                          "report_text_excerpt": excerpt, "issue_theme": "audio mixer regression",
                          "severity": "high", "sentiment": "negative", "counted": True,
                          "patch_version_matched": True})


def entry(rows=(1, 2)) -> dict:
    return {"id": "g68-entry", "product_id": OBS, "update_version": "99.0.0", "verdict": "TEST FIRST",
            "reason_class": "corroborated_issue", "scope": "if you use the test setup",
            "reason": "Two users independently report that the test setup fails.",
            "evidence": [{"id": f"row-{i}", "source_url": URLS[i - 1]} for i in rows],
            "new_in_this_version": False, "reviewed_at": "2026-11-20", "basis": "test"}


def twins() -> list[dict]:
    return [row(1, "Same words posted twice."), row(2, "Same  words posted TWICE.")]


def distinct() -> list[dict]:
    return [row(1, "The mixer drops audio after the update."), row(2, "Recording stops after ten minutes.")]


def without(rows: list[dict], fields=ef.STORED_FIELDS) -> list[dict]:
    return [{k: v for k, v in r.items() if k not in fields} for r in rows]


def with_excerpt_facts(rows: list[dict], values: list, version="v1") -> list[dict]:
    out = []
    for r, value in zip(rows, values):
        r = dict(r)
        r[ef.EXCERPT_FACT] = value
        r[ef.VERSION_FIELD] = version
        out.append(r)
    return out


def supported(e: dict, rows: list[dict]) -> bool:
    return not vr.support_problems(e, rows, {})


def old_support_problems(entry_: dict, counted_rows, records_by_identity) -> list[str]:
    """The distinct-reporter rule as it stood before G68 (origin/main e2cfca68), reading the stored excerpt
    TEXT. Frozen here as the reference the fact-based rule must reproduce on the live corpus."""
    _s = vr._s
    problems: list[str] = []
    by_id = {_s(r.get("id")): r for r in counted_rows}
    cited = []
    for item in entry_.get("evidence") or []:
        r = by_id.get(_s(item.get("id")))
        if r is None:
            problems.append(f"row {item.get('id')!r} is not counted on this page")
            continue
        if _s(r.get("source_url")) != _s(item.get("source_url")):
            problems.append(f"row {item.get('id')!r} source_url differs from the counted row")
            continue
        cited.append(r)
    urls = {_s(r.get("source_url")) for r in cited}
    excerpts = {vr._norm_excerpt(r) for r in cited if vr._norm_excerpt(r)}
    reporters = min(len(urls), len(excerpts) if excerpts else len(urls))
    conf = entry_.get("official_confirmation")
    if conf:
        record = records_by_identity.get((_s(conf.get("product_id")), _s(conf.get("update_version")), ""))
        body = vr._norm_ws((record or {}).get("official_patch_notes_body"))
        if not record or vr._norm_ws(conf.get("statement")) not in body:
            problems.append("official confirmation is not found in the named record's captured official notes")
    needed = 1 if conf else 2
    if reporters < needed:
        problems.append(f"{reporters} distinct counted reporter(s); {needed} required")
    return problems


_LIVE: dict = {}


def live() -> dict:
    if not _LIVE:
        text = STORE.read_bytes().decode("utf-8")
        records, groups = verdict_projection.load_inputs(ROOT)
        _LIVE.update(text=text, rows=yaml.load(text, Loader=yaml.SafeLoader)["evidence"], groups=groups,
                     by_identity={vr.record_identity(r): r for r in records}, reasons=vr.load_reasons())
    return _LIVE


def perturbations(r: dict) -> list[tuple[str, dict]]:
    out = [("removed", {k: v for k, v in r.items() if k not in ef.STORED_FIELDS})]
    for label, value in (("int", 123), ("upper", "A" * 64), ("short", "0" * 63), ("nonhex", "g" * 64)):
        out.append((f"malformed:{label}", dict(r, **{ef.EXCERPT_FACT: value})))
    for label, version in (("v0", "v0"), ("V1", "V1"), ("int1", 1), ("blank", "")):
        out.append((f"version:{label}", dict(r, **{ef.VERSION_FIELD: version})))
    return out


# ------------------------------------------------------------------------------- checks

def part_a() -> None:
    print("[A] the rules: frozen, versioned, one implementation each")
    bad = [(v, ef.normalise_excerpt(v)) for v, norm, h in EXCERPT_VECTORS
           if ef.normalise_excerpt(v) != norm or ef.sha256_text(ef.normalise_excerpt(v)) != h
           or ef.compute_facts({"report_text_excerpt": v})[ef.EXCERPT_FACT] != h]
    check(f"A1 excerpt-norm-1 gives the frozen value and hash for all {len(EXCERPT_VECTORS)} vectors", not bad, str(bad))
    bad = [(v, ef.title_dedup_key(v)) for v, key, h in TITLE_VECTORS
           if ef.title_dedup_key(v) != key or ef.compute_facts({"report_title": v})[ef.TITLE_FACT] != h]
    check(f"A2 title-dedup-1 gives the frozen key and hash for all {len(TITLE_VECTORS)} vectors", not bad, str(bad))
    bad = [(p, ti, ef.compute_issue_bucket(p, {"issue_theme": th, "workflow_area": wa, "report_title": ti}))
           for p, th, wa, ti, want in BUCKET_VECTORS
           if ef.compute_issue_bucket(p, {"issue_theme": th, "workflow_area": wa, "report_title": ti}) != want
           or ef.compute_facts({"product_id": p, "issue_theme": th, "workflow_area": wa,
                                "report_title": ti})[ef.BUCKET_FACT] != want]
    check(f"A3 issue-bucket-1 gives the frozen bucket for all {len(BUCKET_VECTORS)} branch vectors", not bad, str(bad))
    check("A4 the rule sets are frozen: v1 names exactly these three rules, and v1 is current",
          ef.RULE_SETS == FROZEN_RULE_SETS and ef.CURRENT_VERSION == "v1" and ef.EMPTY_SHA256 == EMPTY
          and ef.STORED_FIELDS == ("excerpt_norm_sha256", "title_dedup_sha256", "issue_bucket", "facts_rule_version"),
          str(ef.RULE_SETS))
    excerpt_same = all(vr._norm_excerpt({"report_text_excerpt": v}) == ef.normalise_excerpt(v)
                       for v, _n, _h in EXCERPT_VECTORS)
    titles = ["Foo  Bar", "foo bar", "FOO BAR ", "Foo Baz", "x" * 81, "x" * 80 + "y"]
    fresh = [{"report_id": f"r{i}", "source_url": f"https://q.test/{i}", "report_date": f"2026-01-{i + 1:02d}",
              "release_window_key": "w", "report_title": t} for i, t in enumerate(titles)]
    merged, _stats = recent_reports.merge_recent_reports([], copy.deepcopy(fresh), promoted_urls=set())
    kept = {r["report_title"] for r in merged}
    first_by_key: dict = {}
    for r in fresh:
        first_by_key.setdefault(ef.title_dedup_key(r["report_title"]), r["report_title"])
    check("A5 the facts use the pre-G68 normalisations: verdict_reasons._norm_excerpt is excerpt-norm-1, and the "
          "Level-3 merge keeps one card per title-dedup-1 key",
          excerpt_same and kept == set(first_by_key.values()) and len(kept) == 3, str(sorted(kept)))
    defined = {}
    for module in (writer, builder):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        defined[module.__name__] = sorted(n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                                          and n.name in ("public_issue_bucket", "_public_issue_bucket",
                                                         "clean_public_phrase", "_clean_public_phrase"))
    check("A6 ONE bucket function: both publication modules name lib.evidence_facts.compute_issue_bucket and "
          "define no bucketer of their own",
          writer._public_issue_bucket is builder.public_issue_bucket is ef.compute_issue_bucket
          and writer._clean_public_phrase is builder.clean_public_phrase is ef.clean_public_phrase
          and not any(defined.values()), str(defined))


def part_b() -> None:
    print("[B] the persistence boundaries write the facts")
    fresh = {"id": "g68-new", "product_id": OBS, "update_version": "99.0.0", "source_type": "github_issue",
             "source_name": "GitHub", "source_url": "https://example.invalid/g68/new",
             "parent_title": "OBS hangs on exit", "report_title": "OBS hangs on exit",
             "report_text_excerpt": "  It hangs\non exit. ", "captured_at": "2026-11-20T00:00:00Z",
             "patch_version_matched": True, "counted": True, "issue_theme": "", "workflow_area": "",
             "sentiment": "negative", "severity": "high"}
    old = {"id": "g68-old", "product_id": OBS, "update_version": "99.0.0", "source_type": "github_issue",
           "source_url": "https://example.invalid/g68/old", "report_title": "Old", "report_text_excerpt": "Old.",
           "counted": False, "patch_version_matched": False}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "consensus_evidence.yml"
        base.write_evidence_file([old], path)
        before = path.read_bytes()
        planted = dict(fresh, **{ef.EXCERPT_FACT: "f" * 64, ef.BUCKET_FACT: "planted"})
        added, _total, _rows = base.append_evidence_rows([planted], path)
        after = path.read_bytes()
        stored = yaml.safe_load(after.decode("utf-8"))["evidence"]
        loaded = base.load_evidence(path)
    want = ef.compute_facts(base.normalize_evidence_row(fresh))
    check("B1 base.append_evidence_rows writes the four facts, computed from the row's own text, as its last keys",
          added == 1 and {k: stored[1].get(k) for k in ef.STORED_FIELDS} == want
          and list(stored[1])[-4:] == list(ef.STORED_FIELDS) and want[ef.BUCKET_FACT] == "crash or stability problems",
          str({k: stored[1].get(k) for k in ef.STORED_FIELDS}))
    check("B2 a fact the caller supplied is recomputed, never trusted", stored[1][ef.EXCERPT_FACT] != "f" * 64
          and stored[1][ef.BUCKET_FACT] != "planted")
    check("B3 the existing row keeps every byte and gains no facts (the boundary never touches a stored row)",
          after.startswith(before) and not ef.carries_facts(stored[0]))
    check("B4 load_evidence keeps the facts and adds none to a row that has none (no null keys)",
          ef.carries_facts(loaded[1]) and not any(k in loaded[0] for k in ef.STORED_FIELDS))
    saved = obs.EVIDENCE_PATH
    try:
        with tempfile.TemporaryDirectory() as tmp:
            obs.EVIDENCE_PATH = Path(tmp) / "consensus_evidence.yml"
            first = dict(fresh, id="obs-1", source_url="https://example.invalid/g68/obs1")
            second = dict(fresh, id="obs-2", source_url="https://example.invalid/g68/obs2",
                          report_text_excerpt="Another report.")
            obs.write_evidence([first])
            row1 = obs.parse_existing_rows(obs.EVIDENCE_PATH)[0]
            obs.write_evidence([second])
            rows = obs.parse_existing_rows(obs.EVIDENCE_PATH)
    finally:
        obs.EVIDENCE_PATH = saved
    check("B5 OBS's own writer (collect_obs_reports.write_evidence) writes the facts and leaves an existing row's alone",
          len(rows) == 2 and rows[0] == row1 and not ef.fact_problems(rows[0]) and not ef.fact_problems(rows[1])
          and rows[1][ef.EXCERPT_FACT] == ef.sha256_text("another report."), str(rows[1].get(ef.EXCERPT_FACT)))


def part_c() -> None:
    print("[C] adversarial: a missing or bad fact never adds support to a reviewed verdict reason")
    e = entry()
    check("C1 two cited rows with different excerpts are two reporters (supported)", supported(e, distinct()),
          str(vr.support_problems(e, distinct(), {})))
    check("C2 the same excerpt posted twice is one reporter (unsupported), compared by the excerpt fact",
          not supported(e, twins()) and twins()[0][ef.EXCERPT_FACT] == twins()[1][ef.EXCERPT_FACT])
    stripped = without(twins(), ef.STORED_FIELDS + ("report_text_excerpt",))
    problems = vr.support_problems(e, stripped, {})
    check("C3 twins with neither facts nor text stay unsupported, and say why (the text rule would have counted "
          "two reporters here: fail open)",
          bool(problems) and sum("excerpt_norm_sha256 unavailable (missing)" in p for p in problems) == 2
          and not old_support_problems(e, stripped, {}), str(problems))
    one = twins()
    one[1] = {k: v for k, v in one[1].items() if k not in ef.STORED_FIELDS}
    check("C4 a single cited row without its fact leaves the entry unsupported, even beside rows that have one",
          not supported(e, one) and not supported(e, without(distinct())), str(vr.support_problems(e, one, {})))
    malformed_pairs = [(1, 2), ("A" * 64, "B" * 64), ("0" * 63, "1" * 63), ("g" * 64, "h" * 64), ("a" * 65, "b" * 65)]
    wrongly_supported = [p for p in malformed_pairs if supported(e, with_excerpt_facts(twins(), list(p)))]
    check(f"C5 {len(malformed_pairs)} pairs of DIFFERENT malformed facts on twins never count as two reporters",
          not wrongly_supported, str(wrongly_supported))
    other_rule = [ef.sha256_text(t) for t in ("Same words posted twice.", "Same  words posted TWICE.")]
    bad_versions = ["v0", "V1", "v2", 1, None, ""]
    wrongly_supported = [v for v in bad_versions if supported(e, with_excerpt_facts(twins(), other_rule, version=v))]
    check(f"C6 well-formed but different hashes under {len(bad_versions)} unknown or missing versions never count",
          other_rule[0] != other_rule[1] and not wrongly_supported, str(wrongly_supported))
    # Rows written under v1, BEFORE the simulated rule change (a row is labelled with the version current
    # when it is written).
    v1_twins_other_rule, v1_distinct, v1_twins = with_excerpt_facts(twins(), other_rule), distinct(), twins()
    v2 = {**ef.RULE_SETS, "v2": {**ef.RULE_SETS["v1"], ef.EXCERPT_FACT: "excerpt-norm-2"}}
    with swapped(ef, "RULE_SETS", v2), swapped(ef, "CURRENT_VERSION", "v2"):
        outdated = supported(e, v1_twins_other_rule)
        reason = vr.support_problems(e, v1_distinct, {})
    v3 = {**ef.RULE_SETS, "v3": {**ef.RULE_SETS["v1"], ef.BUCKET_FACT: "issue-bucket-2"}}
    with swapped(ef, "RULE_SETS", v3), swapped(ef, "CURRENT_VERSION", "v3"):
        bucket_bump_keeps_excerpts = supported(e, v1_distinct) and not supported(e, v1_twins)
    check("C7 a fact computed under another rule than the current one is refused (outdated), while a bucket-only "
          "rule change leaves the excerpt facts usable: versions are per fact, never mixed",
          not outdated and any("(outdated)" in p for p in reason) and bucket_bump_keeps_excerpts, str(reason))
    no_text_twins = without(twins(), ("report_text_excerpt",))
    no_text_distinct = without(distinct(), ("report_text_excerpt",))
    check("C8 the rule never reads the excerpt text: with the text removed and the facts kept, twins are one "
          "reporter and distinct rows two",
          not supported(e, no_text_twins) and supported(e, no_text_distinct))
    data = live()
    groups, by_identity, reasons = data["groups"], data["by_identity"], data["reasons"]
    differ, decided_supported = [], 0
    for item in reasons:
        rows = groups.get(vr.reason_identity(item), [])
        new, old = vr.support_problems(item, rows, by_identity), old_support_problems(item, rows, by_identity)
        if new != old:
            differ.append(item.get("id"))
        decided_supported += not new
    check(f"C9 on the live corpus the fact-based rule decides exactly what the text rule decided, problem for "
          f"problem, for all {len(reasons)} reviewed entries ({decided_supported} supported)",
          len(reasons) > 0 and decided_supported > 0 and not differ, str(differ[:5]))
    gained, tried = [], 0
    for item in reasons:
        rows = groups.get(vr.reason_identity(item), [])
        base_ok = not vr.support_problems(item, rows, by_identity)
        cited = {str(x.get("id")) for x in item.get("evidence") or []}
        for index, r in enumerate(rows):
            if str(r.get("id")) not in cited:
                continue
            for label, bad in perturbations(r):
                tried += 1
                mutated = rows[:index] + [bad] + rows[index + 1:]
                if not vr.support_problems(item, mutated, by_identity):
                    gained.append((item.get("id"), label, base_ok))
    check(f"C10 no perturbation of a cited row's facts leaves a live entry supported ({tried} perturbations: every "
          "one refuses, so none can add support)", tried > 0 and not gained, str(gained[:5]))


def part_d() -> None:
    print("[D] the accessors never rebuild a fact from the text")
    r = {"product_id": "adobe-acrobat-pro", "issue_theme": "printing regression", "workflow_area": "printing",
         "report_title": "Printing fails"}
    try:
        ef.stored_issue_bucket(r)
        outcome = "returned"
    except ef.FactUnavailable as exc:
        outcome = exc.reason
    check("D1 a row with a theme, an area and a title but no bucket fact raises (missing); it is not re-bucketed",
          outcome == ef.MISSING, outcome)
    faceted = ef.with_facts(r)
    moved = dict(faceted, issue_theme="installation failure")
    check("D2 the stored bucket is returned as stored, even when the row's theme has since changed",
          ef.stored_issue_bucket(moved) == "printing regression" == faceted[ef.BUCKET_FACT])
    reasons = []
    for value in (None, "ABC", 5):
        try:
            ef.title_key(dict(faceted, **{ef.TITLE_FACT: value}))
            reasons.append("returned")
        except ef.FactUnavailable as exc:
            reasons.append(exc.reason)
    check("D3 the title fact: empty title -> None, missing or malformed -> refused",
          ef.title_key(ef.with_facts({"report_title": ""})) is None and reasons == [ef.MISSING, ef.MALFORMED, ef.MALFORMED],
          str(reasons))
    v2 = {**ef.RULE_SETS, "v2": {**ef.RULE_SETS["v1"], ef.BUCKET_FACT: "issue-bucket-2"}}
    with swapped(ef, "RULE_SETS", v2), swapped(ef, "CURRENT_VERSION", "v2"):
        try:
            ef.stored_issue_bucket(faceted)
            bucket = "returned"
        except ef.FactUnavailable as exc:
            bucket = exc.reason
        excerpt_ok = ef.require_fact(faceted, ef.EXCERPT_FACT) == faceted[ef.EXCERPT_FACT]
        problems = ef.fact_problems(faceted)
    check("D4 after a bucket rule change, a v1 bucket is refused (outdated) and the v1 excerpt still reads",
          bucket == ef.OUTDATED and excerpt_ok and problems == ["outdated:issue_bucket"], f"{bucket} {problems}")


def _store_text(rows: list[dict]) -> str:
    return yaml.safe_dump({"schema_version": 1, "evidence": rows}, sort_keys=False, allow_unicode=True, width=1000)


def part_e() -> None:
    print("[E] coherence and the zero-network migration")
    data = live()
    rows = data["rows"]
    problems = ef.store_fact_problems(rows)
    order = [i for i, r in enumerate(rows) if list(r)[-4:] != list(ef.STORED_FIELDS)]
    check(f"E1 every stored row carries current facts equal to its own text, as its last four keys ({len(rows)} rows)",
          len(rows) > 0 and not problems and not order, f"{ {k: len(v) for k, v in problems.items()} } order={order[:3]}")
    plain = [{"id": f"m{i}", "product_id": OBS, "update_version": "99.0.0", "source_url": f"https://m.test/{i}",
              "report_title": f"Title {i}", "report_text_excerpt": f"Excerpt {i}", "source_date": None,
              "issue_theme": "", "counted": True} for i in range(3)]
    mixed = [ef.with_facts(plain[0])] + plain[1:]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "store.yml"
        path.write_text(_store_text(mixed), encoding="utf-8", newline="")
        before = path.read_text(encoding="utf-8")
        report = mig.run(path, write=True)
        after = path.read_text(encoding="utf-8")
        again = mig.run(path, write=True)
        unchanged = path.read_text(encoding="utf-8") == after
    check("E2 the migration backfills only the rows without facts, keeps every other byte (hash proof), keeps "
          "null fields, and a second run changes nothing",
          report["backfilled"] == 2 and report["unchanged"] == 1 and report["written"] is True
          and ef.strip_fact_lines(after) == ef.strip_fact_lines(before) and "source_date: null" in after
          and again["proof"] == {"no_change": True} and unchanged
          and not ef.store_fact_problems(yaml.safe_load(after)["evidence"]), str(report.get("proof")))
    partial = [dict(plain[0], issue_bucket="general workflow reports"), plain[1]]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "store.yml"
        path.write_text(_store_text(partial), encoding="utf-8", newline="")
        before = path.read_bytes()
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = mig.main(["--store", str(path), "--write"])
        refused_untouched = path.read_bytes() == before
    check("E3 a partial fact set refuses the whole run and writes nothing", rc == 2 and refused_untouched
          and "partial fact set" in err.getvalue(), err.getvalue())
    stale = [ef.with_facts(plain[0]), dict(ef.with_facts(plain[1]), issue_theme="Display Regression")]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "store.yml"
        path.write_text(_store_text(stale), encoding="utf-8", newline="")
        before = path.read_text(encoding="utf-8")
        report = mig.run(path, write=True)
        after = path.read_text(encoding="utf-8")
    changed = [(a, b) for a, b in zip(before.splitlines(), after.splitlines()) if a != b]
    check("E4 a stale fact is rewritten in place, that line only",
          report["refreshed"] == 1 and len(changed) == 1 and changed[0][1] == "  issue_bucket: display regression"
          and len(before.splitlines()) == len(after.splitlines()), str(changed))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "store.yml"
        path.write_text(_store_text(plain), encoding="utf-8", newline="")
        mig.run(path, write=True)
        migrated = path.read_text(encoding="utf-8")
    check("E5 a backfilled row is byte-identical to the same row written by the append path (one format)",
          migrated == _store_text([ef.with_facts(r) for r in plain]))
    allowed = {"__future__", "argparse", "hashlib", "json", "sys", "pathlib", "typing", "yaml", "lib",
               "lib.evidence_facts", "lib.normalize", "re"}
    imported = set()
    for module in (mig, ef):
        for node in ast.walk(ast.parse(Path(module.__file__).read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
    check("E6 the migration and the facts module import nothing that can reach a network", imported <= allowed,
          str(sorted(imported - allowed)))
    clean = ef.with_facts(plain[0])
    stale_row = dict(ef.with_facts(plain[1]), issue_theme="Display Regression")
    codes = sorted(w["code"] for w in qa.scan_evidence_facts([plain[2], stale_row, clean]))
    check("E7 QA names rows without facts and rows whose fact differs from their own text, and nothing else",
          codes == ["evidence_facts_missing", "evidence_facts_stale"] and qa.scan_evidence_facts([clean]) == [],
          str(codes))
    text = data["text"]
    spans = aux072.store_blocks(text)
    leaked = [lo for lo, hi, _r in spans if ef._FACT_LINE.search(text[lo:hi])]
    gaps = [lo for (lo, hi, _r), nxt in zip(spans, [s[0] for s in spans[1:]] + [len(text)])
            if text[hi:nxt] != "".join(ef.fact_line(f, _r[f]) for f in ef.STORED_FIELDS)]
    check("E8 an audited block stops before its row's facts: every block hash a withdrawal manifest pinned before "
          "G68 still holds, and the facts sit exactly between the blocks",
          len(spans) == len(rows) and not leaked and not gaps, f"leaked={len(leaked)} gaps={len(gaps)}")


def part_f() -> None:
    print("[F] the replay tools keep the facts equal to the labels they rewrite")
    r = ef.with_facts({"id": "t1", "product_id": "microsoft-teams", "issue_theme": "", "workflow_area": "",
                       "report_title": "Dropped from meetings", "report_text_excerpt": "x"})
    check("F1 a rewritten theme moves the derived bucket on a row with facts, and nothing on a row without",
          ef.derived_fact_updates(r, {"issue_theme": "meeting join / connection failure"})
          == {ef.BUCKET_FACT: "meeting join / connection failure"}
          and ef.derived_fact_updates(without([r])[0], {"issue_theme": "x"}) == {}
          and ef.derived_fact_updates(r, {}) == {})
    text = _store_text([r])
    ids = ["t1"]
    try:
        edited = rec.apply_writes(text, ids, {0: {"issue_theme": "x y", ef.BUCKET_FACT: "x y"}})
        accepted = yaml.safe_load(edited)["evidence"][0][ef.BUCKET_FACT] == "x y"
    except SystemExit:
        accepted = False
    try:
        rec.apply_writes(text, ids, {0: {"counted": "true"}})
        refused = False
    except SystemExit:
        refused = True
    check("F2 the recompute write site accepts a derived fact line and still refuses any other key",
          accepted and refused)
    legacy = {"id": "join", "product_id": "microsoft-teams", "update_version": "26213.1006.5014.9784",
              "source_url": "https://example.org/join", "parent_title": "Dropped from meetings",
              "report_title": "Dropped from meetings",
              "report_text_excerpt": "Using Teams v. 26213.1006.5014.9784 on Win 11. Dropped from meetings repeatedly.",
              "counted": True, "exclusion_reason": None, "sentiment": "negative", "source_weight": 1,
              "issue_theme": "", "workflow_area": "", "platform": "Windows", "severity": ""}
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "store.yml"
        store.write_text(_store_text([ef.with_facts(legacy)]), encoding="utf-8", newline="")
        report = rt.run(store, write=True)
        after = yaml.safe_load(store.read_text(encoding="utf-8"))["evidence"][0]
    check("F3 the Teams replay rewrites the theme AND the bucket fact with it; the row's facts stay coherent",
          report["written"] is True and after["issue_theme"] == "meeting join / connection failure"
          and after[ef.BUCKET_FACT] == "meeting join / connection failure" and not ef.fact_problems(after),
          str(after.get(ef.BUCKET_FACT)))


def part_g() -> None:
    print("[G] the identities the facts group need no text")
    rows = live()["rows"]
    moved = []
    for r in rows:
        bare = {k: v for k, v in r.items() if k not in TEXT_FIELDS}
        if (base.evidence_key(r, "id"), base.evidence_key(r, "source_url"), report_url_key(str(r.get("source_url") or "")),
                ef.duplicate_group_key(r)) != (base.evidence_key(bare, "id"), base.evidence_key(bare, "source_url"),
                                               report_url_key(str(bare.get("source_url") or "")),
                                               ef.duplicate_group_key(bare)):
            moved.append(r.get("id"))
    check(f"G1 source identity, report identity and duplicate group are unchanged with every text field removed "
          f"({len(rows)} rows)", len(rows) > 0 and not moved, str(moved[:3]))


def part_h() -> None:
    print("[H] simulated mutants: each turns a check above false")
    e = entry()
    stripped = without(twins(), ef.STORED_FIELDS + ("report_text_excerpt",))
    real_dup = ef.duplicate_group_key

    def fail_open(r):
        try:
            return real_dup(r)
        except ef.FactUnavailable:
            return None
    with swapped(ef, "duplicate_group_key", fail_open):
        caught = supported(e, stripped)
    check("H1 mutant 'fail-open fallback' (a missing fact read as no duplicate) makes C3's twins supported; the "
          "real rule refuses them", caught and not supported(e, stripped))
    real_require = ef.require_fact

    def any_version(r, field):
        value = r.get(field)
        if value in (None, ""):
            raise ef.FactUnavailable(field, ef.MISSING)
        return value
    other_rule = [ef.sha256_text(t) for t in ("Same words posted twice.", "Same  words posted TWICE.")]
    wrong = with_excerpt_facts(twins(), other_rule, version="v0")
    with swapped(ef, "require_fact", any_version):
        caught = supported(e, wrong)
    check("H2 mutant 'wrong-version hash accepted' makes C6's twins supported; the real rule refuses them",
          caught and not supported(e, wrong) and ef.require_fact is real_require)
    r = {"product_id": "adobe-acrobat-pro", "issue_theme": "printing regression", "report_title": "Printing fails"}

    def rebucket(row_):
        return row_.get(ef.BUCKET_FACT) or ef.compute_issue_bucket(str(row_.get("product_id") or ""), row_)
    with swapped(ef, "stored_issue_bucket", rebucket):
        try:
            ef.stored_issue_bucket(r)
            caught = True
        except ef.FactUnavailable:
            caught = False
    try:
        ef.stored_issue_bucket(r)
        real = "returned"
    except ef.FactUnavailable:
        real = "refused"
    check("H3 mutant 'bucket recomputed from absent text' returns a bucket for D1's row; the real accessor refuses",
          caught and real == "refused")


def run_suite() -> int:
    print("=" * 92)
    print("Structured evidence facts (G68): written, versioned, backfilled, read fail-closed")
    print("=" * 92)
    part_a()
    part_b()
    part_c()
    part_d()
    part_e()
    part_f()
    part_g()
    part_h()
    print("=" * 92)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    if FAILURES:
        print("Failed: " + ", ".join(FAILURES))
    print("=" * 92)
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run_suite())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
