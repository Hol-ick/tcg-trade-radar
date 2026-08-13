# 거래 데이터 전처리 품질 계층 구현 계획

**목표:** 원문은 보존하면서 이미지 전용 글, 거래 완료·예약 글, 가격 삭제 글, 구매 희망가 미기재, 묶음 가격을 통계에서 안전하게 분리한다.

## 정책

- `sources`는 게시글의 관측 상태를 저장한다: `active`, `completed`, `reserved`, `price_removed`, `image_only`, `unknown`.
- `rows`는 추출된 거래 행의 해석 상태를 저장한다: 가격 상태, 가격 범위, 가격 출처, 분석 가능 여부를 별도 필드로 보존한다.
- 가격 미기재·삭제는 `0원`이 아니라 공개 결과에서 `null`로 표현한다. 기존 SQLite의 호환 필드는 유지하되 통계는 관측 가격 필드를 사용한다.
- 구매글의 가격 없는 행은 수요 건수에는 포함하고 가격 통계에서는 제외한다.
- 묶음·복수 카드의 총액은 개별 카드 가격으로 쪼개지 않고 `bundle`로 제외한다.
- 거래 완료 가격은 과거 관측치로만 남기고 현재 매물·현재 가격 통계에서는 제외한다.
- 이미지 전용 글은 원문/이미지 개수/본문 길이를 `sources`에 남기고 거래 행을 추정 생성하지 않는다.

## 작업 1: 계약과 저장소

**파일:** `kaitori_collector/contracts.py`, `kaitori_collector/storage.py`, `migrations/005_preprocessing_quality.sql`

- 전처리 열의 타입과 기본값을 계약에 추가한다.
- 기존 DB에 열을 안전하게 추가하는 호환 마이그레이션을 넣는다.
- source 상태와 row 상태를 API/CSV/JSON에 노출한다.

## 작업 2: 판정기

**파일:** `kaitori_collector/preprocessing.py`, `kaitori_collector/parser.py`, `kaitori_collector/html.py`

- 제목/본문에서 완료·예약·가격 삭제 신호를 보수적으로 판정한다.
- 이미지 수와 본문 글자 수를 추출한다.
- 가격 출처·정확도·묶음 범위를 판정한다.
- 원문 가격이 없으면 `None` 관측값을 사용한다.

## 작업 3: 분석·내보내기·화면

**파일:** `kaitori_collector/service.py`, `kaitori_collector/storage.py`, `scripts/export_week_snapshot.py`, `web/src/...`

- 현재 매물과 과거 완료 거래를 분리한다.
- 품질 상태별 집계와 제외 사유를 요약에 포함한다.
- CSV/JSON에서 전처리 상태를 확인할 수 있게 한다.
- 화면은 가격 없음/완료/사진 검토/묶음 가격을 구분해 표시한다.

## 검증

- 전처리 판정의 독립적인 단위 테스트를 먼저 실패시키고 구현한다.
- 실제 `.audit/handoff-week.sqlite3` 샘플을 재분석해 상태 분포를 확인한다.
- `pytest`, Python 컴파일, 웹 lint/typecheck/build를 다시 실행한다.
- 변경을 `main`에 커밋하고 `origin/main`에 푸시한다.
