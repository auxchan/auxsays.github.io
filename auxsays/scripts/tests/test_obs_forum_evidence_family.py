#!/usr/bin/env python3
"""Tests for the OBS second independent evidence family (obsproject.com support forum).

Offline only. The forum parser is driven from HTML fixtures and the acceptance authority from
synthetic candidate dicts; nothing here touches the network or the live consensus_evidence.yml.

The suite exists to hold three things still:

  1. The new family did not get its own evidence semantics. Both methods go through
     collect_obs_reports.evaluate_issue and evidence_row, and every deterministic gate that
     applied to a GitHub issue applies to a forum thread.
  2. A forum thread cannot smuggle in a version its opening author never claimed -- not from a
     reply, not from a quote, and not from the thread's last-activity timestamp.
  3. Health is truthful per family, and the retired known_watchlist slot cannot pass for
     independent coverage.
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import collect_obs_reports as obs
from lib import target_outcome as to_module
from lib.target_outcome import classify_target_outcome
from patch_collectors import obs as obs_adapter
from patch_collectors import obs_forum_source as forum

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
        msg = f"  FAIL  {label}"
        if detail:
            msg += f"\n        {detail}"
        print(msg)
        _ERRORS.append(label)


VER = "32.2.2"
OTHER = "32.1.2"
RELEASE = obs.parse_date("2026-08-14")

# A XenForo thread: one opening post and one reply BY A DIFFERENT AUTHOR naming a different
# version, plus a trailing page-level <time> standing in for last-activity. All three traps in
# one fixture, because they are the same trap: reading something other than the opening post.
THREAD_HTML = """
<!doctype html><html><body>
<h1 class="p-title-value">OBS crashes when starting a recording</h1>
<div class="p-body">
<article class="message message--post js-post" data-author="firstauthor"
         data-content="post-1001" id="js-post-1001">
  <header><time class="u-dt" datetime="2026-09-01T10:00:00+0000" data-date="Sep 1, 2026">Sep 1, 2026</time></header>
  <div class="bbWrapper">I updated to 32.2.2. OBS now crashes every time I start a recording.<br />Log attached.</div>
</article>
<article class="message message--post js-post" data-author="secondauthor"
         data-content="post-1002" id="js-post-1002">
  <header><time class="u-dt" datetime="2026-09-20T12:00:00+0000" data-date="Sep 20, 2026">Sep 20, 2026</time></header>
  <div class="bbWrapper">I am on 32.1.2 and I get the same crash here too.</div>
</article>
<time class="u-dt" datetime="2026-10-01T00:00:00+0000">Oct 1, 2026</time>
</div></body></html>
"""

# An opening post that QUOTES another member. The quoted text names a version; the quoting
# author never claims it.
QUOTE_THREAD_HTML = """
<!doctype html><html><body>
<h1 class="p-title-value">Recording stops on its own</h1>
<article data-author="quoter" data-content="post-2001">
  <time class="u-dt" datetime="2026-09-02T10:00:00+0000">Sep 2, 2026</time>
  <div class="bbWrapper">
    <blockquote class="bbCodeBlock"><div class="bbCodeBlock-content">
      othermember said: I am on 32.1.2 and my recording fails constantly.
    </div></blockquote>
    Same here, my recording stops on its own since I installed 32.2.2.
  </div>
</article>
</body></html>
"""

# A listing page. Includes a reply permalink under /forum/posts/, which robots.txt disallows and
# which must never become a cited report URL.
LISTING_HTML = """
<!doctype html><html><body>
<div class="structItemContainer">
  <div class="structItemContainer-group structItemContainer-group--sticky">
    <div class="structItem structItem--thread">
      <a href="/forum/threads/dropped-frames-lag-read-this-first.8870/">Dropped frames/lag? Read this first!</a>
    </div>
  </div>
  <div class="structItemContainer-group">
    <a href="/forum/threads/obs-crashes-on-record.111/">OBS crashes on record</a>
    <a href="/forum/threads/obs-crashes-on-record.111/">duplicate link to same thread</a>
    <a href="/forum/threads/audio-desync-after-update.222/">Audio desync</a>
    <a href="/forum/posts/987654/">reply permalink</a>
    <a href="/forum/whats-new/posts/">what is new</a>
  </div>
</div>
</body></html>
"""


# An opening post whose own <time> is absent. The next timestamp on the page belongs to the
# REPLY, so anything that searches past the opening article would date this thread to the reply.
NO_TIME_THREAD_HTML = """
<!doctype html><html><body>
<h1 class="p-title-value">OBS crashes when starting a recording</h1>
<article data-author="firstauthor" data-content="post-3001">
  <div class="bbWrapper">I updated to 32.2.2. OBS now crashes when I start a recording.</div>
</article>
<article data-author="secondauthor" data-content="post-3002">
  <time class="u-dt" datetime="2026-09-20T12:00:00+0000">Sep 20, 2026</time>
  <div class="bbWrapper">I am on 32.1.2 and I get the same crash.</div>
</article>
</body></html>
"""

# An opening post with no bbWrapper of its own -- the shape a XenForo class rename produces.
NO_BODY_THREAD_HTML = """
<!doctype html><html><body>
<h1 class="p-title-value">Recording stops on its own</h1>
<article data-author="firstauthor" data-content="post-4001">
  <time class="u-dt" datetime="2026-09-01T10:00:00+0000">Sep 1, 2026</time>
  <div class="messageText">I updated and now it stops.</div>
</article>
<article data-author="secondauthor" data-content="post-4002">
  <time class="u-dt" datetime="2026-09-20T12:00:00+0000">Sep 20, 2026</time>
  <div class="bbWrapper">I am on 32.1.2 and my recording fails constantly.</div>
