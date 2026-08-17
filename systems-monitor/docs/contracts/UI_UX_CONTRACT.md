# Systems Monitor UI/UX Contract

```text
Contract: Systems Monitor UI/UX Contract
Version: 1.0.0
Status: BINDING
Parent Master Spec: V4.1
Depends On: Product 1.0.0; Repository Integration 1.0.1; Architecture 1.0.0; Public Data Interface 1.0.0; Release Acceptance 1.0.1
Supersedes: None
Approved By: Taylor
Approved At: 2026-08-17
Content Hash: 537BC054E57980F5DD1177F5C2534F89476772D82F70DF3BDD06DC3333E8CB05
Last Updated: 2026-08-17
```

## Authority / Status

Governing Master sections: §2–3, §38–59, §61, §63, §67 Phase 2, and §69, plus accepted decisions D-006, D-008, and D-009. This BINDING contract is Taylor-approved Phase-2 UI/UX authority. It permits only a subsequently scoped UI-shell implementation task; it does not authorize Phase-3 data/model work, factual public claims, or deployment by itself.

## Purpose and scope

Stabilize the public application structure, navigation, view responsibilities, state semantics, responsive and accessible behavior, and safe degraded-state presentation for the Phase-2 UI shell at `/systems-monitor/`.

Out of scope are data ingestion, production analytics or forecasts, schema expansion, a whole-economy graph, Patch Feed redesign, application implementation, and hosting/workflow changes.

## Application structure and navigation

- **BINDING REQUIREMENT UX-001:** The durable public route is `/systems-monitor/`. The application mounts in a product-scoped root within the existing AUXSAYS global shell and remains isolated from Patch Feed code, data, models, generated records, and styling.
- **BINDING REQUIREMENT UX-002:** The three and only three primary modes are Summary, Verified Data, and Outlook. A semantic mode switcher identifies the current mode and remains in a consistent shell position.
- **BINDING REQUIREMENT UX-003:** Progressive `10 -> 10 -> 10` drill-down is the primary hierarchy. Each level shows at most ten defensible ranked children, preserves the parent context, and provides View All when more defensible items exist. It never invents children to fill a list.
- **BINDING REQUIREMENT UX-004:** Breadcrumbs expose the selected hierarchy path, make prior levels directly reachable, and announce hierarchy changes to assistive technology. Back/forward restores the same canonical, shareable state under D-008.
- **BINDING REQUIREMENT UX-005:** Selected system and hierarchy path persist across primary modes when valid. Mode-specific state is retained only where meaningful and is not allowed to alter the meaning of another mode.
- **BINDING REQUIREMENT UX-006:** View All replaces the ranked subset in the same hierarchy context with a bounded, searchable/sortable list. It does not open a graph and preserves the relationship between the displayed Top 10 and nearby candidates, including supported near-tie and near-cutoff states.
- **BINDING REQUIREMENT UX-007:** Search is an exploration aid over payload-backed labels and identifiers. When present in the payload it may locate indicators, commodities, industries, occupations, companies, facilities, geographies, sources, and events. Results expose available type, hierarchy path/context, current information state, freshness, and view availability; selection navigates to a valid application state. No entity or relationship may be invented, and search is not a substitute for hierarchy navigation.
- **BINDING REQUIREMENT UX-008:** A focused Trace Mode may explain a selected path. A giant all-economy graph is never the landing state or default interaction.

The shared shell contains the AUXSAYS/global relationship, product title, primary-mode switcher, persistent context/breadcrumbs, data-state and fixture treatment, system health, and view content. Systems Monitor does not replace or intercept Patch Feed navigation.

## View contracts

### Summary

