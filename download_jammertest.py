"""Fetch and verify the public Jammertest 2024 GNSS attack archive.

The archive is kept under dataset_gercek/external (ignored by git). Source
metadata, URL, size, and checksums are written to a separate provenance file.
TLS verification is enabled and existing bytes are never overwritten.
"""
from datetime import datetime, timezone
import hashlib
import json
import ssl
import urllib.request

from real_data_catalog import EXTERNAL, ROOT

RECORD_ID = 15911589
API = f"https://zenodo.org/api/records/{RECORD_ID}"
DEST = EXTERNAL / "jammertest_2024" / "GNSS_DATASET_JAMMING_SPOOFING.tar.gz"
PROVENANCE = ROOT / "jammertest_2024_manifest.json"


def _hashes(path):
    md5, sha256 = hashlib.md5(), hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            md5.update(block)
            sha256.update(block)
    return md5.hexdigest(), sha256.hexdigest()


def download():
    context = ssl.create_default_context()
    with urllib.request.urlopen(API, context=context, timeout=60) as response:
        record = json.load(response)
    metadata = record["metadata"]
    expected = next((item for item in record["files"]
                     if item["key"] == DEST.name), None)
    if expected is None or metadata.get("doi") != "10.5281/zenodo.15911589":
        raise ValueError("Official Zenodo record or expected archive is missing")
    if expected["size"] != 375338522 or expected.get("checksum") != "md5:c7b00c63bb1ee5db80c7692a2b06e169":
        raise ValueError("Zenodo archive metadata differs from the pinned source contract")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if DEST.exists():
        md5, sha = _hashes(DEST)
        if DEST.stat().st_size != expected["size"] or md5 != expected["checksum"].split(":", 1)[1]:
            raise ValueError("Existing archive does not match publisher checksum; preserved")
    else:
        partial = DEST.with_name(DEST.name + ".part")
        url = expected["links"]["self"]
        with urllib.request.urlopen(url, context=context, timeout=120) as response:
            if response.status != 200:
                raise ValueError(f"Unexpected download response: {response.status}")
            with partial.open("wb") as stream:
                while block := response.read(1024 * 1024):
                    stream.write(block)
        md5, sha = _hashes(partial)
        if partial.stat().st_size != expected["size"] or md5 != expected["checksum"].split(":", 1)[1]:
            partial.unlink(missing_ok=True)
            raise ValueError("Downloaded archive failed publisher size/MD5 verification")
        partial.replace(DEST)
    entry = dict(dataset=metadata.get("title"), doi=metadata["doi"], record_id=RECORD_ID,
        version="v3",
        url=expected["links"]["self"], license=metadata.get("license"),
        relative_path=DEST.relative_to(ROOT).as_posix(), bytes=DEST.stat().st_size,
        publisher_md5=expected["checksum"].split(":", 1)[1], sha256=sha,
        verified_at_utc=datetime.now(timezone.utc).isoformat(),
        note="Raw publisher archive; no parsing or label interpretation performed.")
    PROVENANCE.write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(entry, ensure_ascii=False, indent=2))
    return entry


if __name__ == "__main__":
    download()
