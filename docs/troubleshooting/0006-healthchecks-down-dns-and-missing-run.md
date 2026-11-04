# TS-0006: 11-04 저녁~11-05 새벽 수집이 세 번 빠져 Healthchecks에서 DOWN

- 날짜: 2026-11-05
- 관련: #51, ADR-0006, ADR-0007, ADR-0011
- 상태: 해결 (외부 장애, 코드 변경 없음)

> 요약: 세 번이 서로 다른 이유였다. 11-04 19:17 KST 다나와 수집은 Actions 러너가 `prod.danawa.com` 이름을 풀지 못해 실패했다(GitHub 장애 시간 안, 연관은 미확인). 20:17은 cron-job.org의 호출에 GitHub API가 500을 돌려줘 실행이 없었다(GitHub 장애). 11-05 00:17은 cron-job.org가 호출 자체를 하지 않았다(이유 모름). 예비 호출을 두는 안은 사용자가 두지 않기로 했다.

## 증상

사용자가 Healthchecks 화면과 메일을 보여 주며 "뭔가 이슈가 있는 거 같은데"라고 알려 줬다. Healthchecks 목록에서 "FlowDeck 다나와 수집", "FlowDeck 연습 쇼핑몰 수집" 둘 다 경고(!) 표시였다. 메일 제목:

```
DOWN | FlowDeck 연습 쇼핑몰 수집 - "FlowDeck 연습 쇼핑몰 수집" is DOWN (success sign...
UP | FlowDeck 다나와 수집 - "FlowDeck 다나와 수집" is UP. The downtime lasted 1 hour, 5...
UP | FlowDeck 연습 쇼핑몰 수집 - "FlowDeck 연습 쇼핑몰 수집" is UP. The downtime lasted ...
```

## 근거

GitHub Actions 가격 수집 실행 (UTC, 2026-11-04 15:39 UTC에 API로 조회):

```
276 가격 수집 workflow_dispatch completed success 2026-11-04T12:17:07Z 2026-11-04T12:19:40Z
275 가격 수집 workflow_dispatch completed failure 2026-11-04T10:17:08Z 2026-11-04T10:21:55Z
274 가격 수집 workflow_dispatch completed success 2026-11-04T09:17:07Z 2026-11-04T09:19:40Z
```

11:17 UTC(20:17 KST) 실행이 없다. 11-05 00:50 KST에 다시 조회했을 때 마지막 실행은 278(14:17 UTC, 23:17 KST)이고 15:17 UTC(00:17 KST) 실행도 없었다.

실행 275의 단계 (다나와 수집만 실패, 평소 1분 20초 안팎인데 3분 39초):

```
7 다나와 수집 failure 2026-11-04T10:17:33Z 2026-11-04T10:21:12Z
8 연습 쇼핑몰 띄우기 success 2026-11-04T10:21:12Z 2026-11-04T10:21:13Z
9 연습 쇼핑몰 수집 success 2026-11-04T10:21:13Z 2026-11-04T10:21:52Z
```

Neon의 수집 실행 기록 (KST):

```
(529, 'danawa', 18:17:31, 18:18:54, 'success', 'schedule', 20, 20, None)
(531, 'danawa', 19:17:33, 19:21:09, 'failed', 'schedule', 20, 0, None)
(532, 'mockshop', 19:21:14, 19:21:49, 'success', 'schedule', 8, 8, None)
(533, 'danawa', 21:17:32, 21:18:54, 'success', 'schedule', 20, 20, None)
```

실행 531의 스냅샷 20개:

```
(531, 'http_error', None, 20, "요청 실패: ConnectError('[Errno -3] Temporary failure in name resolution')")
```

cron-job.org 실행 기록 (KST, 사용자가 내장 브라우저에서 로그인한 뒤 11-05 00:4x에 확인):

```
Today at 1:17:00 AM                     Scheduled
Yesterday at 11:17:05 PM  5.64 s  3.11 s  Successful 200 OK
Yesterday at 10:17:05 PM  5.3 s   3.07 s  Successful 200 OK
Yesterday at 9:17:05 PM   5.44 s  2.68 s  Successful 200 OK
Yesterday at 8:17:06 PM   6.03 s  4.61 s  Failed (HTTP error) 500 Internal Server Error
Yesterday at 7:17:05 PM   5.76 s  3.66 s  Successful 200 OK
...
Yesterday at 12:17:06 AM  6 s     3.04 s  Successful 200 OK
```

오늘 00:17 항목은 없다(실패 기록도 없다). 500 응답 본문은 저장하지 않는 설정(Save responses 꺼짐)이라 볼 수 없다. 상세 화면 문구: "Internal server error: something went wrong on the destination server while handling the request."

cron-job.org 작업 설정 (읽기만 함): 시간대 Asia/Seoul, 날짜 1~31일·모든 요일·모든 달, 시 0~23, 분 17. POST 본문 `{"ref":"main","inputs":{"trigger":"schedule"}}`, 제한 시간 30초.

GitHub 상태 이력 (githubstatus.com RSS, 11-04 장애 "Incident with Pull Requests, Git Operations and Issues"):

```
Nov 4, 11:50 UTC Resolved
Nov 4, 11:43 UTC Monitoring - The degradation affecting Actions has been mitigated.
Nov 4, 11:30 UTC Update - The degradation affecting API Requests, Git Operations, Issues and Pull Requests has been mitigated.
Nov 4, 11:17 UTC Update - ... Some requests may fail or be delayed while we work to restore service.
Nov 4, 11:11 UTC Update - API Requests is experiencing degraded performance.
Nov 4, 09:50 UTC Update - Actions is experiencing degraded performance.
Nov 4, 09:49 UTC Investigating
```

