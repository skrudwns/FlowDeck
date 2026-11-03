# 분석 검증용 외부 데이터

선정 이유는 `docs/adr/0013-validation-datasets.md`. 받기는 `uv run python fetch_external.py`. 받은 파일은 `data/external/`에 두고 커밋하지 않는다.

## 받은 것

### TCPD (Turing Change Point Dataset)

- 쓰임: 변화점·급락 감지 검증 (#30). 사람이 표시한 변화점 라벨이 있다
- 출처: https://github.com/alan-turing-institute/TCPD
- 판: 커밋 `e8f19a3` (2025-07-25), 2026-11-01 받음
- 이용 조건: 코드는 MIT. 데이터는 시계열마다 README에 따로 적혀 있다 (예: brent_spot 퍼블릭 도메인, gdp_* CC-BY 4.0). 10개는 재배포가 안 돼서 저장소에 없다
- 규모: 라벨이 있는 시계열 42개, 시계열마다 라벨 작성자 5명. 데이터가 들어 있는 32개는 길이 15~816
- 받지 않은 10개: apple, bee_waggle_6, bitcoin, iceland_tourism, measles, occupancy, ratner_stock, robocalls, scanline_126007, scanline_42049. 저장소의 `build_tcpd.py`가 원 출처나 인터넷 아카이브에서 받는데, 다른 저장소의 스크립트는 실행하지 않기로 해서 지금은 받지 않았다

### TCPDBench 결과

- 쓰임: 같은 TCPD 시계열에 알고리즘 14개를 돌린 공개 점수. 우리 알고리즘과 같은 지표로 비교한다 (#30)
- 출처: https://github.com/alan-turing-institute/TCPDBench (논문 van den Burg & Williams, 2020, arXiv:2003.06222)
- 판: 커밋 `1672100` (2022-10-24)의 `analysis/output`만, 2026-11-01 받음
- 이용 조건: MIT
- 규모: `summaries/summary_*.json` 42개. 시계열마다 알고리즘별 기본 설정(default)과 최적 설정(oracle) 결과, 찾은 변화점 위치, F1·cover 점수

### 참가격 생필품 가격 (파일)

- 쓰임: 판매점 간 가격 비교와 할인 판별 (#31)
- 출처: 공공데이터포털 15083256 "한국소비자원_생필품 가격 정보", https://www.data.go.kr/data/15083256/fileData.do
- 판: `한국소비자원_생필품 가격 정보_20260925` (월간 갱신, 다음 등록 2026-11-13), 2026-11-01 받음, sha256 `23258dce…24c7d`
- 이용 조건: 이용허락범위 제한 없음, 무료
- 규모: 235,632행. 상품 592개, 판매업소 448곳(롯데슈퍼, 이마트, GS더프레시 대부분). 조사일은 2026-09-11, 09-25 두 날뿐이다. 세일 여부는 86%가 비어 있다
- 한계: 한 달치뿐이라 시계열 분석에는 아래 Open API를 쓴다

### 참가격 생필품 가격 Open API

- 쓰임: 판매점별 과거 가격과 세일 기간 (#42, AN-0004)
- 출처: 공공데이터포털 15158701 "한국소비자원_생필품 가격 정보_GW", `apis.data.go.kr/B551919/ProductPriceInfoService`
- 받기: `chamgagyeok_api.py`가 요청마다 응답 XML을 `data/external/chamgagyeok/api/`에 저장한다. `an0004.py`를 돌리면 없는 것만 요청한다. 인증키는 `backend/.env`의 `DATA_GO_KR_KEY`
- 이용 조건: 공공저작물 출처표시(제1유형). 개발계정은 상세기능마다 하루 2,000건
- 규모: 2026-11-04에 15개 점포 x 46개 조사일(2024-11-08 ~ 2026-10-23) 179,936행. 판매점 목록 630곳, 상품 목록 604개
- 주의: 조사일은 명세의 "매주 금요일"과 달리 대체로 2주 간격이고 공휴일 주는 비어 있다. 세일 표기(Y/N)는 체인과 조사일마다 빈칸 비율이 다르다

### 통계청 소비자물가 품목 지수 (KOSIS)

- 쓰임: 참가격으로 만든 품목 지수와 대조 (#42, AN-0004)
- 출처: KOSIS Open API, 통계청 DT_1J22001 지출목적별 소비자물가지수(품목 포함, 2020=100)
- 받기: `uv run python fetch_external.py kosis`. 인증키는 `backend/.env`의 `KOSIS_API_KEY`
- 판: 전국, 2024-10 ~ 2026-10, 2026-11-04 받음. 579개 항목 x 25개월
- 이용 조건: 무료

### Cavallo(2017) 복제 자료

- 쓰임: 온·오프라인 가격 연구의 표 재현 (#42, AN-0004)
- 출처: openICPSR E113131V1, Cavallo, A. (2017) "Are Online and Offline Prices Similar? Evidence from Large Multi-Channel Retailers", AER 107(1)
- 받기: 사용자가 openICPSR에 로그인하고 약관에 동의해 받는다. `data/external/cavallo2017/`에 `REPLICATION/`과 `LICENSE.txt`를 둔다. `fetch_external.py cavallo2017`은 원자료가 있는지만 확인한다
- 이용 조건: 데이터 CC BY 4.0, 코드 BSD-3 (COPYRIGHT 2017 American Economic Association). 42MB라 저장소에는 넣지 않는다
- 규모: 원자료 `RAWDATA/online_offline_ALL_clean.dta` 45,253행(10개국 56개 유통사 온라인·오프라인 가격), Stata 코드 `CODE/`

## 쓰지 않기로 한 것

- Dominick's (Kilts Center): 학술 연구 전용이고 Kilts Center 구독 데이터 목록에 있다
- Keepa (아마존 가격 이력 API): 유료다 (월 €49부터라는 자료)
- NAB (Numenta Anomaly Benchmark): 라벨은 있지만 대부분 서버 지표라 가격과 거리가 멀다
- KAMIS 농산물 가격: 긴 일별 시계열이지만 키가 필요하고, 위 데이터로 먼저 해 본 뒤 모자라면 다시 본다
