# AUXSAYS Agent Instructions

## Project identity

AUXSAYS.com is an independent patch-intelligence site for creators, streamers, PC gamers, technical workers, and workplace users.

The core user question is:

> Should I install this update, wait, or avoid it?

AUXSAYS is **not** a generic changelog site. It is a decision-intelligence site focused on workflow risk, official changes, known issues, vetted evidence, and practical update guidance.

The site should help users avoid bad patches, broken workflows, unstable releases, and time-wasting updates.

## Operating principles

1. **Credibility before expansion.**
2. **Evidence-backed patch pages before broad coverage.**
3. **No fake consensus.**
4. **No AI slop.**
5. **Do not hide incomplete systems.** Preserve forward progress and label incomplete states honestly.
6. **Be surgical.** Prefer small, reviewable patches over broad rewrites.
7. **Do not silently edit generated or state files.**
8. **Do not remove features just because they are incomplete.** Fix the machinery or label the limitation.
9. **Do not make the site look more mature than the intelligence layer actually is.**
10. **Run relevant validation before reporting success.**

## Development posture

When working in this repo:

- Inspect the existing implementation before making changes.
- Reuse existing data structures, layouts, scripts, and naming conventions when feasible.
- Avoid broad refactors unless explicitly requested.
- Prefer additive, reversible changes.
- Do not overwrite the whole repo.
- Do not invent new architecture if a small extension of the current architecture will work.
- Do not downgrade credibility protections to make a task easier.
- If instructions conflict, stop and report the conflict before making broad changes.

## Current priority product stack

Focus depth before expansion.

Priority products:

1. OBS Studio
2. DaVinci Resolve
3. Adobe Premiere Pro
4. Adobe Acrobat / Acrobat Reader
5. Windows 11
6. Elgato ecosystem
7. Adobe Photoshop
8. ChatGPT
9. Microsoft PowerPoint
10. Microsoft Teams
11. Microsoft 365 Apps
12. DJI Mimo

Do not expand beyond this priority stack unless explicitly instructed.

### Elgato ecosystem treatment

Elgato should be treated as an ecosystem, not a single generic product.

Relevant product/workflow areas include:

- Stream Deck
- Wave Link
- Camera Hub
- 4K Capture Utility
- capture cards
- firmware/software mismatch risk
- OBS integration
- audio routing
- plugin/profile issues
- Marketplace/plugin compatibility

## Verdict labels

Use these decision labels where applicable:

- `AVOID`
- `WAIT`
- `SAFE ENOUGH`
- `OFFICIAL ONLY`
- `INSUFFICIENT DATA`
- `SECURITY UPDATE, TEST FIRST`
- `MANUAL WATCH`

Do not overstate certainty.

For security-sensitive updates, do not casually tell users to avoid them. Prefer wording like:

> Security-sensitive update. Test first if your workflow is fragile, but do not ignore security exposure.

## Evidence states

Allowed internal evidence states:

- `official_only`
- `pilot_sample`
- `consensus_live`
- `insufficient_data`

Public-facing labels must use:

- `official_only` → **Official source only**
- `pilot_sample` → **Verified reports**
- `consensus_live` → **Live consensus**
- `insufficient_data` → **Insufficient data**

Legacy internal handling for `static_sample` may remain only for backward compatibility, but it should not appear as public user-facing language.

## Consensus policy

AUXSAYS consensus must be evidence-backed.

Do not mark anything `consensus_live` unless structured evidence exists.

### Confirmed report rule

Count only patch-specific reports.

A report counts if:

- the exact version/patch is named in the report itself, or
- the parent discussion/thread title names the exact version/patch.

Replies inside a patch-specific parent thread count unless the reply clearly shifts to another version or unrelated issue.

### Do not count

Do not count:

- generic complaints
- vague instability reports with no version/patch match
- unrelated app complaints
- reports where the version cannot be tied to the page
- low-context comments that do not clearly identify the patch/update being discussed

### Equal weighting

Every confirmed report counts equally.

