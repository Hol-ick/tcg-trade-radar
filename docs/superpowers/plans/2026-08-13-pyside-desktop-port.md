# PySide6 데스크톱 포팅 구현 계획

**목표:** 로컬에서 수집·탐색·로그·CSV 저장을 모두 처리하는 단일 PySide6 프로그램을 제공한다.

**구조:** 기존 `JobService`와 `Repository`를 그대로 데이터 경계로 사용한다. 새 Qt 창은 수집 요청을 만들고 백그라운드 스레드에서 서비스를 실행하며, 메인 스레드에서 로그·결과·시장 요약을 갱신한다.

**기술 선택:** Python 3.11+, PySide6, Qt Style Sheet(QSS), SQLite, 기존 collector 서비스.

## 작업 1: 실행 가능한 데스크톱 앱 경계

**파일:**
- 생성: `debug/trade_radar_desktop.py`
- 수정: `pyproject.toml`, `debug/run-kaitori.bat`
- 테스트: `tests/test_desktop_port.py`

- [ ] 앱이 UI 의존성 없이 수집 요청을 만들고 금액·상태 표시값을 변환하는지 테스트한다.
- [ ] PySide6 앱 진입점과 단일 실행 배치 파일을 추가한다.

## 작업 2: 수집·로그·CSV 흐름

**파일:**
- 수정: `debug/trade_radar_desktop.py`
- 테스트: `tests/test_desktop_port.py`

- [ ] 선택된 게임·기간·게시글 수로 `JobRequest`를 만드는 테스트를 추가한다.
- [ ] 수집 스레드, 단계 로그, 원문 결과, CSV 저장 버튼을 연결한다.

## 작업 3: 탐색·판매자 정보 화면

**파일:**
- 수정: `debug/trade_radar_desktop.py`
- 테스트: `tests/test_desktop_port.py`

- [ ] 카드 시장 요약과 판매자 위험 요약을 표시할 모델 변환을 테스트한다.
- [ ] 카드 탐색, 보유 카드 수요, 거래 동향, 판매자 활동을 탭으로 제공한다.

## 작업 4: 검증과 배포 준비

**파일:**
- 수정: `README.md`

- [ ] Python 테스트·컴파일을 실행한다.
- [ ] Qt 오프스크린 기동 확인을 실행한다.
- [ ] 실행 방법을 문서화하고 main에 반영한다.
