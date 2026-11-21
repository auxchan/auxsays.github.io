"""Does a GitHub release body declare a known issue for the release it belongs to? (AUX-125)

WHY THIS EXISTS. OBS edited its 33.0.2 release notes after publication to open with a GitHub
IMPORTANT alert stating a known startup crash on certain older processors. Official ingestion
re-read the body and stored it, but nothing turned the stored statement into anything a reader
sees: the patch page said AUXSAYS had captured no vendor issue data, and the warning sat inside
the collapsed release notes as raw Markdown.

WHAT COUNTS. Only an explicit vendor declaration, read from the vendor's own structure:
  * a GitHub alert block (NOTE, IMPORTANT, WARNING or CAUTION) one of whose clauses OPENS by
    introducing a known issue: "Known issue: ...", "There is a known issue ...", "There are known
    issues ...", "A known issue ...", "Two known issues ...";
  * a heading that names a Known Issue(s) section, with something in it.
An alert is not a known issue because of its markup: OBS uses the same IMPORTANT box for driver
minimums, dropped OS support and a new code-signing certificate, and none of those is a declared
known issue. Nor is an alert that only REFERS to known issues, whether as a pointer ("check the
known issues page", "a list of known issues"), a condition ("If you run into a known issue, ...",
"check whether it is a known issue") or an absence ("no known issues", "any known issues"): it stays
a generic alert. The rule is a short allow-list of the grammatical shapes that introduce a known
issue, so a shape it does not know reads as generic (fails closed). There is no list of issue
phrasings here, and nothing is inferred from words like "crash".

WHICH RELEASE IT BELONGS TO. OBS bodies carry several releases' notes in one page ("33.0.2 Hotfix
Changes", then "33.0.1 Hotfix Changes", ...). A notice is attributed to the release being assessed
only when the structure says so:
  * above the first release heading, when that heading is this release (or the body has none);
  * under this release's own heading;
  * never when it sits under an earlier (or any other) release's heading;
  * never after a plain, bold or HTML line that names another release ("**9.1.2 Hotfix Changes**",
    "<h2>9.1.2</h2>"), whether the body has no Markdown release headings or the line comes later
    in this release's own section: position no longer says whose notice it is.
An alert's declaring sentence may also name versions. Naming only this release confirms it; naming
any other release makes the attribution ambiguous, because "the known issue in 33.0.2" on the
33.0.3 page is a statement about 33.0.2. AMBIGUOUS IS UNKNOWN, and unknown publishes nothing: it is
never treated as declared and never as a claim that the release has no issues.

WHAT IT DOES NOT DO. It produces no count (one alert can describe several issues, so a notice count
is not an issue count) and no issue summary: it says only that the vendor's notes for this version
identify a known issue. The record field it drives, `official_notes_known_issue: declared`, is
present only while the stored body declares one and is removed when a later capture no longer does.

Pure and stdlib-only: the record writer and the zero-network migration both call it, so a record
refreshed from GitHub and a record migrated from its stored body cannot disagree.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

FIELD = "official_notes_known_issue"
DECLARED = "declared"
NOT_DECLARED = "not_declared"
UNKNOWN = "unknown"

GITHUB_RELEASE = "github-release"

# The GitHub alert kinds a vendor uses to flag something. TIP is advice, not a notice.
NOTICE_ALERTS = frozenset({"NOTE", "IMPORTANT", "WARNING", "CAUTION"})

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
_SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_LIST_ITEM = re.compile(r"^\s*(?:[*+-]|\d+[.)])(?:\s|$)")
_QUOTE = re.compile(r"^ {0,3}>[ \t]?(.*)$")
_ALERT = re.compile(r"^ {0,3}>[ \t]?\[!([A-Za-z]+)\][ \t]*(.*)$")
# A dotted version token: 33.0.2, v0.14.1, 33.0. Not part of a longer word or number.
_VERSION = re.compile(r"(?<![\w.])v?(\d+(?:\.\d+)+)(?!\w|\.\d)")
_KNOWN_ISSUE = re.compile(r"\bknown[ \t-]+issues?\b", re.I)
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
_ABSENCE_DETERMINERS = frozenset({"no", "any"})
# A clause DECLARES a known issue only when it OPENS by introducing one (see _declares): the label
# "Known issue: ..." / "**Known issues** - ..." (unless what follows it is empty, "None" or "N/A"), the
# existential "There is (currently) a known issue ..." / "There are (two) known issues ...", or an
# indefinite or counted subject "A known issue ..." / "Two known issues ...". A clause opens at the
# start of the sentence or after a colon, semicolon, dash or opening parenthesis; markup and quotes
# there are skipped. Present tense only ("There was a known issue" usually reports a fixed one).
# Grammar words only, no issue phrasings.
_COUNT = r"(?:two|three|four|five|six|seven|eight|nine|ten|several|multiple|some|\d+)"
_ONE_KNOWN_ISSUE = r"(?:a|an|one)[ \t]+known[ \t-]+issue\b"
_DECLARING = re.compile(
    r"(?:^|[:;(\u2013\u2014]|[ \t]-)[ \t*_\"'\u201c\u2018]*(?:"
    r"(?P<label>known[ \t-]+issues?[*_]*(?:[ \t]*[:\u2013\u2014]|[ \t]+-))"
    r"|there(?:[ \t]+(?:is|are|exists?|remains?)|['\u2019]s)[ \t]+(?:(?:currently|still|also|now)[ \t]+)?"
    r"(?:" + _ONE_KNOWN_ISSUE + r"|(?:" + _COUNT + r"[ \t]+)?known[ \t-]+issues\b)"
    r"|" + _ONE_KNOWN_ISSUE
    + r"|" + _COUNT + r"[ \t]+known[ \t-]+issues\b"
    r")", re.I)
_KI_HEADING_WORDS = frozenset({"known issue", "known issues"})
_VACUOUS_SECTION = frozenset({"", "none", "na", "n a"})


@dataclass(frozen=True)
class Assessment:
    result: str
    reason: str

    @property
    def declared(self) -> bool:
        return self.result == DECLARED


@dataclass
class _Block:
    kind: str                      # "heading" | "alert" | "text"
    text: str = ""
    level: int = 0                 # heading level
    alert: str = ""                # alert kind, upper-case


def is_github_release(front: dict[str, Any] | None) -> bool:
    """Is this record (or incoming adapter record) built from a GitHub release body?"""
    front = front or {}
    return GITHUB_RELEASE in {str(front.get("official_source_type") or "").strip(),
                              str(front.get("official_patch_notes_source_type") or "").strip(),
                              str(front.get("source_type") or "").strip()}


def version_key(value: Any) -> tuple[int, ...] | None:
    """The first dotted version in ``value`` as integers, trailing zeros dropped: 33.0 == 33.0.0."""
    match = _VERSION.search(str(value or ""))
    if not match:
        return None
    parts = [int(p) for p in match.group(1).split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def _version_keys(text: str) -> set[tuple[int, ...]]:
    return {key for key in (version_key(m.group(0)) for m in _VERSION.finditer(text or "")) if key}


def _blocks(body: str) -> list[_Block]:
    lines = str(body or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[_Block] = []
    fence = ""
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        opener = _FENCE.match(line)
        if fence:
            # Fenced content is quoted code: never a heading, never a notice.
            if opener and opener.group(1)[0] == fence[0] and len(opener.group(1)) >= len(fence):
                fence = ""
            i += 1
            continue
        if opener:
            fence = opener.group(1)
            i += 1
            continue
        atx = _ATX.match(line)
        if atx:
            blocks.append(_Block("heading", (atx.group(2) or "").strip(), level=len(atx.group(1))))
            i += 1
            continue
        if (i + 1 < n and line.strip() and _SETEXT.match(lines[i + 1])
                and not _QUOTE.match(line) and not _LIST_ITEM.match(line)):
            level = 1 if lines[i + 1].strip().startswith("=") else 2
            blocks.append(_Block("heading", line.strip(), level=level))
            i += 2
            continue
        alert = _ALERT.match(line)
        if alert:
            parts = [alert.group(2)]
            j = i + 1
            while j < n:
                quoted = _QUOTE.match(lines[j])
                if not quoted:
                    break
                parts.append(quoted.group(1))
                j += 1
            text = " ".join(p.strip() for p in parts if p.strip())
            blocks.append(_Block("alert", text, alert=alert.group(1).upper()))
            i = j
            continue
        blocks.append(_Block("text", line.strip()))
        i += 1
    return blocks


def _sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_BREAK.split(text or "") if s.strip()]


def _declares(sentence: str) -> bool:
    """Does one of this sentence's clauses OPEN by introducing a known issue ("Known issue: ...",
    "There is a known issue ...", "There are known issues ...", "A known issue ...", "Two known
    issues ...")? A mention anywhere else only refers to known issues -- "the known issues page", "a
    list of known issues", "If you run into a known issue", "check whether it is a known issue",
    "check whether there is a known issue", "no known issues", "any known issues", "Known issues:
    none" -- so an alert that only mentions them stays a generic alert (fails closed)."""
    for match in _DECLARING.finditer(sentence):
        if match.group("label") is None or not _section_is_vacuous(sentence[match.end():]):
            return True
    return False


