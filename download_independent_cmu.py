"""Reproduce the public CMU data download without changing detector snapshots."""
import hashlib
import json
import ssl
import time
import urllib.request
import zipfile
from urllib.parse import urlsplit, urlunsplit

import truststore

from real_data_catalog import ROOT, EXTERNAL


def download():
    target = EXTERNAL/'independent_cmu'
    target.mkdir(parents=True, exist_ok=True)
    context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    api = 'https://api.figshare.com/v2/articles/12683453'
    with urllib.request.urlopen(api, context=context, timeout=30) as response:
        metadata = json.load(response)
    if metadata['version'] != 1:
        raise ValueError('CMU source version changed; preserve the version 1 benchmark')
    (target/'article_metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    records = []
    for item in metadata['files']:
        if item['name'] not in ('parameters.csv', 'README.txt', 'flights.zip'):
            continue
        path = target/item['name']
        if not path.exists():
            url = item['download_url']+'?download='+str(time.time_ns())
            # Public redirects can contain stale expiring query strings. Verify
            # TLS and use the same resolved public object without a signed query.
            request = urllib.request.Request(url, headers={'Range': 'bytes=0-0'})
            with urllib.request.urlopen(request, context=context, timeout=30) as response:
                resolved = urlsplit(response.url)
            public = urlunsplit((resolved.scheme, resolved.netloc, resolved.path, '', ''))
            pending = path.with_suffix(path.suffix+'.download')
            with urllib.request.urlopen(public+'?download='+str(time.time_ns()), context=context, timeout=30) as response:
                with pending.open('wb') as handle:
                    while block := response.read(65536):
                        handle.write(block)
            pending.replace(path)
        raw = path.read_bytes()
        if len(raw) != item['size'] or hashlib.md5(raw).hexdigest() != item['computed_md5']:
            raise ValueError(f'Publisher checksum mismatch: {path.name}')
        records.append(dict(relative_path=str(path.relative_to(EXTERNAL)).replace('\\', '/'),
            url=item['download_url'], sha256=hashlib.sha256(raw).hexdigest(),
            publisher_md5=item['computed_md5'], bytes=len(raw)))
    example = target/'example_flight_1.csv'
    # Always derive the sample from the verified archive, never bless altered
    # local sample bytes by copying their hash into a fresh manifest.
    with zipfile.ZipFile(target/'flights.zip') as archive:
        example.write_bytes(archive.read('flights/1.csv'))
    records.append(dict(relative_path=str(example.relative_to(EXTERNAL)).replace('\\', '/'),
        url='https://ndownloader.figshare.com/files/26385070#flights/1.csv',
        sha256=hashlib.sha256(example.read_bytes()).hexdigest(), bytes=example.stat().st_size))
    manifest = dict(schema='independent-cmu-v1', doi='10.1184/R1/12683453',
                    article_version=metadata['version'], files=records)
    (ROOT/'independent_cmu_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    print(json.dumps(download(), indent=2))
