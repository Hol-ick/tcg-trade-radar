# TCG Trade Radar 확장 구현 계획

**목표:** 판매 가격 수집기를 판매·구매·교환 매물 탐색기와 카드별 수요·동향 화면으로 확장한다.

**구조:** 기존 `ExtractedRow`와 작업 API는 하위 호환으로 유지하고, 거래 의도·카드 요약·일별 스냅샷을 별도 필드와 조회 계층으로 추가한다. 데스크톱 앱은 수집 기능을 유지하면서 매물 탐색, 보유 카드 수요, 동향 탭을 기본 화면에 추가한다.

**기술 스택:** Python 3.11 표준 라이브러리, SQLite, tkinter, 기존 unittest.

## 공통 제약

- 공개 게시글만 수집하며 로그인·CAPTCHA 우회·게시글 작성·자동 거래는 구현하지 않는다.
- `ExtractedRow` 기존 필드는 유지하고 새 필드는 기본값을 제공한다.
- `needs_review` 자료는 자동 승인하거나 수요 근거에서 숨기지 않는다.
- `.audit`, SQLite, 토큰·환경 파일의 비밀값은 Git에 올리지 않는다.

### 작업 1: 거래 의도와 표준 매물 레코드

**파일:** `kaitori_collector/intent.py`, `contracts.py`, `parser.py`, `storage.py`, `tests/test_intent.py`, `tests/test_parser.py`

- [ ] 판매·구매·교환 신호와 말머리 우선순위를 테스트한다.
- [ ] `listing_type`, `intent_confidence`, `price_type`, `review_reason`을 추출 결과와 SQLite에 보존한다.
- [ ] 기존 스키마에는 안전한 `ALTER TABLE`을 적용하고 기존 행의 의도를 `unknown`으로 둔다.

### 작업 2: 매물 조회와 수요 집계

**파일:** `storage.py`, `service.py`, `api.py`, `tests/test_market.py`, `migrations/003_market_explorer.sql`

- [ ] 카드·게임·거래 유형·기간·가격·정렬 필터의 조회 테스트를 작성한다.
- [ ] 카드별 판매 수·구매글 수·가격 범위·중앙값·수요 상태·설명 가능한 수요 점수를 계산한다.
- [ ] 일별 스냅샷 저장 및 동향 조회 API를 제공한다.

### 작업 3: 탐색기 데스크톱 화면

**파일:** `debug/kaitori_app.py`

- [ ] 기본 탭을 매물 탐색으로 만들고 수집 탭에 기존 로그·검토 기능을 보존한다.
- [ ] 카드 검색, 판매/구매/교환 필터, 기간 필터, 가격 정렬을 연결한다.
- [ ] 보유 카드 목록을 입력해 구매 수요가 있는 카드와 근거를 표시한다.
- [ ] 게임별 동향 표와 스냅샷 새로고침을 연결한다.

### 작업 4: 검증과 인수인계

**파일:** `README.md`, `docs/api-contract.md`, AIHub linked worklog

- [ ] 전체 unittest, compileall, API smoke 테스트를 실행한다.
- [ ] fixture로 판매·구매·교환 혼합글, 가격 없는 구매글, 중복 수집을 검증한다.
- [ ] GitHub `main`에 확인된 변경만 커밋·푸시하고 AIHub worklog에 결과·검증·남은 작업을 기록한다.
