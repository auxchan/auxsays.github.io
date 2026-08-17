# Phase-2 UI Implementation Design

Status: **APPROVED IMPLEMENTATION DESIGN — IMPLEMENT ONLY IN A SEPARATELY SCOPED TASK**

Date: 2026-08-17

Contracts: BINDING Foundation, `UI_UX_CONTRACT.md` 1.0.0, and `MOTION_INTERACTION_CONTRACT.md` 1.0.0

This document records resolved O-001A/O-001B/O-002 and Taylor-approved O-001C/O-001D. The current approval task creates no production data, application code, dependency installation, Jekyll change, workflow change, or deployment; implementation requires the subsequent scoped Phase-2 task.

## 1. Component and module architecture

The V1 design keeps view code separate without inventing a framework inside React.

```text
systems-monitor/app/                         # O-001A future package; does not exist yet
  src/
    app/
      SystemsMonitorApp                     # application root/error boundary
      AppShell                              # scoped product shell
      RouteStateController                  # URL <-> validated app state
      SnapshotProvider                      # public payload load/validation boundary
      ViewModelFactory                      # payload -> display-safe view models
    shell/
      PrimaryViewSwitcher
      SystemRail
      ContextBreadcrumbs
      ExploreSearch
      SystemHealthSummary
      FixturePublicationBanner
    views/
      summary/SummaryView
      verified/VerifiedDataView
      outlook/OutlookView
      trace/TraceMode                        # lazy, focused, bounded
    shared/
      DataStateLabel                        # OBS/CALC/FCST/SCEN
      FreshnessLabel
      SourceEvidenceLink
      ChartFrame                            # title, summary, visual, table alternative
      Inspector                             # content model; drawer/sheet is responsive
      RankedList
      LoadingState / EmptyState / ErrorState / DegradedState
    state/
      routeSchema                           # allowed params/defaults/canonicalization
      selectionState                        # non-URL and persistent-context rules
    data/
      publicSnapshotTypes                   # generated/hand-maintained from PDI contract later
      validatePublicSnapshot
      fixtureBoundary                       # publicationClass enforcement
  tests/                                    # unit/component/accessibility/routing
```

### MUST EXIST FOR UI SHELL

- `SystemsMonitorApp`, `AppShell`, `RouteStateController`, `SnapshotProvider`, and `ViewModelFactory`.
- One shared shell with `PrimaryViewSwitcher`, `SystemRail`, `ContextBreadcrumbs`, `SystemHealthSummary`, and fixture banner.
- `SummaryView`, `VerifiedDataView`, and `OutlookView` as lazy view boundaries while preserving one shell.
- Focused, lazy `TraceMode` sufficient for one fixture path; it is not a global graph explorer.
- Shared semantic primitives for data state, freshness, source/evidence access, charts plus table/text alternatives, inspectors, ranked lists, and degraded states.
- A single data boundary that rejects invalid payloads before view rendering and maps public records into display-safe view models.

### LATER / CONDITIONAL

- Virtualized all-results tables only after real payload measurements justify them.
- Graphology/Sigma or another graph engine only if focused Trace exceeds accessible SVG/HTML needs; do not load it by default.
- Advanced comparison workspaces, saved views, scorecards, export builders, scenario editors, or model diagnostics after their contracts/data exist.
- A general component library. Extract primitives only after repeated use proves the abstraction.

View code consumes view models, not raw storage or producer shapes. Routing owns only durable selection; transient hover, open tooltip, focus, scroll, animation phase, and inspector tab remain local UI state.

## 2. Routing and canonical query state

D-008 remains the authority: one real pathname, validated query state.

