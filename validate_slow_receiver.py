"""Compare unchanged old/new policy on labelled synthetic temporal probes.

Synthetic results are regression evidence, not a real attack success claim.
Previously published real attack scoring is run into a NEW output directory.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import torch

import receiver_profile
from dataset_loader import _process_dataset_dataframe, get_next_dataset_row
from ml_detection import get_hybrid_decision
from validation import new_state

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT/'validation_results'/'slow_attack_20261023'
BASELINE = OUTPUT/'baseline_receiver_profile.py'


def frame_for(case, seed):
    rng = np.random.default_rng(seed)
    t = np.arange(0., 420., .5)
    # Stationary normal noise, in the declared static receiver domain only.
    frame = pd.DataFrame(dict(timestamp_s=t, lat=38.+rng.normal(0., .15, len(t))/111320,
        lon=39.+rng.normal(0., .15, len(t))/111320, speed_kmh=0.,
        cn0=46.+rng.normal(0., .03, len(t)), receiver_clock_bias_m=100.+.023*t,
        receiver_clock_drift_m_s=-.00096))
    age = (t-50.).clip(min=0.)
    center, limits = receiver_profile.load_profile()[0]['center'], receiver_profile.load_profile()[0]['limits']
    if case.startswith('position_'):
        frame.lat += float(case.removeprefix('position_'))*age/111320
    elif case.startswith('clock_'):
        frame.loc[t >= 50., 'receiver_clock_drift_m_s'] = center[3]+float(case.removeprefix('clock_'))*limits[3]
    elif case == 'short_clock_transient':
        frame.loc[(t >= 50.) & (t < 55.), 'receiver_clock_drift_m_s'] = center[3]+1.5*limits[3]
    elif case == 'bounded_wander':
        frame.lat += np.sin(t/15.)*2./111320
    frame.attrs['source'] = dict(receiver_profile='texbat-grid-static-v1')
    return frame


def replay(frame):
    state = new_state()
    state.use_dataset_mode = True
    assert _process_dataset_dataframe(frame, 'synthetic-temporal-probe', state)
    times, alarms, paths = [], [], set()
    while (row := get_next_dataset_row(state)) is not None:
        # Isolate receiver monitoring from physical rules and navigation holds.
        get_hybrid_decision('NORMAL', [row[3], 0., 0., 0.], state)
        result = state.receiver_profile_result
        times.append(state.sample_time_s)
        alarms.append(result['detected'])
        paths.update(result.get('detection_paths', []))
    times, alarms = np.array(times), np.array(alarms)
    first = times[alarms & (times >= 50.)]
    return dict(alarm_samples=int(alarms.sum()), pre_onset_alarm_samples=int(alarms[times < 50.].sum()),
                post_onset_alarm_samples=int(alarms[times >= 50.].sum()),
                first_alarm_s=float(first[0]) if len(first) else None,
                latency_s=float(first[0]-50.) if len(first) else None, paths=sorted(paths))


def evaluate():
    torch.set_num_threads(1)
    old_result = json.loads((ROOT/'validation_results'/'texbat_timing_20261023'/'results.json').read_text())
    baseline_sha = hashlib.sha256(BASELINE.read_bytes()).hexdigest()
    if baseline_sha != old_result['frozen_detector']['receiver_profile.py']:
        raise ValueError('Baseline code does not match the previously evaluated version')
    spec = importlib.util.spec_from_file_location('baseline_receiver_policy', BASELINE)
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    cases = ('normal', 'bounded_wander', 'short_clock_transient',
             'position_0.05', 'position_0.1', 'position_0.15', 'clock_1.2', 'clock_1.5', 'clock_-1.5')
    probes = []
    try:
        for seed in (81001, 81002, 81003):
            for case in cases:
                frame = frame_for(case, seed)
                sys.modules['receiver_profile'] = baseline
                before = replay(frame.copy())
                sys.modules['receiver_profile'] = receiver_profile
                after = replay(frame.copy())
                probes.append(dict(case=case, seed=seed, synthetic=True, before=before, after=after))
    finally:
        sys.modules['receiver_profile'] = receiver_profile
    report = dict(protocol='Fixed synthetic cases; no real labels supplied to inference. '
                  'Only static receiver monitoring is isolated; no physical-rule or navigation claims.',
                  baseline_code_sha256=baseline_sha,
                  current_code_sha256=hashlib.sha256((ROOT/'receiver_profile.py').read_bytes()).hexdigest(),
                  new_constants=dict(sequential_limit=6., disjoint_window_s=10.,
                                     per_window_increment_cap=1., static_sigma_multiplier=6., static_hold_s=30.),
                  results=probes)
    (OUTPUT/'synthetic_comparison.json').write_text(json.dumps(report, indent=2)+'\n')
    import validate_texbat_timing as timing
    timing.OUTPUT = OUTPUT/'texbat'
    timing.evaluate()
    print('Slow receiver synthetic comparison and new real TEXBAT replay complete.')
    return report


if __name__ == '__main__':
    evaluate()
