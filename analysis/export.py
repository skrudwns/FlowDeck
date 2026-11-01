"""수집 DB(Neon)를 읽어 data/에 parquet으로 저장한다. DB에는 쓰지 않는다.

uv run python export.py                 # backend/.env.neon의 DATABASE_URL
DATABASE_URL=... uv run python export.py

data/는 커밋하지 않는다 (ADR-0004 수집 원칙 6).
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import dotenv_values
from sqlalchemy import create_engine, text

from flowdeck.db import sqlalchemy_url

HERE = Path(__file__).parent
DATA = HERE / "data"

QUERIES = {
    "runs": """
        select id, source, started_at, finished_at, status, trigger,
               products_total, products_succeeded, error_message
        from collection_runs
    """,
    "snapshots": """
        select s.id as snapshot_id, s.run_id, s.collected_at, s.status, s.http_status,
               s.lowest_price, s.offer_count, s.error_message,
               p.id as product_id, p.source, p.source_product_id, p.name, p.active
        from price_snapshots s join products p on p.id = s.product_id
    """,
    "sellers": """
        select sp.snapshot_id, sp.rank, sp.seller_name, sp.seller_code, sp.price,
               sp.delivery_fee, sp.in_stock
        from seller_prices sp
    """,
}


def database_url() -> str:
    url = os.environ.get("DATABASE_URL") or dotenv_values(
        HERE.parent / "backend" / ".env.neon"
    ).get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL이 없음 (backend/.env.neon 또는 환경 변수)")
    return url


def main() -> None:
    DATA.mkdir(exist_ok=True)
    engine = create_engine(sqlalchemy_url(database_url()))
    with engine.connect() as conn:
        conn.execute(text("set transaction read only"))
        for name, sql in QUERIES.items():
            frame = pd.read_sql(text(sql), conn)
            path = DATA / f"{name}.parquet"
            frame.to_parquet(path, index=False)
            print(f"{name}: {len(frame):,}행 → {path.relative_to(HERE)}")
        exported_at = conn.execute(text("select now()")).scalar()
    (DATA / "exported_at.txt").write_text(exported_at.isoformat() + "\n", encoding="utf-8")
    print(f"기준 시각: {exported_at}")
    engine.dispose()


if __name__ == "__main__":
    main()
