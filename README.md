# TCG Trade Radar

## 주간 정적 수집 콘솔

웹 화면은 더 이상 로컬 HTTP worker나 브라우저 API를 호출하지 않습니다. 원본 게시판은 CORS를 제공하지 않기 때문에, GitHub Actions가 일회성 Python 수집을 실행하고 다음 정적 파일을 커밋합니다.

```text
web/public/data/weeks/<gallery_id>/<since>.json
web/public/data/weeks/<gallery_id>/<since>.csv
```

`since`부터 6일 뒤까지가 포함된 정확히 7일 범위입니다. 웹 화면의 `이전 주`, `다음 주`, `이번 주` 버튼은 이 범위를 7일씩 이동합니다. 화면의 `주간 수집 실행` 링크에서 `Collect weekly snapshot` workflow를 수동 실행할 수 있고, 매주 월요일에는 기본 TCG 갤러리가 자동 수집됩니다. 수집은 `python scripts/export_week_snapshot.py ...`로 한 번만 실행되며 서버를 띄우지 않습니다.

디시인사이드 TCG 갤러리의 유저 거래 글을 모아 카드 거래 동향을 살펴보는 도구입니다.

현재는 별도 워커나 브라우저 연결 없이 Python 데스크톱 앱 하나로 실행합니다.
게임은 미리 등록된 5개 프리셋에서 고르고, 최근 7일의 판매·구매·교환 글을 수집합니다.

## 실행

Windows에서는 [`debug/run-kaitori.bat`](debug/run-kaitori.bat)을 실행합니다.

처음 실행하는 환경은 프로젝트 폴더에서 `python -m pip install -e .`로 Playwright 의존성을 설치합니다. Chrome이 설치되어 있으면 자동 사용하며, 화면을 보면서 확인하려면 `TCG_TRADE_BROWSER_HEADLESS=0`을 설정합니다.

또는 프로젝트 폴더에서 다음 명령을 실행합니다.

```powershell
python debug/kaitori_app.py
```

앱의 첫 화면은 매물 탐색입니다. 카드명·게임·거래 유형·기간·정렬을 지정해 카드별 판매 매물과 구매 수요를 검색할 수 있습니다.
`수집·로그` 탭에서 게임과 최근 글 수를 입력하고 수집을 시작합니다.
수집 중에는 목록 요청, 판매/구매/교환 분류, 원문 파싱, 저장 결과를 로그에서 확인할 수 있습니다.
로그는 `전체 복사`로 바로 클립보드에 복사할 수 있습니다.

## 현재 기능

- 유희왕, 원피스 카드게임, 포켓몬 카드게임, 디지몬 카드게임, 뱅가드 프리셋
- 최근 7일 글 수집 및 페이지·게시물 상한
- 판매/거래 탭 제목 매칭
- 판매·구매·교환 의도 분류 및 충돌 시 검토 대기
- 카드명, 가격, 수량, 배송비 포함 여부 추출
- 공개 작성자 닉네임과 유동·고닉 표기 수집
- 게시글 댓글의 공개 닉네임·유형·본문·작성시각 수집
- 카드별 판매 매물·구매글 수·판매가 중앙값·수요 점수
- 보유 카드 목록을 입력한 구매 수요 탐색
- 일별 수요 스냅샷과 게임별 거래 동향
- 이미지에만 가격이 적힌 글의 검토 표시
- 수집 과정 상세 로그와 실패 원인 표시
- 결과 검토 및 CSV 내보내기
- SQLite 기반 원문·추출 행·검토 이력 보존

## 일주일치 일괄 수집

UI를 거치지 않고 5개 게임의 판매·구매·교환 글을 순서대로 수집하려면 다음을 실행합니다.

```powershell
python debug/run_week_collection.py
```

실패한 게임부터 다시 시도하려면 시작 인덱스를 지정할 수 있습니다.

```powershell
python debug/run_week_collection.py --start-index 3
```

## 갤러리 응답 사전 점검

운영 DB나 작업 이력을 만들지 않고 여러 갤러리의 목록 응답·말머리·차단 여부만 확인하려면 다음을 실행합니다.

```powershell
python debug/probe_galleries.py --gallery tcggame --gallery onepiececardgame --gallery pokemoncardgame --gallery digimontcg --gallery vg
```

이 점검은 응답이 비었거나 HTML 구조가 바뀐 경우를 `게시글 없음`으로 오인하지 않도록 상태를 구분해 JSON으로 출력합니다.

## 유희왕 샘플 수집

