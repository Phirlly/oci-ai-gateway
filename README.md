# OCI AI Gateway

Use OCI Generative AI, Anthropic and OpenAI models through one OCI-hosted gateway
and LiteLLM Compare. Enable any combination, including a single provider.
Terraform/Resource Manager provisions a CPU VM running LiteLLM, PostgreSQL and Caddy.

**Development preview.** The direct Resource Manager package is under validation;
the deploy button will be published after Console and live-model acceptance.

## Deploy and demonstrate

The primary deployment path is [OCI Resource Manager](RESOURCE_MANAGER.md):
select providers, Apply, save keys only for enabled external providers, and open
deployment status. OCI is enabled by default; Anthropic and OpenAI are optional.
Setup creates presenter access and runs four samples per enabled model.
After **Ready**, open Compare and run the [demo script](demo/PROMPT.md).

For configured teams, [GitHub Actions](SETUP.md) remains an optional entrypoint:

| Workflow action | Result |
|---|---|
| Deploy | Provision resources, configure models and presenter, run bundled samples |
| Status | Inspect infrastructure and health without model calls |
| Verify samples | Check login, access, enabled model routes and streaming |
| Remove | Remove deployment-owned resources without needing a working VM |

**Ready** requires trusted HTTPS, presenter login and successful samples through
every enabled real model route. Reuse the deployment for another demonstration.
OCI supplies hosting, networking, secret delivery and resource automation, plus
managed inference when selected. External providers use their own API keys.

See [Resource Manager setup and cleanup](RESOURCE_MANAGER.md), [GitHub setup](SETUP.md) and
[local verification](runtime/LOCAL_TESTING.md). License: [MIT](LICENSE).
