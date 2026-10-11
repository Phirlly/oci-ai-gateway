# Local Verification and Troubleshooting

These checks use synthetic accounts and mocked model responses. The local
Compose profile is disposable verification, not a hosted customer demo.
Run every command below from the repository root.

Requires Linux or macOS, Python 3.12, Docker CLI with Compose and a running local
engine exposed through a Unix-socket Docker context. No provider credentials
or additional Python packages are needed.

## Run

```sh
python3.12 -m tests.contracts.runtime
python3.12 -m tests.contracts.demo
python3.12 -m tests.contracts.native_oci
python3.12 -m tests.contracts.native_deployment
```

For a Podman machine available through the Docker `podman` context:

```sh
GATEWAY_TEST_DOCKER_CONTEXT=podman python3.12 -m tests.contracts.runtime
```

The runner pulls pinned images, creates disposable credentials, checks the
isolated runtime and removes its own resources. It leaves the engine running.
The first image download can take several minutes.

The separate demo suite exercises both real pinned provider adapters against
isolated synthetic HTTP providers, including streaming and rate-limit behavior.
It runs inside the gateway container; the runtime suite checks the published
local edge. Neither suite establishes real account/model access or public TLS.

The native OCI suite also requires Git. It verifies and patches temporary copies
of two pinned-image source files, then tests completion, streaming, HTTP cleanup,
signing cancellation and normal log output in a network-disabled container.
The production callback is exercised through the real proxy with synthetic
native OCI and Anthropic responses. Native cloud activation remains pending.
It needs no OCI credentials or local documentation cache.

The native deployment suite starts the production gateway/database Compose
services with synthetic secrets, the verified overlay and no outbound network or
published ports. It checks startup, authentication and callback policy from
inside the container. It does not exercise the host's systemd or OCI identity.

On Ubuntu with systemd, a local Docker engine and noninteractive sudo, run
`python3.12 -m tests.contracts.signing_systemd`. It owns uniquely named test units
and a network-disabled container; it verifies activation and worker/container
restart with synthetic signatures. It skips on macOS. No OCI identity is used.
Failures retain exact recovery names/paths; stop its container before its named
socket/service, remove only those two unit files, reload systemd, then remove the
empty socket directory and retained test inputs. Do not restart shared Docker.

## Image Pulls

If Docker Hub pulls fail with a certificate-trust error, the configured public
mirror can supply the same pinned PostgreSQL and Caddy images:

```sh
GATEWAY_TEST_DOCKER_CONTEXT=podman \
GATEWAY_TEST_POSTGRES_REGISTRY=public.ecr.aws/docker/library \
GATEWAY_TEST_CADDY_REGISTRY=public.ecr.aws/docker/library \
python3.12 -m tests.contracts.runtime
```

LiteLLM still downloads from GHCR. For corporate HTTPS inspection, configure the
approved corporate CA in the container engine. Keep TLS verification enabled.

## Recover Interrupted Cleanup

Use the exact project and input directory reported by the failure, and the
Docker context used for that run:

```sh
test_context='podman'
test_project='gateway-contract-REPLACE'
test_inputs='/absolute/path/reported/by/the/runner'
```

Supply the retained inputs and remove only that project's containers and storage:

```sh
GATEWAY_CONFIG_FILE="$PWD/tests/contracts/runtime/fixtures/gateway.yaml" \
GATEWAY_SECRETS_FILE="$test_inputs/gateway-secrets.json" \
DATABASE_PASSWORD_FILE="$test_inputs/database-password" \
docker --context "$test_context" compose --project-directory "$PWD" \
  -f runtime/compose.local.yaml -p "$test_project" down --volumes --timeout 10
```

Verify removal, including stopped containers:

```sh
docker --context "$test_context" container ls --all --quiet --filter "label=com.docker.compose.project=$test_project"
docker --context "$test_context" network ls --quiet --filter "label=com.docker.compose.project=$test_project"
docker --context "$test_context" volume ls --quiet --filter "label=com.docker.compose.project=$test_project"
```

Only after **all three commands succeed with empty output**, remove the exact
reported input directory inside this repository's `.tmp/`:

```sh
rm -r -- "$test_inputs"
```

If any command fails or lists remaining resources, retain the inputs and retry
with the same context and project. Do not run a global prune. Other projects
and the container engine remain untouched.

For an interrupted native deployment suite, use its retained manifest instead:

```sh
docker --context "$test_context" compose -f "$test_inputs/compose.json" \
  -p "$test_project" down --volumes --timeout 10
```

Then perform the same three resource checks before removing its input directory.
