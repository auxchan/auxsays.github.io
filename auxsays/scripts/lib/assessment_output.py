"""THE STORED PROVISIONAL ASSESSMENT: the one reader of `_data/provisional_assessments.yml` (AUX-137).

WHAT THE FILE IS. At ASSESSMENT_MIN_REPORTS accepted reports a page triggers a provisional risk assessment (owner
ruling of 2026-11-24). The weighing of a page's reports is computed OUTSIDE this repository by a scheduled step that
reads this public tree and pushes ONE file back: `auxsays/_data/provisional_assessments.yml`. For each page it
weighed, the file holds what the weighing supports (verdict, scope, basis, why the rest of the page keeps the
volume-based WAIT), the lines it prints, and the FINGERPRINT of the inputs it was computed from. Nothing else of
that step is in this repository, and nothing here needs it: without the file every page is decided exactly as
before (the count-based assessment) and says that the weighing is pending.

THE ONE CALL. lib.patch_decision.assess calls `weighing_for(record, rows)` once per page at the trigger, and
nothing else reads the file. It returns the stored weighing ONLY when all of these hold, else None:
  * the file parses, its `schema_version` is SCHEMA_VERSION and its header is complete (`file_errors`);
  * the page has an entry and the entry passes `entry_errors` (closed vocabularies, plain text, bounded sizes);
  * the entry's `fingerprint` equals `fingerprint(record, rows)` of the CURRENT tree: the page's identity fields,
    its counted rows, the counted rows and identity fields of every other page of the same product (earlier
    releases are compared with it), the stored tracker records of all those rows, the tracker vocabularies, the
    product's and the store's newest collection days, and the source of the public modules the weighing calls.
    Any change to any of them makes the entry STALE until the step runs again.
A missing, stale or invalid entry is never used in part, and a page whose weighing is not current is never
published with a weighed verdict: it gets the count-based result and the pending line (patch_decision.
ASSESS_PENDING). QA names every such page (`assessment_output_missing`, `assessment_output_stale`) and a broken
file (`assessment_output_invalid`).

ONE WRITER. The step publishes the file in a separate output-only repository; this repository's import lane
(.github/workflows/assessment-import.yml, import_assessment_output.py) reads it with no credential, checks it here
and commits it through lib/automation_writeback.py, which stages it only for a lane that names it exactly and never
beside any other path (SINGLE_WRITER_PATHS there). No other lane names it, and no credential held outside this
repository can write here.

The step itself calls `install_weigher` (never a public lane): the call site then weighs live and the step records
each result with `entry_from` and `fingerprint`, so the file is written by the same contract this module reads.

Pure: standard library and PyYAML. No network, no clock.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Mapping

from . import assessment_facts

OUTPUT_NAME = "provisional_assessments.yml"
OUTPUT_RELPATH = "auxsays/_data/" + OUTPUT_NAME
ROOT = assessment_facts.ROOT
OUTPUT_PATH = ROOT / "_data" / OUTPUT_NAME
SCHEMA_VERSION = 1
FINGERPRINT_RULE = "assessment-inputs-2"

WAIT = "WAIT"
TEST_FIRST = "TEST FIRST"
# The bases a stored weighing may decide a page on, with the verdict each gives. Published reason codes.
BASIS_MAINTAINER_REGRESSION = "maintainer_confirmed_regression"
BASIS_SEVERE_REGRESSION = "repeated_severe_regression"
BASIS_TEST_FIRST = "provisional_test_first"
BASES = {BASIS_MAINTAINER_REGRESSION: WAIT, BASIS_SEVERE_REGRESSION: WAIT, BASIS_TEST_FIRST: TEST_FIRST}
# Why the rest of a page keeps the temporary volume-based WAIT ("" when it does not).
RETAIN_CODES = frozenset({"", "maintainer_records_not_current", "collection_stale", "dimensions_not_established",
                          "regression_not_established", "no_repeated_concrete_failure"})
# The dimension lines a stored weighing may print (each also in patch_decision.ASSESS_LABELS).
LINE_LABELS = ("Independent corroboration", "Maintainer response", "Recurring problems", "Severity and data loss",
               "Affected setups", "Positive outcomes", "Fixes and open problems", "Collection health")
# The record fields the weighing reads. Its own tests pin that it reads no other.
# assessment-inputs-2: the release date is an input as well.
RECORD_FIELDS = ("product_id", "update_version", "target_build", "update_product", "update_published_at")
# The public modules whose code the weighing calls on these inputs; a change to one makes every entry stale.
CODE_MODULES = ("assessment_facts.py", "evidence_facts.py", "source_segments.py")
TEXT_FIELDS = ("recommendation", "body", "retained", "other_setups")
ENTRY_KEYS = ("page", "fingerprint", "reports", "verdict", "scope", "basis", "retain", "page_wide",
              "version_conflicts", "lines", *TEXT_FIELDS)
HEADER_KEYS = ("schema_version", "rule_version", "fingerprint_rule", "generated_at", "source_commit", "pages")
MAX_TEXT = 4000
_TEXT_RE = re.compile(r"^[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f<>]*$")
_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$", re.ASCII)
_RULE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,79}$", re.ASCII)
_STAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$", re.ASCII)
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_ISSUE_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/[0-9]+$", re.ASCII)

_STATE: dict[str, Any] = {}


class StoredWeighing:
    """One page's stored weighing, read back. The same interface lib.patch_decision uses: `verdict`, `scope`,
    `basis`, `retain`, `page_wide`, `version_conflicts`, `marked`, `facts` (the tracker-record count, recomputed
    here from the public data layer, never stored), and the stored wording."""

    def __init__(self, entry: Mapping[str, Any], facts: Any) -> None:
        self.verdict = str(entry["verdict"])
        self.scope = str(entry["scope"])
        self.basis = str(entry["basis"])
        self.retain = str(entry["retain"])
        self._page_wide = bool(entry["page_wide"])
        self.version_conflicts = list(entry["version_conflicts"])
        self._lines = dict(entry["lines"])
        self._text = {k: str(entry[k]) for k in TEXT_FIELDS}
        self.facts = facts

    @property
    def page_wide(self) -> bool:
        return self._page_wide

    @property
    def marked(self) -> list[dict[str, str]]:
        return self.facts.marked

    def lines(self) -> dict[str, str]:
        return dict(self._lines)

    def recommendation(self, phrase: str) -> str:  # noqa: ARG002 - the phrase is the stored verdict and scope
        return self._text["recommendation"]

    def body(self, n: int) -> str:  # noqa: ARG002 - the count is part of the fingerprint
        return self._text["body"]

    def retained(self) -> str:
        return self._text["retained"]

    def other_setups(self) -> str:
        return self._text["other_setups"]

    def __repr__(self) -> str:
        return f"StoredWeighing({self.verdict!r}, {self.basis!r}, retain={self.retain!r})"


# ------------------------------------------------------------------------------------------- the fingerprint
def _canon(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _canon(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_canon(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _digest(value: Any) -> str:
    text = json.dumps(_canon(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def _strip(value: Any) -> str:
    return str(value or "").strip()


def page_key(record: Mapping[str, Any] | None) -> str:
    """product|version|build, the projection's page key (lib.verdict_projection.page_key)."""
    from . import verdict_reasons  # noqa: PLC0415 - verdict_reasons imports the authority
    return "|".join(verdict_reasons.record_identity(record or {}))


