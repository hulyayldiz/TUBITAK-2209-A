"""Replay downloaded sources without fitting models or inventing ground truth."""
from collections import Counter
from datetime import datetime, timezone
import json
import math
import time
from pathlib import Path

import torch

from dataset_loader import get_next_dataset_row, load_dataset_from_local_path
from detection import calculate_metrics
from download_real_data import sha256_file
from ml_detection import get_hybrid_decision
from navigation import process_navigation
from real_data_catalog import ROOT, available_sources
from validation import finish_frame, new_state, step_features


def validate_sources(output=None):
    torch.set_num_threads(1)
    results = []
    for name, path in available_sources().items():
        state = new_state()
        state.use_dataset_mode = True
        if not load_dataset_from_local_path(str(path), state):
            raise ValueError(state.get('dataset_error'))
        counts, models, count, imu_count, cn0_count = Counter(), Counter(), 0, 0, 0
        receiver_statuses = Counter()
        start = time.perf_counter()
        while (row := get_next_dataset_row(state)) is not None:
            lat, lon, speed, cn0, _ = row
            state.navigation_time = state.sample_time_s
            state.acceleration = 0.
            rule, reason, features = step_features(state, row[:4], state.sample_dt)
            state.vae_buffer.append(features)
            state.vae_buffer = state.vae_buffer[-10:]
            final, _, _, _ = get_hybrid_decision(rule, features, state, state.vae_buffer)
            f_lat, f_lon, _, final, _ = process_navigation(state, lat, lon, speed, cn0,
                True, .5, 40., dt=state.sample_dt, decision=(final, reason))
            metrics = calculate_metrics(state, final, lat, lon, f_lat, f_lon)
            if not all(math.isfinite(value) for value in (f_lat, f_lon)):
                raise ValueError(f'Non-finite navigation at {count}')
            if not state.ground_truth_available and not all(math.isnan(x) for x in metrics[:5]):
                raise AssertionError('Unlabelled source generated accuracy statistics')
            counts[final] += 1
            models[state.ml_source] += 1
            if state.ml_source == 'TEXBAT_RECEIVER_PROFILE':
                receiver_statuses[state.receiver_profile_result['status']] += 1
            imu_count += bool(state.imu_data)
            cn0_count += state.cn0_available
            count += 1
            finish_frame(state, row[:4])
            if count % 10000 == 0:
                print(name, count, 'replayed', flush=True)
        result = dict(name=name, path=str(path.relative_to(ROOT)), input_sha256=sha256_file(path),
            rows_replayed=count, source=state.dataset_summary,
            cn0_observations=cn0_count, body_imu_observations=imu_count,
            output_decision_counts=dict(counts), ml_sources=dict(models),
            receiver_status_counts=dict(receiver_statuses),
            elapsed_s=round(time.perf_counter()-start, 3),
            accuracy=None, false_alarm_rate=None, position_rmse_m=None,
            limitation='No verified per-epoch attack labels or independent GNSS antenna position reference; '
                       'decision counts are not accuracy or false-alarm rates. Models not field-calibrated on these sources.')
        results.append(result)
        print(name, count, 'complete', dict(counts), flush=True)
    report = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        protocol='Full adapted-source replay; synthetic models unchanged; explicit cleanStatic-normal '
                 'calibrated static GRID profile where applicable. Continuation used for development; '
                 'not an independent field benchmark. No forensic log writes.',
        source_manifest_sha256=sha256_file(ROOT/'real_data_manifest.json'),
        code_sha256={name: sha256_file(ROOT/name) for name in
                     ('dataset_adapters.py', 'dataset_loader.py', 'validate_real_data.py',
                      'detection.py', 'ml_detection.py', 'navigation.py', 'features.py',
                      'fusion.py', 'receiver_profile.py')},
        model_sha256={name: sha256_file(ROOT/name) for name in
                      ('gnss_rf_model.pkl', 'gnss_lstm_vae.pth', 'models/texbat_grid_profile.json')},
        results=results)
    output = Path(output) if output is not None else ROOT/'validation_results'/'real_alarm_fix_20261023'
    output.mkdir(parents=True, exist_ok=True)
    (output/'replay_results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    validate_sources()
