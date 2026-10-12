# Resource Manager deployment

**Candidate under validation.** The release ZIP and deploy button are not yet
published. The saved-secret journey and complete fresh deployment still require
live acceptance. GitHub Actions remains available through [setup](SETUP.md).

## Prerequisites

- An OCI OC1 tenancy, compartment and subscribed hosting region.
- Permission to manage Resource Manager, Compute/network, Vault/keys/secrets and
  the deployment's IAM policies in the tenancy home region; read regional metadata.
- Capacity for an E4/E5 Flex AMD VM and a regional Canonical Ubuntu24.04 image.
- Access to each selected model. OCI inference needs a subscribed inference
  region; Anthropic/OpenAI need their own API keys only when enabled.
- For reusable external keys, save each key once as a **CURRENT plain-text**
  secret in an independently managed Vault, in the deployment compartment and
  hosting region. The deployer needs permission to list/read secret metadata.
  Never put keys in secret names, descriptions, tags or Terraform variables.

| Optional provider | Example model | Credential |
|---|---|---|
| OCI Generative AI (enabled by default) | `google.gemini-2.5-flash-lite` | VM instance identity; no model API key |
| Anthropic | `claude-sonnet-4-6` | Anthropic API key |
| OpenAI | `gpt-4.1-mini-2025-04-14` | OpenAI project API key |

Enable at least one provider, with one model per provider. Model IDs are
configurable within the supported adapters; access/compatibility must be verified.
Availability depends on region/account. OCI's Gemini route is hosted by Google.
Budget for resources and model calls.

## Deploy and demonstrate

1. In Resource Manager, create a stack from the prepared **Console ZIP**. The
   candidate must come from a reviewed, publicly available source commit. A raw
   GitHub source ZIP is not the prepared package.
2. Select the compartment, unique deployment name, availability domain and
   Ubuntu24.04 AMD image. Enable the providers you want and review their model
   IDs, inference region if using OCI, and presenter username. Select **Saved
   Anthropic key** and/or **Saved OpenAI key** for enabled external providers.
   Choose a different secret for each provider. **Apply**.
3. Saved keys need no further entry. If you left a selector blank, open that
   provider's **key secret** output and save its key as a **CURRENT plain-text**
   version. The stack creates these fallback secrets and their Vault. OCI-only
   needs no external keys. Terraform receives only secret IDs, never key contents.
4. Open **Check last verification**. Installation/TLS may take several minutes.
   Missing credentials show `WAITING_CREDENTIALS`. **READY** requires trusted
   HTTPS, presenter login/access and all samples: four per enabled model.
5. Open **View presenter password**, view the secret contents and copy its
   `password` field. Sign into **Open Compare** with the reported username.
   Select the enabled models and follow the [short demo script](demo/PROMPT.md).

The VM installs the pinned applications, generates its internal credentials,
creates the presenter and runs the bundled samples. No GitHub fork, runner
credentials, OCI API-key upload, local CLI or SSH is required by this path.
Source installation verifies hashes from the package's exact public Git commit.

## Repeat or recover

- Apply automatically waits up to three minutes for a new Vault's DNS/TLS
  endpoint before creating its key. If this readiness step times out, retry
  Apply on the same stack after checking OCI service availability. Destroy
  does not run this check.
- Reuse Compare without redeploying. Status reports the **last verification**,
  not continuous model health. Ordinary status polling makes no model calls.
- To retry failed/interrupted samples or activate corrected external keys,
  increase **verification_run** and Apply. Runs range from 1 to 20 and never decrease.
  Each run has4,8 or12 samples, with bounded retries only for completed HTTP429
  responses. Uncertain model calls are never automatically replayed.
- Setup retries preserve the database, internal keys and initialized presenter.
  If you change the presenter password in the UI, update the presenter secret's
  `password` field to the current value for subsequent verification.
- Keep deployment identity, models, region, image and presenter identity unchanged.
  Provider and saved-secret selections are also fixed for a deployment; update
  key contents in the same secret rather than selecting a different secret.
  A shared-key change may affect other deployments using it. Use a new deployment for
  those changes or after20 verification runs. Remove
  the old deployment if it is no longer needed.
- `WAITING_FRONTEND` waits for public HTTPS/login. `ERROR` before verification
  retries setup; a completed `ERROR`, `FAILED` or `INTERRUPTED` requires a new run.
  Check OCI service logs/IAM/model access when setup cannot complete.

## Remove

Run **Destroy** in Resource Manager. It removes deployment-owned resources even
when the VM is unavailable. Vaults/secrets may remain scheduled for deletion.
Confirm Destroy succeeded before deleting the stack. The supplied compartment,
OCI identity and external provider accounts/keys are preserved.

Selected saved secrets and their Vaults are preserved by this stack. Use shared
secrets independent of disposable deployments: deleting their original owning
stack would still remove them. Keep selected secrets and metadata-read permission
available until dependent stacks are removed; failed metadata reads can block
Terraform's pre-Destroy refresh.

This single-VM demo has no high availability, automated credential rotation or
production backup/restore.
