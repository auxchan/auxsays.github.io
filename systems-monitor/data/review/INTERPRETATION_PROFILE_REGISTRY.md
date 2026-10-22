# Interpretation Profile Registry

Status: ENGINE IMPLEMENTED — FACTOR PROFILES REQUIRE GOVERNED APPROVAL

## Deterministic contract

An interpretation is a versioned `CALC` derived from one accepted change event. It records the profile/version, method reference, input observation references, and input event reference. Runtime AI is not used.

## Required profile fields

- profile ID and semantic version;
- canonical factor ID;
- method reference;
- one plain-English rule for every allowed materiality state;
- no causal wording unless an accepted relationship and method justify it.

## Current safe output

For the six current accepted observations, AUXSAYS says the observation and period were accepted and explicitly says that no material increase/decrease can be claimed because the public snapshot lacks a comparable prior point. This is deliberate, not missing UI.

## Prohibited output

- “good” or “bad” based only on numeric direction;
- percentile, trend, acceleration, or historical-range language without retained support;
- hourly movement for weekly/monthly data;
- causal claims from hierarchy placement;
- AI-generated prose in normal operation.
