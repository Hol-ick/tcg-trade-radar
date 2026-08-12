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

## `POST /rows/:id/review`

```json
{ "action": "approve|reject|edit", "actor": "admin", "after_data": { "rarity": "울레" } }
```

승인·반려·수정은 `kaitori_reviews`에 append-only로 기록합니다. `approve`만 내보내기 대상이 됩니다.

## `POST /jobs/:id/export`

현재 `approved` 행만 내보내고 상태를 `exported`로 변경합니다. 응답은 `{ "job_id": "...", "rows": [...] }` 형태이며 각 행에 `buy_price_krw`를 포함합니다.

## `POST /jobs/:id/retry`

`failed` 또는 `completed` 작업을 `queued`로 되돌려 재실행합니다. source·row·review 유일성 제약으로 기존 결과와 이력을 보존합니다.
