#!/usr/bin/env python3
"""Static tests for the patch-alert email-capture framework.

Locks the safety properties: the signup form is config-gated and renders NOTHING until both
site.newsletter.enabled is true AND an action_url is set; it ships default-off; it holds no API
key/secret; it is a plain no-JS POST form; and it is placed on the Patch Feed and every patch
record page. No network, no writes.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_newsletter_signup.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"

INCLUDE = (_AUX / "_includes" / "newsletter-signup.html").read_text(encoding="utf-8")
CONFIG = (_AUX / "_config.yml").read_text(encoding="utf-8")
FEED = (_AUX / "_layouts" / "aux-updates.html").read_text(encoding="utf-8")
RECORD = (_AUX / "_layouts" / "aux-update.html").read_text(encoding="utf-8")

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERRORS.append(label)


def run() -> int:
    print("=" * 60)
    print("Newsletter signup framework tests")
    print("=" * 60)

    # --- gating: renders nothing unless enabled AND action_url set --------------
    check("form is gated on site.newsletter.enabled AND a non-blank action_url",
          "nl.enabled and nl.action_url != blank" in INCLUDE)
    check("no form markup is emitted outside that gate (form is inside the {% if %})",
          INCLUDE.index("{% if nl.enabled") < INCLUDE.index("<form")
          and INCLUDE.index("<form") < INCLUDE.rindex("{% endif %}"))

    # --- ships default-off / inert ---------------------------------------------
    check("_config ships newsletter.enabled: false (nothing live by default)",
          "newsletter:" in CONFIG and "enabled: false" in CONFIG.split("newsletter:", 1)[1])
    check("_config ships an empty action_url (no endpoint wired yet)",
          'action_url: ""' in CONFIG)

    # --- no secret / API key VALUE embedded (prose mentioning "secret" is fine) --
    import re
    combined = INCLUDE + "\n" + CONFIG
    cred = re.search(r"(?i)(authorization\s*:|bearer\s+\S|api[_-]?key\s*[:=]\s*\S|secret\s*[:=]\s*\S|token\s*[:=]\s*\S)", combined)
    check("no API key / token / secret VALUE is embedded in the include or config",
          cred is None, f"matched: {cred.group(0) if cred else ''}")

    # --- no-JS friendly POST form with an email field + accessible label -------
    check("plain POST form (works without JavaScript)",
          'method="post"' in INCLUDE and 'action="{{ nl.action_url }}"' in INCLUDE)
    check("collects an email field with an associated label (accessible)",
          'name="email"' in INCLUDE and 'type="email"' in INCLUDE
          and 'class="aux-newsletter-label"' in INCLUDE and 'for="aux-nl-email' in INCLUDE)
    check("section is labelled for assistive tech",
          'aria-labelledby="aux-nl-heading"' in INCLUDE)

    # --- placement: Patch Feed + every patch record page -----------------------
    check("included on the Global Patch Feed layout", "newsletter-signup.html" in FEED)
    check("included on every patch record page (aux-update layout)", "newsletter-signup.html" in RECORD)

    # --- honest copy: no overclaim of 'safe' -----------------------------------
    check("default copy does not promise 'safe' (says clear/wait/avoid verdict)",
          "safe" not in (INCLUDE.lower()) and "verdict" in INCLUDE.lower())

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed tests:")
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
