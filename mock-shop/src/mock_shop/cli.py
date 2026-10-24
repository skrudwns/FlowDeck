"""연습 쇼핑몰 명령어.

uv run mock-shop serve --port 8020
uv run mock-shop serve --at 2026-10-25T14:00+09:00   # 가격 기준 시각 고정 (화면 확인용)
uv run mock-shop fixtures ../backend/tests/fixtures
"""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

# 백엔드 파서 테스트용 HTML의 기준 시각. 이 시각에 p06은 가장 싼 판매처(바사스토어)가 품절이라
# 최저가에서 품절을 빼는지 확인할 수 있다
FIXTURE_AT = datetime(2026, 10, 25, 5, 0, tzinfo=UTC)
FIXTURE_PRODUCT = "p06"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mock-shop")
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser("serve", help="쇼핑몰 서버 띄우기")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8020)
    serve.add_argument(
        "--at",
        type=datetime.fromisoformat,
        help="가격 기준 시각을 고정한다 (예: 2026-10-25T14:00+09:00). 시간대 필수",
    )

    fixtures = commands.add_parser(
        "fixtures", help="정해 둔 시각의 페이지를 파일로 저장 (백엔드 파서 테스트용)"
    )
    fixtures.add_argument("out_dir", type=Path)

    args = parser.parse_args(argv)
    if args.command == "serve":
        return _serve(args.host, args.port, args.at)
    return _fixtures(args.out_dir)


def _serve(host: str, port: int, at: datetime | None) -> int:
    import uvicorn

    from mock_shop.app import create_app, utc_now

    if at is not None and at.tzinfo is None:
        print("--at에는 시간대를 붙인다 (예: +09:00)", file=sys.stderr)
        return 2
    app = create_app(now=(lambda: at) if at else utc_now)
    uvicorn.run(app, host=host, port=port)
    return 0


def _fixtures(out_dir: Path) -> int:
    from mock_shop.app import render_product, render_product_list

    pages = {
        "mockshop_list_1.html": render_product_list(1, FIXTURE_AT),
        "mockshop_list_2.html": render_product_list(2, FIXTURE_AT),
        "mockshop_product.html": render_product(FIXTURE_PRODUCT, FIXTURE_AT),
    }
    for name, html in pages.items():
        (out_dir / name).write_text(html, encoding="utf-8")
        print(f"저장: {out_dir / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
