import datetime as dt
import pathlib
import re
import textwrap
import urllib.request

RELEASE_URL = "https://www.blackmagicdesign.com/media/release/20260414-01"
SUPPORT_URL = "https://www.blackmagicdesign.com/support"
DOWNLOAD_URL = "https://www.blackmagicdesign.com/event/davinciresolvedownload"
FORUM_URL = "https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=234676"
OUTPUT_DIR = pathlib.Path("auxsays/updates/generated")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
USER_AGENT = "auxsays-davinci-update-watcher"

NEG = ["crash","crashes","freeze","freezing","broken","issue","issues","bug","bugs","rollback","unstable","hang","hanging"]
POS = ["stable","works","working","smooth","improved","better","fixed","solid"]

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

def summarize_forum(version: str):
    try:
        forum_text = strip_html(fetch_text(FORUM_URL)).lower()
    except Exception:
        return {
            "label": "Insufficient data",
            "confidence": "Low",
            "sample_count": 0,
            "sources": "Blackmagic Forum",
            "summary": "Too little post-release filtering is wired up yet to make a reliable community call. This pilot currently focuses on official release facts only."
        }
    if version.lower() not in forum_text and "resolve 21" not in forum_text:
        return {
            "label": "Insufficient data",
            "confidence": "Low",
            "sample_count": 0,
            "sources": "Blackmagic Forum",
            "summary": "Not enough version-specific discussion was found in the official forum thread to make a reliable call yet."
        }
    neg = sum(forum_text.count(k) for k in NEG)
    pos = sum(forum_text.count(k) for k in POS)
    sample = neg + pos
    if sample < 3:
        label = "Insufficient data"
        summary = "The official forum thread exists, but there still is not enough filtered discussion to make a reliable community call."
        conf = "Low"
    elif neg >= pos + 4:
        label = "Negative"
        summary = "Proceed with caution. The official forum thread is surfacing more problem reports than calm confirmations so far."
        conf = "Low"
    elif pos >= neg + 3:
        label = "Positive"
        summary = "Early reaction in the official forum looks fairly calm. There are still beta caveats, but the thread is not surfacing one dominant breakage pattern."
        conf = "Low"
    else:
        label = "Moderate"
        summary = "If your current Resolve setup is stable, there is no rush. The official forum thread looks mixed rather than clearly bad or clearly calm."
        conf = "Low"
    return {
        "label": label,
        "confidence": conf,
        "sample_count": sample,
        "sources": "Blackmagic Forum",
        "summary": summary
    }

def detect_release():
    support_html = fetch_text(SUPPORT_URL)
    support_text = strip_html(support_html)
    version = "21"
    beta_match = re.search(r"DaVinci Resolve(?: Studio)?\s+21\s+Public Beta\s*(\d+)", support_text, re.I)
    if beta_match:
        version = f"21 Public Beta {beta_match.group(1)}"
    reaction = summarize_forum(version)
    summary = (
        f"Published Apr 14, 2026. Blackmagic Design announced DaVinci Resolve 21 and made the public beta available. "
        f"The 21 release adds a new Photo page for still images and expands AI-powered tools across the Resolve workflow."
    )
    body = textwrap.dedent(f"""    ---
    layout: aux-update
    title: "DaVinci Resolve {version} official update breakdown"
    description: "{summary}"
    permalink: /updates/davinci-resolve/{version.lower().replace(' ', '-').replace('.', '-')}/
    update_entry: true
    update_product: "DaVinci Resolve"
    update_category: "video-editing"
    update_type: "video-editing"
    update_source_name: "Blackmagic Design"
    update_source_url: "{RELEASE_URL}"
    update_download_url: "{DOWNLOAD_URL}"
    update_version: "{version}"
    update_logo_text: "BMD"
    update_published_at: "2026-04-14T00:00:00Z"
    update_last_checked: "{dt.datetime.utcnow().replace(microsecond=0).isoformat()}Z"
    update_consensus_label: "{reaction['label']}"
    update_consensus_confidence: "{reaction['confidence']}"
    update_consensus_sample_count: {reaction['sample_count']}
    update_consensus_sources: "{reaction['sources']}"
    update_consensus_summary: "{reaction['summary']}"
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
    - Official forum release thread: {FORUM_URL}
    """)
    slug_date = "2026-04-14"
    slug_version = version.lower().replace(" ", "-").replace(".", "-")
    out_file = OUTPUT_DIR / f"{slug_date}-davinci-resolve-{slug_version}.md"
    out_file.write_text(body, encoding="utf-8")
    legacy = OUTPUT_DIR / "2026-04-14-davinci-resolve-21.md"
    if legacy.exists() and "public-beta" in slug_version:
        legacy.write_text(legacy.read_text(encoding='utf-8').replace('update_entry: true','update_entry: false',1), encoding='utf-8')
    print(f"Updated {out_file}")

if __name__ == "__main__":
    detect_release()
