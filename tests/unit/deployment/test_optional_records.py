"""Controller credential records bind provider selection without bearer lifecycle."""

import json
import unittest

from deployment.credential_errors import DeliveryError
from deployment.credential_records import parse_record
from tests.unit.runtime.optional_fixture import SUBSETS, document


class OptionalRecordTests(unittest.TestCase):
    def test_each_selection_has_no_generated_key_or_expiry(self):
        for providers in SUBSETS:
            with self.subTest(providers=providers):
                value = document(providers)
                record = parse_record(json.dumps(value).encode(), value["identity"])
                self.assertTrue(record.is_native)
                self.assertIsNone(record.model_key_ocid)
                self.assertIsNone(record.expires_at)

    def test_disabled_missing_or_mixed_schema_credentials_are_rejected(self):
        for change in ("missing", "disabled", "legacy"):
            value = document(("openai",))
            if change == "missing":
                del value["credentials"]["openai_api_key"]
            elif change == "disabled":
                value["credentials"]["anthropic_api_key"] = "synthetic-disabled"
            else:
                value["schema_version"] = 3
            with self.subTest(change=change), self.assertRaises(DeliveryError):
                parse_record(json.dumps(value).encode(), value["identity"])
