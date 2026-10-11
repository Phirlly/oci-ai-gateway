"""LiteLLM imports this instance only after its gateway config file exists."""

from runtime.oci_gateway_callback import NativeGateway
from runtime.oci_gateway_config import load_routes

INSTANCE = NativeGateway(load_routes())