| Parameter | Allowed shape | Default / canonical rule |
|---|---|---|
| `view` | `summary`, `verified`, `outlook` | `summary`; omit when default |
| `system` | payload-backed stable slug | none; default system comes from payload ordering and is omitted |
| `path` | `/`-separated payload-backed descendant slugs, ordered below `system` | empty; selected factor/node is final segment; hierarchy depth is derived, not duplicated |
| `horizon` | payload-validated semantic ID; required primary identities are `current-year`, `next-year`, and `plus-3-years` | `current-year`; omit outside Outlook and when default |
| `scenario` | `baseline` or payload-backed scenario ID | `baseline`; omit outside Outlook and when default |
| `geo` | payload-backed stable geography code | product/default geography; omit when default |
| `range` | payload-backed approved range ID | view-specific default; omit when default |

Canonical examples:

```text
/systems-monitor/
/systems-monitor/?view=verified&system=fixture-system-a&path=fixture-factor-a
/systems-monitor/?view=outlook&system=fixture-system-a&horizon=next-year&scenario=fixture-scenario-a
```

Outlook visibly offers Current Year, Next Year, and +3 Years whenever the applicable predictive payload exists. Those are semantic, dynamic concepts: displayed calendar years derive from snapshot/forecast-origin semantics. Additional approved payload horizons may supplement but not replace them without a Master amendment.

Validation order is view, system, path, geography, then view-specific options. Unknown keys are ignored and removed from the canonical URL. An unknown `view` becomes Summary. An invalid system returns to the payload default. A path is validated segment by segment and truncated at the last valid ancestor. Invalid dependent horizon/scenario/range values return to their view defaults. Parsing never causes an error page.

On direct load and refresh, parse once, validate against the loaded payload, then `replaceState` with the canonical form. Deliberate mode, system, hierarchy, geography, horizon, scenario, or range changes use `pushState`; corrections and default elision use `replaceState`. `popstate` restores state without adding another history entry and moves focus to the restored context heading. Share/copy uses only the validated canonical URL.

System and path persist across modes when the target view supports them. Outlook-only parameters are removed outside Outlook. Transient states never enter the URL. If a previously valid shared selection is absent from a newer payload, the UI shows a concise unavailable-context notice and falls back to the nearest valid ancestor.

## 3. Public fixture design

The fixture is a contract-validation asset for future implementation, not a factual dataset. No fixture file is created in this drafting phase.

### Envelope and safety rules

- Use the BINDING Public Data Interface envelope and `snapshot.publicationClass: fixture` as the only public factual/fixture discriminant. Never add `isFixture`.
- Every visible entity/provider/series label begins with `SYNTHETIC TEST` or `FIXTURE`. IDs use a `fixture-` namespace. Units are `synthetic-index-points` or another explicitly non-economic test unit.
- App shell, inspectors, tables, chart summaries, raw views, and any future export repeat “SYNTHETIC TEST DATA — NOT A PUBLIC CLAIM.”
- Use internally consistent ISO timestamps solely to test timing semantics. They are labeled fixture timestamps and never described as recent real-world observations.
- Fixture output is release-blocked by the Release Acceptance contract; a factual release may not contain `publicationClass: fixture`.

### Minimum fixture coverage

One fixture snapshot contains:

1. Ten top-level systems named `SYNTHETIC TEST SYSTEM 01` through `10`.
2. At least one system with ten children and one child with ten grandchildren, plus an eleventh bounded child in the full collection to exercise View All without fabricating a displayed Top 10.
3. One `OBS` series with source observation/publication/retrieval/vintage timing and a synthetic provider record.
4. One `CALC` series with method reference and source-observation dependencies.
5. Baseline `FCST` records exercising all three required semantic horizons—`current-year`, `next-year`, and `plus-3-years`—with synthetic origins, ranges/intervals, evidence, model-skill state, positive pressures, and offsets. Display-year labels are derived, not fixture-hard-coded product architecture.
6. One `SCEN` record with a clearly synthetic assumption and explicit relationship to baseline.
7. Snapshot generated/published timing and system evaluated timing distinct from source timing; one known next-expected-release time.
8. One human-capital record labeled `SYNTHETIC TEST OCCUPATION ALPHA`, linked to a synthetic industry/factor without a real labor claim.
9. One bounded trace: no more than 12 nodes/16 edges, with relationship type, direction, lag, evidence strength, provenance, and one competing/offsetting path.
10. Separate test variants for loading, source delayed, source stale, insufficient evidence, forecast unavailable, high disagreement, partial payload, and snapshot unavailable.
11. One synthetic ranking boundary in which ranks 10 and 11 carry an approved near-tie state, rank 11 is marked near-cutoff, and at least one item supplies `priorRank`/change. These fields are producer-supplied test semantics; the UI does not compute production hysteresis or stability.

