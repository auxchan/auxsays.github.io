#!/usr/bin/env python3
"""Official records are written only with an ISO publication date (R4-FIX).

On 2026-11-26 the official ingest (3c107ec0) wrote
`updates/generated/November 1-netlify-google-gemini-4-neon-...md` with
`update_published_at: November 18, 2026`. The Netlify entry's URL carries no date, so the adapter
read the article's lead date and passed it through `normalize_date`, which returns text it cannot
parse VERBATIM; the writer then took the filename from its first ten characters. My Patch Stack's
picker stopped being newest-first for Netlify (dashboard IV2) and CI went red on main.

Proved here, offline (no network; every write goes to a temporary directory):
  A. the adapter turns "Month D, YYYY" (and an unambiguous abbreviation) into an ISO instant;
  B. the Netlify extractor, fed the real entry's text, emits the ISO date;
  C. the writer refuses a present-but-non-ISO date (InvalidPublicationDate) and writes nothing;
  D. patch_ingest refuses THAT record with a logged reason and keeps the rest of the run, in a write
     run and a dry run alike, without marking it seen;
  E. re-ingesting the repaired record refreshes it in place -- no second page;
  F. the tracked corpus holds no non-ISO record, and the repaired page exists exactly once.
"""
from __future__ import annotations

import contextlib
import io
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import yaml

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import patch_ingest  # noqa: E402
import qa_patch_records  # noqa: E402
from adapters import html_changelog as HC  # noqa: E402
from lib.normalize import split_front_matter  # noqa: E402
from lib.write_update_record import (  # noqa: E402
    InvalidPublicationDate, MissingPublicationDate, publication_date_problem, write_record,
)

GENERATED = _REPO / "auxsays" / "updates" / "generated"
REPAIRED = GENERATED / "2026-11-18-netlify-google-gemini-4-neon-now-available-in-ai-gateway-and-agent-runners.md"
PERMALINK = "/updates/netlify/netlify/google-gemini-4-neon-now-available-in-ai-gateway-and-agent-runners/"
ISO = "2026-11-18T00:00:00Z"

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
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERRORS.append(label)


def front(path: Path) -> dict:
    fm, _ = split_front_matter(path.read_text(encoding="utf-8"))
    return yaml.safe_load(fm or "") or {}


def netlify_source() -> dict:
    rows = yaml.safe_load((_REPO / "auxsays" / "_data" / "patch_ingestion_sources.yml").read_text(encoding="utf-8"))
    return next(r for r in rows if r.get("product_id") == "netlify")


class _Page:
    def __init__(self, text: str) -> None:
        self.text = text


def fake_site(pages: dict[str, str]):
    def fetch_text(url, **_kwargs):
        return _Page(pages[url])
    return fetch_text


