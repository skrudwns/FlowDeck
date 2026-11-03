# %% [markdown]
# # AN-0004: 참가격 2년 이력으로 본 세일 주기와 할인 판별, 공식 통계·선행 연구 대조
#
# 기록: docs/analysis/0004-price-history-and-benchmarks.md
# 데이터: 참가격 Open API 응답 캐시 data/external/chamgagyeok/api/ (chamgagyeok_api.py),
#         KOSIS data/external/kosis/, Cavallo(2017) data/external/cavallo2017/
# 그래프: docs/assets/an0004-*.png
# 출처: 한국소비자원 참가격(공공데이터포털 15158701), 통계청 소비자물가지수(KOSIS DT_1J22001),
#       Cavallo(2017, AER) 복제 자료(openICPSR E113131V1, CC BY 4.0)

# %%
import json
from datetime import date, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from chamgagyeok_api import fetch, rows

HERE = Path(__file__).parent
EXTERNAL = HERE / "data" / "external"
ASSETS = HERE.parent / "docs" / "assets"
plt.rcParams["font.family"] = "AppleGothic"
plt.rcParams["axes.unicode_minus"] = False
pd.set_option("display.width", 200)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(ASSETS / f"an0004-{name}.png", dpi=120)
    plt.close(fig)


# %% [markdown]
# ## 1. 데이터
#
# 조사일: 2024-11 ~ 2026-10의 금요일마다 꽃소금(goodId 35)을 조회해 결과가 있는 날을 조사일로 봤다.
# 점포: 체인마다 2024-11-08, 2025-09-19에 모두 자료가 있는 점포를 2곳(편의점은 본사 1곳) 골랐다.
# 같은 체인 안에서는 가격이 거의 같아서(AN-0003) 체인마다 1~2곳이면 체인 가격을 볼 수 있다.

# %%
STORES = {
    "62": "CU",
    "150": "GS25",
    "115": "세븐일레븐",
    "1787": "GS더프레시",
    "1677": "GS더프레시",
    "103": "농협",
    "33": "농협",
    "1520": "롯데슈퍼",
    "2129": "롯데슈퍼",
    "682": "신세계백화점",
    "151": "신세계백화점",
    "707": "이마트",
    "156": "이마트",
    "1948": "현대백화점",
    "55": "현대백화점",
}

day = date(2026, 10, 30)
DATES = []
while day >= date(2024, 11, 1):
    key = day.strftime("%Y%m%d")
    if rows(fetch("getProductPriceInfoSvc", goodInspectDay=key, goodId="35")):
        DATES.append(key)
    day -= timedelta(days=7)
DATES.sort()

records = []
for d in DATES:
    for e in STORES:
        records += rows(fetch("getProductPriceInfoSvc", goodInspectDay=d, entpId=e))
hist = pd.DataFrame(records)
hist["date"] = pd.to_datetime(hist.goodInspectDay)
hist["price"] = hist.goodPrice.astype(float)
hist["chain"] = hist.entpId.map(STORES)
hist["sale"] = hist.goodDcYn.map({"Y": True, "N": False})  # 빈칸은 모름(NaN)

stores = {s["entpId"]: s["entpName"] for s in rows(fetch("getStoreInfoSvc.do"))}
products = pd.DataFrame(rows(fetch("getProductInfoSvc.do"))).set_index("goodId")
classes = pd.DataFrame(rows(fetch("getStandardInfoSvc.do", classCode="AL"))).set_index("code")
hist["name"] = hist.goodId.map(products.goodName)
hist["cls"] = hist.goodId.map(products.goodSmlclsCode).map(classes.codeName)

