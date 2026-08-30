# Phase-2 Dependency and License Candidate Review

- Review date: 2026-08-17
- Scope: Foundation-level candidate screening only; no dependency is installed or approved by this document.
- Requirement: Exact versions, transitive licenses, security advisories, maintenance state, browser support, bundle impact, and lockfile must be rechecked when Phase 2 selects dependencies.

| Candidate | Intended Phase-2 role | Upstream license | Foundation disposition |
|---|---|---|---|
| React | Isolated Systems Monitor UI | MIT | Viable candidate; Master-preferred application model. |
| TypeScript | Public payload and component types | Apache-2.0 | Viable candidate. Preserve strict public/internal type boundaries. |
| Vite | Static frontend build | MIT | Viable candidate. Its build license inventory feature should be evaluated for distributable attributions. |
| Motion for React | State/continuity motion | MIT | Viable candidate. Open-source package only; Motion+ is not required or authorized. |
| Vitest | Unit/schema/interaction tests | MIT (bundled dependency notices include permissive licenses) | Viable candidate; exact Node/Vite compatibility must be pinned. |
| React Testing Library | Accessible behavior tests | MIT | Viable candidate. |
| Recharts | General chart candidate | MIT | Evaluation candidate only; keyboard access, chart summaries, SSR/static behavior, interaction protocol, and bundle size need a proof. |
| Graphology | Focused trace graph data model | MIT | Compatible, but specialized Trace Mode is not required for the initial Phase-2 shell. Defer installation until needed. |
| Sigma.js | WebGL focused trace rendering | MIT | Compatible, but not a default dashboard dependency. Defer until a trace-mode scale/performance proof justifies it. |
| IBM Plex Sans / Mono / Sans Condensed | Typography candidate | SIL Open Font License 1.1 | Viable candidate; retain license text and evaluate self-hosting/subsetting terms. |
| Inter | Body typography alternative | SIL Open Font License 1.1; “Inter” is a Reserved Font Name | Viable candidate; modifications/subsetting must respect reserved-name terms. |
| Barlow | Display alternative | SIL Open Font License | Viable candidate; IBM Plex may reduce font-family count. |

## Primary verification links

- [React license](https://github.com/facebook/react/blob/master/LICENSE)
- [TypeScript repository/license](https://github.com/microsoft/TypeScript)
- [Vite repository/license](https://github.com/vitejs/vite)
- [Vite generated dependency-license documentation](https://github.com/vitejs/vite/blob/main/docs/guide/features.md#license)
- [Motion repository/license](https://github.com/motiondivision/motion)
- [Vitest core license](https://github.com/vitest-dev/vitest/blob/main/packages/vitest/LICENSE.md)
- [React Testing Library repository/license](https://github.com/testing-library/react-testing-library)
- [Recharts license](https://github.com/recharts/recharts/blob/main/LICENSE)
- [Graphology license](https://github.com/graphology/graphology/blob/master/LICENSE.txt)
- [Sigma.js license](https://github.com/jacomyal/sigma.js/blob/main/LICENSE.txt)
- [IBM Plex repository/license](https://github.com/IBM/plex)
- [Inter repository/license](https://github.com/rsms/inter)
- [Barlow repository/license](https://github.com/jpt/barlow)

## Required Phase-2 controls

1. Select the smallest necessary dependency set; do not install Graphology/Sigma merely because future Trace Mode exists.
2. Pin supported Node and package versions and commit one lockfile.
3. Generate and retain a production dependency/license inventory.
4. Self-host approved font assets where practical; preserve required license notices and provenance.
5. Run dependency/security scanning and verify no premium/private API is implicitly required.
6. Treat chart-library selection as open until the accessibility and interaction proof passes.

This review is engineering due diligence, not legal advice.

