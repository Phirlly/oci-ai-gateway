"""Public source retrieval has fixed authority, bounded reads and owned cleanup."""

import unittest
from unittest.mock import Mock, patch

from runtime.source_download import download_sources
from .source_fixture import FILES, archive, manifest


class SourceDownloadTests(unittest.TestCase):
    def response(self, status, body=b"", location=None):
        result = Mock(status=status)
        result.read.return_value = body
        result.getheader.return_value = location
        return result

    def run_download(self, responses):
        connections = [Mock() for _ in responses]
        for connection, response in zip(connections, responses):
            connection.getresponse.return_value = response
        self.connections = connections
        self.factory = self.enterContext(patch("runtime.source_download.HTTPSConnection", side_effect=connections))
        return download_sources(manifest())

    def test_exact_public_commit_redirect_and_archive_are_verified(self):
        location = "https://codeload.github.com/synthetic/gateway/legacy.zip/" + "a" * 40
        responses = [self.response(302, location=location), self.response(200, archive())]
        self.assertEqual(self.run_download(responses), FILES)
        self.assertEqual([call.args[0] for call in self.factory.call_args_list], ["api.github.com", "codeload.github.com"])
        for connection, response in zip(self.connections, responses):
            headers = connection.request.call_args.kwargs["headers"]
            self.assertNotIn("Authorization", headers)
            response.close.assert_called_once_with()
            connection.close.assert_called_once_with()

    def test_bad_redirect_or_http_error_never_reaches_another_host(self):
        for status, location in ((302, "https://other.invalid/archive"), (302, "http://codeload.github.com/archive"),
                                 (404, None), (429, None)):
            with self.subTest(status=status, location=location):
                response = self.response(status, location=location)
                with self.assertRaises(ValueError):
                    self.run_download([response])
                self.assertEqual(self.factory.call_count, 1)
                response.close.assert_called_once_with()
                self.connections[0].close.assert_called_once_with()

    def test_read_failure_and_oversized_response_close_both_owners(self):
        for failure in (TimeoutError(), None):
            response = self.response(200, b"x" * (8 * 1024 * 1024 + 1))
            response.read.side_effect = failure
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                self.run_download([response])
            response.close.assert_called_once_with()
            self.connections[0].close.assert_called_once_with()