print(f"조사일 {len(DATES)}개: {DATES[0]} ~ {DATES[-1]}")
gaps = pd.Series(pd.to_datetime(DATES)).diff().dt.days.value_counts().sort_index()
print("조사일 간격(일):", gaps.to_dict())
print(f"{len(hist):,}행, 상품 {hist.goodId.nunique()}개")
print(
    hist.groupby("chain").agg(
        점포=("entpId", "nunique"), 상품=("goodId", "nunique"), 행=("price", "size")
    )
)
print("세일 표기:")
print(
    hist.assign(표기=hist.goodDcYn.replace("", "빈칸").fillna("빈칸"))
    .groupby(["chain", "표기"])
    .size()
    .unstack(fill_value=0)
)

# 체인 가격: 같은 체인 점포 가격의 중앙값 (점포 2곳이면 평균과 같다)
chain_price = hist.groupby(["chain", "goodId", "date"]).price.median().unstack("chain")
STORE_CHAINS = ["롯데슈퍼", "GS더프레시", "이마트", "현대백화점", "신세계백화점", "농협"]


# %% [markdown]
# ## 2. 세일 표기가 남아 있는 곳과 세일 주기 (GS더프레시)
#
# 세일 표기(goodDcYn)는 체인과 조사일마다 남는 정도가 다르다. N이 같이 남아 있어야
# "세일 아님"을 알 수 있어서, 점포·조사일별로 Y나 N이 있는 비율을 본다.

# %%
flag = hist.assign(labeled=hist.sale.notna(), on_sale=hist.sale.eq(True))
by_store_date = flag.groupby(["chain", "entpId", "date"]).agg(
    상품=("goodId", "size"), 표기=("labeled", "mean"), 세일=("on_sale", "mean")
)
print(
    by_store_date.groupby("chain")
    .agg(
        조사일=("상품", "size"),
        표기_중앙값=("표기", "median"),
        표기_80이상_조사일=("표기", lambda s: int((s >= 0.8).sum())),
        세일_중앙값=("세일", "median"),
    )
    .round(3)
)

# 표기가 80% 이상 남은 점포·조사일만 정답으로 쓴다. 그 안에서도 빈칸 행은 뺀다
labeled_days = by_store_date[by_store_date.표기 >= 0.8].index
lab = flag.set_index(["chain", "entpId", "date"]).loc[labeled_days].reset_index()
lab = lab[lab.labeled]
print(
    "정답으로 쓸 행:",
    len(lab),
    lab.groupby("chain").size().to_dict(),
    "조사일:",
    lab.groupby("chain").date.nunique().to_dict(),
)

# 세일 기간: 할인 시작일~종료일. 같은 점포·상품·기간은 한 번만 센다
periods = (
    hist[hist.sale.eq(True) & hist.goodDcStartDay.notna() & (hist.goodDcStartDay != "")]
    .drop_duplicates(["entpId", "goodId", "goodDcStartDay", "goodDcEndDay"])
    .assign(
        start=lambda d: pd.to_datetime(d.goodDcStartDay, errors="coerce"),
        end=lambda d: pd.to_datetime(d.goodDcEndDay, errors="coerce"),
    )
    .dropna(subset=["start", "end"])
)
periods["days"] = (periods.end - periods.start).dt.days + 1
print("세일 기간(일), 체인별:")
print(periods.groupby("chain").days.describe(percentiles=[0.1, 0.5, 0.9]).round(1))

gs = lab[lab.chain == "GS더프레시"]
gs_share = gs.groupby(["entpId", "goodId"]).on_sale.agg(["mean", "size"])
gs_share = gs_share[gs_share["size"] >= 10]
print(
    "GS더프레시 상품별 세일 조사일 비율 (표기 조사일 10개 이상):",
    gs_share["mean"].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).round(3).to_dict(),
)
print(
    "한 번도 세일 아님:",
    round((gs_share["mean"] == 0).mean(), 3),
    "절반 넘게 세일:",
    round((gs_share["mean"] > 0.5).mean(), 3),
)

