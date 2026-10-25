"""포털에서 수집 워크플로를 바로 실행한다 (workflow_dispatch). 이유는 ADR-0011.

토큰은 이 저장소의 Actions 쓰기 권한만 가진 fine-grained token을 따로 만들어 쓴다.
cron-job.org에 넣은 토큰과 같이 쓰지 않는다. 토큰과 응답 본문은 로그나 오류 메시지에 넣지 않는다.
"""

from dataclasses import dataclass

import httpx

from flowdeck.config import Settings

API_URL = "https://api.github.com"
# ADR-0006에서 확인한 버전. 이 버전부터 성공 응답이 200과 실행 ID다
API_VERSION = "2026-03-10"


class DispatchError(Exception):
    pass


@dataclass(frozen=True)
class DispatchResult:
    workflow_run_id: int | None
    html_url: str | None


class WorkflowDispatcher:
    def __init__(
        self,
        token: str,
        repository: str,
        workflow: str,
        ref: str = "main",
        http: httpx.Client | None = None,
    ):
        self._token = token
        self._url = f"{API_URL}/repos/{repository}/actions/workflows/{workflow}/dispatches"
        self._ref = ref
        self._http = http or httpx.Client(timeout=10.0)

    def dispatch(self, inputs: dict[str, str]) -> DispatchResult:
        try:
            response = self._http.post(
                self._url,
                json={"ref": self._ref, "inputs": inputs},
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": API_VERSION,
                },
            )
        except httpx.HTTPError as e:
            raise DispatchError(f"GitHub 요청 실패: {type(e).__name__}") from None
        if response.status_code == 204:
            # 예전 API 버전의 응답. 실행 ID가 없다
            return DispatchResult(workflow_run_id=None, html_url=None)
        if response.status_code != 200:
            raise DispatchError(f"GitHub 응답 {response.status_code}: {_message(response)}")
        data = response.json()
        return DispatchResult(
            workflow_run_id=data.get("workflow_run_id"), html_url=data.get("html_url")
        )


def _message(response: httpx.Response) -> str:
    try:
        return str(response.json().get("message", ""))[:200]
    except ValueError:
        return ""


def make_dispatcher(settings: Settings) -> WorkflowDispatcher | None:
    """토큰이 없으면 None. 그때 수동 실행 요청은 다음 정기 호출 때 실행된다."""
    if not settings.portal_github_token or not settings.portal_github_token.get_secret_value():
        return None
    return WorkflowDispatcher(
        token=settings.portal_github_token.get_secret_value(),
        repository=settings.portal_github_repository,
        workflow=settings.portal_collect_workflow,
        ref=settings.portal_github_ref,
    )
