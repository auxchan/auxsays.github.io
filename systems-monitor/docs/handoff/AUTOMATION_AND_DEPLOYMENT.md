# Automation and deployment

`.github/workflows/pages.yml` builds and deploys on every push to `main` or manual dispatch. It uses Node 24, `npm ci`, UI validation, Jekyll build, static-site verification, and GitHub Pages deployment. The workflow itself contains no Taylor-approval or release-evidence check; the restriction is governance/process, not a technical workflow guard.

The Systems Monitor production workflow (`.github/workflows/systems-monitor-data.yml`) runs on a four-hour heartbeat. It retrieves only already-governed BLS/DOL series, validates acceptance and source evidence, and writes the production read model through the repository's conflict-safe writeback helper. Successful unchanged source checks are stored separately so polling cadence survives without republishing an unchanged snapshot. This bounded runner does not activate the wider candidate-source scheduler.

Secrets belong only in GitHub secrets/environment variables. Implemented candidate acquisition uses `AUXSAYS_BEA_USER_ID` and `AUXSAYS_CENSUS_API_KEY`; `AUXSAYS_EIA_API_KEY` is documented for a blocked candidate route. Never persist values or expose credential-bearing transport URLs in logs, commands, or artifacts.

The original handoff authorized no deployment. Taylor subsequently authorized updating the live site to the latest current build on 2026-11-05; see `state/review/persistent-world/SYSTEMS_MONITOR_RELEASE_PATH.md`. The release requires the repository's guarded merge and passing release evidence. It does not authorize forecast activation, new structural acceptance, or additional neighborhood development.
