\
import datetime as dt
import email.utils
import json
import pathlib
import re
import textwrap
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import os

API_URL = "https://api.github.com/repos/obsproject/obs-studio/releases/latest"
ISSUES_URL = "https://api.github.com/repos/obsproject/obs-studio/issues"
FORUM_RSS_URL = "https://obsproject.com/forum/list/-/index.rss"
DOWNLOAD_PAGE_URL = "https://obsproject.com/download"
OUTPUT_DIR = pathlib.Path("auxsays/updates/generated")
INDEX_PATH = pathlib.Path("auxsays/updates/index.md")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PRODUCT_NAME = "OBS Studio"
CATEGORY = "creator-software"
TYPE = "broadcasting"
LOGO_TEXT = "OBS"

SEVERE_NEG = ["crash","crashes","crashing","freeze","freezing","fails to launch","won't launch","unable to open","black screen","broken","hang","hangs","memory leak","regression","corrupt","unusable","rollback"]
MEDIUM_NEG = ["stutter","lag","audio issue","desync","plugin issue","plugin broke","bug","buggy","problem","issue","slower","high cpu","high gpu","glitch","flicker","not working","broken scene"]
POSITIVE = ["stable","works fine","fixed","fixes","improved","smoother","better","resolved","solid","no issue","no issues","works great"]
THEMES = {
    "crash stability": ["crash","hang","freeze","launch","black screen","regression","unusable"],
    "performance": ["stutter","lag","high cpu","high gpu","slower","memory leak"],
    "audio": ["audio","desync","sound"],
    "plugins": ["plugin","browser source","websocket"],
    "ui workflow": ["ui","layout","mixer","workflow","scene"]
}

def http_get(url: str, accept: str = None):
    headers = {"User-Agent": "auxsays-obs-consensus-pilot"}
    if accept:
        headers["Accept"] = accept
    token = os.getenv("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()

def github_json(url: str):
    return json.loads(http_get(url, "application/vnd.github+json").decode("utf-8"))

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
    dt_obj = dt.datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    nice_date = dt_obj.strftime("%b %d, %Y")
    summary_parts = []
    if bullets:
        summary_parts.append(bullets[0])
    if len(bullets) > 1:
        summary_parts.append(bullets[1])
    summary = " ".join(summary_parts).strip()
    if not summary:
        summary = f"{PRODUCT_NAME} {version} is the latest official release published by the developer."
    return f"Published {nice_date}. {summary}"

def contains_version(text: str, version: str) -> bool:
    if not text:
        return False
    text = text.lower()
    version = version.lower().lstrip("v")
    parts = [version, f"obs {version}", f"obs studio {version}"]
    return any(p in text for p in parts)

def score_text(text: str):
    lowered = text.lower()
    score = 0
    severe = 0
    matched_themes = set()
    for kw in SEVERE_NEG:
        if kw in lowered:
            score -= 3
            severe += 1
    for kw in MEDIUM_NEG:
        if kw in lowered:
            score -= 1
    for kw in POSITIVE:
        if kw in lowered:
            score += 1
    for theme, kws in THEMES.items():
        if any(kw in lowered for kw in kws):
            matched_themes.add(theme)
    return score, severe, matched_themes

def fetch_github_reaction(version: str, published_at: str):
    params = urllib.parse.urlencode({"state":"all","sort":"updated","direction":"desc","since":published_at,"per_page":50})
    data = github_json(f"{ISSUES_URL}?{params}")
    matched = []
    for item in data:
        if item.get("pull_request"):
            continue
        title = item.get("title") or ""
        body = item.get("body") or ""
        blob = f"{title}\n{body}"
        if not (contains_version(blob, version) or "obs update" in blob.lower() or version in blob.lower()):
            continue
        score, severe, themes = score_text(blob)
        matched.append({"source":"GitHub Issues","title":title,"score":score,"severe":severe,"themes":sorted(themes)})
    return matched

def fetch_forum_reaction(version: str, published_at: str):
    raw = http_get(FORUM_RSS_URL).decode("utf-8", errors="ignore")
    root = ET.fromstring(raw)
    items = []
    release_dt = dt.datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    for item in root.findall(".//item"):
        title = item.findtext("title") or ""
        desc = item.findtext("description") or ""
        pub_date = item.findtext("pubDate") or ""
        blob = f"{title}\n{desc}"
        if not (contains_version(blob, version) or "obs update" in blob.lower() or version in blob.lower()):
            continue
        try:
            pub_dt = email.utils.parsedate_to_datetime(pub_date)
            if pub_dt < release_dt:
                continue
        except Exception:
            pass
        score, severe, themes = score_text(blob)
        items.append({"source":"OBS Forums","title":title,"score":score,"severe":severe,"themes":sorted(themes)})
    return items

def summarize_reaction(github_items: list, forum_items: list):
    all_items = github_items + forum_items
    sample_count = len(all_items)
    if sample_count < 4:
        return {
            "community_reaction":"insufficient",
            "community_confidence":"Low",
            "community_sample_count":sample_count,
            "community_sources":"GitHub Issues + OBS Forums",
            "community_summary":"Not enough reliable post-release feedback has surfaced yet to make a confident call."
        }

    github_score = sum(i["score"] for i in github_items)
    forum_score = sum(i["score"] for i in forum_items)
    weighted_score = github_score * 0.6 + forum_score * 0.4
    severe_count = sum(i["severe"] for i in all_items)

    theme_counts = {}
    for item in all_items:
        for theme in item["themes"]:
            theme_counts[theme] = theme_counts.get(theme, 0) + 1
    sorted_themes = sorted(theme_counts.items(), key=lambda kv: kv[1], reverse=True)
    theme_phrase = sorted_themes[0][0] if sorted_themes else None

    if severe_count >= 3 or weighted_score <= -4:
        reaction = "negative"
        summary = "Proceed with caution. Repeated complaints are showing up across high-signal sources."
        if theme_phrase:
            summary += f" Early reaction is clustering around {theme_phrase}."
    elif weighted_score >= 2 and severe_count == 0:
        reaction = "positive"
        summary = "Murphy’s law and all, but so far this looks solid."
        if theme_phrase:
            summary += f" No repeated major breakages are surfacing, and the main discussion is around {theme_phrase}."
        else:
            summary += " No repeated major breakages are surfacing across the official community sources checked."
    else:
        reaction = "moderate"
        summary = "If it ain’t broke, maybe don’t mess with it yet."
        if theme_phrase:
            summary += f" Some users are reporting issues, with early discussion centering on {theme_phrase}."
        else:
            summary += " Some users are reporting issues, but the problems do not yet look broad enough to call the release unstable."

    confidence = "Low"
    if sample_count >= 8:
        confidence = "Medium"
    if sample_count >= 20 and github_items and forum_items:
        confidence = "High"

    return {
        "community_reaction":reaction,
        "community_confidence":confidence,
        "community_sample_count":sample_count,
        "community_sources":"GitHub Issues + OBS Forums",
        "community_summary":summary
    }

def section_block(heading: str, items: list[str]) -> str:
    lines = [f"## {heading}", ""]
    for item in items[:8]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)

