"""The manager keeps a usable private socket across worker/container restarts."""

import sys
import unittest

from .fixture import SystemdSocket


@unittest.skipUnless(sys.platform == "linux", "Requires Linux systemd and a local Docker engine")
class SystemdActivationContracts(unittest.TestCase):
    def test_manager_activation_preserves_socket_mount_across_restarts(self):
        with SystemdSocket() as owner:
            self.assertEqual(owner.pid(), "0")
            first = owner.probe()
            pid = owner.pid()
            self.assertNotEqual(pid, "0")
            self.assertEqual(first["modes"], [0o700, 0o600])
            self.assertEqual(first["owners"], [0, 0])
            owner.restart_worker()
            self.assertNotIn(owner.pid(), ("0", pid))
            self.assertEqual(owner.probe(), first)
            owner.restart_container()
            self.assertEqual(owner.probe(), first)
