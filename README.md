# OCI AI Gateway

Compare an OCI-managed model and Anthropic through LiteLLM Compare, hosted on
OCI. Terraform runs through OCI Resource Manager; a CPU VM runs the pinned
LiteLLM, PostgreSQL and Caddy images.

**Development preview.** The direct Resource Manager package is under validation;
the deploy button will be published after Console and live-model acceptance.

## Deploy and demonstrate

The primary deployment path is [OCI Resource Manager](RESOURCE_MANAGER.md):
create the stack, Apply, save your Anthropic key in the created secret, and open
the deployment status. Setup creates the presenter and runs eight samples.
After **Ready**, open Compare with the generated presenter credentials, select
both models and run the [sample](demo/PROMPT.md).

For configured teams, [GitHub Actions](SETUP.md) remains an optional entrypoint:

| Workflow action | Result |
|---|---|
| Deploy | Provision resources, configure models and presenter, run bundled samples |
| Status | Inspect infrastructure and health without model calls |
| Verify samples | Check login, access, both model routes and streaming |
| Remove | Remove deployment-owned resources without needing a working VM |

**Ready** requires trusted HTTPS, presenter login and successful samples through
both real model routes. Reuse the same deployment for another demonstration.
OCI supplies hosting, networking, secret delivery, resource automation and managed
inference; Anthropic supplies the external route.

See [Resource Manager setup and cleanup](RESOURCE_MANAGER.md), [GitHub setup](SETUP.md) and
[local verification](runtime/LOCAL_TESTING.md). License: [MIT](LICENSE).
