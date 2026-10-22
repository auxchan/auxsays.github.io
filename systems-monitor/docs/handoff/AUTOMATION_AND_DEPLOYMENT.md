# Automation and deployment

`.github/workflows/pages.yml` builds and deploys on every push to `main` or manual dispatch. It uses Node 24, `npm ci`, UI validation, Jekyll build, static-site verification, and GitHub Pages deployment. The workflow itself contains no Taylor-approval or release-evidence check; the restriction is governance/process, not a technical workflow guard.

The layoffs scheduler configuration declares a four-hour evaluation heartbeat and source-specific minimum intervals, grace periods, and credentials, but no verified Systems Monitor scheduled GitHub Actions workflow currently wires that scheduler into unattended acquisition/publication. Treat this as an implementation gap.

Secrets belong only in GitHub secrets/environment variables. Implemented candidate acquisition uses `AUXSAYS_BEA_USER_ID` and `AUXSAYS_CENSUS_API_KEY`; `AUXSAYS_EIA_API_KEY` is documented for a blocked candidate route. Never persist values or expose credential-bearing transport URLs in logs, commands, or artifacts.

No deployment, public factual activation, workflow enablement, push, or merge was authorized by this handoff. Pages deployment remains gated by Taylor approval and release evidence.
