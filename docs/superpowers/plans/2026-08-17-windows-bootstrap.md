# Windows 새 환경 부트스트랩 도구 구현 계획

> **실행 에이전트용:** 이 계획은 작업 단위별로 실행한다. 현재 세션에서 각 검토 지점을 확인하며 구현한다.

**목표:** Git 저장소를 처음 받은 Windows 사용자가 배치 파일 하나로 Python 가상환경·프로젝트 의존성·로컬 데이터 폴더를 준비하고, `checkhost` 점검으로 실행 가능 상태와 공개 수집 대상 연결 상태를 확인한 뒤 데스크톱 앱을 바로 실행하게 한다.

**구조:** `debug/setup-trade-radar.bat`가 저장소 위치를 스스로 계산하고 `.venv`를 생성·설정한다. `debug/checkhost.bat`는 설치된 런타임·패키지·브라우저·저장 폴더·공개 갤러리 응답을 읽기 전용으로 검사하고, 순수 표준 라이브러리 Python 모듈이 결과를 안정적으로 분류한다. 기존 `run-kaitori.bat`는 준비가 안 된 새 환경에서 설치 도구를 한 번 호출한 뒤 반드시 가상환경 Python으로 앱을 실행한다.

**기술 스택:** Windows batch, Python 3.11+, Python 표준 라이브러리 `urllib`·`socket`·`json`, PySide6, Playwright, 기존 `pyproject.toml` 의존성.

## 공통 제약

- 저장소의 실제 기준 경로는 배치 파일 위치에서 계산하며 사용자별 절대 경로를 하드코딩하지 않는다.
- 프로젝트 의존성은 `pyproject.toml`에서 설치하고 배치 파일에 패키지 버전을 중복 선언하지 않는다.
- API 토큰·쿠키·비밀번호·개인 경로는 생성하거나 기록하지 않는다.
- `checkhost`는 공개 HTTP GET만 수행하고 게시글 작성·댓글 작성·로그인·CAPTCHA 우회를 수행하지 않는다.
- 네트워크·브라우저 설치 실패는 원인과 다음 행동을 표시하되, 이미 설치된 Chrome/Edge로 실행할 수 있는 경우 환경 점검 전체를 실패시키지 않는다.
- 수집 원본 DB와 공개 CSV의 데이터 계약은 변경하지 않는다.

---

### 작업 1: 표준 라이브러리 호스트·환경 점검 모듈

**파일:**
- 생성: `debug/checkhost.py`
- 테스트: `tests/test_checkhost.py`

**인터페이스:**
- 사용: `python debug/checkhost.py [--skip-network] [--json]`
- 제공: `parse_python_version`, `classify_response`, `build_environment_report`, `probe_url` 함수와 콘솔용 `main()`

- [ ] **1단계: 실패하는 테스트 작성** — Python 버전 문자열 판정, 빈 응답·정상 응답·차단 응답 분류, JSON 보고서의 비밀값 제외를 고정한다.
- [ ] **2단계: 테스트가 실패하는지 확인** — `python -m unittest tests.test_checkhost -v` 실행 후 모듈 부재 오류를 확인한다.
- [ ] **3단계: 최소 구현 작성** — 네트워크 요청은 `urllib.request`로 제한하고, 응답 본문은 길이·상태·콘텐츠 유형만 보고하며 HTML 원문·헤더 인증값을 출력하지 않는다.
- [ ] **4단계: 테스트 통과 확인** — 동일 테스트에서 전부 통과하고 `--skip-network --json` 출력이 JSON으로 파싱되는지 확인한다.
- [ ] **5단계: 커밋** — `git add debug/checkhost.py tests/test_checkhost.py` 후 `feat: add host preflight checker`로 커밋한다.

### 작업 2: 새 환경 설치·설정 배치 파일

**파일:**
- 생성: `debug/setup-trade-radar.bat`
- 수정: `.gitignore`
- 테스트: `tests/test_bootstrap_files.py`

