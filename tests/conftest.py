from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from site_audit.fetch import CertInfo, Fetched, MAX_BODY_BYTES
from site_audit.page import build_page, measure_resources

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


class FakeNetwork:
    def __init__(self, responses: dict[str, Fetched] | None = None, cert: CertInfo | None = None):
        self.responses = responses or {}
        self.cert = cert or CertInfo(reachable=True, valid=True, not_after=NOW + timedelta(days=200), issuer="Test CA", tls_version="TLSv1.3")
        self.requests: list[tuple[str, str]] = []

    def add(self, url: str, status: int = 200, body: str | bytes = b"", headers: dict[str, str] | None = None, history=None, **extra) -> None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.responses[url] = Fetched(
            url=extra.pop("final_url", url),
            status=status,
            headers={k.lower(): v for k, v in (headers or {}).items()},
            body=data,
            history=history or [],
            transfer_size=len(data) or None,
            **extra,
        )

    def _lookup(self, method: str, url: str) -> Fetched:
        self.requests.append((method, url))
        found = self.responses.get(url)
        if found is None:
            return Fetched(url=url, status=404)
        return found

    def get(self, url: str, *, follow: bool = True, max_bytes: int = MAX_BODY_BYTES) -> Fetched:
        return self._lookup("GET", url)

    def head(self, url: str) -> Fetched:
        found = self._lookup("HEAD", url)
        return Fetched(
            url=found.url,
            status=found.status,
            headers=found.headers,
            history=found.history,
            error=found.error,
            transfer_size=found.transfer_size,
        )

    def cert_info(self, host: str, port: int = 443) -> CertInfo:
        return self.cert


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def make_page(html: str, url: str = "https://www.beispiel.test/", net: FakeNetwork | None = None, headers=None, cookies=None, measure: bool = False):
    net = net or FakeNetwork()
    fetched = Fetched(
        url=url,
        status=200,
        headers={k.lower(): v for k, v in (headers or {}).items()},
        set_cookies=list(cookies or []),
        body=html.encode("utf-8"),
        transfer_size=len(html.encode("utf-8")),
    )
    page = build_page(fetched, url, net, now=NOW)
    if measure:
        measure_resources(page, 60)
    return page


@pytest.fixture
def fake_net() -> FakeNetwork:
    return FakeNetwork()
