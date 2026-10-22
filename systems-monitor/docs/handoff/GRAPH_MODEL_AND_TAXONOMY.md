# Graph model and taxonomy

Authoritative builder: `app/src/data/persistentWorldModel.ts`; reviewed Layoffs overlay: `layoffsBranchTaxonomy.ts`.

- World: `persistent-employment-world-rd-001`
- Schema: `persistent-world-0.1.0`
- Layout: `employment-sectors-1.1.0`
- Fingerprint: `fnv1a32:88684cdb`
- Placements: 1 outcome + 10 Level-1 + 100 Level-2 + 1,000 Level-3 = 1,111
- Relationships: 1,110 `HIERARCHY_TETHER` + 2,000 `SYNTHETIC_INFLUENCE` = 3,110
- Accepted/factual structural relationships: 0 / 0

The ten Level-1 systems are Output & Growth, Consumer Demand, Employer Labor Demand, Layoffs & Job Destruction, Business Investment, Rates & Credit, Labor Costs & Wages, Productivity & Automation, Labor Supply, and Policy, Trade & External Shocks.

Each Level-1 has exactly ten Level-2 placements; each Level-2 has exactly ten Level-3 placements. The Layoffs branch has 100 reviewed real economic candidates. The other nine branches retain 900 `Renderer fixture NN` Level-3 records. Candidates are not accepted observations or relationships.

Canonical factor identity, hierarchy placement, evidence, and structural relationship are separate. Multiple placements may reuse one canonical factor. Placement aliases never duplicate data. The fingerprint hashes layout plus sorted placements/relationships; camera navigation must not alter it.
