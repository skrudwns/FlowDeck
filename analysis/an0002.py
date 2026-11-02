# %% [markdown]
# # AN-0002: 변화점·급락 감지 알고리즘 검증
#
# 기록: docs/analysis/0002-change-point-validation.md
# 데이터: data/external/tcpd, data/external/tcpdbench (fetch_external.py),
#         data/*.parquet (export.py)
# 그래프: docs/assets/an0002-*.png

# %%
import glob
import json
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from cpd import (
    cover_score,
    f1_score,
    matched,
    mbic,
    mbic_cost,
    pelt,
    residual_sigma,
    step_rule,
    zscore,
)
from mock_shop.catalog import PRODUCTS, SELLERS
from mock_shop.pricing import KST, offer_at

HERE = Path(__file__).parent
EXT = HERE / "data" / "external"
ASSETS = HERE.parent / "docs" / "assets"
plt.rcParams["font.family"] = "AppleGothic"
plt.rcParams["axes.unicode_minus"] = False
pd.set_option("display.width", 200)

RULE = {"min_pct": 5, "persist": 2}  # AN-0001에서 정한 제품 규칙의 처음 값
RULE_GRID = [(p, k) for p in (1, 2, 3, 5, 8, 10, 15, 20, 30) for k in (1, 2, 3, 5)]
PELT_GRID = [0.1, 0.3, 1, 3, 10, 30, 100, 300]


def save(fig, name):
    fig.tight_layout()
    fig.savefig(ASSETS / f"an0002-{name}.png", dpi=120)
    plt.close(fig)


# %% [markdown]
# ## 1. 지표 구현 확인: TCPDBench에 저장된 점수 재현

# %%
summaries = sorted(glob.glob(str(EXT / "tcpdbench/analysis/output/summaries/*.json")))
checked, worst = 0, 0.0
for path in summaries:
    s = json.load(open(path))
    for key, runs in s["results"].items():
        run = runs[0]
        if not key.startswith("default_") or run["status"] != "SUCCESS" or not run["scores"]:
            continue
        f1, _, _ = f1_score(s["annotations"], run["cplocations"])
        cover = cover_score(s["annotations"], run["cplocations"], s["dataset_nobs"])
        worst = max(worst, abs(f1 - run["scores"]["f1"]), abs(cover - run["scores"]["cover"]))
        checked += 1
print(f"저장된 결과 {checked}개 재현, 최대 차이 {worst:.2e}")

# %% [markdown]
# ## 2. 연습 쇼핑몰 정답 (4주, 판매처별 시간 단위 가격)
#
# 정답 변화점: 급락·주말 할인이 켜지고 꺼지는 시각. 매일 자정의 ±3% 변동은 알림 대상이 아니라 뺀다.
# 허용 오차는 1시간.

# %%
start = datetime(2026, 10, 26, tzinfo=KST)
hours = [start + timedelta(hours=h) for h in range(24 * 28)]
mock = []
for product in PRODUCTS:
    for code in product.base_prices:
        offers = [offer_at(product, SELLERS[code], t) for t in hours]
        price = np.array([o.price for o in offers], dtype=float)
        truth, drops = set(), set()
        for rule in ("flash_sale", "weekend_sale"):
            on = np.array([rule in o.rules for o in offers])
            truth |= {t for t in range(1, len(on)) if on[t] != on[t - 1]}
            drops |= {t for t in range(1, len(on)) if on[t] and not on[t - 1]}
        mock.append({"x": price, "truth": truth, "drops": drops})


def mock_scores(detect, margin=1):
    tp = fp = fn = drop_hits = 0
    for s in mock:
        pred = set(detect(s["x"]))
        hits = matched(s["truth"], pred, margin)
        tp += len(hits)
        fn += len(s["truth"]) - len(hits)
        fp += len(pred) - len(matched(pred, s["truth"], margin))
        drop_hits += len(matched(s["drops"], pred, margin))
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return precision, recall, f1, drop_hits / sum(len(s["drops"]) for s in mock)


