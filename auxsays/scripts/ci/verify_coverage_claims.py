#!/usr/bin/env python3
"""Refuse to publish a coverage claim the coverage projection does not support (AUX-102).

WHY. Catalog inclusion was never coupled to collection. A product entered `patch_products.yml` with
a hand-written "Monitoring active", its company page said it "is tracked by AUXSAYS", its product page
said it "is tracked for ... public release signals", and none of that was true for 30 of 47 products
(NVIDIA among them). The pills had already been fixed (AUX-039); nothing stopped the prose, the
catalog fields or the next new product from saying it again.

ONLY TEXT AUXSAYS WROTE CAN BLOCK A DEPLOY. Product, company and hub pages also render vendor-written
text (record titles in the history and latest-signals tables, feed cards), and vendors write ordinary
English: a changelog titled "Monitoring active sessions in the audit log" is not a coverage claim. A
first version scanned the whole visible page, so one such title would have failed every deploy until
someone intervened, and a lane going stale at runtime would have brought its pages' record titles into
the scan. So the phrase rules read only the template's own coverage prose, which the layouts mark with
`data-coverage-prose` (status line, stat card, Coverage section, tracking-rules lines, the hub's radar
head), the page's own meta description (written in the page's front matter, and what a search result
shows), and the catalog text, which is reviewed and checked as data. The fallback rule reads pill
markup, never text. The templates are also guarded statically (test_coverage_governance G3).

WHAT IT CHECKS. ERROR blocks the deploy; WARN is printed and never blocks.
  CATALOG    ERROR  `patch_products.yml` / `patch_companies.yml` carry none of the retired static
                    coverage fields (coverage_state, coverage_status_label, ingestion_status,
                    current_status_label, ingestion_active, dossier_note): coverage is derived, never
                    written by hand.
             ERROR  no catalog text carries a retired claim phrase (the catalog is hand-written and
                    reviewed, and its text renders outside the marked coverage prose).
  DEBT       ERROR  `_data/coverage_debt.yml` is well formed and names catalog products only.
             ERROR  a Core product whose official lane is switched off by CONFIGURATION (no source, a
                    disabled source, a manual-only source) has a debt entry. Existing gaps are listed
                    there, so this refuses only a NEW one. A lane that is enabled and failing at
                    runtime is never refused: impairment changes the label, it does not stop a deploy.
             WARN   a debt entry for a product whose lane now operates (close it).
  PROJECTION ERROR  the deploy-time `_data/coverage_state.yml` exists, has one row per catalog product
                    and company, and every state and label is a member of the closed vocabulary.
  PILLS      ERROR  every coverage pill on the built site (an element carrying data-coverage-product or
                    data-coverage-company) shows exactly the state and label the projection gives that
                    product or company; every product page carries its own pill; and no page carries a
                    fallback pill ("Coverage status unknown"), which only a render without the
                    projection produces.
  PROSE      ERROR  every product and company page, and the Patch Feed hub, carries marked coverage
                    prose (so the rule below can never pass by reading nothing), and every marked
                    region closes.
             ERROR  the marked coverage prose and the meta description of a product or company page
                    whose coverage is not operating, and of the hub, carry none of the retired claim
                    phrases ("is tracked by AUXSAYS", "is tracked for", "Monitoring active", "official
                    source mapped", ...).

Run:  python auxsays/scripts/ci/verify_coverage_claims.py --site auxsays/_site [--source auxsays]
Exit: 0 clean (warnings allowed), 1 an error, 2 the site directory is unusable.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

import build_coverage_projection as cov  # noqa: E402

FORBIDDEN_CATALOG_KEYS = ("coverage_state", "coverage_status_label", "ingestion_status",
                          "current_status_label", "ingestion_active", "dossier_note")
# Claim phrases retired by AUX-102. Case-sensitive on purpose: the per-patch monitoring card's own
# status vocabulary is upper case ("MONITORING ACTIVE") and describes community collection for one
# patch, which is a different, correctly derived claim.
CLAIM_PHRASES = ("is tracked by AUXSAYS", "is tracked for", "is tracked because", "is tracked as part of",
                 "tracking focuses on", "Monitoring active", "official source mapped", "Source map staged",
                 "not yet monitoring", "OFFICIAL SOURCE ACTIVE")
HUB_PHRASES = ("is tracked by AUXSAYS", "is tracked because", "is tracked as part of", "tracking focuses on",
               "Monitoring active", "tracked companies", "tracked software")
NOT_OPERATING = ("impaired", "planned", "not_monitored")

_PILL = re.compile(r"<span\b([^>]*\bdata-coverage-(product|company)=\"([^\"]*)\"[^>]*)>([^<]*)</span>", re.I)
_STATE_CLASS = re.compile(r"patch-coverage-pill--coverage-([a-z_]+)")
# A fallback pill, recognised by its MARKUP. Vendor text reaches a page HTML-escaped, so it can never
# produce a class attribute; the bare words "Coverage status unknown" in a record title are not a pill.
_FALLBACK_PILL = re.compile(r"\bclass=\"[^\"]*\bpatch-coverage-pill--coverage-unknown\b", re.I)
_TAG = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
# The page's meta description: from the page's own front matter (never a vendor record on a product,
# company or hub page), and the text a search result shows for it.
_META_DESCRIPTION = re.compile(r"<meta name=\"description\" content=\"([^\"]*)\"", re.I)

# The attribute a layout puts on an element whose text is the template's own coverage prose.
PROSE_ATTR = "data-coverage-prose"
_VOID = frozenset(("area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source",
                   "track", "wbr"))


def page_text(text: str) -> str:
    """Visible-ish text: scripts and styles dropped, tags removed, entities decoded, space collapsed."""
    return " ".join(html.unescape(_TAG.sub(" ", _SCRIPT.sub(" ", text))).split())


class _ProseRegions(HTMLParser):
    """Collects the text inside every element carrying `data-coverage-prose`.

    A region ends at the end tag that balances its opening tag (same tag name, counted), so markup
    nested inside it is fine. Script and style content is never text. A region still open at the end
    of the document is reported, never scanned: reading on to the end of the page would reach the
    vendor-written records this rule exists to leave alone.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.regions: list[list[str]] = []
        self._tag: str | None = None
        self._depth = 0
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style"):
            self._skip += 1
            return
        if tag in _VOID:
            return
        if self._tag is None:
            if any(name == PROSE_ATTR for name, _value in attrs):
                self._tag, self._depth = tag, 1
                self.regions.append([])
            return
        if tag == self._tag:
            self._depth += 1
        self.regions[-1].append(" ")

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        if self._tag is not None:
            self.regions[-1].append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
            return
        if self._tag is None:
            return
        self.regions[-1].append(" ")
        if tag == self._tag:
            self._depth -= 1
            if self._depth == 0:
                self._tag = None

    def handle_data(self, data: str) -> None:
        if self._tag is not None and not self._skip:
            self.regions[-1].append(data)


