import json, pathlib
STATE_PATH=pathlib.Path("auxsays/_data/patch_state.json")
NOTIFY_PATH=pathlib.Path("auxsays/_data/patch_notifications.json")
def load_json(path,fallback): return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback
def save_json(path,payload): path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
def main():
 state=load_json(STATE_PATH,{})
 state.setdefault("davinci-resolve", {"current_version":"21 Public Beta 1","previous_version":"","current_consensus":"Moderate","previous_consensus":"","status_change_type":"new"})
 save_json(STATE_PATH,state)
if __name__=="__main__": main()
