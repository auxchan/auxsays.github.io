#!/usr/bin/env python3
"""Patch pages link community reports by source, date and issue, never by the reporter's title.

Three lists on a patch page link to community reports: the confirmed "User Reports / Sources" list
(including its evidence-samples fallback), the Level 2 "Update-linked user reports" card and the
Level 3 "Recent reports" card. Each used to print the thread title the source's author wrote as the
link text. Each now prints a descriptor AUXSAYS composes from its own stored fields -- source name,
report date and the AUXSAYS issue label -- and says "issue not classified" / "date not recorded"
rather than inventing either. Links, dates, counts, the counted / not-counted framing and the
provenance line are unchanged. This is display only: no evidence, record or `_data` file changes.

    S  the shipped layout's emitting markup reads no title field on the three lists
    R  the SHIPPED layout rendered with the liquid gem over FROZEN SYNTHETIC fixtures: every link
       keeps its URL, no stored title of 20+ characters appears anywhere in the page (text or
       attribute), the descriptor carries source, date and issue, and the counts and framing hold;
       a confirmed source with no issue label reads "issue not classified" even when its
       workflow_area, theme, outcome and classification are set (one named check per field)
    A  attributes and accessible names
    N  non-vacuity: the detector finds a planted title, the same layout with the old link text
       put back exposes the titles on all three surfaces, and a neutral branch that prints the
       sibling fields exposes all four
    W  WARN-ONLY diagnostic: the real records rendered through the shipped layout, reporting any
       stored title still present. It never fails and never adds a check, so evidence growth
       cannot change this suite's governed count.

Needs ruby + the liquid gem, like the other render suites. Without them L1 fails and every render
check fails with it, rather than skipping.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_publication_title_minimisation.py
"""
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from html.parser import HTMLParser
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"
UPDATE_LAYOUT = _AUX / "_layouts" / "aux-update.html"
MIN_TITLE = 20
NL = chr(10)

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
        print(f"  FAIL  {label}" + (f"{NL}        {detail}" if detail else ""))


# --------------------------------------------------------------------------- rendering

_RENDER_RB = r"""
require 'liquid'
require 'json'

module Shims
  def relative_url(i) = "/" + i.to_s.sub(%r{\A/}, "")
  def absolute_url(i) = "https://auxsays.test/" + i.to_s.sub(%r{\A/}, "")
  def jsonify(i) = JSON.generate(i)
  def markdownify(i) = i.to_s
  # Jekyll's `where`, as the other render harnesses shim it: string comparison of the property.
  def where(input, property, value)
    input = input.values if input.is_a?(Hash)
    return input unless input.respond_to?(:select)
    input.select { |item| item.is_a?(Hash) && item[property].to_s == value.to_s }
  end
end
Liquid::Template.register_filter(Shims)

payload = JSON.parse(File.read(ARGV[0]))
tpl = Liquid::Template.parse(payload['template'])
out = payload['pages'].map do |page|
  begin
    tpl.render!({ 'site' => payload['site'], 'page' => page, 'content' => '' })
  rescue => e
    "<<ERR: #{e.class}: #{e.message}>>"
  end
end
print JSON.generate(out)
"""


def layout_source(path: Path = UPDATE_LAYOUT) -> str:
    """The layout body as Jekyll renders it, minus what needs a file system or a plugin.

    Includes are removed (none of them renders a report title; they need a file system), exactly as
    the other render harnesses here do."""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[-1]
    text = re.sub(r"\{%-?\s*include\s.*?-?%\}", "", text, flags=re.S)
    return re.sub(r"\{%-?\s*seo\s*-?%\}", "", text)


def render(template: str, site: dict, pages: list[dict]) -> tuple[list[str] | None, str]:
    """-> (one html string per page, '') or (None, reason). One ruby process for the whole batch."""
    ruby = shutil.which("ruby")
    if not ruby:
        return None, "ruby is not on PATH"
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "render.rb"
        script.write_text(_RENDER_RB, encoding="utf-8")
        payload = Path(td) / "payload.json"
        payload.write_text(json.dumps({"template": template, "site": site, "pages": pages}, default=str),
                           encoding="utf-8")
        try:
            proc = subprocess.run([ruby, str(script), str(payload)], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=600)
        except subprocess.TimeoutExpired:
            return None, "ruby render timed out"
    if proc.returncode != 0 or not proc.stdout.strip():
        return None, (proc.stderr or "")[-400:]
    try:
        return json.loads(proc.stdout), ""
    except ValueError as exc:
        return None, f"unreadable ruby output: {exc}"


