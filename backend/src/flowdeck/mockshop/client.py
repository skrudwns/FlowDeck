"""연습 쇼핑몰 페이지 요청. 요청 간격, robots.txt, 차단 처리는 PoliteClient (ADR-0004)."""

from flowdeck.polite_http import PoliteClient, Response

# 수집 작업이 같은 머신에 띄운 쇼핑몰 (ADR-0010)
DEFAULT_BASE_URL = "http://127.0.0.1:8020"


class MockShopClient(PoliteClient):
    def __init__(self, base_url: str = DEFAULT_BASE_URL, **kwargs):
        super().__init__(base_url, **kwargs)

    def fetch_list(self, page: int) -> Response:
        return self.get(f"{self.base_url}/products?page={page}")

    def fetch_product(self, product_id: str) -> Response:
        return self.get(f"{self.base_url}/products/{product_id}")