def _identity(record: Mapping[str, Any]) -> dict[str, str]:
    return {k: _strip(record.get(k)) for k in RECORD_FIELDS}


def _rows_digest(rows: Any) -> str:
    return _digest(sorted((_digest(r) for r in rows or () if isinstance(r, Mapping))))


_CAPTURE_BLOCK_RE = re.compile(r"^- id: .*?(?=^- id: |\Z)", re.M | re.S)
_PRODUCT_RE = re.compile(r"^  product_id: ['\"]?([A-Za-z0-9_.-]+)", re.M)
_CAPTURED_RE = re.compile(r"^  captured_at: ['\"]?([0-9]{4}-[0-9]{2}-[0-9]{2})", re.M)


def _product_days(evidence_path: Path) -> dict[str, str]:
    """product -> the day its newest row was collected; the "" key -> the store's newest day (the reference date
    tracker records are aged against, lib.assessment_facts.newest_capture)."""
    try:
        text = Path(evidence_path).read_text(encoding="utf-8")
    except OSError:
        return {}
    out: dict[str, str] = {"": assessment_facts.newest_capture(evidence_path)}
    for block in _CAPTURE_BLOCK_RE.findall(text):
        product, day = _PRODUCT_RE.search(block), _CAPTURED_RE.search(block)
        if product and day and day.group(1) > out.get(product.group(1), ""):
            out[product.group(1)] = day.group(1)
    return out


