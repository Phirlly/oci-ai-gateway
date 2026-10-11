"""Provider version vectors and dynamic sample totals preserve no-replay evidence."""

import tempfile
import unittest
from pathlib import Path

from runtime.console_state import ConsoleState
from runtime.gateway_http import GatewayError
from .optional_console_fixture import context
from .optional_fixture import SUBSETS


class OptionalConsoleStateTests(unittest.TestCase):
    def test_all_selections_accept_only_exact_versions_and_complete_sample_count(self):
        for providers in SUBSETS:
            with self.subTest(providers=providers), tempfile.TemporaryDirectory() as directory:
                state = ConsoleState(Path(directory), context(providers), "ocid1.vaultsecret.oc1.iad.context")
                record = state.begin()
                self.assertEqual(record["total"], 4 * len(providers))
                self.assertIsNone(record["provider_versions"])
                record.update(provider_versions={p: 1 for p in providers if p != "oci"}, phase="active")
                state.save(record)
                self.assertEqual(state.load()["phase"], "active")
                record.update(phase="complete", result="READY", passed=4 * len(providers), finished_at="2026-10-11T12:00:00Z")
                state.save(record)
                record["passed"] -= 1
                with self.assertRaises(GatewayError):
                    state.save(record)

    def test_unpinned_or_incomplete_vector_cannot_mark_active(self):
        with tempfile.TemporaryDirectory() as directory:
            state = ConsoleState(Path(directory), context(), "ocid1.vaultsecret.oc1.iad.context")
            record = state.begin()
            for versions in (None, {}, {"anthropic": 1}, {"anthropic": 1, "openai": 0}):
                with self.subTest(versions=versions), self.assertRaises(GatewayError):
                    state.save(record | {"phase": "active", "provider_versions": versions})
