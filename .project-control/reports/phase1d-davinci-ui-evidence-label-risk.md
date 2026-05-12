# Phase 1D — DaVinci UI and Evidence-Label Risk Review

**Phase:** 1D  
**Date:** 2026-05-12  
**Read-only:** Yes. Layouts and generated records not modified.

---

## 1. Scope

Inspected:
- `auxsays/_layouts/aux-update.html` (413 lines)
- `auxsays/_layouts/aux-home.html` (222 lines)
- `auxsays/updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md`
- `auxsays/updates/generated/2026-04-14-davinci-resolve-21.md`

---

## 2. aux-update.html — Rendering Logic for DaVinci Records

### 2.1 Evidence state derivation (lines 56–67)

The layout derives its displayed evidence state from `consensus_collection_status` and `evidence_state`, not just the field values:

```liquid
{% if collection_status == 'live_consensus' or collection_status == 'consensus_live' %}
  evidence_state = 'Live consensus'
{% elsif collection_status == 'pilot_initial_sample' or 'static_initial_sample'
      or page.evidence_state == 'pilot_sample' or 'static_sample' %}
  evidence_state = 'Verified reports'
{% elsif official_captured %}
  evidence_state = 'Official source only'
{% else %}
  evidence_state = 'Insufficient data'
{% endif %}
```

**DaVinci Beta 1 result:** `consensus_collection_status: deferred_official_only`, `evidence_state: official_only`, official source URL is present → `evidence_state = 'Official source only'`. ✅ Correct.

### 2.2 official_only_zero_reports override (lines 69–103)

```liquid
{% assign official_only_zero_reports = false %}
{% if evidence_state == 'Official source only' and report_count == 0 %}
  official_only_zero_reports = true
{% endif %}
...
{% if official_only_zero_reports %}
  decision_label = 'No AUXSAYS recommendation yet.'
  verdict_text = 'Official source captured. No confirmed patch-specific reports have been counted.'
  decision_body = verdict_text
{% endif %}
```

**DaVinci Beta 1 result:** `update_report_count: 0`, `evidence_state: official_only` → `official_only_zero_reports = true` → `decision_label` is overridden to `'No AUXSAYS recommendation yet.'`. 

**The `quick_verdict: WAIT for production systems` and `update_decision_label: WAIT for production systems` in the DaVinci Beta 1 record are both SUPPRESSED by the layout.** The public page shows "No AUXSAYS recommendation yet." instead of "WAIT." This is the correct behavior — the layout protects against advisory language rendering as evidence-backed verdict.

### 2.3 known_issues_label (lines 73–80)

```liquid
{% if page.known_issues_present == true %}
  known_issues_label = 'Yes'
{% elsif page.known_issues_present == false %}
  known_issues_label = 'No'
{% elsif page.complaint_themes and page.complaint_themes.size > 0 %}
  known_issues_label = 'Yes'
{% endif %}
```

**DaVinci Beta 1 result:** `known_issues_present: true` → `known_issues_label = 'Yes'`. This displays "Known issues: Yes" on the record page even though there are 0 confirmed reports.

**Risk:** A reader seeing "Known issues: Yes" alongside "Official source only" could infer that AUXSAYS has confirmed specific issues exist with this release, when in fact the `complaint_themes` are advisory/anticipatory content based on the beta context, not confirmed patch-specific reports.

### 2.4 practical_recommendations rendering (lines 114–117)

```liquid
{% assign has_practical_recommendations = false %}
{% if page.practical_recommendations and page.practical_recommendations.size > 0 %}
  has_practical_recommendations = true
{% endif %}
{% assign recommendation_renderable = false %}
{% if official_only_zero_reports or has_practical_recommendations %}
  recommendation_renderable = true
{% endif %}
```

**DaVinci Beta 1 result:** `practical_recommendations` is present AND `official_only_zero_reports` is true → `recommendation_renderable = true`. The practical recommendations section renders.

**Risk:** The practical recommendations include `"Wait for production systems unless you have a specific Resolve 21 beta feature to test."` — but the layout's verdict override says `"No AUXSAYS recommendation yet."` These two statements appear on the same page and directly contradict each other. The verdict is suppressed to "No AUXSAYS recommendation yet." but the recommendations block says "WAIT."

**This is the most significant current UI risk:** A reader sees "No AUXSAYS recommendation yet." in the verdict zone AND "Wait for production systems" in the recommendations section on the same page. The veteran AUXSAYS reader knows recommendations are advisory. A first-time reader may interpret the recommendations as the AUXSAYS recommendation, defeating the override.