def _population() -> dict[str, list[tuple[dict[str, str], str, list]]]:
    """product -> [(identity fields, rows digest, rows)] of every page in the tree, read once per process."""
    if "population" not in _STATE:
        by_product: dict[str, list] = {}
        try:
            from . import verdict_projection  # noqa: PLC0415 - it imports the authority
            records, groups = verdict_projection.load_inputs(ROOT)
            from . import verdict_reasons  # noqa: PLC0415
            for rec in records:
                rows = groups.get(verdict_reasons.record_identity(rec), [])
                if rows:
                    by_product.setdefault(_strip(rec.get("product_id")), []).append(
                        (_identity(rec), _rows_digest(rows), rows))
        except Exception:  # noqa: BLE001 - fail closed: an unreadable tree matches no entry
            by_product = {"": [({"unreadable": "tree"}, "", [])]}
        _STATE["population"] = by_product
    return _STATE["population"]


def _code_digest() -> str:
    if "code" not in _STATE:
        here = Path(__file__).resolve().parent
        parts = {}
        for name in CODE_MODULES:
            try:
                parts[name] = hashlib.sha256((here / name).read_bytes()).hexdigest()
            except OSError:
                parts[name] = "missing"
        _STATE["code"] = parts
    return _STATE["code"]


def _file_digest(path: Path) -> str:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return "missing"


def fingerprint(record: Mapping[str, Any] | None, rows: Any, *, source_facts: Any = None,
                population: Mapping[str, list] | None = None) -> str:
    """The fingerprint of every input the weighing of this page reads (see the module docstring). The private step
    and the reader call this same function on the same tree, so equal inputs give equal fingerprints."""
    rec = record or {}
    product = _strip(rec.get("product_id"))
    if population is None:
        population = _STATE.get("population_override")
    pages = (population if population is not None else _population()).get(product, [])
    facts = assessment_facts.stored() if source_facts is None else source_facts
    days = _STATE.get("days")
    if days is None:
        days = _STATE["days"] = _product_days(assessment_facts.EVIDENCE_PATH)
    as_of = getattr(source_facts, "as_of", None) if source_facts is not None else None
    urls = set()
    for row in list(rows or ()) + [r for _i, _d, page_rows in pages for r in page_rows]:
        if isinstance(row, Mapping):
            urls.add(_strip(row.get("source_url")))
    tracker = {u: facts.get(u) for u in sorted(urls) if isinstance(facts, Mapping) and u in facts}
    doc = {
        "rule": FINGERPRINT_RULE,
        "page": _identity(rec),
        "rows": _rows_digest(rows),
        "product": sorted([[_digest(i), d] for i, d, _r in pages]),
        "facts": _digest(tracker),
        "facts_as_of": as_of if as_of is not None else assessment_facts.stored_as_of(),
        "vocabularies": _file_digest(assessment_facts.VOCABULARY_PATH),
        "days": [days.get(product, ""), days.get("", "")],
        "code": _code_digest(),
    }
    return "sha256:" + _digest(doc)


# -------------------------------------------------------------------------------------------- validation
def _text_ok(value: Any) -> bool:
    return isinstance(value, str) and len(value) <= MAX_TEXT and bool(_TEXT_RE.match(value))


def entry_errors(entry: Any) -> list[str]:
    """Why a stored page entry may not be used ([] when it may)."""
    if not isinstance(entry, Mapping):
        return ["entry is not a mapping"]
    errors = []
    if set(entry) != set(ENTRY_KEYS):
        errors.append(f"keys {sorted(entry)} are not {sorted(ENTRY_KEYS)}")
        return errors
    if not _text_ok(entry["page"]) or entry["page"].count("|") != 2:
        errors.append("page is not product|version|build")
    if not isinstance(entry["fingerprint"], str) or not _FINGERPRINT_RE.match(entry["fingerprint"]):
        errors.append("fingerprint is not sha256:<64 hex>")
    if not isinstance(entry["reports"], int) or isinstance(entry["reports"], bool) or entry["reports"] < 0:
        errors.append("reports is not a count")
    verdict, basis = entry["verdict"], entry["basis"]
    if verdict not in ("", WAIT, TEST_FIRST) or basis not in ("", *BASES) or bool(verdict) != bool(basis) \
            or (basis and BASES[basis] != verdict):
        errors.append(f"verdict {verdict!r} and basis {basis!r} are not a stored pair")
    if entry["retain"] not in RETAIN_CODES:
        errors.append(f"retain {entry['retain']!r} is not a known code")
    if not isinstance(entry["page_wide"], bool) or (entry["page_wide"] and verdict != WAIT):
        errors.append("page_wide is not a boolean of a WAIT")
    elif verdict == WAIT and entry["page_wide"] == str(entry["scope"]).startswith("if you use"):
        # REVIEW3 F2: the precedence reads `page_wide` and `scope` together; a WAIT is page-wide exactly when its
        # scope names no setup.
        errors.append("page_wide contradicts the scope of the WAIT")
    conflicts = entry["version_conflicts"]
    if not isinstance(conflicts, list) or not all(isinstance(c, str) and _ISSUE_RE.match(c) for c in conflicts):
        errors.append("version_conflicts is not a list of tracker issue links")
    lines = entry["lines"]
    if not isinstance(lines, Mapping) or not all(k in LINE_LABELS and _text_ok(v) for k, v in lines.items()):
        errors.append("lines carry a label or a text this file may not hold")
    for key in ("scope", *TEXT_FIELDS):
        if not _text_ok(entry[key]):
            errors.append(f"{key} is not plain text")
    if not errors and verdict and not entry["recommendation"]:
        errors.append("a deciding entry carries no recommendation")
    return errors


