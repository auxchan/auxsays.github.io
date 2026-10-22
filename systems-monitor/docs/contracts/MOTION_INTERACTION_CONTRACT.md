# Systems Monitor Motion/Interaction Contract

```text
Contract: Systems Monitor Motion/Interaction Contract
Version: 1.0.0
Status: BINDING
Parent Master Spec: V4.1
Depends On: Product 1.0.0; UI/UX 1.0.0 BINDING; Release Acceptance 1.0.1
Supersedes: None
Approved By: Taylor
Approved At: 2026-08-17
Content Hash: 5B4EB9039259333E269B974B72107765A2E47F268A2E77A9BA490925E5E0548F
Last Updated: 2026-08-17
```

## Authority / Status

Governing Master sections: §46–52, §56–58, §61, §63, and §69. This BINDING contract is Taylor-approved Phase-2 interaction authority. It permits only subsequently scoped UI-shell implementation; dependency installation remains subject to exact-version verification and task authority.

## Purpose and scope

Define a shared interaction grammar that supports comprehension, hierarchy, evidence inspection, and causal reading across Summary, Verified Data, Outlook, and focused Trace Mode. It does not prescribe decorative animation per component.

## Motion classes

| Class | Nominal duration | Intent |
|---|---:|---|
| Micro feedback | 80–140 ms | Press, toggle, focus acknowledgement, immediate status response |
| Hover | 120–180 ms | Pointer emphasis without moving layout |
| Selection | 180–260 ms | Row, node, series, or state selection |
| Layout reconfiguration | 240–360 ms | Bounded card/module or hierarchy rearrangement |
| Inspector transition | 260–360 ms | Drawer, sheet, or evidence-panel entry/exit |
| View transition | 320–500 ms | Summary / Verified Data / Outlook mode change |
| Causal trace | 700–1500 ms total | Bounded sequential path explanation; user-controllable |

- **BINDING REQUIREMENT MI-001:** Durations may be tuned within these classes, but interaction response is immediate and motion never blocks input, reading, or cancellation.
- **BINDING REQUIREMENT MI-002:** Default easing is restrained: ease-out for entry/selection, ease-in for exit, and smooth symmetric easing for short spatial continuity. Spring/overshoot behavior is prohibited where it could imply volatility, certainty, or gamification.

## Hover, focus, and selection

- **BINDING REQUIREMENT MI-003:** Cards/modules use minimal surface/line emphasis; no elevation jump or gratuitous glow. Focus is at least as visible as hover.
- **BINDING REQUIREMENT MI-004:** Top-10 rows and forecast items emphasize label, rank/context, and the relevant series/path together. Selection persists independently of pointer position and exposes the same detail by keyboard/touch.
- **BINDING REQUIREMENT MI-004A:** Top-10 hover, focus, or pinned detail exposes when available: current value, direction/change, rank/prior-rank state, freshness, and source/evidence quality, including supported near-tie/near-cutoff meaning.
- **BINDING REQUIREMENT MI-004B:** Predictive-item hover, focus, or pinned detail exposes when available: forecast horizon, prediction interval/range, calibrated directional probability only when genuinely supplied, model-skill/relationship-evidence summary, strongest positive pressure, and strongest negative or offsetting pressure.
- **BINDING REQUIREMENT MI-005:** Chart hover/focus reveals the nearest supported datum, crosshair/marker, state label, value/unit, and timing/provenance entry. Keyboard focus and tap can pin the same content; leaving hover does not erase a pinned selection.
- **BINDING REQUIREMENT MI-006:** Causal nodes emphasize immediate connected edges and dim unrelated nodes to a readable minimum. Source/evidence controls use explicit focus/selected states and never encode trust solely by glow, motion, or color.
- **BINDING REQUIREMENT MI-007:** No critical value, provenance, uncertainty, relationship, or action exists only on pointer hover.

## Hierarchy transitions

- **BINDING REQUIREMENT MI-008:** A drill transition follows the comprehension sequence: selected item becomes the context anchor; children resolve; breadcrumb advances. Where practical, the selected label maintains spatial continuity while surrounding content fades/repositions.
- **BINDING REQUIREMENT MI-009:** Back/up reverses context coherently without requiring a literal reverse animation. Focus returns to the initiating item or the nearest stable equivalent, and loading never animates invented children.
- **BINDING REQUIREMENT MI-010:** View All and search-result navigation preserve hierarchy context. Large list changes use bounded cross-fades or direct replacement, not continuous animation of every row.

## Primary-view transitions

