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


def _opening_post(wrapper_inner: str, after_wrapper: str = "", title: str = "OBS window capture is black") -> str:
    """A thread page whose opening post's bbWrapper holds `wrapper_inner`, plus a reply with text.

    The reply is there so a parser that searched past the opening post would find words to
    borrow; every empty-body case below must stay empty instead.
    """
    return f"""
<!doctype html><html><body>
<h1 class="p-title-value">{title}</h1>
<article data-author="firstauthor" data-content="post-7001">
  <time class="u-dt" datetime="2026-11-10T21:17:11+0000">Nov 10, 2026</time>
  <div class="bbWrapper">{wrapper_inner}</div>
  {after_wrapper}
</article>
<article data-author="secondauthor" data-content="post-7002">
  <time class="u-dt" datetime="2026-11-11T09:00:00+0000">Nov 11, 2026</time>
  <div class="bbWrapper">I am on 32.1.2 and see the same black capture.</div>
</article>
</body></html>
"""


# The shape of obsproject.com thread 196879, the post that tripped threads_bodyless in production:
# a wrapper holding nothing but an embedded video player. Structure only -- no real post text.
EMBED_ONLY_THREAD_HTML = _opening_post(
    '<div class="bbMediaWrapper"><div class="bbMediaWrapper-inner">'
    '<iframe src="https://www.youtube.com/embed/abc" loading="lazy" allowfullscreen></iframe>'
    '</div></div>')
IMAGE_ONLY_THREAD_HTML = _opening_post(
    '<img src="https://obsproject.com/forum/attachments/x.png" class="bbImage" alt="" />')
ATTACHMENT_ONLY_THREAD_HTML = _opening_post(
    "", '<section class="message-attachments"><ul class="attachmentList">'
        '<li class="file"><a href="/forum/attachments/log-txt.123/">log.txt</a></li></ul></section>')
QUOTE_ONLY_THREAD_HTML = _opening_post(
    '<blockquote class="bbCodeBlock bbCodeBlock--quote"><div class="bbCodeBlock-content">'
    "othermember said: since 32.1.2 my capture is black.</div></blockquote>")
