# Layoffs Level-4 Adversarial Economic QA

Status: **MACHINE QA COMPLETE — HUMAN QA PENDING**

This audit asks whether the current branch can overstate evidence. A PASS means the tested defect is prevented or disclosed; it does not promote candidate data or approve the branch for publication.

| Defect challenged | Result | Evidence |
|---|---|---|
| Duplicate canonical factors | PASS | The taxonomy resolves 100 placements to 64 explicit canonical identities; repeated placements remain visible in the generated audit. |
| Duplicate or orphan source records hidden by canonicalization | PASS | All 77 UI-side state records are enumerated. Nine source-only records are disclosed for review instead of silently merged; one plural business-formation alias is marked for removal. |
| Wrong source scope shown as accepted | PASS | Ambiguous broad concepts are Class D or blocked, and acquisition bindings carry explicit roles such as alternate scope, calculation input, or structural source. |
| Wrong geography | PASS | Acceptance and comparable-history matching require exact geography equality. |
| Wrong units | PASS | Acceptance and comparison require exact units; cross-unit comparison is forbidden. |
| Wrong seasonal adjustment | PASS | Acceptance and comparison require exact adjustment state; cross-adjustment comparison is forbidden. |
| Wrong cadence or invented temporal resolution | PASS | Comparable changes use the source's native weekly, monthly, or quarterly cadence. |
| Revised value silently replacing historical truth | PASS | Immutable vintage identities, supersession links, and public/operational/latest replay modes are tested. |
| Monthly data presented as hourly movement | PASS | Native-cadence comparison is enforced and no interpolation is implemented. |
| Candidate observation shown as accepted | PASS | The 282-row live batch remains `NOT_ACCEPTED_NOT_PUBLISHABLE`; production acceptance authority is `NONE`. |
| Measurement shown as causation | PASS | Interpretation templates prohibit causal and destination-impact claims. |
| Hierarchy shown as structural evidence | PASS | Existing hierarchy tethers remain navigation-only; accepted structural relationships remain zero. |
| BEA direct/total double counting | PASS | Direct requirements may create topology candidates; total requirements remain a non-recursive benchmark. Existing tests reject recursive use. |
| Commodity/industry namespace leakage | PASS | The proposed handoff remains blocked until authoritative Make/Use or market-share semantics exist. No edge is accepted. |
| Source outage shown as economic decline | PASS | Source state is separate from observation direction; no new direction is published. |
| Unsupported red/green interpretation | PASS | Materiality authority is `NONE`; materiality remains `UNKNOWN`, and no supportive/adverse color state is activated. |

## Open defects and blockers

- Nine source-only records still need an explicit canonicalization, calculation-input retention, or reviewed removal decision.
- The live BLS/DOL history is candidate evidence only. No comparable history can be presented as accepted until a governed acceptance rule covers the exact series and scope.
- The BEA lane is credential-blocked, and the industry-to-commodity handoff is not implemented or accepted.
- Human Level-4 and structural-path QA remain pending.
