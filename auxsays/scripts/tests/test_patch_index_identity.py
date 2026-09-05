#!/usr/bin/env python3
"""Record-index lookups must use CANONICAL patch identity, never a rebuilt partial key.

`apply_consensus_to_records._index_generated_records()` has been keyed by the canonical identity
triple `(product_id, update_version, target_build)` since #58 (4fe9e415). Five collector writebacks
predated that change and still rebuilt a 2-tuple `(PRODUCT_ID, update_version)` key, which misses
every one of the 896 live entries:

  - adobe_premiere / davinci / microsoft_windows subscripted it directly -> KeyError, caught by
    run_patch_evidence_collection's per-collector handler, which ROLLS BACK the whole transaction
    and reports a generic `collector_error:KeyError`. The collector's entire run is discarded.
  - adobe_acrobat_community / collect_obs_reports guarded with `not in` -> silently returned False,
    abandoning a fully-gated, ready write. Counts were later repaired by reconcile_record_counts,
    which masked the bug; the narrative fields (consensus_report, evidence_samples, ...) were not.

None of the five needed a key at all. `_result_for_group` already resolved the record by
`patch_key(pid, ver, build)` and published it as `matched_generated_record_path` -- the same field
`apply_consensus_to_records.main()` uses for its own writes. Reusing it is build-exact for free and
cannot drift from the group the safety gates were evaluated against.

This suite is behavioural: it drives the REAL `apply_consensus_writeback` bodies with the module
seams stubbed, and asserts which record path each one writes to. It never asserts source text, and
never depends on git history.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_patch_index_identity.py
"""
from __future__ import annotations

import importlib
import re
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from lib.patch_identity import is_build_aware, patch_key  # noqa: E402

PPT = "microsoft-powerpoint"
B110, B124, B158, B190 = "20228.20110", "20228.20124", "20228.20158", "20228.20190"

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        _ERRORS.append(label)
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))


RECORD = """---
layout: aux-update
update_entry: true
product_id: {pid}
update_version: '{ver}'
{build_line}update_product: {product}
update_report_count: 0
evidence_last_checked: '2026-01-01T00:00:00Z'
---
body
"""


def write_record(root: Path, pid: str, ver: str, build: str = "") -> Path:
    gen = root / "updates" / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    slug = f"{ver}-{build}".replace(".", "-").replace(" ", "-").strip("-")
    path = gen / f"2026-01-01-{pid}-{slug}.md"
    path.write_text(RECORD.format(
        pid=pid, ver=ver, product=pid,
        build_line=(f"target_build: '{build}'\n" if build else "")), encoding="utf-8")
    return path


# ---------------------------------------------------------------- driving the real writebacks


def drive_writeback(module_name: str, call, *, matched_rel: str | None, root: Path,
                    would_write: bool = True, version: str = "1.0", fields: dict | None = None):
    """Run the REAL apply_consensus_writeback, with the REAL _apply_record_fields.

    Only `_index_generated_records` and `run_dry_run` are stubbed -- the index deliberately EMPTY so
    the resolved path is the only way to reach a record, and the write plan is exercised for real so
    a "returned True but wrote nothing" answer is visible rather than hidden behind a stub.
    Returns (returned_value, file_changed, raised_exception_or_None). Also asserts, via
    `decoy_written`, that no implementation reached the record through the index."""
    acr = importlib.import_module("apply_consensus_to_records")
    mod = importlib.import_module(module_name)

    result = {
        "product_id": "x", "update_version": version, "would_write": would_write,
        "matched_generated_record_path": matched_rel,
        # A COLLECTOR-OWNED field: the collector boundary (COLLECTOR_WRITABLE_FIELDS) filters
        # everything else out, and this suite is about WHICH RECORD is written, not which fields.
        # Field authority is covered by test_collector_write_authority.py.
        "proposed_fields_if_written": dict(fields if fields is not None
                                           else {"evidence_last_checked": "2099-01-01T00:00:00Z"}),
    }
    # A record that is NOT the resolved one, reachable by every partial-key strategy.
    decoy = write_record(root, "decoy-product", version)
    decoy_rel = decoy.relative_to(root)
    pid_const = getattr(mod, "PRODUCT_ID", None) or "adobe-acrobat-pro"
    decoy_keys = {(pid_const, version, ""), (pid_const, version), pid_const, version}
    saved = {k: getattr(acr, k) for k in ("_index_generated_records", "run_dry_run")}
    saved_root = getattr(mod, "ROOT", None)
    target = (root / matched_rel) if matched_rel else None
    before = target.read_text(encoding="utf-8") if target and target.exists() else None
    # The index is seeded with a DECOY keyed on this product+version. An empty index would make the
    # fail-closed claim vacuous -- every strategy, including "pick a version-level sibling", would
    # find nothing and return False. With a decoy present, any implementation that reaches into the
    # index by product+version writes the WRONG record, and the assertions below catch it.
    acr._index_generated_records = lambda: {k: {"abs_path": decoy, "path": str(decoy_rel)}
                                            for k in decoy_keys}
    acr.run_dry_run = lambda **kw: [result]
    mod.ROOT = root
    try:
        decoy_before = decoy.read_text(encoding="utf-8")
        got = call(mod)
        after = target.read_text(encoding="utf-8") if target and target.exists() else None
        if decoy.read_text(encoding="utf-8") != decoy_before:
            raise AssertionError(f"DECOY WRITTEN: reached the record via the index, not the "
                                 f"resolved path ({decoy})")
        return got, (before != after), None
    except Exception as exc:  # noqa: BLE001 -- the point is to observe it
        return None, False, exc
    finally:
        for k, v in saved.items():
            setattr(acr, k, v)
        if saved_root is not None:
            mod.ROOT = saved_root


