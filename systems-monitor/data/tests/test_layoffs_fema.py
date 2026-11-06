import copy
import json
import unittest

from _support import CONFIG, FIXTURES
from systems_monitor_data.layoffs_fema import (
    event_revision_key,
    load_layoffs_fema_registry,
    parse_fema_declarations,
    plan_fema_request,
)


class LayoffsFemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_layoffs_fema_registry(CONFIG / "layoffs" / "sources_fema.json")
        cls.source = cls.registry["sources"][0]
        cls.payload = (FIXTURES / "layoffs_fema_declarations_minimized.json").read_bytes()

    def test_request_is_bounded_deterministic_and_credential_free(self):
        url = plan_fema_request(self.source, declared_since="2026-09-01T00:00:00Z")
        self.assertIn("DisasterDeclarationsSummaries", url)
        self.assertIn("declarationDate", url)
        self.assertNotIn("token", url.lower())

    def test_parser_emits_event_not_scalar_observation(self):
        events = parse_fema_declarations(
            self.payload,
            self.source,
            artifact_sha256="a" * 64,
            retrieved_time="2026-09-29T17:02:31Z",
            provenance_url=self.source["endpoint"],
        )
        self.assertEqual(1, len(events))
        event = events[0]
        self.assertEqual("EM-3654-HI", event.declaration_id)
        self.assertEqual("Hawaii (County)", event.designated_area)
        self.assertEqual("EVENT_SOURCE_IDENTIFIED_PENDING_ACCEPTANCE", event.activation_state)
        self.assertFalse(event.publication_eligible)
        self.assertNotIn("value", event.__dataclass_fields__)
        self.assertIn("NOT_CAUSAL", event.relationship_boundary)
        self.assertEqual(64, len(event_revision_key(event)))

    def test_schema_drift_and_duplicates_fail_closed(self):
        document = json.loads(self.payload)
        missing = copy.deepcopy(document)
        del missing["DisasterDeclarationsSummaries"][0]["designatedArea"]
        with self.assertRaisesRegex(ValueError, "required fields"):
            parse_fema_declarations(json.dumps(missing).encode(), self.source, artifact_sha256="b" * 64, retrieved_time="2026-09-29T17:02:31Z", provenance_url=self.source["endpoint"])
        duplicate = copy.deepcopy(document)
        duplicate["DisasterDeclarationsSummaries"].append(copy.deepcopy(duplicate["DisasterDeclarationsSummaries"][0]))
        with self.assertRaisesRegex(ValueError, "duplicated"):
            parse_fema_declarations(json.dumps(duplicate).encode(), self.source, artifact_sha256="c" * 64, retrieved_time="2026-09-29T17:02:31Z", provenance_url=self.source["endpoint"])


if __name__ == "__main__":
    unittest.main()
