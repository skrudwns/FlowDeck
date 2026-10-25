from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import func, select

from flowdeck.api.deps import SessionDep
from flowdeck.api.schemas import JobOut, RunOut
from flowdeck.jobs import JOBS
from flowdeck.models import CollectionRun, Product
from flowdeck.scheduler import get_schedule, next_run_at

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def list_jobs(session: SessionDep) -> list[JobOut]:
    now = datetime.now(UTC)
    jobs = []
    for job in JOBS:
        schedule = get_schedule(session, job.id)
        # 작업 하나가 수집 대상 하나를 맡는다
        last_run = session.scalar(
            select(CollectionRun)
            .where(CollectionRun.source == job.source)
            .order_by(CollectionRun.started_at.desc(), CollectionRun.id.desc())
        )
        active = session.scalar(
            select(func.count())
            .select_from(Product)
            .where(Product.source == job.source, Product.active)
        )
        jobs.append(
            JobOut(
                id=job.id,
                name=job.name,
                source=job.source,
                description=job.description,
                schedule=schedule.label,
                interval_hours=schedule.interval_hours,
                enabled=schedule.enabled,
                next_run_at=next_run_at(schedule, now),
                active_products=active or 0,
                last_run=RunOut.model_validate(last_run) if last_run else None,
            )
        )
    return jobs
