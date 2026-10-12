"""Built-in-only fixture containing the actual production readiness resource."""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def prepare(directory):
    source = (ROOT / "infra/secrets.tf").read_text()
    marker = 'resource "terraform_data" "vault_endpoint" {'
    gate = marker + source.split(marker, 1)[1].split('\nresource "', 1)[0]
    gate = gate.replace("oci_kms_vault.runtime.id", "var.fixture_vault_id")
    gate = gate.replace("oci_kms_vault.runtime.management_endpoint", "var.fixture_endpoint")
    settings = '''
variable "fixture_vault_id" { default = "vault-one" }
variable "fixture_endpoint" { default = "synthetic-endpoint" }
variable "region" { default = "us-ashburn-1" }
variable "vault_readiness_script_path" { default = "./probe script.py" }
resource "terraform_data" "key" {
  depends_on = [terraform_data.vault_endpoint]
}
'''
    (directory / "main.tf").write_text(gate + settings)
    (directory / "probe script.py").write_text('''
import os
from pathlib import Path
assert os.environ["VAULT_READINESS_ENDPOINT"] == "synthetic-endpoint"
assert os.environ["VAULT_READINESS_REGION"] == "us-ashburn-1"
with Path("calls").open("a") as calls:
    calls.write("probe\\n")
raise SystemExit(1 if Path("fail").exists() else 0)
''')


def terraform(directory, *arguments, success=True):
    binary = os.environ.get("GATEWAY_TERRAFORM_15", str(ROOT / ".cache/terraform/1.5.7/terraform"))
    result = subprocess.run([binary, "-chdir=" + str(directory), *arguments],
                            capture_output=True, text=True, timeout=30,
                            env={**os.environ, "TF_IN_AUTOMATION": "1", "TF_INPUT": "0"})
    if (result.returncode == 0) != success:
        raise AssertionError(result.stdout + result.stderr)
    return result


def resources(directory):
    state = json.loads(terraform(directory, "show", "-json").stdout)
    return {r["address"]: r for r in state.get("values", {}).get("root_module", {}).get("resources", [])}
