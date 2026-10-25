from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from flowdeck.api.deps import DispatcherDep, SessionDep
from flowdeck.api.schemas import ErrorOut, JobOut, JobUpdate, RunOut, RunRequestOut
from flowdeck.control import manual_run_block, request_run, update_schedule
from flowdeck.jobs import JOBS, JOBS_BY_ID, Job
from flowdeck.models import CollectionRun, Product, RunRequest
from flowdeck.scheduler import get_schedule, next_run_at

router = APIRouter(prefix="/jobs", tags=["jobs"])

# 제어 요청을 받을 수 없을 때 (flowdeck.control.ControlError)
CONTROL_ERRORS = {400: {"model": ErrorOut}, 404: {"model": ErrorOut}, 409: {"model": ErrorOut}}


def _get_job(job_id: str) -> Job:
    job = JOBS_BY_ID.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="작업을 찾지 못함")
    return job


def _job_out(session, job: Job, now: datetime) -> JobOut:
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
    pending = session.scalar(
        select(RunRequest)
        .where(RunRequest.job_id == job.id, RunRequest.status == "pending")
        .order_by(RunRequest.id.desc())
    )
    return JobOut(
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
        pending_request=RunRequestOut.model_validate(pending) if pending else None,
        manual_run_blocked=manual_run_block(session, job, now),
    )


@router.get("")
def list_jobs(session: SessionDep) -> list[JobOut]:
    now = datetime.now(UTC)
    return [_job_out(session, job, now) for job in JOBS]


@router.patch("/{job_id}", responses=CONTROL_ERRORS)
def update_job(job_id: str, body: JobUpdate, session: SessionDep) -> JobOut:
    """주기(시간), 정기 실행 켜짐을 바꾼다. 꺼도 수동 실행은 된다."""
    job = _get_job(job_id)
    now = datetime.now(UTC)
    update_schedule(
        session, job, "portal", now, interval_hours=body.interval_hours, enabled=body.enabled
    )
    return _job_out(session, job, now)


@router.post("/{job_id}/run-requests", status_code=201, responses=CONTROL_ERRORS)
def create_run_request(
    job_id: str, session: SessionDep, dispatcher: DispatcherDep
) -> RunRequestOut:
    """수동 실행 요청. GitHub 토큰이 있으면 워크플로를 바로 실행하고, 없거나 실패하면
    다음 정기 호출(매시 17분) 때 실행된다."""
    job = _get_job(job_id)
    request = request_run(session, job, "portal", datetime.now(UTC), dispatcher)
    return RunRequestOut.model_validate(request)
