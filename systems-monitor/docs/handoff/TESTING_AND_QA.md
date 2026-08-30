# Testing and QA

Fresh handoff validation:

- Python data suite: 236 tests PASS.
- UI suite: 216/217 PASS in the full run; one asynchronous shell test timed out under suite load.
- The exact failed shell test passed in isolation immediately afterward (1 PASS, 13 skipped).
- The failure is recorded as timing-sensitive/flaky, not hidden as a clean full-suite pass.

Primary commands:

```text
cd systems-monitor/data
python -m unittest discover -s tests -p "test_*.py"

cd systems-monitor/app
npm test
npm run typecheck
npm run build
```

Human QA boundaries: Phase-3 Data QA PASS; Phase-4A QA PASS; node-title cleanup PASS only for label/value separation. Persistent-world production integration, accepted structural motion, and Gate B remain pending. Preserve fixture-leakage, topology-fingerprint, exact-ten, replay, source-rights, atomic publication, reduced-motion, and accessibility regressions.
