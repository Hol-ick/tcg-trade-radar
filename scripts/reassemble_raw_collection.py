"""Reassemble and verify a split raw SQLite collection database."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def reassemble(input_dir: Path, output: Path) -> dict[str, object]:
    manifest = json.loads((input_dir / "raw-dataset-manifest.json").read_text(encoding="utf-8"))
    temporary = output.with_name(f"{output.name}.partially-written")
    digest = hashlib.sha256()
    total = 0
    try:
        with temporary.open("wb") as destination:
            for part in manifest["parts"]:
                part_path = input_dir / part["file"]
                part_digest = hashlib.sha256()
                with part_path.open("rb") as source:
                    while block := source.read(16 * 1024 * 1024):
                        destination.write(block)
                        digest.update(block)
                        part_digest.update(block)
                        total += len(block)
                if part_digest.hexdigest() != part["sha256"]:
                    raise ValueError(f"part checksum mismatch: {part_path.name}")
        if total != manifest["source_size"]:
            raise ValueError(f"source size mismatch: {total} != {manifest['source_size']}")
        if digest.hexdigest() != manifest["source_sha256"]:
            raise ValueError("reassembled source checksum mismatch")
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return {"output": str(output), "size": total, "sha256": digest.hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(reassemble(args.input_dir, args.output), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
