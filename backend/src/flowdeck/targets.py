"""사이트에서 찾은 상품 목록과 DB 맞추기 (연습 쇼핑몰, ADR-0010).

목록에 없는 상품은 지우지 않고 비활성화만 한다. 이미 쌓인 가격 기록은 남긴다.
다나와 수집 대상은 2026-10-25부터 파일이 아니라 DB가 기준이다 (ADR-0011).
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from flowdeck.models import Product


@dataclass(frozen=True)
class SyncResult:
    added: list[str]
    reactivated: list[str]
    deactivated: list[str]


def sync_products(session: Session, source: str, pcodes: list[str]) -> SyncResult:
    existing = {
        p.source_product_id: p
        for p in session.scalars(select(Product).where(Product.source == source))
    }
    wanted = set(pcodes)
    added, reactivated, deactivated = [], [], []

    for pcode in pcodes:
        product = existing.get(pcode)
        if product is None:
            session.add(Product(source=source, source_product_id=pcode, active=True))
            added.append(pcode)
        elif not product.active:
            product.active = True
            reactivated.append(pcode)

    for pcode, product in existing.items():
        if pcode not in wanted and product.active:
            product.active = False
            deactivated.append(pcode)

    session.commit()
    return SyncResult(added, reactivated, sorted(deactivated))