### 2.5 consensus_report rendering (lines 118–120)

```liquid
{% assign consensus_report_renderable = false %}
{% if report_count > 0 and consensus_text != blank %}
  consensus_report_renderable = true
{% endif %}
```

**DaVinci Beta 1 result:** `update_report_count: 0` → `consensus_report_renderable = false`. The `consensus_report` field (which contains text about the 7-report legacy value) does NOT render. ✅ Correct — the legacy explanation text is suppressed by the zero count gate.

### 2.6 Summary of DaVinci Beta 1 record rendering

| UI element | Rendered value | Risk level |
|---|---|---|
| Verdict / decision_label | `No AUXSAYS recommendation yet.` (layout override) | ✅ Correct |
| Evidence state badge | `Official source only` | ✅ Correct |
| Report count | `0` | ✅ Correct |
| Known issues label | `Yes` | ⚠️ Potentially misleading |
| Practical recommendations | Renders (WAIT language) | ⚠️ Contradicts verdict override |
| consensus_report text | Not rendered (zero count gate) | ✅ Correct |
| complaint_themes | Likely renders (if layout displays them) | ⚠️ Advisory content implied as evidence |
| quick_verdict | Suppressed by official_only_zero_reports override | ✅ Correct |
| update_decision_label | Suppressed by override | ✅ Correct |
| legacy_manual_report_count | Not displayed by layout (field exists but not in layout template) | ✅ No risk |

---

## 3. aux-home.html — Homepage Patch Signals Inclusion

### 3.1 Homepage signal filter logic (lines 143–156)

```liquid
{% assign report_count = item.update_report_count | default: 0 | plus: 0 %}
{% assign known_issues_value = item.known_issues_present | default: false %}
{% assign evidence_state = item.evidence_state | default: 'insufficient_data' ... %}
{% assign is_known_issue = false %}
{% if known_issues_value == true or ... %}
  is_known_issue = true
{% endif %}
{% assign has_evidence_signal = false %}
{% if report_count > 0 or is_known_issue == true or evidence_state == 'pilot_sample' ... %}
  has_evidence_signal = true
{% endif %}
```

**DaVinci Beta 1 result:** `update_report_count: 0`, `known_issues_present: true` → `is_known_issue = true` → `has_evidence_signal = true`.

### 3.2 Homepage inclusion bucket logic (lines 158–169)

```liquid
{% if signal_bucket == 5 and has_evidence_signal == true %}
  show_signal = true
{% endif %}
```

**DaVinci Beta 1 result:** `has_evidence_signal = true`, `consensus_label = 'Insufficient data'` → item is not negative/moderate/positive → falls through to **bucket 5** → `show_signal = true`.

**ACTIVE RISK CONFIRMED:** The DaVinci Resolve 21 Public Beta 1 record IS currently included in the homepage Patch Signals section. It appears in bucket 5 with the label:

```
DaVinci Resolve 21 Public Beta 1
Insufficient data • known issues
[Official source only] [Manual watch]
Apr 14
```

A homepage visitor sees this record under "Patch Signals" alongside OBS and other records that have genuine counted evidence. The label `• known issues` next to `Insufficient data` implies that AUXSAYS has identified specific patch issues, when in fact `known_issues_present: true` reflects only advisory/anticipatory complaint themes about a beta build.

**This is the highest-severity UI risk identified in Phase 1D.**

### 3.3 DaVinci generic record (davinci-resolve-21.md)

`known_issues_present: null`, `update_report_count: 0`. `has_evidence_signal = false` → not included in homepage Patch Signals. ✅ Correct — the archived generic record is correctly excluded.

---

## 4. Risk Register

| Risk | Severity | Currently active? | Layout protection exists? |
|---|---|---|---|
| Homepage shows DaVinci Beta 1 as a "known issues" signal | **High** | **Yes** | No — `known_issues_present: true` triggers homepage inclusion |
| Practical recommendations say "WAIT" while verdict says "No recommendation yet" | **Medium** | **Yes** | Partial — verdict is overridden but recommendations still render |
| `known_issues_label: Yes` on record detail page with 0 reports | **Medium** | **Yes** | No layout suppression for this label |
| `complaint_themes` may render on record page implying counted evidence | **Low-Medium** | Unknown (depends on template section) | Unknown — template section not confirmed |
| `legacy_manual_report_count` visible to users | **Low** | Not confirmed — field not in layout template | Field exists in record, layout does not display it |
| Future layout change removes `official_only_zero_reports` override | **High** | Not currently active | Yes — but fragile single-point protection |
| Evidence state `official_only` is correctly shown | None | ✅ Working | Yes |
| Report count 0 is correctly shown | None | ✅ Working | Yes |

