"""Reproduce synthetic receiver onboarding and actual Streamlit load checks.

All new-device fixtures in this script are explicitly synthetic. Their
profiles are exported under validation_results, never installed as hardware.
"""
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import torch

import receiver_registry as registry
from dataset_loader import _process_dataset_dataframe, get_next_dataset_row
from ml_detection import get_hybrid_decision
from validation import new_state

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT/'validation_results'/'receiver_profiles_20261023'/'synthetic_contracts'


def make_frame(receiver_id, motion, session, seed, rf_only=False):
    rng = np.random.default_rng(seed)
    t = np.arange(0., 180., .5)
    data = pd.DataFrame(dict(timestamp_s=t, lat=38.+rng.normal(0., .05, len(t))/111320,
        lon=39., speed_kmh=0., cn0=46.+rng.normal(0., .01, len(t)),
        receiver_clock_bias_m=100.+.02*t, receiver_clock_drift_m_s=.02,
        receiver_id=receiver_id, receiver_motion=motion, session_id=session,
        synthetic=True))
    if motion == 'moving':
        data.lat += t*10./111320
        data.speed_kmh = 36.
    if rf_only:
        data = data.drop(columns=['receiver_clock_bias_m', 'receiver_clock_drift_m_s'])
    return data


def replay(frame):
    state = new_state()
    state.use_dataset_mode = True
    _process_dataset_dataframe(frame, 'SYNTHETIC receiver-contract probe', state)
    alarms, assessed, first = 0, 0, None
    while (row := get_next_dataset_row(state)) is not None:
        get_hybrid_decision('NORMAL', [row[3], 0., 0., 0.], state)
        result = state.receiver_profile_result
        if result['detected'] and first is None:
            first = state.sample_time_s
        alarms += bool(result['detected'])
        assessed += bool(result.get('fully_assessed'))
    return dict(alarms=alarms, first_alarm_s=first, fully_assessed=assessed,
                source=state.ml_source, motion=state.receiver_profile_result.get('motion'),
                static_anchor_created=state.receiver_profile_monitor.anchor is not None)


def evaluate():
    torch.set_num_threads(1)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    profiles = OUTPUT/'profiles'
    datasets, checks = [], []
    for receiver_id, motion, rf_only in (('synthetic-static-a', 'static', False),
                                         ('synthetic-moving-b', 'moving', True)):
        paths = []
        for session, seed in (('calibration', 201), ('validation', 202), ('deployment', 203)):
            path = OUTPUT/f'{receiver_id}-{session}.csv'
            make_frame(receiver_id, motion, session, seed, rf_only).to_csv(path, index=False)
            paths.append(path)
        profile_path = profiles/f'{receiver_id}.json'
        if not profile_path.exists():
            subprocess.run([sys.executable, str(ROOT/'calibrate_receiver.py'),
                '--normal', str(paths[0]), '--validation', str(paths[1]), '--receiver-id', receiver_id,
                '--profile-id', receiver_id, '--motion', motion, '--warmup-s', '10',
                '--position-sigma-m', '2', '--trusted-normal', '--output-dir', str(profiles)], check=True)
        profile = registry.validate_profile(json.loads(profile_path.read_text(encoding='utf-8')))
        assert profile['calibration']['source_sha256'] == __import__('hashlib').sha256(paths[0].read_bytes()).hexdigest()
        assert profile['validation']['source_sha256'] == __import__('hashlib').sha256(paths[1].read_bytes()).hexdigest()
        datasets.append((receiver_id, paths[2]))
    original_dir = registry.PROFILE_DIR
    registry.PROFILE_DIR = profiles
    try:
        for receiver_id, path in datasets:
            frame = pd.read_csv(path)
            normal = replay(frame)
            assert normal['alarms'] == 0
            attack = frame.copy()
            if receiver_id == 'synthetic-static-a':
                attack.receiver_clock_drift_m_s = .12
            else:
                attack.loc[attack.timestamp_s >= 50., 'cn0'] += 10.
            probe = replay(attack)
            assert probe['alarms'] > 0
            if receiver_id == 'synthetic-static-a':
                assert probe['first_alarm_s'] < 3.
            else:
                assert not probe['static_anchor_created']
            checks.append(dict(receiver_id=receiver_id, synthetic=True, normal=normal, attack_probe=probe))
        from streamlit.testing.v1 import AppTest
        ui = []
        for receiver_id, path in datasets:
            app = AppTest.from_file(str(ROOT/'main.py'), default_timeout=60).run()
            app.radio(key='veri_modu_radio').set_value('📂 Veri Seti Yükle').run()
            next(x for x in app.text_input if x.label == 'Tam dosya yolu').set_value(str(path))
            next(x for x in app.button if x.label == '📂 Yükle').click().run()
            assert not app.exception and not app.error
            assert app.session_state['ml_source'] == 'RECEIVER_PROFILE'
            assert app.session_state['receiver_identity']['receiver_id'] == receiver_id
            assert app.session_state['forensic_chain_valid']
            assert any('Alıcı edinimi:' in x.value for x in app.info)
            ui.append(dict(receiver_id=receiver_id, runtime_exceptions=0, errors=[], acquisition_coverage_visible=True))
    finally:
        registry.PROFILE_DIR = original_dir
    report = dict(synthetic_only=True, separate_normal_sessions=True, exported_not_installed=True,
                  checks=checks, ui=ui, limitations='Normal-session checks are not real hardware/attack validation.')
    (OUTPUT/'results.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('Two synthetic receiver contracts, CLI calibration, inference and UI checks passed.')


if __name__ == '__main__':
    evaluate()
