# TS-0003: 수집 워크플로 예약 실행이 돌지 않음

- 날짜: 2026-10-24
- 관련: #2, PR #3(병합 커밋 `53b977e`), ADR-0003
- 상태: 미해결

> 요약: 수동 실행은 성공하는데 매시 17분 예약 실행이 한 번도 돌지 않았다. GitHub은 건너뛴 예약 실행의 이유를 남기지 않아서 원인을 직접 확인할 수 없다.

## 증상

- 13:56 PR #3 병합으로 `collect.yml`이 main에 들어갔다. 바로 수동 실행했고 성공했다 (20/20, 1분 21초).
- 그 뒤 14:17, 15:17 예약 실행이 둘 다 돌지 않았다. 15:42에 Actions 목록을 봤을 때 실행은 수동 실행 1건뿐이었다.

```yaml
on:
  schedule:
    - cron: "17 * * * *"
  workflow_dispatch:
```

## 재현

병합 후 두 번 연속. 같은 파일의 수동 실행은 정상이다.

## 원인 찾기

| 가설 | 확인 방법 | 결과 |
|---|---|---|
| 예약 설정이 main에 없다 | `git show origin/main:.github/workflows/collect.yml` | 아님. cron이 main에 있다 |
| 워크플로가 비활성화돼 있다 | Actions 페이지의 비활성 표시 | 아님. 표시 없음, 수동 실행 정상 |
| 저장소에서 Actions가 막혀 있다 | CI, 수동 실행 이력 | 아님. 둘 다 돌았다 |
| 파일이 잘못돼서 GitHub이 무시한다 | 수동 실행 | 아님. 같은 파일로 수동 실행이 됐다 |
| GitHub Actions 장애 | githubstatus.com 장애 이력 | 2026-10-24 Actions 장애 공지 없음. 마지막은 10-23 |
| 부하로 지연·누락 | GitHub 문서 | 가능성 있음. 문서에 "can be delayed during periods of high loads", 부하가 심하면 "some queued jobs may be dropped". 밖에서 확인할 방법은 없다 |
| GitHub 쪽 예약 등록 문제 | GitHub 커뮤니티 토론 #185355 | 가능성 있음. 아래 |

GitHub 커뮤니티 토론 https://github.com/orgs/community/discussions/185355 :

- 2026-01-26 GitHub 직원 답변: 직전 주의 관련 변경을 되돌렸고, "Any commit pushed to the default branch will resync the impacted scheduled workflows."
- 2026-07 ~ 09에도 같은 증상 보고가 이어졌다. 비공개 저장소 사례가 여럿 있다. 커밋을 push해서 나아졌다는 사람도, 안 나아졌다는 사람도 있다. 예상 76회 중 5회만 돌았다는 보고도 있고, 그 사람은 외부 cron 서비스로 `workflow_dispatch`를 호출하는 방식으로 바꿨다.
- "무료 계정의 비공개 저장소에서는 예약 실행이 막힌다"는 주장도 있다 (https://dev.to/devactivity/github-actions-cron-schedules-uncovering-the-hidden-free-tier-hurdle-for-private-repos-223a). 출처가 없고 GitHub 문서나 직원 답변으로 확인되지 않았다. 이 프로젝트는 비공개 저장소, 무료 계정이다.

## 원인

확인하지 못했다. GitHub은 예약 실행을 건너뛴 이유를 기록하지 않는다.

## 해결

진행 중. 다음 순서로 확인한다.

1. 기본 브랜치에 커밋을 넣어 예약을 다시 동기화한다 (GitHub 직원 답변). 이 문서를 담은 PR을 main에 병합하는 것으로 한다.
2. 그다음 예약 시각(16:17)에 도는지 본다.
3. 그래도 안 돌거나 띄엄띄엄 돌면 ADR-0003 실행 위치를 다시 검토한다.

## 배운 것

- GitHub Actions 예약 실행은 문서상으로도 "늦어지거나 빠질 수 있는" 기능이다. ADR-0003을 쓸 때 그 문장을 읽었지만, 실제로 몇 시간씩 안 돌 수 있다는 것까지는 고려하지 않았다. 몇 주 연속 수집이 목적이면 예약이 실제로 돌았는지 확인하는 장치가 필요하다.
