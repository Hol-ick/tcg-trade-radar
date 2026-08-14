# 원본 수집 DB

원본 SQLite `kaitori.sqlite3`는 GitHub의 단일 파일 상한을 넘기 때문에 `kaitori.sqlite3.part-0001`부터 `part-0006`까지 512MiB 이하 조각으로 분할해 Git LFS에 저장한다.

- 원본 크기: 2,924,371,968 bytes
- 원본 SHA-256: `1a37a9b10c60e5debcc1896d5b28b8d593f980800f59e89610dea8f4169f3726`
- 조각별 크기·SHA-256: `raw-dataset-manifest.json`
- 조각을 합친 뒤 manifest의 원본 SHA-256과 비교하면 byte 단위 원본 복원이 확인된다.

복원 예시:

```text
python scripts/reassemble_raw_collection.py --input-dir data/raw/collections/2026-02-14_2026-08-13 --output kaitori.sqlite3
```
