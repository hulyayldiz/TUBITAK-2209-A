"""Full CMU regression after navigation changes; not a new independent test."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import zipfile

import pandas as pd
import torch

from dataset_loader import _process_dataset_dataframe, get_next_dataset_row
from download_real_data import sha256_file
from ml_detection import get_hybrid_decision
from navigation import process_navigation
from real_data_catalog import ROOT, EXTERNAL
from sensors import calculate_distance_km
from validation import new_state, step_features, finish_frame

OUTPUT = ROOT/'validation_results'/'navigation_fix_20261023'
FILES = ('navigation.py', 'fusion.py', 'detection.py', 'ml_detection.py', 'config.py',
         'features.py', 'dataset_loader.py', 'dataset_adapters.py', 'receiver_profile.py',
         'receiver_registry.py', 'gnss_rf_model.pkl', 'gnss_lstm_vae.pth', 'gnss_kinematic_model.pkl',
         'models/texbat_grid_profile.json')


def evaluate():
    torch.set_num_threads(1)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frozen = {name: sha256_file(ROOT/name) for name in FILES}
    previous_path = ROOT/'validation_results'/'independent_real_20261023'/'results.json'
    previous = json.loads(previous_path.read_text(encoding='utf-8'))
    for name in ('navigation.py', 'fusion.py'):
        if sha256_file(OUTPUT/('baseline_'+name)) != previous['frozen_detector']['sha256'][name]:
            raise ValueError('Saved navigation baseline differs from historical CMU evaluation')
    baseline = {r['flight']: r for r in previous['results']}
    source = EXTERNAL/'independent_cmu'
    metadata = json.loads((source/'article_metadata.json').read_text())
    archive_path = source/'flights.zip'
    expected = next(r for r in metadata['files'] if r['name'] == 'flights.zip')
    if hashlib.md5(archive_path.read_bytes()).hexdigest() != expected['computed_md5']:
        raise ValueError('CMU archive differs from publisher checksum')
    parameters = pd.read_csv(source/'parameters.csv').set_index('flight')
    records = []
    with zipfile.ZipFile(archive_path) as archive:
        members = sorted((int(Path(n).stem), n) for n in archive.namelist() if n.endswith('.csv'))
        if len(members) != 209 or {i for i, _ in members} != set(parameters.index):
            raise ValueError('Expected every one of the 209 producer-listed records')
        for flight, member in members:
            raw = archive.read(member)
            digest = hashlib.sha256(raw).hexdigest()
            if digest != baseline[flight]['source_sha256']:
                raise ValueError('CMU flight bytes changed since baseline')
            state = new_state()
            state.use_dataset_mode = True
            assert _process_dataset_dataframe(pd.read_csv(io.BytesIO(raw)), f'CMU/{flight}.csv', state)
            decisions, detectors, rules, causes = Counter(), Counter(), Counter(), Counter()
            count = used = rejected_eligible = 0
            max_filter_measurement_difference = 0.
            while (row := get_next_dataset_row(state)) is not None:
                assert not state.ground_truth_available
                state.navigation_time = state.sample_time_s
                rule, reason, features = step_features(state, row[:4], state.sample_dt)
                state.vae_buffer = (state.vae_buffer+[features])[-10:]
                decision, *_ = get_hybrid_decision(rule, features, state, state.vae_buffer)
                lat, lon, _, final, nav_reason = process_navigation(state, *row[:4], True, .5, 40.,
                    dt=state.sample_dt, decision=(decision, reason))
                if not all(math.isfinite(x) for x in (lat, lon, state.position_sigma_m)):
                    raise ValueError('Non-finite navigation output')
                used += bool(state.gnss_measurement_used)
                rejected_eligible += decision == 'NORMAL' and not state.gnss_measurement_used
                decisions[final] += 1
                detectors[decision] += 1
                rules[rule] += 1
                if final != 'NORMAL':
                    causes[nav_reason.split('(')[0]] += 1
                max_filter_measurement_difference = max(max_filter_measurement_difference,
                    calculate_distance_km(lat, lon, row[0], row[1])*1000.)
                count += 1
                finish_frame(state, row[:4])
            assert count == baseline[flight]['rows']
            records.append(dict(flight=flight, rows=count, source_sha256=digest,
                historical_nominal_alarm_samples=baseline[flight]['nominal_alarm_samples'],
                nominal_alarm_samples=count-decisions['NORMAL'], gnss_measurement_used_samples=used,
                normal_decision_measurement_unused_samples=rejected_eligible,
                decisions=dict(decisions), detector_decisions=dict(detectors), rule_decisions=dict(rules),
                causes=dict(causes), max_filter_measurement_difference_m=max_filter_measurement_difference,
                difference_is_not_ground_truth_error=True))
            if len(records) % 20 == 0:
                print(f'CMU regression {len(records)}/209 completed', flush=True)
    if frozen != {name: sha256_file(ROOT/name) for name in FILES}:
        raise ValueError('Code/model changed during regression')
    rows = sum(r['rows'] for r in records)
    alarms = sum(r['nominal_alarm_samples'] for r in records)
    summary = dict(records=len(records), rows=rows,
        historical_nominal_alarm_samples=sum(r['historical_nominal_alarm_samples'] for r in records),
        nominal_alarm_samples=alarms, nominal_alarm_rate=alarms/rows,
        gnss_measurement_used_samples=sum(r['gnss_measurement_used_samples'] for r in records),
        normal_decision_measurement_unused_samples=sum(r['normal_decision_measurement_unused_samples'] for r in records),
        records_with_alarms=sum(r['nominal_alarm_samples'] > 0 for r in records))
    report = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), independent_test=False,
        protocol='Regression on known CMU records after navigation fix. No model training, '
                 'decision relabelling or archive flight selection. All 209 included. '
                 'Physical acceleration limit sets missing-IMU process uncertainty; NIS gate unchanged.',
        source_url=previous['source_url'], archive_sha256=sha256_file(archive_path),
        baseline_report_sha256=sha256_file(previous_path), frozen_before_after=frozen,
        summary=summary, results=records,
        limitations=['Nominal-operation assumption; no verified attack labels.',
          'Known development data, not renewed independent evidence.',
          'No C/N0/AV schema; RF/VAE not validated. No independent position truth.',
          'Filter-to-measurement difference is not absolute position accuracy.'])
    (OUTPUT/'cmu_regression.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary), flush=True)
    return report


if __name__ == '__main__':
    evaluate()
