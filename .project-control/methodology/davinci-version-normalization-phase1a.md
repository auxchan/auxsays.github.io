# DaVinci Resolve — Version Normalization

**Status:** Research document — Phase 1A  
**Date:** 2026-05-11  
**Scope:** Version string normalization rules for DaVinci Resolve ingestion. Research only — no production changes, no config edits applied.

---

## 1. Problem Statement

DaVinci Resolve does not use semver. Its release titles are natural-language strings extracted from press release pages or forum posts. The current `version_pattern` regex in `patch_ingestion_sources.yml` was written for OBS Studio (which always has at least two numeric components) and silently rejects several valid DaVinci version formats.

---

## 2. Version Sample Inventory

| `raw_version` (as it appears in source) | `normalized_version` | `display_version` | `matching_aliases` | Notes |
|---|---|---|---|---|
| `DaVinci Resolve 21 Public Beta 1` | `21.0.0-beta.1` | `21 Public Beta 1` | `21`, `21.0`, `21.0.0`, `21b1` | Channel: beta, seq: 1 |
| `DaVinci Resolve 21 Public Beta 2` | `21.0.0-beta.2` | `21 Public Beta 2` | `21`, `21.0`, `21.0.0`, `21b2` | Channel: beta, seq: 2 |
| `DaVinci Resolve 21` | `21.0.0` | `21` | `21`, `21.0`, `21.0.0` | Stable, major-only |
| `21.0` | `21.0.0` | `21.0` | `21`, `21.0`, `21.0.0` | Stable, two-component |
| `21.1` | `21.1.0` | `21.1` | `21.1`, `21.1.0` | Minor release |
| `20.2.3` | `20.2.3` | `20.2.3` | `20.2.3` | Full three-component |
| `19.1.4` | `19.1.4` | `19.1.4` | `19.1.4` | Full three-component |

### Field definitions

- **`raw_version`** — the string extracted verbatim from the source (page title, press release headline, or forum post title). Never modified.
- **`normalized_version`** — machine-comparable version string. Always three numeric components (`MAJOR.MINOR.PATCH`) plus an optional pre-release suffix (`-beta.N`). Used for deduplication, sorting, and `update_version` front matter field (or stored alongside it).
- **`display_version`** — the string shown to users on the rendered page. Matches how Blackmagic labels the release. Stored in `update_detail_title` or the title field; not necessarily the same as `normalized_version`.
- **`matching_aliases`** — additional version strings that community reports may use when referring to this release. Used by evidence collection scripts when matching `update_version` against issue body text.

---

## 3. Current `version_pattern` and Its Failures

Config entry (`auxsays/_data/patch_ingestion_sources.yml`, DaVinci section):

```yaml
version_pattern: ^(v)?(?P<version>[0-9]+(\.[0-9]+)+.*)$
```

The `(\.[0-9]+)+` group requires **one or more** `.N` components after the major version. This means:

| Input | Matches current pattern? | Reason |
|---|---|---|
| `21` | **No** | No `.N` component present |
| `21.0` | Yes | One `.N` component |
| `21.0.0` | Yes | Two `.N` components |
| `21 Public Beta 1` | **No** | Space after `21`; no `.N` before space |
| `DaVinci Resolve 21 Public Beta 1` | **No** | Prefix text before digits |
| `21.0.0-beta.1` | Yes | Treated as `21.0.0-beta` + `.1` |
| `20.2.3` | Yes | Three `.N` components |

The two failure cases that will be hit most often in practice: `21` (major-only stable release) and `21 Public Beta 1` (beta with natural-language suffix).

---

## 4. Recommended Regex

### 4.1 Pattern for `version_pattern` in config (DaVinci entry only)

```
^(v)?(?P<version>[0-9]+(\.[0-9]+)*.*)$
```

Change: `+` → `*` on the inner `(\.[0-9]+)` group. This allows zero additional components, making `21` a valid match. The `.*` tail continues to capture `Public Beta 1` and similar suffixes.

**This change must not be applied to the OBS entry.** OBS versions always have at least two numeric components; keeping `+` there prevents false matches.

### 4.2 Post-capture normalization function (pseudocode)

