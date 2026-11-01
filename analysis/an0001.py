# %% [markdown]
# # AN-0001: 다나와 1주 수집 데이터 들여다보기
#
# 기록: docs/analysis/0001-danawa-first-week.md
# 데이터: export.py로 받은 data/*.parquet (커밋하지 않음)
# 그래프: docs/assets/an0001-*.png

# %%
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).parent
ASSETS = HERE.parent / "docs" / "assets"
KST = "Asia/Seoul"

plt.rcParams["font.family"] = "AppleGothic"  # 개발 Mac의 한글 글꼴
plt.rcParams["axes.unicode_minus"] = False
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 32)

runs = pd.read_parquet(HERE / "data" / "runs.parquet")
snaps = pd.read_parquet(HERE / "data" / "snapshots.parquet")
sellers = pd.read_parquet(HERE / "data" / "sellers.parquet")
print("기준 시각:", (HERE / "data" / "exported_at.txt").read_text().strip())

runs = runs[runs.source == "danawa"].assign(kst=lambda f: f.started_at.dt.tz_convert(KST))
snaps = snaps[snaps.source == "danawa"].assign(kst=lambda f: f.collected_at.dt.tz_convert(KST))
sellers = sellers[sellers.snapshot_id.isin(snaps.snapshot_id)]


def save(fig, name):
    fig.tight_layout()
    fig.savefig(ASSETS / f"an0001-{name}.png", dpi=120)
    plt.close(fig)


# %% [markdown]
# ## 1. 수집 간격과 빠진 시간

# %%
sched = runs[runs.trigger == "schedule"].sort_values("kst")
gap = sched.kst.diff().dt.total_seconds() / 60
duration = (runs.finished_at - runs.started_at).dt.total_seconds()
print(f"실행 {len(runs)}회 (정기 {len(sched)}, 수동 {len(runs) - len(sched)})")
print(f"정기 실행 간격(분): 최소 {gap.min():.1f}, 중앙값 {gap.median():.1f}, 최대 {gap.max():.1f}")
print("시작 분:", sched.kst.dt.minute.value_counts().sort_index().to_dict())
print(f"실행 시간(초): 중앙값 {duration.median():.0f}, 최대 {duration.max():.0f}")
print("실행 상태:", runs.status.value_counts().to_dict())

# %% [markdown]
# ## 2. 실패 기록

# %%
failed = snaps[snaps.status != "ok"]
print("상품별 결과 상태:", snaps.status.value_counts().to_dict())
print(
    failed.assign(hour=failed.kst.dt.strftime("%m-%d %H시"))
    .groupby(["hour", "status", "error_message"])
    .size()
    .rename("건수")
    .to_string()
)

# %% [markdown]
# ## 3. 최저가 변동 빈도와 폭
#
# 최저가는 JSON-LD의 lowPrice. 정상 수집끼리 바로 앞 수집과 비교한다.

# %%
ok = snaps[snaps.status == "ok"].sort_values(["source_product_id", "kst"]).copy()
top = sellers[sellers["rank"] == 1][["snapshot_id", "seller_name", "price"]].rename(
    columns={"seller_name": "top_seller", "price": "top_price"}
)
ok = ok.merge(top, on="snapshot_id", how="left")
by_product = ok.groupby("source_product_id")
ok["prev_price"] = by_product.lowest_price.shift()
ok["prev_top"] = by_product.top_seller.shift()
ok["change"] = ok.lowest_price - ok.prev_price
ok["pct"] = ok.change / ok.prev_price * 100
pairs = ok[ok.prev_price.notna()]
changes = pairs[pairs.change != 0].copy()

print(
    f"연속 수집 쌍 {len(pairs)}개 중 최저가가 바뀐 쌍 {len(changes)}개",
    f"({len(changes) / len(pairs):.1%})",
)
print("바뀐 금액(원) 분위수:", changes.change.abs().quantile([0.25, 0.5, 0.75, 0.9]).to_dict())

per_product = (
    pairs.groupby("source_product_id")
    .apply(
        lambda g: pd.Series(
            {
                "이름": g["name"].iloc[0][:24],
                "변동률%": (g.change != 0).mean() * 100,
                "5%이상": (g.pct.abs() >= 5).sum(),
                "판매처수": g.offer_count.median(),
                "범위%": (g.lowest_price.max() - g.lowest_price.min())
                / g.lowest_price.median()
                * 100,
            }
        ),
        include_groups=False,
    )
    .sort_values("변동률%", ascending=False)
)
print(per_product.round(1).to_string())

changes["크기"] = pd.cut(
    changes.pct.abs(),
    [0, 0.1, 1, 5, 20, np.inf],
    labels=["<0.1%", "0.1~1%", "1~5%", "5~20%", "20%~"],
)
changes["1위교체"] = changes.top_seller != changes.prev_top
print(pd.crosstab(changes["크기"], changes["1위교체"], margins=True).to_string())

fig, ax = plt.subplots(figsize=(7, 3.6))
pd.crosstab(changes["크기"], changes["1위교체"]).rename(
    columns={False: "1위 판매처 그대로", True: "1위 판매처 바뀜"}
).plot.bar(ax=ax, rot=0, color=["#0369a1", "#f59e0b"])
ax.set_xlabel("직전 수집 대비 최저가 변화 폭")
ax.set_ylabel("건수")
ax.set_title("최저가가 바뀐 426번의 변화 폭")
save(fig, "change-size")

