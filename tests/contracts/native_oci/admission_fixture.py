"""Denial assertions require zero signing and zero model requests."""

from native_proxy_fixture import EXTERNAL
from payload_fixture import ROUTE
from socket_signer_fixture import SocketProxyCase


class AdmissionCase(SocketProxyCase):
    async def deny(self, extra):
        for alias in (ROUTE, EXTERNAL):
            with self.subTest(alias=alias, fields=sorted(extra)):
                response = await self.request({"model": alias, **extra})
                self.assertIn(response.status_code, (400, 401, 403), response.text[:200])
                self.assertEqual(self.socket.requests, [])
                self.assertEqual(self.upstream.requests, [])
