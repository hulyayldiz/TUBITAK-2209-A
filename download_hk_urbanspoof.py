"""Fetch the small published GNSS/INS reference tracks for HK-UrbanSpoof.

The large raw IF files are deliberately not downloaded here. Source data is
kept under the ignored external-data directory; GitHub blob SHA-1 and local
SHA-256 values are recorded for byte provenance.
"""
from datetime import datetime, timezone
import hashlib
import json
import ssl
import urllib.request

from real_data_catalog import ROOT

COMMIT = "95def2b6a42eee6299bbc1a5b880a9f3bfc070d6"
BASE = f"https://raw.githubusercontent.com/Fangjingxiaotao/HK-UrbanSpoof/{COMMIT}"
FILES = {
    "S2_GT.txt": (45730, "1c03c4683dae12b7c41bb5ad079becf8387693f9"),
    "S3_GT.txt": (1168279, "eb6d687933fe3cf34f6f9a6c1a6c8f2bee932b70"),
}
DEST = ROOT/"dataset_gercek"/"external"/"hk_urban_spoof"
MANIFEST = ROOT/"hk_urban_spoof_manifest.json"


def git_blob_sha1(content):
    return hashlib.sha1(b"blob "+str(len(content)).encode()+b"\0"+content).hexdigest()


def download():
    context = ssl.create_default_context()
    items = []
    DEST.mkdir(parents=True, exist_ok=True)
    for name, (size, expected_git_sha) in FILES.items():
        path = DEST/name
        if path.exists():
            content = path.read_bytes()
        else:
            request = urllib.request.Request(BASE+"/"+name, headers={"User-Agent":"vers8-audited-dataset"})
            with urllib.request.urlopen(request, context=context, timeout=90) as response:
                content = response.read()
            pending = path.with_suffix(path.suffix+".part")
            pending.write_bytes(content)
            path = pending
        if len(content) != size or git_blob_sha1(content) != expected_git_sha:
            if path.suffix.endswith(".part"):
                path.unlink(missing_ok=True)
            raise ValueError(f"HK-UrbanSpoof file failed pinned size/Git blob verification: {name}")
        if path.suffix.endswith(".part"):
            target = DEST/name
            path.replace(target)
            path = target
        items.append(dict(name=name, relative_path=path.relative_to(ROOT).as_posix(),
            bytes=len(content), git_blob_sha1=expected_git_sha,
            sha256=hashlib.sha256(content).hexdigest(), url=BASE+"/"+name))
        print(name, len(content), items[-1]["sha256"])
    manifest = dict(schema="hk-urbanspoof-reference-v1", repository="Fangjingxiaotao/HK-UrbanSpoof",
        commit=COMMIT, source_url="https://github.com/Fangjingxiaotao/HK-UrbanSpoof",
        license="No license declaration found in the pinned repository; local validation use only.",
        source_description="S2/S3 post-processed NovAtel SPAN-CPT GNSS/INS reference trajectories.",
        raw_if_downloaded=False, files=items,
        downloaded_at_utc=datetime.now(timezone.utc).isoformat())
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    download()
