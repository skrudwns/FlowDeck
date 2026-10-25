"""수집 데이터와 제어 테이블. 구조와 이유는 docs/adr/0005, 0010, 0011."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Product(Base):
    """수집 대상 상품."""

    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("source", "source_product_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(20))
    # 다나와는 pcode
    source_product_id: Mapped[str] = mapped_column(String(40))
    name: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CollectionRun(Base):
    """수집 실행 한 번."""

    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 수집 대상: danawa / mockshop (ADR-0010)
    source: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # running / success / partial / failed
    status: Mapped[str] = mapped_column(String(20))
    # schedule / manual
    trigger: Mapped[str] = mapped_column(String(20))
    products_total: Mapped[int] = mapped_column(Integer, default=0)
    products_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    snapshots: Mapped[list["PriceSnapshot"]] = relationship(back_populates="run")


class PriceSnapshot(Base):
    """실행마다 상품별 결과. 실패해도 상태와 원인을 남긴다."""

    __tablename__ = "price_snapshots"
    __table_args__ = (Index("ix_price_snapshots_product_collected", "product_id", "collected_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("collection_runs.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # ok / parse_failed / http_error / blocked / disallowed
    status: Mapped[str] = mapped_column(String(20))
    http_status: Mapped[int | None] = mapped_column(SmallInteger)
    lowest_price: Mapped[int | None] = mapped_column(Integer)
    offer_count: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)

    run: Mapped[CollectionRun] = relationship(back_populates="snapshots")
    product: Mapped[Product] = relationship()
    sellers: Mapped[list["SellerPrice"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan", order_by="SellerPrice.rank"
    )


class SellerPrice(Base):
    """스냅샷의 상위 판매처. 페이지에 나오는 만큼 저장한다 (다나와는 관찰한 최대 10곳)."""

    __tablename__ = "seller_prices"

    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("price_snapshots.id", ondelete="CASCADE"), primary_key=True
    )
    rank: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    seller_name: Mapped[str] = mapped_column(Text)
    # 다나와 업체 코드 (예: TH201 = 11번가)
    seller_code: Mapped[str | None] = mapped_column(String(20))
    price: Mapped[int] = mapped_column(Integer)
    delivery_fee: Mapped[int | None] = mapped_column(Integer)
    # 품절로 나온 판매처도 저장한다. 최저가와 판매처 수에는 넣지 않는다 (ADR-0010)
    in_stock: Mapped[bool] = mapped_column(default=True, server_default="true")

    snapshot: Mapped[PriceSnapshot] = relationship(back_populates="sellers")


class JobSchedule(Base):
    """작업별 주기. 행이 없으면 기본값(매시, 켜짐)으로 본다 (ADR-0011)."""

    __tablename__ = "job_schedules"

    # flowdeck.jobs.JOBS의 id
    job_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    interval_hours: Mapped[int] = mapped_column(SmallInteger)
    enabled: Mapped[bool] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RunRequest(Base):
    """포털에서 들어온 수동 실행 요청. Postgres 테이블을 작업 큐로 쓴다 (ADR-0011)."""

    __tablename__ = "run_requests"
    __table_args__ = (Index("ix_run_requests_job_status", "job_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(String(40))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # pending / done
    status: Mapped[str] = mapped_column(String(20))
    # 이 요청을 처리한 수집 실행
    run_id: Mapped[int | None] = mapped_column(ForeignKey("collection_runs.id"))
    # GitHub Actions 바로 실행 결과. dispatch_error는 바로 실행하지 않은(못한) 이유 문장
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    workflow_run_url: Mapped[str | None] = mapped_column(Text)
    dispatch_error: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    """수집 대상, 주기, 수동 실행 변경 이력. 대상 목록 파일의 git 이력을 대신한다 (ADR-0011)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # portal / cli. 인증이 없어서 사람 대신 경로를 남긴다
    actor: Mapped[str] = mapped_column(String(20))
    # product_added / product_reactivated / product_deactivated / schedule_changed / run_requested
    action: Mapped[str] = mapped_column(String(40))
    target: Mapped[str] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(Text)
