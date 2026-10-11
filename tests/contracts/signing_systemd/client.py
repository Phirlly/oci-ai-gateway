"""Sign synthetic bytes and report only socket ownership and inode identity."""

import json
import stat
from pathlib import Path
from types import SimpleNamespace

from runtime.oci_signing_client import SocketSigner
from runtime.oci_signing_scope import SigningScope
from tests.unit.runtime.oci_signing_fixture import COMPARTMENT, MODEL, REGION, chat_body


if __name__ == "__main__":
    directory = Path("/run/contract-signing")
    path = directory / "sign.sock"
    scope = SigningScope(REGION, COMPARTMENT, MODEL)
    request = SimpleNamespace(method="POST", url=scope.url, body=chat_body(), headers={})
    SocketSigner(scope, path=str(path), timeout=10).do_request_sign(request)
    assert request.headers["authorization"].startswith("Signature synthetic-")
    metadata = [directory.stat(), path.stat()]
    print(json.dumps({"inodes": [item.st_ino for item in metadata],
                      "modes": [stat.S_IMODE(item.st_mode) for item in metadata],
                      "owners": [item.st_uid for item in metadata]}))