- **BINDING REQUIREMENT UX-009:** Information priority is: selected context and current-state label; primary system/state visualization; concise KPIs with provenance state; movers/events/context; human-capital preview; then source health and supporting detail.
- **BINDING REQUIREMENT UX-010:** A core-system rail presents the top-level systems and selection state without becoming a generic dashboard menu. The primary visualization receives the largest analytical region; compact modules support rather than compete with it.
- **BINDING REQUIREMENT UX-011:** KPI and context modules identify `OBS`, `CALC`, `FCST`, or `SCEN`, their as-of meaning, and whether the publication is fixture. Current-state and forecast values are never visually blended.
- **BINDING REQUIREMENT UX-012:** Movers/events describe only payload-supported changes with source/evidence access. Human-capital preview is a bounded entry into an occupation context, not a claim-generating recommendation panel.
- **BINDING REQUIREMENT UX-013:** Source-health visibility is concise at overview level and opens evidence detail without forcing users to infer health from color alone.
- **BINDING REQUIREMENT UX-051:** Where supported, Summary includes a bounded market-share/demand-redistribution preview and names the declared measure type. Final-demand allocation share, industry/output share, company market share, and constrained-resource allocation share may not be collapsed into generic “market share.”

### Verified Data

- **BINDING REQUIREMENT UX-014:** Verified Data is evidence-first: selected series/context and historical chart; data-state/as-of summary; source inspector; then tabular/raw/export affordances allowed by the payload and rights metadata.
- **BINDING REQUIREMENT UX-015:** The source inspector distinguishes provider/source, observation time, source publication time, retrieval time, revision/vintage, system evaluation time, snapshot generation/publication time, next expected release when known, rights/provenance, and cadence-aware freshness.
- **BINDING REQUIREMENT UX-016:** `OBS` and `CALC` remain explicit at the datum and series level. Calculated values expose calculation/method references available in the public payload; Verified Data never promotes `FCST` or `SCEN` as verified observation.
- **BINDING REQUIREMENT UX-017:** Geography controls appear only for payload-supported comparable geographies and include clear scope. Changing geography updates the canonical state and prevents invalid comparisons.
- **BINDING REQUIREMENT UX-018:** Raw/table/export access is read-only, uses the approved public payload, honors disclosure/rights fields, and does not expose internal storage shapes, secrets, unpublished records, or unsupported bulk export.

### Outlook

- **BINDING REQUIREMENT UX-019:** Outlook identifies selected horizon and baseline/scenario state before presenting forecasts. Its hierarchy prioritizes industry ranking, occupation ranking, forecast inspector, pressures, intervals, model-skill/evidence, and reasoning access.
- **BINDING REQUIREMENT UX-052:** When an applicable predictive payload exists, Outlook visibly offers the three required primary semantic horizons: Current Year (`current-year`), Next Year (`next-year`), and +3 Years (`plus-3-years`) or contract-equivalent stable identities. Displayed calendar years derive from the governing snapshot/forecast time semantics and are never permanently hard-coded. Additional future approved horizons may supplement but may not replace these three without a Master amendment.
- **BINDING REQUIREMENT UX-020:** Every forecast item identifies `FCST` or `SCEN`, horizon, forecast origin/as-of, prediction interval where available, evidence and model-skill dimensions, and freshness. A range is not labeled as a calibrated probability unless the approved payload says so.
- **BINDING REQUIREMENT UX-021:** Positive and negative pressures are separate, source-backed factors; visual prominence does not imply causal certainty. High disagreement is a first-class state, not averaged away.
- **BINDING REQUIREMENT UX-022:** Scenario controls change only approved scenario assumptions, label resulting outputs `SCEN`, and provide a clear return to baseline. Scenario output never becomes observed history or baseline forecast input silently.
- **BINDING REQUIREMENT UX-023:** “What would change our mind?” lists payload-backed sensitivities, invalidation conditions, or missing evidence. It must not fabricate thresholds. Trace/reasoning opens a focused explanation for the current selection.
- **BINDING REQUIREMENT UX-053:** Outlook industry ranking means industries expected to require the most human capital for the selected horizon. Occupation ranking means occupations expected to generate the largest number of actual hiring opportunities/openings for that horizon. Neither ranking automatically means fastest percentage growth, highest wage, largest occupation, or largest current workforce.
- **BINDING REQUIREMENT UX-054:** Where supported, Outlook provides an explicit demand/market redistribution region or inspector entry and labels the declared allocation/share type rather than generically calling every measure “market share.”
- **BINDING REQUIREMENT UX-055:** For each material forecast, the UI reserves and presents when available: forecast/range, data coverage, relationship evidence, historical model skill, regime stability, positive pressures, offsets, source support, measured-versus-modeled relationships, active scenario/assumptions, what would change our mind, and prior-forecast change attribution. Missing dimensions are labeled unavailable or omitted, never fabricated.

