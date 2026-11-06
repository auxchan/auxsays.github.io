#!/usr/bin/env python3
"""Audited fill of the day each stored OBS Studio report was posted, where the store has none (AUX-090).

WHY. Every OBS row reached the evidence store without a `source_date`. The OBS acceptance authority
already reads each report's own date for its release-date gate (collect_obs_reports.issue_source_date:
the GitHub issue's created_at; the forum opening post's own <time>), but the evidence row it builds
never carried that date, so every OBS report on a patch page read "date not recorded".

WHICH FIELD. `source_date` is the store's field for the day the REPORT ITSELF was written, in every
lane that fills it: the PowerPoint GitHub lane stores the issue's created_at, the Windows Tech Community
lane stores the page's original post date (lib/post_dates), Teams stores the question's dateCreated and
Premiere the first post's creationDate. A feed's last-activity stamp was a collector INPUT defect that
those lanes fixed by writing the original date into this field (AUX-020 is the one deferred residual,
PowerPoint's Learn RSS gate). No other creation-date field exists in the store, so this fills
`source_date` with the same meaning and the store's format, the day 'YYYY-MM-DD' in UTC.

WHICH DATE. The creation time of the report the row's own URL names, read from the public source:
  github_issue          the issue's created_at (REST), never updated_at or closed_at
  github_issue_comment  the comment's own created_at, never its parent issue's
  forum_opening_post    the first <time> inside the opening post's own article
                        (obs_forum_source.parse_opening_post), never the page's last activity
  forum_reply           the <time> inside the reply's own article (data-content="post-<id>"), never
                        the opening post's
Every OBS row stored today is an issue opener or a forum opening post; the two reply kinds exist so
that a reply can never be dated by the post it answers.

WHAT IS PINNED. audit/obs_report_dates.json holds, per row, the five-field identity, the block hash
before and after, the day, and its source: kind, public URL, the timestamp exactly as the source served
it, its UTC form and the author. A day with no source timestamp, a day that is not that timestamp's UTC
day, a kind that does not match the URL's shape, or a report created after the row's own captured_at
refuses the whole run.

THE EDIT is one line per row and nothing else: `  source_date: null` becomes `  source_date: 'D'`, or,
on a row with no source_date key, `  source_date: 'D'` is inserted directly after its `  captured_at:`
line, which is where the store's field order puts it. captured_at, counted, exclusion_reason, the
identity and every other byte stay; target_release_date and source_date_pass are NOT set, so no
acceptance gate reads anything new and no count can move. Counted rows only.

The mechanism is AUX-072's and AUX-088's, imported: five-field selection, the store block splitter
with its row-for-block proof, pinned before/after block hashes, a field-by-field proof that nothing but
the date moved, dry run by default, `--write --confirm-write`, all or nothing, idempotent.
`--regenerate` then runs the OBS lane's scoped writers (build_consensus_from_evidence.py --product-id
obs-studio --reconcile-only, apply_consensus_to_records.py --product-id obs-studio --write-all
--confirm-write), which project the dates into the records' source lists.

`--verify-sources` re-reads every pinned source, one request at a time, and compares (network; never
part of a write).

  python auxsays/scripts/fill_obs_report_dates.py                                     # dry run
  python auxsays/scripts/fill_obs_report_dates.py --write --confirm-write --regenerate
         ... --audit PATH --parent-commit SHA                                # also write the audit
  python auxsays/scripts/fill_obs_report_dates.py --verify-sources                    # re-read sources

Exit: 0 dry run, written, nothing left to do, or sources verified; 1 refused (nothing written) or a
source disagrees; 2 usage error; 3 a scoped writer failed after the store step.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import withdraw_live_citation_rows as aux088  # noqa: E402
from lib.report_counts import counted_evidence_counts  # noqa: E402
from patch_collectors import obs_forum_source as forum  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
STORE = ROOT / "_data" / "consensus_evidence.yml"
MANIFEST = SCRIPTS / "audit" / "obs_report_dates.json"

PRODUCT_ID = "obs-studio"
FIELD = "source_date"
EOL = aux088.EOL
SELECTOR = aux088.SELECTOR
KINDS = ("github_issue", "github_issue_comment", "forum_opening_post", "forum_reply")
Refusal = aux088.Refusal
sha = aux088.sha
identity = aux088.identity

DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
NULL_LINE = EOL + "  " + FIELD + ": null" + EOL
FIELD_PREFIX = EOL + "  " + FIELD + ":"
CAPTURED_LINE_RE = re.compile(r"\n  captured_at: [^\n]*\n")
GH_ISSUE_RE = re.compile(r"^https://github\.com/obsproject/obs-studio/issues/([0-9]+)$")
GH_COMMENT_RE = re.compile(r"^https://github\.com/obsproject/obs-studio/issues/([0-9]+)#issuecomment-([0-9]+)$")
FORUM_THREAD_RE = re.compile(r"^https://obsproject\.com/forum/threads/(?:[^/#?]*\.)?([0-9]+)/?$")
FORUM_REPLY_RE = re.compile(
    r"^https://obsproject\.com/forum/threads/(?:[^/#?]*\.)?([0-9]+)/(?:post-|#post-)([0-9]+)$")
STAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)(Z|[+-]\d{2}:?\d{2})$")
WRITERS = (
    ("build_consensus_from_evidence.py", "--product-id", PRODUCT_ID, "--reconcile-only"),
    ("apply_consensus_to_records.py", "--product-id", PRODUCT_ID, "--write-all", "--confirm-write"),
)
GITHUB_API = "https://api.github.com/repos/obsproject/obs-studio"
USER_AGENT = forum.USER_AGENT


# ---------------------------------------------------------------------------------------------------
# What a URL names, and when that post was created. Pure functions over the public source.

def source_kind(url: str) -> tuple[str, dict[str, str]]:
    """The kind of post a row's URL names, with its ids; ("", {}) when it names none we can date."""
    url = str(url or "").strip()
    for kind, pattern, names in (("github_issue_comment", GH_COMMENT_RE, ("issue", "comment_id")),
                                 ("github_issue", GH_ISSUE_RE, ("issue",)),
                                 ("forum_reply", FORUM_REPLY_RE, ("thread", "post_id")),
                                 ("forum_opening_post", FORUM_THREAD_RE, ("thread",))):
        match = pattern.match(url)
        if match:
            return kind, dict(zip(names, match.groups()))
    return "", {}


