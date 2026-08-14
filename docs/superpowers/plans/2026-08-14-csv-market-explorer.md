# CSV 시장 분석 도구 구현 계획

> **실행 방식:** 이 계획은 현재 세션에서 단계별로 구현하고 각 단계마다 테스트한다.

**목표:** GitHub Pages의 기본 화면을 CSV 기반 TCG 시장 분석 도구로 바꾸고, 기존 실시간 수집 콘솔은 `/dev` 경로로 보존한다.

**구조:** 정적 웹앱이 샘플 CSV를 `/data/analysis/`에서 읽고, 사용자가 선택한 CSV는 브라우저에서만 파싱한다. 데이터는 `MarketRow` 계약으로 정규화한 뒤 모든 카드·판매자·차트·표가 같은 필터 결과를 공유한다. 외부 API와 서버 저장은 사용하지 않는다.

**시각 방향:** 게시판의 거친 원문과 시장 계기판을 결합한다. 종이색 바탕(`#f4f0e7`), 잉크색(`#15201b`), 코랄(`#ff6b57`), 라임(`#d9ff7a`), 민트(`#8fe3c5`)를 사용하고, 숫자는 데이터 계기판처럼 조밀하게 배치한다. 한 가지 시각적 서명은 날짜별 수요·공급 막대 위에 놓이는 라임색 `market pulse` 선이다.

```text
┌─────────────────────────────────────────────────────────────┐
│ TCG TRADE RADAR        CSV 이름 / 행 수       CSV 열기  수집기 │
├───────────────┬─────────────────────────────────────────────┤
│ FILTERS       │ MARKET PULSE                                │
│ 카드 검색     │ 요약 수치 4개                                │
│ 거래 의도     │ 가격 추이 SVG                               │
│ 품질/날짜     │ 수요 · 공급 SVG                             │
│               ├─────────────────────────────────────────────┤
│ 데이터 안내   │ TOP CARDS 표 + 판매자/원문 링크               │
└───────────────┴─────────────────────────────────────────────┘
```

## 작업 1: 데이터 계약과 CSV 어댑터

**파일:** `web/src/lib/market-data.ts`, `web/src/lib/types.ts`

- legacy CSV(`card_name`, `price_krw`)와 전처리 CSV(`card_name_raw`, `price_krw_observed`, `listing_type`)를 같은 `MarketRow`로 변환한다.
- 따옴표·쉼표·줄바꿈이 들어간 CSV를 표준 파서 없이 처리한다.
- 거래 의도가 없는 legacy 행은 제목·원문에서 판매/구매/교환을 보수적으로 추론하고 `unknown`을 보존한다.
- 가격이 없거나 0인 행은 거래량에는 남기고 가격 통계에서는 제외한다.
- 날짜·판매자·카드명·품질 상태를 차트와 표가 공통으로 사용한다.

## 작업 2: 분석 화면

**파일:** `web/src/market-explorer.tsx`, `web/src/components/market-charts.tsx`, `web/src/App.tsx`

- 기본 경로는 번들된 `tcggame-sales-50-20260812.csv`를 로드한다.
- CSV 선택/드롭으로 새 파일을 메모리에서 교체한다.
- 검색어, 거래 의도, 품질, 날짜 범위를 하나의 필터 상태로 관리한다.
- 필터 결과를 요약 수치, 가격 중앙값 추이, 수요·공급 수량 추이, 카드별 표에 동시에 반영한다.
- 기존 `LiveConsole`는 `/dev`와 `?page=collector`에서 유지한다.

## 작업 3: 스타일과 정적 데이터

**파일:** `web/src/index.css`, `web/public/data/analysis/tcggame-sales-50-20260812.csv`, `web/public/data/analysis/tcggame-live-20260812.csv`

- 분석 화면 전용 반응형 레이아웃과 키보드 포커스 스타일을 추가한다.
- 기본 샘플 CSV를 정적 자산으로 배포한다.
- 모바일에서는 필터가 상단 접이식 영역으로 내려가고 차트는 가로 스크롤 없이 읽히게 한다.

## 작업 4: 검증과 게시

- `pnpm --dir web lint`
- `pnpm --dir web typecheck`
- `pnpm --dir web build`
- Playwright로 기본 CSV 로드, 검색/필터, 파일 선택, 차트 렌더링, 모바일 폭을 확인한다.
- GitHub Pages 산출물이 `/tcg-trade-radar/` base path에서 CSV를 읽는지 확인한다.
