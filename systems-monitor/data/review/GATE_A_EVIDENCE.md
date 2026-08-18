# Gate-A evidence — corrected candidate

Status: `GATE A OPEN`; `HUMAN_DATA_QA = PENDING`; no public activation.

## Factual slice and public boundary

- Six original-authority U.S. labor observations: payrolls 158,858 thousand,
  U-3 4.1%, participation 61.4%, initial claims 209,000, job openings 7,359
  thousand, and hires 5,348 thousand.
- Internal evidence: `internal-factual-review-model.json`.
- BINDING PDI 1.0.0 candidate: `factual-snapshot-candidate.json`.
- Candidate SHA-256:
  `0D463A590921B5652F7D095DE52468937D4B74CB62DC7933C040D89CDF926B9B`.
- The earlier internal-shaped candidate falsely passed a validator that checked
  only that internal shape. Regression tests now reject it; explicit export and
  independent Python/TypeScript PDI validation guard the public boundary.
- Candidate is OBS-only; events and forecast/ranking collections are empty;
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

- `python -m unittest discover -s tests -v`: 82/82 passed in 0.388 seconds.
- `npm test`: 61/61 passed in 9.03 seconds; `npm run typecheck`: passed.
- Idempotent capture, concurrent activation, candidate-failure pointer
  preservation, security allowlisting/redaction, dual replay, and rights tests
  passed.
- A full six-indicator collection is bounded to two official network requests.
  Current ignored local evidence footprint: 3,786,405 bytes; PDI candidate:
  15,780 bytes. Recurring data/infrastructure cost remains $0.

Remaining evidence: Taylor must complete `HUMAN_DATA_QA.md`; hosted/runtime
activation evidence remains blocked because deployment/public activation is not
authorized. Gate A and Phase 3 remain open; Phase 4 is locked.
