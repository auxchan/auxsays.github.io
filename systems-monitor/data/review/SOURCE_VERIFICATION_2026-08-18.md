# Current official source verification — 2026-08-18

The machine-readable registry is authoritative for implementation settings.
This review note records why the four source families were enabled.

## BLS CES, CPS, and JOLTS

- Official API: `https://api.bls.gov/publicAPI/v2/timeseries/data/`
- Access: HTTPS POST JSON; optional registration key. This slice uses the
  unregistered path and sends no credential.
- Reviewed unregistered limits: 25 queries/day, 25 series/query, 10 years/query,
  and 50 requests per 10 seconds. The combined first-slice BLS request uses five
  series, one year, and one request.
- Terms: `https://www.bls.gov/developers/termsOfService.htm`
- API FAQ/limits: `https://www.bls.gov/developers/api_faqs.htm`
- Rights: `https://www.bls.gov/opub/copyright-information.htm`; BLS publications
  are generally public domain, with separate treatment required for identified
  third-party images/illustrations. Attribution and retrieval date are retained.
- CES cadence/revisions: monthly; two subsequent monthly revisions plus annual
  benchmarking. Methodology: `https://www.bls.gov/opub/hom/ces/home.htm`.
- CPS cadence/revisions: monthly; seasonal factors can be revised annually.
  Methodology: `https://www.bls.gov/opub/hom/cps/calculation.htm`.
- JOLTS cadence/revisions: monthly; prior month revised with the next release and
  annual revisions can cover five years. Methodology:
  `https://www.bls.gov/opub/hom/jlt/presentation.htm`.
- Current JOLTS code structure was verified against
  `https://www.bls.gov/jlt/jlt_series_changes.htm`. The enabled level series are
  `JTS000000000000000JOL` and `JTS000000000000000HIL`.

## DOL Weekly Claims

- Query form: `https://oui.doleta.gov/unemploy/claims.asp`
- Machine endpoint: `https://oui.doleta.gov/unemploy/wkclaims/report.asp`
- Access: HTTPS POST form, official national result as XML, no authentication.
- Current release: `https://www.dol.gov/ui/data.pdf`.
- Archive: `https://oui.doleta.gov/unemploy/claims_arch.asp`.
- Cadence: Thursday 08:30 ET. Advance claims are revised in the following weekly
  release.
- Rights: `https://www.dol.gov/general/aboutdol/copyright`; federal content is
  generally public domain, with identified third-party content handled
  separately. Attribution is retained.
- The source registry imposes a conservative local limit of 24 query requests
  per day and 2 per 10 seconds; this is an AUXSAYS safety bound, not a claimed
  provider quota.
- Operational finding: the official XML page reported a run date of 2026-08-18
  but its latest populated national SA initial-claims row was week ending
  2026-07-18 (`189,000`). The official current weekly PDF covered week ending
  2026-08-08 (`209,000`). The machine collector therefore marks the XML
  observation stale instead of silently presenting it as current; the bounded
  human-review candidate uses the independently verified current PDF artifact.

Terms were reviewed 2026-08-18 and are scheduled for recheck 2027-02-18. No
aggregator, commercial API, news numerical source, or credential was used.
