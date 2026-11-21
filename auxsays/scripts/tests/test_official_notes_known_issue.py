"""A known issue the vendor declares in its GitHub release notes reaches the patch page (AUX-125, G85).

WHAT WAS WRONG. OBS edited its 33.0.2 release notes after publication to open with a GitHub IMPORTANT
alert declaring a known startup crash on certain older processors. Official ingestion re-read the
release and stored the edited body (9687ad0c), so detection worked. Nothing turned the stored notice
into anything a reader sees: the Vendor Known Issues card said AUXSAYS had captured no vendor issue
data, and the notice sat inside the collapsed release notes as raw Markdown.

WHAT IS PINNED HERE.
  [P] the parser: an explicit known-issue declaration only (alert markup alone is not one), scoped to
      the release being assessed, ambiguous attribution = unknown, which publishes nothing;
  [W] the regression the owner asked for, end to end through patch_ingest.run_source and the real
      GitHub adapter (listing stubbed, no network): a release captured clean, then edited to add a
      known-issue notice, then edited to remove it -- the body refreshes, the field is set and then
      removed, and the rendered card follows each step; an unchanged body adds no churn; a refused
      body keeps the field; and the documented refresh window is what the code actually does;
  [C] Release Health semantics are untouched: no issue count, no known_issues_present, nothing new on
      a Windows record, and the field is derived, never taken from the caller;
  [R] rendering through the shipped Liquid: Release Health and absent-field cards byte-identical to
      the pre-AUX-125 card, the declared card, and the notice directly under the verdict;
  [M] the migration: zero network, only demonstrated changes, one line each, idempotent, refuses what
      it cannot do exactly, and the committed corpus has nothing left to migrate;
  [B] the new import resolves when patch_ingest and the migration run as bare scripts.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_official_notes_known_issue.py
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
_SCRIPTS = _AUX / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import yaml  # noqa: E402

import migrate_official_notes_known_issue as migration  # noqa: E402
import patch_ingest  # noqa: E402
from adapters import github_releases  # noqa: E402
from lib import notes_known_issue as nki  # noqa: E402
from lib import write_update_record as writer  # noqa: E402

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print("  PASS  " + label)
    else:
        _FAIL += 1
        print("  FAIL  " + label)
        if detail:
            print("        " + str(detail)[:600])
        _ERRORS.append(label)


FIXTURES = _SCRIPTS / "tests" / "fixtures" / "notes_known_issue"
FROZEN = json.loads((FIXTURES / "obs_studio_33_0_2_stored_body.json").read_text(encoding="utf-8"))
PRE_CARD = FIXTURES / "aux-vendor-known-issues.pre-aux125.html"
LAYOUT_PATH = _AUX / "_layouts" / "aux-update.html"
INCLUDES = _AUX / "_includes"
RECORDS = _AUX / "updates" / "generated"
SOURCES = _AUX / "_data" / "patch_ingestion_sources.yml"

WARNING_SENTENCES = ("The official release notes for this version identify a known issue. "
                     "Review the details before installing.")
ABSENT_TEXT = ("AUXSAYS has not captured official issue data for this patch. This does not indicate "
               "the vendor has no issues.")

# Synthetic release notes in the OBS shape (setext release headings, newest first, CRLF). Invented
# text: no vendor wording is reproduced here.
HOTFIX = ("9.1.2 Hotfix Changes\r\n--------------------\r\n\r\n* Fixed a crash when closing a dialog (#101)\r\n"
          "* Fixed a typo in a menu (#102)\r\n\r\n9.1.1 Hotfix Changes\r\n--------------------\r\n\r\n"
          "* Fixed audio drift in long recordings (#100)\r\n\r\n9.1 New Features\r\n----------------\r\n\r\n"
          "* Added a new transition (#90)")
NOTICE = ("> [!IMPORTANT]\r\n> There is a known issue with 9.1.2 where the app can fail to start on some "
          "systems. If you are affected, use 9.1.1 until a fix ships.\r\n\r\n")


def assess(body: str, version: str = "9.1.2") -> nki.Assessment:
    return nki.assess(body, version)


# The frozen 33.0.2 fixture keeps the vendor's STRUCTURE, not its text: every letter-word the parser does
# not read becomes x's of the same length, while line breaks, Markdown markers, punctuation, digits and
# versions are kept. P0 proves the parser reads the skeleton exactly as it reads the real stored body.
_MASK_KEEP = frozenset({
    "known", "issue", "issues", "there", "is", "are", "exist", "exists", "remain", "remains", "s",
    "currently", "still", "also", "now", "a", "an", "one", "two", "three", "four", "five", "six", "seven",
    "eight", "nine", "ten", "several", "multiple", "some", "no", "any", "none", "n", "na",
    "note", "important", "warning", "caution", "tip"})


def mask_body(text: str) -> str:
    def word(m: re.Match) -> str:
        w = m.group(0)
        if w.lower() in _MASK_KEEP or (w in ("v", "V") and text[m.end():m.end() + 1].isdigit()):
            return w
        return "x" * len(w)
    return re.sub(r"[A-Za-z]+", word, text)


# --------------------------------------------------------------------------------------------
def section_p_parser() -> None:
    print("\n[P] the parser: explicit declaration only, scoped to the release, ambiguous = unknown")
    skeleton = FROZEN["masked_body"]
    record = RECORDS / FROZEN["record"].rsplit("/", 1)[-1]
    stored = str((front_of(record) if record.exists() else {}).get("official_patch_notes_body") or "")
    pinned = hashlib.sha256(stored.encode("utf-8")).hexdigest() == FROZEN["sha256"]
    leftover = sorted({w for w in re.findall(r"[A-Za-z]+", skeleton)
                       if w.lower() not in _MASK_KEEP and set(w) != {"x"} and w not in ("v", "V")})
    check("P0 the frozen fixture is the masked structure of the body stored at 9687ad0c: no vendor words, and "
          "while the record stores that body the parser reads both alike",
          FROZEN["update_version"] == "33.0.2" and leftover == [] and len(skeleton) > 1000
          and (not pinned or (mask_body(stored) == skeleton
                              and nki.assess(stored, "33.0.2") == nki.assess(skeleton, "33.0.2")
                              and nki.assess(stored, "33.0.1") == nki.assess(skeleton, "33.0.1"))),
          f"pinned={pinned} leftover={leftover[:5]}")
    real = nki.assess(skeleton, "33.0.2")
    check("P1 the real stored OBS 33.0.2 body declares a known issue for 33.0.2",
          real.result == nki.DECLARED and "above the first release heading" in real.reason
          and "naming this version" in real.reason, real)
    moved = nki.assess(skeleton, "33.0.1")
    check("P2 the same body read for 33.0.1 does not transfer the notice (it names 33.0.2)",
          moved.result == nki.UNKNOWN, moved)

    generic = ("> [!IMPORTANT]\r\n> Version 9 requires graphics driver 570 or newer. If you see problems "
               "with hardware encoding, update your driver.\r\n\r\n> [!WARNING]\r\n> macOS 12 is no "
               "longer supported.\r\n\r\n> [!CAUTION]\r\n> Back up your profile before upgrading.\r\n\r\n"
               "> [!NOTE]\r\n> Some plugins need an update.\r\n\r\n")
    g = assess(generic + HOTFIX)
    check("P3 generic IMPORTANT/WARNING/CAUTION/NOTE alerts with no known-issue declaration -> not declared",
          g.result == nki.NOT_DECLARED and "4 alert(s)" in g.reason, g)

    older = HOTFIX.replace("* Fixed audio drift in long recordings (#100)",
                           "> [!IMPORTANT]\r\n> There is a known issue where the app can fail to start.\r\n\r\n"
                           "* Fixed audio drift in long recordings (#100)")
    o = assess(older)
    check("P4 a known-issue alert inside an older release's section is never this release's",
          o.result == nki.NOT_DECLARED and "another release" in o.reason, o)
    o_for_old = assess(older, "9.1.1")
    check("P5 ...and it IS the older release's own notice when that release is assessed",
          o_for_old.result == nki.DECLARED, o_for_old)

    unattributed = ("> [!WARNING]\r\n> There is a known issue where the app can fail to start.\r\n\r\n"
                    + "9.1.1 Hotfix Changes" + HOTFIX.split("9.1.1 Hotfix Changes", 1)[1])
    u = assess(unattributed, "9.1.2")
    check("P6 a version-less notice above a body whose first release heading is ANOTHER release -> unknown",
          u.result == nki.UNKNOWN and "first release heading is another version" in u.reason, u)
    other_named = assess("> [!NOTE]\r\n> There is a known issue with 9.1.1 on older processors.\r\n\r\n" + HOTFIX)
    check("P7 a notice whose declaring sentence names another version -> unknown, not declared",
          other_named.result == nki.UNKNOWN and "naming another version" in other_named.reason, other_named)
    both_named = assess("> [!NOTE]\r\n> There is a known issue with 9.1.2 and 9.1.1 on older processors.\r\n\r\n" + HOTFIX)
    check("P8 a declaring sentence naming this AND another version is ambiguous -> unknown",
          both_named.result == nki.UNKNOWN, both_named)
    versionless = assess("> [!CAUTION]\r\n> Known issue: the app can fail to start on some systems.\r\n\r\n" + HOTFIX)
    check("P9 a version-less known-issue alert above THIS release's heading -> declared",
          versionless.result == nki.DECLARED, versionless)

    ki_current = HOTFIX.replace("* Fixed a typo in a menu (#102)\r\n",
                                "* Fixed a typo in a menu (#102)\r\n\r\n### Known Issues\r\n\r\n"
                                "* The app can fail to start on some systems.\r\n")
    check("P10 a Known Issues section under this release's heading -> declared",
          assess(ki_current).result == nki.DECLARED, assess(ki_current))
    ki_older = HOTFIX.replace("* Fixed audio drift in long recordings (#100)\r\n",
                              "* Fixed audio drift in long recordings (#100)\r\n\r\n### Known Issues\r\n\r\n"
                              "* Exports can stall.\r\n")
    check("P11 a Known Issues section under an older release's heading -> not declared for this release",
          assess(ki_older).result == nki.NOT_DECLARED, assess(ki_older))
    ki_versioned = HOTFIX + "\r\n\r\n9.1.1 Known Issues\r\n------------------\r\n\r\n* Exports can stall.\r\n"
    check("P12 a heading that names another release's Known Issues -> not declared for this release",
          assess(ki_versioned).result == nki.NOT_DECLARED, assess(ki_versioned))
    flat = "## Changes\n\n* Faster startup\n\n## Known issues\n\n* Large models can run out of memory.\n"
    check("P13 a Known Issues section in a body with no release headings belongs to the release",
          nki.assess(flat, "0.44.0").result == nki.DECLARED, nki.assess(flat, "0.44.0"))
    empty_sections = ["## Known Issues\n\n* None\n", "## Known Issues\n\nN/A\n",
                      "## Known Issues\n\nThere are currently no known issues.\n", "## Known Issues\n"]
    check("P14 an empty, 'None', 'N/A' or no-known-issues section -> not declared",
          all(nki.assess(b, "0.44.0").result == nki.NOT_DECLARED for b in empty_sections),
          [nki.assess(b, "0.44.0") for b in empty_sections])

    negated = ["> [!NOTE]\r\n> There are no known issues in this release.\r\n\r\n",
               "> [!NOTE]\r\n> We are not aware of any known issues.\r\n\r\n",
               "> [!IMPORTANT]\r\n> If you hit any known issues, tell us.\r\n\r\n"]
    check("P15 'no known issues' / 'any known issues' is not a declaration",
          all(assess(b + HOTFIX).result == nki.NOT_DECLARED for b in negated),
          [assess(b + HOTFIX) for b in negated])
    tip = assess("> [!TIP]\r\n> There is a known issue with 9.1.2 on some systems.\r\n\r\n" + HOTFIX)
    check("P16 a TIP alert is advice, not a notice -> not declared", tip.result == nki.NOT_DECLARED, tip)
    fenced = assess("```\r\n> [!IMPORTANT]\r\n> There is a known issue with 9.1.2.\r\n```\r\n\r\n" + HOTFIX)
    check("P17 alert markup inside a code fence is quoted code -> not declared",
          fenced.result == nki.NOT_DECLARED, fenced)
    bullet = assess(HOTFIX.replace("* Fixed a typo in a menu (#102)",
                                   "* Blocked a plugin from loading due to known issues (#102)"))
    check("P18 a plain bullet that mentions known issues (no alert, no section) -> not declared",
          bullet.result == nki.NOT_DECLARED, bullet)
    dotzero = "> [!IMPORTANT]\r\n> Known issue: exports can stall.\r\n\r\n9.1 New Features\r\n----------------\r\n\r\n* X\r\n"
    check("P19 a '9.1' heading is the 9.1.0 release (trailing zeros), and not 9.1.2",
          nki.assess(dotzero, "9.1.0").result == nki.DECLARED
          and nki.assess(dotzero, "9.1.2").result == nki.UNKNOWN,
          [nki.assess(dotzero, "9.1.0"), nki.assess(dotzero, "9.1.2")])
    check("P20 no body -> not declared; field_value is 'declared' or None only",
          nki.assess("", "9.1.2").result == nki.NOT_DECLARED
          and nki.field_value(NOTICE + HOTFIX, "9.1.2") == "declared"
          and nki.field_value(HOTFIX, "9.1.2") is None
          and nki.field_value(unattributed, "9.1.2") is None)

    bold = ("**9.1.3 Hotfix Changes**\n\n* Fixed a crash (#103)\n\n**9.1.2 Hotfix Changes**\n\n"
            "> [!IMPORTANT]\n> There is a known issue where the app can fail to start.\n\n* Fixed audio drift (#100)\n")
    plain = bold.replace("**", "")
    top = ("**9.1.3 Hotfix Changes**\n\n> [!IMPORTANT]\n> There is a known issue where the app can fail to start.\n\n"
           "* Fixed a crash (#103)\n\n**9.1.2 Hotfix Changes**\n\n* Fixed audio drift (#100)\n")
    check("P21 no Markdown release headings: a notice after a line naming an older release is unknown, never "
          "this release's; one above any such line is still this release's",
          all(nki.assess(b, "9.1.3").result == nki.UNKNOWN for b in (bold, plain))
          and nki.assess(top, "9.1.3").result == nki.DECLARED,
          [nki.assess(b, "9.1.3") for b in (bold, plain, top)])
    pointers = ["> [!IMPORTANT]\r\n> Read the installation guide before upgrading. Check the known issues page "
                "before reporting a bug.\r\n\r\n",
                "> [!NOTE]\r\n> For a list of known issues, see the wiki.\r\n\r\n",
                "> [!WARNING]\r\n> Install the 2025 runtime first; the known issues with older runtimes are "
                "listed in the FAQ.\r\n\r\n"]
    labels = ["> [!CAUTION]\r\n> **Known issue:** the app can fail to start on some systems.\r\n\r\n",
              "> [!WARNING]\r\n> Two known issues affect some systems.\r\n\r\n",
              "> [!IMPORTANT]\r\n> There are known issues with older processors.\r\n\r\n"]
    check("P22 an install/prerequisite alert that only REFERS to known issues is generic -> not declared; "
          "a label or an introduced known issue still declares",
          all(assess(b + HOTFIX).result == nki.NOT_DECLARED for b in pointers)
          and all(assess(b + HOTFIX).result == nki.DECLARED for b in labels),
          [assess(b + HOTFIX) for b in pointers + labels])

    conditional = ["> [!IMPORTANT]\r\n> Please read the installation guide before upgrading. If you run into a known "
                   "issue, check the FAQ before opening a bug report.\r\n\r\n",
                   "> [!NOTE]\r\n> Before reporting a crash after installing, check whether it is a known issue.\r\n\r\n",
                   "> [!WARNING]\r\n> Before installing, check whether your GPU is affected by a known issue listed "
                   "on our wiki.\r\n\r\n",
                   "> [!NOTE]\r\n> If your plugin has a known issue, contact its author.\r\n\r\n",
                   "> [!IMPORTANT]\r\n> Check whether there is a known issue for your GPU before installing.\r\n\r\n",
                   "> [!NOTE]\r\n> Known issues: none.\r\n\r\n",
                   "> [!NOTE]\r\n> There was a known issue with exports that is now resolved.\r\n\r\n"]
    opening = ["> [!WARNING]\r\n> Note: there is a known issue where exports can stall.\r\n\r\n",
               "> [!CAUTION]\r\n> A known issue can stop the app from starting on some systems.\r\n\r\n",
               "> [!IMPORTANT]\r\n> There's currently a known issue with older processors.\r\n\r\n",
               "> [!WARNING]\r\n> Known Issues:\r\n> - exports can stall\r\n\r\n"]
    check("P23 an installation or prerequisite alert that mentions 'a known issue' only as a condition, a "
          "question, an empty label or a fixed past issue is generic -> not declared; a clause that OPENS by "
          "introducing a known issue declares",
          all(assess(b + HOTFIX).result == nki.NOT_DECLARED for b in conditional)
          and all(assess(b + HOTFIX).result == nki.DECLARED for b in opening),
          [assess(b + HOTFIX) for b in conditional + opening])

    notice = "> [!IMPORTANT]\n> There is a known issue where the app can fail to start.\n\n"
    mixed = ["9.1.3 Hotfix Changes\n--------------------\n\n* Fixed a crash (#103)\n\n**9.1.2 Hotfix Changes**\n\n"
             + notice + "* Fixed audio drift (#100)\n",
             "## 9.1.3\n\n* Fixed a crash (#103)\n\n9.1.2 Hotfix Changes:\n\n" + notice + "* Fixed audio drift (#100)\n",
             "## 9.1.3\n\n* Fixed a crash (#103)\n\n<h2>9.1.2</h2>\n\n" + notice + "* Fixed audio drift (#100)\n"]
    own = ["## 9.1.3\n\n" + notice + "* Fixed a crash (#103)\n\n**9.1.2 Hotfix Changes**\n\n* Fixed audio drift (#100)\n",
           "Upgrading from 9.1.2? Read the guide first.\n\n## 9.1.3\n\n" + notice + "* Fixed a crash (#103)\n",
           "## 9.1.3\n\n* Fixed a regression from 9.1.2 (#104)\n\n" + notice]
    check("P24 a notice after a plain, bold or HTML line naming an older release, inside this release's own "
          "headed section, is unknown, never this release's; one before any such line, after this release's "
          "own heading starts its section again, or after a list item that names an older release, is still "
          "this release's",
          all(nki.assess(b, "9.1.3").result == nki.UNKNOWN for b in mixed)
          and all(nki.assess(b, "9.1.3").result == nki.DECLARED for b in own),
          [nki.assess(b, "9.1.3") for b in mixed + own])


# --------------------------------------------------------------------------------------------
def obs_source() -> dict:
    sources = yaml.safe_load(SOURCES.read_text(encoding="utf-8")) or []
    return next(s for s in sources if isinstance(s, dict) and s.get("product_id") == "obs-studio")


def release(version: str, body: str, rid: int, published: str) -> dict:
    return {
        "id": rid, "tag_name": version, "name": version, "draft": False, "prerelease": False,
        "body": body + "\r\n\r\n## Checksums\r\n\r\nabc123  OBS-Studio-" + version + ".zip",
        "html_url": f"https://github.com/obsproject/obs-studio/releases/tag/{version}",
        "published_at": published, "created_at": published,
        "assets": [{"name": f"OBS-Studio-{version}-Windows-x64-Installer.exe", "size": 194000000,
                    "browser_download_url": f"https://github.com/obsproject/obs-studio/releases/download/{version}/x.exe"}],
    }


class Clock:
    def __init__(self) -> None:
        self.n = 0

    def __call__(self) -> str:
        self.n += 1
        return f"2026-11-21T{10 + self.n // 60:02d}:{self.n % 60:02d}:00Z"


def run_ingest(listing: list, state: dict, out: Path, clock: Clock) -> dict:
    original_fetch, original_now = github_releases.fetch_json, patch_ingest.utc_now
    try:
        github_releases.fetch_json = lambda url: listing
        patch_ingest.utc_now = clock
        args = SimpleNamespace(limit=2, output=out, overwrite_existing=False, updates_dir=out.parent / "updates")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return patch_ingest.run_source(obs_source(), args, state)
    finally:
        github_releases.fetch_json, patch_ingest.utc_now = original_fetch, original_now


def front_of(path: Path) -> dict:
    front, _ = writer._front_matter(path)
    return front


def section_w_regression() -> None:
    print("\n[W] a release whose notes acquire, then lose, a known-issue notice after publication")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "generated"
        out.mkdir()
        state: dict = {"schema_version": 1, "sources": {}}
        clock = Clock()
        pub = "2026-11-20T15:00:26Z"
        run_ingest([release("9.1.2", HOTFIX, 912, pub)], state, out, clock)
        files = sorted(out.glob("*.md"))
        path = files[0] if files else out / "missing.md"
        f1 = front_of(path) if files else {}
        check("W1 first capture (no notice): one record, body stored, field absent",
              len(files) == 1 and "9.1.2 Hotfix Changes" in str(f1.get("official_patch_notes_body"))
              and nki.FIELD not in f1, str(sorted(f1))[:300])
        card1 = render_card(f1)

        result = run_ingest([release("9.1.2", NOTICE + HOTFIX, 912, pub)], state, out, clock)
        f2 = front_of(path)
        check("W2 notes edited to ADD a known-issue notice: the refresh stores the edited body",
              "> [!IMPORTANT]" in str(f2.get("official_patch_notes_body"))
              and [r.get("action") for r in result.get("refreshed", [])] == ["refreshed"],
              json.dumps(result.get("refreshed"))[:300])
        check("W3 ...and sets official_notes_known_issue: declared, advancing record_last_updated",
              f2.get(nki.FIELD) == "declared"
              and f2.get("record_last_updated") != f1.get("record_last_updated"),
              f"{f2.get(nki.FIELD)!r} {f1.get('record_last_updated')} -> {f2.get('record_last_updated')}")
        card2 = render_card(f2)

        result3 = run_ingest([release("9.1.2", NOTICE + HOTFIX, 912, pub)], state, out, clock)
        f3 = front_of(path)
        changed = sorted(k for k in set(f2) | set(f3) if f2.get(k) != f3.get(k))
        check("W4 an UNCHANGED body adds no churn: field kept, record_last_updated kept, only freshness moves",
              f3.get(nki.FIELD) == "declared" and f3.get("record_last_updated") == f2.get("record_last_updated")
              and set(changed) <= {"source_last_checked", "official_body_last_checked", "official_source_attempts"}
              and [r.get("action") for r in result3.get("refreshed", [])] == ["freshness-updated"],
              f"changed={changed} actions={[r.get('action') for r in result3.get('refreshed', [])]}")

        run_ingest([release("9.1.2", "", 912, pub)], state, out, clock)
        f4 = front_of(path)
        check("W5 a capture whose body the writer refuses (GitHub returned none) keeps the stored notice and field",
              f4.get(nki.FIELD) == "declared" and "> [!IMPORTANT]" in str(f4.get("official_patch_notes_body")),
              repr(f4.get(nki.FIELD)))

        run_ingest([release("9.1.2", HOTFIX, 912, pub)], state, out, clock)
        f5 = front_of(path)
        check("W6 notes edited to REMOVE the notice: body refreshed and the field removed",
              nki.FIELD not in f5 and "> [!IMPORTANT]" not in str(f5.get("official_patch_notes_body"))
              and f5.get("record_last_updated") != f4.get("record_last_updated"), str(sorted(f5))[:300])
        card5 = render_card(f5)
        if None in (card1, card2, card5):
            check("W7 could not render: ruby/liquid unavailable", False,
                  "install ruby and the liquid gem (CI pins liquid 4.0.4)")
            check("W8 could not render: ruby/liquid unavailable", False)
        else:
            check("W7 the rendered card follows: absent text -> vendor warning (open) -> absent text again",
                  ABSENT_TEXT in card1 and "Vendor warning identified." not in card1
                  and WARNING_SENTENCES in card2 and " open aria-label=" in card2
                  and card5 == card1, f"{card1[:160]!r} | {card2[:160]!r}")
            check("W8 the warning card links the official release notes and prints no count",
                  'href="https://github.com/obsproject/obs-studio/releases/tag/9.1.2">Official release notes' in card2
                  and re.search(r"<summary>[^<]*\d", card2) is None, card2[:400])

    print("\n[W] the effective refresh window (GPT Q4, documented, not widened)")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "generated"
        out.mkdir()
        state = {"schema_version": 1, "sources": {}}
        clock = Clock()
        src = obs_source()
        ingestion = src.get("ingestion") or {}
        check("W9 the OBS source sets no record_limit/scan_limit, so per-run refresh = --limit (2)",
              "record_limit" not in ingestion and "scan_limit" not in ingestion
              and patch_ingest.resolve_record_limit(src, SimpleNamespace(limit=2)) == 2)
        listing = [release("9.1.2", HOTFIX, 912, "2026-11-20T15:00:00Z"),
                   release("9.1.1", "9.1.1 Hotfix Changes\r\n---\r\n\r\n* A\r\n", 911, "2026-11-10T15:00:00Z"),
                   release("9.1.0", "9.1 New Features\r\n---\r\n\r\n* B\r\n", 910, "2026-11-01T15:00:00Z")]
        for _ in range(3):
            run_ingest(listing, state, out, clock)
        edited = list(listing)
        edited[2] = release("9.1.0", "> [!IMPORTANT]\r\n> Known issue: exports can stall.\r\n\r\n"
                            "9.1 New Features\r\n---\r\n\r\n* B\r\n", 910, "2026-11-01T15:00:00Z")
        res = run_ingest(edited, state, out, clock)
        oldest = next((p for p in out.glob("*9-1-0.md")), None)
        skipped = [s.get("reason") for s in res.get("skipped", [])]
        check("W10 a later edit to the THIRD-newest ingested release is not re-read (the documented gap)",
              oldest is not None and nki.FIELD not in front_of(oldest)
              and "state-seen-outside-refresh-window" in skipped, f"skipped={skipped}")


# --------------------------------------------------------------------------------------------
def github_record(body: str, version: str = "9.1.2", **extra) -> dict:
    rec = {
        "record_id": f"github:obs-studio:{version}", "company_id": "obs-project", "product_id": "obs-studio",
        "company": "OBS Project", "software": "OBS Studio", "category": "Streaming", "version": version,
        "title": version, "published_at": "2026-11-20T15:00:26Z",
        "source_url": f"https://github.com/obsproject/obs-studio/releases/tag/{version}",
        "official_url": "https://github.com/obsproject/obs-studio/releases", "download_url": "",
        "file_size": "", "file_size_note": "", "body": body, "checksums_body": "", "summary": "",
        "source_type": "github-release", "capture_status": "captured-from-github-release-body",
        "source_last_checked": "2026-11-20T23:12:10Z",
    }
    rec.update(extra)
    return rec


def windows_record(**extra) -> dict:
    rec = {
        "record_id": "windows:25h2:26200.9999", "company_id": "microsoft",
        "product_id": "microsoft-windows-11", "company": "Microsoft", "software": "Windows 11",
        "category": "Operating System", "version": "25H2", "title": "Windows 11 25H2",
        "published_at": "2026-11-11T18:00:00Z", "target_build": "26200.9999",
        "target_os_build": "26200.9999", "target_kb": "KB5099999", "target_feature_version": "25H2",
        "source_url": "https://example.test/release-health", "official_url": "https://example.test/release-health",
        # A body the parser WOULD read as declaring (a Known Issues section in a body with no release
        # headings), so only the GitHub-release scope keeps the field off this record.
        "body": "> [!IMPORTANT]\n> There is a known issue with 25H2 on some devices.\n\n## Known issues\n\n"
                "* Some devices can fail to install this update.\n",
        "source_type": "release_health", "official_source_type": "release_health",
        "official_known_issues_present": True, "official_active_issue_count": 2,
        "official_resolved_issue_count": 1, "official_safeguard_hold_count": 0,
        "source_last_checked": "2026-11-20T00:00:00Z",
    }
    rec.update(extra)
    return rec


def section_c_contract() -> None:
    print("\n[C] Release Health semantics, the user-report field and the caller are left alone")
    check("C1 OFFICIAL_ISSUE_FIELDS is exactly the four Release Health fields (no notice field added)",
          writer.OFFICIAL_ISSUE_FIELDS == ("official_known_issues_present", "official_active_issue_count",
                                           "official_resolved_issue_count", "official_safeguard_hold_count")
          and nki.FIELD not in writer.OFFICIAL_ISSUE_FIELDS)
    declared = writer.build_front_matter(github_record(NOTICE + HOTFIX))
    check("C2 a declared GitHub record carries the field and NO issue count, Release Health field or user-report flag",
          declared.get(nki.FIELD) == "declared"
          and not any(f in declared for f in writer.OFFICIAL_ISSUE_FIELDS)
          and declared.get("known_issues_present") is None, str({k: declared.get(k) for k in
                                                                 ("known_issues_present", nki.FIELD)}))
    check("C3 the field is derived from the body, never taken from the caller",
          nki.FIELD not in writer.build_front_matter(github_record(HOTFIX, **{nki.FIELD: "declared"})))
    win = writer.build_front_matter(windows_record())
    check("C4 a Windows Release Health record gets no notice field, though the parser alone would read its body as declaring",
          nki.FIELD not in win and win.get("official_active_issue_count") == 2
          and win.get("official_known_issues_present") is True
          and nki.assess(win.get("official_patch_notes_body"), "25H2").result == nki.DECLARED)
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        path, _ = writer.write_record(out, windows_record())
        before = path.read_bytes()
        writer.write_record(out, windows_record(source_last_checked="2026-11-20T00:00:00Z"))
        after_front = front_of(path)
        check("C5 refreshing a Windows record never adds the field; its issue counts are what the adapter wrote",
              nki.FIELD not in after_front and after_front.get("official_active_issue_count") == 2
              and b"official_notes_known_issue" not in before, str(sorted(after_front))[:200])


# --------------------------------------------------------------------------------------------
_RENDER_RB = r"""
require 'liquid'
require 'json'

