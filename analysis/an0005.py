"""AN-0005: 포털 가격 신호(backend/src/flowdeck/signals.py)를 연습 쇼핑몰 정답과
다나와 데이터에 돌려 본다.

uv run python export.py   # 다나와 데이터 (data/에 저장, 커밋하지 않음)
uv run python an0005.py
"""

# %%
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from cpd import step_rule
from mock_shop.catalog import PRODUCTS, SELLERS
from mock_shop.pricing import KST, offer_at

from flowdeck.signals import (
    USUAL_WINDOW,
    SellerOffer,
    price_changes,
    seller_key,
    seller_positions,
)

HERE = Path(__file__).parent
DATA = HERE / "data"
pd.set_option("display.width", 200)


def scores(truth: pd.Series, pred: pd.Series) -> dict[str, float]:
    tp = int((truth & pred).sum())
    fp = int((~truth & pred).sum())
    fn = int((truth & ~pred).sum())
    precision = tp / (tp + fp) if tp + fp else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * precision * recall / (precision + recall) if tp else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def positions_over_time(observations: pd.DataFrame) -> pd.DataFrame:
    """observations: product, at, key, price, in_stock, cash (한 행이 한 수집의 판매처 하나).
    수집마다 signals.seller_positions를 그대로 부른다. 평소 가격은 그 전 7일의 재고 있는 가격."""
    rows = []
    for _, frame in observations.groupby("product", sort=False):
        past: dict[str, deque[tuple[datetime, int]]] = defaultdict(deque)
        for at, snap in frame.groupby("at", sort=True):
            current = [
                SellerOffer(key=r.key, price=int(r.price), in_stock=r.in_stock, cash=r.cash)
                for r in snap.itertuples()
            ]
            for values in past.values():
                while values and values[0][0] < at - USUAL_WINDOW:
                    values.popleft()
            history = {key: [p for _, p in values] for key, values in past.items()}
            positions = seller_positions(current, history)
            for r in snap.itertuples():
                pos = positions[r.key]
                rows.append(
                    {
                        "index": r.Index,
                        "vs_others_pct": pos.vs_others_pct if pos else None,
                        "others_count": pos.others_count if pos else None,
                        "vs_usual_pct": pos.vs_usual_pct if pos else None,
                        "usual_points": pos.usual_points if pos else None,
                        "cheaper_than_others": bool(pos and pos.cheaper_than_others),
                        "cheaper_than_usual": bool(pos and pos.cheaper_than_usual),
                    }
                )
            for o in current:
                if o.in_stock:
                    past[o.key].append((at, o.price))
    return observations.join(pd.DataFrame(rows).set_index("index"))


# %% [markdown]
# ## 1. 연습 쇼핑몰: 정답(주말 할인, 급락 특가)과 맞춰 보기
#
# AN-0002와 같은 4주(2026-10-26~11-22)를 매시 만든다. 평소 가격에 7일이 필요해서 평가는 11-02부터.

# %%
START = datetime(2026, 10, 26, tzinfo=KST)
END = datetime(2026, 11, 23, tzinfo=KST)
EVAL_FROM = START + USUAL_WINDOW

records = []
at = START
while at < END:
    for product in PRODUCTS:
        for code in product.base_prices:
            o = offer_at(product, SELLERS[code], at)
            records.append(
                {
                    "product": product.id,
                    "at": at,
                    "key": seller_key(code, o.seller.name, False),
                    "seller": code,
                    "price": o.price,
                    "in_stock": o.in_stock,
                    "cash": False,
                    "weekend_sale": "weekend_sale" in o.rules,
                    "flash_sale": "flash_sale" in o.rules,
                }
            )
    at += timedelta(hours=1)
mock = positions_over_time(pd.DataFrame(records))
ev = mock[(mock["at"] >= EVAL_FROM) & mock.in_stock].copy()
ev["sale"] = ev.weekend_sale | ev.flash_sale
ev["either"] = ev.cheaper_than_others | ev.cheaper_than_usual
print(
    f"평가 대상: 재고 있는 판매처-시각 {len(ev):,}개,"
    f" 할인 {ev.sale.sum():,}개 ({ev.sale.mean():.1%})"
)
print(
    f"다른 판매처 비교를 낸 비율 {ev.vs_others_pct.notna().mean():.1%},"
    f" 평소 가격을 낸 비율 {ev.vs_usual_pct.notna().mean():.1%}"
)

table = pd.DataFrame(
    {
        name: scores(ev.sale, ev[col])
        for name, col in [
            ("다른 판매처보다 쌈", "cheaper_than_others"),
            ("평소보다 쌈", "cheaper_than_usual"),
            ("둘 중 하나", "either"),
        ]
    }
).T
print(table.round(3))

# 규칙별 재현율
for rule in ("weekend_sale", "flash_sale"):
    part = ev[ev[rule]]
    print(
        f"{rule}: {len(part):,}개, 다른 판매처 {part.cheaper_than_others.mean():.3f},"
        f" 평소 {part.cheaper_than_usual.mean():.3f}, 둘 중 하나 {part.either.mean():.3f}"
    )

