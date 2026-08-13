# TCG Trade Radar 웹 콘솔

React/Vite 화면에서 로컬 Python 워커를 호출해 실제 거래글을 수집합니다. 조회 기간의 기본값만 최근 7일이며, 별도의 주간 수집 기능은 없습니다.

## 로컬 실행

터미널을 두 개 열고 워커와 웹 화면을 각각 실행합니다.

```powershell
python -m kaitori_collector --serve --host 127.0.0.1 --port 8787 --db .audit\kaitori.sqlite3
```

```powershell
pnpm --config.minimum-release-age=0 --dir web install
pnpm --dir web dev --host 127.0.0.1 --port 5173
```

`http://127.0.0.1:5173`에서 게임·조회 기간·최근 게시글 수를 설정하고 `수집 시작`을 누릅니다. 게임은 5개 프리셋으로 고정되어 있고, 판매·구매·교환 말머리를 함께 수집합니다.

## 화면 기능

- 미리 등록된 5개 TCG 갤러리 선택
- 기본 7일 조회 기간과 이전·다음 기간 이동
- 최근 게시글 수·페이지 수·요청 간격 설정
- 판매·구매·교환·미분류 결과와 검토 필요 건수 확인
- 수집 단계별 로그와 워커 상태 확인
- 원문 게시글 링크 확인
- CSV 저장

## 확인 명령

```powershell
pytest -q
python -m compileall -q kaitori_collector debug tests scripts
pnpm --config.minimum-release-age=0 --dir web lint
pnpm --config.minimum-release-age=0 --dir web typecheck
pnpm --config.minimum-release-age=0 --dir web build
```

GitHub Pages 공개 화면은 정적 파일만 제공하므로 실제 수집 버튼은 로컬 워커가 연결된 개발 화면에서 사용합니다. 원본 게시글은 공개 읽기 범위만 대상으로 하며, 로그인·게시글 작성·CAPTCHA 우회·개인 거래 중개는 지원하지 않습니다. 요청 간 지연과 페이지·게시물 상한을 적용하고, 가격이 이미지에만 있는 글은 자동 확정하지 않고 검토 대상으로 표시합니다.
