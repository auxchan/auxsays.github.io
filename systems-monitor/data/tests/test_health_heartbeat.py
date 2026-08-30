import unittest

from _support import CONFIG
from systems_monitor_data.health import evaluate_health, heartbeat_due, source_work_due
from systems_monitor_data.registry import Registry


class HealthHeartbeatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = Registry(CONFIG)
        cls.monthly = cls.registry.source("bls-ces")["health_policy"]

    def test_current(self):
        self.assertEqual("current", evaluate_health(self.monthly, now="2026-08-18T00:00:00Z", last_retrieval="2026-08-01T00:00:00Z", last_validation="2026-08-01T00:00:00Z"))

    def test_delayed(self):
        self.assertEqual("delayed", evaluate_health(self.monthly, now="2026-09-10T00:00:00Z", last_retrieval="2026-08-01T00:00:00Z", last_validation="2026-08-01T00:00:00Z"))

    def test_stale(self):
        self.assertEqual("stale", evaluate_health(self.monthly, now="2026-11-01T00:00:00Z", last_retrieval="2026-08-01T00:00:00Z", last_validation="2026-08-01T00:00:00Z"))

    def test_unavailable(self):
        self.assertEqual("unavailable", evaluate_health(self.monthly, now="2026-08-18T00:00:00Z", last_retrieval=None, last_validation=None))

    def test_schema_change(self):
        self.assertEqual("schema_format_changed", evaluate_health(self.monthly, now="2026-08-18T00:00:00Z", last_retrieval=None, last_validation=None, failure="schema_format_changed"))

    def test_validation_failure(self):
        self.assertEqual("validation_failed", evaluate_health(self.monthly, now="2026-08-18T00:00:00Z", last_retrieval=None, last_validation=None, failure="validation_failed"))

    def test_rights_blocked(self):
        self.assertEqual("rights_blocked", evaluate_health(self.monthly, now="2026-08-18T00:00:00Z", last_retrieval="2026-08-01T00:00:00Z", last_validation="2026-08-01T00:00:00Z", rights_allowed=False))

    def test_four_hour_heartbeat(self):
        self.assertTrue(heartbeat_due("2026-08-18T00:00:00Z", "2026-08-18T04:00:00Z"))

    def test_heartbeat_does_not_force_monthly_fetch(self):
        self.assertFalse(source_work_due(self.monthly, last_success="2026-08-18T00:00:00Z", now="2026-08-18T04:00:00Z"))


if __name__ == "__main__":
    unittest.main()

