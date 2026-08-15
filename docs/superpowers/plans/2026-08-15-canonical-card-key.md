# 카드 키 단일 계약 구현 계획

> **실행 에이전트용:** 이 계획은 작업 단위별로 실행한다. 각 단계 후 검증 결과와 변경 범위를 확인한다.

**목표:** Python 전처리가 생성한 `card_key`를 웹 시장 탐색기가 그대로 사용하게 하고, `card_key`가 없는 구형 CSV도 최신 Python 정규화 규칙과 최대한 같은 결과를 내도록 한다.

**구조:** 분석 CSV에 `card_key`가 있으면 그것을 정본으로 사용한다. 구형 샘플처럼 키가 없는 CSV만 웹의 보수적 fallback 정규화를 사용하며, fallback은 Python의 거래 표현·수량·단가·배송비·가격·카드 코드 보존 규칙을 반영한다. export 계약 테스트는 canonical key가 파티션을 거쳐도 보존되는지 고정한다. HTML·광고·배송비·수량만 남은 오염 라벨은 `excluded`로 분류하되 원본 행은 보존한다.

**기술 스택:** Python 3, unittest/pytest, React 19, TypeScript, Vite, pnpm

## 공통 제약

- 원본 거래 행과 SQLite 스키마는 변경하지 않는다.
- `card_key`가 있는 CSV에서는 웹이 자체 정규화로 키를 덮어쓰지 않는다.
- `card_key`가 없는 구형 CSV는 기존 화면 호환을 위해 fallback으로 계속 표시한다.
- Python 수집기·개인정보 수집 범위·공개 원문 경계를 변경하지 않는다.
- React 변경 후 lint, typecheck, build를 모두 실행한다.

---

### 작업 1: Python export 계약을 테스트로 고정

**파일:**
- 수정: `tests/test_export_partitioned_market.py`
- 참고: `scripts/export_partitioned_market.py`

**인터페이스:**
- 사용: `export_partitioned_market(input_csv, output_root)`
- 검증: 출력 파티션의 `card_key`가 입력 관측행의 canonical key와 동일함

- [x] 파티션 출력 행에서 `card_key`가 입력값 그대로 유지되는 회귀 검증을 추가한다.
- [x] 기존 파티션 행 수·요약·manifest 검증을 유지한다.
- [x] `python -B -m pytest -q tests/test_export_partitioned_market.py`로 통과를 확인한다.

### 작업 2: 웹 분석기의 canonical key 우선 처리

**파일:**
- 수정: `web/src/lib/market-data.ts`

**인터페이스:**
- 제공: `normalizeCardName(value)`는 `card_key`가 없는 구형 CSV용 fallback 정규화 함수로 유지한다.
- 사용: `normalizeMarketRow(record, id)`는 `record.card_key`를 우선 선택한다.

- [x] Python 정규화와 동일한 거래 표현·수량·단가·배송비·가격 제거 규칙으로 fallback을 보강한다.
- [x] `card_name_normalized`가 있으면 표시명과 fallback의 우선 입력으로 사용한다.
- [x] CSV의 `card_key`를 소문자 locale 키로 변환해 `MarketRow.cardKey`에 저장한다.
- [x] 기존 샘플 CSV처럼 `card_key`가 없는 입력은 fallback으로 계속 처리한다.
- [x] 스크립트·광고·배송·수량 전용 라벨을 웹 분석 집계에서 제외하고 품질 필터로 복원 가능하게 한다.

### 작업 3: 정적·동작 검증

**파일:**
- 참고: `web/src/lib/market-data.ts`, `tests/test_normalization.py`, `tests/test_export_partitioned_market.py`

- [x] `python -B -m pytest -q` 실행 결과 `95 passed`를 확인한다.
- [x] `python -B -m compileall -q kaitori_collector scripts tests`를 확인한다.
- [x] 웹 `lint`, `typecheck`, `build`를 확인한다.
- [x] `git diff --check`를 확인한다.
- [x] 최신 파티션 CSV 선택·검색·품질 필터·모바일 레이아웃·콘솔·네트워크를 브라우저에서 확인한다.

### 작업 4: 커밋·원격 반영

**파일:**
- 수정: 작업 1~2의 파일과 이 계획 문서

- [x] `git status`와 diff를 검토한다.
- [x] 변경 파일만 명시적으로 stage한다.
- [x] 검증 결과를 확인한 뒤 `fix: use canonical card keys in market explorer`로 커밋한다.
- [x] `origin/main`에 push한다.
- [x] push 후 로컬 HEAD와 `origin/main`이 같은지 확인한다.
