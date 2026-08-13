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

행의 전처리 필드:

```text
post_status, price_status, price_scope, price_origin,
analysis_status, card_match_status
```