# 세일 사이 간격: 같은 점포·상품의 다음 세일 시작까지
p = periods[periods.chain == "GS더프레시"].sort_values(["entpId", "goodId", "start"])
p["next_start"] = p.groupby(["entpId", "goodId"]).start.shift(-1)
p["gap"] = (p.next_start - p.end).dt.days
print(
    "GS더프레시 세일 끝 ~ 다음 세일 시작(일):",
    p.gap.describe(percentiles=[0.1, 0.5, 0.9]).round(1).to_dict(),
)
print("겹치거나 바로 이어지는 비율(간격 1일 이하):", round((p.gap.dropna() <= 1).mean(), 3))

# 세일 가격은 평소 가격보다 얼마나 싼가: 같은 점포·상품의 세일 아닌 조사일 가격 중앙값 대비
regular = gs[~gs.on_sale].groupby(["entpId", "goodId"]).price.median().rename("regular")
depth = gs[gs.on_sale].join(regular, on=["entpId", "goodId"]).dropna(subset=["regular"])
depth["rel"] = depth.price / depth.regular - 1
print(
    "GS더프레시 세일 가격, 평소 가격 대비:",
    depth.rel.describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).round(3).to_dict(),
)
print("평소 가격과 같거나 비싼 세일:", round((depth.rel >= 0).mean(), 3))

fig, ax = plt.subplots(figsize=(7, 3.4))
ax.hist(gs_share["mean"] * 100, bins=np.arange(0, 102.5, 5), color="#f59e0b")
ax.set_xlabel("표기가 있는 조사일 중 세일이었던 비율 (%)")
ax.set_ylabel("점포·상품 수")
ax.set_title("GS더프레시 2년, 점포·상품별 세일 비율", fontsize=10)
save(fig, "gs-sale-share")


# %% [markdown]
# ## 3. 가격만으로 세일을 판별: 이력이 길면 나아지나
#
# 정답: 표기가 남은 조사일의 Y/N (빈칸은 뺀다. AN-0003은 09-25 빈칸을 N으로 가정했다)
# - 직전 비교: 같은 점포의 직전 조사일 가격보다 x% 이상 싸다 (AN-0003의 시점 비교)
# - 평소 비교: 같은 점포의 직전 6개 조사일 가격 중앙값보다 x% 이상 싸다 (3개 이상 있을 때)
# - 체인 비교: 같은 날 다른 점포 체인 가격의 중앙값보다 x% 이상 싸다 (AN-0003과 같음)

# %%
h = hist.sort_values("date")
grp = h.groupby(["entpId", "goodId"]).price
h["prev"] = grp.shift()
h["usual"] = grp.transform(lambda s: s.shift().rolling(6, min_periods=3).median())
others_by_chain = {
    c: chain_price.drop(columns=[c]).reindex(columns=[x for x in STORE_CHAINS if x != c])
    for c in STORE_CHAINS
}
h["others"] = np.nan
for c, o in others_by_chain.items():
    idx = h.chain == c
    keys = pd.MultiIndex.from_arrays([h.loc[idx, "goodId"], h.loc[idx, "date"]])
    h.loc[idx, "others"] = o.median(axis=1).reindex(keys).to_numpy()
    h.loc[idx, "n_others"] = o.notna().sum(axis=1).reindex(keys).to_numpy()
h.loc[h.n_others < 3, "others"] = np.nan

ev = h.merge(lab[["entpId", "goodId", "date", "on_sale"]], on=["entpId", "goodId", "date"])
ev = ev.dropna(subset=["prev", "usual", "others"])
print(
    "평가 행:",
    len(ev),
    ev.groupby("chain").size().to_dict(),
    "세일 비율:",
    round(ev.on_sale.mean(), 3),
)