**인터페이스:**
- 사용: 저장소에서 `debug\setup-trade-radar.bat`, 선택적으로 `debug\setup-trade-radar.bat --skip-browser`
- 제공: 저장소 루트 `.venv\Scripts\python.exe`, `.audit\` 디렉터리, editable 프로젝트 설치

- [ ] **1단계: 실패하는 테스트 작성** — 배치 파일이 루트 상대 경로, `.venv`, `py -3.11`/`python` fallback, `--skip-browser` 옵션, 비밀 파일 제외 원칙을 포함하는지 텍스트 계약으로 고정한다.
- [ ] **2단계: 테스트가 실패하는지 확인** — `python -m unittest tests.test_bootstrap_files -v`에서 파일 부재 또는 계약 누락으로 실패하는 것을 확인한다.
- [ ] **3단계: 최소 구현 작성** — Python 3.11+을 찾고, `.venv`를 만들고, `pip install -e .`을 수행하고, `.audit`를 만들며, 기본적으로 Playwright Chromium 설치를 시도한다. 브라우저 설치 실패는 경고로 남기고 Chrome/Edge fallback을 안내한다.
- [ ] **4단계: 테스트 통과 확인** — 배치 텍스트 계약 테스트와 실제 `--skip-browser` 재실행을 통과시킨다.
- [ ] **5단계: 커밋** — `git add debug/setup-trade-radar.bat .gitignore tests/test_bootstrap_files.py` 후 `feat: add Windows setup helper`로 커밋한다.

### 작업 3: checkhost 실행 래퍼와 데스크톱 실행 연결

**파일:**
- 생성: `debug/checkhost.bat`
- 수정: `debug/run-kaitori.bat`
- 테스트: `tests/test_bootstrap_files.py`

**인터페이스:**
- 사용: `debug\checkhost.bat`, `debug\checkhost.bat --skip-network`, `debug\run-kaitori.bat`
- 제공: 준비 상태 요약, 환경 실패 시 설치 안내, 준비된 경우 가상환경 Python으로 `trade_radar_desktop.py` 실행

- [ ] **1단계: 실패하는 테스트 작성** — checkhost가 `.venv` Python을 우선하고, run-kaitori가 `.venv`가 없을 때 setup을 호출하며, 앱을 시스템 Python으로 직접 실행하지 않는 계약을 고정한다.
- [ ] **2단계: 테스트가 실패하는지 확인** — `python -m unittest tests.test_bootstrap_files -v`에서 기존 배치의 직접 `python` 실행 때문에 실패하는 것을 확인한다.
- [ ] **3단계: 최소 구현 작성** — 공백·한글 경로·저장소 위치를 안전하게 인용하고, setup 실패 시 창을 유지해 오류를 볼 수 있게 하며, checkhost 결과는 종료 코드로도 전달한다.
- [ ] **4단계: 테스트 통과 확인** — 배치 텍스트 계약, `checkhost.bat --skip-network`, 준비된 가상환경을 통한 `python -c` 점검을 통과시킨다.
- [ ] **5단계: 커밋** — `git add debug/checkhost.bat debug/run-kaitori.bat tests/test_bootstrap_files.py` 후 `feat: wire Windows preflight into desktop runner`로 커밋한다.

### 작업 4: 사용자 가이드와 기존 안내 정합성

**파일:**
- 생성: `docs/windows-setup.md`
- 수정: `README.md`, `docs/desktop-app.md`, `web/src/dev-page.tsx`

**인터페이스:**
- 사용: 새 사용자는 `debug\setup-trade-radar.bat` 또는 `debug\run-kaitori.bat`에서 시작한다.
- 제공: Python 설치 조건, 최초 설정, checkhost 해석, 브라우저 fallback, 데이터 위치, CSV/Git 반영 경계, 문제 해결 절차

- [ ] **1단계: 가이드 검토 기준 작성** — 새 환경의 선행 조건, 첫 실행, 재실행, 네트워크 오류, Playwright 브라우저 설치 실패, GitHub Pages가 로컬 앱을 실행할 수 없는 이유를 포함한다.
- [ ] **2단계: 기존 안내와 충돌 확인** — `rg`로 `Collector.exe`가 이미 배포된 것처럼 설명하는 문구와 직접 시스템 Python을 요구하는 문구를 찾는다.
- [ ] **3단계: 문서 구현** — 새 배치 파일을 첫 진입점으로 올리고, 휴대형 EXE가 없는 현재 사실과 Python 기반 앱의 경계를 명확히 기록한다.
- [ ] **4단계: 문서 검증** — 링크·명령어·파일 경로를 실제 저장소와 대조하고, 영문/한글 경로 및 Windows CMD 문법을 확인한다.
- [ ] **5단계: 커밋** — `git add README.md docs/desktop-app.md docs/windows-setup.md web/src/dev-page.tsx` 후 `docs: add Windows first-run guide`로 커밋한다.

### 작업 5: 전체 검증과 GitHub 반영

**파일:**
- 검토: 위 작업의 모든 변경 파일
- 테스트: `tests/` 전체, 배치 계약 테스트, 컴파일 검사

**인터페이스:**
- 사용: Python 테스트·컴파일·checkhost dry-run·웹 lint/typecheck/build
- 제공: 새 환경에서 재현 가능한 설치·점검·실행 경로와 원격 `main` 반영

- [ ] **1단계: 실패 기준 점검** — 배치 파일의 CRLF, `git diff --check`, 민감 파일 미추가, 루트 경로 의존 여부를 확인한다.
- [ ] **2단계: 전체 테스트 실행** — `python -B -m pytest -q`, `python -B -m compileall -q kaitori_collector debug tests scripts`, `python debug/checkhost.py --skip-network --json`을 실행한다.
- [ ] **3단계: 웹 검증 실행** — `pnpm --dir web typecheck`, `pnpm --dir web lint`, `pnpm --dir web build`를 실행한다.
- [ ] **4단계: 실제 점검** — 현재 PC의 `.venv` 환경에서 `debug\checkhost.bat --skip-network`와 네트워크 포함 checkhost를 실행하고, 앱 프로세스를 자동 종료하지 않은 채 실행 진입점이 올바른지 확인한다.
- [ ] **5단계: 커밋·푸시** — 변경 범위를 확인해 커밋하고 `origin/main`에 fast-forward 가능한 방식으로 푸시한다. 마지막으로 로컬/원격 SHA와 작업 트리 상태를 보고한다.
