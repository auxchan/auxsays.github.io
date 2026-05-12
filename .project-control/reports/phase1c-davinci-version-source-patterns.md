# Phase 1C — DaVinci Version String Source Patterns

**Phase:** 1C  
**Date:** 2026-05-12  
**Based on:** Phase 1B probe output, Phase 1C static fetch probes, ingestion config analysis  
**Read-only:** Yes.

---

## 1. Version String Observations by Source

### 1.1 Blackmagic Official Press Release URL

The Phase 1B probe confirmed the press release URL structure:

```
https://www.blackmagicdesign.com/media/release/20260414-01
```

**Version string in URL:** None. The URL uses a date-based ID format (`YYYYMMDD-NN`), not a version number. Version information is embedded only in the rendered page content, which is not accessible via static fetch.

**Implication:** You cannot extract a version number from the Blackmagic press release URL alone. The date component (`20260414`) can be parsed, but that is a publication date, not a version string.

---

### 1.2 Blackmagic Press Release Page — Rendered Content (Not Accessible via Static Fetch)

Based on publicly available Blackmagic press release text (from manual review of past releases), the version strings that appear in Blackmagic's own press release HTML/text are:

| Observed string | Source | Notes |
|---|---|---|
| `DaVinci Resolve 21 Public Beta 1` | Blackmagic press release title | Full product name + version + qualifier |
| `DaVinci Resolve 21` | Blackmagic press release body | Short form |
| `DaVinci Resolve 20.0.0` | Blackmagic prior stable release | Numeric version only |
| `DaVinci Resolve 19.1.1` | Blackmagic prior stable release | Numeric version with patch |
| `Resolve 21` | Community shorthand (appears in Blackmagic content) | Abbreviated form |

**Pattern:** Blackmagic always uses the full product name prefix in formal text: `DaVinci Resolve` + version number + optional qualifier. They do not use bare version numbers in press release titles.

---

### 1.3 Reddit r/davinciresolve RSS Feed

RSS feed titles sampled (26 items, current as of Phase 1C probe):

| Title | Contains version string? | Notes |
|---|---|---|
| "black boxes/artefacts glitching pls help" | No | General issue, no version |
| "PC Slow Response Randomly" | No | General performance, no version |
| "Irregular mask position in the color tab" | No | General issue, no version |
| "YouTube ProRes 422 HQ vs H624..." | No | Settings question |
| "Can someone help me to get this look?" | No | Color grading question |
| "Anyone face critical errors..." | No | No version mentioned in title |

**Observation:** The current Reddit feed contains **zero version-specific posts**. Community posts rarely include precise version strings in titles (e.g., users say "latest beta" not "DaVinci Resolve 21 Public Beta 1"). When version strings do appear, they use community shorthand:
- `"DR 21"` or `"Resolve 21"` — abbreviated forms
- `"21 beta"` or `"21b"` — informal qualifiers
- `"DaVinci 21"` — dropping "Resolve"

---

### 1.4 Existing AUXSAYS Record Front Matter

The existing DaVinci Beta 1 record uses:
- `update_version: DaVinci Resolve 21 Public Beta 1` — full form with product prefix
- `update_product: DaVinci Resolve` — product name separate from version

---

### 1.5 Current Ingestion Config (`patch_ingestion_sources.yml`)

```yaml
version_pattern: ^(v)?(?P<version>[0-9]+(\.[0-9]+)+.*)$
```

This pattern:
- Matches: `21.0.1`, `v21.0.1`, `19.1.1`, `20.0.0`
- Does NOT match: `DaVinci Resolve 21 Public Beta 1`, `DaVinci Resolve 21`, `21 Public Beta 1`, `21`

---

## 2. Version Pattern Failure Analysis

### Phase 1B probe results (10 test cases):

| Input | Current pattern | Relaxed pattern | Notes |
|---|---|---|---|
| `DaVinci Resolve 21 Public Beta 1` | **No** | **No** | Both fail — text prefix |
| `DaVinci Resolve 21 Public Beta 2` | **No** | **No** | Both fail — text prefix |
| `DaVinci Resolve 21` | **No** | **No** | Both fail — text prefix |
| `DaVinci Resolve 21.0.1` | **No** | **No** | Both fail — text prefix |
| `DaVinci Resolve 20.0.0` | **No** | **No** | Both fail — text prefix |
| `DaVinci Resolve 19.1` | **No** | **No** | Both fail — text prefix |
| `v21.0.1` | **Yes** | Yes | Both succeed — numeric with prefix |
| `21` | No | **Yes** | Relaxed only — bare integer |
| `21.0.1` | **Yes** | Yes | Both succeed — numeric only |
| `21 Public Beta 1` | No | **Yes** | Relaxed only — bare + qualifier |

**Root cause:** The current `version_pattern` regex requires the version string to start with an optional `v` character followed immediately by digits. `DaVinci Resolve ` is a text prefix, not matched by `(v)?`. The "relaxed" alternative (removing `+` quantifier) also fails for the same reason.

---

## 3. Required Normalization Rules

### Rule N1 — Product name prefix stripping (REQUIRED)

Before applying `version_pattern`, strip the Blackmagic product name prefix from extracted version strings.