# A wrapper with nothing in it at all: no text, no quote, no media, no attachment. That is also
# what hidden or moderated content looks like, so it must NOT be presumed legitimately empty.
EMPTY_WRAPPER_THREAD_HTML = _opening_post("  ")
TEXT_THREAD_HTML = _opening_post(f"Since {VER} my recording crashes every time.")


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
    print("T24 the write-mode ownership gate authorizes the new family")
    # A DRY RUN CANNOT REACH THIS GATE. The bounded calibration was clean and the first
    # write-enabled production run failed at `ownership_violation:evidence_unauthorized_source`,
    # because the per-product allow-lists are positive and only consulted on an actual append.
    # Asserted against the real gate, and in BOTH directions -- an allow-list test that only
    # checks its own entry is present proves nothing about the gate consulting it.
    from lib import collector_ownership as ownership
    check("T24.1 obs_forum is an authorized METHOD for obs-studio",
          "obs_forum" in ownership.ALLOWED_METHODS["obs-studio"],
          str(sorted(ownership.ALLOWED_METHODS["obs-studio"])))
    check("T24.2 obs_forum_thread is an authorized SOURCE TYPE for obs-studio",
          "obs_forum_thread" in ownership.ALLOWED_SOURCE_TYPES["obs-studio"],
          str(sorted(ownership.ALLOWED_SOURCE_TYPES["obs-studio"])))
    check("T24.3 the retired watchlist keeps its registration, so its health can still be emitted",
          "known_watchlist" in ownership.ALLOWED_METHODS["obs-studio"])

    import yaml as _yaml
    live_rows = _yaml.safe_load(live_evidence_before.decode("utf-8"))["evidence"]

    def _dump(rows):
        return _yaml.safe_dump({"schema_version": 1, "evidence": rows}, sort_keys=False,
                               allow_unicode=True, width=1000)

    gate_post = forum_post(body=f"{VER} crashes on record", thread_id="196568")
    gate_row = obs.normalize_row(forum_row(gate_post))
    try:
        ownership.validate_evidence("obs-studio", live_evidence_before.decode("utf-8"),
                                    _dump(live_rows + [gate_row]))
        accepted_by_gate, gate_reason = True, ""
    except Exception as exc:
        accepted_by_gate = False
        gate_reason = str(getattr(exc, "reason", "") or exc)
    check("T24.4 the gate ACCEPTS a forum evidence append", accepted_by_gate, gate_reason)

    stranger = dict(gate_row, source_type="reddit_community_report",
                    id="obs-studio-32-2-2-stranger-1",
                    source_url="https://example.invalid/r/obs/1/")
    try:
        ownership.validate_evidence("obs-studio", live_evidence_before.decode("utf-8"),
                                    _dump(live_rows + [stranger]))
        refused_stranger = False
    except Exception:
        refused_stranger = True
    check("T24.5 and still REFUSES a source type nobody registered", refused_stranger,
          "the gate admitted an unregistered source")

    print("T25 the revalidation harness classifies the new source honestly")
    import revalidate_consensus_evidence as reval
    rv = {"product_id": "obs-studio", "update_version": VER, "counted": True,
          "patch_version_matched": True, "source_type": forum.SOURCE_TYPE,
          "source_url": "https://obsproject.com/forum/threads/some-thread.196568/"}
    # `pending_source_adapter` says the source is recognised but has no adapter yet.
    # `unsupported_source_type` would say OBS evidence carries a source nobody knows -- a
    # misreport rather than a gap, and the default for any type left off the list.
    check("T25.1 a forum row is pending_source_adapter, not unsupported_source_type",
          reval.classify_row(rv)[0] == "pending_source_adapter", str(reval.classify_row(rv)))
    check("T25.2 a GitHub row still has its real adapter contract",
          reval.classify_row(dict(rv, source_type="github_issue"))[0] == "candidate_for_revalidation",
          str(reval.classify_row(dict(rv, source_type="github_issue"))))
    check("T25.3 a genuinely unknown source type is still unsupported",
          reval.classify_row(dict(rv, source_type="zz_not_a_source"))[0] == "unsupported_source_type")
    print("T26 a version named as the author's WORKAROUND is not evidence against it")
    # Found by the bounded production audit, not by a test. obsproject.com thread 190590 is about
    # 32.0.0 removing a flag and closes with "my current solution is to just use version 31.1.2".
    # The first production run of the forum family counted that as evidence AGAINST 31.1.2. The
    # motion-verb rollback cue misses it because nobody moved anywhere -- the sentence says what
    # the author runs now.
    real = ("After updating to 32.0.0, I found that --disable-shutdown-check has been removed. "
            "This breaks my automation. As of now my current solution is to just use version "
            "31.1.2 and turn off automatic update checks.")
    got_wa = classify_target_outcome(real, "31.1.2")
    check("T26.1 the workaround version is a rollback target, not an affected version",
          got_wa.outcome == "rollback_target", f"{got_wa.outcome} via {got_wa.basis}")
    check("T26.2 and its basis names the workaround cue",
          got_wa.basis == "target_is_the_workaround", got_wa.basis)
    check("T26.3 the version that actually regressed is still affected/acceptable",
          classify_target_outcome(real, "32.0.0").outcome != "rollback_target",
          classify_target_outcome(real, "32.0.0").outcome)
    for text, label in ((f"The workaround is to stay on {VER}.", "workaround is to stay on"),
                        (f"My solution was to keep using {VER}.", "solution was to keep using"),
                        (f"Workaround: install {VER} instead.", "workaround: install")):
        o = classify_target_outcome(text, VER)
        check(f"T26 \"{label}\" vetoes the named version",
              o.outcome == "rollback_target", f"{o.outcome} via {o.basis}")
    # The counterweight. A sentence saying the workaround FAILS on a version must not veto that
    # version. Measured note: this holds via R3, because "does not work" is itself an AFFECTED
    # cue -- so this pins the OUTCOME, not the verb list. Adding `work` to that list changes 0
    # outcomes across both corpora, i.e. it is an equivalent variant rather than a defect.
    fails = f"I tried the workaround but it does not work on {VER}, OBS still crashes."
    o_fails = classify_target_outcome(fails, VER)
    check("T26.7 \"the workaround does not work on X\" does NOT veto X",
          o_fails.outcome != "rollback_target", f"{o_fails.outcome} via {o_fails.basis}")

    # T26b: the inverse phrasing. The cue above was corpus-safe -- 0 changed outcomes over 1,111
    # issues and every counted stored row -- and still semantically wrong: "The solution is NOT
    # to use version 31.1.2" vetoed 31.1.2 as the healthy fallback while the author was saying to
    # avoid it. Corpus safety is not semantic completeness; nothing in either corpus happened to
    # phrase it that way. Driven through the real classifier, not by re-deriving the regex.
    avoidance = [
        (f"The solution is not to use version {OTHER}.", "not to use"),
        (f"My workaround is to avoid using {OTHER}.", "avoid using"),
        (f"The workaround is to run without {OTHER}.", "run without"),
        (f"Use any version except {OTHER} as the workaround.", "except TARGET"),
        (f"The solution is to stay away from {OTHER}.", "stay away from"),
        (f"The workaround was to stop using {OTHER}.", "stop using"),
    ]
    for text, label in avoidance:
        o = classify_target_outcome(text, OTHER)
        check(f"T26b \"{label}\" does NOT make the target a rollback/workaround version",
              o.outcome != "rollback_target", f"{o.outcome} via {o.basis}")
    # Affirmative selection must still veto, or the repair has simply disabled the cue.
    selection = [
        (f"My current solution is to just use version {OTHER}.", "solution is to just use"),
        (f"Workaround: install {OTHER} instead.", "workaround: install"),
        (f"The solution was to keep using {OTHER}.", "keep using"),
        (f"I am staying on {OTHER} as a workaround.", "staying on"),
        # `no` must NOT read as avoidance: this sentence affirmatively selects the target, and the
        # generic polarity lookback would have refused it on the bare "no".
        (f"There is no other workaround; use {OTHER}.", "no other workaround; use"),
        # `except` guards the verb->target gap only. In the marker->verb gap it blocked this
        # sentence, which affirmatively selects the target as the only remaining option.
        (f"There is no workaround except to use {OTHER}.", "no workaround except to use"),
    ]
    for text, label in selection:
        o = classify_target_outcome(text, OTHER)
        check(f"T26b \"{label}\" still vetoes the named version",
              o.outcome == "rollback_target", f"{o.outcome} via {o.basis}")
    # The real thread, unchanged by the tightening.
    o190 = classify_target_outcome(real, "31.1.2")
    check("T26b.12 thread 190590 still vetoes 31.1.2 after the tightening",
          o190.outcome == "rollback_target" and o190.basis == "target_is_the_workaround",
          f"{o190.outcome} via {o190.basis}")
    check("T26b.13 and 32.0.0 from that thread is still not vetoed",
          classify_target_outcome(real, "32.0.0").outcome != "rollback_target")
    print("T27 the audited-withdrawal tool derives its verdict and keeps the row")
    import withdraw_obs_role_misattributed_rows as wd
    kept = {"id": "obs-studio-31-1-2-obs-forum-thread-190590", "product_id": "obs-studio",
            "update_version": "31.1.2", "counted": True, "exclusion_reason": None,
            "source_url": "https://obsproject.com/forum/threads/x.190590/",
            "report_text_excerpt": "my current solution is to just use version 31.1.2"}
    clean = {"id": "obs-studio-32-2-2-obs-forum-thread-1", "product_id": "obs-studio",
             "update_version": VER, "counted": True, "exclusion_reason": None,
             "source_url": "https://obsproject.com/forum/threads/y.1/",
             "report_text_excerpt": f"Since {VER} my recording crashes every time."}
    other = dict(clean, product_id="microsoft-windows-11", id="win-1")
    refused = wd.refused_rows([kept, clean, other])
    check("T27.1 the workaround row is reported as refused",
          [r["id"] for r, _ in refused] == [kept["id"]], str([r["id"] for r, _ in refused]))
    check("T27.2 with the reason the authority gives, not a hard-coded string",
          refused[0][1] == "version_is_rollback_target", refused[0][1])
    check("T27.3 a legitimate forum row is NOT refused",
          clean["id"] not in [r["id"] for r, _ in refused])
    check("T27.4 another product is out of scope entirely",
          "win-1" not in [r["id"] for r, _ in refused])
    already = dict(kept, counted=False, exclusion_reason="version_is_rollback_target")
    check("T27.5 an already-withdrawn row is skipped, so the tool is idempotent",
          wd.refused_rows([already]) == [], str(wd.refused_rows([already])))
    _run_health_recovery_checks()
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


