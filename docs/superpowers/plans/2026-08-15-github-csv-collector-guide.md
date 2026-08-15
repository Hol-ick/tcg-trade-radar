# GitHub CSV 분석 카탈로그와 Collector 안내 탭

## 목표

GitHub Pages의 Market explorer가 저장소의 파티션 CSV 인덱스를 읽고 필요한 CSV만 선택적으로 불러오게 한다. 수집은 브라우저에서 실행하지 않고 로컬 데스크톱 앱에서 수행하므로 Collector 탭은 실행·내보내기·Git 반영·분석의 연결 절차를 안내한다.

## 확인된 제약

- 저장소에는 이 프로젝트의 휴대형 `Collector.exe`가 없다.
- `debug/run-kaitori.bat`가 PySide6 데스크톱 수집기의 현재 실행 진입점이다.
- 가상환경의 `kaitori-collector.exe`는 Python 콘솔 스크립트 shim이며 휴대형 앱으로 배포할 수 없다.
- GitHub Pages는 방문자의 로컬 EXE를 브라우저 보안 정책으로 실행할 수 없다.

## 구현 범위

1. `index/partitions.csv` 파싱 함수와 경로별 URL 생성을 추가한다.
2. Market explorer의 CSV 선택기에 GitHub CSV 카탈로그를 연결한다.
3. 게임·월·거래유형별 파티션을 행 수와 함께 선택할 수 있게 한다.
4. Collector 탭을 로컬 데스크톱 수집기 안내 화면으로 교체한다.
5. 실행 배치 파일, 데스크톱 문서, 공개 데이터 카탈로그 링크를 제공한다.
6. 빌드와 로컬/공개 페이지의 Git CSV 로딩 및 Collector 안내 화면을 검증한다.

## 추후 작업

- PyInstaller 또는 유사 도구로 휴대형 EXE를 별도 패키징하고 GitHub Release에 게시한다.
- Release 자산이 생기면 Collector 탭의 다운로드 링크를 Release 자산으로 교체한다.
- 수집 완료 후 자동으로 전처리·분할·Git 반영하는 운영 스크립트를 연결한다.
