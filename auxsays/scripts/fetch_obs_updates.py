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

DOWNLOAD_PAGE_URL = "https://obsproject.com/download"
PRODUCT_NAME = "OBS Studio"
CATEGORY = "creator-software"
TYPE = "broadcasting"
LOGO_TEXT = "OBS"


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

        if line.startswith(("-", "*")):
            item = line[1:].strip()
            if item and not item.startswith("!"):
                sections.setdefault(current, []).append(item)
            continue

        if line and not line.startswith("!["):
            sections.setdefault(current, []).append(line)

    return {k: v for k, v in sections.items() if v}


def collect_bullets(sections: dict, max_items: int = 8):
    bullets = []
    for items in sections.values():
        for item in items:
            cleaned = re.sub(r"\s+", " ", item).strip()
            if cleaned:
                bullets.append(cleaned)
            if len(bullets) >= max_items:
                return bullets
    return bullets


def build_summary(version: str, published_at: str, bullets: list[str]) -> str:
    date_str = published_at[:10]
    try:
        date_obj = dt.datetime.fromisoformat(date_str)
        nice_date = date_obj.strftime("%b %d, %Y")
    except ValueError:
        nice_date = date_str

    summary_parts = []
    if bullets:
        summary_parts.append(bullets[0])
    if len(bullets) > 1:
        summary_parts.append(bullets[1])

    summary = " ".join(summary_parts).strip()
    if not summary:
        summary = f"{PRODUCT_NAME} {version} is the latest official release published by the developer."

    return f"Published {nice_date}. {summary}"


def section_block(heading: str, items: list[str]) -> str:
    lines = [f"## {heading}", ""]
    for item in items[:8]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def format_release(data: dict):
    version = data.get("tag_name") or data.get("name") or "latest"
    published_at = data.get("published_at") or dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    published_date = published_at[:10]
    body = data.get("body") or ""
    html_url = data.get("html_url") or "https://github.com/obsproject/obs-studio/releases"

    sections = split_sections(body)
    bullets = collect_bullets(sections, max_items=8)
    summary = build_summary(version, published_at, bullets)

    slug = slugify(version)
    filename = OUTPUT_DIR / f"{published_date}-obs-studio-{slug}.md"
    if filename.exists():
        return None

    if bullets:
        key_changes = section_block("Key changes", bullets[:4])
    else:
        key_changes = textwrap.dedent("""        ## Key changes

        - Official release notes are available at the linked source.
        """)

    structured_sections = []
    count = 0
    for heading, items in sections.items():
        if count >= 4:
            break
        structured_sections.append(section_block(heading, items))
        count += 1

    official_breakdown = "\n".join(structured_sections).strip()
    if not official_breakdown:
        official_breakdown = textwrap.dedent("""        ## Official breakdown

        - Official release notes are available at the linked source.
        """)

    content = textwrap.dedent(f"""    ---
    layout: aux-update
    title: "{PRODUCT_NAME} {version} official update breakdown"
    description: "{summary.replace('"', '\\\"')}"
    permalink: /updates/obs-studio/{slug}/
    update_entry: true
    update_product: "{PRODUCT_NAME}"
    update_category: "{CATEGORY}"
    update_type: "{TYPE}"
    update_source_name: "GitHub Releases"
    update_source_url: "{html_url}"
    update_download_url: "{DOWNLOAD_PAGE_URL}"
    update_version: "{version}"
    update_logo_text: "{LOGO_TEXT}"
    update_published_at: "{published_at}"
    update_last_checked: "{dt.datetime.utcnow().replace(microsecond=0).isoformat()}Z"
    update_sentiment_ready: false
    tags:
      - obs-studio
      - creator-software
      - broadcasting
      - updates
    ---

    {key_changes}

    {official_breakdown}

    ## Source

    - Official GitHub releases: {html_url}
    - Official download page: {DOWNLOAD_PAGE_URL}
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
