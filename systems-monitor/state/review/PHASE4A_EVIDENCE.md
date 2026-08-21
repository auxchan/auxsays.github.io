# Phase-4A Technical Evidence

Status: **TECHNICAL PASS / HUMAN_PHASE4A_QA PENDING / GATE B OPEN**

## Build identity

- Candidate: `phase4a-candidate:0b3836b23eed52985b746606c0c6bf75d536f885ecb653322af435758be6f5ea`
- Source snapshot: `sha256:8695c5ddc59aa1de4cf0083212c146fe105181beca1749346752d6f5134283a6`
- State run: `state-run:4628b1f96d955855fa8844da3ad55f66b7a45ec429a92ca2a31d8de5865e8bbe`
- State engine: `state-engine-1.0.0`
- Configuration: `phase4a-proof-1.0.0`
- Relationship definitions: `labor-proof-relationships-1.0.0`
- Propagation: `bounded-propagation-1.0.0`; maxDepth 3; maxRounds 8
- Derivation: `derivation-1.0.0`
- Replay: `OPERATIONALLY_KNOWN_AS_OF(2026-08-19T00:00:00Z)`
- Geography / rights: US / ALLOW

## Evidence result

- Six accepted Phase-3 labor observations remained `OBS`; AUXSAYS calculation is `NONE`.
- Six direct current-state outputs are `CALC`, each with an immutable derivation.
- Six direct semantic mapping relationships deterministically followed
  `CANDIDATE → VALIDATED → ACCEPTED` under an external approved rule.
- Runtime traversal used only the six ACCEPTED versions and produced six direct
  identity contributions, depth 1, round 1, then stopped deterministically.
- No relationship connects one labor indicator to another; no causal,
  elasticity, weight, lag, capacity, substitute, FCST, or SCEN claim is present.
- Mixed monthly/weekly valid times, carried-forward identity, age/freshness, and
  separate DOL observation freshness/retrieval-path health remain visible.
- The read model exposes 6 OBS + 6 CALC, derivation references, six accepted/zero
  candidate relationships, unsupported domains, `LIMITED_ENGINE_PROOF`, and
  `DEGRADED_SOURCE_PATH` for the stale DOL XML path.
- Every OBS preserves three distinct evidence layers: machine acquisition
  provenance, exact human-readable original evidence, and source methodology.
  The five BLS observations retain the generic BLS API URL only as acquisition
  provenance and expose their exact `data.bls.gov/timeseries/<series>` pages as
  human evidence. Regression tests prohibit substituting the API endpoint for
  those evidence pages.

The exact six OBS and six CALC outputs are listed concisely in
`PHASE4A_HUMAN_QA.md`; the complete machine record is
`phase4a-read-model-candidate.json` (SHA-256
`68155D23A3D8535F3946EC1AB0BFAB9E6BE093736C148A2F8B28DFBE2693C2E9`).

## Replay / baseline evidence

- Public replay at 2026-08-05 selects only the two JOLTS observations already
  public; later payroll/CPS/claims observations do not leak.
- Operational replay before the common 2026-08-18 19:46 acceptance time selects
  none of the six; the review cutoff after acceptance selects all six.
- Direct identity states declare baseline
  `NOT_APPLICABLE_DIRECT_STATE_MAPPING` because they are not direction/change/
  pressure calculations.
- The reference helper returns `UNKNOWN`/no reference when a previous eligible
  observation is absent and selects the previous retained period when present in
  deterministic tests. No historical value is invented for the factual run.

## Mechanics evidence

- Same-period accepted cycles return `cycle_rejected`; no heuristic SCC solver exists.
- Origin/common-cause/path IDs are retained. Multiple paths with one origin remain
  `UNRESOLVED_EXPLICIT_NO_NAIVE_SUM`, with positive and negative components decomposed.
- Synthetic fixtures—explicitly labeled
  `ENGINE_MECHANICS_TEST_NOT_REAL_ECONOMIC_EVIDENCE`—cover BLOCKED, ABSORBED,
  PARTIALLY_ABSORBED, DELAYED, TRANSMITTED, AMPLIFIED, finite/exhausted capacity,
  substitute available/capacity-limited/none, and UNKNOWN buffer/lag.
- Allocation tests cover conservation, residual, insufficient/excess supply,
  limited capacity, partial allocation, deterministic ordering, and UNKNOWN input.

Synthetic mechanics are architecture proof only, not U.S. economic evidence.

## Tests

- `python -m unittest discover -s tests -v`: **175 passed** (Phase-3 + Phase-4A).
- `npm test -- --run --reporter verbose`: **76 passed** (unchanged Phase-2/3 UI regressions).
- Phase-4A subset: **81 passed**.
- Security cases reject external self-promotion, unsupported causality, hostile
  algorithm strings, geography/unit mismatch, secret/storage-shaped output,
  and markup/control-character escape.
- Windows execution passed. Path-independent canonical IDs and existing
  Windows/Linux-safe path tests provide Linux-compatible evidence; no hosted
  Linux runner was invoked because nothing was pushed.

## Performance / cost

- Measured final local review build: 4.868 ms.
- Peak traced Python memory: 310,083 bytes.
- Relationships/traversals/contributions: 6 / 6 / 6.
- Max depth/rounds reached: 1 / 1.
- Review candidate size / local storage growth: 55,511 bytes; no runtime DB added.
- Recurring infrastructure/API cost: **$0**.
- Dependencies added: **none**; Python standard library and existing local package only.

## Gate-B remaining requirements

Gate B cannot close from this evidence. Phase 4B still requires a separately
authorized bounded source-discovery/intake sprint, then exact original-authority
BEA Supply/Use/Input-Output dataset/table/version/rights/schema/parser/crosswalk
approval before ingestion. It must prove real structural direct-versus-total
role safety, accepted structural relationships, current structural node state,
real lag/buffer/substitution/capacity/common-cause behavior, allocation/current
employment exposure, derivation, coverage, performance/cost, Human QA, and
Taylor approval. None of that work occurred here.