rows = []
for p, k in [(3, 2), (5, 1), (5, 2), (5, 3), (10, 2), (20, 2)]:
    rows.append(
        ("rule", f"{p}%, {k}시간", *mock_scores(lambda x, p=p, k=k: step_rule(x, p, persist=k)))
    )
for c in (0.5, 1, 10):
    rows.append(("pelt", f"배율 {c}", *mock_scores(lambda x, c=c: pelt(x, penalty_scale=c))))
mock_table = pd.DataFrame(rows, columns=["감지기", "설정", "정밀도", "재현율", "F1", "급락 재현율"])
print(f"판매처 시계열 {len(mock)}개, 정답 변화점 {sum(len(s['truth']) for s in mock)}개")
print(mock_table.round(3).to_string(index=False))

# %% [markdown]
# ## 3. TCPD 벤치마크: 공개된 알고리즘 14개와 비교
#
# 단변량이고 데이터가 저장소에 있는 시계열. 모든 방법이 성공한 시계열로만 평균을 낸다.
# default는 정해 둔 설정 하나, best는 시계열마다 가장 좋은 설정의 점수다.

# %%
records = []
for path in summaries:
    s = json.load(open(path))
    name = s["dataset"]
    data_file = EXT / "tcpd/datasets" / name / f"{name}.json"
    if not data_file.exists() or s["dataset_ndim"] != 1:
        continue
    raw = json.load(open(data_file))["series"][0]["raw"]
    x = pd.Series(raw, dtype=float).ffill().bfill().to_numpy()
    ann, n = s["annotations"], s["dataset_nobs"]

    def score(cps, ann=ann, n=n):
        return f1_score(ann, cps)[0], cover_score(ann, cps, n)

    rec = {"dataset": name}
    rec["our_rule|default|f1"], rec["our_rule|default|cover"] = score(step_rule(x, **RULE))
    rec["our_pelt|default|f1"], rec["our_pelt|default|cover"] = score(pelt(x))
    for label, results in (
        ("our_rule", [score(step_rule(x, p, persist=k)) for p, k in RULE_GRID]),
        ("our_pelt", [score(pelt(x, penalty_scale=c)) for c in PELT_GRID]),
    ):
        rec[f"{label}|best|f1"] = max(a for a, _ in results)
        rec[f"{label}|best|cover"] = max(b for _, b in results)
    for key, runs in s["results"].items():
        kind, method = key.split("_", 1)
        ok = [r for r in runs if r["status"] == "SUCCESS" and r["scores"]]
        if not ok:
            continue
        setting = "default" if kind == "default" else "best"
        rec[f"{method}|{setting}|f1"] = max(r["scores"]["f1"] for r in ok)
        rec[f"{method}|{setting}|cover"] = max(r["scores"]["cover"] for r in ok)
    records.append(rec)

bench = pd.DataFrame(records).set_index("dataset")
common = bench.dropna()
print(f"단변량 시계열 {len(bench)}개 중 모든 방법이 성공한 {len(common)}개로 비교")
summary = []
for col in [c for c in common.columns if c.endswith("|f1")]:
    method, setting, _ = col.split("|")
    same = [c for c in common.columns if c.endswith(f"|{setting}|f1")]
    summary.append(
        {
            "설정": setting,
            "방법": method,
            "F1": common[col].mean(),
            "cover": common[f"{method}|{setting}|cover"].mean(),
            "F1 평균 순위": common[same].rank(axis=1, ascending=False)[col].mean(),
        }
    )
summary = pd.DataFrame(summary).sort_values(["설정", "F1"], ascending=[False, False])
print(summary.round(3).to_string(index=False))

fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), sharey=False)
for ax, setting in zip(axes, ("default", "best"), strict=True):
    part = summary[summary["설정"] == setting].sort_values("F1")
    colors = ["#f59e0b" if m.startswith("our_") else "#94a3b8" for m in part["방법"]]
    ax.barh(part["방법"], part["F1"], color=colors)
    ax.set_title(f"{setting} 설정, 평균 F1 (시계열 {len(common)}개)")
    ax.set_xlim(0, 1)
