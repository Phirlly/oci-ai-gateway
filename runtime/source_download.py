"""Fetch one public commit without credentials, arbitrary redirects or proxies."""

from http.client import HTTPSConnection, HTTPException

from .gateway_http import request_deadline
from .source_archive import MAX_DOWNLOAD, source_files, validate_manifest


def download_sources(manifest):
    validate_manifest(manifest)
    repository, commit = manifest["repository"], manifest["commit"]
    requests = [("api.github.com", f"/repos/{repository}/zipball/{commit}"),
                ("codeload.github.com", f"/{repository}/legacy.zip/{commit}")]
    expected_redirect = "https://" + requests[1][0] + requests[1][1]
    try:
        with request_deadline(45):
            for number, (host, path) in enumerate(requests):
                connection = HTTPSConnection(host, timeout=15)
                response = None
                try:
                    connection.request("GET", path, headers={"User-Agent": "oci-ai-gateway-source"})
                    response = connection.getresponse()
                    if response.status == 302 and number == 0:
                        if response.getheader("Location") != expected_redirect:
                            raise ValueError("Unexpected source redirect")
                        continue
                    if response.status != 200:
                        raise ValueError("Public source commit is unavailable")
                    return source_files(response.read(MAX_DOWNLOAD + 1), manifest)
                finally:
                    if response is not None:
                        response.close()
                    connection.close()
    except (OSError, HTTPException, ValueError):
        raise ValueError("Public runtime source could not be verified; retain its repository and commit") from None
    raise ValueError("Public runtime source redirect did not complete")