def _denies(sentence: str) -> bool:
    """Does this sentence mention known issues only to say there are none ("no known issues")?"""
    matches = list(_KNOWN_ISSUE.finditer(sentence))
    for match in matches:
        previous = re.search(r"([A-Za-z]+)[^A-Za-z]*$", sentence[:match.start()])
        if not (previous and previous.group(1).lower() in _ABSENCE_DETERMINERS):
            return False
    return bool(matches)


def _is_known_issues_heading(text: str) -> bool:
    words = re.sub(r"[^a-z]+", " ", _VERSION.sub(" ", text or "").lower()).strip()
    return words in _KI_HEADING_WORDS


def _section_is_vacuous(text: str) -> bool:
    kept = [s for s in _sentences(text) if not _denies(s)]
    return re.sub(r"[^a-z]+", " ", " ".join(kept).lower()).strip() in _VACUOUS_SECTION


def assess(body: Any, version: Any) -> Assessment:
    """declared / not_declared / unknown for the release ``version`` whose notes are ``body``."""
    if not str(body or "").strip():
        return Assessment(NOT_DECLARED, "no release-notes body stored")
    target = version_key(version)
    blocks = _blocks(str(body))

    release_headings = [b for b in blocks if b.kind == "heading" and _version_keys(b.text)]
    first_release = _version_keys(release_headings[0].text) if release_headings else set()
    if not release_headings or first_release == {target}:
        preamble_owner = "current"
    else:
        preamble_owner = "ambiguous"

    # Notes can also introduce a release with a plain, bold or HTML line instead of a Markdown heading
    # ("**9.1.2 Hotfix Changes**", "<h2>9.1.2</h2>"): in a body with no headings at all, or after this
    # release's own heading. Once a line that is not a list item or a quote has named another release,
    # position no longer says whose notice follows: ambiguous, never this release's. The flag starts
    # again at every release heading.
    other_release_named = False

    def owner_of(section: Any) -> str:
        if section == "preamble":
            owner = preamble_owner
        elif section == "ambiguous" or target is None:
            return "ambiguous"
        else:
            owner = "current" if section == target else "other"
        return "ambiguous" if owner == "current" and other_release_named else owner

    declared: list[str] = []
    ambiguous: list[str] = []
    outside: list[str] = []
    generic = 0
    empty_sections = 0

    section: Any = "preamble"
    ki: dict[str, Any] | None = None   # an open Known Issues section: owner, level, collected text

    def close_ki() -> None:
        nonlocal ki, empty_sections
        if ki is None:
            return
        where, label = ki["owner"], ki["label"]
        if _section_is_vacuous(" ".join(ki["text"])):
            empty_sections += 1
        elif where == "current":
            declared.append(f"Known Issues section {label} for this release")
        elif where == "other":
            outside.append(f"Known Issues section {label} belongs to another release")
        else:
            ambiguous.append(f"Known Issues section {label} cannot be attributed to one release")
        ki = None

    for block in blocks:
        if block.kind == "heading":
            keys = _version_keys(block.text)
            if ki is not None and (keys or block.level <= ki["level"]):
                close_ki()
            elif ki is not None:
                ki["text"].append(block.text)
            if keys:
                section = next(iter(keys)) if len(keys) == 1 else "ambiguous"
                other_release_named = False
            if _is_known_issues_heading(block.text):
                close_ki()
                where = owner_of(section)
                label = "above the first release heading" if section == "preamble" else f"under '{block.text}'"
                ki = {"owner": where, "level": block.level, "text": [], "label": label}
            continue

        if ki is not None:
            ki["text"].append(block.text)

        if (block.kind == "text" and target is not None
                and not _LIST_ITEM.match(block.text) and not _QUOTE.match(block.text)
                and _version_keys(block.text) - {target}):
            other_release_named = True

        if block.kind != "alert":
            continue
        if block.alert not in NOTICE_ALERTS:
            continue
        declaring = [s for s in _sentences(block.text) if _declares(s)]
        if not declaring:
            generic += 1
            continue
        where = owner_of(section)
        named = set().union(*(_version_keys(s) for s in declaring))
        place = "above the first release heading" if section == "preamble" else "under a release heading"
        if where == "other":
            outside.append(f"{block.alert} alert declaring a known issue sits in another release's notes")
        elif target is None:
            ambiguous.append(f"{block.alert} alert declares a known issue but the record version is unreadable")
        elif named - {target}:
            ambiguous.append(f"{block.alert} alert {place} declares a known issue naming another version")
        elif where == "ambiguous" and target not in named:
            if section == "preamble" and preamble_owner == "ambiguous":
                why = "the body's first release heading is another version"
            elif section == "ambiguous":
                why = "its release heading names more than one version"
            else:
                why = "an earlier line names another release"
            ambiguous.append(f"{block.alert} alert {place} declares a known issue but {why}")
        else:
            declared.append(f"{block.alert} alert {place} declares a known issue"
                            + (" naming this version" if target in named else ""))
    close_ki()

    if declared:
        return Assessment(DECLARED, "; ".join(declared))
    if ambiguous:
        return Assessment(UNKNOWN, "; ".join(ambiguous))
    seen = []
    if outside:
        seen.extend(outside)
    if generic:
        seen.append(f"{generic} alert(s) with no known-issue declaration")
    if empty_sections:
        seen.append(f"{empty_sections} empty Known Issues section(s)")
    return Assessment(NOT_DECLARED, "; ".join(seen) if seen else "no alert or Known Issues section")


def field_value(body: Any, version: Any) -> str | None:
    """The record field's value: ``declared``, or None (absent) for not declared and unknown alike."""
    return DECLARED if assess(body, version).declared else None