out = []
for chain, e in [("GS더프레시", ev[ev.chain == "GS더프레시"]), ("전체", ev)]:
    truth = e.on_sale
    rel = {
        "직전 비교": e.price / e.prev - 1,
        "평소 비교": e.price / e.usual - 1,
        "체인 비교": e.price / e.others - 1,
    }
    for x in (0.03, 0.05, 0.10, 0.20):
        preds = {k: v <= -x for k, v in rel.items()}
        preds["평소+체인 둘 중 하나"] = preds["평소 비교"] | preds["체인 비교"]
        preds["평소+체인 둘 다"] = preds["평소 비교"] & preds["체인 비교"]
        for name, pred in preds.items():
            tp = (pred & truth).sum()
            precision = tp / pred.sum() if pred.sum() else np.nan
            recall = tp / truth.sum()
            out.append(
                {
                    "대상": chain,
                    "기준": f"{x:.0%}",
                    "방법": name,
                    "행": len(e),
                    "세일": int(truth.sum()),
                    "정밀도": precision,
                    "재현율": recall,
                    "F1": 2 * precision * recall / (precision + recall) if tp else 0.0,
                }
            )
detect = pd.DataFrame(out)
print(detect.round(3).to_string(index=False))

# 평소 비교가 놓치는 세일: 평소 가격 자체가 세일 가격인 경우(세일이 길거나 잦음)
gse = ev[(ev.chain == "GS더프레시") & ev.on_sale]
missed = gse[gse.price / gse.usual - 1 > -0.05]
prev_sale = lab.sort_values("date").assign(
    prev_on_sale=lambda d: d.groupby(["entpId", "goodId"]).on_sale.shift()
)[["entpId", "goodId", "date", "prev_on_sale"]]
missed = missed.merge(prev_sale, on=["entpId", "goodId", "date"], how="left")
print(
    "GS 세일 중 평소 비교(5%)로 못 찾은 비율:",
    round(len(missed) / len(gse), 3),
    "그중 직전 조사일도 세일:",
    round(missed.prev_on_sale.eq(True).mean(), 3),
)


# 가격만으로 찾을 수 있는 한계: 2년 전체의 세일 아닌 가격 중앙값(사후에야 아는 값)과 비교해도
# 세일 가격이 5% 이상 싸지 않은 세일은 가격으로는 찾을 수 없다
ceiling = depth[depth.chain == "GS더프레시"]
print(
    "GS 세일 중 사후 평소 가격보다 5% 이상 싼 비율 (가격만 쓰는 방법의 재현율 상한):",
    round((ceiling.rel <= -0.05).mean(), 3),
)

gs5 = detect[(detect.대상 == "GS더프레시") & (detect.기준 == "5%")].set_index("방법")
fig, ax = plt.subplots(figsize=(7, 3.2))
y = np.arange(len(gs5))
ax.barh(y + 0.2, gs5.정밀도, height=0.4, color="#94a3b8", label="정밀도")
ax.barh(y - 0.2, gs5.재현율, height=0.4, color="#f59e0b", label="재현율")
ax.axvline(
    (ceiling.rel <= -0.05).mean(), color="#64748b", linestyle="--", linewidth=1,
    label="재현율 상한",
)  # fmt: skip
ax.set_yticks(y, gs5.index)
ax.set_xlim(0, 1)
ax.invert_yaxis()
ax.set_title("GS더프레시 세일 판별 (5% 기준, 2년 33개 조사일)", fontsize=10)
ax.legend(frameon=False, loc="lower right", fontsize=8)
save(fig, "gs-detection")


# %% [markdown]
# ## 4. 통계청 소비자물가 품목 지수와 대조
#
# 참가격 상품 소분류 이름이 통계청 품목 이름과 같거나 명백히 같은 품목이면 짝짓는다.
# 참가격 품목 지수: 점포·상품마다 월 평균 가격을 내고, 두 달 모두 있는 점포·상품의 가격 비율을
# 기하평균(Jevons)해 이어 붙인다. 2024-11 = 100. 통계청 지수도 2024-11 = 100으로 바꿔 비교한다.
# 통계청은 가중치와 조사 방법(전국 조사, 대표 규격)이 달라서 수준이 아니라 방향과 크기를 본다.

