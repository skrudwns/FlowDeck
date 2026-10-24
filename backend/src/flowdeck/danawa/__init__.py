"""다나와 상품 페이지 수집. 범위와 원칙은 docs/adr/0004, 0005."""

from flowdeck.danawa.client import DanawaClient
from flowdeck.danawa.parser import parse_product_page
from flowdeck.sources import Source

SOURCE = "danawa"


def danawa_source(client: DanawaClient) -> Source:
    return Source(name=SOURCE, fetch_product=client.fetch_product, parse=parse_product_page)
