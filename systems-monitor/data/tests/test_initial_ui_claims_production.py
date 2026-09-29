import json
import unittest

from _support import CONFIG, PACKAGE_ROOT


LAYOFFS = CONFIG / "layoffs"


def load(name: str):
    return json.loads((LAYOFFS / name).read_text(encoding="utf-8"))


class InitialUiClaimsProductionTests(unittest.TestCase):
    def test_exact_ten_registry_matches_taxonomy_and_scientific_boundary(self):
        production = load("initial_ui_claims_production.json")
        taxonomy = load("taxonomy.json")
        initial_group = next(group for group in taxonomy["groups"] if group["id"] == "initial-ui-claims")

        self.assertEqual(10, len(production["placements"]))
        self.assertEqual(
            [(row["label"], row["canonicalFactorId"]) for row in initial_group["placements"]],
            [(row["label"], row["canonicalFactorId"]) for row in production["placements"]],
        )
        self.assertEqual(0, production["unexplainedRendererFixtures"])
        self.assertEqual(0, production["acceptedStructuralRelationships"])
        self.assertEqual("OPEN", production["gateB"])
        self.assertEqual("LOCKED_UNAVAILABLE", production["forecasting"])
        self.assertEqual("UNAUTHORIZED", production["materiality"])
        self.assertEqual("PENDING", production["humanQa"])

    def test_exact_ten_dispositions_and_classes_are_explicit(self):
        rows = load("initial_ui_claims_production.json")["placements"]
        dispositions = [row["productionDisposition"] for row in rows]
        self.assertEqual(5, dispositions.count("ACCEPTED_OBSERVATION"))
        self.assertEqual(1, dispositions.count("GOVERNED_CALC_PENDING_METHODOLOGY_CALIBRATION"))
        self.assertEqual(1, dispositions.count("SOURCE_IDENTIFIED_PENDING_ACCEPTANCE"))
        self.assertEqual(2, dispositions.count("BLOCKED_CREDENTIAL"))
        self.assertEqual(1, dispositions.count("EVENT_OR_STRUCTURAL_FACTOR"))
        self.assertEqual("B_GOVERNED_CALC", rows[3]["claimClass"])
        self.assertEqual("C_EVENT_OR_STRUCTURAL", rows[9]["claimClass"])
        self.assertTrue(all(row["acceptedHistoryState"] for row in rows))
        self.assertTrue(all(row["blocker"] for row in rows if row["productionDisposition"] != "ACCEPTED_OBSERVATION"))

    def test_governed_renames_update_every_reused_placement(self):
        production = load("initial_ui_claims_production.json")
        taxonomy = load("taxonomy.json")
        migrations = {row["from"]: row["to"] for row in production["canonicalMigrations"]}
        self.assertEqual(5, len(migrations))
        all_ids = [row["canonicalFactorId"] for group in taxonomy["groups"] for row in group["placements"]]
        self.assertTrue(set(migrations).isdisjoint(all_ids))
        self.assertTrue(set(migrations.values()).issubset(all_ids))

        labels_by_id = {}
        for group in taxonomy["groups"]:
            for row in group["placements"]:
                labels_by_id.setdefault(row["canonicalFactorId"], set()).add(row["label"])
        for migration in production["canonicalMigrations"]:
            self.assertEqual({migration["newLabel"]}, labels_by_id[migration["to"]])

    def test_existing_accepted_evidence_is_reused_without_copying_history(self):
        production = load("initial_ui_claims_production.json")
        accepted_history = json.loads((PACKAGE_ROOT / "review" / "layoffs-accepted-history.json").read_text(encoding="utf-8"))
        accepted_ids = {row["canonicalFactorId"] for row in accepted_history["observations"]}
        legacy_aliases = {row["to"]: row["from"] for row in production["canonicalMigrations"]}
        accepted_rows = [row for row in production["placements"] if row["productionDisposition"] == "ACCEPTED_OBSERVATION"]
        for row in accepted_rows:
            history_id = legacy_aliases.get(row["canonicalFactorId"], row["canonicalFactorId"])
            self.assertIn(history_id, accepted_ids)

    def test_census_bds_alternates_do_not_bind_the_exact_ten(self):
        census = load("sources_census.json")
        bds = next(source for source in census["sources"] if source["source_id"] == "census-bds")
        excluded = {"JOB_DESTRUCTION", "ESTABS_EXIT"}
        for row in bds["series"]:
            if row["source_series_id"] in excluded:
                self.assertEqual([], row["placement_candidates"])


if __name__ == "__main__":
    unittest.main()
