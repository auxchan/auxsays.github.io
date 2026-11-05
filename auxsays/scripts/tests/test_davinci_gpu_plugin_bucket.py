#!/usr/bin/env python3
"""DaVinci: "gpu" is not a performance cue, and the two publication bucketers agree (AUX-062 C+D).

Three defects, all measured on counted rows (Q4 measurement, origin/main 69e7a160):

  C. `gpus?` sat in the DaVinci performance rule and `"gpu" in text` in BOTH publication bucketers.
     A GPU error dialog, "GPU memory is full" or a hardware spec line therefore read as a
     performance regression: 10 of 36 stored "performance regression" rows (28%), 0 false negatives.
         "GPU failed to perform image processing because of an error. Error code 1"
         "DaVinci Resolve 21.1 - Your GPU memory is full"
         "SOLVED: DaVinci Resolve 21 “Unsupported GPU Processing Mode” on Windows 11 ..."
  D. apply_consensus_to_records._public_issue_bucket carried a DaVinci branch the builder never had:
     `if "plugin" in text: return "plugin issues"`. "plugin" entered only through the area label
     "plugins / codecs" (every compatibility row), so 7 codec/media reports were published as
     "plugin issues" on v16, 20.1, 20.1.1, 20.3.1, 21 PB1, 21 and 21.0. The builder was the reference.
  E. The historical correction needed a way to write NAMED rows only: the recompute tool's `--write`
     is global and selects its producer by capture date. `--only-id` narrows it, and never writes
     platform.

`gpu` STAYS in the frozen DaVinci sentiment triggers: sentiment is verdict-bearing and is not part
of this item. Offline: frozen rows, a temporary store, and one read of the shipped store.
"""
from __future__ import annotations

import itertools
import re
import subprocess
import sys
import tempfile
import traceback
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import yaml  # noqa: E402

import apply_consensus_to_records as writer                          # noqa: E402
import build_consensus_from_evidence as builder                      # noqa: E402
import recompute_evidence_classification as rc                       # noqa: E402
from patch_collectors import davinci                                 # noqa: E402

DV = "blackmagic-davinci"
PERF = "performance slowdowns"
GENERAL = "general workflow reports"
COMPAT = "compatibility issue"

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


def row(theme: str, area: str, title: str) -> dict:
    return {"product_id": DV, "issue_theme": theme, "workflow_area": area, "report_title": title}


def both(item: dict) -> tuple[str, str]:
    return writer._public_issue_bucket(DV, item), builder.public_issue_bucket(DV, item)


# --- verbatim false-positive titles (counted rows) ----------------------------------------------
GPU_FAILED = "GPU failed to perform image processing because of an error. Error code 1"
GPU_FULL = "DaVinci Resolve 21.1 - Your GPU memory is full"
GPU_UNSUPPORTED = ("SOLVED: DaVinci Resolve 21 “Unsupported GPU Processing Mode” on Windows 11 "
                   "— Root cause was CUDA_VISIBLE_DEVICES=-1")
GPU_RECOGNIZED = "Why isn't my GPU being recognized? (Resolve 21, Debian 13 KDE)"
SPEC_LINE = "DaVinci Resolve 21.1.1 Timeline bug"
SPEC_TEXT = "Specs: Mac Studio M5 Max (GPU 40 core, 64GB), MacOs 27.0.1 DaVinci Resolve 21.1.1 (free)"
SPEC_CPU = "CPU: AMD K19 GPU: 8176MB ATI AMD Radeon RX 7600"

FALSE_POSITIVES = (GPU_FAILED, GPU_FULL, GPU_UNSUPPORTED, GPU_RECOGNIZED, SPEC_LINE)
# The same words in the title, nothing else: what the bucketers read once the stored theme is repaired.
UNSPECIFIED = ("unspecified issue", "general DaVinci Resolve workflow")

# Genuine matches that must survive, each as (heading, body).
GENUINE_PERF = (
    ("Timeline playback is laggy after the update", ""),
    ("Viewer is very slow when scrubbing", ""),
    ("Performance dropped since 21.1", ""),
    ("Resolve lags with Fusion clips", ""),
)

