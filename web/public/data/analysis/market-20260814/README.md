# Partitioned market dataset

전처리 관측행을 게임·월·거래유형별로 중복 없이 나눈 공개 분석 데이터입니다.

- source rows: 163,818
- partitions: 54
- source date range: 2026-03-31T10:11:45+09:00 ~ 2026-08-13T17:09:45+09:00
- listing types: `sell` 판매, `buy` 구매, `trade` 교환, `unknown` 미분류

## 파일 사용 순서

1. `manifest.json`에서 스키마와 전체 행 수를 확인합니다.
2. `index/partitions.csv`에서 원하는 게임·월·거래유형 파티션을 찾습니다.
3. 전체 추세는 `summary/` 아래 집계 CSV를 사용합니다.

각 관측행은 `partitions/<game_id>/<year_month>/<listing_type>.csv` 한 파일에만 존재합니다. 따라서 게임별·월별·유형별 분석을 위해 같은 원본행을 여러 번 커밋하지 않습니다.