def _listing_of(count: int, start: int = 300000) -> str:
    links = "".join(f'<a href="/forum/threads/thread-{n}.{n}/">t{n}</a>'
                    for n in range(start, start + count))
    return f'<html><body><div class="structItemContainer-group">{links}</div></body></html>'


class _CountdownBudget:
    """A run budget that reports expiry after `allow` checks. Deterministic, no clock."""

    def __init__(self, allow: int) -> None:
        self.allow = allow
        self.calls = 0

    def collector_finalize_expired(self) -> bool:
        self.calls += 1
        return self.calls > self.allow


def _capture_emits():
    """Swap the runtime emitter for a recorder; returns (events, restore)."""
    from patch_collectors import runtime_budget as rb
    events: list[tuple[str, dict]] = []
    real = rb.emit

    def fake(event, **fields):
        events.append((event, dict(fields)))

    rb.emit = fake

    def restore():
        rb.emit = real

    return events, restore


# The 18 OBS versions tracked when this was written, in no particular order on purpose.
_OBS_VERSIONS = ["32.1.1", "31.0.3", "33.0.0", "32.2.2", "31.1.0", "32.0.0", "31.0.4", "32.1.2",
                 "32.2.0", "31.1.1", "32.0.1", "33.0.1", "31.1.2", "32.0.2", "32.0.3", "32.0.4",
                 "32.1.0", "32.2.1"]


