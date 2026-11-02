# %% [markdown]
# # AN-0003: 판매점 간 가격 비교와 할인 판별
#
# 기록: docs/analysis/0003-store-prices-and-discounts.md
# 데이터: data/external/chamgagyeok/price_20260925.csv (fetch_external.py),
#         data/*.parquet (export.py)
# 그래프: docs/assets/an0003-*.png
# 출처: 한국소비자원 참가격 (공공데이터포털 15083256)

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).parent
ASSETS = HERE.parent / "docs" / "assets"
plt.rcParams["font.family"] = "AppleGothic"
plt.rcParams["axes.unicode_minus"] = False
pd.set_option("display.width", 200)

D1, D2 = "2026-09-11", "2026-09-25"
CHAINS = {
    "롯데슈퍼": "롯데슈퍼",
    "GS더프레시": "GS더프레시",
    "이마트": "이마트",
    "현대백화점": "현대백화점",
    "신세계백화점": "신세계백화점",
    "(주)농협": "농협",
    "GS25": "편의점",
    "CU": "편의점",
    "세븐일레븐": "편의점",
}
STORE_CHAINS = ["롯데슈퍼", "GS더프레시", "이마트", "현대백화점", "신세계백화점", "농협"]


def save(fig, name):
    fig.tight_layout()
    fig.savefig(ASSETS / f"an0003-{name}.png", dpi=120)
    plt.close(fig)


def chain_of(store: str) -> str:
    for prefix, chain in CHAINS.items():
        if store.startswith(prefix):
            return chain
    return "기타"


# %% [markdown]
# ## 1. 데이터

# %%
raw = pd.read_csv(
    HERE / "data/external/chamgagyeok/price_20260925.csv", dtype=str, encoding="cp949"
)
raw["price"] = pd.to_numeric(raw["판매가격"])
raw["chain"] = raw["판매업소"].map(chain_of)
print(raw.shape)
print(
    raw.groupby("chain").agg(
        행=("price", "size"), 점포=("판매업소", "nunique"), 상품=("상품명", "nunique")
    )
)
print(pd.crosstab([raw.chain, raw.조사일], raw.세일여부.fillna("빈칸")))

# %% [markdown]
# ## 2. 체인 안에서 점포끼리 가격이 같은가


# %%
def mode(x):
    return x.mode().iloc[0]


g = raw.groupby(["chain", "상품명", "조사일"])
cell = g.agg(price=("price", mode), stores=("price", "size")).reset_index()
cell["at_mode"] = g["price"].agg(lambda x: (x == mode(x)).mean()).to_numpy()
cell["spread"] = g["price"].agg(lambda x: x.max() / x.min() - 1).to_numpy()
multi = cell[cell.stores >= 2]
uniform = multi.groupby("chain").apply(
    lambda d: pd.Series(
        {
            "상품·날짜": len(d),
            "최빈가 비율": np.average(d.at_mode, weights=d.stores),
            "전 점포 같은 가격": (d.at_mode == 1).mean(),
            "점포 간 최대 차이 중앙값": d.spread.median(),
        }
    ),
    include_groups=False,
)
print(uniform.round(3))

# 최빈가와 다른 점포는 어디인가: 롯데슈퍼
lotte = raw[raw.chain == "롯데슈퍼"].merge(
    cell[["chain", "상품명", "조사일", "price"]].rename(columns={"price": "chain_price"}),
    on=["chain", "상품명", "조사일"],
)
lotte["off"] = lotte.price != lotte.chain_price
by_store = lotte.groupby("판매업소").off.mean().sort_values(ascending=False)
print("롯데슈퍼 점포별 최빈가와 다른 비율:", by_store.describe().round(3).to_dict())
print(by_store.head(8).round(3).to_dict())
print(
    "최빈가와 다를 때 방향:",
    (lotte[lotte.off].price < lotte[lotte.off].chain_price).mean().round(3),
    "가 더 쌈",
)

# %% [markdown]
# ## 3. 체인끼리 가격 차이와 가장 싼 체인
#
# 체인 가격 = 그 체인 점포들의 최빈가. 편의점은 본사 가격 하나라 따로 둔다.

