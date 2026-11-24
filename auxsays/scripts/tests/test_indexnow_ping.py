#!/usr/bin/env python3
"""The deploy-time IndexNow ping (P8): which pages are sent, the cap, the skip and the fail-soft.

WHAT IS PINNED, by running the shipped code, never by searching it:

  [P] scripts/ci/indexnow_plan.py, run as the bare script pages.yml runs, over synthetic built sites and
      live sitemaps: a URL is planned when it is new or its stored lastmod moved, never when unchanged or on
      another host, newest first; at most 500, the rest named as dropped; nothing planned when nothing
      changed, when the live sitemap is missing, empty or malformed, or when the key file is missing,
      doubled or wrong; it exits 0 every time, even on a bad argument.
  [K] the shipped key file: one 32-hex <key>.txt at the site root holding its own name, not excluded from
      the build, and the one the planner finds.
  [W] pages.yml, parsed: the plan step runs in the build job after the site is built and checked and
      before the upload, continue-on-error, writing the job output; the ping step is the LAST step of the
      deploy job, after the deploy, only on success, continue-on-error, reading only that output, no secret.
  [X] the ping step's run: scalar, extracted and EXECUTED under the runner's bash flags with a fake curl:
      no payload sends nothing; a payload is POSTed once, verbatim, to api.indexnow.org; an HTTP refusal and
      a network failure are warnings and exit 0.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_indexnow_ping.py
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[3]
AUX = _REPO / "auxsays"
PLANNER = AUX / "scripts" / "ci" / "indexnow_plan.py"
PAGES_YML = _REPO / ".github" / "workflows" / "pages.yml"
CONFIG = AUX / "_config.yml"
ORIGIN = "https://auxsays.com/"
KEY = "0123456789abcdef0123456789abcdef"
ENDPOINT = "https://api.indexnow.org/indexnow"

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print("  PASS  " + label)
    else:
        _FAIL += 1
        print("  FAIL  " + label)
        if detail:
            print("        " + detail[:600])
        _ERRORS.append(label)


def sitemap(urls: dict[str, str | None]) -> str:
    body = "".join(f"<url><loc>{u}</loc>" + (f"<lastmod>{m}</lastmod>" if m else "") + "</url>"
                   for u, m in urls.items())
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>')


def run_planner(built: dict | None, live: str | None, *, keys: dict[str, str] | None = None,
                args: list[str] | None = None) -> tuple[int, str, dict | None, str]:
    """(rc, stdout, payload or None, raw output file) for one planner run in a fresh temp tree."""
    with tempfile.TemporaryDirectory() as td:
        site = Path(td) / "_site"
        site.mkdir()
        if built is not None:
            (site / "sitemap.xml").write_text(sitemap(built), encoding="utf-8")
        for name, text in ({f"{KEY}.txt": KEY} if keys is None else keys).items():
            (site / name).write_text(text + "\n", encoding="utf-8")
        live_file = Path(td) / "live.xml"
        if live is not None:
            live_file.write_text(live, encoding="utf-8")
        out = Path(td) / "gh_output"
        out.write_text("", encoding="utf-8")
        argv = args if args is not None else ["--site", str(site), "--live-file", str(live_file),
                                              "--github-output", str(out)]
        proc = subprocess.run([sys.executable, str(PLANNER), *argv], capture_output=True, text=True,
                              encoding="utf-8", timeout=120, cwd=td)
        raw = out.read_text(encoding="utf-8")
    m = re.search(r"^payload=(.*)$", raw, re.M)
    payload = json.loads(m.group(1)) if m and m.group(1) else None
    return proc.returncode, proc.stdout + proc.stderr, payload, raw


def u(path: str) -> str:
    return ORIGIN + path


# --------------------------------------------------------------------------- [P] the planner

def section_p() -> None:
    print("\n[P] the planner: changed pages only, capped, and nothing when in doubt")
    live = {u("a/"): "2026-11-20T00:00:00+00:00", u("b/"): "2026-11-21T00:00:00+00:00",
            u("c/"): None, u("gone/"): "2026-11-01T00:00:00+00:00"}
    built = {u("a/"): "2026-11-20T00:00:00+00:00",          # unchanged
             u("b/"): "2026-11-23T05:00:00+00:00",          # its record changed
             u("c/"): None,                                 # unchanged, undated
             u("new/"): "2026-11-22T00:00:00+00:00",        # new in this build
             u("newer/"): None,                             # new, undated
             "https://elsewhere.example/x/": "2026-11-23T00:00:00+00:00"}
    rc, log, payload, raw = run_planner(built, sitemap(live))
    check("P1 a URL is planned when it is new or its stored date moved, newest dated first, undated new last; "
          "never an unchanged URL or another host's",
          rc == 0 and payload is not None and payload["urlList"] == [u("b/"), u("new/"), u("newer/")],
          f"rc={rc} payload={payload} log={log[-300:]}")
    check("P2 the payload names the host, the key and the key file the engine checks, and the step output "
          "carries the count",
          payload is not None and payload.get("host") == "auxsays.com" and payload.get("key") == KEY
          and payload.get("keyLocation") == f"{ORIGIN}{KEY}.txt" and set(payload) == {"host", "key", "keyLocation", "urlList"}
          and "count=3" in raw, f"{payload} {raw!r}")

    many_live = {u(f"p{i}/"): "2026-01-01T00:00:00+00:00" for i in range(700)}
    many_built = {u(f"p{i}/"): f"2026-11-{1 + i % 28:02d}T{i % 24:02d}:{i % 60:02d}:00+00:00" for i in range(700)}
    rc, log, payload, raw = run_planner(many_built, sitemap(many_live))
    expected = [k for k, _ in sorted(many_built.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)][:500]
    check("P3 at most 500 URLs per deploy, the 500 newest, and the 200 over the cap are named in the log",
          rc == 0 and payload is not None and payload["urlList"] == expected and "count=500" in raw
          and "200 more over the 500 cap" in log, f"rc={rc} n={len(payload['urlList']) if payload else None} {log[-200:]}")

    same = {u("a/"): "2026-11-20T00:00:00+00:00", u("c/"): None}
    cases = {
        "nothing changed": run_planner(same, sitemap(same)),
        "live sitemap missing": run_planner(built, None),
        "live sitemap empty": run_planner(built, sitemap({})),
        "live sitemap malformed": run_planner(built, "<urlset><url><loc>"),
        "no key file": run_planner(built, sitemap(live), keys={}),
        "two key files": run_planner(built, sitemap(live), keys={f"{KEY}.txt": KEY, f"{'f' * 32}.txt": "f" * 32}),
        "key file content wrong": run_planner(built, sitemap(live), keys={f"{KEY}.txt": "not-the-key"}),
        "built sitemap missing": run_planner(None, sitemap(live)),
    }
    bad = {k: (v[0], v[2], v[3]) for k, v in cases.items() if v[0] != 0 or v[2] is not None or "count=0" not in v[3]}
    check(f"P4 nothing is planned, the step output is empty with count=0 and the exit is 0 when nothing changed "
          f"or anything is in doubt ({len(cases)} cases)", not bad, str(bad))
    warned = [k for k, v in cases.items() if k != "nothing changed" and "::warning::IndexNow" not in v[1]]
    check("P5 every refusal is a visible ::warning:: in the log; nothing changed is a plain line",
          not warned and "::warning::" not in cases["nothing changed"][1]
          and "no page changed" in cases["nothing changed"][1], str(warned))
    rc1, log1, _, _ = run_planner(built, sitemap(live), args=["--no-such-flag"])
    rc2, log2, _, _ = run_planner(built, sitemap(live), args=["--site", "/definitely/not/here", "--live-file", "/nope"])
    check("P6 a bad argument or a missing site still exits 0 with a warning (the deploy never waits on it)",
          rc1 == 0 and rc2 == 0 and "::warning::IndexNow" in log1 and "::warning::IndexNow" in log2,
          f"rc1={rc1} rc2={rc2} {log1[-200:]} {log2[-200:]}")


# --------------------------------------------------------------------------- [K] the key file

def section_k() -> None:
    print("\n[K] the shipped key file")
    keys = [p for p in AUX.glob("*.txt") if re.fullmatch(r"[0-9a-f]{32}\.txt", p.name)]
    ok = len(keys) == 1 and keys[0].read_text(encoding="utf-8").strip() == keys[0].stem
    check("K1 exactly one 32-hex <key>.txt at the site source root, holding its own name", ok, str(keys))
    if not ok:
        return
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    name = keys[0].name
    hit = [p for p in cfg.get("exclude") or [] if fnmatch.fnmatch(name, p) or name.startswith(p)]
    check("K2 no exclude pattern in _config.yml drops it from the built site (Jekyll's fnmatch + prefix rule)",
          not hit and not name.startswith(("_", ".", "#", "~")), str(hit))
    sys.path.insert(0, str(PLANNER.parent))
    try:
        import indexnow_plan  # noqa: PLC0415
        found = indexnow_plan.find_key(AUX)
        cap, host = indexnow_plan.MAX_URLS, indexnow_plan.HOST
    finally:
        sys.path.pop(0)
    check("K3 the planner finds that key in the site root, sends for auxsays.com only and caps at 500",
          found == keys[0].stem and cap == 500 and host == "auxsays.com", f"{found} {cap} {host}")


# --------------------------------------------------------------------------- [W] [X] the workflow

def workflow() -> dict:
    return yaml.safe_load(PAGES_YML.read_text(encoding="utf-8"))


def section_w() -> dict | None:
    print("\n[W] pages.yml, parsed")
    wf = workflow()
    build, deploy = wf["jobs"]["build"], wf["jobs"]["deploy"]
    steps = build["steps"]
    names = [s.get("name", "") for s in steps]
    plan_i = [i for i, s in enumerate(steps) if s.get("id") == "indexnow_plan"]
    plan = steps[plan_i[0]] if len(plan_i) == 1 else {}
    built_i = names.index("Build site") if "Build site" in names else -1
    upload_i = next((i for i, s in enumerate(steps) if str(s.get("uses", "")).startswith("actions/upload-pages-artifact")), -1)
    run = str(plan.get("run", ""))
    check("W1 the plan step runs once, in the build job, after the site is built and before it is uploaded, "
          "continue-on-error, on the built site, writing the step output",
          len(plan_i) == 1 and built_i >= 0 and built_i < plan_i[0] < upload_i and plan.get("continue-on-error") is True
          and run.split() == ["python", "auxsays/scripts/ci/indexnow_plan.py", "--site", "auxsays/_site",
                              "--github-output", '"$GITHUB_OUTPUT"'], f"{plan_i} {built_i} {upload_i} {run!r}")
    check("W2 the build job exports exactly that step's payload",
          (build.get("outputs") or {}).get("indexnow_payload") == "${{ steps.indexnow_plan.outputs.payload }}",
          str(build.get("outputs")))
    dsteps = deploy["steps"]
    deploy_i = next((i for i, s in enumerate(dsteps) if str(s.get("uses", "")).startswith("actions/deploy-pages")), -1)
    ping = dsteps[-1]
    text = json.dumps(ping)
    check("W3 the ping is the LAST step of the deploy job, after the deploy, only on success and on main, "
          "continue-on-error, reading only the planned payload and no secret",
          0 <= deploy_i < len(dsteps) - 1 and "success()" in str(ping.get("if", ""))
          and "refs/heads/main" in str(ping.get("if", "")) and ping.get("continue-on-error") is True
          and ping.get("env") == {"PAYLOAD": "${{ needs.build.outputs.indexnow_payload }}"}
          and "secrets." not in text and "${{" not in str(ping.get("run", "")) and deploy.get("needs") == "build",
          json.dumps(ping)[:400])
    return ping


FAKE_CURL = """#!/usr/bin/env bash
printf '%s\\n' "$@" > "$FAKE_LOG"
echo "called" >> "$FAKE_LOG.count"
printf '%s' "${FAKE_CODE}"
exit "${FAKE_RC:-0}"
"""


def run_step(script: str, payload: str, code: str = "202", curl_rc: int = 0) -> tuple[int, str, list[str], int]:
    """Execute the step's run: scalar as the runner does (bash -eo pipefail) with a fake curl on PATH."""
    bash = shutil.which("bash")
    with tempfile.TemporaryDirectory() as td:
        fake = Path(td) / "bin"
        fake.mkdir()
        curl = fake / "curl"
        curl.write_text(FAKE_CURL, encoding="utf-8", newline="\n")
        curl.chmod(0o755)
        step = Path(td) / "step.sh"
        step.write_text(script, encoding="utf-8", newline="\n")
        log = Path(td) / "curl.log"
        env = dict(os.environ, PATH=str(fake) + os.pathsep + os.environ.get("PATH", ""), PAYLOAD=payload,
                   FAKE_LOG=str(log), FAKE_CODE=code, FAKE_RC=str(curl_rc))
        proc = subprocess.run([bash, "--noprofile", "--norc", "-eo", "pipefail", str(step)], capture_output=True,
                              text=True, encoding="utf-8", env=env, timeout=60)
        args = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        calls = len(Path(str(log) + ".count").read_text(encoding="utf-8").splitlines()) if Path(str(log) + ".count").exists() else 0
    return proc.returncode, proc.stdout + proc.stderr, args, calls