## 원인 찾기

| 가설 | 확인 방법 | 결과 |
|---|---|---|
| 19:17 다나와 수집 실패 | Neon 스냅샷 오류 | 20개 모두 DNS 이름 풀이 실패 |
| 20:17 실행이 호출되지 않음 | Actions 실행 목록, cron-job.org 실행 기록 | 호출은 갔다. GitHub API가 500을 돌려줬다 |
| GitHub 쪽 장애 | githubstatus.com 이력 | 11-04 09:49~11:50 UTC 장애. 11:11 UTC부터 API Requests 저하 |
| 00:17 실행도 호출되지 않음 | Actions 실행 목록, cron-job.org 실행 기록과 설정 | cron-job.org 기록에 항목이 없다. 설정은 0시를 포함한다 |

- 실행 531은 19:17:33에 Neon에 실행 행을 만들었고, 19:21:14에 따로 시작한 연습 쇼핑몰 수집 단계(532)도 Neon에 연결해 저장했다. 두 시각에는 Neon 주소가 풀렸다. 그 사이(19:17~19:21)에 러너 DNS 전체가 멈췄는지, `prod.danawa.com` 이름 풀이만 실패했는지는 이 기록으로는 구분하지 못한다.
- 수집기에는 연결 오류 재시도가 없다 (`polite_http.py`). 상품마다 robots.txt부터 다시 받으려다 실패해서, 20개에 3분 36초(평균 약 11초)가 걸렸다.
- 다나와 수집 단계가 실패해도 연습 쇼핑몰 단계는 돌았다(ADR-0012 구조대로).

## 원인

- 20:17 KST(11:17 UTC): GitHub API 장애. 호출 시각이 장애 시간 안이고, 응답이 500이었다.
- 19:17 KST(10:17 UTC): 러너의 DNS 이름 풀이 실패. GitHub Actions 저하(09:50 UTC~) 시간 안이지만, 상태 이력에 DNS 언급은 없고 같은 시각 Neon 주소는 풀렸다. GitHub 장애 때문이라는 것은 추정이다.
- 00:17 KST(15:17 UTC): cron-job.org가 호출하지 않았다. GitHub 장애는 이미 끝난 뒤다. 이유는 모른다. status.cron-job.org는 내용을 읽지 못했다.

Healthchecks 흐름(시각으로 맞춘 추정, Healthchecks 기한 설정과 메일 본문은 보지 않음): 다나와는 19:21 fail 신호로 DOWN, 21:18 성공으로 UP (메일의 "1 hour, 5..."와 19:21→21:18 = 1시간 57분이 맞는다). 연습 쇼핑몰은 19:21 성공 뒤 20:17 실행이 없어 기한을 넘겨 DOWN, 21:19 성공으로 UP. 사용자가 보여 준 목록의 경고(!) 두 개는 00:17 누락 때문으로 보인다.

## 해결

코드와 설정은 바꾸지 않았다. 다음 정기 시각인 11-05 01:17 KST 실행은 정상이었다: Actions 279(16:17:08 UTC) success, Neon 실행 539 다나와 20/20, 540 연습 쇼핑몰 8/8.

검토한 선택지:

- (a) cron-job.org에 매시 47분 예비 호출 추가. `scheduler.decide()`는 정기 실행을 "가장 최근 정기 시각(예: 00:17) 이후 돈 적이 없으면 실행"으로 정하고, 다나와는 한 시에 한 번만 돈다(`hourly_limit_until`). 그래서 코드 변경 없이 17분이 빠진 시만 47분에 수집한다. 대신 건너뛰는 실행도 Actions 준비 단계가 돈다. 지금 한 달 약 1,860분(ADR-0012, 분 단위로 올려 세면 약 2,230분)에, 건너뛰는 실행을 1분으로 치면 최대 744분이 더해져 월 3,000분 한도에 가까워진다. 건너뛰는 실행 시간은 재지 않은 추정이다.
- (b) 수집기에 연결 오류 재시도. 19:17은 4분 가까이 이름 풀이가 실패했고 20:17·00:17은 실행 자체가 없어서, 짧은 재시도로는 세 번 중 어느 것도 막지 못한다고 봤다(Claude 판단).
- (c) 그대로 둔다. 외부 장애 때 그 시 수집이 빠지고 Healthchecks 메일로 안다.

사용자가 "예비호출은 안해도 될 거 같아"라고 해서 (c)로 했다.

## 배운 것

- Healthchecks 경고 하나에 원인이 여러 개 섞일 수 있다. 시 단위로 Actions 실행 목록, DB 실행 기록, cron-job.org 실행 기록을 나란히 놓고 보니 세 번이 각각 다른 곳(러너 DNS, GitHub API, cron-job.org)에서 끊겼다.
- Actions 실행 목록에 실행이 없을 때, 이 구조(ADR-0006)에서는 cron-job.org 기록을 봐야 GitHub가 거절했는지 호출이 안 갔는지 구분된다. cron-job.org는 호출을 건너뛴 때 실패 기록도 남기지 않았다.

## 남은 것

- 00:17 누락의 이유. 다시 일어나면 cron-job.org에 문의하거나 예비 호출을 다시 검토한다.
- 19:17 DNS 실패가 GitHub 장애와 관련이 있는지.
