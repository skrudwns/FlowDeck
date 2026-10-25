from datetime import UTC, datetime

from flowdeck.api.deps import get_dispatcher
from flowdeck.github_dispatch import DispatchResult
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


def test_update_job_schedule(api, session_factory):
    response = api.patch("/jobs/mockshop-prices", json={"interval_hours": 3})

    assert response.status_code == 200
    assert response.json()["schedule"] == "3시간마다 17분 (0시 기준)"
    assert api.patch("/jobs/mockshop-prices", json={"enabled": False}).json()["enabled"] is False


def test_update_job_rejects_unknown_interval(api, session_factory):
    response = api.patch("/jobs/mockshop-prices", json={"interval_hours": 5})

    assert response.status_code == 400
    assert response.json() == {"detail": "주기는 1, 2, 3, 4, 6, 8, 12, 24시간 중 하나"}


def test_unknown_job_is_404(api, session_factory):
    assert api.patch("/jobs/nope", json={"enabled": False}).status_code == 404
    assert api.post("/jobs/nope/run-requests").status_code == 404


def test_run_request_is_queued_without_token(api, session_factory):
    response = api.post("/jobs/mockshop-prices/run-requests")

    assert response.status_code == 201
    body = response.json()
    assert (body["status"], body["dispatched_at"]) == ("pending", None)

    job = {j["id"]: j for j in api.get("/jobs").json()}["mockshop-prices"]
    assert job["pending_request"]["id"] == body["id"]
    assert job["manual_run_blocked"] == "이미 대기 중인 실행 요청이 있음"

    second = api.post("/jobs/mockshop-prices/run-requests")
    assert second.status_code == 409
    assert second.json() == {"detail": "이미 대기 중인 실행 요청이 있음"}


def test_run_request_dispatches_with_token(api, session_factory):
    class Dispatcher:
        def dispatch(self, inputs):
            return DispatchResult(
                workflow_run_id=7, html_url="https://github.com/o/r/actions/runs/7"
            )

    api.app.dependency_overrides[get_dispatcher] = lambda: Dispatcher()

    body = api.post("/jobs/mockshop-prices/run-requests").json()

    assert body["workflow_run_url"] == "https://github.com/o/r/actions/runs/7"
    assert body["dispatched_at"] is not None
