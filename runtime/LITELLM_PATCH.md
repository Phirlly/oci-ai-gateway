# Native OCI compatibility correction

The candidate uses the original pinned LiteLLM image with two verified source
replacements. Version3 deployment packages prepare and mount them automatically;
live cloud acceptance is still pending.

- Upstream: [LiteLLM source](https://github.com/BerriAI/litellm/tree/79645770fedc7ec2627e6468d31062f20f82aecc).
- Patch: [litellm_oci.patch](litellm_oci.patch); original notice: [LITELLM_LICENSE](LITELLM_LICENSE).
- Preparation: [oci_adapter_overlay.py](oci_adapter_overlay.py) checks original,
  patch and result SHA256 values and applies the patch in a temporary directory.
- Changes: reject unsuccessful or incomplete native responses, release streaming
  HTTP responses, and prevent inference dispatch after cancellation during signing.
- Verification: `python3.12 -m tests.contracts.native_oci`; see
  [local prerequisites](LOCAL_TESTING.md).

The production callback reads the existing `/app/config.json` through
`runtime.oci_gateway_loader.INSTANCE`. It permits the two configured aliases,
rejects caller routing/credential overrides, and attaches `SocketSigner` only to
the configured native OCI route. Anthropic retains its adapter and usage reporting.

The offline proxy loads that production callback; only HTTP transport and the
host signing responder are synthetic. `python3.12 -m tests.contracts.native_deployment`
also starts the production Compose gateway/database with synthetic secrets and
isolated networking, checking callback admission and authentication. These checks
do not establish live systemd activation, effective IAM or real model readiness.
An image update requires reviewing the correction and updating verified hashes.
