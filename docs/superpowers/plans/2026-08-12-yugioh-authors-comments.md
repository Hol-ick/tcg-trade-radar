# 유희왕 작성자·댓글 수집 확장 구현 계획

> **실행 에이전트용:** 공개 읽기 전용 수집 범위에서 실행한다.

**목표:** 유희왕 갤러리의 거래 게시글을 수집할 때 공개 작성자 표기(닉네임·유동/고닉 유형)와 댓글을 함께 저장·조회한다.

**구조:** 게시글 파서가 작성자 메타데이터를 추출하고, 댓글은 DCInside의 공개 댓글 조회 응답을 별도 파서로 읽는다. SQLite에는 작성자 필드를 원문(source)에, 댓글은 source와 연결된 별도 테이블에 저장한다.

**기술 스택:** Python 표준 라이브러리, HTMLParser, SQLite, 기존 JobService/API 구조

## 공통 제약

- 공개 HTML과 공개 댓글 응답만 읽고 글쓰기·댓글쓰기·로그인·CAPTCHA 우회는 하지 않는다.
- IP 주소·비밀번호·쿠키·식별 토큰은 저장하지 않는다.
- 댓글 요청은 게시글별 1페이지씩 순차 요청하고 기존 재시도·지연 정책을 따른다.
- 작성자 유형은 `guest`, `registered`, `unknown` 세 값으로 제한한다.

---

### 작업 1: 게시글 작성자 메타데이터

**파일:**
- 수정: `kaitori_collector/contracts.py`, `kaitori_collector/html.py`, `kaitori_collector/parser.py`
- 테스트: `tests/test_parser.py`

**인터페이스:**
- `parse_html()`가 `author_name`, `author_type`을 반환한다.
- `ExtractedRow`와 공개 결과에 작성자 필드를 포함한다.

- [ ] 작성자 HTML fixture와 유동/고닉 판별 실패 테스트 작성
- [ ] HTMLParser에서 공개 닉네임과 고닉 신호만 추출
- [ ] 거래 행과 CLI/API 출력에 필드 연결
- [ ] 파서 테스트 통과

### 작업 2: 댓글 파서·저장

**파일:**
- 생성: `kaitori_collector/comments.py`
- 수정: `kaitori_collector/storage.py`, `migrations/004_authors_comments.sql`
- 테스트: `tests/test_comments.py`, `tests/test_storage.py`

**인터페이스:**
- `parse_comments(html, post_url, gallery_id) -> list[CommentRecord]`
- `Repository.insert_comments(source_id, comments) -> int`
- `Repository.list_comments(job_id=...) -> list[dict]`

- [ ] 댓글 fixture에서 닉네임·유형·본문·시각·댓글 ID 파싱
- [ ] 댓글 테이블과 멱등 키 추가
- [ ] IP 등 비수집 필드가 결과에 없는지 테스트
- [ ] 저장·조회 테스트 통과

### 작업 3: 수집 서비스·API 연결

**파일:**
- 수정: `kaitori_collector/parser.py`, `kaitori_collector/service.py`, `kaitori_collector/api.py`, `debug/trade_radar_app.py`
- 테스트: `tests/test_service.py`, `tests/test_api.py`

**인터페이스:**
- `fetch_comment_text()`가 공개 댓글 조회 POST 응답을 읽는다.
- `GET /jobs/{id}/comments`로 수집 댓글을 조회한다.

- [ ] 게시글 fetch 후 댓글 응답을 순차 요청
- [ ] 댓글 응답 이상 상태를 로그에 기록하고 게시글 수집은 보존
- [ ] 댓글 수를 작업 counts와 UI 로그에 표시
- [ ] API 조회 테스트 통과

### 작업 4: 유희왕 샘플 수집·검증

**파일:**
- 생성: `debug/run_yugioh_sample.py`
- 수정: `README.md`

- [ ] `tcggame`의 최근 판매·구매 게시글을 읽기 전용으로 최대 10개 수집
- [ ] 게시글·작성자·댓글 수를 JSON으로 출력
- [ ] 현재 환경의 응답 공백/차단 여부를 성공 데이터와 구분해 기록
- [ ] 전체 테스트·컴파일·API 스모크·샘플 실행 결과를 보고

