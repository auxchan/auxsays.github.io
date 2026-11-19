"""Remove contributor account handles from GitHub release notes, and nothing else.

GitHub's generated release notes credit every change to an account ("Fix a crash by @someone in
https://github.com/org/repo/pull/123") and list each first-time contributor ("* @someone made their
first contribution in ..."). An account name is personal data, and AUXSAYS does not need it: a reader
deciding whether to install a release needs the change and the pull request, not who wrote it.

WHAT IS REMOVED, and only this:
  * a credit fragment: " by @a" (also "by @a and @b", "by @a, @b", "by @a with @b") when it is
    followed by the pull-request reference, a raw pull URL, the end of the line, or a closing
    full stop -- the shapes GitHub's generator and AUXSAYS's own normalisation produce;
  * a "New Contributors" list line ("* @a made their first contribution in <url>"), and the
    "New Contributors" heading once its list is empty.

WHAT IS KEPT, deliberately:
  * the change text, every pull-request and issue link, the "Full changelog" link;
  * a handle that is the SUBJECT of a line ("Mention @a in the docs"), because it is not a credit;
  * anything that only looks like a handle: a scoped package (@scope/name), a ref (repo@sha,
    actions/checkout@v4), an e-mail address, a decorator. None of them is followed by a credit
    terminator, and none is preceded by " by ".
  * any credit a vendor wrote in its own words ("thanks to ..."): it is attribution, not the
    generator's credit fragment, and it is left as the vendor wrote it.

The public git history keeps every earlier version of these files; removing the handles here changes
what AUXSAYS publishes from now on, not what was published before.
"""
from __future__ import annotations

import re

# A GitHub account name: alphanumerics and single inner hyphens, at most 39 characters; a GitHub
# App's account carries a "[bot]" suffix.
HANDLE = r"@[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}(?:\[bot\])?"
_JOINER = r"\s*(?:,|\band\b|&|\bwith\b)\s*"

# What may follow a credit for it to be one: the PR reference AUXSAYS normalises to ("([PR #12](")
# or its plain-text summary form ("(PR #12"), GitHub's raw form (" in https://..."), the end of the
# line (optionally after a full stop or comma), or a full stop or comma that ends a sentence. A
# dotted or slashed name ("@torch.compile", "@scope/pkg") never ends at one of these.
_CREDIT_RE = re.compile(
    r"[ \t]+by[ \t]+" + HANDLE + r"(?:" + _JOINER + HANDLE + r")*"
    r"(?=[ \t]+\(\[PR[ \t]+#\d+\]\(|[ \t]+\(PR\b|[ \t]+in[ \t]+https?://|[.,]?[ \t]*$|[.,][ \t])",
    re.M)
_NEW_CONTRIBUTOR_LINE_RE = re.compile(
    r"^[ \t]*[*+-][ \t]+" + HANDLE + r"[ \t]+made[ \t]+(?:their|his|her|its)[ \t]+first[ \t]+"
    r"contribution\b[^\r\n]*$")
_NEW_CONTRIBUTORS_HEADING_RE = re.compile(r"^[ \t]*#{1,6}[ \t]+New Contributors[ \t]*$", re.I)
_LIST_ITEM_RE = re.compile(r"^[ \t]*[*+-][ \t]+")

# The same two shapes after strip_markdown_for_summary has flattened a body into one line of text.
_SUMMARY_NEW_CONTRIBUTORS_RE = re.compile(
    r"[ \t]*\bNew Contributors\b(?:[ \t]+" + HANDLE +
    r"(?:[ \t]+made[ \t]+(?:their|his|her|its)[ \t]+first[ \t]+contribution(?:[ \t]+in[ \t]+\S+)?)?)+")


def _split_lines(text: str) -> list[tuple[str, str]]:
    """(content, line ending) pairs, so CRLF bodies keep their exact line endings."""
    out: list[tuple[str, str]] = []
    for raw in text.splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        out.append((content, raw[len(content):]))
    return out


def strip_contributor_credits(body: str) -> str:
    """A release-notes body (Markdown) with contributor handles removed as described above."""
    text = str(body or "")
    if "@" not in text:
        return text
    lines = _split_lines(text)
    removed = [bool(_NEW_CONTRIBUTOR_LINE_RE.match(content)) for content, _ending in lines]
    result: list[tuple[str, str]] = []
    index = 0
    while index < len(lines):
        content, ending = lines[index]
        if removed[index]:
            index += 1
            continue
        if _NEW_CONTRIBUTORS_HEADING_RE.match(content):
            # The heading goes only when it headed a list of handle lines and nothing of that list
            # is left; the blank lines after it go with it, the ones before it still separate.
            following = index + 1
            while following < len(lines) and not lines[following][0].strip():
                following += 1
            emptied = following < len(lines) and removed[following]
            rest = following
            while rest < len(lines) and (removed[rest] or not lines[rest][0].strip()):
                rest += 1
            if emptied and (rest >= len(lines) or not _LIST_ITEM_RE.match(lines[rest][0])):
                index = rest
                continue
        result.append((_CREDIT_RE.sub("", content), ending))
        index += 1
    out = "".join(content + ending for content, ending in result)
    return out.rstrip() if out != text and text == text.rstrip() else out


def strip_contributor_credits_from_summary(summary: str) -> str:
    """The same removal for a one-line plain-text summary built from such a body."""
    text = str(summary or "")
    if "@" not in text:
        return text
    text = _SUMMARY_NEW_CONTRIBUTORS_RE.sub("", text)
    text = _CREDIT_RE.sub("", text)
    return text.strip()
