"""다나와 상품 페이지 요청. 요청 간격, robots.txt, 차단 처리는 PoliteClient (ADR-0004)."""

from flowdeck.polite_http import PoliteClient, Response

BASE_URL = "https://prod.danawa.com"


def product_url(pcode: str) -> str:
    return f"{BASE_URL}/info/?pcode={pcode}"


class DanawaClient(PoliteClient):
    def __init__(self, **kwargs):
        super().__init__(BASE_URL, **kwargs)

    def fetch_product(self, pcode: str) -> Response:
        return self.get(product_url(pcode))
