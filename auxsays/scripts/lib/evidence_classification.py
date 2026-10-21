"""Deterministic classification primitives shared by the evidence collectors.

WHY THIS MODULE EXISTS. `issue_theme` and `platform` are PUBLISHED PROSE. The patch page prints
"Current reports mention <theme>", so a classifier that guesses becomes a sentence a reader
believes. Two Adobe collectors guessed, in two different ways.

Premiere classified with a first-match substring scan -- no word boundaries, no title weighting --
over `parent_title + report_title + report_text`. Reproduced against the shipped function on the
live corpus, it published:

    "500 GB mSata (External - Cache & Render)"       -> export/render failure  (a disk label)
    "Premiere 26.2.2 unstable", body opening
      "windows and menus freeze, rendering seems
       much slower"                                  -> export/render failure  (secondary clause)
                                                     -> platform: windows     (a UI noun)
    "OS: [Windows 11 Pro 24H2 / macOS version]"      -> platform: windows     (unfilled template)
    an explicit macOS freeze report                  -> unspecified issue     (under-classified)
    "There is no crash at all after the update"      -> application crash or hang

The last one is the worst kind: the published theme contradicts the reporter's own sentence.

Acrobat had already repaired the theme half for itself, and recorded what the substring scan had
cost: 59 of 63 counted rows whose own TITLE said crash/freeze/hang published a different theme,
because `sign` matched "de-SIGN" and "SIGN in" and was tested before `crash`. Its platform half was
still the same ordered membership scan as Premiere's, so a stated macOS report was labelled
`windows` whenever the word appeared anywhere -- including as a UI noun.

THE THREE CONCERNS, deliberately separable and separately testable:

  THEME     scored word-boundary rules over the reporter's own heading and body, the heading
            weighted far above the body, best match wins, first rule in table order winning a
            tie. Generalised from Acrobat. The theme TABLES stay with the collectors: Acrobat's
            taxonomy and Premiere's describe different products and feed different published
            sentences, so sharing the mechanism is correct and sharing the vocabulary is not.

  NEGATION  a clause-local guard, NOT a language engine. An explicitly denied symptom does not
            score, and nothing else changes -- a report that denies a crash while describing a
            freeze still themes as a freeze, because suppression removes one rule's hit inside one
            clause and leaves every other clause and every other rule untouched.

            It applies only to rules a collector marks `negatable=True`, and only for a PLAIN
            denial. Inability modals are deliberately excluded: "can't export", "won't launch" and
            "unable to open" are how a failure is normally REPORTED, not how it is denied. Treating
            those as denials would trade one false positive for a large recall loss, and Acrobat's
            own crash pattern matches the literal phrase `won't launch`, so a naive guard would
            have suppressed the very rule it was added to protect.

  PLATFORM  an ALLOWLIST of positive operating-system evidence. Never a denylist of UI phrasings:
            a denylist is open-ended, and every phrasing nobody thought of publishes a confident
            wrong label, while an allowlist fails toward `unknown`. `windows` is the one genuinely
            ambiguous token in English -- it is both an operating system and a UI noun -- so it
            counts only with an OS context (a version, an edition, a device noun, or a preposition
            that frames it as a platform). Two platforms named means `unknown`: one evidence row is
            one person's one observation, and "Windows, macOS" is the ADAPTER's answer to a
            different question about official release targeting.

WHAT THIS MODULE NEVER RETURNS: `sentiment`. It is verdict-bearing -- `build_consensus_from_evidence`
counts sentiments, maps them through `consensus_label` and `lib.patch_decision` into the published
install/wait/avoid verdict -- so it stays with the collector that owns that policy. A theme scorer
able to move sentiment as a side effect could move a published verdict. This one cannot, by
construction: it has no sentiment field to return.

`severity` IS returned, because it travels on the rule. An out-of-vocabulary severity does not fail
loudly downstream -- `build_consensus_from_evidence` sets `exclusion_reason: invalid_severity` and
SILENTLY UN-COUNTS the row -- so `validate_rules` refuses a bad table at import time instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Mirrored from build_consensus_from_evidence, which cannot be imported here: the collectors run as
# BARE SCRIPTS in every production lane, so a `from lib import ...` chain that reaches a top-level
# script passes the test suite and crashes the lane. test_evidence_classification asserts these two
# sets still equal the consumer's, so the mirror cannot drift silently.
VALID_SEVERITIES = frozenset({"low", "medium", "high", "critical"})
VALID_SENTIMENTS = frozenset({"positive", "moderate", "negative"})

#: The reporter's own one-line summary of what went wrong outweighs a passing mention buried in a
#: long body by this factor. Carried over from the Acrobat classifier unchanged.
HEADING_WEIGHT = 5

#: A plain denial must appear within this many characters BEFORE the matched symptom, in the same
#: clause, to suppress it. Bounded on purpose: an unbounded search makes one "not" at the top of a
#: long post suppress every symptom below it.
NEGATION_WINDOW = 40

#: ...and within this many intervening WORDS, which is the tighter of the two bounds and the one
#: that matters. A denial binds tightly to what it denies -- "no crash", "doesn't crash", "does not
#: seem to crash" -- so anything further away is a separate statement.
#:
#: Measured, not guessed. The 40-character bound alone was too loose on the live corpus: in
#: "OSX 10.13.4 - Acrobat Pro NOT WORKING ... my Acrobat Pro won't start up", the "NOT" of
#: "NOT WORKING" sat 31 characters before "won't start" and suppressed it, turning a COUNTED crash
#: report into "unspecified Acrobat issue". "NOT WORKING" asserts a failure; it denies nothing.
#: Five intervening words put it out of range.
NEGATION_MAX_INTERVENING_WORDS = 2

_WORD_RE = re.compile(r"[A-Za-z0-9']+")

UNKNOWN_PLATFORM = "unknown"


# --- theme -------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ThemeRule:
    """One scored theme. `key` is a stable short identifier for tests and telemetry; it is never
    published. `negatable` opts the rule into the clause-local negation guard, which is correct for
    a SYMPTOM ("no crash") and wrong for a CAPABILITY ("can't export") -- see the module docstring.
    """

    theme: str
    area: str
    severity: str
    key: str
    pattern: "re.Pattern[str]"
    negatable: bool = False


@dataclass(frozen=True)
class ThemeVerdict:
    theme: str
    area: str
    severity: str
    key: str
    score: int
    heading_hits: int
    body_hits: int
    suppressed_hits: int = 0


def validate_rules(rules: "tuple[ThemeRule, ...] | list[ThemeRule]") -> None:
    """Refuse a malformed theme table. Called at import time by every collector that ships one."""
    seen: set[str] = set()
    for index, rule in enumerate(rules):
        where = f"rule {index} ({rule.key or '<no key>'})"
        if not rule.theme or not rule.theme.strip():
            raise ValueError(f"{where}: empty theme, which would publish an empty sentence")
        if not rule.area or not rule.area.strip():
            raise ValueError(f"{where}: empty workflow_area")
        if rule.severity not in VALID_SEVERITIES:
            raise ValueError(
                f"{where}: severity {rule.severity!r} is outside {sorted(VALID_SEVERITIES)}; "
                "build_consensus_from_evidence would silently un-count every row it labels")
        if not rule.key or not rule.key.strip():
            raise ValueError(f"{where}: empty key")
        if rule.key in seen:
            raise ValueError(f"{where}: duplicate key {rule.key!r}")
        seen.add(rule.key)


# Clause boundaries. Sentence punctuation, newlines, and the contrast conjunctions, because
# "it doesn't crash but it freezes" is two claims and the denial governs only the first.
_CLAUSE_BOUNDARY_RE = re.compile(
    r"(?:[.;:!?\n\r]+|\s+(?:but|however|although|though|whereas|yet)\s+)", re.I)

# A PLAIN denial. Inability modals (can't, cannot, couldn't, won't, wouldn't, unable, fail) are
# deliberately absent: they report failures rather than deny symptoms.
#
# `without` is ALSO deliberately absent, and that was measured rather than assumed. It is genuinely
# ambiguous -- "it runs without crashing" denies the symptom, but "I can't even hit the report
# button, without Premiere freezing" ASSERTS it, because an inability modal earlier in the clause
# inverts the sense. On the stored Adobe corpus the only `without` in range of a symptom was the
# second kind, on a counted row, so including it bought one wrong suppression and nothing else.
# A double-negative rule ("cancel the denial when an inability modal precedes it in the clause")
# would recover the first kind; it is deferred as an ambiguous case rather than guessed at here.
_PLAIN_NEGATION_RE = re.compile(
    r"(?:\b(?:no|not|never|none|nothing|nor|neither)\b"
    r"|\b(?:is|are|was|were|do|does|did|has|have|had)n[o']?t\b)", re.I)


def clause_spans(text: str) -> list[tuple[int, int]]:
    """`text` split into clause spans. Always covers at least one span for non-empty text."""
    spans: list[tuple[int, int]] = []
    position = 0
    for boundary in _CLAUSE_BOUNDARY_RE.finditer(text or ""):
        if boundary.start() > position:
            spans.append((position, boundary.start()))
        position = boundary.end()
    if position < len(text or ""):
        spans.append((position, len(text)))
    return spans


def _clause_of(spans: list[tuple[int, int]], position: int) -> tuple[int, int] | None:
    for start, end in spans:
        if start <= position < end:
            return (start, end)
    return None


def is_negated(
    text: str,
    position: int,
    spans: list[tuple[int, int]] | None = None,
    *,
    protected: "tuple[tuple[int, int], ...]" = (),
) -> bool:
    """True when a plain denial precedes `position` inside the same clause, close enough to bind.

    `protected` holds the spans of the symptom pattern's OWN matches. A negation word inside one of
    them is part of a matched symptom phrase, not a denial of anything -- the live case is
    "Adobe Acrobat Pro Not Responding / Crashing", where `not responding` IS the match, and its
    "Not" was suppressing the "Crashing" sixteen characters later on a counted row.
    """
    if not text:
        return False
    spans = spans if spans is not None else clause_spans(text)
    clause = _clause_of(spans, position)
    if clause is None:
        return False
    window_start = max(clause[0], position - NEGATION_WINDOW)
    if window_start >= position:
        return False
    for marker in _PLAIN_NEGATION_RE.finditer(text, window_start, position):
        if any(start <= marker.start() < end for start, end in protected):
            continue
        intervening = _WORD_RE.findall(text[marker.end():position])
        if len(intervening) <= NEGATION_MAX_INTERVENING_WORDS:
            return True
    return False


def count_hits(text: str, pattern: "re.Pattern[str]", *, negatable: bool = False) -> tuple[int, int]:
    """(counted, suppressed) matches of `pattern` in `text`.

    With `negatable=False` this is exactly `len(pattern.findall(text))`, which is what the Acrobat
    classifier did -- so a rule that does not opt in scores identically to before.
    """
    text = text or ""
    if not text:
        return (0, 0)
    if not negatable:
        return (len(pattern.findall(text)), 0)
    spans = clause_spans(text)
    matches = list(pattern.finditer(text))
    protected = tuple((m.start(), m.end()) for m in matches)
    counted = suppressed = 0
    for match in matches:
        if is_negated(text, match.start(), spans, protected=protected):
            suppressed += 1
        else:
            counted += 1
    return (counted, suppressed)


def score_themes(
    heading: str,
    body: str,
    rules: "tuple[ThemeRule, ...] | list[ThemeRule]",
    *,
    heading_weight: int = HEADING_WEIGHT,
) -> ThemeVerdict | None:
    """Best-scoring rule, or None when nothing matched -- the caller supplies its own fallback.

    Returning None rather than a fallback rule is deliberate: a fallback that lived in the scored
    table could WIN, and in Premiere the fallback is the one branch that returns `moderate`
    sentiment, which is verdict-bearing. A rule that cannot be in the table cannot win.
    """
    best: ThemeVerdict | None = None
    for rule in rules:
        heading_hits, heading_suppressed = count_hits(heading, rule.pattern, negatable=rule.negatable)
        body_hits, body_suppressed = count_hits(body, rule.pattern, negatable=rule.negatable)
        score = heading_weight * heading_hits + body_hits
        # `>` not `>=`: the first rule in table order wins a tie, which is how the Acrobat
        # classifier already behaved and is what its five shipped checks pin.
        if score and (best is None or score > best.score):
            best = ThemeVerdict(
                theme=rule.theme,
                area=rule.area,
                severity=rule.severity,
                key=rule.key,
                score=score,
                heading_hits=heading_hits,
                body_hits=body_hits,
                suppressed_hits=heading_suppressed + body_suppressed,
            )
    return best


# --- platform ----------------------------------------------------------------------------------

@dataclass(frozen=True)
class PlatformVerdict:
    label: str
    mentioned: tuple[str, ...] = ()
    suppressed: tuple[str, ...] = ()
    basis: str = "no_platform_evidence"


#: Closed vocabulary for `PlatformVerdict.basis`. Telemetry reads it; nothing publishes it.
PLATFORM_BASES = frozenset({
    "definitional_product_platform",
    "single_platform_named",
    "multiple_platforms_named",
    "platform_evidence_suppressed",
    "no_platform_evidence",
})

# Scrubbers, applied before any allowlist runs.
# An unfilled template -- "OS: [Windows 11 Pro 24H2 / macOS version]" -- set `platform: windows` on
# two live rows. A bracketed span is the author's placeholder, not their answer.
_BRACKET_PLACEHOLDER_RE = re.compile(r"\[[^\[\]]{0,160}\]")
# A `>`-quoted line is somebody else's sentence.
_QUOTED_LINE_RE = re.compile(r"(?m)^[ \t]*>.*$")
# Everything after a bare `--` / em-dash line is a signature block.
_SIGNATURE_RE = re.compile(r"(?m)^[ \t]*(?:--|—)[ \t]*$")

_WINDOWS_WORD_RE = re.compile(r"\bwindows\b", re.I)
# Unconditional: a version number makes `win`/`windows` unambiguous. The four-digit alternative is
# Windows Server ("Windows 2016 server"), which a counted Acrobat row names exactly that way.
_WIN_VERSION_RE = re.compile(r"\bwin(?:dows)?\s?(?:7|8\.1|8|10|11|12|20\d\d)\b", re.I)
# Unconditional: a platform written as a parenthesised annotation, as in
# "...blocks UI in Acrobat 26.001.21691 (Windows) -- persists after repair". Nobody writes
# "(windows)" to mean a UI window. Parentheses only: square brackets belong to the placeholder
# scrubber, because "[Windows 11 Pro 24H2 / macOS version]" is an UNFILLED template, not an answer.
_WINDOWS_ANNOTATION_RE = re.compile(r"\(\s*(?:windows|win)\s*\)", re.I)
# `windows` preceded by something that frames it as a platform.
_WINDOWS_BEFORE_RE = re.compile(
    r"\b(?:on|under|using|running|runs|ran|installed|install|reinstall|reinstalled|upgraded|"
    r"os|o/s|platform|system|pc|laptop|desktop|machine|via|native|both)\b[\s:=,/\-]*$", re.I)
# `windows` followed by an edition, a device noun or a version label.
_WINDOWS_AFTER_RE = re.compile(
    r"^[\s:=,/\-]*(?:7|8|8\.1|10|11|12|20\d\d|pro|professional|home|enterprise|education|server|"
    r"ltsc|ltsb|build|builds|version|versions|update|updates|installer|pc|pcs|laptop|laptops|"
    r"desktop|desktops|machine|machines|box|workstation|x64|x86|arm64|insider|defender|"
    r"explorer\s+crash)\b", re.I)
_WINDOWS_CONTEXT_CHARS = 24

# macOS tokens are unambiguous on their own; no context gate is needed.
_MACOS_RE = re.compile(
    r"\b(?:mac\s?os(?:\s?x)?|osx|os\s?x|macbook(?:\s?(?:pro|air))?|imac|mac\s?mini|mac\s?studio|"
    r"mac\s?pro|monterey|ventura|sonoma|sequoia|big\s?sur|catalina|mojave|apple\s?silicon|"
    r"m[1-4]\s?(?:pro|max|ultra)?\s?mac|mac)\b", re.I)
_LINUX_RE = re.compile(
    r"\b(?:linux|ubuntu|debian|fedora|centos|rhel|rocky\s?linux|arch\s?linux|pop!?_?os)\b",
    re.I)


def scrub_platform_text(text: str) -> str:
    """Remove the three spans that are not the reporter's own statement about their own machine."""
    text = text or ""
    signature = _SIGNATURE_RE.search(text)
    if signature:
        text = text[:signature.start()]
    text = _QUOTED_LINE_RE.sub(" ", text)
    text = _BRACKET_PLACEHOLDER_RE.sub(" ", text)
    return text