# %%
wide = cell[cell.chain.isin(STORE_CHAINS)].pivot_table(
    index=["상품명", "조사일"], columns="chain", values="price"
)
cover = wide.notna().sum(axis=1)
w4 = wide[cover >= 4]
gap = w4.max(axis=1) / w4.min(axis=1) - 1
print(f"4개 체인 이상에 있는 상품·날짜 {len(w4)}개, 최고/최저 차이:")
print(gap.describe(percentiles=[0.25, 0.5, 0.75, 0.9]).round(3).to_dict())

rel = w4.div(w4.median(axis=1), axis=0) - 1  # 체인별 중앙값 대비
cheapest = w4.eq(w4.min(axis=1), axis=0)
ties = cheapest.sum(axis=1)
summary3 = pd.DataFrame(
    {
        "중앙값 대비(중앙값)": rel.median(),
        "최저가 체인 비율": cheapest.div(ties, axis=0).sum() / len(w4),
        "상품·날짜": w4.notna().sum(),
    }
).sort_values("중앙값 대비(중앙값)")
print(summary3.round(3))

conv = cell[cell.chain == "편의점"].groupby(["상품명", "조사일"]).price.min()
both = pd.concat([conv.rename("편의점"), wide.median(axis=1).rename("점포 체인 중앙값")], axis=1)
both = both.dropna()
print(
    f"편의점 상품·날짜 {len(both)}개, 점포 체인 중앙값 대비:",
    (both["편의점"] / both["점포 체인 중앙값"] - 1).median().round(3),
)

same_as_median = rel.eq(0) | rel.isna()
at_median = rel.eq(0).sum() / rel.notna().sum()
print("체인 가격이 체인 중앙값과 같은 비율:", at_median.round(3).to_dict())
print("모든 체인이 같은 가격인 상품·날짜:", round(float(same_as_median.all(axis=1).mean()), 3))
print("가장 싼 체인이 둘 이상(동점)인 상품·날짜:", round(float((ties > 1).mean()), 3))

fig, ax = plt.subplots(figsize=(7, 3.6))
part = summary3.sort_values("최저가 체인 비율")
ax.barh(part.index, part["최저가 체인 비율"] * 100, color="#0369a1", height=0.6)
for y, v in enumerate(part["최저가 체인 비율"] * 100):
    ax.text(v + 0.5, y, f"{v:.0f}%", va="center", fontsize=9, color="#334155")
ax.set_xlabel("가장 싼 체인이었던 비율 (%, 동점은 나눠 셈)")
ax.set_title(f"체인별 최저가 비율 (4개 체인 이상에 있는 상품·날짜 {len(w4)}개)", fontsize=10)
ax.grid(axis="x", color="#e2e8f0")
ax.set_axisbelow(True)
save(fig, "chain-levels")

# %% [markdown]
# ## 4. 2주 사이 가격 변화 (체인 가격 기준)

# %%
two = cell.pivot_table(index=["chain", "상품명"], columns="조사일", values="price").dropna()
two["chg"] = two[D2] / two[D1] - 1
changes = two.groupby("chain").chg.agg(
    상품="size",
    바뀐_비율=lambda x: (x != 0).mean(),
    내림=lambda x: (x < 0).mean(),
    올림=lambda x: (x > 0).mean(),
    바뀐_폭_중앙값=lambda x: x[x != 0].abs().median(),
)
print(changes.round(3))

# %% [markdown]
# ## 5. 세일 표기: GS더프레시
#
# 09-11은 Y/N, 09-25는 Y와 빈칸만 있다. 09-25 빈칸은 세일 아님으로 본다 (가정).

