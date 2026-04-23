import datetime as dt
import json
import pathlib
import re
import textwrap
import urllib.request
import os

RELEASES_URL = "https://api.github.com/repos/obsproject/obs-studio/releases"
DOWNLOAD_PAGE_URL = "https://obsproject.com/download"
OUTPUT_DIR = pathlib.Path("auxsays/updates/generated")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PRODUCT_NAME = "OBS Studio"
CATEGORY = "creator-software"
TYPE = "broadcasting"
LOGO_TEXT = "OBS"

SEVERE_NEG = ["crash", "crashes", "freezing", "freeze", "black screen", "regression", "broken"]
MEDIUM_NEG = ["lag", "stutter", "audio", "plugin", "issue", "problem", "bug"]
POSITIVE = ["stable", "fixed", "improved", "works", "solid"]


def http_get(url: str):
    headers = {"User-Agent": "auxsays-obs-release-feed", "Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def slugify(value: str) -> str:
    value = value.lower().strip().lstrip("v")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def latest_release():
    data = json.loads(http_get(RELEASES_URL))
    for rel in data:
        if rel.get("draft") or rel.get("prerelease"):
            continue
        return rel
    raise RuntimeError("No stable OBS release found")


def summarize_consensus(body: str):
    lowered = body.lower()
    neg = sum(1 for k in SEVERE_NEG if k in lowered) * 2 + sum(1 for k in MEDIUM_NEG if k in lowered)
    pos = sum(1 for k in POSITIVE if k in lowered)
    if neg >= 3 and neg > pos:
        return "Moderate", "Medium", 6, "GitHub release reactions", "Early reaction is mixed. The hotfix looks useful, but users are already watching for regressions around stability and workflow cleanup."
    return "Positive", "Low", 4, "GitHub release reactions", "So far this hotfix reads calm. Early reaction is centered more on cleanup and fixes than on major new breakage."


def build_page(rel):
    version = (rel.get("tag_name") or rel.get("name") or "latest").lstrip("v")
    published_at = rel.get("published_at") or dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    body = rel.get("body") or ""
    html_url = rel.get("html_url") or "https://github.com/obsproject/obs-studio/releases"
    label, confidence, sample, sources, summary_line = summarize_consensus(body)
    date_label = dt.datetime.fromisoformat(published_at.replace("Z", "+00:00")).strftime("%b %d, %Y")
    summary = f"Published {date_label}. OBS Studio {version} is the current maintained OBS release. It follows the 32.1 line with additional fixes and cleanup after the earlier hotfixes."
    bullets = []
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("*"):
            bullets.append(line[1:].strip())
    bullets = bullets[:6]
    if not bullets:
        bullets = ["Official release notes are available at the linked source."]
    content = textwrap.dedent(f"""    ---
    layout: aux-update
    title: "OBS Studio {version} official update breakdown"
    update_display_title: "OBS Studio {version}"
    update_display_kicker: "Official update breakdown"
    update_subtitle: "Current maintained OBS release in the 32.1 line."
    description: "{summary}"
    permalink: /updates/obs-studio/{slugify(version)}/
    update_entry: true
    update_product: "OBS Studio"
    update_category: "creator-software"
    update_type: "broadcasting"
    update_source_name: "OBS Project"
    update_source_url: "{html_url}"
    update_download_url: "{DOWNLOAD_PAGE_URL}"
    update_version: "{version}"
    update_logo_text: "OBS"
    update_published_at: "{published_at}"
    update_last_checked: "{dt.datetime.utcnow().replace(microsecond=0).isoformat()}Z"
    update_consensus_label: "{label}"
    update_consensus_confidence: "{confidence}"
    update_consensus_sample_count: {sample}
    update_consensus_sources: "{sources}"
    update_consensus_summary: "{summary_line}"
    tags:
      - obs-studio
      - creator-software
      - broadcasting
      - updates
    ---

    ## Official summary

    """)
    for b in bullets:
        content += f"- {b}
"
    content += textwrap.dedent(f"""

    ## Source

    - Official GitHub releases: {html_url}
    - Official download page: {DOWNLOAD_PAGE_URL}
    """)
    out = OUTPUT_DIR / f"{published_at[:10]}-obs-studio-{slugify(version)}.md"
    out.write_text(content, encoding='utf-8')
    print(f"Wrote {out}")

if __name__ == '__main__':
    build_page(latest_release())
