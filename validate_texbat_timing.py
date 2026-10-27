"""Frozen-detector, source-cited TEXBAT exposure and latency evaluation."""
from collections import Counter
from datetime import datetime, timezone
import json

from scipy.io import loadmat
import torch

from dataset_loader import load_dataset_from_local_path, get_next_dataset_row
from download_real_data import sha256_file
from ml_detection import get_hybrid_decision
from navigation import process_navigation
from real_data_catalog import ROOT, EXTERNAL
from texbat_timing import recording_clock, score_timeline, timeline, OFFSETS
from validation import new_state, step_features, finish_frame

OUTPUT = ROOT/'validation_results'/'texbat_timing_20261023'
FROZEN_FILES = ('detection.py', 'fusion.py', 'navigation.py', 'ml_detection.py',
                'features.py', 'receiver_profile.py', 'config.py', 'dataset_adapters.py',
                'code_carrier.py', 'models/grid_cmc_profile.json',
                'models/texbat_grid_profile.json', 'gnss_rf_model.pkl', 'gnss_lstm_vae.pth')


def evaluate():
    torch.set_num_threads(1)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frozen = {name: sha256_file(ROOT/name) for name in FROZEN_FILES}
    results, clock_origins = [], {}
    for scenario in ('cleanStatic', 'ds2', 'ds3', 'ds7'):
        path = EXTERNAL/'texbat'/scenario/'navsol.mat'
        clocks, alignment = recording_clock(loadmat(path), loadmat(path.with_name('channel.mat')))
        clock_origins[scenario] = alignment['ort_minus_rrt_s']
        state = new_state()
        state.use_dataset_mode = True
        if not load_dataset_from_local_path(str(path), state):
            raise ValueError(state.get('dataset_error'))
        if len(clocks) != len(state.dataset_df):
            raise ValueError('Navigation rows do not match the recording-clock mapping')
        traces, statuses = [], Counter()
        while (row := get_next_dataset_row(state)) is not None:
            # Inference never receives timeline labels or attack start times.
            assert not state.ground_truth_available
            state.navigation_time = state.sample_time_s
            rule, reason, features = step_features(state, row[:4], state.sample_dt)
            state.vae_buffer = (state.vae_buffer+[features])[-10:]
            decision, _, _, _ = get_hybrid_decision(rule, features, state, state.vae_buffer)
            f_lat, f_lon, _, final, _ = process_navigation(state, *row[:4], True, .5, 40.,
                dt=state.sample_dt, decision=(decision, reason))
            status = state.receiver_profile_result['status']
            statuses[status] += 1
            traces.append(dict(recording_s=float(clocks[state.dataset_index-1]),
                playback_s=state.sample_time_s, detector_alarm=decision != 'NORMAL',
                navigation_alarm=final != 'NORMAL', receiver_status=status))
            finish_frame(state, row[:4])
        import pandas as pd
        pd.DataFrame(traces).to_csv(OUTPUT/f'{scenario}_predictions.csv', index=False)
        primary = timeline(scenario)
        scored = {layer: score_timeline(clocks, [x[layer+'_alarm'] for x in traces], primary)
                  for layer in ('detector', 'navigation')}
        alternative = None
        if scenario == 'ds7':
            alt = timeline('ds7', 'afit')
            alternative = dict(timeline=alt, scores={layer: score_timeline(clocks,
                [x[layer+'_alarm'] for x in traces], alt) for layer in ('detector', 'navigation')})
        results.append(dict(scenario=scenario, samples=len(traces),
            input_sha256={name: sha256_file(path.with_name(name)) for name in ('navsol.mat', 'channel.mat')},
            alignment=alignment, primary_timeline=primary, scores=scored,
            alternative_timing=alternative, receiver_status_counts=dict(statuses),
            right_censored_at_last_available_navigation=True))
        print(scenario, json.dumps(scored['detector']), flush=True)
    # Independently cross-check the clock origins against published sample offsets.
    offset_errors = {name: clock_origins[name]-clock_origins['cleanStatic']-OFFSETS[name]
                     for name in clock_origins}
    if any(abs(error) > .001 for error in offset_errors.values()):
        raise ValueError('Local recording origins conflict with published Table 1 offsets')
    if any(sha256_file(ROOT/name) != value for name, value in frozen.items()):
        raise ValueError('Detector changed during the evaluation')
    docs = EXTERNAL/'texbat'/'timing_sources'
    report = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), frozen_detector=frozen,
        protocol='Labels applied after inference only. Boundary ±0.1s and activation-only interval excluded. '
                 'Primary recall is per observed navigation sample, not per episode. TTD requires a fresh '
                 'post-onset rising alarm; a pre-existing alarm is not detection. CMC limits are derived '
                 'from the cleanStatic 50–120s prefix; the fast and slow CMC paths are hashed with the adapter.',
        source_documents={name: sha256_file(docs/name) for name in
                          ('lemmenes_2016.pdf', 'humphreys_ds7_ds8_2016.pdf')},
        source_code={name: sha256_file(ROOT/name) for name in ('texbat_timing.py', 'validate_texbat_timing.py')},
        published_offset_crosscheck_errors_s=offset_errors, results=results,
        limitations=['DS7 primary/AFIT timing disagreement is retained with alternative scores.',
            'No raw-IQ receiver rerun; evaluation uses released GRID navigation/channel outputs.',
            'Detector was developed using these recordings; this is not an independent holdout.',
            'Scoring begins at first valid navigation output; missing startup is not counted as normal.',
            'AFIT documents a hardware-related code/carrier bias in DS2/DS3; detections may exploit this artifact.'])
    (OUTPUT/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    evaluate()