def write_updates_index():
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text("---\nlayout: aux-updates\ntitle: Updates\npermalink: /updates/\n---\n", encoding="utf-8")

def format_release(data: dict):
    version = (data.get("tag_name") or data.get("name") or "latest").lstrip("v")
    published_at = data.get("published_at") or dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    body = data.get("body") or ""
    html_url = data.get("html_url") or "https://github.com/obsproject/obs-studio/releases"

    sections = split_sections(body)
    bullets = collect_bullets(sections, max_items=8)
    summary = build_summary(version, published_at, bullets)

    github_reaction = fetch_github_reaction(version, published_at)
    forum_reaction = fetch_forum_reaction(version, published_at)
    reaction = summarize_reaction(github_reaction, forum_reaction)

    published_date = published_at[:10]
    slug = slugify(version)
    filename = OUTPUT_DIR / f"{published_date}-obs-studio-{slug}.md"

    key_changes = section_block("Key changes", bullets[:4]) if bullets else "## Key changes\n\n- Official release notes are available at the linked source.\n"
    structured_sections = []
    for idx, (heading, items) in enumerate(sections.items()):
        if idx >= 4:
            break
        structured_sections.append(section_block(heading, items))
    official_breakdown = "\n".join(structured_sections).strip() or "## Official breakdown\n\n- Official release notes are available at the linked source.\n"
    reaction_title = reaction["community_reaction"].capitalize() if reaction["community_reaction"] != "insufficient" else "Insufficient data"

    content = textwrap.dedent(f"""\
    ---
    layout: aux-update
    title: "{PRODUCT_NAME} {version} official update breakdown"
    description: "{summary.replace('"', '\\"')}"
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
    community_reaction: "{reaction['community_reaction']}"
    community_confidence: "{reaction['community_confidence']}"
    community_sample_count: {reaction['community_sample_count']}
    community_sources: "{reaction['community_sources']}"
    community_summary: "{reaction['community_summary'].replace('"', '\\"')}"
    tags:
      - obs-studio
      - creator-software
      - broadcasting
      - updates
    ---

    ## Community reaction

    - **Status:** {reaction_title}
    - **Confidence:** {reaction['community_confidence']}
    - **Sample size:** {reaction['community_sample_count']}
    - **Sources checked:** {reaction['community_sources']}
    - **Reader guidance:** {reaction['community_summary']}

    {key_changes}

    {official_breakdown}

    ## Source

    - Official GitHub releases: {html_url}
    - Official download page: {DOWNLOAD_PAGE_URL}
    - GitHub issues for OBS Studio: https://github.com/obsproject/obs-studio/issues
    - OBS Forums: https://obsproject.com/forum/
    """)
    filename.write_text(content, encoding="utf-8")
    return str(filename), reaction

if __name__ == "__main__":
    write_updates_index()
    data = github_json(API_URL)
    path, reaction = format_release(data)
    print(f"Updated {path}")
    print(json.dumps(reaction, indent=2))