# %%
gs_rows = raw[raw.chain == "GS더프레시"]
flag = gs_rows.groupby(["상품명", "조사일"]).세일여부.agg(
    y=lambda x: (x == "Y").mean(), n=lambda x: (x == "N").mean()
)
share = flag.y.xs(D1, level="조사일")
print(
    "09-11 상품별 Y 비율:",
    pd.cut(share, [-0.01, 0, 0.5, 0.99, 1]).value_counts().sort_index().to_dict(),
)
labeled_d1 = flag.xs(D1, level="조사일")
labeled_d1 = labeled_d1[(labeled_d1.y + labeled_d1.n) > 0.5]
label = pd.DataFrame(
    {
        D1: (labeled_d1.y > 0.5).reindex(two.loc["GS더프레시"].index),
        D2: (flag.y.xs(D2, level="조사일") > 0.5).reindex(two.loc["GS더프레시"].index),
    }
)
gs = two.loc["GS더프레시"].join(label.add_suffix("_sale"))
gs = gs.dropna(subset=[f"{D1}_sale", f"{D2}_sale"])
gs["상태"] = (
    gs[f"{D1}_sale"].map({True: "Y", False: "N"})
    + "→"
    + gs[f"{D2}_sale"].map({True: "Y", False: "N"})
)
print(
    gs.groupby("상태")
    .chg.agg(
        상품="size",
        가격_같음=lambda x: (x == 0).mean(),
        내림=lambda x: (x < 0).mean(),
        올림=lambda x: (x > 0).mean(),
        중앙값="median",
    )
    .round(3)
)

# %% [markdown]
# ## 6. 가격만으로 세일을 판별할 수 있나
#
# 정답: GS더프레시 상품별 세일 표기 (09-11 Y/N, 09-25 Y/빈칸).
# - 시점 비교: 같은 체인의 다른 날짜 가격보다 x% 이상 싸다
# - 체인 비교: 같은 날 다른 점포 체인 가격의 중앙값보다 x% 이상 싸다

# %%
others = (
    cell[cell.chain.isin(STORE_CHAINS) & (cell.chain != "GS더프레시")]
    .groupby(["상품명", "조사일"])
    .price.median()
)
rows = []
for day, other_day in ((D1, D2), (D2, D1)):
    d = gs[[day, other_day, f"{day}_sale"]].copy()
    d["oth"] = others.xs(day, level="조사일").reindex(d.index)
    d = d.dropna()
    truth = d[f"{day}_sale"].astype(bool)
    time_rel = d[day] / d[other_day] - 1
    cross_rel = d[day] / d.oth - 1
    for x in (0.03, 0.05, 0.10, 0.20):
        for name, pred in (
            ("시점 비교", time_rel <= -x),
            ("체인 비교", cross_rel <= -x),
            ("둘 다", (time_rel <= -x) & (cross_rel <= -x)),
            ("둘 중 하나", (time_rel <= -x) | (cross_rel <= -x)),
        ):
            tp = (pred & truth).sum()
            precision = tp / pred.sum() if pred.sum() else np.nan
            recall = tp / truth.sum()
            rows.append(
                {
                    "날짜": day,
                    "기준": f"{x:.0%}",
                    "방법": name,
                    "상품": len(d),
                    "세일": int(truth.sum()),
                    "예측": int(pred.sum()),
                    "정밀도": precision,
                    "재현율": recall,
                    "F1": 2 * precision * recall / (precision + recall) if tp else 0.0,
                }
            )
detect = pd.DataFrame(rows)
print(detect.round(3).to_string(index=False))

# 세일 상품의 가격은 다른 체인보다 얼마나 싼가
d = gs[[D1, f"{D1}_sale"]].join(others.xs(D1, level="조사일").rename("oth")).dropna()
d["rel"] = d[D1] / d.oth - 1
print(d.groupby(f"{D1}_sale").rel.describe().round(3))

fig, ax = plt.subplots(figsize=(7, 3.6))
for sale, color, lab in ((False, "#94a3b8", "세일 아님"), (True, "#f59e0b", "세일")):
    vals = d.loc[d[f"{D1}_sale"] == sale, "rel"].clip(-0.6, 0.6) * 100
    ax.hist(vals, bins=np.arange(-60, 62, 4), alpha=0.75, color=color, label=f"{lab} ({len(vals)})")
ax.axvline(0, color="#64748b", linewidth=1)
ax.set_xlabel("GS더프레시 가격, 다른 점포 체인 중앙값 대비 (%)")
ax.set_ylabel("상품 수")
ax.set_title("09-11 GS더프레시 세일 표기별 가격 위치", fontsize=10)
ax.legend(frameon=False)
save(fig, "gs-sale-vs-others")

# %% [markdown]
# ## 7. 가장 싼 체인은 세일 때문인가 (GS더프레시)

