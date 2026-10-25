from datetime import UTC, datetime

from flowdeck.jobs import JOBS
from flowdeck.models import CollectionRun, JobSchedule


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
    assert (job["interval_hours"], job["enabled"]) == (1, True)
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


def test_jobs_api_reads_schedule_from_db(api, session_factory):
    with session_factory() as session:
        session.add(JobSchedule(job_id="mockshop-prices", interval_hours=6, enabled=False))
        session.commit()

    body = {j["id"]: j for j in api.get("/jobs").json()}

    assert body["mockshop-prices"]["schedule"] == "6시간마다 17분 (0시 기준)"
    assert body["mockshop-prices"]["next_run_at"] is None
    assert body["danawa-prices"]["next_run_at"] is not None