save(fig, "tcpd-f1")

# %% [markdown]
# ## 4. 다나와 적용 (AN-0001과 같은 1주 데이터)

# %%
snaps = pd.read_parquet(HERE / "data" / "snapshots.parquet")
danawa = snaps[(snaps.source == "danawa") & (snaps.status == "ok")].copy()
danawa["kst"] = danawa.collected_at.dt.tz_convert(KST)
danawa = danawa.sort_values(["source_product_id", "kst"])

counts = []
events = []
for pcode, g in danawa.groupby("source_product_id"):
    x = g.lowest_price.to_numpy(float)
    big = int((np.abs(np.diff(x) / x[:-1]) >= 0.05).sum())
    cps = step_rule(x, **RULE)
    counts.append({"pcode": pcode, "5% 이상 변화": big, "규칙": len(cps), "PELT": len(pelt(x))})
    edges = [0, *cps, len(x)]
    for i, cp in enumerate(cps):
        before = float(np.median(x[edges[i] : cp]))  # 감지기가 쓰는 직전 구간 수준
        events.append(
            {
                "pcode": pcode,
                "이름": g["name"].iloc[0][:18],
                "시각": g.kst.iloc[cp].strftime("%m-%d %H시"),
                "이전": int(before),
                "이후": int(x[cp]),
                "변화%": (x[cp] - before) / before * 100,
                "유지(시간)": edges[i + 2] - cp,
            }
        )
counts = pd.DataFrame(counts)
events = pd.DataFrame(events)
print("감지 건수 합계:", counts[["5% 이상 변화", "규칙", "PELT"]].sum().to_dict())
for persist in (1, 2, 3, 6):
    n = sum(
        len(step_rule(g.lowest_price.to_numpy(float), 5, persist=persist))
        for _, g in danawa.groupby("source_product_id")
    )
    print(f"규칙 5%, 지속 {persist}시간: {n}건")
print("유지 시간(시간):", events["유지(시간)"].describe().round(1).to_dict())
print(events[events.pcode.isin(["74056484", "106702589"])].round(1).to_string(index=False))

fig, axes = plt.subplots(2, 1, figsize=(8, 5.6), sharex=True)
for ax, pcode, label in zip(
    axes,
    ("74056484", "106702589"),
    ("키오시아 EXCERIA PLUS G4 2TB", "갤럭시 버즈4 프로"),
    strict=True,
):
    g = danawa[danawa.source_product_id == pcode]
    x = g.lowest_price.to_numpy(float)
    ax.step(g.kst, x / 10000, where="post", color="#0369a1")
    for cp in step_rule(x, **RULE):
        ax.axvline(g.kst.iloc[cp], color="#f59e0b", linestyle="--", linewidth=1)
    ax.set_title(f"{label} (주황 점선: 규칙 감지)", fontsize=10)
    ax.set_ylabel("만원")
axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%m-%d", tz=KST))
save(fig, "danawa-cases")

# %% [markdown]
# ## 5. 벌점 고치기 (#40)
#
# 4단계까지의 PELT는 σ를 1차 차분의 MAD로 잡아서, 계단형 가격에서 벌점이 0으로 무너졌다.
# TCPDBench의 default pelt는 R changepoint의 cpt.mean(Normal, MBIC)이다. 값을 표준화하고 σ=1로 둔다.
# 같은 목적함수(cpd.mbic)를 만들어 저장된 R 결과와 맞춰 본 뒤, 세 데이터에 다시 돌린다.


# %%
def mbic_resid(x):
    """MBIC로 한 번 나눈 뒤 구간 잔차로 σ를 다시 잡아 한 번 더 나눈다."""
    z = zscore(x)
    sigma = residual_sigma(z, mbic(z))
    return mbic(z, sigma=max(sigma, 1e-3))


