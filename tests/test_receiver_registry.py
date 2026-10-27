"""Receiver-specific calibration, identity isolation and acquisition coverage."""
import copy
import json

import numpy as np
import pandas as pd
import pytest

import receiver_registry as registry
from dataset_loader import _process_dataset_dataframe, get_next_dataset_row, load_dataset_from_local_path
from ml_detection import get_hybrid_decision
from receiver_profile import receiver_decision
from validation import new_state
from tests.test_real_alarm_fix import profile as profile_fixture  # noqa: F401 - pytest fixture


def normal_frame(receiver='receiver-a', motion='static', session='calibration', seed=100):
    rng = np.random.default_rng(seed)
    t = np.arange(0., 180., .5)
    frame = pd.DataFrame(dict(timestamp_s=t, lat=38.+rng.normal(0., .05, len(t))/111320,
        lon=39., speed_kmh=0., cn0=46.+rng.normal(0., .01, len(t)),
        receiver_clock_bias_m=100.+.02*t, receiver_clock_drift_m_s=.02,
        receiver_id=receiver, receiver_motion=motion, session_id=session))
    if motion == 'moving':
        frame.lat += t*10./111320
        frame.speed_kmh = 36.
    return frame


@pytest.fixture
def installed(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, 'PROFILE_DIR', tmp_path/'profiles')
    first, second = tmp_path/'cal.csv', tmp_path/'val.csv'
    normal_frame().to_csv(first, index=False)
    normal_frame(session='validation', seed=200).to_csv(second, index=False)
    calibrated = registry.calibrate(first, second, receiver_id='receiver-a', profile_id='receiver-a-static',
        motion='static', trusted_normal=True, warmup_s=10.)
    registry.save_profile(calibrated)
    return calibrated, first, second


def replay(frame):
    state = new_state()
    state.use_dataset_mode = True
    _process_dataset_dataframe(frame, 'registry-case', state)
    results = []
    while (row := get_next_dataset_row(state)) is not None:
        decision = get_hybrid_decision('NORMAL', [row[3], 0., 0., 0.], state)[0]
        results.append((state.sample_time_s, decision, dict(state.receiver_profile_result)))
    return state, results


def test_separate_normal_sessions_calibrate_and_auto_match_exact_receiver(installed):
    calibrated, _, _ = installed
    assert calibrated['validation']['status'] == 'passed'
    state, results = replay(normal_frame(session='deployment', seed=300))
    assert state.receiver_profile_name == 'receiver:receiver-a-static'
    assert state.ml_source == 'RECEIVER_PROFILE'
    assert results[19][2]['status'] == 'warming_up'
    assert results[20][2]['fully_assessed']
    assert all(decision == 'NORMAL' for _, decision, _ in results)


def test_identity_motion_and_ambiguous_profile_are_not_guessed(installed):
    state, results = replay(normal_frame(receiver='receiver-b'))
    assert state.receiver_profile_name == 'receiver-unvalidated'
    assert all(not r['available'] for _, _, r in results)
    frame = normal_frame(motion='moving')
    frame['receiver_profile_id'] = 'receiver-a-static'
    with pytest.raises(ValueError, match='identity/motion'):
        replay(frame)
    clone = copy.deepcopy(installed[0])
    clone['profile_id'] = 'second-profile'
    registry.save_profile(clone)
    with pytest.raises(ValueError, match='Multiple receiver profiles'):
        replay(normal_frame())
    frame = normal_frame()
    frame['receiver_profile_id'] = 'receiver-a-static'
    assert replay(frame)[0].receiver_profile_name == 'receiver:receiver-a-static'


def test_wrong_profile_runtime_identity_and_missing_observables_fail_closed(installed):
    state, _ = replay(normal_frame())
    state.receiver_identity['receiver_id'] = 'receiver-b'
    assert not receiver_decision(state, 46.)['available']
    state.receiver_identity['receiver_id'] = 'receiver-a'
    state.receiver_observables = {}
    result = receiver_decision(state, 46.)
    assert not result['available'] and 'receiver_profile_monitor' not in state
    # Physical rules remain authoritative even if profile unavailable.
    assert get_hybrid_decision('JAMMING', [10., 0., 0., 0.], state)[0] == 'JAMMING'


def test_moving_receiver_uses_clock_rf_without_static_position_assumption(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, 'PROFILE_DIR', tmp_path/'profiles')
    first, second = tmp_path/'cal.csv', tmp_path/'val.csv'
    normal_frame(motion='moving').to_csv(first, index=False)
    normal_frame(motion='moving', session='validation', seed=200).to_csv(second, index=False)
    with pytest.raises(ValueError, match='documented position_sigma_m'):
        registry.calibrate(first, second, receiver_id='receiver-a', profile_id='moving-a',
            motion='moving', trusted_normal=True)
    calibrated = registry.calibrate(first, second, receiver_id='receiver-a', profile_id='moving-a',
        motion='moving', trusted_normal=True, position_sigma_m=2.)
    assert calibrated['enabled_features'] == [False, True, True, True]
    registry.save_profile(calibrated)
    state, results = replay(normal_frame(motion='moving', session='deployment', seed=300))
    assert state.receiver_profile_monitor.anchor is None
    assert all(decision == 'NORMAL' for _, decision, _ in results)
    assert results[-1][2]['static_displacement_m'] is None