</article>
</body></html>
"""

# Nested quotes. One non-greedy pass strips the inner block and leaves the outer text behind.
NESTED_QUOTE_HTML = """
<!doctype html><html><body>
<h1 class="p-title-value">Audio desync</h1>
<article data-author="quoter" data-content="post-5001">
  <time class="u-dt" datetime="2026-09-02T10:00:00+0000">Sep 2, 2026</time>
  <div class="bbWrapper">
    <blockquote class="bbCodeBlock"><div class="bbCodeBlock-content">
      outer said: my audio desyncs on 32.1.2
      <blockquote class="bbCodeBlock"><div class="bbCodeBlock-content">
        inner said: mine desyncs on 32.0.4 as well
      </div></blockquote>
      and 32.0.3 did it too -- this text sits AFTER the inner quote closes, which is what
      a single non-greedy pass leaves behind.
    </div></blockquote>
    I see the same desync since 32.2.2.
  </div>
</article>
</body></html>
"""


def gh_issue(title="", body="", created_at="2026-09-01T00:00:00Z", labels=None, number=1):
    return {
        "title": title,
        "body": body,
        "created_at": created_at,
        "labels": [{"name": n} for n in (labels or [])],
        "number": number,
        "html_url": f"https://github.com/obsproject/obs-studio/issues/{number}",
    }


def forum_post(body="", title="Something broke", created_at="2026-09-01T10:00:00+0000",
               thread_id="196568"):
    """A parsed forum candidate, in the shape the shared authority consumes."""
    path = f"/forum/threads/some-thread.{thread_id}/"
    return {
        "title": title,
        "body": body,
        "labels": [],
        "created_at": created_at,
        "author": "someone",
        "post_id": "1",
        "thread_path": path,
        "source_url": forum.thread_url(path),
    }


def forum_row(post, version=VER, basis="body"):
    return obs.evidence_row(post, version, basis, "2026-10-09T00:00:00Z",
                            identity=forum.row_identity(version, post, obs.slug))


def run() -> int:
    live_evidence_before = (obs.EVIDENCE_PATH.read_bytes()
                            if obs.EVIDENCE_PATH.exists() else b"")

    print("T1 existing GitHub Issues acceptance is unchanged")
    gh = obs.evidence_row(gh_issue(title="crash", body=f"{VER} crashes", number=4242),
                          VER, "body", "2026-10-09T00:00:00Z")
    check("T1.1 GitHub row id keeps its own formula",
          gh["id"] == "obs-studio-32-2-2-github-issue-4242", gh["id"])
    check("T1.2 GitHub row source_type unchanged", gh["source_type"] == "github_issue", gh["source_type"])
    check("T1.3 GitHub row source_name unchanged",
          gh["source_name"] == "obsproject/obs-studio", gh["source_name"])
    check("T1.4 GitHub row url unchanged",
          gh["source_url"] == "https://github.com/obsproject/obs-studio/issues/4242", gh["source_url"])
    # The two outcomes the exact_version_re repair deliberately moves, pinned by their real
    # shapes so a later "tidy up" of that lookahead has to confront them.
    recovered = gh_issue(title="Linux: virtual camera needs v4l2loopback restart",
                         body="### Anything else?\n\nThis started for me with 31.1.0.\n"
                              "The capture fails to restart.")
    got15 = obs.evaluate_issue(recovered, "31.1.0", obs.parse_date("2026-07-07"))
    check("T1.5 sentence-end version is now matched (obs #12506 shape)",
          got15 == ("body", None), str(got15))
    healthy = gh_issue(title="Browser source stops after double refresh",
                       body="The browser source stops displaying.\n\n"
                            f"This issue does not occur in version {VER}.")
    got16 = obs.evaluate_issue(healthy, VER, RELEASE)
    check("T1.6 a version named as HEALTHY is refused as working, not by accident",
          got16[1] == "version_reported_working", str(got16))

    print("T2 exact tracked version boundary")
    boundary = [
        (f"I recently updated to {VER}.", True, "sentence-end period"),
        (f"crash on {VER} only", True, "mid sentence"),
        (f"version {VER}, then nothing", True, "comma"),
        (f"{VER}1 is out", False, "longer version by digit"),
        (f"build {VER}.1 here", False, "longer version by component"),
        (f"in 1{VER} nope", False, "left digit boundary"),
    ]
    for text, expected, label in boundary:
        got = obs.match_basis(forum_post(body=text), VER) is not None
        check(f"T2 {label} -> {expected}", got == expected, f"{text!r} gave {got}")

    print("T3 declared-version field behaviour")
    declared_ok = gh_issue(title="no audio after update",
                           body=f"### OBS Studio Version\n{VER}\n\n### What happened?\n"
                                f"This issue does not occur in version {VER}.")
    got31 = obs.evaluate_issue(declared_ok, VER, RELEASE)
    check("T3.1 a DECLARED version is not vetoed (R1 holds)", got31[1] is None, str(got31))
    check("T3.2 a forum post declares nothing (no template field)",
          obs.declared_versions(forum_post(body=f"{VER} crashes")) == set())
    aur = gh_issue(body="### OBS Studio Version\n32.0.0.r2.ga75fdd2-1\n")
    check("T3.3 an AUR git build is NOT read as a bare declaration",
          obs.declared_versions(aur) == set(), str(obs.declared_versions(aur)))
    clean = gh_issue(body=f"### OBS Studio Version\n{VER}\n")
    check("T3.4 a clean declared value still tokenizes",
          obs.declared_versions(clean) == {VER}, str(obs.declared_versions(clean)))

    print("T4 working / fixed / rollback / reference veto, identically for both families")
    vetoes = [
        (f"The browser source stops. This issue does not occur in version {VER}.",
         "version_reported_working", "named as healthy"),
        (f"Recording crashes. I downgraded to {VER} and it works fine now.",
         "version_is_rollback_target", "rollback destination"),
        (f"Audio desync was fixed in {VER}, thanks.", "version_reported_fixed", "fixed in target"),
        (f"My capture fails on an older build (e.g. {VER}) by comparison.",
         "version_reference_only", "illustrative reference"),
    ]
    for text, expected, label in vetoes:
        gh_got = obs.evaluate_issue(gh_issue(title="issue", body=text), VER, RELEASE)[1]
        fm_got = obs.evaluate_issue(forum_post(body=text), VER, RELEASE)[1]
        check(f"T4 {label} vetoed on GitHub", gh_got == expected, f"got {gh_got}")
        check(f"T4 {label} vetoed on the forum, same reason", fm_got == expected, f"got {fm_got}")
    # The counterweight: the veto is not blanket. A rollback destination the author says ALSO
    # fails is affected, and R3 must still say so -- this is the real obsproject.com thread
    # 196545 shape. Without this the veto would silently delete legitimate evidence.
    both = (f"I was on 32.2.9 and saw green flicker. I then downgraded to OBS {VER}, "
            "and tried it again, but the exact same issue happens.")
    got_both = obs.evaluate_issue(forum_post(body=both), VER, RELEASE)
    check("T4 a rollback destination that ALSO fails is still accepted (R3)",
          got_both == ("body", None), str(got_both))
    check("T4 and its basis is an affected cue, not silence",
          classify_target_outcome(both, VER).outcome == "affected",
          classify_target_outcome(both, VER).basis)

    print("T5 a concrete user-facing issue is required")
    generic = [
        (f"Is OBS {VER} safe to install?", "question with no problem"),
        (f"OBS {VER} is now available for download.", "announcement"),
        (f"How do I set up a scene in {VER}?", "setup question"),
        (f"Anyone else running {VER}?", "general discussion"),
    ]
    for text, label in generic:
        got = obs.evaluate_issue(forum_post(title=text, body=text), VER, RELEASE)[1]
        check(f"T5 {label} refused", got == "generic_or_no_concrete_issue", f"got {got}")
    concrete = obs.evaluate_issue(
        forum_post(title="OBS crashes", body=f"Since {VER} OBS crashes when I start recording."),
        VER, RELEASE)
    check("T5 a concrete crash report is accepted", concrete == ("body", None), str(concrete))

    print("T6 developer / build-only reports are excluded")
    devs = [
        (f"cmake configure fails for {VER}: the compiler cannot find libobs headers.", "cmake"),
        (f"Build of {VER} fails in GitHub Actions with a linker error.", "ci build"),
    ]
    for text, label in devs:
        got = obs.evaluate_issue(forum_post(title="build", body=text), VER, RELEASE)[1]
        check(f"T6 {label} refused as developer/build-only",
              got == "developer_or_build_only", f"got {got}")
    enduser = obs.evaluate_issue(
        forum_post(title="recording", body=f"On {VER} my recording fails and the screen capture is black."),
        VER, RELEASE)
    check("T6 an end-user failure is NOT swept up by the developer filter",
          enduser == ("body", None), str(enduser))

    print("T7 the ORIGINAL post date is used, never last-activity and never a reply")
    opening = forum.parse_opening_post(THREAD_HTML)
    check("T7.1 the thread parses", opening is not None)
    check("T7.2 date is the opening post, not the reply or the page footer",
          opening["created_at"].startswith("2026-09-01"), opening["created_at"])
    check("T7.3 the source date resolves to the opening post day",
          obs.issue_source_date(opening) == obs.parse_date("2026-09-01"),
          str(obs.issue_source_date(opening)))
    check("T7.4 author is the opening author", opening["author"] == "firstauthor", opening["author"])
    check("T7.5 an unparseable date is NOT invented (fail closed)",
          obs.issue_source_date(forum_post(created_at="")) is None)

    print("T8 the release-date gate")
    body8 = f"Since {VER} my recording crashes every time."
    before = obs.evaluate_issue(forum_post(body=body8, created_at="2026-08-13T00:00:00+0000"), VER, RELEASE)
    on_day = obs.evaluate_issue(forum_post(body=body8, created_at="2026-08-14T00:00:00+0000"), VER, RELEASE)
    after = obs.evaluate_issue(forum_post(body=body8, created_at="2026-09-01T00:00:00+0000"), VER, RELEASE)
    undated = obs.evaluate_issue(forum_post(body=body8, created_at=""), VER, RELEASE)
    nogate = obs.evaluate_issue(forum_post(body=body8, created_at=""), VER, None)
    check("T8.1 a report before the release date is refused",
          before[1] == "before_release_date", str(before))
    check("T8.2 a report ON the release date is accepted", on_day == ("body", None), str(on_day))
    check("T8.3 a report after the release date is accepted", after == ("body", None), str(after))
    check("T8.4 a missing source date FAILS CLOSED when the release date is known",
          undated[1] == "missing_source_date", str(undated))
    check("T8.5 the gate is inactive when the release date is unknown (no date invented)",
          nogate == ("body", None), str(nogate))

    print("T9 the cited URL is one specific report")
    row = forum_row(forum_post(body=f"{VER} crashes on record", thread_id="196568"))
    check("T9.1 the row cites a specific thread URL",
          row["source_url"] == "https://obsproject.com/forum/threads/some-thread.196568/",
          row["source_url"])
    check("T9.2 the row id is keyed on the stable thread id",
          row["id"] == "obs-studio-32-2-2-obs-forum-thread-196568", row["id"])
    # The slug can be edited; the numeric id cannot. Two runs that see different slugs for one
    # thread must not produce two rows.
    renamed = dict(forum_post(body=f"{VER} crashes on record", thread_id="196568"))
    renamed["thread_path"] = "/forum/threads/a-totally-different-slug.196568/"
    check("T9.3 an edited thread slug does not change the row identity",
          forum_row(renamed)["id"] == row["id"], forum_row(renamed)["id"])
    paths = forum.list_thread_paths(LISTING_HTML)
    check("T9.4 the listing yields thread paths, de-duplicated",
          paths == ["/forum/threads/obs-crashes-on-record.111/",
                    "/forum/threads/audio-desync-after-update.222/"], str(paths))
    check("T9.5 a /forum/posts/ reply permalink is never collected",
          not any("/forum/posts/" in path for path in paths), str(paths))

    print("T10 pinned advice guides are excluded at discovery, not at acceptance")
    sticky = forum.sticky_thread_paths(LISTING_HTML)
    check("T10.1 the sticky group is recognised",
          sticky == {"/forum/threads/dropped-frames-lag-read-this-first.8870/"}, str(sticky))
    listed = forum.list_thread_paths(LISTING_HTML)
    check("T10.2 a pinned thread is not enumerated as a candidate",
          not any("read-this-first" in path for path in listed), str(listed))
    with_sticky = forum.list_thread_paths(LISTING_HTML, include_sticky=True)
    check("T10.3 the exclusion is what removes it, not the fixture",
          len(with_sticky) == len(listed) + 1, f"{len(with_sticky)} vs {len(listed)}")
    # WHY discovery has to carry this. The authority judges text, and a staff advice guide is
    # written in the vocabulary of the problems it is about -- the real thread 8870 title
    # alone carries three concrete-issue terms. Asserting that the authority WOULD take it is
    # the honest pin: it records that the sticky exclusion is load-bearing, so nobody deletes
    # it believing the acceptance gates already cover this.
    guide = forum_post(
        title="Dropped frames/disconnecting/lag? Read this first!",
        body=("NOTE: This thread contains EVERY piece of dropped frames / disconnect advice "
              f"we can give. Applies to {VER} and later."))
    check("T10.4 the authority alone would NOT have refused the guide (hence T10.2)",
          obs.evaluate_issue(guide, VER, RELEASE) == ("body", None),
          str(obs.evaluate_issue(guide, VER, RELEASE)))
    announce = forum_post(title=f"OBS Studio {VER} released",
                          body=f"OBS Studio {VER} is now available. See the changelog for details.")
    got10b = obs.evaluate_issue(announce, VER, RELEASE)
    check("T10.5 a release announcement IS refused by the authority",
          got10b[1] == "generic_or_no_concrete_issue", str(got10b))

    print("T11 a reply can never lend its version to the thread")
    check("T11.1 the opening body carries the opening author version",
          VER in opening["body"], opening["body"][:120])
    check("T11.2 the opening body does NOT carry the reply author version",
          OTHER not in opening["body"], opening["body"])
    got11 = obs.evaluate_issue(opening, OTHER, obs.parse_date("2026-04-21"))
    check("T11.3 the reply version is refused for this thread",
          got11[1] == "missing_exact_version", str(got11))
    got11b = obs.evaluate_issue(opening, VER, RELEASE)
    check("T11.4 the opening author version is still accepted",
          got11b == ("body", None), str(got11b))
    quoted = forum.parse_opening_post(QUOTE_THREAD_HTML)
    check("T11.5 a QUOTED member version is stripped from the body",
          OTHER not in quoted["body"], quoted["body"])
    check("T11.6 the quoting author own version survives",
          VER in quoted["body"], quoted["body"])
    got11c = obs.evaluate_issue(quoted, OTHER, obs.parse_date("2026-04-21"))
    check("T11.7 the quoted version is refused for the quoting author",
          got11c[1] == "missing_exact_version", str(got11c))

    print("T12 one physical report cannot count twice across methods")
    with tempfile.TemporaryDirectory() as tmp:
        original = obs.EVIDENCE_PATH
        obs.EVIDENCE_PATH = Path(tmp) / "consensus_evidence.yml"
        try:
            post = forum_post(body=f"{VER} crashes on record", thread_id="5000")
            first = forum_row(post)
            # Same physical thread, discovered a second time with a DIFFERENT row id -- the
            # shape a second method produces. URL identity must still suppress it.
            second = dict(first)
            second["id"] = "obs-studio-32-2-2-some-other-method-5000"
            added_rows: list[dict] = []
            added, total, rows = obs.write_evidence([first, second], added_out=added_rows)
            check("T12.1 only one row lands for one physical report", added == 1, f"added={added}")
            check("T12.2 added_out reports exactly what was appended",
                  len(added_rows) == 1 and added_rows[0]["id"] == first["id"], str(added_rows))
            again, _t, _r = obs.write_evidence([first])
            check("T12.3 a later run re-discovering it adds nothing", again == 0, f"added={again}")
            gh_same = obs.evidence_row(gh_issue(body=f"{VER} crashes", number=77), VER, "body",
                                       "2026-10-09T00:00:00Z")
            gh_added, _t2, _r2 = obs.write_evidence([gh_same])
            check("T12.4 a genuinely different GitHub report is NOT suppressed",
                  gh_added == 1, f"added={gh_added}")
        finally:
            obs.EVIDENCE_PATH = original

    print("T13 the second source is a genuinely distinct family")
    from urllib.parse import urlparse
    gh_host = urlparse(gh["source_url"]).netloc
    fm_host = urlparse(row["source_url"]).netloc
    check("T13.1 different hosts", gh_host != fm_host, f"{gh_host} vs {fm_host}")
    check("T13.2 the forum family is not on github.com",
          "github.com" not in fm_host, fm_host)
    check("T13.3 different source_type", gh["source_type"] != row["source_type"],
          gh["source_type"] + " vs " + row["source_type"])
    check("T13.4 different source_name", gh["source_name"] != row["source_name"])
    check("T13.5 the two method ids are distinct",
          obs_adapter.GITHUB_METHOD_ID != obs_adapter.FORUM_METHOD_ID)

    print("T14 both families carry equal weight")
    check("T14.1 GitHub source_weight is 1", gh["source_weight"] == 1, str(gh["source_weight"]))
    check("T14.2 forum source_weight is 1", row["source_weight"] == 1, str(row["source_weight"]))
    check("T14.3 forum rows are counted like any other", row["counted"] is True)
    check("T14.4 forum rows carry no exclusion reason", row["exclusion_reason"] is None)
    check("T14.5 forum rows record the matched version",
          row["matched_version"] == VER and row["patch_version_matched"] is True)

    print("T15 per-method health is truthful")
    states = [
        (("http_403", {}, 0), "blocked", "forum unreachable"),
        ((None, {"threads_requested": 10, "threads_in_pool": 0}, 0), "broken",
         "pages fetched but extractor mapped nothing"),
        ((None, {"threads_requested": 10, "threads_in_pool": 9, "threads_failed": 1}, 2),
         "partial", "some pages lost"),
        ((None, {"threads_requested": 10, "threads_in_pool": 10}, 2), "success", "accepted rows"),
        ((None, {"threads_requested": 10, "threads_in_pool": 10}, 0), "no_results",
         "reachable, nothing countable"),
    ]
    for args, expected, label in states:
        got = obs_adapter.forum_status(*args)
        check(f"T15 {label} -> {expected}", got == expected, f"got {got}")
    # A reachable-but-empty forum must NOT read as blocked, or every quiet week looks like an
    # outage and the real outage stops standing out.
    check("T15.6 an empty pool with no requests is not blocked",
          obs_adapter.forum_status(None, {"threads_requested": 0, "threads_in_pool": 0}, 0)
          == "no_results")
    # The whole point of a second family: one family failing must not be reported as green, and
    # must not be hidden by the other family succeeding.
    # The whole point of a second family: one family failing must not read as green, and must
    # not be hidden by the other family succeeding. Asserted against the production helper.
    outage = obs_adapter.github_health(
        0, {"github_status": "failed", "github_error": "http_502",
            "github_accepted_count": 0, "github_rejected_count": 0})
    check("T15.7 a GitHub outage is reported broken even on a zero exit",
          outage == ("broken", "http_502"), str(outage))
    healthy_gh = obs_adapter.github_health(0, {"github_status": "ok", "github_accepted_count": 3})
    check("T15.8 a working GitHub run still reports success",
          healthy_gh == ("success", ""), str(healthy_gh))
    quiet_gh = obs_adapter.github_health(0, {"github_status": "ok", "github_accepted_count": 0})
    check("T15.9 a quiet GitHub run is no_results, not broken",
          quiet_gh == ("no_results", ""), str(quiet_gh))
    crashed = obs_adapter.github_health(1, {"error": "boom"})
    check("T15.10 a non-zero collector status is broken",
          crashed == ("broken", "boom"), str(crashed))

    print("T16 known_watchlist cannot pass for independent coverage")
    wl = obs_adapter.retired_watchlist_row("obs-studio", VER, "2026-10-09T00:00:00Z")
    check("T16.1 it is emitted as disabled", wl["status"] == "disabled", str(wl["status"]))
    check("T16.2 it is retired, with a reason naming its replacement",
          wl["blocked_reason"] == "retired_superseded_by_obs_forum", str(wl["blocked_reason"]))
    check("T16.3 it claims no candidates and no accepted reports",
          wl["candidates_found"] == 0 and wl["accepted_reports"] == 0, str(wl))
    check("T16.4 it is emitted every run, so its status cannot freeze",
          wl["method_id"] == "known_watchlist" and bool(wl.get("last_run")), str(wl))
    # Coverage is computed from ACCEPTED evidence rows, and a disabled method with zero
    # candidates cannot produce one. Proven by construction, not by reading the source.
    counted_types = {r["source_type"] for r in [gh, row]}
    check("T16.5 accepted OBS evidence carries only the two real source types",
          counted_types == {"github_issue", forum.SOURCE_TYPE}, str(counted_types))
    check("T16.6 curated_watchlist is not among them",
          wl["source_type"] not in counted_types, wl["source_type"])

    print("T18 the pool builder and the health predicate agree on their own counters")
    thread_pages = {
        "https://obsproject.com/forum/threads/obs-crashes-on-record.111/": THREAD_HTML,
        "https://obsproject.com/forum/threads/audio-desync-after-update.222/": QUOTE_THREAD_HTML,
    }

    def fake_fetch(url, timeout=25):
        if "/list/" in url:
            if "page-" in url:
                raise forum.ForumUnavailable("http_404")
            return LISTING_HTML
        if url in thread_pages:
            return thread_pages[url]
        raise forum.ForumUnavailable("http_500")

    pool, stats = forum.build_pool(max_threads_per_forum=5, listing_pages=1, fetch=fake_fetch)
    # Exactly two: all three subforums return the same fixture listing, and a thread path is
    # fetched once across the whole pool rather than once per forum.
    check("T18.1 the pool holds the parsed opening posts, de-duplicated across forums",
          len(pool) == 2, f"{len(pool)} threads, stats={stats}")
    check("T18.2 every pooled post carries its own specific thread URL",
          all(post["source_url"].startswith("https://obsproject.com/forum/threads/")
              for post in pool), str([p.get("source_url") for p in pool]))
    check("T18.3 the stats keys are exactly the ones forum_status reads",
          {"listings_requested", "listings_failed", "threads_requested", "threads_failed",
           "threads_unparsed", "threads_in_pool"} <= set(stats), str(sorted(stats)))
    check("T18.4 threads_in_pool matches the pool it returned",
          stats["threads_in_pool"] == len(pool), str(stats))
    check("T18.5 a healthy pool from these stats reports success",
          obs_adapter.forum_status(None, stats, 1) == "success",
          obs_adapter.forum_status(None, stats, 1) + " " + str(stats))

    # A transport failure must surface as `partial`, never as a quiet success.
    def half_broken(url, timeout=25):
        if "/list/" in url:
            return LISTING_HTML
        if "obs-crashes-on-record" in url:
            return THREAD_HTML
        raise forum.ForumUnavailable("http_503")

    pool2, stats2 = forum.build_pool(max_threads_per_forum=5, listing_pages=1, fetch=half_broken)
    check("T18.6 a lost thread page is counted, not ignored",
          stats2["threads_failed"] > 0, str(stats2))
    check("T18.7 and it reports partial, not success",
          obs_adapter.forum_status(None, stats2, len(pool2)) == "partial",
          obs_adapter.forum_status(None, stats2, len(pool2)))

    def all_listings_dead(url, timeout=25):
        raise forum.ForumUnavailable("http_403")

    forum.reset_pool()
    pool3, stats3, error3 = forum.get_pool(listing_pages=1, fetch=all_listings_dead)
    check("T18.8 a total outage is reported as an error, not an empty forum",
          error3 == "all_listings_failed" and pool3 == [], f"{error3} {pool3}")
    check("T18.9 and it reports blocked",
          obs_adapter.forum_status(error3, stats3, 0) == "blocked")
    forum.reset_pool()
    print("T19 the collector emits a MEASURED per-family delta, never a flattering default")
    from patch_collectors.base import CollectorContext

    captured: dict[str, object] = {}

    def fake_collect_one(version, record_path, since, max_pages, write,
                         extra_accepted=None, extra_rejected=None):
        captured["extra_accepted"] = list(extra_accepted or [])
        captured["extra_rejected"] = list(extra_rejected or [])
        # Three forum reports were accepted but only ONE was new; two were already stored. A
        # health row that reported 3 would be the defaulted-to-accepted-count defect.
        return 0, {
            "version": version,
            "accepted_count": 5,
            "rejected_count": 1,
            "github_status": "ok",
            "github_accepted_count": 2,
            "github_rejected_count": 1,
            "added_rows_by_source_type": {"github_issue": 1, forum.SOURCE_TYPE: 1},
        }

    pooled = [forum_post(body=f"Since {VER} my recording crashes every time.", thread_id=str(n))
              for n in (9001, 9002, 9003)]
    real_collect_one = obs.collect_one
    real_records = obs.active_obs_records
    real_reset = forum.reset_pool
    real_get_pool = forum.get_pool
    try:
        obs.collect_one = fake_collect_one
        obs.active_obs_records = lambda: [(VER, None)]
        forum.reset_pool = lambda: None
        forum.get_pool = lambda *a, **k: (list(pooled), {"threads_requested": 3,
                                                         "threads_in_pool": 3}, None)
        out = obs_adapter.ObsCollector().collect(
            CollectorContext(write=True, since=None, max_pages=1))
    finally:
        obs.collect_one = real_collect_one
        obs.active_obs_records = real_records
        forum.reset_pool = real_reset
        forum.get_pool = real_get_pool

    check("T19.1 the collector produced one result for the version", len(out) == 1, str(len(out)))
    health = {row["method_id"]: row for row in out[0]["method_health"]}
    check("T19.2 both families and the retired slot are reported",
          set(health) == {"github_issues", "obs_forum", "known_watchlist"}, str(sorted(health)))
    check("T19.3 forum accepted three candidates from the pool",
          len(captured["extra_accepted"]) == 3, str(len(captured["extra_accepted"])))
    check("T19.4 the forum health row reports the MEASURED delta (1), not the accepted count (3)",
          health["obs_forum"]["evidence_rows_added"] == 1,
          str(health["obs_forum"]["evidence_rows_added"]))
    check("T19.5 the suppressed rediscoveries are reported as duplicates",
          health["obs_forum"]["duplicate_existing_evidence"] == 2,
          str(health["obs_forum"]["duplicate_existing_evidence"]))
    # accepted(2) and added(1) are deliberately DIFFERENT here. When a fixture makes them
    # equal, an assertion on either one cannot tell which field the code read -- two fields
    # that are always equal are one field, and the delta defect hides in exactly that gap.
    check("T19.6 the GitHub row reports its measured delta (1), not its accepted count (2)",
          health["github_issues"]["evidence_rows_added"] == 1,
          str(health["github_issues"]["evidence_rows_added"]))
    check("T19.9 and its duplicate count is the difference",
          health["github_issues"]["duplicate_existing_evidence"] == 1,
          str(health["github_issues"]["duplicate_existing_evidence"]))
    check("T19.7 the GitHub row reports its own accepted count, not the merged one",
          health["github_issues"]["accepted_reports"] == 2,
          str(health["github_issues"]["accepted_reports"]))
    check("T19.8 the forum rows passed to the writer carry forum identity",
          all(r["source_type"] == forum.SOURCE_TYPE for r in captured["extra_accepted"]),
          str({r["source_type"] for r in captured["extra_accepted"]}))
    print("T20 the opening post cannot fall through to a reply when its markup moves")
    no_time = forum.parse_opening_post(NO_TIME_THREAD_HTML)
    check("T20.1 a thread whose opening post has no date is DROPPED, not dated by its reply",
          no_time is None, str(no_time))
    no_body = forum.parse_opening_post(NO_BODY_THREAD_HTML)
    check("T20.2 a thread whose opening post has no body parses with an EMPTY body",
          no_body is not None and no_body["body"] == "", str(no_body))
    check("T20.3 and it does NOT borrow the reply body",
          OTHER not in (no_body or {}).get("body", ""), str((no_body or {}).get("body")))
    got203 = obs.evaluate_issue(no_body, OTHER, obs.parse_date("2026-04-21"))
    check("T20.4 so the reply version is still refused for that thread",
          got203[1] == "missing_exact_version", str(got203))
    nested = forum.parse_opening_post(NESTED_QUOTE_HTML)
    check("T20.5 a NESTED quote is stripped at every level",
          not any(v in nested["body"] for v in ("32.1.2", "32.0.4", "32.0.3")),
          nested["body"])
    check("T20.6 the quoting author own version survives nesting",
          VER in nested["body"], nested["body"])

    check("T20.9 an UNBALANCED quote drops the rest rather than keeping a stranger version",
          "32.1.2" not in forum._strip_blockquotes(
              "mine broke <blockquote>other said: 32.1.2 is fine for me"),
          forum._strip_blockquotes("mine broke <blockquote>other said: 32.1.2 is fine for me"))
    check("T20.10 text before an unbalanced quote is kept",
          "mine broke" in forum._strip_blockquotes(
              "mine broke <blockquote>other said: 32.1.2 is fine for me"))
    check("T20.11 a post with no quote at all is untouched",
          forum._strip_blockquotes(f"plain text about {VER}") == f"plain text about {VER}")
    # A family that silently degrades to titles only must stop reporting success.
    def bodyless_fetch(url, timeout=25):
        if "/list/" in url:
            return LISTING_HTML
        return NO_BODY_THREAD_HTML

    pool4, stats4 = forum.build_pool(max_threads_per_forum=5, listing_pages=1, fetch=bodyless_fetch)
    check("T20.7 bodyless posts are counted, not ignored",
          stats4["threads_bodyless"] == len(pool4) and len(pool4) > 0, str(stats4))
    check("T20.8 and the method reports partial, not success",
          obs_adapter.forum_status(None, stats4, 0) == "partial",
          obs_adapter.forum_status(None, stats4, 0) + " " + str(stats4))
    print("T21 requests to a volunteer-run community server are paced")
    import os as _os
    import time as _time
    prior = _os.environ.get("AUXSAYS_OBS_FORUM_REQUEST_DELAY_SECONDS")
    try:
        _os.environ["AUXSAYS_OBS_FORUM_REQUEST_DELAY_SECONDS"] = "0.2"
        forum._last_request_at = 0.0
        started = _time.monotonic()
        for _ in range(3):
            forum._pace()
        elapsed = _time.monotonic() - started
        # The FIRST call is free (the clock starts unset), so three calls cost two intervals.
        # Compared with SLACK, not with the exact boundary: time.sleep can return a hair
        # early against monotonic on Windows, and a zero-margin assertion on a sleep is a
        # flaky test. The slack is far below the signal -- removing the pacing entirely
        # gives ~0.000s, not 0.39s -- so the check still fails decisively.
        check("T21.1 consecutive requests are spaced by the configured interval",
              elapsed >= 0.30, f"{elapsed:.3f}s for 3 calls at 0.2s, expected ~0.40s")
        _os.environ["AUXSAYS_OBS_FORUM_REQUEST_DELAY_SECONDS"] = "0"
        forum._last_request_at = 0.0
        started = _time.monotonic()
        for _ in range(3):
            forum._pace()
        check("T21.2 the interval is overridable, so a test is never slowed by it",
              _time.monotonic() - started < 0.2)
    finally:
        if prior is None:
            _os.environ.pop("AUXSAYS_OBS_FORUM_REQUEST_DELAY_SECONDS", None)
        else:
            _os.environ["AUXSAYS_OBS_FORUM_REQUEST_DELAY_SECONDS"] = prior
        forum._last_request_at = 0.0
    # Calling _pace() directly proves the pacer works, not that the fetcher uses it. Without
    # this, deleting the _pace() call from _fetch would leave the suite green.
    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"<html></html>"

    paced: list[int] = []
    real_pace = forum._pace
    real_urlopen = forum.urllib.request.urlopen
    try:
        forum._pace = lambda: paced.append(1)
        forum.urllib.request.urlopen = lambda *a, **k: _FakeResponse()
        forum._fetch("https://obsproject.com/forum/list/windows-support.32/")
    finally:
        forum._pace = real_pace
        forum.urllib.request.urlopen = real_urlopen
    check("T21.4 _fetch paces every request it makes", paced == [1], str(paced))
    check("T21.3 the default floor is a real delay, not zero",
          forum._MIN_REQUEST_INTERVAL > 0, str(forum._MIN_REQUEST_INTERVAL))
    print("T22 prose that names the version as HEALTHY is refused (adversarial probe findings)")
    # Found by probing phrasings, not by a corpus observation: the results-table cue needs a
    # bracket/dash/colon delimiter and target_works needs the word "work", so a plain adjective
    # said in prose reached acceptance. Measured alone over 1,111 live OBS issues these cues
    # change 0 outcomes, and over all 1,320 counted stored rows across every product they newly
    # veto 0 rows -- counterweights, not a widening of what gets deleted.
    healthy = [
        (f"My recording fails. {VER} was fine for me.", "was fine"),
        (f"Capture is broken now. No problems on {VER}.", "no problems on"),
        (f"It crashes. I never saw this happen in {VER}.", "never saw this happen in"),
        (f"Streaming fails. {VER} ran flawlessly for weeks.", "ran flawlessly"),
    ]
    for text, label in healthy:
        gh_got = obs.evaluate_issue(gh_issue(title="issue", body=text), VER, RELEASE)[1]
        fm_got = obs.evaluate_issue(forum_post(body=text), VER, RELEASE)[1]
        check(f"T22 \"{label}\" is not counted as affected (GitHub)", gh_got is not None, "ACCEPTED")
        check(f"T22 \"{label}\" is not counted as affected (forum)", fm_got is not None, "ACCEPTED")
    # The counterweight, both directions. A regression sentence that happens to contain "fine"
    # must still count, or the cue deletes the reports it was meant to protect.
    regression = f"{VER} was fine until I added a browser source, now it freezes."
    got22 = obs.evaluate_issue(forum_post(body=regression), VER, RELEASE)
    check("T22.9 \"was fine UNTIL\" is a regression report and still counts",
          got22 == ("body", None), str(got22))
    before = f"I never saw this before {VER}, now it crashes constantly."
    got22b = obs.evaluate_issue(forum_post(body=before), VER, RELEASE)
    check("T22.10 \"never saw this BEFORE X\" is an affected report and still counts",
          got22b == ("body", None), str(got22b))

    # The cue table is built from f-strings, so a quantifier written `{0,2}` instead of `{{0,2}}`
    # is silently evaluated as the TUPLE (0, 2) and rendered as literal text. That is not a
    # syntax error and not a test failure: the surviving `(?:\w+\s+)` then demands EXACTLY one
    # intervening word, so a case with exactly one word still passes. It shipped that way here
    # until a reformat made the rendered pattern visible. Scanned across the whole table, because
    # every cue in it is written the same way.
    import re as _re
    all_cues = (to_module._WORKING_CUES + to_module._ROLLBACK_CUES + to_module._FIXED_CUES
                + to_module._REFERENCE_CUES + to_module._AFFECTED_CUES)
    artifacts = [basis for pattern, basis in all_cues if _re.search(r"\(\d+, \d+\)", pattern)]
    check("T22.11 the cue table is not vacuous (patterns were actually read)",
          len(all_cues) >= 15, str(len(all_cues)))
    check("T22.12 no cue carries an f-string brace artifact like (0, 2)",
          not artifacts, str(artifacts))
    # And the quantifier itself, at both ends -- a case with exactly one intervening word cannot
    # distinguish `{0,2}` from the broken form.
    for words, label in ((f"This does not occur in {VER}.", "0 intervening words"),
                         (f"I never saw this happen in {VER}.", "1 intervening word"),
                         (f"I never saw this issue happen in {VER}.", "2 intervening words")):
        got = obs.evaluate_issue(forum_post(title="crash", body="It crashes. " + words),
                                 VER, RELEASE)[1]
        check(f"T22 the occurrence cue vetoes with {label}",
              got == "version_reported_working", f"got {got}")
    # A MISSING thing is the problem, not an absence of the problem. "doesn't appear" was in the
    # occurrence verb list and vetoed obsproject.com thread 196135 -- "Downstream- key doesn't
    # appear on 32.2.1" -- whose title says 32.2.1 IS affected. Neither corpus measurement could
    # see it: the GitHub corpus and the stored rows carry no such phrasing. A veto is only as
    # safe as the corpus it was measured against, and this one needed the new family to surface.
    for text, label in ((f"The dock doesn't appear on {VER} after installation.", "dock missing"),
                        (f"The menu does not appear in {VER}.", "menu missing"),
                        (f"My source doesn't appear on {VER}.", "source missing")):
        outcome = classify_target_outcome(text, VER)
        check(f"T22 a {label} report is NOT read as the version working",
              outcome.outcome != "working", f"{outcome.outcome} via {outcome.basis}")
    # ...while the unambiguous phrasings still veto, so removing `appear` did not reopen them.
    for text, label in ((f"This issue does not occur in version {VER}.", "does not occur"),
                        (f"This does not happen on {VER}.", "does not happen"),
                        (f"I never saw this happen in {VER}.", "never saw this happen")):
        outcome = classify_target_outcome(text, VER)
        check(f"T22 \"{label}\" still reads as the version working",
              outcome.outcome == "working", f"{outcome.outcome} via {outcome.basis}")
    print("T23 a thread identity is resolved, never invented")
    check("T23.1 the slugged URL shape resolves",
          forum.thread_id("/forum/threads/a-slug.196568/") == "196568")
    check("T23.2 the SLUGLESS URL shape resolves to the same id",
          forum.thread_id("/forum/threads/196568/") == "196568",
          str(forum.thread_id("/forum/threads/196568/")))
    for path in ("/forum/posts/999/", "", "/forum/threads/no-id/", "/forum/list/windows.32/"):
        check(f"T23 no id is invented for {path!r}", forum.thread_id(path) is None,
              str(forum.thread_id(path)))
    slugged = forum_post(body=f"{VER} crashes on record", thread_id="196568")
    slugless = dict(slugged, thread_path="/forum/threads/196568/",
                    source_url="https://obsproject.com/forum/threads/196568/")
    check("T23.3 both URL shapes produce ONE row identity",
          forum_row(slugged)["id"] == forum_row(slugless)["id"],
          forum_row(slugged)["id"] + " vs " + forum_row(slugless)["id"])
    check("T23.4 an unresolvable path yields no identity at all",
          forum.row_identity(VER, {"thread_path": "/forum/threads/no-id/"}, obs.slug) is None)
    unresolvable = dict(slugged, thread_path="/forum/threads/no-id/")
    acc23, rej23 = obs_adapter.evaluate_forum_candidates(
        VER, RELEASE, [unresolvable], "2026-10-09T00:00:00Z")
    check("T23.5 and the candidate is REFUSED rather than stored under an invented identity",
          acc23 == [] and rej23 and rej23[0]["reason"] == "unresolvable_thread_identity",
          str((acc23, rej23)))
    print("T17 implementing this did not rewrite stored OBS evidence")
    live_now = obs.EVIDENCE_PATH.read_bytes() if obs.EVIDENCE_PATH.exists() else b""
    check("T17.1 the live evidence store is byte-identical after the suite",
          hashlib.sha256(live_now).hexdigest() == hashlib.sha256(live_evidence_before).hexdigest(),
          f"{len(live_evidence_before)} -> {len(live_now)} bytes")
    check("T17.2 EVIDENCE_PATH was restored to the real store",
          obs.EVIDENCE_PATH.name == "consensus_evidence.yml", str(obs.EVIDENCE_PATH))
    # A stored row may stop counting only by audited withdrawal, never by an implementation
    # change quietly re-deriving it. Nothing here writes to the real path, and this is the
    # assertion that fails if that ever stops being true.

    print()
    print("=" * 60)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    print("=" * 60)
    if _ERRORS:
        for label in _ERRORS:
            print(f"  failed: {label}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
