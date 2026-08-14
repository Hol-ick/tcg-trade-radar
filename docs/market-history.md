# 시장 이력 데이터 계약

그래프 UI를 만들기 전에 수집 데이터가 보존해야 하는 시간 축을 고정한다. 그래프는 아직 이 문서의 범위가 아니다.

## 시간 의미

- `event_date`: 게시글의 `posted_at`에서 파생한 시장 이벤트 날짜. 과거 게시글의 가격·수요 활동 추이를 볼 때 사용한다.
- `observed_date`: 게시글 버전의 `fetched_at`에서 파생한 관측 날짜. 반복 수집으로 실제 공급·수요 재고가 어떻게 바뀌었는지 볼 때 사용한다.
- `observed_at`: `observed_date`의 원본 ISO-8601 시각이다.
- `updated_at`: 전처리·검수로 변경될 수 있으므로 시간 축으로 사용하지 않는다.

## 원천 관측

`kaitori_market_observations`는 게시글 버전(`source_id`)과 추출 행(`row_id)의 조합마다 하나의 관측을 저장한다. 내용이 바뀐 같은 게시글은 `content_hash`가 달라져 새 source version이 되므로 기존 가격을 덮어쓰지 않는다.

각 관측에는 카드 키, 판매자, 매도·매수·교환 의도, 수량, 관측 가격, 가격 품질(`price_status`·`price_scope`), 게시글 상태와 분석 품질을 함께 저장한다. 가격이 없거나 묶음 가격인 행도 원천 관측으로 남기되 가격 통계에는 포함하지 않는다.

`card_match_status`와 `review_status`도 함께 보존한다. 따라서 화면은 `matched`만 보는 엄격 모드, `candidate`까지 보는 탐색 모드, `needs_review`를 별도 표시하는 검수 모드를 선택할 수 있다. 현재 수집분에는 아직 `candidate`·`unmatched`가 섞여 있으므로 품질 필터 없이 그래프를 그리지 않는다.

## 일별 집계

`kaitori_market_daily`는 `(gallery_id, card_key, event_date, observed_date)` 단위의 그래프용 집계다.

- 공급: `sell` 행의 게시글 수·수량·사용 가능한 가격 통계
- 수요: `buy` 행의 게시글 수·수량·사용 가능한 희망 가격 통계
- 보조: 교환 수, source 수, seller 수, 검수 필요 수, 품질 상태
- 공급·수요 수량은 행의 `quantity`를 합산하고, 가격 중앙값은 `usable + per_card + exact/estimated`만 사용한다.
- `post_status != active`, `context_only`, `excluded` 행은 현재 시장 집계에서 제외한다.

## 운영 규칙

```powershell
python scripts/materialize_market_history.py --db .audit\kaitori.sqlite3
```

이 명령은 관측 테이블과 일별 집계를 멱등적으로 다시 만든다. 수집 작업 완료 시에도 같은 갱신 경로가 실행되므로, 향후 주기 수집이 쌓이면 `observed_date` 축으로 재고 추이를 만들 수 있다.
