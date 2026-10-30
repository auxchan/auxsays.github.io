import importlib.util
import json
import unittest

from _support import CONFIG, PACKAGE_ROOT


SCRIPT_PATH = PACKAGE_ROOT / "run_layoffs_update.py"
SPEC = importlib.util.spec_from_file_location("run_layoffs_update", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class LayoffsSourceStateReconciliationTests(unittest.TestCase):
    def test_existing_accepted_history_wins_over_current_retrieval_health(self):
        layoffs = CONFIG / "layoffs"
        bls_dol = load(layoffs / "sources_bls_dol.json")
        census = load(layoffs / "sources_census.json")
        context = load(layoffs / "sources_bea_fed_courts.json")
        fema = load(layoffs / "sources_fema.json")
        taxonomy = load(layoffs / "taxonomy.json")
        scheduler = load(layoffs / "scheduler.json")
        accepted_history = load(PACKAGE_ROOT / "review" / "layoffs-accepted-history.json")
        health = {
            row["sourceId"]: {
                "activationState": "SOURCE_IDENTIFIED",
                "health": "disabled",
                "reasonCode": "NETWORK_DISABLED_REVIEW_BUILD",
            }
            for row in scheduler["sources"]
        }

        states = MODULE.factor_states(bls_dol, census, context, fema, taxonomy, accepted_history, health)
        by_factor = {row["canonicalFactorId"]: row for row in states}
        exact_ten_accepted = {
            "factor:canonical:layoffs-and-discharges": "JTS000000000000000LDL",
            "factor:canonical:temporary-layoffs": "LNS13023653",
            "factor:canonical:permanent-job-losers": "LNS13026638",
            "factor:canonical:gross-job-losses": "BDS0000000000000000110004LQ5",
            "factor:canonical:jobs-lost-at-establishment-deaths": "BDS0000000000000000110008LQ5",
        }
        for factor_id, series_id in exact_ten_accepted.items():
            self.assertEqual("ACCEPTED", by_factor[factor_id]["activationState"])
            self.assertEqual("EXISTING_ACCEPTED_HISTORY_REUSED", by_factor[factor_id]["reasonCode"])
            self.assertEqual(series_id, by_factor[factor_id]["seriesId"])
            self.assertTrue(by_factor[factor_id]["period"])
            self.assertTrue(by_factor[factor_id]["acceptedAt"])

        self.assertNotIn("factor:canonical:establishment-deaths", by_factor)
        self.assertNotIn("factor:establishment-death-job-losses", by_factor)

    def test_exact_series_with_accepted_history_resolves_as_accepted(self):
        layoffs = CONFIG / "layoffs"
        bls_dol = load(layoffs / "sources_bls_dol.json")
        census = load(layoffs / "sources_census.json")
        context = load(layoffs / "sources_bea_fed_courts.json")
        fema = load(layoffs / "sources_fema.json")
        taxonomy = load(layoffs / "taxonomy.json")
        scheduler = load(layoffs / "scheduler.json")
        accepted_history = load(PACKAGE_ROOT / "review" / "layoffs-accepted-history.json")
        health = {
            row["sourceId"]: {"activationState": "ACCEPTED", "health": "disabled", "reasonCode": "ACCEPTED_HISTORY_AVAILABLE"}
            for row in scheduler["sources"]
        }
        states = MODULE.factor_states(bls_dol, census, context, fema, taxonomy, accepted_history, health)
        by_factor = {row["canonicalFactorId"]: row for row in states}
        self.assertEqual("ACCEPTED", by_factor["factor:canonical:average-weekly-hours"]["activationState"])
        self.assertIn("displayValue", by_factor["factor:canonical:average-weekly-hours"])


if __name__ == "__main__":
    unittest.main()