def file_errors(doc: Any) -> list[str]:
    """Why the file may not be read at all ([] when its header is sound; entries are checked one by one)."""
    if not isinstance(doc, Mapping):
        return ["the file is not a mapping"]
    if doc.get("schema_version") != SCHEMA_VERSION:
        return [f"schema_version {doc.get('schema_version')!r} is not {SCHEMA_VERSION}"]
    errors = []
    if set(doc) != set(HEADER_KEYS):
        errors.append(f"top-level keys {sorted(doc)} are not {sorted(HEADER_KEYS)}")
    if doc.get("fingerprint_rule") != FINGERPRINT_RULE:
        errors.append(f"fingerprint_rule {doc.get('fingerprint_rule')!r} is not {FINGERPRINT_RULE}")
    if not isinstance(doc.get("rule_version"), str) or not _RULE_RE.match(doc.get("rule_version") or ""):
        errors.append("rule_version is not a rule name")
    if not isinstance(doc.get("generated_at"), str) or not _STAMP_RE.match(doc.get("generated_at") or ""):
        errors.append("generated_at is not a UTC timestamp")
    if not isinstance(doc.get("source_commit"), str) or not _COMMIT_RE.match(doc.get("source_commit") or ""):
        errors.append("source_commit is not a commit id")
    if not isinstance(doc.get("pages"), list):
        errors.append("pages is not a list")
    return errors


# ------------------------------------------------------------------------------------------------ reading
def _load() -> dict[str, Any]:
    """{'status': missing|invalid|ok, 'problem': str, 'pages': {page key: entry}, 'rule_version': str}."""
    if "file" in _STATE:
        return _STATE["file"]
    source = _STATE.get("override", OUTPUT_PATH)
    state: dict[str, Any] = {"status": "missing", "problem": "", "pages": {}, "rule_version": "", "bad": {}}
    if isinstance(source, Mapping):
        doc: Any = source
    elif source is None or not Path(source).is_file():
        _STATE["file"] = state
        return state
    else:
        import yaml  # noqa: PLC0415
        try:
            doc = yaml.load(Path(source).read_text(encoding="utf-8"), Loader=yaml.SafeLoader)
        except Exception as exc:  # noqa: BLE001 - ANY parser failure is an invalid file, never a crash
            state.update(status="invalid", problem=f"the file does not parse ({type(exc).__name__})")
            _STATE["file"] = state
            return state
    errors = file_errors(doc)
    if errors:
        state.update(status="invalid", problem="; ".join(errors[:3]))
        _STATE["file"] = state
        return state
    pages: dict[str, Any] = {}
    for entry in doc["pages"]:
        problems = entry_errors(entry)
        key = str(entry.get("page")) if isinstance(entry, Mapping) else ""
        if problems or key in pages or key in state["bad"]:
            state["bad"][key] = problems or ["page listed twice"]
            pages.pop(key, None)
            continue
        pages[key] = entry
    state.update(status="ok", pages=pages, rule_version=doc["rule_version"])
    _STATE["file"] = state
    return state


def status() -> dict[str, Any]:
    """The file's state for QA: status, problem, rule_version, entry count and the keys of unusable entries."""
    state = _load()
    return {"status": state["status"], "problem": state["problem"], "rule_version": state["rule_version"],
            "pages": len(state["pages"]), "bad": dict(state["bad"])}


def page_state(record: Mapping[str, Any] | None, rows: Any, *, source_facts: Any = None) -> str:
    """'current', 'stale' (an entry computed from other inputs), 'invalid' (an entry that fails its checks, or a
    broken file) or 'missing' (no file, or no entry for this page)."""
    if _STATE.get("weigher") is not None:
        return "current"
    state = _load()
    if state["status"] == "invalid":
        return "invalid"
    key = page_key(record)
    if key in state["bad"]:
        return "invalid"
    entry = state["pages"].get(key)
    if entry is None:
        return "missing"
    rows = [r for r in rows or () if isinstance(r, Mapping)]
    if entry["reports"] != len(rows) \
            or entry["fingerprint"] != fingerprint(record, rows, source_facts=source_facts):
        return "stale"
    return "current"


