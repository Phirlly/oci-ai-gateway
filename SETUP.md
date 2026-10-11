# Setup

Development preview: live GitHub deployment acceptance is pending. Budget for
Compute, storage, Vault and model usage while testing.

## Prerequisites

- An owned public GitHub repository with Actions enabled. Fork this repository or
  reuse a configured team repository. Deploy only reviewed, pushed commits.
  Keep the repository and deployed commit available during setup: the VM downloads
  that exact source and verifies every runtime file against its retained hashes.
- An OCI OC1 tenancy, existing compartment and subscribed hosting/inference
  regions. The selected image, shape and model must be available with capacity.
- An OCI signing identity permitted to manage Resource Manager, Compute/network,
  Vault/keys/secrets in that compartment; read regional
  metadata; and create the package's IAM policies in the tenancy home region.
  Your administrator must grant these permissions before deployment.
  [Resource Manager permissions](https://docs.oracle.com/en-us/iaas/Content/Identity/Reference/resourcemanagerpolicyreference.htm)
  and [native inference permissions](https://docs.oracle.com/en-us/iaas/Content/generative-ai/chat-permissions.htm)
  describe the service requirements.
- An Anthropic account/key with access to the configured external model.

The workflow creates the VM/network, reserved public IP, Vault/secret and scoped
instance permissions. The host signs OCI inference requests with its instance
identity; no OCI model API key is needed. Public ports 80/443
support HTTPS and certificate issuance; gateway/database ports stay private.

## Configure once

1. Copy [deployment.tfvars.json.example](deployment.tfvars.json.example) to
   `deployment.tfvars.json`. Replace tenancy/compartment placeholders, choose a
   unique deployment ID and set the presenter email. Review both model IDs,
   regions, exact image build and VM size. Keep this local file out of Git.
2. Create the GitHub environment **gateway** under **Settings → Environments**.
   Restrict it to your reviewed deployment branch. This repository uses `dev`.
3. Add environment variable **DEPLOYMENT_CONFIG** containing the complete JSON
   file. To upload the file unchanged using GitHub CLI:

   ```sh
   gh variable set DEPLOYMENT_CONFIG --env gateway < deployment.tfvars.json
   ```

4. Add two more **environment variables**:

   | Name | Value |
   |---|---|
   | `OCI_USER_OCID` | OCI signing user's OCID |
   | `OCI_FINGERPRINT` | Registered signing key fingerprint |

   Keep tenancy, compartment, regions, models and resource settings only in
   `DEPLOYMENT_CONFIG`. Do not duplicate them as individual GitHub variables.

5. Add these three required **environment secrets**:

   | Name | Value |
   |---|---|
   | `OCI_PRIVATE_KEY` | Matching PEM private key: unencrypted PKCS8/RSA or encrypted PKCS8 |
   | `ANTHROPIC_API_KEY` | Anthropic API key |
   | `DEMO_PASSWORD` | Presenter password: 12–256 characters including uppercase, lowercase, number and symbol |

   Only for an encrypted PKCS8 private key, add `OCI_PRIVATE_KEY_PASSPHRASE` as
   an additional secret. Leave it unset for an unencrypted key. `OPENAI_API_KEY`
   is not used by this OCI + Anthropic configuration.

`DEMO_PASSWORD` is the browser login password. Never place passwords/API keys in
the settings JSON. GitHub's built-in token records recovery history; no personal
GitHub token is required by the workflow. Local OCI profile names, including
`DEFAULT`, are not deployment settings and are not used on GitHub runners.
Configure only **gateway**. The workflow maintains **gateway-submissions**
automatically for nonsecret recovery records; it needs no secrets or setup.

Existing setups with `OCI_USER_OCID` and `OCI_FINGERPRINT` stored as secrets:
create the matching variables before adopting this workflow revision. Run
**Status** on the updated branch, then remove the two old secrets after it passes.
Start new runs from the updated branch; older workflow revisions still use secrets.

## Run the demo

Open **Actions → Gateway demo → Run workflow** on the permitted branch. Choose
**Deploy**. It submits Terraform, delivers runtime credentials through Vault,
creates restricted presenter access and verifies eight samples.

The run summary reports status, Compare URL, username and sample results. Open
the URL only after **Ready**, sign in with `DEMO_PASSWORD`, select `oci-managed`
and `external-anthropic`, then use [the presenter script](demo/PROMPT.md).

**Status** makes no model calls. **Verify samples** repeats the eight samples
using the current presenter password. Only completed HTTP429 responses permit
retries: at most three attempts per sample, 24 total. Waits start at 2 then 4
seconds, honor longer numeric retry guidance up to 30 seconds, and share each
sample's 90-second deadline. Unsupported guidance, timeouts and other failures
stop that sample. Results show attempts, elapsed time and safe error metadata;
they do not establish the cause of a rate limit. Any failed sample means not ready.
Inspect workflow and Resource Manager status before rerunning after an interruption.

Vault reads wait briefly for new versions and in-progress updates. A confirmed
ETag rejection of credential staging permits up to three attempts, each after
ownership and saved-state checks. Uncertain writes are not replayed. If credential
verification still fails, retain the saved state before another Deploy.
Failed runs log any verified OCI HTTP status and recognized service error code;
request contents and detailed error payloads remain suppressed.

## Reuse and adapt

- Reuse the same settings, repository and environment for the same deployment.
  Its original package/settings and credentials are preserved on reruns.
- To change regions, models, image, size or presenter identity, remove the old
  deployment and use a new deployment ID. Do not edit recovery history or stack
  variables manually. Native instance credentials refresh automatically; external
  API credentials remain subject to their provider's account policy.
- If the presenter changes their password, update `DEMO_PASSWORD` for verification.
  Deploy does not reset an initialized account.
- The supported routes are OCI's native Chat API and Anthropic's native adapter.
  The example uses Gemini Flash-Lite through OCI; that model is hosted by Google.
  An `OPENAI_API_KEY` secret alone does not add an OpenAI route.
  Changing providers requires a reviewed adapter/configuration change and tests.
- Sample requests and expected categories are separate files under `demo/`.
  Add synthetic workloads there; do not submit customer data for this demo.

## Remove

Choose **Remove** with the same configuration and OCI signing identity. Cleanup
uses OCI APIs and Resource Manager, so it works when the VM is stopped or
unreachable. Provider keys and presenter login are not required.

Removal destroys managed infrastructure. Legacy version2 deployments also remove
their owned model keys and require the corresponding OCI permission. Resource
Manager stack/state, GitHub recovery records and scheduled Vault/secret deletion
may remain. The supplied compartment, OCI identity and Anthropic account/key are
preserved. Keep recovery records until cleanup is confirmed. If deletion evidence
is ambiguous after an interruption, automation stops for reconciliation instead
of reporting success.
Resume interrupted removal with the current controller; do not downgrade it
after cleanup has started.

Existing version2 deployments retain their original settings and package for
Status, Verify and Remove. Use version3 and a fresh deployment ID for native
signing; do not change the schema of an existing deployment. No model-key TTL
setting is used in version3.

This single-VM demonstration does not provide high availability, automated
credential rotation or production backup/restore.
