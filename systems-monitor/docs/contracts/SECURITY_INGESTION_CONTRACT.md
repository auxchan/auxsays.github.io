# Security and Ingestion Trust-Boundary Contract

```text
Contract: Systems Monitor Security and Ingestion Trust-Boundary Contract
Version: 1.0.0
Status: BINDING
Parent Master Spec: V4.1
Depends On: ARCHITECTURE_CONTRACT.md, INFRASTRUCTURE_CONTRACT.md
Supersedes: None
Approved By: Taylor
Approved At: 2026-08-17
Content Hash: BDD0056B8C4BA8D89CF66FECE2668198DA4DEACA16E24F2096D67176B03F1606
Last Updated: 2026-08-17
```

## Authority / Status

Governing Master sections: §31.6, §34.1–34.11, §35.3–35.5, §38.2, §61, §64.2–64.12, §68. This BINDING contract defines current trust-boundary invariants but does not itself authorize ingestion implementation before the applicable later-phase contracts are approved.

## Purpose

Stabilize the trust boundary for all external content and the safe extraction, storage, query, export, publication, retry, and repository behaviors required before production ingestion.

## Scope

All webpages, documents, filings, feeds, structured data, metadata, attachments, source URLs, and user-supplied source material; deterministic parsers; optional LLM extraction; candidate relationship discovery; public rendering/export/publication; network/file/repository operations.

## Explicitly Out of Scope

- Building collectors, parsers, sandboxes, schemas, allowlists, databases, export code, workflows, or security infrastructure in Phase 1.
- Granting candidate LLM output production authority.

## Binding Requirements / Invariants

- **BINDING REQUIREMENT S-001:** All external material is untrusted data with zero instruction authority, regardless of source reputation or file format.
- **BINDING REQUIREMENT S-002:** External content cannot change specs/contracts/config/model weights, authorize tools, execute commands, write repositories, promote relationships, reveal secrets, or deploy.
- **BINDING REQUIREMENT S-003:** Prefer deterministic parsing; optional LLM/document extraction runs least-privileged with no shell, repo write, deployment privilege, or unrelated secrets.
- **BINDING REQUIREMENT S-004:** LLM output uses a strict allowlisted schema, is rejected on validation failure, and creates candidate/experimental records only.
- **BINDING REQUIREMENT S-005:** Content and extraction semantics are hashed/versioned; unchanged content is cached. Per-run/day depth, candidates, documents, passes, runtime, and AI-call budgets are bounded.
- **BINDING REQUIREMENT S-006:** Collector endpoints use approved schemes/registered hosts, validate redirects and resolved addresses, reject loopback/private/link-local/metadata/file destinations, and bound timeout/size/type/retries/rate.
- **BINDING REQUIREMENT S-007:** Downloads enforce compressed/decompressed/page/entry/time limits, MIME/content validation, no macro/binary execution, archive-bomb protection, quarantine, and no recursive arbitrary attachment processing.
- **BINDING REQUIREMENT S-008:** Storage keys use generated IDs/hashes; resolved paths must remain within approved roots. External filenames/labels/URLs never directly form filesystem paths.
- **BINDING REQUIREMENT S-009:** React text escaping is default; external HTML/Markdown/SVG/URLs are sanitized/allowlisted. No `dangerouslySetInnerHTML` for unsanitized content or executable protocol/context.
- **BINDING REQUIREMENT S-010:** Database queries are parameterized with allowlisted fields and bounded ranges/results; public inputs cannot supply raw SQL or arbitrary expressions. No `eval`; configuration formulas require a constrained declarative language if used.
- **BINDING REQUIREMENT S-011:** CSV/XLSX exports neutralize untrusted text/string cells beginning with formula-trigger syntax (`=`, `+`, `-`, `@`) under a later approved documented reversible policy. Legitimate typed numeric values remain numeric—including negative or explicitly positive values such as numeric `-4.2` or `+4.2`—and must not be converted to strings merely because their text serialization begins with `-` or `+`.
- **BINDING REQUIREMENT S-012:** Secrets/restricted datasets/private dumps never enter git, logs, public artifacts, or client bundles. CI uses scoped environment secrets and least-privilege permissions.
- **BINDING REQUIREMENT S-013:** Third-party Actions/dependencies are reviewed, versioned/pinned appropriately, locked, scanned where practical, and not followed blindly from mutable branches.
- **BINDING REQUIREMENT S-014:** Public publication enforces rights and schema allowlists, builds an immutable snapshot, validates it, then atomically updates the current pointer.
- **BINDING REQUIREMENT S-015:** Jobs use deterministic idempotency keys, bounded retries/backoff, and concurrency control; duplicates/partial failures cannot duplicate facts or replace a valid snapshot.