DETECTORS = {
    "규칙(5%, 2시간)": lambda x: step_rule(x, **RULE),
    "PELT(차분 MAD)": pelt,
    "MBIC": lambda x: mbic(zscore(x)),
    "MBIC(잔차 σ)": mbic_resid,
}

# 5-1. 저장된 R 결과와 같은 위치가 나오는가 (저장 값 = 우리 표기 - 1)
same, other = 0, []
tcpd = []
for path in summaries:
    s = json.load(open(path))
    name = s["dataset"]
    if name not in common.index:
        continue
    raw = json.load(open(EXT / "tcpd/datasets" / name / f"{name}.json"))["series"][0]["raw"]
    x = pd.Series(raw, dtype=float).ffill().bfill().to_numpy()
    r_run = s["results"]["default_pelt"][0]
    r_cps = [c + 1 for c in r_run["cplocations"]]
    ours = mbic(zscore(x))
    if ours == r_cps:
        same += 1
    else:
        z = zscore(x)
        other.append((name, r_cps, ours, mbic_cost(z, r_cps), mbic_cost(z, ours)))
    rec = {
        "dataset": name,
        "R pelt": r_run["scores"]["f1"],
        "zero": common.loc[name, "zero|default|f1"],
    }
    for label, detect in DETECTORS.items():
        cps = detect(x)
        rec[label] = f1_score(s["annotations"], cps)[0]
        rec[f"{label} cover"] = cover_score(s["annotations"], cps, s["dataset_nobs"])
        shifted = [c - 1 for c in cps]  # TCPDBench가 R 결과를 저장한 표기
        rec[f"{label} -1"] = f1_score(s["annotations"], shifted)[0]
    tcpd.append(rec)
print(f"R pelt와 위치가 같은 시계열 {same}개 / {len(common)}개")
for name, r_cps, ours, r_cost, our_cost in other:
    print(f"  {name}: R {r_cps} 목적함수 {r_cost:.3f}, 우리 {ours} 목적함수 {our_cost:.3f}")
tcpd = pd.DataFrame(tcpd).set_index("dataset")
print(tcpd.mean().round(3).to_string())
print(
    "R pelt와 F1이 같은 시계열(-1 표기):",
    int((tcpd["MBIC -1"] - tcpd["R pelt"]).abs().lt(1e-9).sum()),
)

# %%
# 5-2. 연습 쇼핑몰, 5-3. 다나와
rows = [(label, *mock_scores(detect)) for label, detect in DETECTORS.items()]
print(pd.DataFrame(rows, columns=["감지기", "정밀도", "재현율", "F1", "급락 재현율"]).round(3))

midnight = 0
for s in mock:
    pred = mbic(zscore(s["x"]))
    midnight += sum(hours[p].hour == 0 for p in pred if all(abs(p - t) > 1 for t in s["truth"]))
print("MBIC 오탐 중 자정:", midnight)

per_product = []
for _, g in danawa.groupby("source_product_id"):
    x = g.lowest_price.to_numpy(float)
    rule_cps, mbic_cps = step_rule(x, **RULE), mbic(zscore(x))
    # 4단계와 같이 직전 구간 중앙값 대비 변화율
    before = [np.median(x[a:c]) for a, c in zip([0, *mbic_cps], mbic_cps, strict=False)]
    small = [c for c, b in zip(mbic_cps, before, strict=True) if abs(x[c] - b) / b < 0.05]
    per_product.append(
        {
            "이름": g["name"].iloc[0][:16],
            "변동폭%": (x.max() - x.min()) / np.median(x) * 100,
            "규칙": len(rule_cps),
            "MBIC": len(mbic_cps),
            "MBIC 중 5% 미만": len(small),
            "MBIC(잔차 σ)": len(mbic_resid(x)),
            "겹침": len(matched(rule_cps, mbic_cps, 1)),
        }
    )
per_product = pd.DataFrame(per_product).sort_values("변동폭%")
print(per_product.round(0).to_string(index=False))
print(per_product.drop(columns=["이름", "변동폭%"]).sum().to_dict())
