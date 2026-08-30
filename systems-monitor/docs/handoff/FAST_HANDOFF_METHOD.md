# Fast handoff method for future transfers

Use this repeatable six-step method instead of rediscovering the repository each time:

1. **Freeze the baseline (2 minutes):** record repo, branch, HEAD, origin/main, tracked/staged status, Master hash, contract index hash, and topology fingerprint in one command transcript.
2. **Run four fixed audits in parallel:** governance; architecture/UI; graph/data; automation/testing. Each agent returns a predefined JSON-shaped summary and makes no edits.
3. **Generate from templates:** keep the handoff filenames and section schemas stable. Update facts, counts, hashes, gates, blockers, and file maps rather than rewriting prose.
4. **Validate once:** parse JSON/YAML, check every referenced path, run focused contract/topology/fixture tests, then the full relevant suites. Browser-test only the canonical review route.
5. **Adversarial pass:** give a context-free reviewer only `START_HERE_CLAUDE.md`; require it to identify authority, worktree, current truth, blockers, forbidden actions, and first safe task.
6. **Package atomically:** create manifest hashes, commit the handoff, ZIP only the handoff directory, compare extracted bytes, compute ZIP SHA-256, and report links.

Maintain a small script in a future authorized sprint to collect read-only baseline facts and render the manifest. It must never edit governance, accept data, commit, push, or deploy.
