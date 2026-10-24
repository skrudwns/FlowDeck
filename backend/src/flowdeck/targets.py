"""수집 대상 목록 파일과 DB 맞추기.

대상 목록을 파일(backend/targets/danawa.txt)로 두면 무엇을 언제 넣고 뺐는지가 git 이력에 남는다.
파일에 없는 상품은 지우지 않고 비활성화만 한다. 이미 쌓인 가격 기록은 남긴다.
"""

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from flowdeck.models import Product


@dataclass(frozen=True)
class SyncResult:
    added: list[str]
    reactivated: list[str]
    deactivated: list[str]


def read_targets(path: Path) -> list[str]:
    """한 줄에 pcode 하나. # 뒤는 주석."""
    pcodes = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        value = line.split("#", 1)[0].strip()
        if not value:
            continue
        if not value.isdigit():
            raise ValueError(f"{path}:{number} pcode는 숫자여야 함: {value!r}")
        if value not in pcodes:
            pcodes.append(value)
    return pcodes


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
