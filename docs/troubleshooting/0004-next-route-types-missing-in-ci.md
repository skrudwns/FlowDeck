# TS-0004: CI에서만 PageProps, LayoutProps 타입을 못 찾음

- 날짜: 2026-10-24
- 관련: #14, PR #22, ADR-0009
- 상태: 해결

> 요약: Next.js 라우트 타입(`PageProps`, `LayoutProps`)은 `next dev`·`next build`·`next typegen`이 만든다. 로컬에는 개발 서버가 만들어 둔 게 있었고, CI는 빌드 전에 `tsc`를 돌려서 없었다.

## 증상

PR #22 CI의 web 작업이 타입 검사 단계에서 실패했다. 로컬에서는 같은 `npm run typecheck`가 통과했다.

```
Cannot find name 'PageProps'.
Cannot find name 'LayoutProps'.
```

## 원인 찾기

| 가설 | 확인 방법 | 결과 |
|---|---|---|
| 두 타입은 Next.js가 생성하는 전역 타입이다 | `node_modules/next/dist/docs/.../02-typescript.md` | 맞음. "generated during `next dev`, `next build`, or via `next typegen`" |
| 로컬에는 생성된 파일이 있다 | `web/.next/types/`, `web/next-env.d.ts` | 맞음. `next-env.d.ts`가 `./.next/types/routes.d.ts`를 import하고, 둘 다 개발 서버를 띄울 때 생겼다 |
| 로컬에서 재현된다 | `rm -rf .next` 후 `tsc --noEmit` | 맞음. 같은 `Cannot find name` 오류 |
| CI는 생성 전에 검사한다 | ci.yml 순서 | 맞음. `npm ci` → 타입 확인 → lint → typecheck(`tsc --noEmit`) → build. `.next`는 저장소에 없다 |

같은 문서에 `next-env.d.ts`는 `.gitignore`에 넣고 git에서 빼라고 되어 있다. 이걸 보고 처음에는 create-next-app이 만든 그대로 커밋하면서 `next-env.d.ts`도 저장소에 들어갔다고 이 문서에 적었다. 확인해 보니 틀렸다. create-next-app의 `.gitignore`에 이미 들어 있어서 커밋된 적이 없었다 (`git ls-files web | grep next-env` 결과 0). 그래서 CI에는 `next-env.d.ts`도 `.next/types`도 없었다.

## 원인

로컬 검사는 개발 서버가 만들어 둔 `.next/types`에 기대서 통과했다. 깨끗한 환경(CI)에는 그 파일이 없다.

## 해결

`typecheck` 스크립트를 `next typegen && tsc --noEmit`으로 바꿨다 (커밋 `508f334`). 타입 검사 전에 라우트 타입을 만든다.

- 로컬: `rm -rf .next` 후 `npm run typecheck` 통과
- CI: web 작업의 API 타입 확인, lint, typecheck, build가 모두 통과 (CI #41, #42)

## 배운 것

- 로컬에서 통과한 검사가 생성된 파일에 기대고 있지 않은지 본다. 이번 경우 `rm -rf .next`한 뒤 검사를 돌려 봤으면 로컬에서 먼저 잡혔다.
- 문서에서 읽은 일반론("이 파일이 커밋돼 있으면 빼라")을 이 저장소에 그대로 적용하기 전에 실제 상태를 확인한다.
