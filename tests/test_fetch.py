import httpx
import respx

from site_audit import fetch
from site_audit.fetch import HttpNetwork


def make_network(**kwargs):
    return HttpNetwork(delay=0, **kwargs)


@respx.mock
def test_redirect_chain_is_recorded():
    respx.get("http://x.test/robots.txt").respond(404)
    respx.get("https://x.test/robots.txt").respond(404)
    respx.get("http://x.test/").respond(301, headers={"location": "https://x.test/"})
    respx.get("https://x.test/").respond(200, text="<html></html>", headers={"content-type": "text/html"})
    result = make_network().get("http://x.test/")
    assert result.status == 200
    assert result.url == "https://x.test/"
    assert result.history == [("http://x.test/", 301)]


@respx.mock
def test_robots_disallow_blocks_request_without_sending_it():
    respx.get("https://x.test/robots.txt").respond(200, text="User-agent: *\nDisallow: /privat\n")
    blocked = respx.get("https://x.test/privat")
    allowed = respx.get("https://x.test/offen").respond(200, text="ok")
    net = make_network()
    assert net.get("https://x.test/privat").blocked is True
    assert not blocked.called
    assert net.get("https://x.test/offen").status == 200
    assert allowed.called


@respx.mock
def test_robots_rule_for_site_audit_agent_is_honoured():
    respx.get("https://x.test/robots.txt").respond(200, text="User-agent: site-audit\nDisallow: /\n")
    page = respx.get("https://x.test/")
    assert make_network().get("https://x.test/").blocked is True
    assert not page.called


@respx.mock
def test_body_is_capped():
    respx.get("https://x.test/robots.txt").respond(404)
    respx.get("https://x.test/gross").respond(200, content=b"a" * 1000)
    result = make_network().get("https://x.test/gross", max_bytes=100)
    assert result.truncated is True
    assert len(result.body) == 100


@respx.mock
def test_network_error_is_returned_not_raised():
    respx.get("https://x.test/robots.txt").respond(404)
    respx.get("https://x.test/").mock(side_effect=httpx.ConnectError("refused"))
    result = make_network().get("https://x.test/")
    assert result.status is None
    assert "ConnectError" in result.error


@respx.mock
def test_head_falls_back_to_get_when_not_allowed():
    respx.get("https://x.test/robots.txt").respond(404)
    respx.head("https://x.test/a").respond(405)
    respx.get("https://x.test/a").respond(200, content=b"12345")
    result = make_network().head("https://x.test/a")
    assert result.status == 200 and len(result.body) == 5


@respx.mock
def test_too_many_redirects():
    respx.get("https://x.test/robots.txt").respond(404)
    respx.get("https://x.test/loop").respond(302, headers={"location": "https://x.test/loop"})
    result = make_network().get("https://x.test/loop")
    assert result.status is None
    assert result.error == "zu viele Weiterleitungen"


@respx.mock
def test_set_cookie_headers_are_kept_separately():
    respx.get("https://x.test/robots.txt").respond(404)
    respx.get("https://x.test/").respond(200, headers=[("set-cookie", "a=1; Secure"), ("set-cookie", "b=2")], text="x")
    result = make_network().get("https://x.test/")
    assert result.set_cookies == ["a=1; Secure", "b=2"]


@respx.mock
def test_rate_limit_waits_between_requests_to_same_host(monkeypatch):
    sleeps = []
    monkeypatch.setattr(fetch.time, "sleep", lambda seconds: sleeps.append(seconds))
    respx.get("https://x.test/robots.txt").respond(404)
    respx.get("https://x.test/a").respond(200, text="a")
    respx.get("https://x.test/b").respond(200, text="b")
    net = HttpNetwork(delay=1.0)
    net.get("https://x.test/a")
    net.get("https://x.test/b")
    assert sleeps and all(0 < s <= 1.0 for s in sleeps)


@respx.mock
def test_user_agent_identifies_the_tool():
    respx.get("https://x.test/robots.txt").respond(404)
    route = respx.get("https://x.test/").respond(200, text="x")
    make_network().get("https://x.test/")
    assert route.calls.last.request.headers["user-agent"].startswith("site-audit/")
