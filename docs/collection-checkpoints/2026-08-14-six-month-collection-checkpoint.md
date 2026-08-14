# 6개월 거래글 수집 체크포인트

- 체크포인트 시각: 2026-08-14 17:38:52 KST
- 대상 기간: 2026-02-14 00:00:00 ~ 2026-08-13 17:09:45 KST
- 대상 게임: `tcggame`, `onepiececardgame`, `pokemoncardgame`, `digimontcg`, `vg`
- 수집 방식: 게임별 Python 프로세스, 상세글 동시 요청 4개, 요청 간격 0.25초
- 재개 방식: 동일 작업을 다시 실행해도 기존 source/post를 재사용하고 중복 연결을 피한다.
- 공개 스냅샷: 현재 체크포인트 기준 부분 수집분을 `web/public/data/collections/2026-02-14_2026-08-13`에 생성했다.
- 원본 보존본: 전체 SQLite를 `data/raw/collections/2026-02-14_2026-08-13/kaitori.sqlite3.part-*` 조각과 `raw-dataset-manifest.json`으로 Git LFS에 보존한다.

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

1. 네트워크가 회복되면 `python -B`로 같은 수집 작업을 재개해 기존 source를 활용한다.
2. 다섯 작업이 모두 완료된 뒤 기간 경계·중복·누락·댓글·상한 초과를 검증한다.
3. 반년 수집이 끝나면 같은 기간 디렉터리의 구조화 CSV/JSONL과 Git LFS 원본 DB를 갱신하고, manifest의 상태를 `complete`로 바꾼다.
4. 공개 분석 화면에 원본 DB의 닉네임·댓글·원문을 직접 노출하지 않는 범위를 확정한다.

## 체크포인트 이후 코드 수정

- `fetch_text_auto()`의 `HTTPError` fallback 경로에서 Python 예외 변수 수명이 끝난 뒤 참조하던 `UnboundLocalError`를 수정했다.
- 회귀 테스트를 먼저 실패시킨 뒤 수정 후 통과했다. `python -B -m pytest -q` 결과 85개 통과, `python -B -m compileall` 및 diff 검사도 통과했다.
- 수정 커밋 `0c39ac9`가 GitHub `main`에 반영됐다. 이동 전 경로가 박힌 오래된 `.pyc`가 확인되어 재개 실행과 검증은 `-B` 옵션을 사용한다.