# %%
for day in (D1, D2):
    w = w4.xs(day, level="조사일")
    gs_cheapest = w.index[(w["GS더프레시"] == w.min(axis=1)) & w["GS더프레시"].notna()]
    sale = label[day].reindex(gs_cheapest)
    print(
        day,
        f"GS가 가장 싼 상품 {len(gs_cheapest)}개 중 세일 {int(sale.sum())}개,",
        f"표기 없음 {int(sale.isna().sum())}개",
    )

# 가장 싼 체인이 2주 사이 바뀌었나
c1 = w4.xs(D1, level="조사일")
c2 = w4.xs(D2, level="조사일")
common = c1.index.intersection(c2.index)
first = c1.loc[common].idxmin(axis=1)
second = c2.loc[common].idxmin(axis=1)
unique = (c1.loc[common].eq(c1.loc[common].min(axis=1), axis=0).sum(axis=1) == 1) & (
    c2.loc[common].eq(c2.loc[common].min(axis=1), axis=0).sum(axis=1) == 1
)
print(
    f"두 날짜 모두 4개 체인 이상, 최저가 체인이 하나인 상품 {int(unique.sum())}개 중",
    f"최저가 체인이 바뀐 상품 {int((first != second)[unique].sum())}개",
)
moved = pd.crosstab(first[unique & (first != second)], second[unique & (first != second)])
print(moved)

# %% [markdown]
# ## 8. 다나와 적용 (AN-0001과 같은 데이터)
#
# 판매처의 평소 가격 = 그 판매처의 1주 중앙값. 평소 가격보다 5% 이상 싸면 할인 중으로 본다.

# %%
snaps = pd.read_parquet(HERE / "data" / "snapshots.parquet")
sellers = pd.read_parquet(HERE / "data" / "sellers.parquet")
ok = snaps[(snaps.source == "danawa") & (snaps.status == "ok")]
sp = sellers.merge(ok[["snapshot_id", "source_product_id", "name"]], on="snapshot_id")
usual = sp.groupby(["source_product_id", "seller_code"]).price.transform("median")
seen = sp.groupby(["source_product_id", "seller_code"]).snapshot_id.transform("nunique")
sp["usual"] = usual
sp["seen"] = seen
sp["discount"] = sp.price <= sp.usual * 0.95
print("판매처·상품 조합:", sp.groupby(["source_product_id", "seller_code"]).ngroups)
print("할인 중 행 비율:", sp.discount.mean().round(3))

top = sp[sp["rank"] == 1]
print(
    f"1위 판매처가 할인 중인 시각 {top.discount.mean():.3f}",
    f"(1위 판매처를 본 수집이 24회 미만이면 평소 가격이 불안정: {(top.seen < 24).mean():.3f})",
)
# 할인을 뺀 최저가: 같은 수집에서 할인 중이 아닌 판매처 중 최저가
regular_min = sp[~sp.discount].groupby("snapshot_id").price.min()
lowest = sp.groupby("snapshot_id").price.min()
gap_d = (regular_min / lowest - 1).dropna()
print(
    "최저가와 할인 아닌 최저가 차이:",
    {
        "같음": round(float((gap_d == 0).mean()), 3),
        "5% 이상": round(float((gap_d >= 0.05).mean()), 3),
        "중앙값(차이 있을 때)": round(float(gap_d[gap_d > 0].median()), 3),
    },
)
gap_named = gap_d[gap_d > 0].to_frame("gap").join(ok.set_index("snapshot_id")["name"])
print(gap_named.groupby("name").gap.agg(["size", "median"]).sort_values("size").round(3))
per_product = top.groupby("name").discount.mean().sort_values(ascending=False)
print(per_product.round(3).head(8).to_string())

# 체인 안 가격 통일과 비교: G마켓과 옥션이 같이 있을 때 같은 가격인가
pair = sp[sp.seller_name.isin(["G마켓", "옥션"])].pivot_table(
    index="snapshot_id", columns="seller_name", values="price", aggfunc="min"
)
pair = pair.dropna()
print(f"G마켓·옥션 둘 다 있는 수집 {len(pair)}회, 같은 가격 {(pair.G마켓 == pair.옥션).mean():.3f}")
