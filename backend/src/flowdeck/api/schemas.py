"""API 응답 형식. DB 모델을 그대로 내보내지 않는다 (ADR-0008)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _FromORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LatestResult(_FromORM):
    """상품의 가장 최근 수집 결과. 실패했으면 가격은 비어 있다."""

    snapshot_id: int
    collected_at: datetime
    status: str
    lowest_price: int | None
    offer_count: int | None


class ProductOut(_FromORM):
    id: int
    source: str
    source_product_id: str
    name: str | None
    active: bool
    created_at: datetime
    latest: LatestResult | None = None


class PricePoint(_FromORM):
    snapshot_id: int
    collected_at: datetime
    status: str
    lowest_price: int | None
    offer_count: int | None


class SellerOut(_FromORM):
    rank: int
    seller_name: str
    seller_code: str | None
    price: int
    delivery_fee: int | None
    # 품절로 나온 판매처. 최저가와 판매처 수에는 들어가지 않는다 (ADR-0010)
    in_stock: bool


class RunOut(_FromORM):
    id: int
    source: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    trigger: str
    products_total: int
    products_succeeded: int
    error_message: str | None


class RunProductResult(_FromORM):
    snapshot_id: int
    product_id: int
    source_product_id: str
    product_name: str | None
    status: str
    http_status: int | None
    lowest_price: int | None
    error_message: str | None


class RunDetail(RunOut):
    results: list[RunProductResult]


class JobOut(BaseModel):
    id: str
    name: str
    source: str
    description: str
    schedule: str
    next_run_at: datetime
    active_products: int
    last_run: RunOut | None
