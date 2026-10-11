"""Private, atomic evidence for Console verification; caller holds bootstrap lock."""

import json
import os
import re
import stat
import tempfile
from hashlib import sha256
from pathlib import Path

from .console_settings import decode_json
from .gateway_http import GatewayError

RECORDS = {"console-state.json", "console-credentials.json", "gateway-secrets.json"}
PHASES = {"preparing", "active", "started", "complete"}
RESULTS = {"PENDING", "READY", "FAILED", "ERROR"}


def read_record(directory, name):
    try:
        directory = Path(directory)
        metadata = directory.lstat()
        if (name not in RECORDS or not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != os.geteuid() or metadata.st_mode & 0o077):
            raise ValueError
        try:
            descriptor = os.open(directory / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            return None
        with os.fdopen(descriptor, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid()
                    or stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_size > 16384):
                raise ValueError
            return decode_json(stream.read(16385))
    except (OSError, ValueError, TypeError, RecursionError):
        raise GatewayError("Console private evidence is invalid; preserve it for recovery") from None


def write_record(directory, name, value):
    read_record(directory, name)  # Verify existing file and private parent before replacement.
    temporary = None
    try:
        content = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        if len(content) > 16384:
            raise ValueError
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fchmod(stream.fileno(), 0o600)
            os.fsync(stream.fileno())
        os.replace(temporary, Path(directory) / name)
        temporary = None
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except (OSError, ValueError, TypeError):
        raise GatewayError("Console evidence could not be persisted; stop this operation") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class ConsoleState:
    def __init__(self, directory, context, context_secret_id):
        self.directory = directory
        self.run = context["verification_run"]
        self.optional = context["settings"]["schema_version"] == 2
        self.total, self.providers = 8, set()
        if self.optional:
            from demo.samples import sample_count
            from .provider_selection import model_aliases
            settings = context["settings"]["runtime"]
            self.total = sample_count(model_aliases(settings))
            self.providers = set(settings["models"]) - {"oci"}
        identity = {key: value for key, value in context.items() if key != "verification_run"}
        identity["context_secret_id"] = context_secret_id
        self.identity = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()

    def validate(self, value):
        fields = {"identity", "run", "phase", "external_version", "result", "passed", "finished_at"}
        if self.optional:
            fields = fields - {"external_version"} | {"schema_version", "provider_versions", "total"}
        if not isinstance(value, dict) or set(value) != fields:
            raise GatewayError("Console run fields differ from this deployment")
        if self.optional:
            versions = value["provider_versions"]
            valid_versions = (versions is None or isinstance(versions, dict) and set(versions) == self.providers
                              and all(type(v) is int and v > 0 for v in versions.values()))
            pinned = versions is not None
            if type(value["schema_version"]) is not int or value["schema_version"] != 2 or value["total"] != self.total:
                raise GatewayError("Console run schema or sample count changed")
        else:
            valid_versions = type(value["external_version"]) is int and value["external_version"] >= 0
            pinned = value["external_version"] != 0
        if (not valid_versions
                or value["identity"] != self.identity or type(value["run"]) is not int
                or not 1 <= value["run"] <= 20 or value["run"] > self.run
                or value["phase"] not in PHASES or value["result"] not in RESULTS
                or type(value["passed"]) is not int or not 0 <= value["passed"] <= self.total
                or not isinstance(value["finished_at"], str)
                or (value["finished_at"] and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value["finished_at"]) is None)
                or (value["phase"] != "preparing" and not pinned)
                or (value["phase"] == "complete" and (value["result"] == "PENDING" or not value["finished_at"]))
                or (value["result"] == "READY" and (value["phase"] != "complete" or value["passed"] != self.total))):
            raise GatewayError("Console run identity or evidence changed; explicit recovery is required")
        return value

    def load(self):
        value = read_record(self.directory, "console-state.json")
        return None if value is None else self.validate(value)

    def save(self, value):
        self.load()
        write_record(self.directory, "console-state.json", self.validate(value))

    def begin(self):
        value = self.load()
        if value is None or value["run"] < self.run:
            value = {"identity": self.identity, "run": self.run, "phase": "preparing",
                     "external_version": 0, "result": "PENDING", "passed": 0, "finished_at": ""}
            if self.optional:
                del value["external_version"]
                value.update(schema_version=2, provider_versions=None, total=self.total)
            self.save(value)
        return value