Illustrative specimen (shape, not a production payload):

```json
{
  "schemaVersion": "1.0.0",
  "contractVersion": "1.0.0",
  "snapshot": {
    "id": "fixture-phase2-ui-shell",
    "evaluatedAt": "2000-01-02T00:00:00Z",
    "generatedAt": "2000-01-02T00:01:00Z",
    "publishedAt": "2000-01-02T00:05:00Z",
    "asOf": "2000-01-01T23:59:59Z",
    "sourceSnapshotId": "fixture-sources-phase2-001",
    "publicationClass": "fixture"
  },
  "systems": [{
    "id": "fixture-system-01",
    "label": "SYNTHETIC TEST SYSTEM 01"
  }],
  "sources": {},
  "events": [],
  "outlook": {
    "horizons": ["current-year", "next-year", "plus-3-years"],
    "forecasts": []
  },
  "extensions": {
    "auxsays.phase2.trace": {
      "fixtureOnly": "SYNTHETIC TEST TRACE — NOT A CAUSAL CLAIM"
    }
  }
}
```

The abbreviated specimen follows the BINDING Public Data Interface envelope: version fields at top level, publication identity/timing inside `snapshot`, and top-level systems/sources/events/outlook/extensions. Exact item records must be copied from and validated against that contract during implementation. Trace/test-control metadata uses namespaced `extensions`; it does not require a schema amendment. Degraded conditions should be harness-selected fixture variants rather than a new public truth field.

## 4. Design-token and styling strategy

The root selector `[data-aux-product="systems-monitor"]` establishes containment. All custom properties use `--aux-sm-*`; component styles use CSS Modules or equivalently locally scoped selectors; resets and typography changes are rooted. Portals must render into a Systems Monitor-owned portal root so overlays retain token scope. No selector may target Patch Feed/global classes.

Token groups:

- Color/surface: graphite/deep navy `canvas`, `surface-1..3`, overlay; high-contrast `text-primary`, `secondary`, `muted`; restrained cyan/teal `accent`, `focus`; separate success/warning/delayed/stale/error tokens.
- Lines: subtle/strong/divider/grid/reference/selected. Chart grids stay subordinate to data and annotation.
- Typography: display, section, body, label, numeric, provenance/code. Final font files and subsetting remain license/performance work; roles do not depend on a particular font.
- Spacing: `4, 8, 12, 16, 24, 32, 48` px-equivalent tokens, plus responsive container/gutter tokens.
- Radius: `0, 4, 8, 12`; large panels use restrained edges rather than pill/card walls. Pills are reserved for compact states/tags.
- State: `OBS`, `CALC`, `FCST`, `SCEN`, fixture, source health, selection, and forecast direction use separate semantic token families. State meaning is reinforced with labels/line styles/markers/patterns.
- Layers: base `0`, sticky `10`, popover/tooltip `20`, inspector/sheet `30`, modal `40`, toast `50`. Components consume named tokens.

## 5. Responsive and accessibility implementation design

Desktop uses a system rail plus one dominant visualization/content region and an adjacent inspector only above its content-fit threshold. Tablet changes the rail into a horizontal selector or sheet and moves the inspector below/to a sheet. Mobile stacks content, uses a compact mode selector, bottom-sheet/full-screen inspector, shortened labels only when accessible names remain complete, and fewer chart labels/series. Tables scroll within labeled regions; the page itself does not overflow horizontally.