# %% [markdown]
# ## 4. 판매처가 많으면 가격이 자주 움직이나 (상품 선정 때의 가정)

# %%
rho = per_product[["판매처수", "변동률%"]].corr(method="spearman").iloc[0, 1]
print(f"판매처 수와 변동률의 스피어먼 상관: {rho:.2f} (상품 {len(per_product)}개)")

fig, ax = plt.subplots(figsize=(6, 3.8))
ax.scatter(per_product["판매처수"], per_product["변동률%"], color="#0369a1")
ax.set_xlabel("판매처 수 (중앙값)")
ax.set_ylabel("시간당 최저가 변동률 (%)")
ax.set_title(f"판매처 수와 변동률 (상품 20개, 스피어먼 {rho:.2f})")
save(fig, "offers-vs-rate")

# %% [markdown]
# ## 5. 큰 변화(5% 이상)는 언제 일어나나

# %%
big = changes[changes.pct.abs() >= 5]
drops = big[big.pct < 0].kst.dt.hour.value_counts().reindex(range(24), fill_value=0)
rises = big[big.pct > 0].kst.dt.hour.value_counts().reindex(range(24), fill_value=0)
print("큰 하락 시각:", drops[drops > 0].to_dict())
print("큰 상승 시각:", rises[rises > 0].to_dict())

# 이전 1위 판매처가 다음 수집에도 목록에 있었나
listed = sellers.set_index(["snapshot_id", "seller_name"]).index
big_listed = [
    (sid, seller) in listed for sid, seller in zip(big.snapshot_id, big.prev_top, strict=True)
]
print(f"큰 변화 {len(big)}건 중 이전 1위 판매처가 목록에 남아 있던 건: {sum(big_listed)}")

fig, ax = plt.subplots(figsize=(7.5, 3.4))
ax.bar(np.arange(24) - 0.2, drops.values, width=0.4, label="5% 이상 하락", color="#0369a1")
ax.bar(np.arange(24) + 0.2, rises.values, width=0.4, label="5% 이상 상승", color="#f59e0b")
ax.set_xticks(range(0, 24, 2))
ax.set_xlabel("시각 (한국 시간)")
ax.set_ylabel("건수")
ax.set_title("최저가가 5% 이상 바뀐 시각")
ax.legend()
save(fig, "big-change-hours")

# %% [markdown]
# ## 6. 사례: 키오시아 급등, 버즈 시리즈의 하루 주기

# %%
cases = {
    "74056484": "키오시아 EXCERIA PLUS G4 2TB",
    "106702589": "갤럭시 버즈4 프로",
    "96987275": "갤럭시 버즈3 FE",
}
fig, axes = plt.subplots(len(cases), 1, figsize=(8, 7), sharex=True)
for ax, (pcode, label) in zip(axes, cases.items(), strict=True):
    series = ok[ok.source_product_id == pcode].set_index("kst").lowest_price
    ax.step(series.index, series.values / 10000, where="post", color="#0369a1")
    ax.set_title(label, fontsize=10)
    ax.set_ylabel("만원")
axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%m-%d", tz=KST))
fig.suptitle("최저가 추이 (매시 수집)")
save(fig, "cases")

kioxia = ok[ok.source_product_id == "74056484"]
print(kioxia.set_index("kst").lowest_price.resample("D").agg(["min", "median", "max"]).to_string())
first_two = sellers.merge(snaps[["snapshot_id", "source_product_id", "kst"]], on="snapshot_id")
first_two = first_two[(first_two.source_product_id == "74056484") & (first_two["rank"] <= 3)]
print(
    first_two[first_two.kst < "2026-10-24 17:00+09:00"][
        ["kst", "rank", "seller_name", "price"]
    ].to_string()
)

# %% [markdown]
# ## 7. 1위 판매처 교체와 분포

# %%
switch = pairs.top_seller != pairs.prev_top
rate = pairs.assign(sw=switch).groupby("source_product_id").sw.mean() * 100
print(
    f"1위 판매처가 바뀐 비율: 전체 {switch.mean():.1%},",
    f"상품별 중앙값 {rate.median():.1f}% ({rate.min():.1f}~{rate.max():.1f}%)",
)
print("1위 판매처 비중:", ok.top_seller.value_counts(normalize=True).head(6).round(3).to_dict())

# %% [markdown]
# ## 8. 데이터 품질: JSON-LD 최저가와 목록 1위 가격, 배송비

# %%
diff = ok.lowest_price - ok.top_price
print(
    f"최저가와 1위 가격: 같음 {(diff == 0).mean():.1%}, 최저가가 쌈 {(diff < 0).mean():.1%}, "
    f"비쌈 {(diff > 0).mean():.1%}"
)
fee = sellers.delivery_fee
print(
    f"배송비 1만 원 이상: {(fee >= 10000).sum()}행 / {len(fee)}행. 많은 값:",
    fee[fee >= 10000].value_counts().head(5).to_dict(),
)
