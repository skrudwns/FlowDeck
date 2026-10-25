"""수집기 명령어.

uv run flowdeck products sync targets/danawa.txt
uv run flowdeck products add 109680239 122644105
uv run flowdeck products list
uv run flowdeck products deactivate 109680239
uv run flowdeck collect --trigger manual
uv run flowdeck collect --source mockshop --mockshop-url http://127.0.0.1:8020
uv run flowdeck plan --trigger schedule --github-output "$GITHUB_OUTPUT"
uv run flowdeck openapi ../web/openapi.json
"""

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from flowdeck.collector import run_collection
from flowdeck.config import get_settings
from flowdeck.danawa import SOURCE, danawa_source
from flowdeck.danawa.client import DanawaClient
from flowdeck.db import make_engine, make_session_factory
from flowdeck.jobs import job_for_source
from flowdeck.mockshop import SOURCE as MOCKSHOP
from flowdeck.mockshop import mockshop_source
from flowdeck.mockshop.client import DEFAULT_BASE_URL as DEFAULT_MOCKSHOP_URL
from flowdeck.mockshop.client import MockShopClient
from flowdeck.models import Product
from flowdeck.monitor import evaluate_run, send_ping
from flowdeck.scheduler import plan
from flowdeck.sources import Source
from flowdeck.targets import read_targets, sync_products


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="flowdeck")
    commands = parser.add_subparsers(dest="command", required=True)

    products = commands.add_parser("products", help="수집 대상 상품 관리").add_subparsers(
        dest="action", required=True
    )
    sync = products.add_parser(
        "sync", help="대상 목록 파일과 DB 맞추기 (파일에 없는 상품은 비활성화)"
    )
    sync.add_argument("file", type=Path)
    add = products.add_parser("add", help="다나와 pcode로 상품 추가 (이미 있으면 다시 활성화)")
    add.add_argument("pcodes", nargs="+")
    products.add_parser("list", help="상품 목록")
    deactivate = products.add_parser("deactivate", help="수집 대상에서 빼기 (기록은 남김)")
    deactivate.add_argument("pcodes", nargs="+")

    collect = commands.add_parser("collect", help="수집 한 번 실행")
    collect.add_argument("--source", choices=[SOURCE, MOCKSHOP], default=SOURCE)
    collect.add_argument("--trigger", choices=["schedule", "manual"], default="manual")
    collect.add_argument("--mockshop-url", default=DEFAULT_MOCKSHOP_URL, help="연습 쇼핑몰 주소")
    collect.add_argument("--delay", type=float, default=3.0, help="요청 사이 간격(초)")

    plan_cmd = commands.add_parser(
        "plan", help="이번 호출에서 돌 작업 정하기 (수집 워크플로 첫 단계, ADR-0011)"
    )
    plan_cmd.add_argument(
        "--trigger",
        choices=["schedule", "portal", "manual"],
        default="manual",
        help="워크플로를 호출한 쪽: cron-job.org, 포털, GitHub 화면",
    )
    plan_cmd.add_argument(
        "--github-output", type=Path, help="수집 대상별 실행 종류를 적을 GitHub Actions 출력 파일"
    )

    openapi = commands.add_parser(
        "openapi", help="포털 API의 OpenAPI 문서를 파일로 저장 (웹 타입 생성용)"
    )
    openapi.add_argument("out", type=Path)

    args = parser.parse_args(argv)
    if args.command == "openapi":
        return _openapi(args.out)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    session_factory = make_session_factory(make_engine())

    if args.command == "plan":
        return _plan(session_factory, args.trigger, args.github_output)
    if args.command == "collect":
        if args.source == MOCKSHOP:
            client = MockShopClient(args.mockshop_url, delay_seconds=args.delay)
            source = mockshop_source(client)
        else:
            client = DanawaClient(delay_seconds=args.delay)
            source = danawa_source(client)
        try:
            return _collect(session_factory, source, args.trigger)
        finally:
            client.close()
    if args.action == "sync":
        return _sync(session_factory, args.file)
    if args.action == "add":
        return _add(session_factory, args.pcodes)
    if args.action == "deactivate":
        return _set_active(session_factory, args.pcodes, active=False)
    return _list(session_factory)


