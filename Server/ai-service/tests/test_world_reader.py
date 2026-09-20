import unittest
from unittest.mock import MagicMock, patch

from app.core.world.reader import read_public_page
from app.core.world.models import WorldError


class WorldReaderTest(unittest.TestCase):
    def pool(self, status=200, body=b"<title>Title</title><p>Hello</p><script>SECRET SCRIPT</script>", headers=None):
        pool = MagicMock()
        response = pool.__enter__.return_value.urlopen.return_value
        response.status = status
        response.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        response.read.return_value = body
        return pool, response

    def test_pinned_ip_tls_host_and_html_cleanup(self):
        pool, response = self.pool()
        with patch("app.core.world.reader.resolve_public_url", return_value=("https://example.com/a", ["93.184.216.34"])), patch("urllib3.HTTPSConnectionPool", return_value=pool) as factory:
            doc = read_public_page("https://example.com/a")
        self.assertEqual(doc.title, "Title")
        self.assertEqual(doc.content, "Hello")
        self.assertEqual(factory.call_args.args, ("93.184.216.34",))
        self.assertEqual(factory.call_args.kwargs["server_hostname"], "example.com")
        self.assertEqual(factory.call_args.kwargs["assert_hostname"], "example.com")
        request = pool.__enter__.return_value.urlopen.call_args.kwargs
        self.assertFalse(request["redirect"])
        self.assertFalse(request["retries"])
        self.assertEqual(request["headers"]["Host"], "example.com")
        response.close.assert_called_once()

    def test_redirect_to_private_network_rejected_before_second_request(self):
        pool, response = self.pool(status=302, headers={"Location": "http://127.0.0.1/"})
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]), patch("urllib3.HTTPSConnectionPool", return_value=pool), patch("urllib3.HTTPConnectionPool") as plain:
            with self.assertRaises(WorldError):
                read_public_page("https://example.com/")
            plain.assert_not_called()
        response.close.assert_called_once()

    def test_redirect_domain_resolves_private(self):
        pool, _ = self.pool(status=302, headers={"Location": "https://private.example.com/"})
        rows = [[(2, 1, 6, "", ("93.184.216.34", 443))], [(2, 1, 6, "", ("10.0.0.1", 443))]]
        with patch("socket.getaddrinfo", side_effect=rows), patch("urllib3.HTTPSConnectionPool", return_value=pool) as factory:
            with self.assertRaises(WorldError):
                read_public_page("https://example.com/")
            self.assertEqual(factory.call_count, 1)

    def test_binary_and_compressed_payload_rejected(self):
        for headers in [{"Content-Type": "application/pdf"}, {"Content-Type": "text/html", "Content-Encoding": "gzip"}]:
            pool, response = self.pool(headers=headers)
            with patch("app.core.world.reader.resolve_public_url", return_value=("https://example.com/", ["93.184.216.34"])), patch("urllib3.HTTPSConnectionPool", return_value=pool), self.assertRaises(WorldError):
                read_public_page("https://example.com/")
            response.read.assert_not_called()
