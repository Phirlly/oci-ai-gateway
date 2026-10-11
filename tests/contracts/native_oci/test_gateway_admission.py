"""Caller endpoint, identity and transport overrides never acquire authority."""

from admission_fixture import AdmissionCase


class GatewayAdmission(AdmissionCase):
    async def test_endpoint_provider_scope_and_model_overrides_are_denied(self):
        for name, value in (("api_base", "https://synthetic.invalid"),
                            ("base_url", "https://synthetic.invalid"),
                            ("custom_llm_provider", "openai"), ("oci_region", "us-chicago-1"),
                            ("oci_compartment_id", "ocid1.compartment.oc1..other"),
                            ("model", "oci/other")):
            await self.deny({name: value})

    async def test_credential_and_transport_overrides_are_denied(self):
        for name, value in (("api_key", "synthetic-caller-key"), ("oci_key", "synthetic-key"),
                            ("oci_key_file", "/synthetic/path"), ("oci_signer", "synthetic"),
                            ("oci_user", "synthetic"), ("oci_tenancy", "synthetic"),
                            ("oci_fingerprint", "synthetic"), ("client", {}),
                            ("extra_headers", {"host": "synthetic.invalid"}),
                            ("headers", {"authorization": "synthetic"}),
                            ("default_headers", {"host": "synthetic.invalid"}),
                            ("provider_specific_header", {"custom_llm_provider": "oci",
                                                          "extra_headers": {"Host": "synthetic.invalid"}})):
            await self.deny({name: value})

    async def test_missing_and_wrong_gateway_auth_do_not_sign_or_send(self):
        for key in (None, "sk-synthetic-wrong"):
            with self.subTest(key=key):
                response = await self.request(key=key)
                self.assertIn(response.status_code, (400, 401, 403))
                self.assertEqual(self.socket.requests, [])
                self.assertEqual(self.upstream.requests, [])


class GatewayCredentialOptIn(AdmissionCase):
    allow_client_credentials = True

    async def test_policy_still_denies_endpoint_and_key_with_proxy_opt_in(self):
        for name, value in (("api_base", "https://synthetic.invalid"),
                            ("base_url", "https://synthetic.invalid"), ("api_key", "synthetic")):
            await self.deny({name: value})
