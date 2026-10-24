import httpx
import pytest

from flowdeck.danawa.client import DanawaClient
from flowdeck.polite_http import USER_AGENT, Blocked, DisallowedByRobots

ROBOTS = "User-agent: *\nDisallow: /api/\nDisallow: /info/ajax/\n"


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def make_client(handler, clock=None, delay=3.0):
    clock = clock or FakeClock()
    http = httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": USER_AGENT})
    return DanawaClient(http=http, delay_seconds=delay, sleep=clock.sleep, clock=clock), clock


def site(product_status=200, robots=ROBOTS):
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=robots)
        return httpx.Response(product_status, text="<html>상품</html>")

    return handler, requested


def test_reads_robots_then_product_page():
    handler, requested = site()
    client, _ = make_client(handler)

    response = client.fetch_product("1000001")

    assert response.status_code == 200
    assert requested == [
        "https://prod.danawa.com/robots.txt",
        "https://prod.danawa.com/info/?pcode=1000001",
    ]


def test_waits_between_requests():
    handler, _ = site()
    client, clock = make_client(handler, delay=3.0)

    client.fetch_product("1")
    client.fetch_product("2")

    # robots → 상품1 → 상품2, 요청 사이마다 3초
    assert clock.slept == [3.0, 3.0]


def test_does_not_request_paths_disallowed_by_robots():
    handler, requested = site(robots="User-agent: *\nDisallow: /info/\n")
    client, _ = make_client(handler)

    with pytest.raises(DisallowedByRobots):
        client.fetch_product("1000001")
    assert requested == ["https://prod.danawa.com/robots.txt"]


@pytest.mark.parametrize("status", [403, 429])
def test_treats_403_and_429_as_blocked(status):
    handler, _ = site(product_status=status)
    client, _ = make_client(handler)

    with pytest.raises(Blocked) as exc:
        client.fetch_product("1000001")
    assert exc.value.status_code == status


def test_returns_other_errors_as_response():
    handler, _ = site(product_status=500)
    client, _ = make_client(handler)

    assert client.fetch_product("1000001").status_code == 500


def test_sends_collector_user_agent():
    seen = []

    def handler(request):
        seen.append(request.headers["User-Agent"])
        return httpx.Response(200, text=ROBOTS)

    client, _ = make_client(handler)
    client.fetch_product("1")

    assert set(seen) == {USER_AGENT}
