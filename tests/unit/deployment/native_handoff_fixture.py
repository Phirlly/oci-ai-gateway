"""Real native controller boundaries against isolated ORM, Vault and Compute fakes."""

from pathlib import Path

from deployment.gateway_config import GatewayConfig
from deployment.native_package import NativePackage
from deployment.resource_manager_stacks import StackTarget
from .cloud_inventory_fixture import CloudMetadata, cloud_inventory
from .handoff_fixture import HandoffFixture
from .native_fixture import NATIVE_SETTINGS
from .record_fixtures import IDENTITY


class NativeHandoffFixture(HandoffFixture):
    def __init__(self):
        super().__init__()
        settings = NATIVE_SETTINGS | {"inference_region": IDENTITY["inference_region"],
                                      "oci_model_id": IDENTITY["model_id"]}
        self.target = StackTarget(GatewayConfig(settings), self.target.controller_id)
        self.package = NativePackage.build(Path(__file__).resolve().parents[3],
                                           repository="synthetic/gateway", commit="a" * 40)
        self.orm.package = self.package
        self.compute = CloudMetadata()
        self.keys = None

    def advance(self, **inputs):
        return super().advance(compute=self.compute, **inputs)

    def base_succeeded(self):
        self.advance()
        self.orm.jobs[0]["lifecycle-state"] = "SUCCEEDED"
        self.orm.inventories[self.orm.jobs[0]["id"]] = cloud_inventory()