def section_x(ping: dict | None) -> None:
    print("\n[X] the ping step, executed with a fake curl")
    script = str((ping or {}).get("run", ""))
    if not shutil.which("bash") or not script:
        check("X1 bash and the ping step's run: scalar are available", False, f"bash={shutil.which('bash')}")
        return
    payload = json.dumps({"host": "auxsays.com", "key": KEY, "keyLocation": f"{ORIGIN}{KEY}.txt",
                          "urlList": [u("a/"), u("b/")]}, separators=(",", ":"))
    rc, log, args, calls = run_step(script, "")
    check("X1 no planned payload: curl is never run, the log says nothing was sent, exit 0",
          rc == 0 and calls == 0 and "nothing sent" in log, f"rc={rc} calls={calls} {log}")
    rc, log, args, calls = run_step(script, payload, "202")
    data = args[args.index("--data") + 1] if "--data" in args else None
    check("X2 a payload is POSTed once, verbatim, as JSON, to api.indexnow.org; an accepted answer is logged",
          rc == 0 and calls == 1 and data == payload and args[-1] == ENDPOINT
          and "Content-Type: application/json; charset=utf-8" in args and "accepted" in log and "::warning::" not in log,
          f"rc={rc} calls={calls} args={args} {log}")
    rc, log, args, calls = run_step(script, payload, "429")
    check("X3 a refusal (HTTP 429) is a ::warning:: and exits 0", rc == 0 and calls == 1 and "::warning::" in log
          and "429" in log, f"rc={rc} {log}")
    rc, log, args, calls = run_step(script, payload, "000", curl_rc=7)
    check("X4 a network failure (curl exits non-zero) is a ::warning:: and exits 0 under -e and pipefail",
          rc == 0 and calls == 1 and "::warning::" in log and "no response" in log, f"rc={rc} {log}")


def run() -> int:
    section_p()
    section_k()
    ping = section_w()
    section_x(ping)
    print()
    print("=" * 96)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed checks:")
        for e in _ERRORS:
            print(f"  - {e}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2) from None
