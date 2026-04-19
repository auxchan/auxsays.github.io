import datetime as dt
import json
import os
import pathlib
import re
import textwrap
import urllib.request

API_URL = "https://api.github.com/repos/obsproject/obs-studio/releases/latest"
OUTPUT_DIR = pathlib.Path("auxsays/updates/generated")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def github_request(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "auxsays-obs-update-watcher"
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def split_sections(body: str):
    current = "General"
    sections = {current: []}
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            current = re.sub(r"^#+\s*", "", line).strip()
            sections.setdefault(current, [])
            continue
        if line.startswith(('-', '*')):
            item = line[1:].strip()
            if item:
                sections.setdefault(current, []).append(item)
            continue
        if line and not line.startswith('!['):
            sections.setdefault(current, []).append(line)
    return {k: v for k, v in sections.items() if v}


def build_summary(sections: dict):
    bullets = []
    for items in sections.values():
        for item in items:
            bullets.append(item)
    bullets = bullets[:6]
    if not bullets:
        return "Official OBS Studio release notes are available at the linked source.", []
    lead = bullets[0]
    if len(bullets) > 1:
        lead += " " + bullets[1]
    return lead, bullets


def format_release(data: dict):
    version = data.get("tag_name") or data.get("name") or "latest"
    release_name = data.get("name") or version
    published_at = data.get("published_at") or dt.datetime.utcnow().isoformat() + "Z"
    published_date = published_at[:10]
    body = data.get("body") or ""
    html_url = data.get("html_url") or "https://github.com/obsproject/obs-studio/releases"

    sections = split_sections(body)
    summary, bullets = build_summary(sections)
    why_it_matters = bullets[0] if bullets else "OBS Studio shipped a new release from the official repository."

    slug = slugify(version)
    filename = OUTPUT_DIR / f"{published_date}-obs-studio-{slug}.md"
    if filename.exists():
        return None

    section_md = []
    for heading, items in list(sections.items())[:5]:
        clean_items = items[:8]
        section_md.append(f"## {heading}\n")
        for item in clean_items:
            section_md.append(f"- {item}")
        section_md.append("")

    content = textwrap.dedent(f"""\
    ---
    layout: aux-update
    title: "OBS Studio {version}: official update breakdown"
    description: "{summary.replace('"', '\\"')}"
    permalink: /updates/obs-studio/{slug}/
    update_entry: true
    update_product: "OBS Studio"
    update_category: "creator-software"
    update_type: "broadcasting"
    update_source_name: "GitHub Releases"
    update_source_url: "{html_url}"
    update_version: "{version}"
    update_published_at: "{published_at}"
    update_last_checked: "{dt.datetime.utcnow().replace(microsecond=0).isoformat()}Z"
    update_sentiment_ready: false
    tags:
      - obs-studio
      - creator-software
      - broadcasting
      - updates
    ---

    ## TL;DR

    {summary}

    ## Why this matters

    {why_it_matters}

    ## Official breakdown

    {'\n'.join(section_md).strip()}

    ## Source

    - Official release notes: {html_url}
    """)
    filename.write_text(content, encoding="utf-8")
    return str(filename)


if __name__ == "__main__":
    data = github_request(API_URL)
    result = format_release(data)
    if result:
        print(f"Generated {result}")
    else:
        print("Latest OBS release already exists. No file created.")
