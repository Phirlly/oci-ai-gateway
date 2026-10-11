# Native OCI compatibility correction

The candidate uses the original pinned LiteLLM image with two verified source
replacements. It is **not activated in cloud deployments yet**.

- Upstream: [LiteLLM source](https://github.com/BerriAI/litellm/tree/79645770fedc7ec2627e6468d31062f20f82aecc).
- Patch: [litellm_oci.patch](litellm_oci.patch); original notice: [LITELLM_LICENSE](LITELLM_LICENSE).
- Preparation: [oci_adapter_overlay.py](oci_adapter_overlay.py) checks original,
  patch and result SHA256 values and applies the patch in a temporary directory.
- Changes: reject unsuccessful or incomplete native responses, release streaming
  HTTP responses, and prevent inference dispatch after cancellation during signing.
- Verification: `python3.12 -m tests.contracts.native_oci`; see
  [local prerequisites](LOCAL_TESTING.md).

The offline proxy fixture supplies test-only routing and transport. These checks
do not establish deployed callback policy, OCI IAM, real model access or readiness.
An image update requires reviewing the correction and updating verified hashes.
