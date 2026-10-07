# Claude Code entry point

Start with `systems-monitor/docs/handoff/START_HERE_CLAUDE.md`. The captured implementation baseline is `5e65d429857eb9a88f41c6672dc3043130988cfc` on `codex/systems-monitor-persistent-world`. Do not treat hierarchy tethers, source candidates, or fixtures as accepted economic evidence.

## AUXSAYS

For AUXSAYS work, the instructions are [`AGENTS.md`](AGENTS.md).

**Merging is the one rule worth repeating here, because this file is the one that
loads automatically.** A pull request may not be merged while its CI is red. GitHub
cannot enforce that on this repository — it was measured, see AUX-013 in
[`docs/ENGINEERING_LEDGER.md`](docs/ENGINEERING_LEDGER.md) — so the gate is a script:

```bash
python auxsays/scripts/ci/guarded_merge.py <PR> --merge
```

Do not use `gh pr merge`, and do not chain the gate into another merge command.
Reading the status and merging as one gesture is exactly how PR #163 went in red.
