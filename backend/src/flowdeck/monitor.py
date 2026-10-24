"""수집 실행 결과 판정과 Healthchecks.io 신호. 기준과 이유는 docs/adr/0007-collection-monitoring.md.

수집이 아예 안 돌면 이 코드도 안 돈다. 그 경우는 Healthchecks.io가 "신호 없음"으로 잡는다.
"""

import logging
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from flowdeck.models import CollectionRun, PriceSnapshot

# 처음 값. 운영하면서 실제 실패 패턴을 보고 조정한다 (ADR-0007)
MAX_FAILED_PRODUCTS = 2
MAX_SELLER_PARSE_ERRORS = 2

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class HealthReport:
    ok: bool
    summary: str


def evaluate_run(session: Session, run_id: int) -> HealthReport:
    run = session.scalar(
        select(CollectionRun)
        .where(CollectionRun.id == run_id)
        .options(selectinload(CollectionRun.snapshots).selectinload(PriceSnapshot.product))
    )
    if run is None:
        return HealthReport(ok=False, summary=f"run {run_id}을 찾지 못함")

    snapshots = sorted(run.snapshots, key=lambda s: s.id)
    failed = [s for s in snapshots if s.status != "ok"]
    seller_errors = [s for s in snapshots if s.status == "ok" and s.error_message]

    problems = []
    if run.status == "failed":
        problems.append("실행 실패")
    if any(s.status == "blocked" for s in snapshots):
        problems.append("차단 응답")
    if len(failed) > MAX_FAILED_PRODUCTS:
        problems.append(f"요청·파싱 실패 {len(failed)}개")
    if len(seller_errors) > MAX_SELLER_PARSE_ERRORS:
        problems.append(f"판매처 목록 파싱 실패 {len(seller_errors)}개")

    lines = [
        f"run {run.id}: {run.status} ({run.products_succeeded}/{run.products_total}), "
        f"trigger={run.trigger}",
    ]
    if problems:
        lines.append("문제: " + ", ".join(problems))
    if run.error_message:
        lines.append(f"실행 메시지: {run.error_message}")
    for s in failed:
        lines.append(f"- {s.product.source_product_id} {s.status}: {s.error_message}")
    for s in seller_errors:
        lines.append(f"- {s.product.source_product_id} 판매처 목록: {s.error_message}")

    return HealthReport(ok=not problems, summary="\n".join(lines))


def send_ping(url: str, ok: bool, body: str, http: httpx.Client | None = None) -> bool:
    """성공이면 체크 주소로, 아니면 /fail로 보낸다. 전송 실패는 수집 결과에 영향을 주지 않는다."""
    target = url.rstrip("/") + ("" if ok else "/fail")
    client = http or httpx.Client(timeout=10.0)
    try:
        response = client.post(target, content=body.encode("utf-8"))
        response.raise_for_status()
        return True
    except httpx.HTTPError as e:
        # 주소는 비밀 값이라 로그에 남기지 않는다
        log.warning("Healthchecks 신호 전송 실패: %r", type(e).__name__)
        return False
    finally:
        if http is None:
            client.close()
