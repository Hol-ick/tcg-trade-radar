# 거래 데이터 전처리 품질 계층

수집 결과는 원문을 보존한 채 다음 상태를 별도로 저장한다.

- 게시글: `active`, `completed`, `reserved`, `price_removed`, `image_only`, `unknown`
- 가격: `exact`, `estimated`, `missing`, `removed`
- 가격 범위: `per_card`, `per_quantity`, `bundle`
- 분석 상태: `usable`, `needs_review`, `context_only`, `excluded`

가격이 없는 글은 API와 CSV에서 `price_krw: null`로 표현한다. 구매글은 가격이 없어도 수요 건수에는 포함하지만 가격 중앙값에서는 제외한다. 거래완료·예약·사진 전용 글과 묶음 가격은 현재 카드별 매물 통계에서 제외하고 원문 확인용으로 남긴다.

기존 DB 재처리:

```powershell
python scripts/reprocess_quality.py --db .audit\handoff-week.sqlite3
```

## 수량 표기와 가격 후보 분리

거래글의 `이상한사탕1`, `하솔3 3500`, `레드카드 1 2000`, `나옹 x 2` 같은 표현은 숫자 하나만 보고 가격으로 확정하지 않는다.

- 카드명에 붙은 1~99의 숫자, `x 2`, `2장`·`2매`·`2개`는 수량 후보로 분리한다.
- 카드 세트 코드인 `BT9-098`, `ex9`, `Lm2`와 `1.6` 같은 소수 가격은 수량으로 분리하지 않는다.
- 수량만 있고 가격이 없으면 행을 버리지 않고 `price_status=missing`, `price_scope=unknown`, `review_status=needs_review`로 남긴다.
- `1.4`·`3.5` 같은 소수 단위 없는 가격은 만원 단위 추정으로, `2000`·`3500` 같은 네 자리 정수는 원 단위 추정으로 기록한다.
- `장당`, 여러 카드, 일괄 가격은 가격을 읽더라도 자동 가격 통계에서는 검토 대상으로 남긴다.

기존에 공개한 분할 CSV를 원본 행 수 그대로 재계산하려면 별도 출력 위치에서 먼저 실행한다. 원본 SQLite와 기존 공개 데이터는 덮어쓰지 않는다.

```powershell
python scripts/reparse_partitioned_market.py `
  --input-root web\public\data\analysis\market-20260814 `
  --output-root .audit\reprocessed-market-20260815
```

재처리 결과의 `reparse-report.json`에는 행 수, 수량 복구 수, 가격 미기재 전환 수와 샘플 URL이 기록된다. 결과를 확인한 뒤 공개 데이터 교체가 필요할 때만 `export_partitioned_market.py`의 산출물을 `web/public/data/analysis/`에 반영한다.

행의 전처리 필드:

```text
post_status, price_status, price_scope, price_origin,
analysis_status, card_match_status
```
