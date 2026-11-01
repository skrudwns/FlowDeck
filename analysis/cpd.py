"""변화점 감지 평가 지표와 감지기. AN-0002(docs/analysis/0002-change-point-validation.md)에서 쓴다.

지표는 TCPDBench(van den Burg & Williams, 2020, MIT)의 정의를 따라 다시 구현했다.
TCPDBench에 저장된 점수가 그대로 나오는지로 구현을 확인한다 (an0002.py 1단계).

- 변화점 위치는 0부터 센다. 위치 t는 "t부터 새 구간"이라는 뜻이다.
- 0은 항상 변화점으로 본다 (시계열의 시작).
"""

from collections.abc import Iterable, Mapping

import numpy as np
import ruptures

MARGIN = 5


def matched(truth: Iterable[int], predicted: Iterable[int], margin: int = MARGIN) -> set[int]:
    """truth 중 margin 안에 짝이 되는 예측이 있는 것. 예측 하나는 한 번만 짝이 된다."""
    remaining = set(predicted)
    hits = set()
    for tau in truth:
        near = sorted((abs(tau - x), x) for x in remaining if abs(tau - x) <= margin)
        if near:
            hits.add(tau)
            remaining.remove(near[0][1])
    return hits


def f1_score(
    annotations: Mapping[str, Iterable[int]], predicted: Iterable[int], margin: int = MARGIN
) -> tuple[float, float, float]:
    """(F1, 정밀도, 재현율). 정밀도는 모든 작성자 라벨을 합친 것 기준, 재현율은 작성자별 평균."""
    # 짝짓기가 탐욕적이라 set을 도는 순서에 따라 결과가 조금 달라질 수 있다.
    # TCPDBench와 같은 점수가 나오도록 set을 같은 순서로 만든다
    per_annotator = []
    for cps in annotations.values():
        a = set(cps)
        a.add(0)
        per_annotator.append(a)
    pred = set(predicted)
    pred.add(0)
    union: set[int] = set()
    for a in per_annotator:
        for tau in a:
            union.add(tau)
    precision = len(matched(union, pred, margin)) / len(pred)
    recall = float(np.mean([len(matched(a, pred, margin)) / len(a) for a in per_annotator]))
    if precision + recall == 0:
        return 0.0, precision, recall
    return 2 * precision * recall / (precision + recall), precision, recall


def _segments(cps: Iterable[int], n: int) -> list[range]:
    bounds = sorted({c for c in cps if 0 < c < n})
    edges = [0, *bounds, n]
    return [range(a, b) for a, b in zip(edges, edges[1:], strict=False)]


def _jaccard(a: range, b: range) -> float:
    inter = max(0, min(a.stop, b.stop) - max(a.start, b.start))
    return inter / (len(a) + len(b) - inter)


def cover_score(
    annotations: Mapping[str, Iterable[int]], predicted: Iterable[int], n: int
) -> float:
    """작성자별 분할을 예측 분할이 얼마나 덮는지(Arbelaez 2010 식 8)의 평균."""
    pred = _segments(predicted, n)
    scores = []
    for cps in annotations.values():
        truth = _segments(cps, n)
        scores.append(sum(len(r) * max(_jaccard(r, p) for p in pred) for r in truth) / n)
    return float(np.mean(scores))


# --- 감지기 ---


def step_rule(
    values: np.ndarray, min_pct: float = 5.0, min_abs: float = 0.0, persist: int = 2
) -> list[int]:
    """제품 규칙(AN-0001): 직전 수준 대비 min_pct% 이상, min_abs 이상 바뀌고
    그 수준이 persist번 이상 이어지면 변화로 본다. 한 시간짜리 특가나 10원 경쟁을 거르려는 것.

    직전 수준은 마지막 변화점 이후 값들의 중앙값이다.
    """
    x = np.asarray(values, dtype=float)
    cps: list[int] = []
    start = 0
    t = 1
    while t + persist <= len(x):
        level = float(np.median(x[start:t]))
        new = x[t : t + persist]
        moved = np.abs(new - level)
        threshold = max(min_abs, abs(level) * min_pct / 100)
        same_side = np.all(new > level) or np.all(new < level)
        if same_side and np.all(moved >= threshold):
            cps.append(t)
            start = t
            t += persist
        else:
            t += 1
    return cps


def pelt(values: np.ndarray, penalty_scale: float = 1.0, min_size: int = 2) -> list[int]:
    """PELT(L2 비용). 벌점은 BIC 꼴 2·log(n)·σ²이고 σ는 1차 차분의 MAD로 잡는다.
    값 범위가 시계열마다 달라서 표준화한 뒤 돌린다."""
    x = np.asarray(values, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    std = x.std(axis=0)
    std[std == 0] = 1
    z = (x - x.mean(axis=0)) / std
    diff = np.diff(z, axis=0)
    sigma = np.median(np.abs(diff - np.median(diff, axis=0)), axis=0).mean() * 1.4826 / np.sqrt(2)
    sigma = max(sigma, 1e-3)
    pen = penalty_scale * 2 * np.log(len(z)) * sigma**2 * z.shape[1]
    ends = ruptures.Pelt(model="l2", min_size=min_size, jump=1).fit(z).predict(pen=pen)
    return [e for e in ends if e < len(z)]
