# TCG Trade Radar 데스크톱 앱

실제 수집은 이 앱 내부에서 직접 실행됩니다. 별도의 워커 주소, 브라우저 프록시, GitHub Pages 연결은 필요하지 않습니다.

현재 저장소에는 휴대형 `Collector.exe`가 포함되어 있지 않습니다. `debug\run-kaitori.bat`가 프로젝트 가상환경의 PySide6 데스크톱 앱을 실행하며, GitHub Pages의 Collector 탭은 이 로컬 실행 절차와 CSV 반영 흐름을 안내합니다.

## 실행

새 PC에서는 먼저 설치·점검 배치 파일을 실행합니다.

```text
debug\setup-trade-radar.bat
debug\checkhost.bat
```

그 다음 프로젝트 폴더에서 앱 실행 파일을 엽니다.

```text
debug\run-kaitori.bat
```

`setup-trade-radar.bat`가 Python 3.11 이상을 확인하고 `.venv`에 의존성을 설치합니다. 수동 설치가 필요한 경우에만 다음 명령을 사용합니다.

```powershell
python -m pip install -e .
```

새 환경 전체 절차와 오류 해석은 [Windows 새 환경 시작 안내](windows-setup.md)를 참고하세요.

## 화면 구성

- 대시보드: 최근 카드·구매 수요·판매 매물·주의 판매자 요약
- 실시간 수집: 게임·기간·최근 글 수 설정, 수집 로그, 이번 결과 CSV 저장
- 매물 탐색: 카드별 판매·구매·가격·수요 요약과 CSV 저장
- 보유 카드 수요: 카드 목록에서 구매글이 있는 카드를 찾음
- 거래 동향: 수집 데이터로 일별 스냅샷을 생성하고 조회
- 판매자 신호: 반복 등록과 검토 신호를 우선순위로 표시

수집·원문·댓글·판매자 신호는 로컬 SQLite 파일 `.audit\kaitori.sqlite3`에 저장됩니다.
