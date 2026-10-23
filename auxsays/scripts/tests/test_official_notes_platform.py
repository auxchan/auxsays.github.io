"""A record built from one platform's release notes says so, and nothing more.

WHAT WAS WRONG. Elgato publishes some versions' notes per platform. The first Zendesk run published
"Wave Link 3.2.10" from the article "Elgato Wave Link 3.2.10 (Windows) Release Notes" and
"Wave Link 2.0.9" from "Elgato Wave Link 2.0.9 Release Notes (macOS)" -- platform-neutral titles
over one platform's notes. A Windows reader of 2.0.9 got macOS notes with nothing marking them.

WHAT IS PINNED HERE.
  [A] the adapter reads the platform from the article TITLE only, from a closed vocabulary;
  [B] the field travels beside the verbatim title, so record identity cannot move;
  [C] end to end through fetch(): labelled, unlabelled, deferred and unrecognised articles;
  [D] the writer's create path stores labelled titles (SEO <title> reads front matter only);
  [E] the refresh path relabels, repairs partial records, stays idempotent, and never touches a
      curated title or another product;
  [F] a second platform's article arriving later freezes the labelled record, still labelled;
  [G] the real patch layout renders whose notes these are;
  [H] the publish QA refuses community reports or counted evidence for per-platform vendors;
  [I] a tripwire: no community collector or method route may target those vendors yet.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_official_notes_platform.py
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
_SCRIPTS = _AUX / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import yaml  # noqa: E402

from adapters import zendesk_help_center as zendesk  # noqa: E402
from lib import write_update_record as writer  # noqa: E402
import patch_ingest  # noqa: E402
import qa_patch_records as qa  # noqa: E402

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
            print("        " + detail)
        _ERRORS.append(label)


HOST = "help.elgato.com"
WAVE_SECTION = 4913442828941
# The two titles the live records were built from, recovered exactly by recomputing the seen-ledger
# digest sha256(url + version + title)[:16].
WINDOWS_TITLE = "Elgato Wave Link 3.2.10 (Windows) Release Notes"
MACOS_TITLE = "Elgato Wave Link 2.0.9 Release Notes (macOS)"


def wave_source() -> dict:
    return {
        "product_id": "elgato-wave-link", "company_id": "elgato", "company": "Elgato",
        "software": "Wave Link", "public_category": "Audio",
        "ingestion": {
            "adapter": "zendesk_help_center", "type": "help_center_release_notes",
            "official_url": f"https://{HOST}/hc/en-us/sections/{WAVE_SECTION}-Release-Notes",
            "version_pattern": r"^Elgato Wave Link (?P<version>[0-9]+(\.[0-9]+)+).*$",
            "product_terms": ["wave link"],
        },
    }


def article(article_id: int, title: str, created: str, body: str = "") -> dict:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-")
    return {"id": article_id, "section_id": WAVE_SECTION, "title": title, "created_at": created,
            "updated_at": created, "draft": False, "locale": "en-us",
            "html_url": f"https://{HOST}/hc/en-us/articles/{article_id}-{slug}",
            "body": body or f"<p>{title} official changes.</p>", "label_names": ["Release Notes"]}


def list_url() -> str:
    return (f"https://{HOST}/api/v2/help_center/en-us/sections/{WAVE_SECTION}/articles.json"
            "?per_page=100&sort_by=created_at&sort_order=desc")


def page(articles: list) -> str:
    return json.dumps({"count": len(articles), "page": 1, "page_count": 1, "per_page": 100,
                       "next_page": None, "previous_page": None, "articles": articles})


def run_fetch(articles: list) -> tuple:
    original = zendesk.fetch_text
    buf = io.StringIO()
    try:
        zendesk.fetch_text = lambda url, **_kw: SimpleNamespace(text=page(articles))
        with redirect_stderr(buf):
            records = zendesk.fetch(wave_source(), limit=200)
    finally:
        zendesk.fetch_text = original
    return records, buf.getvalue()


def diag(stderr: str, key: str) -> int:
    m = re.search(rf"\b{key}=(\d+)", stderr)
    return int(m.group(1)) if m else -1


# --------------------------------------------------------------------------------------------
def section_a_title_parser() -> None:
    print("\n[A] the platform comes from the article TITLE, in a closed vocabulary")
    p = zendesk.notes_platform_from_title
    check("A1 '(Windows)' mid-title -> windows", p(WINDOWS_TITLE) == "windows")
    check("A2 '(macOS)' suffix -> macos", p(MACOS_TITLE) == "macos")
    check("A3 a title naming no platform -> nothing",
          p("Elgato Stream Deck 7.6 Release Notes") == "")
    check("A4 a title naming BOTH -> nothing, never a pick",
          p("Elgato Wave Link 3.4 (Windows) (macOS) Release Notes") == "")
    unrecognised = ["Elgato Wave Link 3.4 Release Notes for Mac",
                    "Elgato Wave Link 3.4 Release Notes - Windows and macOS",
                    "Elgato Wave Link 3.4 (Mac) Release Notes"]
    check("A5 platform words outside the known form -> nothing (no aliases)",
          all(p(t) == "" for t in unrecognised), str([p(t) for t in unrecognised]))


def section_b_identity() -> None:
    print("\n[B] the field travels beside the verbatim title; identity cannot move")
    art = article(49526614077713, WINDOWS_TITLE, "2026-08-05T10:00:00Z")
    rec = zendesk._record(wave_source(), art, "3.2.10", "body")
    digest = hashlib.sha256((art["html_url"] + "3.2.10" + WINDOWS_TITLE).encode("utf-8")).hexdigest()[:16]
    check("B1 the candidate title stays verbatim, platform included", rec["title"] == WINDOWS_TITLE)
    check("B2 record_id is the digest of the VERBATIM title (a published record stays seen)",
          rec["record_id"] == f"zendesk:elgato-wave-link:3.2.10:{digest}", rec["record_id"])
    check("B3 the platform is carried as its own field", rec.get("official_notes_platform") == "windows")
    plain = zendesk._record(wave_source(), article(1, "Elgato Wave Link 3.3 Release Notes",
                                                   "2026-09-01T00:00:00Z"), "3.3", "body")
    check("B4 an unlabelled article carries no platform key at all (never '')",
          "official_notes_platform" not in plain, str(plain.get("official_notes_platform")))


def section_c_fetch() -> None:
    print("\n[C] end to end through fetch(): labelled, deferred, unrecognised")
    articles = [
        article(11, WINDOWS_TITLE, "2026-08-05T10:00:00Z",
                body="<p>Windows x64 and arm64. Also fixes an issue seen on macOS.</p>"),
        article(12, MACOS_TITLE, "2026-08-12T10:00:00Z"),
        article(13, "Elgato Wave Link 3.4 (Windows) Release Notes", "2026-10-01T10:00:00Z"),
        article(14, "Elgato Wave Link 3.4 (macOS) Release Notes", "2026-10-01T11:00:00Z"),
        article(15, "Elgato Wave Link 3.3 Release Notes for Mac", "2026-09-10T10:00:00Z"),
        article(16, "Elgato Wave Link 3.2.9 Release Notes", "2026-07-20T10:00:00Z",
                body="<p>Windows and macOS fixes.</p>"),
    ]
    records, stderr = run_fetch(articles)
    by_version = {r["version"]: r for r in records}
    check("C1 the Windows article's record says windows (the body naming macOS is ignored)",
          by_version.get("3.2.10", {}).get("official_notes_platform") == "windows")
    check("C2 the macOS article's record says macos",
          by_version.get("2.0.9", {}).get("official_notes_platform") == "macos")
    check("C3 a version claimed by two platform articles is still deferred",
          "3.4" not in by_version and diag(stderr, "versions_deferred") == 1, stderr[-200:])
    check("C4 a platform word in an unknown form labels nothing and is counted",
          "official_notes_platform" not in by_version.get("3.3", {"official_notes_platform": "x"})
          and diag(stderr, "platform_titles_unrecognized") == 1, stderr[-200:])
    check("C5 a neutral title whose BODY names both systems stays unlabelled",
          "official_notes_platform" not in by_version.get("3.2.9", {"official_notes_platform": "x"}))


# --------------------------------------------------------------------------------------------
def candidate(version: str, platform: str = "", title: str = "",
              checked: str = "2026-10-23T00:13:53Z") -> dict:
    rec = {"record_id": f"zendesk:elgato-wave-link:{version}:x", "company_id": "elgato",
           "product_id": "elgato-wave-link", "company": "Elgato", "software": "Wave Link",
           "category": "Audio", "version": version, "title": title or f"Elgato Wave Link {version}",
           "published_at": "2026-08-05T10:00:00Z",
           "source_url": f"https://{HOST}/hc/en-us/articles/1-Elgato-Wave-Link",
           "official_url": f"https://{HOST}/hc/en-us/sections/1", "download_url": "",
           "body": "Official changes for this version, long enough to count as a captured body.",
           "source_type": "help_center_release_notes", "source_last_checked": checked}
    if platform:
        rec["official_notes_platform"] = platform
    return rec


TITLE_KEYS = ("title", "description", "update_feed_title", "update_detail_title")


def section_d_create() -> None:
    print("\n[D] create stores labelled titles; unlabelled records are byte-for-byte as before")
    labelled = writer.build_front_matter(candidate("3.2.10", "windows"))
    check("D1 the field is written on create", labelled.get("official_notes_platform") == "windows")
    check("D2 the headline names whose notes these are",
          labelled["update_feed_title"] == "Wave Link 3.2.10 — Windows release notes"
          and labelled["update_detail_title"] == "Wave Link 3.2.10 — Windows release notes",
          labelled["update_feed_title"])
    check("D3 the SEO title and description carry it too (no template can reach <title>)",
          labelled["title"] == "Wave Link 3.2.10 official update breakdown (Windows release notes)"
          and labelled["description"].endswith("for 3.2.10 (Windows release notes)."),
          f"{labelled['title']} | {labelled['description']}")
    plain = writer.build_front_matter(candidate("3.3"))
    check("D4 an unlabelled record's titles are exactly the established form",
          plain["title"] == "Wave Link 3.3 official update breakdown"
          and plain["description"] == "Official Wave Link update record captured from Elgato for 3.3."
          and plain["update_feed_title"] == "Wave Link 3.3" and plain["update_detail_title"] == "Wave Link 3.3"
          and "official_notes_platform" not in plain)
    try:
        bogus = writer.build_front_matter(candidate("3.3", "linux"))
    except Exception as exc:  # noqa: BLE001 -- a crash on bad input FAILS D5 by name
        bogus = {"_raised": repr(exc)}
    check("D5 a value outside the vocabulary is never written",
          "official_notes_platform" not in bogus and bogus.get("update_feed_title") == "Wave Link 3.3",
          str(bogus.get("_raised") or bogus.get("update_feed_title")))
    check("D6 identity is untouched: permalink and version are the platform-free ones",
          labelled["permalink"] == plain["permalink"].replace("3-3", "3-2-10")
          and labelled["update_version"] == "3.2.10" and "windows" not in labelled["permalink"],
          labelled["permalink"])


def section_e_refresh() -> None:
    print("\n[E] refresh relabels, repairs, stays idempotent, and touches nothing curated")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        # The live shape: a record created BEFORE the label existed.
        path, action = writer.write_record(out, candidate("3.2.10"))
        front0, _ = writer._front_matter(path)
        check("E0 the pre-fix record is created unlabelled", action == "created"
              and front0["update_feed_title"] == "Wave Link 3.2.10", action)

        path2, action = writer.write_record(out, candidate("3.2.10", "windows"))
        front, _ = writer._front_matter(path2)
        check("E1 the next refresh relabels all four titles and sets the field",
              action == "refreshed" and front.get("official_notes_platform") == "windows"
              and all("Windows release notes" in str(front[k]) for k in TITLE_KEYS),
              f"{action} {[front.get(k) for k in TITLE_KEYS]}")
        check("E2 same file, same permalink, same version (identity unmoved)",
              path2 == path and front["permalink"] == front0["permalink"]
              and front["update_version"] == "3.2.10")
        changed = {k for k in set(front0) | set(front) if front0.get(k) != front.get(k)}
        owned = set(TITLE_KEYS) | {"official_notes_platform", "official_source_attempts",
                                   "record_last_updated"}
        check("E7 the relabelling refresh changed only the fields this change owns",
              "official_notes_platform" in changed and changed <= owned,
              f"changed outside the owned set: {sorted(changed - owned)}")
        # A LATER run, as in production: same observation, new check time. Only freshness may
        # move; a bogus material change would bump record_last_updated and churn every record.
        _p, action = writer.write_record(out, candidate("3.2.10", "windows",
                                                        checked="2026-10-23T06:13:53Z"))
        steady, _ = writer._front_matter(path)
        check("E3 a steady-state refresh does not report a material change",
              action in ("unchanged", "freshness-updated")
              and steady.get("record_last_updated") == front.get("record_last_updated"),
              f"{action} record_last_updated {front.get('record_last_updated')} -> "
              f"{steady.get('record_last_updated')}")
        _p, action = writer.write_record(out, candidate("3.2.10"))
        after_absent, _ = writer._front_matter(path)
        check("E4 a refresh carrying no platform keeps the label (absent is not 'none')",
              after_absent.get("official_notes_platform") == "windows"
              and "Windows release notes" in after_absent["update_feed_title"], action)

        # Partial record: field present, one title still in the unlabelled form.
        front_p, body = writer._front_matter(path)
        front_p["update_feed_title"] = "Wave Link 3.2.10"
        path.write_text(writer._dump_record(front_p, body), encoding="utf-8")
        writer.write_record(out, candidate("3.2.10"))
        repaired, _ = writer._front_matter(path)
        check("E5 a partially labelled record is repaired on refresh",
              repaired["update_feed_title"] == "Wave Link 3.2.10 — Windows release notes",
              repaired["update_feed_title"])

        # A curated title matches no generated form and is never rewritten.
        path_c, _ = writer.write_record(out, candidate("2.0.9"))
        front_c, body_c = writer._front_matter(path_c)
        front_c["update_detail_title"] = "Wave Link 2.0.9: the macOS maintenance release"
        path_c.write_text(writer._dump_record(front_c, body_c), encoding="utf-8")
        writer.write_record(out, candidate("2.0.9", "macos"))
        curated, _ = writer._front_matter(path_c)
        check("E6 a curated title is left alone while the field still lands",
              curated["update_detail_title"] == "Wave Link 2.0.9: the macOS maintenance release"
              and curated.get("official_notes_platform") == "macos"
              and curated["update_feed_title"] == "Wave Link 2.0.9 — macOS release notes",
              str({k: curated.get(k) for k in TITLE_KEYS}))

    # Another product with a non-generated title and no platform: refresh must not touch it.
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        other = candidate("3.3")
        p, _ = writer.write_record(out, other)
        f, b = writer._front_matter(p)
        f["title"] = "Wave Link 3.3 official update breakdown, hand-edited"
        p.write_text(writer._dump_record(f, b), encoding="utf-8")
        writer.write_record(out, other)
        g, _ = writer._front_matter(p)
        # ALL FOUR titles, not just the hand-edited one: the curated rule protects that one
        # whatever the platform logic does, so checking it alone passed a refresh that defaulted
        # every unlabelled record to a platform.
        check("E8 with no platform anywhere, refresh leaves every title exactly as found",
              all(g.get(k) == f.get(k) for k in TITLE_KEYS)
              and g.get("record_last_updated") == f.get("record_last_updated")
              and "official_notes_platform" not in g,
              str({k: g.get(k) for k in TITLE_KEYS}))


def section_f_second_article_later() -> None:
    print("\n[F] a second platform's article arriving LATER freezes the labelled record, labelled")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "gen"
        out.mkdir()
        state: dict = {"schema_version": 1, "sources": {}}
        args = SimpleNamespace(limit=2, output=out, overwrite_existing=False)
        first = [article(21, WINDOWS_TITLE, "2026-08-05T10:00:00Z")]
        both = first + [article(22, "Elgato Wave Link 3.2.10 (macOS) Release Notes", "2026-08-06T10:00:00Z")]
        original = zendesk.fetch_text
        try:
            zendesk.fetch_text = lambda url, **_kw: SimpleNamespace(text=page(first))
            with redirect_stderr(io.StringIO()):
                patch_ingest.run_source(wave_source(), args, state)
            files = sorted(out.glob("*.md"))
            snapshot = files[0].read_text(encoding="utf-8") if files else ""
            zendesk.fetch_text = lambda url, **_kw: SimpleNamespace(text=page(both))
            with redirect_stderr(io.StringIO()):
                patch_ingest.run_source(wave_source(), args, state)
        finally:
            zendesk.fetch_text = original
        files_after = sorted(out.glob("*.md"))
        front, _ = writer._front_matter(files_after[0]) if files_after else ({}, "")
        check("F1 one record exists, built from the Windows article", len(files) == 1
              and front.get("official_notes_platform") == "windows", str([f.name for f in files]))
        check("F2 once both platforms publish, the version is deferred and the page is untouched",
              len(files_after) == 1 and files_after[0].read_text(encoding="utf-8") == snapshot)
        check("F3 the frozen page still says it holds the Windows notes, not every platform's",
              "Windows release notes" in str(front.get("update_feed_title")))


# --------------------------------------------------------------------------------------------
_RENDER_RB = r"""
require 'liquid'
require 'json'
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
payload = JSON.parse(File.read(ARGV[0]))
print Liquid::Template.parse(payload['layout']).render!('site' => payload['site'], 'page' => payload['page'])
"""


def render_update(page: dict):
    ruby = shutil.which("ruby")
    if not ruby:
        return None
    text = (_AUX / "_layouts" / "aux-update.html").read_text(encoding="utf-8").split("---", 2)[-1]
    text = re.sub(r"\{%-?\s*include\s.*?-?%\}", "", text, flags=re.S)
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "r.rb").write_text(_RENDER_RB, encoding="utf-8")
        (Path(td) / "p.json").write_text(json.dumps({
            "layout": text, "page": page,
            "site": {"title": "AUXSAYS", "time": "2026-10-23T00:00:00Z", "pages": [],
                     "data": {"evidence_method_health": {"methods": []}}}}, default=str),
            encoding="utf-8")
        out = subprocess.run([ruby, str(Path(td) / "r.rb"), str(Path(td) / "p.json")],
                             capture_output=True, text=True, encoding="utf-8", errors="replace",
                             timeout=180)
    return out.stdout if out.returncode == 0 else f"RENDER-ERROR {out.stderr[-300:]}"


def section_g_render() -> None:
    print("\n[G] the real patch layout says whose notes these are")
    base = writer.build_front_matter(candidate("2.0.9", "macos"))
    html = render_update(dict(base, official_patch_notes_body="<p>Fixes.</p>"))
    if html is None:
        for n in ("G1", "G2", "G3"):
            check(f"{n} could not render: ruby/liquid unavailable", False,
                  "install ruby and the liquid gem (CI pins liquid 4.0.4)")
        return
    sentence = "These are Elgato's macOS release notes for this version."
    check("G1 the applicability line names the platform the notes cover", sentence in html,
          html[:200] if html.startswith("RENDER-ERROR") else "sentence missing")
    check("G2 the collapsed Official Patch Notes summary names it too",
          re.search(r"<summary>Official Patch Notes \(macOS\)", html) is not None)
    plain = render_update(dict(writer.build_front_matter(candidate("3.3")),
                               official_patch_notes_body="<p>Fixes.</p>"))
    check("G3 an unlabelled record renders neither", plain is not None
          and not plain.startswith("RENDER-ERROR") and "Official Patch Notes" in plain
          and "release notes for this version." not in plain
          and "Official Patch Notes (" not in plain, (plain or "")[:200])


def section_h_publish_guard() -> None:
    print("\n[H] the publish QA refuses community reports or counted evidence for per-platform vendors")
    official = {"company_id": "elgato", "product_id": "elgato-wave-link", "update_version": "3.2.10",
                "evidence_state": "official_only", "update_report_count": 0}
    clean = qa.scan_platform_scoped_consensus([(Path("r.md"), official)], {})
    check("H1 an official-only Elgato record passes", clean == [], str(clean))
    claimed = qa.scan_platform_scoped_consensus(
        [(Path("r.md"), dict(official, update_report_count=3, evidence_state="pilot_sample"))], {})
    check("H2 an Elgato record claiming reports is an error",
          [e["code"] for e in claimed] == ["platform_scoped_report_claimed"], str(claimed))
    counted = qa.scan_platform_scoped_consensus(
        [(Path("r.md"), official)], {("elgato-stream-deck", "7.6", ""): 2})
    check("H3 counted evidence for ANY Elgato product is an error, labelled or not",
          [e["code"] for e in counted] == ["platform_scoped_evidence_counted"], str(counted))
    # Each a claim on its own, with every other field official-only: the page keys "Verified
    # reports" on the collection status and falls back to evidence_samples for its citations.
    pilot = qa.scan_platform_scoped_consensus(
        [(Path("r.md"), dict(official, consensus_collection_status="pilot_initial_sample"))], {})
    check("H6 a zero-report Elgato record with a pilot collection status is an error",
          [e["code"] for e in pilot] == ["platform_scoped_report_claimed"], str(pilot))
    sampled = qa.scan_platform_scoped_consensus(
        [(Path("r.md"), dict(official, evidence_samples=[{"source_url": "https://example.test/1"}]))], {})
    check("H7 a zero-report Elgato record listing evidence samples is an error",
          [e["code"] for e in sampled] == ["platform_scoped_report_claimed"], str(sampled))
    other = qa.scan_platform_scoped_consensus(
        [(Path("o.md"), {"company_id": "obs-project", "product_id": "obs-studio",
                         "update_report_count": 9, "evidence_state": "pilot_sample"})],
        {("obs-studio", "32.0", ""): 9})
    check("H4 another vendor's reports are untouched", other == [], str(other))
    # EXECUTED through the function the deploy and every writeback lane call, not grepped for: a
    # record file claiming reports must surface the error from the real call site.
    with tempfile.TemporaryDirectory() as td:
        rec = Path(td) / "2026-08-05-wave-link-3-2-10.md"
        rec.write_text("---\n" + yaml.safe_dump(dict(official, update_report_count=2,
                                                       evidence_state="pilot_sample"))
                       + "---\nbody\n", encoding="utf-8")
        errors, _warnings = qa.scan_evidence_count_alignment([rec])
    check("H5 the guard fires inside the QA pass the deploy and every writeback lane execute",
          "platform_scoped_report_claimed" in [e["code"] for e in errors],
          str([e["code"] for e in errors]))


def section_i_tripwire() -> None:
    print("\n[I] tripwire: no community lane may target a per-platform vendor yet")
    import run_patch_evidence_collection as rpec
    from lib import method_routing
    blocked = qa.PLATFORM_UNGATED_COMPANIES
    company_of = {p.get("id"): p.get("company_id")
                  for p in yaml.safe_load((_AUX / "_data" / "patch_products.yml").read_text(encoding="utf-8")) or []}
    every_flag = {name: "true" for name in dir(rpec) if name.endswith("_ENABLE_ENV")}
    env = {getattr(rpec, name): "true" for name in every_flag}
    registered = rpec.build_collectors(env)
    hit = sorted(pid for pid in registered if company_of.get(pid) in blocked)
    check("I1 no collector, under any enable flag, targets a per-platform vendor", not hit,
          f"{hit}: add platform-aware acceptance first (AUX-049)")
    routed = sorted(pid for pid in method_routing.METHOD_PLANS if company_of.get(pid) in blocked)
    check("I2 no method plan targets a per-platform vendor", not routed, str(routed))


# --------------------------------------------------------------------------------------------
# Verbatim download sections of the captured official notes (whitespace collapsed), so the
# classifier is proven on what Elgato actually publishes, without reading bot-written records.
SD_76_NOTES = ("22 September 2026 Download Links macOS Elgato Stream Deck 7.6.pkg Windows Elgato "
               "Stream Deck 7.6.msi What's new in Stream Deck 7.6? Infobar Actions for Stream Deck Neo")
CH_23_NOTES = ("Release Date: 14 July 2026 Windows Camera Hub 2.3.msi macOS Camera Hub 2.3.pkg "
               "New Facecam 4K Firmware - Sharper, Cleaner, More Accurate")
FOURK_1716_NOTES = ("Utility 1.7.16? Download Download 4K Capture Utility 1.7.16 from Elgato.com or the "
                    "direct link below. Download for Windows Removed Bonjour Service")
WL_3210_NOTES = ("Release Date : 5 August 2026 Download Links Windows Elgato Wave Link 3.2.10.msix (x64) "
                 "Elgato Wave Link 3.2.10.msix (arm64) What's new in Wave Link 3.2.10 (Windows)?")
WL_209_NOTES = ("Release Date : 12 August 2026 Download Links macOS Elgato Wave Link 2.0.9.pkg "
                "What's new in Wave Link 2.0.9?")


def section_j_joint_platform_evidence() -> None:
    print("\n[J] notes for BOTH platforms are established by installers, never assumed from a silent title")
    # Each product's own configured `product_terms` (patch_ingestion_sources.yml), composed into
    # installer names exactly as the adapter does.
    terms = {"Stream Deck": ["stream deck"], "Camera Hub": ["camera hub"],
             "4K Capture Utility": ["4k capture utility", "4k capture"], "Wave Link": ["wave link"]}

    def p(title: str, body: str, version: str) -> tuple:
        product = next(name for name in terms if name in title)
        names = zendesk._installer_names({"company": "Elgato", "ingestion": {"product_terms": terms[product]}})
        return zendesk.notes_platform_for(title, body, version, names)

    check("J1 Stream Deck 7.6: same-version .pkg and .msi -> windows_macos, from installers",
          p("Elgato Stream Deck 7.6 Release Notes", SD_76_NOTES, "7.6") == ("windows_macos", "installer_downloads"))
    check("J2 Camera Hub 2.3: same-version .msi and .pkg -> windows_macos",
          p("Elgato Camera Hub 2.3 Release Notes", CH_23_NOTES, "2.3") == ("windows_macos", "installer_downloads"))
    check("J3 4K Capture Utility 1.7.16: a silent title with a Windows download only -> unknown",
          p("Elgato 4K Capture Utility 1.7.16 Release Notes", FOURK_1716_NOTES, "1.7.16") == ("", ""))
    check("J4 Wave Link 3.2.10 stays Windows: the title token decides, from the title",
          p(WINDOWS_TITLE, WL_3210_NOTES, "3.2.10") == ("windows", "title_token"))
    check("J5 Wave Link 2.0.9 stays macOS",
          p(MACOS_TITLE, WL_209_NOTES, "2.0.9") == ("macos", "title_token"))
    check("J6 a silent title with no installers at all -> unknown, never neutral",
          p("Elgato Stream Deck 7.7 Release Notes", "Fixes for Windows and macOS users.", "7.7") == ("", ""))
    check("J7 installers for ANOTHER version, or a mix of versions -> unknown",
          p("Elgato Stream Deck 7.6 Release Notes", SD_76_NOTES.replace("7.6.pkg", "7.5.1.pkg")
            .replace("7.6.msi", "7.5.1.msi"), "7.6") == ("", "")
          and p("Elgato Stream Deck 7.6 Release Notes", SD_76_NOTES.replace("7.6.msi", "7.5.1.msi"), "7.6") == ("", ""))
    check("J8 an installer for one platform only -> unknown",
          p("Elgato Stream Deck 7.6 Release Notes", "Download Links macOS Elgato Stream Deck 7.6.pkg", "7.6") == ("", ""))
    # Independent review's counterexample: other software's installers, same version, both platforms.
    check("J14 installers not named for the tracked product -> unknown, in prose or in a download list",
          p("Elgato Stream Deck 7.6 Release Notes", "Troubleshooting note: DemoPlugin 7.6.pkg and DemoTool "
            "7.6.msi both fail to launch. No product downloads are listed.", "7.6") == ("", "")
          and p("Elgato Stream Deck 7.6 Release Notes",
                "Download Links macOS DemoPlugin 7.6.pkg Windows DemoTool 7.6.msi", "7.6") == ("", ""))
    check("J15 the product's own files named in a sentence are prose, not a download list -> unknown",
          p("Elgato Stream Deck 7.6 Release Notes", "Known issue: Elgato Stream Deck 7.6.pkg fails to open on "
            "older Macs, and Elgato Stream Deck 7.6.msi needs a restart.", "7.6") == ("", "")
          # each file is introduced by list vocabulary, but prose stands BETWEEN them
          and p("Elgato Stream Deck 7.6 Release Notes", "Known issues: Elgato Stream Deck 7.6.pkg fails to open "
                "on older Macs. Windows: Elgato Stream Deck 7.6.msi needs a restart.", "7.6") == ("", ""))
    sd_list = "Download Links macOS Elgato Stream Deck 7.6.pkg {note} Windows Elgato Stream Deck 7.6.msi"
    check("J19 only an architecture or platform qualifier may stand in a list; any other note breaks it",
          all(p("Elgato Stream Deck 7.6 Release Notes", sd_list.format(note=note), "7.6") == ("", "")
              for note in ("(withdrawn)", "(coming soon)", "(unavailable)", "(crashes on launch)"))
          and all(p("Elgato Stream Deck 7.6 Release Notes", sd_list.format(note=note), "7.6")
                  == ("windows_macos", "installer_downloads") for note in ("(Apple Silicon)", "(x64)", ""))
          and p("Elgato Stream Deck 7.6 Release Notes", "Known issues: Elgato Stream Deck 7.6.pkg (crashes on "
                "launch) Elgato Stream Deck 7.6.msi (needs a restart).", "7.6") == ("", ""))
    check("J20 a file whose name only ENDS in the product's name is another product's, wherever it is listed",
          p("Elgato Stream Deck 7.6 Release Notes", "Download Links macOS DemoPlugin for Stream Deck 7.6.pkg "
            "Windows Elgato Stream Deck 7.6.msi", "7.6") == ("", "")
          and p("Elgato Wave Link 3.4 Release Notes", "Download Links macOS Elgato Stream Deck + Wave Link "
                "3.4.pkg Windows Elgato Wave Link 3.4.msix", "3.4") == ("", "")
          and p("Elgato Stream Deck 7.6 Release Notes", "Elgato Stream Deck 7.6.pkg / Elgato Stream Deck 7.6.msi",
                "7.6") == ("windows_macos", "installer_downloads"))
    check("J16 another product's installers do not contradict the tracked product's",
          p("Elgato Stream Deck 7.6 Release Notes",
            SD_76_NOTES + " Requires Elgato Camera Hub 2.3.pkg or later.", "7.6")
          == ("windows_macos", "installer_downloads"))

    # The writer stores the value and its basis; joint notes add no title suffix or page line.
    joint = candidate("7.6", "windows_macos")
    joint["official_notes_platform_basis"] = "installer_downloads"
    front = writer.build_front_matter(joint)
    plain = writer.build_front_matter(candidate("7.6"))
    check("J9 create stores windows_macos with its basis, titles exactly the unsuffixed form",
          front.get("official_notes_platform") == "windows_macos"
          and front.get("official_notes_platform_basis") == "installer_downloads"
          and all(front[k] == plain[k] for k in TITLE_KEYS), str({k: front.get(k) for k in TITLE_KEYS}))
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        path, _ = writer.write_record(out, candidate("7.6"))
        before, _ = writer._front_matter(path)
        _p, action = writer.write_record(out, joint)
        after, _ = writer._front_matter(path)
        check("J10 the next refresh of an unlabelled record adds windows_macos and its basis only",
              after.get("official_notes_platform") == "windows_macos"
              and after.get("official_notes_platform_basis") == "installer_downloads"
              and all(after.get(k) == before.get(k) for k in TITLE_KEYS), action)
        # An observation that lost the notes -- the adapter then sends the TITLE as the body, and no
        # captured flag -- is not evidence the installers went away: the label stays.
        lost = candidate("7.6")
        lost["body"] = "Elgato Wave Link 7.6 Release Notes"
        writer.write_record(out, lost)
        survived, _ = writer._front_matter(path)
        check("J17 a refresh whose article body was missing keeps an installer-based label",
              survived.get("official_notes_platform") == "windows_macos"
              and survived.get("official_notes_platform_basis") == "installer_downloads",
              str(survived.get("official_notes_platform")))
        # The installers were the evidence: a later observation of the same notes that no longer
        # establishes both platforms takes the label away, instead of keeping it as "absent = keep".
        regressed = candidate("7.6")
        regressed["body"] = SD_76_NOTES.replace("7.6.pkg", "7.6.1.pkg")
        regressed["official_notes_body_captured"] = True
        writer.write_record(out, regressed)
        gone, _ = writer._front_matter(path)
        # A title-token label is NOT dropped by a captured body that says nothing about platforms.
        path_w, _ = writer.write_record(out, dict(candidate("3.2.10", "windows"),
                                                  official_notes_platform_basis="title_token"))
        writer.write_record(out, dict(candidate("3.2.10"), official_notes_body_captured=True))
        kept, _ = writer._front_matter(path_w)
        check("J13 a label whose evidence was the installers leaves with them; a title label stays",
              "official_notes_platform" not in gone and "official_notes_platform_basis" not in gone
              and kept.get("official_notes_platform") == "windows",
              f"gone={gone.get('official_notes_platform')!r} kept={kept.get('official_notes_platform')!r}")
    bogus = candidate("7.6", "windows_macos")
    bogus["official_notes_platform_basis"] = "a guess"
    check("J11 a basis outside its vocabulary is never written",
          "official_notes_platform_basis" not in writer.build_front_matter(bogus))

    # End to end through fetch(): the diagnostics count installers that established nothing.
    articles = [article(31, "Elgato Wave Link 3.3 Release Notes", "2026-09-01T10:00:00Z",
                        body="<p>Download Links macOS Elgato Wave Link 3.3.pkg Windows Elgato Wave Link 3.3.msi</p>"),
                article(32, "Elgato Wave Link 3.2.11 Release Notes", "2026-08-20T10:00:00Z",
                        body="<p>Download Links Windows Elgato Wave Link 3.2.11.msix</p>")]
    records, stderr = run_fetch(articles)
    by_version = {r["version"]: r for r in records}
    check("J12 through fetch(): joint installers label, one-platform installers are counted, not guessed",
          by_version.get("3.3", {}).get("official_notes_platform") == "windows_macos"
          and "official_notes_platform" not in by_version.get("3.2.11", {"official_notes_platform": "x"})
          and diag(stderr, "platform_downloads_unverified") == 1, stderr[-200:])
    # The captured flag is set only by a real body, and is the writer's input, never a record field.
    records, _ = run_fetch([article(33, "Elgato Wave Link 3.4.1 Release Notes", "2026-09-10T10:00:00Z",
                                    body="<p></p>"),
                            article(34, "Elgato Wave Link 3.4.2 Release Notes", "2026-09-12T10:00:00Z")])
    by_version = {r["version"]: r for r in records}
    empty, real = by_version.get("3.4.1", {}), by_version.get("3.4.2", {})
    with tempfile.TemporaryDirectory() as td:
        written, _ = writer.write_record(Path(td), real)
        stored, _ = writer._front_matter(written)
    check("J18 only a captured body is flagged as an observation of the notes, and the flag is never stored",
          "official_notes_body_captured" not in empty and empty.get("body") == empty.get("title")
          and real.get("official_notes_body_captured") is True
          and "official_notes_body_captured" not in stored,
          f"empty={sorted(empty)} stored={'official_notes_body_captured' in stored}")


def run() -> int:
    section_a_title_parser()
    section_b_identity()
    section_c_fetch()
    section_d_create()
    section_e_refresh()
    section_f_second_article_later()
    section_g_render()
    section_h_publish_guard()
    section_i_tripwire()
    section_j_joint_platform_evidence()
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
        raise SystemExit(2) from None