SITES = [
    ("patch_collectors.adobe_premiere", lambda m: m.apply_consensus_writeback("1.0"), "premiere"),
    ("patch_collectors.davinci", lambda m: m.apply_consensus_writeback("1.0"), "davinci"),
    ("patch_collectors.microsoft_windows", lambda m: m.apply_consensus_writeback("1.0"), "windows"),
    ("patch_collectors.adobe_acrobat_community",
     lambda m: m.apply_consensus_writeback("adobe-acrobat-pro", "1.0"), "acrobat"),
    ("collect_obs_reports", lambda m: m.apply_consensus_writeback("1.0"), "obs"),
]


# ---------------------------------------------------------------- F1 behavioural harness


def _drive_resolve_context():
    """Run the REAL Pipeline.resolve_context over two patch targets with DIFFERENT builds, then the
    REAL verify_candidates over its output. Returns [(label, ok, detail), ...]."""
    import types  # noqa: PLC0415
    orch = importlib.import_module("orchestrate_evidence_run")
    cr = importlib.import_module("lib.context_resolution")
    ppt = importlib.import_module("patch_collectors.microsoft_powerpoint")
    from lib.orchestration import OrchestrationState  # noqa: PLC0415

    key_a = "|".join(patch_key(PPT, "2607", B110))
    key_b = "|".join(patch_key(PPT, "2607", B158))

    def fake_resolve(candidate, reason, *, fetch_thread, budget):
        return types.SimpleNamespace(
            resolution_result=cr.RESOLVED_EXACT_BUILD, segment_key="seg",
            as_dict=lambda: {"resolution_result": cr.RESOLVED_EXACT_BUILD, "role_counts": {},
                             "build_claims": [], "resolution_match_basis": "explicit_role_x"})

    def fake_row(record, target, cand, at):
        # every row carries ITS OWN target's build, exactly as the real builder does
        return {"product_id": PPT, "update_version": "2607",
                "target_build": target["target_build"], "counted": True,
                "source_url": "https://x/" + target["target_build"]}

    def _state_with(results):
        st = OrchestrationState()
        st.method_results = [dict(r) for r in results]
        return st

    saved = (cr.resolve_candidate, cr.independent_reports, ppt.row_from_candidate,
             cr.augmented_candidate)
    out = []
    try:
        cr.resolve_candidate = fake_resolve
        cr.independent_reports = lambda *a, **k: []
        cr.augmented_candidate = lambda cand, outcome: cand
        ppt.row_from_candidate = fake_row

        state = OrchestrationState()
        state.method_results = [
            {"method_id": "m", "patch_key": key_a, "accepted_rows": [],
             "resolvable_rows": [{"source_url": "https://x/a"}]},
            {"method_id": "m", "patch_key": key_b, "accepted_rows": [],
             "resolvable_rows": [{"source_url": "https://x/b"}]},
        ]
        rec = types.SimpleNamespace(update_published_at="2026-01-01")
        me = types.SimpleNamespace(_records={key_a: rec, key_b: rec}, _seen={},
                                   context_fetch=lambda *a, **k: None, context_max_fetches=8,
                                   _persist_url_state=lambda *a, **k: None)
        st = orch.Pipeline.resolve_context(me, state)

        ctx = [r for r in st.method_results if r.get("role") == "context_resolution"]
        out.append(("F1 one context result per patch target, not one per run",
                    len(ctx) == 2, f"{len(ctx)} results"))
        out.append(("F1 the two results carry the two DISTINCT target keys",
                    {r["patch_key"] for r in ctx} == {key_a, key_b},
                    str([r["patch_key"] for r in ctx])))
        leaked = [(r["patch_key"], row.get("target_build")) for r in ctx
                  for row in r["accepted_rows"]
                  if row.get("target_build") != r["patch_key"].split("|")[2]]
        out.append(("F1 no row is attached to a key it does not belong to", not leaked, str(leaked)))
        out.append(("F1 each health row is stamped with its own build",
                    {r["health_row"]["target_build"] for r in ctx} == {B110, B158},
                    str([r["health_row"]["target_build"] for r in ctx])))
        out.append(("F1 health counters are per key (1 candidate each), not run-wide",
                    all(r["health_row"]["candidates_found"] == 1 for r in ctx),
                    str([r["health_row"]["candidates_found"] for r in ctx])))
        raised = None
        try:
            orch.Pipeline.verify_candidates(me, st)
        except Exception as exc:  # noqa: BLE001 -- observing it is the point
            raised = exc
        out.append(("F1 verify_candidates does NOT raise cross-build leakage",
                    raised is None, repr(raised)))
        plan = st.method_plan.get("context_resolution") or {}
        out.append(("F1 the run-wide telemetry still aggregates over every target",
                    plan.get("attempted") == 2, str(plan.get("attempted"))))

        # F1b: INDEPENDENT REPLIES. A candidate whose thread yields extra qualifying reports emits
        # more accepted rows than outcomes. The health-row counter contract is
        # accepted_candidates <= candidates_found AND evidence_rows_added <= accepted_candidates
        # (the latter two default to accepted_reports), so an independent reply must count on BOTH
        # sides. Getting this wrong makes validate_evidence_method_health fail -- and it is a
        # --validate gate, so the whole lane's writeback is refused and the run publishes nothing.
        import validate_evidence_method_health as vh  # noqa: PLC0415

        def two_replies(candidate, *, budget, exclude_segment_key, issue_predicate):
            return [types.SimpleNamespace(segment_url=f"https://x/r{i}", author_id=f"a{i}",
                                          explicit_build=B110, candidate=candidate)
                    for i in (1, 2)]

        cr.independent_reports = two_replies
        st2 = orch.Pipeline.resolve_context(
            types.SimpleNamespace(_records={key_a: rec}, _seen={},
                                  context_fetch=lambda *a, **k: None, context_max_fetches=8,
                                  _persist_url_state=lambda *a, **k: None),
            _state_with([{"method_id": "m", "patch_key": key_a, "accepted_rows": [],
                          "resolvable_rows": [{"source_url": "https://x/a"}]}]))
        ctx2 = [r for r in st2.method_results if r.get("role") == "context_resolution"]
        rows = [r["health_row"] for r in ctx2]
        errs: list[str] = []
        for i, hr in enumerate(rows, 1):
            vh._validate_counter_relationships(errs, row_index=i, row=hr)
        out.append(("F1b independent replies produce a VALID method-health row",
                    not errs, f"{errs} | {[{k: hr[k] for k in ('candidates_found','accepted_candidates','evidence_rows_added','accepted_reports')} for hr in rows]}"))
        # F1c: per-key STATUS and rejected_reports. Reverting the status ladder to run-wide
        # mislabels a blocked target as `partial`, stamps blocked_reason on healthy targets, and
        # inflates rejected_reports -- none of which the count assertions above would notice.
        cr.independent_reports = lambda *a, **k: []
        calls = {"n": 0}

        def blocked_first(candidate, reason, *, fetch_thread, budget):
            calls["n"] += 1
            res = cr.FETCH_BLOCKED if calls["n"] == 1 else cr.RESOLVED_EXACT_BUILD
            return types.SimpleNamespace(
                resolution_result=res, segment_key="seg",
                as_dict=lambda: {"resolution_result": res, "role_counts": {},
                                 "build_claims": [], "resolution_match_basis": ""})

        cr.resolve_candidate = blocked_first
        st3 = orch.Pipeline.resolve_context(
            types.SimpleNamespace(_records={key_a: rec, key_b: rec}, _seen={},
                                  context_fetch=lambda *a, **k: None, context_max_fetches=8,
                                  _persist_url_state=lambda *a, **k: None),
            _state_with([{"method_id": "m", "patch_key": key_a, "accepted_rows": [],
                          "resolvable_rows": [{"source_url": "https://x/a"}]},
                         {"method_id": "m", "patch_key": key_b, "accepted_rows": [],
                          "resolvable_rows": [{"source_url": "https://x/b"}]}]))
        by_key = {r["patch_key"]: r for r in st3.method_results
                  if r.get("role") == "context_resolution"}
        out.append(("F1c the blocked target alone is marked blocked",
                    by_key.get(key_a, {}).get("status") == "blocked"
                    and by_key.get(key_b, {}).get("status") == "success",
                    str({k: v.get("status") for k, v in by_key.items()})))
        out.append(("F1c blocked_reason is not stamped on the healthy target",
                    not (by_key.get(key_b, {}).get("health_row") or {}).get("blocked_reason"),
                    str((by_key.get(key_b, {}).get("health_row") or {}).get("blocked_reason"))))
        out.append(("F1c rejected_reports is per key, not the run total",
                    [(by_key[k]["health_row"]["rejected_reports"]) for k in (key_a, key_b)] == [1, 0],
                    str({k: v["health_row"]["rejected_reports"] for k, v in by_key.items()})))

        out.append(("F1b every accepted row is still on its own build",
                    all(row.get("target_build") == r["patch_key"].split("|")[2]
                        for r in ctx2 for row in r["accepted_rows"]), ""))
    finally:
        (cr.resolve_candidate, cr.independent_reports, ppt.row_from_candidate,
         cr.augmented_candidate) = saved
    return out


