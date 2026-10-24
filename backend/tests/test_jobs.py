from datetime import UTC, datetime

from flowdeck.jobs import JOBS, Job

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


def test_danawa_job_is_defined():
    assert [j.id for j in JOBS] == ["danawa-prices"]


def test_jobs_api_includes_last_run_and_counts(api, seeded):
    body = api.get("/jobs").json()

    assert len(body) == 1
    job = body[0]
    assert job["name"] == "다나와 가격 수집"
    assert job["schedule"] == "매시 17분"
    assert job["active_products"] == 1
    assert job["last_run"]["id"] == seeded["run2"]
    assert job["next_run_at"]


def test_jobs_api_without_runs(api, session_factory):
    assert api.get("/jobs").json()[0]["last_run"] is None
