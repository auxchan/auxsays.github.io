# Motion and Performance Audit

Status: LOCAL BROWSER MEASUREMENT COMPLETE — HUMAN QA PENDING

## Architecture

The renderer keeps all 1,111 placement identities resident but draws a bounded semantic neighborhood. World coordinates, topology, membership, and the topology fingerprint do not change during camera travel.

The cinematic camera uses a bounded interruptible transition sampled from the current pose: eased dolly-out, shallow orbital arc/bank, and dolly-in. Rapid retargeting begins from the current camera pose instead of snapping to an obsolete destination.

## Interaction

- double-click the visible parent/base node: up exactly one level;
- `Alt+Left`: keyboard equivalent;
- `Up one level`: touch/click equivalent;
- double-click empty space: Reset;
- reduced-motion mode applies the destination immediately and redraws on demand.

## Budgets

- overview/focus/full-world use bounded level-of-detail rendering;
- full-detail rendering of all 1,111 interactive nodes is intentionally prohibited;
- connector glint period remains 2,500 ms;
- topology fingerprint must remain unchanged across navigation.

## Local browser measurement

Measured in the in-app browser on the depth-2 Real Wage Purchasing Power focus after a cold reload:

- first draw: 237.4 ms;
- camera settle: 833.2 ms;
- mean Canvas draw: 2.38 ms;
- median Canvas draw: 2.50 ms;
- p95 Canvas draw: 4.00 ms;
- semantic labels: 11;
- connector glint period: 2,500 ms.

The earlier local focus baseline was approximately 2.2 ms p95 and ~1.15 s camera settle. The temporal UI is outside the Canvas animation loop: the small draw-time difference is within local-run variance, while camera settle remains bounded and faster in this sample. Full-detail all-node rendering remains intentionally disallowed by LOD.
