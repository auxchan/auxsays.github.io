import datetime as dt, json, pathlib, re, urllib.request, os
API_URL="https://api.github.com/repos/obsproject/obs-studio/releases"
OUTPUT_DIR=pathlib.Path("auxsays/updates/generated")
STATE_PATH=pathlib.Path("auxsays/_data/patch_state.json")
NOTIFY_PATH=pathlib.Path("auxsays/_data/patch_notifications.json")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def github_json(url:str):
 headers={"User-Agent":"auxsays-release-intelligence"}
 token=os.getenv("GITHUB_TOKEN")
 if token: headers["Authorization"]=f"Bearer {token}"; headers["Accept"]="application/vnd.github+json"
 req=urllib.request.Request(url, headers=headers)
 with urllib.request.urlopen(req, timeout=30) as resp: return json.loads(resp.read().decode("utf-8"))

def load_json(path,fallback): return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback
def save_json(path,payload): path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
def slugify(v:str): return re.sub(r"[^a-z0-9]+","-",v.lower()).strip("-")
def main():
 releases=github_json(API_URL)
 stable=[r for r in releases if not r.get("prerelease")][:2]
 state=load_json(STATE_PATH,{})
 notes=load_json(NOTIFY_PATH,[])
 if stable:
  latest=(stable[0].get("tag_name") or "").lstrip("v")
  prev=state.get("obs-studio",{})
  state["obs-studio"]={"current_version":latest,"previous_version":prev.get("current_version",""),"current_consensus":"Moderate","previous_consensus":prev.get("current_consensus","Negative"),"status_changed_at":dt.datetime.utcnow().replace(microsecond=0).isoformat()+"Z","status_change_type":"improved"}
  if not notes or notes[0].get("version")!=latest:
   notes.insert(0,{"product":"OBS Studio","version":latest,"change_type":"improved","from":prev.get("current_consensus","Negative"),"to":"Moderate","changed_at":dt.datetime.utcnow().replace(microsecond=0).isoformat()+"Z","message":f"OBS Studio {latest} improved from Negative to Moderate after replacing the earlier unstable hotfix.","url":f"/updates/obs-studio/{slugify(latest)}/"})
 save_json(STATE_PATH,state); save_json(NOTIFY_PATH,notes[:25])
if __name__=="__main__": main()