# The 7 pages whose label the writer's "plugin" branch corrupted: codec/media reports, stored as the
# compatibility rule's own (theme, area).
COMPAT_THEME, COMPAT_AREA = "compatibility issue", "plugins / codecs"
CODEC_TITLES = (
    "H.265 footage will not import on 20.1 after the update",
    "AAC audio codec missing in the Linux build",
    "MP4 clips show black in the media pool",
)

# The ten stored rows (AUX-062 C): a counted DaVinci Reddit row stored "performance regression" on a
# bare "gpu" and nothing else. Nine are corrected; the tenth is not reproducible and stays.
CORRECTED_NINE = {
    "1t1gyr9-can-somebody-help-me-please": "unspecified issue",
    "1uizkd7-gpu-failed-to-perform-image-processing-be": "unspecified issue",
    "1wazcmw-davinci-resolve-211-your-gpu-memory-is-fu": "unspecified issue",
    "1w927vk-why-isnt-my-gpu-being-recognized-resolve": "install issue",
    "1waholl-the-new-davinci-resolve-211-version-is-br": "unspecified issue",
    "1wygy6n-davinci-resolve-2111-timeline-bug": "unspecified issue",
    "1x6lczv-solved-davinci-resolve-21-unsupported-gpu": "unspecified issue",
    "1x9zw94-sombody-please-help-me-im-loosing-my-mind": "unspecified issue",
}
UNRESOLVED_TENTH = "1os2u3c-ai-multicam-smartswitch-the-gpu-failed-to"


def load_store_rows() -> list[dict]:
    return yaml.load((ROOT / "_data" / "consensus_evidence.yml").read_bytes().decode("utf-8"),
                     Loader=yaml.SafeLoader)["evidence"]


