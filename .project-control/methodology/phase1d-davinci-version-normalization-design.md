# Phase 1D — DaVinci Version Normalization Design

**Phase:** 1D  
**Date:** 2026-05-12  
**Status:** Design only — no production changes in Phase 1D.

---

## 1. Context

The current ingestion config `version_pattern` for DaVinci is:
```
^(v)?(?P<version>[0-9]+(\.[0-9]+)+.*)$
```
This pattern requires the version string to begin with an optional `v` then digits. It fails all Blackmagic-format strings such as `DaVinci Resolve 21 Public Beta 1`.

The DaVinci Beta 1 generated record has `update_version: '21 Public Beta 1'`. This is the current canonical form in the generated record.

The DaVinci generic record has `update_version: '21'`.

---

## 2. Observed Version String Variants

### 2.1 Blackmagic official sources

| String | Where seen | Notes |
|---|---|---|
| `DaVinci Resolve 21 Public Beta 1` | Press release title | Full official form, includes product name and qualifier |
| `DaVinci Resolve Studio 21 Public Beta 1` | Studio variant name | Same release, paid tier label |
| `DaVinci Resolve 21` | Press release body | Major version only, no qualifier |
| `DaVinci Resolve 20.0.0` | Prior stable release | Three-part numeric |
| `DaVinci Resolve 19.1.1` | Prior stable | Three-part numeric with patch |
| `DaVinci Resolve 19.1` | Prior stable | Two-part numeric |

### 2.2 Community shorthand (Reddit, forum, YouTube)

| String | Meaning |
|---|---|
| `Resolve 21` | DaVinci Resolve 21 (any qualifier) |
| `DaVinci 21` | Same |
| `DR21` | Abbreviation for DaVinci Resolve 21 |
| `DR 21` | Same with space |
| `21 beta` | Beta build of version 21 |
| `21b1` | Beta 1 of version 21 |
| `21 Public Beta 1` | Slightly more formal community form |
| `Resolve 21 Beta` | Community shorthand for any beta |
| `v21` | Prefixed with v |
| `21.x` | Unspecified point release of 21 |

### 2.3 Current AUXSAYS canonical form

The existing generated record uses `update_version: '21 Public Beta 1'`. This strips the `DaVinci Resolve` product name prefix but retains the qualifier.

---

## 3. Canonical product_id

```
product_id: blackmagic-davinci
```

Both "DaVinci Resolve" (free) and "DaVinci Resolve Studio" (paid) releases map to this single `product_id`. The Studio label is a pricing tier, not a separate product. Version numbers are identical across both tiers.

---

## 4. Canonical update_version Forms

### 4.1 Beta releases

| Canonical form | Example | Rules |
|---|---|---|
| `21 Public Beta 1` | `DaVinci Resolve 21 Public Beta 1` → `21 Public Beta 1` | Strip product prefix; retain `Public Beta N` qualifier |
| `21 Public Beta 2` | `DaVinci Resolve 21 Public Beta 2` → `21 Public Beta 2` | Same |

### 4.2 Stable major releases

| Canonical form | Example | Rules |
|---|---|---|
| `21` | `DaVinci Resolve 21` → `21` | Strip product prefix; bare integer for major-only |
| `20.0.0` | `DaVinci Resolve 20.0.0` → `20.0.0` | Strip product prefix; retain full numeric form |
| `19.1.1` | `DaVinci Resolve 19.1.1` → `19.1.1` | Same |
| `19.1` | `DaVinci Resolve 19.1` → `19.1` | Same |

### 4.3 Current AUXSAYS records and their canonical versions

| Generated record | Current `update_version` | Canonical? |
|---|---|---|
| `2026-04-14-davinci-resolve-21-public-beta-1.md` | `21 Public Beta 1` | **Yes** — this is the target |
| `2026-04-14-davinci-resolve-21.md` | `21` | **Yes** — archived broad entry |

---

## 5. Aliases (Normalize → Canonical)

The normalization pre-processor maps these aliases to canonical forms:

### 5.1 Product prefix stripping

Apply in order (longest match first):
```
"DaVinci Resolve Studio " → strip
"DaVinci Resolve "        → strip
"DaVinci "                → strip
"Resolve "                → strip
```

After stripping, `DaVinci Resolve 21 Public Beta 1` → `21 Public Beta 1`.

### 5.2 Qualifier normalization

After prefix stripping, normalize qualifier variants:

| Input (after prefix strip) | Normalized output |
|---|---|
| `21 Public Beta 1` | `21 Public Beta 1` (no change) |
| `21 Public Beta 2` | `21 Public Beta 2` (no change) |
| `21 Beta 1` | `21 Public Beta 1` |
| `21 Beta1` | `21 Public Beta 1` |
| `21b1` | `21 Public Beta 1` |
| `21 beta` | **Reject** — ambiguous, no beta number |
| `21b` | **Reject** — ambiguous |
| `Resolve 21 Beta` | **Reject** after prefix strip → `21 Beta` → ambiguous |
| `21 Beta 2` | `21 Public Beta 2` |
| `21b2` | `21 Public Beta 2` |
| `v21` | `21` |
| `21.0` | `21.0` (retain numeric form as-is) |
| `21.0.0` | `21.0.0` |
| `21` | `21` |
| `21.x` | **Reject** — wildcard, not a specific release |
| `DR21` | **Reject** — no reliable mapping without beta/stable context |
| `DR 21` | **Reject** — same |

---

