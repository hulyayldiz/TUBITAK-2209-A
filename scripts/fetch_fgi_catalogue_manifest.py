"""Snapshot public FGI Jammertest 2025 file metadata (no dataset payloads)."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DATASET_ID = "095782a8-4e31-456e-8719-7021b4c96362"
DATASET_URL = f"https://etsin.fairdata.fi/dataset/{DATASET_ID}"
FILES_URL = f"https://metax.fairdata.fi/v3/datasets/{DATASET_ID}/files?limit=20&offset=0"
DEFAULT_OUTPUT = Path("data_manifests/fgi_jammertest_2025.json")


def get_json(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "metax.fairdata.fi":
        raise ValueError(f"Unexpected metadata URL: {url}")
    request = Request(url, headers={"User-Agent": "BKZS-vers8-catalogue-manifest/1.0"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    page_url: str | None = FILES_URL
    files: list[dict] = []
    expected_count: int | None = None
    while page_url:
        page = get_json(page_url)
        if expected_count is None:
            expected_count = int(page["count"])
        for item in page["results"]:
            checksum = item.get("checksum", "")
            algorithm, separator, digest = checksum.partition(":")
            files.append(
                {
                    "path": item["pathname"],
                    "size_bytes": int(item["size"]),
                    "checksum_algorithm": algorithm if separator else None,
                    "checksum": digest if separator else checksum or None,
                    "frozen": item.get("frozen"),
                    "modified": item.get("modified"),
                    "published": item.get("published"),
                }
            )
        page_url = page.get("next")

    files.sort(key=lambda item: item["path"])
    if expected_count != len(files):
        raise RuntimeError(f"Expected {expected_count} metadata rows, received {len(files)}")

    by_extension: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "size_bytes": 0})
    for item in files:
        extension = Path(item["path"]).suffix.lower() or "[none]"
        by_extension[extension]["count"] += 1
        by_extension[extension]["size_bytes"] += item["size_bytes"]

    manifest = {
        "dataset_id": DATASET_ID,
        "doi": "10.23729/fd-bb2cf9f9-d135-35d4-bda0-46eaca30e2ee",
        "dataset_url": DATASET_URL,
        "metadata_api": FILES_URL,
        "snapshot_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "access": "Open",
        "license": "CC BY 4.0",
        "file_count": len(files),
        "total_size_bytes": sum(item["size_bytes"] for item in files),
        "files_by_extension": dict(sorted(by_extension.items())),
        "payloads_downloaded_by_this_script": False,
        "files": files,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(files)} metadata rows ({manifest['total_size_bytes']} bytes) to {args.output}")


if __name__ == "__main__":
    main()