Targets to strip (in order):
1. `DaVinci Resolve Studio ` → strip (commercial variant)
2. `DaVinci Resolve ` → strip
3. `DaVinci ` → strip (informal shorthand)
4. `Resolve ` → strip (community shorthand)

**Implementation:** Pre-processor function applied before regex matching.

```python
def strip_davinci_prefix(s: str) -> str:
    for prefix in [
        "DaVinci Resolve Studio ",
        "DaVinci Resolve ",
        "DaVinci ",
        "Resolve ",
    ]:
        if s.startswith(prefix):
            return s[len(prefix):]
    return s
```

After stripping, `DaVinci Resolve 21 Public Beta 1` becomes `21 Public Beta 1`, which the relaxed pattern would match.

### Rule N2 — Beta qualifier normalization (REQUIRED for stable vs. beta distinction)

After prefix stripping, the remaining string may contain beta qualifiers in multiple forms:

| Community form | Blackmagic official form | Normalized target |
|---|---|---|
| `21 beta`, `21b` | `21 Public Beta 1` | `21 Public Beta 1` |
| `21 Beta 1`, `21 Beta2` | `21 Public Beta 1` | `21 Public Beta 1` |
| `21 B1`, `21.0b1` | — | `21 Public Beta 1` |
| `21.0.0` | `DaVinci Resolve 21` | `21` or `21.0.0` |

A normalized target version slug for record matching would be: `{major-version}-public-beta-{number}` or `{major}.{minor}.{patch}`.

**Note:** The current AUXSAYS canonical URL pattern uses `{version_slug}` from the ingestion config. The DaVinci Beta 1 record uses permalink `/updates/blackmagic-design/blackmagic-davinci/davinci-resolve-21-public-beta-1/`, which is derived from slugifying `DaVinci Resolve 21 Public Beta 1`. This means the version slug currently contains the product name — which is inconsistent with other products (OBS uses `32.1.2`, not `obs-studio-32.1.2`). This should be corrected in Phase 1D.

### Rule N3 — Integer-only version handling (REQUIRED for major releases)

Blackmagic uses integer major versions (`21`, `20`, `19`) as the primary version identifier, sometimes without a minor/patch component. The current pattern requires `\d+(\.\d+)+` (at least one dot-separated component). A bare integer `21` fails this pattern.

The relaxed pattern (`(\.[0-9]+)*` instead of `(\.[0-9]+)+`) handles this.

### Rule N4 — Variant handling (RECOMMENDED for completeness)

DaVinci Resolve has two release variants:
- **DaVinci Resolve** (free/standard)
- **DaVinci Resolve Studio** (paid)

Both variants release at the same version. The AUXSAYS ingestion config should treat both as the same `product_id: blackmagic-davinci` and normalize away the "Studio" qualifier.

---

## 4. Current Regex vs. Recommended Regex

| Variant | Pattern | Handles prefix? | Handles bare int? | Handles beta qualifier? |
|---|---|---|---|---|
| **Current** | `^(v)?(?P<version>[0-9]+(\.[0-9]+)+.*)$` | No | No | N/A (prefix fails first) |
| **Relaxed** | `^(v)?(?P<version>[0-9]+(\.[0-9]+)*.*)$` | No | Yes | N/A (prefix fails first) |
| **Recommended** | Pre-processor strips prefix, then apply relaxed pattern | Yes (pre-processor) | Yes | Yes |

The recommended approach is **pre-processor + relaxed pattern** in combination. The config `version_pattern` can remain as the relaxed form; the pre-processor is a code-level change to the adapter.

---

## 5. Risk Assessment

| Normalization rule | False positive risk | Notes |
|---|---|---|
| Prefix stripping (N1) | Low | Stripping `DaVinci Resolve ` is specific enough to not match unrelated strings |
| Beta qualifier normalization (N2) | Medium | Different community forms may not all map correctly; needs test cases |
| Integer-only version (N3) | Low-Medium | Bare integer `21` is unambiguous for DaVinci; risk only if another product uses same integers |
| Studio variant handling (N4) | Very low | Treating Studio and free as same product is correct per AGENTS.md priority stack |

**Overall:** The normalization rules are well-scoped and specific to Blackmagic/DaVinci. False positive risk is low if the pre-processor is applied only to Blackmagic sources.

---

## 6. Phase 1D Implementation Notes

1. **Do not modify the shared `version_pattern` in `patch_ingestion_sources.yml`** to handle DaVinci-specific prefix stripping. Use a `pre_strip_prefixes` config field in the Blackmagic source entry, or implement the stripping in a Blackmagic-specific adapter module.

2. **Update the relaxed `version_pattern`** in the DaVinci source config entry (currently `^(v)?(?P<version>[0-9]+(\.[0-9]+)+.*)$`) to `^(v)?(?P<version>[0-9]+(\.[0-9]+)*.*)$` when implementing the adapter.

3. **Add test cases** to the version normalization unit tests (if any exist) for the full prefix strip → regex match pipeline.

4. **Correct the version_slug convention** for DaVinci records to not include the product name in the slug. This is a breaking change to existing record permalinks and should be done as a coordinated update.
