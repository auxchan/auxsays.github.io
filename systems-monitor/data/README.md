# Systems Monitor deterministic data and state package

This package implements the Phase-3 six-indicator labor-data slice and the
Phase-4A state/relationship/propagation/derivation engine proof. It uses only the
Python standard library and local SQLite/content-addressed files.

Runtime data belongs under `local/` and is ignored by git. The committed
`review/` files are bounded review evidence and are never the public website's
active data source.

Run all deterministic tests from this directory:

```text
python -m unittest discover -s tests -v
```

Build a local factual candidate (network access required):

```text
python scripts/run_data.py collect --local-root local
```

The command records official artifacts locally, validates and normalizes the
six enabled observations, writes a clearly classified internal review model,
exports and validates a separate pre-activation candidate targeting PDI 1.0.0,
and does not publicly activate it. The candidate contains no `publishedAt`.

Rebuild the committed PDI review artifact deterministically from the committed
internal review model:

```text
python scripts/build_review_candidate.py
```

Create a bounded local-only activation proof. This materializes a distinct PDI
snapshot with the actual local activation time through a temporary local
pointer; it does not activate AUXSAYS.com:

```text
python scripts/build_local_activation_proof.py
```

Print the one-line browser-console loader for local factual UI review:

```text
python scripts/print_local_ui_loader.py
```

Build the deterministic local-only Phase-4A review candidate from the committed
Phase-3 factual review model (no network access or public activation):

```text
python scripts/build_phase4a_review.py
```

The Phase-4A candidate is explicitly `LIMITED_ENGINE_PROOF`, contains only OBS
and CALC records, and is not Gate-B evidence or a public data activation.
