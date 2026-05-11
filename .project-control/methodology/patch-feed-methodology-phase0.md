# AUXSAYS Patch Feed — Methodology Note (Phase 0)

**Internal project-control document. Not for public site publishing.**  
Date: 2026-05-11 | Phase: 0

---

## 1. OBS Studio Proof-of-Concept Methodology

OBS Studio is the first AUXSAYS product to move from legacy/manual report counts into a fully structured, evidence-backed pilot model. This section documents the complete methodology as inspected in Phase 0.

### 1.1 How OBS Official Releases Are Detected

OBS Studio uses the `github_releases` adapter (`auxsays/scripts/adapters/github_releases.py`). The source configuration in `auxsays/_data/patch_ingestion_sources.yml` specifies:

- **API endpoint**: `https://api.github.com/repos/obsproject/obs-studio/releases`
- **Parser profile**: `github_release_standard`
- **Version pattern**: `^(v)?(?P<version>[0-9]+(\.[0-9]+)+.*)$`
- **Pre-releases**: excluded (`include_prereleases: false`)
- **Update detection method**: GitHub release tag comparison

The GitHub Releases API returns structured JSON with version tags, publication timestamps, release note bodies, and asset download links including checksums. This is the highest-confidence source class in the system because GitHub's API provides machine-readable, versioned, timestamped release data without scraping.

### 1.2 How OBS GitHub Issues Are Searched

The community-evidence collector (`auxsays/scripts/collect_obs_reports.py`) uses the GitHub Search Issues API:

- **Repository**: `obsproject/obs-studio`
- **Query template**: `repo:obsproject/obs-studio is:issue "{version}"`  
  - Optional: `created:>={since}` to limit search window
- **Pagination**: up to N pages of 100 results each
- **Pull requests excluded**: `if item.get("pull_request"): continue`
- **Deduplication**: issues tracked by URL to prevent double-counting

The search query wraps the version string in quotes to require an exact phrase match at the search level, before the stricter per-issue matching step.

### 1.3 How Exact Patch/Version Matching Works

Matching is a two-stage process:

**Stage 1 — Search-level filter**: The GitHub Search API query uses quoted exact-string matching for the version. This narrows the candidate set.

**Stage 2 — Per-issue pattern match** (`match_basis` function):
- A regex `exact_version_re(version)` is built: `(?<![0-9.]){re.escape(version)}(?![0-9.])` — this prevents partial version matches (e.g., `32.1.1` would not match inside `32.1.10`).
- The pattern is tested against `issue["title"]` first (basis = `"title"`).
- If not found in title, it is tested against `issue["body"]` (basis = `"body"`).
- If neither matches, the candidate is rejected.

This two-stage approach ensures only genuinely version-specific issues are counted.

### 1.4 How Reports Are Accepted or Rejected

**Accepted** when:
- `exact_version_re(version)` matches the title or body of the issue.
- The issue is not a pull request.

**Rejected** when:
- The version pattern does not appear in title or body.
- The issue appears to be developer/build-infrastructure noise (`likely_developer_only()` function).

**Developer-noise filter** (`likely_developer_only`):
- Checks for build/dev terms: `"build failure"`, `"cmake"`, `"compile"`, `"github actions"`, `"enable_plugins"`, etc.
- Only rejects if developer terms are present **and** end-user terms are absent.
- End-user terms that override rejection: `"crash"`, `"freeze"`, `"hang"`, `"lag"`, `"recording"`, `"streaming"`, `"audio mixer"`, `"black screen"`, `"hotkey"`, `"pipewire"`.

**Important**: The developer-noise filter is OBS-specific because it targets OBS-specific template headings and jargon. The overall accept/reject logic (exact version match) is generalisable.

### 1.5 How Theme, Workflow Area, Platform, Severity, and Sentiment Are Assigned

The `classify()` function applies keyword-based rules to the combined issue text (title + scrubbed body + labels):

