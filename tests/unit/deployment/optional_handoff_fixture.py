"""Schema4 controller composition with exact owned synthetic infrastructure."""

from pathlib import Path

from deployment.gateway_config import GatewayConfig
from deployment.optional_package import OptionalPackage
from deployment.resource_manager_stacks import StackTarget
from .native_handoff_fixture import NativeHandoffFixture
from .optional_fixture import settings
from .record_fixtures import IDENTITY
from .vault_fixture import MemoryVault


class OptionalHandoffFixture(NativeHandoffFixture):
    def __init__(self, providers=("openai",)):
        super().__init__()
        values = settings(providers)
        self.target = StackTarget(GatewayConfig(values), self.target.controller_id)
        self.package = OptionalPackage.build(Path(__file__).resolve().parents[3],
                                             repository="synthetic/gateway", commit="a" * 40)
        self.orm.package = self.package
        identity = {key: value for key, value in IDENTITY.items() if key not in {"model_id", "inference_region"}}
        identity["models"] = values["models"]
        if "oci" in providers:
            identity["inference_region"] = values["inference_region"]
        self.vault = MemoryVault(identity)
        self.vault.region = values["region"]

    def advance(self, **inputs):
        return super().advance(inference_region=self.target.config.values.get("inference_region"), **inputs)
