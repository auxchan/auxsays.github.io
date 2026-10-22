# Repository Integration Contract

```text
Contract: Systems Monitor Repository Integration Contract
Version: 1.0.1
Status: BINDING
Parent Master Spec: V4.1
Depends On: PRODUCT_CONTRACT.md
Supersedes: None
Approved By: Taylor
Approved At: 2026-08-17
Content Hash: 0AB85F8F5869430F80A0782EAF84F40E1D8E8C45E1CE974F09904C7EFD7FEA92
Last Updated: 2026-08-17
```

## Authority / Status

Governing Master sections: §0.2–0.3, §35.1–35.3, §38.1–38.2, §39, §60, §64.2–64.12, §66–67, §69. This BINDING contract carries accepted D-007/D-008 repository and routing baselines. Taylor approved O-001C/O-001D and the BINDING Phase-2 UI/Motion contracts on 2026-08-17; actual package, Jekyll, and workflow changes still require a scoped implementation task.

## Purpose

Define the smallest safe integration between the existing Jekyll/GitHub Pages repository and the future isolated Systems Monitor application.

## Scope

- Repository-root product ownership under `systems-monitor/`, beginning with `systems-monitor/docs/`.
- Future Jekyll-served route at `auxsays/systems-monitor/` producing `/systems-monitor/`.
- Future isolated React/TypeScript source/build integration, global-shell attachment, static assets, routing, and cross-platform rules.

## Explicitly Out of Scope

- Creating the Jekyll page, React package/router, assets, workflow steps, or navigation item in Phase 1.
- Changing Patch Feed files, generated/state files, or existing automation.
- Choosing analytics infrastructure or internal data schemas.

## Binding Requirements / Invariants

- **BINDING REQUIREMENT RI-001:** Existing AUXSAYS/Patch Feed behavior must remain unchanged except for narrowly approved shared-shell integration in a later phase.
- **BINDING REQUIREMENT RI-002:** `/systems-monitor/` must be a real static-hosted route that survives direct navigation and refresh.
- **BINDING REQUIREMENT RI-003:** Supported app state must preserve browser back/forward and shareable deep links without assuming server SPA rewrites.
- **BINDING REQUIREMENT RI-004:** Durable state uses validated, canonically serialized query parameters on `/systems-monitor/` unless a future approved contract amendment changes the strategy. Expected keys include `view`, `system`, `path`, `horizon`, and `scenario`; unknown/invalid values fail to safe defaults.
- **BINDING REQUIREMENT RI-005:** Client-only pathnames such as `/systems-monitor/verified/...` must not be advertised unless real static files or a proven Pages-compatible mapping exist.
- **BINDING REQUIREMENT RI-006:** Do not install a site-wide 404-to-SPA workaround that changes unrelated AUXSAYS behavior.
- **BINDING REQUIREMENT RI-007:** Application and asset base paths must work at the custom domain and in Pages CI; no workstation-absolute paths.
- **BINDING REQUIREMENT RI-008:** Use repo-relative, platform-safe path operations, UTF-8, pinned supported runtimes, one committed lockfile, and Linux-CI validation.
- **BINDING REQUIREMENT RI-009:** Systems Monitor CSS/DOM behavior must be scoped to a dedicated root; avoid leaking rules into Patch Feed/global pages.
- **BINDING REQUIREMENT RI-010:** Build outputs, dependency notices, and Jekyll processing behavior must be explicit and reproducible.
- **BINDING REQUIREMENT RI-011:** No generated/status/transient Patch Feed artifact may be included merely because validation created it.
- **BINDING REQUIREMENT RI-012:** `.github/workflows/pages.yml` is unchanged during Phase 1; later changes require explicit approved scope and Patch Feed regression validation.

## Static routing contract

Canonical examples:

```text
/systems-monitor/
/systems-monitor/?view=verified&system=employer-labor-demand&path=job-openings
/systems-monitor/?view=outlook&system=labor-supply&horizon=next-year
```