Semantic HTML is the default. Mode controls use the correct tabs/radio/navigation pattern after interaction testing. Ranked items are buttons/links in lists; breadcrumbs use `nav` with a label; inspectors have explicit headings and dismiss behavior. Charts expose a title, description, selected-data summary, keyboard path where practical, and a table/list equivalent. Automated accessibility is necessary but not sufficient: test keyboard-only, focus restore, 200%/400% zoom/reflow, reduced motion, high contrast, and representative NVDA/VoiceOver paths.

## 6. O-001A — RESOLVED engineering choice

**Selected choice:** one isolated React/TypeScript package at repository-relative `systems-monitor/app/`.

**Rationale:** D-007 already assigns `systems-monitor/` to product-owned source/config/tests. `auxsays/package.json` is an existing site-tools package, not a frontend application, so adding the app there would mix ownership and dependency lifecycles. The public Jekyll attachment remains separately owned under `auxsays/systems-monitor/` after Taylor authorizes it.

**Future affected paths:** `systems-monitor/app/package.json`, `systems-monitor/app/package-lock.json`, `systems-monitor/app/src/`, `systems-monitor/app/tests/`, and bounded package config/scripts. This decision creates none of them now.

**Compatibility:** scripts must use repo-relative paths and work under Windows local development and Ubuntu/Node 24 CI. Vite’s public base, if approved later, must emit `/systems-monitor/`-safe URLs. The package must not import Patch Feed internals or reuse `auxsays/package.json` as its app manifest.

## 7. O-001B — RESOLVED engineering choice

**Selected choice:** npm with one committed `package-lock.json` colocated at `systems-monitor/app/package-lock.json`; CI uses `npm ci` from that package.

**Rationale:** the repository already provisions Node/npm, Pages currently uses Node 24, and npm adds no package-manager bootstrap or workspace-wide manifest. A per-package lockfile gives deterministic installs while preserving the existing `auxsays` tooling boundary.

**Future affected paths:** `systems-monitor/app/package.json`, its lockfile, and package-local scripts/config. Exact versions are selected and license/security/bundle-audited only when dependency installation is separately authorized.

**Compatibility:** pin supported Node/npm behavior through `engines` and CI; run package commands with an explicit prefix or working directory. Do not create a repository-root lockfile or modify the unrelated site-tools package merely for the app.

## 8. O-001C — ACCEPTED / RESOLVED — TAYLOR APPROVAL

**Approved choice (Taylor, 2026-08-17):** Systems Monitor owns generated assets; builds are clean, CI-generated, and uncommitted.

- Source remains `systems-monitor/app/`.
- Future Vite output first lands in ignored `systems-monitor/.build/ui/` with a manifest and content-hashed assets.
- A bounded package-owned composition step copies only manifest-referenced assets into temporary `auxsays/systems-monitor/assets/` and generates temporary `auxsays/_includes/generated/systems-monitor-assets.html` for the future Jekyll page.
- Jekyll then composes those files into `auxsays/_site/systems-monitor/`. Generated source-tree staging and `_site` remain uncommitted.
- The Systems Monitor package owns generation and cleanup; Jekyll owns the final site composition. A pre-build clean removes only the three exact generated directories/files, and post-validation may clean staging without touching the uploaded artifact.
- Manifest validation rejects missing/unreferenced output, wrong `/systems-monitor/` base URLs, or assets older than the current build. A failure occurs before Pages artifact upload, leaving the last valid deployment live.

**Approval rationale:** hashed assets avoid stale browser caches, the generated include gives Jekyll deterministic composition, and uncommitted output avoids generated-source drift. Ownership and cleanup are narrow enough to test.