def _windows_has_os_context(text: str) -> bool:
    if _WIN_VERSION_RE.search(text) or _WINDOWS_ANNOTATION_RE.search(text):
        return True
    for match in _WINDOWS_WORD_RE.finditer(text):
        before = text[max(0, match.start() - _WINDOWS_CONTEXT_CHARS):match.start()]
        after = text[match.end():match.end() + _WINDOWS_CONTEXT_CHARS]
        if _WINDOWS_BEFORE_RE.search(before) or _WINDOWS_AFTER_RE.search(after):
            return True
    return False


def _named_platforms(text: str) -> list[str]:
    named: list[str] = []
    if _windows_has_os_context(text):
        named.append("windows")
    if _MACOS_RE.search(text):
        named.append("macos")
    if _LINUX_RE.search(text):
        named.append("linux")
    return named


def resolve_platform(
    text: str,
    *,
    definitional: str | None = None,
    scrub: bool = True,
) -> PlatformVerdict:
    """Positive OS evidence from `text`, or `unknown`.

    `definitional` is the product's own platform, for a product that IS an operating system or a
    collector lane scoped to one client. It short-circuits, because `microsoft-windows-11` reports
    do not have to say the word "Windows" -- 197 of 488 of them do not, and a text-only resolver
    would wrongly downgrade every one.
    """
    if definitional:
        return PlatformVerdict(
            label=definitional,
            mentioned=(definitional,),
            basis="definitional_product_platform",
        )

    raw = text or ""
    scrubbed = scrub_platform_text(raw) if scrub else raw
    named = _named_platforms(scrubbed)
    suppressed: list[str] = []

    if "windows" not in named and _WINDOWS_WORD_RE.search(scrubbed):
        # The reproduced UI-noun case: "windows and menus freeze".
        suppressed.append("windows_without_os_context")
    if not named and scrubbed != raw and _named_platforms(raw):
        suppressed.append("platform_named_only_in_removed_span")

    if len(named) == 1:
        return PlatformVerdict(named[0], tuple(named), tuple(suppressed), "single_platform_named")
    if len(named) > 1:
        return PlatformVerdict(
            UNKNOWN_PLATFORM, tuple(named), tuple(suppressed), "multiple_platforms_named")
    return PlatformVerdict(
        UNKNOWN_PLATFORM,
        (),
        tuple(suppressed),
        "platform_evidence_suppressed" if suppressed else "no_platform_evidence",
    )