def test_static_position_only_receiver_does_not_fabricate_clock_or_cn0(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, 'PROFILE_DIR', tmp_path/'profiles')
    frames = [normal_frame(), normal_frame(session='validation', seed=200)]
    paths = [tmp_path/'cal.csv', tmp_path/'val.csv']
    for frame, path in zip(frames, paths):
        frame.drop(columns=['cn0', 'receiver_clock_bias_m', 'receiver_clock_drift_m_s']).to_csv(path, index=False)
    calibrated = registry.calibrate(*paths, receiver_id='receiver-a', profile_id='position-only',
        motion='static', trusted_normal=True)
    registry.save_profile(calibrated)
    frame = pd.read_csv(paths[1])
    frame.lat += (frame.timestamp_s-50.).clip(lower=0)*.5/111320
    state, results = replay(frame)
    assert not state.cn0_available
    assert any(decision != 'NORMAL' for _, decision, _ in results)
    assert results[-1][2]['enabled_features'] == ['position_rate_m_s']
    assert results[-1][2]['values'][1:] == [None]*3


def test_acquisition_checks_instantaneous_strong_clock_before_thirty_seconds(profile_fixture):  # noqa: F811 - pytest fixture parameter
    frame = normal_frame().drop(columns=['receiver_id', 'receiver_motion'])
    frame.receiver_clock_drift_m_s = .2
    frame.attrs['source'] = dict(receiver_profile='texbat-grid-static-v1')
    _, results = replay(frame)
    alarm = next(row for row in results if row[1] != 'NORMAL')
    assert alarm[0] < 3.
    assert alarm[2]['fully_assessed'] is False
    assert alarm[2]['detection_paths'] == ['startup_strong_clock']
    assert alarm[2]['assessed_features'] == ['reported_clock_drift_m_s']
    assert 'position_rate_m_s' in alarm[2]['pending_features']


def test_failed_validation_is_not_installed_and_never_changes_calibration_bounds(installed, tmp_path):
    calibrated, first, _ = installed
    changed = normal_frame(session='validation-new', seed=200)
    changed.lat += changed.timestamp_s*.5/111320
    path = tmp_path/'bad-validation.csv'
    changed.to_csv(path, index=False)
    failed = registry.calibrate(first, path, receiver_id='receiver-a', profile_id='failed',
        motion='static', trusted_normal=True, warmup_s=10.)
    assert failed['validation']['status'] == 'failed'
    assert failed['center'] == calibrated['center'] and failed['limits'] == calibrated['limits']
    with pytest.raises(ValueError, match='not passed'):
        registry.save_profile(failed)
    assert not (registry.PROFILE_DIR/'failed.json').exists()


def test_attestation_same_session_attack_labels_and_overwrite_are_rejected(installed, tmp_path):
    calibrated, first, second = installed
    kwargs = dict(receiver_id='receiver-a', profile_id='test', motion='static')
    with pytest.raises(ValueError, match='attestation'):
        registry.calibrate(first, second, **kwargs)
    with pytest.raises(ValueError, match='separate sessions'):
        registry.calibrate(first, first, trusted_normal=True, **kwargs)
    attack = normal_frame(session='different')
    attack['attack_label'] = 'spoofing'
    attack.to_csv(tmp_path/'attack.csv', index=False)
    with pytest.raises(ValueError, match='Attack-labelled'):
        registry.calibrate(first, tmp_path/'attack.csv', trusted_normal=True, **kwargs)
    with pytest.raises(FileExistsError):
        registry.save_profile(calibrated)
    with pytest.raises(ValueError, match='Profile id'):
        registry.load_registered_profile('../other')


def test_bad_identity_load_does_not_replace_current_dataset(installed, tmp_path):
    state, _ = replay(normal_frame())
    old_frame = state.dataset_df
    frame = normal_frame()
    frame.loc[20:, 'receiver_id'] = 'different-receiver'
    path = tmp_path/'mixed.csv'
    frame.to_csv(path, index=False)
    assert not load_dataset_from_local_path(str(path), state)
    assert state.dataset_df is old_frame
    assert 'constant' in state.dataset_error


def test_registry_profile_change_resets_observation_history(installed):
    calibrated, _, _ = installed
    state, _ = replay(normal_frame())
    old_monitor = state.receiver_profile_monitor
    path = registry.PROFILE_DIR/'receiver-a-static.json'
    changed = copy.deepcopy(calibrated)
    changed['warmup_s'] = 11.
    path.write_text(json.dumps(changed), encoding='utf-8')
    result = receiver_decision(state, 46.)
    assert state.receiver_profile_monitor is not old_monitor
    assert result['status'] == 'warming_up'


@pytest.mark.parametrize('field,value', [('calibration', None), ('validation', []),
    ('enabled_features', [True, True]), ('motion', 'unknown'), ('warmup_s', 0.)])
def test_corrupt_profiles_are_not_applied(installed, field, value):
    data = copy.deepcopy(installed[0])
    data[field] = value
    with pytest.raises(ValueError):
        registry.validate_profile(data)


def test_moving_receiver_without_clock_or_rf_cannot_be_calibrated(tmp_path):
    paths = [tmp_path/'cal.csv', tmp_path/'val.csv']
    for session, path in zip(('calibration', 'validation'), paths):
        normal_frame(motion='moving', session=session).drop(
            columns=['cn0', 'receiver_clock_bias_m', 'receiver_clock_drift_m_s']).to_csv(path, index=False)
    with pytest.raises(ValueError, match='No usable receiver observables'):
        registry.calibrate(*paths, receiver_id='receiver-a', profile_id='unsupported',
                           motion='moving', trusted_normal=True, position_sigma_m=2.)


def test_direct_unknown_receiver_cannot_bypass_registry_and_use_legacy_profile():
    state = new_state()
    state.receiver_profile_name = 'receiver-unvalidated'
    result = receiver_decision(state, 46.)
    assert not result['available'] and 'legacy GRID calibration not applied' in result['reason']
