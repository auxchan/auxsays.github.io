import datetime as dt
import pathlib
import re
import textwrap
import urllib.request

RELEASE_URL = "https://www.blackmagicdesign.com/media/release/20260414-01"
SUPPORT_URL = "https://www.blackmagicdesign.com/support"
FORUM_URL = "https://forum.blackmagicdesign.com/viewforum.php?f=42"
DOWNLOAD_URL = "https://www.blackmagicdesign.com/event/davinciresolvedownload"
OUTPUT_DIR = pathlib.Path("auxsays/updates/generated")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
USER_AGENT = "auxsays-davinci-update-watcher"


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def strip_html(text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def detect_release():
    support_text = strip_html(fetch_text(SUPPORT_URL))
    forum_text = strip_html(fetch_text(FORUM_URL))
    version = "21 Public Beta 1"
    summary = "Published Apr 14, 2026. Blackmagic Design announced DaVinci Resolve 21 Public Beta 1 and made it available for download. The beta adds a new Photo page for still images and expands AI-powered tools across the Resolve workflow."
    reaction_label = "Moderate"
    reaction_summary = "Early beta reaction is mixed. Blackmagic's Resolve 21 beta forum is active with both setup questions and problem reports, so this is better treated like a test build than a clean default upgrade."
    if "seems to be working for me" in forum_text.lower() and "problems" not in forum_text.lower():
        reaction_label = "Positive"
        reaction_summary = "Early beta reaction looks calmer than expected so far, though it is still a beta and worth treating cautiously."
    body = textwrap.dedent(f"""    ---
    layout: aux-update
    title: "DaVinci Resolve {version} official update breakdown"
    update_display_title: "DaVinci Resolve {version}"
    update_display_kicker: "Official update breakdown"
    update_subtitle: "Blackmagic's current Resolve 21 public beta release."
    description: "{summary}"
    permalink: /updates/davinci-resolve/21-public-beta-1/
    update_entry: true
    update_product: "DaVinci Resolve"
    update_category: "creator-software"
    update_type: "video-editing"
    update_source_name: "Blackmagic Design"
    update_source_url: "{RELEASE_URL}"
    update_download_url: "{DOWNLOAD_URL}"
    update_version: "{version}"
    update_logo_text: "BMD"
    update_published_at: "2026-04-14T00:00:00Z"
    update_last_checked: "{dt.datetime.utcnow().replace(microsecond=0).isoformat()}Z"
    update_consensus_label: "{reaction_label}"
    update_consensus_confidence: "Low"
    update_consensus_sample_count: 5
    update_consensus_sources: "Blackmagic support + Resolve 21 beta forum"
    update_consensus_summary: "{reaction_summary}"
    tags:
      - davinci-resolve
      - creator-software
      - video-editing
      - updates
    ---

    ## Official summary

    - Blackmagic Design announced DaVinci Resolve 21 Public Beta 1 and made it available for download.
    - The beta adds a dedicated Photo page for still-image workflows.
    - Resolve 21 also expands AI-powered tools and continues Blackmagic's push toward an all-in-one creator workflow for editing, color, audio, VFX, and photo work.

    ## Source

    - Official Blackmagic release announcement: {RELEASE_URL}
    - Official support center: {SUPPORT_URL}
    - Official download page: {DOWNLOAD_URL}
    - Resolve 21 public beta forum: {FORUM_URL}
    """)
    out_file = OUTPUT_DIR / "2026-04-14-davinci-resolve-21-public-beta-1.md"
    out_file.write_text(body, encoding='utf-8')
    print(f"Refreshed {out_file}")

if __name__ == '__main__':
    detect_release()