def utc_instant(stamp: Any) -> datetime | None:
    """A served timestamp as an aware UTC datetime; None for a naive or unparseable one (never guessed)."""
    match = STAMP_RE.match(str(stamp or "").strip())
    if not match:
        return None
    zone = match.group(2)
    if zone != "Z" and ":" not in zone:
        zone = zone[:3] + ":" + zone[3:]
    try:
        value = datetime.fromisoformat(match.group(1) + ("+00:00" if zone == "Z" else zone))
    except ValueError:
        return None
    return value.astimezone(timezone.utc)


def utc_day(stamp: Any) -> str:
    instant = utc_instant(stamp)
    return instant.strftime("%Y-%m-%d") if instant else ""


def utc_text(stamp: Any) -> str:
    instant = utc_instant(stamp)
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ") if instant else ""


def created_at_from_github(url: str, payload: Any) -> str:
    """The creation timestamp of the GitHub post `url` names. For an issue, `payload` is the issue;
    for a comment it is THE COMMENT (GET /issues/comments/<id>), and its own created_at is the answer,
    never the issue's."""
    kind, ids = source_kind(url)
    if not isinstance(payload, dict):
        raise Refusal(f"no GitHub payload for {url}")
    if kind == "github_issue":
        if str(payload.get("number") or "") != ids["issue"] or "pull_request" in payload:
            raise Refusal(f"the payload is not issue {ids['issue']}")
        return str(payload.get("created_at") or "")
    if kind == "github_issue_comment":
        if (str(payload.get("id") or "") != ids["comment_id"]
                or not str(payload.get("issue_url") or "").endswith("/issues/" + ids["issue"])):
            raise Refusal(f"the payload is not comment {ids['comment_id']} on issue {ids['issue']}")
        return str(payload.get("created_at") or "")
    raise Refusal(f"not a GitHub issue or comment URL: {url}")