### Focused Trace Mode

- **BINDING REQUIREMENT UX-024:** Trace begins with a selected cause, outcome, or forecast and displays only a bounded relevant path plus immediate alternatives. The Phase-2 fixture target is no more than 12 visible nodes and 16 visible edges; expansion remains explicit and bounded.
- **BINDING REQUIREMENT UX-025:** Selecting or focusing a node emphasizes immediate connected edges and dims unrelated nodes without hiding their existence. The inspector names relationship type, direction, lag/range, evidence strength, provenance, and information state.
- **BINDING REQUIREMENT UX-026:** Competing and offsetting paths are visually and textually distinct. Directional arrows, labels, and summaries supplement color. Layout and motion may aid reading but must not imply unrecorded causality or certainty.
- **BINDING REQUIREMENT UX-027:** Trace always offers a text/list equivalent and a route back to the originating view and hierarchy context. Unsupported or oversized paths degrade to a bounded list, not an all-economy graph.
- **BINDING REQUIREMENT UX-056:** Trace and evidence inspectors faithfully expose the approved relationship evidence/method class—such as Direct, Statistical, Modeled, or Hypothesis, or later contract-approved equivalents. They may not collapse distinct classes into one generic causal-looking edge.

## Data-state, fixture, and liveness presentation

- **BINDING REQUIREMENT UX-028:** `OBS`, `CALC`, `FCST`, and `SCEN` use persistent text labels, distinct semantic tokens, and shape/icon or pattern reinforcement. Color is supplementary. Direction and desirability are separate from information state.
- **BINDING REQUIREMENT UX-029:** `snapshot.publicationClass` from the BINDING Public Data Interface is the sole public fixture/factual discriminant. `fixture` produces an always-visible “SYNTHETIC TEST DATA — NOT A PUBLIC CLAIM” banner at app and export boundaries. No independent public `isFixture` field is permitted.
- **BINDING REQUIREMENT UX-030:** The liveness treatment can state: current system state; evaluated time; source-relative current/delayed/stale counts; new observations; material state changes; and next expected release. Unknown values are labeled unknown or omitted, never guessed.
- **BINDING REQUIREMENT UX-031:** D-009’s four-hour maximum is an MVP system-evaluation heartbeat, not a universal source freshness promise. Source health is assessed against declared cadence and expected release. An unchanged monthly series remains current until its release expectation or source-specific policy is exceeded.
- **BINDING REQUIREMENT UX-032:** Observation, publication, retrieval, evaluation, generation, and snapshot publication timestamps retain their distinct labels and semantics wherever shown. A concise overview may summarize them but the inspector must expose the available distinctions.

## Responsive behavior

- **BINDING REQUIREMENT UX-033:** Desktop uses a persistent or sticky system rail, wide primary visualization, and adjacent inspector only when space supports both. Tablet converts the rail to a compact horizontal selector or sheet and uses one dominant analytical column. Mobile uses a semantic mode selector, collapsible context header, stacked content, and bottom sheet/full-screen inspector.
- **BINDING REQUIREMENT UX-034:** Charts change composition rather than merely scale: fewer simultaneous labels, touch-sized targets, scrollable tables instead of compressed columns, text summaries, and optional simplified series. Analytical meaning and state labels remain intact.
- **BINDING REQUIREMENT UX-035:** On touch, tap/selection and explicit detail controls replace hover; long-press is not required. Density reduction removes secondary decoration and defers detail without hiding critical provenance, uncertainty, fixture, or degraded-state information.
- **BINDING REQUIREMENT UX-036:** Breakpoints are implementation choices tested by layout behavior, not device names. No supported width may require horizontal page scrolling; intentionally scrollable tables/charts must be labeled and keyboard operable.