def run_suite() -> int:
    print("=" * 92)
    print("DaVinci: 'gpu' is not a performance cue; both publication bucketers agree (AUX-062 C+D)")
    print("=" * 92)

    # ---- C1: the producer ----------------------------------------------------------------------
    themes = {title: davinci.classify(title, "")[0] for title in FALSE_POSITIVES}
    check("C1 producer: no verbatim GPU false-positive title is a performance regression",
          all(t != "performance regression" for t in themes.values()), str(themes))
    check("C2 producer: the performance rule no longer carries a gpu alternative",
          not re.search(r"\bgpus?\b", davinci._DAVINCI_THEME_RULES[-3].pattern.pattern, re.I)
          and not any(rule.pattern.search("gpu") for rule in davinci._DAVINCI_THEME_RULES
                      if rule.theme == "performance regression"),
          str([rule.pattern.pattern for rule in davinci._DAVINCI_THEME_RULES if rule.theme == "performance regression"]))
    check("C3 producer: a spec line naming the GPU is not a performance regression",
          davinci.classify(SPEC_LINE, SPEC_TEXT)[0] != "performance regression"
          and davinci.classify("Help me", SPEC_CPU)[0] != "performance regression",
          str((davinci.classify(SPEC_LINE, SPEC_TEXT), davinci.classify("Help me", SPEC_CPU))))
    genuine = [davinci.classify(h, b) for h, b in GENUINE_PERF]
    check("C4 producer: genuine performance / lag / slow reports are still performance regressions",
          all(g[0] == "performance regression" and g[1] == "timeline / GPU performance" for g in genuine),
          str(genuine))
    check("C5 producer: sentiment keeps 'gpu' (frozen trigger) -- a GPU-only report is still negative",
          "gpu" in davinci._DAVINCI_SENTIMENT_TRIGGERS
          and all(davinci.classify(t, "")[4] == "negative" for t in (GPU_FAILED, GPU_FULL, GPU_UNSUPPORTED)),
          str([davinci.classify(t, "")[4] for t in (GPU_FAILED, GPU_FULL, GPU_UNSUPPORTED)]))

    # ---- C: both bucketers ---------------------------------------------------------------------
    results = [both(row(*UNSPECIFIED, title)) for title in FALSE_POSITIVES]
    check("C6 writer: a GPU-only title is no longer bucketed as performance slowdowns",
          all(w != PERF for w, _ in results), str(results))
    check("C7 builder: a GPU-only title is no longer bucketed as performance slowdowns",
          all(b != PERF for _, b in results), str(results))
    check("C8 the two bucketers agree on every verbatim GPU false-positive title",
          all(w == b for w, b in results), str(results))
    check("C9 a GPU-only title falls through to the general bucket, not a made-up one",
          all(w == GENERAL for w, _ in results), str(results))
    genuine_rows = [row("performance regression", "timeline / GPU performance", h) for h, _ in GENUINE_PERF]
    genuine_rows += [row(*UNSPECIFIED, "Resolve is very slow and laggy on the color page")]
    check("C10 genuine performance rows still bucket as performance slowdowns in both copies",
          all(both(item) == (PERF, PERF) for item in genuine_rows), str([both(i) for i in genuine_rows]))
    stored = row("performance regression", "timeline / GPU performance", GPU_FULL)
    check("C11 an UNCORRECTED stored performance row keeps its stored bucket (forward-only until recomputed)",
          both(stored) == (PERF, PERF), str(both(stored)))

    # ---- D: the plugin branch ------------------------------------------------------------------
    compat = [row(COMPAT_THEME, COMPAT_AREA, title) for title in CODEC_TITLES]
    check("D1 writer: a codec/media report is bucketed as the builder buckets it, never 'plugin issues'",
          all(writer._public_issue_bucket(DV, item) == COMPAT for item in compat),
          str([writer._public_issue_bucket(DV, item) for item in compat]))
    check("D2 builder (the reference) buckets the same rows as 'compatibility issue'",
          all(builder.public_issue_bucket(DV, item) == COMPAT for item in compat),
          str([builder.public_issue_bucket(DV, item) for item in compat]))
    check("D3 the string 'plugin issues' is no longer producible for DaVinci",
          "plugin issues" not in {writer._public_issue_bucket(DV, row(t, a, h))
                                  for t in ("compatibility issue", "unspecified issue", "plugin compatibility")
                                  for a in ("plugins / codecs", "plugins", "general DaVinci Resolve workflow")
                                  for h in ("", "plugin crashes my timeline", "codec plugin missing")}
          and 'return "plugin issues"' not in Path(writer.__file__).read_text(encoding="utf-8"))
    check("D4 the OBS plugin bucket is untouched",
          writer._public_issue_bucket("obs-studio", row("plugin compatibility", "plugins", "x"))
          == builder.public_issue_bucket("obs-studio", row("plugin compatibility", "plugins", "x"))
          == "plugin or setup compatibility")

    # ---- the parity test -----------------------------------------------------------------------
    rule_pairs = {(rule.theme, rule.area) for rule in davinci._DAVINCI_THEME_RULES}
    rule_pairs |= {UNSPECIFIED, ("plugin compatibility", "plugins"), ("", "")}
    headings = [GPU_FAILED, GPU_FULL, SPEC_LINE, GPU_RECOGNIZED, "", "plugin crashes my timeline",
                "codec plugin missing", "Timeline is slow", "Render fails on export", "Crash on launch",
                "Magic Mask crash", "Install error", "Decode and render failure"] + list(CODEC_TITLES)
    grid = [row(t, a, h) for (t, a), h in itertools.product(sorted(rule_pairs), headings)]
    split = [(r["issue_theme"], r["workflow_area"], r["report_title"][:30], *both(r))
             for r in grid if both(r)[0] != both(r)[1]]
    check(f"E1 parity over the full rule-table x title grid: the two bucketers agree on all {len(grid)} synthetic rows",
          not split, str(split[:4]))

    store_rows = [r for r in load_store_rows() if r.get("product_id") == DV]
    store_split = [(r.get("id"), *both(r)) for r in store_rows if both(r)[0] != both(r)[1]]
    check(f"E2 parity over every DaVinci row in the store: the two bucketers agree on all {len(store_rows)} rows",
          len(store_rows) > 0 and not store_split, str(store_split[:4]))
    counts = Counter(writer._public_issue_bucket(DV, r) for r in store_rows)
    check("E3 'plugin issues' labels no longer appear anywhere in the store's DaVinci population",
          counts.get("plugin issues", 0) == 0, str(counts))
    # Reported, not gated: the OBS and other-product copies are outside this fix's scope.
    print(f"  INFO  DaVinci bucket population in the store: {dict(counts)}")

    # ---- the stored rows (historical correction) -----------------------------------------------
    def find(fragment: str) -> list[dict]:
        return [r for r in store_rows if fragment in r["id"]]

    wrong = {}
    for fragment, theme in CORRECTED_NINE.items():
        for r in find(fragment):
            if r["issue_theme"] != theme or r["workflow_area"] == "timeline / GPU performance":
                wrong[r["id"][-40:]] = (r["issue_theme"], r["workflow_area"])
    matched = sum(len(find(f)) for f in CORRECTED_NINE)
    check(f"F1 the nine corrected stored rows no longer carry the performance theme ({matched} rows incl. sibling versions)",
          matched >= 9 and not wrong, str(wrong))
    nine = [r for f in CORRECTED_NINE for r in find(f)]
    check("F2 the correction touched theme/area/severity only: all nine are still counted, negative, medium",
          all(r["counted"] is True and r["sentiment"] == "negative" and r["severity"] == "medium" for r in nine),
          str([(r["id"][-30:], r["counted"], r["sentiment"], r["severity"]) for r in nine if not (
              r["counted"] is True and r["sentiment"] == "negative" and r["severity"] == "medium")]))
    tenth = find(UNRESOLVED_TENTH)
    print(f"  INFO  unresolved tenth row ({UNRESOLVED_TENTH}): {[(r['issue_theme'], r['severity']) for r in tenth]}")

    # ---- E: --only-id on a temporary store ------------------------------------------------------
    def fake(rid: str, pid: str, title: str, excerpt: str, theme: str, area: str, platform: str,
             captured: str = "2026-09-01T00:00:00Z") -> dict:
        return {"id": rid, "product_id": pid, "update_version": "1.0", "source_url": f"https://example.org/{rid}",
                "parent_title": title, "report_title": title, "report_text_excerpt": excerpt,
                "issue_theme": theme, "workflow_area": area, "platform": platform, "severity": "medium",
                "sentiment": "negative", "counted": True, "exclusion_reason": None, "captured_at": captured,
                "source_date": "2026-04-10"}

    gpu_a = fake("gpu-a", DV, GPU_FULL, GPU_FULL + " Hi all, I upgraded this evening.",
                 "performance regression", "timeline / GPU performance", "unknown")
    gpu_b = fake("gpu-b", DV, GPU_FAILED, GPU_FAILED + " It happens every time I open a project.",
                 "performance regression", "timeline / GPU performance", "unknown")
    # Would also be rewritten by a global run, but is not named:
    gpu_unnamed = fake("gpu-unnamed", DV, GPU_UNSUPPORTED, GPU_UNSUPPORTED + " Root cause found.",
                       "performance regression", "timeline / GPU performance", "unknown")
    # A stored performance row that DOES carry a genuine cue is kept even when named.
    perf_ok = fake("perf-ok", DV, "Timeline is very slow", "Timeline is very slow and laggy.",
                   "performance regression", "timeline / GPU performance", "unknown")
    # Platform downgrade is a global-run behaviour: --only-id must never write it.
    plat = fake("plat", DV, "[Linux] DaVinci Resolve can't open projects",
                "[Linux] DaVinci Resolve can't open projects I switched from Windows to Linux.",
                "unspecified issue", "general DaVinci Resolve workflow", "windows")
    obs_same = fake("gpu-a", "obs-studio", "OBS Dock size issue", "Operating System Info Other",
                    "unspecified issue", "general OBS workflow", "unknown")
    tmp = Path(tempfile.mkdtemp(prefix="aux062_"))
    store = tmp / "consensus_evidence.yml"
    rows = [gpu_a, gpu_b, gpu_unnamed, perf_ok, plat, obs_same]
    store.write_text(yaml.safe_dump({"evidence": rows}, sort_keys=False, allow_unicode=True), encoding="utf-8")
    before = store.read_bytes()

    global_dry = rc.run(store, False)
    check("G1 premise: the unscoped tool WOULD rewrite more rows than the ones named",
          global_dry["rows_changed"] >= 3 and global_dry["platform_labels_written"] >= 1, str(global_dry["rows_changed"]))

    dry = rc.run(store, False, ("gpu-a", "gpu-b"), DV)
    check("G2 --only-id dry run: considers exactly the named rows", dry["rows_in_scope"] == 2, str(dry["rows_in_scope"]))
    check("G3 --only-id dry run writes nothing", store.read_bytes() == before and dry["written"] is False)
    check("G4 --only-id proposes theme, area and severity for the named rows, nothing else",
          {c["id"] for c in dry["changes"]} == {"gpu-a", "gpu-b"}
          and all(set(c) & {"platform"} == set() for c in dry["changes"])
          and all(c["issue_theme"] == ["performance regression", "unspecified issue"] for c in dry["changes"]),
          str(dry["changes"]))
    check("G5 --only-id never writes platform, even where the unscoped run would",
          rc.run(store, False, ("plat",), DV)["rows_changed"] == 0
          and rc.run(store, False)["platform_labels_written"] >= 1)
    check("G6 --only-id on a stored row with a genuine performance cue keeps it",
          rc.run(store, False, ("perf-ok",), DV)["only_ids"]["perf-ok"] == {"theme": "confirmed", "written": False})

    for bad, why in ((("nope",), "unknown id"), (("gpu-a", "gpu-a"), "repeated id")):
        try:
            rc.run(store, False, bad, DV)
            refused = False
        except SystemExit:
            refused = True
        check(f"G7 --only-id refuses {why}", refused)
    try:
        rc.run(store, False, ("gpu-a",), "")
        refused = False
    except SystemExit as exc:
        refused = "--product-id" in str(exc)
    check("G8 --only-id refuses to run without --product-id (an id alone is not an identity)", refused)

    rc.run(store, True, ("gpu-a", "gpu-b"), DV)
    after_rows = yaml.safe_load(store.read_text(encoding="utf-8"))["evidence"]
    unchanged = [r for r in after_rows if r["id"] not in ("gpu-a", "gpu-b") or r["product_id"] != DV]
    original = [r for r in rows if r["id"] not in ("gpu-a", "gpu-b") or r["product_id"] != DV]
    check("G9 --only-id --write changes exactly the named rows: every other row parses back identical",
          unchanged == original)
    named_after = [r for r in after_rows if r["id"] in ("gpu-a", "gpu-b") and r["product_id"] == DV]
    check("G10 the written rows changed theme and area only; sentiment, counted, text, identity untouched",
          all(r["issue_theme"] == "unspecified issue" and r["workflow_area"] == "general DaVinci Resolve workflow"
              and r["sentiment"] == "negative" and r["counted"] is True and r["severity"] == "medium"
              and r["platform"] == "unknown" for r in named_after)
          and [{k: v for k, v in r.items() if k not in ("issue_theme", "workflow_area")} for r in named_after]
          == [{k: v for k, v in r.items() if k not in ("issue_theme", "workflow_area")} for r in rows[:2]])
    check("G11 a second --only-id run changes nothing",
          rc.run(store, False, ("gpu-a", "gpu-b"), DV)["rows_changed"] == 0)
    check("G12 the same id on another product is not touched (identity is product + id)",
          [r for r in after_rows if r["product_id"] == "obs-studio"] == [obs_same])
    cli = subprocess.run([sys.executable, str(SCRIPTS / "recompute_evidence_classification.py"), "--store", str(store),
                          "--only-id", "gpu-a"], capture_output=True, text=True)
    check("G13 the CLI refuses --only-id without --product-id and does not write",
          cli.returncode != 0 and yaml.safe_load(store.read_text(encoding="utf-8"))["evidence"] == after_rows,
          cli.stderr[-120:])

    if FAILURES:
        print("Failed: " + ", ".join(FAILURES))
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run_suite())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
