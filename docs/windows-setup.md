# Windows 새 환경 시작 안내

이 문서는 GitHub 저장소를 처음 받은 사용자가 TCG Trade Radar 데스크톱 수집기를 실행하기 위한 안내입니다.

현재 저장소에는 휴대형 `Collector.exe`가 포함되어 있지 않습니다. 수집기는 Python과 PySide6로 실행되며, `debug\*.bat` 파일이 설치·점검·실행을 연결합니다. GitHub Pages의 웹 화면은 로컬 PC의 배치 파일이나 EXE를 직접 실행할 수 없고, 공개 분석 CSV를 읽는 역할만 합니다.

## 필요한 것

- Windows 10 또는 Windows 11
- Python 3.11 이상
- Git으로 저장소를 받았거나 GitHub에서 ZIP으로 내려받은 프로젝트 폴더
- 최초 설치 시 Python 패키지와 Playwright 브라우저를 받을 인터넷 연결
- Chrome 또는 Edge가 이미 설치되어 있다면 Playwright Chromium 설치가 실패해도 실행할 수 있습니다.

Python을 설치할 때는 설치 화면의 `Add python.exe to PATH`를 선택하는 것이 좋습니다. Python 설치 후 새 명령 프롬프트를 열어야 `py` 또는 `python` 명령이 인식될 수 있습니다.

## 첫 실행: 가장 간단한 순서

프로젝트 폴더에서 아래 순서로 배치 파일을 실행합니다.

```text
debug\setup-trade-radar.bat
debug\checkhost.bat
debug\run-kaitori.bat
```

첫 번째 파일은 다음 작업을 자동으로 처리합니다.

- 저장소 위치를 배치 파일 기준으로 계산하므로 프로젝트를 어느 드라이브에 두어도 됩니다.
- `.venv` 가상환경을 생성합니다.
- `pyproject.toml`의 PySide6·Playwright 의존성을 설치합니다.
- 로컬 SQLite·로그가 저장될 `.audit` 폴더를 만듭니다.
- Playwright Chromium 설치를 시도합니다.
- 수집기 모듈을 컴파일해 설치 상태를 확인합니다.

설치가 끝나면 `checkhost.bat`가 Python·가상환경·PySide6·Playwright·브라우저·공개 갤러리 응답을 점검합니다. 그 뒤 `run-kaitori.bat`를 실행하면 별도 워커 주소나 브라우저 연결 없이 데스크톱 앱 안에서 직접 수집합니다.

설치가 이미 끝난 PC에서 `run-kaitori.bat`를 다시 실행하면 기존 `.venv`를 재사용합니다. 의존성이 빠졌으면 setup을 다시 호출해 보완합니다.

## 명령 프롬프트에서 실행하기

배치 파일을 더블클릭하지 않고 결과를 확인하려면 저장소 루트에서 실행합니다.

```powershell
debug\setup-trade-radar.bat
debug\checkhost.bat --skip-network
debug\run-kaitori.bat
```

Playwright Chromium을 별도로 받지 않고 이미 설치된 Chrome·Edge fallback만 확인하려면 다음처럼 설치를 생략할 수 있습니다.

```powershell
debug\setup-trade-radar.bat --skip-browser
```

`--skip-network`는 `checkhost`의 공개 주소 요청만 생략합니다. 설치 상태는 계속 검사합니다. `checkhost.py --json`을 사용하면 자동화나 문제 신고에 쓸 수 있는 구조화 결과를 얻을 수 있지만, HTML 본문·쿠키·토큰은 출력하지 않습니다.

## checkhost 결과 읽기

| 상태 | 의미 | 다음 행동 |
| --- | --- | --- |
| `정상` | 필요한 런타임 또는 주소가 응답함 | 계속 사용 |
| `빈 응답` | HTTP 응답은 왔지만 본문이 비어 있음 | 수집 로그에서 모바일 fallback·구조 변경 여부 확인 |
| `차단/제한` | 403·429 등 공개 읽기 요청이 제한됨 | 잠시 후 재시도하고 CAPTCHA·로그인 우회는 하지 않음 |
| `오류` | DNS·TLS·시간 초과 등 통신 실패 | 네트워크·보안 프로그램·프록시 확인 |
| `설치 필요` | Python·PySide6·Playwright·브라우저가 준비되지 않음 | `setup-trade-radar.bat` 재실행 |