```python
import re

VERSION_PREFIX_RE = re.compile(
    r"(?:DaVinci\s+Resolve\s+)?(?P<numeric>[0-9]+(?:\.[0-9]+)*)(?:\s+Public\s+Beta\s+(?P<beta>[0-9]+))?",
    re.I
)

def normalize_davinci_version(raw: str) -> dict:
    m = VERSION_PREFIX_RE.search(raw)
    if not m:
        return {"raw_version": raw, "normalized_version": None, "display_version": raw}

    numeric = m.group("numeric")           # e.g. "21" or "21.0" or "20.2.3"
    beta_seq = m.group("beta")             # e.g. "1" or None

    # Pad to three components
    parts = numeric.split(".")
    while len(parts) < 3:
        parts.append("0")
    base = ".".join(parts[:3])             # "21.0.0"

    if beta_seq:
        normalized = f"{base}-beta.{beta_seq}"
        display = f"{numeric} Public Beta {beta_seq}"
        slug = f"{numeric.replace('.', '-')}-public-beta-{beta_seq}"
    else:
        normalized = base
        display = numeric
        slug = numeric.replace(".", "-")

    return {
        "raw_version": raw,
        "normalized_version": normalized,   # machine sort / dedup key
        "display_version": display,         # rendered on page
        "url_slug": slug,                   # permalink component
        "is_prerelease": bool(beta_seq),
    }
```

---

## 5. False-Positive Risks and Mitigations

### 5.1 Matching `21` inside unrelated text

The numeric string `21` is common in dates, issue numbers, and version references to unrelated software. In evidence collection, matching `update_version: "21"` against issue body text will produce false positives.

**Mitigations:**

1. **Context window matching** — require the version number to appear adjacent to the product name. Acceptable patterns in body text:
   - `DaVinci Resolve 21`
   - `DaVinci 21`
   - `Resolve 21`
   - `DR21` (community shorthand)
   - `version 21` (only inside a DaVinci-related thread)

2. **Never match bare `21`** — a bare occurrence of `21` in an issue body is not sufficient to count the report. Require at least one adjacent product keyword within 50 characters.

3. **Thread-level filtering** — for forum-based evidence, the thread must be in a DaVinci-specific subforum or have DaVinci in its title. This eliminates the need for strict body matching on the version number alone.

4. **`match_basis` field** — the evidence row schema has a `match_basis` field (`title`, `body`, `both`). Rows matched only on `body` with a bare version number should be flagged for manual review rather than auto-counted.

### 5.2 Beta versions being counted against stable records

A community report about `21 Public Beta 1` should not be counted against `21` (stable). The matching logic must compare `normalized_version` strings, not raw strings. `21.0.0-beta.1 ≠ 21.0.0`.

### 5.3 Two-component versions (`21.0`) aliasing to three-component (`21.0.0`)

Some users write `21.0`; others write `21.0.0`. Both refer to the same release. The `matching_aliases` list for each record should include all plausible user-written forms, and the evidence collector should normalize its extracted version before comparing.

### 5.4 Version appearing in changelog of a different product

A DaVinci issue thread might reference another tool's `v21` tag. Thread-level filtering (see 5.1 point 3) is the primary defence; body-level product-name proximity is the secondary check.

---

## 6. Slug Construction Rules

The permalink slug must be stable once written. Derivation rules:

```
Stable "21"           → slug: "21"
Stable "21.0"         → slug: "21-0"  (dots → hyphens)
Stable "21.1"         → slug: "21-1"
Stable "20.2.3"       → slug: "20-2-3"
Beta "21 Public Beta 1" → slug: "21-public-beta-1"
Beta "21 Public Beta 2" → slug: "21-public-beta-2"
```

File name pattern: `{YYYY-MM-DD}-davinci-resolve-{slug}.md`

Example: `2026-04-14-davinci-resolve-21-public-beta-1.md` (matches the existing live record).

---

## 7. Relationship to Other Phase 1A Documents

| Document | Relationship |
|---|---|
| `obs-to-davinci-field-mapping.md` | Section 4 of that document is the source of the normalization content summarized here. This document expands it. |
| `davinci-pipeline-current-state.md` | Explains why `version_pattern` has never been exercised against a live DaVinci fetch. |
| `davinci-official-source-feasibility.md` | Explains where the `raw_version` string would come from (page title / URL prefix). |
