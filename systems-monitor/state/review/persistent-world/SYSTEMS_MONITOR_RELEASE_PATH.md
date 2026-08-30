# Systems Monitor Release Path

Status: **LOCAL HUMAN QA AVAILABLE / PUBLIC ACTIVATION BLOCKED**

## Current path

```text
systems-monitor/app
  npm test + typecheck + Vite build
  manifest validation + bundle measurement
  temporary manifest-owned Jekyll composition
auxsays/systems-monitor/index.html
  /systems-monitor/
GitHub Pages workflow
  npm ci → validate → Jekyll build → static verification → artifact upload
```

The persistent world is activated only in development when the hash starts
`#persistent-world`. The provider then uses the Phase-2 fixture snapshot and
ignores persisted factual/Motion-QA state. The shell shows a persistent
`TEST FIXTURE / never publishable` warning. Workstream-1A remains available at
`#workstream1a` and reads the separate factual snapshot.

Local QA URL:

`http://127.0.0.1:4174/systems-monitor/#persistent-world`

## Local QA requirements

- static world identity and fingerprint survive selection/reset/history;
- outcome + ten Master drivers appear at overview;
- exact-ten Level-2 and Level-3 navigation works by canvas and structured list;
- full-world density is explicit;
- reduced motion removes camera travel/glints;
- factual readings remain separate and reachable.

## Public blockers

- no public persistent-graph PDI extension is approved;
- Level-2 taxonomy remains candidate and Level-3 is fixture-only;
- accepted factual structural relationships remain zero;
- BEA credential/live evidence, Make handoff, common-cause proof, state
  transformation, and employment-exposure CALC remain incomplete;
- Gate B and Human QA remain open;
- public activation and deployment are not authorized.

No workflow, Patch Feed, generated record, or deployment file is changed by
this sprint.
