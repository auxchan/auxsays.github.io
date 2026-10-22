# Phase-2 Dependency Verification

Verified 2026-08-17 for `systems-monitor/app/` on Node `24.16.0` and npm `11.13.0`.

## Production dependencies

| Package | Exact version | Purpose | License | Result |
|---|---:|---|---|---|
| React | 19.2.8 | Component/runtime model | MIT | PASS |
| React DOM | 19.2.8 | Browser renderer | MIT | PASS |
| React Is | 19.2.8 | Required Recharts peer compatibility | MIT | PASS |
| Recharts | 3.10.1 | Accessible analytical chart rendering | MIT | PASS with explicit HTML controls/table equivalence |

- Registry metadata and the installed lock graph were checked before/after installation.
- `npm audit --json` and `npm audit --omit=dev --json`: zero known vulnerabilities.
- Production lock inventory: 44 unique package/version records; all licenses are approved permissive SPDX expressions. See `DEPENDENCY_LICENSE_INVENTORY.json`.
- React/Recharts peer ranges resolve without invalid or unmet peers (`npm ls --depth=0`).
- No premium/commercial feature is required.
- Graphology, Sigma, and a motion library were not installed.

## Recharts O-002 proof

- Accessibility layer: Recharts 3 enables it by default; the implementation also sets `accessibilityLayer` explicitly.
- Keyboard/touch: native point-selection buttons expose every material point independently of the SVG; the generated chart accessibility layer is supplemental.
- Screen readers: title, description, live selected value, point controls, and complete table are available without relying on the chart's application-mode support. Manual assistive-technology review remains required.
- Responsive: Recharts' responsive chart mode is used inside bounded product containers.
- Reference/annotation: `ReferenceLine` marks the current fixture boundary.
- Dark theme: chart colors use scoped `--aux-sm-*` tokens.
- Bundle: production output measured at 183,867 gzip bytes across all eight application assets, below the 368,640-byte gzip gate.
- Maintenance/status: 3.10.1 was the current stable npm release at verification time and supports React 19 and the installed Node runtime.

Authoritative upstream references used for the interaction review:

- <https://github.com/recharts/recharts/wiki/Recharts-and-accessibility>
- <https://recharts.github.io/en-US/api/AreaChart/>
- <https://recharts.github.io/en-US/api/ResponsiveContainer/>
- <https://recharts.github.io/en-US/api/ReferenceLine/>