## Accessibility

- **BINDING REQUIREMENT UX-037:** Landmarks, headings, lists, tables, buttons, tabs/radiogroups where appropriate, and form labels use native semantics first. Focus order follows visual/read order; focus is never trapped except in a correctly implemented modal inspector.
- **BINDING REQUIREMENT UX-038:** Every interactive element is keyboard reachable with a visible high-contrast focus indicator. Mode switching, hierarchy rows, breadcrumbs, charts, inspectors, View All, and Trace have documented keyboard operation and preserve or deliberately move focus after state changes.
- **BINDING REQUIREMENT UX-039:** Charts provide a concise title/description, current selection summary, keyboard-operable data access where feasible, and an equivalent table or structured list for material values. Critical information never exists only in hover, color, animation, or spatial position.
- **BINDING REQUIREMENT UX-040:** Text and meaningful non-text contrast target WCAG 2.2 AA. Status and direction combine text with non-color cues. Controls meet practical touch-target sizing, zoom/reflow remains usable, and live announcements are concise and non-repetitive.
- **BINDING REQUIREMENT UX-041:** Reduced-motion behavior follows the Motion/Interaction Contract. Accessibility is validated with keyboard, high zoom/reflow, automated checks, and representative screen-reader paths before approval.

## Loading, error, and degraded states

- **BINDING REQUIREMENT UX-042:** Loading uses stable layout placeholders and a named status; it does not present placeholder numbers. Existing valid content may remain visible during a refresh with an explicit updating state.
- **BINDING REQUIREMENT UX-043:** Source delayed and source stale are distinct, cadence-aware states. Insufficient evidence, forecast unavailable, and high model disagreement suppress unsupported conclusions and provide the reason/evidence state available from the payload.
- **BINDING REQUIREMENT UX-044:** A partial payload identifies unavailable modules while preserving valid ones and provenance. Snapshot unavailable provides a bounded retry/last-valid-snapshot message without inventing substitute claims.
- **BINDING REQUIREMENT UX-045:** Fixture state is persistent and release-blocking. Error and empty states include a clear next action only when that action is real; they never manufacture fallback rankings, relationships, or forecasts.

## Design-token and style-isolation contract

- **BINDING REQUIREMENT UX-046:** All product tokens are namespaced under a dedicated Systems Monitor root (proposed selector `[data-aux-product="systems-monitor"]` and `--aux-sm-*` custom properties). Component styles are locally scoped; resets and typography rules may not target global elements outside that root.
- **BINDING REQUIREMENT UX-047:** The palette uses graphite/deep-navy surfaces, neutral high-contrast text, restrained cyan/teal analytical accents, and semantic status colors. Surface, line, text, chart-series, state, focus, and health tokens remain separate so theme changes do not change meaning.
- **BINDING REQUIREMENT UX-048:** Token roles include: surface levels; primary/secondary/muted text; subtle/strong borders; typography roles for display, section, body, label, numeric, and code/provenance; a `4, 8, 12, 16, 24, 32, 48` spacing scale; restrained `0, 4, 8, 12` radii; and explicit focus, overlay, and chart tokens.
- **BINDING REQUIREMENT UX-049:** Z layers are finite and documented: base content, sticky navigation, popover/tooltip, inspector/sheet, modal, and toast. Components consume semantic layer tokens rather than arbitrary large values.
- **BINDING REQUIREMENT UX-050:** Chart hierarchy prioritizes selected series/path, then comparison/context, interval/uncertainty, grid/reference, and annotation. Patterns, line styles, markers, and labels reinforce color. Styling avoids neon overload, gratuitous glass, giant rounded-card walls, retro CRT treatment, and generic admin-dashboard composition.

