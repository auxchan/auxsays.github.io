# Systems Monitor data integrity package

This package implements the Phase-3 six-indicator labor-data slice. It uses
only the Python standard library and local SQLite/content-addressed files.

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
six enabled observations, writes a review candidate, and does not activate it.

Print the one-line browser-console loader for local factual UI review:

```text
python scripts/print_local_ui_loader.py
```