# %%
# 놓친 주말 할인: 다른 판매처 대비 위치가 어디였나
miss = ev[ev.weekend_sale & ~ev.cheaper_than_others]
print("놓친 주말 할인의 다른 판매처 대비 % 분포")
print(miss.vs_others_pct.describe().round(2))
print(miss.groupby("product").size())

# 오탐: 할인 아닌데 신호가 난 경우는 어느 판매처
fp = ev[~ev.sale & ev.either]
print("오탐", len(fp))
print(fp.groupby(["product", "seller"]).size().sort_values(ascending=False).head(10))
print(fp[["vs_others_pct", "vs_usual_pct"]].describe().round(2))

# %% [markdown]
# ## 2. 최저가 변화: 백엔드 구현이 analysis/cpd.py의 step_rule과 같은 위치를 내는가

# %%
mismatch = 0
total = 0
for product in PRODUCTS:
    lowest = (
        mock[(mock["product"] == product.id) & mock.in_stock].groupby("at").price.min().sort_index()
    )
    points = [(t, int(p)) for t, p in lowest.items()]
    ours = [points.index((c.at, c.after)) for c in price_changes(points)]
    ref = step_rule(np.array([p for _, p in points]), min_pct=5, persist=2)
    total += len(ref)
    mismatch += ours != ref
print(
    f"연습 쇼핑몰 상품 {len(PRODUCTS)}개, step_rule 변화점 {total}개, 위치가 다른 상품 {mismatch}개"
)

# %% [markdown]
# ## 3. 다나와: 정답 없이 신호가 얼마나 자주 나는지

# %%
snaps = pd.read_parquet(DATA / "snapshots.parquet")
sellers = pd.read_parquet(DATA / "sellers.parquet")
print("기준 시각:", (DATA / "exported_at.txt").read_text().strip())
dn = sellers.merge(
    snaps[(snaps.source == "danawa") & (snaps.status == "ok")][
        ["snapshot_id", "collected_at", "product_id"]
    ],
    on="snapshot_id",
)
dn["cash"] = dn.price_label.eq("현금")
dn["key"] = [
    seller_key(c, n, cash)
    for c, n, cash in zip(dn.seller_code, dn.seller_name, dn.cash, strict=True)
]
dn = dn.rename(columns={"product_id": "product", "collected_at": "at"})
# 같은 수집에 같은 키가 둘이면(드묾) 순위가 높은 쪽만
dn = dn.sort_values("rank").drop_duplicates(["snapshot_id", "key"])
dn = positions_over_time(dn[["product", "at", "key", "rank", "price", "in_stock", "cash"]])
print(f"다나와 판매처-수집 {len(dn):,}개, 기간 {dn['at'].min()} ~ {dn['at'].max()}")

d7 = dn[dn["at"] >= dn["at"].min() + USUAL_WINDOW]
d7 = d7[d7.in_stock]
print(
    f"7일 뒤부터 {len(d7):,}개: 다른 판매처 비교 가능 {d7.vs_others_pct.notna().mean():.1%},"
    f" 평소 가격 가능 {d7.vs_usual_pct.notna().mean():.1%}"
)
print(
    f"다른 판매처보다 쌈 {d7.cheaper_than_others.mean():.1%},"
    f" 평소보다 쌈 {d7.cheaper_than_usual.mean():.1%},"
    f" 둘 다 {(d7.cheaper_than_others & d7.cheaper_than_usual).mean():.1%}"
)
first = d7[d7["rank"] == 1]
print(
    f"1위만 {len(first):,}개: 다른 판매처보다 쌈 {first.cheaper_than_others.mean():.1%},"
    f" 평소보다 쌈 {first.cheaper_than_usual.mean():.1%}"
)
print("현금가 판매처의 '다른 판매처보다 쌈' 비율", round(d7[d7.cash].cheaper_than_others.mean(), 3))
print("현금가 아닌 판매처", round(d7[~d7.cash].cheaper_than_others.mean(), 3))
print("상품별 '평소보다 쌈' 비율")
print(d7.groupby("product").cheaper_than_usual.mean().sort_values(ascending=False).round(3).head(8))

# %%
# 최저가 변화: 최근 7일, 상품당 건수
dsn = snaps[(snaps.source == "danawa") & (snaps.status == "ok") & snaps.lowest_price.notna()]
last7 = dsn[dsn.collected_at >= dsn.collected_at.max() - timedelta(days=7)]
counts = {
    pid: len(
        price_changes([(t, int(p)) for t, p in zip(g.collected_at, g.lowest_price, strict=True)])
    )
    for pid, g in last7.sort_values("collected_at").groupby("product_id")
}
print(
    f"최근 7일 최저가 변화 {sum(counts.values())}건, 상품 {len(counts)}개,"
    f" 상품당 중앙값 {np.median(list(counts.values()))}"
)