def _run_health_recovery_checks() -> None:
    """T28-T34: truthful empty-body health, newest-first walk, and budget-stop telemetry."""
    from patch_collectors import runtime_budget as rb
    from patch_collectors.base import CollectorContext

    print("T28 a legitimately textless opening post is classified, kept and judged unchanged")
    cases = (
        ("embed-only (the thread 196879 shape)", EMBED_ONLY_THREAD_HTML, forum.BODY_NON_TEXT_ONLY),
        ("image-only", IMAGE_ONLY_THREAD_HTML, forum.BODY_NON_TEXT_ONLY),
        ("attachment-only", ATTACHMENT_ONLY_THREAD_HTML, forum.BODY_NON_TEXT_ONLY),
        ("quote-only", QUOTE_ONLY_THREAD_HTML, forum.BODY_QUOTE_ONLY),
    )
    for label, html, expected in cases:
        post = forum.parse_opening_post(html)
        check(f"T28 the {label} post parses with an EMPTY body (the reply is never borrowed)",
              post is not None and post["body"] == "", str(post and post["body"]))
        check(f"T28 the {label} post is classified {expected}",
              post is not None and post["body_state"] == expected, str(post and post["body_state"]))
        check(f"T28 {expected} is a non-degrading (textless) state",
              expected in forum.TEXTLESS_BODY_STATES and expected not in forum.DEGRADING_BODY_STATES)
    text_post = forum.parse_opening_post(TEXT_THREAD_HTML)
    check("T28.1 a post with text is classified text",
          text_post["body_state"] == forum.BODY_TEXT, text_post["body_state"])

    # One textless post in a realistic pool: the production shape. It must not degrade the pool.
    many = 60
    pages = {f"https://obsproject.com/forum/threads/thread-{n}.{n}/": TEXT_THREAD_HTML
             for n in range(300000, 300000 + many)}
    pages["https://obsproject.com/forum/threads/thread-300007.300007/"] = EMBED_ONLY_THREAD_HTML

    def realistic_fetch(url, timeout=25):
        if "/list/" in url:
            return _listing_of(many)
        return pages[url]

    events, restore = _capture_emits()
    try:
        pool28, stats28 = forum.build_pool(max_threads_per_forum=many, listing_pages=1,
                                           fetch=realistic_fetch)
    finally:
        restore()
    check("T28.2 the textless post stays in the pool, judged on its title as before",
          stats28["threads_in_pool"] == many and len(pool28) == many, str(stats28))
    check("T28.3 it is counted as textless, not bodyless",
          stats28["threads_textless"] == 1 and stats28["threads_bodyless"] == 0, str(stats28))
    check("T28.4 one textless post does NOT make the pool partial",
          obs_adapter.forum_status(None, stats28, 1) == "success"
          and obs_adapter.forum_status(None, stats28, 0) == "no_results",
          obs_adapter.forum_status(None, stats28, 1) + " " + str(stats28))
    named = [f for e, f in events if e == "obs_forum_empty_body"]
    check("T28.5 the diagnostic names the empty-body thread by id and class",
          named == [{"thread": "/forum/threads/thread-300007.300007/", "thread_id": "300007",
                     "state": forum.BODY_NON_TEXT_ONLY, "degrading": False}], str(named))
    check("T28.6 and it carries no post text (only path, id, class, flag)",
          all(set(f) == {"thread", "thread_id", "state", "degrading"} for f in named), str(named))

    print("T29 a missing wrapper, an empty wrapper and an extraction failure stay degrading")
    no_wrapper = forum.parse_opening_post(NO_BODY_THREAD_HTML)
    check("T29.1 a missing wrapper is classified no_wrapper",
          no_wrapper["body_state"] == forum.BODY_NO_WRAPPER, no_wrapper["body_state"])
    empty_wrapper = forum.parse_opening_post(EMPTY_WRAPPER_THREAD_HTML)
    check("T29.2 a wrapper with nothing explainable in it is classified empty_wrapper",
          empty_wrapper["body_state"] == forum.BODY_EMPTY_WRAPPER, empty_wrapper["body_state"])
    check("T29.3 both are degrading states",
          {forum.BODY_NO_WRAPPER, forum.BODY_EMPTY_WRAPPER} <= forum.DEGRADING_BODY_STATES)

    # A GENUINE extraction failure: the wrapper holds the author's own text, outside any quote,
    # and our extractor returns nothing. Produced the way it would really happen -- a regression
    # in our own quote stripping or balanced-div slicing -- and caught by the independent scan.
    real_strip = forum._strip_blockquotes
    real_slice = forum._slice_balanced_div
    try:
        forum._strip_blockquotes = lambda html: ""
        stripped_away = forum.parse_opening_post(TEXT_THREAD_HTML)
    finally:
        forum._strip_blockquotes = real_strip
    check("T29.4 a quote-strip regression that empties a real post is an extraction failure",
          stripped_away["body"] == "" and stripped_away["body_state"] == forum.BODY_EXTRACTION_FAILED,
          str(stripped_away["body_state"]))
    try:
        forum._slice_balanced_div = lambda html, start: ""
        sliced_away = forum.parse_opening_post(QUOTE_THREAD_HTML)
    finally:
        forum._slice_balanced_div = real_slice
    check("T29.5 a slicing regression that loses text beside a quote is an extraction failure, "
          "not quote-only",
          sliced_away["body"] == "" and sliced_away["body_state"] == forum.BODY_EXTRACTION_FAILED,
          str(sliced_away["body_state"]))
    check("T29.6 extraction_failed is a degrading state",
          forum.BODY_EXTRACTION_FAILED in forum.DEGRADING_BODY_STATES)
    check("T29.7 a wrapper the independent scan cannot find is an extraction failure",
          forum.classify_body("<p>no wrapper markup here</p>", True, "") == forum.BODY_EXTRACTION_FAILED)

    def degrading_fetch_for(html):
        def fetch(url, timeout=25):
            if "/list/" in url:
                return LISTING_HTML
            if "obs-crashes-on-record" in url:
                return THREAD_HTML
            return html
        return fetch

    for label, html in (("missing wrapper", NO_BODY_THREAD_HTML),
                        ("empty wrapper", EMPTY_WRAPPER_THREAD_HTML)):
        pool29, stats29 = forum.build_pool(max_threads_per_forum=5, listing_pages=1,
                                           fetch=degrading_fetch_for(html))
        check(f"T29 one {label} post is counted bodyless, not textless",
              stats29["threads_bodyless"] == 1 and stats29["threads_textless"] == 0, str(stats29))
        check(f"T29 one {label} post still makes the pool partial",
              obs_adapter.forum_status(None, stats29, 1) == "partial",
              obs_adapter.forum_status(None, stats29, 1))
    try:
        forum._strip_blockquotes = lambda html: ""
        pool29f, stats29f = forum.build_pool(max_threads_per_forum=5, listing_pages=1,
                                             fetch=degrading_fetch_for(QUOTE_THREAD_HTML))
    finally:
        forum._strip_blockquotes = real_strip
    check("T29.8 an extraction failure across the pool is bodyless and partial",
          stats29f["threads_bodyless"] == 2 and stats29f["threads_textless"] == 0
          and obs_adapter.forum_status(None, stats29f, 0) == "partial", str(stats29f))
    # A post the parser handed over without a state (a future refactor) must fail closed.
    real_parse = forum.parse_opening_post
    try:
        forum.parse_opening_post = lambda html: {k: v for k, v in (real_parse(html) or {}).items()
                                                 if k != "body_state"} or None
        pool29s, stats29s = forum.build_pool(max_threads_per_forum=5, listing_pages=1,
                                             fetch=degrading_fetch_for(EMBED_ONLY_THREAD_HTML))
    finally:
        forum.parse_opening_post = real_parse
    check("T29.9 an empty body with no recorded state fails closed into the degrading counter",
          stats29s["threads_bodyless"] == 1 and stats29s["threads_textless"] == 0, str(stats29s))

    print("T30 legitimately textless posts still degrade the pool when they are a material share")
    def all_textless(url, timeout=25):
        if "/list/" in url:
            return LISTING_HTML
        return IMAGE_ONLY_THREAD_HTML

    pool30, stats30 = forum.build_pool(max_threads_per_forum=5, listing_pages=1, fetch=all_textless)
    check("T30.1 a pool where every post is image-only counts them all as textless",
          stats30["threads_textless"] == len(pool30) == 2 and stats30["threads_bodyless"] == 0,
          str(stats30))
    check("T30.2 and a pool-wide collapse reports partial, not success",
          obs_adapter.forum_status(None, stats30, 1) == "partial",
          obs_adapter.forum_status(None, stats30, 1) + " " + str(stats30))
    big = 60
    big_pages = {f"https://obsproject.com/forum/threads/thread-{n}.{n}/": EMBED_ONLY_THREAD_HTML
                 for n in range(300000, 300000 + big)}

    def big_collapse(url, timeout=25):
        if "/list/" in url:
            return _listing_of(big)
        return big_pages[url]

    _ev, _restore = _capture_emits()
    try:
        pool30b, stats30b = forum.build_pool(max_threads_per_forum=big, listing_pages=1,
                                             fetch=big_collapse)
    finally:
        _restore()
    check("T30.3 a 60-thread pool of embed-only posts reports partial",
          obs_adapter.forum_status(None, stats30b, 3) == "partial", str(stats30b))
    named30 = [f for e, f in _ev if e == "obs_forum_empty_body"]
    suppressed30 = [f for e, f in _ev if e == "obs_forum_empty_body_suppressed"]
    check("T30.4 the per-thread diagnostic is bounded during a collapse",
          len(named30) == forum._MAX_EMPTY_BODY_EVENTS and suppressed30
          and suppressed30[0]["count"] == big - forum._MAX_EMPTY_BODY_EVENTS,
          f"{len(named30)} named, suppressed={suppressed30}")
    # The bound itself, at the edges. Driven through forum_status, which is what health reads.
    def status_for(in_pool, textless):
        return obs_adapter.forum_status(None, {"threads_requested": in_pool, "threads_in_pool": in_pool,
                                               "threads_textless": textless}, 1)
    collapse_at = -(-180 // forum._EMPTY_BODY_COLLAPSE_DENOMINATOR)
    check("T30.5 in a 180-thread pool, one fewer than a material share is still healthy",
          status_for(180, collapse_at - 1) == "success", status_for(180, collapse_at - 1))
    check("T30.6 and a material share is partial",
          status_for(180, collapse_at) == "partial", status_for(180, collapse_at))
    check("T30.7 the floor: a small pool is not degraded by one or two textless posts",
          status_for(20, 1) == "success" and status_for(20, 2) == "success",
          f"{status_for(20, 1)} {status_for(20, 2)}")
    check("T30.8 but a small pool that is mostly textless is",
          status_for(20, forum._EMPTY_BODY_COLLAPSE_FLOOR) == "partial"
          and status_for(2, 2) == "partial", f"{status_for(20, 3)} {status_for(2, 2)}")
    check("T30.9 no empty bodies at all is never a collapse",
          not forum.empty_body_collapse({"threads_in_pool": 0}) and status_for(180, 0) == "success")

    print("T31 accepted evidence is unchanged: the authority sees identical inputs")
    fixtures = (THREAD_HTML, QUOTE_THREAD_HTML, NESTED_QUOTE_HTML, TEXT_THREAD_HTML,
                EMBED_ONLY_THREAD_HTML, QUOTE_ONLY_THREAD_HTML, NO_BODY_THREAD_HTML)
    inputs_same = True
    rows_same = True
    leaked = False
    for index, html in enumerate(fixtures):
        post = forum.parse_opening_post(html)
        path = f"/forum/threads/fixture.{8800 + index}/"
        post.update(thread_path=path, source_url=forum.thread_url(path))
        bare = {k: v for k, v in post.items() if k != "body_state"}
        for version in (VER, OTHER):
            if (obs.evaluate_issue(post, version, RELEASE) != obs.evaluate_issue(bare, version, RELEASE)
                    or obs.match_basis(post, version) != obs.match_basis(bare, version)):
                inputs_same = False
            got_rows = obs_adapter.evaluate_forum_candidates(version, RELEASE, [post], "2026-11-14T00:00:00Z")
            bare_rows = obs_adapter.evaluate_forum_candidates(version, RELEASE, [bare], "2026-11-14T00:00:00Z")
            if got_rows != bare_rows:
                rows_same = False
            for row in got_rows[0]:
                if "body_state" in row or any(str(v) in forum.DEGRADING_BODY_STATES | forum.TEXTLESS_BODY_STATES
                                              for v in row.values()):
                    leaked = True
    check("T31.1 evaluate_issue and match_basis give the same answer with or without body_state",
          inputs_same)
    check("T31.2 accepted rows and rejections are identical with or without body_state", rows_same)
    check("T31.3 no evidence row carries the diagnostic", not leaked)
    check("T31.4 a text post's body is byte-identical to the pinned pre-change extraction",
          forum.parse_opening_post(THREAD_HTML)["body"]
          == "I updated to 32.2.2. OBS now crashes every time I start a recording. Log attached.",
          forum.parse_opening_post(THREAD_HTML)["body"])
    accepted31 = obs_adapter.evaluate_forum_candidates(VER, RELEASE, obs_adapter.forum_candidates(VER, pool28),
                                                        "2026-11-14T00:00:00Z")[0]
    accepted31_bare = obs_adapter.evaluate_forum_candidates(
        VER, RELEASE, obs_adapter.forum_candidates(VER, [{k: v for k, v in p.items() if k != "body_state"}
                                                         for p in pool28]), "2026-11-14T00:00:00Z")[0]
    check("T31.5 over a whole pool, candidates and accepted rows match with the diagnostic removed",
          accepted31 == accepted31_bare and len(accepted31) == many - 1,
          f"{len(accepted31)} vs {len(accepted31_bare)}")

    print("T32 the newest OBS release is walked first, and no version is starved")
    check("T32.1 release order is numeric, not string order",
          obs_adapter.version_order_key("33.10.0") > obs_adapter.version_order_key("33.9.0")
          and sorted(["33.9.0", "33.10.0"])[0] == "33.10.0")
    check("T32.2 a pre-release sorts before its release",
          obs_adapter.version_order_key("32.0.0-beta1") < obs_adapter.version_order_key("32.0.0"))
    same = {v: "2026-11-14T15:00:00Z" for v in _OBS_VERSIONS}
    order = obs_adapter.walk_order(_OBS_VERSIONS, same)
    check("T32.3 the newest releases come first",
          order[:3] == ["33.0.1", "33.0.0", "32.2.2"], str(order[:4]))
    check("T32.4 every version is walked exactly once",
          sorted(order) == sorted(_OBS_VERSIONS) and len(order) == len(_OBS_VERSIONS), str(order))
    check("T32.5 the order is deterministic and independent of input order",
          obs_adapter.walk_order(list(reversed(_OBS_VERSIONS)), same) == order
          and obs_adapter.walk_order(sorted(_OBS_VERSIONS), dict(same)) == order)
    stale = dict(same, **{"31.1.0": "2026-11-01T00:00:00Z", "32.1.2": "2026-11-05T00:00:00Z"})
    stale.pop("32.0.3")
    order_stale = obs_adapter.walk_order(_OBS_VERSIONS, stale)
    check("T32.6 after the newest, the least recently refreshed come next (never-refreshed first)",
          order_stale[3:6] == ["32.0.3", "31.1.0", "32.1.2"], str(order_stale[:7]))
    check("T32.7 a newest release that was refreshed most recently still goes first",
          obs_adapter.walk_order(_OBS_VERSIONS, dict(same, **{"33.0.1": "2026-11-14T23:59:59Z"}))[0] == "33.0.1")
    # Starvation, simulated: each run reaches only a few versions more than the reserved newest.
    # Every version must be refreshed, and within a bounded number of runs.
    refreshed = {v: "2026-11-01T00:00:00Z" for v in _OBS_VERSIONS}
    first_seen: dict[str, int] = {}
    reach = obs_adapter.NEWEST_FIRST + 1
    for run_no in range(1, 40):
        stamp = f"2026-11-{1 + run_no // 24:02d}T{run_no % 24:02d}:00:00Z"
        for version in obs_adapter.walk_order(_OBS_VERSIONS, refreshed)[:reach]:
            refreshed[version] = stamp
            first_seen.setdefault(version, run_no)
    rest = len(_OBS_VERSIONS) - obs_adapter.NEWEST_FIRST
    check("T32.8 with runs that reach only one version past the newest, every version is refreshed",
          set(first_seen) == set(_OBS_VERSIONS), str(sorted(set(_OBS_VERSIONS) - set(first_seen))))
    check("T32.9 and none waits longer than one full rotation of the rest",
          max(first_seen.values()) <= rest, str(max(first_seen.values())))
    check("T32.10 an unreadable health table falls back to newest-first, still deterministic",
          obs_adapter.walk_order(_OBS_VERSIONS, {})[:3] == ["33.0.1", "33.0.0", "32.2.2"])

    print("T33 a budget stop records what was processed and skipped; skipped versions get no row")
    pooled33 = [forum_post(body=f"Since {VER} my recording crashes every time.", thread_id="9101")]
    pool_stats33 = {"threads_requested": 180, "threads_in_pool": 178, "threads_failed": 1,
                    "threads_unparsed": 1, "threads_skipped": 0, "threads_textless": 1}
    calls33: list[str] = []

    def fake_collect_one33(version, record_path, since, max_pages, write,
                           extra_accepted=None, extra_rejected=None):
        calls33.append(version)
        return 0, {"version": version, "accepted_count": 1, "rejected_count": 0,
                   "github_status": "ok", "github_accepted_count": 0, "github_rejected_count": 0,
                   "added_rows_by_source_type": {}}

    real = (obs.collect_one, obs.active_obs_records, forum.reset_pool, forum.get_pool,
            obs_adapter.last_refreshed_by_version, rb.get_run_budget())
    events33, restore33 = _capture_emits()
    try:
        obs.collect_one = fake_collect_one33
        obs.active_obs_records = lambda: [(v, None) for v in _OBS_VERSIONS]
        forum.reset_pool = lambda: None
        forum.get_pool = lambda *a, **k: (list(pooled33), dict(pool_stats33), None)
        obs_adapter.last_refreshed_by_version = lambda: dict(same)
        rb.set_run_budget(_CountdownBudget(allow=4))
        out33 = obs_adapter.ObsCollector().collect(CollectorContext(write=True, since=None, max_pages=1))
    finally:
        restore33()
        (obs.collect_one, obs.active_obs_records, forum.reset_pool, forum.get_pool,
         obs_adapter.last_refreshed_by_version) = real[:5]
        rb.set_run_budget(real[5])
    expected_done = order[:4]
    expected_skipped = order[4:]
    check("T33.1 the run processed the newest releases first, then stopped",
          [r["version"] for r in out33] == expected_done and calls33 == expected_done,
          str([r["version"] for r in out33]))
    health_versions = {row["update_version"] for r in out33 for row in r.get("method_health") or []}
    check("T33.2 no skipped version gets ANY health row, so none can look freshly refreshed",
          health_versions == set(expected_done) and not (health_versions & set(expected_skipped)),
          str(sorted(health_versions)))
    stop33 = [f for e, f in events33 if e == "collector_budget_stop"]
    check("T33.3 the budget stop names the processed and skipped versions",
          len(stop33) == 1 and stop33[0]["processed"] == ",".join(expected_done)
          and stop33[0]["skipped"] == ",".join(expected_skipped)
          and stop33[0]["versions_processed"] == 4 and stop33[0]["versions_skipped"] == 14,
          str(stop33))
    check("T33.4 and carries the pool's fetched, parsed, failed and skipped counts",
          bool(stop33) and stop33[0]["threads_fetched"] == 180 and stop33[0]["threads_parsed"] == 178
          and stop33[0]["threads_failed"] == 2 and stop33[0]["threads_skipped"] == 0, str(stop33))
    walk33 = [f for e, f in events33 if e == "obs_version_walk"]
    check("T33.5 every run records its walk, budget stop or not",
          len(walk33) == 1 and walk33[0]["budget_stopped"] is True
          and walk33[0]["order"] == ",".join(order) and walk33[0]["skipped"] == ",".join(expected_skipped),
          str(walk33))

    # A budget that runs out INSIDE the forum pool: the stop carries counts, and no version gets a row.
    def pool_fetch(url, timeout=25):
        if "/list/" in url:
            return LISTING_HTML
        return THREAD_HTML

    events34, restore34 = _capture_emits()
    real_get_pool34 = forum.get_pool
    real_lr34 = obs_adapter.last_refreshed_by_version
    real_records34 = obs.active_obs_records
    prior_budget = rb.get_run_budget()
    try:
        # 3 listing checks + 1 thread check pass; the second thread check expires.
        rb.set_run_budget(_CountdownBudget(allow=4))
        forum.reset_pool()
        forum.get_pool = lambda *a, **k: real_get_pool34(max_threads_per_forum=5, listing_pages=1,
                                                          fetch=pool_fetch)
        obs_adapter.last_refreshed_by_version = lambda: dict(same)
        obs.active_obs_records = lambda: [(v, None) for v in _OBS_VERSIONS]
        out34 = obs_adapter.ObsCollector().collect(CollectorContext(write=False, since=None, max_pages=1))
    finally:
        restore34()
        forum.get_pool = real_get_pool34
        obs_adapter.last_refreshed_by_version = real_lr34
        obs.active_obs_records = real_records34
        rb.set_run_budget(prior_budget)
        forum.reset_pool()
    fstop = [f for e, f in events34 if e == "obs_forum_budget_stop"]
    check("T33.6 a pool budget stop carries fetched, parsed, failed and skipped counts",
          len(fstop) == 1 and fstop[0]["reason"] == "thread_fetch" and fstop[0]["threads_fetched"] == 1
          and fstop[0]["threads_parsed"] == 1 and fstop[0]["threads_failed"] == 0
          and fstop[0]["threads_skipped"] == 1, str(fstop))
    check("T33.7 a run whose pool was cut short writes NO version rows at all",
          out34 == [], str(out34))
    cstop = [f for e, f in events34 if e == "collector_budget_stop"]
    check("T33.8 and its collector stop lists every version as skipped",
          len(cstop) == 1 and cstop[0]["versions_processed"] == 0 and cstop[0]["versions_skipped"] == 18
          and cstop[0]["threads_skipped"] == 1, str(cstop))

    events35, restore35 = _capture_emits()
    prior_budget = rb.get_run_budget()
    try:
        rb.set_run_budget(_CountdownBudget(allow=1))
        forum.build_pool(max_threads_per_forum=5, listing_pages=1, fetch=pool_fetch)
    finally:
        restore35()
        rb.set_run_budget(prior_budget)
    lstop = [f for e, f in events35 if e == "obs_forum_budget_stop" and f["reason"] == "listing_enumeration"]
    check("T33.9 a listing-stage stop is emitted once, with the listings it skipped",
          len(lstop) == 1 and lstop[0]["listings_requested"] == 1 and lstop[0]["listings_skipped"] == 2,
          str(lstop))

    print("T34 the registry describes the new failure semantics")
    from lib import acquisition_methods as am
    entry = next(m for m in am.METHODS if m["method_id"] == "obs_forum")
    modes = " ".join(entry["failure_modes"])
    check("T34.1 failure_modes say a legitimately textless post is counted apart",
          "threads_textless" in modes and "threads_bodyless" in modes, modes[:200])
    check("T34.2 failure_modes describe the pool-collapse safeguard", "material share" in modes)


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