**Alternatives considered:** committing built assets (rejected: review noise and stale artifacts); fixed unhashed filenames (rejected: Pages/browser cache ambiguity); overlaying an independent SPA after Jekyll (rejected: weak shell/manifest ownership); a separate deployment artifact/job (not needed for one small package).

The architecture, exact temporary paths, non-commit policy, manifest validation, bounded cleanup, and Jekyll composition are approved. The current task creates none of them; a subsequent scoped implementation task is still required.

## 9. O-001D — ACCEPTED / RESOLVED — TAYLOR APPROVAL

**Current behavior:** the single Pages build job checks out the repository, sets up Ruby 3.3, Node 24, and Python, runs existing source-health/logo/generated-record checks, builds Jekyll from `auxsays/`, and uploads `auxsays/_site`; the deploy job publishes that artifact. It does not install or build React.

**Approved minimal architecture (Taylor, 2026-08-17):** keep one build job. After the existing runtimes and before Jekyll build, run package-local `npm ci` and a package production build/composition that cleans, builds, validates the Vite manifest, and composes the temporary Jekyll assets/include. Run the existing Jekyll build unchanged in purpose, then a Systems-Monitor-specific static-site verification that checks the `/systems-monitor/` entry, asset references, fixture banner/release block, and no missing files before the existing upload step.

No additional job is required. The React output becomes an input to the same atomic Jekyll artifact. UI failure blocks upload/deploy and leaves the previous Pages release live. Existing Patch Feed generation/QA remains in its current order and is neither imported nor modified by the UI package.

**Rollback:** remove the bounded Systems Monitor install/build/verify steps and future Jekyll include/page references; delete only approved generated staging paths. The original Jekyll artifact flow then remains.

**Files for the subsequent authorized implementation scope:** `.github/workflows/pages.yml`; `.gitignore`; package files/config/scripts under `systems-monitor/app/`; and the minimal Jekyll attachment at `auxsays/systems-monitor/index.html` plus its generated include/assets paths. The architecture is approved; no such file is modified now.

## 10. O-002 — RESOLVED engineering choice

**Selected library family:** Recharts for Phase-2 React charts; exact version remains implementation-time verification, not a reopened product decision.

Recharts is the clearer fit for the V1 shell because it is React-native and compositional, provides TypeScript declarations, responsive chart containers and reference/annotation primitives, and in Recharts 3 enables an accessibility layer by default with documented arrow-key data-point navigation. The official package declares MIT licensing and side-effect metadata for bundling. Its current official release must still be pinned and audited immediately before install.

Apache ECharts remains a capable later alternative for genuinely large or complex visualizations: it provides TypeScript, tree-shakeable core/component imports, canvas/SVG renderers, ARIA descriptions/decals, and Apache-2.0 licensing. For this accessible, focused React shell its broader surface is not decisive, its ARIA feature is opt-in, and the official accessibility material does not document equivalent keyboard data-point navigation. Phase 2 does not need its scale advantage because whole-economy graph initialization is prohibited.

**Non-negotiable conditions before install/merge:** recheck exact version, license/transitive inventory, advisories, React compatibility, bundle measurements, touch behavior, dark-theme customization, annotations, and representative NVDA/JAWS/VoiceOver behavior. Recharts does not remove the requirement for text summaries, equivalent tables/lists, non-color encodings, or touch controls. If those proofs fail, reopen O-002 and return the product-level tradeoff to Taylor.

Primary research record:

- Recharts accessibility: https://github.com/recharts/recharts/wiki/Recharts-and-accessibility
- Recharts package metadata: https://github.com/recharts/recharts/blob/main/package.json
- Recharts releases: https://github.com/recharts/recharts/releases
- Apache ECharts accessibility: https://echarts.apache.org/handbook/en/best-practices/aria/
- Apache ECharts tree-shaking: https://echarts.apache.org/handbook/en/basics/import/
- Apache ECharts repository/license/releases: https://github.com/apache/echarts

## 11. Performance budget

