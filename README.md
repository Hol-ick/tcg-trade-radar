# TCG Trade Radar

## 권장 실행: Windows 데스크톱 앱

실제 수집은 웹 페이지가 아니라 로컬 PySide6 앱 안에서 직접 실행됩니다. 별도 워커 연결은 필요하지 않습니다.

새로운 PC에서는 아래 파일을 순서대로 실행합니다.

```text
debug\setup-trade-radar.bat
debug\checkhost.bat
debug\run-kaitori.bat
```

이미 설정된 PC에서는 [`debug/run-kaitori.bat`](debug/run-kaitori.bat)만 실행하면 됩니다. 설치·점검·문제 해결은 [Windows 새 환경 시작 안내](docs/windows-setup.md), 앱 기능은 [데스크톱 앱 문서](docs/desktop-app.md)를 참고하세요.

디시인사이드 TCG 갤러리의 유저 거래 글을 모아 카드 거래 동향을 살펴보는 도구입니다. 수집·로그·SQLite 저장·CSV 내보내기는 모두 로컬 앱에 포함됩니다.

현재 저장소에는 휴대형 `Collector.exe`가 없습니다. 가상환경의 `kaitori-collector.exe`는 Python 콘솔 진입점 shim이므로 배포용 EXE로 간주하지 않으며, 새 환경 준비는 Git에 포함된 배치 파일을 사용합니다.

## GitHub Pages 분석 화면

GitHub Pages의 `Collector` 탭은 로컬 수집기를 직접 실행하는 기능이 아니라 데스크톱 앱 실행과 CSV 반영을 안내하는 화면입니다. 브라우저 보안상 방문자의 PC에서 `bat`, `exe`, 로컬 SQLite 또는 로컬 워커를 자동으로 시작할 수 없습니다.

## 실행

웹 콘솔·API를 개발하거나 기존 계약을 점검할 때만 로컬 워커를 직접 실행합니다.

```powershell
python -m kaitori_collector --serve --host 127.0.0.1 --port 8787 --db .audit\kaitori.sqlite3
```

다른 터미널에서 웹 콘솔을 실행합니다.

```powershell
pnpm --config.minimum-release-age=0 --dir web install
pnpm --config.minimum-release-age=0 --dir web dev --host 127.0.0.1 --port 5173
```

`http://127.0.0.1:5173`을 열면 정적 분석 화면을 확인할 수 있습니다. 실제 수집은 [`debug/run-kaitori.bat`](debug/run-kaitori.bat)을 사용하세요.

처음 실행하는 환경의 의존성 설치는 `python -m pip install -e .` 대신 [`debug/setup-trade-radar.bat`](debug/setup-trade-radar.bat)를 권장합니다. Chrome이 설치되어 있으면 자동 사용하며, 화면을 보면서 확인하려면 `TCG_TRADE_BROWSER_HEADLESS=0`을 설정합니다.

또는 프로젝트 폴더에서 다음 배치 파일을 실행합니다.

```text
debug\run-kaitori.bat
```

데스크톱 앱은 수집 전용으로 단순화되어 있습니다. 게임을 고르고 기간 프리셋 또는 직접 날짜를 선택한 뒤, 슬라이더로 최근 글 수를 조절해 수집을 시작합니다.
수집 중에는 목록 요청, 판매/구매/교환 분류, 원문 파싱, 저장 결과를 로그에서 확인할 수 있습니다.
완료된 행은 결과 표에서 확인하고 `CSV 저장`으로 바로 가져갈 수 있습니다. 로그는 `로그 복사`로 클립보드에 복사할 수 있습니다.

## 현재 기능

- 유희왕, 원피스 카드게임, 포켓몬 카드게임, 디지몬 카드게임, 뱅가드 프리셋
- 최근 7일 글 수집 및 페이지·게시물 상한
- 판매/거래 탭 제목 매칭
- 판매·구매·교환 의도 분류 및 충돌 시 검토 대기
- 카드명, 가격, 수량, 배송비 포함 여부 추출
- 공개 작성자 닉네임과 유동·고닉 표기 수집
- 게시글 댓글의 공개 닉네임·유형·본문·작성시각 수집
- 이미지에만 가격이 적힌 글의 검토 표시
- 수집 과정 상세 로그와 실패 원인 표시
- 수집 결과 검토 및 CSV 내보내기
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

## 웹 콘솔과 실제 수집

워커와 웹 화면을 각각 실행합니다.

```powershell
python -m kaitori_collector --serve --host 127.0.0.1 --port 8787 --db .audit\kaitori.sqlite3
pnpm --config.minimum-release-age=0 --dir web install
pnpm --config.minimum-release-age=0 --dir web dev --host 127.0.0.1 --port 5173
```

두 번째 터미널에서 웹 화면을 실행한 뒤 `http://127.0.0.1:5173`을 엽니다. `수집 시작`은 선택한 게임·기간·게시글 수를 Python 워커에 전달하고, 수집 중 로그와 결과를 화면에 표시합니다. 기간 기본값은 최근 7일일 뿐 별도 주간 수집 기능은 아닙니다.

가격이 이미지에만 있는 글은 자동 확정하지 않고 검토 대상으로 남기며, CAPTCHA나 차단 우회는 사용하지 않습니다.

## 분할 시장 분석 CSV

전처리된 시장 관측행은 [공개 데이터 카탈로그](web/public/data/analysis/market-20260814/)에서 게임·월·거래유형별 파티션으로 확인할 수 있습니다. 각 관측행은 `partitions/<game_id>/<year_month>/<listing_type>.csv` 한 곳에만 들어가며, `summary/`에는 게임별·월별·거래유형별 집계가 있습니다.

```powershell
python scripts/export_partitioned_market.py `
  --input .audit\preprocessed-market-20260814\observations.csv `
  --output-root web\public\data\analysis\market-20260814 `
  --replace
```

`listing_type`은 `sell` 판매, `buy` 구매, `trade` 교환, `unknown` 미분류입니다. `manifest.json`과 `index/partitions.csv`를 먼저 읽으면 필요한 파일만 선택할 수 있습니다.

## 범위와 주의사항

- 공개 게시글만 대상으로 합니다.
- 로그인, 게시글 작성, CAPTCHA 우회, 개인 거래 중개는 지원하지 않습니다.
- 요청 간 지연과 페이지·게시물 상한을 적용합니다.
- 원문 URL은 결과에서 확인할 수 있지만 전화번호·계좌번호를 수집·내보내지 않도록 설계합니다.
- 사이트 응답 차단이나 HTML 구조 변경이 발생하면 로그에 요청 단계와 원인을 남깁니다.

## 프로젝트 구조

```text
debug/              실시간 수집 화면과 일괄 수집 실행 파일
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
