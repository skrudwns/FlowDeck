"""다나와 상품 페이지 요청. ADR-0004 수집 원칙을 코드로 지킨다.

- 원칙 2: 요청 사이에 간격을 둔다 (delay_seconds).
- 원칙 4: robots.txt가 막은 경로는 요청하지 않는다.
- 원칙 5: 403, 429는 차단으로 보고 Blocked를 던진다. 호출한 쪽은 수집을 멈춘다. 우회하지 않는다.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.robotparser import RobotFileParser

import httpx

BASE_URL = "https://prod.danawa.com"
# 브라우저로 위장하지 않고 수집기임을 밝힌다
USER_AGENT = "FlowDeckCollector/0.1 (+https://github.com/skrudwns/FlowDeck)"
BLOCKED_STATUSES = frozenset({403, 429})


class Blocked(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"차단 응답 {status_code}")
        self.status_code = status_code


class DisallowedByRobots(Exception):
    pass


@dataclass(frozen=True)
class Response:
    status_code: int
    text: str


def product_url(pcode: str) -> str:
    return f"{BASE_URL}/info/?pcode={pcode}"


class DanawaClient:
    def __init__(
        self,
        http: httpx.Client | None = None,
        delay_seconds: float = 3.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._http = http or httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=20.0, follow_redirects=True
        )
        self._delay = delay_seconds
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: float | None = None
        self._robots: RobotFileParser | None = None

    def load_robots(self) -> None:
        """실행마다 한 번 robots.txt를 받는다. 규칙이 바뀌면 다음 실행부터 반영된다.

        urllib.robotparser는 경로 와일드카드(*)를 지원하지 않는다. prod.danawa.com의 규칙은
        2026-10-24 기준 단순 경로 접두어뿐이라 문제없지만, 규칙이 바뀌면 다시 확인해야 한다.
        """
        response = self._get(f"{BASE_URL}/robots.txt")
        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        self._robots = parser

    def fetch_product(self, pcode: str) -> Response:
        url = product_url(pcode)
        if self._robots is None:
            self.load_robots()
        if not self._robots.can_fetch(USER_AGENT, url):
            raise DisallowedByRobots(url)
        return self._get(url)

    def _get(self, url: str) -> Response:
        self._wait_for_turn()
        response = self._http.get(url)
        self._last_request_at = self._clock()
        if response.status_code in BLOCKED_STATUSES:
            raise Blocked(response.status_code)
        return Response(status_code=response.status_code, text=response.text)

    def _wait_for_turn(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self._delay - (self._clock() - self._last_request_at)
        if remaining > 0:
            self._sleep(remaining)

    def close(self) -> None:
        self._http.close()