`빈 응답`이나 `차단/제한`은 프로그램 설치 오류와 다른 상태입니다. 수집기는 공개 읽기 경로에서 데스크톱·모바일·브라우저 fallback을 구분하고 로그에 남기지만, 로그인·CAPTCHA 우회는 수행하지 않습니다.

## 데이터가 저장되는 위치

- `.venv\`: 이 프로젝트 전용 Python 환경
- `.audit\kaitori.sqlite3`: 수집 원문·추출행·댓글·로그·검토 상태를 저장하는 로컬 SQLite
- 앱에서 저장한 CSV: 사용자가 지정한 파일 위치
- `web\public\data\`: GitHub Pages가 읽는 공개 분석·주간 CSV

`.audit\`와 `.venv\`는 공유·커밋 대상이 아닙니다. 개인 토큰·쿠키·비밀번호를 `.env`나 문서에 넣지 마세요. 공개 데이터로 내보낼 때는 기존 CSV export 규칙을 사용하고 원문 HTML·개인 식별 정보를 공개 파티션에 복사하지 않습니다.

## GitHub Pages와 로컬 앱의 경계

GitHub Pages는 정적 웹 호스팅이므로 다음 작업을 수행하지 않습니다.

- 사용자의 PC에서 `bat`나 `exe` 실행
- 사용자의 SQLite 파일 읽기
- 원본 갤러리로 직접 수집 요청 전송
- 로컬 앱의 수집 로그 조회

실제 수집은 `run-kaitori.bat`로 로컬에서 수행합니다. 결과 CSV를 검토한 뒤 저장소의 공개 데이터 export 절차로 반영하면 GitHub Pages 시장 탐색기가 갱신된 CSV를 읽습니다.

## 문제 해결

### `Python 3.11 이상을 찾지 못했습니다.`

Python 3.11 이상을 설치하고 PATH 추가를 선택한 뒤 명령 프롬프트를 새로 엽니다. `py -3.11 --version` 또는 `python --version`으로 확인합니다.

### `PySide6` 또는 `playwright` 설치 실패

인터넷 연결과 Python 버전을 확인하고 `debug\setup-trade-radar.bat`를 다시 실행합니다. 회사·보안망에서 PyPI가 차단되면 네트워크 관리자에게 Python 패키지 저장소 접근을 요청해야 합니다. 임의의 DLL이나 실행 파일을 프로젝트 폴더에 복사하지 않습니다.

### Chromium 설치 실패

`debug\checkhost.bat --skip-network`를 실행해 Chrome 또는 Edge가 보이는지 확인합니다. 브라우저가 있으면 수집기의 자동 browser fallback을 사용할 수 있습니다. 둘 다 없고 Playwright 설치도 막혔다면 Chromium 설치가 가능한 네트워크에서 setup을 다시 실행합니다.

### 공개 주소가 `빈 응답` 또는 `차단/제한`

이는 설치 실패가 아닐 수 있습니다. 요청 간격·페이지 상한을 유지하고, 수집 앱의 단계별 로그에서 `empty`, `blocked`, `structure_changed`를 구분해 확인합니다. 로그인, CAPTCHA 입력 자동화, 게시글 작성은 지원 범위가 아닙니다.

### 앱 창이 바로 닫힘

더블클릭 대신 명령 프롬프트에서 `debug\run-kaitori.bat`를 실행해 오류를 확인합니다. 먼저 `debug\checkhost.bat --skip-network`를 실행하면 의존성 누락을 빠르게 찾을 수 있습니다.

## 관련 문서

- [데스크톱 앱 기능 안내](desktop-app.md)
- [프로젝트 README](../README.md)
- [공개 데이터 전처리 기준](preprocessing-quality.md)
