"""Fatal identity state must end the worker even when its reply fails."""

import unittest
from unittest.mock import MagicMock, Mock, patch

from runtime.oci_instance_signer import SigningUnavailable
from runtime.oci_signing_protocol import ProtocolError
from runtime.oci_signing_service import serve
from .oci_signing_fixture import chat_body


class SigningServiceFailureTests(unittest.TestCase):
    def test_identity_failure_exits_after_failed_reply_without_accepting_again(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        listener = Mock()
        listener.accept.side_effect = [(connection, None), AssertionError("Accepted after identity failure")]
        signer = Mock()
        signer.sign.side_effect = SigningUnavailable("private-credential-marker")
        body = chat_body()
        with patch("runtime.oci_signing_service.select.select"), \
                patch("runtime.oci_signing_service.receive_frame", return_value=body), \
                patch("runtime.oci_signing_service._reply", side_effect=ProtocolError("disconnected")) as reply:
            self.assertEqual(serve(listener, signer), 1)
        signer.sign.assert_called_once_with(body, timeout=20)
        reply.assert_called_once_with(connection, {"status": "unavailable"}, 3)
        listener.accept.assert_called_once_with()
        connection.__exit__.assert_called_once()
