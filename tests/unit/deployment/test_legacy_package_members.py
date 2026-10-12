"""Freeze original archive identities independently of builder constants."""

import unittest
from hashlib import sha256

from deployment.foundation_package import MEMBERS, GATEWAY_MEMBERS, NATIVE_MEMBERS, OPTIONAL_MEMBERS


class LegacyPackageMembersTests(unittest.TestCase):
    def test_original_member_names_are_unchanged(self):
        # SHA256 of newline-joined sorted names at reviewed dev c951536.
        # Contents may evolve for new deployments; recovery recognizes these names.
        for names, expected in (
            (MEMBERS, "4e305180242bb060c7773653f1b5ea5962cbc35ba05caee98aabb55695a08f53"),
            (GATEWAY_MEMBERS, "0d2ba7cca5088173e15534ec0a4f869af74d182d09a9d472a4dc571a98b9e201"),
            (NATIVE_MEMBERS, "9cb9d150a0ea3ee6f2e3a2d7ff003b08669dd285c28a670deacc56ce034ef5cc"),
            (OPTIONAL_MEMBERS, "49c6f77445feccc5e5d83187d6820b57df21b88e3b4d8b6ee2eec68a5d0d612b"),
        ):
            with self.subTest(members=len(names)):
                self.assertEqual(sha256("\n".join(sorted(names)).encode()).hexdigest(), expected)