## Security profile

### Trust zones

```text
Untrusted network/file content
  -> bounded fetch/quarantine
    -> deterministic parse / isolated extraction
      -> schema validation
        -> candidate/normalized staging
          -> governed promotion and rights checks
            -> explicit public export
```

No arrow implies authorization to cross backward or mutate governance.

### Minimum audit fields

When implemented, record source/content hash, retrieval time, byte/type/parser/extractor/prompt/model/schema versions, run/idempotency identity, validation result, candidate status, rights result, publication snapshot, and security rejection category without logging secrets or restricted bodies unnecessarily.

## Interfaces / Dependencies

- Architecture defines privilege/domain separation.
- Infrastructure supplies scoped secrets, storage, telemetry, idempotency, and atomic publication mechanisms.
- Public Data Interface defines the publishable schema.
- Later Data/Source/Dependency contracts must incorporate these invariants rather than restating weaker versions.

## Allowed Implementation Freedom

- **IMPLEMENTATION CHOICE:** Specific sandbox, HTTP client, parser, sanitizer, CSP, database, secret scanner, or formula-neutralization mechanism may be selected after threat/test review.
- **IMPLEMENTATION CHOICE:** Domain allowlists may be configuration-driven if config itself is reviewed/validated and cannot introduce private-network destinations.

## Prohibited Behavior

- Trusting prompts embedded in content; shell-generated fetch commands; unrestricted URL fetching; automatic macro/binary execution; unsanitized HTML/SVG; raw public SQL/config expressions; secret-bearing fixtures; direct candidate-to-production promotion; partial in-place publication; unbounded recursive research.

## Failure / Degraded States

- Unsafe/unsupported material is rejected or quarantined with an auditable reason.
- Extraction or AI failure yields no candidate rather than invented output and does not block core deterministic operation.
- Network/source failure uses bounded retries and cannot broaden allowlists.
- Publication/security/rights validation failure preserves the prior valid snapshot.

## Acceptance Criteria

1. Before production ingestion, tests cover prompt injection, SSRF/redirect/DNS cases, size/archive/path traversal, XSS/protocols, SQL/config injection, formula injection, secrets, idempotency/concurrency, and atomic publication failure.
2. Extraction jobs demonstrably lack shell/repo-write/deploy privilege and unrelated secrets.
3. Schema-invalid or weak candidate output cannot become accepted production relationships.
4. External content cannot alter governance or deployment through any designed interface.
5. Phase-1 check confirms no ingestion/security implementation or secrets were created.
6. Export tests preserve typed negative/positive numerics as numeric values while neutralizing formula-triggering untrusted text/string cells.

## Risks / Open Decisions

- Concrete sandbox/network/storage/security products are later-phase decisions. See R-005, R-006, R-010, R-012.

## Version / Approval / Change History

- 1.0.0 (2026-08-17): First BINDING version approved by Taylor after Phase-1 external review, including the typed-numeric/untrusted-text S-011 clarification.
- 0.1.1 (2026-08-17): Clarified S-011 to protect untrusted text from spreadsheet formula injection without coercing legitimate typed numeric values. Remains DRAFT pending final validation and promotion.
- 0.1.0 (2026-08-17): Initial Foundation trust-boundary draft. Not approved.
