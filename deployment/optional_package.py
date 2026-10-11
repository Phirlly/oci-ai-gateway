"""A distinct schema4 archive retains legacy formats and supports optional native startup."""

from .foundation_package import OPTIONAL_FILES
from .native_package import NativePackage, SOURCE_EXCLUSIONS

OPTIONAL_EXCLUSIONS = (SOURCE_EXCLUSIONS - {"runtime/compose.cloud.yaml"}) | {"runtime/systemd/docker-native.conf"}


class OptionalPackage(NativePackage):
    files = OPTIONAL_FILES
    source_exclusions = OPTIONAL_EXCLUSIONS
