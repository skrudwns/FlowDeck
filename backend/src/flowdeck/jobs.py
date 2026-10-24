"""수집 작업 정의.

실제로 실행을 거는 건 cron-job.org다 (ADR-0006). 여기 주기는 포털에 보여주고 다음 실행 시각을
계산하는 데만 쓴다. 주기를 바꾸면 cron-job.org 설정도 같이 고쳐야 한다 (ADR-0009).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Job:
    id: str
    name: str
    source: str
    description: str
    # 매시 몇 분에 도는지. 지금 작업은 모두 1시간 주기다
    minute_of_hour: int

    @property
    def schedule(self) -> str:
        return f"매시 {self.minute_of_hour}분"

    def next_run_after(self, now: datetime) -> datetime:
        candidate = now.replace(minute=self.minute_of_hour, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(hours=1)
        return candidate


JOBS: tuple[Job, ...] = (
    Job(
        id="danawa-prices",
        name="다나와 가격 수집",
        source="danawa",
        description="다나와 상품 페이지에서 최저가, 판매처 수, 상위 판매처 가격을 모은다",
        minute_of_hour=17,
    ),
)