| Matched term | Theme | Workflow area | Severity | Sentiment |
|---|---|---|---|---|
| `"crashes on quit"` / `"crash if"` | crash / stability | application stability | high | negative |
| `"screen capture"` / `"black screen"` / `"xcomposite"` | screen capture regression | screen/window capture | high | negative |
| `"black square"` / `"mouse cursor"` | visual capture artifact | display capture / HDR workflow | medium | negative |
| `"audio mixer"` / `"audio"` | audio mixer regression | audio mixer UI | medium | negative |
| `"hotkey"` | hotkey regression | keyboard shortcuts | medium | negative |
| `"web camera"` / `"camera"` | camera/source regression | camera source workflow | medium | negative |
| `"rescale output"` | output configuration regression | output settings | medium | negative |
| `"freeze"` / `"hang"` | freeze / hang | application stability | high | negative |
| `"plugin"` | plugin compatibility | plugins | medium | negative |
| (fallback) | unspecified issue | general OBS workflow | medium | moderate |

**Platform detection**: scans combined text for `"windows"`, `"macos"`, `"linux"`. First match wins; default is `"unknown"`.

All OBS-sourced GitHub issues are classified as `"negative"` or `"moderate"` sentiment — the system currently does not produce `"positive"` sentiment from GitHub Issues, as the model only looks for problem reports.

### 1.6 How Structured Evidence Rows Are Written

The `evidence_row()` function in `collect_obs_reports.py` assembles a standardised row:

```yaml
id: obs-studio-{version-slug}-github-issue-{number}
product_id: obs-studio
update_version: "32.1.2"
source_type: github_issue
source_name: obsproject/obs-studio
source_url: https://github.com/obsproject/obs-studio/issues/{number}
parent_title: "{issue title}"
report_title: "{issue title}"
report_text_excerpt: "{version-anchored excerpt, max 280 chars}"
captured_at: "{ISO 8601 UTC timestamp}"
patch_version_matched: true
matched_version: "32.1.2"
match_basis: title|body
counted: true
exclusion_reason: null
issue_theme: "{classified theme}"
workflow_area: "{classified area}"
platform: windows|macos|linux|unknown
severity: high|medium|low|critical
sentiment: negative|moderate|positive
source_weight: 1
```

The `excerpt()` function anchors the snippet around the first occurrence of the version string in the body, giving 280 characters of surrounding context.

Rows are written to `auxsays/_data/consensus_evidence.yml` under a top-level `evidence:` list. The file uses YAML anchoring via `schema_version: 1`.

### 1.7 How Generated Patch Record Counts Are Updated

After collecting evidence, `collect_obs_reports.py` (or `build_consensus_from_evidence.py`) counts accepted rows per `(product_id, update_version)` pair and can update the `update_report_count` field in the corresponding generated markdown record under `auxsays/updates/generated/`.

The `build_consensus_from_evidence.py` script:
- Loads all evidence items from `consensus_evidence.yml`
- Groups by `(product_id, update_version)`
- Counts only items where `counted == true` and the item passes `is_patch_specific()` (either `patch_version_matched: true` or the version string appears in the parent/report titles or excerpt)
- Derives `consensus_label` from the ratio of negative vs. positive sentiments
- Derives `confidence` from total count (≥25 → Medium, ≥8 → Low-Medium, >0 → Low)
- Writes a `consensus_status.json` file (not the generated records themselves; those are updated separately)

**Important distinction**: `build_consensus_from_evidence.py` writes only `_data/consensus_status.json`. The actual generated records (`updates/generated/*.md`) are updated by `collect_obs_reports.py` as part of the collection run, or by a separate pipeline step.

### 1.8 How Legacy/Manual Counts Differ from Evidence-Backed Counts

**Legacy/manual counts** (as found in OBS 32.1.1):
- `update_report_count: 39` — a total including all historical signals
- `legacy_consensus_score: -42` — a raw score from an older model
- `legacy_consensus_score_percent: 29` — percentage representation
- These were set by hand or by an earlier non-structured counting method
- They predate the structured `consensus_evidence.yml` pilot

**Evidence-backed counts** (as found in OBS 32.1.2):
- `update_report_count: 20` — derived from confirmed, deduplicated GitHub Issues
- Each issue is individually traceable via its `source_url` in `consensus_evidence.yml`
- The `audit_consensus_evidence.py` script compares the generated record count against the evidence count and flags discrepancies
- The `audit` script's `--strict` mode also flags stale records (where source was re-checked after the record's `update_last_checked`)

**Key distinction**: evidence-backed counts are auditable. Legacy counts are opaque. The audit script identifies which records have evidence-backed counts and which are still on legacy/manual numbers.

### 1.9 Which Parts Are OBS-Specific