## 6. Exact-Match Rules

Version matching for evidence counting uses **exact string match** after normalization.

Rule: `evidence.update_version == record.update_version` after pre-processor is applied.

Evidence rows must carry the canonical form. Non-canonical forms must be rejected at evidence write time, not at aggregation time.

Example:
- Generated record: `update_version: '21 Public Beta 1'`
- Evidence row A: `update_version: '21 Public Beta 1'` → **match**
- Evidence row B: `update_version: 'DaVinci Resolve 21 Public Beta 1'` → pre-processor → `21 Public Beta 1` → **match after normalization**
- Evidence row C: `update_version: '21'` → **no match** (different version — Beta 1 vs. generic)
- Evidence row D: `update_version: '21 beta'` → **reject** (ambiguous)

---

## 7. Rejection Rules

Evidence rows with these `update_version` values must be excluded with `exclusion_reason: 'version_normalization_rejected'`:

| Input | Reason |
|---|---|
| `21 beta` | No beta number — cannot confirm which beta |
| `21b` | Same |
| `Resolve 21 Beta` | Same |
| `DR21` | No qualifier — cannot distinguish beta from stable |
| `21.x` | Wildcard — not a specific release |
| `DaVinci Resolve` (no version) | No version at all |
| Empty string | No version |
| `21 Studio` | Studio is not a version qualifier |

---

## 8. False-Positive Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Community post says "21 beta" without specifying Beta 1 vs Beta 2 | **High** | Reject ambiguous forms; require exact beta number |
| Post title says "DaVinci 21" but the issue is actually about version 20 | **Medium** | Require `patch_version_matched: true` set by human or exact-match algorithm |
| Evidence row counted for generic `21` matches against the specific `21 Public Beta 1` record | **High** | Exact-match only; `21` ≠ `21 Public Beta 1` |
| Future stable `21.0` release evidence counted against beta record | **High** | Exact-match only; `21.0` ≠ `21 Public Beta 1` |
| Studio and non-Studio rows double-count the same release | **Low** | Both map to same `product_id: blackmagic-davinci`; dedup on `source_url` to prevent same report counted twice |
| User reports general DaVinci bugs (not patch-specific) | **High** | `patch_version_matched: true` gate; `confirmed_patch_specific_reports_v1` policy |

---

## 9. Beta vs. Stable Separation

| Release type | `update_version` pattern | `intelligence_stage` (if evidence exists) | Notes |
|---|---|---|---|
| Public beta | `{N} Public Beta {M}` | `pilot` | Treat each beta number as a separate version |
| Stable major | `{N}` | `pilot` or `official_live` | e.g., `21` |
| Stable point | `{N}.{M}.{P}` | `pilot` or `official_live` | e.g., `20.0.0` |

Beta and stable releases MUST NOT share evidence rows. A report about `21 Public Beta 1` is NOT evidence for `21` (stable), and vice versa.

---

## 10. Studio vs. Non-Studio Wording Policy

**Policy:** DaVinci Resolve and DaVinci Resolve Studio are treated as the same AUXSAYS product (`product_id: blackmagic-davinci`) with the same version. They release simultaneously and have identical version numbers.

**In evidence rows:** Strip the Studio qualifier during pre-processing. Do not create a separate `product_id` for the Studio tier.

**In generated records:** The `update_product` field should use `DaVinci Resolve` (the base name). The record_note or official_summary may note that the record covers both DaVinci Resolve and DaVinci Resolve Studio.

**Risk:** If in a future release Blackmagic diverges Studio and non-Studio version numbers, this policy must be revisited.

---

## 11. Suggested Test Cases

```python
# Prefix stripping
assert normalize("DaVinci Resolve 21 Public Beta 1") == "21 Public Beta 1"
assert normalize("DaVinci Resolve Studio 21 Public Beta 1") == "21 Public Beta 1"
assert normalize("DaVinci Resolve 21") == "21"
assert normalize("Resolve 21") == "21"
assert normalize("DaVinci 21") == "21"
assert normalize("DaVinci Resolve 20.0.0") == "20.0.0"

# Qualifier normalization
assert normalize("21 Beta 1") == "21 Public Beta 1"
assert normalize("21b1") == "21 Public Beta 1"
assert normalize("v21") == "21"
assert normalize("21.0.0") == "21.0.0"

# Rejections
assert reject("21 beta") == True   # no beta number
assert reject("21b") == True       # no beta number
assert reject("21.x") == True      # wildcard
assert reject("DR21") == True      # abbreviation, ambiguous
assert reject("") == True          # empty

# Exact match after normalization
assert canonical("21 Public Beta 1") == "21 Public Beta 1"
assert canonical("DaVinci Resolve 21 Public Beta 1") == "21 Public Beta 1"
assert "21 Public Beta 1" != "21"   # beta ≠ stable major
assert "21 Public Beta 1" != "21 Public Beta 2"  # beta 1 ≠ beta 2
assert "21" != "21.0.0"             # major ≠ full numeric (treat as distinct until policy set)
```

---

## 12. Phase 1D Scope Note

This design document must not be implemented in Phase 1D. In Phase 1D:
- Production `version_pattern` in `patch_ingestion_sources.yml` is NOT modified.
- Production scripts are NOT modified.
- This document is design reference only for Phase 1E implementation.

The normalization logic should be implemented as a utility function in `auxsays/scripts/lib/` (e.g., `normalize_davinci_version.py`) so it can be imported by both the evidence collector and the write-back script without duplication.
