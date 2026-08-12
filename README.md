# TCG Trade Radar

디시인사이드 TCG 갤러리의 유저 거래 글을 모아 카드 거래 동향을 살펴보는 도구입니다.

현재는 별도 워커나 브라우저 연결 없이 Python 데스크톱 앱 하나로 실행합니다.
게임은 미리 등록된 5개 프리셋에서 고르고, 최근 7일의 판매·거래 글을 수집합니다.

## 실행

Windows에서는 [`debug/run-kaitori.bat`](debug/run-kaitori.bat)을 실행합니다.

또는 프로젝트 폴더에서 다음 명령을 실행합니다.

```powershell
python debug/kaitori_app.py
```

앱에서 게임을 선택하고 최근 글 수를 입력한 뒤 `수집 시작`을 누르면 됩니다.
수집 중에는 목록 요청, 판매/거래 탭 매칭, 원문 파싱, 저장 결과를 로그에서 확인할 수 있습니다.
로그는 `전체 복사`로 바로 클립보드에 복사할 수 있습니다.

## 현재 기능

- 유희왕, 원피스 카드게임, 포켓몬 카드게임, 디지몬 카드게임, 뱅가드 프리셋
- 최근 7일 글 수집 및 페이지·게시물 상한
- 판매/거래 탭 제목 매칭
- 카드명, 가격, 수량, 배송비 포함 여부 추출
- 이미지에만 가격이 적힌 글의 검토 표시
- 수집 과정 상세 로그와 실패 원인 표시
- 결과 검토 및 CSV 내보내기
- SQLite 기반 원문·추출 행·검토 이력 보존

## 일주일치 일괄 수집

UI를 거치지 않고 5개 게임을 순서대로 수집하려면 다음을 실행합니다.

```powershell
python debug/run_week_collection.py
```

실패한 게임부터 다시 시도하려면 시작 인덱스를 지정할 수 있습니다.

```powershell
python debug/run_week_collection.py --start-index 3
```

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
debug/              데스크톱 앱과 일괄 수집 실행 파일
kaitori_collector/  수집·파싱·저장·검토 핵심 코드
tests/              단위 테스트
docs/               API 계약 및 확장 기획
migrations/         SQLite 스키마
```
