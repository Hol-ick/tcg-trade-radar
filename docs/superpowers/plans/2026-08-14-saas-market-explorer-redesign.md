# SaaS 마켓 익스플로러 리디자인 구현 계획

> 기준 레퍼런스: [shadcn/ui dashboard-01](https://ui.shadcn.com/blocks?category=dashboard)의 사이드바 + 인셋 콘텐츠 + 요약 카드 + 차트 + 데이터 테이블 구조.

## 목표

현재의 포스터형 화면을 업무용 SaaS 분석 도구로 바꾼다. 데이터 파싱·필터링·차트 계산 로직은 유지하고, 정보 위계와 조작 밀도를 대시보드에 맞게 재구성한다.

## 설계 결정

- 흰색 카드, 얇은 테두리, 12px radius, 중립적인 slate 색상과 indigo primary를 사용한다.
- 고정 사이드바에는 제품 내비게이션과 데이터 소스 상태를 둔다.
- 본문은 breadcrumb → 페이지 제목 → 데이터 액션 → 필터 툴바 → KPI → 차트 → 테이블 순서로 배치한다.
- 큰 히어로 문구와 장식용 원·형광색 카드를 제거하고, 숫자·상태·컨트롤을 우선한다.
- 모바일에서는 사이드바를 숨기고 필터·카드·차트를 단일 열로 쌓으며, 테이블은 가로 스크롤을 유지한다.

## 변경 범위

- `web/src/market-explorer.tsx`: SaaS 대시보드 정보 구조와 내비게이션 마크업
- `web/src/index.css`: 기존 CSV market lens 스타일을 SaaS 토큰과 반응형 레이아웃으로 교체
- 데이터 어댑터와 차트 계산은 변경하지 않음

## 검증

- `pnpm --dir web typecheck`
- `pnpm --dir web lint`
- `pnpm --dir web build`
- Playwright로 기본 CSV, 업로드, 검색, 수집기 링크, 콘솔, 데스크톱/모바일 렌더링 확인
