from datetime import UTC, datetime

from flowdeck.jobs import JOBS, Job
from flowdeck.models import CollectionRun

JOB = Job(id="x", name="x", source="danawa", description="", minute_of_hour=17)


def test_next_run_is_later_this_hour():
    now = datetime(2026, 10, 24, 12, 5, tzinfo=UTC)

    assert JOB.next_run_after(now) == datetime(2026, 10, 24, 12, 17, tzinfo=UTC)


def test_next_run_moves_to_next_hour_once_passed():
    now = datetime(2026, 10, 24, 12, 17, tzinfo=UTC)

    assert JOB.next_run_after(now) == datetime(2026, 10, 24, 13, 17, tzinfo=UTC)


def test_next_run_crosses_midnight():
    now = datetime(2026, 10, 24, 23, 40, tzinfo=UTC)

    assert JOB.next_run_after(now) == datetime(2026, 10, 25, 0, 17, tzinfo=UTC)


def test_schedule_label():
    assert JOB.schedule == "매시 17분"


def test_jobs_are_defined_one_per_source():
    assert [(j.id, j.source) for j in JOBS] == [
        ("danawa-prices", "danawa"),
        ("mockshop-prices", "mockshop"),
    ]


def test_jobs_api_includes_last_run_and_counts(api, seeded):
    body = api.get("/jobs").json()

    assert len(body) == 2
    job = body[0]
    assert job["name"] == "다나와 가격 수집"
    assert job["schedule"] == "매시 17분"
    assert job["active_products"] == 1
    assert job["last_run"]["id"] == seeded["run2"]
    assert job["next_run_at"]


def test_jobs_api_without_runs(api, session_factory):
    assert [j["last_run"] for j in api.get("/jobs").json()] == [None, None]


def test_each_job_gets_last_run_of_its_own_source(api, seeded, session_factory):
    mockshop_run = add_run(session_factory, "mockshop", datetime(2026, 10, 24, 8, 30, tzinfo=UTC))

    body = {j["id"]: j for j in api.get("/jobs").json()}

    # 다나와 run2(09:17)가 더 최근이지만 연습 쇼핑몰 작업에는 붙지 않는다
    assert body["danawa-prices"]["last_run"]["id"] == seeded["run2"]
    assert body["mockshop-prices"]["last_run"]["id"] == mockshop_run
    assert body["mockshop-prices"]["last_run"]["source"] == "mockshop"


def add_run(session_factory, source, at):
    with session_factory() as session:
        run = CollectionRun(
            source=source,
            started_at=at,
            finished_at=at,
            status="success",
            trigger="schedule",
            products_total=0,
            products_succeeded=0,
        )
        session.add(run)
        session.commit()
        return run.id