- **BINDING REQUIREMENT MI-011:** Summary, Verified Data, and Outlook transition as modes in one shell: shell, mode switcher, selected context, breadcrumbs, fixture state, and health treatment remain stable; only the analytical region changes.
- **BINDING REQUIREMENT MI-012:** Shared elements may preserve the selected system/series identity, but false morphing between semantically different observed and forecast marks is prohibited. `OBS`, `CALC`, `FCST`, and `SCEN` labels update before or with the content they qualify.
- **BINDING REQUIREMENT MI-013:** Navigation and URL state update synchronously with selection. A transition failure leaves a usable prior or explicit degraded state, not a blank intermediate page.

## Trace motion

- **BINDING REQUIREMENT MI-014:** Sequential activation may show a bounded causal path in declared direction. Edge timing may reflect ordering or recorded lag only when labeled; animation speed is not evidence strength or probability.
- **BINDING REQUIREMENT MI-015:** Evidence strength and uncertainty use explicit labels/visual encodings independent of activation timing. Competing/offsetting paths can be stepped or compared without implying that the animated-first path is dominant.
- **BINDING REQUIREMENT MI-016:** Trace playback has pause/replay/step or direct-selection control whenever sequence conveys material meaning. The full text/list explanation is available without playback.

## Performance and restraint

- **BINDING REQUIREMENT MI-017:** Prefer transform and opacity on bounded elements. Avoid recurring layout/paint animation, large-area blur, perpetual motion, gratuitous pulsing/glow, animated backgrounds, and whole-graph initialization.
- **BINDING REQUIREMENT MI-018:** Motion targets a visually stable 60 Hz experience on representative devices, avoids main-thread tasks over 50 ms during interaction, and degrades by shortening/removing nonessential transitions before reducing input responsiveness.
- **BINDING REQUIREMENT MI-019:** Loading indicators are finite, low-motion, and accompanied by text. Live data does not pulse merely because it is current; animation is reserved for an actual user action or material state change.

## Reduced motion

- **BINDING REQUIREMENT MI-020:** Under `prefers-reduced-motion: reduce`, causal autoplay is disabled; shared-element morphs, parallax, animated crosshairs, count-ups, and nonessential spatial travel are removed.
- **BINDING REQUIREMENT MI-021:** Essential changes use immediate replacement or a brief opacity change no longer than 100 ms. Focus placement, state labels, breadcrumbs, selection indicators, text summaries, and live announcements communicate every result without animation.
- **BINDING REQUIREMENT MI-022:** The initial preference is honored before first meaningful render where practical and applies to CSS and JavaScript-driven motion. A component may not override it for decoration.

## Touch and keyboard equivalence

- **BINDING REQUIREMENT MI-023:** Tap pins the detail available on hover; a separate explicit control opens deeper detail. Long-press, precision dragging, and multi-touch gestures are optional enhancements only.
- **BINDING REQUIREMENT MI-024:** Keyboard users can reach, select, dismiss, and traverse material chart, hierarchy, inspector, and trace states. Escape dismisses transient overlays; focus is restored predictably.
- **BINDING REQUIREMENT MI-025:** Drag/brush interactions provide discrete controls or inputs for the same time-range or selection outcome. Instructions are discoverable and do not depend on pointer vocabulary.

## Implementation freedom

- **IMPLEMENTATION CHOICE:** CSS transitions or an approved motion library may implement the grammar after dependency approval; component code need not share one animation primitive where native CSS is sufficient.
- **IMPLEMENTATION CHOICE:** Exact easing curves and reduced-motion opacity treatment may be tuned through usability testing within this contract.

## Acceptance criteria

1. Pointer, keyboard, and touch reach equivalent material information and actions for representative cards, Top-10 rank/boundary states, charts, forecast details, evidence elements, and Trace nodes; hover is never mandatory.
2. Drill-down, breadcrumb/back navigation, and three-mode transitions preserve context and focus with no semantic morph between information states.
3. Trace sequence never encodes unlabeled strength, probability, lag, or dominance.
4. Reduced-motion tests show no autoplay, nonessential travel, or lost meaning.
5. Representative desktop and mobile traces meet the performance budget without perpetual or whole-graph effects.
6. Loading/error interruptions leave a stable accessible state.

## Version / approval / change history

- `1.0.0` (2026-08-17): First BINDING version approved by Taylor after external review and the authorized hover/focus/pinned-detail completeness correction.
- `0.1.0` (2026-08-17): Initial Phase-2 review draft. Not approved.

Amendments follow `CONTRACT_TEMPLATE.md`; Taylor approval is required for promotion.