---

## 5. Is Current Live Display Honest Enough?

**Assessment: Partially.**

The report count (0), evidence state (Official source only), and verdict (No AUXSAYS recommendation yet) are all displayed correctly. The major override logic in the layout is working as intended.

The honesty problem is in the **homepage** and the **recommendation block**:

1. **Homepage:** The record appears under "Patch Signals" because of `known_issues_present: true`. A user navigating from the homepage sees a signal that implies actionable risk, arrives at the record, and finds "No AUXSAYS recommendation yet." The journey is confusing. The homepage signal label `• known issues` is misleading because it derives from advisory complaint themes, not confirmed reports.

2. **Practical recommendations WAIT language:** The recommendations block contradicts the verdict. The WAIT language is editorial and appropriate for a public beta, but it undercuts the layout's protective override.

Both risks are manageable — neither constitutes a false evidence claim — but they represent a UX integrity concern that should be addressed in Phase 1E.

---

## 6. Phase 1E Recommendations

### Rec 1 — QA model update for manual_watch + advisory content (HIGH PRIORITY)

Add a QA check in `qa_patch_records.py` that flags records with:
- `intelligence_stage: manual_watch` AND
- `known_issues_present: true` AND
- `confirmed_patch_specific_report_count: 0`

as requiring explicit acknowledgment that the `known_issues_present` flag reflects advisory content only. This can be a new warning code: `manual_watch_known_issues_no_evidence`.

### Rec 2 — Homepage filter should exclude pure manual_watch records (HIGH PRIORITY)

Update the homepage filter condition in `aux-home.html`:

**Current:**
```liquid
{% if report_count > 0 or is_known_issue == true or evidence_state == 'pilot_sample' ... %}
  has_evidence_signal = true
{% endif %}
```

**Proposed addition:**
```liquid
{% assign stage = item.intelligence_stage | default: '' | downcase %}
{% if report_count > 0 or (is_known_issue == true and stage != 'manual_watch') or ... %}
  has_evidence_signal = true
{% endif %}
```

This would exclude `manual_watch` records from homepage inclusion even if `known_issues_present: true`, because the known issues flag on a manual_watch record reflects advisory content, not confirmed evidence.

**This is a layout change — do not implement in Phase 1D. Requires explicit approval and testing.**

### Rec 3 — Add advisory_content_only guard to recommendation rendering (MEDIUM PRIORITY)

Consider adding a `advisory_content_only: true` front-matter field to records that carry `practical_recommendations` and `complaint_themes` as editorial advisory content (not evidence-backed). The layout could then render these under a clearly labelled "Editorial guidance" heading rather than in the recommendations section that normally reflects evidence-backed decisions.

### Rec 4 — Normalize legacy_manual_report_count (LOW PRIORITY)

The `legacy_manual_report_count: 7` field in the DaVinci Beta 1 record is an unrendered field (the layout does not display it). However, it is not part of the formal ingestion schema, is not validated by QA, and could cause confusion if future layout changes inadvertently expose it. Consider either:
1. Adding it to the QA schema as an explicitly documented historical-only field
2. Removing it from the generated record and noting the historical value only in `record_note`

### Rec 5 — QA cross-check: known_issues_present requires complaint_themes or evidence (LOW PRIORITY)

Add a QA rule: if `known_issues_present: true` AND `confirmed_patch_specific_report_count: 0` AND `complaint_themes` is empty, flag as `known_issues_flag_unsupported` — the flag claims issues are present but no themes or evidence back it up. For DaVinci Beta 1, this would not trigger because complaint_themes ARE present.

---

## 7. Do Not Modify in Phase 1D

- `auxsays/_layouts/aux-update.html` — not modified
- `auxsays/_layouts/aux-home.html` — not modified
- `auxsays/updates/generated/2026-04-14-davinci-resolve-21-public-beta-1.md` — not modified
- `auxsays/updates/generated/2026-04-14-davinci-resolve-21.md` — not modified

All changes described above are Phase 1E recommendations only.
