"""Native bundle records require exact ownership and no bearer-only fields."""

import json
import unittest
from datetime import datetime, timezone

from deployment.credential_errors import DeliveryError
from deployment.credential_records import parse_record
from .native_fixture import native_document
from .record_fixtures import IDENTITY


class NativeRecordTests(unittest.TestCase):
    def test_native_record_has_no_manufactured_key_expiry(self):
        record = parse_record(json.dumps(native_document()).encode(), IDENTITY)
        self.assertTrue(record.is_native)
        self.assertIsNone(record.model_key_ocid)
        self.assertIsNone(record.expires_at)
        record.require_unexpired(datetime(2040, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(record.version_name, "runtime-" + "a" * 32)

    def test_legacy_fields_or_missing_credentials_are_not_native_records(self):
        changes = [{"expires_at": "2040-01-01T00:00:00Z"},
                   {"model_key_ocid": "ocid1.generativeaiapikey.oc1.iad.synthetic"},
                   {"kind": "creation-intent"}, {"schema_version": 2}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(DeliveryError):
                parse_record(json.dumps(native_document() | change).encode(), IDENTITY)
        value = native_document()
        value["credentials"]["oci_api_key"] = "secret-sentinel"
        with self.assertRaises(DeliveryError) as raised:
            parse_record(json.dumps(value).encode(), IDENTITY)
        self.assertNotIn("secret-sentinel", str(raised.exception))

    def test_owner_context_and_password_are_validated(self):
        for field, value in (("identity", {}), ("runtime", {}), ("operation_id", "")):
            with self.subTest(field=field), self.assertRaises(DeliveryError):
                parse_record(json.dumps(native_document() | {field: value}).encode(), IDENTITY)
        value = native_document()
        value["credentials"]["demo_password"] = "weak"
        with self.assertRaises(DeliveryError):
            parse_record(json.dumps(value).encode(), IDENTITY)