def _ping_url(source: str) -> str | None:
    settings = get_settings()
    secret = settings.mockshop_healthcheck_url if source == MOCKSHOP else settings.healthcheck_url
    return secret.get_secret_value() if secret else None


def _plan(session_factory, trigger: str, github_output: Path | None) -> int:
    with session_factory() as session:
        decisions = plan(session, datetime.now(UTC), trigger)

    lines = []
    for d in decisions:
        print(f"{d.job.id}: {d.trigger or '건너뜀'} ({d.reason})")
        lines.append(f"{d.job.source}={d.trigger or ''}")
        if d.trigger is None:
            # 주기를 늘려도 Healthchecks가 "신호 없음"으로 알리지 않게
            # 스케줄러가 돌았다는 신호를 보낸다 (ADR-0011 감시)
            ping_url = _ping_url(d.job.source)
            if ping_url:
                body = f"{d.job.name}: 이번 호출에서 돌지 않음. {d.reason}"
                send_ping(ping_url, ok=True, body=body)
    if github_output:
        with github_output.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return 0


def _collect(session_factory, source: Source, trigger: str) -> int:
    ping_url = _ping_url(source.name)

    try:
        run = run_collection(
            session_factory, source, trigger=trigger, job_id=job_for_source(source.name).id
        )
    except Exception as e:
        if ping_url:
            send_ping(ping_url, ok=False, body=f"{source.name} 수집 중 예상하지 못한 오류: {e!r}")
        raise

    with session_factory() as session:
        report = evaluate_run(session, run.id)
    print(report.summary)
    print(f"걸린 시간: {run.finished_at - run.started_at}")

    if ping_url:
        sent = send_ping(ping_url, ok=report.ok, body=report.summary)
        kind = "정상" if report.ok else "fail"
        print(f"Healthchecks 신호({kind}): {'보냄' if sent else '전송 실패'}")
    else:
        print("Healthchecks 주소가 없어서 신호를 보내지 않음")

    # 문제가 있으면 GitHub Actions에서도 실패로 보이게 종료 코드 1
    return 0 if report.ok else 1


def _openapi(out: Path) -> int:
    """서버를 띄우지 않고 앱 정의에서 바로 뽑는다. DB에는 접속하지 않는다."""
    import json

    from flowdeck.api.app import create_app

    text = json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n"
    out.write_text(text, encoding="utf-8")
    print(f"저장: {out}")
    return 0


def _sync(session_factory, path: Path) -> int:
    pcodes = read_targets(path)
    with session_factory() as session:
        result = sync_products(session, SOURCE, pcodes)
    print(
        f"대상 {len(pcodes)}개: 추가 {len(result.added)}, 다시 활성화 {len(result.reactivated)}, "
        f"비활성화 {len(result.deactivated)}"
    )
    for pcode in result.deactivated:
        print(f"  비활성화: {pcode}")
    return 0


def _add(session_factory, pcodes: list[str]) -> int:
    with session_factory() as session:
        for pcode in pcodes:
            if not pcode.isdigit():
                print(f"pcode는 숫자여야 함: {pcode}", file=sys.stderr)
                return 2
            product = session.scalar(
                select(Product).where(Product.source == SOURCE, Product.source_product_id == pcode)
            )
            if product is None:
                session.add(Product(source=SOURCE, source_product_id=pcode, active=True))
                print(f"추가: {pcode}")
            elif not product.active:
                product.active = True
                print(f"다시 활성화: {pcode}")
            else:
                print(f"이미 있음: {pcode}")
        session.commit()
    return 0


def _set_active(session_factory, pcodes: list[str], active: bool) -> int:
    with session_factory() as session:
        found = session.scalars(
            select(Product).where(Product.source == SOURCE, Product.source_product_id.in_(pcodes))
        ).all()
        for product in found:
            product.active = active
        session.commit()
        missing = set(pcodes) - {p.source_product_id for p in found}
    for pcode in sorted(missing):
        print(f"없는 상품: {pcode}", file=sys.stderr)
    return 1 if missing else 0


def _list(session_factory) -> int:
    with session_factory() as session:
        for p in session.scalars(select(Product).order_by(Product.id)):
            print(f"{p.source_product_id}\t{'활성' if p.active else '중지'}\t{p.name or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
