"""Explicit pinned-SDK lane; ordinary unit tests do not require the OCI SDK."""

import sys
import unittest


def main():
    import oci
    if sys.version_info[:2] != (3, 12) or oci.__version__ != "2.187.0":
        raise SystemExit("Signing contracts require Python3.12 and OCI SDK2.187.0")
    suite = unittest.defaultTestLoader.loadTestsFromNames([
        "tests.contracts.oci_signing.test_signatures", "tests.contracts.oci_signing.test_refresh"])
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
