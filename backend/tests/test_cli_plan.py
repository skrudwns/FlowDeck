from flowdeck import cli
from flowdeck.models import JobSchedule


def test_plan_writes_github_output_and_pings_skipped_jobs(session_factory, tmp_path, monkeypatch):
    with session_factory() as session:
        session.add(JobSchedule(job_id="mockshop-prices", interval_hours=1, enabled=False))
        session.commit()
    pings = []
    monkeypatch.setattr(cli, "_ping_url", lambda source: f"https://hc.example/{source}")
    monkeypatch.setattr(cli, "send_ping", lambda url, ok, body: pings.append((url, ok, body)))
    out = tmp_path / "github_output"

    assert cli._plan(session_factory, "schedule", out) == 0

    # 다나와는 실행 기록이 없으니 정기 실행, 연습 쇼핑몰은 꺼져 있어서 건너뜀
    assert out.read_text().splitlines() == ["danawa=schedule", "mockshop="]
    assert pings == [
        (
            "https://hc.example/mockshop",
            True,
            "연습 쇼핑몰 가격 수집: 이번 호출에서 돌지 않음. 정기 실행이 꺼져 있음",
        )
    ]