# %%
kosis = pd.DataFrame(json.loads((EXTERNAL / "kosis/DT_1J22001_202410_202610.json").read_text()))
kosis["month"] = pd.PeriodIndex(kosis.PRD_DE, freq="M")
cpi = kosis.pivot_table(index="month", columns="C2_NM", values="DT", aggfunc="first").astype(float)
cpi = cpi.loc["2024-11":"2026-10"]

ALIASES = {
    "계란": "달걀", "쌀(백미)": "쌀", "커피믹스": "커피", "컵라면": "라면", "포기김치": "김치",
    "콜라": "탄산음료", "사이다": "탄산음료", "세탁세제(액체형)": "세탁세제",
    "세탁세제(가루형)": "세탁세제", "주방세제": "부엌용세제", "대파": "파", "쪽파": "파",
    "햄": "햄및베이컨", "베이컨": "햄및베이컨", "빙과류": "아이스크림", "참치캔": "수산물통조림",
}  # fmt: skip
hist["cpi_item"] = hist.cls.map(lambda n: ALIASES.get(n, n))
hist.loc[~hist.cpi_item.isin(cpi.columns), "cpi_item"] = np.nan
monthly = (
    hist.dropna(subset=["cpi_item"])
    .assign(month=lambda d: d.date.dt.to_period("M"))
    .groupby(["cpi_item", "entpId", "goodId", "month"])
    .price.mean()
)


def jevons(s: pd.Series) -> pd.Series:
    wide = s.unstack("month")
    months = wide.columns.sort_values()
    level = [100.0]
    for a, b in zip(months[:-1], months[1:], strict=False):
        both = wide[[a, b]].dropna()
        level.append(
            level[-1] * float(np.exp(np.log(both[b] / both[a]).mean())) if len(both) else np.nan
        )
    return pd.Series(level, index=months)


cg = monthly.groupby(level="cpi_item").apply(lambda s: jevons(s.droplevel("cpi_item"))).unstack(0)
pairs = monthly.groupby(level="cpi_item").apply(
    lambda s: s.droplevel("cpi_item").index.droplevel("month").nunique()
)
cg = cg.loc["2024-11":"2026-10"]
items = [c for c in cg.columns if c in cpi.columns and pairs[c] >= 3 and cg[c].notna().all()]
cpi_b = cpi[items] / cpi[items].iloc[0] * 100
cg_b = cg[items] / cg[items].iloc[0] * 100
print(f"짝지은 품목 {len(items)}개 (점포·상품 3개 이상, 24개월 모두 있음)")

total = pd.DataFrame(
    {
        "참가격": cg_b.iloc[-1] / 100 - 1,
        "통계청": cpi_b.iloc[-1] / 100 - 1,
        "점포·상품": pairs[items],
    }
)
print(
    "2년 누적 변화, 품목 간 상관:",
    round(total.참가격.corr(total.통계청), 3),
    "순위 상관:",
    round(total.참가격.corr(total.통계청, method="spearman"), 3),
)
print(
    "방향(오름/내림)이 같은 품목 비율:",
    round((np.sign(total.참가격) == np.sign(total.통계청)).mean(), 3),
)
total["차이"] = total.참가격 - total.통계청
# 신선식품(상품분류 0301)과 나머지(가공식품, 생활용품)를 나눠 본다
fresh_items = set(
    hist.loc[hist.goodId.map(products.goodSmlclsCode).str.startswith("0301"), "cpi_item"].dropna()
)
total["신선"] = total.index.isin(fresh_items)
for is_fresh, t in total.groupby("신선"):
    print(
        "신선식품" if is_fresh else "가공·생활용품",
        f"{len(t)}개: 상관 {t.참가격.corr(t.통계청):.3f}, "
        f"방향 같음 {(np.sign(t.참가격) == np.sign(t.통계청)).mean():.3f}, "
        f"차이 절댓값 중앙값 {t.차이.abs().median():.3f}",
    )
