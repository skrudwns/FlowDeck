# TS-0002: CI가 시작하자마자 실패, setup-uv@v10을 찾지 못함

- 날짜: 2026-10-24
- 관련: #2, PR #3, 커밋 `c049889`(CI 추가), `75adb91`(수집 워크플로 추가)
- 상태: 미해결

> 요약: setup-uv는 v8부터 `@v8` 같은 major 태그를 만들지 않는다. 최신 릴리스가 v10.3.2라는 것만 보고 `@v10`으로 적었다.

## 증상

브랜치를 push하자 CI가 두 번(push, PR #3) 모두 7~8초 만에 실패했다. 테스트 단계까지 가지도 못했다.

```
Unable to resolve action `astral-sh/setup-uv@v10`, unable to find version `v10`
```

## 원인 찾기

| 가설 | 확인 방법 | 결과 |
|---|---|---|
| `v10` 태그가 없다 | GitHub API `git/matching-refs/tags/v10` | 맞음. `v10.0.0` ~ `v10.3.2`만 있고 `v10`은 없음 |
| setup-uv가 원래 major 태그를 안 쓴다 | major 태그(`v` + 숫자만) 목록 | `v1` ~ `v7`은 있음. `v8`부터 없음 |
| checkout도 같은 문제가 있다 | `matching-refs/tags/v7` | 아님. `actions/checkout`은 `v7` 태그가 있음 |

setup-uv v8.0.0 릴리스 노트:

```
## No more major and minor tags
To increase security even more we will stop publishing minor tags. You won't be able to use `@v8` or `@v8.0` any longer.
> Use the immutable tag as a version `astral-sh/setup-uv@v8.0.0`
```

이유는 major 태그를 따라가면 tj-actions 사건 같은 공급망 공격에 노출된다는 것이다.

## 원인

워크플로를 쓸 때 GitHub API로 최신 릴리스(`v10.3.2`)만 확인하고, 다른 액션들처럼 `@v10`이 있을 거라고 짐작했다. 태그가 실제로 있는지는 확인하지 않았다.

## 해결

## 배운 것

- 액션 버전은 릴리스 이름이 아니라 실제 태그가 있는지 확인하고 적는다.
- major 태그(`@v7`)는 액션 쪽에서 언제든 다른 커밋으로 옮길 수 있다. 전체 버전 태그나 커밋 SHA로 고정하는 게 더 안전하다.
