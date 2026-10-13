# Continued Claims / Insured Unemployment Level-4 Human QA

State: `PENDING`

Review URL: `http://127.0.0.1:4173/systems-monitor/#continued-claims-level4-qa`

Node-interface URL: `http://127.0.0.1:4173/systems-monitor/#persistent-world/placement%3Alayoffs-job-destruction%3Acontinued-claims-insured-unemployment`

Taylor should verify:

- the parent presents Continued Claims (count) and Insured Unemployment Rate (percent) as two separate direct observations;
- the exact ten child identities match the frozen taxonomy;
- Initial Claims, Hires Rate, Job Openings Rate, Temporary Help Employment, and Average Weekly Hours reuse the existing 114 accepted records;
- Total Nonfarm Payroll Change uses `PAYROLL_CHANGE_V1` over accepted `CES0000000001` t/t-1 inputs, remains input-history-pending, and does not publish a number;
- State-Level Payroll Growth Breadth uses the fixed `CES_STATE_TOTAL_NONFARM_V1` 50-state-plus-DC universe, remains input-history-pending, and does not publish a number;
- Business Formations Within 4 Quarters uses `BF_BF4Q` as the direct actual formation series and does not substitute projected `BF_PBF4Q` or spliced `BF_SBF4Q`;
- Real GDP Growth and Real PCE Growth remain explicitly credential-blocked;
- accepted, pending, and blocked states are visually distinct;
- no renderer fixture, causal, materiality, destination-impact, or forecast claim appears.

Do not change this state to `PASS` without Taylor's explicit approval.
