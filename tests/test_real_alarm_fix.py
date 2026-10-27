
import numpy as np
import pandas as pd
import pytest

from dataset_adapters import zip_dataframe
from dataset_loader import _process_dataset_dataframe, get_next_dataset_row
from detection import run_firewall_rules
from fusion import get_fused_position
from ml_detection import get_hybrid_decision
from validation import State, new_state
from tests.test_dataset_adapters import zip_bytes


def test_held_gps_payload_is_coalesced_before_subframe_clock_sort():
    gps = ('Timpstemp,imgid,lat,lon,fix_type,vel_n_m_s,vel_e_m_s\n'
           '1000000,1,47,8,3,0,0\n1200000,2,47,8,3,0,0\n'
           '1199000,3,47.000001,8,3,1,0\n1232333,4,47.000001,8,3,1,0\n')
    with zip_bytes({'Log Files/OnboardGPS.csv': gps}) as archive:
        frame = zip_dataframe(archive)
    assert len(frame) == 2
    assert frame.timestamp_s.iloc[1] == pytest.approx(.199)
    assert frame.attrs['source']['held_gps_rows_removed'] == 2


def test_speed_uncertainty_removes_noise_alarm_but_not_large_attack():
    state = new_state()
    state.prev_speed = 0.
    state.speed_accuracy_m_s = state.previous_speed_accuracy_m_s = 1.
    label, _ = run_firewall_rules(state, state.prev_lat, state.prev_lon, 45., 7.2,
                                  45., .5, 40., 45., dt=.03)
    assert state.acceleration > 60. and state.acceleration_lower_bound == 0.
    assert label == 'NORMAL'
    label, reason = run_firewall_rules(state, state.prev_lat, state.prev_lon, 45., 250.,
                                      45., .5, 40., 45., dt=.2)
    assert label == 'SPOOFING' and 'İvme' in reason


@pytest.mark.parametrize('uncertainty', [float('nan'), float('inf'), -1., 0.])
def test_invalid_speed_accuracy_never_suppresses_a_real_acceleration_violation(uncertainty):
    state = new_state()
    state.speed_accuracy_m_s = state.previous_speed_accuracy_m_s = uncertainty
    label, reason = run_firewall_rules(state, state.prev_lat, state.prev_lon, 45., 250.,
                                      45., .5, 40., 45., dt=.2)
    assert label == 'SPOOFING' and 'İvme' in reason


def test_reported_position_noise_changes_gate_without_accepting_jump():
    state = new_state()
    state.prev_speed = 0.
    state.horizontal_accuracy_m = 5.
    get_fused_position(state, state.prev_lat, state.prev_lon, 0, 0)
    ekf = state.ekf_filter
    # Avoid relying on the intentionally broad initialization covariance.
    ekf.P *= .01
    get_fused_position(state, state.prev_lat+3/111320, state.prev_lon, 0, 0)
    assert state.gnss_measurement_used
    get_fused_position(state, state.prev_lat+.1, state.prev_lon, 0, 0)
    assert not state.gnss_measurement_used


@pytest.fixture
def profile(monkeypatch):
    import receiver_profile
    bounds = dict(schema=receiver_profile.PROFILE_ID, features=list(receiver_profile.FEATURES),
                  center=[0., 0., 0., 0.], limits=[.2, .3, 1., .03], position_sigma_m=2.,
                  window_s=10., warmup_s=30.)
    monkeypatch.setattr(receiver_profile, 'load_profile', lambda: (bounds, 'test-profile'))
    return bounds


def run_receiver_case(change=None):
    frame = pd.DataFrame(dict(timestamp_s=np.arange(0., 80., .5), lat=38., lon=39.,
        speed_kmh=0., cn0=46., receiver_clock_bias_m=100., receiver_clock_drift_m_s=0.))
    if change:
        change(frame)
    frame.attrs['source'] = dict(receiver_profile='texbat-grid-static-v1')
    state = new_state()
    state.use_dataset_mode = True
    _process_dataset_dataframe(frame, 'case', state)
    outputs, statuses = [], []
    while (row := get_next_dataset_row(state)) is not None:
        rule, _ = run_firewall_rules(state, row[0], row[1], row[3], row[2],
                                    45., .5, 40., 45., dt=state.sample_dt)
        outputs.append(get_hybrid_decision(rule, [row[3], 0., 0., 0.], state)[0])
        statuses.append(state.receiver_profile_result['status'])
    return outputs, statuses


def test_normal_receiver_and_marginal_single_clock_departure_are_not_attack(profile):
    def noise(frame):
        frame.receiver_clock_bias_m = 100.+frame.timestamp_s*.32
    outputs, statuses = run_receiver_case(noise)
    assert set(outputs) == {'NORMAL'}
    assert 'advisory' in statuses and 'warming_up' in statuses


def test_strong_clock_pull_is_still_detected_after_confirmation(profile):
    def attack(frame):
        frame.loc[frame.timestamp_s >= 40., 'receiver_clock_drift_m_s'] = .2
    outputs, statuses = run_receiver_case(attack)
    assert set(outputs[:80]) == {'NORMAL'}
    assert any(value != 'NORMAL' for value in outputs[80:90])
    assert 'alarm' in statuses


def test_coordinate_drift_and_rf_change_form_two_evidence_groups(profile):
    def attack(frame):
        delta = (frame.timestamp_s-40.).clip(lower=0)
        frame.lat += .5*delta/111320
        frame.cn0 += delta*.2
    outputs, _ = run_receiver_case(attack)
    assert set(outputs[:80]) == {'NORMAL'}
    assert any(value != 'NORMAL' for value in outputs[100:])


def test_profile_does_not_block_immediate_jamming_during_warmup(profile):
    outputs, statuses = run_receiver_case(lambda frame: frame.__setitem__('cn0', 10.))
    assert outputs[0] == 'JAMMING'
    assert statuses[0] == 'warming_up'


def test_missing_calibration_is_explicit_and_physical_rules_continue(monkeypatch):
    import receiver_profile
    def missing():
        raise FileNotFoundError('missing profile')
    monkeypatch.setattr(receiver_profile, 'load_profile', missing)
    outputs, statuses = run_receiver_case(lambda frame: frame.__setitem__('cn0', 10.))
    assert outputs[0] == 'JAMMING' and set(statuses) == {'unavailable'}


def test_no_uncertainty_or_receiver_state_leaks_into_a_new_dataset():
    state = State(speed_accuracy_m_s=9., previous_speed_accuracy_m_s=9.,
                  horizontal_accuracy_m=99., receiver_profile_monitor='old')
    _process_dataset_dataframe(pd.DataFrame(dict(lat=[38.], lon=[39.], speed_kmh=[0.])),
                               'new.csv', state)
    assert state.receiver_profile_name is None
    assert 'horizontal_accuracy_m' not in state and 'receiver_profile_monitor' not in state


def test_unknown_grid_receiver_is_not_silently_assigned_the_static_model():
    from dataset_adapters import texbat_navsol
    from tests.test_dataset_adapters import nav_fixture
    frame = texbat_navsol(nav_fixture())
    assert frame.attrs['source']['receiver_profile'] == 'grid-unvalidated'
    state = new_state()
    state.use_dataset_mode = True
    _process_dataset_dataframe(frame, 'unknown.mat', state)
    get_next_dataset_row(state)
    get_hybrid_decision('JAMMING', [10., 0., 0., 0.], state)
    assert state.receiver_profile_result['status'] == 'unavailable'
    assert not state.receiver_profile_result['available']
