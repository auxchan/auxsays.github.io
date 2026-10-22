# Gate-A evidence — PASS

Status: `GATE A = PASS`; `HUMAN_DATA_QA ROUND 2 = PASS`; `PHASE 3 DATA INTEGRITY = CLOSED`; no public activation.

## Factual slice and public boundary

- Six original-authority U.S. labor observations: payrolls 158,858 thousand,
  U-3 4.1%, participation 61.4%, initial claims 209,000, job openings 7,359
  thousand, and hires 5,348 thousand.
- Internal evidence: `internal-factual-review-model.json`.
- Pre-activation candidate targeting PDI 1.0.0:
  `factual-snapshot-candidate.json`; SHA-256
  `91AB68EB5DF12374D5D7CC81931E65AF5D95C7FFC40E2E45372A46951F5D3D66`.
  It contains no `snapshot` or `publishedAt` activation claim.
- Local activation test materialized the distinct immutable PDI snapshot
  `local-active-pdi-test-snapshot.json` at `2026-08-19T01:35:09.664540Z`;
  SHA-256 `B98EB22CE44A8B71924B8B02FBBA2D6619CF81146137D29F2C8F22EB7BF64232`.
  This was temporary local pointer evidence, not AUXSAYS.com activation.
- Public hierarchy uses `childRefs[]` plus a namespaced node registry; the UI
  derives nested children only after candidate/PDI validation.
- The earlier internal-shaped candidate falsely passed a validator that checked
  only that internal shape. Regression tests now reject it; explicit export and
  independent Python/TypeScript PDI validation guard the public boundary.
- The later SHA `0D463A...926B9B` is also superseded because it incorrectly
  copied generation time into `snapshot.publishedAt` without activation.
- Candidate payload is OBS-only; events and forecast/ranking collections are empty;
  Outlook is explicitly unavailable.
- The Round-2 factual UI exposes one exact official series ID and series-specific
  original-authority evidence link per observation, retains the generic BLS API
  only as machine-retrieval provenance, labels methodology separately, removes
  the fixture-only Outlook warning, and presents the DOL replay proof through
  progressive disclosure. Taylor approved the corrected evidence surface.

## Source, time, replay, and rights evidence

- Official BLS releases: July Employment Situation 2026-08-07 08:30 ET; June
  JOLTS 2026-08-04 10:00 ET. Publication, retrieval, and acceptance times are
  distinct in the deduplicated provenance registry.
- DOL: official PDF observation is current through week ending 2026-08-08
  (209,000); automated XML path is independently `stale`, ending 2026-07-18.
- Original DOL revision proof for week ending 2024-03-02: 217,000 advance on
  2024-03-07 → 210,000 revised on 2024-03-14. Publicly available as of
  2024-03-10 and operationally known before Release-B acceptance: 217,000;
  latest revised truth: 210,000.
- Rights tests remain fail-closed by operation; current BLS/DOL public display
  is ALLOW. Revocation prevents activation and withdrawal replaces the pointer.

## Measured validation and operating envelope

- `python -m unittest discover -s tests -v`: 94/94 passed in 0.489 seconds.
- `npm test`: 76/76 passed in 9.85 seconds; `npm run typecheck`: passed.
- `npm run build` and `npm run verify:site`: passed; eight hashed assets,
  187,744 gzip bytes against the 368,640-byte budget.
- Idempotent capture, concurrent activation, candidate-failure pointer
  preservation, security allowlisting/redaction, dual replay, and rights tests
  passed.
- A full six-indicator collection is bounded to two official network requests.
  Current ignored local evidence footprint remains bounded; recurring
  data/infrastructure cost remains $0.

Taylor's 2026-08-18 verdict closes Gate A and Phase 3. This proves the bounded
data-integrity capability; it does not claim forecasting, dependency or
allocation modeling, employment prediction, or Phase-4 implementation.
Hosted/runtime factual activation remains separately unauthorized and was not
performed. Phase 4 may proceed to contract/design drafting only.