# --------------------------------------------------------------------------- detection

def norm(text: str) -> str:
    return " ".join(str(text or "").split())


def visible(page_html: str) -> str:
    """Rendered HTML with entities decoded, so an escaped title is found as readily as a raw one."""
    return norm(html.unescape(page_html or ""))


def titles_found(page_html: str, titles) -> list[str]:
    hay = visible(page_html)
    raw = norm(page_html)
    return sorted({t for t in titles if len(norm(t)) >= MIN_TITLE and (norm(t) in hay or norm(t) in raw)})


class _Links(HTMLParser):
    """Every <a>, with its attributes and its text, plus every attribute value on the page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict] = []
        self.attr_values: list[str] = []
        self._open: list[dict] = []

    def handle_starttag(self, tag, attrs):
        for _name, value in attrs:
            if value:
                self.attr_values.append(value)
        if tag == "a":
            link = {"attrs": dict(attrs), "text": ""}
            self.links.append(link)
            self._open.append(link)

    def handle_endtag(self, tag):
        if tag == "a" and self._open:
            self._open.pop()

    def handle_data(self, data):
        for link in self._open:
            link["text"] += data


def parse_links(page_html: str) -> _Links:
    parser = _Links()
    parser.feed(page_html or "")
    for link in parser.links:
        link["text"] = norm(link["text"])
    return parser


def section(page_html: str, start_marker: str, end_marker: str) -> str:
    i = (page_html or "").find(start_marker)
    if i < 0:
        return ""
    j = page_html.find(end_marker, i)
    return page_html[i:j if j > 0 else len(page_html)]


def sources_section(h: str) -> str:
    """The confirmed-sources list only (the official-sources list below it is not a report list)."""
    return section(h, 'class="update-source-list update-source-list--accepted"', "</ul>")


def tier2_section(h: str) -> str:
    return section(h, 'class="update-linked-card"', "</section>")


def l3_section(h: str) -> str:
    return section(h, 'class="recent-reports-card"', "</section>")


# --------------------------------------------------------------------------- frozen fixtures
# Every title below is a SYNTHETIC stand-in for a source-authored title: distinctive, 20+ characters,
# and including the characters an escaping bug would expose (quotes, ampersand, angle brackets).

T = {
    "full": "SYNTHETIC TITLE one: the taskbar vanished after the cumulative patch",
    "nodate": "SYNTHETIC TITLE two: render queue freezes at ninety percent",
    "noissue": "SYNTHETIC TITLE three: scene switcher drops the camera source",
    "nourl": "SYNTHETIC TITLE four: printing to PDF hangs on the second page",
    "noname": "SYNTHETIC TITLE five: Bluetooth audio stutters since this morning",
    "markup": 'SYNTHETIC TITLE six: "quoted" & <b>marked up</b> text stays out',
    "theme": "SYNTHETIC TITLE seven: stored under issue_theme instead of issue",
    "sample_a": "SYNTHETIC SAMPLE TITLE alpha: export dialog closes itself",
    "sample_b": "SYNTHETIC SAMPLE TITLE beta: no label stored for this sample",
    "t2_a": "SYNTHETIC L2 TITLE alpha: slide show stops on the third slide",
    "t2_b": "SYNTHETIC L2 TITLE beta: embedded video plays without sound",
    "t2_other": "SYNTHETIC L2 TITLE for another patch: must not render here",
    "ac2": "SYNTHETIC ACROBAT L2 TITLE: signature panel greys out",
}
T["sib_empty"] = "SYNTHETIC TITLE eight: empty issue label beside other fields"
T["sib_absent"] = "SYNTHETIC TITLE nine: no issue key at all beside other fields"
for i in range(1, 11):
    T[f"l3_{i}"] = f"SYNTHETIC L3 TITLE number {i:02d}: a slide master stops saving"
for i in range(1, 4):
    T[f"ac3_{i}"] = f"SYNTHETIC ACROBAT L3 TITLE number {i}: the print preview stays empty"

WIN_PAGE = {
    "layout": "aux-update", "title": "Windows 11 25H2 (synthetic)", "product_id": "microsoft-windows-11",
    "update_product": "Windows 11", "update_version": "25H2", "target_build": "26200.9999",
    "update_published_at": "2026-10-13T00:00:00Z", "update_report_count": 7,
    "confirmed_patch_specific_report_count": 7, "update_source_url": "https://example.test/notes",
    "accepted_report_sources": [
        {"source_name": "Microsoft Learn Q&A", "source_type": "microsoft_learn_qna", "source_date": "2026-10-03",
         "source_url": "https://example.test/q/full", "source_title": T["full"],
         "issue": "update/install failure in windows update", "workflow_area": "windows update"},
        {"source_name": "r/davinciresolve", "source_type": "reddit_community_report",
         "source_url": "https://example.test/q/nodate", "source_title": T["nodate"],
         "issue": "render/export failures", "workflow_area": "render export"},
        {"source_name": "OBS Project Support Forum", "source_type": "obs_forum_thread", "source_date": "2026-10-05",
         "source_url": "https://example.test/q/noissue", "source_title": T["noissue"], "issue": "",
         "workflow_area": ""},
        {"source_name": "Adobe Community Bug Report", "source_type": "adobe_community_bug_report",
         "source_date": "2026-10-06", "source_title": T["nourl"], "issue": "printing regression"},
        {"source_type": "microsoft_tech_community", "source_date": "2026-10-07",
         "source_url": "https://example.test/q/noname", "source_title": T["noname"],
         "issue": "audio regression"},
        {"source_name": "Super User", "source_type": "stack_exchange_question", "source_date": "2026-10-08",
         "source_url": "https://example.test/q/markup", "source_title": T["markup"],
         "issue": "display regression"},
        {"source_name": "obsproject/obs-studio", "source_type": "github_issue", "source_date": "2026-10-09",
         "source_url": "https://example.test/q/theme", "title": T["theme"],
         "issue_theme": "crash or hang"},
    ],
}
SAMPLES_PAGE = {
    "layout": "aux-update", "title": "OBS Studio 99.0 (synthetic)", "product_id": "obs-studio",
    "update_product": "OBS Studio", "update_version": "99.0", "update_published_at": "2026-10-01T00:00:00Z",
    "update_report_count": 2, "confirmed_patch_specific_report_count": 2,
    "evidence_samples": [
        {"source_name": "OBS Project Support Forum", "source_url": "https://example.test/s/a",
         "source_title": T["sample_a"], "counted": True, "issue": "output or recording regressions"},
        {"source_name": "obsproject/obs-studio", "source_url": "https://example.test/s/b",
         "source_title": T["sample_b"], "counted": True, "issue": ""},
    ],
}
# "Never invent an issue" on the confirmed-sources list, pinned against the fields that sit beside the
# label. Both rows carry NO issue label (one empty, one with the key missing) but distinctive values in
# every sibling field a template could be tempted to fall back on. Each value has its own marker word,
# so a leak is attributed to the one field it came from.
SIBLING_FIELDS = {"workflow_area": "kestrel", "theme": "osprey", "outcome": "plover", "classification": "merlin"}
SIBLING_VALUES = {field: f"{word} {field.replace('_', ' ')} value" for field, word in SIBLING_FIELDS.items()}
SIBLING_PAGE = {
    "layout": "aux-update", "title": "OBS Studio 98.0 (synthetic)", "product_id": "obs-studio",
    "update_product": "OBS Studio", "update_version": "98.0", "update_published_at": "2026-10-02T00:00:00Z",
    "update_report_count": 2, "confirmed_patch_specific_report_count": 2,
    "accepted_report_sources": [
        {"source_name": "OBS Project Support Forum", "source_type": "obs_forum_thread", "source_date": "2026-10-11",
         "source_url": "https://example.test/sib/empty", "source_title": T["sib_empty"], "issue": "",
         **SIBLING_VALUES},
        {"source_name": "obsproject/obs-studio", "source_type": "github_issue", "source_date": "2026-10-12",
         "source_url": "https://example.test/sib/absent", "source_title": T["sib_absent"], **SIBLING_VALUES},
    ],
}
SIBLING_EXPECTED = ["OBS Project Support Forum report, October 11, 2026: issue not classified",
                    "obsproject/obs-studio report, October 12, 2026: issue not classified"]
# The confirmed-sources neutral branch, and a control that prints every sibling field there instead.
S1_NEUTRAL = "{% else %}issue not classified{% endif %}{% endcapture %}"
S1_SIBLING_CONTROL = ("{% else %}{{ source.workflow_area }} {{ source.theme }} {{ source.outcome }} "
                      "{{ source.classification }}{% endif %}{% endcapture %}")

PPT_KEY = "microsoft-powerpoint|2699|20399.20100"
PPT_PAGE = {
    "layout": "aux-update", "title": "PowerPoint 2699 (synthetic)", "product_id": "microsoft-powerpoint",
    "update_product": "Microsoft PowerPoint", "update_version": "2699", "target_build": "20399.20100",
    "update_published_at": "2026-10-20T00:00:00Z", "update_report_count": 0,
    "confirmed_patch_specific_report_count": 0,
}
ACRO_KEY = "adobe-acrobat-reader|26.009.20001|26.009.20001"
ACRO_PAGE = {
    "layout": "aux-update", "title": "Acrobat Reader 26.009.20001 (synthetic)", "product_id": "adobe-acrobat-reader",
    "update_product": "Adobe Acrobat Reader", "update_version": "26.009.20001",
    "update_published_at": "2026-10-14T00:00:00Z", "update_report_count": 0,
    "confirmed_patch_specific_report_count": 0,
}
SITE = {
    "title": "AUXSAYS", "time": "2026-11-05T00:00:00Z",
    "data": {
        "evidence_method_health": {"methods": []}, "patch_companies": [], "patch_products": [],
        "patch_verdicts": {},
        "update_linked_evidence": {"reports": [
            {"associated_patch_key": PPT_KEY, "report_title": T["t2_a"], "source_url": "https://example.test/t2/a",
             "source_family": "Microsoft Q&A", "report_date": "2026-10-30", "issue_summary": "slideshow failure",
             "update_link_signal": "explicit_update_attribution", "classification": "update_linked"},
            {"associated_patch_key": PPT_KEY, "report_title": T["t2_b"], "source_url": "https://example.test/t2/b",
             "source_family": "Super User / Stack Exchange", "report_date": "2026-10-31",
             "association_basis": "report_date_inside_release_window", "classification": "update_linked"},
            {"associated_patch_key": "microsoft-powerpoint|2698|20398.20000", "report_title": T["t2_other"],
             "source_url": "https://example.test/t2/other", "source_family": "Microsoft Q&A",
             "report_date": "2026-09-30", "classification": "update_linked"},
        ]},
        "recent_powerpoint_reports": {"reports": [
            {"release_window_key": PPT_KEY, "report_title": T[f"l3_{i}"],
             "source_url": f"https://example.test/l3/{i}", "source_family": "Microsoft Q&A",
             "report_date": f"2026-10-{20 + i:02d}", "window_version": "2699", "window_build": "20399.20100",
             "window_start": "2026-10-20"} for i in range(1, 11)]},
        "acrobat_update_linked_evidence": {"reports": [
            {"associated_patch_key": ACRO_KEY, "report_title": T["ac2"], "source_url": "https://example.test/ac2/1",
             "source_family": "adobe community bug report", "report_date": "2026-10-16",
             "update_link_reason": "update_named_as_cause", "classification": "update_linked"}]},
        "recent_acrobat_reports": {"reports": [
            {"release_window_key": ACRO_KEY, "report_title": T[f"ac3_{i}"],
             "source_url": f"https://example.test/ac3/{i}", "source_family": "adobe community bug report",
             "report_date": f"2026-10-1{4 + i}", "window_version": "26.009.20001",
             "window_build": "26.009.20001", "window_start": "2026-10-14"} for i in range(1, 4)]},
    },
}
PAGES = [WIN_PAGE, SAMPLES_PAGE, PPT_PAGE, ACRO_PAGE, SIBLING_PAGE]
ALL_TITLES = sorted(set(T.values()))

# The link-text expressions of the three surfaces before this change, for the N control.
OLD_LINK_TEXT = {
    "sources": ("{{ source_link_text | strip | escape }}</a>",
                "{{ source.source_title | default: source.title }}</a>"),
    "tier2": ('target="_blank">{{ r_link_text | strip | escape }}</a>\n              <span class="update-linked-item__meta">',
              'target="_blank">{{ r.report_title | escape_once }}</a>\n              <span class="update-linked-item__meta">'),
    "l3": ('target="_blank">{{ r_link_text | strip | escape }}</a>\n              <span class="recent-reports-item__meta">',
           'target="_blank">{{ r.report_title | escape_once }}</a>\n              <span class="recent-reports-item__meta">'),
}

DATE_PART_RE = re.compile(r", (?:(?:January|February|March|April|May|June|July|August|September|October|November|"
                          r"December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{1,2}, \d{4}|date not recorded): \S")


def emitting(src: str) -> str:
    return re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "", src, flags=re.S)


# --------------------------------------------------------------------------- W: real-record diagnostic

def _front_matter(path: Path):
    import yaml  # noqa: PLC0415 -- only the diagnostic needs it
    text = path.read_text(encoding="utf-8")
    m = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m:
        return None
    data = yaml.load(m.group(1), Loader=yaml.SafeLoader)
    return data if isinstance(data, dict) else None


def real_record_diagnostic(layout: Path = UPDATE_LAYOUT, aux_root: Path = _AUX, limit_lines: int = 25) -> dict:
    """Render every record that has something to link through `layout` and look for stored titles.

    WARN-only by contract: returns a summary and prints WARN lines; it never calls check()."""
    import yaml  # noqa: PLC0415
    started = time.monotonic()
    data_dir = aux_root / "_data"

    def load(name: str, default):
        path = data_dir / name
        if not path.is_file():
            return default
        return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.SafeLoader) or default

    tiers = {name: load(f"{name}.yml", {"reports": []}) for name in (
        "update_linked_evidence", "recent_powerpoint_reports", "acrobat_update_linked_evidence",
        "recent_acrobat_reports")}
    site = {"title": "AUXSAYS", "time": "2026-11-05T00:00:00Z", "data": {
        **tiers, "evidence_method_health": {"methods": []},
        "patch_companies": load("patch_companies.yml", []), "patch_products": load("patch_products.yml", []),
        "patch_verdicts": load("patch_verdicts.yml", {})}}
    tier_keys = {}
    for name, payload in tiers.items():
        for row in (payload or {}).get("reports") or []:
            key = str(row.get("associated_patch_key") or row.get("release_window_key") or "")
            if key and len(norm(row.get("report_title"))) >= MIN_TITLE:
                tier_keys.setdefault(key, set()).add(norm(row.get("report_title")))
    store = load("consensus_evidence.yml", {"evidence": []})
    store_rows = store.get("evidence", []) if isinstance(store, dict) else (store or [])
    store_titles: dict[tuple[str, str], set[str]] = {}
    for row in store_rows:
        k = (str(row.get("product_id") or ""), str(row.get("update_version") or ""))
        for field in ("report_title", "parent_title", "listing_card_title"):
            t = norm(row.get(field))
            if len(t) >= MIN_TITLE:
                store_titles.setdefault(k, set()).add(t)

    pages, page_titles, names = [], [], []
    for path in sorted((aux_root / "updates" / "generated").glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        maybe_tier = ("microsoft-powerpoint" in raw or "acrobat" in raw)
        if "source_title:" not in raw and not maybe_tier:
            continue
        try:
            fm = _front_matter(path)
        except Exception:  # noqa: BLE001
            fm = None
        if not fm:
            continue
        build = str(fm.get("target_build") or "")
        if "acrobat" in str(fm.get("product_id") or ""):
            build = str(fm.get("update_version") or "")
        key = f"{fm.get('product_id')}|{fm.get('update_version')}|{build}"
        own = {norm(s.get("source_title") or s.get("title")) for s in
               (fm.get("accepted_report_sources") or []) + (fm.get("evidence_samples") or [])
               if isinstance(s, dict)}
        own = {t for t in own if len(t) >= MIN_TITLE}
        tier = tier_keys.get(key, set())
        if not own and not tier:
            continue
        stored = store_titles.get((str(fm.get("product_id") or ""), str(fm.get("update_version") or "")), set())
        pages.append(fm)
        page_titles.append((own, tier, stored))
        names.append(path.name)

    out = {"pages": len(pages), "rendered": 0, "errors": 0, "pages_with_titles": 0,
           "by_surface": {"sources": 0, "tier2": 0, "l3": 0, "elsewhere": 0}, "warn_lines": 0}
    if not pages:
        return out
    rendered, why = render(layout_source(layout), site, pages)
    if rendered is None:
        print(f"  WARN  W diagnostic could not render: {why}")
        out["errors"] = len(pages)
        return out
    for name, page_html, (own, tier, stored) in zip(names, rendered, page_titles):
        if page_html.startswith("<<ERR"):
            out["errors"] += 1
            continue
        out["rendered"] += 1
        found = titles_found(page_html, own | tier | stored)
        if not found:
            continue
        out["pages_with_titles"] += 1
        parts = {"sources": sources_section(page_html), "tier2": tier2_section(page_html),
                 "l3": l3_section(page_html)}
        for title in found:
            where = next((s for s, part in parts.items() if titles_found(part, [title])), "elsewhere")
            out["by_surface"][where] += 1
            if out["warn_lines"] < limit_lines:
                # The page and surface only: the title itself is not reprinted into the CI log.
                print(f"  WARN  W stored title still rendered: {name} [{where}] ({len(title)} chars)")
                out["warn_lines"] += 1
    out["seconds"] = round(time.monotonic() - started, 1)
    return out


# --------------------------------------------------------------------------- the suite

def run() -> int:  # noqa: PLR0915
    print("=" * 78)
    print("Patch pages: community reports linked by source, date and issue (D1)")
    print("=" * 78)
    src = UPDATE_LAYOUT.read_text(encoding="utf-8")
    body = emitting(src)

    # ---- S: static -----------------------------------------------------------------------
    title_fields = ("source_title", "source.title", "report_title", "parent_title", "listing_card_title",
                    "report_excerpt", "report_text_excerpt")
    check("S1 the layout's emitting markup reads no source-authored title or excerpt field",
          not [f for f in title_fields if f in body], str([f for f in title_fields if f in body]))
    check("S2 each of the three lists still links its source URL",
          '<a href="{{ source_url_clean }}">' in body and body.count('href="{{ r.source_url }}"') == 2)
    check("S3 the link text of all three lists is the composed descriptor",
          body.count("{{ source_link_text | strip | escape }}") == 2
          and body.count("{{ r_link_text | strip | escape }}") == 2)

    # ---- render the fixtures, plus the N control (old link text restored) -----------------
    template = layout_source()
    control = template
    swapped = 0
    for new, old in OLD_LINK_TEXT.values():
        n = control.count(new)
        swapped += n
        control = control.replace(new, old)
    rendered, why = render(template, SITE, PAGES)
    control_rendered, control_why = render(control, SITE, PAGES) if swapped else (None, "nothing to swap")
    print()
    check("L1 the liquid gem is available and the shipped layout renders every fixture page",
          rendered is not None and not any(h.startswith("<<ERR") for h in rendered),
          why or str([h[:200] for h in (rendered or []) if h.startswith("<<ERR")]))
    win, samples, ppt, acro, sib = (rendered or [""] * len(PAGES))[:5]

    # ---- R: confirmed sources -------------------------------------------------------------
    src_links = [ln for ln in parse_links(sources_section(win)).links]
    hrefs = [ln["attrs"].get("href") for ln in src_links]
    check("R1 every confirmed source with a URL is still linked to that exact URL, and only those",
          hrefs == ["https://example.test/q/full", "https://example.test/q/nodate", "https://example.test/q/noissue",
                    "https://example.test/q/noname", "https://example.test/q/markup", "https://example.test/q/theme"],
          str(hrefs))
    check("R2 no stored title (20+ chars) appears anywhere in the rendered page, raw or escaped",
          bool(win) and not titles_found(win, ALL_TITLES), str(titles_found(win, ALL_TITLES)))
    texts = [ln["text"] for ln in src_links]
    check("R3 the descriptor is source, date and AUXSAYS issue label",
          bool(texts) and texts[0] == "Microsoft Learn Q&A report, October 3, 2026: update/install failure in windows update",
          str(texts[:1]))
    check("R4 a source with no date says so instead of printing an empty date",
          len(texts) > 1 and texts[1] == "r/davinciresolve report, date not recorded: render/export failures"
          and "()" not in sources_section(win), str(texts[1:2]))
    check("R5 a source with no issue label gets a neutral descriptor, never an invented issue",
          len(texts) > 2 and texts[2] == "OBS Project Support Forum report, October 5, 2026: issue not classified",
          str(texts[2:3]))
    plain = visible(sources_section(win))
    check("R6 a source with no URL renders the descriptor as plain text, never an empty href",
          'href=""' not in win and "Adobe Community Bug Report, October 6, 2026: printing regression." in plain,
          plain[:300])
    check("R7 a source with no name reads 'Community report', with no stray separator",
          len(texts) > 3 and texts[3] == "Community report, October 7, 2026: audio regression"
          and not re.search(r"<cite>\s*[.,]", win), str(texts[3:4]))
    check("R8 a source name that already ends in 'report' is not doubled",
          "report report" not in plain.lower() and "Report report" not in plain)
    check("R9 the legacy `title` key and `issue_theme` label are read like the current ones",
          len(texts) > 5 and texts[5] == "obsproject/obs-studio report, October 9, 2026: crash or hang", str(texts[5:6]))
    check("R10 the source type and workflow lines still render, and the count is unchanged",
          "<span>microsoft learn qna</span>" in win and "<small>Workflow: windows update</small>" in win
          and '<span class="update-sources-count">(7)</span>' in win)
    s_links = parse_links(sources_section(samples)).links
    check("R11 the evidence-samples fallback links its samples by descriptor, never by title",
          [ln["attrs"].get("href") for ln in s_links] == ["https://example.test/s/a", "https://example.test/s/b"]
          and [ln["text"] for ln in s_links] == [
              "OBS Project Support Forum report, date not recorded: output or recording regressions",
              "obsproject/obs-studio report, date not recorded: issue not classified"]
          and not titles_found(samples, ALL_TITLES), str([ln["text"] for ln in s_links]))

    # ---- R: Level 2 -----------------------------------------------------------------------
    t2 = tier2_section(ppt)
    t2_links = parse_links(t2).links
    check("R12 Level 2 links each update-linked report to its URL with the descriptor",
          [ln["attrs"].get("href") for ln in t2_links] == ["https://example.test/t2/a", "https://example.test/t2/b"]
          and [ln["text"] for ln in t2_links] == ["Microsoft Q&A report, Oct 30, 2026: slideshow failure",
                                                  "Super User / Stack Exchange report, Oct 31, 2026: issue not classified"],
          str([ln["text"] for ln in t2_links]))
    check("R13 Level 2 keeps both counts and the not-counted framing",
          "<dt>Update-linked reports</dt>" in t2 and re.search(r"<dt>Update-linked reports</dt>\s*<dd>2</dd>", t2)
          and "<dt>Confirmed patch-specific reports</dt>" in t2 and "<strong>not</strong> counted" in t2)
    check("R14 Level 2 keeps the source line with its machine-readable date",
          '<time datetime="2026-10-30">' in t2 and "Microsoft Q&amp;A &middot;" in t2)

    # ---- R: Level 3 -----------------------------------------------------------------------
    l3 = l3_section(ppt)
    l3_links = parse_links(l3).links
    check("R15 Level 3 shows 8 of 10, each linked to its URL by a neutral descriptor",
          len(l3_links) == 8 and [ln["attrs"].get("href") for ln in l3_links][:1] == ["https://example.test/l3/1"]
          and all(ln["text"].endswith(": issue not classified") and ln["text"].startswith("Microsoft Q&A report, Oct ")
                  for ln in l3_links)
          and '<span class="recent-reports-card__count">10</span>' in l3 and "Showing 8 of 10" in l3,
          str([ln["text"] for ln in l3_links][:2]))
    check("R16 Level 3 keeps 'Not attributed' and 'Patch attribution: not established'",
          "Not attributed to this update." in l3 and "Patch attribution: not established." in l3)
    check("R17 no Level 2 or Level 3 title renders on the PowerPoint page, including another patch's",
          bool(ppt) and not titles_found(ppt, ALL_TITLES), str(titles_found(ppt, ALL_TITLES)))

    # ---- R: Acrobat's own tier files -------------------------------------------------------
    a2 = parse_links(tier2_section(acro)).links
    a3 = parse_links(l3_section(acro)).links
    check("R18 Acrobat's Level 2 and Level 3 link by descriptor, with no doubled 'report'",
          [ln["text"] for ln in a2] == ["adobe community bug report, Oct 16, 2026: issue not classified"]
          and len(a3) == 3 and all(ln["text"].startswith("adobe community bug report, Oct 1") for ln in a3)
          and [ln["attrs"].get("href") for ln in a2] == ["https://example.test/ac2/1"],
          str([ln["text"] for ln in a2 + a3]))
    check("R19 no Acrobat title renders",
          bool(acro) and not titles_found(acro, ALL_TITLES), str(titles_found(acro, ALL_TITLES)))

    # ---- R: confirmed sources never invent an issue from the fields beside the label ----------
    sib_links = parse_links(sources_section(sib)).links
    check("R20 a confirmed source with an empty or missing issue label reads 'issue not classified', even "
          "with workflow_area, theme, outcome and classification set",
          [ln["attrs"].get("href") for ln in sib_links] == ["https://example.test/sib/empty", "https://example.test/sib/absent"]
          and [ln["text"] for ln in sib_links] == SIBLING_EXPECTED and bool(sib) and not titles_found(sib, ALL_TITLES),
          str([ln["text"] for ln in sib_links]))

    def sibling_leaks(field: str) -> list[str]:
        """Link texts or accessible-name attributes of the unlabelled rows that carry `field`'s marker."""
        word = SIBLING_FIELDS[field]
        names = [v for ln in sib_links for v in (ln["text"], ln["attrs"].get("aria-label") or "",
                                                 ln["attrs"].get("title") or "")]
        return [v for v in names if word in v.lower()]

    check("R21 ... its link text and accessible name never carry the workflow_area",
          len(sib_links) == 2 and not sibling_leaks("workflow_area"), str(sibling_leaks("workflow_area")))
    check("R22 ... never the theme", len(sib_links) == 2 and not sibling_leaks("theme"), str(sibling_leaks("theme")))
    check("R23 ... never the outcome", len(sib_links) == 2 and not sibling_leaks("outcome"), str(sibling_leaks("outcome")))
    check("R24 ... never the classification",
          len(sib_links) == 2 and not sibling_leaks("classification"), str(sibling_leaks("classification")))

    # ---- A: attributes and accessible names --------------------------------------------------
    leaked_attrs = [v for h in (rendered or []) for v in parse_links(h).attr_values
                    if any(norm(t) in norm(v) for t in ALL_TITLES)]
    check("A1 no attribute value (title, aria-label, data-*, href, alt) carries a stored title",
          bool(rendered) and not leaked_attrs, str(leaked_attrs[:3]))
    report_links = (src_links + s_links + t2_links + l3_links + a2 + a3 + sib_links)
    check("A2 every report link's accessible name carries a date (or 'date not recorded') and an issue",
          len(report_links) == 24 and all(DATE_PART_RE.search(ln["text"]) for ln in report_links),
          str([ln["text"] for ln in report_links if not DATE_PART_RE.search(ln["text"])][:3]))
    check("A3 no report link has an aria-label or title attribute that could differ from its text",
          not [ln for ln in report_links if "aria-label" in ln["attrs"] or "title" in ln["attrs"]])

    # ---- N: non-vacuity ------------------------------------------------------------------------
    planted = f'<p>x</p><a href="/q" aria-label="{html.escape(T["markup"], quote=True)}">y</a>'
    check("N1 the detector finds a title planted only in an attribute, HTML-escaped",
          titles_found(planted, [T["markup"]]) == [T["markup"]])
    cw = (control_rendered or [""] * 4)
    check("N2 CONTROL: the old link text put back exposes the confirmed-source titles",
          swapped == 3 and T["full"] in titles_found(sources_section(cw[0]), ALL_TITLES)
          and T["sample_a"] in titles_found(sources_section(cw[1]), ALL_TITLES), control_why or f"swapped {swapped}")
    check("N3 CONTROL: ... and the Level 2 titles",
          T["t2_a"] in titles_found(tier2_section(cw[2]), ALL_TITLES)
          and T["ac2"] in titles_found(tier2_section(cw[3]), ALL_TITLES))
    check("N4 CONTROL: ... and the Level 3 titles",
          T["l3_1"] in titles_found(l3_section(cw[2]), ALL_TITLES)
          and T["ac3_1"] in titles_found(l3_section(cw[3]), ALL_TITLES))
    # R21-R24 are only as good as their fixture: a neutral branch that prints the sibling fields must
    # put every one of the four marker words into the unlabelled rows' link text.
    sib_control = template.replace(S1_NEUTRAL, S1_SIBLING_CONTROL, 1) if template.count(S1_NEUTRAL) == 1 else ""
    sib_rendered, sib_why = render(sib_control, SITE, [SIBLING_PAGE]) if sib_control else (None, "neutral branch not found once")
    sib_control_texts = [ln["text"].lower() for ln in parse_links(sources_section((sib_rendered or [""])[0])).links]
    check("N5 CONTROL: a neutral branch that prints the sibling fields exposes all four in the link text",
          len(sib_control_texts) == 2
          and all(word in text for text in sib_control_texts for word in SIBLING_FIELDS.values()),
          sib_why or str(sib_control_texts))

    # ---- W: real records, WARN only ------------------------------------------------------------
    print()
    print("W  real records through the shipped layout (WARN only; never a check)")
    try:
        summary = real_record_diagnostic()
        print(f"  W summary: {json.dumps(summary, sort_keys=True)}")
    except Exception as exc:  # noqa: BLE001 -- a diagnostic must not turn a suite red
        print(f"  WARN  W diagnostic did not run: {type(exc).__name__}: {exc}")

    print()
    print("=" * 78)
    for e in _ERRORS:
        print(f"  - {e}")
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
