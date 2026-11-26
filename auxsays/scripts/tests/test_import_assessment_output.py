"""The import lane of the stored provisional assessments (import_assessment_output.py + assessment-import.yml).

What is pinned: the file is installed only when every independent check passes (the whole file is refused for
one bad entry); a refused candidate never touches the tracked file; the script runs as a bare script and prints
fixed status lines only; and the workflow reads the file with no credential, names it as its ONLY writeback path,
references no secret and stays out of the shared writer queue. Offline; writes only under a temporary folder.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]
REPO = SCRIPTS.parents[1]
sys.path.insert(0, str(SCRIPTS))

import yaml  # noqa: E402

import import_assessment_output as imp  # noqa: E402
from ci import verify_published_payload as vpp  # noqa: E402
from lib import assessment_output as ao  # noqa: E402

WORKFLOW = REPO / ".github" / "workflows" / "assessment-import.yml"
NOW = datetime(2026, 11, 26, 12, 0, 0, tzinfo=timezone.utc)
COMMIT = "a" * 40
PRIVATE_DIR = vpp.PRIVATE_COMPONENT_DIRS[0]  # the publish gate's own list; no new literal here

PASS = FAIL = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}" + (f"  -- {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n{title}")


def entry(page: str = "example-app|1.2.3|", **over) -> dict:
    e = {"page": page, "fingerprint": "sha256:" + "0" * 64, "reports": 30, "verdict": "", "scope": "", "basis": "",
         "retain": "collection_stale", "page_wide": False, "version_conflicts": [],
         "lines": {"Collection health": "Collection is stale."}, "recommendation": "", "body": "",
         "retained": "AUXSAYS keeps its temporary volume-based precaution.", "other_setups": ""}
    e.update(over)
    return e


def text(pages: list[dict], *, generated_at: str = "2026-01-01T00:00:00Z") -> str:
    return ao.render(pages, rule_version="example-rule-1", generated_at=generated_at, source_commit=COMMIT)


def errors(t: str | bytes) -> list[str]:
    return imp.candidate_errors(t if isinstance(t, bytes) else t.encode("utf-8"), now=NOW)


# ------------------------------------------------------------------------------------------------ [V]
def check_validation() -> None:
    section("[V] independent checks")
    good = text([entry(), entry("example-app|1.2.4|")])
    check("V1 a canonical, valid file passes", errors(good) == [], str(errors(good)))
    shipped = ao.OUTPUT_PATH.read_bytes() if ao.OUTPUT_PATH.is_file() else good.encode("utf-8")
    check("V2 the shipped output file passes the import's checks (the contract is the reader's own)",
          imp.candidate_errors(shipped) == [], str(imp.candidate_errors(shipped)))
    bad_entry = text([entry(), entry("example-app|1.2.4|", verdict="WAIT", basis="")])
    check("V3 one entry the reader would drop makes the WHOLE file refused",
          errors(bad_entry) == ["entry_invalid"], str(errors(bad_entry)))
    unknown = text([entry(retain="some_new_code")])
    check("V4 a code outside the closed vocabulary is refused", errors(unknown) == ["entry_invalid"])
    html = text([entry(retained="<script>x</script>")])
    check("V5 markup in a text field is refused", errors(html) == ["entry_invalid"])
    header = good.replace("schema_version: 1", "schema_version: 2")
    check("V6 a header the reader does not know is refused", errors(header) == ["header_invalid"])
    extra_key = good.replace("source_commit: ", "extra: 1\nsource_commit: ")
    check("V7 an unknown top-level key is refused", errors(extra_key) == ["header_invalid"])
    commented = good + "# a comment of its own\n"
    check("V8 a comment of its own (not the canonical text) is refused", errors(commented) == ["not_canonical"])
    reordered = good.replace("schema_version: 1\nrule_version: example-rule-1",
                             "rule_version: example-rule-1\nschema_version: 1")
    check("V9 the same content in another layout is refused", errors(reordered) == ["not_canonical"])
    doc = yaml.safe_load(good)
    anchored = yaml.safe_dump(doc, sort_keys=False).replace("lines:", "lines: &L", 1)
    check("V10 an anchor (and any non-canonical YAML) is refused", "not_canonical" in errors(anchored)
          or "does_not_parse" in errors(anchored), str(errors(anchored)))
    twice = text([entry(), entry()])
    check("V11 a page listed twice is refused", errors(twice) == ["page_listed_twice"], str(errors(twice)))
    future = text([entry()], generated_at="2026-11-26T13:00:00Z")
    check("V12 a file stamped in the future is refused", errors(future) == ["generated_in_future"])
    check("V13 an empty, oversized, non-UTF-8 or unparseable candidate is refused, never a crash",
          (errors(b""), errors(b"x" * (imp.MAX_BYTES + 1)), errors(b"\xff\xfe"), errors("a: [\n"))
          == (["empty"], ["too_large"], ["not_utf8"], ["does_not_parse"]))
    leak = text([entry(retained=f"See {PRIVATE_DIR} for the rule.")])
    named = text([entry(retained="The file provisional_assessments.yml is public.")])
    check("V14 a text naming the private component is refused; the public output's own name is not",
          errors(leak) == ["names_private_component"] and errors(named) == [], str((errors(leak), errors(named))))
    listed = text([entry(page=["example-app|1.2.3|"])])
    impossible = text([entry()], generated_at="2026-13-45T99:99:99Z")
    check("V15 an entry shape the contract did not foresee, or an impossible stamp, is a refusal, never a crash",
          (errors(listed), errors(impossible)) == (["entry_invalid"], ["header_invalid"]),
          str((errors(listed), errors(impossible))))


# ------------------------------------------------------------------------------------------------ [I]
def check_install(tmp: Path) -> None:
    section("[I] install")
    target = tmp / "repo" / "auxsays" / "_data" / ao.OUTPUT_NAME
    good, other = tmp / "good.yml", tmp / "other.yml"
    good.write_bytes((text([entry()])).encode("utf-8"))
    other.write_bytes((text([entry("example-app|1.2.4|")])).encode("utf-8"))
    first = imp.install(good, target, now=NOW)
    again = imp.install(good, target, now=NOW)
    check("I1 a valid candidate is installed once, then reported unchanged",
          (first, again) == ((imp.INSTALLED, []), (imp.UNCHANGED, [])) and target.read_bytes() == good.read_bytes(),
          str((first, again)))
    before = target.read_bytes()
    bad = tmp / "bad.yml"
    bad.write_bytes((text([entry(verdict="WAIT")])).encode("utf-8"))
    refused = imp.install(bad, target, now=NOW)
    check("I2 a refused candidate leaves the tracked file byte-identical",
          refused[0] == imp.REFUSED and target.read_bytes() == before, str(refused))
    check("I3 a missing candidate is refused", imp.install(tmp / "absent.yml", target, now=NOW)[0] == imp.REFUSED)
    changed = imp.install(other, target, now=NOW)
    check("I4 a different valid candidate replaces the file",
          changed == (imp.INSTALLED, []) and target.read_bytes() == other.read_bytes())
    script = SCRIPTS / "import_assessment_output.py"
    leak = tmp / "leak.yml"
    leak.write_bytes((text([entry(retained=f"SECRET-MARKER-41 {PRIVATE_DIR}")])).encode("utf-8"))
    run = subprocess.run([sys.executable, str(script), "--candidate", str(leak), "--target", str(target)],
                         capture_output=True, text=True, cwd=str(tmp))
    out = run.stdout + run.stderr
    check("I5 run as a BARE script: refusal exits 1 and prints one fixed status line, never the content",
          run.returncode == 1 and out.strip() == "IMPORT_STATUS: refused reasons=names_private_component"
          and "SECRET-MARKER-41" not in out, out[-300:])
    ok = subprocess.run([sys.executable, str(script), "--candidate", str(other), "--target", str(target)],
                        capture_output=True, text=True, cwd=str(tmp))
    check("I6 run as a bare script on an identical file: exit 0, `unchanged`",
          ok.returncode == 0 and ok.stdout.strip() == "IMPORT_STATUS: unchanged", ok.stdout + ok.stderr)
    older = tmp / "older.yml"
    older.write_bytes((text([entry()], generated_at="2025-12-31T00:00:00Z")).encode("utf-8"))
    before = target.read_bytes()
    back = imp.install(older, target, now=NOW)
    newer = tmp / "newer.yml"
    newer.write_bytes((text([entry()], generated_at="2026-01-02T00:00:00Z")).encode("utf-8"))
    forward = imp.install(newer, target, now=NOW)
    check("I7 a valid file generated EARLIER than the installed one is refused (no silent revert); a newer one installs",
          back == (imp.REFUSED, ["older_than_installed"]) and forward == (imp.INSTALLED, [])
          and target.read_bytes() == newer.read_bytes(), str((back, forward, before == target.read_bytes())))


# ------------------------------------------------------------------------------------------------ [F]
def _runs(doc: dict) -> list[str]:
    """Every `run:` scalar of the workflow with full-line shell comments removed (parsed, not grepped)."""
    out = []
    for job in doc["jobs"].values():
        for step in job.get("steps", []):
            if "run" in step:
                out.append("\n".join(ln for ln in str(step["run"]).splitlines() if not ln.lstrip().startswith("#")))
    return out


def check_workflow() -> None:
    section("[F] the workflow")
    raw = WORKFLOW.read_text(encoding="utf-8")
    doc = yaml.load(raw, Loader=yaml.SafeLoader)
    triggers = doc.get(True) or doc.get("on")  # YAML 1.1 reads the bare key `on` as True
    check("F1 scheduled and dispatchable only (no push, pull_request or workflow_run trigger)",
          set(triggers) == {"schedule", "workflow_dispatch"}, str(triggers))
    check("F2 permissions are exactly contents: write and actions: write",
          doc["permissions"] == {"contents": "write", "actions": "write"}, str(doc["permissions"]))
    check("F3 its own concurrency group, never the shared writer queue",
          doc["concurrency"] == {"group": "assessment-import", "cancel-in-progress": False})
    check("F4 it references no secret of any kind", "secrets." not in raw and "secrets[" not in raw)
    runs = _runs(doc)
    shell = "\n".join(runs)
    fetch = [r for r in runs if "fetch" in r and "OUTPUT_REPO" in r]
    check("F5 the output file is read anonymously over HTTPS from the output repository, one blob, no checkout",
          len(fetch) == 1 and 'https://github.com/${OUTPUT_REPO}.git' in fetch[0]
          and "git -C \"$RUNNER_TEMP/output\" show \"FETCH_HEAD:${OUTPUT_FILE}\"" in fetch[0]
          and "TOKEN" not in fetch[0] and "clone" not in fetch[0], fetch[0][-300:] if fetch else "no fetch step")
    allows = re.findall(r"--allow\s+(\S+)", shell)
    check("F6 the writeback's ONLY path is the output file, named exactly",
          allows == [ao.OUTPUT_RELPATH] and shell.count("automation_writeback.py") == 1, str(allows))
    order = [i for i, r in enumerate(runs) if "import_assessment_output.py" in r] + \
            [i for i, r in enumerate(runs) if "automation_writeback.py" in r]
    check("F7 the independent check runs before, and in a separate step from, the writeback",
          len(order) == 2 and order[0] < order[1], str(order))
    check("F8 every multi-command step that pipes sets pipefail",
          all("set -euo pipefail" in r for r in runs if "|" in r.replace("||", "") and "\n" in r.strip()))
    steps = [st for job in doc["jobs"].values() for st in job.get("steps", [])]
    wb = [st for st in steps if "automation_writeback.py" in str(st.get("run", ""))]
    lead = str(wb[0]["run"]).split("automation_writeback.py")[0] if wb else ""
    lead = "\n".join(ln for ln in lead.splitlines() if not ln.lstrip().startswith("#"))
    check("F10 the writeback runs on EVERY run that passed the check (no step condition, no early exit), so its "
          "no-change deploy recovery is reachable",
          len(wb) == 1 and "if" not in wb[0] and not re.search(r"\bexit\b", lead)
          and "--deploy-recovery" in str(wb[0]["run"]), lead[-300:])
    names = sorted(p.name for p in WORKFLOW.parent.glob("*.y*ml") if ao.OUTPUT_NAME in p.read_text(encoding="utf-8"))
    check("F9 it is the ONLY workflow of this repository that names the output file", names == [WORKFLOW.name],
          str(names))


def run() -> int:
    try:
        check_validation()
        with tempfile.TemporaryDirectory(prefix="aux-import-") as td:
            check_install(Path(td))
        check_workflow()
    finally:
        ao.reset()
    print("\n" + "=" * 78)
    print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
    for f in FAILURES:
        print(f"  failed: {f}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
