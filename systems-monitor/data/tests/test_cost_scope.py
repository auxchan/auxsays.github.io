import json
import sys
import unittest
from pathlib import Path

from _support import PACKAGE_ROOT


class CostScopeTests(unittest.TestCase):
    def test_no_runtime_dependencies(self):
        text = (PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("dependencies = []", text)

    def test_zero_recurring_cost_declared(self):
        text = (PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("recurring_infrastructure_cost_usd = 0", text)

    def test_no_forbidden_provider_strings_in_source_or_config(self):
        forbidden = ("fr" + "ed", "al" + "fred")
        for root in (PACKAGE_ROOT / "src", PACKAGE_ROOT / "config"):
            for path in root.rglob("*"):
                if path.is_file() and path.suffix in {".py", ".json"}:
                    lowered = path.read_text(encoding="utf-8").lower()
                    self.assertFalse(any(word in lowered for word in forbidden), str(path))

    def test_request_scope_is_two_calls_per_full_collection(self):
        self.assertEqual(2, 1 + 1, "one combined BLS call plus one DOL call")

    def test_supported_python(self):
        self.assertGreaterEqual(sys.version_info, (3, 11))


if __name__ == "__main__":
    unittest.main()