유희왕 갤러리의 최근 거래 글을 최대 10개까지 읽기 전용으로 점검하려면 다음을 실행합니다.

```powershell
python debug/run_yugioh_sample.py --max-posts 10
```

수집 전송은 `auto`가 기본값이며 데스크톱 HTTP 응답이 비면 DCInside 모바일 읽기 경로와 모바일 User-Agent로 다시 읽고, 그래도 실패할 때만 Playwright 브라우저를 사용합니다. 직접 선택하려면 `python debug/run_yugioh_sample.py --transport browser --max-posts 10`을 사용합니다. 브라우저가 설치된 경로가 자동 인식되지 않으면 `TCG_TRADE_BROWSER_EXECUTABLE`에 Chrome 실행 파일 경로를 지정합니다.

결과 JSON에는 게시글 작성자, 유동·고닉 유형, 댓글, 단계별 로그가 함께 포함됩니다. 댓글은 모바일 글 응답에 포함된 공개 댓글을 먼저 읽고, 필요한 경우 별도 공개 댓글 응답을 추가로 조회합니다.

## 개발 확인

```powershell
python -m unittest discover -s tests -v
python -m compileall -q kaitori_collector debug tests scripts
```

## 웹 Dev 수집과 CSV 저장

로컬 worker와 웹 화면을 함께 띄운 뒤 `http://127.0.0.1:5173/dev/`에서 작은 범위로 실제 수집을 실행할 수 있습니다.

```powershell
python -m kaitori_collector --serve --host 127.0.0.1 --port 8787 --db .audit\kaitori.sqlite3 --data-root data
pnpm --dir web dev --host 127.0.0.1 --port 5173
```

작업이 `completed`이고 결과 행이 있으면 결과 카드의 `CSV 저장` 버튼으로 `tcg-trade-radar-<job-id>.csv`를 내려받습니다. `GET /jobs/<job-id>/csv`는 검토 상태를 변경하지 않고 추출 행만 UTF-8 CSV로 반환하며, 원문 HTML은 포함하지 않습니다. 목록 응답 구조가 일시적으로 인식되지 않으면 데스크톱 응답을 모바일·브라우저 fallback으로 확인하고 bounded retry를 적용합니다.

수집 로그에 `원본 서버가 빈 응답을 반환했습니다`와 `status=200, content_length=0`이 표시되면 데스크톱 전송이 비어 모바일 읽기 경로로 전환되지 못한 상태입니다. 목록의 `판매·구매·거래` 글이 1페이지에 없을 수 있으므로 샘플 수집은 최근 5페이지까지 확인합니다. `python debug/probe_galleries.py --gallery tcggame`으로 갤러리별 응답을 확인할 수 있습니다. CAPTCHA나 차단 우회는 사용하지 않습니다.

## 범위와 주의사항

- 공개 게시글만 대상으로 합니다.
- 로그인, 게시글 작성, CAPTCHA 우회, 개인 거래 중개는 지원하지 않습니다.
- 요청 간 지연과 페이지·게시물 상한을 적용합니다.
- 원문 URL은 결과에서 확인할 수 있지만 전화번호·계좌번호를 수집·내보내지 않도록 설계합니다.
- 사이트 응답 차단이나 HTML 구조 변경이 발생하면 로그에 요청 단계와 원인을 남깁니다.

## 프로젝트 구조

```text
debug/              매물 탐색기, 수집 화면, 일괄 수집 실행 파일
kaitori_collector/  수집·파싱·저장·검토 핵심 코드
tests/              단위 테스트
docs/               API 계약 및 확장 기획
migrations/         SQLite 스키마
```

## API 탐색 엔드포인트

기존 작업 API와 함께 다음 조회 API를 제공합니다.

- `GET /market/listings`: 원문 매물 목록
- `GET /market/cards`: 카드별 판매·구매 요약
- `GET /market/snapshots`: 일별 동향 스냅샷
- `POST /market/snapshots`: 현재 수집 데이터로 스냅샷 생성
- `GET /jobs/{id}/comments`: 작업에 포함된 댓글 목록

카드 요약에는 원문 카드명과 별도로 거래 표현·수량·가격 꼬리표를 제거한 `card_name_normalized`가 포함됩니다. `sell_count`·`buy_count`는 매물 행 수, `sell_post_count`·`buy_post_count`는 게시글 수이며, `recent_buy_count`와 `demand_score`로 최근 수요를 구분합니다. `quality_status=needs_review`인 항목은 원문을 확인한 뒤 해석해야 합니다.
