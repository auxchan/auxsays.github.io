# Systems Monitor Contract Template

Use this lean template only when a subsystem becomes active. Remove conditional profiles that do not apply; do not add empty boilerplate.

## Authority chain

1. Current authoritative Systems Monitor Master Specification
2. Approved/BINDING subsystem contract
3. Recorded accepted decisions
4. Current scoped implementation task
5. Existing repository conventions where they do not conflict
6. Historical chat, notes, and superseded material

When authorities conflict, the higher authority wins. Record the conflict, propose the minimum amendment, pause only affected scope, and continue unaffected work safely.

```text
Contract:
Version:
Status: DRAFT
Parent Master Spec: V4.1
Depends On:
Supersedes: None
Approved By: —
Approved At: —
Content Hash: PENDING — DRAFT
Last Updated: YYYY-MM-DD
```

## Authority / Status

State the governing Master sections and clarify that `DRAFT` is not implementation authority.

## Purpose

Describe the boundary this contract stabilizes.

## Scope

List only current approved scope.

## Explicitly Out of Scope

Name adjacent work that this contract does not authorize.

## Binding Requirements / Invariants

Label each item `BINDING REQUIREMENT`.

## Interfaces / Dependencies

Identify inputs, outputs, parent contracts, and downstream consumers.

## Allowed Implementation Freedom

Label each item `IMPLEMENTATION CHOICE`.

## Prohibited Behavior

State actions that violate the contract.

## Failure / Degraded States

Define safe behavior when inputs, dependencies, or validation fail.

## Acceptance Criteria

Use objective, testable criteria. Do not weaken criteria to obtain a pass.

## Risks / Open Decisions

Label decisions that must be resolved before affected implementation as `OPEN DECISION`.

## Conditional Profile

Include only applicable Data, Model, Security, UI, or Infrastructure details.

## Version / Approval / Change History

Retain prior versions or supersession references. Taylor alone may promote status to `PROVISIONAL` or `BINDING`.

## Amendment protocol

An amendment proposal must record: problem, why the current contract fails, affected requirements, minimum change, downstream impact, test/migration impact, and whether Taylor's decision is required. Update the version and `CHANGELOG.md`; never rewrite history.

## Contract content-hash convention

For a `PROVISIONAL` or `BINDING` contract, `Content Hash` is the uppercase SHA-256 of the contract's canonical UTF-8 text after normalizing CRLF/CR line endings to LF and omitting the single complete `Content Hash:` header line. All other content, including version, status, approval metadata, requirements, and change history, is covered. A `DRAFT` may retain `PENDING — DRAFT`.
