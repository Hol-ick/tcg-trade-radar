# 분할 시장 CSV 공개 데이터 구현 계획

> **실행 에이전트용:** 이 계획은 현재 세션에서 실행한다. 각 작업 후 검증 결과를 확인하고 다음 작업으로 진행한다.

**목표:** 전처리 시장 관측 데이터를 게임·월·거래유형별 중복 없는 파티션 CSV와 게임별·월별·거래유형별 집계 CSV로 나누어 GitHub Pages가 소비할 수 있는 공개 데이터 카탈로그를 만든다.

**구조:** 안정된 `observations.csv` 스냅샷을 입력으로 사용한다. 각 관측행은 `partitions/<game_id>/<year_month>/<listing_type>.csv` 한 곳에만 기록하고, 분석용 집계표와 manifest/index는 별도로 생성한다. 기존 전체 전처리 CSV와 원본 SQLite는 변경하지 않는다.

**기술 스택:** Python 표준 라이브러리 `csv`, `json`, `pathlib`, `statistics`; 기존 pytest; GitHub Pages 정적 파일.

## 공통 제약

- 입력 스냅샷은 `.audit/preprocessed-market-20260814/observations.csv`로 고정한다.
- 거래유형 값은 `sell`, `buy`, `trade`, `unknown` 네 가지로 정규화한다.
- 날짜가 없거나 잘못된 행은 `unknown-date` 월 파티션으로 보존한다.
- 한 관측행은 파티션 CSV 하나에만 기록하며, 집계 CSV에는 복제하지 않는다.
- 공개 데이터의 각 파일은 100MB 미만이어야 한다.
- 기존 `data/*.csv`와 `.audit/` 산출물은 staging하지 않는다.

---

### 작업 1: 파티션 생성기와 테스트

**파일:**
- 생성: `scripts/export_partitioned_market.py`
- 생성: `tests/test_export_partitioned_market.py`
- 수정: `.gitignore`
- 생성: `docs/superpowers/plans/2026-08-15-partitioned-market-csv.md`

**인터페이스:**
- 제공: `export_partitioned_market(input_csv: Path, output_root: Path) -> dict[str, Any]`
- CLI: `python scripts/export_partitioned_market.py --input <csv> --output-root <dir>`
- 생성 파일: `manifest.json`, `README.md`, `index/partitions.csv`, `summary/by_game.csv`, `summary/by_month.csv`, `summary/by_listing_type.csv`, `summary/by_game_month.csv`, `summary/by_game_month_listing_type.csv`, `partitions/<game>/<month>/<type>.csv`

- [ ] **1단계: 실패하는 테스트 작성** — 게임·월·유형 파티션, 미상 날짜, 집계 합계, UTF-8 CSV 헤더를 검증한다.
- [ ] **2단계: 테스트가 실패하는지 확인** — `python -m pytest tests/test_export_partitioned_market.py -q` 실행 후 생성 모듈 부재로 실패해야 한다.
- [ ] **3단계: 최소 구현 작성** — 입력을 한 번 순회하면서 curated schema로 파티션에 쓰고, 카운터·수량·가격 후보·카드·판매자·날짜 범위를 집계한다.
- [ ] **4단계: 테스트 통과 확인** — `python -m pytest tests/test_export_partitioned_market.py -q`에서 전부 통과한다.

### 작업 2: 실제 스냅샷 산출물 생성

**파일:**
- 생성: `web/public/data/analysis/market-20260814/` 아래 공개 CSV·JSON·README
- 입력: `.audit/preprocessed-market-20260814/observations.csv`

**인터페이스:**
- `index/partitions.csv`의 `path`, `game_id`, `game_name`, `year_month`, `listing_type`, `rows`, `bytes`, `min_posted_at`, `max_posted_at`로 파일을 선택한다.
- `manifest.json`의 `source`, `counts`, `dimensions`, `schema`, `files`로 전체 데이터셋을 설명한다.

- [ ] **1단계:** 생성기를 실제 스냅샷에 실행한다.
- [ ] **2단계:** 파티션 행 합계가 입력 행 수와 일치하고, 각 행 ID가 정확히 한 번만 존재하는지 검사한다.
- [ ] **3단계:** 각 공개 파일 크기와 CSV 헤더·UTF-8 BOM·날짜 범위를 검사한다.

### 작업 3: Git 공개와 배포 검증

**파일:**
- 수정: `README.md` — 공개 데이터 카탈로그 사용법 추가
- 생성: `web/public/data/analysis/market-20260814/README.md` 및 산출물

- [ ] `pytest`, `compileall`, 생성기 검증을 실행한다.
- [ ] 공개 데이터만 명시적으로 staging하고 `git diff --cached --check`를 실행한다.
- [ ] 커밋 후 `origin/main`에 push한다.
- [ ] GitHub Actions와 공개 URL에서 manifest·CSV HTTP 200을 확인한다.

### 커밋 단위

```powershell
git add -- scripts/export_partitioned_market.py tests/test_export_partitioned_market.py README.md .gitignore docs/superpowers/plans/2026-08-15-partitioned-market-csv.md
git add -f -- web/public/data/analysis/market-20260814
git commit -m "feat: publish partitioned market datasets"
git push origin main
```
