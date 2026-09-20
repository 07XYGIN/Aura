"""Bounded public HTTP reader used inside the local MCP server.

Connect to a validated numeric IP (not a second DNS lookup), retaining TLS SNI
and certificate verification for the original hostname. Revalidate every redirect.
No cookies, proxy environment, authorization headers or JavaScript execution.
"""
from datetime import UTC, datetime
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit

import urllib3

from .models import WebDocument, WorldError
from .security import resolve_public_url
from .service import MAX_CONTENT, clean_text

MAX_BYTES = 1024 * 1024


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.in_title = False
        self.title = []
        self.body = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg", "template"}:
            self.hidden += 1
        if tag == "title":
            self.in_title = True
        if not self.hidden and tag in {"p", "div", "br", "li", "h1", "h2", "h3", "article", "section"}:
            self.body.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg", "template"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "title":
            self.in_title = False
        if tag in {"p", "div", "li", "h1", "h2", "h3"}:
            self.body.append("\n")

    def handle_data(self, data):
        if self.hidden:
            return
        if self.in_title:
            self.title.append(data)
        else:
            self.body.append(data)


def read_public_page(url: str) -> WebDocument:
    for hop in range(4):
        url, addresses = resolve_public_url(url)
        parts = urlsplit(url)
        pool_cls = urllib3.HTTPSConnectionPool if parts.scheme == "https" else urllib3.HTTPConnectionPool
        tls = {"server_hostname": parts.hostname, "assert_hostname": parts.hostname, "cert_reqs": "CERT_REQUIRED"} if parts.scheme == "https" else {}
        with pool_cls(addresses[0], port=parts.port or (443 if tls else 80), **tls) as pool:
            path = parts.path or "/"
            if parts.query:
                path += "?" + parts.query
            response = pool.urlopen(
                "GET", path, headers={"Host": parts.netloc, "User-Agent": "Aura-WorldReader/1.0", "Accept": "text/html,text/plain,application/xhtml+xml", "Accept-Encoding": "identity"},
                redirect=False, retries=False, preload_content=False,
                timeout=urllib3.Timeout(connect=5, read=10),
            )
            try:
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    if not location or hop == 3:
                        raise WorldError("redirect_error", "网页重定向次数过多或目标无效。")
                    url = urljoin(url, location)
                    continue
                if response.status != 200:
                    raise WorldError("http_error", "网页无法读取。")
                mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                if mime not in {"text/html", "application/xhtml+xml", "text/plain"}:
                    raise WorldError("unsupported_content", "第一版仅支持 HTML 和纯文本网页，不支持文件或二进制内容。")
                if response.headers.get("Content-Encoding", "identity").lower() not in {"identity", ""}:
                    raise WorldError("unsupported_content", "网页未提供安全的未压缩文本响应。")
                raw = response.read(MAX_BYTES + 1, decode_content=False)
                byte_truncated = len(raw) > MAX_BYTES
                charset = re.search(r"charset=[\"']?([\w-]+)", response.headers.get("Content-Type", ""), re.I)
                try:
                    text = raw[:MAX_BYTES].decode(charset.group(1) if charset else "utf-8", errors="replace")
                except LookupError:
                    text = raw[:MAX_BYTES].decode("utf-8", errors="replace")
            finally:
                response.close()
        title = None
        if mime != "text/plain":
            parser = PageText()
            parser.feed(text)
            text = "".join(parser.body)
            title = clean_text("".join(parser.title))[:300] or None
        text = clean_text(text)
        if not text:
            raise WorldError("empty_document", "网页没有可读取的正文。")
        return WebDocument(url=url, title=title, content=text[:MAX_CONTENT], fetched_at=datetime.now(UTC), truncated=byte_truncated or len(text) > MAX_CONTENT)
    raise WorldError("redirect_error", "网页重定向次数过多。")
