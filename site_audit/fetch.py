from __future__ import annotations

import socket
import ssl
import time
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import urljoin, urlsplit

import httpx

USER_AGENT = "site-audit/0.1 (+https://github.com/Joermy/site-audit)"
MAX_BODY_BYTES = 5_000_000
MAX_REDIRECTS = 5


class RobotsBlocked(Exception):
    pass


@dataclass
class Fetched:
    url: str
    status: int | None
    headers: dict[str, str] = field(default_factory=dict)
    set_cookies: list[str] = field(default_factory=list)
    body: bytes = b""
    history: list[tuple[str, int]] = field(default_factory=list)
    error: str | None = None
    truncated: bool = False
    transfer_size: int | None = None
    blocked: bool = False

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 300

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


@dataclass
class CertInfo:
    reachable: bool
    valid: bool = False
    not_after: datetime | None = None
    issuer: str | None = None
    tls_version: str | None = None
    error: str | None = None


class Network(Protocol):
    def get(self, url: str, *, follow: bool = True, max_bytes: int = MAX_BODY_BYTES) -> Fetched: ...

    def head(self, url: str) -> Fetched: ...

    def cert_info(self, host: str, port: int = 443) -> CertInfo: ...


class HttpNetwork:
    def __init__(self, *, delay: float = 1.0, timeout: float = 15.0, user_agent: str = USER_AGENT):
        self.delay = delay
        self.timeout = timeout
        self.user_agent = user_agent
        self._client = httpx.Client(
            follow_redirects=False,
            timeout=timeout,
            headers={"User-Agent": user_agent, "Accept": "*/*"},
        )
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpNetwork":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _wait(self, host: str) -> None:
        if self.delay <= 0:
            return
        last = self._last_request.get(host)
        if last is not None:
            remaining = self.delay - (time.monotonic() - last)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request[host] = time.monotonic()

    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin in self._robots:
            return self._robots[origin]
        parser: urllib.robotparser.RobotFileParser | None = urllib.robotparser.RobotFileParser()
        try:
            self._wait(parts.netloc)
            response = self._client.get(f"{origin}/robots.txt", follow_redirects=True)
            if response.status_code == 200:
                parser.parse(response.text.splitlines())
            elif response.status_code in (401, 403):
                parser.disallow_all = True
            else:
                parser.allow_all = True
        except httpx.HTTPError:
            parser = None
        self._robots[origin] = parser
        return parser

    def allowed(self, url: str) -> bool:
        parser = self._robots_for(url)
        if parser is None:
            return True
        return parser.can_fetch(self.user_agent, url)

    def _request(self, method: str, url: str, follow: bool, max_bytes: int) -> Fetched:
        history: list[tuple[str, int]] = []
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            if not self.allowed(current):
                return Fetched(
                    url=current,
                    status=None,
                    history=history,
                    error="durch robots.txt gesperrt",
                    blocked=True,
                )
            self._wait(urlsplit(current).netloc)
            try:
                with self._client.stream(method, current) as response:
                    status = response.status_code
                    headers = {k.lower(): v for k, v in response.headers.items()}
                    cookies = response.headers.get_list("set-cookie")
                    location = response.headers.get("location")
                    if follow and status in (301, 302, 303, 307, 308) and location:
                        history.append((current, status))
                        current = urljoin(current, location)
                        continue
                    body = bytearray()
                    truncated = False
                    if method == "GET":
                        for chunk in response.iter_bytes():
                            body.extend(chunk)
                            if len(body) > max_bytes:
                                truncated = True
                                del body[max_bytes:]
                                break
                    length = headers.get("content-length")
                    transfer = int(length) if length and length.isdigit() else None
                    return Fetched(
                        url=current,
                        status=status,
                        headers=headers,
                        set_cookies=cookies,
                        body=bytes(body),
                        history=history,
                        truncated=truncated,
                        transfer_size=transfer,
                    )
            except httpx.HTTPError as exc:
                return Fetched(url=current, status=None, history=history, error=_describe(exc))
        return Fetched(url=current, status=None, history=history, error="zu viele Weiterleitungen")

    def get(self, url: str, *, follow: bool = True, max_bytes: int = MAX_BODY_BYTES) -> Fetched:
        return self._request("GET", url, follow, max_bytes)

    def head(self, url: str) -> Fetched:
        result = self._request("HEAD", url, True, 0)
        if result.status in (405, 501):
            return self._request("GET", url, True, MAX_BODY_BYTES)
        return result

    def cert_info(self, host: str, port: int = 443) -> CertInfo:
        context = ssl.create_default_context()
        try:
            with socket.create_connection((host, port), timeout=self.timeout) as raw:
                with context.wrap_socket(raw, server_hostname=host) as tls:
                    cert = tls.getpeercert()
                    version = tls.version()
        except ssl.SSLCertVerificationError as exc:
            return CertInfo(reachable=True, valid=False, error=exc.verify_message or str(exc))
        except (OSError, ssl.SSLError) as exc:
            return CertInfo(reachable=False, error=_describe(exc))
        not_after = None
        if cert and cert.get("notAfter"):
            not_after = datetime.fromtimestamp(ssl.cert_time_to_seconds(cert["notAfter"]), tz=timezone.utc)
        issuer = None
        if cert and cert.get("issuer"):
            for group in cert["issuer"]:
                for key, value in group:
                    if key == "organizationName":
                        issuer = value
        return CertInfo(reachable=True, valid=True, not_after=not_after, issuer=issuer, tls_version=version)


def _describe(exc: BaseException) -> str:
    text = str(exc).strip()
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__