- **GitHub Issues search**: specific to products with GitHub repositories as the bug tracker
- **`obsproject/obs-studio` repo constant**: hard-coded in `collect_obs_reports.py`
- **Developer-noise filter terms**: OBS-specific terms (`cmake`, `enable_plugins`, `libobs-metal`, etc.)
- **Issue template scrubbing** (removing `### OBS Studio Log URL` headings from body text)
- **Theme classification terms**: some are OBS-specific (`"pipewire"`, `"xcomposite"`, `"rescale output"`)

### 1.10 Which Parts Can Generalise to Other Source Classes

**Fully generalisable** (require only configuration changes):
- Exact version regex matching logic (`exact_version_re`, `match_basis`)
- Evidence row schema (`consensus_evidence.yml` fields)
- `build_consensus_from_evidence.py` — product-agnostic, works on any row in evidence file
- `audit_consensus_evidence.py` — product-agnostic
- Sentiment/severity/confidence labelling model
- `is_patch_specific()` check
- The counted/excluded distinction and `exclusion_reason` field

**Requires adapter work** (new collector per source class):
- GitHub Issues collector → works for any GitHub-hosted project
- Forum/community scraping → must be built per-vendor
- Adobe Community → requires Adobe Community API or HTML parsing
- Blackmagic forum → requires custom adapter

---

## 2. Source-Class Generalisation Proposal

### 2.1 Class 1 — GitHub-Native Products

**Examples**: OBS Studio, ComfyUI, Blender (partial)  
**Official source**: GitHub Releases API → `github_releases` adapter  
**Evidence source**: GitHub Issues API → `collect_obs_reports.py`-style collector (generalised)

**What needs to happen to extend to another GitHub-native product**:
1. Add source entry in `patch_ingestion_sources.yml` with `adapter: github_releases` and the correct repo
2. Create a product-specific collector (or generalise `collect_obs_reports.py` to accept `repo` and `product_id` as parameters — this is the natural next step)
3. Remove OBS-specific developer-noise terms and replace with product-appropriate ones
4. Test version matching against known releases before enabling

**Confidence level**: High. The methodology is proven and the infrastructure is in place.

### 2.2 Class 2 — Vendor-Release-Page Products

**Examples**: DaVinci Resolve / Blackmagic Design, Elgato  
**Official source**: vendor HTML pages, download portals, support pages  
**Evidence source**: vendor forums, Reddit, support communities — only when version-specific

**Characteristics**:
- No GitHub-like structured release/issue API
- Version numbers may be embedded in press release prose, not structured data
- Forum posts are not machine-queryable by version
- Release page HTML may change without notice
- Checksums and file sizes often not provided

**Current DaVinci status** (see Section 3 below).

### 2.3 Class 3 — Vendor Help-Center Products

**Examples**: Elgato ecosystem (Stream Deck, Wave Link, Camera Hub, 4K Capture Utility)  
**Official source**: product-specific help center release notes  
**Evidence source**: Elgato community forums, Reddit, OBS plugin issues

**Characteristics**:
- Release notes exist but are per-product, not aggregated
- Version numbers usually appear in structured help articles
- Firmware/software mismatch risk is Elgato-specific (hardware dependency)
- OBS plugin compatibility is a cross-product concern

### 2.4 Class 4 — Adobe-Style Products

**Examples**: Premiere Pro, Acrobat, Photoshop, After Effects  
**Official source**: Adobe release notes pages (structured HTML), help center articles  
**Evidence source**: Adobe Community bug reports (versioned bug threads)

**Characteristics**:
- Adobe Community bug reports frequently name exact build versions (e.g., `26.2 Build 65`)
- Adobe Help Center release notes have stable URLs per product
- Build number precision is important — version `26.2` and `26.2 Build 65` are distinct
- Evidence for Premiere Pro 26.2 already exists in `consensus_evidence.yml` (3 manually entered rows)

---

## 3. DaVinci Resolve / Blackmagic Design Strategy

### 3.1 Current Source Configuration

From `auxsays/_data/patch_ingestion_sources.yml`:
- **Adapter**: `html_blog`
- **Official URL**: `https://www.blackmagicdesign.com/media`
- **Secondary URL**: `https://www.blackmagicdesign.com/support/family/davinci-resolve-and-fusion`
- **Status**: **disabled** (`enabled: false`)
- **Parser profile**: `blackmagic_media_keyword_filter`
- **Update detection**: `manual watch with title-date keyword filter candidate`
- **Reliability**: `Medium`, **Breakage risk**: `Medium-High`
- **Source health note**: "Official record tracked; automated ingestion is not active because the current Blackmagic adapter path is not source-specific enough for safe unattended runs."