def forum_post_time(page_html: str, post_id: str) -> str:
    """The <time> inside the article of post `post_id`, bounded to that article; "" when absent."""
    html = str(page_html or "")
    tags = list(forum._ARTICLE_TAG_RE.finditer(html))  # noqa: SLF001 - the forum module's own markup
    for index, tag in enumerate(tags):
        found = forum._POST_ID_RE.search(tag.group(0))  # noqa: SLF001
        if found and found.group(1) == str(post_id):
            end = tags[index + 1].start() if index + 1 < len(tags) else len(html)
            stamp = forum._TIME_RE.search(html[tag.end():end])  # noqa: SLF001
            return stamp.group(1) if stamp else ""
    return ""


def created_at_from_forum(url: str, page_html: str) -> str:
    """The creation timestamp of the forum post `url` names, from its thread page."""
    kind, ids = source_kind(url)
    if kind == "forum_opening_post":
        post = forum.parse_opening_post(str(page_html or ""))
        return str(post.get("created_at") or "") if post else ""
    if kind == "forum_reply":
        return forum_post_time(page_html, ids["post_id"])
    raise Refusal(f"not an OBS forum thread or post URL: {url}")


# ---------------------------------------------------------------------------------------------------
# The pinned manifest.

def _ident(entry: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(entry.get(key) or "") for key in SELECTOR)


def entry_refusal(entry: dict[str, Any]) -> str:
    """'' when an entry's date is backed by a source timestamp it can be checked against."""
    ident = _ident(entry)
    day = str(entry.get(FIELD) or "")
    source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
    stamp = str(source.get("created_at") or "")
    if not DAY_RE.match(day):
        return f"no day for {ident[3]}"
    if not stamp or not str(source.get("url") or ""):
        return f"a date without a source timestamp: {ident[3]}"
    if str(source.get("url")) != ident[4]:
        return f"the source is not the row's own URL: {ident[3]}"
    kind = str(source.get("kind") or "")
    if kind not in KINDS or source_kind(ident[4])[0] != kind:
        return f"kind {kind!r} does not match the URL of {ident[3]}"
    if utc_instant(stamp) is None:
        return f"the source timestamp has no zone or does not parse: {ident[3]}"
    if utc_day(stamp) != day:
        return f"the day is not the UTC day of the source timestamp: {ident[3]}"
    if str(source.get("created_at_utc") or "") != utc_text(stamp):
        return f"the recorded UTC instant disagrees with the source timestamp: {ident[3]}"
    return ""


def manifest_entries(doc: dict[str, Any]) -> list[dict[str, Any]]:
    if list(doc.get("selector") or []) != list(SELECTOR):
        raise Refusal("manifest: the selector is not the five-field identity")
    if doc.get("product_id") != PRODUCT_ID or doc.get("field") != FIELD:
        raise Refusal("manifest: not an OBS source_date manifest")
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        raise Refusal("manifest: no entries")
    seen: set[tuple[str, ...]] = set()
    for entry in entries:
        ident = _ident(entry)
        if ident[0] != PRODUCT_ID or ident[2]:
            raise Refusal(f"manifest: not an OBS row (OBS has no build): {ident}")
        if not all(ident[i] for i in (1, 3, 4)):
            raise Refusal(f"manifest: an entry lacks part of the five-field identity: {ident}")
        if ident in seen:
            raise Refusal(f"manifest: identity listed twice: {ident}")
        seen.add(ident)
        if not all(aux088.SHA256_RE.match(str(entry.get(k) or "")) for k in ("block_sha256_before",
                                                                             "block_sha256_after")):
            raise Refusal(f"manifest: missing or malformed block hash for {ident[3]}")
        why = entry_refusal(entry)
        if why:
            raise Refusal("manifest: " + why)
    return entries


