"""Offline envelope tests; vendor into each service's tests/ directory."""

from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("feed_validator", ROOT / "scripts/validate_feed.py")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)
NOW = dt.datetime(2026, 10, 1, 12, tzinfo=dt.timezone.utc)


class FeedContractTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads((ROOT / "schema.json").read_text(encoding="utf-8"))
        self.feed = {
            "service": ROOT.name,
            "schema_version": "1.0",
            "generated_at": NOW.isoformat(),
            "status": "active",
            "ttl_hours": 30,
            "data": {},
        }

    def check(self, feed):
        validator.validate_feed(feed, self.schema, ROOT.name, NOW)

    def test_valid_and_explicit_degraded_states(self):
        self.check(self.feed)
        for status in ["partial", "unavailable"]:
            self.check({**self.feed, "status": status, "notes": "Provider unavailable"})

    def test_invalid_fields_fail_closed(self):
        for key, values in {
            "service": ["other_service"],
            "status": ["unknown"],
            "generated_at": [
                "bad",
                "1970-01-01T00:00:00Z",
                "2026-10-01T12:00:00",
                "2026-10-02T12:00:00Z",
                "2026-09-01T00:00:00Z",
            ],
            "ttl_hours": [0, -1, True, float("nan"), float("inf")],
            "data": [[], None],
        }.items():
            for value in values:
                with (
                    self.subTest(key=key, value=value),
                    self.assertRaises((ValueError, validator.jsonschema.ValidationError)),
                ):
                    self.check({**self.feed, key: value})

    def test_missing_required_fields_rejected(self):
        for key in self.schema["required"]:
            feed = copy.deepcopy(self.feed)
            del feed[key]
            with self.subTest(key=key), self.assertRaises(validator.jsonschema.ValidationError):
                self.check(feed)

    def test_degraded_state_needs_explanation(self):
        for status in ["partial", "unavailable"]:
            with self.assertRaises(ValueError):
                self.check({**self.feed, "status": status})

    def test_nested_nonfinite_numbers_and_json_constants_rejected(self):
        with self.assertRaises(ValueError):
            self.check({**self.feed, "data": {"last": float("nan")}})
        for value in ["NaN", "Infinity", "-Infinity"]:
            with self.assertRaises(ValueError):
                json.loads('{"last":' + value + "}", parse_constant=validator.reject_constant)


if __name__ == "__main__":
    unittest.main()