print(total.sort_values("차이").round(3).to_string())

mom_cg = np.log(cg_b).diff().iloc[1:]
mom_cpi = np.log(cpi_b).diff().iloc[1:]
per_item = pd.Series({c: mom_cg[c].corr(mom_cpi[c]) for c in items})
print(
    "월 변화율 상관, 품목별:", per_item.describe(percentiles=[0.25, 0.5, 0.75]).round(3).to_dict()
)
print("참가격 월 변화가 0인 비율:", round((mom_cg.abs() < 1e-9).mean().mean(), 3))
print(
    "월 변화 크기 중앙값 |참가격|, |통계청|:",
    round(mom_cg.abs().median().median(), 4),
    round(mom_cpi.abs().median().median(), 4),
)

# 가공식품·생활용품 묶음: 짝지은 품목의 단순 평균 (가중치 없음)
agg = pd.DataFrame({"참가격": cg_b.mean(axis=1), "통계청(같은 품목)": cpi_b.mean(axis=1)})
print("품목 평균 지수 2년 변화:", (agg.iloc[-1] / 100 - 1).round(3).to_dict())

fig, axes = plt.subplots(1, 2, figsize=(10, 4))
ax = axes[0]
ax.scatter(total.통계청 * 100, total.참가격 * 100, s=14, color="#2563eb")
lim = [min(total.min().min() * 100, -30), max(total[["참가격", "통계청"]].max().max() * 100, 30)]
ax.plot(lim, lim, color="#94a3b8", linewidth=1)
ax.set_xlabel("통계청 품목 지수 2년 변화 (%)")
ax.set_ylabel("참가격으로 만든 지수 2년 변화 (%)")
ax.set_title(f"품목 {len(items)}개, 2024-11 → 2026-10", fontsize=10)
ax = axes[1]
x = agg.index.to_timestamp()
ax.plot(x, agg["참가격"], color="#2563eb", label="참가격 (15개 점포)")
ax.plot(x, agg["통계청(같은 품목)"], color="#64748b", label="통계청 (같은 품목)")
ax.set_ylabel("2024-11 = 100, 품목 단순 평균")
ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
ax.legend(frameon=False, fontsize=8)
ax.set_title("짝지은 품목의 평균 지수", fontsize=10)
save(fig, "kosis")


# %% [markdown]
# ## 5. Cavallo(2017) 재현
#
# 원자료 online_offline_ALL_clean.dta로 논문(NBER w22142 rev0, 결과 2016-03-23)의 표 3, 5, 6을
# 다시 계산한다. 복제 자료의 CODE/stats-retailers.do, stats-time-country.do를 pandas로 옮겼다.
# 표의 기본 표본: 세일 가격 제외, 대체 입력값(imputed) 포함.

# %%
cav = pd.read_stata(EXTERNAL / "cavallo2017/REPLICATION/RAWDATA/online_offline_ALL_clean.dta")


def cav_sale(d):
    """stats-*.do의 세일 표시: 오프라인 메모나 가격 유형, 온라인 세일 표시"""
    c = d.COMMENTS.fillna("")
    offline = (
        (c == "s")
        | c.str.contains("sale")
        | c.str.contains("s.*off")
        | (d.PRICETYPE == "Sale/Discounted Price")
    )
    return offline | (d.sale_online == 1)


def cav_markup(d):
    m = 100 * (d.price_online / d.price - 1)
    m = m.where(m.abs() >= 0.1, 0.0)  # Stata 정밀도 보정
    return m.where(m.abs() <= 50)  # 50% 넘는 차이는 매칭 오류로 보고 뺀다


