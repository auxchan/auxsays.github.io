# Product Contract

```text
Contract: Systems Monitor Product Contract
Version: 1.0.0
Status: BINDING
Parent Master Spec: V4.1
Depends On: None
Supersedes: None
Approved By: Taylor
Approved At: 2026-08-17
Content Hash: ED64C95813C0EB43C9FCFD1745F19A7945638C39F287D547806BB018BB102D8B
Last Updated: 2026-08-17
```

## Authority / Status

Governing Master sections: §0–5, §38–39, §55, §64.1–64.12, §68–71. This BINDING contract is current Foundation product authority. It authorizes Phase-2 contract/design drafting only; substantive UI implementation still requires the applicable Phase-2 contracts to be reviewed and approved.

## Purpose

Stabilize the identity, public boundary, information-state invariants, primary user experience, and credibility gates of AUXSAYS U.S. Systems Monitor.

## Scope

- A new first-class AUXSAYS.com product at `/systems-monitor/` alongside Patch Feed.
- Shared AUXSAYS branding/global shell where appropriate, with isolated application, data, and model systems.
- Exactly three public primary views: Summary, Verified Data, and Outlook.
- Progressive `10 -> 10 -> 10` hierarchy with focused trace visualization as an explanation tool.
- Long-term product outcome: traceable current-state evidence and calibrated, accountable economic/labor forecasts.

## Explicitly Out of Scope

- Replacing or redesigning Patch Feed.
- Phase-2 UI implementation, collectors, storage, cloud selection, models, public forecasts, or launch.
- Treating future/experimental behavioral signals or broad hidden-dependency discovery as Foundation blockers.

## Binding Requirements / Invariants

- **BINDING REQUIREMENT P-001:** Public canonical product route is `/systems-monitor/`.
- **BINDING REQUIREMENT P-002:** Systems Monitor is first-class alongside Patch Feed and must not share Patch Feed data/model machinery by accident.
- **BINDING REQUIREMENT P-003:** The primary views are exactly Summary, Verified Data, and Outlook.
- **BINDING REQUIREMENT P-004:** `OBS`, `CALC`, `FCST`, and `SCEN` are distinct types; a forecast/scenario never silently becomes observed truth.
- **BINDING REQUIREMENT P-005:** Verified Data exposes observed/calculated evidence without presenting forecasts as fact.
- **BINDING REQUIREMENT P-006:** Outlook labels forecast horizon, baseline/scenario state, prediction range, evidence, and model-skill dimensions without implying an uncalibrated probability.
- **BINDING REQUIREMENT P-007:** Progressive Top 10 is the primary navigation. Do not invent children to reach ten; preserve View All and hierarchy context.
- **BINDING REQUIREMENT P-008:** A giant network graph is not the default. Trace Mode is focused and explanatory.
- **BINDING REQUIREMENT P-009:** No fabricated numbers, sources, probabilities, causal certainty, model skill, or hidden-dependency evidence may appear.
- **BINDING REQUIREMENT P-010:** Fixture/illustrative values must be explicitly non-claim data and release-blocked from factual publication.
- **BINDING REQUIREMENT P-011:** Capability gates control breadth and public claims; visual completeness cannot substitute for methodological readiness.
- **BINDING REQUIREMENT P-012:** Core product operation must not require continuous external LLM access.

## Interfaces / Dependencies

- Repository Integration owns static hosting, route mechanics, and global shell attachment.
- Architecture/Infrastructure own presentation, public-data, compute, and storage boundaries.
- Public Data Interface owns frontend payload semantics.
- Security Ingestion owns external-content trust boundaries.
- Release Acceptance owns phase/capability-gate evidence.

## Allowed Implementation Freedom

- **IMPLEMENTATION CHOICE:** Internal React component composition, state-management approach, CSS strategy, and chart implementation may be selected within approved UI/repository contracts.
- **IMPLEMENTATION CHOICE:** Fewer than ten children may be displayed when only fewer are defensible.
- **IMPLEMENTATION CHOICE:** Selected context may be serialized through static-host-compatible URLs defined by Repository Integration.

## Prohibited Behavior

- Broad existing-site rewrite; Patch Feed regression or replacement.
- Unsupported public predictive claims or illustrative rankings presented as real.
- Generic confidence percentages/badges without calibrated probabilistic meaning.
- Silent change to view count, primary hierarchy, route, or information-state meanings.

## Failure / Degraded States

- Missing/weak data produces explicit Source Delay, Insufficient Evidence, Forecast Unavailable, or Model Disagreement states.
- Failed refresh keeps the last valid public snapshot; it must not produce substitute conclusions.
- When a view cannot support a claim, omit or label the claim rather than inventing completion.

## Acceptance Criteria

1. Route, product boundary, three views, hierarchy, and graph rule are explicit and consistent with V4.1.
2. Information states and fixture/public-claim constraints are unambiguous.
3. Dependencies delegate implementation details without weakening product requirements.
4. Phase-1 review confirms no Patch Feed behavior or application implementation changed.

## Risks / Open Decisions

- See R-004 and R-009. No product decision is open before Phase-2 contract drafting.

## Version / Approval / Change History

- 1.0.0 (2026-08-17): First BINDING version approved by Taylor after Phase-1 external review; substantive requirements unchanged from the reviewed DRAFT.
- 0.1.0 (2026-08-17): Initial Foundation draft. Not approved.