class JekyllInclude < Liquid::Tag
  SYNTAX = /([\w.\/-]+)((\s+\w+\s*=\s*(?:"[^"]*"|'[^']*'|[\w.\[\]\/-]+))*)/
  def initialize(name, markup, tokens)
    super
    m = markup.strip.match(SYNTAX) or raise Liquid::SyntaxError, "bad include: #{markup}"
    @file = m[1]
    @params = {}
    (m[2] || "").scan(/(\w+)\s*=\s*("[^"]*"|'[^']*'|[\w.\[\]\/-]+)/) { |k, v| @params[k] = v }
  end
  def render(context)
    path = File.join(context.registers[:include_root], @file)
    raise Liquid::FileSystemError, "missing include #{@file}" unless File.exist?(path)
    vals = {}
    @params.each do |k, v|
      vals[k] = (v =~ /\A"(.*)"\z/m || v =~ /\A'(.*)'\z/m) ? $1 : context[v]
    end
    partial = Liquid::Template.parse(File.read(path, encoding: "utf-8"))
    context.stack { context["include"] = vals; partial.render!(context) }
  end
end
Liquid::Template.register_tag("include", JekyllInclude)

module Shims
  def relative_url(i) = "/" + i.to_s.sub(%r{\A/}, "")
  def absolute_url(i) = "https://auxsays.test/" + i.to_s.sub(%r{\A/}, "")
  def jsonify(i) = JSON.generate(i)
  def markdownify(i) = i.to_s
  def where(input, property, value)
    input = input.values if input.is_a?(Hash)
    return input unless input.respond_to?(:select)
    input.select { |item| item.is_a?(Hash) && item[property].to_s == value.to_s }
  end
end
Liquid::Template.register_filter(Shims)

payload = JSON.parse(File.read(ARGV[0], encoding: "utf-8"))
out = payload["cases"].map do |c|
  begin
    Liquid::Template.parse(c["template"]).render!({ "site" => c["site"], "page" => c["page"] },
                                                  registers: { include_root: c["includes"] })
  rescue => e
    "RENDER-ERROR #{e.class}: #{e.message}"
  end
end
print JSON.generate(out)
"""

_LAYOUT = LAYOUT_PATH.read_text(encoding="utf-8")
_CARD_START = _LAYOUT.find("{% assign official_active = ")
_CARD_END = _LAYOUT.find("\n", _LAYOUT.find("{% include aux-vendor-known-issues.html")) + 1
# The real assigns and include call the patch layout uses for the card, sliced from the shipped file.
CARD_CALL = _LAYOUT[_CARD_START:_CARD_END] if _CARD_START >= 0 else ""
_HERO_START = _LAYOUT.find("      {%- comment -%}\n        VENDOR WARNING (AUX-125)")
_HERO_END = _LAYOUT.find("      {%- endif %}\n", _HERO_START) + len("      {%- endif %}\n") if _HERO_START >= 0 else -1
HERO_BLOCK = _LAYOUT[_HERO_START:_HERO_END] if _HERO_START >= 0 and _HERO_END > _HERO_START else ""
SITE = {"title": "AUXSAYS", "time": "2026-11-21T00:00:00Z", "pages": [],
        "data": {"evidence_method_health": {"methods": []}}}


def render_many(cases: list[dict]) -> list[str] | None:
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "r.rb").write_text(_RENDER_RB, encoding="utf-8")
        (Path(td) / "p.json").write_text(json.dumps({"cases": cases}, default=str), encoding="utf-8")
        out = subprocess.run([ruby, str(Path(td) / "r.rb"), str(Path(td) / "p.json")],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    if out.returncode != 0:
        return [f"RENDER-ERROR {out.stderr[-300:]}"] * len(cases)
    return json.loads(out.stdout)


def render_card(page: dict, includes: Path = INCLUDES) -> str | None:
    rendered = render_many([{"template": CARD_CALL, "page": page, "site": SITE, "includes": str(includes)}])
    return None if rendered is None else rendered[0]


def _layout_body(text: str) -> str:
    body = text.split("---", 2)[-1]
    return re.sub(r"\{%-?\s*include\s.*?-?%\}", "", body, flags=re.S)


def rh_pages() -> list[dict]:
    base = {"product_id": "windows-11", "official_source_type": "release_health",
            "update_source_url": "https://example.test/release-health"}
    shapes = [
        {"official_known_issues_present": True, "official_active_issue_count": 2,
         "official_resolved_issue_count": 1, "official_safeguard_hold_count": 0},
        {"official_known_issues_present": True, "official_active_issue_count": 0,
         "official_resolved_issue_count": 3, "official_safeguard_hold_count": 1},
        {"official_known_issues_present": False, "official_active_issue_count": 0,
         "official_resolved_issue_count": 0, "official_safeguard_hold_count": 0},
        {"official_known_issues_present": True, "official_active_issue_count": 1,
         "official_resolved_issue_count": 0, "official_safeguard_hold_count": 2},
        {"official_known_issues_present": False, "official_active_issue_count": 0,
         "official_resolved_issue_count": 4, "official_safeguard_hold_count": 0},
    ]
    pages = [dict(base, **s) for s in shapes]
    # The same Release Health pages carrying the notes field: Release Health still decides.
    return pages + [dict(p, **{nki.FIELD: "declared"}) for p in pages]


def section_r_render() -> None:
    print("\n[R] the shipped Liquid: Release Health and absent text byte-identical, the warning when declared")
    check("R0 the card call sliced from the layout passes the record's field to the card",
          "notes_notice=page.official_notes_known_issue" in CARD_CALL and "has_data=vki_has_data" in CARD_CALL)
    with tempfile.TemporaryDirectory() as td:
        old = Path(td) / "old"
        old.mkdir()
        shutil.copy(PRE_CARD, old / "aux-vendor-known-issues.html")
        github_absent = {"product_id": "obs-studio", "official_source_type": "github-release",
                         "update_source_url": "https://github.com/obsproject/obs-studio/releases/tag/9.1.2"}
        github_declared = dict(github_absent, **{nki.FIELD: "declared"})
        product_call = ("{% include aux-vendor-known-issues.html active=page.a resolved=page.r safeguard=page.s "
                        "has_data=page.h source_url=page.u scope='product' %}")
        product_pages = [{"a": 3, "r": 1, "s": 0, "h": True, "u": "https://example.test/rh"},
                         {"a": 0, "r": 0, "s": 0, "h": False, "u": ""}]
        cases = []
        for page in rh_pages() + [github_absent]:
            for inc in (INCLUDES, old):
                cases.append({"template": CARD_CALL, "page": page, "site": SITE, "includes": str(inc)})
        for page in product_pages:
            for inc in (INCLUDES, old):
                cases.append({"template": product_call, "page": page, "site": SITE, "includes": str(inc)})
        cases.append({"template": CARD_CALL, "page": github_declared, "site": SITE, "includes": str(INCLUDES)})
        out = render_many(cases)
    if out is None:
        for n in ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9"):
            check(f"{n} could not render: ruby/liquid unavailable", False,
                  "install ruby and the liquid gem (CI pins liquid 4.0.4)")
        return
    n_rh = len(rh_pages())
    pairs = [(out[2 * i], out[2 * i + 1]) for i in range(n_rh + 1 + len(product_pages))]
    rh_pairs, absent_pair, product_pairs = pairs[:n_rh], pairs[n_rh], pairs[n_rh + 1:]
    check("R1 every Release Health card renders byte-identical to the pre-AUX-125 card (with or without the field)",
          all(new == old_ and not new.startswith("RENDER-ERROR") for new, old_ in rh_pairs),
          next((f"{n[:300]!r} != {o[:300]!r}" for n, o in rh_pairs if n != o), ""))
    check("R2 the product-page card (scope product) renders byte-identical too",
          all(new == old_ and not new.startswith("RENDER-ERROR") for new, old_ in product_pairs))
    absent_new, absent_old = absent_pair
    check("R3 a GitHub record WITHOUT the field renders exactly today's card",
          absent_new == absent_old and ABSENT_TEXT in absent_new
          and "No vendor-known issue data captured for this patch." in absent_new, absent_new[:300])
    check("R4 ...which never says the vendor has no known issues",
          "no known issues" not in absent_new.lower() and "No active vendor-known issues" not in absent_new)
    declared = out[-1]
    summary = re.search(r"<summary>(.*?)</summary>", declared, re.S)
    check("R5 a declared notice opens the card with GPT's wording as its summary",
          '<details class="panel update-info-card update-vendor-issues aux-collapsible-card" open aria-label=' in declared
          and summary is not None and summary.group(1) == "Vendor Known Issues — Vendor warning identified.",
          declared[:300])
    check("R6 ...states the notice, links the official notes and this page's Official Patch Notes",
          WARNING_SENTENCES in declared and "Not counted as community reports." in declared
          and 'href="https://github.com/obsproject/obs-studio/releases/tag/9.1.2">Official release notes' in declared
          and 'href="#official-patch-notes"' in declared, declared[:500])
    check("R7 ...and prints no count of any kind",
          re.search(r"\d", summary.group(1) if summary else "x1") is None
          and "active" not in declared and "safeguard" not in declared)

    # The notice under the verdict, in the real layout (includes stripped as the other suites do).
    layout = _layout_body(_LAYOUT)
    without_hero = _layout_body(_LAYOUT.replace(HERO_BLOCK, "")) if HERO_BLOCK else ""
    page_absent = dict(writer.build_front_matter(github_record(HOTFIX)))
    page_declared = dict(writer.build_front_matter(github_record(NOTICE + HOTFIX)))
    pages = render_many([
        {"template": layout, "page": page_absent, "site": SITE, "includes": str(INCLUDES)},
        {"template": without_hero, "page": page_absent, "site": SITE, "includes": str(INCLUDES)},
        {"template": layout, "page": page_declared, "site": SITE, "includes": str(INCLUDES)},
    ]) or ["RENDER-ERROR"] * 3
    absent_page, baseline_page, declared_page = pages
    check("R8 without the field the page renders byte-identical to the layout without the notice block",
          bool(HERO_BLOCK) and absent_page == baseline_page and not absent_page.startswith("RENDER-ERROR")
          and "update-official-notes-warning" not in absent_page, absent_page[:200])
    at_verdict = declared_page.find('id="verdict"')
    at_notice = declared_page.find("update-official-notes-warning")
    at_evidence = declared_page.find("update-evidence-card")
    check("R9 with the field the notice renders directly under the verdict, before the evidence card",
          -1 < at_verdict < at_notice < at_evidence
          and "<strong>Vendor warning identified.</strong> " + WARNING_SENTENCES in declared_page
          and 'href="https://github.com/obsproject/obs-studio/releases/tag/9.1.2">Official release notes' in declared_page,
          f"verdict@{at_verdict} notice@{at_notice} evidence@{at_evidence}")


# --------------------------------------------------------------------------------------------
def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_migration(args: list[str]) -> tuple[int, dict]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = migration.main(args)
    text = buf.getvalue()
    try:
        return rc, json.loads(text[text.index("{"):])
    except ValueError:
        return rc, {"raw": text}


def section_m_migration() -> None:
    print("\n[M] the migration: zero network, demonstrated changes only, one line each, idempotent")
    with tempfile.TemporaryDirectory() as td:
        corpus = Path(td) / "generated"
        corpus.mkdir()
        made = {}
        for name, rec in (("declared", github_record(NOTICE + HOTFIX, "9.1.2")),
                          ("clean", github_record(HOTFIX.replace("9.1.2", "9.1.3"), "9.1.3")),
                          ("stale", github_record(HOTFIX.replace("9.1.2", "9.1.4"), "9.1.4")),
                          ("windows", windows_record())):
            path, _ = writer.write_record(corpus, rec)
            made[name] = path
        writer_text = made["declared"].read_text(encoding="utf-8")
        line = f"{nki.FIELD}: declared\n"
        made["declared"].write_text(writer_text.replace(line, ""), encoding="utf-8", newline="\n")
        stale_text = made["stale"].read_text(encoding="utf-8")
        close = stale_text.find("\n---\n", 3) + 1
        made["stale"].write_text(stale_text[:close] + line + stale_text[close:], encoding="utf-8", newline="\n")
        unrelated = corpus / "2026-01-01-other-1-0.md"
        unrelated.write_text("---\nlayout: aux-update\nproduct_id: other\n---\n", encoding="utf-8", newline="\n")
        before = {p.name: _digest(p) for p in corpus.glob("*.md")}
        stale_before = made["stale"].read_text(encoding="utf-8")

        rc, report = _run_migration(["--records", str(corpus), "--write"])
        after = {p.name: _digest(p) for p in corpus.glob("*.md")}
        touched = sorted(n for n in after if after[n] != before.get(n))
        check("M1 the manifest is exactly the demonstrated changes: one set, one removed",
              rc == 0 and sorted(report.get("manifest", [])) == sorted(
                  [f"{made['declared'].name}: set", f"{made['stale'].name}: removed"])
              and touched == sorted([made["declared"].name, made["stale"].name]), json.dumps(report)[:400])
        check("M2 the migrated record is byte-identical to what the writer itself produces",
              made["declared"].read_text(encoding="utf-8") == writer_text)
        check("M3 the removal deletes exactly the one line",
              made["stale"].read_text(encoding="utf-8") == stale_before.replace(line, "", 1)
              and nki.FIELD not in front_of(made["stale"]))
        check("M4 the Windows record (whose body alone would read as declaring) and an unrelated record are untouched",
              after[made["windows"].name] == before[made["windows"].name]
              and after[unrelated.name] == before[unrelated.name])
        rc2, report2 = _run_migration(["--records", str(corpus), "--write"])
        again = {p.name: _digest(p) for p in corpus.glob("*.md")}
        check("M5 idempotent: a second run has an empty manifest and changes no byte",
              rc2 == 0 and report2.get("manifest") == [] and again == after, json.dumps(report2)[:300])

        odd = made["clean"]
        odd_text = HOTFIX.replace("9.1.2", "9.1.3")
        body_front, body_rest = writer._front_matter(odd)
        body_front["official_patch_notes_body"] = NOTICE.replace("9.1.2", "9.1.3") + odd_text
        body_front[nki.FIELD] = True
        odd.write_text(writer._dump_record(body_front, body_rest), encoding="utf-8", newline="\n")
        # A change that WOULD be written, so the refusal is what holds it back.
        made["declared"].write_text(writer_text.replace(line, ""), encoding="utf-8", newline="\n")
        frozen = {p.name: _digest(p) for p in corpus.glob("*.md")}
        rc3, report3 = _run_migration(["--records", str(corpus), "--write"])
        check("M6 a record it cannot edit exactly is refused, and then NOTHING is written",
              rc3 == 2 and report3.get("refused") and report3.get("mode") == "dry_run"
              and {p.name: _digest(p) for p in corpus.glob("*.md")} == frozen, json.dumps(report3)[:300])

    entries = migration.plan(RECORDS)
    pending = [f"{e['path'].name}: {e['decision']}" for e in entries if e["decision"] != "unchanged"]
    check("M7 the committed corpus has nothing left to migrate: every GitHub record agrees with its stored body",
          len(entries) > 0 and pending == [], f"{len(entries)} records, pending={pending[:5]}")
    frozen_record = RECORDS / FROZEN["record"].rsplit("/", 1)[-1]
    if frozen_record.exists():
        stored = front_of(frozen_record)
        same_body = hashlib.sha256(str(stored.get("official_patch_notes_body") or "").encode("utf-8")).hexdigest() == FROZEN["sha256"]
        check("M8 OBS Studio 33.0.2 carries the field while it stores the frozen body",
              (not same_body) or stored.get(nki.FIELD) == "declared", repr(stored.get(nki.FIELD)))
    else:
        check("M8 OBS Studio 33.0.2 carries the field while it stores the frozen body", True)

    banned = {"urllib", "http", "socket", "requests", "ssl", "subprocess", "lib.http", "lib.github_api",
              "adapters", "patch_collectors"}
    found = []
    for path in (_SCRIPTS / "migrate_official_notes_known_issue.py", _SCRIPTS / "lib" / "notes_known_issue.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                names = [mod] + [f"{mod}.{a.name}" for a in node.names]
            for name in names:
                if any(name == b or name.startswith(b + ".") for b in banned):
                    found.append(f"{path.name}: {name}")
    check("M9 zero network by construction: neither the migration nor the parser imports a transport",
          found == [], str(found))


# --------------------------------------------------------------------------------------------
def section_b_bare_script() -> None:
    print("\n[B] the new import resolves when the lanes run their scripts bare")
    env = {k: v for k, v in os.environ.items() if k not in {"GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY"}}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    ingest = subprocess.run([sys.executable, "auxsays/scripts/patch_ingest.py", "--help"], cwd=_REPO,
                            capture_output=True, text=True, env=env, timeout=120)
    check("B1 patch_ingest.py imports the writer (and the parser) as a bare script",
          ingest.returncode == 0 and "usage" in ingest.stdout.lower(), ingest.stderr[-300:])
    with tempfile.TemporaryDirectory() as td:
        mig = subprocess.run([sys.executable, "auxsays/scripts/migrate_official_notes_known_issue.py",
                              "--records", td], cwd=_REPO, capture_output=True, text=True, env=env, timeout=120)
    check("B2 the migration runs as a bare script (report-only by default)",
          mig.returncode == 0 and '"mode": "dry_run"' in mig.stdout, mig.stderr[-300:])


def run() -> int:
    section_p_parser()
    section_w_regression()
    section_c_contract()
    section_r_render()
    section_m_migration()
    section_b_bare_script()
    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(1)
