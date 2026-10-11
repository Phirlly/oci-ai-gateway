"""One and three model journeys require exact access before making model calls."""

import json
import unittest
from unittest.mock import Mock, patch

from demo.verification import presenter_client
from runtime.gateway_http import GatewayError, Response
from runtime.presenter import Presenter


class OptionalVerificationTests(unittest.TestCase):
    def test_exact_enabled_models_allow_session_but_missing_extra_or_duplicate_models_fail(self):
        for models in (("external-openai",), ("oci-managed", "external-anthropic", "external-openai")):
            presenter = Presenter("gateway-test", "presenter@example.invalid", models)
            for rows, succeeds in ((models, True), ((), False), (models + ("disabled",), False),
                                   ((models[0],) * (len(models) + 1), False)):
                public = Mock(base_url="https://8.8.4.4")
                public.request.return_value = Response(200, b'{}', {})
                session = Mock()
                session.request.side_effect = [Response(200, json.dumps({"data": [{"model_group": m} for m in rows]}).encode(), {}),
                                               Response(403, b'{}', {})]
                with self.subTest(models=models, rows=rows), \
                        patch("demo.verification.presenter_session", return_value="synthetic"), \
                        patch("demo.verification.GatewayHTTP", return_value=session):
                    if succeeds:
                        self.assertIs(presenter_client(public, presenter, "Synthetic9!Password"), session)
                    else:
                        with self.assertRaises(GatewayError):
                            presenter_client(public, presenter, "Synthetic9!Password")
