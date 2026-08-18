# Gate-A evidence — corrected candidate

Status: `GATE A OPEN`; `HUMAN_DATA_QA = PENDING`; no public activation.

## Factual slice and public boundary

- Six original-authority U.S. labor observations: payrolls 158,858 thousand,
  U-3 4.1%, participation 61.4%, initial claims 209,000, job openings 7,359
  thousand, and hires 5,348 thousand.
- Internal evidence: `internal-factual-review-model.json`.
- Pre-activation candidate targeting PDI 1.0.0:
  `factual-snapshot-candidate.json`; SHA-256
  `5E7AB8146E10987E109ECF8505B4586FE6E4FAABE17873B988E726766D92388E`.
  It contains no `snapshot` or `publishedAt` activation claim.
- Local activation test materialized the distinct immutable PDI snapshot
  `local-active-pdi-test-snapshot.json` at `2026-08-18T23:09:35.452742Z`;
  SHA-256 `F479DF1A254065757A3DAE2AE6FDDD6BA40E550E5B184BBD70A8CD7B110A647C`.
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

- `python -m unittest discover -s tests -v`: 90/90 passed in 0.460 seconds.
- `npm test`: 66/66 passed in 9.96 seconds; `npm run typecheck`: passed.
- `npm run build` and `npm run verify:site`: passed; eight hashed assets,
  186,346 gzip bytes against the 368,640-byte budget.
- Idempotent capture, concurrent activation, candidate-failure pointer
  preservation, security allowlisting/redaction, dual replay, and rights tests
  passed.
- A full six-indicator collection is bounded to two official network requests.
  Current ignored local evidence footprint remains bounded; recurring
  data/infrastructure cost remains $0.

Remaining evidence: Taylor must complete `HUMAN_DATA_QA.md`; hosted/runtime
public activation remains unauthorized and was not performed. Gate A and Phase
3 remain open; Phase 4 is locked.
