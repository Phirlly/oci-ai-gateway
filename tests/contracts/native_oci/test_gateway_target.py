"""Deployment hooks recheck startup scope before attaching the signer."""

from unittest.mock import MagicMock

from fastapi import HTTPException

from native_proxy_fixture import NativeProxyCase
from payload_fixture import COMPARTMENT, MODEL, ROUTE


class GatewayTarget(NativeProxyCase):
    async def test_mismatched_native_targets_never_receive_a_signer(self):
        for change in ({"model": "oci/other"}, {"oci_region": "us-chicago-1"},
                       {"oci_compartment_id": "ocid1.compartment.oc1..other"},
                       {"api_base": "https://synthetic.invalid"}, {"api_key": "synthetic"},
                       {"oci_signer": "synthetic"}, {"extra_body": {"compartmentId": "other"}}):
            with self.subTest(change=change):
                kwargs = {"model": "oci/" + MODEL, "oci_region": "us-ashburn-1",
                          "oci_compartment_id": COMPARTMENT, "litellm_logging_obj": MagicMock(), **change}
                with self.assertRaises(HTTPException) as caught:
                    await self.probe.async_pre_call_deployment_hook(kwargs, "acompletion")
                self.assertEqual(caught.exception.status_code, 400)
                self.assertNotIsInstance(kwargs.get("oci_signer"), type(self.probe.oci_signer))

    async def test_malformed_snapshots_have_a_fixed_rejection(self):
        for snapshot in (None, [], {"body": []}, {"body": {}, "credential_fields": [None]}):
            with self.subTest(snapshot=snapshot):
                with self.assertRaises(HTTPException) as caught:
                    await self.probe.async_pre_call_hook(None, None,
                        {"model": ROUTE, "proxy_server_request": snapshot}, "acompletion")
                self.assertEqual(caught.exception.status_code, 400)
