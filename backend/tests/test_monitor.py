from datetime import UTC, datetime

import httpx

from flowdeck.models import CollectionRun, PriceSnapshot, Product
from flowdeck.monitor import evaluate_run, send_ping

NOW = datetime(2026, 10, 24, 8, 17, tzinfo=UTC)


def make_run(session_factory, statuses, run_status="success", seller_errors=0):
    """statuses: 상품별 스냅샷 상태 목록. seller_errors: ok 중 판매처 목록을 못 읽은 개수."""
    with session_factory() as session:
        run = CollectionRun(
            started_at=NOW,
            finished_at=NOW,
            status=run_status,
            trigger="schedule",
            products_total=len(statuses),
            products_succeeded=statuses.count("ok"),
        )
        session.add(run)
        remaining_seller_errors = seller_errors
        for i, status in enumerate(statuses):
            product = Product(source="danawa", source_product_id=str(1000 + i), active=True)
            message = None
            if status != "ok":
                message = f"{status} 원인"
            elif remaining_seller_errors:
                message = "판매처 목록(ul.list__mall-price)을 찾지 못함"
                remaining_seller_errors -= 1
            session.add(
                PriceSnapshot(
                    run=run,
                    product=product,
                    collected_at=NOW,
                    status=status,
                    lowest_price=50000 if status == "ok" else None,
                    error_message=message,
                )
            )
        session.commit()
        return run.id


def evaluate(session_factory, run_id):
    with session_factory() as session:
        return evaluate_run(session, run_id)


def test_all_ok_is_healthy(session_factory):
    run_id = make_run(session_factory, ["ok"] * 20)

    report = evaluate(session_factory, run_id)

    assert report.ok
    assert "(20/20)" in report.summary


def test_one_or_two_failures_are_still_healthy_but_listed(session_factory):
    run_id = make_run(session_factory, ["ok"] * 18 + ["http_error", "parse_failed"], "partial")

    report = evaluate(session_factory, run_id)

    assert report.ok
    assert "1018 http_error" in report.summary
    assert "1019 parse_failed" in report.summary


def test_three_failures_are_unhealthy(session_factory):
    run_id = make_run(session_factory, ["ok"] * 17 + ["parse_failed"] * 3, "partial")

    report = evaluate(session_factory, run_id)

    assert not report.ok
    assert "요청·파싱 실패 3개" in report.summary


def test_any_blocked_is_unhealthy(session_factory):
    run_id = make_run(session_factory, ["ok", "blocked"], "partial")

    report = evaluate(session_factory, run_id)

    assert not report.ok
    assert "차단 응답" in report.summary


def test_failed_run_is_unhealthy(session_factory):
    run_id = make_run(session_factory, ["http_error"], "failed")

    assert not evaluate(session_factory, run_id).ok


def test_three_seller_list_errors_are_unhealthy(session_factory):
    run_id = make_run(session_factory, ["ok"] * 20, seller_errors=3)

    report = evaluate(session_factory, run_id)

    assert not report.ok
    assert "판매처 목록 파싱 실패 3개" in report.summary


def test_two_seller_list_errors_are_still_healthy(session_factory):
    run_id = make_run(session_factory, ["ok"] * 20, seller_errors=2)

    assert evaluate(session_factory, run_id).ok


def test_missing_run_is_unhealthy(session_factory):
    assert not evaluate(session_factory, 999).ok


def recording_client(status=200):
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append((str(request.url), request.content.decode("utf-8")))
        return httpx.Response(status)

    return httpx.Client(transport=httpx.MockTransport(handler)), sent


def test_ping_success_goes_to_check_url():
    client, sent = recording_client()

    assert send_ping("https://hc-ping.com/abc", True, "run 1: success", http=client)
    assert sent == [("https://hc-ping.com/abc", "run 1: success")]


def test_ping_failure_goes_to_fail_endpoint():
    client, sent = recording_client()

    send_ping("https://hc-ping.com/abc/", False, "문제", http=client)

    assert sent[0][0] == "https://hc-ping.com/abc/fail"


def test_ping_error_does_not_raise():
    client, _ = recording_client(status=500)

    assert send_ping("https://hc-ping.com/abc", True, "x", http=client) is False
