# 6개월 거래글 수집 체크포인트

- 체크포인트 시각: 2026-08-14 17:38:52 KST
- 대상 기간: 2026-02-14 00:00:00 ~ 2026-08-13 17:09:45 KST
- 대상 게임: `tcggame`, `onepiececardgame`, `pokemoncardgame`, `digimontcg`, `vg`
- 수집 방식: 게임별 Python 프로세스, 상세글 동시 요청 4개, 요청 간격 0.25초
- 재개 방식: 동일 작업을 다시 실행해도 기존 source/post를 재사용하고 중복 연결을 피한다.
- 공개 스냅샷: 아직 생성하지 않음. 현재 SQLite와 로그는 로컬 감사용이며 저장소에는 포함하지 않는다.

## 보존된 코드 상태

- GitHub: `GITHUB:/Hol-ick/tcg-trade-radar`
- 체크포인트 직전 코드 커밋: `87c569a` (`perf: index repeated listing lookups`)
- 포함된 수집 안정화: 기존 source 재사용, 일시적 네트워크 오류 재시도, 상세글 동시 수집 제한, 반복 매물 조회 인덱스
- 검증 상태: 해당 커밋 직전 Python 테스트 79개 통과, `py_compile` 통과

## 중단 시점의 실제 수집량

| 게임 | 작업 ID | 상태 | source | 추출 행 | 댓글 | 가장 오래된 글 | 가장 최근 글 | 날짜 범위 단순 진행률 | 상한 초과 |
|---|---|---:|---:|---:|---:|---|---|---:|---:|
| `tcggame` | `job-f1150c3e1ecf` | failed | 4,487 | 26,831 | 7,676 | 2026-07-28 | 2026-08-13 | 8.9% | 0 |
| `onepiececardgame` | `job-c24cfb731683` | failed | 3,630 | 11,589 | 4,469 | 2026-07-12 | 2026-08-13 | 17.8% | 0 |
| `pokemoncardgame` | `job-86efe171cb4e` | failed | 3,525 | 18,748 | 4,513 | 2026-03-31 | 2026-08-13 | 75.0% | 0 |
| `digimontcg` | `job-ba4760d526d7` | failed | 3,513 | 15,189 | 4,647 | 2026-07-04 | 2026-08-13 | 22.2% | 0 |
| `vg` | `job-7c8460a65422` | failed | 3,519 | 19,058 | 4,436 | 2026-06-17 | 2026-08-13 | 31.7% | 0 |

`날짜 범위 단순 진행률`은 가장 오래된 수집 글 날짜를 기준으로 계산한 진행률이다. 페이지 누락 여부와 6개월 완전성은 아직 검증하지 않았다.

## 중단 원인

- `tcggame`, `onepiececardgame`, `pokemoncardgame`, `digimontcg`: `URLError: [Errno 11001] getaddrinfo failed`
- `vg`: 같은 네트워크 장애 뒤 `UnboundLocalError: cannot access local variable 'http_error' where it is not associated with a value`가 추가 발생
- 다섯 게임 모두 `2026-08-13 17:09:45 KST` 이후 글은 0건으로 확인했다.

## 다음 작업

1. 재시도 예외 처리의 `http_error` 미초기화 문제를 수정하고 단위 테스트를 추가한다.
2. 네트워크가 회복되면 같은 수집 작업을 재개해 기존 source를 활용한다.
3. 다섯 작업이 모두 완료된 뒤 기간 경계·중복·누락·댓글·상한 초과를 검증한다.
4. 검증을 통과한 경우에만 `web/public/data/collections/2026-02-14_2026-08-13` 공개 CSV/JSONL을 생성하고 GitHub에 반영한다.
