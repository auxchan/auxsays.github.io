import datetime as dt, json, pathlib, re, urllib.request, os, yaml
API_URL="https://api.github.com/repos/obsproject/obs-studio/releases"
OUTPUT_DIR=pathlib.Path("auxsays/updates/generated")
STATE_PATH=pathlib.Path("auxsays/_data/patch_state.json")
NOTIFY_PATH=pathlib.Path("auxsays/_data/patch_notifications.json")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def github_json(url:str):
    headers={"User-Agent":"auxsays-release-intelligence"}
    token=os.getenv("GITHUB_TOKEN")
    if token: headers["Authorization"]=f"Bearer {token}"
    headers["Accept"]="application/vnd.github+json"
    req=urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp: return json.loads(resp.read().decode("utf-8"))

def load_json(path,fallback): return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback

def save_json(path,payload): path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

def slugify(v:str): return re.sub(r"[^a-z0-9]+","-",str(v).lower()).strip("-")

def yaml_frontmatter(data): return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000).strip()

def write_obs_update_page(release, status="current"):
    version=(release.get("tag_name") or release.get("name") or "").lstrip("v")
    published=release.get("published_at") or dt.datetime.utcnow().replace(microsecond=0).isoformat()+"Z"
    date_slug=published[:10]
    slug=slugify(version)
    body=(release.get("body") or "No official release body was returned by the GitHub API.").strip()
    report_count=0
    label="Insufficient data"
    score=0
    if status == "current":
        label="Moderate"
        score=12
    front={
        "layout":"aux-update",
        "title":f"OBS Studio {version} official update breakdown",
        "description":f"Published {published[:10]}. OBS Studio {version} official release record with AUXSAYS consensus tracking and the official upstream release notes preserved below.",
        "permalink":f"/updates/obs-project/obs-studio/{slug}/",
        "update_entry":True,
        "company_id":"obs-project",
        "product_id":"obs-studio",
        "update_brand_id":"obs-studio",
        "update_product":"OBS Studio",
        "update_category":"creator-software",
        "update_type":"broadcasting",
        "update_source_name":"OBS Project",
        "update_source_url":release.get("html_url") or f"https://github.com/obsproject/obs-studio/releases/tag/{release.get('tag_name')}",
        "update_download_url":"https://obsproject.com/download",
        "update_version":version,
        "update_logo_text":"OBS",
        "update_published_at":published,
        "update_last_checked":dt.datetime.utcnow().replace(microsecond=0).isoformat()+"Z",
        "update_status":status,
        "update_feed_title":f"OBS Studio {version}",
        "update_detail_title":f"OBS Studio {version}",
        "update_consensus_label":label,
        "consensus_score":score,
        "consensus_score_percent":max(0,min(100,int((score+100)/2))),
        "update_report_count":report_count,
        "update_consensus_confidence":"Low",
        "quick_verdict":f"OBS Studio {version} has an initialized AUXSAYS record. Consensus will be updated as matched reports are collected.",
        "official_summary":f"OBS Project published OBS Studio {version}. The official GitHub release notes are preserved below.",
        "consensus_report":"Consensus collection is initialized. Community reports still need to be gathered, categorized, and verified before a strong recommendation is assigned.",
        "complaint_themes":[],
        "status_events":[
            {"at":published,"label":"Published","note":"Official OBS release detected from GitHub releases."},
            {"at":dt.datetime.utcnow().replace(microsecond=0).isoformat()+"Z","label":label,"note":"Initial AUXSAYS consensus record created."}
        ],
        "official_patch_notes_source_type":"github-release",
        "official_patch_notes_capture_status":"captured-from-github-release-body"
    }
    output=OUTPUT_DIR/f"{date_slug}-obs-studio-{slug}.md"
    output.write_text("---\n"+yaml_frontmatter(front)+"\n---\n\n## Official patch notes\n\n"+body+"\n", encoding="utf-8")

def main():
    releases=github_json(API_URL)
    stable=[r for r in releases if not r.get("prerelease")][:2]
    state=load_json(STATE_PATH,{})
    notes=load_json(NOTIFY_PATH,[])
    for idx, release in enumerate(stable):
        write_obs_update_page(release, "current" if idx==0 else "archived")
    if stable:
        latest=(stable[0].get("tag_name") or "").lstrip("v")
        prev=state.get("obs-studio",{})
        now=dt.datetime.utcnow().replace(microsecond=0).isoformat()+"Z"
        state["obs-studio"]={"current_version":latest,"previous_version":prev.get("current_version",""),"current_consensus":"Moderate","previous_consensus":prev.get("current_consensus","Insufficient"),"status_changed_at":now,"status_change_type":"updated","report_count":0}
        if not notes or notes[0].get("version")!=latest:
            notes.insert(0,{"product":"OBS Studio","version":latest,"change_type":"updated","from":prev.get("current_consensus","Insufficient"),"to":"Moderate","changed_at":now,"message":f"OBS Studio {latest} official update record has been refreshed with upstream release notes and initialized consensus tracking.","url":f"/updates/obs-project/obs-studio/{slugify(latest)}/","report_count":0})
    save_json(STATE_PATH,state); save_json(NOTIFY_PATH,notes[:25])
if __name__=="__main__": main()