Do not weight Reddit, official forums, company forums, or community forums differently.

Source type may be labeled for auditability only. It should not multiply or discount the report.

## Patch-page quality standard

Patch pages are the core product.

A strong patch page should answer quickly:

1. What is the update?
2. Should the user install, wait, avoid, or treat it as official-only?
3. What changed officially?
4. What broke or may be risky?
5. How many reports were counted?
6. What is the evidence state?
7. What is the confidence?
8. What practical action should the user take?

### Preferred patch-page priority

Patch pages should prioritize:

1. Verdict
2. Confidence
3. Evidence state
4. Reports counted
5. Known issues
6. Official source captured
7. Risk areas
8. Official additions/fixes
9. Evidence details
10. Practical recommendation

### Do not render blank credibility fields

Never render a blank field such as:

```text
File size:
```

with no value.

Use explicit states such as:

```text
File size: Not provided by source
```

or:

```text
File size: Creative Cloud-managed / not provided by source
```

Do not render empty checksum sections.

Only show checksum data if actual checksum data exists. If checksum absence needs to be mentioned, use explicit wording such as:

```text
Checksum: Not provided by source
```

## Homepage Patch Signals rules

Homepage Patch Signals should show meaningful updates only.

Show a patch on the homepage only if at least one is true:

- `homepage_featured: true`
- report count > 0
- known issues are present
- evidence state is `pilot_sample` or `consensus_live`
- intelligence stage is `pilot` or `consensus_live`

Hide from homepage:

- official-only records with 0 reports
- insufficient-data records with 0 reports
- staged placeholders
- low-quality auto-ingested marketing posts

Do not hide records from the full Patch Feed unless explicitly instructed.

The homepage is a signal surface. The full Patch Feed is the broader inventory.

## Official-source ingestion rules

Official ingestion must be conservative.

Do not create records from generic marketing posts unless clearly tied to an update, version, release, patch, or known-issues entry.

Do not call a “What’s New” page complete release notes unless it actually functions as release notes.

Do not invent version numbers.

Do not infer stability from official notes alone.

Source classification should distinguish:

- release notes
- fixed issues
- known issues
- security advisory
- community official post
- download portal
- release health
- manual watch

If official source data is unavailable, use explicit status fields rather than blank values.

## Product-specific risk models

Not all products have the same patch-risk profile.

### OBS Studio

Relevant risk areas:

- streaming stability
- recording stability
- encoders
- plugins
- scene/source behavior
- capture devices
- audio routing

### DaVinci Resolve / Premiere Pro

Relevant risk areas:

- project opening
- timeline/editing stability
- GPU acceleration
- codecs
- exports
- plugins
- media relinking
- beta-vs-stable risk

### Adobe Acrobat / Reader

Relevant risk areas:

- PDF opening/rendering
- fillable forms
- signatures/e-sign
- printing
- browser plugin behavior
- enterprise deployment
- security urgency
- old PDF/form compatibility

### Windows 11

Relevant risk areas:

- security urgency
- known issue/safeguard hold
- gaming performance
- creator-app compatibility
- capture-card/audio routing
- GPU/driver interaction
- enterprise deployment
- staged rollout/channel behavior

### Elgato

Relevant risk areas:

- Stream Deck profiles/plugins
- OBS actions
- Wave Link routing
- Camera Hub/Facecam behavior
- 4K Capture Utility/capture devices
- firmware mismatch
- Marketplace/plugin compatibility

### ChatGPT

Relevant risk areas:

- model behavior
- tool availability
- memory behavior
- plan-gated changes
- region/staged rollout
- usage limits
- UI/workflow changes

### Microsoft 365 / PowerPoint / Teams

Relevant risk areas:

- channel-specific rollout
- enterprise deployment
- collaboration/sync
- media export
- meeting reliability
- add-in compatibility
- Copilot behavior

## Logo and icon policy

Use real company logos and product/software icons when feasible.

Do not AI-generate or hand-draw approximations of brand logos.

