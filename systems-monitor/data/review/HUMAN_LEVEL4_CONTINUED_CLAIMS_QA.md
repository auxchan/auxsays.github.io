# Continued Claims / Insured Unemployment Level-4 Human QA

State: `PENDING`

Review URL: `http://127.0.0.1:4173/systems-monitor/#continued-claims-level4-qa`

Node-interface URL: `http://127.0.0.1:4173/systems-monitor/#persistent-world/placement%3Alayoffs-job-destruction%3Acontinued-claims-insured-unemployment`

Taylor should verify:

- the parent presents Continued Claims (count) and Insured Unemployment Rate (percent) as two separate direct observations;
- the exact ten child identities match the frozen taxonomy;
- Initial Claims, Hires Rate, Job Openings Rate, Temporary Help Employment, and Average Weekly Hours reuse the existing 114 accepted records;
- Payroll Growth remains methodology-pending and does not publish a number;
- Regional Employment Growth remains taxonomy/method-pending and does not assume a geography;
- Business Formations does not silently equate its broad label with projected formations within four quarters;
- Real GDP Growth and Real PCE Growth remain explicitly credential-blocked;
- accepted, pending, and blocked states are visually distinct;
- no renderer fixture, causal, materiality, destination-impact, or forecast claim appears.

Do not change this state to `PASS` without Taylor's explicit approval.
