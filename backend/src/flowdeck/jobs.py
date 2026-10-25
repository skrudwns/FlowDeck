"""수집 작업 정의.

작업 하나가 수집 대상 하나를 맡는다. 주기는 DB(job_schedules)에 있고 실행 판단은
flowdeck.scheduler가 한다 (ADR-0011).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Job:
    id: str
    name: str
    source: str
    description: str
    # 한 시(한국 시간 HH:00~HH:59)에 한 번만 돈다. 다나와 수집 원칙 2의 해석 (ADR-0011)
    one_run_per_hour: bool


JOBS: tuple[Job, ...] = (
    Job(
        id="danawa-prices",
        name="다나와 가격 수집",
        source="danawa",
        description="다나와 상품 페이지에서 최저가, 판매처 수, 상위 판매처 가격을 모은다",
        one_run_per_hour=True,
    ),
    Job(
        id="mockshop-prices",
        name="연습 쇼핑몰 가격 수집",
        source="mockshop",
        description="연습 쇼핑몰 상품 목록을 돌며 판매처별 가격과 재고를 모은다",
        one_run_per_hour=False,
    ),
)

JOBS_BY_ID: dict[str, Job] = {j.id: j for j in JOBS}


def job_for_source(source: str) -> Job:
    return next(j for j in JOBS if j.source == source)
