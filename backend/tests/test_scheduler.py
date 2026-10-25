from datetime import UTC, datetime

from flowdeck.jobs import JOBS_BY_ID
from flowdeck.models import CollectionRun, JobSchedule, RunRequest
from flowdeck.scheduler import (
    KST,
    Schedule,
    latest_slot,
    next_run_at,
    plan,
)

DANAWA = JOBS_BY_ID["danawa-prices"]
MOCKSHOP = JOBS_BY_ID["mockshop-prices"]


def kst(day, hour, minute=0, second=0):
    return datetime(2026, 10, day, hour, minute, second, tzinfo=KST)


def test_latest_slot_hourly():
    assert latest_slot(1, kst(25, 4, 30)) == kst(25, 4, 17)
    assert latest_slot(1, kst(25, 4, 17)) == kst(25, 4, 17)
    assert latest_slot(1, kst(25, 4, 16)) == kst(25, 3, 17)


def test_latest_slot_aligns_to_midnight_kst():
    assert latest_slot(6, kst(25, 8, 0)) == kst(25, 6, 17)
    assert latest_slot(6, kst(25, 6, 5)) == kst(25, 0, 17)
    assert latest_slot(6, kst(25, 0, 5)) == kst(24, 18, 17)
    assert latest_slot(24, kst(25, 23, 59)) == kst(25, 0, 17)


def test_latest_slot_accepts_utc():
    # 2026-10-24 21:30 UTC = 10-25 06:30 한국 시간
    assert latest_slot(6, datetime(2026, 10, 24, 21, 30, tzinfo=UTC)) == kst(25, 6, 17)


def test_next_run_at():
    assert next_run_at(Schedule(6, True), kst(25, 8, 0)) == kst(25, 12, 17)
    assert next_run_at(Schedule(6, False), kst(25, 8, 0)) is None


def test_schedule_labels():
    assert Schedule(1, True).label == "매시 17분"
    assert Schedule(6, True).label == "6시간마다 17분 (0시 기준)"


def add_run(session_factory, source, started_at):
    with session_factory() as session:
        run = CollectionRun(
            source=source,
            started_at=started_at,
            finished_at=started_at,
            status="success",
            trigger="schedule",
            products_total=1,
            products_succeeded=1,
        )
        session.add(run)
        session.commit()


def set_schedule(session_factory, job, interval_hours, enabled=True):
    with session_factory() as session:
        session.add(JobSchedule(job_id=job.id, interval_hours=interval_hours, enabled=enabled))
        session.commit()


def add_request(session_factory, job, at):
    with session_factory() as session:
        session.add(RunRequest(job_id=job.id, requested_at=at, status="pending"))
        session.commit()


def decisions(session_factory, now, dispatch_trigger="schedule"):
    with session_factory() as session:
        return {d.job.id: (d.trigger, d.reason) for d in plan(session, now, dispatch_trigger)}


def test_hourly_jobs_run_when_slot_has_no_run(session_factory):
    add_run(session_factory, "danawa", kst(25, 3, 17, 40))
    add_run(session_factory, "mockshop", kst(25, 3, 17, 40))

    # 정기 실행 시작 시각이 흔들려도(3:17:40 다음 4:17:30) 빠지지 않는다
    result = decisions(session_factory, kst(25, 4, 17, 30))

    assert result["danawa-prices"] == ("schedule", "04:17 정기 실행")
    assert result["mockshop-prices"] == ("schedule", "04:17 정기 실행")


def test_skips_when_slot_already_ran(session_factory):
    set_schedule(session_factory, MOCKSHOP, 6)
    add_run(session_factory, "mockshop", kst(25, 6, 17, 30))

    trigger, reason = decisions(session_factory, kst(25, 7, 17, 30))["mockshop-prices"]

    assert trigger is None
    assert reason == "주기가 아니라 건너뜀. 다음 정기 실행 12:17"


def test_missed_slot_is_caught_up_at_next_tick(session_factory):
    set_schedule(session_factory, MOCKSHOP, 6)
    add_run(session_factory, "mockshop", kst(25, 0, 17, 30))

    # 6:17 호출을 놓쳤으면 7:17에 돈다
    assert decisions(session_factory, kst(25, 7, 17, 30))["mockshop-prices"][0] == "schedule"


def test_disabled_job_does_not_run_on_schedule(session_factory):
    set_schedule(session_factory, MOCKSHOP, 1, enabled=False)

    assert decisions(session_factory, kst(25, 4, 17, 30))["mockshop-prices"] == (
        None,
        "정기 실행이 꺼져 있음",
    )


def test_pending_request_runs_even_when_disabled(session_factory):
    set_schedule(session_factory, MOCKSHOP, 1, enabled=False)
    add_request(session_factory, MOCKSHOP, kst(25, 4, 30))

    result = decisions(session_factory, kst(25, 4, 31), dispatch_trigger="portal")

    assert result["mockshop-prices"] == ("manual", "대기 중인 수동 실행 요청")


def test_github_manual_dispatch_runs_every_job(session_factory):
    add_run(session_factory, "mockshop", kst(25, 4, 17, 30))

    result = decisions(session_factory, kst(25, 4, 40), dispatch_trigger="manual")

    assert result["mockshop-prices"] == ("manual", "GitHub 화면에서 직접 실행")


def test_danawa_runs_at_most_once_per_clock_hour(session_factory):
    add_run(session_factory, "danawa", kst(25, 4, 17, 30))
    add_request(session_factory, DANAWA, kst(25, 4, 40))

    trigger, reason = decisions(session_factory, kst(25, 4, 41), dispatch_trigger="portal")[
        "danawa-prices"
    ]

    assert trigger is None
    assert reason == "이번 시에 이미 수집함. 한 시에 한 번만 수집 (05:00부터 가능)"


def test_danawa_manual_run_before_tick_skips_that_hours_schedule(session_factory):
    add_run(session_factory, "danawa", kst(25, 4, 5))

    # 4:05 수동 실행 뒤 4:17 정기 호출은 시 제한에 걸린다
    assert decisions(session_factory, kst(25, 4, 17, 30))["danawa-prices"][0] is None


def test_mockshop_has_no_hourly_limit(session_factory):
    add_run(session_factory, "mockshop", kst(25, 4, 17, 30))
    add_request(session_factory, MOCKSHOP, kst(25, 4, 40))

    assert decisions(session_factory, kst(25, 4, 41), "portal")["mockshop-prices"][0] == "manual"
