"""수집기 명령어.

uv run flowdeck products sync targets/danawa.txt
uv run flowdeck products add 109680239 122644105
uv run flowdeck products list
uv run flowdeck products deactivate 109680239
uv run flowdeck collect --trigger manual
"""

import argparse
import logging
import sys
from pathlib import Path

from sqlalchemy import select

from flowdeck.collector import SOURCE, run_collection
from flowdeck.danawa.client import DanawaClient
from flowdeck.db import make_engine, make_session_factory
from flowdeck.models import Product
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
    collect.add_argument("--trigger", choices=["schedule", "manual"], default="manual")
    collect.add_argument("--delay", type=float, default=3.0, help="요청 사이 간격(초)")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    session_factory = make_session_factory(make_engine())

    if args.command == "collect":
        return _collect(session_factory, args.trigger, args.delay)
    if args.action == "sync":
        return _sync(session_factory, args.file)
    if args.action == "add":
        return _add(session_factory, args.pcodes)
    if args.action == "deactivate":
        return _set_active(session_factory, args.pcodes, active=False)
    return _list(session_factory)


def _collect(session_factory, trigger: str, delay: float) -> int:
    client = DanawaClient(delay_seconds=delay)
    try:
        run = run_collection(session_factory, client, trigger=trigger)
    finally:
        client.close()
    print(
        f"run {run.id}: {run.status} "
        f"({run.products_succeeded}/{run.products_total}) "
        f"{run.finished_at - run.started_at}"
    )
    if run.error_message:
        print(run.error_message)
    # 전부 실패하면 GitHub Actions에서 실패로 보이게 종료 코드 1
    return 1 if run.status == "failed" else 0


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
