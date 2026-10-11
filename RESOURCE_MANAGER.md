# Resource Manager deployment

**Candidate under validation.** The release ZIP and deploy button are not yet
published. Console rendering, secret generation and fresh live deployment still
require acceptance. GitHub Actions remains available through [setup](SETUP.md).

## Prerequisites

- An OCI OC1 tenancy, compartment and subscribed hosting/inference regions.
- Permission to manage Resource Manager, Compute/network, Vault/keys/secrets and
  the deployment's IAM policies in the tenancy home region; read regional metadata.
- Capacity for an E4/E5 Flex AMD VM and a regional Canonical Ubuntu24.04 image.
- Access to the configured OCI Chat model and an Anthropic key for its model.

The defaults match the existing deployment: OCI `google.gemini-2.5-flash-lite`
and Anthropic `claude-sonnet-4-6`. Availability depends on region/account;
OCI's Gemini route is hosted by Google. Budget for resources and model calls.

## Deploy and demonstrate

1. In Resource Manager, create a stack from the prepared **Console ZIP**. The
   candidate must come from a reviewed, publicly available source commit. A raw
   GitHub source ZIP is not the prepared package.
2. Select the compartment, unique deployment name, availability domain and
   Ubuntu24.04 AMD image. Review models, regions and presenter username. **Apply**.
3. Open **Save Anthropic key** in stack outputs. Create a plain-text secret
   version containing your key; make it **CURRENT**. Do not put keys/passwords
   in stack variables. The stack creates the Vault and secret containers.
4. Open **Check last verification**. Installation/TLS may take several minutes.
   Missing credentials show `WAITING_CREDENTIALS`. **READY** requires trusted
   HTTPS, presenter login/access and all eight samples through the two models.
5. Open **View presenter password**, view the secret contents and copy its
   `password` field. Sign into **Open Compare** with the reported username.
   Select both models and follow the [short demo script](demo/PROMPT.md).

The VM installs the pinned applications, generates its internal credentials,
creates the presenter and runs the bundled samples. No GitHub fork, runner
credentials, OCI API-key upload, local CLI or SSH is required by this path.
Source installation verifies hashes from the package's exact public Git commit.

## Repeat or recover

- Reuse Compare without redeploying. Status reports the **last verification**,
  not continuous model health. Ordinary status polling makes no model calls.
- To retry failed/interrupted samples or activate a corrected Anthropic key,
  increase **verification_run** and Apply. Runs range from 1 to 20 and never decrease.
  Each run allows eight samples, with bounded retries only for completed HTTP429
  responses. Uncertain model calls are never automatically replayed.
- Setup retries preserve the database, internal keys and initialized presenter.
  If you change the presenter password in the UI, update the presenter secret's
  `password` field to the current value for subsequent verification.
- Keep deployment identity, models, region, image and presenter identity unchanged.
  Use a new deployment for those changes or after 20 verification runs. Remove
  the old deployment if it is no longer needed.
- `WAITING_FRONTEND` waits for public HTTPS/login. `ERROR` before verification
  retries setup; a completed `ERROR`, `FAILED` or `INTERRUPTED` requires a new run.
  Check OCI service logs/IAM/model access when setup cannot complete.

## Remove

Run **Destroy** in Resource Manager. It removes deployment-owned resources even
when the VM is unavailable. Vaults/secrets may remain scheduled for deletion.
Confirm Destroy succeeded before deleting the stack. The supplied compartment,
OCI identity and Anthropic account/key are preserved.

This single-VM demo has no high availability, automated credential rotation or
production backup/restore.
