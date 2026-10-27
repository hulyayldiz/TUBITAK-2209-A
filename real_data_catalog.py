"""Known source locations, rooted independently of the launch directory."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent
EXTERNAL = ROOT / 'dataset_gercek' / 'external'
SOURCES = {
    'Zurich — gerçek Fotokite uçuşu (GPS + gövde IMU)': EXTERNAL/'zurich'/'AGZ_subset.zip',
    'TEXBAT — cleanStatic (işlenmiş gerçek sinyal)': EXTERNAL/'texbat'/'cleanStatic'/'navsol.mat',
    'TEXBAT — DS2 (işlenmiş gerçek sinyal)': EXTERNAL/'texbat'/'ds2'/'navsol.mat',
    'TEXBAT — DS3 (işlenmiş gerçek sinyal)': EXTERNAL/'texbat'/'ds3'/'navsol.mat',
    'TEXBAT — DS7 (işlenmiş gerçek sinyal)': EXTERNAL/'texbat'/'ds7'/'navsol.mat',
    'CMU — bağımsız nominal uçuş 1 (GNSS/INS)': EXTERNAL/'independent_cmu'/'example_flight_1.csv',
}


def available_sources():
    return {name: path for name, path in SOURCES.items() if path.is_file()}


def declared_grid_profile(digest):
    """Only the explicitly downloaded static scenarios share this calibration."""
    path = ROOT/'real_data_manifest.json'
    if path.is_file():
        data = json.loads(path.read_text(encoding='utf-8'))
        known = {item['sha256'] for item in data['files']
                 if item['relative_path'] in {
                     f'texbat/{scenario}/navsol.mat' for scenario in ('cleanStatic', 'ds2', 'ds3', 'ds7')}}
        if digest in known:
            return 'texbat-grid-static-v1'
    return 'grid-unvalidated'


def verify_source_file(path):
    """Validate known download bytes (including sibling channel measurements)."""
    path = Path(path).resolve()
    recorded = {}
    for filename in ('real_data_manifest.json', 'independent_cmu_manifest.json'):
        manifest_path = ROOT/filename
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            recorded.update({(EXTERNAL/item['relative_path']).resolve(): item['sha256']
                             for item in manifest['files']})
    inputs = [path]
    channel = path.with_name('channel.mat')
    if path.name == 'navsol.mat' and channel in recorded:
        inputs.append(channel)
    primary = None
    for item in inputs:
        digest = hashlib.sha256()
        with item.open('rb') as handle:
            while block := handle.read(1024*1024):
                digest.update(block)
        value = digest.hexdigest()
        if item in recorded and value != recorded[item]:
            raise ValueError(f'Kaynak dosyası manifest ile eşleşmiyor: {item.name}')
        if item == path:
            primary = value
    return primary
