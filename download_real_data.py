"""Download the audited public subset and retain a SHA-256 provenance manifest.

Run: python download_real_data.py
TLS verification stays enabled, using the OS certificate store. Large raw
TEXBAT .bin files and account-protected IEEE files are not part of this subset.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import ssl
import urllib.request

from real_data_catalog import EXTERNAL, ROOT

TEXBAT = 'https://rnl-data.ae.utexas.edu/datastore/texbat/'
DOCS = 'https://rnl-data.ae.utexas.edu/datastore/satNavCourse/logFileDocumentation/'
FILES = {
    'zurich/AGZ_subset.zip': 'https://download.ifi.uzh.ch/rpg/AGZ_data/AGZ_subset.zip',
    'zurich/source.html': 'https://rpg.ifi.uzh.ch/zurichmavdataset.html',
    'texbat/readme.txt': TEXBAT + 'processed/readme.txt',
    'texbat/navsoldef.txt': DOCS + 'navsoldef.txt',
    'texbat/channeldef.txt': DOCS + 'channeldef.txt',
    'texbat/source.html': 'https://radionavlab.ae.utexas.edu/texbat/',
}
for scenario in ('cleanStatic', 'ds2', 'ds3', 'ds7'):
    for name in ('navsol.mat', 'channel.mat'):
        FILES[f'texbat/{scenario}/{name}'] = TEXBAT + f'processed/{scenario}/{name}'

MANIFEST = ROOT / 'real_data_manifest.json'


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        while block := handle.read(1024*1024):
            digest.update(block)
    return digest.hexdigest()


def download_all():
    try:
        import truststore
        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        context = ssl.create_default_context()
    previous = json.loads(MANIFEST.read_text(encoding='utf-8')) if MANIFEST.exists() else {}
    recorded = {item['relative_path']: item for item in previous.get('files', [])}
    entries = []
    for relative, url in FILES.items():
        path = EXTERNAL / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            partial = path.with_name(path.name + '.part')
            with urllib.request.urlopen(url, context=context, timeout=90) as response:
                expected = response.headers.get('Content-Length')
                with partial.open('wb') as handle:
                    while block := response.read(1024*1024):
                        handle.write(block)
            if expected is not None and partial.stat().st_size != int(expected):
                raise ValueError(f'Incomplete download: {relative}')
            partial.replace(path)
        digest = sha256_file(path)
        if relative in recorded and recorded[relative]['sha256'] != digest:
            raise ValueError(f'Local source changed: {relative}; original manifest retained')
        entries.append(dict(relative_path=relative, url=url, bytes=path.stat().st_size,
            sha256=digest, local_file_mtime_utc=datetime.fromtimestamp(
                path.stat().st_mtime, timezone.utc).isoformat()))
        print(relative, path.stat().st_size, digest)
    # A provenance manifest identifies source bytes. A read-only recheck must
    # not change its hash just because the wall clock has advanced.
    if previous.get('files') == entries:
        return previous
    manifest = dict(schema='external-real-data-v1',
        verified_at_utc=datetime.now(timezone.utc).isoformat(),
        hash_policy='Local SHA-256 of HTTPS download; no upstream signed digest supplied.',
        files=entries,
        excluded=dict(texbat_raw_bin='Not downloaded; 39-44 GB per attack scenario.',
                      ieee_uav_attack='Requires IEEE account login; not downloaded.'))
    pending = MANIFEST.with_suffix('.pending')
    pending.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    pending.replace(MANIFEST)
    return manifest


if __name__ == '__main__':
    download_all()
