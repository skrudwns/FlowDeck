import json

import httpx
import pytest

from flowdeck.config import Settings
from flowdeck.github_dispatch import DispatchError, WorkflowDispatcher, make_dispatcher

URL = "https://api.github.com/repos/o/r/actions/workflows/collect.yml/dispatches"


def make(handler):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return WorkflowDispatcher(token="t0ken", repository="o/r", workflow="collect.yml", http=http)


def test_sends_dispatch_and_returns_run_details():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "workflow_run_id": 123,
                "run_url": "https://api.github.com/repos/o/r/actions/runs/123",
                "html_url": "https://github.com/o/r/actions/runs/123",
            },
        )

    result = make(handler).dispatch({"trigger": "portal"})

    assert result.workflow_run_id == 123
    assert result.html_url == "https://github.com/o/r/actions/runs/123"
    request = seen[0]
    assert str(request.url) == URL
    assert request.headers["Authorization"] == "Bearer t0ken"
    assert request.headers["X-GitHub-Api-Version"] == "2026-03-10"
    assert json.loads(request.content) == {"ref": "main", "inputs": {"trigger": "portal"}}


def test_error_status_raises_without_leaking_token():
    def handler(request):
        return httpx.Response(401, json={"message": "Bad credentials"})

    with pytest.raises(DispatchError) as exc:
        make(handler).dispatch({"trigger": "portal"})
    assert str(exc.value) == "GitHub 응답 401: Bad credentials"
    assert "t0ken" not in str(exc.value)


def test_network_error_raises_dispatch_error():
    def handler(request):
        raise httpx.ConnectError("boom")

    with pytest.raises(DispatchError, match="ConnectError"):
        make(handler).dispatch({"trigger": "portal"})


def test_no_dispatcher_without_token(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.delenv("PORTAL_GITHUB_TOKEN", raising=False)
    assert make_dispatcher(Settings(_env_file=None)) is None

    monkeypatch.setenv("PORTAL_GITHUB_TOKEN", "x")
    assert make_dispatcher(Settings(_env_file=None)) is not None


def test_actions_env_vars_do_not_change_dispatch_target(monkeypatch):
    # GitHub Actions는 GITHUB_REPOSITORY, GITHUB_REF를 자동으로 넣는다.
    # GITHUB_REF는 refs/heads/main 형식이라 그대로 읽으면 ref가 잘못된다
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db.example.com/db")
    monkeypatch.setenv("PORTAL_GITHUB_TOKEN", "x")
    monkeypatch.setenv("GITHUB_REPOSITORY", "someone/else")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")

    dispatcher = make_dispatcher(Settings(_env_file=None))

    assert dispatcher._url == URL.replace("o/r", "skrudwns/FlowDeck")
    assert dispatcher._ref == "main"
