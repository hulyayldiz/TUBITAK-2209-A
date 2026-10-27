"""No-tuning validation of all 209 new CMU nominal flight/ground records."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import zipfile

import pandas as pd
import torch

from dataset_loader import _process_dataset_dataframe, get_next_dataset_row
from download_real_data import sha256_file
from ml_detection import get_hybrid_decision
from navigation import process_navigation
from real_data_catalog import ROOT, EXTERNAL
from validation import new_state, step_features, finish_frame

OUTPUT = ROOT/'validation_results'/'independent_real_20261023'


def check_freeze(frozen):
    for name, expected in frozen['sha256'].items():
        if sha256_file(ROOT/name) != expected:
            raise ValueError(f'Independent test invalidated: detector changed: {name}')


def evaluate():
    torch.set_num_threads(1)
    frozen = json.loads((OUTPUT/'frozen_detector.json').read_text(encoding='utf-8'))
    check_freeze(frozen)
    path = EXTERNAL/'independent_cmu'
    meta = json.loads((path/'article_metadata.json').read_text(encoding='utf-8'))
    archive_meta = next(x for x in meta['files'] if x['name'] == 'flights.zip')
    archive_path = path/'flights.zip'
    if hashlib.md5(archive_path.read_bytes()).hexdigest() != archive_meta['computed_md5']:
        raise ValueError('CMU archive does not match publisher checksum')
    parameters = pd.read_csv(path/'parameters.csv').set_index('flight')
    results = []
    with zipfile.ZipFile(archive_path) as archive:
        members = [n for n in archive.namelist() if n.endswith('.csv')]
        ids = sorted((int(n.rsplit('/', 1)[-1].removesuffix('.csv')), n) for n in members)
        if len(ids) != 209 or {flight for flight, _ in ids} != set(parameters.index):
            raise ValueError('Expected all 209 producer-listed records, no cherry picking')
        for number, member in ids:
            raw = archive.read(member)  # zipfile checks entry CRC; full archive MD5 also checked.
            import io
            data = pd.read_csv(io.BytesIO(raw))
            state = new_state()
            state.use_dataset_mode = True
            _process_dataset_dataframe(data, f'CMU/{number}.csv', state)
            counts, rule_counts, causes, models, count = Counter(), Counter(), Counter(), Counter(), 0
            alarm_duration = 0.
            first_t = last_t = None
            while (row := get_next_dataset_row(state)) is not None:
                state.navigation_time = state.sample_time_s
                assert not state.ground_truth_available
                rule, reason, features = step_features(state, row[:4], state.sample_dt)
                state.vae_buffer = (state.vae_buffer+[features])[-10:]
                decision, _, _, _ = get_hybrid_decision(rule, features, state, state.vae_buffer)
                *position, final, nav_reason = process_navigation(state, *row[:4], True, .5, 40.,
                    dt=state.sample_dt, decision=(decision, reason))
                if not all(__import__('math').isfinite(x) for x in position[:2]):
                    raise ValueError(f'Non-finite navigation output in flight {number}')
                counts[final] += 1
                rule_counts[rule] += 1
                if final != 'NORMAL':
                    causes[nav_reason.split('(')[0]] += 1
                    if last_t is not None:
                        alarm_duration += state.sample_time_s-last_t
                models[state.ml_source] += 1
                first_t = state.sample_time_s if first_t is None else first_t
                last_t = state.sample_time_s
                count += 1
                finish_frame(state, row[:4])
            alarms = count-counts['NORMAL']
            route = str(parameters.loc[number, 'route'])
            results.append(dict(flight=number, route=route, is_cruise_flight=route.startswith('R'),
                source_member=member, source_sha256=hashlib.sha256(raw).hexdigest(),
                input_rows=len(data), rows=count, duration_s=last_t-first_t,
                decisions=dict(counts), rule_decisions=dict(rule_counts), causes=dict(causes),
                nominal_alarm_samples=alarms, nominal_alarm_rate=alarms/count,
                alarm_duration_s=alarm_duration, ml_sources=dict(models)))
            if len(results) % 20 == 0:
                print('CMU records', len(results), 'completed', flush=True)
        # A deterministic first flight is also available for manual app loading.
        example = path/'example_flight_1.csv'
        example.write_bytes(archive.read(next(n for n in members if n == 'flights/1.csv')))
    check_freeze(frozen)
    total = sum(x['rows'] for x in results)
    alarms = sum(x['nominal_alarm_samples'] for x in results)
    summary = dict(records=len(results), cruise_flights=sum(x['is_cruise_flight'] for x in results),
        rows=total, nominal_alarm_samples=alarms, nominal_alarm_rate=alarms/total,
        records_with_alarms=sum(x['nominal_alarm_samples'] > 0 for x in results),
        record_duration_s=sum(x['duration_s'] for x in results))
    report = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        source_url='https://kilthub.cmu.edu/articles/dataset/12683453', doi='10.1184/R1/12683453',
        archive_sha256=sha256_file(archive_path), publisher_md5_verified=True,
        detector_freeze_verified_before_and_after=True, frozen_detector=frozen,
        adapter_sha256=sha256_file(ROOT/'dataset_adapters.py'),
        evaluation_code_sha256=sha256_file(ROOT/'validate_independent_real.py'),
        summary=summary, results=results,
        limitations=['All 209 records included, including ancillary ground/hover tests.',
            'Nominal energy-study flights; no producer binary spoofing labels. Alarm rate assumes nominal operations.',
            'Different DJI M100 platform and MicroStrain receiver; fused GNSS/INS output, not raw GPS.',
            'No C/N0 and no AV feature schema: only physical/navigation layers assessed; RF/VAE not validated.',
            'No independent IMU/attitude/position truth; no attack recall or position RMSE can be inferred.',
            'No model training, threshold change or flight selection based on predictions.'])
    (OUTPUT/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary), flush=True)
    return report


if __name__ == '__main__':
    evaluate()