## Ranking stability and boundary transparency

- **BINDING REQUIREMENT UX-057:** Top-10 presentation must not imply that adjacent ranks are meaningfully different when the supplied analytical evidence says they are indistinguishable. Supported near ties, near-cutoff state, prior rank, and rank change are communicated explicitly.
- **BINDING REQUIREMENT UX-058:** Genuine material rank changes must not be visually hidden to manufacture cosmetic stability. View All preserves boundary context between the displayed Top 10 and nearby candidates.
- **BINDING REQUIREMENT UX-059:** Ranking hysteresis/stability computation belongs to the analytical producer unless a later approved contract explicitly assigns it elsewhere. The frontend consumes and faithfully presents `rankState`, `nearTie`, `nearCutoff`, `priorRank`, or equivalent approved public-payload semantics; it does not invent production ranking logic.

## Implementation freedom

- **IMPLEMENTATION CHOICE:** Exact breakpoints, token values within the approved visual direction, component state library, and responsive chart label algorithms may be chosen during authorized implementation.
- **IMPLEMENTATION CHOICE:** A system rail may become a select, tabs, or sheet at constrained widths if semantics, context, and test criteria remain intact.
- **IMPLEMENTATION CHOICE:** Inspector may be inline, drawer, or sheet by available space, with one consistent semantic content model.

## Acceptance criteria

1. The three modes, hierarchy, breadcrumbs, context persistence, View All, search, direct loads, refresh, and back/forward meet the canonical routing design.
2. Summary, Verified Data, Outlook, and Trace satisfy their information and evidence boundaries with a contract-valid fixture.
3. `OBS`, `CALC`, `FCST`, `SCEN`, fixture state, timing dimensions, degraded states, and source-aware freshness are distinct in visual and assistive output.
4. Desktop, tablet, and mobile compositions pass defined responsive cases without hiding evidence or uncertainty.
5. Keyboard, focus, chart alternative, contrast, touch equivalence, and reduced-motion tests pass.
6. Systems Monitor styles and events do not alter Patch Feed or unrelated AUXSAYS pages.
7. Representative fixture-UI comprehension testing records task completion, user errors, abandoned drill-downs, source/evidence inspection success, hierarchy-navigation success, information-state misunderstandings, and forecast/uncertainty misunderstandings. Users must be able to identify information state, represented period, source, forecast-change attribution when present, uncertainty/evidence meaning, reversal conditions, direct-versus-modeled relationships, hierarchy return, and whether ranks 10/11 are materially different or effectively tied when supplied evidence says they are indistinguishable.
8. No production dependency, application/Jekyll/workflow change, public claim, or deployment occurs outside a separately scoped implementation/release task and its required verification.

## Risks / approved decisions

- **APPROVED DECISION O-001C — Taylor, 2026-08-17:** Systems Monitor owns uncommitted, content-hashed generated output and the bounded manifest-aware Jekyll composition paths recorded in `DECISIONS.md`.
- **APPROVED DECISION O-001D — Taylor, 2026-08-17:** retain one Pages build job and one Jekyll artifact with package-local pre-Jekyll build/composition and post-Jekyll validation when implementation is separately authorized.
- Final font files and self-hosting/subsetting remain implementation-time dependency/licensing work.
- No Public Data Interface amendment was found necessary for this draft; focused-trace and test-variant metadata fit namespaced `extensions` and existing public records.

## Version / approval / change history

- `1.0.0` (2026-08-17): First BINDING version approved by Taylor after external review and the authorized horizon, ranking, comprehension, fixture-envelope, product-semantic, search, and interaction corrections.
- `0.1.0` (2026-08-17): Initial Phase-2 review draft. Not approved.

Amendments follow `CONTRACT_TEMPLATE.md`; Taylor approval is required for promotion or any change that conflicts with a BINDING Foundation contract.