def load_manifest(path: Path) -> list[dict[str, Any]]:
    return manifest_entries(json.loads(Path(path).read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------------------------------
# The edit and its proof.

def date_line(day: str) -> str:
    return "  " + FIELD + ": '" + day + "'"


def date_block(block: str, day: str) -> str:
    """One line: a null date becomes the day, or the day is inserted right after captured_at."""
    present = block.count(FIELD_PREFIX)
    if present == 1 and block.count(NULL_LINE) == 1:
        return block.replace(NULL_LINE, EOL + date_line(day) + EOL, 1)
    if present:
        raise Refusal("unexpected block shape: the row already carries a non-null source_date")
    captured = list(CAPTURED_LINE_RE.finditer(block))
    if len(captured) != 1:
        raise Refusal(f"unexpected block shape: {len(captured)} captured_at lines")
    cut = captured[0].end()
    return block[:cut] + date_line(day) + EOL + block[cut:]


def _expected_keys(old: dict[str, Any]) -> list[str]:
    keys = list(old)
    if FIELD in keys:
        return keys
    at = keys.index("captured_at") + 1
    return keys[:at] + [FIELD] + keys[at:]


def _obs_counts(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], int]:
    # OBS has no build contract, so the Windows identity gate has no targets to read here.
    return counted_evidence_counts([r for r in rows if str(r.get("product_id") or "") == PRODUCT_ID],
                                   windows_targets={})


def plan(text: str, entries: list[dict[str, Any]]) -> dict[str, Any]:  # noqa: PLR0912
    """Decide every entry and prove the resulting text, without writing. Raises Refusal."""
    blocks = aux088.aux072.store_blocks(text)
    by_identity: dict[tuple[str, ...], list[int]] = {}
    for index, (_lo, _hi, row) in enumerate(blocks):
        by_identity.setdefault(identity(row), []).append(index)

    refusals: list[str] = []
    decided: list[dict[str, Any]] = []
    edits: dict[int, tuple[str, str]] = {}
    for entry in entries:
        ident = _ident(entry)
        label = f"{ident[1]} {ident[3]}"
        hits = by_identity.get(ident, [])
        if len(hits) != 1:
            refusals.append(f"{len(hits)} blocks match the five-field identity of {label}")
            continue
        index = hits[0]
        lo, hi, row = blocks[index]
        block, day = text[lo:hi], entry[FIELD]
        digest = sha(block)
        item = {**dict(zip(SELECTOR, ident)), FIELD: day, "kind": entry["source"]["kind"],
                "block_sha256_before_run": digest}
        if digest == entry["block_sha256_after"]:
            if row.get(FIELD) != day:
                refusals.append(f"pinned dated block carries another date: {label}")
                continue
            item["action"] = "already_dated"
            decided.append(item)
            continue
        if digest != entry["block_sha256_before"]:
            refusals.append(f"block changed since the manifest was pinned: {label}")
            continue
        if row.get("counted") is not True:
            refusals.append(f"not a counted row: {label}")
            continue
        if row.get(FIELD) not in (None, ""):
            refusals.append(f"the row already carries a date: {label}")
            continue
        captured, created = utc_instant(row.get("captured_at")), utc_instant(entry["source"]["created_at"])
        if captured is None or created is None or created > captured:
            refusals.append(f"the report would be dated after it was captured: {label}")
            continue
        try:
            new_block = date_block(block, day)
        except Refusal as exc:
            refusals.append(f"{label}: {exc}")
            continue
        if sha(new_block) != entry["block_sha256_after"]:
            refusals.append(f"the edit does not produce the pinned block for {label}")
            continue
        edits[index] = (new_block, day)
        item["action"] = "date"
        decided.append(item)
    if refusals:
        raise Refusal("; ".join(refusals))

    pieces, cursor = [], 0
    for index in sorted(edits):
        lo, hi, _row = blocks[index]
        pieces += [text[cursor:lo], edits[index][0]]
        cursor = hi
    new_text = "".join(pieces) + text[cursor:]

    rows_before = [row for _lo, _hi, row in blocks]
    rows_after = [row for _lo, _hi, row in aux088.aux072.store_blocks(new_text)]
    if len(rows_after) != len(rows_before):
        raise Refusal("the edit changed the row count")
    for index, (old, new) in enumerate(zip(rows_before, rows_after)):
        if index not in edits:
            if new != old:
                raise Refusal(f"the edit changed an unselected row at {index} ({old.get('id')})")
            continue
        # The whole row, captured_at included, must equal the old row plus the date, in the store's key order.
        if new != dict(old, **{FIELD: edits[index][1]}) or list(new) != _expected_keys(old):
            raise Refusal(f"the edit changed more than the date at row {index} ({old.get('id')})")
    counted_before = {identity(r) for r in rows_before if r.get("counted") is True}
    counted_after = {identity(r) for r in rows_after if r.get("counted") is True}
    if counted_before != counted_after:
        raise Refusal("the edit changed which rows count")
    before, after = _obs_counts(rows_before), _obs_counts(rows_after)
    if before != after:
        raise Refusal("the edit changed a count")
    undated = sorted(" ".join(identity(r)[1:4:2]) for r in rows_after
                     if r.get("product_id") == PRODUCT_ID and r.get("counted") is True and not r.get(FIELD))
    return {
        "new_text": new_text,
        "entries": decided,
        "dated_now": len(edits),
        "counted_obs_rows": len([r for r in rows_after if r.get("product_id") == PRODUCT_ID
                                 and r.get("counted") is True]),
        "counted_obs_rows_still_undated": undated,
    }


def run(store: Path, manifest: Path, write: bool) -> dict[str, Any]:
    raw = Path(store).read_bytes()
    result = plan(raw.decode("utf-8"), load_manifest(manifest))
    new_text = result.pop("new_text")
    result.update({
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "store_sha256_before": sha(raw),
        "store_sha256_after": sha(new_text),
        "manifest_sha256": sha(Path(manifest).read_bytes()),
        "written": False,
    })
    if write and result["dated_now"]:
        Path(store).write_bytes(new_text.encode("utf-8"))
        result["written"] = True
    return result


# ---------------------------------------------------------------------------------------------------
# Re-reading the sources (network, operator-run, never part of a write).

def _http(url: str, accept: str) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept": accept}
    token = os.getenv("GITHUB_TOKEN") if url.startswith("https://api.github.com/") else None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:  # noqa: S310
        return response.read()


def fetch_github(path: str) -> Any:
    time.sleep(0.4)
    return json.loads(_http(GITHUB_API + path, "application/vnd.github+json").decode("utf-8"))


def fetch_forum(url: str) -> str:
    time.sleep(3.0)
    return _http(url, "text/html").decode("utf-8", errors="replace")


def served_created_at(url: str, fetch_json: Callable[[str], Any], fetch_text: Callable[[str], str]) -> str:
    kind, ids = source_kind(url)
    if kind == "github_issue":
        return created_at_from_github(url, fetch_json(f"/issues/{ids['issue']}"))
    if kind == "github_issue_comment":
        return created_at_from_github(url, fetch_json(f"/issues/comments/{ids['comment_id']}"))
    if kind in ("forum_opening_post", "forum_reply"):
        thread = url.split("#", 1)[0]
        thread = re.sub(r"/post-[0-9]+$", "/", thread)
        return created_at_from_forum(url, fetch_text(thread))
    raise Refusal(f"cannot date {url}")


def verify_sources(entries: list[dict[str, Any]], fetch_json: Callable[[str], Any] = fetch_github,
                   fetch_text: Callable[[str], str] = fetch_forum) -> list[dict[str, Any]]:
    """Each entry's source re-read and re-derived; the list of disagreements (empty when all agree)."""
    disagreements = []
    for entry in entries:
        try:
            served = served_created_at(entry["source_url"], fetch_json, fetch_text)
        except Exception as exc:  # noqa: BLE001 - any failure to re-read is a disagreement, never a pass
            served = f"unreadable: {type(exc).__name__}"
        if served != entry["source"]["created_at"] or utc_day(served) != entry[FIELD]:
            disagreements.append({"id": entry["id"], "update_version": entry["update_version"],
                                  "pinned": entry["source"]["created_at"], "served": served})
    return disagreements


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--store", type=Path, default=STORE)
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--write", action="store_true", help="apply the dates in place")
    ap.add_argument("--confirm-write", action="store_true", help="required together with --write")
    ap.add_argument("--regenerate", action="store_true",
                    help="after the store step, run the OBS scoped writers (default tree only)")
    ap.add_argument("--audit", type=Path, help="also write the run's audit JSON here")
    ap.add_argument("--parent-commit", default="", help="commit the store was read at (audit only)")
    ap.add_argument("--verify-sources", action="store_true",
                    help="re-read every pinned source over the network and compare; writes nothing")
    args = ap.parse_args(argv)
    if args.write != args.confirm_write:
        print("refusing: --write and --confirm-write must be given together")
        return 2
    if args.regenerate and not args.write:
        print("refusing: --regenerate needs --write --confirm-write")
        return 2
    if args.verify_sources and args.write:
        print("refusing: --verify-sources never writes")
        return 2
    if args.regenerate and Path(args.store).resolve() != STORE.resolve():
        print("refusing: --regenerate runs the writers over the default tree, so --store must be the default")
        return 2
    try:
        if args.verify_sources:
            entries = load_manifest(args.manifest)
            bad = verify_sources(entries)
            for item in bad:
                print(f"  DISAGREES {item['update_version']} {item['id']}: pinned {item['pinned']} served {item['served']}")
            print(f"sources re-read: {len(entries)}, disagreeing: {len(bad)}")
            return 1 if bad else 0
        result = run(args.store, args.manifest, args.write)
    except Refusal as exc:
        print("REFUSED, nothing written: " + str(exc))
        return 1
    actions: dict[str, int] = {}
    for item in result["entries"]:
        actions[item["action"]] = actions.get(item["action"], 0) + 1
    print(f"entries: {len(result['entries'])} {json.dumps(actions, sort_keys=True)}")
    print(f"rows to date: {result['dated_now']} (written: {'yes' if result['written'] else 'no'})")
    print(f"counted OBS rows: {result['counted_obs_rows']}, still without a date: "
          f"{len(result['counted_obs_rows_still_undated'])}")
    status = 0
    if args.regenerate:
        result["writers"] = aux088.regenerate(WRITERS)
        for step in result["writers"]:
            print(f"writer rc={step['returncode']}: {step['command']}")
        if any(step["returncode"] != 0 for step in result["writers"]):
            print("a scoped writer failed after the store step; see the audit")
            status = 3
    if args.audit:
        audit = dict(result, parent_commit=args.parent_commit)
        args.audit.write_bytes((json.dumps(audit, indent=1, ensure_ascii=False) + EOL).encode("utf-8"))
    if result["written"]:
        print(f"WROTE {args.store}")
    elif args.write:
        print("nothing to write (idempotent)")
    else:
        print("dry run: pass --write --confirm-write to apply")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
