"""작업 주기와 실행 판단. 규칙과 이유는 docs/adr/0011-portal-control-and-scheduler.md.

cron-job.org가 매시 17분에 수집 워크플로를 호출하면(ADR-0006) 워크플로 첫 단계에서 plan()이
작업마다 돌지 말지 정한다. 포털이나 GitHub 화면에서 호출해도 같은 규칙으로 본다.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from flowdeck.jobs import JOBS, Job
from flowdeck.models import CollectionRun, JobSchedule, RunRequest

KST = ZoneInfo("Asia/Seoul")
# cron-job.org가 호출하는 분. 바꾸려면 cron-job.org 설정도 바꿔야 한다
TICK_MINUTE = 17
# 24의 약수만 둬서 날마다 같은 시각에 돈다
INTERVAL_CHOICES = (1, 2, 3, 4, 6, 8, 12, 24)


@dataclass(frozen=True)
class Schedule:
    interval_hours: int
    enabled: bool

    @property
    def label(self) -> str:
        if self.interval_hours == 1:
            return f"매시 {TICK_MINUTE}분"
        return f"{self.interval_hours}시간마다 {TICK_MINUTE}분 (0시 기준)"


DEFAULT_SCHEDULE = Schedule(interval_hours=1, enabled=True)


def get_schedule(session: Session, job_id: str) -> Schedule:
    row = session.get(JobSchedule, job_id)
    if row is None:
        return DEFAULT_SCHEDULE
    return Schedule(interval_hours=row.interval_hours, enabled=row.enabled)


def latest_slot(interval_hours: int, now: datetime) -> datetime:
    """now 이전(같으면 포함)의 가장 최근 정기 실행 시각.

    한국 시간 0시부터 interval_hours마다, 매번 17분.
    """
    local = now.astimezone(KST)
    slot = local.replace(minute=TICK_MINUTE, second=0, microsecond=0)
    slot = slot.replace(hour=slot.hour - slot.hour % interval_hours)
    if slot > local:
        slot -= timedelta(hours=interval_hours)
    return slot


def next_run_at(schedule: Schedule, now: datetime) -> datetime | None:
    if not schedule.enabled:
        return None
    return latest_slot(schedule.interval_hours, now) + timedelta(hours=schedule.interval_hours)


def hourly_limit_until(session: Session, job: Job, now: datetime) -> datetime | None:
    """한 시에 한 번만 도는 작업(다나와)이 이번 시에 이미 돌았으면, 다시 돌 수 있는 시각."""
    if not job.one_run_per_hour:
        return None
    hour_start = now.astimezone(KST).replace(minute=0, second=0, microsecond=0)
    if _ran_since(session, job, hour_start):
        return hour_start + timedelta(hours=1)
    return None


def has_pending_request(session: Session, job: Job) -> bool:
    return bool(
        session.scalar(
            select(exists().where(RunRequest.job_id == job.id, RunRequest.status == "pending"))
        )
    )


def _ran_since(session: Session, job: Job, since: datetime) -> bool:
    return bool(
        session.scalar(
            select(
                exists().where(
                    CollectionRun.source == job.source, CollectionRun.started_at >= since
                )
            )
        )
    )


@dataclass(frozen=True)
class Decision:
    job: Job
    # schedule / manual. None이면 이번 호출에서 돌지 않는다
    trigger: str | None
    reason: str


def decide(session: Session, job: Job, now: datetime, dispatch_trigger: str) -> Decision:
    """dispatch_trigger: 워크플로를 호출한 쪽 (schedule / portal / manual)."""
    schedule = get_schedule(session, job.id)
    slot = latest_slot(schedule.interval_hours, now)

    if has_pending_request(session, job):
        trigger, reason = "manual", "대기 중인 수동 실행 요청"
    elif schedule.enabled and not _ran_since(session, job, slot):
        trigger, reason = "schedule", f"{slot:%H:%M} 정기 실행"
    elif dispatch_trigger == "manual":
        trigger, reason = "manual", "GitHub 화면에서 직접 실행"
    elif not schedule.enabled:
        return Decision(job, None, "정기 실행이 꺼져 있음")
    else:
        upcoming = next_run_at(schedule, now)
        return Decision(job, None, f"주기가 아니라 건너뜀. 다음 정기 실행 {upcoming:%H:%M}")

    blocked_until = hourly_limit_until(session, job, now)
    if blocked_until is not None:
        return Decision(
            job,
            None,
            f"이번 시에 이미 수집함. 한 시에 한 번만 수집 ({blocked_until:%H:%M}부터 가능)",
        )
    return Decision(job, trigger, reason)


def plan(session: Session, now: datetime, dispatch_trigger: str) -> list[Decision]:
    return [decide(session, job, now, dispatch_trigger) for job in JOBS]
