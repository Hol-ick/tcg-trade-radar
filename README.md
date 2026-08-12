# TCG Trade Radar

디시인사이드 TCG 갤러리의 유저 거래 글을 모아 카드 거래 동향을 살펴보는 도구입니다.

현재는 별도 워커나 브라우저 연결 없이 Python 데스크톱 앱 하나로 실행합니다.
게임은 미리 등록된 5개 프리셋에서 고르고, 최근 7일의 판매·구매·교환 글을 수집합니다.

## 실행

Windows에서는 [`debug/run-kaitori.bat`](debug/run-kaitori.bat)을 실행합니다.

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

## 개발 확인

```powershell
python -m unittest discover -s tests -v
python -m compileall -q kaitori_collector debug tests scripts
```

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
