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


class ProductCreate(BaseModel):
    """다나와 상품 추가. 연습 쇼핑몰 상품은 쇼핑몰 목록으로 정해진다 (ADR-0010)."""

    source_product_id: str


class ProductUpdate(BaseModel):
    active: bool


class AuditLogOut(_FromORM):
    id: int
    at: datetime
    actor: str
    action: str
    target: str
    detail: str | None


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


class ErrorOut(BaseModel):
    """제어 요청을 받을 수 없을 때. detail에 이유를 담는다."""

    detail: str


# 제어 엔드포인트의 오류 응답 (flowdeck.control.ControlError). OpenAPI 문서와 웹 타입에 들어간다
CONTROL_ERRORS = {400: {"model": ErrorOut}, 404: {"model": ErrorOut}, 409: {"model": ErrorOut}}


class RunRequestOut(_FromORM):
    id: int
    job_id: str
    requested_at: datetime
    # pending / done
    status: str
    run_id: int | None
    dispatched_at: datetime | None
    workflow_run_url: str | None
    dispatch_error: str | None


class JobUpdate(BaseModel):
    """바꿀 값만 보낸다."""

    interval_hours: int | None = None
    enabled: bool | None = None


class JobOut(BaseModel):
    id: str
    name: str
    source: str
    description: str
    schedule: str
    interval_hours: int
    enabled: bool
    # 정기 실행이 꺼져 있으면 비어 있다
    next_run_at: datetime | None
    active_products: int
    last_run: RunOut | None
    pending_request: RunRequestOut | None
    # 지금 수동 실행을 요청할 수 없는 이유. 요청할 수 있으면 비어 있다
    manual_run_blocked: str | None