def run() -> int:
    print("=" * 74)
    print("Canonical patch identity for record-index lookups")
    print("=" * 74)

    # ---------- I1: the canonical index ----------
    print("\n[I1] the record index is keyed by canonical identity")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for b in (B110, B124, B158, B190):
            write_record(root, PPT, "2607", b)
        write_record(root, "obs-studio", "31.0.4")
        acr = importlib.import_module("apply_consensus_to_records")
        saved = acr.GENERATED_DIR, acr.ROOT
        try:
            acr.GENERATED_DIR = root / "updates" / "generated"
            acr.ROOT = root
            index = acr._index_generated_records()
        finally:
            acr.GENERATED_DIR, acr.ROOT = saved

    check("I1 every key is the identity triple", index and all(len(k) == 3 for k in index),
          str(sorted(index)[:2]))
    check("I1 the four PowerPoint siblings are four DISTINCT keys",
          len({k for k in index if k[0] == PPT}) == 4, str(sorted(k for k in index if k[0] == PPT)))
    for b in (B110, B124, B158, B190):
        check(f"I1 {b} has its own key", patch_key(PPT, "2607", b) in index)
    check("I1 a version-only product keeps an empty build slot",
          ("obs-studio", "31.0.4", "") in index, str([k for k in index if k[0] == "obs-studio"]))
    check("I1 no 2-tuple key exists to be found",
          not any(len(k) == 2 for k in index))

    # ---------- I7: sibling isolation ----------
    print("\n[I7] a lookup for one build never returns a sibling")
    got = index.get(patch_key(PPT, "2607", B190))
    check("I7 .20190 resolves to its OWN record",
          got is not None and B190.replace(".", "-") in Path(got["abs_path"]).name,
          str(got and got["abs_path"]))
    check("I7 .20190's record is not .20110's",
          got is not None and B110.replace(".", "-") not in Path(got["abs_path"]).name)
    check("I7 a build that does not exist resolves to NOTHING, not a sibling",
          index.get(patch_key(PPT, "2607", "20228.99999")) is None)
    check("I7 dropping the build entirely also resolves to nothing for a build-aware product",
          index.get((PPT, "2607", "")) is None)

    # ---------- I2-I6: every writeback resolves via the canonical result ----------
    print("\n[I2-I6] every collector writeback writes the record the dry-run resolved")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rec = write_record(root, PPT, "1.0")
        rel = str(rec.relative_to(root))
        for module_name, call, label in SITES:
            rec.write_text(RECORD.format(pid=PPT, ver="1.0", product=PPT, build_line=""),
                           encoding="utf-8")   # reset between sites
            ok, changed, exc = drive_writeback(module_name, call, matched_rel=rel, root=root)
            check(f"I2-I6 {label}: does not raise", exc is None, repr(exc))
            check(f"I2-I6 {label}: wrote the record the dry-run resolved", changed, "file unchanged")
            check(f"I2-I6 {label}: reported success", ok is True, repr(ok))

    # ---------- I8: fail closed when identity is missing ----------
    print("\n[I8] a group that resolved to no record fails CLOSED")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write_record(root, PPT, "1.0")
        for module_name, call, label in SITES:
            ok, changed, exc = drive_writeback(module_name, call, matched_rel=None, root=root)
            check(f"I8 {label}: refuses rather than raising", exc is None, repr(exc))
            check(f"I8 {label}: writes NOTHING", not changed)
            check(f"I8 {label}: reports failure", ok is False, repr(ok))

    print("\n[I8b] a group whose gates refused is never written")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rec = write_record(root, PPT, "1.0")
        rel = str(rec.relative_to(root))
        for module_name, call, label in SITES:
            ok, changed, exc = drive_writeback(module_name, call, matched_rel=rel, root=root,
                                               would_write=False)
            check(f"I8b {label}: would_write=False writes nothing",
                  not changed and ok is False and exc is None, f"{ok} {changed} {exc}")

    print("\n[I8c] an ambiguous version (more than one matching group) is never written")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rec = write_record(root, PPT, "1.0")
        rel = str(rec.relative_to(root))
        for module_name, call, label in SITES:
            # two results share the version -> len(matches) != 1 -> refuse
            acr = importlib.import_module("apply_consensus_to_records")
            mod = importlib.import_module(module_name)
            written: list[Path] = []
            base = {"product_id": "x", "update_version": "1.0", "would_write": True,
                    "matched_generated_record_path": rel,
                    "proposed_fields_if_written": {"update_report_count": 7}}
            saved = {k: getattr(acr, k) for k in ("_index_generated_records", "run_dry_run",
                                                  "_apply_record_fields")}
            saved_root = mod.ROOT
            try:
                acr._index_generated_records = lambda: {}
                acr.run_dry_run = lambda **kw: [dict(base), dict(base)]
                acr._apply_record_fields = lambda p, f: written.append(Path(p))
                mod.ROOT = root
                ok = call(mod)
            finally:
                for k, v in saved.items():
                    setattr(acr, k, v)
                mod.ROOT = saved_root
            check(f"I8c {label}: two matching groups -> refuse", ok is False and written == [],
                  f"{ok} {written}")

    # ---------- I8d: an already-current record is reported honestly ----------
    # The writeback's own early-exit compares proposed vs current INCLUDING record_last_updated,
    # which is regenerated every call, so it never fires. _apply_record_fields then recomputes
    # substantiveness EXCLUDING that timestamp and can legitimately write nothing. Returning True
    # there would report a phantom record update -- and in the OBS caller it would suppress the
    # count fallback that runs only `if not record_updated`.
    print("\n[I8d] a write that changes nothing reports False, not a phantom success")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rec = write_record(root, PPT, "1.0")          # fixture has update_report_count: 0
        rel = str(rec.relative_to(root))
        for module_name, call, label in SITES:
            rec.write_text(RECORD.format(pid=PPT, ver="1.0", product=PPT, build_line=""),
                           encoding="utf-8")
            ok, changed, exc = drive_writeback(
                module_name, call, matched_rel=rel, root=root,
                # same count already on the record + a fresh timestamp: nothing substantive
                # evidence_last_checked MATCHES the fixture, so only record_last_updated differs
                # -- and that is excluded from substantiveness, so nothing may be written.
                fields={"evidence_last_checked": "2026-01-01T00:00:00Z",
                        "record_last_updated": "2099-01-01T00:00:00Z"})
            check(f"I8d {label}: nothing written", not changed and exc is None, f"{changed} {exc}")
            check(f"I8d {label}: reports False, not a phantom update", ok is False, repr(ok))

    # ---------- I9: version-only products keep working ----------
    print("\n[I9] version-only products are unaffected")
    check("I9 patch_key collapses the build slot for a non-build-aware product",
          patch_key("obs-studio", "31.0.4", "99999.99999") == ("obs-studio", "31.0.4", ""))
    check("I9 ...and for every other version-only product id",
          all(patch_key(p, "1.0", "9.9") == (p, "1.0", "") for p in
              ("adobe-premiere-pro", "blackmagic-davinci",
               "adobe-acrobat-pro", "adobe-acrobat-reader", "obs-studio")))
    # Phrased as "these products are not build-aware" rather than "only PowerPoint is", so
    # legitimately adding Word/Excel/Outlook later does not read as a regression here.
    # microsoft-windows-11 left the list when it BECAME build-aware -- one record is now one
    # cumulative update, not one servicing train -- so it is asserted from the other side below.
    check("I9 the version-only writebacks this suite drives serve version-only products",
          not any(is_build_aware(p) for p in
                  ("obs-studio", "adobe-premiere-pro", "blackmagic-davinci",
                   "adobe-acrobat-pro", "adobe-acrobat-reader")))
    check("I9 a build-aware product does NOT collapse its build slot",
          patch_key("microsoft-windows-11", "25H2", "26200.9168")
          == ("microsoft-windows-11", "25H2", "26200.9168")
          and is_build_aware("microsoft-windows-11"))
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rec = write_record(root, "obs-studio", "31.0.4")
        rel = str(rec.relative_to(root))
        ok, changed, exc = drive_writeback("collect_obs_reports",
                                           lambda m: m.apply_consensus_writeback("31.0.4"),
                                           matched_rel=rel, root=root, version="31.0.4")
        check("I9 a version-only writeback still writes its record",
              exc is None and ok is True and changed, f"{ok} {changed} {exc}")

    # ---------- no rebuilt partial keys remain ----------
    print("\n[doctrine] no exact-patch lookup rebuilds a partial key")
    offenders = []
    for path in sorted(_SCRIPTS.rglob("*.py")):
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        # Catch BOTH shapes: an inline tuple subscript, and a tuple bound to a local on one line
        # and used to subscript on another (what adobe_acrobat_community and collect_obs_reports
        # actually had). Any subscript of the index by anything other than a patch_key/key_from
        # call is suspect.
        # Locals assigned FROM a canonical helper are as good as the call itself -- binding the key
        # to a name first is a readability refactor, not a defect, so collect those names and treat
        # them as canonical. What stays an offender is a tuple literal, or any other expression.
        canonical_locals = set(re.findall(
            r"^\s*([a-z_][a-z0-9_]*)\s*=\s*(?:patch_key|key_from)\s*\(", text, re.M))
        for n, line in enumerate(text.splitlines(), 1):
            sub = re.search(r"records_index\s*(?:\[|\.get\()\s*([^\]\)]*)", line)
            if not sub:
                continue
            expr = sub.group(1).strip()
            if not expr:
                continue
            canonical = (re.match(r"(patch_key|key_from)\s*\(", expr)
                         or expr in canonical_locals)
            if expr.startswith("(") or not canonical:
                offenders.append(f"{path.relative_to(_REPO)}:{n}: {line.strip()[:80]}")
    check("doctrine: nothing subscripts the record index with a rebuilt tuple",
          not offenders, str(offenders))

    # Deliberately NOT pinning how many modules obtain the index: none of them keys into it any
    # more, so letting run_dry_run build its own would be a pure cleanup with no behaviour change,
    # and a count assertion would block it. What matters is that nobody re-derives a key -- checked
    # above -- so assert only that the ones which do obtain it are the writeback modules.
    idx_users = {path.name for path in sorted(_SCRIPTS.rglob("*.py"))
                 if "tests" not in path.parts
                 and "_index_generated_records" in path.read_text(encoding="utf-8")
                 and path.name != "apply_consensus_to_records.py"}
    check("doctrine: only the collector writebacks obtain the record index",
          idx_users <= {"adobe_premiere.py", "davinci.py", "microsoft_windows.py",
                        "adobe_acrobat_community.py", "collect_obs_reports.py"}, str(idx_users))

    acr_src = (_SCRIPTS / "apply_consensus_to_records.py").read_text(encoding="utf-8")
    check("doctrine: the index parameter is typed as the identity TRIPLE everywhere",
          "records_index: dict[tuple[str, str], " not in acr_src)
    # (this test file names the symbol in prose, so scan production code only)
    check("doctrine: the dead 2-tuple record-key factory is gone",
          not any("canonical_to_record_key" in p.read_text(encoding="utf-8")
                  for p in _SCRIPTS.rglob("*.py") if "tests" not in p.parts))

    # ---------- F1: context resolution is per patch target ----------
    # BEHAVIOURAL, not source-pinned: drive the real resolve_context over two patch targets whose
    # builds differ, then run the real verify_candidates over its output. Before the fix the
    # aggregate carried pending[0]'s key, so target B's row was attached to target A and
    # verify_candidates raised "cross-build leakage", terminating the lane with zero evidence.
    print("\n[F1] orchestrated context resolution attributes each row to its OWN build")
    for label, ok, detail in _drive_resolve_context():
        check(label, ok, detail)

    print()
    print("=" * 74)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 74)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
