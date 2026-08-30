import socket
import unittest
from unittest.mock import patch

from _support import CONFIG
from systems_monitor_data.retrieval import BoundedRetriever, RequestBudget, bls_request_body
from systems_monitor_data.security import redact_mapping, sanitize_url, validate_url


def resolver_for(address):
    return lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]


class SecurityRetrievalTests(unittest.TestCase):
    def test_https_allowlist(self):
        self.assertEqual("https://api.bls.gov/path", validate_url("https://api.bls.gov/path", resolver=resolver_for("23.1.1.1")))

    def test_http_rejected(self):
        with self.assertRaises(ValueError):
            validate_url("http://api.bls.gov/path", resolver=resolver_for("23.1.1.1"))

    def test_unknown_host_rejected(self):
        with self.assertRaises(ValueError):
            validate_url("https://example.com/path", resolver=resolver_for("23.1.1.1"))

    def test_private_ip_rejected(self):
        with self.assertRaises(ValueError):
            validate_url("https://api.bls.gov/path", resolver=resolver_for("127.0.0.1"))

    def test_metadata_ip_rejected(self):
        with self.assertRaises(ValueError):
            validate_url("https://api.bls.gov/path", resolver=resolver_for("169.254.169.254"))

    def test_embedded_credentials_rejected(self):
        with self.assertRaises(ValueError):
            validate_url("https://user:secret@api.bls.gov/path", resolver=resolver_for("23.1.1.1"))

    def test_query_secret_redacted(self):
        self.assertIn("registrationkey=REDACTED", sanitize_url("https://api.bls.gov/x?registrationkey=secret&x=1"))

    def test_header_secret_redacted(self):
        self.assertEqual("REDACTED", redact_mapping({"Authorization": "secret"})["Authorization"])

    def test_bls_scope_bound(self):
        with self.assertRaises(ValueError):
            bls_request_body([str(i) for i in range(26)], 2020, 2020)

    def test_bls_history_bound(self):
        with self.assertRaises(ValueError):
            bls_request_body(["x"], 2010, 2020)

    def test_retry_is_bounded(self):
        retriever = BoundedRetriever(max_attempts=2, sleeper=lambda _: None)
        with patch.object(retriever, "_request", side_effect=TimeoutError("x")) as mocked, self.assertRaises(RuntimeError):
            retriever.fetch("https://api.bls.gov/x", expected_types=("application/json",))
        self.assertEqual(2, mocked.call_count)

    def test_daily_request_budget(self):
        budget = RequestBudget(max_per_day=2, max_per_10_seconds=10)
        budget.record(100000); budget.record(100001)
        with self.assertRaises(RuntimeError): budget.record(100002)

    def test_rate_request_budget(self):
        budget = RequestBudget(max_per_day=10, max_per_10_seconds=2)
        budget.record(100000); budget.record(100001)
        with self.assertRaises(RuntimeError): budget.record(100002)


if __name__ == "__main__":
    unittest.main()