def cav_levels(d):
    d = d.assign(m=cav_markup(d)).dropna(subset=["m"])

    def one(x):
        return pd.Series(
            {
                "관측": len(x),
                "같음%": 100 * (x.m == 0).mean(),
                "온라인 비쌈%": 100 * (x.m > 0).mean(),
                "온라인 쌈%": 100 * (x.m < 0).mean(),
                "다를 때 차이%": x.m[x.m != 0].mean(),
                "평균 차이%": x.m.mean(),
            }
        )

    t = d.groupby("COUNTRY").apply(one)
    t.loc["ALL"] = one(d)
    return t


cav_ns = cav[~cav_sale(cav)]
levels = cav_levels(cav_ns)
print("표 3 재현 (세일 제외)")
print(levels.round(1))
paper_t3 = pd.DataFrame(
    {
        "관측": [3699, 3797, 1915, 4031, 513, 1604, 2186, 3212, 2094, 15332, 38383],
        "같음%": [60, 74, 42, 91, 87, 74, 48, 85, 91, 69, 72],
        "다를 때 차이%": [3, 5, -7, -5, 3, -8, -13, -3, -8, -5, -4],
    },
    index=[
        "ARGENTINA", "AUSTRALIA", "BRAZIL", "CANADA", "CHINA", "GERMANY",
        "JAPAN", "SOUTHAFRICA", "UK", "USA", "ALL",
    ],
)  # fmt: skip
check = levels[["관측", "같음%", "다를 때 차이%"]].round(0).join(paper_t3.add_suffix("_논문"))
print("논문과 다른 칸:", int((check.iloc[:, :3].values != check.iloc[:, 3:].values).sum()))

m_all = cav_markup(cav)
matched = m_all.notna()
sale = cav_sale(cav)
print(
    f"세일 포함: 관측 {matched.sum():,}, 같음 {100 * (m_all[matched] == 0).mean():.1f}%, "
    f"세일 비중 {100 * sale[matched].mean():.1f}%, "
    f"세일 가격 중 같음 {100 * (m_all[matched & sale] == 0).mean():.1f}%"
)


def cav_changes(d):
    d = d[d.COUNTRY != "CHINA"].dropna(subset=["price", "price_online"])
    d = pd.concat([d, d.assign(COUNTRY="ALL")])
    d = d.assign(nid=d.groupby(["id", "retailer", "COUNTRY"], sort=False).ngroup())
    d = d.sort_values(["nid", "date"], kind="stable")
    g = d.groupby("nid")

    def pct(new, old):
        p = 100 * (new / old - 1)
        return p.where(~((p.abs() < 0.1) | (p.abs() > 200)), 0.0).where(p.notna())

    d = d.assign(
        on=pct(d.price_online, g.price_online.shift()), off=pct(d.price, g.price.shift())
    ).dropna(subset=["on", "off"])
    obs = d.groupby("COUNTRY").size()
    d = d[d.groupby("nid").on.transform("count") >= 2]  # 변화를 2번 이상 볼 수 있는 상품만
    out = {}
    for country, x in d.groupby("COUNTRY"):
        on, off = x.on.abs() > 0, x.off.abs() > 0
        freq = x.assign(a=on, b=off).groupby("nid")[["a", "b"]].mean()
        out[country] = {
            "관측": obs[country],
            "가격 변경": int((on | off).sum()),
            "동시%": 100 * (on & off).sum() / (on | off).sum(),
            "빈도 온라인": freq.a.mean(),
            "빈도 오프라인": freq.b.mean(),
            "크기 온라인%": x.on[on].abs().mean(),
            "크기 오프라인%": x.off[off].abs().mean(),
        }
    return pd.DataFrame(out).T


changes_cav = cav_changes(cav_ns)
print("표 5, 6 재현 (세일 제외)")
print(changes_cav.round(3))
print("논문 ALL: 관측 14367, 가격 변경 1331, 동시 19%, 빈도 .076/.068, 크기 22.02/19.98")