These are budgets for implementation review, measured with production builds and representative fixture routes.

| Area | Phase-2 target / safeguard |
|---|---|
| Initial shell | At most 180 KiB gzip JS and 35 KiB gzip CSS before a primary chart/view-specific lazy chunk |
| First usable primary view | At most 300 KiB gzip total JS after its required chart module; no Trace/graph code |
| View chunks | Summary, Verified, and Outlook loaded on demand; target each additional view at or below 120 KiB gzip |
| Trace | Separate lazy chunk, target at or below 150 KiB gzip; never initialized on default load |
| Public fixture/payload | Target at or below 200 KiB uncompressed / 50 KiB gzip for the Phase-2 fixture; paginate/defer bounded detail rather than ship a whole graph |
| Interaction | Immediate visual acknowledgement; representative interaction INP at or below 200 ms; avoid main-thread tasks over 50 ms during interaction |
| Motion | Visually stable 60 Hz target; transform/opacity; shorten/remove nonessential motion under pressure |
| Mobile | Test constrained width and 4× CPU slowdown; reduce simultaneous labels/series and lazy-load inspectors/tables rather than removing provenance |

Budgets are gates, not promises for unbuilt code. A justified exception requires measurement, a recorded risk, and an offsetting plan; it may not enable a whole-economy graph.

## 12. Phase-2 testing plan

No tests are implemented in this drafting phase.

| Layer | Required coverage |
|---|---|
| Route/unit | defaults/canonical order and elision; every parameter validator; unknown keys; invalid path truncation; dependent horizon/scenario/geography/range; share URL |
| Navigation/component | Summary/Verified/Outlook switching; direct load; refresh; back/forward; persistent context; `10 -> 10 -> 10`; breadcrumbs; View All; search selection |
| Data semantics | `publicationClass` fixture banner/export block; absence of public `isFixture`; `OBS/CALC/FCST/SCEN`; provenance and all timing dimensions; cadence-aware current/delayed/stale |
| View states | loading; source delayed/stale; insufficient evidence; forecast unavailable; disagreement; partial payload; snapshot unavailable; no fabricated fallback conclusion |
| Accessibility | keyboard/focus order and restoration; visible focus; chart summary/table and keyboard path; non-color encodings; semantic controls; automated WCAG checks; 200%/400% zoom; representative screen readers |
| Comprehension/usability | With representative users, record task completion, errors, abandoned drill-downs, source/evidence inspection success, hierarchy-navigation success, information-state misunderstandings, and forecast/uncertainty misunderstandings. Confirm users can identify state, period, source, forecast-change attribution when present, evidence/uncertainty meaning, reversal conditions, direct-versus-modeled relationships, hierarchy return, and rank-10/11 near-tie meaning. Manual evidence is sufficient; no production analytics service is required. |
| Motion/input | reduced motion; no trace autoplay; hover/tap/keyboard equivalence; brush/range alternatives; Trace pause/step/select and text equivalent |
| Responsive | desktop/tablet/mobile compositions, system rail adaptations, inspector drawer/sheet, touch targets, density reduction, no page overflow |
| Performance | production chunk budgets, lazy-view/chart/Trace loading, payload budget, long tasks, representative mobile interaction and animation |
| Isolation/regression | scoped selectors/portals; no Patch Feed DOM/style/event changes; existing AUXSAYS navigation remains functional |
| Pages composition | `/systems-monitor/` base/path under a static server; direct query load and refresh; hashed manifest references; no missing assets; clean rebuild removes stale output |

## 13. Risks and conflicts

No conflict with a BINDING Foundation contract and no Public Data Interface schema gap was found. O-001C/O-001D and both Phase-2 contracts are Taylor-approved. Chart accessibility and bundle performance remain exact-install/implementation proof obligations even after selecting Recharts. Final font selection remains open and is not needed to begin the scoped UI shell. Phase-3 ingestion/data/model work remains unauthorized.