def run() -> int:
    print("A. the adapter's date conversion")
    check("A1 'November 18, 2026' -> ISO", HC._iso_date("November 18, 2026") == ISO, HC._iso_date("November 18, 2026"))
    check("A2 'Nov 18, 2026' and 'Nov. 18, 2026' -> ISO",
          HC._iso_date("Nov 18, 2026") == ISO and HC._iso_date("Nov. 18, 2026") == ISO)
    check("A3 'Sept 3, 2026' -> 2026-09-03", HC._iso_date("Sept 3, 2026") == "2026-09-03T00:00:00Z")
    check("A4 an ISO date passes through as an instant", HC._iso_date("2026-11-18") == ISO)
    bad = {t: HC._iso_date(t) for t in ("Febtember 3, 2026", "February 30, 2026", "Ma 3, 2026", "Release 3, 2026", "")}
    check("A5 not-a-month, impossible day and ambiguous prefix give '' (never the text)",
          all(v == "" for v in bad.values()), str(bad))
    check("A6 the page-level fallback converts too",
          HC._date_from_html("<p>Changelog</p><p>November 18, 2026</p>") == ISO)

    print("B. the Netlify extractor on the real entry's text (offline)")
    stored = front(REPAIRED) if REPAIRED.exists() else {}
    body = str(stored.get("official_patch_notes_body") or "")
    base = "https://www.netlify.com/changelog/"
    entry = base + "gemini-4-neon-ai-gateway-agent-runners/"
    dated = base + "2026-11-17-connectors-for-agent-runners/"
    detail = ("<html><h1>Google Gemini 4 Neon now available in AI Gateway and Agent Runners</h1>"
              f"<article>{body}</article></html>")
    abbreviated = ("<html><h1>Abbreviated entry</h1><article>All changelog entries Nov 20, 2026 "
                   + "An entry whose lead date is abbreviated. " * 4 + "</article></html>")
    listing = ("<a href='/changelog/gemini-4-neon-ai-gateway-agent-runners/'>B</a>"
               "<a href='/changelog/2026-11-17-connectors-for-agent-runners/'>C</a>"
               "<a href='/changelog/abbreviated-entry/'>D</a>")
    pages = {base: listing, entry: detail, dated: abbreviated.replace("Nov 20", "December 1"),
             base + "abbreviated-entry/": abbreviated}
    source = netlify_source()
    original_fetch = HC.fetch_text
    HC.fetch_text = fake_site(pages)
    try:
        records = HC.fetch(source, limit=5)
    finally:
        HC.fetch_text = original_fetch
    by_url = {r["source_url"]: r for r in records}
    check("B0 the fixture is the stored entry's own body", "November 18, 2026" in body[:400], body[:120])
    check("B1 the slug-only entry gets the ISO date of its article lead",
          by_url.get(entry, {}).get("published_at") == ISO, str(by_url.get(entry, {}).get("published_at")))
    check("B2 a date-slug entry still takes the date its URL states",
          by_url.get(dated, {}).get("published_at") == "2026-11-17T00:00:00Z")
    check("B3 an abbreviated lead date converts",
          by_url.get(base + "abbreviated-entry/", {}).get("published_at") == "2026-11-20T00:00:00Z")
    check("B4 every extracted date satisfies the writer's guard",
          records and all(not publication_date_problem(r) for r in records), str([r["published_at"] for r in records]))

    print("C. the writer's backstop")
    ok = {"2026-11-18": "", ISO: "", "2026-11-18 00:00:00": ""}
    check("C1 ISO date, instant and space form are accepted",
          all(publication_date_problem({"published_at": k}) == "" for k in ok))
    reasons = {v: publication_date_problem({"published_at": v}) for v in ("November 18, 2026", "2026-02-30", "18/11/2026", "")}
    check("C2 text date, impossible date, other order and empty each give a reason",
          all(reasons.values()), str(reasons))
    record = {"record_id": "html:netlify:bad", "company_id": "netlify", "product_id": "netlify", "company": "Netlify",
              "software": "Netlify", "version": "Bad date entry", "title": "Bad date entry",
              "published_at": "November 18, 2026", "source_url": base + "bad-date-entry/", "official_url": base,
              "body": "x" * 100}
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "generated"
        try:
            write_record(out, dict(record))
            raised = None
        except InvalidPublicationDate as exc:
            raised = exc
        check("C3 write_record raises InvalidPublicationDate (a MissingPublicationDate) and writes no file",
              isinstance(raised, MissingPublicationDate) and not list(out.glob("*")), str(raised))

    print("D. patch_ingest refuses the record and keeps the run")
    good = dict(record, record_id="html:netlify:good", version="Good date entry", title="Good date entry",
                published_at="2026-11-19T00:00:00Z", source_url=base + "good-date-entry/")

    class _Adapter:
        @staticmethod
        def fetch(source, limit=3):
            return [dict(record), dict(good)]

    original_module = patch_ingest.adapter_module
    patch_ingest.adapter_module = lambda name: _Adapter
    try:
        for write in (True, False):
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / "generated"
                out.mkdir(parents=True)
                state = {"schema_version": 1, "sources": {}, "seen": {}}
                args = SimpleNamespace(limit=2, output=out, overwrite_existing=False)
                err = io.StringIO()
                try:
                    with contextlib.redirect_stderr(err):
                        result = patch_ingest.run_source(source, args, state, write=write)
                except Exception as exc:  # without the guard the writer's backstop aborts the source
                    result = {"status": f"raised {type(exc).__name__}", "skipped": [], "would_create": None}
                refused = [s for s in result["skipped"] if s.get("reason") == "refused-invalid-publication-date"]
                names = sorted(p.name for p in out.glob("*.md"))
                mode = "write" if write else "dry run"
                check(f"D1 {mode}: the non-ISO record is refused with its reason, the run succeeds",
                      result["status"] == "success" and [s["record_id"] for s in refused] == ["html:netlify:bad"]
                      and "non-ISO" in refused[0].get("detail", ""), str(result["skipped"]))
                check(f"D2 {mode}: the refusal is logged", "refused record html:netlify:bad" in err.getvalue(), err.getvalue())
                if write:
                    check("D3 write: the good record is still written, and only it",
                          names == ["2026-11-19-netlify-good-date-entry.md"], str(names))
                    check("D4 write: the refused record is not marked seen (a fixed adapter creates it later)",
                          not patch_ingest.is_seen(state, "netlify", "html:netlify:bad")
                          and patch_ingest.is_seen(state, "netlify", "html:netlify:good"))
                else:
                    check("D5 dry run: the refused record takes no creation slot",
                          result.get("would_create") == ["html:netlify:good"] and names == [],
                          str(result.get("would_create")))
    finally:
        patch_ingest.adapter_module = original_module

    print("E. re-ingesting the repaired record creates no second page")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "generated"
        out.mkdir(parents=True)
        siblings = [p for p in GENERATED.glob("*-netlify-*.md")]
        for p in siblings:
            shutil.copy2(p, out / p.name)
        before = sorted(p.name for p in out.glob("*.md"))
        state = {"schema_version": 1, "sources": {}, "seen": {}}
        args = SimpleNamespace(limit=5, output=out, overwrite_existing=False)
        HC.fetch_text = fake_site({base: "<a href='/changelog/gemini-4-neon-ai-gateway-agent-runners/'>B</a>",
                                   entry: detail})
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                result = patch_ingest.run_source(source, args, state, write=True)
        finally:
            HC.fetch_text = original_fetch
        after = sorted(p.name for p in out.glob("*.md"))
        refreshed = [r.get("path") for r in result["refreshed"]] + [s.get("path") for s in result["skipped"]]
        check("E1 no file is created; the file set is unchanged", result["written"] == [] and after == before,
              str(sorted(set(after) - set(before))))
        check("E2 the repaired file is the one the run matched",
              any(Path(p).name == REPAIRED.name for p in refreshed if p), str(refreshed))
        check("E3 its update_published_at stays ISO", str(front(out / REPAIRED.name).get("update_published_at")) == ISO)
        with_permalink = [n for n in after if front(out / n).get("permalink") == PERMALINK]
        check("E4 exactly one page carries the permalink", with_permalink == [REPAIRED.name], str(with_permalink))

    print("F. the tracked corpus")
    records = sorted(GENERATED.glob("*.md"))
    bad_names = [p.name for p in records if not p.name[:10].replace("-", "").isdigit() or p.name[10:11] != "-"]
    check("F1 every generated record's filename starts YYYY-MM-DD-", not bad_names, str(bad_names[:5]))
    bad_dates = []
    for p in records:
        fm = front(p)
        if fm.get("update_entry") and publication_date_problem({"published_at": fm.get("update_published_at")}):
            bad_dates.append(p.name)
    check("F2 every generated record's update_published_at is ISO", not bad_dates, str(bad_dates[:5]))
    owners = [p.name for p in records if f"permalink: {PERMALINK}" in p.read_text(encoding="utf-8")]
    check("F3 the repaired page exists exactly once, under its ISO filename", owners == [REPAIRED.name], str(owners))
    check("F4 its front matter carries the ISO date and the original permalink",
          str(stored.get("update_published_at")) == ISO and stored.get("permalink") == PERMALINK
          and str((stored.get("status_events") or [{}])[0].get("at")) == ISO)
    with tempfile.TemporaryDirectory() as td:
        broken = Path(td) / "generated" / "November 1-netlify-x.md"
        broken.parent.mkdir(parents=True)
        broken.write_text(REPAIRED.read_text(encoding="utf-8").replace(f"update_published_at: '{ISO}'",
                                                                       "update_published_at: November 18, 2026"),
                          encoding="utf-8")
        errors, warnings = qa_patch_records.scan_record(broken)
        _, clean_warnings = qa_patch_records.scan_record(REPAIRED)
        check("F5 QA warns (never errors) on a non-ISO record, and not on the repaired one",
              any(w.get("code") == "non_iso_publication_date" for w in warnings)
              and not any(e.get("code") == "non_iso_publication_date" for e in errors)
              and not any(w.get("code") == "non_iso_publication_date" for w in clean_warnings),
              str([w.get("code") for w in warnings]))

    total = _PASS + _FAIL
    print(f"\nResults: {_PASS}/{total} passed, {_FAIL} failed")
    for label in _ERRORS:
        print(f"  - {label}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
