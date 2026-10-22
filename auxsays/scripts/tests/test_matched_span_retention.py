#!/usr/bin/env python3
"""A counted evidence row must carry the evidence for its own version match.

Stored excerpts are truncated -- Reddit DaVinci rows are cut at 280 characters, 261 of 319 at the
cap -- so an `exact_version_text` claim could not be audited after the fact. Two rows from one post
shared an identical truncated prefix and were counted against two different versions; nothing on
disk showed which occurrence had established either match, so the question of whether they were
right was unanswerable rather than merely unanswered.

The matcher now reports the span it ACCEPTED, and the row keeps that occurrence, the field it came
from and a bounded window around it. Nothing is searched a second time: a second search could land
on a different occurrence than the one that decided the match.

Forward-only. Existing rows are untouched: the fields are optional and appended last, and empty
optional fields are dropped by the normaliser, so no stored row gains, loses or reorders a key.

Offline: no network, no repo writes.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from patch_collectors import base                               # noqa: E402
from patch_collectors import davinci as dv                      # noqa: E402

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
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))


def run_suite() -> int:
    print("=" * 92)
    print("PART A  one predicate, now reporting where it matched")
    print("=" * 92)

    for text, ver in (("we are on 26.001.21745.", "26.001.21745"),
                      ("v25.001.21111 broke printing", "25.001.21111"),
                      ("dev25.001.21111 is a branch", "25.001.21111"),
                      ("nothing relevant here", "26.2")):
        a = base.exact_version_match(text, ver)
        s = base.exact_version_match_span(text, ver)
        check(f"Part A: the span view agrees with the original on {text[:26]!r}",
              a == s[:3], f"{a} vs {s[:3]}")

    text = "Upgraded yesterday. Now on 20.3.2 and it crashes."
    ok, mv, _b, start, end = base.exact_version_match_span(text, "20.3.2")
    check("Part A: the span covers exactly the accepted occurrence",
          ok and text[start:end] == "20.3.2", f"{text[start:end]!r}")

    # A REJECTED occurrence precedes the accepted one. The span must point at the accepted one --
    # which is why the provenance comes from the matcher and is never re-derived by searching.
    tricky = "branch dev20.3.2 is unrelated; I am on 20.3.2 now"
    ok, _mv, _b, start, end = base.exact_version_match_span(tricky, "20.3.2")
    check("Part A: the span is the ACCEPTED occurrence, not the first textual one",
          ok and start == tricky.index("on 20.3.2") + 3, f"start={start}")

    print()
    print("=" * 92)
    print("PART B  provenance: the occurrence, its field, a bounded window")
    print("=" * 92)

    parts = [("parent_title", "Resolve crashing"),
             ("report_title", "Resolve crashing"),
             ("report_text", "Since this morning DaVinci Resolve 20.3.2 freezes on launch.")]
    joined = " ".join(v for _n, v in parts)
    ok, _mv, _b, start, end = base.exact_version_match_span(joined, "20.3.2")
    prov = base.match_provenance(parts, start, end)
    check("Part B: the matched text is the accepted occurrence",
          prov.get("matched_text") == "20.3.2", str(prov))
    check("Part B: and its field is attributed correctly",
          prov.get("matched_field") == "report_text", str(prov))

    titled = [("parent_title", "Resolve 20.3.2 crash"), ("report_title", ""),
              ("report_text", "it just dies")]
    j2 = " ".join(v for _n, v in titled)
    _ok, _mv, _b, s2, e2 = base.exact_version_match_span(j2, "20.3.2")
    check("Part B: a match in the title is attributed to the title",
          base.match_provenance(titled, s2, e2).get("matched_field") == "parent_title")

    # THE POINT OF THE CHANGE: a match beyond the excerpt cut survives in the row.
    long_body = ("I have been using Resolve for years without trouble. " * 8) + "Now on 20.3.2 it crashes."
    long_parts = [("parent_title", "Crash"), ("report_title", "Crash"), ("report_text", long_body)]
    lj = " ".join(v for _n, v in long_parts)
    _ok, _mv, _b, ls, le = base.exact_version_match_span(lj, "20.3.2")
    lprov = base.match_provenance(long_parts, ls, le)
    check("Part B: the version is ABSENT from the truncated excerpt",
          "20.3.2" not in base.excerpt(long_body))
    check("Part B: but present in the retained context",
          "20.3.2" in lprov.get("matched_context", ""))
    bound = 2 * base.MATCH_CONTEXT_CHARS + len("20.3.2") + 6
    check("Part B: and the context is bounded, an audit aid not a copy of the post",
          len(lprov.get("matched_context", "")) <= bound,
          f"len={len(lprov.get('matched_context', ''))} bound={bound}")
    check("Part B: no match means no provenance",
          base.match_provenance(parts, -1, -1) == {})

    print()
    print("=" * 92)
    print("PART C  the DaVinci producer keeps it; existing rows are untouched")
    print("=" * 92)

    record = base.PatchRecord(product_id="blackmagic-davinci", update_version="20.3.2",
                              path=Path("x.md"), update_published_at="2026-02-01",
                              update_status="stable", update_product="DaVinci Resolve")
    cand = {"source_url": "https://www.reddit.com/r/davinciresolve/comments/abc/crash",
            "source_type": "reddit_community_report", "parent_title": "Resolve crash",
            "report_title": "Resolve crash", "source_date": "2026-02-10",
            "report_text": long_body}
    row = dv.row_from_candidate(record, cand, "2026-10-22T00:00:00Z")
    check("Part C: a matched DaVinci row retains the accepted occurrence",
          row.get("matched_text") == "20.3.2", str(row.get("matched_text")))
    check("Part C: with its field",
          row.get("matched_field") == "report_text", str(row.get("matched_field")))
    check("Part C: and a context that substantiates it although the excerpt cannot",
          "20.3.2" in str(row.get("matched_context") or "")
          and "20.3.2" not in str(row.get("report_text_excerpt") or ""))

    unmatched = dict(cand, report_text="Resolve keeps crashing, no version given.",
                     parent_title="crash", report_title="crash")
    urow = dv.row_from_candidate(record, unmatched, "2026-10-22T00:00:00Z")
    check("Part C: an unmatched row carries no provenance at all",
          not any(k in urow for k in ("matched_text", "matched_field", "matched_context")),
          str([k for k in ("matched_text", "matched_field", "matched_context") if k in urow]))

    # A REAL stored row, round-tripped through the normaliser: it must come back with exactly the
    # keys it went in with, so re-serialising the store cannot churn every existing row.
    import yaml  # noqa: PLC0415
    stored = yaml.load((ROOT / "_data" / "consensus_evidence.yml").read_text(encoding="utf-8"),
                       Loader=yaml.SafeLoader)["evidence"]
    sample = next(r for r in stored if r.get("product_id") == "blackmagic-davinci")
    normalized = base.normalize_evidence_row(dict(sample))
    check("Part C: a stored row written before this gains none of the new keys",
          not any(k in normalized for k in ("matched_text", "matched_field", "matched_context")))
    # Subset, not equality: the normaliser already drops EMPTY optional fields (a stored row with null
    # dates loses those keys on any round-trip, before and after this change alike). What this change
    # must not do is ADD a key, which would churn every existing row on the next re-serialisation.
    check("Part C: and the normaliser adds no key to it",
          set(normalized) <= set(sample), str(set(normalized) - set(sample)))
    check("Part C: the new fields are optional and appended last in the schema",
          base.EVIDENCE_FIELDS[-3:] == ("matched_text", "matched_field", "matched_context")
          and {"matched_text", "matched_field", "matched_context"} <= base.OPTIONAL_EVIDENCE_FIELDS)

    print()
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
