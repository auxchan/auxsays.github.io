import datetime as dt
import pathlib
import re
import textwrap
import urllib.request

RELEASE_URL = "https://www.blackmagicdesign.com/media/release/20260414-01"
SUPPORT_URL = "https://www.blackmagicdesign.com/support"
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
    release_html = fetch_text(RELEASE_URL)
    support_html = fetch_text(SUPPORT_URL)

    release_text = strip_html(release_html)
    support_text = strip_html(support_html)

    title = "DaVinci Resolve 21 official update breakdown"
    version = "21"

    # Try to detect "Public Beta 1" from support center text.
    beta_match = re.search(r"DaVinci Resolve Studio\s+21\s+Public Beta\s*(\d+)", support_text, re.I)
    if beta_match:
        version = f"21 Public Beta {beta_match.group(1)}"
        title = f"DaVinci Resolve {version} official update breakdown"

    summary = (
        f"Published Apr 14, 2026. Blackmagic Design announced DaVinci Resolve 21 and made the public beta available. "
        f"The 21 release adds a new Photo page for still images and expands AI-powered tools across the Resolve workflow."
    )

    body = textwrap.dedent(f"""    ---
    layout: aux-update
    title: "{title}"
    description: "{summary}"
    permalink: /updates/davinci-resolve/{version.lower().replace(' ', '-').replace('.', '-')}/
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
    update_consensus_label: "Insufficient data"
    update_consensus_confidence: "Low"
    update_consensus_sample_count: 0
    update_consensus_sources: "Official forum parsing not enabled yet"
    update_consensus_summary: "Too little post-release filtering is wired up yet to make a reliable community call. This pilot currently focuses on official release facts only."
    tags:
      - davinci-resolve
      - creator-software
      - video-editing
      - updates
    ---

    ## Official summary

    - Blackmagic Design announced DaVinci Resolve 21 and made the public beta available for download.
    - The new release adds a dedicated Photo page for still-image workflows.
    - Version 21 also expands AI-powered tools and continues Blackmagic's push toward an all-in-one creator workflow for editing, color, audio, VFX, and now photo work.

    ## Source

    - Official Blackmagic release announcement: {RELEASE_URL}
    - Official support center: {SUPPORT_URL}
    - Official download page: {DOWNLOAD_URL}
    """)

    slug_date = "2026-04-14"
    slug_version = version.lower().replace(" ", "-").replace(".", "-")
    out_file = OUTPUT_DIR / f"{slug_date}-davinci-resolve-{slug_version}.md"

    if not out_file.exists():
        out_file.write_text(body, encoding="utf-8")
        print(f"Created {out_file}")
    else:
        # Refresh last_checked field on reruns.
        existing = out_file.read_text(encoding="utf-8")
        refreshed = re.sub(
            r'update_last_checked: ".*?"',
            f'update_last_checked: "{dt.datetime.utcnow().replace(microsecond=0).isoformat()}Z"',
            existing,
        )
        out_file.write_text(refreshed, encoding="utf-8")
        print(f"Refreshed {out_file}")

if __name__ == "__main__":
    detect_release()
