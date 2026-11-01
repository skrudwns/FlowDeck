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
- 한계: 한 달치뿐이라 시계열 분석에는 아래 Open API의 과거 이력이 필요하다

## 받을 예정 (사용자 작업 필요)

| 데이터 | 쓰임 | 필요한 것 | 이용 조건 |
|---|---|---|---|
| 참가격 생필품 가격 Open API (공공데이터포털 15158701) | 판매점별 과거 가격 이력 (#31) | 공공데이터포털 회원가입, 활용신청, 인증키 | 공공저작물 출처표시(제1유형). 개발계정 하루 2,000건 |
| 통계청 소비자물가 품목 지수 (KOSIS Open API) | 참가격으로 만든 지수와 대조 (#31) | KOSIS 회원가입, 인증키 | 무료 |
| Cavallo(2017, AER) 복제 자료 (openICPSR E113131V1) | 온·오프라인 가격 연구 수치 재현 (#31) | openICPSR 로그인과 약관 동의 후 직접 받기 | 약관은 받을 때 확인. 가격 원자료가 들어 있는지는 아직 모른다 |

## 쓰지 않기로 한 것

- Dominick's (Kilts Center): 학술 연구 전용이고 Kilts Center 구독 데이터 목록에 있다
- Keepa (아마존 가격 이력 API): 유료다 (월 €49부터라는 자료)
- NAB (Numenta Anomaly Benchmark): 라벨은 있지만 대부분 서버 지표라 가격과 거리가 멀다
- KAMIS 농산물 가격: 긴 일별 시계열이지만 키가 필요하고, 위 데이터로 먼저 해 본 뒤 모자라면 다시 본다