def coverage_prose(text: str) -> tuple[list[str], bool]:
    """(the text of each closed `data-coverage-prose` region, whether every region closed)."""
    parser = _ProseRegions()
    parser.feed(text)
    parser.close()
    closed = parser._tag is None
    regions = parser.regions if closed else parser.regions[:-1]
    return [" ".join("".join(r).split()) for r in regions], closed


def _strings(value: Any, path: str = ""):
    """Every string inside a catalog row, with the key path it sits at."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _strings(v, f"{path}[{i}]")


def url_to_file(site: Path, url: str) -> Path:
    rel = str(url or "").strip().lstrip("/")
    return site / rel / "index.html" if not rel.endswith(".html") else site / rel


def load_projection(path: Path) -> tuple[dict, dict] | None:
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    products = {str(r.get("product_id")): r for r in data.get("products") or [] if isinstance(r, dict)}
    companies = {str(r.get("company_id")): r for r in data.get("companies") or [] if isinstance(r, dict)}
    return products, companies


def check_data(source: Path, products_proj: dict | None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    data = source / "_data"
    catalog = [p for p in (yaml.safe_load((data / "patch_products.yml").read_text(encoding="utf-8")) or [])
               if isinstance(p, dict)]
    companies = [c for c in (yaml.safe_load((data / "patch_companies.yml").read_text(encoding="utf-8")) or [])
                 if isinstance(c, dict)]
    for kind, rows, key in (("product", catalog, "id"), ("company", companies, "id")):
        for row in rows:
            found = [k for k in FORBIDDEN_CATALOG_KEYS if k in row]
            if found:
                errors.append(f"CATALOG {kind} {row.get(key)} carries a static coverage field {found}: "
                              f"coverage is derived by build_coverage_projection.py, never written by hand")
            for where, value in _strings(row):
                for phrase in CLAIM_PHRASES:
                    if phrase in value:
                        errors.append(f"CATALOG {kind} {row.get(key)} {where} says {phrase!r}: catalog "
                                      f"text describes the software, never whether it is monitored")
    try:
        debt = cov.load_debt(data / "coverage_debt.yml")
    except (ValueError, yaml.YAMLError) as exc:
        errors.append(f"DEBT the coverage debt file is unreadable: {exc}")
        debt = []
    ids = {cov.product_id_of(p) for p in catalog}
    errors += [f"DEBT {e}" for e in cov.debt_errors(debt, ids)]
    debt_ids = {str(e.get("product_id")) for e in debt}
    if products_proj is not None:
        for product in catalog:
            pid = cov.product_id_of(product)
            row = products_proj.get(pid) or {}
            if product.get("priority") == "Core" and row.get("official") in cov.OFFICIAL_OFF \
                    and pid not in debt_ids:
                errors.append(f"DEBT Core product {pid} has no operating official lane (official "
                              f"{row.get('official')}) and no entry in _data/coverage_debt.yml")
            if pid in debt_ids and row.get("state") in cov.OPERATING_STATES:
                warnings.append(f"DEBT {pid} now reads {row.get('state')}; close its coverage debt entry")
    return errors, warnings


def check_projection(catalog_ids: set[str], company_ids: set[str], products: dict,
                     companies: dict) -> list[str]:
    errors = []
    for pid in sorted(catalog_ids - set(products)):
        errors.append(f"PROJECTION no coverage row for catalog product {pid}")
    for cid in sorted(company_ids - set(companies)):
        errors.append(f"PROJECTION no coverage row for company {cid}")
    for pid, row in sorted(products.items()):
        state = row.get("state")
        if state not in cov.COVERAGE_STATES or row.get("label") != cov.COVERAGE_LABELS.get(state):
            errors.append(f"PROJECTION product {pid}: state {state!r} / label {row.get('label')!r} "
                          f"is not a vocabulary pair")
    for cid, row in sorted(companies.items()):
        if row.get("state") not in cov.COMPANY_STATES or not str(row.get("label") or "").strip():
            errors.append(f"PROJECTION company {cid}: state {row.get('state')!r} is not in the vocabulary")
    return errors


def check_site(site: Path, catalog: list[dict], companies_cat: list[dict], products: dict,
               companies: dict) -> tuple[list[str], dict]:
    errors: list[str] = []
    stats = {"pages": 0, "pills": 0, "product_pages": 0, "company_pages": 0, "prose_regions": 0}
    product_pages: dict[Path, str] = {}
    company_pages: dict[Path, str] = {}
    for product in catalog:
        product_pages[url_to_file(site, product.get("product_url"))] = cov.product_id_of(product)
    for company in companies_cat:
        company_pages[url_to_file(site, company.get("company_url"))] = str(company.get("id"))
    hub = site / "updates" / "index.html"

    for path in sorted(site.rglob("*.html")):
        stats["pages"] += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(site).as_posix()
        fallback = bool(_FALLBACK_PILL.search(text))
        for attrs, kind, ident, label in _PILL.findall(text):
            stats["pills"] += 1
            want = (products if kind.lower() == "product" else companies).get(ident)
            m = _STATE_CLASS.search(attrs)
            got_state, got_label = (m.group(1) if m else ""), " ".join(html.unescape(label).split())
            fallback = fallback or got_label == cov.UNKNOWN_LABEL
            if want is None:
                errors.append(f"PILLS {rel}: a pill names {kind} {ident!r}, which has no projection row")
            elif (got_state, got_label) != (want.get("state"), want.get("label")):
                errors.append(f"PILLS {rel}: {kind} {ident} shows ({got_state!r}, {got_label!r}); the "
                              f"projection says ({want.get('state')!r}, {want.get('label')!r})")
        if fallback:
            errors.append(f"PILLS {rel} shows the '{cov.UNKNOWN_LABEL}' fallback: the coverage "
                          f"projection was missing or incomplete when it was built")
        pid = product_pages.get(path)
        cid = company_pages.get(path)
        if pid is None and cid is None and path != hub:
            continue
        # Phrase rules read the template's marked coverage prose only, never vendor-written records.
        # Regions are joined with a separator no phrase contains, so two neighbouring regions can
        # never form a phrase between them.
        regions, closed = coverage_prose(text)
        described = [" ".join(html.unescape(d).split()) for d in _META_DESCRIPTION.findall(text)]
        prose = " | ".join(regions + described)
        stats["prose_regions"] += len(regions)
        if not regions:
            errors.append(f"PROSE {rel}: the page carries no marked coverage prose ({PROSE_ATTR}), so "
                          f"its coverage wording cannot be checked")
        if not closed:
            errors.append(f"PROSE {rel}: a {PROSE_ATTR} region never closes")
        if pid is not None:
            stats["product_pages"] += 1
            if f'data-coverage-product="{pid}"' not in text:
                errors.append(f"PILLS {rel}: the product page for {pid} carries no coverage pill of its own")
            state = (products.get(pid) or {}).get("state")
            if state in NOT_OPERATING:
                for phrase in CLAIM_PHRASES:
                    if phrase in prose:
                        errors.append(f"PROSE {rel}: {pid} is {state} but the page says {phrase!r}")
        if cid is not None:
            stats["company_pages"] += 1
            state = (companies.get(cid) or {}).get("state")
            if state in NOT_OPERATING:
                for phrase in CLAIM_PHRASES:
                    if phrase in prose:
                        errors.append(f"PROSE {rel}: company {cid} is {state} but the page says {phrase!r}")
        if path == hub:
            for phrase in HUB_PHRASES:
                if phrase in prose:
                    errors.append(f"PROSE {rel}: the Patch Feed hub says {phrase!r}")
    for path, pid in sorted(product_pages.items()):
        if not path.is_file():
            errors.append(f"PILLS no built product page for {pid} at {path.relative_to(site).as_posix()}")
    return errors, stats


def verify(site: Path, source: Path, projection_path: Path | None = None) -> tuple[list[str], list[str], dict]:
    projection_path = projection_path or source / "_data" / cov.OUTPUT_PATH.name
    loaded = load_projection(projection_path)
    errors: list[str] = []
    if loaded is None:
        errors.append(f"PROJECTION {projection_path} is missing or unreadable: the deploy must build it "
                      f"before jekyll build")
        products, companies = {}, {}
    else:
        products, companies = loaded
    data_errors, warnings = check_data(source, products if loaded is not None else None)
    errors += data_errors
    data = source / "_data"
    catalog = [p for p in yaml.safe_load((data / "patch_products.yml").read_text(encoding="utf-8")) or []
               if isinstance(p, dict)]
    companies_cat = [c for c in yaml.safe_load((data / "patch_companies.yml").read_text(encoding="utf-8")) or []
                     if isinstance(c, dict)]
    stats: dict[str, Any] = {}
    if loaded is not None:
        errors += check_projection({cov.product_id_of(p) for p in catalog},
                                   {str(c.get("id")) for c in companies_cat}, products, companies)
        site_errors, stats = check_site(site, catalog, companies_cat, products, companies)
        errors += site_errors
    return errors, warnings, stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--site", required=True, type=Path, help="the built site directory")
    ap.add_argument("--source", type=Path, default=None, help="the Jekyll source (default: the site's parent)")
    ap.add_argument("--projection", type=Path, default=None,
                    help="the coverage projection (default: <source>/_data/coverage_state.yml)")
    args = ap.parse_args(argv)
    if not (args.site / "index.html").is_file():
        print(f"verify_coverage_claims: {args.site} has no index.html", file=sys.stderr)
        return 2
    source = args.source if args.source is not None else args.site.resolve().parent
    if not (source / "_data" / "patch_products.yml").is_file():
        print(f"verify_coverage_claims: {source} is not the Jekyll source", file=sys.stderr)
        return 2
    errors, warnings, stats = verify(args.site, source, args.projection)
    if stats:
        print(f"pages {stats['pages']}; coverage pills {stats['pills']}; product pages "
              f"{stats['product_pages']}; company pages {stats['company_pages']}; coverage prose "
              f"regions {stats['prose_regions']}")
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"FAIL  {e}")
    if errors:
        print(f"verify_coverage_claims: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"verify_coverage_claims: clean ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