- The physical Jekyll entry remains `/systems-monitor/index.html`.
- The router parses an allowlisted query schema and serializes canonical ordering/encoding.
- `history.pushState`/`replaceState` may update query state on the same pathname; `popstate` restores it.
- Missing/invalid query state resolves to Summary without throwing or redirect loops.
- Static asset URLs use a build-controlled `/systems-monitor/` base or a Jekyll-injected manifest resolved through `relative_url`.
- The existing site 404 remains the fallback for unsupported physical paths.

## Interfaces / Dependencies

- Product Contract controls route and product/UX identity.
- Architecture defines source/module ownership.
- Infrastructure/Public Data contracts define public payload location independently of Jekyll source files.
- Future UI/Motion contracts own component, accessibility, responsive, and interaction behavior.
- Existing repo instructions continue to govern Patch Feed areas and shared deployment safety where not product-specific.

## Allowed Implementation Freedom

- **IMPLEMENTATION CHOICE:** O-001A is RESOLVED: the isolated React/TypeScript package location is `systems-monitor/app/`.
- **IMPLEMENTATION CHOICE:** O-001B is RESOLVED: use npm with one committed package-local `systems-monitor/app/package-lock.json` and package-local `npm ci` in future CI.
- **IMPLEMENTATION CHOICE:** Asset manifest injection or fixed hashed asset directory may be used after build proof.
- **IMPLEMENTATION CHOICE:** A later approved contract may generate selected real static deep pages, but query-state support remains the baseline.

## Prohibited Behavior

- Broad Jekyll/theme rewrite, path routing that works only in-app, hardcoded `D:\` paths, unpinned dependencies, or committed build/transient output without ownership rules.
- Adding React dependencies to the existing site-tools package by convenience without an explicit package-boundary decision.

## Failure / Degraded States

- Invalid query values produce a safe default state and optional non-blocking notice.
- Missing JS may show an honest static loading/error shell rather than false data.
- Build failure prevents deployment; it must not publish a partial monitor while replacing a valid site artifact.

## Acceptance Criteria

1. Direct `/systems-monitor/` navigation, refresh, back/forward, canonical query links, invalid state, assets, and existing 404 behavior are covered by Phase-2 tests.
2. Jekyll build and existing Patch Feed QA pass in Linux CI after future integration.
3. No global style/script regression is observed on existing core routes.
4. Dependency lockfile and license inventory are present for the selected package.
5. Phase-1 artifact check finds no UI/workflow/Patch Feed changes.

## Risks / Resolved Decisions

- O-001A/O-001B are RESOLVED engineering choices. O-001C/O-001D are ACCEPTED/RESOLVED by Taylor: uncommitted Systems-Monitor-owned hashed staging and bounded manifest-aware Jekyll composition feed the existing single Pages/Jekyll artifact, with fail-before-upload behavior and scoped cleanup.
- O-002 is RESOLVED to the Recharts family. Before installation/merge, the exact selected version must pass license, transitive dependency, advisory, React compatibility, bundle, responsive, annotation/reference, touch, dark-theme, keyboard, and representative screen-reader proof. Reopen O-002 if material requirements fail. See R-002, R-003, R-009, R-010, R-014, and R-016.

## Version / Approval / Change History

- 1.0.1 (2026-08-17): Taylor-authorized compatible BINDING amendment recording the legitimately resolved Phase-2 O-001A/O-001B/O-002 choices and Taylor approvals of O-001C/O-001D; repository/routing architecture is unchanged.
- 1.0.0 (2026-08-17): First BINDING version approved by Taylor after Phase-1 external review, including the accepted D-007/D-008 repository and routing baselines.
- 0.1.2 (2026-08-17): Recorded Taylor approval of D-008 and removed obsolete proposed-authority language without changing the reviewed routing design. Remains DRAFT pending contract promotion.
- 0.1.1 (2026-08-17): Clarified RI-004/D-008 draft authority and replaced the former combined open-decision reference with O-001A through O-001D. Remains DRAFT.
- 0.1.0 (2026-08-17): Initial Foundation draft with query-state static routing recommendation. Not approved.
