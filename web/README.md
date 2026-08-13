# TCG Trade Radar 웹 콘솔

React/Vite로 만든 정적 주간 수집 결과 화면입니다. 브라우저에서 원본 게시판이나 로컬 워커를 직접 호출하지 않고, GitHub Pages에 배포된 JSON/CSV 스냅샷만 읽습니다.

## 로컬 실행

저장소 루트에서 다음을 실행합니다.

```powershell
pnpm --dir web install
pnpm --dir web dev --host 127.0.0.1 --port 5173
```

`http://127.0.0.1:5173`에서 주간 콘솔을 열 수 있습니다. `/dev/` 경로는 개발용 화면 라우트를 유지하지만, 공개 수집은 GitHub Actions의 `Collect weekly snapshot` 워크플로가 담당합니다.

## 화면 기능

- 미리 등록된 5개 TCG 갤러리 선택
- 7일 단위 이전 주·다음 주 조회
- 판매·구매·교환·미분류 결과와 검토 필요 건수 확인
- 원문 게시글 링크 확인
- 선택한 주간 결과 CSV 다운로드

주간 결과 파일은 다음 규칙으로 배포됩니다.

```text
web/public/data/weeks/<gallery_id>/<since>.json
web/public/data/weeks/<gallery_id>/<since>.csv
```

## 주간 수집

GitHub Actions에서 `Collect weekly snapshot`을 수동 실행하거나 매주 월요일 자동 실행합니다. 수집 범위는 `since`부터 6일 뒤까지의 정확히 7일이며, 실행 스크립트는 다음과 같습니다.

```powershell
python scripts/export_week_snapshot.py `
  --since 2026-08-07 `
  --until 2026-08-13 `
  --gallery-id tcggame
```

스크립트는 Python 수집기를 한 번 실행한 뒤 JSON과 CSV를 생성합니다. HTTP 워커를 시작하지 않으며, 수집 원문과 SQLite 감사 기록은 웹 정적 파일과 분리됩니다.

## 확인 명령

```powershell
pytest -q
python -m compileall -q kaitori_collector debug tests scripts
pnpm --dir web lint
pnpm --dir web typecheck
pnpm --dir web build
```

원본 게시글은 공개 읽기 범위만 대상으로 하며, 로그인·게시글 작성·CAPTCHA 우회·개인 거래 중개는 지원하지 않습니다. 요청 간 지연과 페이지·게시물 상한을 적용하고, 가격이 이미지에만 있는 글은 자동 확정하지 않고 검토 대상으로 표시합니다.