Preferred source order:

1. Official vendor brand/press/media kit
2. Official product/app icon from vendor-controlled pages
3. Official documentation or developer resources
4. License-compatible third-party icon libraries, only with documented license/attribution
5. Existing manually curated local asset

Store approved assets locally under:

```text
auxsays/assets/img/patch-logos/
```

Do not hotlink external logo URLs in product/company data.

Every company/product logo path should point to a local asset.

Every asset should have provenance metadata in:

```text
auxsays/_data/patch_logo_sources.yml
```

Use marks only for product/company identification and editorial reference.

Do not imply sponsorship, endorsement, affiliation, or partnership.

Do not claim there is zero trademark/copyright risk. Use a practical, conservative identification-use policy.

## Important repo structure

Site root:

```text
auxsays/
```

Important files:

```text
auxsays/_data/patch_companies.yml
auxsays/_data/patch_products.yml
auxsays/_data/patch_ingestion_sources.yml
auxsays/_data/consensus_evidence.yml
auxsays/_data/patch_logo_sources.yml
auxsays/_layouts/aux-home.html
auxsays/_layouts/aux-update.html
auxsays/_layouts/aux-updates.html
auxsays/_layouts/aux-patch-company.html
auxsays/_layouts/aux-patch-product.html
auxsays/assets/css/auxsays-custom.css
auxsays/scripts/patch_ingest.py
auxsays/scripts/qa_patch_records.py
auxsays/scripts/source_health_snapshot.py
auxsays/scripts/build_consensus_from_evidence.py
auxsays/scripts/validate_ingestion_sources.py
auxsays/scripts/validate_logo_assets.py
```

Generated records live under:

```text
auxsays/updates/generated/
```

Avoid editing generated records unless the task explicitly requires it. If generated records are edited, state that clearly in the final report.

## Forbidden or transient files

Do not commit or include these in patches unless explicitly required:

```text
auxsays/_site/
node_modules/
.jekyll-cache/
__pycache__/
*.pyc
auxsays/_data/source_health.yml
auxsays/_data/qa_status.json
auxsays/_data/consensus_status.json
auxsays/_data/patch_ingest_state.json
auxsays/assets/img/patch-logos/_generation-report.json
```

If one of these files appears changed, verify whether the change is intentional. If not intentional, revert it.

## GitHub Actions / state-file caution

Source health and generated status files may be produced during local or CI validation.

Do not treat generated local output as hand-authored source.

Do not include generated runtime output just because a script created it.

If GitHub Actions creates durable patch records, report that the user may need to pull before pushing again.

## Validation commands

Run relevant validation before reporting completion.

Common validation commands:

```bash
python auxsays/scripts/validate_ingestion_sources.py
python auxsays/scripts/qa_patch_records.py
python auxsays/scripts/build_consensus_from_evidence.py
python auxsays/scripts/validate_logo_assets.py
```

If Ruby/Jekyll validation is relevant and dependencies are available:

```bash
cd auxsays
bundle exec jekyll build --trace
```

If a validation failure is unrelated to the task, report it honestly and do not pretend it passed.

## Delivery expectations

When completing a task, report:

1. Exact files changed
2. Why each file changed
3. Validation commands run
4. Validation results
5. Whether generated records were edited
6. Whether state files were edited
7. Whether build/transient files were avoided
8. Known risks or limitations
9. Recommended next step

## Preferred task sizing

A good task should usually have:

- one primary objective
- two to six likely files touched
- clear forbidden files
- clear validation commands
- clear success criteria

Avoid broad tasks like:

```text
Make AUXSAYS better.
```

Prefer scoped tasks like:

```text
Repair the Premiere Pro 26.2 page so it shows a WAIT verdict, renders Verified reports wording, displays evidence sample cards, hides empty checksum sections, and preserves generated/state files.
```

## Final reminder

AUXSAYS should feel like a careful, evidence-backed patch intelligence site.

Do not let implementation shortcuts make it look like a generic AI-generated software blog.
