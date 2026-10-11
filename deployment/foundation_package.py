"""Allowlisted Terraform/runtime archives and exact job-content attestation."""

import io
import os
import stat
import tempfile
import zipfile
import zlib
from contextlib import contextmanager
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from .credential_errors import DeliveryError
from .submission_records import digest
from .package_sources import package_sources

SOURCE_FILES = ('.terraform.lock.hcl', 'identity.tf', 'locals.tf', 'outputs.tf',
                'providers.tf', 'secrets.tf', 'variables.tf', 'versions.tf')
MEMBERS = frozenset('foundation/' + name for name in SOURCE_FILES)
CLOUD_FILES = ('cloud-bootstrap.tf', 'cloud-compute.tf', 'cloud-network.tf', 'cloud-variables.tf')
RUNTIME_FILES = (
    '__init__.py', 'bootstrap.py', 'cloud_credentials.py', 'gateway_entrypoint.py',
    'gateway_http.py', 'host_commands.py', 'host_firewall.py', 'install_assets.py',
    'password_policy.py', 'presenter.py', 'presenter_api.py', 'presenter_state.py',
    'runtime_bundle.py', 'runtime_files.py', 'compose.cloud.yaml', 'docker-daemon.json',
    'systemd/docker-guard.conf', 'systemd/oci-ai-gateway-bootstrap.service',
    'systemd/oci-ai-gateway-bootstrap.timer',
)
GATEWAY_FILES = {**{'foundation/' + name: 'infra/' + name for name in SOURCE_FILES + CLOUD_FILES},
                 **{'runtime/' + name: 'runtime/' + name for name in RUNTIME_FILES}}
GATEWAY_MEMBERS = frozenset(GATEWAY_FILES)
NATIVE_RUNTIME_FILES = (
    'source_archive.py', 'source_download.py', 'source_bootstrap.py',
    'systemd/oci-ai-gateway-native-bootstrap.service',
    'compose.native.yaml', 'systemd/docker-native.conf',
    'native_startup.py', 'oci_adapter_overlay.py', 'oci_gateway_callback.py',
    'oci_gateway_config.py', 'oci_gateway_loader.py', 'oci_instance_signer.py',
    'oci_signing_client.py', 'oci_signing_entrypoint.py', 'oci_signing_protocol.py',
    'oci_signing_scope.py', 'oci_signing_service.py', 'litellm_oci.patch', 'LITELLM_LICENSE',
    'systemd/oci-ai-gateway-signing.service', 'systemd/oci-ai-gateway-signing.socket',
)
NATIVE_FILES = GATEWAY_FILES | {'runtime/' + name: 'runtime/' + name for name in NATIVE_RUNTIME_FILES}
NATIVE_MEMBERS = frozenset(NATIVE_FILES) | {'runtime/source.json'}
OPTIONAL_FILES = NATIVE_FILES | {'runtime/' + name: 'runtime/' + name for name in (
    'provider_selection.py', 'optional_bundle.py', 'optional_startup.py')}
OPTIONAL_MEMBERS = frozenset(OPTIONAL_FILES) | {'runtime/source.json'}
MAX_ARCHIVE_BYTES = 1024 * 1024
MAX_MEMBER_BYTES = 256 * 1024


def archive_digest(content):
    try:
        if not isinstance(content, bytes) or len(content) > MAX_ARCHIVE_BYTES:
            raise ValueError
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            names = {e.filename for e in entries}
            if len(entries) != len(names) or names not in (MEMBERS, GATEWAY_MEMBERS, NATIVE_MEMBERS, OPTIONAL_MEMBERS):
                raise ValueError
            if sum(e.file_size for e in entries) > MAX_ARCHIVE_BYTES:
                raise ValueError
            hashes = {}
            for entry in entries:
                mode = stat.S_IFMT(entry.external_attr >> 16)
                if (entry.orig_filename != entry.filename or entry.flag_bits & 1
                        or mode not in (0, stat.S_IFREG)
                        or entry.file_size > MAX_MEMBER_BYTES
                        or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    raise ValueError
                with archive.open(entry) as member:
                    data = member.read(MAX_MEMBER_BYTES + 1)
                if len(data) != entry.file_size or len(data) > MAX_MEMBER_BYTES:
                    raise ValueError
                hashes[entry.filename] = sha256(data).hexdigest()
            return digest(hashes)
    except (OSError, ValueError, RuntimeError, EOFError, zlib.error, zipfile.BadZipFile, NotImplementedError):
        raise DeliveryError('Terraform package contents could not be verified.') from None


@dataclass(frozen=True, repr=False)
class FoundationPackage:
    content: bytes
    digest: str = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, 'digest', archive_digest(self.content))

    @classmethod
    def build(cls, directory):
        return cls._build(directory, {'foundation/' + name: name for name in SOURCE_FILES})

    @property
    def is_gateway(self):
        return self.schema_version in (2, 3, 4)

    @property
    def schema_version(self):
        with zipfile.ZipFile(io.BytesIO(self.content)) as archive:
            names = frozenset(archive.namelist())
            if names == OPTIONAL_MEMBERS:
                return 4
            return 3 if names == NATIVE_MEMBERS else (2 if names == GATEWAY_MEMBERS else 1)

    @classmethod
    def _build(cls, directory, files, *, generated=None):
        return cls(package_sources(directory, files, generated=generated))

    def verify(self, content):
        if archive_digest(content) != self.digest:
            raise DeliveryError('Job Terraform contents differ from the submitted package.')

    @contextmanager
    def path(self):
        with tempfile.TemporaryDirectory(prefix='gateway-foundation-') as directory:
            path = Path(directory) / 'foundation.zip'
            with path.open('xb') as output:
                os.chmod(path, 0o600)
                output.write(self.content)
            yield path


class GatewayPackage(FoundationPackage):
    @classmethod
    def build(cls, directory):
        return cls._build(directory, GATEWAY_FILES)
