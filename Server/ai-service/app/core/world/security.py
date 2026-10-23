"""Public HTTP URL validation, also used at every actual network hop."""
import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

from .models import WorldError


def public_ip(value: str) -> bool:
    address = ipaddress.ip_address(value)
    # Reject transition/mapped addresses rather than trusting an embedded IPv4.
    if isinstance(address, ipaddress.IPv6Address) and (
        address.ipv4_mapped or address.sixtofour or address.teredo
        or address in ipaddress.ip_network("64:ff9b::/96")
    ):
        return False
    return address.is_global and not address.is_multicast and not address.is_reserved


def validate_url(url: str) -> str:
    try:
        if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 33 for c in url) or "\\" in url:
            raise ValueError()
        parts = urlsplit(url)
        host = (parts.hostname or "").rstrip(".").encode("idna").decode("ascii").lower()
        if parts.scheme not in {"http", "https"} or not host or parts.username is not None or parts.password is not None:
            raise ValueError()
        if parts.port not in {None, 80, 443}:
            raise ValueError()
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".lan", ".home", ".test", ".invalid")):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if "." not in host or "%" in host or ":" in host:
                raise ValueError()
        else:
            if not public_ip(str(address)):
                raise ValueError()
        netloc = f"[{host}]" if ":" in host else host
        if parts.port is not None:
            netloc += f":{parts.port}"
        return urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))
    except (ValueError, UnicodeError):
        raise WorldError("unsafe_url", "仅允许公开互联网的 HTTP/HTTPS 网页（80/443 端口），禁止内网、凭据和非法地址。") from None


def resolve_public_url(url: str) -> tuple[str, list[str]]:
    url = validate_url(url)
    parts = urlsplit(url)
    try:
        rows = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
        addresses = list(dict.fromkeys(row[4][0] for row in rows))
        if not addresses or not all(public_ip(value) for value in addresses):
            raise WorldError("unsafe_url", "网页地址解析到了非公开网络，已拒绝访问。")
        return url, addresses
    except (socket.gaierror, ValueError):
        raise WorldError("dns_error", "网页域名无法解析。") from None
