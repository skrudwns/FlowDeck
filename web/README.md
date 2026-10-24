# web

FlowDeck 포털 웹. Next.js 16 (App Router), TypeScript, Tailwind CSS. 구조와 이유는 `docs/adr/0009-portal-web-structure.md`.

## 실행

포털 API가 먼저 떠 있어야 한다 (`backend/README.md`).

```bash
npm install
FLOWDECK_API_URL=http://localhost:8000 npm run dev   # http://localhost:3000
```

## 화면

| 경로 | 내용 |
|---|---|
| `/` | 작업 목록(주기, 다음 실행, 마지막 실행), 수집 → 가공 → 저장 → 알림 흐름 |
| `/runs`, `/runs/[id]` | 실행 이력, 상품별 결과와 실패 원인 |
| `/products`, `/products/[id]` | 상품 가격 표(검색, 상태 거르기), 최저가 차트, 판매처 가격 |

## API 타입

백엔드 API가 바뀌면 타입을 다시 만든다. 생성물(`openapi.json`, `src/lib/api/schema.d.ts`)은 커밋한다. CI가 다시 만들어 보고 다르면 실패한다.

```bash
npm run gen:api
```

## 검사

```bash
npm run lint
npm run typecheck
npm run build   # API 서버 없이 된다
```

## 참고

- 이 버전의 Next.js는 `cacheComponents`가 켜져 있어서, 요청마다 가져오는 데이터와 `params`·`searchParams`는 `<Suspense>` 안에서 읽는다.
- 버전별 문서는 `node_modules/next/dist/docs/`에 있다 (`AGENTS.md`).