def weighing_for(record: Mapping[str, Any] | None, rows: Any, *, source_facts: Any = None) -> Any:
    """THE weighing of one page at the trigger, or None when no CURRENT stored weighing exists (the caller then
    decides the page exactly as without one). Called by lib.patch_decision.assess and nothing else."""
    rec = record or {}
    weigher: Callable | None = _STATE.get("weigher")
    if weigher is not None:
        return weigher(rec, rows, source_facts)
    if page_state(rec, rows, source_facts=source_facts) != "current":
        return None
    entry = _load()["pages"][page_key(rec)]
    facts = assessment_facts.weigh(rows, source_facts, version=_strip(rec.get("update_version")))
    return StoredWeighing(entry, facts)


def record_facts(record: Mapping[str, Any] | None, rows: Any, *, source_facts: Any = None) -> Any:
    """The tracker-record count of a page (public data layer), with or without a stored weighing."""
    return assessment_facts.weigh(rows, source_facts, version=_strip((record or {}).get("update_version")))


# ------------------------------------------------------------------------------------------------ writing
def entry_from(weighing: Any, record: Mapping[str, Any], rows: Any, *, source_facts: Any = None) -> dict[str, Any]:
    """The stored entry of a live weighing (the private step's side of the contract). `weighing` offers the
    interface StoredWeighing reads back."""
    rows = [r for r in rows or () if isinstance(r, Mapping)]
    phrase = f"{weighing.verdict} {weighing.scope}".strip()
    entry = {
        "page": page_key(record),
        "fingerprint": fingerprint(record, rows, source_facts=source_facts),
        "reports": len(rows),
        "verdict": str(weighing.verdict or ""),
        "scope": str(weighing.scope or ""),
        "basis": str(weighing.basis or ""),
        "retain": str(weighing.retain or ""),
        "page_wide": bool(weighing.page_wide),
        "version_conflicts": [str(c) for c in weighing.version_conflicts],
        "lines": {k: v for k, v in weighing.lines().items() if k in LINE_LABELS and v},
        "recommendation": weighing.recommendation(phrase) if weighing.verdict else "",
        "body": weighing.body(len(rows)) if weighing.verdict else "",
        "retained": weighing.retained() if weighing.retain else "",
        "other_setups": weighing.other_setups(),
    }
    return entry


def render(pages: list[Mapping[str, Any]], *, rule_version: str, generated_at: str, source_commit: str) -> str:
    """The file text: one stable layout, pages sorted by key."""
    import yaml  # noqa: PLC0415
    doc = {"schema_version": SCHEMA_VERSION, "rule_version": rule_version, "fingerprint_rule": FINGERPRINT_RULE,
           "generated_at": generated_at, "source_commit": source_commit,
           "pages": sorted((dict(p) for p in pages), key=lambda p: p["page"])}
    head = ("# GENERATED by the scheduled provisional-assessment step (lib/assessment_output.py documents it).\n"
            "# Its ONE writer pushes this file through lib/automation_writeback.py; never edited by hand, never\n"
            "# written by a public lane. A page entry is used only while its fingerprint matches the current tree.\n")
    return head + yaml.safe_dump(doc, sort_keys=False, allow_unicode=False, width=100000)


# ---------------------------------------------------------------------------------------- overrides (tests)
def use(source: Any) -> None:
    """Read `source` instead of the tracked file: a path, a parsed document, or None (no file). Tests and tools."""
    _STATE.pop("file", None)
    _STATE["override"] = source


def population_from(pages: Any) -> dict[str, list]:
    """A product population from (record, rows) pairs, in the shape `fingerprint` reads (tests and tools)."""
    out: dict[str, list] = {}
    for rec, rows in pages:
        rows = [r for r in rows or () if isinstance(r, Mapping)]
        out.setdefault(_strip(rec.get("product_id")), []).append((_identity(rec), _rows_digest(rows), rows))
    return out


def use_population(population: Mapping[str, list] | None) -> None:
    """Fingerprint against this product population instead of the tree's (tests with synthetic pages)."""
    _STATE["population_override"] = population


def install_weigher(fn: Callable | None) -> None:
    """The private step only: weigh live at the call site instead of reading the file."""
    _STATE["weigher"] = fn


def reset() -> None:
    """Forget every cached read and override."""
    _STATE.clear()