### 3.2 Existing DaVinci Generated Records

Two records exist:

| Record | Status | Report Count | Evidence-Backed? |
|---|---|---|---|
| DaVinci Resolve 21 (generic) | archived | 0 | No — insufficient data |
| DaVinci Resolve 21 Public Beta 1 | current | 7 | **Unclear** — counts appear manually set |

The Public Beta 1 record has `update_report_count: 7` but no corresponding rows in `consensus_evidence.yml` for `product_id: blackmagic-davinci`. The 7 count is not evidence-backed under the current methodology.

### 3.3 Why Official Body Capture Is Failing or Limited

- Blackmagic's media/release page (`blackmagicdesign.com/media`) is a keyword-filtered blog, not a structured release feed
- There is no GitHub Releases equivalent
- Release note body text is not machine-extractable without JavaScript rendering or careful HTML parsing
- The Blackmagic adapter (`html_blog`) is flagged as too broad for unattended runs
- The `fetch_davinci_updates.py` script is a minimal stub that only sets a hardcoded state entry — it does not actually scrape or validate anything

### 3.4 Why DaVinci Requires a Different Methodology Than OBS

| Dimension | OBS Studio | DaVinci Resolve |
|---|---|---|
| Official source type | GitHub Releases API (structured JSON) | Vendor HTML press release page |
| Version in source | Explicit, machine-readable tag | Embedded in prose, requires parsing |
| Issue tracker | GitHub Issues (searchable by version) | Blackmagic Forum (no API, no search-by-version) |
| API availability | Full GitHub REST API | None |
| Automation confidence | High | Low-Medium |
| Evidence collection approach | Automated GitHub Issues search | Manual watch or forum scraping (risky) |

### 3.5 What Must Be Validated Before DaVinci Can Be Evidence-Backed

Before DaVinci can be treated as evidence-backed like OBS:

1. **Official source adapter must be reliable**: The Blackmagic HTML parser must accurately detect new releases without false positives. This requires: testing on at least 3 known historical release URLs, verifying version extraction logic, confirming the source URL pattern has not changed.

2. **Evidence source must be identified**: A queryable, version-specific community source must be found. Candidates:
   - Blackmagic Design forum (would require per-thread scraping; no version search API)
   - Reddit r/davinciresolve (requires Reddit API; version matching feasible but noisy)
   - Neither candidate is as clean as GitHub Issues

3. **Version matching must be tested**: DaVinci version strings (e.g., `"21 Public Beta 1"`) are non-standard and would require a custom version normaliser before the standard `exact_version_re()` approach would work reliably.

4. **A trial run must be validated by hand**: At least one DaVinci version must go through a full collect → audit → count cycle, with manual verification of every counted report before any number is published.

5. **The `fetch_davinci_updates.py` stub must be replaced or removed**: The current file is a hardcoded state-setter that does not perform real ingestion. It should not be confused with a real collector.

**Recommendation**: Do not treat DaVinci report counts as evidence-backed until Steps 1–4 above are complete. The current 7-report count for Public Beta 1 should be labelled as `intelligence_stage: manual_watch` or left with `update_consensus_label: Insufficient data` until a real evidence cycle is run.

---

## 4. Evidence-Backing Criteria (Before a Product Can Be Treated Like OBS)

A product can be treated as evidence-backed when all of the following are true:

1. **Official source is reliably automated**: At least two weeks of unattended runs without false positives or missed releases.
2. **Evidence source is identified and queryable**: A source exists where community reports can be searched by exact version string.
3. **Version matching is tested**: The `exact_version_re()` pattern (or equivalent) correctly matches and rejects across at least 10 manually verified candidates.
4. **At least one full evidence cycle is completed**: Collect → deduplicate → audit → compare against manual count → pass audit with zero unexplained discrepancies.
5. **Evidence rows are in `consensus_evidence.yml`**: The counted reports are traceable to source URLs in the evidence file.
6. **The audit script passes `--strict`**: `audit_consensus_evidence.py --json --strict` reports no discrepancies for that product.
7. **No manual overrides remain unexplained**: If any `counted: true` rows were manually set (not by a collector script), they must have `captured_at` dates and a clear rationale in the row's `report_text_excerpt`.
