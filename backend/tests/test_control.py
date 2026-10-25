from datetime import datetime

import pytest
from sqlalchemy import select

from flowdeck import control
from flowdeck.control import (
    ControlError,
    add_danawa_product,
    manual_run_block,
    request_run,
    set_product_active,
    update_schedule,
)
from flowdeck.github_dispatch import DispatchError, DispatchResult
from flowdeck.jobs import JOBS_BY_ID
from flowdeck.models import AuditLog, CollectionRun, Product, RunRequest
from flowdeck.scheduler import KST, Schedule, get_schedule

NOW = datetime(2026, 10, 25, 14, 30, tzinfo=KST)
DANAWA = JOBS_BY_ID["danawa-prices"]
MOCKSHOP = JOBS_BY_ID["mockshop-prices"]


def audit(session):
    return [(a.actor, a.action, a.target, a.detail) for a in session.scalars(select(AuditLog))]


def test_add_danawa_product_and_log(session_factory):
    with session_factory() as session:
        product = add_danawa_product(session, " 1234 ", "portal", NOW)

        assert (product.source, product.source_product_id, product.active) == (
            "danawa",
            "1234",
            True,
        )
        assert audit(session) == [("portal", "product_added", "danawa:1234", None)]


def test_add_reactivates_stopped_product(session_factory):
    with session_factory() as session:
        session.add(Product(source="danawa", source_product_id="1", name="A", active=False))
        session.commit()

        add_danawa_product(session, "1", "cli", NOW)

        assert session.scalar(select(Product.active)) is True
        assert audit(session) == [("cli", "product_reactivated", "danawa:1", "A")]


@pytest.mark.parametrize(
    ("pcode", "status"),
    [("abc", 400), ("1", 409)],
)
def test_add_rejects_invalid_or_duplicate(session_factory, pcode, status):
    with session_factory() as session:
        session.add(Product(source="danawa", source_product_id="1", active=True))
        session.commit()

        with pytest.raises(ControlError) as exc:
            add_danawa_product(session, pcode, "portal", NOW)
        assert exc.value.status == status


def test_add_stops_at_active_limit(session_factory, monkeypatch):
    monkeypatch.setattr(control, "MAX_ACTIVE_DANAWA", 2)
    with session_factory() as session:
        add_danawa_product(session, "1", "portal", NOW)
        add_danawa_product(session, "2", "portal", NOW)

        with pytest.raises(ControlError, match="2개까지"):
            add_danawa_product(session, "3", "portal", NOW)


def test_deactivate_and_reactivate(session_factory):
    with session_factory() as session:
        product = add_danawa_product(session, "1", "portal", NOW)
        set_product_active(session, product, False, "portal", NOW)
        # 상태가 같으면 기록하지 않는다
        set_product_active(session, product, False, "portal", NOW)
        set_product_active(session, product, True, "portal", NOW)

        assert [a[1] for a in audit(session)] == [
            "product_added",
            "product_deactivated",
            "product_reactivated",
        ]


def test_mockshop_products_cannot_be_changed(session_factory):
    with session_factory() as session:
        product = Product(source="mockshop", source_product_id="p01", active=True)
        session.add(product)
        session.commit()

        with pytest.raises(ControlError, match="연습 쇼핑몰"):
            set_product_active(session, product, False, "portal", NOW)


def test_update_schedule_and_log(session_factory):
    with session_factory() as session:
        update_schedule(session, MOCKSHOP, "portal", NOW, interval_hours=6)
        update_schedule(session, MOCKSHOP, "portal", NOW, enabled=False)
        # 바뀐 게 없으면 기록하지 않는다
        update_schedule(session, MOCKSHOP, "portal", NOW, enabled=False)

        assert get_schedule(session, MOCKSHOP.id) == Schedule(6, False)
        assert [a[3] for a in audit(session)] == [
            "매시 17분 → 6시간마다 17분 (0시 기준)",
            "6시간마다 17분 (0시 기준) → 6시간마다 17분 (0시 기준), 꺼짐",
        ]


def test_update_schedule_rejects_unknown_interval(session_factory):
    with session_factory() as session:
        with pytest.raises(ControlError) as exc:
            update_schedule(session, MOCKSHOP, "portal", NOW, interval_hours=5)
        assert exc.value.status == 400


class FakeDispatcher:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def dispatch(self, inputs):
        self.calls.append(inputs)
        if self.error:
            raise self.error
        return DispatchResult(workflow_run_id=1, html_url="https://github.com/o/r/actions/runs/1")


def test_request_run_queues_and_dispatches(session_factory):
    dispatcher = FakeDispatcher()
    with session_factory() as session:
        request = request_run(session, MOCKSHOP, "portal", NOW, dispatcher)

        assert dispatcher.calls == [{"trigger": "portal"}]
        assert (request.status, request.workflow_run_url, request.dispatch_error) == (
            "pending",
            "https://github.com/o/r/actions/runs/1",
            None,
        )
        assert audit(session) == [("portal", "run_requested", "mockshop-prices", None)]


def test_request_stays_queued_when_dispatch_fails(session_factory):
    dispatcher = FakeDispatcher(error=DispatchError("GitHub 응답 401: Bad credentials"))
    with session_factory() as session:
        request = request_run(session, MOCKSHOP, "portal", NOW, dispatcher)

        assert request.status == "pending"
        assert request.dispatched_at is None
        assert request.dispatch_error == "GitHub 응답 401: Bad credentials"


def test_second_request_is_rejected_while_one_is_pending(session_factory):
    with session_factory() as session:
        request_run(session, MOCKSHOP, "portal", NOW, None)

        assert manual_run_block(session, MOCKSHOP, NOW) == "이미 대기 중인 실행 요청이 있음"
        with pytest.raises(ControlError):
            request_run(session, MOCKSHOP, "portal", NOW, None)
        assert len(session.scalars(select(RunRequest)).all()) == 1


def test_danawa_request_rejected_after_run_this_hour(session_factory):
    with session_factory() as session:
        session.add(
            CollectionRun(
                source="danawa",
                started_at=datetime(2026, 10, 25, 14, 17, tzinfo=KST),
                status="success",
                trigger="schedule",
                products_total=1,
                products_succeeded=1,
            )
        )
        session.commit()

        with pytest.raises(ControlError, match="15:00부터 가능"):
            request_run(session, DANAWA, "portal", NOW, None)
