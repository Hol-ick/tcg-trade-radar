# 카이토리 워커 API 계약

기본 주소는 `http://127.0.0.1:8787`이며, `KAITORI_API_TOKEN`이 설정된 환경에서는 `/health`를 제외한 요청에 `Authorization: Bearer <token>`이 필요합니다.

## `GET /health`

인증 없이 연결 상태와 워커 버전을 확인합니다.

```json
{ "version": "0.1.0" }
```

## `POST /jobs`

```json
{
  "gallery_id": "tcggame",
  "gallery_url": "https://gall.dcinside.com/mgallery/board/lists?id=tcggame",
  "subject": "판매",
  "since": "2026-08-01",
  "until": "2026-08-12",
  "max_posts": 200,
  "max_pages": 1,
  "delay": 1.0,
  "buy_rate": 60,
  "keep_raw": true,
  "review_unmatched": true
}
```

`max_posts`는 1~200, `max_pages`는 1~20, `delay`는 0 이상, `buy_rate`는 0~100입니다. 응답은 관리자 화면의 두 계약을 모두 만족하도록 다음처럼 반환합니다.

```json
{ "job_id": "job-abc123", "id": "job-abc123" }
```

## `GET /jobs/:id`

```json
{
  "id": "job-abc123",
  "state": "queued|running|completed|failed",
  "counts": {
    "sources": 3,
    "rows": 8,
    "parsed": 4,
    "needs_review": 4,
    "approved": 0,
    "rejected": 0,
    "exported": 0
  },
  "worker_version": "0.1.0",
  "last_success_at": null,
  "error_message": null
}
```

## `GET /jobs/:id/results`

검토 대상까지 포함한 행을 반환합니다. `?approved_only=true`를 붙이면 `approved`와 이미 내보낸 `exported` 행만 반환합니다. 원문 HTML은 포함하지 않고, `post_url`/`source_url`과 `raw_line`만 관리자 감사용으로 제공합니다.

각 행은 기존 `ExtractedRow` 필드에 더해 `card_name`, `card_code`, `review_status`, `source_url`, `buy_price_krw`, `exportable` 별칭을 제공합니다. `shipping_included`는 `included`, `separate`, `unknown` 중 하나입니다.

## `GET /jobs/:id/logs`

목록 요청·응답·파싱·저장 단계의 작업 로그를 반환합니다. `?limit=500`으로 최대 개수를 조절할 수 있습니다.

```json
{
  "job_id": "job-abc123",
  "logs": [
    {
      "id": 1,
      "created_at": "2026-08-12T12:00:00+09:00",
      "level": "warning",
      "step": "list",
      "message": "목록 글 행을 찾지 못함 · 차단 응답 또는 HTML 구조 변경 가능",
      "details": { "characters": 1280 }
    }
  ]
}
```

## `GET /market/listings`

매물 탐색용 원문 단위 결과를 반환한다. 인증이 설정된 서버에서는 기존 작업 API와 같은 Bearer 토큰이 필요하다.

지원 쿼리: `q`, `game_id`, `listing_type=sell|buy|trade|unknown`, `since`, `until`, `min_price`, `max_price`, `status`, `sort=recent|price_asc|price_desc|demand`, `limit`.

```json
{
  "rows": [
    {
      "card_name_raw": "블루아이즈",
      "listing_type": "buy",
      "price_type": "wanted",
      "price_krw": 30000,
      "intent_confidence": 0.84,
      "post_url": "https://..."
    }
  ]
}
```

## `GET /market/cards`

카드별 판매·구매 표본을 집계한다. `q`, `game_id`, `listing_type`, `since`, `until`, `sort`, `limit`을 지원한다.

```json
{
  "cards": [
    {
      "card_key": "블루아이즈",
      "sell_count": 2,
      "buy_count": 6,
      "sell_price_median": 31000,
      "wanted_price_median": 29000,
      "demand_status": "hot_demand",
      "demand_score": 3.0,
      "evidence": "최근 데이터 구매글 6건 / 판매 매물 2건"
    }
  ]
}
```

가격이 없는 구매글도 `buy_count`와 수요 표본에는 포함되며 `wanted_price_median`은 `null`일 수 있다.

추가 분석 필드:

- `card_name_normalized`: 분석용 정규화 카드명. 원문을 대체하지 않는다.
- `sell_post_count`, `buy_post_count`: 거래 행이 속한 고유 게시글 수.
- `sell_quantity`, `buy_quantity`: 수집된 수량 합계.
- `recent_sell_count`, `recent_buy_count`: 기준일로부터 7일 이내의 거래 행 수.
- `demand_ratio`: 전체 구매 행 수를 판매 행 수로 나눈 비율.
- `demand_score`: 최근성 가중 구매량을 최근성 가중 판매량으로 나눈 값.
- `quality_status`: `observed`, `low_sample`, `needs_review` 중 하나.

최근성 가중치는 7일 이내 1.0, 8~30일 0.5, 그 이전 0.25이며, 날짜가 없는 행은 수요 건수에는 포함하되 최근성 점수에는 포함하지 않는다.

## `POST /rows/:id/review`

```json
{ "action": "approve|reject|edit", "actor": "admin", "after_data": { "rarity": "울레" } }
```

승인·반려·수정은 `kaitori_reviews`에 append-only로 기록합니다. `approve`만 내보내기 대상이 됩니다.

## `POST /jobs/:id/export`

현재 `approved` 행만 내보내고 상태를 `exported`로 변경합니다. 응답은 `{ "job_id": "...", "rows": [...] }` 형태이며 각 행에 `buy_price_krw`를 포함합니다.

## `POST /jobs/:id/retry`

`failed` 또는 `completed` 작업을 `queued`로 되돌려 재실행합니다. source·row·review 유일성 제약으로 기존 결과와 이력을 보존합니다.
