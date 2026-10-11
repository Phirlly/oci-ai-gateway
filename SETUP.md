# GitHub Actions setup (optional)

For direct OCI Console deployment, use [Resource Manager](RESOURCE_MANAGER.md).
Budget for Compute, storage, Vault and model usage while testing.

## Prerequisites

- An owned public GitHub repository with Actions enabled. Fork this repository or
  reuse a configured team repository. Deploy only reviewed, pushed commits.
  Keep the repository and deployed commit available during setup: the VM downloads
  that exact source and verifies every runtime file against its retained hashes.
- An OCI OC1 tenancy, existing compartment and subscribed hosting region.
  OCI inference additionally needs its subscribed inference region. The selected
  image, shape and models must be available with capacity/account access.
- An OCI signing identity permitted to manage Resource Manager, Compute/network,
  Vault/keys/secrets in that compartment; read regional
  metadata; and create the package's IAM policies in the tenancy home region.
  Your administrator must grant these permissions before deployment.
  [Resource Manager permissions](https://docs.oracle.com/en-us/iaas/Content/Identity/Reference/resourcemanagerpolicyreference.htm)
  and [native inference permissions](https://docs.oracle.com/en-us/iaas/Content/generative-ai/chat-permissions.htm)
  describe the service requirements.
- An Anthropic or OpenAI account/key only for each enabled external provider.

The workflow creates the VM/network, reserved public IP, Vault/secret and scoped
instance permissions. The host signs OCI inference requests with its instance
identity; no OCI model API key is needed. Public ports 80/443
support HTTPS and certificate issuance; gateway/database ports stay private.

## Configure once

1. Copy [deployment.tfvars.json.example](deployment.tfvars.json.example) to
   `deployment.tfvars.json`. Replace tenancy/compartment placeholders, choose a
   unique deployment ID and set the presenter email. Review enabled model IDs,
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

5. Add the required **environment secrets**, plus keys for enabled providers:

   | Name | Value |
   |---|---|
   | `OCI_PRIVATE_KEY` | Matching PEM private key: unencrypted PKCS8/RSA or encrypted PKCS8 |
   | `ANTHROPIC_API_KEY` | Required only when `models.anthropic` is present |
   | `OPENAI_API_KEY` | Required only when `models.openai` is present |
   | `DEMO_PASSWORD` | Presenter password: 12–256 characters including uppercase, lowercase, number and symbol |

   Only for an encrypted PKCS8 private key, add `OCI_PRIVATE_KEY_PASSPHRASE` as
   an additional secret. Leave it unset for an unencrypted key. Disabled provider
   keys are not required or published, even if saved in the GitHub environment.

The example enables only OCI. Add either or both external entries to `models`:

```json
"models": {
  "oci": "google.gemini-2.5-flash-lite",
  "anthropic": "claude-sonnet-4-6",
  "openai": "gpt-4.1-mini-2025-04-14"
}
```

Omit a provider to disable it; keep at least one. If you omit `oci`, also omit
`inference_region`. No parallel enable flags or external-model fields are used.

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
creates restricted presenter access and verifies four samples per enabled model.

The run summary reports status, Compare URL, username and sample results. Open
the URL only after **Ready**, sign in with `DEMO_PASSWORD`, select the enabled
models, then use [the presenter script](demo/PROMPT.md).

**Status** makes no model calls. **Verify samples** repeats the4,8 or12 samples
using the current presenter password. Only completed HTTP429 responses permit
retries: at most three attempts per sample. Waits start at 2 then 4
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
- To change providers, regions, models, image, size or presenter identity, remove the old
  deployment and use a new deployment ID. Do not edit recovery history or stack
  variables manually. Native instance credentials refresh automatically; external
  API credentials remain subject to their provider's account policy.
- If the presenter changes their password, update `DEMO_PASSWORD` for verification.
  Deploy does not reset an initialized account.
- The supported routes use OCI native Chat, Anthropic and OpenAI Chat Completions
  through the pinned LiteLLM adapters. One model per enabled provider.
  The example uses Gemini Flash-Lite through OCI; that model is hosted by Google.
  An API key alone does not enable a route; select it in `models` for a fresh
  deployment. Other adapters and request types need separate validation.
- Sample requests and expected categories are separate files under `demo/`.
  Add synthetic workloads there; do not submit customer data for this demo.

## Remove

Choose **Remove** with the same configuration and OCI signing identity. Cleanup
uses OCI APIs and Resource Manager, so it works when the VM is stopped or
unreachable. Provider keys and presenter login are not required.

Removal destroys managed infrastructure. Legacy version2 deployments also remove
their owned model keys and require the corresponding OCI permission. Resource
Manager stack/state, GitHub recovery records and scheduled Vault/secret deletion
may remain. The supplied compartment, OCI identity and external accounts/keys are
preserved. Keep recovery records until cleanup is confirmed. If deletion evidence
is ambiguous after an interruption, automation stops for reconciliation instead
of reporting success.
Resume interrupted removal with the current controller; do not downgrade it
after cleanup has started.

Existing version2/3 deployments retain their original settings and package for
recovery. Use version4 and a fresh deployment ID for optional providers; never
change an existing deployment's schema. Version4 uses no OCI model-key TTL.

This single-VM demonstration does not provide high availability, automated
credential rotation or production backup/restore.
